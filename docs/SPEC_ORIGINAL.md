# Especificación original (prompt maestro, 2026-10-01)

PROMPT MAESTRO PARA DESARROLLAR UNA PLATAFORMA DE ANÁLISIS BURSÁTIL, SCORING Y BACKTESTING POINT-IN-TIME

Actúa como un equipo senior completo de ingeniería cuantitativa, data engineering, software architecture, backend, machine learning, estadística financiera, QA y DevOps.

Tu objetivo es diseñar y programar desde cero una plataforma profesional que analice acciones cotizadas, produzca señales de inversión y permita comprobar rigurosamente si esas señales habrían funcionado históricamente.

No quiero un prototipo superficial ni un notebook aislado. Quiero una aplicación modular, auditable, reproducible, extensible y preparada para evolucionar.

La prioridad absoluta es evitar cualquier forma de contaminación del pasado con información futura.

⸻

1. OBJETIVO GENERAL

El software deberá poder recibir un ticker y una fecha de análisis y responder:

1. Qué información estaba realmente disponible en esa fecha.
2. Situación fundamental de la empresa.
3. Situación técnica.
4. Valoración relativa e histórica.
5. Calidad financiera.
6. Crecimiento.
7. Riesgo.
8. Momentum.
9. Contexto de mercado.
10. Comparación con sector e índice.
11. Señal resultante.
12. Probabilidad estimada de superar a su benchmark.
13. Horizonte temporal de 6 y 12 meses.
14. Nivel de confianza.
15. Factores positivos.
16. Factores negativos.
17. Explicación íntegra de por qué se genera la señal.

El sistema deberá producir internamente:

* BUY
* HOLD
* SELL

No obligar al modelo a generar una señal extrema cuando la evidencia sea insuficiente.

SELL significará inicialmente:

evitar o infraponderar la acción respecto de su benchmark.

No debe interpretarse automáticamente como posición corta.

Una estrategia SHORT podrá implementarse posteriormente como módulo separado.

⸻

2. PRINCIPIO FUNDAMENTAL: POINT-IN-TIME

La regla más importante del sistema es:

En cualquier simulación histórica, el modelo únicamente puede utilizar información que un inversor habría podido conocer realmente en ese instante.

Toda información deberá tener, siempre que sea posible:

* period_start
* period_end
* publication_date
* publication_time
* available_at
* source
* revision_id
* ingested_at

No basta con saber a qué trimestre pertenece un dato.

Hay que saber cuándo se hizo público.

Ejemplo:

Un resultado correspondiente a Q3 2020 publicado el 5 de noviembre de 2020 no puede utilizarse en un análisis fechado el 31 de octubre de 2020.

Implementar controles automáticos que impidan materialmente esta contaminación.

⸻

3. PREVENCIÓN OBLIGATORIA DE LOOK-AHEAD BIAS

Implementar mecanismos explícitos contra:

* utilización de estados financieros publicados posteriormente;
* estimaciones de analistas revisadas posteriormente;
* información macroeconómica publicada posteriormente;
* revisiones posteriores de datos macroeconómicos;
* precios posteriores al instante de generación de señal;
* conocimiento de corporate actions futuros;
* conocimiento de adquisiciones, quiebras o deslistados futuros;
* utilización de la composición actual de índices para reconstruir universos históricos;
* utilización del precio de cierre para generar una señal que supuestamente se ejecuta antes del cierre.

El sistema deberá disponer de tests automáticos específicos para detectar estos errores.

Si el snapshot es:

2020-06-15 16:00

ninguna feature podrá tener:

available_at > 2020-06-15 16:00

El pipeline debe fallar explícitamente si esto ocurre.

⸻

4. SURVIVORSHIP BIAS: PROHIBIDO USAR LOS COMPONENTES ACTUALES

Nunca reconstruir el pasado utilizando las acciones que actualmente forman parte de:

* S&P 500
* IBEX 35

Crear una tabla histórica:

index_membership

con al menos:

* security_id
* ticker histórico
* índice
* inclusion_date
* exclusion_date
* reason
* source

Cuando se reconstruya una fecha histórica T0:

universe(T0)

deberá contener exclusivamente las compañías que realmente pertenecían al índice en T0.

También deben conservarse:

* compañías posteriormente quebradas;
* compañías adquiridas;
* compañías deslistadas;
* antiguos tickers;
* cambios de ticker;
* fusiones;
* spin-offs;
* cambios de ISIN/CUSIP cuando corresponda.

No eliminar del dataset empresas porque ya no existan actualmente.

⸻

5. SECURITY MASTER

Construir un Security Master central.

No utilizar el ticker como identificador principal porque puede cambiar o reutilizarse.

Crear un identificador interno permanente:

security_id

Campos recomendados:

* security_id
* ticker_actual
* ticker_historico
* nombre
* ISIN
* CUSIP si aplica
* FIGI si está disponible
* exchange
* currency
* country
* sector
* industry
* GICS
* fecha_inicio_cotizacion
* fecha_fin_cotizacion
* delisted
* delisting_reason
* acquirer_security_id
* successor_security_id

⸻

6. UNIVERSOS INICIALES

Primera versión:

* S&P 500
* IBEX 35

Diseñar toda la arquitectura de forma genérica para posteriormente añadir:

* Nasdaq 100
* EuroStoxx
* STOXX Europe 600
* MSCI World
* mercados emergentes
* small caps
* otros mercados.

⸻

7. DATOS DE MERCADO

Almacenar OHLCV:

* Open
* High
* Low
* Close
* Volume

Con:

* precios originales;
* precios ajustados;
* splits;
* reverse splits;
* dividendos;
* derechos;
* spin-offs;
* distribuciones especiales;
* otras corporate actions.

Nunca ajustar precios retrospectivamente de manera que introduzca información futura en features que no deberían conocerla.

Separar claramente:

raw_price

de:

adjusted_price

y documentar cuándo utilizar cada uno.

⸻

8. TOTAL RETURN

Los resultados de la inversión deben utilizar preferentemente total shareholder return.

Incluir:

* apreciación/depreciación del precio;
* dividendos;
* corporate distributions.

Comparar contra un benchmark equivalente de retorno total.

No comparar una acción con dividendos contra un índice price-return sin corregirlo.

⸻

9. MOMENTO REAL DE GENERACIÓN Y EJECUCIÓN

Definir explícitamente:

signal_timestamp

y:

execution_timestamp

Ejemplo:

Si los indicadores técnicos utilizan el cierre del 10 de enero:

signal_timestamp = después del cierre

la entrada más temprana permitida será la siguiente sesión.

Por defecto:

entry_price = next_session_open

Permitir posteriormente:

* next open;
* next VWAP;
* next close;
* configurable execution delay.

Nunca ejecutar retroactivamente una señal con un precio que el modelo no podía conocer.

⸻

10. CALENDARIOS BURSÁTILES

Implementar calendarios reales por mercado.

Inicialmente:

* NYSE/Nasdaq
* BME

Gestionar:

* fines de semana;
* festivos;
* cierres anticipados;
* sesiones inexistentes;
* diferencias horarias;
* horario de verano;
* timestamps timezone-aware.

Nunca sumar simplemente 180 o 365 días y asumir que existe sesión.

⸻

11. ANÁLISIS FUNDAMENTAL

Construir un Fundamental Engine modular.

Subscores independientes 0–100.

11.1 Quality

Analizar como mínimo:

* ROIC;
* ROE;
* ROA;
* margen bruto;
* margen EBITDA;
* margen EBIT;
* margen neto;
* estabilidad de márgenes;
* conversión EBITDA → caja;
* conversión beneficio → CFO;
* conversión beneficio → FCF;
* accruals;
* evolución histórica.

No valorar únicamente el dato actual.

Calcular:

* nivel actual;
* media 3 años;
* media 5 años;
* tendencia;
* variabilidad;
* percentil histórico.

⸻

12. VALUATION ENGINE

Incluir, cuando tengan sentido sectorial:

* P/E;
* forward P/E;
* EV/EBITDA;
* EV/EBIT;
* EV/FCF;
* Price/FCF;
* FCF Yield;
* P/B;
* P/S;
* PEG;
* dividend yield;
* earnings yield.

Comparar cada empresa simultáneamente contra:

1. su propia historia;
2. sector;
3. industria;
4. mercado.

Crear percentiles.

Ejemplo:

PE_sector_percentile

PE_5y_historical_percentile

No interpretar un múltiplo aisladamente.

⸻

13. CRECIMIENTO

Analizar:

* revenue growth;
* EBITDA growth;
* EBIT growth;
* net income growth;
* EPS growth;
* FCF growth.

En:

* YoY;
* CAGR 3 años;
* CAGR 5 años.

Distinguir:

* crecimiento orgánico;
* adquisiciones cuando sea posible;
* crecimiento financiado mediante deuda;
* crecimiento acompañado de dilución.

⸻

14. BALANCE Y SOLVENCIA

Incluir:

* net debt;
* net debt / EBITDA;
* debt / equity;
* gross debt;
* cash;
* current ratio;
* quick ratio;
* interest coverage;
* CFO/debt;
* FCF/debt;
* vencimientos de deuda cuando estén disponibles.

Analizar nivel y tendencia.

⸻

15. CAPITAL ALLOCATION

Analizar:

* dividendos;
* payout;
* crecimiento del dividendo;
* recompras;
* emisiones;
* dilución;
* stock-based compensation;
* M&A;
* reducción de deuda;
* reinversión.

Calcular variación del número de acciones.

Detectar casos en los que:

net income ↑

pero:

EPS crece mucho menos

por dilución.

⸻

16. EARNINGS QUALITY

Analizar:

* CFO / net income;
* FCF / net income;
* accruals;
* cuentas a cobrar;
* inventarios;
* deferred revenue;
* working capital;
* one-off items si están disponibles.

Detectar posibles:

* deterioros de calidad;
* crecimiento poco respaldado por caja;
* distorsiones contables.

⸻

17. ANALYST EXPECTATIONS

Solo si se dispone de históricos realmente point-in-time.

Analizar:

* consenso EPS;
* consenso ingresos;
* revisiones a 30/60/90 días;
* upgrades/downgrades;
* earnings surprise;
* revenue surprise.

Nunca utilizar una estimación reconstruida desde información actual.

Si no existe histórico point-in-time fiable:

NO utilizar esta feature.

El sistema debe priorizar integridad frente a cantidad de variables.

⸻

18. MÉTRICAS POR SECTOR

Crear adaptadores sectoriales.

El sistema no debe valorar todas las industrias igual.

Ejemplos:

Bancos

* CET1;
* NIM;
* NPL;
* cost of risk;
* loan/deposit;
* depósitos;
* tangible book value;
* ROE/ROTCE.

Seguros

* combined ratio;
* solvency ratio;
* primas;
* reservas.

REIT

* FFO;
* AFFO;
* NAV;
* occupancy;
* debt/EBITDA.

Oil & Gas

* producción;
* reservas;
* lifting cost;
* breakeven;
* FCF;
* sensibilidad commodities.

Utilities

* deuda;
* capex;
* regulated asset base;
* cash flows;
* cobertura de dividendos.

Diseñar plugin architecture para añadir nuevos modelos sectoriales.

⸻

19. TECHNICAL ENGINE

Evitar incorporar decenas de indicadores redundantes.

Crear bloques independientes.

Trend

* SMA20;
* SMA50;
* SMA100;
* SMA200;
* EMA;
* precio vs medias;
* slope SMA50;
* slope SMA200;
* estructura MA20/50/200;
* máximos/mínimos.

Momentum

* retorno 1 mes;
* 3 meses;
* 6 meses;
* 12 meses;
* 12-1 momentum;
* RSI;
* MACD;
* ROC.

Relative Strength

Comparar contra:

* índice;
* sector;
* industria.

Horizontes:

* 1M;
* 3M;
* 6M;
* 12M.

Volatility

* realized volatility;
* ATR;
* downside volatility;
* beta;
* drawdown;
* rolling drawdown.

Volume

* volumen relativo;
* media volumen;
* price-volume trend;
* volumen en rupturas;
* OBV opcional.

Eliminar o penalizar features altamente correlacionadas.

⸻

20. MARKET REGIME ENGINE

Clasificar el contexto de mercado.

Features posibles:

* benchmark vs SMA200;
* breadth;
* volatility index cuando corresponda;
* yield curve;
* 10Y yield;
* tipos oficiales;
* credit spreads;
* market volatility;
* tendencia global.

Estados posibles:

* bull;
* bear;
* sideways;
* high volatility;
* low volatility;
* stress regime.

No utilizar datos macro publicados posteriormente.

Guardar:

macro_available_at

⸻

21. SCORING ENGINE INICIAL

La primera versión debe ser interpretable.

No comenzar directamente con una red neuronal.

Mantener scores separados.

Por ejemplo:

Fundamental:

* Quality
* Valuation
* Growth
* Balance Sheet
* Earnings Quality
* Capital Allocation
* Earnings Momentum

Technical:

* Trend
* Momentum
* Relative Strength
* Volatility
* Volume

Market:

* Market Regime
* Sector Regime

Risk.

Cada score:

0–100

Guardar todos los componentes individuales.

⸻

22. MODELOS POR HORIZONTE

No utilizar necesariamente el mismo modelo para 6 y 12 meses.

Crear:

model_6m

model_12m

Pesos iniciales configurables.

Ejemplo inicial NO definitivo:

6M:

* fundamental 45%
* técnico 40%
* market regime 15%

12M:

* fundamental 60%
* técnico 25%
* market regime 15%

Estos pesos son únicamente una hipótesis inicial.

El backtesting deberá evaluar y eventualmente modificar los pesos.

⸻

23. PROBABILIDAD, NO SOLO SCORE

El sistema deberá terminar aprendiendo:

P(outperform benchmark | features)

Para:

* 6 meses;
* 12 meses.

Generar:

* signal;
* probability;
* expected excess return;
* confidence.

No confundir:

score

con:

probability.

Las probabilidades deberán calibrarse.

⸻

24. OUTPUT DEL ANÁLISIS

Ejemplo:

Ticker: XYZ

As of:
2020-10-01 16:00 ET

6M:
BUY

Probability outperform:
68%

Expected excess return:
+7.4%

12M:
BUY

Probability outperform:
72%

Expected excess return:
+11.2%

Fundamental:
82/100

Technical:
69/100

Risk:
61/100

Market regime:
74/100

POSITIVOS:

* ROIC aumentando.
* FCF sólido.
* valoración inferior a media histórica.
* fuerza relativa positiva.
* deuda descendiendo.

NEGATIVOS:

* margen operativo deteriorándose.
* valoración frente sector exigente.
* volatilidad aumentando.

Guardar íntegramente este análisis.

⸻

25. FEATURE SNAPSHOTS

Crear una tabla esencial:

feature_snapshots

Cada predicción debe conservar exactamente las features utilizadas.

Campos:

* snapshot_id
* security_id
* as_of
* model_version
* data_version
* feature_version
* valores de las features
* availability metadata

El resultado deberá ser totalmente reproducible años después.

⸻

26. VERSIONADO

Toda predicción deberá guardar:

* model_version;
* code_version;
* data_version;
* feature_version;
* scoring_version;
* config_version;
* git commit;
* execution timestamp.

Nunca sobrescribir predicciones históricas.

Deben ser inmutables.

⸻

27. SUSTITUIR EL TEST DIARIO 10+10

NO utilizar como método principal:

seleccionar diariamente 10 acciones del S&P 500 y 10 del IBEX.

Ese sistema genera demasiadas observaciones temporalmente solapadas y altamente correlacionadas.

Sustituirlo por una arquitectura de evaluación mucho más robusta.

Mantener opcionalmente un pequeño regression test diario únicamente para detectar errores del pipeline.

⸻

28. BACKTEST PRINCIPAL: PANEL HISTÓRICO COMPLETO

El backtest principal deberá evaluar:

TODAS las compañías que realmente pertenecían al universo en cada fecha.

No seleccionar solo 10.

Frecuencia configurable.

Por defecto:

monthly snapshots

por ejemplo, primera sesión de cada mes.

Esto reduce enormemente el solapamiento frente a evaluar todos los días.

También permitir:

* semanal;
* trimestral;
* fechas de rebalanceo;
* event-driven.

Cada snapshot:

1. reconstruye universo histórico;
2. reconstruye datos disponibles;
3. calcula features;
4. genera predicciones;
5. congela predicción;
6. espera conceptualmente el horizonte futuro;
7. calcula posteriormente el resultado.

⸻

29. EVITAR SOLAPAMIENTO DE TARGETS

Un target de 12 meses genera retornos solapados si utilizamos observaciones demasiado frecuentes.

Implementar análisis estadístico que tenga en cuenta esta dependencia.

Permitir dos modos.

NON-OVERLAPPING

Ejemplo:

12M horizon:

una cohorte cada 12 meses.

6M:

una cohorte cada 6 meses.

Sirve como evaluación muy limpia.

OVERLAPPING

Permitir mayor frecuencia para aumentar muestras, pero tratar correctamente autocorrelación y dependencia.

No considerar cada observación como independiente.

⸻

30. WALK-FORWARD VALIDATION

El método principal de validación debe ser temporal.

Ejemplo:

Train:
2005–2012

Validation:
2013–2014

Test:
2015

Después:

Train:
2005–2013

Validation:
2014–2015

Test:
2016

etc.

Permitir:

* expanding window;
* rolling window.

Nunca usar random shuffle para series temporales.

⸻

31. PURGED CROSS VALIDATION

Cuando existan labels con horizontes futuros solapados, implementar purging.

Eliminar del entrenamiento observaciones cuyo periodo de outcome se solape con la ventana de validación/test.

Ejemplo:

Una observación:

T0 = 2020-01-01

label_end = 2021-01-01

no puede formar parte del entrenamiento si su outcome invade temporalmente el periodo de test que queremos considerar desconocido.

⸻

32. EMBARGO

Incluir embargo temporal entre train y test.

Configurable según horizonte.

Evitar fugas indirectas debidas a observaciones casi idénticas temporalmente.

⸻

33. LABEL AVAILABILITY

Regla crítica:

Una observación histórica únicamente puede utilizarse para entrenar cuando su resultado ya habría sido conocido en la fecha de entrenamiento.

Ejemplo:

modelo reentrenado a:

2020-01-01

Una señal generada:

2019-08-01

con horizonte 12M no puede formar parte del training set porque su resultado se conocería aproximadamente en:

2020-08-01

Implementar explícitamente:

label_available_at

⸻

34. NESTED VALIDATION

Separar:

* entrenamiento;
* selección de hiperparámetros;
* validación;
* test final.

Los hiperparámetros nunca deben optimizarse mirando directamente el test final.

Implementar nested walk-forward cuando se utilice ML.

⸻

35. HOLDOUT FINAL

Reservar un periodo histórico completo como:

final_holdout

que no podrá utilizarse durante el desarrollo ni optimización.

Ejemplo configurable:

últimos 2–3 años disponibles.

Solo evaluar sobre él cuando una versión del modelo esté congelada.

Registrar cada acceso.

⸻

36. FORWARD PAPER TEST

Desde el momento actual, mantener además un test prospectivo real.

Cada señal generada hoy se guarda de forma inmutable.

Posteriormente se evalúa a:

* 6M;
* 12M.

Este será el test de máxima calidad porque no puede producirse look-ahead accidental.

Crear:

live_prediction_registry

⸻

37. CHAMPION / CHALLENGER

Mantener:

champion_model

y uno o varios:

challenger_models

Todos reciben exactamente los mismos snapshots.

Comparar posteriormente.

Un Challenger solo puede sustituir al Champion cuando demuestre mejoras robustas fuera de muestra.

No promover modelos por una única métrica.

⸻

38. BENCHMARKS

Cada acción deberá compararse contra:

1. índice principal;
2. sector;
3. eventualmente industria.

Ejemplo S&P:

benchmark mercado apropiado.

Ejemplo IBEX:

benchmark total-return equivalente.

Guardar:

stock_total_return

market_total_return

sector_total_return

market_excess_return

sector_excess_return

⸻

39. TARGET PRINCIPAL

El target principal debe ser:

future excess total return

No:

future price > current price

Ejemplo:

Stock:
+5%

Index:
+18%

Excess:
-13%

Una señal BUY probablemente no fue buena pese a que el precio aumentó.

⸻

40. TARGETS SECUNDARIOS

Guardar también:

* absolute return;
* excess return;
* sector excess return;
* volatility;
* downside volatility;
* max drawdown;
* max adverse excursion;
* max favorable excursion.

⸻

41. RISK-ADJUSTED PERFORMANCE

Calcular:

* Sharpe;
* Sortino;
* information ratio;
* maximum drawdown;
* Calmar;
* volatility;
* beta;
* downside risk.

Aplicar cuando tengan sentido estadístico.

⸻

42. TRANSACTION COSTS

Incluso aunque inicialmente solo analicemos señales, diseñar el backtester preparado para incorporar:

* comisiones;
* bid/ask spread;
* slippage;
* impuestos cuando proceda;
* FX;
* market impact opcional.

No asumir trading gratuito.

⸻

43. PORTFOLIO BACKTEST

Separar dos conceptos:

A. calidad de la predicción;

B. rentabilidad de una cartera.

Implementar ambos.

La calidad del modelo debe poder evaluarse sin depender de una estrategia concreta de portfolio construction.

Posteriormente permitir:

* equal weight;
* score weighted;
* volatility weighted;
* top N;
* long-only;
* market neutral;
* rebalanceo mensual/trimestral.

⸻

44. MÉTRICAS DE CLASIFICACIÓN

Calcular:

* accuracy;
* balanced accuracy;
* precision BUY;
* precision SELL;
* recall;
* F1;
* confusion matrix.

Pero estas métricas NO serán suficientes por sí solas.

⸻

45. CALIBRACIÓN

Para probabilidades:

* Brier Score;
* Log Loss;
* calibration curve;
* Expected Calibration Error si se desea.

Ejemplo:

Si el modelo genera cientos de señales con:

P(outperform)=70%

aproximadamente el 70% debería realmente superar el benchmark.

Analizar calibración por:

* mercado;
* horizonte;
* sector;
* régimen;
* confidence bucket.

⸻

46. INFORMATION COEFFICIENT

Calcular:

Spearman correlation(score, future_excess_return)

y opcionalmente Pearson.

Obtener:

* mean IC;
* median IC;
* IC volatility;
* information ratio del IC;
* IC por año;
* IC por sector;
* IC por régimen.

⸻

47. DECILE ANALYSIS

Ordenar acciones por score.

Crear:

D1 = peor 10%

…

D10 = mejor 10%.

Calcular retorno futuro medio/mediano de cada decil.

Evaluar:

* monotonicidad;
* D10-D1 spread;
* D10 vs benchmark;
* D1 vs benchmark.

Visualizarlo.

⸻

48. QUANTILE STABILITY

No basta con que D10 haya funcionado globalmente.

Calcular resultados por:

* año;
* década;
* sector;
* mercado;
* régimen.

Evitar modelos cuyo resultado dependa exclusivamente de pocos periodos.

⸻

49. REGIME ANALYSIS

Segmentar resultados en:

* bull;
* bear;
* sideways;
* high volatility;
* low volatility;
* crisis;
* rising rates;
* falling rates.

Comprobar en qué entornos funciona cada factor.

No adaptar automáticamente la conclusión para justificar el pasado.

⸻

50. ERROR ANALYSIS

Cada error importante debe generar una autopsia automática.

Ejemplo:

Prediction:
BUY 78%

Expected excess:
+11%

Actual excess:
-19%

Analizar qué ocurrió posteriormente.

Clasificaciones orientativas:

* valuation trap;
* earnings deterioration;
* sector shock;
* macro shock;
* momentum reversal;
* balance deterioration;
* idiosyncratic event;
* M&A;
* accounting issue;
* commodity shock;
* model calibration error;
* data quality problem;
* unknown.

No permitir que este análisis modifique directamente el modelo.

Solo generar hipótesis.

⸻

51. CONTROL CONTRA OVERFITTING

No ajustar los pesos después de cada error.

Crear ciclo:

error

→ análisis

→ hipótesis

→ challenger

→ backtest

→ walk-forward

→ holdout

→ forward validation

→ posible promoción.

Implementar registro de experimentos.

⸻

52. MULTIPLE TESTING

Si se prueban cientos o miles de combinaciones de features/parámetros, aumenta mucho la probabilidad de encontrar resultados aparentemente buenos por azar.

Registrar:

* número de experimentos;
* variantes evaluadas;
* métricas;
* periodo.

Incorporar cuando proceda:

* corrección por multiple testing;
* Probability of Backtest Overfitting;
* Deflated Sharpe Ratio;
* bootstrap;
* permutation tests.

No seleccionar modelos únicamente por el mejor Sharpe histórico.

⸻

53. BOOTSTRAP Y ROBUSTEZ

Implementar análisis de incertidumbre mediante:

* bootstrap;
* block bootstrap cuando proceda;
* confidence intervals.

Obtener intervalos para:

* IC;
* excess return;
* accuracy;
* Sharpe;
* decile spread.

⸻

54. SENSITIVITY ANALYSIS

Evaluar si pequeñas variaciones de parámetros destruyen el resultado.

Ejemplo:

Si funciona con:

SMA = 197

pero no con:

SMA 180–220,

puede existir sobreajuste.

Favorecer regiones estables de parámetros frente a óptimos puntuales.

⸻

55. ABLATION TESTING

Para cada grupo de features:

* Quality;
* Valuation;
* Momentum;
* Technical;
* Market Regime;
* etc.

Realizar tests eliminándolo.

Comparar impacto.

Esto permitirá descubrir si una familia de variables aporta información real.

⸻

56. FEATURE IMPORTANCE

Cuando se utilice ML:

* permutation importance;
* SHAP;
* gain importance con precaución;
* partial dependence cuando proceda.

Analizar estabilidad temporal de feature importance.

No aceptar un modelo únicamente porque tenga buen resultado agregado.

⸻

57. CONTROL DE CORRELACIÓN

Detectar features redundantes.

Crear:

* correlation matrix;
* clustering de features;
* VIF cuando corresponda;
* mutual information opcional.

Evitar incluir numerosos indicadores técnicos que describen esencialmente lo mismo.

⸻

58. DATA QUALITY ENGINE

Crear controles automáticos:

* missing values;
* outliers;
* duplicate rows;
* price gaps;
* impossible OHLC;
* negative values donde no procedan;
* discontinuidades;
* stale data;
* currency mismatch;
* corporate action errors;
* timestamp inconsistencies.

Registrar errores y provenance.

⸻

59. DATA LINEAGE

Cada feature debe poder responder:

¿de qué dato original salió?

Guardar:

* provider;
* original identifier;
* retrieval timestamp;
* raw record;
* transformations;
* version.

⸻

60. REPRODUCIBILIDAD

Dada:

* security_id;
* as_of;
* model_version;
* data_version;

el sistema debe poder reconstruir exactamente la misma predicción.

Guardar seeds aleatorios.

Usar configuraciones inmutables.

⸻

61. MACHINE LEARNING

Solo incorporar después de disponer de baseline interpretable.

Modelos iniciales recomendados para comparación:

* Logistic Regression;
* Linear/Elastic Net;
* Random Forest;
* Gradient Boosting;
* XGBoost;
* LightGBM si procede.

Evaluarlos contra el baseline.

No asumir que ML mejorará el resultado.

⸻

62. TARGETS ML

Posibles targets:

Clasificación:

outperform > 0

Regresión:

future_excess_return

También experimentar con:

future_rank_percentile

Comparar enfoques.

⸻

63. CROSS-SECTIONAL MODELING

Considerar especialmente modelos cross-sectional.

En cada fecha T:

comparar las acciones entre sí.

Normalizar features mediante:

* percentile rank;
* z-score;
* sector-neutral z-score.

Esto puede ser más robusto que comparar ratios absolutos durante décadas con diferentes regímenes.

⸻

64. NORMALIZACIÓN POR SECTOR

Para ratios muy dependientes del sector:

calcular:

sector_percentile

o:

sector_zscore

No penalizar automáticamente sectores estructuralmente distintos.

⸻

65. WINSORIZATION

Permitir tratamiento robusto de outliers.

Ejemplo:

winsorization cross-sectional por fecha.

Debe hacerse exclusivamente con datos disponibles dentro de esa fecha.

Nunca utilizar estadísticas calculadas sobre todo el dataset futuro.

⸻

66. SCALING

Cualquier scaler utilizado por ML deberá entrenarse exclusivamente sobre el training set.

No calcular media/desviación del dataset completo antes de dividir.

⸻

67. IMPUTATION

Igual para imputación.

La estrategia se aprende sobre training.

Nunca usar estadísticas futuras para rellenar históricos.

Registrar si un valor fue imputado.

⸻

68. DELISTING RETURNS

No eliminar una empresa justo antes de que desaparezca.

Incorporar cuando sea posible el retorno final de deslisting.

Si una compañía quiebra:

el resultado debe reflejarlo.

Este punto es fundamental contra survivorship bias.

⸻

69. M&A

Cuando una compañía sea adquirida:

calcular correctamente el retorno hasta:

* cash consideration;
* stock consideration;
* fecha efectiva.

No tratar la desaparición del ticker como dato perdido.

⸻

70. CORPORATE ACTIONS

Implementar tratamiento explícito de:

* splits;
* reverse splits;
* spin-offs;
* mergers;
* tender offers;
* special dividends;
* rights issues.

Añadir tests.

⸻

71. FX

Para compañías o benchmarks en divisas distintas:

separar:

* local return;
* base-currency return.

Configurable.

No mezclar inadvertidamente rentabilidades en EUR y USD.

⸻

72. ARQUITECTURA DE SOFTWARE

Preferencia inicial:

Backend:
Python.

API:
FastAPI.

Base de datos transaccional:
PostgreSQL.

Series históricas masivas:
Parquet + DuckDB o equivalente eficiente.

ORM:
SQLAlchemy.

Validation:
Pydantic.

Dataframes:
Polars preferentemente donde aporte rendimiento; Pandas donde sea necesario.

ML:
scikit-learn + XGBoost/LightGBM opcional.

Backtesting:
motor propio para garantizar control point-in-time.

Orquestación:
Prefect/Airflow/Dagster, seleccionar justificadamente.

Contenedores:
Docker.

Tests:
pytest.

Migrations:
Alembic.

Experiment tracking:
MLflow o equivalente.

Dashboards:
Plotly/Dash o frontend separado.

No quedar atado a estas tecnologías si existe una alternativa claramente superior, pero justificar cualquier cambio.

⸻

73. ESTRUCTURA DE MÓDULOS

Arquitectura orientativa:

src/
  core/
  config/
  security_master/
  data/
    providers/
    ingestion/
    validation/
    point_in_time/
    corporate_actions/
  universe/
    index_membership/
  fundamentals/
    quality/
    valuation/
    growth/
    balance/
    capital_allocation/
    sector_models/
  technical/
    trend/
    momentum/
    relative_strength/
    volatility/
    volume/
  market_regime/
  features/
    feature_store/
    snapshots/
  scoring/
  models/
    baseline/
    ml/
    calibration/
  signals/
  backtest/
    engine/
    execution/
    costs/
    labels/
    benchmarks/
  validation/
    walk_forward/
    purged_cv/
    embargo/
    holdout/
  analytics/
    metrics/
    deciles/
    ic/
    calibration/
    regimes/
    errors/
  experiments/
  api/
  jobs/
  tests/

⸻

74. BASE DE DATOS

Diseñar como mínimo:

securities

ticker_history

index_membership

prices

corporate_actions

dividends

financial_statements

fundamental_facts

analyst_estimates

macro_data

sector_classification

feature_snapshots

models

model_versions

predictions

backtest_runs

backtest_observations

realized_returns

benchmarks

experiments

error_analysis

live_predictions

data_sources

data_quality_issues

Diseñar índices SQL y relaciones apropiadas.

⸻

75. API

Endpoints orientativos:

POST /analysis

Recibe:

{
  "ticker": "AAPL",
  "as_of": "2020-10-01",
  "horizons": ["6m", "12m"]
}

GET /analysis/{prediction_id}

POST /backtests

GET /backtests/{id}

GET /models

GET /models/{version}

GET /securities/{ticker}

GET /universes/{index}/{date}

GET /analytics/model/{version}

⸻

76. DASHBOARD

Crear vistas para:

Stock Analyzer

Mostrar:

* señal;
* probabilidades;
* scores;
* ratios;
* gráficos;
* factores positivos/negativos.

Time Machine

Usuario selecciona:

Ticker + fecha.

El sistema enseña exactamente:

Qué habría dicho el modelo aquel día.

Y debajo:

Qué ocurrió después.

Model Performance

Mostrar:

* accuracy;
* IC;
* calibration;
* deciles;
* excess returns;
* drawdowns;
* resultados por año;
* sector;
* mercado;
* régimen.

Experiments

Champion vs challengers.

⸻

77. AUTOMATIZACIÓN

Crear pipelines automáticos para:

DAILY INGESTION

Actualizar:

* precios;
* corporate actions;
* nuevos filings;
* benchmark;
* macro;
* index changes.

FEATURE REFRESH

Calcular únicamente features nuevas.

LIVE ANALYSIS

Generar señales en frecuencia configurable.

BACKTEST RESEARCH

Ejecutar backtests programados.

MODEL MONITORING

Detectar:

* data drift;
* performance drift;
* calibration drift.

⸻

78. TEST DIARIO CORREGIDO

El antiguo sistema:

10 S&P + 10 IBEX diarios

NO será la validación científica principal.

Convertirlo en:

daily pipeline regression test

Ejemplo:

seleccionar un conjunto pequeño y determinista de securities y fechas históricas conocidas y comprobar:

* que la reconstrucción point-in-time sigue siendo igual;
* que no aparecen datos futuros;
* que las features no cambian inesperadamente;
* que las predicciones de una versión congelada son reproducibles.

Este test comprueba SOFTWARE.

No capacidad predictiva.

⸻

79. VALIDACIÓN ESTADÍSTICA PRINCIPAL

Usar:

1. panel histórico completo;
2. snapshots mensuales;
3. walk-forward;
4. purging;
5. embargo;
6. holdout;
7. forward paper test.

Esta será la evaluación real del MODELO.

⸻

80. TEST SUITE

Crear tests exhaustivos.

Especialmente:

test_no_future_financial_data

test_no_future_price_data

test_historical_index_membership

test_delisted_companies_preserved

test_next_session_execution

test_label_availability

test_purged_training

test_embargo

test_split_adjustment

test_dividend_total_return

test_merger_handling

test_reproducible_snapshot

test_timezone

test_market_calendar

test_scaler_train_only

test_imputer_train_only

test_holdout_never_used_for_training

test_model_version_immutability

⸻

81. PROPERTY-BASED TESTING

Incorporar Hypothesis o equivalente para propiedades importantes.

Ejemplo:

para cualquier snapshot:

max(feature.available_at) <= snapshot.as_of

debe ser siempre verdadero.

⸻

82. CI/CD

Cada commit deberá ejecutar:

* lint;
* type checks;
* unit tests;
* integration tests;
* point-in-time tests;
* database migration tests.

No desplegar si falla alguno.

⸻

83. LOGGING

Implementar structured logging.

Cada predicción deberá registrar:

* request;
* snapshot;
* data sources;
* model;
* features;
* execution;
* warnings.

⸻

84. CONFIGURACIÓN

Nada crítico debe estar hardcoded.

Utilizar YAML/TOML/env.

Ejemplo:

horizons:
  - 6m
  - 12m
execution:
  mode: next_open
backtest:
  rebalance_frequency: monthly
validation:
  mode: expanding_walk_forward
  embargo_days: configurable

⸻

85. DATA PROVIDERS

Crear interfaces abstractas:

PriceProvider

FundamentalProvider

IndexMembershipProvider

CorporateActionsProvider

MacroProvider

AnalystEstimatesProvider

para que podamos cambiar proveedores sin reescribir la aplicación.

Nunca diseñar la lógica central alrededor de un único proveedor externo.

⸻

86. CACHING

Implementar cache para:

* historical snapshots;
* fundamentals;
* features;
* index universe.

Evitar descargar o recalcular continuamente datos inmutables.

⸻

87. RATE LIMITING

Los conectores externos deberán:

* respetar rate limits;
* retry exponencial;
* cache;
* checkpoints;
* idempotencia.

⸻

88. IDEMPOTENCIA

Ejecutar dos veces un pipeline de ingestión para la misma fecha no debe crear duplicados ni inconsistencias.

⸻

89. FAIL LOUDLY

Si falta un dato esencial:

NO inventar.

NO reemplazar silenciosamente.

Marcar:

data_quality_warning

y reducir confianza o impedir predicción según severidad.

⸻

90. EXPLAINABILITY

Cada predicción debe poder explicar:

* principales factores positivos;
* principales factores negativos;
* contribution de features;
* comparación sectorial;
* comparación histórica.

No generar explicaciones inventadas mediante LLM desconectadas de los cálculos reales.

Toda explicación debe derivarse de datos efectivamente utilizados.

⸻

91. LLM OPCIONAL

Un LLM puede utilizarse posteriormente para:

* resumir filings;
* clasificar riesgos textuales;
* sintetizar resultados;
* redactar explicación comprensible.

Pero:

la señal cuantitativa no debe depender inicialmente de texto no reproducible.

Si se usa LLM:

guardar:

* modelo;
* versión;
* prompt;
* respuesta;
* timestamp;
* documentos utilizados.

⸻

92. RESULTADO DEL BACKTEST

Cada ejecución debe generar un informe completo.

Ejemplo:

Universe

S&P 500 historical
2005–2025

Predictions

125,422

Out-of-sample

34,872

12M

IC:
…

Accuracy:
…

Brier:
…

D10 excess:
…

D1 excess:
…

Spread:
…

Sharpe:
…

Max DD:
…

Resultados por:

* año;
* sector;
* régimen;
* confidence;
* score bucket.

⸻

93. EVITAR SESGO POR OPTIMIZACIÓN DEL UNIVERSO

No eliminar retrospectivamente:

* empresas pequeñas;
* empresas problemáticas;
* acciones con datos incompletos;

sin documentarlo.

Cada filtro debe formar parte de la definición point-in-time del universo.

Guardar motivo de exclusión.

⸻

94. MISSING DATA

No usar conocimiento futuro para decidir si una empresa “tenía suficientes datos”.

La disponibilidad también debe evaluarse point-in-time.

Registrar:

feature_missing_mask.

⸻

95. OUTPUT DE DESARROLLO QUE DEBES ENTREGAR

No quiero únicamente explicaciones.

Debes crear realmente el proyecto.

Trabaja por fases pero produce código ejecutable.

Entrega:

1. arquitectura;
2. estructura de carpetas;
3. modelo de datos;
4. migrations;
5. Security Master;
6. interfaces de data providers;
7. point-in-time engine;
8. ingestion pipeline;
9. feature engine;
10. fundamental engine;
11. technical engine;
12. market regime engine;
13. scoring baseline;
14. prediction engine;
15. backtest engine;
16. walk-forward engine;
17. purged/embargo validation;
18. analytics;
19. API;
20. dashboard básico;
21. tests;
22. Docker;
23. CI;
24. documentación;
25. ejemplos funcionales.

⸻

96. CRITERIO DE CALIDAD

No des una funcionalidad por terminada porque:

el código ejecuta.

Debe cumplir:

* correcta;
* testeada;
* tipada;
* documentada;
* reproducible;
* point-in-time;
* modular;
* auditable.

⸻

97. NO INVENTAR DATOS

Durante desarrollo puede utilizarse:

* mocks;
* fixtures;
* datasets sintéticos.

Pero deben estar claramente etiquetados.

Nunca presentar datos ficticios como históricos reales.

⸻

98. DESARROLLO ITERATIVO

Orden recomendado.

PHASE 1

Infraestructura + Security Master + historical universe.

PHASE 2

Market data + corporate actions + calendars.

PHASE 3

Point-in-time fundamentals.

PHASE 4

Feature store.

PHASE 5

Baseline scoring.

PHASE 6

Time-machine engine.

PHASE 7

Historical backtesting.

PHASE 8

Walk-forward + purging + embargo.

PHASE 9

Analytics dashboard.

PHASE 10

Machine learning challengers.

PHASE 11

Forward live test.

No saltar directamente a ML.

⸻

99. CRITERIO PARA PROMOVER UN MODELO

Un modelo nuevo solo puede convertirse en Champion si:

1. mejora fuera de muestra;
2. no empeora gravemente el drawdown;
3. mantiene calibración;
4. sus resultados no dependen de un único año;
5. funciona en varias submuestras;
6. sobrevive sensitivity analysis;
7. mejora suficientemente al baseline;
8. no utiliza información futura;
9. supera el holdout;
10. posteriormente mantiene comportamiento razonable en forward test.

⸻

100. REGLA DE ORO

Implementa esta filosofía en todo el proyecto:

El objetivo no es construir el backtest que mejor explique el pasado. El objetivo es determinar si la información disponible en cada momento contenía señal predictiva útil sobre resultados posteriores.

Ante cualquier decisión de arquitectura, prioriza:

1. ausencia de sesgos;
2. reproducibilidad;
3. auditabilidad;
4. robustez estadística;
5. interpretabilidad;
6. rendimiento computacional.

En ese orden.

⸻

101. PRIMERA TAREA

Antes de escribir miles de líneas de código:

1. transforma estos requisitos en arquitectura técnica;
2. identifica decisiones pendientes;
3. crea el esquema completo de datos;
4. define interfaces;
5. define flujo point-in-time;
6. define flujo de backtest;
7. define tests anti-leakage;
8. genera ADRs para las decisiones arquitectónicas relevantes;
9. después comienza a implementar.

No preguntes por detalles menores que puedan resolverse con decisiones razonables y configurables.

Cuando haya varias alternativas razonables:

* selecciona una;
* explica brevemente por qué;
* implementa de forma desacoplada para poder sustituirla.

⸻

102. DEFINICIÓN FINAL DEL PRODUCTO

El producto terminado debe permitir hacer dos cosas distintas.

ANÁLISIS ACTUAL

Usuario introduce:

AAPL

El software devuelve:

* fundamental;
* técnico;
* valoración;
* riesgo;
* contexto;
* BUY/HOLD/SELL;
* probabilidades 6M/12M;
* explicación.

TIME MACHINE

Usuario introduce:

AAPL

2018-06-01

El software reconstruye exclusivamente la información disponible el 1 de junio de 2018, ejecuta la versión seleccionada del modelo y responde:

Esto es lo que habría dicho el software aquel día.

Después muestra:

Esto fue lo que realmente ocurrió a 6 y 12 meses.

Incluyendo:

* total return;
* benchmark return;
* excess return;
* sector excess;
* drawdown;
* resultado de la señal.

Finalmente muestra el comportamiento estadístico de ese modelo sobre miles de situaciones equivalentes.

⸻

No simplifiques ninguno de los controles contra:

* look-ahead bias;
* survivorship bias;
* data leakage;
* label leakage;
* overlapping labels;
* overfitting;
* multiple testing;
* selection bias.

Si una funcionalidad aparentemente mejora resultados pero compromete la integridad temporal del sistema, debe rechazarse.

Construye el sistema como si sus resultados tuvieran que ser auditados posteriormente por un equipo cuantitativo independiente.