# ADR-0060 — V1 adaptativo: regularización y Platt causal

V0 en 1ca46e9 es inmutable. V1 reutiliza exactamente su archivo DEV congelado,
sin consultas a la base ni acceso a resultados holdout/OOT. Es ADAPTIVE_DEV_ITERATION_1:
se diseñó después de observar V0; ninguna mejora constituye confirmación independiente.

Antes de cualquier fit real se congela el manifiesto, SHA de código, hashes V0,
cohortes, familias, target, preprocessing, diseño interno, grid, calibrador y reglas descriptivas.
Inner TRAIN expansivo mínimo 18 meses; validación de seis meses, paso seis meses;
train_decision + H12 + embargo1 <= validation_start, con madurez efectiva anterior al fit.
Se excluyen bloques parciales. Resultan 1/3/5 validaciones en F1/F2/F3.
No cambia el mínimo TRAIN del contrato externo. F1 tiene sólo 222 observaciones OOF.

C pertenece a {0.01,0.03,0.1,0.3,1}; se selecciona por LogLoss OOF interna ponderada
por fila; empate numérico <=1e-12 elige el menor C. Brier sólo diagnóstico.
Se refit sobre TRAIN externo. Se reutiliza sin cambios TrainPreprocessor de V0.

Platt: MLE binomial sigmoid(intercept + slope * logit(p)), sólo OOF causal del C
seleccionado. Slope >=1e-6 predeclarado conserva orden estricto y evita inversiones;
si alcanza la frontera se informa, sin atribuir señal útil a una pendiente casi cero.
Se clipan logits a [1e-12,1-1e-12]. Datos con una clase/logits constantes o sin
historia OOF no admiten calibración. Convergencia o alteración de ranks implica STOP.
La selección de C y Platt comparten OOF interna: permitido, pero puede introducir
optimismo interno; la pequeña historia y cambio de prevalencia limitan generalización.

Un mapa positivo preserva AUC/AP/IC y buckets dentro de cada fold y mes.
Distintos calibradores por fold pueden alterar AUC/AP/IC pooled: es agregación temporal,
no fuga ni fallo de monotonía. No se oculta ni se trata como mejora cross-sectional.
Spreads se promedian por mes con empates promedio, igual que V0.

Bootstrap pareado: 1000 muestras de meses completos; LL/Brier/AUC/spread,
seis comparaciones fijadas. Todos los intervalos ADAPTIVE_DEV_EXPLORATORY;
no preservan dependencia serial de targets H12 solapados.

Reglas descriptivas por prioridad se congelan en el manifiesto; no son gates de aprobación.
Modelos RESEARCH_DEV_ONLY, ADAPTIVE_DEV, RETROSPECTIVE_UNVALIDATED. Sin promoción.
