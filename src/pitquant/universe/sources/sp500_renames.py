# ruff: noqa: E501
"""Name / ticker change STATEMENTS of archived S&P DJI releases (ADR-0035).

An official S&P release sometimes says, in the same breath as an index change, that a constituent is being renamed or that a company «will
remain in the S&P 500» under a new name («Delphi Automotive plc (NYSE: DLPH), to be renamed Aptiv plc …. The renamed Aptiv plc will remain in the
S&P 500»). That sentence is PRIMARY evidence that the index slot continues under the new name; it does not prove the CUSIP transition date.
Only these closed sentence forms are parsed (no free-text similarity); every statement keeps its excerpt so it can be audited.

* ``TO_BE_RENAMED``      «X (EXCH: T), to be renamed Y [and trade under new symbol Z]»
* ``CHANGE_ITS_NAME``    «Post …, X will remain in the S&P 500 … It will change its name to Y» / «X will change its name [and ticker] to Y»
* ``NAME_AND_TICKER``    «X will have a name and ticker change to [«new»] Y (EXCH: T)»
* ``SURVIVING_ENTITY``   «X will be treated as the surviving entity. Post merger, the company will be named Y … ticker symbol «Z»»
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

RENAMES_PARSER_VERSION = "sp500-renames-1"

_NM = r"[A-Z][\w&.'’\-]*(?:\s+[A-Za-z0-9][\w&.'’\-]*){0,5}"  # a company name: capitalised words, at most 6 tokens
_EX = r"\((?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*\)"

_TO_BE = re.compile(
    rf"(?P<old>{_NM})\s*\((?:[A-Za-z][A-Za-z /]{{1,18}})\s*:\s*(?P<ot>[A-Z][A-Za-z0-9.\-]{{0,9}})\s*\)\s*,\s*to be renamed\s+(?P<new>{_NM}?)(?:\s+and\s+trade under new symbol\s+(?P<nt>[A-Z]{{1,6}}))?\s*[,.]"
)
_REMAIN_IT = re.compile(
    rf"(?:Post[- ][a-z\- ]+,\s*)?(?P<old>{_NM}) will remain in the S&P 500(?: (?:&|and) 100)?(?: ind(?:ex|ices))?[^.]{{0,60}}\.\s+It will change its name (?:and (?:its )?ticker(?: symbol)? )?to\s+(?P<new>{_NM}?)(?:\s*{_EX})?(?:\s+and its ticker symbol to\s+(?P<nt>[A-Z]{{1,6}}))?\s*\."
)
_CHANGE_NAME = re.compile(
    rf"(?:Post[- ][a-z\- ]+,\s*)?(?:the [\"“]old[\"”] )?(?P<old>{_NM}) will change its name (?:and (?:its )?ticker(?: symbol)? )?to\s+(?P<new>{_NM}?)(?:\s*{_EX})?(?:\s+and its ticker symbol to\s+(?P<nt>[A-Z]{{1,6}}))?\s*(?:,|\.)"
)
_NAME_TICKER = re.compile(
    rf"(?P<old>{_NM}) will have a name (?:and ticker )?change to\s+[\"“]?(?:new)?[\"”]?\s*(?P<new>{_NM}?)\s*{_EX}"
)
_SURVIVING = re.compile(
    rf"(?P<old>{_NM}) will be treated as the surviving entity\.\s+Post[- ]merger, the company will be named\s+(?P<new>{_NM}?)\s+and will trade[^.]{{0,80}}?ticker symbol [\"“](?P<nt>[A-Z]{{1,6}})[\"”]"
)


@dataclass(frozen=True)
class RenameStatement:
    kind: str
    old_name: str
    new_name: str
    old_ticker: str | None
    new_ticker: str | None
    remains_in_index: bool
    excerpt: str
    announced_on: date


def _clean(n: str) -> str:
    n = re.sub(r"^.*?PRNewswire\s*/\s*--\s*", "", n.strip())
    n = re.sub(r"^(?:Post[- ][a-z\- ]+,\s*)", "", n)
    n = re.sub(r"^.*\bconstituents?\s+", "", n)
    n = re.sub(r"^Post[- ][a-z]+\s+", "", n)
    n = re.sub(r"[\"“”]", "", n).strip(" ,.")
    n = re.sub(r"^(?:the\s+)?(?:old|new)\s+", "", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def parse_rename_statements(text: str, announced: date) -> list[RenameStatement]:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"S&\s+P", "S&P", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    out: list[RenameStatement] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, m: re.Match[str], ot: str | None, nt: str | None) -> None:
        old, new = _clean(m.group("old")), _clean(m.group("new"))
        if not old or not new or old.lower() == new.lower() or old.lower() == "it" or "S&P" in old:
            return  # a pronoun / a sentence fragment is not a company
        key = (kind, old.lower(), new.lower())
        if key in seen:
            return
        seen.add(key)
        window = text[m.start() : m.end() + 400]
        remains = kind == "CHANGE_ITS_NAME" or bool(
            re.search(
                rf"(?:The renamed )?{re.escape(new)}[^.]{{0,30}}(?:will|to) remain in the S&P 500",
                window,
            )
        )
        out.append(
            RenameStatement(
                kind,
                old,
                new,
                ot.upper() if ot else None,
                nt.upper() if nt else None,
                remains,
                text[max(0, m.start() - 20) : m.end() + 200][:420],
                announced,
            )
        )

    for m in _TO_BE.finditer(text):
        add("TO_BE_RENAMED", m, m.group("ot"), m.group("nt"))
    for m in _REMAIN_IT.finditer(text):
        add("CHANGE_ITS_NAME", m, None, m.groupdict().get("nt"))
    for m in _CHANGE_NAME.finditer(text):
        add("CHANGE_ITS_NAME", m, None, m.groupdict().get("nt"))
    for m in _NAME_TICKER.finditer(text):
        add("NAME_AND_TICKER", m, None, m.groups()[-1])
    for m in _SURVIVING.finditer(text):
        add("SURVIVING_ENTITY", m, None, m.group("nt"))
    return out
