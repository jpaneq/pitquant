# Pilotos forward y auditoría de las 290 decisiones — 2026-11-03

## Qué se ha observado

58 selecciones originaron 290 decisiones (cinco horizontes), de las cuales 86
fueron BUY y 204 NO_ORDER. Son reglas antiguas, no predicciones de los nuevos
modelos. Entre las compras: 19 objetivos, 20 stops y 47 pendientes (8 todavía
sin primera vela elegible). Ningún horizonte calendario original ha vencido.

Entre las 39 decisiones cerradas: 48,72 % de objetivos, retorno bruto medio
−1,074 %, ganancia media +5,290 % y pérdida media −7,119 %. Con esos tamaños
medios observados se necesitaría aproximadamente 57,37 % de acierto para
compensar pérdidas, antes de costes. Es una descripción del grupo cerrado,
no una estimación estable ni una recomendación de umbrales. Las 204 NO_ORDER
son contrafactuales: 38 objetivos, 61 stops, 95 pendientes y 10 sin datos.

No se deben contar los horizontes del mismo valor como apuestas independientes,
ni sumar los retornos como si cada decisión tuviese todo el capital disponible.
Los cierres tempranos seleccionan unas observaciones y todavía no permiten
comparar de forma definitiva todos los horizontes. Se conserva cada decisión;
no se modifican reglas a posteriori para hacer aparecer mejores resultados.
La app muestra este resumen en /operaciones y el detalle por decisión sigue
accesible. GET /trades/audit devuelve filas, mercados y horizontes.

## Pilotos ejecutados

Acciones: 27.370 filas de entrenamiento; diez acciones fijas por disponibilidad.
BTC: 2.560 filas. Dos modelos logísticos V1 y once pronósticos reales del 3 de
noviembre, basados en cierres del 2 de noviembre. Cero órdenes automáticas.
Las probabilidades son experimentales y no tienen calibración demostrada.

Replay BTC 24 meses: solo el tramo permitido 2024-11-03 a 2025-08-31;
301 observaciones, 11 intervalos sin solapamiento temporal (no independencia
estadística). Acierto 62,46 %, siempre-subida 56,15 %, momentum 51,83 %;
Brier 0,23424 y LogLoss 0,66119. Son datos de vintage actual y no forward real.
Los replays equity 12/24 y BTC 12 meses permanecen bloqueados por reservas.
Holdout outcomes accessed = 0; OOT outcomes accessed = 0.

## Uso

Desde la raíz del repositorio, con el entorno ya instalado:

```sh
export PITQUANT_DATABASE_URL="sqlite+pysqlite:////Users/jairo/Proyectos/pitquant/data/pitquant.db"
export PYTHONPATH="$PWD/src"
.venv/bin/python scripts/forward_pilots.py
```

Este comando genera los pronósticos actuales si hay cierres frescos y revisa
los emitidos; no descarga precios, no entrena ni abre operaciones. Primero
actualiza las fuentes mediante los procedimientos de ingesta existentes.
Los datos ausentes quedan como huecos; no se simula haber emitido señales ayer.

Entrenamiento inicial idempotente (ya ejecutado, no hace nuevos fits si V1 existe):

```sh
.venv/bin/python scripts/forward_pilots.py --train
```

Candidato mensual explícito, solo cuando existan etiquetas forward maduras:

```sh
.venv/bin/python scripts/forward_pilots.py --candidate
```

No se activa un programador automáticamente. Para seguimiento diario, programar
el primer comando después de los cierres/ingesta. Revisiones: acciones 1,5,10,20
sesiones; BTC 1,7,14,30 días. V1 sigue fija. No promover candidatos automáticamente.
Los controles direccionales se comparan sobre los mismos pronósticos maduros;
las simulaciones manuales y benchmarks se muestran por separado, con al menos
10 cierres para agregados. La app está en http://127.0.0.1:8000/pilotos.

Para servir tras instalar dependencias y compilar frontend:

```sh
.venv/bin/python -m uvicorn pitquant.api.main:app --host 127.0.0.1 --port 8000
```

## Corrección técnica de las reglas anteriores

20/86 compras se emitieron con precio etiquetado STALE. Las nuevas decisiones
exigen LIVE/EOD para abrir; STALE/UNAVAILABLE/desconocido conservan análisis y
contrafactual pero no orden. Política FRESH_QUOTE_REQUIRED_V2. No se reescriben
las decisiones antiguas ni se reajustan los parámetros de señal, ATR o volatilidad.

## Desglose de las compras antiguas al corte

| Mercado | Compras | Objetivos | Stops | Pendientes | Media bruta cerradas |
|---|---:|---:|---:|---:|---:|
| BTC | 10 | 0 | 5 | 5 | -6.61 % |
| IBEX | 15 | 1 | 5 | 9 | -3.29 % |
| MSCI_WORLD | 16 | 7 | 0 | 9 | 4.92 % |
| SP500 | 45 | 11 | 10 | 24 | -1.12 % |

| Horizonte antiguo | Compras | Objetivos | Stops | Pendientes |
|---|---:|---:|---:|---:|
| 1 meses | 18 | 8 | 7 | 3 |
| 3 meses | 18 | 5 | 7 | 6 |
| 6 meses | 18 | 4 | 4 | 10 |
| 12 meses | 16 | 1 | 1 | 14 |
| 24 meses | 16 | 1 | 1 | 14 |

BTC agrupa solo dos selecciones: sus cinco stops son horizontes del mismo episodio, no cinco pruebas independientes. No elegir mercados o horizontes ganadores tras ver esta tabla.

## Validación de implementación

Comprobados lint, tipos estrictos, suite temporal (515 pruebas), suite SQLite
(1.170 aprobadas, tres skips de datos locales), PostgreSQL estricto (21),
migraciones upgrade/check/downgrade y frontend (77 pruebas, compilación).
Una prueba adicional posterior comprueba que UPDATE/DELETE SQL directos sobre
el diario SQLite fallan; las 13 pruebas específicas del piloto pasan.
Los avisos de frontend preexistentes no bloquean la compilación.
Se han evaluado las posiciones antiguas sin abrir nuevas: tres cierres
adicionales registrados. El resultado consolidado sigue siendo 19 objetivos,
20 stops y 47 pendientes de compra en la auditoría al corte.
