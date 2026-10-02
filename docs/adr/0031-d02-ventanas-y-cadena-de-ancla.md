# ADR-0031 — Diagnóstico exacto de ventanas D-02, evidencia oficial sobre CSV y demanda D-05

**Estado:** aceptada · **Fecha:** 2026-10-03 · **Sin cambio de esquema** (migraciones 0001…0012 intactas)

## Contexto
D-02 y D-05 bloquean el primer `ResearchExperiment`. El objetivo ya no es cobertura global 2011→hoy sino una
ventana continua PRE-holdout de ≥60 meses (preferida 96): 2017-10→2022-09 y 2014-10→2022-09.

## Hallazgo estructural (cadena de ancla única)
La reconstrucción parte de UNA ancla (SPY/IVV, 2026-10-01) y deshace eventos hacia atrás. La pertenencia en la
apertura de D exige TODOS los eventos posteriores a D confirmados, también los de 2022-10→2026. Por tanto:
- un evento sin confirmar en 2024 bloquea cohortes de 2018 aunque esté fuera de la ventana;
- `pitquant sp500-window-readiness` separa **bloqueos dentro de la ventana** y **bloqueos de cadena** (posteriores) y
  muestra, como HIPOTÉTICO (nunca estado), cuántas cohortes se demostrarían con una segunda ancla verificada al final
  de la ventana. Una segunda ancla (composición verificada ~2022-09/10) desacoplaría la ventana de los eventos del
  periodo holdout/posterior; **la fuente es trabajo externo** (no se ha buscado).
- Los cambios de ticker de miembros (FLT→CPAY, GDI→IR, IR→TT, DWDP→DD, UTX→RTX…) rompen la reversibilidad en espacio
  de tickers aunque todos los eventos estén confirmados: hace falta una tabla fechada de alias/identidad
  (CUSIP/CIK) con evidencia oficial. Hoy sólo se **marcan** (`TICKER_CHANGE_CANDIDATE`); persistirlos como eventos de
  identidad exige securities US en el Security Master. Un cambio de ticker NO es un cambio de membresía.

## Decisiones
1. **Oficial > CSV.** El CSV de discovery sigue siendo QA. Un `CONFLICT` (fecha oficial ≠ CSV) cuyo intervalo no
   contiene ninguna apertura mensual es **inmaterial**: se aplica la fecha OFICIAL (nunca se edita para coincidir con
   el CSV) y se lista (`D02Report.immaterial_conflicts`). Si el intervalo cruza una apertura, sigue bloqueando.
2. **Reprocesado offline del archivo** (`scripts/ingest_sp500_evidence.py --offline`, sin red): 1.396 documentos ya
   archivados. Parser `sp500-evidence-3`: «will (all) move to the S&P 500, replacing / switching places with»
   (rebalanceos), «will switch places with … respectively in the S&P 500», sustituido sin ticker (resuelto en el
   mismo comunicado, nunca adivinado), tipografía «S& P» y «( NASD : T )», «effective before the open», y legs con
   fechas distintas (alta y baja separadas: hay un intervalo de 501 miembros). Las listas de distinta longitud NO se
   emparejan. Resultado: bloqueos dentro de la ventana mínima 91 → 60 y preferida 134 → 97.
3. **Fichas de gap** (`docs/SP500_GAP_CARDS.md/.json`, generadas): effective/announcement date, tickers y nombres,
   fuente discovery, fuente oficial archivada, `parser_status` (`NO_DOCUMENT`, `PARSER_MISS`, `PARSED_NO_DATE`,
   `PARSED_DATE_CONFLICT`, `PARSED_BUT_NOT_MATCHED`), identidad y qué falta. La investigación externa la hace el propietario.
4. **Demanda D-05 sin llamadas** (`pitquant tiingo-backfill-plan`, `docs/US_MARKET_BACKFILL_PLAN.md`): membresía
   CANDIDATA (ancla con todos los eventos deshechos de forma permisiva), etiquetada `CANDIDATE_MEMBERSHIP_NOT_PROVEN`;
   cota superior de símbolos, no universo ni cobertura del proveedor. Dividendos/splits `REQUIRED_UNVERIFIED`; CA complejas `UNKNOWN`.
5. **Walk-forward**: con la configuración por defecto (train_min 60m) la ventana de 60 cohortes da **0 folds**; la de 96
   da 3 (6M) y 2 (12M). No se cambia la configuración sin decisión del propietario.
6. **`US_BASELINE_V0`** se registra `BLOCKED` con las puertas cerradas de `research_readiness` (no una lista a mano);
   sin dataset mientras la pertenencia no esté probada; sin entrenar.
7. `ExperimentSpec.commit_sha` añade `+dirty` si el árbol difiere de HEAD.

## No cambia
Ancla `MULTI_SOURCE_CONFIRMED` (no `OFFICIAL_SPDJI`), 51 features V0, holdout sellado, Analyzer V0, sin BTC.
`D02_RESEARCH_READY` sigue exigiendo ≥60 cohortes consecutivas probadas, reversibles, sin eventos sin resolver.
