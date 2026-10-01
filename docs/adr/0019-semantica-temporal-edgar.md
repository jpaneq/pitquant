# ADR-0019 — Semántica temporal de EDGAR: zona horaria de cada campo y fuente canónica

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Amplía:** ADR-0015 · **Cierra:** discrepancia
«header EST vs submissions UTC»

## Contexto
La especificación oficial de difusión de EDGAR (PDS Technical Specification,
`sec.gov/files/edgar/pds_dissemination_spec.pdf`, pág. 10) define «Acceptance Time … Time
(EST) at which the submission was accepted by EDGAR». Por otro lado, el campo
`acceptanceDateTime` de `data.sec.gov/submissions` lleva sufijo `Z`.

Una iteración anterior concluyó «submissions es UTC» sin una referencia independiente. No
basta con que «parezca coincidir».

## Investigación reproducible
`scripts/edgar_time_investigation.py` descarga y **archiva** (`raw_source_archive`, SHA-256),
para 10 filings reales de MSFT y AAPL, todas las representaciones disponibles:

| Fuente | Campo | Zona declarada en el propio valor |
|---|---|---|
| H header `.hdr.sgml` | `<ACCEPTANCE-DATETIME>YYYYMMDDHHMMSS` | ninguna |
| I página índice `-index.htm` | «Accepted» `YYYY-MM-DD HH:MM:SS` | ninguna |
| S `submissions` JSON | `acceptanceDateTime` `…T…Z` | sufijo `Z` |
| A feed Atom de la compañía (`browse-edgar … output=atom`) | `<updated>` | **desfase explícito** (`-05:00`/`-04:00`): es la propia SEC declarando la zona del mismo instante, no un reloj independiente |
| L HTTP de `{acc}.txt` | `Last-Modified` | GMT (RFC 7231) |
| F submissions / índice | `filingDate` / «Filing Date» | fecha (sin hora) |

**Casos cubiertos:**
- invierno y verano;
- antes de la apertura (06:00 y 08:01);
- en sesión (11:03 y 15:04);
- en torno a las 16:00 (16:00:33 y 16:01:56);
- 17:16 (antes del corte de las 17:30) y 18:02 / 18:12 (después);
- el lunes posterior al fin del horario de verano (2018-11-05).

**Resultados:** aritmética sobre los valores brutos, en
`docs/edgar_time_investigation.json`.

| Hipótesis | Diferencia frente a A (reloj con desfase explícito) |
|---|---|
| H leído como hora del Este (con DST) | **0 s en 10/10** |
| H leído como UTC | −14.400 s (verano) / −18.000 s (invierno) en 10/10 |
| S leído como UTC | **0 s en 6/6** (los 4 filings antiguos no están en la página `recent`) |
| S leído como hora del Este | +4 h / +5 h |

Además:
- I coincide con el reloj de pared de H en 10/10.
- L es siempre ≥ H leído como hora del Este. En filings recientes la diferencia es de
  74–542 s; los ficheros antiguos se reescribieron en 2017, así que L es un reloj débil.
- F cumple exactamente la regla del corte de las 17:30 hora del Este (18:02 → día hábil
  siguiente; 17:16 → mismo día) sólo si H se lee como hora del Este.

## Decisión
1. **Header H:** hora de pared **US/Eastern con DST** (EST en invierno, EDT en verano). El
   «EST» de la documentación es un término genérico para la hora del Este.
   - Conversión: `eastern_wall_clock_to_utc`.
   - Una hora ambigua (repetida al atrasar el reloj) o inexistente (al adelantarlo) se
     resuelve con el **instante candidato posterior**: *fail closed*.
2. **Submissions S:** **UTC genuino**. Sólo sirve para comprobación cruzada, siempre leído
   como UTC (`submissions_acceptance_utc`). Se elimina la tolerancia doble anterior (UTC o
   Este). Un valor sin zona o ilegible no es de confianza.
3. **Página índice I:** el mismo reloj de pared que H. No se usa como fuente.
4. **Feed Atom A:** representación de la propia SEC del mismo instante, con el desfase
   explícito. Es la prueba principal de la zona. La corroboración **independiente** es el
   cambio de `filingDate` en el corte de las 17:30 hora del Este. Se usa en la
   investigación y en los tests de regresión, no en la ingestión.
5. **`filingDate` F:** fecha de presentación según el corte de las 17:30 hora del Este.
   **Nunca** determina la disponibilidad.
6. **HTTP `Last-Modified` L:** no es una marca de aceptación (los ficheros se reescriben). No
   se usa.
7. **Fuente canónica de PITQuant:** `accepted_at` = H convertido a UTC según el punto 1.
8. `effective_available_at` (columna `available_at`) =
   `filing_available_at(calendario XNYS, accepted_at, política, retardo)` (ADR-0015).
   **Si H y S discrepan** más de 120 s, la incertidumbre es residual y se aplica *fail
   closed*:
   - `available_at = max(política, next_session_open(max(H, S)))`;
   - `availability_policy` termina en `+mismatch_fail_closed`;
   - se registra la incidencia `acceptance_mismatch`.
9. Los valores internos se almacenan siempre en UTC (`UTCDateTime`). Ningún parser convierte
   implícitamente:
   - el header se parsea como hora de pared sin zona y se le asigna la zona explícitamente;
   - `fromisoformat` respeta la `Z`.

## Consecuencias y tests
`tests/unit/test_edgar_time_real.py` fija todo esto contra los **bytes reales archivados**
(`tests/fixtures/sec_real/`):
- H coincide con A, y el desfase sigue el DST;
- I = H;
- S es UTC;
- leer S como hora del Este da discrepancia;
- se cumple el corte de las 17:30;
- L ≥ H;
- casos DST ambiguos o inexistentes (sólo con fixtures: ningún filing real cae en esa hora);
- valores ilegibles.

Los 126 filings reales ya ingeridos cumplen la comprobación estricta (0 discrepancias), así
que su disponibilidad no cambia. D-01 queda validada en su semántica temporal.
