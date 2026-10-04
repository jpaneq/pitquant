# Acciones: señales en el gráfico y pruebas diarias

## En el Analyzer (`/analyzer/AAPL`)
Barra del gráfico: **Señales algoritmo (R)** y **Mis pruebas (F)**.
- **R** (flechas): lo que habría dado la regla del Trade Plan V0 en fechas pasadas, calculada sólo con datos conocidos entonces y jugada sobre las barras posteriores con el motor de simulación congelado. Retrospectivo, sin costes, no validado, sin escribir en la base. Sin tasa de aciertos con <10 operaciones cerradas. El holdout 2022-10→2025-09 nunca se dibuja.
- **F** (círculos): tus simulaciones paper reales (manuales o automáticas) de ese valor.
- «Predicción» sigue desactivada: no existe un modelo validado; el contrato de predicción permanece `NOT_YET_VALIDATED`.
- Datos: barras EOD (última sesión completa; STALE si faltan sesiones). Con el token `demo` sólo AAPL, MSFT y VTI.

## Rutina diaria
```bash
python -m pitquant.cli strategy-daily-test --refresh --json   # actualiza barras y hace UN tick al reloj del servidor
python -m pitquant.cli strategy-daily-test --tickers AAPL,MSFT
```
Idempotente por día. La base real necesita `alembic upgrade head` (migración 0020) antes de la primera ejecución; haz una copia de `data/pitquant.db` antes. Programación diaria: `deploy/launchd/com.pitquant.daily-equity-test.plist` (plantilla, no instalada).
Cada llamada devuelve decisiones nuevas, operaciones abiertas/cerradas y métricas con sus avisos (`INSUFFICIENT_SAMPLE`, `COSTS_NOT_MODELED`, …).
