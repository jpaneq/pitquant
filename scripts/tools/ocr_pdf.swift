// OCR of a scanned PDF with Apple Vision (macOS). Usage: ocr_pdf <file.pdf>
// Prints the recognised text of every page (Spanish + English), pages separated by \f.
import Foundation
import PDFKit
import Vision
import AppKit

guard CommandLine.arguments.count == 2, let doc = PDFDocument(url: URL(fileURLWithPath: CommandLine.arguments[1])) else {
    FileHandle.standardError.write("usage: ocr_pdf file.pdf\n".data(using: .utf8)!)
    exit(2)
}
var pages: [String] = []
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.5
    let size = NSSize(width: box.width * scale, height: box.height * scale)
    let img = page.thumbnail(of: size, for: .mediaBox)
    guard let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["es-ES", "en-US"]
    req.usesLanguageCorrection = true
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let lines = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    pages.append(lines.joined(separator: "\n"))
}
print(pages.joined(separator: "\u{0C}"))
