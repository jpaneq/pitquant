# Filing Intelligence Layer — diseño y contrato (ADR-0048)

**Estado: DISEÑO + CONTRATO. No se llama a ningún modelo** (`LLM_CALLS_ENABLED=False`; `analyze_filing` lanza `NotImplementedError`). Código: `src/pitquant/research/filing_intelligence.py`. Tabla: `filing_analysis_snapshots` (migración 0026, append-only).

## Objetivo
Convertir un filing SEC (10-K, 10-Q, 8-K, ...) en una lectura ESTRUCTURADA, versionada y auditable que pueda compararse con las features numéricas, sin que el texto libre entre jamás como feature.

## `FilingAnalysisSnapshot` (esquema `filing-analysis-1`)
Identidad: `accession_number`, `security_id`, `issuer_id`, `form`, `period_end`, `accepted_at`, `filing_available_at`, `document_hash` (SHA-256 del documento archivado).
Versionado: `analysis_schema_version`, `prompt_version`, `model_provider`, `model_name`, `model_version`. Un prompt o un modelo nuevo = snapshot NUEVO (clave única sobre toda la tupla); nunca se edita.
Resultado: `blocks` (18), `status` (COMPLETE/PARTIAL/FAILED), `confidence` (0–1), `warnings`, `analysis_available_at`, `is_retrospective`.

### Los 18 bloques
`business_model`, `revenue_drivers`, `segments`, `geographic_exposure`, `customer_concentration`, `competition`, `moat_signals`, `growth_outlook`, `margin_outlook`, `capex_plans`, `capital_allocation`, `debt_liquidity`, `new_risk_factors`, `removed_risk_factors`, `legal_regulatory`, `accounting_quality`, `management_tone`, `guidance_changes`.

Cada bloque es **sólo enums**: `signal` (IMPROVING/STABLE/DETERIORATING/MIXED/NOT_STATED), `magnitude` (NONE/LOW/MEDIUM/HIGH/NOT_STATED), `change_vs_prior` (NEW/INCREASED/UNCHANGED/DECREASED/REMOVED/NOT_COMPARABLE) y `evidence`. El campo `note` (≤ 300 caracteres) es sólo para mostrar y no entra en `feature_vector`.

### Evidencia obligatoria
Un bloque que afirma algo (cualquier valor distinto de NOT_STATED / NOT_COMPARABLE) debe llevar ≥ 1 `Evidence`: sección, cita (≤ 30 palabras: es un puntero, no una copia del filing) y offsets de carácter en el documento archivado. Sin evidencia el bloque no puede afirmar nada (validación).

### Codificación numérica
`feature_vector()` codifica los enums (`signal` −1/0/+1, `magnitude` 0–3, `change` −1/0/+1); NOT_STATED / NOT_COMPARABLE = `None`, nunca 0.

## Regla PIT
Un snapshot es utilizable en T sólo si `filing_available_at ≤ T` **y** `analysis_available_at ≤ T`. Un análisis generado después del filing (siempre el caso de un backfill) es `is_retrospective` y sólo cuenta desde su propia fecha: un backfill hecho en 2026 sobre un filing de 2015 NO es utilizable para una decisión de 2015. `pit_snapshots(snaps, T)` devuelve el último utilizable por accession. `available_at` del filing = `ACCEPTANCE-DATETIME` (ADR-0019), nunca la fecha del periodo.

## Salidas LLM (cuando se active)
Salida JSON validada contra este esquema (pydantic, `extra="forbid"`); si no valida ⇒ `FAILED` y se guarda el intento con su error, nunca un resultado parcial sin marcar. Temperatura 0, semilla y versión de modelo registradas. Sin acceso a internet ni a datos posteriores a `filing_available_at` dentro del prompt (el documento archivado es la única entrada).

## Protocolo de comparación (A/B/C/D)
Sobre la MISMA muestra DEV, mismas fechas y mismos objetivos que `docs/RUN3_CONTINUOUS_FEATURES_REPORT.md`:
- **A** — baseline ingenuo (tasa base, momentum, baja volatilidad).
- **B** — features numéricas V1 (técnicas + fundamentales).
- **C** — sólo Filing Intelligence (`fi_*`).
- **D** — B + C.

Criterio: D debe superar a B fuera de muestra (folds expansivos purgados, no solapados) con intervalo de confianza que excluya 0 y estabilidad por periodo/región/régimen; C por sí sola no justifica nada. Cobertura mínima: sólo EE. UU. con filings archivados; el resto es `NOT_REGISTERED`.

## Fuera de alcance de esta entrega
Llamadas reales a un LLM, entrenamiento, ajuste de prompts, cualquier uso en la revisión viva o en la rutina.
