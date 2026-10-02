# ADR-0026 — Ancla S&P 500 desde SPY/IVV y reconstrucción D-02

**Estado:** aceptada · **Fecha:** 2026-10-02 · **Amplía:** ADR-0025 · **Migración:** `0010`

## Decisión
1. **`SP500_CURRENT_ANCHOR`** se construye con los holdings diarios de SPY (State Street, `.xlsx`) e IVV
   (iShares, `latest-holdings.csv`). Estados: `OFFICIAL_SPDJI` (nunca desde ETF), `MULTI_SOURCE_CONFIRMED`,
   `CONFLICT`, `BLOCKED`. Cada fichero y página se archiva (URL, SHA-256) antes de parsear.
2. **Equities por regla, no por recuento.** Se excluyen: clase de activo ≠ Equity, líneas de caja, tickers sin
   símbolo, tickers numéricos (placeholders de CVR/derechos), CUSIP con dígito de control inválido y líneas
   «NO MARKET» (restos no cotizados de valores excluidos). SPY e IVV no tienen por qué coincidir en número.
3. **Claves.** SPY aporta CUSIP y SEDOL; el CSV público de IVV **no** trae CUSIP/ISIN (discrepancia con la
   descripción del propietario, documentada en `docs/SP500_CURRENT_ANCHOR.md`). IVV se reconcilia por
   ticker normalizado (`BRK.B ≡ BRK-B ≡ BRK B` sólo si los nombres son compatibles) y, si el emisor cambió de
   nombre, por ticker + peso (±20 %), dejando constancia.
4. **Fechas distintas.** El snapshot más antiguo se avanza con los eventos S&P confirmados oficialmente entre
   ambas fechas antes de comparar; una diferencia sin explicar es `CONFLICT`.
5. **Reconstrucción.** Con ancla `MULTI_SOURCE_CONFIRMED`: anclar → deshacer eventos confirmados →
   snapshots históricos → rejugar → ancla (reversibilidad exacta o ninguna cohorte es canónica). La
   membresía al abrir la sesión D exige deshacer TODOS los eventos efectivos posteriores a D: un solo evento
   sin confirmar (DISCOVERY_ONLY / TBA / UNRESOLVED / CONFLICT) invalida las fechas anteriores a él pero
   nunca un periodo posterior demostrado. La fecha de ruptura es la MÁS TARDÍA entre CSV y oficial.
6. **`D02_RESEARCH_READY`** = al menos 60 cohortes mensuales consecutivas (primer día hábil NYSE) fuera
   del holdout con membresía confirmada; preferido ≥ 96.
7. **Flags separados** (`research_readiness.py`): `D02_RESEARCH_READY`, `US_D05_RESEARCH_READY`,
   `ES_D05_RESEARCH_READY`, `FEATURE_ENGINE_IMPLEMENTED`, `FEATURE_RESEARCH_READY_US/_ES` y el global (US y
   ES), `LABEL_ENGINE_READY_US`, `BASELINE_MODEL_READY`. Ninguno se fija a mano.
8. **Benchmark US:** SPY como ETF investible explícito, `US_BENCHMARK_SPY_TOTAL_RETURN`,
   `benchmark_type = ETF_PROXY`; el retorno total se calcula internamente (nunca `adjClose`).
9. **Muestra D-05 determinista:** SHA-256 de `PITQUANT_D05_SAMPLE_V1`; umbrales fijos (≥ 98 % activas,
   ≥ 95 % ex-miembros/deslistadas, 100 % de ground truth sin contradicción) que no se relajan.

## Límites
- El ancla es del 2026-10-01 (SPY) / 2026-09-30 (IVV): los eventos posteriores (p. ej. 2026-10-06) no están
  en el ancla.
- Los eventos con ticker histórico distinto del actual (renombres) requieren evidencia de identidad para
  encadenar la reversión; si no, la reversibilidad falla y no hay cohortes canónicas.
