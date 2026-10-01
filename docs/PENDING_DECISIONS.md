# Decisiones pendientes (requieren al propietario)

Todo lo demás se ha resuelto con decisiones razonables y configurables (ver ADRs).
Estas decisiones condicionan la **validez** de los resultados, no la arquitectura: el
código funciona con cualquier opción gracias a las interfaces de providers.

| ID | Decisión | Por qué importa | Opciones (verificar coste y condiciones actuales) | Recomendación provisional |
|---|---|---|---|---|
| D-01 | Fuente de fundamentales PIT **EE. UU.** | Sin `available_at` real no hay backtest fundamental válido | (a) SEC EDGAR XBRL *companyfacts* + `acceptanceDateTime` del filing — gratuito, PIT con hora real, requiere normalización propia; (b) Sharadar SF1 (Nasdaq Data Link) — incluye deslistadas y fechas de publicación; (c) Compustat PIT vía WRDS — estándar académico, acceso institucional | Empezar con **(a)** como fuente primaria auditable; (b) como contraste |
| D-02 | Histórico de constituyentes **S&P 500** | Survivorship bias | Sharadar SP500 (cambios históricos), S&P DJI (licencia), reconstrucción desde notas de prensa de S&P DJI | Proveedor con cambios fechados; la reconstrucción manual es viable pero laboriosa |
| D-03 | Histórico de constituyentes **IBEX 35** | Survivorship bias | Avisos del Comité Asesor Técnico del IBEX (BME) — públicos, fechados; proveedores de índices | Reconstrucción desde avisos de BME (≈ 2 revisiones ordinarias/año + extraordinarias), cargada como CSV versionado con `source` por fila |
| D-04 | Fundamentales PIT **España** | IBEX sin datos PIT = sólo análisis técnico | Informes financieros periódicos en CNMV (fecha/hora de registro), XBRL/ESEF desde 2020, proveedores comerciales | CNMV como fuente de `available_at`; valores numéricos de ESEF donde exista |
| D-05 | Precios con deslistadas y corporate actions | Delisting returns, M&A | Sharadar SEP, CRSP (gold standard EE. UU.), EODHD/Tiingo (cobertura de deslistadas desigual) | Validar cobertura de deslistadas antes de pagar |
| D-06 | Benchmarks total return | Comparación justa | S&P 500 TR (SPXT), IBEX 35 con Dividendos; sector: SPDR sector ETFs (TR vía ajuste de dividendos) | Tal cual |
| D-07 | Estimaciones de analistas PIT | Sección 17 | I/B/E/S (institucional) o desactivar | **Desactivada** hasta tener fuente PIT verificable |
| D-08 | Divisa base para informes | Mezcla EUR/USD | EUR (residencia en España) o local | Excess return en **divisa local** vs benchmark local; informes de cartera en **EUR** |
| D-09 | Periodo de holdout final | Debe fijarse **antes** de mirar resultados | Últimos 24 o 36 meses con label disponible | **36 meses**: 2022-10 → 2025-09 (labels 12M disponibles hasta 2026-09). Se congela en `config/default.yaml` en el primer commit |
| D-10 | Despliegue | Infraestructura | Mac Mini (Docker Compose: PostgreSQL + API + Prefect) o VPS | Docker Compose local; el código no depende del host |

> D-09 se fija ya en configuración para que ningún resultado posterior pueda influir en la
> elección del holdout. Cambiarlo requiere un ADR nuevo y queda registrado.
