# Bloqueos de identidad por security (generado)

Generado con `scripts/gen_identity_reports.py` desde el run `7854a476-c1cd-4475-97e5-f3234643abe0`. Fechas candidatas: primer día hábil de cada mes entre 2011-01-01 y 2026-10-01 (190). `backtest_universe` falla cerrado si UN miembro no tiene identidad probada; este informe no relaja nada, sólo registra qué security bloquea qué fechas. Entrada de trabajo de la siguiente iteración.

Fechas backtestables: **0/190**.

| security | blocked_dates | first_blocked_date | last_blocked_date | reason | missing_evidence |
|---|---|---|---|---|---|
| MTS | 186 | 2011-01-03 | 2026-06-01 | UNRESOLVED: 2026-06-30:none:- | ninguna línea ordinaria ANCV con la etiqueta del código BME dentro del intervalo: falta un documento oficial fechado código BME ↔ ISIN (boletín BME, ficha archivada o ISIN extranjero del emisor) |
| MTS | 4 | 2026-07-01 | 2026-10-01 | PROVISIONAL: trailing edge after an unresolved run | corroboración oficial exacta del ISIN tras el último snapshot ANCV (composición BME archivada, no transcrita) |
| **MTS (total únicas)** | 190 | 2011-01-03 | 2026-10-01 | | |
| LOG | 42 | 2023-01-02 | 2026-06-01 | PROVISIONAL: 2026-06-30:ambiguous:ES0105027009/ES0160973014 (candidatos ES0105027009, ES0160973014) | dos líneas ordinarias comparten etiqueta ANCV: falta un documento oficial exacto (aviso/folleto) que fije cuál es la clase cotizada en el IBEX |
| LOG | 4 | 2026-07-01 | 2026-10-01 | PROVISIONAL: trailing edge after an unresolved run | corroboración oficial exacta del ISIN tras el último snapshot ANCV (composición BME archivada, no transcrita) |
| **LOG (total únicas)** | 46 | 2023-01-02 | 2026-10-01 | | |
| FER | 42 | 2023-01-02 | 2026-06-01 | UNRESOLVED: 2026-06-30:none:- | ninguna línea ordinaria ANCV con la etiqueta del código BME dentro del intervalo: falta un documento oficial fechado código BME ↔ ISIN (boletín BME, ficha archivada o ISIN extranjero del emisor) |
| FER | 4 | 2026-07-01 | 2026-10-01 | PROVISIONAL: trailing edge after an unresolved run | corroboración oficial exacta del ISIN tras el último snapshot ANCV (composición BME archivada, no transcrita) |
| **FER (total únicas)** | 46 | 2023-01-02 | 2026-10-01 | | |
| PUIG | 23 | 2024-08-01 | 2026-06-01 | PROVISIONAL: 2026-06-30:ambiguous:ES0105777009/ES0105777017 (candidatos ES0105777009, ES0105777017) | dos líneas ordinarias comparten etiqueta ANCV: falta un documento oficial exacto (aviso/folleto) que fije cuál es la clase cotizada en el IBEX |
| PUIG | 4 | 2026-07-01 | 2026-10-01 | PROVISIONAL: trailing edge after an unresolved run | corroboración oficial exacta del ISIN tras el último snapshot ANCV (composición BME archivada, no transcrita) |
| **PUIG (total únicas)** | 27 | 2024-08-01 | 2026-10-01 | | |
| ABG.P | 8 | 2012-11-01 | 2013-06-03 | UNRESOLVED: 2013-06-30:none:- | ninguna línea ordinaria ANCV con la etiqueta del código BME dentro del intervalo: falta un documento oficial fechado código BME ↔ ISIN (boletín BME, ficha archivada o ISIN extranjero del emisor) |
| ABG.P | 12 | 2014-07-01 | 2015-06-01 | UNRESOLVED: 2015-06-30:none:- | ninguna línea ordinaria ANCV con la etiqueta del código BME dentro del intervalo: falta un documento oficial fechado código BME ↔ ISIN (boletín BME, ficha archivada o ISIN extranjero del emisor) |
| ABG.P | 5 | 2015-07-01 | 2015-11-02 | PROVISIONAL: trailing edge after an unresolved run | corroboración oficial exacta del ISIN tras el último snapshot ANCV (composición BME archivada, no transcrita) |
| **ABG.P (total únicas)** | 25 | 2012-11-01 | 2015-11-02 | | |
| GRF | 6 | 2016-01-04 | 2016-06-01 | PROVISIONAL: unexplained window between snapshots (candidatos ES0171996012, ES0171996087) | fecha oficial del cambio de ISIN (hecho relevante/aviso de canje o cambio de nominal) o fecha de emisión ANCV del ISIN nuevo |
| REE | 6 | 2016-07-01 | 2016-12-01 | PROVISIONAL: unexplained window between snapshots (candidatos ES0173093115, ES0173093024) | fecha oficial del cambio de ISIN (hecho relevante/aviso de canje o cambio de nominal) o fecha de emisión ANCV del ISIN nuevo |
| PHM | 3 | 2020-10-01 | 2020-12-01 | PROVISIONAL: leading edge: 2020-06-30: ISIN absent (candidatos ES0169501022) | snapshot ANCV previo o fecha oficial de admisión/alta del ISIN |

## Combinaciones de bloqueos por fecha

| security(es) bloqueantes | fechas |
|---|---|
| MTS | 104 |
| FER, LOG, MTS, PUIG | 27 |
| ABG.P, MTS | 25 |
| FER, LOG, MTS | 19 |
| GRF, MTS | 6 |
| MTS, REE | 6 |
| MTS, PHM | 3 |
