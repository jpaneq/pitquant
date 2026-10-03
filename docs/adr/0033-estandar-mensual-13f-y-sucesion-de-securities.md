# ADR-0033 — Estándar mensual vs diario canónico, puente de identidad con la lista SEC 13(f) y sucesión de securities

**Estado:** aceptada · **Fecha:** 2026-10-03 · **Migración:** `0014` · **Amplía** ADR-0032.

## Decisiones
1. **Dos estándares.** `D02_DAILY_CANONICAL_READY` (criterio estricto anterior: cualquier cambio sin resolver o pata de CSV sin confirmar
   bloquea el segmento) y `D02_MONTHLY_RESEARCH_READY` (puerta del Research Lab). El backtest decide a `decision_at` mensuales: una
   incertidumbre sobre el día de un evento sólo bloquea la cohorte que puede cambiar (`MONTHLY_DATE_AMBIGUITY`); si el intervalo no cruza
   ningún decision_at es `DATE_UNCERTAIN_MONTHLY_INVARIANT` y no bloquea. `train_min` sigue en 60 meses.
2. **Jerarquía de evidencia.** PRIMARY: ancla SEC de SPY, comunicado oficial de S&P, presentación SEC del emisor, identificador SEC. SECONDARY:
   republicación verificable. DISCOVERY_ONLY (CSV, GitHub, Wikipedia): nunca invalida evidencia primaria consistente. Una pata extra sin
   confirmar es `DISCOVERY_UNCORROBORATED` (aviso); una fecha del CSV que discrepa de la oficial es `DISCOVERY_CONFLICT` y no ensancha la
   fecha primaria. Un posible miembro transitorio sólo bloquea si puede cambiar un decision_at mensual Y un comunicado archivado menciona el ticker.
3. **Registro por cohorte** (`Cohort`): `decision_at`, `forward_set`, `backward_set`, `sets_equal`, `primary_conflicts`, `monthly_ambiguity`,
   estado. Forward parte del ancla A y aplica sólo cambios seguros ≤ decision_at; backward parte del ancla B y deshace sólo los seguros
   posteriores. Difieren exactamente donde una security tiene un intervalo incierto que cubre el decision_at; si difieren sin explicación: falla cerrado.
   Los eventos PRIMARIOS del segmento se aplican aunque la security no esté en ninguno de los dos anclas (miembro transitorio); un par
   primario alta+baja de un ticker sin security_id bloquea las cohortes que abarca.
4. **Lista oficial SEC 13(f)** (`sec_13f_list_entries`, PDF archivados con SHA-256, 2017Q3 → 2022Q3): `OFFICIAL_SECURITY_IDENTIFIER_REFERENCE`,
   nunca fuente de membresía; un CUSIP es evidencia de ESE trimestre. Puente para N-30D identificadas sólo por nombre: nombre legal normalizado
   exacto + clase de acción, candidato ÚNICO; varios o ninguno → `UNRESOLVED`; nunca similitud difusa. Genera `security_identifier_evidence`
   (`OFFICIAL`, CUSIP, `SEC_13F_LIST`).
5. **Sucesión de securities** (`security_succession`): `NAME_CHANGE_SAME_SECURITY`, `TICKER_CHANGE_SAME_SECURITY`, `SECURITY_REPLACEMENT_SUCCESSOR`,
   `SHARE_CLASS_CHANGE`, `TRUE_INDEX_EXIT/ENTRY`, `SAME_SECURITY_IDENTITY_LINK`, con `effective_at`, ratio, `membership_continuity`, fuente y hash.
   **Un security_id nuevo no es una salida + entrada del índice**: con continuidad, el motor colapsa predecesora→sucesora (cadenas incluidas).
   Un emisor con LEI idéntico en dos NPORT-P sigue siendo transición de identidad. Seis casos investigados externamente se aplican sólo si las
   listas 13F los verifican (CUSIP antes/después; DELETED/ADDED en el trimestre de la sustitución): Discovery (A y C separadas), KLA, Aon, Seagate,
   Apache→APA, Jacobs.
6. **Gaps reclasificados** en `PRIMARY_DELTA_UNEXPLAINED`, `PRIMARY_EVENT_MISSING`, `MONTHLY_DATE_AMBIGUITY`, `SECURITY_IDENTITY_ONLY`,
   `TICKER_OR_NAME_CHANGE`, `SUCCESSOR_SECURITY`, `DISCOVERY_UNCORROBORATED`, `DISCOVERY_CONFLICT`, `TRANSIENT_EVENT_POSSIBLE`, `RESOLVED`.
   Sólo los PRIMARIOS cuentan como blockers de membresía; los de identidad se cuentan aparte.
7. **Gates separados:** `D02_MONTHLY_RESEARCH_READY`, `D02_DAILY_CANONICAL_READY`, `US_SECURITY_IDENTITY_READY`, `US_FUNDAMENTALS_READY`,
   `US_D05_RESEARCH_READY`, `BASELINE_TRAINING_READY`. Un problema de identidad no contamina las métricas de membresía.

## Límites
- La verificación de las seis resoluciones usa las listas 13F (presencia de CUSIP y estado ADDED/DELETED) además de los datos aportados; no se
  han descargado los 8-K.
- El nombre del emisor en la lista 13F está truncado («DISCOVERY COMMUNICATNS»): por eso el puente genérico exige igualdad exacta y no cubre esos casos.
- El resto de blockers primarios necesita la fecha oficial de cada cambio (`docs/SP500_LOCAL_GAPS.md`).
