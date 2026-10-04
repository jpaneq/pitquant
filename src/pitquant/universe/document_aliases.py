"""Explicit human-approved aliases scoped to an exact SEC document and raw string."""

VERSION = "document-typo-alias-v2"
PPG_ACCESSION = "0001193125-17-355427"
PPG_RAW = "PPoG Industries, Inc."
PPG_RESOLVED = "PPG Industries, Inc."


def document_name(raw_name: str, accession: str) -> str:
    if accession == PPG_ACCESSION and raw_name == PPG_RAW:
        return PPG_RESOLVED
    return raw_name
