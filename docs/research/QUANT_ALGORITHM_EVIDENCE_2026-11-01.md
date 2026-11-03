# Algoritmos cuantitativos: evidencia pública y selección para PITQuant

Fecha de revisión: 1 de noviembre de 2026. Investigación documental; ninguna ejecución de estrategias, instalación, entrenamiento o apertura de datos reservados. Las prioridades siguientes son propuestas de investigación, no modificaciones de los experimentos congelados.

## Conclusión de trabajo

La vía con mejor relación entre evidencia, coste y encaje es investigar estrategias sencillas de momentum, value y calidad; conservar boosting/ranking como candidato supervisado; y evaluar carteras después de costes. No hay fundamento para afirmar que hemos encontrado el algoritmo completo de Medallion, Citadel o Jane Street en GitHub. Sí hay métodos públicos útiles y algunas familias ya coinciden con las de PITQuant.

Tres objetos diferentes: una **señal** (momentum o calidad), un **modelo** que combina señales (ridge, árboles o redes) y una **política de cartera/ejecución** que convierte scores en posiciones. Un paper puede apoyar uno de esos objetos sin validar los otros. Ordenar bien activos tampoco equivale a conocer su precio futuro o el mejor instante de entrada.

## 1. Qué reconocen las seis firmas

| Firma | Evidencia pública verificable | Qué NO permite concluir |
|---|---|---|
| Renaissance Technologies | Su [web oficial](https://www.rentec.com/) declara métodos matemáticos y estadísticos para diseñar y ejecutar inversiones. | No publica allí una especificación reproducible de Medallion. No atribuirle HMM, redes o una fórmula concreta solo por relatos sobre sus investigadores. |
| Two Sigma | Su [página de inversión](https://www.twosigma.com/businesses/investment-management/) menciona explícitamente regresiones ridge, NLP, deep learning sobre secuencias y combinación de pronósticos con costes y riesgo. | Que use ridge no significa que nuestros datos, señales, parámetros o rendimiento sean iguales. No he encontrado aquí un sistema completo que podamos copiar. |
| D. E. Shaw | Describe [estrategias sistemáticas](https://www.deshaw.com/what-we-do/investment-management). Su artículo [Machine Teaching](https://www.deshaw.com/assets/articles/DESCO_Machine_Teaching_20231211.pdf), diciembre de 2023, confirma uso de optimizadores para construir y gestionar carteras. | Una explicación de optimización no revela su alpha ni un modelo predictivo listo para operar. |
| Citadel | [GQS](https://www.citadel.com/what-we-do/global-quantitative-strategies/) confirma estrategias algorítmicas automatizadas. Una [vacante oficial de investigación](https://www.citadel.com/careers/details/global-quantitative-strategies-gqs-machine-learning-researcher/) enumera deep learning, series temporales, NLP, LLM y RL. | La vacante informa sobre líneas de trabajo, no demuestra qué modelo concreto opera cada fondo ni su rentabilidad. Citadel Securities es una empresa distinta: su [investigación](https://www.citadelsecurities.com/careers/quantitative-research/) se centra también en microestructura. |
| AQR | Publica artículos, definiciones y [datos de value y momentum](https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Factors-Monthly), además de calidad, beta y trend. | Sus artículos no son especificaciones completas de sus productos actuales; sus propias páginas distinguen investigación de productos. |
| Jane Street | Su [página de ML](https://www.janestreet.com/join-jane-street/machine-learning/) confirma redes neuronales para estrategias y desarrollo de arquitecturas propias. | No proporciona pesos, datos y reglas suficientes para reproducir su sistema. Un notebook de una competición con su nombre no constituye su estrategia de producción. |

Inferencia para PITQuant: las técnicas lineales no son impropias de un sistema profesional. El déficit que debemos resolver es empírico —transferencia temporal, datos y coste de implementación—, no encontrar un nombre de algoritmo más impresionante.

## 2. Papers que merecen trabajo

Los niveles son una valoración de esta revisión: **A**, evidencia amplia y relacionada con otras investigaciones; **B**, evidencia empírica pertinente pero limitada para nuestro caso; **C**, exploración; **I**, infraestructura sin demostración de alpha. Ningún nivel implica rentabilidad futura garantizada.

| Investigación | Método, evidencia y límite | Encaje y prioridad |
|---|---|---|
| Moskowitz, Ooi y Pedersen, **Time Series Momentum**, JFE, 2012. [Fuente](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum) | **A**. Tendencia propia a partir del retorno pasado; analiza 58 futuros/forwards de distintas clases durante más de 25 años. Diferente del momentum relativo entre acciones. | Primera referencia para una estrategia de tendencia. La adaptación BTC spot long/cash no reproduce una cartera diversificada long/short de futuros. |
| Hurst, Ooi y Pedersen, **A Century of Evidence on Trend-Following Investing**, JPM, 2017. [Fuente](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) | **A**. Extiende la historia de trend; la versión oficial consultada remonta la reconstrucción a 1880. [Trends Everywhere, 2020](https://www.aqr.com/insights/research/journal-article/trends-everywhere) añade mercados no examinados previamente. | Justifica estudiar robustez entre mercados y periodos. Reconstrucciones históricas y costes estimados no equivalen a décadas de operación real. |
| Asness, Moskowitz y Pedersen, **Value and Momentum Everywhere**, Journal of Finance, 2013. [Fuente](https://www.aqr.com/insights/research/journal-article/value-and-momentum-everywhere) | **A**. Primas de value y momentum en ocho mercados/clases y diversificación entre ambas familias. No necesita deep learning. | Prioridad para controles de ranking de acciones. Seleccionar solo ganadores long-only y usar fundamentales SEC exige una nueva adaptación evaluada. |
| Asness, Frazzini y Pedersen, **Quality Minus Junk**, Review of Accounting Studies, 2019. [Artículo](https://link.springer.com/article/10.1007/s11142-018-9470-2) | **A**. Calidad combina rentabilidad, crecimiento y seguridad; evidencia estadounidense e internacional. No es simplemente comprar un ROE alto. | Aprovecha parte de nuestros fundamentales. Revisar cinco años de historia, accruals, deuda y disponibilidad PIT antes de afirmar réplica. Un subconjunto debe llamarse proxy. |
| Gu, Kelly y Xiu, **Empirical Asset Pricing via Machine Learning**, RFS, 2020. [NBER y publicación](https://www.nber.org/papers/w25398) | **B** para PITQuant. Compara modelos lineales, árboles y redes para primas de acciones; encuentra valor en interacciones no lineales y señales de momentum, liquidez y volatilidad. | Apoya un challenger tabular acotado; no prueba nuestro horizonte H12 ni nuestras features. La [web del autor](https://dachxiu.chicagobooth.edu/) enlaza código, pero su repositorio es de simulaciones, no una réplica integral de producción. |
| Poh, Lim, Zohren y Roberts, **Building Cross-Sectional Systematic Strategies by Learning to Rank**, preprint 2020, versión publicada en JFDS. [Paper](https://arxiv.org/abs/2012.07149), [texto](https://arxiv.org/pdf/2012.07149) | **B**. LambdaMART/XGBoost y otros rankers para momentum; NYSE/CRSP 1980–2019, carteras mensuales y targets de 21 días. Los resultados principales excluyen costes de transacción. | Referencia especialmente cercana a nuestro XGBRanker. No autoriza copiar su rendimiento a H12, ni explica los seis IC indefinidos. No localicé en el paper consultado un enlace a un repositorio oficial completo. |
| Jensen, Kelly y Pedersen, **Is There a Replication Crisis in Finance?**, Journal of Finance, 2023. [Artículo](https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13249) | **A** como evidencia de amplitud: 153 factores, 93 países y 13 temas, con análisis bayesiano de replicación. | Catálogo y contraste externo. Su muestra, construcción y pruebas no convierten automáticamente un factor en una estrategia rentable en nuestro universo. |
| Chen y Zimmermann, **Open Source Cross-Sectional Asset Pricing**, Critical Finance Review, 2022. [Autores/código](https://github.com/OpenSourceAP/CrossSection), [manuscrito](https://www.cfr-cologne.de/download/workingpaper/cfr-20-04.pdf) | **A** para transparencia de definiciones y reproducción. Proporciona construcción de señales y carteras, no un predictor único universal. | Referencia para especificar indicadores verificables y evitar reinventar fórmulas. Reproducir un resultado en su muestra no demuestra rendimiento posterior. |
| Liu y Tsyvinski, **Risks and Returns of Cryptocurrency**, RFS, 2021. [Working paper de autores](https://www.nber.org/papers/w24877) | **B**. Encuentra momentum temporal y atención como variables relevantes para cripto. El mercado y la disponibilidad de señales pueden cambiar. | Justifica controles de momentum BTC. La atención histórica necesitaría timestamps y archivo propio; no introducirla retroactivamente como dato PIT. |
| Boyd et al., **Multi-Period Trading via Convex Optimization**, 2017. [Autor y código asociado](https://stanford.edu/~boyd/papers/cvx_portfolio.html) | **I**. Optimización de retorno esperado, riesgo, transacciones y costes de mantener posiciones. El artículo no resuelve cómo producir buenos pronósticos. | Útil para pesos, rotación y restricciones cuando exista señal. No añadir un optimizador como supuesto remedio a un predictor sin ventaja. |
| Rozario et al., **A Decade of Evidence of Trend Following Investing in Cryptocurrencies**, 2020. [Preprint](https://arxiv.org/abs/2009.12155), [código de autores](https://github.com/Globe-Research/bittrends) | **C**. Ejemplo de tendencia BTC con código. El rendimiento extraordinario del resumen no es una expectativa utilizable. No he verificado una publicación revisada por pares para esta versión. | Material de estudio, no bot para instalar. El código consultado es antiguo, corta precios en diciembre de 2019 y exige adaptación. |

La combinación value + quality + momentum propuesta aquí sería una **combinación nueva para PITQuant**, no un algoritmo idéntico de AQR ni una conclusión de un único paper que certifique esa combinación concreta.

## 3. Evidencia que limita las promesas

No se seleccionaron únicamente artículos con resultados favorables:

- **Hou, Xue y Zhang, Replicating Anomalies, RFS 2020:** reducir el peso de microcaps y cambiar procedimientos elimina muchas significancias. Esto contrasta con las conclusiones más favorables de otras réplicas; no usan exactamente los mismos diseños. [Manuscrito de los autores](https://theinvestmentcapm.com/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf).
- **McLean y Pontiff, Does Academic Research Destroy Stock Return Predictability?, Journal of Finance 2016:** documenta deterioro fuera de muestra y después de publicación. Una fórmula conocida puede seguir conteniendo información y, a la vez, tener menos prima explotable. [Paper de los autores](https://papers.ssrn.com/abstract_id=2156623).
- **Frazzini, Israel y Moskowitz, Trading Costs, working paper 2018:** estudia ejecuciones institucionales reales; el coste depende de tamaño, activo y ejecución. Sus condiciones no son automáticamente las de nuestro bróker. [Fuente](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs).
- **Muravyev et al., Anomalies and Their Short-Sale Costs, Journal of Finance 2025:** en 162 anomalías, los costes del préstamo de acciones eliminan buena parte de los beneficios anormales estudiados. Esto impide trasladar sin ajustes una cartera académica long/short a una cuenta real. [Artículo](https://doi.org/10.1111/jofi.13501).
- **Grobys et al., Cryptocurrency momentum has (not) its moments, 2025:** documenta crashes de momentum cripto y sensibilidad a la construcción de la cartera. [Artículo](https://link.springer.com/article/10.1007/s11408-025-00474-9). No es el mismo diseño que BTC long/cash.

Decisión: medir ventaja **neta** frente a referencias sencillas y a riesgo comparable; no elegir artículos o modelos por su Sharpe más alto.

## 4. GitHub: qué reutilizar y qué no

Licencias identificadas en repositorios/API a fecha de consulta; no constituyen revisión legal completa. La licencia del código no libera los datos de sus restricciones. Las fechas de push son señales de actividad, no pruebas de calidad ni de rentabilidad. El JSON adjunto conserva metadatos, referencias de commits y hashes de los archivos concretos revisados.

| Repositorio | Licencia identificada | Uso propuesto y fricción |
|---|---|---|
| [OpenSourceAP/CrossSection](https://github.com/OpenSourceAP/CrossSection) | GPL-2.0 | Consultar definiciones y contrastes. El pipeline actual incluye Python/R y fuentes WRDS. No copiar todo su código ni sustituir nuestra procedencia de datos; revisar compatibilidad antes de incorporar código GPL. |
| [bkelly-lab/jkp-data](https://github.com/bkelly-lab/jkp-data) | Código MIT; datos distribuidos CC BY-NC 4.0 | Es el sucesor Python recomendado por los autores. Requiere WRDS para reconstruir datos; su README describe ejecución completa con 450 GB RAM y 128 cores. Aprovechar definiciones seleccionadas, no lanzar el pipeline global. |
| [bkelly-lab/ReplicationCrisis](https://github.com/bkelly-lab/ReplicationCrisis) | Sin licencia detectada por API | El README declara que ya no se mantiene y remite a jkp-data. No empezar una integración nueva desde esta base antigua. |
| [xiubooth/ML_Codes](https://github.com/xiubooth/ML_Codes) | Sin licencia detectada por API; copyright de autores en README | Enlazado por Dacheng Xiu; contiene simulaciones. No presentarlo como implementación integral, actual y libre para copiar de todo Gu–Kelly–Xiu. |
| [microsoft/qlib](https://github.com/microsoft/qlib) | MIT | Referencia de workflows y modelos, no sustituto del motor PIT. El archivo revisado `qlib/contrib/model/gbdt.py` configura MSE/binary: no es por sí mismo un ranker por queries ni una garantía de nuestro contrato temporal. |
| [lightgbm-org/LightGBM](https://github.com/lightgbm-org/LightGBM) | MIT | Biblioteca oficial para un único challenger futuro si se aprueba un experimento nuevo. La antigua URL microsoft/LightGBM redirige a esta organización. No cambia automáticamente la evidencia del modelo. |
| [catboost/catboost](https://github.com/catboost/catboost) | Apache-2.0 | Alternativa técnica mantenida. Posponer: instalar varios boosters y elegir después el que gane en el mismo DEV aumenta el riesgo de selección adaptativa. |
| [scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn) | BSD-3-Clause | Biblioteca ya coherente con nuestra arquitectura para controles lineales y, eventualmente, random forest. Reutilizar implementación oficial sin confundir biblioteca con estrategia. |
| [cvxgrp/cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | GPL-3.0 | Referencia de carteras/costes; revisar compatibilidad y necesidad antes de integrar. No es un predictor ni sustituye el registro inmutable de operaciones de PITQuant. |
| [Globe-Research/bittrends](https://github.com/Globe-Research/bittrends) | MIT | Notebook/código de un preprint, última actividad de push identificada en 2020. En `Price_Data.py` hay un corte de 2019 y `time.sleep` sin importación visible de `time`; no se ejecutó. No es una dependencia lista para producción. |
| [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | MIT | Framework de reinforcement learning. Se pospone por complejidad de recompensa, simulador y evaluación; su existencia no demuestra ventaja neta para PITQuant. No se auditó su código interno. |

No se instalaron estas bibliotecas ni se clonaron/ejecutaron esos proyectos. Revisión estática limitada a READMEs, metadatos y los archivos listados en el JSON. Tampoco se asumió que un repo comunitario que cite a un fondo sea de ese fondo.

## 5. Qué haría en PITQuant para ahorrar trabajo

Las siguientes son prioridades de ingeniería/investigación propias, inferidas de las fuentes; **no un protocolo ya aprobado**.

| Orden | Trabajo propuesto | Reutilización | Condición para hacerlo |
|---|---|---|---|
| 1 | Especificar tres controles de equity: momentum, value y quality; un control BTC de tendencia. Compararlos con benchmark y alternativa trivial. | Precios y fundamentales de PITQuant, definiciones de artículos. | Primero mapear exactamente qué inputs existen a T0; no rellenar cinco años faltantes ni equiparar un proxy a QMJ. |
| 2 | Elegir explícitamente el producto: ranking de siguiente mes o predicción H12. | Contratos y simulador existentes. | Mantener experimentos separados: rebalancear mensualmente no significa predecir a 12 meses. Cambiar target/folds exigiría una versión metodológica distinta, no una reparación técnica. |
| 3 | Auditar si los controles explican lo que aprende nuestro modelo; después, como máximo un challenger tabular. | Observabilidad nueva; boosting ya investigado. | Resolver aprobación de V0R2 por separado. Propuesta preferida si se abre una investigación posterior: LightGBM; mantener XGB como referencia y no buscar simultáneamente en todas las familias. No se afirma superioridad de LightGBM. |
| 4 | Pasar de scores a cartera con pesos y límites sencillos antes de optimización compleja. | Simulation Lab y seguimiento de operaciones. | Incorporar rotación, spread, comisiones, slippage, dividendos/corporate actions y, si aplica, préstamo/funding. No equiparar retorno de precio y total return. |
| 5 | Comparación prospectiva estable con pronósticos guardados y versión fija. | Snapshots y registro de predicción/operación ya existentes. | Toda predicción debe existir antes del resultado; un hueco forward permanece hueco. No elegir retrospectivamente solo las operaciones favorables. |

Para una réplica futura se necesitan calendario y universo de la fecha, activos desaparecidos, datos conocidos en T0, etiquetas maduras, splits temporales purgados por solapamiento y todos los intentos registrados. En H12, doce meses de observaciones solapadas no son doce apuestas independientes. Los controles de costes y riesgo deben aplicarse igual a la estrategia y a su benchmark. Estas son condiciones del diseño propuesto; no se han dado por cumplidas para cada dataset externo.

No abrir holdout/OOT para elegir entre los candidatos de esta lista. La búsqueda bibliográfica ya informa nuestras decisiones: una futura selección basada en ella debe reconocer esa adaptación y congelarse antes de observar nuevos resultados.

## 6. Qué pospondría

- Entrenar un LLM financiero propio para decidir operaciones. El uso de LLM por firmas confirma una familia tecnológica, no su adecuación a nuestro dataset. Un asistente para explicar fuentes es un proyecto distinto de un predictor numérico.
- Reinforcement learning, transformers o redes profundas sin un control tabular y una muestra temporal suficiente. No están descartados para siempre; no son el siguiente ahorro evidente.
- Market making/HFT: [Avellaneda–Stoikov, 2008](https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf) es una referencia legítima de cotización e inventario, pero una teoría no aporta nuestra cola de órdenes, latencia o ejecución real. No se atribuye su uso actual a Jane Street o Citadel.
- Pairs trading: [Gatev, Goetzmann y Rouwenhorst](https://www.nber.org/papers/w7032.pdf) estudian una regla relativa clásica. Hace falta evaluar otra estrategia con dos patas, costes y préstamo; no es un plugin que mejore automáticamente el predictor direccional existente.
- Reescribir PITQuant sobre Qlib o descargar todo WRDS. Se pueden aprovechar ideas sin perder los controles de trazabilidad ya construidos.

## 7. Alcance, límites y entrega

La investigación revisó fuentes corporativas primarias, publicaciones y manuscritos de autores, repositorios oficiales/académicos y API de GitHub. Se consultaron resúmenes y secciones metodológicas relevantes; no se reprodujeron tablas econométricas ni se realizó auditoría integral de seguridad, licencias, código o datos. Algunas páginas de editoriales no pudieron recuperarse y se usaron manuscritos de autores/NBER identificados como tales. Ningún resultado externo se presenta como un resultado nuestro ni como prueba de rentabilidad futura.

Las seis firmas no son idénticas ni operan un único horizonte. La estrategia y el acceso a datos/ejecución importan tanto como el algoritmo. El resultado práctico es una lista corta razonada: **controles de momentum/value/quality, tendencia BTC como adaptación explícita, y un challenger tabular limitado si se autoriza investigación posterior**.

Estado de este trabajo: solo documentación. Fits nuevos = 0; predicciones DEV nuevas = 0; holdout outcomes accessed = 0; OOT outcomes accessed = 0. Sin cambios de gates, champion, datasets o manifiestos; sin órdenes, commits ni merges.
