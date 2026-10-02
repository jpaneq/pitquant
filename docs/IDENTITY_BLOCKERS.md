# Bloqueos de identidad por security (generado)

Generado con `scripts/gen_identity_reports.py` desde el run `abf041cd-47d5-459b-8e71-82cc5660b632`. Fechas candidatas: primer día hábil de cada mes entre 2011-01-01 y 2026-10-01 (190). `backtest_universe` falla cerrado si UN miembro no tiene identidad probada; este informe no relaja nada, sólo registra qué security bloquea qué fechas. Entrada de trabajo de la siguiente iteración.

Fechas backtestables: **190/190**.

| security | blocked_dates | first_blocked_date | last_blocked_date | reason | missing_evidence |
|---|---|---|---|---|---|

## Combinaciones de bloqueos por fecha

| security(es) bloqueantes | fechas |
|---|---|

## Evolución frente a la línea base (8d2993e)

Los conteos por security se solapan: una misma fecha podía estar bloqueada por varias.

Fechas elegibles: **0/190 → 190/190**.

| security | blocked_dates_before | blocked_dates_after | newly_eligible_dates | dates_unlocked_if_resolved_alone_now | evidence_status |
|---|---|---|---|---|---|
| MTS | 190 | 0 | 190 | 0 | RESOLVED: 94 official code<->ISIN statements stored |
| FER | 46 | 0 | 46 | 0 | RESOLVED: 97 official code<->ISIN statements stored |
| LOG | 46 | 0 | 46 | 0 | RESOLVED: 80 official code<->ISIN statements stored |
| PUIG | 27 | 0 | 27 | 0 | RESOLVED: 29 official code<->ISIN statements stored |
| ABG.P | 25 | 0 | 25 | 0 | RESOLVED: 30 official code<->ISIN statements stored |
| GRF | 6 | 0 | 6 | 0 | RESOLVED: 90 official code<->ISIN statements stored |
| REE | 6 | 0 | 6 | 0 | RESOLVED: 40 official code<->ISIN statements stored |
| PHM | 3 | 0 | 3 | 0 | RESOLVED: 76 official code<->ISIN statements stored |
