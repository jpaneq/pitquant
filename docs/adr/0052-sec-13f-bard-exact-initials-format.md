# ADR-0052 — Formato exacto de iniciales C.R. Bard en 13F

Accepted 2026-10-05. Versión `sec13f-legal-name-format-v2`.

El N-30D de 2017-09-30 contiene `C.R. Bard, Inc.`. La lista oficial SEC del mismo trimestre contiene `BARD C R INC`, descripción `COM`, CUSIP `067383109`. Se acepta exclusivamente la expansión exacta `BARD C R INC` → `C R BARD INC`; puntuación y sufijos se normalizan mediante la regla existente. No se reordenan nombres arbitrarios, no hay similitud difusa y no se modifica el control de clase o unicidad del trimestre.

Archivo oficial: https://www.sec.gov/divisions/investment/13f/13flist2017q3.pdf · SHA256 `7fa1277cb4e8b2029f76a089a6548aff830e61f45a86cd538836ebee9fae721c`, verificado contra el original archivado. 2017Q4: https://www.sec.gov/divisions/investment/13f/13flist2017q4.pdf · SHA256 `dad016bea5d30e413fec9262f3e825585002c03fac0aecc257832388343e5b7c`, también verificado; la marca DELETED no se utiliza para inferir una fecha de salida.

Se añade evidencia oficial CUSIP mediante la tabla existente SecurityIdentifierEvidence, observada al cierre de 2017Q3. No se crea security ni evento corporativo. La fecha de ingesta es actual; no se afirma que el sistema lo archivara en 2017. Las pruebas rechazan BARD C B INC y BARD C R INC CLASS B.
