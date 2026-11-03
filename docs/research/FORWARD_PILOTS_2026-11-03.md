# PITQuant: dos pilotos prospectivos y comparación histórica

Fecha: 3 de noviembre de 2026. El usuario ha elegido **ambos mercados, evaluados por separado**: acciones a **20 sesiones** y BTC a **30 días naturales**. Las ventanas de **12 y 24 meses** describen el histórico a comparar, no el horizonte de cada pronóstico.

Estado: enfoque y horizontes confirmados; diseño de ejecución propuesto. **No hay un nuevo entrenamiento ni una activación de recogida programada en esta entrega.** Este documento no modifica los manifiestos, gates, modelos o muestras reservadas de investigaciones anteriores.

## Qué enseña la imagen

Se ven indicadores rotulados como PnL del día UTC (+910,45 dólares) y no realizado (+220,53 dólares). El recorte no permite verificar tamaño de cuenta, riesgo, comisiones, depósitos, operaciones cerradas, duración del historial ni si es simulación. Esos importes tampoco demuestran que el algoritmo haya aprendido. La afirmación de aprendizaje necesitaría versiones de modelo, actualizaciones efectivas y evaluación posterior de cada versión.

## Ciclo que queremos construir

1. Preparar un baseline reproducible con datos permitidos y resultados cuyo horizonte haya terminado antes de su corte de entrenamiento.
2. Congelar versión de modelo, datos, transformaciones, parámetros y reglas. Guardar cada pronóstico antes del resultado.
3. Mostrar su evolución diaria. Emitir resultados de aprendizaje solo al completar las 20 sesiones o 30 días; la trayectoria intermedia sigue siendo provisional.
4. Asociar las simulaciones al ID y versión de la predicción original. Registrar también las predicciones para las que no se abrió una operación.
5. Proponer correcciones como una versión nueva; conservar la anterior para comparar ambas sobre las mismas fechas futuras.

Un modelo fijo puede acertar o fallar sin aprender. Reentrenar con resultados nuevos es una actualización del modelo. Cambiar features, horizonte, algoritmo o reglas de entrada es además un cambio de estrategia y debe identificarse como tal. Ninguno garantiza mejorar.

## Dos carriles de evidencia

| Carril | Qué mide | Qué no acredita |
|---|---|---|
| Forward desde la activación real | Predicciones efectivamente generadas con su hora, datos disponibles y resultado posterior. | No puede reconstruirse hacia atrás ni empezar artificialmente el 3 de noviembre si no se generó realmente entonces. |
| Replay de los últimos 12/24 meses | Evaluación cronológica: en cada fecha se entrena solo con pasado permitido y etiquetas maduras; se predice antes de revelar el resultado. | No es un pronóstico emitido en esa fecha histórica. Los datos descargados ahora no prueban su disponibilidad entonces. |

El histórico exige más datos previos al inicio del tramo de evaluación para formar indicadores y entrenar. Las ventanas de 12/24 meses no deben convertirse inadvertidamente en todo el conjunto de entrenamiento. El universo histórico debe ser reproducible: probar retrospectivamente solo los supervivientes elegidos hoy tiene otra interpretación y se debe marcar expresamente.

Si se cambia el modelo usando los fallos observados de un replay, ese replay se convierte en desarrollo adaptativo. No se vuelve independiente por ejecutarlo de nuevo. Los días o activos con huecos permanecen registrados; no se rellenan señales retrospectivas ni se eliminan del informe por mal resultado.

## Contratos de evaluación propuestos

Acciones: calendario de la bolsa del activo; 20 sesiones, no 20 días naturales. BTC: 30 días naturales y cierres diarios UTC. Los resultados se publican separados por mercado, versión, activo, fecha y tipo de evidencia.

- **Predicción:** dirección respecto a un precio de referencia explícito y resultado en el horizonte completo. Guardar retorno esperado si el modelo lo produce; una probabilidad sin calibración validada no se llama confianza demostrada.
- **Simulación:** entrada ejecutable posterior a la generación, costes declarados, posición/notional y regla de salida fijados de antemano. No rellenar al precio de una apertura ya pasada. Aplicar el motor diario conservador existente a stop/target coincidentes.
- **Separación:** acertar la dirección final no implica ganar la operación. Una salida por stop no cambia el pronóstico original; su resultado al horizonte completo se evalúa aparte.
- **Acierto:** definir qué significa subir/bajar y cómo tratar el retorno exactamente cero antes de calcular tasas. El denominador incluye todas las predicciones maduras elegibles; abstenciones, pendientes y falta de datos se informan aparte.
- **Referencias:** siempre-subida para dirección; buy-and-hold para estrategia; y una regla de momentum fijada previamente. Comparar capital, fechas, costes y exposición de manera coherente. No presentar exceso bruto de una regla contra retorno neto de otra.
- **Métricas:** aciertos/fallos de dirección, cobertura, N maduro, retorno medio ganado/perdido, resultado neto cuando los costes estén definidos, drawdown y comparación con referencia. PnL en dinero requiere un capital y libro de posiciones reales o simulados explícitos.
- **Dependencia:** pronósticos diarios a 30 días se solapan; no son 30 apuestas independientes. Informar también resultados por cohortes no solapadas, concentración por activo y limitaciones de muestra.

Las reglas exactas de costes, universo y baseline deben cerrarse antes del primer fit. Los costes sin especificar se muestran como no modelados: no autorizan un resultado llamado neto.

## Aprendizaje y correcciones

Propuesta inicial: modelo de referencia fijo y revisiones mensuales, en lugar de modificarlo tras cada pérdida. La revisión puede dar lugar a un candidato nuevo usando únicamente etiquetas ya maduras. Se conservan ambas versiones en seguimiento paralelo. La promoción requiere un criterio fijado antes de comparar y evidencia suficiente; ninguna versión se promueve automáticamente por ganar un día.

Para empezar, son razonables modelos numéricos sencillos y ya compatibles con la arquitectura, con inputs de precios auditados. La elección y sus parámetros deben documentarse, sin una búsqueda abierta de modelos sobre los mismos meses. La investigación H12 anterior conserva su historia y sus conclusiones.

## Qué existe y qué falta

El módulo BTC experimental ya congela pronósticos por día, vincula la predicción con una simulación y añade evaluaciones al madurar. Simulation Lab y Operaciones aportan registro y evolución. La rutina de acciones revisada es un motor de reglas y simulación; su propio código declara que no es un modelo predictivo entrenado.

Falta cerrar el universo/datos permitidos y el baseline del nuevo piloto de acciones, el contrato común de versiones/comparación y el replay cronológico de ambos pilotos. También hay que comprobar calidad de datos, costes y reservas antes de entrenar. No se considera que una infraestructura ya existente sea un piloto nuevo funcionando.

## Reservas históricas existentes

El protocolo BTC reserva **2025-10-01 a 2026-09-30**; por tanto, las ventanas recientes de 12/24 meses solicitadas se solapan con una reserva vigente. No se han leído sus outcomes. También deben comprobarse las reservas de equity antes de calcular replays.

Opciones que requieren una decisión expresa de política de datos: mantener las reservas y excluir esas fechas del replay permitido, o reclasificar formalmente su uso en un protocolo nuevo, reconociendo que dejarían de ser prueba virgen para los usos afectados. El cambio de enfoque no debe producir una apertura silenciosa ni reutilizar el sello de independencia anterior.

## Fuentes metodológicas

La validación cronológica evita entrenar con futuro: [TimeSeriesSplit, scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html). Esa clase por sí sola no aplica la madurez de nuestras etiquetas ni la purga necesaria para cada horizonte.

El esquema predecir, esperar el resultado y después actualizar corresponde a evaluación progresiva con etiquetas retrasadas: [documentación de River](https://riverml.xyz/latest/api/evaluate/progressive-val-score/). No se ha instalado River ni se exige sustituir nuestras bibliotecas.

Archivos locales revisados: `docs/BTC_RESEARCH_PROTOCOL.md`, `docs/BTC_EXPERIMENTAL_PREDICTOR.md`, `src/pitquant/btc/experimental.py`, `src/pitquant/positions/routine.py` y metadatos del manifiesto equity V1. No se ejecutaron entrenamientos, replays ni automatizaciones; no se consultaron outcomes reservados.
