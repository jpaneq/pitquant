# ADR-0036 — D-02: originales primarios y securities fechadas

Estado: aceptado. Referencia anterior: `f84f38d` (27/60 cohortes, racha 15).

## Evidencia integrada

`scripts/ingest_d02_documentary.py` descarga únicamente URLs revisadas y declaradas;
por defecto reproduce el archivo sin red. `docs/d02_documentary_ingestion.json`
identifica originales, URL, SHA-256, fecha declarada de publicación y resultado.
Los bytes se conservan en el archivo de contenido configurado. No se almacena una
transcripción como si fuera el original. La hora de publicación desconocida se
representa conservadoramente al final de su día en Nueva York; no se inventa una
hora de acceptance de EDGAR. La alerta Nasdaq actualizada se fecha 2020-11-16,
según su cuerpo, y no con el encabezado anterior de 2020-11-09.

Las especificaciones verifican las cláusulas del original y los CUSIP de ambas
patas en listas oficiales 13(f), además de localizar securities inequívocas:

| Caso | Hecho legal | Inicio ticker | Tratamiento |
|---|---|---|---|
| Quintiles IMS → IQVIA | 2017-11-06 | IQV 2017-11-15 | misma security |
| Michael Kors → Capri | 2018-12-31 | CPRI 2019-01-02 | misma security |
| Torchmark → Globe Life | 2019-08-08 | GL 2019-08-09 | misma security |
| Harris → L3Harris | 2019-06-29 | LHX 2019-07-01 | continuidad de acciones Harris |
| Leucadia → Jefferies | fecha legal no cerrada con este original | JEF 2018-05-24 | misma security; circular OCC 43106 archivada desde MIAX |
| Mylan → Viatris | cierre 2020-11-16 | VTRS regular way 2020-11-17 | security sucesora, 1:1 |
| Discovery A/C → WBD | cierre 2022-04-08 | WBD 2022-04-11 | cada clase se convierte 1:1; dos predecesoras |

Para WBD son obligatorios conjuntamente el comunicado de cierre, el informe Q1
que declara la conversión de clases y el comunicado S&P que confirma que permanece
en el índice. La clase B no se incorpora como miembro del S&P 500. El ratio de
AT&T y el de las acciones preferentes no se aplican a Discovery A/C. Tampoco se
aplica el ratio de L3 a las acciones Harris.

El comunicado S&P del 2020-05-06 se ingiere con el parser existente: DXCM sustituye
AGN y DPZ sustituye CPRI antes de abrir el 2020-05-12. Su cambio del S&P 100 no se
traslada al S&P 500. La fecha exacta del cambio de CUSIP sigue PARTIAL donde la
prueba archivada no permite cerrarla; identidad y membresía tienen gates distintos.

## Identidad temporal

La reconciliación usa lineages para conservar una plaza. `SuccessionTimeline`
materializa las securities legales al abrir cada sesión de decisión: Praxair antes
de Linde, Mylan antes de Viatris, y ambas clases Discovery antes de WBD. Las
sustituciones fechadas usan la sesión de transición declarada, separada del cierre
legal. El timestamp a medianoche UTC representa la frontera de sesión, no una
hora de cierre de la operación. Los cambios de nombre conservan una identidad
continua con alias de ticker fechados.

Fechas desconocidas, sucesiones incompatibles, ciclos o múltiples predecesoras
sin conversión de clases bloquean la composición. No se rellena por similitud de
texto. Se versiona el motor como `anchor-graph-5`; una ejecución preliminar local
con versión 4 no se reutiliza como resultado vigente.

La salvedad Bemis/Amcor del ADR-0035 permanece: falta materializar la security
transitoria Bemis entre su alta del 2019-06-07 y el cierre de la combinación. Esta
integración no añade un enlace legal ni un ratio para ese caso. Las cohortes
mensuales no tienen una decisión en ese intervalo. No se certifica un universo
canónico diario completo.

## PostgreSQL

La migración 0015 permitió un evento de 43 caracteres en `varchar(32)`. SQLite
no hacía visible el problema. La migración 0017 amplía a 64 y la regresión PostgreSQL
comprueba que se conserva el texto completo. El downgrade rechaza una reducción
que perdería hechos inmutables. No cambia datos históricos ni elimina registros.

## Resultado y reproducción

Resultado local: **54/60**, racha **54**, dos fichas de membresía que afectan las
primeras seis cohortes (PPoG/PPG), una ficha de identidad y dos securities débiles
(PPoG y C.R. Bard). `D02_MONTHLY_RESEARCH_READY=false`,
`BASELINE_TRAINING_READY=false`, `train_min=60`; no hay folds entrenables.

```sh
export PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db
.venv/bin/alembic upgrade head
.venv/bin/python scripts/ingest_d02_documentary.py --fetch --apply
.venv/bin/python scripts/ingest_sp500_evidence.py --offline
.venv/bin/python scripts/build_sp500_anchor_graph.py
.venv/bin/python scripts/gen_d02_residual_package.py
```

Para reproducción posterior sin red, omitir `--fetch` cuando los originales ya
estén archivados. La ingesta reutiliza originales idénticos y no duplica enlaces ni
alias. El archivo y la base local no están versionados: otra instalación debe
recuperar los originales o recibir esos artefactos antes de reproducir el informe.

No se amplía la ventana ni se consulta el holdout. Simulation Lab, Analyzer,
datasets, entrenamiento y modelos quedan fuera de esta integración.
