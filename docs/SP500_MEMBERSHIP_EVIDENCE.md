# Evidencia de membresía S&P 500 (D-02, candidato construido desde fuentes públicas)

> Generado por `scripts/gen_sp500_evidence_report.py` (ADR-0025). **No es canónico**: la lista comunitaria sólo descubre;
> cada cambio necesita un comunicado de S&P (tier 1) o su copia en PRNewswire (tier 2). Ningún evento se corrige para
> que coincida con GitHub/Wikipedia.

## Resumen

```
discovery_events_2011_present        = 558   (filas del CSV: 325)
official_confirmed (tier 1 S&P)      = 164
official_republished_confirmed (t2)  = 7
date_tba                             = 5
conflicts                            = 67
unresolved                           = 23
discovery_only (sin evidencia)       = 292
coverage_pct                         = 30.6%
```

## Estados D-02

- `SP500_MEMBERSHIP_DISCOVERY_READY` = **true** (CSV archivado sha256 `591c9eb91b71af204f28cf3fb1e2f81483b8a336f2d5810313de21d4a23d845e`).
- `SP500_MEMBERSHIP_EVIDENCE_COVERAGE` = **30.6%** (171/558 eventos con evidencia oficial concordante).
- `SP500_MEMBERSHIP_CANONICAL_READY` = **false**: (1) `CURRENT_ANCHOR_BLOCKED` (la página de S&P DJI devuelve 403 y su `Full Constituents List` no se puede archivar automáticamente: sin ancla no hay reconstrucción hacia atrás ni comprobación de reversibilidad sobre datos reales), y (2) quedan eventos sin evidencia (ver gaps).

Primer evento sin confirmar: **2011-01-18**. Sin ancla actual no hay primera fecha reconstruible ni año completo reconstruible; con ancla, las fechas anteriores a ese evento dependerían de él y no podrían declararse canónicas (fail-closed).

## Documentos de evidencia

- Tier 1 `OFFICIAL_SPDJI` (press.spglobal.com): 438 cláusulas «will replace … in the S&P 500» parseadas.
- Tier 2 `OFFICIAL_REPUBLISHED` (PRNewswire vía Wayback): 20 cláusulas.
- El archivo de prensa de S&P Global sólo contiene comunicados de cambios de índice desde ~2014; PRNewswire sólo es localizable por el índice CDX de Wayback (2010–2011 sobre todo).

## Cobertura por año

| año | eventos discovery | confirmados | % |
|---|---|---|---|
| 2011 | 27 | 7 | 26% |
| 2012 | 26 | 13 | 50% |
| 2013 | 29 | 12 | 41% |
| 2014 | 20 | 13 | 65% |
| 2015 | 43 | 16 | 37% |
| 2016 | 37 | 24 | 65% |
| 2017 | 37 | 16 | 43% |
| 2018 | 34 | 13 | 38% |
| 2019 | 42 | 14 | 33% |
| 2020 | 35 | 4 | 11% |
| 2021 | 32 | 10 | 31% |
| 2022 | 35 | 10 | 29% |
| 2023 | 48 | 7 | 15% |
| 2024 | 34 | 4 | 12% |
| 2025 | 38 | 3 | 8% |
| 2026 | 41 | 5 | 12% |

## Universo

- Tickers distintos añadidos en eventos 2011+: 379; eliminados: 352; unión (sin ancla no se conoce la composición inicial): 593.
- Former constituents con eliminación confirmada oficialmente: 170.
- Resolución ticker → `security_id`: **no resuelta** (el Security Master sólo contiene AAPL y MSFT del S&P 500). Evidencia de membresía e identidad de la security son capas separadas.

## Comparación con el CSV de descubrimiento (QA, nunca corrige lo oficial)

- Coinciden (fecha efectiva oficial = fecha CSV): 171.
- Diferencia de fecha (CONFLICT): 67; diferencia de ticker / un solo lado (UNRESOLVED): 23.
- Faltan en lo oficial (DISCOVERY_ONLY + TBA sin fecha posterior): 297.
- Anuncios oficiales ≥ 2011 sin fila CSV correspondiente (sobrantes): 210 (pueden ser anuncios TBA reemplazados, cambios de otro índice mal clasificados o rectificaciones).

| anuncio | cambio declarado | tipo | añadida | eliminada | tier |
|---|---|---|---|---|---|
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2013-02-08 | None TBA | MERGER_OR_ACQUISITION | PVH | BIG | OFFICIAL_SPDJI |
| 2013-04-25 | 2013-04-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | REGN | PCS | OFFICIAL_SPDJI |
| 2013-05-04 | 2013-05-08 AFTER_CLOSE | MERGER_OR_ACQUISITION | MAC | CVH | OFFICIAL_SPDJI |
| 2013-05-17 | 2013-05-23 AFTER_CLOSE | SPINOFF | KSU | DF | OFFICIAL_SPDJI |
| 2013-06-15 | 2013-06-21 AFTER_CLOSE | UNSPECIFIED | ZTSWI | FHN | OFFICIAL_SPDJI |
| 2013-06-21 | 2013-06-28 AFTER_CLOSE | SPINOFF | NWSAV | APOL | OFFICIAL_SPDJI |
| 2013-07-02 | 2013-07-08 AFTER_CLOSE | MERGER_OR_ACQUISITION | NLSN | S | OFFICIAL_SPDJI |
| 2013-09-07 | 2013-09-10 AFTER_CLOSE | MERGER_OR_ACQUISITION | DAL | BMC | OFFICIAL_SPDJI |
| 2013-09-12 | 2013-09-19 AFTER_CLOSE | UNSPECIFIED | VRTX | AMD | OFFICIAL_SPDJI |
| 2013-09-12 | 2013-09-19 AFTER_CLOSE | UNSPECIFIED | AME | SAI | OFFICIAL_SPDJI |
| 2013-10-22 | 2013-10-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | RIG | DELL | OFFICIAL_SPDJI |
| 2013-10-29 | 2013-11-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | KORS | NYX | OFFICIAL_SPDJI |
| 2013-10-29 | 2013-11-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | KORS | NYX | OFFICIAL_SPDJI |
| 2013-11-09 | 2013-11-12 AFTER_CLOSE | MERGER_OR_ACQUISITION | KORS | NYX | OFFICIAL_SPDJI |
| 2013-11-23 | 2013-11-29 AFTER_CLOSE | SPINOFF | ALLEWI | JCP | OFFICIAL_SPDJI |
| 2013-12-05 | 2013-12-09 AFTER_CLOSE | MERGER_OR_ACQUISITION | GGP | MOLX | OFFICIAL_SPDJI |
| 2013-12-12 | 2013-12-20 AFTER_CLOSE | UNSPECIFIED | ADS | ANF | OFFICIAL_SPDJI |
| 2013-12-12 | 2013-12-20 AFTER_CLOSE | UNSPECIFIED | MHK | JDSU | OFFICIAL_SPDJI |
| 2014-01-17 | 2014-01-23 AFTER_CLOSE | MERGER_OR_ACQUISITION | TSCO | LIFE | OFFICIAL_SPDJI |
| 2014-03-15 | 2014-03-21 AFTER_CLOSE | UNSPECIFIED | GMCR | WPX | OFFICIAL_SPDJI |
| 2014-03-27 | 2014-04-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESS | CLF | OFFICIAL_SPDJI |
| 2014-04-25 | 2014-04-30 AFTER_CLOSE | SPINOFF | NAVIV | SLM | OFFICIAL_SPDJI |
| 2014-04-25 | 2014-04-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | UA | BEAM | OFFICIAL_SPDJI |
| 2014-05-06 | 2014-05-07 AFTER_CLOSE | MERGER_OR_ACQUISITION | AVGO | LSI | OFFICIAL_SPDJI |
| 2014-06-13 | 2014-06-20 AFTER_CLOSE | UNSPECIFIED | XEC | IGT | OFFICIAL_SPDJI |
| 2014-06-25 | 2014-06-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | AMG | FRX | OFFICIAL_SPDJI |
| 2014-06-28 | 2014-07-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | MLM | X | OFFICIAL_SPDJI |
| 2014-08-15 | 2014-08-18 AFTER_CLOSE | MERGER_OR_ACQUISITION | MNK | RDC | OFFICIAL_SPDJI |
| 2014-09-13 | 2014-09-19 AFTER_CLOSE | UNSPECIFIED | URI | GHC | OFFICIAL_SPDJI |
| 2014-09-13 | 2014-09-19 AFTER_CLOSE | UNSPECIFIED | UHS | BTU | OFFICIAL_SPDJI |
| 2014-10-30 | 2014-11-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | LVLT | JBL | OFFICIAL_SPDJI |
| 2014-12-02 | 2014-12-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | RCL | BMS | OFFICIAL_SPDJI |
| 2015-01-22 | 2015-01-26 AFTER_CLOSE | MERGER_OR_ACQUISITION | ENDP | COV | OFFICIAL_SPDJI |
| 2015-01-24 | 2015-01-26 AFTER_CLOSE | MERGER_OR_ACQUISITION | HCA | SWY | OFFICIAL_SPDJI |
| 2015-03-10 | 2015-03-11 AFTER_CLOSE | MERGER_OR_ACQUISITION | SWKS | PETM | OFFICIAL_SPDJI |
| 2015-03-14 | None UNKNOWN | UNSPECIFIED | EQIX | DNR | OFFICIAL_SPDJI |
| 2015-03-14 | 2015-03-17 AFTER_CLOSE | UNSPECIFIED | SLG | NBR | OFFICIAL_SPDJI |
| 2015-03-14 | 2015-03-17 AFTER_CLOSE | UNSPECIFIED | HBI | AVP | OFFICIAL_SPDJI |
| 2015-03-14 | 2015-03-17 AFTER_CLOSE | MERGER_OR_ACQUISITION | HSIC | CFN | OFFICIAL_SPDJI |
| 2015-03-17 | 2015-03-20 AFTER_CLOSE | MERGER_OR_ACQUISITION | AAL | AGN | OFFICIAL_SPDJI |
| 2015-06-10 | 2015-06-11 AFTER_CLOSE | MERGER_OR_ACQUISITION | QRVO | LO | OFFICIAL_SPDJI |
| 2015-06-25 | 2015-07-01 AFTER_CLOSE | SPINOFF | CPGXWI | ATI | OFFICIAL_SPDJI |
| 2015-06-27 | 2015-06-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | JBHT | TEG | OFFICIAL_SPDJI |
| 2015-07-07 | 2015-07-08 AFTER_CLOSE | MERGER_OR_ACQUISITION | AAP | FDO | OFFICIAL_SPDJI |
| 2015-07-25 | 2015-07-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | SIG | DTV | OFFICIAL_SPDJI |
| 2015-08-28 | 2015-08-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | ATVI | PLL | OFFICIAL_SPDJI |
| 2015-08-28 | 2015-09-02 AFTER_CLOSE | MERGER_OR_ACQUISITION | UAL | HSP | OFFICIAL_SPDJI |
| 2015-11-10 | 2015-11-17 AFTER_CLOSE | UNSPECIFIED | SYFWI | GNW | OFFICIAL_SPDJI |
| 2015-11-13 | 2015-11-18 AFTER_CLOSE | MERGER_OR_ACQUISITION | ILMN | SIAL | OFFICIAL_SPDJI |
| 2015-12-23 | 2015-12-28 AFTER_CLOSE | MERGER_OR_ACQUISITION | CHD | ALTR | OFFICIAL_SPDJI |
| 2015-12-29 | 2016-01-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | WSH | FOSL | OFFICIAL_SPDJI |
| 2016-01-14 | 2016-01-15 AFTER_CLOSE | MERGER_OR_ACQUISITION | EXR | CB | OFFICIAL_SPDJI |

## Reconstrucción D-02 (ancla SPY/IVV → deshacer eventos confirmados → rejugar)

- Ancla: **MULTI_SOURCE_CONFIRMED** (as_of 2026-10-01); eventos 558, confirmados 171; reversibilidad exacta de la cadena confirmada: **True**.
- Primera fecha con membresía demostrada (earliest reconstructible date): **2026-09-21** (nada anterior es canónico: queda un evento sin confirmar posterior a cada fecha anterior).
- Periodo continuo más largo: 2026-10-01 → 2026-10-01, **1 cohortes mensuales** fuera del holdout (el holdout excluye 0 cohortes demostradas).
- Primer / último año completo reconstruible: None / None.
- **D02_RESEARCH_READY = false** (mínimo 60 cohortes consecutivas; preferido 96). Notas: ninguna
- Eventos sin confirmar más recientes (rompen la cadena), de más reciente a más antiguo:

  - 2026-09-21: DISCOVERY_ONLY +P --: no official evidence found for this addition
  - 2026-09-21: DISCOVERY_ONLY +ILMN --: no official evidence found for this addition
  - 2026-09-21: DISCOVERY_ONLY +BE --: no official evidence found for this addition
  - 2026-09-21: DISCOVERY_ONLY +- -TTD: no official evidence found for this removal
  - 2026-09-21: DISCOVERY_ONLY +- -TAP: no official evidence found for this removal
  - 2026-09-21: DISCOVERY_ONLY +- -BLDR: no official evidence found for this removal
  - 2026-08-18: DISCOVERY_ONLY +VMRK --: no official evidence found for this addition
  - 2026-08-18: DISCOVERY_ONLY +- -EQR: no official evidence found for this removal
  - 2026-08-06: CONFLICT +FERG -EA: official effective session 2026-08-05 != discovery date 2026-08-06
  - 2026-06-30: UNRESOLVED +HONA --: no resolvable date/timing in the release
  - 2026-06-30: DISCOVERY_ONLY +- -CAG: no official evidence found for this removal
  - 2026-06-25: DISCOVERY_ONLY +ECHO --: no official evidence found for this addition

## Gaps (eventos sin evidencia oficial concordante)

| fecha | añadida | eliminada | fuente discovery | fuente oficial | estado | motivo |
|---|---|---|---|---|---|---|
| 2011-01-18 | — | QLGC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-02-28 | — | AYE | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-02-28 | JOY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-03-01 | COV | MFE | chinobing CSV | https://web.archive.org/web/20110625120229id_/https://www.prnewswire.c | DATE_TBA | release states a date to be announced |
| 2011-04-28 | — | NOVL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2011-04-28 | CMG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-07-01 | MPC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2011-07-06 | ACN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
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
| 2012-03-13 | CCI | CEG | chinobing CSV | https://press.spglobal.com/2012-03-07-S-P-Indices-Announces-Change-to- | DATE_TBA | release states a date to be announced |
| 2012-04-02 | FOSL | MHS | chinobing CSV | https://press.spglobal.com/2012-03-28-S-P-Indices-Announces-Changes-to | DATE_TBA | release states a date to be announced |
| 2012-05-01 | PSX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-05-22 | ALXN | MMI | chinobing CSV | https://press.spglobal.com/2012-05-21-S-P-Indices-Announces-Change-to- | CONFLICT | official effective session 2012-05-25 != discovery date 2012-05-22 |
| 2012-06-05 | LRCX | NVLS | chinobing CSV | https://press.spglobal.com/2012-05-10-S-P-Indices-Announces-Changes-to | DATE_TBA | release states a date to be announced |
| 2012-07-27 | ESV | GR | chinobing CSV | https://press.spglobal.com/2012-07-26-Ensco-plc-Set-to-Join-the-S-P-50 | CONFLICT | official effective session 2012-07-31 != discovery date 2012-07-27 |
| 2012-10-01 | — | ATGE | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-10-01 | PNR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-10-02 | KRFT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-12-12 | — | RRD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2012-12-12 | GRMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2012-12-24 | APTV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-01-02 | — | FII | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-01-02 | ABBV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-02-14 | PVH | BIG | chinobing CSV | https://press.spglobal.com/2013-02-07-PVH-Set-To-Join-S-P-500-Big-Lots | DATE_TBA | release states a date to be announced |
| 2013-05-01 | — | TMUS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-06-07 | — | HNZ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-06-07 | GM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-06-24 | ZTS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-07-01 | NWSA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-09-23 | — | LDOS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-09-23 | AME | SAI | chinobing CSV | https://press.spglobal.com/2013-09-11-Vertex-Ametek-Set-to-Join-the-S- | CONFLICT | official effective session 2013-09-20 != discovery date 2013-09-23 |
| 2013-09-23 | VRTX | AMD | chinobing CSV | https://press.spglobal.com/2013-09-11-Vertex-Ametek-Set-to-Join-the-S- | CONFLICT | official effective session 2013-09-20 != discovery date 2013-09-23 |
| 2013-12-02 | ALLE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-12-09 | — | MOLX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-12-10 | GGP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2013-12-23 | — | TER | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-12-23 | — | VIAV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2013-12-23 | FB | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-04-03 | GOOG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-01 | NAVI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-01 | UAA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-05-07 | AVGO | LSI | chinobing CSV | https://press.spglobal.com/2014-05-05-Avago-Technologies-Set-to-Join-t | CONFLICT | official effective session 2014-05-08 != discovery date 2014-05-07 |
| 2014-06-20 | XEC | IGT | chinobing CSV | https://press.spglobal.com/2014-06-12-Cimarex-Energy-to-Join-the-S-P-5 | CONFLICT | official effective session 2014-06-23 != discovery date 2014-06-20 |
| 2014-08-07 | DISCK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2014-09-22 | — | BTUUQ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-03-17 | HSIC | CFN | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | CONFLICT | official effective session 2015-03-18 != discovery date 2015-03-17 |
| 2015-03-23 | EQIX | DNR | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | UNRESOLVED | no resolvable date/timing in the release |
| 2015-03-23 | HBI | AVP | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | CONFLICT | official effective session 2015-03-18 != discovery date 2015-03-23 |
| 2015-03-23 | SLG | NBR | chinobing CSV | https://press.spglobal.com/2015-03-13-Celgene-Kinder-Morgan-and-Actavi | CONFLICT | official effective session 2015-03-18 != discovery date 2015-03-23 |
| 2015-04-07 | — | WIN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-04-07 | O | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-01 | BXLT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-02 | — | MWV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-07-02 | CPGX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-02 | WRK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-06 | — | KRFT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-07-06 | KHC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-07-07 | AAP | FDO | chinobing CSV | https://press.spglobal.com/2015-07-06-Advance-Auto-Parts-Set-to-Join-t | CONFLICT | official effective session 2015-07-09 != discovery date 2015-07-07 |
| 2015-07-20 | PYPL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-09-21 | CMCSK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-09-21 | NWS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-10-08 | — | JOY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-10-08 | VRSK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-02 | — | HCBK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-11-02 | HPE | — | chinobing CSV | https://press.spglobal.com/2015-10-27-Blackrock-Set-to-Join-the-S-P-10 | UNRESOLVED | no resolvable date/timing in the release |
| 2015-11-10 | FCPT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-17 | — | FCPT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-11-18 | ILMN | SIAL | chinobing CSV | https://press.spglobal.com/2015-11-12-Illumina-Set-to-Join-the-S-P-500 | CONFLICT | official effective session 2015-11-19 != discovery date 2015-11-18 |
| 2015-11-18 | SYF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-30 | CSRA | — | chinobing CSV | https://press.spglobal.com/2015-11-23-CSRA-to-Join-the-S-P-500-Compute | UNRESOLVED | no resolvable date/timing in the release |
| 2015-12-01 | — | DXC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-12-14 | — | CMCSK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-01-04 | CPRI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-01-05 | WLTW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-03-03 | UDR | GMCR | chinobing CSV | https://press.spglobal.com/2016-03-03-UDR-Set-to-Join-the-S-P-500-Heal | CONFLICT | official effective session 2016-03-07 != discovery date 2016-03-03 |
| 2016-03-04 | — | CNX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-03-04 | AWK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-04-08 | UA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-05-12 | ALK | SNDK | chinobing CSV | https://press.spglobal.com/2016-05-10-Alaska-Air-Group-Set-to-Join-the | CONFLICT | official effective session 2016-05-13 != discovery date 2016-05-12 |
| 2016-06-21 | — | CVC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-06-24 | FBHS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-07-01 | — | CPGX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-07-05 | FTV | — | chinobing CSV | https://press.spglobal.com/2016-06-23-Albemarle-and-Fortive-Set-to-Joi | UNRESOLVED | no resolvable date/timing in the release |
| 2016-09-08 | CHTR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-12-02 | EVHC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-02-28 | INCY | SE | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-01 | CBOE | PBI | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-02 | REG | ENDP | chinobing CSV | https://press.spglobal.com/2017-02-23-Incyte-CBOE-Holdings-Regency-Cen | UNRESOLVED | no resolvable date/timing in the release |
| 2017-03-20 | — | FSLR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-03-20 | — | FTR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-03-20 | AMD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-03-20 | ARE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-03-20 | RJF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-04-04 | DXC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-06-15 | RE | MJN | chinobing CSV | https://press.spglobal.com/2017-06-12-Everest-Re-Group-Set-to-Join-S-P | CONFLICT | official effective session 2017-06-19 != discovery date 2017-06-15 |
| 2017-07-25 | MGM | RAI | chinobing CSV | https://press.spglobal.com/2017-07-19-MGM-Resorts-ResMed-Packaging-Cor | CONFLICT | official effective session 2017-07-26 != discovery date 2017-07-25 |
| 2017-08-07 | BHF | — | chinobing CSV | https://press.spglobal.com/2017-07-31-Brighthouse-Financial-Set-to-Joi | UNRESOLVED | no resolvable date/timing in the release |
| 2017-08-08 | — | AN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-08-28 | Q | WFM | chinobing CSV | https://press.spglobal.com/2017-08-24-Charter-Communications-Set-to-Jo | CONFLICT | official effective session 2017-08-29 != discovery date 2017-08-28 |
| 2017-08-29 | IQV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | — | DD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-09-01 | DWDP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | SBAC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-13 | CDNS | SPLS | chinobing CSV | https://press.spglobal.com/2017-09-08-Cadence-Design-Systems-Set-to-Jo | CONFLICT | official effective session 2017-09-18 != discovery date 2017-09-13 |
| 2017-10-13 | NCLH | LVLT | chinobing CSV | https://press.spglobal.com/2017-10-04-Norwegian-Cruise-Line-Set-to-Joi | UNRESOLVED | no resolvable date/timing in the release |
| 2017-12-29 | HII | BCR | chinobing CSV | https://press.spglobal.com/2017-12-28-Huntington-Ingalls-Industries-Se | CONFLICT | official effective session 2018-01-03 != discovery date 2017-12-29 |
| 2018-03-19 | — | PDCO | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-03-19 | NKTR | CHK | chinobing CSV | https://press.spglobal.com/2018-03-09-Take-Two-Interactive-Software-SV | UNRESOLVED | no resolvable date/timing in the release |
| 2018-03-19 | SIVB | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-03-19 | TTWO | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
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
| 2018-07-02 | CPRT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-09-19 | — | KORS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-11-06 | LIN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-11-13 | JKHY | EQT | chinobing CSV | https://press.spglobal.com/2018-11-07-Jack-Henry-Associates-Set-to-Joi | CONFLICT | official effective session 2018-11-14 != discovery date 2018-11-13 |
| 2018-11-27 | LW | COL | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | CONFLICT | official effective session 2018-12-03 != discovery date 2018-11-27 |
| 2018-11-29 | MXIM | AET | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | CONFLICT | official effective session 2018-12-03 != discovery date 2018-11-29 |
| 2018-12-21 | CE | ESRX | chinobing CSV | https://press.spglobal.com/2018-12-19-Celanese-Set-to-Join-S-P-500 | CONFLICT | official effective session 2018-12-24 != discovery date 2018-12-21 |
| 2019-04-02 | — | BHF | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-01 | — | HRS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-01 | LHX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-03 | — | DWDP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-03 | — | FLR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-03 | CTVA | — | chinobing CSV | https://press.spglobal.com/2019-05-28-Corteva-Set-to-Join-S-P-500-Fluo | UNRESOLVED | no resolvable date/timing in the release |
| 2019-06-03 | DD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-07 | AMCR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
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
| 2020-03-03 | TT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-03 | — | UTX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-03 | CARR | — | chinobing CSV | https://press.spglobal.com/2020-03-31-Otis-Worldwide-and-Carrier-Globa | UNRESOLVED | no resolvable date/timing in the release |
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
| 2020-10-12 | VNT | — | chinobing CSV | https://press.spglobal.com/2020-10-05-Vontier-Set-to-Join-S-P-500 | UNRESOLVED | no resolvable date/timing in the release |
| 2020-11-17 | — | MYL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-11-17 | VTRS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-12-21 | — | AIV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-12-21 | TSLA | — | chinobing CSV | https://press.spglobal.com/2020-12-11-Tesla-Set-to-Join-S-P-500-100-Ap | UNRESOLVED | no resolvable date/timing in the release |
| 2021-03-22 | — | SLG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | — | VNT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | — | XRX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-03-22 | CZR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-03-22 | GNRC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-03-22 | PENN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-06-04 | — | HFC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-06-04 | OGN | — | chinobing CSV | https://press.spglobal.com/2021-05-27-Organon-Set-to-Join-S-P-500-Holl | UNRESOLVED | no resolvable date/timing in the release |
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
| 2022-02-02 | CEG | GPS | chinobing CSV | https://press.spglobal.com/2022-01-26-Constellation-Energy-Set-to-Join | CONFLICT | official effective session 2022-02-03 != discovery date 2022-02-02 |
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
| 2023-01-04 | GEHC | — | chinobing CSV | https://press.spglobal.com/2022-12-28-GE-HealthCare-Technologies-Set-t | UNRESOLVED | no resolvable date/timing in the release |
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
| 2023-10-06 | VLTO | — | chinobing CSV | https://press.spglobal.com/2023-09-28-Veralto-Set-to-Join-S-P-500-Vest | UNRESOLVED | no resolvable date/timing in the release |
| 2023-10-14 | LULU | ATVI | chinobing CSV | https://press.spglobal.com/2023-10-13-Lululemon-Athletica-Hubbell-Set- | CONFLICT | official effective session 2023-10-18 != discovery date 2023-10-14 |
| 2023-12-17 | BLDR | SEDG | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-17 | JBL | ALK | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-17 | UBER | SEE | chinobing CSV | https://press.spglobal.com/2023-12-01-Uber-Technologies,-Jabil-and-Bui | CONFLICT | official effective session 2023-12-18 != discovery date 2023-12-17 |
| 2023-12-31 | — | RVTY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2023-12-31 | RVTY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-01-01 | — | RVTY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-01-01 | RVTY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-02-02 | — | CDAY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-02-02 | DAY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-03-04 | — | PEAK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-03-04 | DOC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-03-26 | — | FLT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-03-27 | CPAY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2024-04-02 | SOLV | — | chinobing CSV | https://press.spglobal.com/2024-03-27-GE-Vernova-and-Solventum-Set-to- | UNRESOLVED | no resolvable date/timing in the release |
| 2024-04-03 | GEV | — | chinobing CSV | https://press.spglobal.com/2024-03-27-GE-Vernova-and-Solventum-Set-to- | UNRESOLVED | no resolvable date/timing in the release |
| 2024-04-04 | — | VFC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-04-04 | — | XRAY | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2024-05-04 | VST | PXD | chinobing CSV | https://press.spglobal.com/2024-05-03-Vistra-Set-to-Join-S-P-500-Aaon- | CONFLICT | official effective session 2024-05-08 != discovery date 2024-05-04 |
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
| 2024-10-01 | AMTM | — | chinobing CSV | https://press.spglobal.com/2024-09-24-Amentum-Set-to-Join-S-P-500-Bath | UNRESOLVED | no resolvable date/timing in the release |
| 2024-11-23 | TPL | MRO | chinobing CSV | https://press.spglobal.com/2024-11-21-Texas-Pacific-Land-Set-to-Join-S | CONFLICT | official effective session 2024-11-26 != discovery date 2024-11-23 |
| 2024-12-19 | LII | CTLT | chinobing CSV | https://press.spglobal.com/2024-12-18-Lennox-International-Set-to-Join | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-19 |
| 2024-12-24 | LII | CTLT | chinobing CSV | https://press.spglobal.com/2024-12-18-Lennox-International-Set-to-Join | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-24 |
| 2024-12-26 | APO | QRVO | chinobing CSV | https://press.spglobal.com/2024-12-06-Apollo-Global-Management-and-Wor | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-26 |
| 2024-12-26 | WDAY | AMTM | chinobing CSV | https://press.spglobal.com/2024-12-06-Apollo-Global-Management-and-Wor | CONFLICT | official effective session 2024-12-23 != discovery date 2024-12-26 |
| 2025-03-25 | DASH | BWA | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | EXE | FMC | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | TKO | TFX | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-03-25 | WSM | CE | chinobing CSV | https://press.spglobal.com/2025-03-07-DoorDash,-TKO-Group-Holdings,-Wi | CONFLICT | official effective session 2025-03-24 != discovery date 2025-03-25 |
| 2025-05-13 | COIN | DFS | chinobing CSV | https://press.spglobal.com/2025-05-12-Coinbase-Global-Set-to-Join-S-P- | CONFLICT | official effective session 2025-05-19 != discovery date 2025-05-13 |
| 2025-05-14 | — | COIN | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-05-17 | COIN | DFS | chinobing CSV | https://press.spglobal.com/2025-05-12-Coinbase-Global-Set-to-Join-S-P- | CONFLICT | official effective session 2025-05-19 != discovery date 2025-05-17 |
| 2025-07-04 | DDOG | JNPR | chinobing CSV | https://press.spglobal.com/2025-07-02-Datadog-Set-to-Join-S-P-500 | CONFLICT | official effective session 2025-07-09 != discovery date 2025-07-04 |
| 2025-07-11 | DDOG | JNPR | chinobing CSV | https://press.spglobal.com/2025-07-02-Datadog-Set-to-Join-S-P-500 | CONFLICT | official effective session 2025-07-09 != discovery date 2025-07-11 |
| 2025-07-22 | XYZ | HES | chinobing CSV | https://press.spglobal.com/2025-07-18-Block-Set-to-Join-S-P-500 | CONFLICT | official effective session 2025-07-23 != discovery date 2025-07-22 |
| 2025-08-09 | — | PARA | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-08-12 | PSKY | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2025-08-27 | IBKR | WBA | chinobing CSV | https://press.spglobal.com/2025-08-25-Interactive-Brokers-Group-Set-to | CONFLICT | official effective session 2025-08-28 != discovery date 2025-08-27 |
| 2025-08-30 | IBKR | WBA | chinobing CSV | https://press.spglobal.com/2025-08-25-Interactive-Brokers-Group-Set-to | CONFLICT | official effective session 2025-08-28 != discovery date 2025-08-30 |
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
| 2025-11-29 | SNDK | IPG | chinobing CSV | https://press.spglobal.com/2025-11-24-Sandisk-Set-to-Join-S-P-500-Upwo | CONFLICT | official effective session 2025-11-28 != discovery date 2025-11-29 |
| 2025-12-02 | SNDK | IPG | chinobing CSV | https://press.spglobal.com/2025-11-24-Sandisk-Set-to-Join-S-P-500-Upwo | CONFLICT | official effective session 2025-11-28 != discovery date 2025-12-02 |
| 2025-12-12 | ARES | K | chinobing CSV | https://press.spglobal.com/2025-12-08-Ares-Management-Set-to-Join-S-P- | CONFLICT | official effective session 2025-12-11 != discovery date 2025-12-12 |
| 2025-12-13 | ARES | K | chinobing CSV | https://press.spglobal.com/2025-12-08-Ares-Management-Set-to-Join-S-P- | CONFLICT | official effective session 2025-12-11 != discovery date 2025-12-13 |
| 2025-12-24 | — | LKQ | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2025-12-24 | — | MHK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-01 | FIX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-02 | — | SOLS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-02 | CRH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-02 | CVNA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-01-15 | — | MMC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-01-15 | MRSH | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-02-05 | CIEN | DAY | chinobing CSV | https://press.spglobal.com/2026-02-04-Ciena-Set-to-Join-S-P-500-Arrowh | CONFLICT | official effective session 2026-02-09 != discovery date 2026-02-05 |
| 2026-02-08 | CIEN | DAY | chinobing CSV | https://press.spglobal.com/2026-02-04-Ciena-Set-to-Join-S-P-500-Arrowh | CONFLICT | official effective session 2026-02-09 != discovery date 2026-02-08 |
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
| 2026-06-30 | HONA | — | chinobing CSV | https://press.spglobal.com/2026-06-23-Honeywell-Aerospace-Set-to-Join- | UNRESOLVED | no resolvable date/timing in the release |
| 2026-08-06 | FERG | EA | chinobing CSV | https://press.spglobal.com/2026-07-31-Ferguson-Enterprises-Set-to-Join | CONFLICT | official effective session 2026-08-05 != discovery date 2026-08-06 |
| 2026-08-18 | — | EQR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-08-18 | VMRK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | — | BLDR | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | — | TAP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | — | TTD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2026-09-21 | BE | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | ILMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2026-09-21 | P | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
