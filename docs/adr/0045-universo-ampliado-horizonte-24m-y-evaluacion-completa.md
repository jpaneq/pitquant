# ADR-0045 — Universo ampliado (≈100 valores), horizonte de 24 meses y evaluación completa del algoritmo

Estado: aceptada (2026-10-05). Sin migración. Complementa ADR-0042/0043/0044.

## Decisión
1. **Universo ≈100 valores** (IBEX 12, S&P 500 10, MSCI World 78: EE. UU., Europa, Japón, Australia, Canadá) con precios diarios gratuitos de Yahoo (ADR-0043). La lista es de empresas ACTUALES (sesgo de supervivencia) y orientativa; editable con `data/daily_universe.json`.
2. **Bolsas:** tabla única sufijo→calendario/moneda/etiqueta (`market/exchanges.py`): .MC, .AS, .SW, .DE, .L, .PA, .MI, .ST, .CO, .BR, .HE, .T, .HK, .AX, .TO y EE. UU. El calendario de Tokio sólo existe desde 1997: `MarketCalendar` cae a 2000 si 1995 no es válido (V1 empieza en 2011). La rutina analiza un valor de MSCI World sólo si SU bolsa está abierta.
3. **Horizonte de 24 meses** en la rutina y el backtest (junto a 1, 3, 6, 12). Ventanas que alcanzan el holdout se omiten por horizonte.
4. **Fundamentales:** sólo donde hay datos SEC point-in-time (hoy AAPL, MSFT, KO). Para ellos el backtest emite una segunda llamada con valoración y fundamentales y mide su aporte. Ampliar exige `PITQUANT_SEC_USER_AGENT` real (no se persiste) y `sec-ingest`.
5. **Informe completo** (`backtest-run`): resumen, método, cobertura, resultados por horizonte, calidad de la señal (puntuación→rentabilidad, IC por regla), aporte de fundamentales, **variantes** re-puntuadas offline (quitar una regla, usar sólo el signo de una, mover umbral, invertir), sensibilidad del objetivo, selección por puntuación (corte transversal), por mercado/región/periodo, **por valor con mejores/peores decisiones y su porqué**, y **propuestas de mejora** generadas de los números. Un segundo fichero lista CADA decisión (valor, fecha, horizonte, precio, llamada, en base a qué reglas, qué pasó).
6. Las propuestas NO se aplican: se vuelven a ejecutar con ellas y se compara con esta línea base. Para evitar sobreajuste, las variantes se informan por periodo (≤2022-09 y ≥2025-10) y el holdout 2022-10→2025-09 sigue sellado.
