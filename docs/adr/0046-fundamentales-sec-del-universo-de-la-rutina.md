# ADR-0046 — Fundamentales SEC del universo de la rutina

Estado: aceptada (2026-10-05). Sin migración. Complementa ADR-0019/0020/0022/0045.

## Decisión
1. `pitquant fundamentals-universe` (`jobs/sec_universe.py`) ingiere de SEC EDGAR (fuente oficial, point-in-time por accession y `ACCEPTANCE-DATETIME`) los fundamentales de una lista de tickers de EE. UU. (por defecto 15 grandes no financieras del universo). El ticker→CIK sale del fichero oficial `company_tickers.json` de la SEC, archivado con su SHA-256: no se adivina ningún CIK.
2. **User-Agent de contacto:** se lee de `PITQUANT_SEC_USER_AGENT` (política de uso justo de la SEC) y nunca se guarda ni se archiva. Sin él no se hace ninguna petición.
3. **Identidad (ADR-0020):** los hechos pertenecen al EMISOR. El valor con precios de Yahoo (`securities.issuer_id`) se ENLAZA al emisor SEC (`LINKED`); nunca se reutiliza ni se sobrescribe un vínculo distinto (`CONFLICT_DIFFERENT_ISSUER`). Se añade un perfil SEC (sector SIC, tipo especial banco/seguro/REIT) al valor con precios.
4. Bancos, aseguradoras y planes de salud quedan fuera de la lista por defecto (su perfil fundamental especializado no está soportado).
5. Resultado inicial (2026-10-05): 15 emisores ingeridos, 14 con fundamentales utilizables. Limitaciones visibles: XOM tiene un CIK nuevo con 1 solo filing (cambio de registrante: necesita verificación de sucesión antes de enlazar el CIK anterior), y WMT, CVX y COST no normalizan aún el TTM de ingresos (conceptos XBRL sin mapear).
6. Defecto corregido: `latest_period` valía la CADENA «None» cuando no había ningún TTM calculable y el Analyzer fallaba; ahora es `None` y el valor se degrada con «Insufficient».
