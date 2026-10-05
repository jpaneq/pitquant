# Under Armour Class C — official evidence matrix

Candidate index date **2016-04-08 remains UNCONFIRMED_NOT_REJECTED**. First blocked monthly decision: **2016-09**.

| SOURCE | OFFICIAL? | CONTEMPORANEOUS? | DIRECTLY_PROVES_INDEX_MEMBERSHIP? | DATE_EXPLICIT? | ARCHIVED? | HASHABLE? | ACCEPTABLE_UNDER_CURRENT_CONTRACT? |
|---|---|---|---|---|---|---|---|
| [OCC notice 38727 hosted by MIAX](https://www.miaxglobal.com/sites/default/files/alert-files/UA_Distribution__38727.pdf) | True | True | False | True | True | True | False |
| [SEC preliminary proxy 0001193125-15-223346](https://www.sec.gov/Archives/edgar/data/1336917/000119312515223346/d931136dpre14a.htm) | True | False | False | True | True | True | False |
| [SEC 2016 10-K](https://www.sec.gov/Archives/edgar/data/1336917/000133691717000017/ua-20161231x10k.htm) | True | False | False | True | True | True | False |

Explicit dates above concern corporate actions, issuer expectations and ticker history, **not an index effective date**. Originals, retrieval times, archive IDs, hashes, paths and resolver versions are in the companion JSON.

OCC notice 38727 is dated April 7, 2016: it identifies Class A CUSIP 904311107 and Class C 904311206; payable April 7, ex-distribution and futures adjustment April 8, when-issued UA.C WI trading March 23. The SEC 10-K confirms regular-way UA.C listing April 8 and ticker transitions December 7. The 2015 preliminary proxy is prospective, not contemporaneous evidence of the completed April 2016 index event; it expressly leaves index inclusion to S&P discretion.

The combination is insufficient: two classes, a stock distribution, listing and issuer expectation do not establish the date S&P included Class C. Official index notices/history are permissible under the current contract; a literal S&P press release is not the only allowed format. No methodology is relaxed.

Minimum missing proof: a dated official S&P DJI notice or constituent history explicitly linking **Under Armour Class C** to the index and stating its effective addition date. Archive and hash it, replay 2016-03..2016-09, then advance toward older critical months.

Class-specific aliases can be replayed offline with `scripts/apply_under_armour_ticker_evidence.py` and the explicit project DB. Class A UA has an unknown start, retained PARTIAL, and a verified end of December 6. UA.C runs April 8..December 6; Class A UAA and Class C UA start December 7. No class succession or membership event is created.
