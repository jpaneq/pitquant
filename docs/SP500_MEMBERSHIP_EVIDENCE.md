# Evidencia de membresía S&P 500 (D-02, candidato construido desde fuentes públicas)

> Generado por `scripts/gen_sp500_evidence_report.py` (ADR-0025). **No es canónico**: la lista comunitaria sólo descubre;
> cada cambio necesita un comunicado de S&P (tier 1) o su copia en PRNewswire (tier 2). Ningún evento se corrige para
> que coincida con GitHub/Wikipedia.

## Resumen

```
discovery_events_2011_present        = 549   (filas del CSV: 323)
official_confirmed (tier 1 S&P)      = 88
official_republished_confirmed (t2)  = 2
date_tba                             = 2
conflicts                            = 32
unresolved                           = 110
discovery_only (sin evidencia)       = 315
coverage_pct                         = 16.4%
```

## Estados D-02

- `SP500_MEMBERSHIP_DISCOVERY_READY` = **true** (CSV archivado sha256 `591c9eb91b71af204f28cf3fb1e2f81483b8a336f2d5810313de21d4a23d845e`).
- `SP500_MEMBERSHIP_EVIDENCE_COVERAGE` = **16.4%** (90/549 eventos con evidencia oficial concordante).
- `SP500_MEMBERSHIP_CANONICAL_READY` = **false**: (1) `CURRENT_ANCHOR_BLOCKED` (la página de S&P DJI devuelve 403 y su `Full Constituents List` no se puede archivar automáticamente: sin ancla no hay reconstrucción hacia atrás ni comprobación de reversibilidad sobre datos reales), y (2) quedan eventos sin evidencia (ver gaps).

Primer evento sin confirmar: **2011-01-18**. Sin ancla actual no hay primera fecha reconstruible ni año completo reconstruible; con ancla, las fechas anteriores a ese evento dependerían de él y no podrían declararse canónicas (fail-closed).

## Documentos de evidencia

- Tier 1 `OFFICIAL_SPDJI` (press.spglobal.com): 206 cláusulas «will replace … in the S&P 500» parseadas.
- Tier 2 `OFFICIAL_REPUBLISHED` (PRNewswire vía Wayback): 20 cláusulas.
- El archivo de prensa de S&P Global sólo contiene comunicados de cambios de índice desde ~2014; PRNewswire sólo es localizable por el índice CDX de Wayback (2010–2011 sobre todo).

## Cobertura por año

| año | eventos discovery | confirmados | % |
|---|---|---|---|
| 2011 | 25 | 2 | 8% |
| 2012 | 25 | 1 | 4% |
| 2013 | 28 | 3 | 11% |
| 2014 | 19 | 7 | 37% |
| 2015 | 42 | 5 | 12% |
| 2016 | 36 | 10 | 28% |
| 2017 | 37 | 7 | 19% |
| 2018 | 34 | 7 | 21% |
| 2019 | 42 | 12 | 29% |
| 2020 | 35 | 3 | 9% |
| 2021 | 32 | 10 | 31% |
| 2022 | 35 | 10 | 29% |
| 2023 | 48 | 6 | 12% |
| 2024 | 34 | 2 | 6% |
| 2025 | 38 | 2 | 5% |
| 2026 | 39 | 3 | 8% |

## Universo

- Tickers distintos añadidos en eventos 2011+: 368; eliminados: 341; unión (sin ancla no se conoce la composición inicial): 576.
- Former constituents con eliminación confirmada oficialmente: 90.
- Resolución ticker → `security_id`: **no resuelta** (el Security Master sólo contiene AAPL y MSFT del S&P 500). Evidencia de membresía e identidad de la security son capas separadas.

## Comparación con el CSV de descubrimiento (QA, nunca corrige lo oficial)

- Coinciden (fecha efectiva oficial = fecha CSV): 90.
- Diferencia de fecha (CONFLICT): 32; diferencia de ticker / un solo lado (UNRESOLVED): 110.
- Faltan en lo oficial (DISCOVERY_ONLY + TBA sin fecha posterior): 317.
- Anuncios oficiales ≥ 2011 sin fila CSV correspondiente (sobrantes): 10 (pueden ser anuncios TBA reemplazados, cambios de otro índice mal clasificados o rectificaciones).

| anuncio | cambio declarado | tipo | añadida | eliminada | tier |
|---|---|---|---|---|---|
| 2011-05-26 | 2011-06-02 AFTER_CLOSE | MERGER_OR_ACQUISITION | AMB | PLD | OFFICIAL_REPUBLISHED |
| 2011-06-23 | 2011-06-30 AFTER_CLOSE | SPINOFF | MPCWI | RSH | OFFICIAL_REPUBLISHED |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2013-10-22 | 2013-10-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | RIG | DELL | OFFICIAL_SPDJI |
| 2013-10-29 | 2013-11-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | KORS | NYX | OFFICIAL_SPDJI |
| 2014-04-25 | 2014-04-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | UA | BEAM | OFFICIAL_SPDJI |
| 2015-07-25 | 2015-07-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | SIG | DTV | OFFICIAL_SPDJI |
| 2015-12-29 | 2016-01-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | WSH | FOSL | OFFICIAL_SPDJI |
| 2026-10-02 | 2026-10-06 BEFORE_OPEN | MERGER_OR_ACQUISITION | TWLO | WBD | OFFICIAL_SPDJI |

## Gaps (eventos sin evidencia oficial concordante)

| fecha | añadida | eliminada | fuente discovery | fuente oficial | estado | motivo |
|---|---|---|---|---|---|---|
| 2011-01-18 | — | QLGC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-02-28 | — | AYE | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-02-28 | JOY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-03-01 | COV | MFE | chinobing CSV | https://web.archive.org/web/20110625120229id_/https://www.prnewswire.c | DATE_TBA | release states a date to be announced |
| 2011-04-01 | EW | Q | chinobing CSV | https://web.archive.org/web/20110326024207id_/https://www.prnewswire.c | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2011-04-28 | — | NOVL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-04-28 | CMG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-06-02 | ANR | MEE | chinobing CSV | https://web.archive.org/web/20201126184401id_/https://www.prnewswire.c | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2011-07-01 | MPC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-07-06 | ACN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-09-26 | MOS | NSM | chinobing CSV | https://web.archive.org/web/20110928145638id_/https://www.prnewswire.c | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2011-10-14 | — | CEPH | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-10-17 | TEL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-11-01 | — | ITT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-11-01 | XYL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-11-23 | — | JNS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-11-23 | CBE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-12-19 | — | MWW | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-12-19 | BWA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-12-19 | DLTR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-12-19 | PRGO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-12-21 | — | TLAB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-12-21 | TRIP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-01-03 | WPX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-03-13 | CCI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-04-02 | — | MHS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-05-01 | — | SVU | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-05-01 | PSX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-05-22 | — | MMI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-05-25 | — | EP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-05-25 | ALXN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-05-25 | KMI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-06-05 | LRCX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-06-29 | MNST | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-07-02 | STX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-07-27 | ESV | GR | chinobing CSV | https://press.spglobal.com/2012-07-26-Ensco-plc-Set-to-Join-the-S-P-50 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2012-07-31 | ESV | GR | chinobing CSV | https://press.spglobal.com/2012-07-26-Ensco-plc-Set-to-Join-the-S-P-50 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2012-09-05 | LYB | SHLD | chinobing CSV | https://press.spglobal.com/2012-08-29-LyondellBasell-Industries-Set-to | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2012-10-01 | — | ATGE | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-10-01 | ADTWI | LXK | chinobing CSV | https://press.spglobal.com/2012-09-24-ADT-Pentair-Set-to-Join-the-S-P- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2012-10-01 | PNR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-10-02 | KRFT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-10-05 | PETM | SUN | chinobing CSV | https://press.spglobal.com/2012-10-01-PetSmart-Set-to-Join-the-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2012-12-12 | — | RRD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-12-12 | GRMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-12-24 | APTV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-12-24 | DLPH | TIE | chinobing CSV | https://press.spglobal.com/2012-12-18-Delphi-Automotive-Set-to-Join-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-01-02 | — | FII | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-01-02 | ABBV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-02-14 | PVH | BIG | chinobing CSV | https://press.spglobal.com/2013-02-07-PVH-Set-To-Join-S-P-500-Big-Lots | DATE_TBA | release states a date to be announced |
| 2013-05-01 | — | TMUS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-05-01 | REGN | PCS | chinobing CSV | https://press.spglobal.com/2013-04-24-Regeneron-Set-to-Join-the-S-P-50 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-05-09 | MAC | CVH | chinobing CSV | https://press.spglobal.com/2013-05-03-Macerich-Set-to-Join-the-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-06-07 | — | HNZ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-06-07 | GM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-06-24 | ZTS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-06-24 | ZTSWI | FHN | chinobing CSV | https://press.spglobal.com/2013-06-14-Zoetis-Set-to-Join-S-P-500-First | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-07-01 | NWSA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-07-01 | NWSAV | APOL | chinobing CSV | https://press.spglobal.com/2013-06-20-News-Corp-Set-to-Join-S-P-500-Ma | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-07-09 | NLSN | S | chinobing CSV | https://press.spglobal.com/2013-07-01-Nielsen-Set-to-Join-the-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-09-11 | DAL | BMC | chinobing CSV | https://press.spglobal.com/2013-09-06-Delta-Air-Lines-Set-to-Join-the- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-09-23 | — | LDOS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-09-23 | AME | SAI | chinobing CSV | https://press.spglobal.com/2013-09-11-Vertex-Ametek-Set-to-Join-the-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-09-23 | VRTX | AMD | chinobing CSV | https://press.spglobal.com/2013-09-11-Vertex-Ametek-Set-to-Join-the-S- | CONFLICT | official effective session 2013-09-20 != discovery date 2013-09-23 |
| 2013-12-02 | ALLE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-12-02 | ALLEWI | JCP | chinobing CSV | https://press.spglobal.com/2013-11-22-Allegion-plc-Set-to-Join-the-S-P | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-12-09 | GGP | MOLX | chinobing CSV | https://press.spglobal.com/2013-12-04-General-Growth-Properties-Set-to | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-12-10 | GGP | MOLX | chinobing CSV | https://press.spglobal.com/2013-12-04-General-Growth-Properties-Set-to | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2013-12-23 | — | TER | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-12-23 | — | VIAV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-12-23 | FB | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-12-23 | MHK | JDSU | chinobing CSV | https://press.spglobal.com/2013-12-11-Facebook-Set-to-Join-the-S-P-100 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-01-24 | TSCO | LIFE | chinobing CSV | https://press.spglobal.com/2014-01-16-Tractor-Supply-Set-to-Join-the-S | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-04-03 | GOOG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-01 | NAVI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-01 | NAVIV | SLM | chinobing CSV | https://press.spglobal.com/2014-04-24-Navient-Under-Armour-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-05-01 | UAA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-07 | AVGO | LSI | chinobing CSV | https://press.spglobal.com/2014-05-05-Avago-Technologies-Set-to-Join-t | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-05-08 | AVGO | LSI | chinobing CSV | https://press.spglobal.com/2014-05-05-Avago-Technologies-Set-to-Join-t | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-06-20 | XEC | IGT | chinobing CSV | https://press.spglobal.com/2014-06-12-Cimarex-Energy-to-Join-the-S-P-5 | CONFLICT | official effective session 2014-06-23 != discovery date 2014-06-20 |
| 2014-08-07 | DISCK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-08-19 | MNK | RDC | chinobing CSV | https://press.spglobal.com/2014-08-14-Mallinckrodt-Set-to-Join-the-S-P | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2014-09-22 | — | BTUUQ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2014-09-22 | UHS | BTU | chinobing CSV | https://press.spglobal.com/2014-09-12-United-Rentals-and-Universal-Hea | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-03-17 | HSIC | CFN | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-03-18 | HSIC | CFN | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-03-23 | AAL | AGN | chinobing CSV | https://press.spglobal.com/2015-03-16-American-Airlines-Group-Set-to-J | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-03-23 | EQIX | DNR | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | UNRESOLVED | no resolvable date/timing in the release |
| 2015-03-23 | HBI | AVP | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | CONFLICT | official effective session 2015-03-18 != discovery date 2015-03-23 |
| 2015-03-23 | SLG | NBR | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | CONFLICT | official effective session 2015-03-18 != discovery date 2015-03-23 |
| 2015-04-07 | — | WIN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-04-07 | O | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-01 | — | QEP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-07-01 | BXLT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-01 | JBHT | TEG | chinobing CSV | https://press.spglobal.com/2015-06-26-J-B-Hunt-Transport-Services-Set- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-07-02 | — | MWV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-07-02 | CPGX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-02 | CPGXWI | ATI | chinobing CSV | https://press.spglobal.com/2015-06-24-Columbia-Pipeline-to-Join-the-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-07-02 | WRK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-06 | — | KRFT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-07-06 | KHC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-07 | AAP | FDO | chinobing CSV | https://press.spglobal.com/2015-07-06-Advance-Auto-Parts-Set-to-Join-t | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-07-09 | AAP | FDO | chinobing CSV | https://press.spglobal.com/2015-07-06-Advance-Auto-Parts-Set-to-Join-t | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-07-20 | PYPL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-08-31 | ATVI | PLL | chinobing CSV | https://press.spglobal.com/2015-08-27-Activision-Blizzard-United-Conti | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-09-21 | CMCSK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-09-21 | NWS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-10-08 | — | JOY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-10-08 | VRSK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-02 | — | HCBK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-11-02 | HPE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-10 | FCPT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-17 | — | FCPT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-11-18 | ILMN | SIAL | chinobing CSV | https://press.spglobal.com/2015-11-12-Illumina-Set-to-Join-the-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-11-18 | SYF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-18 | SYFWI | GNW | chinobing CSV | https://press.spglobal.com/2015-11-09-Synchrony-Financial-Set-to-Join- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-11-19 | ILMN | SIAL | chinobing CSV | https://press.spglobal.com/2015-11-12-Illumina-Set-to-Join-the-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2015-11-30 | CSRA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-12-01 | — | DXC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-12-14 | — | CMCSK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-12-29 | CHD | ALTR | chinobing CSV | https://press.spglobal.com/2015-12-22-Church-Dwight-Set-to-Join-the-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-01-04 | CPRI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-01-05 | WLTW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-01-19 | EXR | CB | chinobing CSV | https://press.spglobal.com/2016-01-13-Extra-Space-Storage-Set-to-Join- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-02-01 | CFG | PCP | chinobing CSV | https://press.spglobal.com/2016-01-26-Citizens-Financial-Group-Set-to- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-02-22 | CXO | PCL | chinobing CSV | https://press.spglobal.com/2016-02-16-Concho-Resources-Set-to-Join-the | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-03-03 | UDR | GMCR | chinobing CSV | https://press.spglobal.com/2016-03-03-UDR-Set-to-Join-the-S-P-500-Heal | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-03-04 | — | CNX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-03-04 | AWK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-03-07 | UDR | GMCR | chinobing CSV | https://press.spglobal.com/2016-03-03-UDR-Set-to-Join-the-S-P-500-Heal | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-03-30 | HOLX | POM | chinobing CSV | https://press.spglobal.com/2016-03-24-Hologic-Centene-Set-to-Join-the- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-04-08 | UA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-05-03 | AYI | ADT | chinobing CSV | https://press.spglobal.com/2016-04-26-Acuity-Brands-Set-to-Join-the-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-05-12 | ALK | SNDK | chinobing CSV | https://press.spglobal.com/2016-05-10-Alaska-Air-Group-Set-to-Join-the | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-05-13 | ALK | SNDK | chinobing CSV | https://press.spglobal.com/2016-05-10-Alaska-Air-Group-Set-to-Join-the | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-05-31 | AJG | CCE | chinobing CSV | https://press.spglobal.com/2016-05-24-Arthur-J-Gallagher-Co-Set-to-Joi | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-06-21 | — | CVC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-06-24 | FBHS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-07-01 | — | CPGX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-07-01 | LNT | GAS | chinobing CSV | https://press.spglobal.com/2016-06-29-Alliant-Energy-Set-to-Join-the-S | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-07-05 | FTV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-09-06 | MTD | JCI | chinobing CSV | https://press.spglobal.com/2016-08-25-Mettler-Toledo-International-Set | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-09-08 | CHTR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-09-23 | COO | HOT | chinobing CSV | https://press.spglobal.com/2016-09-20-The-Cooper-Companies-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-10-03 | COTY | DO | chinobing CSV | https://press.spglobal.com/2016-09-27-Coty-Set-to-Join-the-S-P-500-Dia | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-12-02 | AMSG | LM | chinobing CSV | https://press.spglobal.com/2016-11-29-Mid-America-Apartment-Communitie | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2016-12-02 | EVHC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-02-28 | INCY | SE | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-01 | CBOE | PBI | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-02 | REG | ENDP | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-16 | SNPS | HAR | chinobing CSV | https://press.spglobal.com/2017-03-13-Synopsys-Set-to-Join-S-P-500-The | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-03-20 | — | FSLR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-03-20 | — | FTR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-03-20 | AMD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-03-20 | ARE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-03-20 | RJF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-04-04 | CSC | SWN | chinobing CSV | https://press.spglobal.com/2017-03-28-Computer-Sciences-Set-to-Join-S- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-04-04 | DXC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-04-05 | IT | DNB | chinobing CSV | https://press.spglobal.com/2017-03-29-Gartner-Set-to-Join-S-P-500-Dun- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-06-15 | RE | MJN | chinobing CSV | https://press.spglobal.com/2017-06-12-Everest-Re-Group-Set-to-Join-S-P | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-06-19 | HLT | YHOO | chinobing CSV | https://press.spglobal.com/2017-06-09-Hilton-Worldwide-Align-Technolog | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-06-19 | RE | MJN | chinobing CSV | https://press.spglobal.com/2017-06-12-Everest-Re-Group-Set-to-Join-S-P | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-07-25 | MGM | RAI | chinobing CSV | https://press.spglobal.com/2017-07-19-MGM-Resorts-ResMed-Packaging-Cor | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-07-26 | DRE | RIG | chinobing CSV | https://press.spglobal.com/2017-07-19-MGM-Resorts-ResMed-Packaging-Cor | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-07-26 | MGM | RAI | chinobing CSV | https://press.spglobal.com/2017-07-19-MGM-Resorts-ResMed-Packaging-Cor | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-07-26 | RMD | MNK | chinobing CSV | https://press.spglobal.com/2017-07-19-MGM-Resorts-ResMed-Packaging-Cor | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-08-07 | BHF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-08-08 | — | AN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-08-28 | Q | WFM | chinobing CSV | https://press.spglobal.com/2017-08-24-Charter-Communications-Set-to-Jo | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-08-29 | IQV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | — | DD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-09-01 | DWDP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | SBAC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-13 | CDNS | SPLS | chinobing CSV | https://press.spglobal.com/2017-09-08-Cadence-Design-Systems-Set-to-Jo | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-09-18 | CDNS | SPLS | chinobing CSV | https://press.spglobal.com/2017-09-08-Cadence-Design-Systems-Set-to-Jo | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2017-10-13 | NCLH | LVLT | chinobing CSV | https://press.spglobal.com/2017-10-04-Norwegian-Cruise-Line-Set-to-Joi | UNRESOLVED | no resolvable date/timing in the release |
| 2017-12-29 | HII | BCR | chinobing CSV | https://press.spglobal.com/2017-12-28-Huntington-Ingalls-Industries-Se | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-01-03 | HII | BCR | chinobing CSV | https://press.spglobal.com/2017-12-28-Huntington-Ingalls-Industries-Se | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-03-19 | — | PDCO | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-03-19 | NKTR | CHK | chinobing CSV | https://press.spglobal.com/2018-03-09-Take-Two-Interactive-Software-SV | UNRESOLVED | no resolvable date/timing in the release |
| 2018-03-19 | SIVB | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-03-19 | TTWO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-05-31 | ABMD | WYN | chinobing CSV | https://press.spglobal.com/2018-05-25-ABIOMED-Set-to-Join-S-P-500-Othe | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-06-05 | — | NAVI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-06-05 | EVRG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-06-07 | TWTR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-06-15 | — | TWX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-06-18 | — | AYI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-06-18 | — | RRC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-06-18 | BR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-06-18 | HFC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-06-20 | FLT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-07-02 | — | KDP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-07-02 | CPRT | DPS | chinobing CSV | https://press.spglobal.com/2018-06-25-Copart-Set-to-Join-S-P-500-Exeli | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-09-17 | WCG | XL | chinobing CSV | https://press.spglobal.com/2018-09-11-WellCare-Health-Plans-Set-to-Joi | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-09-19 | — | KORS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-11-06 | LIN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-11-13 | JKHY | EQT | chinobing CSV | https://press.spglobal.com/2018-11-07-Jack-Henry-Associates-Set-to-Joi | CONFLICT | official effective session 2018-11-14 != discovery date 2018-11-13 |
| 2018-11-27 | LW | COL | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-11-29 | MXIM | AET | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-12-03 | LW | COL | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-12-03 | MXIM | AET | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-12-21 | CE | ESRX | chinobing CSV | https://press.spglobal.com/2018-12-19-Celanese-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2018-12-24 | CE | ESRX | chinobing CSV | https://press.spglobal.com/2018-12-19-Celanese-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2019-04-02 | — | BHF | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-01 | — | HRS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-01 | LHX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-03 | — | DWDP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-03 | — | FLR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-03 | CTVA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-03 | DD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-07 | AMCR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-07 | BMS | MAT | chinobing CSV | https://press.spglobal.com/2019-06-03-Bemis-Set-to-Join-S-P-500-Mattel | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2019-07-01 | MKTX | LLL | chinobing CSV | https://press.spglobal.com/2019-06-24-MarketAxess-Holdings-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2019-08-08 | — | TMK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-08-08 | GL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-10-18 | BKR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-11-05 | — | SYMC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-11-05 | NLOK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-11-05 | PEAK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-11-21 | — | CELG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-11-21 | NOW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-05 | — | CBS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-05 | VIAC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-09 | — | BBT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-09 | TFC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-10 | — | JEC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-10 | J | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-23 | — | AMG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-23 | — | MAC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-23 | — | TRIP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-23 | LYV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-23 | STE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-23 | ZBRA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-03-03 | GDI | XEC | chinobing CSV | https://press.spglobal.com/2020-02-27-Gardner-Denver-Holdings-Set-to-J | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2020-03-03 | TT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-03 | — | UTX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-03 | CARR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-03 | OTIS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-03 | RTX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-06 | — | M | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-06 | — | RTN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-06 | HWM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-05-12 | — | CPRI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-05-12 | DPZ | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-05-12 | DXCM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-06-22 | — | ADS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-06-22 | — | HOG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-06-22 | — | JWN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-06-22 | BIO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-06-22 | TDY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-06-22 | TYL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-09-18 | — | CTL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-09-18 | LUMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-09-21 | — | COTY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-09-21 | — | HRB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-09-21 | — | KSS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-09-21 | CTLT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-09-21 | ETSY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-09-21 | TER | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-10-12 | — | NBL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-10-12 | VNT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-11-17 | — | MYL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-11-17 | VTRS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-12-21 | — | AIV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-12-21 | TSLA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-03-22 | — | SLG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | — | VNT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | — | XRX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | CZR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-03-22 | GNRC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-03-22 | PENN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-06-04 | — | HFC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-06-04 | OGN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-08-03 | — | LB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-08-03 | BBWI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-09-20 | — | NOV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-09-20 | — | UNM | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-09-20 | BRO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-09-20 | CDAY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-10-04 | — | COG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-10-04 | CTRA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-12-20 | — | HBI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-12-20 | — | LEG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-12-20 | — | WU | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-12-20 | FDS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-12-20 | SBNY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-12-20 | SEDG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-01-20 | — | WLTW | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-01-20 | WTW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-02-02 | CEG | GPS | chinobing CSV | https://press.spglobal.com/2022-01-26-Constellation-Energy-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2022-02-17 | — | VIAC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-02-17 | PARA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-04-11 | — | DISCA | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-04-11 | — | DISCK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-04-11 | WBD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-05-10 | — | BLL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-05-10 | BALL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-06-09 | — | FB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-06-09 | META | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-06-21 | — | IPGP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-06-21 | — | UA | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-06-21 | — | UAA | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-06-21 | KDP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-06-21 | ON | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-06-28 | — | ANTM | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-06-28 | ELV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-09-19 | — | PENN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-09-19 | — | PVH | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-09-19 | CSGP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-09-19 | INVH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2022-11-08 | — | NLOK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-11-08 | GEN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-01-04 | — | VNO | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-01-04 | GEHC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-07 | AXON | FRC | chinobing CSV | https://press.spglobal.com/2023-05-01-Axon-Enterprise-Set-to-Join-S-P- | CONFLICT | official effective session 2023-05-04 != discovery date 2023-05-07 |
| 2023-05-09 | — | BF-B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-05-09 | — | BRK-B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-05-09 | BF.B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-09 | BRK.B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-14 | — | BF.B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-05-14 | BF-B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-17 | CEG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-17 | DOW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-17 | FOX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-17 | FOXA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-17 | IR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-05-18 | — | PKI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-05-18 | RVTY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-06-03 | PANW | DISH | chinobing CSV | https://press.spglobal.com/2023-06-02-Palo-Alto-Networks-Set-to-S-P-50 | UNRESOLVED | before-open change on 2023-06-19: not a XNYS session |
| 2023-06-04 | — | PANW | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-06-04 | DISH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-06-08 | — | FISV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-06-08 | FI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-06-20 | PANW | DISH | chinobing CSV | https://press.spglobal.com/2023-06-02-Palo-Alto-Networks-Set-to-S-P-50 | UNRESOLVED | before-open change on 2023-06-19: not a XNYS session |
| 2023-07-11 | — | RE | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-07-11 | EG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-08-29 | KVUE | AAP | chinobing CSV | https://press.spglobal.com/2023-08-21-Kenvue-Set-to-Join-S-P-500-Advan | CONFLICT | official effective session 2023-08-25 != discovery date 2023-08-29 |
| 2023-08-31 | — | ABC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-09-01 | ABC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-09-02 | — | ABC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-09-03 | COR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-09-24 | — | BRK.B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-09-24 | BRK-B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-09-26 | — | BRK-B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-09-26 | BRK.B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-10-06 | — | DXC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-10-06 | VLTO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-10-14 | LULU | ATVI | chinobing CSV | https://press.spglobal.com/2023-10-13-Lululemon-Athletica-Hubbell-Set- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2023-10-18 | LULU | ATVI | chinobing CSV | https://press.spglobal.com/2023-10-13-Lululemon-Athletica-Hubbell-Set- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2023-12-17 | BLDR | SEDG | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-17 | JBL | ALK | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-17 | UBER | SEE | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-31 | — | RVTY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-12-31 | RVTY (PREVIOUSLY PKI) | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-01-01 | — | RVTY (PREVIOUSLY PKI) | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-01-01 | RVTY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-02-02 | — | CDAY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-02-02 | DAY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-03-04 | — | PEAK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-03-04 | DOC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-03-26 | — | FLT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-03-27 | CPAY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-04-02 | SOLV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-04-03 | GEV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-04-04 | — | VFC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-04-04 | — | XRAY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-05-04 | VST | PXD | chinobing CSV | https://press.spglobal.com/2024-05-03-Vistra-Set-to-Join-S-P-500-Aaon- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-05-08 | VST | PXD | chinobing CSV | https://press.spglobal.com/2024-05-03-Vistra-Set-to-Join-S-P-500-Aaon- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-06-23 | CRWD | CMA | chinobing CSV | https://press.spglobal.com/2024-06-07-KKR,-CrowdStrike-Holdings-and-Go | CONFLICT | official effective session 2024-06-24 != discovery date 2024-06-23 |
| 2024-06-23 | GDDY | ILMN | chinobing CSV | https://press.spglobal.com/2024-06-07-KKR,-CrowdStrike-Holdings-and-Go | CONFLICT | official effective session 2024-06-24 != discovery date 2024-06-23 |
| 2024-06-23 | KKR | RHI | chinobing CSV | https://press.spglobal.com/2024-06-07-KKR,-CrowdStrike-Holdings-and-Go | CONFLICT | official effective session 2024-06-24 != discovery date 2024-06-23 |
| 2024-07-09 | — | WRK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-07-12 | SW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-08-04 | — | BF-B | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-08-04 | BF.B | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-09-22 | DELL | ETSY | chinobing CSV | https://press.spglobal.com/2024-09-06-Palantir-Technologies,-Dell-Tech | CONFLICT | official effective session 2024-09-23 != discovery date 2024-09-22 |
| 2024-09-22 | ERIE | BIO | chinobing CSV | https://press.spglobal.com/2024-09-06-Palantir-Technologies,-Dell-Tech | CONFLICT | official effective session 2024-09-23 != discovery date 2024-09-22 |
| 2024-09-22 | PLTR | AAL | chinobing CSV | https://press.spglobal.com/2024-09-06-Palantir-Technologies,-Dell-Tech | CONFLICT | official effective session 2024-09-23 != discovery date 2024-09-22 |
| 2024-10-01 | — | BBWI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-10-01 | AMTM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-11-23 | TPL | MRO | chinobing CSV | https://press.spglobal.com/2024-11-21-Texas-Pacific-Land-Set-to-Join-S | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-11-26 | TPL | MRO | chinobing CSV | https://press.spglobal.com/2024-11-21-Texas-Pacific-Land-Set-to-Join-S | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-12-19 | LII | CTLT | chinobing CSV | https://press.spglobal.com/2024-12-18-Lennox-International-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-12-24 | LII | CTLT | chinobing CSV | https://press.spglobal.com/2024-12-18-Lennox-International-Set-to-Join | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2024-12-26 | APO | QRVO | chinobing CSV | https://press.spglobal.com/2024-12-06-Apollo-Global-Management-and-Wor | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-26 |
| 2024-12-26 | WDAY | AMTM | chinobing CSV | https://press.spglobal.com/2024-12-06-Apollo-Global-Management-and-Wor | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-26 |
| 2025-03-25 | DASH | BWA | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | EXE | FMC | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | TKO | TFX | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | WSM | CE | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-05-13 | COIN | DFS | chinobing CSV | https://press.spglobal.com/2025-05-12-Coinbase-Global-Set-to-Join-S-P- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-05-14 | — | COIN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-05-17 | COIN | DFS | chinobing CSV | https://press.spglobal.com/2025-05-12-Coinbase-Global-Set-to-Join-S-P- | CONFLICT | official effective session 2025-05-19 != discovery date 2025-05-17 |
| 2025-07-04 | DDOG | JNPR | chinobing CSV | https://press.spglobal.com/2025-07-02-Datadog-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-07-11 | DDOG | JNPR | chinobing CSV | https://press.spglobal.com/2025-07-02-Datadog-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-07-22 | XYZ | HES | chinobing CSV | https://press.spglobal.com/2025-07-18-Block-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-07-23 | XYZ | HES | chinobing CSV | https://press.spglobal.com/2025-07-18-Block-Set-to-Join-S-P-500 | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-08-09 | — | PARA | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-08-12 | PSKY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-08-27 | IBKR | WBA | chinobing CSV | https://press.spglobal.com/2025-08-25-Interactive-Brokers-Group-Set-to | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-08-30 | IBKR | WBA | chinobing CSV | https://press.spglobal.com/2025-08-25-Interactive-Brokers-Group-Set-to | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-09-06 | APP | MKTX | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-06 |
| 2025-09-06 | EME | ENPH | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-06 |
| 2025-09-06 | HOOD | CZR | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-06 |
| 2025-09-09 | — | APP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-09-09 | — | EME | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-09-09 | — | HOOD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-09-09 | CZR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-09-09 | ENPH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-09-09 | MKTX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-09-23 | APP | MKTX | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-23 |
| 2025-09-23 | EME | ENPH | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-23 |
| 2025-09-23 | HOOD | CZR | chinobing CSV | https://press.spglobal.com/2025-09-05-AppLovin,-Robinhood-Markets-and- | CONFLICT | official effective session 2025-09-22 != discovery date 2025-09-23 |
| 2025-11-06 | Q | EMN | chinobing CSV | https://press.spglobal.com/2025-10-27-Solstice-Advance-Materials-and-Q | CONFLICT | official effective session 2025-11-04 != discovery date 2025-11-06 |
| 2025-11-13 | — | FI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-11-13 | FISV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-11-29 | SNDK | IPG | chinobing CSV | https://press.spglobal.com/2025-11-24-Sandisk-Set-to-Join-S-P-500-Upwo | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-12-02 | SNDK | IPG | chinobing CSV | https://press.spglobal.com/2025-11-24-Sandisk-Set-to-Join-S-P-500-Upwo | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-12-12 | ARES | K | chinobing CSV | https://press.spglobal.com/2025-12-08-Ares-Management-Set-to-Join-S-P- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-12-13 | ARES | K | chinobing CSV | https://press.spglobal.com/2025-12-08-Ares-Management-Set-to-Join-S-P- | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2025-12-24 | — | LKQ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-12-24 | — | MHK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-01 | FIX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-02 | — | SOLS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-02 | CRH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-02 | CVNA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-15 | — | MMC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-15 | MRSH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-02-05 | CIEN | DAY | chinobing CSV | https://press.spglobal.com/2026-02-04-Ciena-Set-to-Join-S-P-500-Arrowh | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2026-02-08 | CIEN | DAY | chinobing CSV | https://press.spglobal.com/2026-02-04-Ciena-Set-to-Join-S-P-500-Arrowh | UNRESOLVED | only one side of the pair matches the discovery row (ticker difference?) |
| 2026-03-25 | — | LW | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-03-25 | — | MOH | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-03-25 | — | MTCH | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-03-25 | — | PAYC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-03-25 | COHR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-03-25 | LITE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-03-25 | SATS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-03-25 | VRT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-05-22 | — | BK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-05-22 | BNY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-06-04 | FDXF | EPAM | chinobing CSV | https://press.spglobal.com/2026-05-27-FedEx-Freight-Holding-Company-Se | CONFLICT | official effective session 2026-06-02 != discovery date 2026-06-04 |
| 2026-06-20 | — | CPB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-06-20 | — | POOL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-06-20 | FLEX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-06-20 | MRVL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-06-25 | — | SATS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-06-25 | ECHO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-06-30 | — | CAG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-06-30 | HONA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-08-06 | FERG | EA | chinobing CSV | https://press.spglobal.com/2026-07-31-Ferguson-Enterprises-Set-to-Join | CONFLICT | official effective session 2026-08-05 != discovery date 2026-08-06 |
| 2026-08-18 | — | EQR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-08-18 | VMRK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | — | BLDR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | — | TAP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | — | TTD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | BE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | ILMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | P | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
