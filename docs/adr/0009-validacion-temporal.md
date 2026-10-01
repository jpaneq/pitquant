# ADR-0009 — Validación: walk-forward purgado con embargo y label availability

**Estado:** aceptada · **Fecha:** 2026-10-01

## Decisión
`PurgedWalkForward` genera folds temporales y aplica, en este orden:
1. **Partición temporal** por `t_exec` (expanding por defecto; rolling opcional). Nunca shuffle.
2. **Label availability**: se descarta del train toda observación con
   `label_available_at > train_cutoff` (el instante en que se "entrena" el fold = inicio de validación).
3. **Purging**: se descarta del train toda observación cuyo intervalo
   `[t_exec, label_end]` se solape con el intervalo envolvente de validación+test.
4. **Embargo**: se descartan observaciones cuyo `t_exec` caiga en
   `(fin_test, fin_test + embargo]` (relevante en CV combinatoria; en walk-forward puro el
   embargo actúa también antes del bloque de validación).
5. Validación de invariantes: ningún índice compartido entre particiones; `max(train.label_available_at) ≤ train_cutoff`.

El `HoldoutGuard` mantiene un periodo final inaccesible: cualquier fold que lo toque lanza
`HoldoutAccessError`, salvo `unlock(model_version, reason)` con modelo congelado, que
queda registrado en `holdout_access_log` y es irreversible.

## Referencias
López de Prado (2018), *Advances in Financial Machine Learning*, cap. 7 y 11–12.
