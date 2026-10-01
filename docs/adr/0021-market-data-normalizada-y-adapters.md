# ADR-0021 — Market data normalizada, adapters por proveedor, corporate actions y total return

**Estado:** aceptada · **Fecha:** 2026-10-01 · **Amplía:** ADR-0004, ADR-0012 ·
**Migración:** `0004` (tablas `corporate_action_events`, `provider_adjusted_prices`)

## Contexto
El propietario ha fijado las decisiones de proveedor (gestión externa; aquí no se evalúan
costes):

| Dato | EE. UU. | España |
|---|---|---|
| Fundamentales | SEC EDGAR (sin cambio) | CNMV |
| Precios | Sharadar SEP (proveedor preferido futuro) | EODHD (proveedor práctico) |
| Membership | Sharadar SP500 = candidato técnico; el fichero S&P DJI sigue siendo el objetivo canónico (D-02) | — |
| Identidad | — | CNMV ANCV + BME (ADR-0020) |
| Corporate actions | — | oficial BME/CNMV primero; EODHD sólo complementa precios, dividendos, splits y deslistados |
| QA de ciclo de vida | Alpha Vantage, sólo QA | — |

Todavía no hay claves de API. Los adapters deben poder construirse y probarse sin ellas.

## Decisión

### 1. Capa normalizada (`pitquant.market.normalized`)
`Provider → raw archive → parser → registro normalizado → validación PIT → almacenamiento`.

- **Registros:** `MarketBar` (OHLCV RAW), `CorporateAction`, `ListingEvent`, `TickerEvent`,
  `DelistingEvent` y `SecurityListing`.
- **Aislamiento:** ningún proveedor escribe lógica propia en el backtester; el backtester y el
  motor de total return sólo leen registros normalizados.
- **`store_batch`:**
  - rechaza claves de proveedor sin `security_id` probado;
  - rechaza `available_at` futuro o anterior al hecho que describe;
  - guarda las barras RAW en `prices`;
  - guarda el ajustado del proveedor sólo en `provider_adjusted_prices` (QA);
  - guarda las acciones en `corporate_action_events` (append-only, idempotente por proveedor,
    id y hash).

### 2. Modelo de corporate actions
- **Tipos:** CASH_DIVIDEND, SPECIAL_DIVIDEND, STOCK_DIVIDEND, SPLIT, REVERSE_SPLIT, RIGHTS_ISSUE,
  SCRIP_DIVIDEND, SPINOFF, CASH_ACQUISITION, STOCK_ACQUISITION, MERGER, DELISTING, BANKRUPTCY,
  TICKER_CHANGE y EXCHANGE_CHANGE, más LISTING, RETURN_OF_CAPITAL e ISIN_CHANGE.
- **Campos de cada evento:**
  - fechas `announcement_date`, `ex_date`, `record_date`, `payment_date` y `effective_date`;
  - `available_at`, `source` (proveedor y tier OFFICIAL/VENDOR/FIXTURE), `source_hash`,
    identificador crudo del proveedor y versión del parser.
- **Campos obligatorios por tipo:** las fechas que faltan quedan NULL; nunca se infieren.
- **Eventos españoles complejos** (ampliación con derechos, scrip, OPA, fusión, canje):
  - si vienen de un proveedor (tier VENDOR), se rechazan como canónicos
    (`requires_official_source`) y generan un DQ issue;
  - deben venir de la capa oficial BME/CNMV.

### 3. Nunca precios ajustados como fuente primaria
- **Serie base:** el OHLCV RAW.
- **Ajustes:** se reconstruyen desde las corporate actions.
- **Ajustado del proveedor:** sólo sirve para comparar y detectar discrepancias.
- **Si el proveedor sólo publica una columna ajustada:**
  - Sharadar SEP publica open, high, low, close y volume ajustados por splits, y sólo
    `closeunadj` sin ajustar;
  - EODHD publica el volume ajustado por splits;
  - se desajustan con el factor de split y se marcan en `imputed_fields`.

### 4. Adapters
- **`SharadarMarketDataProvider`.** Usa el esquema público oficial (sharadar.com/docs: stocks,
  actions, tickers, sp500) y la URL `api.sharadar.com/v1.0/data/{tabla}` con `api_key`.
  - **Identidad:** los tickers se reutilizan, así que se usa `permaticker` resuelto por ticker
    Y fecha; si es ambiguo, se rechaza.
  - **Adquisiciones:** se normalizan como MERGER + DelistingEvent(ACQUIRED), porque Sharadar no
    da el tipo de contraprestación. Nunca se adivina si fue en efectivo o en acciones.
  - **Semánticas sin verificar:**
    - si el `value` del dividendo está ajustado por splits (la documentación oficial y fuentes
      de terceros discrepan; se marca `value_basis=UNVERIFIED`);
    - la dirección de `tickerchangefrom/to`.
- **`SharadarSP500MembershipProvider`.**
  - **Reconstrucción:** se ancla en las filas `current` y se recorre hacia atrás con `added` y
    `removed`.
  - **Validación:** cada snapshot `historical` debe coincidir; si no, falla cerrado.
  - **Tickers:** una baja y una alta con el mismo permaticker en la misma fecha son un
    TICKER_CHANGE.
  - **Fecha:** la `date` de SP500 se trata como fecha efectiva, SIN VERIFICAR, hasta cruzarla con
    anuncios oficiales de S&P DJI (`cross_check_announcements` falla cerrado).
  - **Estado:** `ADAPTER_CONTRACT_TESTED` con fixtures; pasaría a `CANONICAL_CANDIDATE` sólo
    con la suite sobre datos reales. Sustituir el fichero S&P DJI exigirá un ADR posterior.
- **`EODHDMarketDataProvider`.** Usa la documentación técnica pública:
  - el OHLC es raw y `adjusted_close` sólo sirve para QA;
  - el volumen está ajustado por splits;
  - el dividendo es `unadjustedValue`, con las fechas de declaración, registro y pago;
  - el split se lee del formato "new/old";
  - los deslistados conservan su histórico y un símbolo renombrado devuelve vacío (el ticker
    no es identidad).
- **`AlphaVantageLifecycleQAProvider`.** Sólo QA de altas y bajas (`LISTING_STATUS`): devuelve
  discrepancias y nunca precios ni membership.
- **Sin clave:** `SOURCE_NOT_CONFIGURED`. La normalización funciona igual y nada más falla.
  Las claves se leen sólo del entorno y `redact()` las elimina de cualquier URL archivada.

### 5. Motor de total return (`pitquant.market.total_return`)
- **Retorno diario:** `R_t = s_t·(P_t + D_t)/P_{t−1} + V_t/P_{t−1}`, sobre cierres RAW y
  usando sólo las acciones con `available_at ≤ as_of`.
- **Spin-offs, derechos y scrip:** exigen una valoración; sin ella, `InsufficientValuationError`
  (nunca un cero silencioso).
- **Eventos terminales:**
  - adquisición en efectivo: el efectivo;
  - adquisición en acciones: ratio × precio del adquirente, que es obligatorio;
  - quiebra: la recuperación declarada, o 0;
  - deslistado sin contraprestación: el último cierre, con aviso.
- **Validación:** sólo con fixtures por ahora (casos D-05 verificados con precios inventados).
  No se usa el holdout.

### 6. Cobertura y analizador
- **`pitquant.coverage.security_coverage`** informa, por security y periodo, de identidad,
  precios, fundamentales (por emisor), corporate actions, benchmark y sector. Estados:
  `COMPLETE`, `PARTIAL`, `INSUFFICIENT` y `UNRESOLVED_IDENTITY`; la identidad domina.
- **`pitquant.analyzer.eligibility.support_decision`** decide SUPPORTED_SECURITY sólo a partir
  de la cobertura. La pertenencia a un índice no es una entrada: SUPPORTED_SECURITY ≠
  INDEX_MEMBERSHIP. Sin scoring.

## Consecuencias
- **`data-readiness` separa:**
  - adapter (código) de dato real;
  - identidad US de identidad ES;
  - IBEX 2011+ de IBEX anterior a 2011.
- **Un adapter terminado nunca marca READY la fuente.**
- **Bloqueos por credencial** (`BLOCKED_BY_CREDENTIAL`): Sharadar (incluido el sample oficial,
  que también requiere clave), EODHD y Alpha Vantage.
- **Al tener claves:**
  1. ejecutar la suite D-05 y los contract tests sobre datos reales;
  2. resolver las semánticas sin verificar;
  3. etiquetar `REAL_DATA_FULLY_VALIDATED`.
