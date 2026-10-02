# S&P 500 — readiness de ventanas D-02 (generado)

> Generado por `scripts/gen_us_window_reports.py` desde la base. No editar a mano.

Ancla: `MULTI_SOURCE_CONFIRMED` as_of 2026-10-01 · run de eventos `1dbc300e-298d-43a8-a1a0-c0adf697fdfd` · 536 eventos, 294 confirmados (incl. 72 CONFLICT inmateriales), 242 rompen la cadena · `D02_RESEARCH_READY = false` · holdout 2022-10-01 → 2025-09-30 sellado.

## Hallazgo estructural

Con **una sola ancla (hoy, 2026-10-01)** la pertenencia en la apertura de una fecha D exige TODOS los eventos posteriores a D confirmados: los eventos de 2022-10 → 2026 (periodo de holdout y posterior) bloquean cohortes de 2017-2022 aunque estén fuera de la ventana. El número «hipotético con ancla al final de la ventana» muestra cuánto se ganaría con una segunda ancla verificada cerca de 2022-09/10 (no es un estado).

## Gate mínimo (60 cohortes): 2017-10-01 → 2022-09-30

| campo | valor |
|---|---|
| status | BLOCKED_BY_EVENTS_IN_WINDOW |
| monthly_cohorts | 60 |
| reconstructible_cohorts (hoy) | 0 |
| longest consecutive run (hoy) | 0 |
| HIPOTÉTICO con ancla al final de la ventana | 3 cohortes, racha 3 |
| first_failure | cohort 2017-10-02: 158 unconfirmed events dated on/after it; nearest 2018-01-03 +HII -BCR (CONFLICT) |
| blocking events DENTRO de la ventana | 60 |
| blocking events DESPUÉS (cadena) | 98 {'2022': 2, '2023': 34, '2024': 16, '2025': 14, '2026': 32} |
| CONFLICT inmateriales resueltos en la ventana | 9 |
| blocking_identity (tickers sin security) | 59 |
| holdout_overlap | False |

Bloqueos dentro de la ventana por causa:

| estado / parser | n |
|---|---|
| DISCOVERY_ONLY / NO_DOCUMENT | 42 |
| DISCOVERY_ONLY / PARSER_MISS | 15 |
| CONFLICT / PARSED_DATE_CONFLICT | 2 |
| DISCOVERY_ONLY / PARSED_BUT_NOT_MATCHED | 1 |

## Gate preferido (96 cohortes): 2014-10-01 → 2022-09-30

| campo | valor |
|---|---|
| status | BLOCKED_BY_EVENTS_IN_WINDOW |
| monthly_cohorts | 96 |
| reconstructible_cohorts (hoy) | 0 |
| longest consecutive run (hoy) | 0 |
| HIPOTÉTICO con ancla al final de la ventana | 3 cohortes, racha 3 |
| first_failure | cohort 2014-10-01: 195 unconfirmed events dated on/after it; nearest 2015-04-07 +None -WIN (DISCOVERY_ONLY) |
| blocking events DENTRO de la ventana | 97 |
| blocking events DESPUÉS (cadena) | 98 {'2022': 2, '2023': 34, '2024': 16, '2025': 14, '2026': 32} |
| CONFLICT inmateriales resueltos en la ventana | 20 |
| blocking_identity (tickers sin security) | 90 |
| holdout_overlap | False |

Bloqueos dentro de la ventana por causa:

| estado / parser | n |
|---|---|
| DISCOVERY_ONLY / NO_DOCUMENT | 62 |
| DISCOVERY_ONLY / PARSER_MISS | 26 |
| CONFLICT / PARSED_DATE_CONFLICT | 4 |
| UNRESOLVED / PARSED_NO_DATE | 3 |
| DISCOVERY_ONLY / PARSED_BUT_NOT_MATCHED | 2 |

## Clasificación de causas

- `NO_DOCUMENT`: el comunicado de S&P DJI no está en el archivo crudo → fuente externa (ChatGPT).
- `PARSER_MISS`: hay un comunicado archivado que menciona el ticker pero no se extrajo la cláusula (layout no soportado, p. ej. «added … replacing … which will be removed» con fechas distintas por lado). Trabajo offline, sin descargas.
- `PARSED_NO_DATE`: comunicado parseado sin fecha/hora efectiva (TBA o redacción sin fecha concreta).
- `PARSED_DATE_CONFLICT`: fecha oficial ≠ CSV y el intervalo contiene una apertura mensual (material).
- `TICKER_CHANGE_CANDIDATE(...)`: el ticker aparece en una cláusula de cambio de nombre/ticker de un comunicado; un cambio de ticker NO es un cambio de membresía (hoy sólo se marca; persistirlo como evento de identidad exige securities US en el Security Master).

## Reprocesado del archivo (parser `sp500-evidence-3`)

Sin descargas: 1.396 documentos archivados (1.344 press.spglobal.com + 52 PRNewswire/Wayback) re-parseados. Patrones nuevos: «will move to the S&P 500, replacing/switching places with» (rebalanceos), «will switch places with … respectively in the S&P 500», sustituido sin ticker («X will replace Joy Global in the S&P 500», ticker resuelto en el mismo comunicado), tipografía «S& P» / «( NASD : T )», «effective before the open». El CSV de discovery sigue siendo sólo QA: un CONFLICT cuya diferencia no cruza ninguna apertura mensual se resuelve con la fecha OFICIAL (nunca se edita para coincidir con el CSV).
