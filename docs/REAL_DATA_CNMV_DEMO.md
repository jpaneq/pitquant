# Demostración PIT con datos REALES de la CNMV (Enagás, CIF A-28294726)

Generado con `scripts/gen_real_demos.py`. Fuentes: 5 informes semestrales oficiales (2017S1–2019S1); cada ficha y cada XBRL IPP están archivados con SHA-256. Taxonomía en la clave (`ipp_ge@2016-06-01`): sólo se comparan versiones dentro de la misma taxonomía.

Concepto `I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos]` a 30-06-2017. El informe 2017S1 (publicado el 18-07-2017 y modificado el 27-07-2017) se usa desde la apertura del 28-07 (DATE_ONLY, *fail closed*). El informe 2018S1 da otro valor en su columna comparativa: es una versión posterior y no reescribe la anterior. La CNMV no indica hora: nunca se inventa.

## as_of 2017-07-27T17:30:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for 24de0193-b883-4f3b-8400-79c2e0d63c2f (ticker then: unknown) as of 2017-07-27T15:30:00+00:00
KNOWN: nothing — no version was available at that instant.
NOT KNOWN: 688034000.0 from CNMV nreg 2017082262 — available_after_as_of: available_at 2017-07-28T07:00:00+00:00 > as_of (accepted -)
NOT KNOWN: 682573000.0 from CNMV nreg 2018085463 — available_after_as_of: available_at 2018-07-18T07:00:00+00:00 > as_of (accepted -)
```

## as_of 2018-07-17T17:30:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for 24de0193-b883-4f3b-8400-79c2e0d63c2f (ticker then: unknown) as of 2018-07-17T15:30:00+00:00
KNOWN: 688034000.0 EUR (ipp_ge@2016-06-01:I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] ..2017-06-30, 2017 S1)
  filing      IFI_IPP 2017 S1 (published 2017-07-18, modified 2017-07-27, DATE_ONLY) CNMV nreg 2017082262 filed 2017-07-18 (amendment)
  document    https://www.cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2017082262
  accepted_at - (header)
  available   2017-07-28T07:00:00+00:00 (DATE_ONLY: next XMAD open after end of latest(publication, modifications))
  parser      cnmv-ipp-3  header sha256 d5c2c14624f0f8f13e0e098898ef842cba67d7d6e51be07b56d0fd0db638c4c4
  xbrl sha256 c87ea2b3558d001907397742541fceb3604b95f1a85bc430cfcf1603df3bf77a
NOT KNOWN: 682573000.0 from CNMV nreg 2018085463 — available_after_as_of: available_at 2018-07-18T07:00:00+00:00 > as_of (accepted -)
```

## as_of 2018-07-18T09:00:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for 24de0193-b883-4f3b-8400-79c2e0d63c2f (ticker then: unknown) as of 2018-07-18T07:00:00+00:00
KNOWN: 682573000.0 EUR (ipp_ge@2016-06-01:I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] ..2017-06-30, 2018 S1)
  filing      IFI_IPP 2018 S1 (published 2018-07-17, DATE_ONLY) CNMV nreg 2018085463 filed 2018-07-17
  document    https://www.cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2018085463
  accepted_at - (header)
  available   2018-07-18T07:00:00+00:00 (DATE_ONLY: next XMAD open after end of publication date)
  parser      cnmv-ipp-3  header sha256 6719024f5e777cb3415fb8bc51c7d0ed5d48e5e981e29115efa54d420bef6d6d
  xbrl sha256 734fcffab760dc70db541b1c21850e0e0bdb63b1f97a6925ba2417f6af5326f3
NOT KNOWN: 688034000.0 from CNMV nreg 2017082262 — superseded_by:0a8d2784-8f33-4e75-952f-8ca3c1dd608d: a later version (CNMV nreg 2018085463, available 2018-07-18T07:00:00+00:00) was also known at as_of
```
