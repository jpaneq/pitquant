# ADR-0067 — Ficha de empresa e indicador «cara / barata»

Fecha: 2026-11-09. Estado: aceptado (petición del propietario: resumen visual de la
información SEC por ticker y un indicador de si la acción está cara o barata).

## Decisión

- `analyzer/factsheet.py` + `GET /companies`, `GET /companies/{ticker}`; página `/empresas/:ticker`
  («Empresas» en el menú; los tickers de «Lo que dice hoy» enlazan a su ficha).
- Reutiliza los motores existentes (`fundamental_v1`, `valuation_v1`); no hay cálculo financiero
  en el frontend. Historia trimestral de 10 años (un punto por periodo nuevo, con los filings
  aceptados antes de cada fecha) e historia mensual de valoración.
- **Indicador.** Cuatro rentabilidades por precio (más alto = más barata): beneficio/precio,
  caja libre/precio, ventas/precio y beneficio operativo/valor de empresa. Percentil de hoy
  frente a (a) la historia mensual propia de 10 años (≥ 24 puntos) y (b) las demás empresas
  no financieras del universo hoy. Puntuación 0–100 = media de lo disponible; bandas ≥ 80 muy
  barata, 60–80 barata, 40–60 en su precio, 20–40 cara, < 20 muy cara. Sin dato ⇒ no se adivina.
- Bancos/aseguradoras: «no aplicable» (sus métricas son otras).
- La comparación con las demás se calcula una vez al día en memoria (≈ 20 s la primera ficha).

## Consecuencias

- Es **descriptivo, no predictivo**: el examen v3 (ADR-0066) mostró que la valoración apenas
  ayuda a predecir el mes siguiente. La página lo dice expresamente.
- Universo actual de grandes compañías: «barata frente a las demás» es relativo a ese grupo.
