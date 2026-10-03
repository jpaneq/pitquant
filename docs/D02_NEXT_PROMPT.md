# Prompt para la siguiente iteración D-02

La integración documental está hecha en este checkout, sobre `f84f38d`.
Lee `docs/adr/0036-d02-primary-documentary-integration.md`,
`docs/D02_RESIDUAL_PACKAGE.md`, `docs/d02_residual_cards.json` y el manifiesto
`docs/d02_documentary_ingestion.json`. Respeta cambios concurrentes y las
instrucciones del repositorio. No repitas la integración de IQVIA, Capri, Globe
Life, L3Harris, Jefferies, Viatris, WBD y los cambios S&P de mayo de 2020.

Estado medido: 54/60 cohortes mensuales, racha 54, dos fichas de membresía en
2017-09-30→2018-03-31 (PPoG/PPG), una ficha sólo de identidad, dos securities
con identidad débil (PPoG y C.R. Bard). Ambos gates de investigación mensual y
entrenamiento siguen false. No cambies train_min=60 ni amplíes la ventana para
eludir los seis meses pendientes. El holdout 2022-10→2025-09 continúa sellado.

Objetivo principal: cerrar PPoG/PPG únicamente con evidencia primaria suficiente.
El N-30D `0001193125-17-355427` contiene realmente «PPoG»: no es un fallo de
extracción. Busca un documento oficial contemporáneo que vincule esa posición
con PPG (CUSIP 693506107) y permita demostrar continuidad de la misma security.
Archiva los bytes originales con SHA-256 y publicación/acceptance real, añade una
regla explícita con procedencia y verifica inequívocamente el vínculo con las
anclas. No uses similitud difusa, un CSV comunitario ni la ausencia de una noticia
como prueba. Si sólo tienes una hipótesis, conserva las dos fichas y el gate false.
La SEC exige un User-Agent de contacto: usa PITQUANT_SEC_USER_AGENT configurado
por el usuario; no inventes un correo. La ingesta documental existente usa
fuentes oficiales de emisores, S&P, Nasdaq y OCC/MIAX sin ese requisito de EDGAR.

Segundo objetivo: cerrar identidad C.R. Bard con documentación oficial del CUSIP
067383109. No conviertas su compra por Becton Dickinson en una continuidad
arbitraria de índice. Identidad de una security y sustitución de un miembro son
hechos distintos. Mantén las transiciones de CUSIP PARTIAL cuando no esté probada
su fecha exacta. Una pareja de listas 13(f) sólo prueba identificadores observados.

Si trabajas en el universo diario, atiende separadamente Bemis→Amcor: S&P prueba
el alta de BMS el 2019-06-07 y la continuidad de la plaza, pero AMCR comienza con
el cierre del 2019-06-11. La security Bemis debe existir durante ese intervalo.
Fuentes ya localizadas, aún NO integradas como sucesión por esta iteración:
- https://www.amcor.com/media/news/amcor-completes-acquisition-of-bemis
- https://assets.ctfassets.net/f7tuyt85vtoa/7uMkcwHwG3veEBDMHe5GgS/ad1d42c3df304744357a1c7d2f1ffe48/Amcor_FY19_Results_and_2020_Guidance_-_21_August_2019.pdf
Verifica el ratio efectivamente realizado 5.1 y las fechas desde originales;
crea la security predecesora con evidencia oficial, no un alias retroactivo de
Amcor. No marques DAILY_CANONICAL_READY por resolver sólo cohortes mensuales.

La migración 0017 amplía security_succession.event_type a 64 caracteres: el tipo
NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY tiene 43. Mantén la regresión
PostgreSQL y el downgrade que rechaza truncar hechos inmutables.
SuccessionTimeline devuelve las predecesoras antes de una sustitución y admite
las dos clases Discovery anteriores a WBD; conserva esos límites y pruebas.

Reproduce primero con PITQUANT_DATABASE_URL apuntando a la base con los originales:
1. .venv/bin/alembic upgrade head
2. .venv/bin/python scripts/ingest_d02_documentary.py --apply
3. .venv/bin/python scripts/ingest_sp500_evidence.py --offline
4. .venv/bin/python scripts/build_sp500_anchor_graph.py
5. .venv/bin/python scripts/gen_d02_residual_package.py
Si faltan originales, usa --fetch --apply en el paso 2; no borres la base existente.
No edites manualmente los JSON de gaps ni el paquete generado.

Añade sólo pruebas útiles: vínculo documental válido e inválido, identificación
inequívoca, hash manipulado, fuente ambigua, idempotencia, fronteras temporales y
no contaminación del holdout. Ejecuta lint, mypy, suite backend, make pit,
PostgreSQL estricto y alembic check. No cambies Simulation Lab, Analyzer, features,
datasets, modelos ni champion para resolver D-02. Entrega los números medidos,
fuentes, límites residuales y archivos modificados. No declares 60/60 ni habilites
entrenamiento sin que el cálculo y los gates lo demuestren.
