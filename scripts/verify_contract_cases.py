"""Fetch + archive the official documents behind the D-05 contract cases and print the
sentences that state each expected value (evidence for VERIFIED). Needs
PITQUANT_SEC_USER_AGENT. Output: docs/d05_contract_evidence.json."""

from __future__ import annotations

import html
import io
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pdfplumber  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

A = "https://www.sec.gov/Archives/edgar/data/"
DOCS = {
    "US-SPLIT-AAPL-2014": (
        A + "320193/000119312514154883/d715379dex991.htm",
        [
            r"split[- ]adjusted basis[^.]{0,80}",
            r"seven[- ]for[- ]one[^.]{0,80}",
            r"7[- ]for[- ]1[^.]{0,80}",
        ],
    ),
    "US-SPLIT-AAPL-2020": (
        A + "320193/000032019320000060/a8-kexhibit991q3202062.htm",
        [r"split[- ]adjusted basis[^.]{0,80}", r"four[- ]for[- ]one[^.]{0,80}"],
    ),
    "US-REVSPLIT-C-2011": (
        A + "831001/000119312511131957/dex991.htm",
        [r"1-for-10[^.]{0,120}", r"split-adjusted basis[^.]{0,120}"],
    ),
    "US-SPINOFF-ABT-ABBV-2013": (
        A + "1800/000104746913000015/a2212294zex-99_1.htm",
        [r"one share of AbbVie[^.]{0,120}", r"distribution[^.]{0,160}"],
    ),
    "US-SPECIALDIV-MSFT-2004": (
        A + "789019/000119312504197513/d8k.htm",
        [r"special dividend[^.]{0,200}", r"\$3\.00[^.]{0,120}"],
    ),
    "US-CASHACQ-HNZ-2013": (
        A + "46640/000119312513258009/d555504dex991.htm",
        [r"\$72\.50[^.]{0,160}", r"(completed|completion)[^.]{0,160}"],
    ),
    "US-CASHACQ-HNZ-2013/25": (
        A + "46640/000087666113000400/ruleprovisionnotice.htm",
        [r"[^.]{0,120}"],
    ),
    "US-STOCKACQ-XTO-2010": (
        A + "868809/000095010310001867/dp18265_8k.htm",
        [r"0\.7098[^.]{0,160}", r"June 25, 2010[^.]{0,160}"],
    ),
    "US-STOCKACQ-XTO-2010/25": (
        A + "868809/000087666110000228/ruleprovisionnotice.htm",
        [r"[^.]{0,120}"],
    ),
    "ES-MERGER-BKIA-2021": (
        "https://www.caixabank.com/deployedfiles/caixabank_com/Estaticos/PDFs/"
        "Accionistasinversores/Informacion_General/"
        "20210319_Algarve-Anuncio-de-canje_con-firmas_v-final_limpia.pdf",
        [
            r"tipo de canje es de 0,6845[^.]{0,120}",
            r"Fecha de Canje será el último día[^.]{0,120}",
            r"[^.]{0,120}26 de marzo de 2021[^.]{0,80}",
        ],
    ),
    "ES-SPLIT-ITX-2014": (
        "https://www.cnmv.es/WebServices/VerDocumento/Ver?e=%2FlSbfe04j58P1DtZ5v+r2Lojc5caDacz"
        "WitwUsYwRmRQSRh0dt1K2vXNhAR3mLSV",
        [r"cinco acciones nuevas por cada acción antigua[^.]{0,80}"],
    ),
    "US-BANKRUPTCY-LEH-2008": (
        A + "806085/000110465908059632/a08-22764_48k.htm",
        [r"Chapter 11[^.]{0,200}", r"New York Stock Exchange[^.]{0,200}", r"delist[^.]{0,200}"],
    ),
}


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("set PITQUANT_SEC_USER_AGENT", file=sys.stderr)
        return 2
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    out = {}
    with make_session_factory(make_engine(s.database.url))() as ses:
        for case, (url, pats) in DOCS.items():
            body = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": ua}), timeout=60
            ).read()
            is_pdf = body[:5] == b"%PDF-"
            row = archive_document(
                ses,
                store,
                provider="CONTRACT_EVIDENCE",
                source_identifier=url,
                data=body,
                mime_type="application/pdf" if is_pdf else "text/html",
                parser_version="d05-evidence-1",
            )
            if is_pdf:
                with pdfplumber.open(io.BytesIO(body)) as doc:
                    raw = " ".join(pg.extract_text() or "" for pg in doc.pages)
            else:
                raw = html.unescape(re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace")))
            text = re.sub(r"\s+", " ", raw)
            hits = []
            for p in pats:
                hits += [m.group(0).strip()[:220] for m in re.finditer(p, text, flags=re.I)][:3]
            out[case] = {"url": url, "sha256": row.sha256, "excerpts": hits[:6]}
            time.sleep(0.3)
        ses.commit()
    (ROOT / "docs" / "d05_contract_evidence.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    )
    for k, v in out.items():
        print("==", k)
        for h in v["excerpts"]:
            print("   ", h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
