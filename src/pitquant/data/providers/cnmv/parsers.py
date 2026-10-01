"""Parsers for CNMV public pages and IPP XBRL (no network here).

* ``parse_ifi_list``: an issuer's list of periodic reports (``ListaIFI.aspx?nif=``).
* ``parse_ifi_detail``: one report's page (``DetalleIFIAlDia?nreg=``) — period, CIF,
  «Publicación inicial» (DATE ONLY), the modifications table (dates) and the XBRL link.
* ``parse_ipp_xbrl``: numeric facts of an IPP XBRL instance. IPP facts are dimensional;
  dimensions that only say "current/previous period" are dropped (the dates already fix
  the period) so the same economic fact lines up across reports — a later report's
  comparative column becomes a later VERSION of the earlier fact (restatement detection).
"""

from __future__ import annotations

import html
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date

from pitquant.core.errors import DataQualityError

PARSER_VERSION = "cnmv-ipp-3"
_XBRLI = "{http://www.xbrl.org/2003/instance}"
_XBRLDI = "{http://xbrl.org/2006/xbrldi}"


def _d(s: str) -> date:
    dd, mm, yy = s.strip().split("/")
    return date(int(yy), int(mm), int(dd))


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


@dataclass(frozen=True)
class IfiListEntry:
    nreg: str
    published: date
    label: str


def parse_ifi_list(page: bytes) -> list[IfiListEntry]:
    s = page.decode("utf-8", errors="replace")
    out = []
    for row in re.findall(r"<tr.*?</tr>", s, flags=re.S):
        n = re.search(r"nreg=(\d+)", row)
        if not n:
            continue
        t = _text(row)
        m = re.match(r"(\d{2}/\d{2}/\d{4})\s+(.*)", t)
        if m:
            out.append(IfiListEntry(n.group(1), _d(m.group(1)), m.group(2)))
    return out


@dataclass(frozen=True)
class Modification:
    section: str
    description: str
    on: date


@dataclass(frozen=True)
class IfiDetail:
    company: str
    cif: str
    period_start: date
    period_end: date
    semester: str | None
    fiscal_year: int
    publication_date: date
    modifications: tuple[Modification, ...]
    xbrl_path: str | None  # relative link to the XBRL download (session token)
    publication_time: str | None = None  # never present on this page (DATE_ONLY)
    documents: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def last_modification(self) -> date | None:
        return max((m.on for m in self.modifications), default=None)


def _span(s: str, suffix: str) -> str | None:
    m = re.search(rf'id="[^"]*{suffix}"[^>]*>([^<]*)<', s)
    return m.group(1).strip() if m else None


def parse_ifi_detail(page: bytes) -> IfiDetail:
    s = page.decode("utf-8", errors="replace")
    company = _span(s, "lblNombreEntidad")
    start, end = _span(s, "_lblInicioPeriodo"), _span(s, "_lblFinPeriodo")
    pub, cif, year = _span(s, "_lblPublicacion"), _span(s, "_lblNIF"), _span(s, "_lblEjercicio")
    if not (company and start and end and pub and cif and year):
        raise DataQualityError("CNMV IFI page layout not recognised (missing header fields)")
    mods: list[Modification] = []
    panel = re.search(r'panelModificaciones".*?</table>', s, flags=re.S)
    if panel:
        for row in re.findall(r"<tr>(.*?)</tr>", panel.group(0), flags=re.S):
            cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
            if len(cells) == 3 and re.fullmatch(r"\d{2}/\d{2}/\d{4}", cells[2]):
                mods.append(Modification(cells[0], cells[1], _d(cells[2])))
    xbrl = re.search(r'href="([^"]*descargaxbrlipp\.ashx\?t=[^"]+)"', s)
    docs = tuple(
        (html.unescape(t), html.unescape(u))
        for u, t in re.findall(r'href="([^"]*verdocumento/ver\?e=[^"]+)"[^>]*title="([^"]*)"', s)
    )
    return IfiDetail(
        company=html.unescape(company),
        cif=cif,
        period_start=_d(start),
        period_end=_d(end),
        semester=_span(s, "_lblSemestre"),
        fiscal_year=int(year),
        publication_date=_d(pub),
        modifications=tuple(mods),
        xbrl_path=html.unescape(xbrl.group(1)) if xbrl else None,
        documents=docs,
    )


# ───────────────────────────── IPP XBRL ─────────────────────────────

# Suffix that only positions a column relative to the report's own period. It is stripped;
# what remains (e.g. "IngresosOrdinariosClientesExternos") keeps its meaning. A member that
# is ONLY relative ("PeriodoActual", "AcumuladoAnterior") disappears with its axis.
_RELATIVE_SUFFIX = re.compile(
    r"((Periodo|Acumulado|Ejercicio)?(Actual|Anterior)|PeriodoCorriente)$"
)


@dataclass(frozen=True)
class IppFact:
    taxonomy: str  # family@version, e.g. "ipp_ge@2016-06-01"
    concept: str  # code + normalised dimensions, e.g. "I1205[ImportePorcentaje=Importe]"
    period_start: date | None
    period_end: date
    unit: str
    value: float
    decimals: str | None


def _short(qname: str) -> str:
    local = qname.split(":")[-1]
    return re.sub(r"(Eje|Miembro)$", "", local)


def parse_ipp_xbrl(data: bytes) -> list[IppFact]:
    root = ET.fromstring(data)
    contexts: dict[str, tuple[tuple[tuple[str, str], ...], date | None, date]] = {}
    for c in root.iter(f"{_XBRLI}context"):
        if c.find(f".//{_XBRLDI}typedMember") is not None:
            continue  # typed dimensions (free-text axes): not comparable, skipped
        dims = tuple(
            sorted(
                (axis, member)
                for m in c.iter(f"{_XBRLDI}explicitMember")
                for axis, member in [
                    (
                        _short(m.attrib["dimension"]),
                        _RELATIVE_SUFFIX.sub("", _short(m.text or "")),
                    )
                ]
                if member
            )
        )
        p = c.find(f"{_XBRLI}period")
        if p is None:
            continue
        inst = p.find(f"{_XBRLI}instant")
        s, e = p.find(f"{_XBRLI}startDate"), p.find(f"{_XBRLI}endDate")
        if inst is not None and inst.text:
            contexts[c.attrib["id"]] = (dims, None, date.fromisoformat(inst.text.strip()))
        elif s is not None and e is not None and s.text and e.text:
            contexts[c.attrib["id"]] = (
                dims,
                date.fromisoformat(s.text.strip()),
                date.fromisoformat(e.text.strip()),
            )
    units: dict[str, str] = {}
    for u in root.iter(f"{_XBRLI}unit"):
        ms = [m.text.split(":")[-1] for m in u.iter(f"{_XBRLI}measure") if m.text]
        units[u.attrib["id"]] = "/".join(ms) if ms else u.attrib["id"]
    out: dict[tuple[str, str, date | None, date, str], IppFact] = {}
    for el in root:
        ctx, unit = el.attrib.get("contextRef"), el.attrib.get("unitRef")
        if not ctx or not unit or ctx not in contexts or el.text is None:
            continue
        ns, _, local = el.tag[1:].partition("}") if el.tag.startswith("{") else ("", "", el.tag)
        if "cnmv.es/xbrl/ipp" not in ns:
            continue
        try:
            value = float(el.text.strip())
        except ValueError:
            continue
        dims, start, end = contexts[ctx]
        concept = local + ("[" + ",".join(f"{a}={b}" for a, b in dims) + "]" if dims else "")
        # family AND version (e.g. "ipp_ge@2016-06-01"): codes are only comparable within one
        # taxonomy version; cross-version linking would need an explicit mapping.
        family_version = ns.rstrip("/").split("/ipp/")[1].split("/")
        taxonomy = f"ipp_{family_version[0]}@{family_version[1]}"
        unit_name = units.get(unit, unit)
        key = (taxonomy, concept, start, end, unit_name)
        prev = out.get(key)
        if prev is not None and not math.isclose(prev.value, value, rel_tol=1e-9, abs_tol=0.5):
            raise DataQualityError(f"conflicting duplicate IPP fact {key}: {prev.value} vs {value}")
        out[key] = IppFact(
            taxonomy, concept, start, end, unit_name, value, el.attrib.get("decimals")
        )
    return list(out.values())
