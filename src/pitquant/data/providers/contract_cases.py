"""Known historical events every D-05 candidate must reproduce.

VERIFIED cases cite the official document read to confirm every value in ``expect``.
UNVERIFIED cases were written from general knowledge: their values are expectations to be
CONFIRMED against an official source (issuer IR, SEC filing, CNMV/BME notice) before a
provider can be accepted on them. Never promote a case to VERIFIED without reading the
source; never "fix" an expectation to match what a provider returns.
"""

from __future__ import annotations

from datetime import date

from pitquant.data.providers.contract import Category, ContractCase, Verification

V, U = Verification.VERIFIED, Verification.UNVERIFIED

CASES: tuple[ContractCase, ...] = (
    # ── United States ─────────────────────────────────────────────────────────
    ContractCase(
        "US-SPLIT-AAPL-2014",
        "US",
        Category.SPLIT,
        "AAPL",
        date(2014, 6, 2),
        {"ex_date": date(2014, 6, 9), "ratio": 7.0},
        V,
        "https://www.sec.gov/Archives/edgar/data/320193/000119312514154883/d715379dex991.htm",
        "Apple 8-K ex.99.1 (2014-04-23): seven-for-one split, shares to begin trading on a "
        "'split-adjusted basis on June 9, 2014'.",
    ),
    ContractCase(
        "US-SPLIT-AAPL-2020",
        "US",
        Category.SPLIT,
        "AAPL",
        date(2020, 8, 3),
        {"ex_date": date(2020, 8, 31), "ratio": 4.0},
        V,
        "https://www.sec.gov/Archives/edgar/data/320193/000032019320000060/a8-kexhibit991q3202062.htm",
        "Apple 8-K ex.99.1 (2020-07-30): four-for-one split, trading on a 'split-adjusted "
        "basis on August 31, 2020'.",
    ),
    ContractCase(
        "US-REVSPLIT-C-2011",
        "US",
        Category.REVERSE_SPLIT,
        "C",
        date(2011, 5, 2),
        {"ex_date": date(2011, 5, 9), "ratio": 0.1},
        V,
        "https://www.sec.gov/Archives/edgar/data/831001/000119312511131957/dex991.htm",
        "Citigroup 8-K ex.99.1 dated May 9, 2011: 1-for-10 reverse split effective 4:10 p.m. "
        "Friday May 6; 'C' begins split-adjusted trading on NYSE today. New CUSIP/ISIN: the "
        "provider must keep the same security identity across the reverse split.",
    ),
    ContractCase(
        "US-TICKER-FB-META-2022",
        "US",
        Category.TICKER_CHANGE,
        "FB",
        date(2022, 6, 1),
        {"new_symbol": "META", "change_date": date(2022, 6, 9)},
        V,
        "https://investor.atmeta.com/investor-news/press-release-details/2022/"
        "Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx",
        "'will begin trading on NASDAQ under the ticker symbol META prior to market open "
        "on June 9, 2022'.",
    ),
    ContractCase(
        "US-SPINOFF-ABT-ABBV-2013",
        "US",
        Category.SPIN_OFF,
        "ABT",
        date(2012, 12, 3),
        {"ex_date": date(2013, 1, 1), "ratio": 1.0},
        V,
        "https://www.sec.gov/Archives/edgar/data/1800/000104746913000015/a2212294zex-99_1.htm",
        "Abbott 8-K ex.99.1 (2013-01-02): 'For every 1 share of Abbott ... received 1 share of "
        "AbbVie common stock on Jan. 1, 2013' (expectation = stated distribution date).",
    ),
    ContractCase(
        "US-SPECIALDIV-MSFT-2004",
        "US",
        Category.SPECIAL_DIVIDEND,
        "MSFT",
        date(2004, 11, 1),
        {"ex_date": date(2004, 11, 15), "amount": 3.00},
        V,
        "https://www.sec.gov/Archives/edgar/data/789019/000119312504197513/d8k.htm",
        "Microsoft 8-K (2004-11-15): $3.00 special dividend; 'November 15, 2004, the "
        "ex-dividend date for the special dividend'.",
    ),
    ContractCase(
        "US-CASHACQ-HNZ-2013",
        "US",
        Category.CASH_ACQUISITION,
        "HNZ",
        date(2013, 5, 1),
        {"delisted_on": date(2013, 6, 7), "cash_per_share": 72.50},
        V,
        "https://www.sec.gov/Archives/edgar/data/46640/000119312513258009/d555504dex991.htm",
        "Heinz 8-K ex.99.1: '$72.50 in cash for each share'; 'no further trading after the "
        "close of business on June 7, 2013'.",
    ),
    ContractCase(
        "US-STOCKACQ-XTO-2010",
        "US",
        Category.STOCK_ACQUISITION,
        "XTO",
        date(2010, 6, 1),
        {"delisted_on": date(2010, 6, 25), "exchange_ratio": 0.7098},
        V,
        "https://www.sec.gov/Archives/edgar/data/868809/000095010310001867/dp18265_8k.htm",
        "XTO 8-K (2010-06-25): each share converted into '0.7098 of a share of ExxonMobil "
        "common stock'; merger consummated and NYSE notified on June 25, 2010.",
    ),
    ContractCase(
        "US-BANKRUPTCY-LEH-2008",
        "US",
        Category.BANKRUPTCY,
        "LEH",
        date(2008, 9, 2),
        {"delisted_on": date(2008, 9, 17)},
        U,
        tolerance_days=10,
        note="Lehman Brothers Chapter 11 filed 2008-09-15; NYSE delisting date to confirm. "
        "Provider must keep LEH and give a terminal value / delisting return.",
    ),
    ContractCase(
        "US-ORDDIV-AAPL-2020",
        "US",
        Category.ORDINARY_DIVIDEND,
        "AAPL",
        date(2020, 8, 3),
        {"ex_date": date(2020, 8, 10), "amount": 0.82},
        V,
        "https://www.sec.gov/Archives/edgar/data/320193/000032019320000060/a8-kexhibit991q3202062.htm",
        "Apple 8-K ex.99.1 (2020-07-30): $0.82 cash dividend (pre-split), record date "
        "2020-08-10; expectation uses the stated record date (ex-date within tolerance).",
    ),
    ContractCase(
        "US-EXCHMOVE-PEP-2017",
        "US",
        Category.EXCHANGE_MOVE,
        "PEP",
        date(2017, 12, 1),
        {"move_date": date(2017, 12, 20)},
        V,
        "https://www.sec.gov/Archives/edgar/data/77476/000095010317012290/dp83934_8k.htm",
        "PepsiCo 8-K (2017-12-08): NYSE listing ends at close 2017-12-19, trading begins on "
        "Nasdaq at open 2017-12-20 under 'PEP' (identity must be continuous).",
    ),
    # ── Spain ────────────────────────────────────────────────────────────────
    ContractCase(
        "ES-RESOLUTION-POP-2017",
        "ES",
        Category.BANKRUPTCY,
        "POP",
        date(2017, 6, 1),
        {"delisted_on": date(2017, 6, 7)},
        U,
        note="Banco Popular resolved (SRB/FROB) on 2017-06-07, shares written off, sold to "
        "Santander for EUR 1: terminal value 0. Confirm against CNMV/FROB documents.",
    ),
    ContractCase(
        "ES-RIGHTS-SAN-2017",
        "ES",
        Category.RIGHTS_ISSUE,
        "SAN",
        date(2017, 7, 3),
        {"ex_date": date(2017, 7, 7)},
        U,
        tolerance_days=10,
        note="Santander capital increase with pre-emptive rights after acquiring Popular "
        "(Jul-2017). Ratio, subscription price and ex-date to be taken from the CNMV "
        "prospectus before adding them to expect.",
    ),
    ContractCase(
        "ES-SPLIT-ITX-2014",
        "ES",
        Category.SPLIT,
        "ITX",
        date(2014, 7, 1),
        {"ex_date": date(2014, 7, 15), "ratio": 5.0},
        U,
        tolerance_days=10,
        note="Ratio 5x1 confirmed by the CNMV hecho relevante (cnmv.es VerDocumento, archived); "
        "it does NOT state the ex-date, so the case stays UNVERIFIED.",
    ),
    ContractCase(
        "ES-TICKER-GAS-NTGY-2018",
        "ES",
        Category.TICKER_CHANGE,
        "GAS",
        date(2018, 6, 1),
        {"new_symbol": "NTGY", "change_date": date(2018, 6, 29)},
        U,
        tolerance_days=10,
        note="Gas Natural Fenosa → Naturgy (GAS → NTGY) in 2018; date to confirm with the "
        "BME aviso (the IBEX fixtures use this pair with illustrative dates).",
    ),
    ContractCase(
        "ES-SCRIP-IBE",
        "ES",
        Category.SCRIP_DIVIDEND,
        "IBE",
        date(2018, 1, 2),
        {"ex_date": date(2018, 1, 10)},
        U,
        tolerance_days=40,
        note="Iberdrola 'Retribución Flexible' scrip programme: pick ONE documented edition "
        "from CNMV and fix its ex-date before use; the date here is a placeholder.",
    ),
    ContractCase(
        "ES-BONUS-ACS",
        "ES",
        Category.BONUS_ISSUE,
        "ACS",
        date(2019, 1, 2),
        {"ex_date": date(2019, 2, 5)},
        U,
        tolerance_days=40,
        note="Ampliación liberada (scrip) — pick one documented ACS edition in CNMV; "
        "placeholder date.",
    ),
    ContractCase(
        "ES-CAPINC-SAN-2017",
        "ES",
        Category.CAPITAL_INCREASE,
        "SAN",
        date(2017, 7, 3),
        {"ex_date": date(2017, 7, 7)},
        U,
        tolerance_days=10,
        note="Same Santander 2017 increase seen as a capital increase; confirm in the CNMV "
        "prospectus.",
    ),
    ContractCase(
        "ES-TENDER-ABE-2018",
        "ES",
        Category.TENDER_OFFER_DELISTING,
        "ABE",
        date(2018, 5, 2),
        {"delisted_on": date(2018, 8, 6)},
        U,
        tolerance_days=40,
        note="Abertis: OPA (Atlantia/ACS/Hochtief) followed by exclusion; IBEX row 109 "
        "excluded ABE on 2018-05-09. Stock-exchange delisting date to confirm in CNMV.",
    ),
    ContractCase(
        "ES-MERGER-BKIA-2021",
        "ES",
        Category.MERGER,
        "BKIA",
        date(2021, 3, 1),
        {"delisted_on": date(2021, 3, 26), "exchange_ratio": 0.6845},
        V,
        "https://www.caixabank.com/deployedfiles/caixabank_com/Estaticos/PDFs/"
        "Accionistasinversores/Informacion_General/"
        "20210319_Algarve-Anuncio-de-canje_con-firmas_v-final_limpia.pdf",
        "CaixaBank exchange announcement (2021-03-19): 0,6845 new CaixaBank shares per Bankia "
        "share; the exchange date is Bankia's last trading day, 26 March 2021.",
        tolerance_days=10,
    ),
)
