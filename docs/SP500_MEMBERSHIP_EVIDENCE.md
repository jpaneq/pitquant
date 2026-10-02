# Evidencia de membresía S&P 500 (D-02, candidato construido desde fuentes públicas)

> Generado por `scripts/gen_sp500_evidence_report.py` (ADR-0025). **No es canónico**: la lista comunitaria sólo descubre;
> cada cambio necesita un comunicado de S&P (tier 1) o su copia en PRNewswire (tier 2). Ningún evento se corrige para
> que coincida con GitHub/Wikipedia.

## Resumen

```
discovery_events_2011_present        = 536   (filas del CSV: 325)
official_confirmed (tier 1 S&P)      = 215
official_republished_confirmed (t2)  = 7
date_tba                             = 5
conflicts                            = 79
unresolved                           = 6
discovery_only (sin evidencia)       = 224
coverage_pct                         = 41.4%
```

## Estados D-02

- `SP500_MEMBERSHIP_DISCOVERY_READY` = **true** (CSV archivado sha256 `591c9eb91b71af204f28cf3fb1e2f81483b8a336f2d5810313de21d4a23d845e`).
- `SP500_MEMBERSHIP_EVIDENCE_COVERAGE` = **41.4%** (222/536 eventos con evidencia oficial concordante).
- `SP500_MEMBERSHIP_CANONICAL_READY` = **false**: (1) `CURRENT_ANCHOR_BLOCKED` (la página de S&P DJI devuelve 403 y su `Full Constituents List` no se puede archivar automáticamente: sin ancla no hay reconstrucción hacia atrás ni comprobación de reversibilidad sobre datos reales), y (2) quedan eventos sin evidencia (ver gaps).

Primer evento sin confirmar: **2011-01-18**. Sin ancla actual no hay primera fecha reconstruible ni año completo reconstruible; con ancla, las fechas anteriores a ese evento dependerían de él y no podrían declararse canónicas (fail-closed).

## Documentos de evidencia

- Tier 1 `OFFICIAL_SPDJI` (press.spglobal.com): 1509 cláusulas «will replace … in the S&P 500» parseadas.
- Tier 2 `OFFICIAL_REPUBLISHED` (PRNewswire vía Wayback): 40 cláusulas.
- El archivo de prensa de S&P Global sólo contiene comunicados de cambios de índice desde ~2014; PRNewswire sólo es localizable por el índice CDX de Wayback (2010–2011 sobre todo).

## Cobertura por año

| año | eventos discovery | confirmados | % |
|---|---|---|---|
| 2011 | 27 | 7 | 26% |
| 2012 | 25 | 14 | 56% |
| 2013 | 29 | 13 | 45% |
| 2014 | 20 | 13 | 65% |
| 2015 | 43 | 21 | 49% |
| 2016 | 36 | 27 | 75% |
| 2017 | 37 | 19 | 51% |
| 2018 | 31 | 21 | 68% |
| 2019 | 39 | 20 | 51% |
| 2020 | 30 | 16 | 53% |
| 2021 | 25 | 19 | 76% |
| 2022 | 33 | 12 | 36% |
| 2023 | 48 | 8 | 17% |
| 2024 | 34 | 4 | 12% |
| 2025 | 38 | 3 | 8% |
| 2026 | 41 | 5 | 12% |

## Universo

- Tickers distintos añadidos en eventos 2011+: 379; eliminados: 357; unión (sin ancla no se conoce la composición inicial): 596.
- Former constituents con eliminación confirmada oficialmente: 210.
- Resolución ticker → `security_id`: **no resuelta** (el Security Master sólo contiene AAPL y MSFT del S&P 500). Evidencia de membresía e identidad de la security son capas separadas.

## Comparación con el CSV de descubrimiento (QA, nunca corrige lo oficial)

- Coinciden (fecha efectiva oficial = fecha CSV): 222.
- Diferencia de fecha (CONFLICT): 79; diferencia de ticker / un solo lado (UNRESOLVED): 6.
- Faltan en lo oficial (DISCOVERY_ONLY + TBA sin fecha posterior): 229.
- Anuncios oficiales ≥ 2011 sin fila CSV correspondiente (sobrantes): 1245 (pueden ser anuncios TBA reemplazados, cambios de otro índice mal clasificados o rectificaciones).

| anuncio | cambio declarado | tipo | añadida | eliminada | tier |
|---|---|---|---|---|---|
| 2010-12-22 | 2011-01-03 AFTER_CLOSE | SPINOFF | MMI | MDP | OFFICIAL_REPUBLISHED |
| 2011-01-26 | None TBA | MERGER_OR_ACQUISITION | COV | MFE | OFFICIAL_REPUBLISHED |
| 2011-03-24 | 2011-03-31 AFTER_CLOSE | MERGER_OR_ACQUISITION | EW | Q | OFFICIAL_REPUBLISHED |
| 2011-03-29 | 2011-04-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | BLK | GENZ | OFFICIAL_REPUBLISHED |
| 2011-05-24 | 2011-06-01 AFTER_CLOSE | MERGER_OR_ACQUISITION | ANR | MEE | OFFICIAL_REPUBLISHED |
| 2011-05-26 | 2011-06-02 AFTER_CLOSE | MERGER_OR_ACQUISITION | AMB | PLD | OFFICIAL_REPUBLISHED |
| 2011-06-23 | 2011-06-30 AFTER_CLOSE | SPINOFF | MPCWI | RSH | OFFICIAL_REPUBLISHED |
| 2011-09-21 | 2011-09-23 AFTER_CLOSE | MERGER_OR_ACQUISITION | MOS | NSM | OFFICIAL_REPUBLISHED |
| 2012-03-08 | None TBA | MERGER_OR_ACQUISITION | CCI | CEG | OFFICIAL_SPDJI |
| 2012-03-29 | None TBA | MERGER_OR_ACQUISITION | FOSL | MHS | OFFICIAL_SPDJI |
| 2012-04-24 | 2012-04-30 AFTER_CLOSE | SPINOFF | PSXWI | SVU | OFFICIAL_SPDJI |
| 2012-05-11 | None TBA | MERGER_OR_ACQUISITION | LRCX | NVLS | OFFICIAL_SPDJI |
| 2012-05-18 | 2012-05-24 AFTER_CLOSE | MERGER_OR_ACQUISITION | KMI | EP | OFFICIAL_SPDJI |
| 2012-05-22 | 2012-05-24 AFTER_CLOSE | MERGER_OR_ACQUISITION | ALXN | MMI | OFFICIAL_SPDJI |
| 2012-06-22 | 2012-06-28 AFTER_CLOSE | SPINOFF | MNST | SLE | OFFICIAL_SPDJI |
| 2012-06-26 | 2012-06-29 AFTER_CLOSE | MERGER_OR_ACQUISITION | STX | PGN | OFFICIAL_SPDJI |
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-07-27 | 2012-07-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | ESV | GR | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-08-30 | 2012-09-04 AFTER_CLOSE | UNSPECIFIED | LYB | SHLD | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | ADTWI | LXK | OFFICIAL_SPDJI |
| 2012-09-25 | 2012-09-28 AFTER_CLOSE | SPINOFF | PNRWI | DV | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-09-26 | 2012-10-01 AFTER_CLOSE | SPINOFF | KRFTV | ANR | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-10-02 | 2012-10-04 AFTER_CLOSE | MERGER_OR_ACQUISITION | PETM | SUN | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-11-27 | 2012-11-30 AFTER_CLOSE | MERGER_OR_ACQUISITION | DG | CBE | OFFICIAL_SPDJI |
| 2012-12-06 | 2012-12-11 AFTER_CLOSE | MERGER_OR_ACQUISITION | GRMN | RRD | OFFICIAL_SPDJI |
| 2012-12-06 | 2012-12-11 AFTER_CLOSE | MERGER_OR_ACQUISITION | GRMN | RRD | OFFICIAL_SPDJI |
| 2012-12-06 | 2012-12-11 AFTER_CLOSE | MERGER_OR_ACQUISITION | GRMN | RRD | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2012-12-19 | 2012-12-21 AFTER_CLOSE | MERGER_OR_ACQUISITION | DLPH | TIE | OFFICIAL_SPDJI |
| 2013-02-08 | None TBA | MERGER_OR_ACQUISITION | PVH | BIG | OFFICIAL_SPDJI |

## Reconstrucción D-02 (ancla SPY/IVV → deshacer eventos confirmados → rejugar)

- Ancla: **MULTI_SOURCE_CONFIRMED** (as_of 2026-10-01); eventos 536, confirmados 294; reversibilidad exacta de la cadena confirmada: **True**.
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
  - 2026-06-30: UNRESOLVED +HONA --: no resolvable date/timing in the release
  - 2026-06-30: DISCOVERY_ONLY +- -CAG: no official evidence found for this removal
  - 2026-06-25: DISCOVERY_ONLY +ECHO --: no official evidence found for this addition
  - 2026-06-25: DISCOVERY_ONLY +- -SATS: no official evidence found for this removal

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
| 2013-12-09 | GGP | MOLX | chinobing CSV | https://press.spglobal.com/2013-12-04-General-Growth-Properties-Set-to | CONFLICT | official effective session 2013-12-10 != discovery date 2013-12-09 |
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
| 2015-11-02 | — | HCBK | chinobing CSV | https://press.spglobal.com/2015-10-27-Blackrock-Set-to-Join-the-S-P-10 | CONFLICT | official effective session 2015-11-03 != discovery date 2015-11-02 |
| 2015-11-10 | FCPT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-11-17 | — | FCPT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-11-18 | ILMN | SIAL | chinobing CSV | https://press.spglobal.com/2015-11-12-Illumina-Set-to-Join-the-S-P-500 | CONFLICT | official effective session 2015-11-19 != discovery date 2015-11-18 |
| 2015-11-18 | SYF | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2015-12-01 | — | DXC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2015-12-14 | — | CMCSK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-01-04 | CPRI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-01-05 | WLTW | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-03-03 | UDR | GMCR | chinobing CSV | https://press.spglobal.com/2016-03-03-UDR-Set-to-Join-the-S-P-500-Heal | CONFLICT | official effective session 2016-03-07 != discovery date 2016-03-03 |
| 2016-04-08 | UA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-05-12 | ALK | SNDK | chinobing CSV | https://press.spglobal.com/2016-05-10-Alaska-Air-Group-Set-to-Join-the | CONFLICT | official effective session 2016-05-13 != discovery date 2016-05-12 |
| 2016-06-21 | — | CVC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2016-06-24 | FBHS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2016-07-01 | — | CPGX | chinobing CSV | https://press.spglobal.com/2016-06-23-Albemarle-and-Fortive-Set-to-Joi | CONFLICT | official effective session 2016-07-06 != discovery date 2016-07-01 |
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
| 2017-08-28 | Q | WFM | chinobing CSV | https://press.spglobal.com/2017-08-24-Charter-Communications-Set-to-Jo | CONFLICT | official effective session 2017-08-29 != discovery date 2017-08-28 |
| 2017-08-29 | IQV | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | — | DD | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2017-09-01 | DWDP | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-01 | SBAC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2017-09-13 | CDNS | SPLS | chinobing CSV | https://press.spglobal.com/2017-09-08-Cadence-Design-Systems-Set-to-Jo | CONFLICT | official effective session 2017-09-18 != discovery date 2017-09-13 |
| 2017-12-29 | HII | BCR | chinobing CSV | https://press.spglobal.com/2017-12-28-Huntington-Ingalls-Industries-Se | CONFLICT | official effective session 2018-01-03 != discovery date 2017-12-29 |
| 2018-06-05 | — | NAVI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-06-05 | EVRG | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-06-15 | FLT | TWX | chinobing CSV | https://press.spglobal.com/2018-06-15-NVIDIA-Set-to-Join-S-P-100-Fleet | CONFLICT | official effective session 2018-06-20 != discovery date 2018-06-15 |
| 2018-07-02 | — | KDP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-09-19 | — | KORS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2018-11-06 | LIN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2018-11-13 | JKHY | EQT | chinobing CSV | https://press.spglobal.com/2018-11-07-Jack-Henry-Associates-Set-to-Joi | CONFLICT | official effective session 2018-11-14 != discovery date 2018-11-13 |
| 2018-11-27 | LW | COL | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | CONFLICT | official effective session 2018-12-03 != discovery date 2018-11-27 |
| 2018-11-29 | MXIM | AET | chinobing CSV | https://press.spglobal.com/2018-11-26-Lamb-Weston-Holdings-Maxim-Integ | CONFLICT | official effective session 2018-12-03 != discovery date 2018-11-29 |
| 2018-12-21 | CE | ESRX | chinobing CSV | https://press.spglobal.com/2018-12-19-Celanese-Set-to-Join-S-P-500 | CONFLICT | official effective session 2018-12-24 != discovery date 2018-12-21 |
| 2019-04-02 | — | BHF | chinobing CSV | https://press.spglobal.com/2019-03-26-Dow-Set-to-Join-S-P-500-and-S-P- | CONFLICT | official effective session 2019-04-03 != discovery date 2019-04-02 |
| 2019-06-01 | — | HRS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-01 | LHX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-03 | — | DWDP | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-06-03 | — | FLR | chinobing CSV | https://press.spglobal.com/2019-05-28-Corteva-Set-to-Join-S-P-500-Fluo | CONFLICT | official effective session 2019-06-04 != discovery date 2019-06-03 |
| 2019-06-03 | DD | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-06-07 | AMCR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-08-08 | — | TMK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-08-08 | GL | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-10-18 | BKR | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-11-05 | — | SYMC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-11-05 | NLOK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-11-05 | PEAK | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-05 | — | CBS | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-05 | VIAC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-09 | — | BBT | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-09 | TFC | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2019-12-10 | — | JEC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2019-12-10 | J | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-03-03 | TT | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-03 | — | UTX | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-03 | RTX | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-04-06 | — | M | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-04-06 | HWM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-05-12 | — | CPRI | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-05-12 | DPZ | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-05-12 | DXCM | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-09-18 | — | CTL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-09-18 | LUMN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-10-12 | VNT | — | chinobing CSV | https://press.spglobal.com/2020-10-05-Vontier-Set-to-Join-S-P-500 | CONFLICT | official effective session 2020-10-09 != discovery date 2020-10-12 |
| 2020-11-17 | — | MYL | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2020-11-17 | VTRS | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2020-12-21 | — | AIV | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-06-04 | — | HFC | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-06-04 | OGN | — | chinobing CSV | https://press.spglobal.com/2021-05-27-Organon-Set-to-Join-S-P-500-Holl | CONFLICT | official effective session 2021-06-03 != discovery date 2021-06-04 |
| 2021-08-03 | — | LB | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-08-03 | BBWI | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2021-10-04 | — | COG | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2021-10-04 | CTRA | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
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
| 2022-11-08 | — | NLOK | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
| 2022-11-08 | GEN | — | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this addition |
| 2023-01-04 | — | VNO | chinobing CSV | — | DISCOVERY_ONLY | no official evidence found for this removal |
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
| 2023-10-06 | VLTO | — | chinobing CSV | https://press.spglobal.com/2023-09-28-Veralto-Set-to-Join-S-P-500-Vest | CONFLICT | official effective session 2023-10-02 != discovery date 2023-10-06 |
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
| 2024-04-02 | SOLV | — | chinobing CSV | https://press.spglobal.com/2024-03-27-GE-Vernova-and-Solventum-Set-to- | CONFLICT | official effective session 2024-04-01 != discovery date 2024-04-02 |
| 2024-04-03 | GEV | — | chinobing CSV | https://press.spglobal.com/2024-03-27-GE-Vernova-and-Solventum-Set-to- | CONFLICT | official effective session 2024-04-02 != discovery date 2024-04-03 |
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
| 2024-10-01 | AMTM | — | chinobing CSV | https://press.spglobal.com/2024-09-24-Amentum-Set-to-Join-S-P-500-Bath | CONFLICT | official effective session 2024-09-30 != discovery date 2024-10-01 |
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
