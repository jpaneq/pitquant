# ADR-0025 — Evidencia de membresía S&P 500 (candidato D-02 desde fuentes públicas)

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0017, ADR-0024 · **Migración:** `0009`

## Contexto
Sin un universo histórico del S&P 500 no se puede medir la cobertura de former/delisted constituents
(test crítico de Tiingo) ni empezar cohortes US. El fichero licenciado de S&P DJI sigue sin estar.

## Decisión
1. **Jerarquía de fuentes.** Tier 1 `OFFICIAL_SPDJI`: comunicados en `press.spglobal.com`. Tier 2
   `OFFICIAL_REPUBLISHED`: copia en PRNewswire (captura Wayback `id_`) de un comunicado emitido por S&P
   (se exige firma S&P, boilerplate «About S&P» y texto con los cambios concretos). Tier 3
   `DISCOVERY_ONLY`: CSV comunitario (MIT) y Wikipedia: sólo descubren; **nunca** son membresía.
2. **Modelo temporal.** Cada evento distingue `announcement_at`, `stated_change_date`, `timing`
   (`AFTER_CLOSE | BEFORE_OPEN | EFFECTIVE_ON_DATE | TBA | UNKNOWN`) y `effective_at` = apertura NYSE de
   la primera sesión en la que el cambio rige, con el calendario real (tras el cierre del viernes
   2011-04-01 → lunes 2011-04-04; tras el cierre del lunes 2012-07-30 → 2012-07-31). Un `TBA` prueba
   intención, no fecha. Un universo «al inicio de la sesión s» contiene un ticker si `effective_at <= apertura(s)`.
3. **Estados por evento:** `OFFICIAL_CONFIRMED`, `OFFICIAL_REPUBLISHED_CONFIRMED` (únicos que pueden
   alimentar el universo canónico), `DISCOVERY_ONLY`, `DATE_TBA`, `CONFLICT` (la fecha efectiva oficial
   difiere del CSV: nunca se corrige lo oficial), `UNRESOLVED` (un solo lado del par, fecha no
   resoluble, ticker distinto).
4. **No se impone 1 alta = 1 baja ni 500 líneas.** Altas y bajas sueltas son eventos independientes;
   se clasifica el motivo (spin-off, fusión/adquisición, quiebra, no representativa) sólo como dato.
5. **Persistencia (append-only):** `sp500_discovery_rows`, `sp500_announcements` (una fila por cláusula
   «X will replace Y in the S&P 500», versionada por `parser_version`) y `sp500_membership_events` (una
   *run* por ejecución; la última es la vigente). Todo documento se archiva (URL, SHA-256) antes de parsear.
6. **Reconstrucción.** `undo_events` / `replay_events` son estrictas (fallan si un evento no es
   aplicable) y reversibles: ancla → deshacer → rejugar → ancla. Con un solo evento sin resolver, las
   fechas dependientes no son canónicas (fail-closed). El ancla actual es `CURRENT_ANCHOR_BLOCKED` si la
   página de S&P DJI no se puede archivar (hoy: HTTP 403).
7. **Estados D-02:** `SP500_MEMBERSHIP_DISCOVERY_READY`, `…_EVIDENCE_COVERAGE`, `…_CANONICAL_READY`
   (`pitquant sp500-evidence`). CANONICAL_READY exige ancla archivada y cero eventos sin confirmar.
8. **Identidad separada de membresía.** El ticker de un comunicado no es identidad: `added_security_id` /
   `removed_security_id` quedan nulos hasta resolverlos con el Security Master (CIK/CUSIP/ticker fechado).

## Límites
- El archivo de prensa de S&P Global sólo trae cambios de índice desde ~2014 y PRNewswire sólo es
  localizable por el índice CDX de Wayback: los huecos se listan en `docs/SP500_MEMBERSHIP_EVIDENCE.md`
  para investigación externa; no se completan con el CSV.
- El parser cubre las formas «A will replace B in the S&P 500» (par único y listas posicionales
  «respectively») con fecha en la frase, en el encabezado resumen, en la tabla de fecha efectiva o en la
  introducción; el resto queda `UNRESOLVED`, no adivinado.
