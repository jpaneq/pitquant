# Demostración PIT con datos REALES de la CNMV (Enagás, CIF A-28294726)

Generado con `scripts/gen_real_demos.py`. Fuentes: 5 informes semestrales oficiales (2017S1–2019S1); cada ficha y cada XBRL IPP están archivados con SHA-256. Taxonomía en la clave (`ipp_ge@2016-06-01`): sólo se comparan versiones dentro de la misma taxonomía.

Concepto `I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos]` a 30-06-2017. El informe 2017S1 (publicado el 18-07-2017 y modificado el 27-07-2017) se usa desde la apertura del 28-07 (DATE_ONLY, *fail closed*). El informe 2018S1 da otro valor en su columna comparativa: es una versión posterior y no reescribe la anterior. La CNMV no indica hora: nunca se inventa.

## as_of 2017-07-27T17:30:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for ce79cc0a-00dd-4bcb-a653-9909fe94aa72 (ticker then: ENG) as of 2017-07-27T15:30:00+00:00
  identity    ISIN on that day: ES0130960018 (proven 2010-06-30..open)
  identity    issuer ENAGAS, S.A. (CIF A-28294726 [CNMV IFI page (NIF field)])
KNOWN: nothing — no version was available at that instant.
NOT KNOWN: 688034000.0 from CNMV nreg 2017082262 — available_after_as_of: available_at 2017-07-28T07:00:00+00:00 > as_of (accepted -)
NOT KNOWN: 682573000.0 from CNMV nreg 2018085463 — available_after_as_of: available_at 2018-07-18T07:00:00+00:00 > as_of (accepted -)
```

## as_of 2018-07-17T17:30:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for ce79cc0a-00dd-4bcb-a653-9909fe94aa72 (ticker then: ENG) as of 2018-07-17T15:30:00+00:00
  identity    ISIN on that day: ES0130960018 (proven 2010-06-30..open)
  identity    issuer ENAGAS, S.A. (CIF A-28294726 [CNMV IFI page (NIF field)])
KNOWN: 688034000.0 EUR (ipp_ge@2016-06-01:I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] ..2017-06-30, 2017 S1)
  filing      IFI_IPP 2017 S1 (published 2017-07-18, modified 2017-07-27, DATE_ONLY) CNMV nreg 2017082262 filed 2017-07-18 (amendment)
  document    https://www.cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2017082262
  accepted_at - (header)
  available   2017-07-28T07:00:00+00:00 (DATE_ONLY: next XMAD open after end of latest(publication, modifications))
  parser      cnmv-ipp-3  header sha256 cfc674b5d01075d4b2c1c842db9cda14f030daae7466c2de9b98192a2b7d2068
  xbrl sha256 c87ea2b3558d001907397742541fceb3604b95f1a85bc430cfcf1603df3bf77a
NOT KNOWN: 682573000.0 from CNMV nreg 2018085463 — available_after_as_of: available_at 2018-07-18T07:00:00+00:00 > as_of (accepted -)
```

## as_of 2018-07-18T09:00:00+02:00
```
I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] @ 2017-06-30 for ce79cc0a-00dd-4bcb-a653-9909fe94aa72 (ticker then: ENG) as of 2018-07-18T07:00:00+00:00
  identity    ISIN on that day: ES0130960018 (proven 2010-06-30..open)
  identity    issuer ENAGAS, S.A. (CIF A-28294726 [CNMV IFI page (NIF field)])
KNOWN: 682573000.0 EUR (ipp_ge@2016-06-01:I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos] ..2017-06-30, 2018 S1)
  filing      IFI_IPP 2018 S1 (published 2018-07-17, DATE_ONLY) CNMV nreg 2018085463 filed 2018-07-17
  document    https://www.cnmv.es/Portal/AlDia/DetalleIFIAlDia?nreg=2018085463
  accepted_at - (header)
  available   2018-07-18T07:00:00+00:00 (DATE_ONLY: next XMAD open after end of publication date)
  parser      cnmv-ipp-3  header sha256 eee463890aa0480936d91f84d52949dd7732accad4046fb00f42ff829e6be015
  xbrl sha256 734fcffab760dc70db541b1c21850e0e0bdb63b1f97a6925ba2417f6af5326f3
NOT KNOWN: 688034000.0 from CNMV nreg 2017082262 — superseded_by:6ea831dc-5f94-4284-add0-30bf85e73f35: a later version (CNMV nreg 2018085463, available 2018-07-18T07:00:00+00:00) was also known at as_of
```
