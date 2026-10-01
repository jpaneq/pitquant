# ADR-0015 — Fundamentales SEC con procedencia por accession

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Resuelve:** D-01

## Decisión
- Fuente primaria: SEC EDGAR. `companyfacts` sólo para descubrimiento, descarga eficiente,
  validación y caché. La procedencia temporal se resuelve por **accession**.
- Por cada accession con hechos: metadatos de *submissions* (CIK, form, filing date,
  report period, primary document) + **header** `.hdr.sgml` con `ACCEPTANCE-DATETIME`
  (hora del Este) → `accepted_at`. El header y la instancia XBRL del filing se archivan.
- El campo `acceptanceDateTime` de *submissions* se guarda sólo como contraste; si no
  coincide con el header (interpretado como UTC o como hora del Este) se registra un aviso
  de calidad y manda el header.
- Cada hecho es una **versión** inmutable ligada a `security_id, cik, accession_number,
  form, period_start, period_end, filed_date, accepted_at, taxonomy, concept, unit, value,
  source_document, is_amendment, ingested_at`. Las reexpresiones y comparativos posteriores
  son versiones nuevas; `facts_as_of` elige la disponible en `as_of`.
- Hechos cuyo accession no tiene header verificado → rechazados (`fact_without_filing`).
  Valores de companyfacts que contradicen la instancia XBRL del propio filing → rechazados
  (`companyfacts_xbrl_mismatch`). En re-ingestas se revalida desde la instancia archivada.
- `available_at` ≠ `period_end` ≠ `filed_date`. Política `conservative_session` (defecto):
  aceptado en sesión y `accepted_at + lag` antes del cierre → `accepted_at + lag`; en otro
  caso (tras el cierre, fin de semana, festivo, o lag que cruza el cierre) → apertura de la
  siguiente sesión. Alternativa `accepted_plus_lag` para investigación intradía.
- Cobertura inicial: filings desde **2011-01-01** (era XBRL); el diseño admite backfill
  anterior sin cambios de esquema.
- Cliente HTTP: User-Agent con contacto obligatorio (`PITQUANT_SEC_USER_AGENT`), límite de
  peticiones configurable, reintentos con backoff exponencial, transporte inyectable.

## Consecuencias
+ Ninguna cifra corregida en 2025 puede aparecer en un snapshot de 2024.
− Más peticiones (header + índice + instancia por filing); mitigado por idempotencia y
  archivo local.
− Los conceptos se guardan tal cual en la taxonomía (sin normalizar todavía); la
  normalización (revenue, EBIT, deuda…) es trabajo del Feature Engine.
