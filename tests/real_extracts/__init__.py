# ruff: noqa: E501
"""REAL_EXTRACT: rows copied from official/vendor sources archived locally (SHA-256 in each
constant). Facts only (dates, prices, amounts) — never whole pages. NOT synthetic; used as
regression ground truth for the corporate-action / total-return engine, never as research data."""

# Apple IR «Dividend History» (Wayback capture 20260422063456 of investor.apple.com/dividend-history/)
APPLE_SHA = "4f315669af2154373e8d48ee877d6b6d8a07974c9b25b4199cc9be2faa0471a3"
_APPLE_REAL = (
    "October 29, 2020 November 9, 2020 November 12, 2020 $0.205 Regular Cash "
    "July 30, 2020 August 24, 2020 August 31, 2020* N/A 4-for-1 Stock Split "
    "July 30, 2020 August 10, 2020 August 13, 2020 $.82 Regular Cash "
    "April 30, 2020 May 11, 2020 May 14, 2020 $.82 Regular Cash"
)

# Enagás IR «Dividends» table rows (sha of the captured page: ENAGAS_SHA)
ENAGAS_SHA = "b35e8141617fdf032d90485d8a5112e4d93cd02cfb774aef9fec87b326710c79"
ENAGAS_HTML = (
    "<table><tbody><tr><th>Payment date</th><th>Gross Payment\xa0(€/share)</th>"
    "<th>Net Payment\xa0(€/share)</th><th>Type</th><th>For</th><th>Ex dividend date</th></tr>"
    "<tr><td>22/12/2023</td><td>0.696</td><td>0.56376</td><td>Interim</td>"
    "<td>Fiscal year 2023</td><td>20/12/2023</td></tr>"
    "<tr><td>09/07/2020</td><td>0,960</td><td>0,7776</td><td>Complementary</td>"
    "<td>Fiscal year 2019</td><td>07/07/2020</td></tr>"
    "<tr><td>23/12/2020</td><td>0,672</td><td>0,54432</td><td>Interim</td>"
    "<td>Fiscal year 2020</td><td>21/12/2020</td></tr>"
    "<tr><td>02/07/2015</td><td>0,50</td><td>0,40</td><td>Complementary</td>"
    "<td>Fiscal year 2014</td><td>\xa0</td></tr></tbody></table>"
)

# Microsoft IR «Dividends and Stock History»
MSFT_SHA = "ec22b6934db311f782aaf28ae931f67a05df37f53de2fdf3cb0d4206c7016a6d"
MSFT_TEXT = (
    "Special Dividend Dividend Period Amount Announcement Date Ex-Dividend Date Record Date "
    "Payable Date Special $3.00 Jul 20, 2004 Nov 15, 2004 Nov 17, 2004 Dec 2, 2004 "
    "Stock Information"
)

# BME daily bulletin 2_38_0 (sections archived; ENG row of each session)
BME_ROWS = {
    "20231219": "MC ENG ENAGAS F 16,7500 18-12-23 16,8050 16,6350 16,6700 16,7002 1.272.013 21.259.289,50",
    "20231220": "MC ENG ENAGAS F 16,6700 19-12-23 16,0600 15,6450 15,6700 15,7964 1.530.511 24.176.503,23",
    "20240701": "MC ENG ENAGAS F 13,8900 28-06-24 14,2600 14,0400 14,1000 14,1255 1.807.656 25.536.139,12",
    "20240702": "MC ENG ENAGAS F 14,1000 01-07-24 13,1000 12,7700 12,7900 12,9187 2.742.659 35.432.068,74",
}

# EODHD public demo token, raw (unadjusted) closes — QA vendor, single source
AAPL_CLOSES = {  # 4-for-1 split effective 2020-08-31 (Apple IR)
    "2020-08-25": 499.30, "2020-08-26": 506.09, "2020-08-27": 500.04, "2020-08-28": 499.23,
    "2020-08-31": 129.04, "2020-09-01": 134.18, "2020-09-02": 131.40, "2020-09-03": 120.88,
    "2020-09-04": 120.96,
}  # fmt: skip
MSFT_CLOSES = {"2004-11-12": 29.97, "2004-11-15": 27.39}

APPLE_TEXT = (
    "Dividend History Dividend amounts not split adjusted. Declared Record Payable Amount Type "
    + _APPLE_REAL
    + " * Reflects first date shares trade on a split-adjusted basis."
)
