# Cómo interpreta el programa los análisis fundamentales

Resumen de lo que hace el código (`fundamental_v1`, `analysis_v0`, `positions/review`). Todo son **reglas fijas sin validar con backtest**; ninguna cifra es una predicción.

## 1. De dónde salen los números
- **SEC EDGAR** (10-K anual, 10-Q trimestral): cada dato (hecho XBRL) se guarda con la fecha y hora en que la SEC aceptó el informe (`available_at`). El programa solo ve lo que ya era público en cada fecha (point-in-time) y usa la **última revisión conocida**; nunca datos revisados después.
- **TTM (últimos 12 meses)** = ejercicio anterior + acumulado del año actual − acumulado del mismo periodo del año anterior. Si falta algo, el valor queda **vacío con su motivo** (`missing_fundamental`, `insufficient_history`, `NOT_MEANINGFUL`…): nunca se rellena con 0 ni con 50.
- ~50 métricas por empresa: **ingresos, beneficio bruto/operativo/neto, caja operativa, capex, caja libre**; **márgenes, ROA, ROE**; **calidad** (caja operativa/beneficio, devengos/activos); **crecimiento** (interanual y CAGR 3-5 años); **inversión** (crecimiento de activos, capex/activos); **balance** (deuda, deuda neta, deuda/capital, liquidez corriente, cobertura de intereses); **retribución al accionista** (dividendo, recompras, variación de acciones).
- **Valoración:** PER, precio/ventas, rentabilidad por caja libre, EV/ventas, siempre **frente a la propia historia de la empresa (5 años)**, no frente a sus competidoras.

## 2. De los números a las etiquetas (`analysis-v0`)
| Etiqueta | Cómo se calcula | Resultado |
|---|---|---|
| **Fundamentales** | 5 comprobaciones: margen operativo >10 %, margen de caja libre >5 %, ROA >5 %, caja operativa/beneficio ≥0,8, margen neto >0 | ≥4 cumplidas = **Strong**, ≥2 = **Moderate**, menos = **Weak** |
| **Crecimiento** | 5 medidas (ingresos y beneficio operativo interanual, caja libre, CAGR 3 años) con crecimiento >5 % | ≥4 = **Strong**, ≥2 = **Moderate**, menos = **Weak** |
| **Valoración** | percentil medio de PER, P/S y (100 − percentil de la rentabilidad por caja libre) en su historia de 5 años | ≤30 = **Cheap**, ≥70 = **Expensive**, entre medias **Fair** |
Si hay menos del 60 % de las medidas (o menos de 2) la etiqueta es **Insufficient**: nunca se fuerza «Strong». También se generan «positivos» y «riesgos» con umbral y valor visible (p. ej. margen operativo >20 %, cobertura de intereses >10×).

## 3. Cómo los usa el algoritmo
- En la **revisión de posiciones** y en la **rutina diaria**, solo dos etiquetas entran en la puntuación: **valoración** (Cheap +1, Fair 0, Expensive −1) y **fundamentales** (Strong +1, Moderate 0, Weak −1). «Insufficient» o sin datos = la regla se **salta**.
- Cada una se multiplica por el peso del **horizonte**: corto (≤3 m) 0,25; medio (4-8 m) 1,0; largo (≥9 m) 1,5. A plazo largo los fundamentales pueden aportar hasta ±3 puntos frente a umbrales de +2,5 (ampliar/entrar) y −2,0 (vender): pesan mucho.
- La etiqueta de **crecimiento** y las métricas sueltas se muestran, pero hoy **no** puntúan.
- En el backtest, para las empresas con datos SEC se hace una **segunda llamada** «con fundamentales» (cada 3 decisiones) para medir si cambian el resultado.

## 4. Límites que conviene recordar
- Umbrales **absolutos** (no por sector): un margen del 10 % es «bueno» para un supermercado y «malo» para software.
- La valoración compara la empresa **consigo misma**, no con sus pares.
- **Bancos, aseguradoras y REIT**: perfil no soportado todavía («SPECIALIZED PROFILE NOT YET SUPPORTED»).
- Conceptos contables sin normalizar: **WMT, CVX y COST** no tienen aún ingresos TTM; **XOM** tiene un CIK nuevo con un solo informe.
- Los fundamentales cambian cada trimestre: son una señal **lenta**; con 17 empresas (hoy) no se puede concluir si aportan algo.
