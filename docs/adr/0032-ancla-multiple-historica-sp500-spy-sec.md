# ADR-0032 — Reconstrucción histórica del S&P 500 con múltiples anclas (SPY, SEC) y reconciliación local de eventos

**Estado:** aceptada · **Fecha:** 2026-10-03 · **Migración:** `0013` · **Sustituye** el enfoque de ancla única de ADR-0026/0031 como
mecanismo de readiness (el código antiguo queda como `--legacy`).

## Contexto: por qué la ancla única era estructuralmente inadecuada
Con una sola ancla (SPY/IVV, 2026-10-01) y «deshacer todos los eventos», la pertenencia en la apertura de D exige confirmar TODOS los
eventos posteriores a D: un evento sin resolver en 2025 bloqueaba una cohorte de 2018 (98 «bloqueos de cadena» 2022-10→2026 sobre la
ventana 2017-10→2022-09). Era un defecto de diseño, no de datos.

## Decisión
1. **Grafo de anclas históricas.** `SP500Anchor` / `SP500AnchorMember` (append-only): composiciones de SPY presentadas a la SEC.
   - **Tier A `SEC_NPORT_IDENTIFIED_ANCHOR`**: NPORT-P `primary_doc.xml`, Part C, CUSIP e ISIN leídos (nunca reconstruidos); LEI del emisor.
   - **Tier B `SEC_SCHEDULE_ANCHOR`**: Schedule of Investments de un N-30D (nombres + acciones + valor, sin identificadores).
   - **Tier C `MULTI_SOURCE_CURRENT_ANCHOR`**: el ancla SPY/IVV actual, intacta (no se degrada ni se sobrescribe; no se usa pre-holdout).
   Cada ancla se **verifica contra EDGAR** (CIK 0000884394, formulario y periodo, en las submissions y en la cabecera de la presentación
   completa); cualquier discrepancia aborta ANTES de guardar nada (`AnchorVerificationError`).
2. **No son `OFFICIAL_SPDJI`.** `evidence_kind = SEC_FILED_INDEX_REPLICATION_ANCHOR`: es la cartera de un ETF que replica el índice. El
   hallazgo del cross-check lo confirma: el N-30D de 2022-09-30 incluye EQT y PG&E, comprados al cierre para su efectividad el 2022-10-03,
   que el NPORT-P (estado del índice) no incluye. Para un ancla Tier B se retiran de su conjunto las altas CONFIRMADAS con efecto en la
   sesión siguiente.
3. **Dos relojes, nunca mezclados.** `as_of_date` (estado descrito) ≠ `source_available_at` (aceptación SEC, semanas después; CHECK
   `source_available_at >= as_of_date`). Las anclas son **dato de referencia histórico**: ningún módulo de features, analyzer, backtest ni
   API puede importarlas (test estático).
4. **Identidad en espacio de `security_id`** (CUSIP → ISIN → evidencia de emisor/nombre; el ticker sólo auxiliar). `SecurityIdentifierEvidence`
   (`OFFICIAL`, `SEC_NPORT_P_HOLDING`) por cada ancla: el mismo CUSIP en anclas consecutivas forma la cadena. Un cambio de ticker con el mismo
   CUSIP es un evento de identidad, no salida + entrada. Un emisor con LEI idéntico en dos NPORT-P (HCP→Healthpeak, BB&T→Truist,
   CBS→ViacomCBS, Symantec→NortonLifeLock…) es una **transición de identidad** (linaje), no un cambio de membresía. El enlace schedule↔NPORT
   se hace por (precio por acción, acciones) de la MISMA fecha con unicidad mutua; el resto, por nombre único; si no, `NAME_ONLY`.
5. **Segmentos entre anclas consecutivas**, validados de forma independiente (`SP500MembershipSegment`): sólo cuentan los eventos con efecto
   en (A, B]. Para cada security se construye una línea temporal con intervalos de efectividad posibles (exacto si el evento oficial está
   confirmado; ventana si hay conflicto de fecha; (anuncio, B] si el comunicado no da fecha; todo el segmento si nada). Replay **forward**
   (A + eventos = B) y **backward** (B − eventos = A); el delta no explicado se clasifica (`MISSING_ADDITION_EVENT`, `MISSING_REMOVAL_EVENT`,
   `SECURITY_IDENTITY_GAP`, `DATE_CONFLICT`, `DATE_MISSING_IN_RELEASE`, `TRANSIENT_HOLDING`, `TICKER_ALIAS_ONLY`, `UNEXPLAINED`).
6. **Cohorte `MEMBERSHIP_READY`** (apertura del primer día hábil del mes) si ninguna security tiene un intervalo incierto que la cubra, no hay
   holdings de las dos anclas sin resolver y el segmento no está bloqueado. Nada posterior a la ancla B puede invalidar una cohorte anterior.
7. **Holdout.** Sólo se cargan anclas con `as_of <= 2022-09-30`; la de 2022-09-30 termina la cadena pre-holdout.
   `post_limit_events_used = 0` y un test lo exige. No se ha ingerido ningún ancla posterior.
8. **Modo ESTRICTO (puerta) vs INDULGENTE (QA).** Las patas sin confirmar del CSV de discovery nunca aportan fechas. En estricto bloquean
   su segmento si exceden los cambios visibles en las anclas o si el mismo ticker se añade y retira dentro del segmento (miembro transitorio
   invisible). El «% de eventos del CSV confirmados» deja de ser métrica principal (QA).
9. **Posiciones residuales.** SPY conserva restos de acciones que salen del índice o de spin-offs (1 acción de Vontier, 14 k USD de Embecta).
   Se clasifican `TRANSIENT_CORPORATE_ACTION` (valor < 1 M USD; el menor miembro genuino de 2019-2022 vale > 12 M USD).
10. **Gates separados.** `D02_RESEARCH_READY` (≥60 cohortes consecutivas pre-holdout), `US_IDENTITY_READY`, `US_FUNDAMENTALS_READY`,
    `US_D05_RESEARCH_READY` y `BASELINE_TRAINING_READY` (≥96 cohortes y ≥2 folds OOS con `train_min = 60`, sin tocar). Los fundamentales no
    bloquean D-02.

## Consecuencias y límites
- Las anclas trimestrales/semestrales sólo acotan los cambios; **la fecha exacta de cada cambio sigue necesitando evidencia oficial**. Los
  gaps son LOCALES (`docs/SP500_LOCAL_GAPS.md`) y sólo bloquean su segmento.
- Un miembro transitorio entre dos anclas es invisible para ellas: sólo lo cubre un comunicado archivado o el control estricto del CSV.
- Los cambios de CUSIP sin LEI común (re-domiciliaciones, holdings, N-30D sin identificadores) quedan como `SECURITY_IDENTITY_GAP` con pista
  de continuidad (solapamiento de tokens + ratio de acciones); no se fusionan por heurística.
- El grafo cubre 2017-09-30 → 2022-09-30; no se han buscado anclas anteriores (el criterio era 60/60 primero).
