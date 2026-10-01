# ADR-0002 — Identificador interno `security_id` (no ticker)

**Estado:** aceptada · **Fecha:** 2026-10-01

## Contexto
Los tickers cambian (FB→META) y se reutilizan (p. ej. un símbolo liberado tras un
deslisting puede asignarse a otra empresa años después). ISIN cambia en fusiones y
redomiciliaciones.

## Decisión
- `security_id`: UUID v4 en texto, inmutable, asignado por el Security Master.
- `ticker_history(security_id, ticker, exchange, valid_from, valid_to)` con intervalos
  semiabiertos y **sin solapamiento** por `(ticker, exchange)`.
- `identifier_history` análoga para ISIN / CUSIP / FIGI.
- `resolve(ticker, exchange, as_of)` devuelve la emisión que tenía ese ticker en esa fecha;
  si hay ambigüedad, lanza `AmbiguousIdentifierError` (fail loudly).
- Granularidad: **emisión cotizada** (share class), no compañía. Una tabla `issuers` agrupa clases.

## Consecuencias
+ Inmune a reutilización de tickers. − Todo input de usuario requiere resolución con fecha.
