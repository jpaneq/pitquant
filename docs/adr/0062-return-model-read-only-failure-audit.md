# ADR-0062 — Auditoría del fallo Return sin nuevos ajustes

Estado: aceptado para diagnóstico DEV; 2026-10-06.

Partimos de ce2e539 y conservamos los tres experimentos congelados. El diagnóstico usa
315 candidatos archivados, sus 945 ajustes internos y las predicciones exteriores ya
publicadas. No instancia estimadores, accede a base de datos, ajusta preprocesamiento ni
construye predicciones TEST de candidatos no seleccionados.

Las reglas de cálculo, colas, N mínimo, márgenes, Pareto y clasificación se conservan en
FIRST_EQUITY_RETURN_12M_V0_FAILURE_AUDIT_DESIGN.json, creado antes de calcular los
resultados nuevos. La clasificación es exploratoria: las condiciones operativas A/C
son indicadores, no pruebas de causalidad. Cuando selección y cambio temporal coexisten,
se usa E, conforme a la rama MIXED del diseño. Esa interpretación se hace tras inspección;
no constituye una nueva regla de validación ni una evidencia confirmatoria.

Se reproduce X con medianas, clipping y escalas almacenados. TRAIN in-sample se etiqueta
separadamente de validación OOF. El gradiente KKT describe el óptimo cero del objetivo
ElasticNet. Un IC agrupado puede ser distinto de cero aunque todos los meses de un
candidato sean constantes: se publican tanto Pareto agrupado como mensual y se prioriza
IC mensual para interpretar ranking. Folds interiores repetidos no son réplicas nuevas.

IC por sector requiere N≥5 y predicciones no constantes; se agrega por mes ponderando
N entre sectores elegibles. Se publica cobertura; no es un modelo neutralizado. Se
conservan las familias y regímenes existentes; no se crean scores ni categorías nuevas.

Los hashes, etiquetas y contratos USD/TOTAL_RETURN/SPY se comprueban sin alterar datos.
El extracto congelado no contiene las patas originales de precio/acciones corporativas;
no se afirma haber descartado errores vendor aguas arriba. Si aparece una inconsistencia
interna, el cálculo falla y se detiene. Los extremos quedan conservados e identificados.

DEV permanece en iteración 2, holdout/OOT en cero. Cualquier ajuste posterior requiere
revisión humana y consumiría la última iteración estructural 3; ningún acceso a holdout
se habilita por este diagnóstico.
