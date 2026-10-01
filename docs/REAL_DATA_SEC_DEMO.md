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
