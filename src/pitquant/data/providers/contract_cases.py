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
        U,
        "https://investor.apple.com/faq/default.aspx",
        "IR FAQ: 'a 7-for-1 basis on June 9, 2014' confirms the ratio; it does not say "
        "whether June 9 is the ex-date (first split-adjusted session) — confirm.",
    ),
    ContractCase(
        "US-SPLIT-AAPL-2020",
        "US",
        Category.SPLIT,
        "AAPL",
        date(2020, 8, 3),
        {"ex_date": date(2020, 8, 31), "ratio": 4.0},
        U,
        "https://investor.apple.com/faq/default.aspx",
        "IR FAQ states 4-for-1 'on August 28, 2020' (distribution); first split-adjusted "
        "session believed to be 2020-08-31 — confirm the ex-date.",
    ),
    ContractCase(
        "US-REVSPLIT-C-2011",
        "US",
        Category.REVERSE_SPLIT,
        "C",
        date(2011, 5, 2),
        {"ex_date": date(2011, 5, 9), "ratio": 0.1},
        U,
        "",
        "1-for-10, split-adjusted trading from 2011-05-09 per Citigroup 8-K exhibit "
        "(seen only as a search excerpt; read the filing to verify). New CUSIP/ISIN: the "
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
        {"ex_date": date(2013, 1, 2), "ratio": 1.0},
        U,
        note="Abbott → AbbVie, 1 ABBV per ABT share; distribution 2013-01-01, regular-way "
        "ex-date believed 2013-01-02.",
    ),
    ContractCase(
        "US-SPECIALDIV-MSFT-2004",
        "US",
        Category.SPECIAL_DIVIDEND,
        "MSFT",
        date(2004, 11, 1),
        {"ex_date": date(2004, 11, 15), "amount": 3.00},
        U,
        note="One-time USD 3.00 special dividend (paid Dec-2004); confirm ex-date.",
    ),
    ContractCase(
        "US-CASHACQ-HNZ-2013",
        "US",
        Category.CASH_ACQUISITION,
        "HNZ",
        date(2013, 5, 1),
        {"delisted_on": date(2013, 6, 7), "cash_per_share": 72.50},
        U,
        note="H.J. Heinz acquired by Berkshire Hathaway / 3G for USD 72.50 cash per share.",
    ),
    ContractCase(
        "US-STOCKACQ-XTO-2010",
        "US",
        Category.STOCK_ACQUISITION,
        "XTO",
        date(2010, 6, 1),
        {"delisted_on": date(2010, 6, 25), "exchange_ratio": 0.7098},
        U,
        note="XTO Energy acquired by Exxon Mobil, 0.7098 XOM per XTO share (all stock).",
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
        note="Inditex 5-for-1 split, Jul-2014; confirm ex-date in the CNMV hecho relevante.",
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
)
