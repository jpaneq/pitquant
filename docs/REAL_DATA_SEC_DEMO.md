# Demostración PIT con datos REALES de SEC EDGAR (MSFT, CIK 0000789019)

Generado el 2026-10-01 con `pitquant explain` sobre una base local, tras ingerir 126 filings de MSFT y AAPL (51.538 versiones de hechos) desde EDGAR, con headers e instancias XBRL archivados con su SHA-256.

Caso: beneficio neto de FY2016 (2015-07-01..2016-06-30). El 10-K de 2016 lo publicó como 16.798 M$; el 10-K de 2018 lo reexpresó a 20.539 M$.

`ticker then: unknown` es deliberado: el emisor se registró desde su CIK, sin ticker, porque los tickers sólo pueden venir de una fuente fechada (universo o D-05) y aún no hay ninguna.

## as_of 2016-07-28T16:00:00-04:00
```
NetIncomeLoss @ 2016-06-30 for b5996a6e-9873-4988-b0c9-1a9a4452660e (ticker then: unknown) as of 2016-07-28T20:00:00+00:00
KNOWN: nothing — no version was available at that instant.
NOT KNOWN: 16798000000.0 from 0001193125-16-662209 — available_after_as_of: available_at 2016-07-29T13:30:00+00:00 > as_of (accepted 2016-07-28T20:12:18+00:00)
NOT KNOWN: 16798000000.0 from 0001564590-17-014900 — available_after_as_of: available_at 2017-08-03T13:30:00+00:00 > as_of (accepted 2017-08-02T20:15:01+00:00)
NOT KNOWN: 20539000000.0 from 0001564590-18-019062 — available_after_as_of: available_at 2018-08-03T15:18:33+00:00 > as_of (accepted 2018-08-03T15:03:33+00:00)
```

## as_of 2018-08-03T11:15:00-04:00
```
NetIncomeLoss @ 2016-06-30 for b5996a6e-9873-4988-b0c9-1a9a4452660e (ticker then: unknown) as of 2018-08-03T15:15:00+00:00
KNOWN: 16798000000.0 USD (us-gaap:NetIncomeLoss 2015-07-01..2016-06-30, 2017FY)
  filing      10-K 0001564590-17-014900 filed 2017-08-02
  document    https://www.sec.gov/Archives/edgar/data/789019/000156459017014900/msft-10k_20170630.htm
  accepted_at 2017-08-02T20:15:01+00:00 (header)
  available   2017-08-03T13:30:00+00:00 (conservative_session)
  parser      sec-edgar-1  header sha256 155030c37cfb71ee5461f6cb1b05ba034df2513370802bd1c785b8da12aad8cf
  xbrl sha256 8ad519cb071368833b3dabd33c4cb3c92af2cc42b5dd71fab0c7a5a9212a1205
NOT KNOWN: 16798000000.0 from 0001193125-16-662209 — superseded_by:1169649a-5a99-49c5-9301-200e813014d9: a later version (0001564590-17-014900, available 2017-08-03T13:30:00+00:00) was also known at as_of
NOT KNOWN: 20539000000.0 from 0001564590-18-019062 — available_after_as_of: available_at 2018-08-03T15:18:33+00:00 > as_of (accepted 2018-08-03T15:03:33+00:00)
```

## as_of 2018-08-03T11:20:00-04:00
```
NetIncomeLoss @ 2016-06-30 for b5996a6e-9873-4988-b0c9-1a9a4452660e (ticker then: unknown) as of 2018-08-03T15:20:00+00:00
KNOWN: 20539000000.0 USD (us-gaap:NetIncomeLoss 2015-07-01..2016-06-30, 2018FY)
  filing      10-K 0001564590-18-019062 filed 2018-08-03
  document    https://www.sec.gov/Archives/edgar/data/789019/000156459018019062/msft-10k_20180630.htm
  accepted_at 2018-08-03T15:03:33+00:00 (header)
  available   2018-08-03T15:18:33+00:00 (conservative_session)
  parser      sec-edgar-1  header sha256 263cafcc1b312909ced9fe9183b8def23edfd8198b373a2117d819a979feeaac
  xbrl sha256 a6def703863717bcb3c0b95505492dd5dce9b2de0ee5b427522da7e5f23e9635
NOT KNOWN: 16798000000.0 from 0001193125-16-662209 — superseded_by:a8dedfba-6e3a-4d6f-a1be-f628396fd789: a later version (0001564590-18-019062, available 2018-08-03T15:18:33+00:00) was also known at as_of
NOT KNOWN: 16798000000.0 from 0001564590-17-014900 — superseded_by:a8dedfba-6e3a-4d6f-a1be-f628396fd789: a later version (0001564590-18-019062, available 2018-08-03T15:18:33+00:00) was also known at as_of
```

## Enmienda real: MSFT 10-Q/A 0001193125-12-026864 (Q2 FY2012)

El 10-Q original (0001193125-12-017029, presentado el 2012-01-19) no lo cita ningún valor de companyfacts: este atribuye los hechos a la enmienda. Por eso el sistema sólo los conoce desde la enmienda, aceptada el viernes 2012-01-27 a las 15:04 ET. No hay fuga: se conocen más tarde, no antes.

**Actualización (recuperación desde la instancia):** la ingestión ya no depende de companyfacts para saber qué filings existen. Al intentar recuperar el 10-Q original desde su propia instancia XBRL se comprobó que **no tenía XBRL**: su directorio sólo contiene HTML. Microsoft presentó el 10-Q/A el 2012-01-27 para aportar el anexo XBRL. El filing queda registrado con su header (aceptado el 2012-01-19 16:09 ET) y marcado `filing_not_cited_by_companyfacts` + `xbrl_instance_missing`: sus cifras no eran legibles por máquina hasta la enmienda.

### as_of 2012-01-26T16:00:00-05:00
```
SalesRevenueNet @ 2011-12-31 for b5996a6e-9873-4988-b0c9-1a9a4452660e (ticker then: unknown) as of 2012-01-26T21:00:00+00:00
KNOWN: nothing — no version was available at that instant.
NOT KNOWN: 20885000000.0 from 0001193125-12-026864 — available_after_as_of: available_at 2012-01-27T20:19:25+00:00 > as_of (accepted 2012-01-27T20:04:25+00:00)
NOT KNOWN: 20885000000.0 from 0001193125-12-316848 — available_after_as_of: available_at 2012-07-27T13:30:00+00:00 > as_of (accepted 2012-07-26T20:12:48+00:00)
NOT KNOWN: 20885000000.0 from 0001193125-13-022207 — available_after_as_of: available_at 2013-01-25T14:30:00+00:00 > as_of (accepted 2013-01-24T21:10:59+00:00)
NOT KNOWN: 20885000000.0 from 0001193125-13-310206 — available_after_as_of: available_at 2013-07-31T13:30:00+00:00 > as_of (accepted 2013-07-30T20:14:49+00:00)
```

### as_of 2012-01-27T15:30:00-05:00
```
SalesRevenueNet @ 2011-12-31 for b5996a6e-9873-4988-b0c9-1a9a4452660e (ticker then: unknown) as of 2012-01-27T20:30:00+00:00
KNOWN: 20885000000.0 USD (us-gaap:SalesRevenueNet 2011-10-01..2011-12-31, 2012Q2)
  filing      10-Q/A 0001193125-12-026864 filed 2012-01-27 (amendment)
  document    https://www.sec.gov/Archives/edgar/data/789019/000119312512026864/d266753d10qa.htm
  accepted_at 2012-01-27T20:04:25+00:00 (header)
  available   2012-01-27T20:19:25+00:00 (conservative_session)
  parser      sec-edgar-1  header sha256 bf802702babdca992fc80f455061603603570a9c721e30d4b9d32afd72379acd
  xbrl sha256 8ba9ee847bec0ac77bc561da7394b8cd30a731c037c15289cc3ca45d0ba618b9
NOT KNOWN: 20885000000.0 from 0001193125-12-316848 — available_after_as_of: available_at 2012-07-27T13:30:00+00:00 > as_of (accepted 2012-07-26T20:12:48+00:00)
NOT KNOWN: 20885000000.0 from 0001193125-13-022207 — available_after_as_of: available_at 2013-01-25T14:30:00+00:00 > as_of (accepted 2013-01-24T21:10:59+00:00)
NOT KNOWN: 20885000000.0 from 0001193125-13-310206 — available_after_as_of: available_at 2013-07-31T13:30:00+00:00 > as_of (accepted 2013-07-30T20:14:49+00:00)
```

## «¿Por qué NO se conocía?» con datos reales: valor rechazado (AAPL)

companyfacts da 0.0 como valor nominal por acción. La instancia XBRL del propio 10-Q dice 1e-05. El valor de companyfacts se rechaza y nunca se almacena; la incidencia de calidad es su rastro.
```
CommonStockParOrStatedValuePerShare @ 2014-03-29 for dd082daa-fdce-41c4-90b9-9593a7b7a98c (ticker then: unknown) as of 2014-12-31T21:00:00+00:00
KNOWN: 1e-05 USD/shares (us-gaap:CommonStockParOrStatedValuePerShare ..2014-03-29, 2014FY)
  filing      10-K 0001193125-14-383437 filed 2014-10-27
  document    https://www.sec.gov/Archives/edgar/data/320193/000119312514383437/d783162d10k.htm
  accepted_at 2014-10-27T21:11:55+00:00 (header)
  available   2014-10-28T13:30:00+00:00 (conservative_session)
  parser      sec-edgar-1  header sha256 9012e5a00e197d68e151d1fa1e713ab89636f7ca0a4a53be5093f2f612350e13
  xbrl sha256 3f425ef38234796a8961f454db3818d7052f0a43fae27cf1675951f816703ac4
NOT KNOWN: 1e-05 from 0001193125-14-277160 — superseded_by:af430688-2889-469a-bac9-5c322c437d6f: a later version (0001193125-14-383437, available 2014-10-28T13:30:00+00:00) was also known at as_of
NOT KNOWN: value never stored — rejected:companyfacts_xbrl_mismatch:fb6675c4-a391-4c02-b80b-daf4c0aace09: 0001193125-14-157311 CommonStockParOrStatedValuePerShare None..2014-03-29: companyfacts 0.0 != instance 1e-05
```
