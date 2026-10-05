# PROPUESTA — Cobertura de securities del primer ML

Estado: **NO aplicada**. `REQUIRED_SECURITIES=100`, folds, horizonte, purge, embargo, mínimos fundamentales y holdout permanecen iguales. Esta propuesta sustituye el análisis de la propuesta anterior; no sugiere 100→51 ni un mínimo elegido por conveniencia.

## Origen y significado actual

`research/model_contracts.py::MIN_SECURITIES=100` nació en RUN 3, ADR-0048. Su gate cuenta securities distintas **con cualquier snapshot**, en el conjunto global de investigación. No exige que cada una tenga membresía histórica, objetivo maduro, precio validado o presencia en cada mes. `research/first_ml_contract.py::REQUIRED_SECURITIES=100`, ADR-0049, conservó el número para un gate distinto: securities con al menos una fila elegible según el contrato del primer ML. No hay cálculo de potencia ni presupuesto de error documentado que derive 100.

La política de ampliar la cobertura a 100 puede mantenerse como objetivo operativo. Sin embargo, ese origen global no justifica afirmar que 100 sea un requisito estadístico suficiente o necesario para el experimento US. El contrato actual rechaza non-US mediante `first_ml_eligibility`: membresía XNYS/S&P y benchmark comparable SPY. No se cambia ni renombra el experimento automáticamente.

El inventario actual tiene 100 securities configuradas con snapshots: 55 US y 45 non-US. Sólo 51 US tienen filas PRICE 12M elegibles; los cuatro vínculos restantes siguen pendientes. Incluso resolver los cuatro dejaría 55, no 100. Las 45 non-US no pueden completar el gate US sin cambiar universo y metodología. El número global elegible **bajo el contrato actual** también es 51: no debe confundirse con los 100 valores con snapshots ni con 85 series que pasan QA de precios.

## Auditoría necesaria antes de sustituir el gate

El panel actual aporta 2.396 filas PRICE 12M en 48 cohortes con etiquetas maduras (49–51 securities por cohorte), 51 issuer IDs y entre 9 y 48 meses por security. Otras 93 cohortes DEV tienen cero filas elegibles, por D02 o ventanas sin objetivo admisible. FUNDAMENTALS aporta 1.785 filas; el gate separado exige y conserva 30 securities con 36 meses fundamentales.

El informe generado publica por mes el número de securities elegibles, por security sus meses elegibles, sus issuer IDs distintos y el panel de fechas/IDs sin resultados. También separa PRICE y FUNDAMENTALS. Estas cifras muestran cobertura; los issuer IDs son clusters distintos, no prueba de independencia estadística. La membresía D02 completa y la diversidad de la muestra modelizada son requisitos separados: una lista de valores actuales no elimina por sí sola el sesgo de supervivencia.

Los objetivos 12M de meses contiguos comparten retornos. Además, valores de emisores distintos comparten régimen y benchmark. Por tanto, no se usa `2396` como tamaño efectivo independiente, ni `1/sqrt(45)` promediado sobre 36 meses como si los meses fueran no solapados. La dependencia transversal y temporal puede sesgar los errores estándar de panel financiero: [Petersen, fuente primaria NBER](https://www.nber.org/papers/w11280), [material del autor](https://www.kellogg.northwestern.edu/faculty/petersen/htm/papers/se/se_programming.htm).

## Reemplazo propuesto, sujeto a una decisión previa

Recomiendo un **contrato de cobertura y precisión por fold**, en lugar de un conteo global de tickers con alguna fila. Debe aprobarse y registrarse antes de entrenar o consultar resultados de test:

1. Mantener los gates existentes de evidencia, retorno, disponibilidad PIT, identidad, 85 meses consecutivos, al menos tres folds, purge y embargo. Holdout/OOT siguen sellados.
2. Declarar el universo US objetivo y su criterio de muestreo histórico. Publicar, para cada mes de TRAIN/test, número de securities y emisores con etiquetas maduras, duración de cada serie, faltantes y concentración. No ampliar nombres seleccionando por rendimiento.
3. Fijar a priori un nivel de confianza y un margen de error tolerable para la métrica primaria; estos parámetros no se eligen para que pasen los 51 disponibles. Definir también la cobertura y concentración admisibles según ese universo, no según el resultado de un modelo.
4. Derivar el requisito de información independiente a partir de ese presupuesto. Para ilustrar la lógica, una proporción Bernoulli IID tendría `N_req >= z²/(4 ε²)` en el caso conservador; esa fórmula **no se aplica directamente** al panel ni al Brier. Para la métrica aprobada se debe usar su varianza y un efecto de diseño que considere clusters por emisor y bloques temporales compatibles con 12M. Documentar supuestos y sensibilidad; no afirmar un N_eff que no se ha estimado.
5. Aplicar la política preregistrada con auditoría dependiente de clusters/bloques y sólo información permitida de TRAIN para decisiones de selección. Las cifras de test se usan para la evaluación fijada, no para retocar el gate. Si falta información, ampliar evidencia histórica/universo con reglas prefijadas o seguir bloqueado.

La alternativa es concreta en lo que sustituye: **cobertura mensual histórica y precisión dependiente del panel**, no «>=51 securities alguna vez». No ofrece un umbral numérico nuevo sin presupuesto de precisión aprobado: convertirlo en una constante ahora sería inventarlo. Mantener 100 exige ampliar deliberadamente el universo US, con evidencia histórica, más allá de las 55 configuradas.

## Alcance recomendado y estado

Recomiendo que el primer experimento continúe US-only: es el alcance que hoy implementan membresía, precios, fundamentales y benchmark. Incluir otras regiones requiere sus universos históricos y bases de retorno aceptadas, no sumar tickers para alcanzar 100. No se modifica el identificador FIRST_EQUITY_ML_12M_V0.

La decisión de cobertura sigue pendiente; no bloquea continuar reuniendo la evidencia D02 que falta. Esta propuesta no autoriza M0–M4. FIRST_ML_BASELINE_READY permanece false.
