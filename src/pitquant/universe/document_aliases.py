"""Audited aliases scoped to an exact SEC document and parsed raw string."""

VERSION = "document-typo-alias-v3"
PPG_ACCESSION = "0001193125-17-355427"
PPG_RAW = "PPoG Industries, Inc."
PPG_RESOLVED = "PPG Industries, Inc."


def document_name(raw_name: str, accession: str) -> str:
    if accession == PPG_ACCESSION and raw_name == PPG_RAW:
        return PPG_RESOLVED
    if accession == "0001193125-16-777823":
        # Original HTML has ``Class A<BR>REIT(a)`` and ``NV<BR>Class A``.
        # Restore the line break before removing the schedule's REIT/footnote marker.
        # These are extraction defects, not changes in legal identity or share class.
        return {
            "CBRE Group, Inc. Class AREIT": "CBRE Group, Inc. Class A",
            "LyondellBasell Industries NVClass A": "LyondellBasell Industries NV Class A",
        }.get(raw_name, raw_name)
    return raw_name
