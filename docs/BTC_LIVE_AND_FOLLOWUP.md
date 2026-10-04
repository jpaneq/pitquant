# BTC: mercado en vivo y seguimiento de predicciones

## Tres conceptos separados
1. **LIVE MARKET DISPLAY** (`GET /btc/market/live`): `ticker/price` + `ticker/24hr` de Binance Spot (`data-api.binance.vision`, respaldo `api.binance.com`, sin clave). Lleva `retrieved_at` (`timestamp_kind=RETRIEVED_AT`; el endpoint no da hora de trade y no se inventa). Frescura: LIVE ≤10 s, RECENT ≤60 s, STALE >60 s, UNAVAILABLE.
2. **DAILY MODEL DATA**: última vela 1D UTC con `closeTime <= ahora`. La vela abierta se muestra aparte como `INCOMPLETE` y nunca entra en features, predicciones ni replay.
3. **SYNTHETIC TEST DATA**: sólo con `PITQUANT_E2E_FIXTURE=1`. Sin red: precio live → archivo real más reciente (`STALE`) → `UNAVAILABLE` («REAL DATA UNAVAILABLE»). Nunca fixture como respaldo.

`GET /btc/market/bars?range=1M|3M|6M|1Y|3Y|MAX`: velas diarias cerradas reales archivadas; un día ausente es un hueco (`gap_before`), no se interpola. Funding, OI, basis y red (Coin Metrics) salen del archivo real con `as_of`, `available_at`/`first_knowledge_at` y caducidad (`STALE`).
Al crear una simulación con `use_live_reference`, el servidor guarda la cotización (precio, `retrieved_at`, fuente, frescura) en `data_quality.market_reference_quote`; el motor sigue con su precio y frecuencia fijados.

## Seguimiento de predicciones (`LABEL_NOT_MATURE`)
Revelar una predicción antes de que venza su horizonte es correcto que falle, pero ya no es un error opaco: la API responde 409 con `matures_at` y la UI deshabilita «Reveal Outcome» mostrando la fecha. En su lugar:
- `evaluate_due` (`btc/evaluation.py`) revela, de forma idempotente, toda predicción madura sin resultado; se ejecuta en `forward_cycle` y con `python scripts/btc_archive.py --evaluate-only` (refresca el archivo y comprueba). También `POST /btc/evaluation/run`.
- `GET /btc/evaluation`: pendientes (con fecha de madurez), evaluadas y por horizonte: error medio, sesgo, aciertos direccionales frente a «siempre sube», Brier de P(up), mejora frente a predecir 0 y frente a la media histórica de retornos a H días, y percentil del resultado en la distribución histórica conocida hasta la fecha de decisión. Muestras <10 → `INSUFFICIENT_SAMPLE`; horizontes solapados no son independientes; la historia se descargó hoy (`RETROSPECTIVE_HISTORY_NOT_PIT`).
No se entrena ni se promueve ningún modelo.
