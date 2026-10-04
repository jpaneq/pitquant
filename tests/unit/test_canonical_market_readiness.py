"""Canonical provider policy does not replace per-series QA or exact identity evidence."""

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.market.canonical import source_status
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider
from pitquant.research.membership_bridge import legal_name_key
from pitquant.universe.document_aliases import PPG_ACCESSION, PPG_RAW, PPG_RESOLVED, document_name
from tests.unit.test_yahoo_provider import NOW, body, row


@pytest.mark.parametrize(
    "name,synthetic,expected",
    [
        ("YAHOO_CHART:eod", False, "YAHOO_CANONICAL"),
        ("YAHOO_CHART:eod", True, "SYNTHETIC_EXCLUDED"),
        ("EODHD:eod", False, "LEGACY_EXCLUDED"),
        ("unknown", False, "UNKNOWN_SOURCE_BLOCKED"),
    ],
)
def test_canonical_source_contract(name, synthetic, expected):
    assert source_status(name, synthetic) == expected


def test_approved_typo_is_exact_and_document_specific():
    assert document_name(PPG_RAW, PPG_ACCESSION) == PPG_RESOLVED
    assert document_name("PPoG Industries Inc.", PPG_ACCESSION) == "PPoG Industries Inc."
    assert document_name(PPG_RAW, "other") == PPG_RAW
    assert document_name("PPOG Industries, Inc.", PPG_ACCESSION) == "PPOG Industries, Inc."


def test_exact_sec_formatting_keeps_class_identity():
    assert legal_name_key("COSTCO WHOLESALE CORP /NEW") == legal_name_key("Costco Wholesale Corp")
    assert legal_name_key("MCDONALDS CORP") == legal_name_key("McDonald’s Corp")
    assert legal_name_key("LOWES COMPANIES INC") == legal_name_key("Lowe’s Companies Inc")
    assert legal_name_key("WELLS FARGO & COMPANY/MN") == legal_name_key("Wells Fargo & Co")
    assert legal_name_key("Alphabet Class A") != legal_name_key("Alphabet Class C")


@pytest.mark.parametrize(
    "rows",
    [
        [row(27, 100), row(27, 100)],
        [row(28, 100), row(27, 100)],
        [(100, 90, 99, 100, 10, row(27, 100)[5])],
        [row(27, -1)],
    ],
)
def test_yahoo_rejects_duplicate_chronology_and_impossible_ohlc(rows):
    with pytest.raises(DataQualityError):
        YahooChartMarketDataProvider().normalize("S", "TST", body(rows), NOW)


def test_yahoo_requires_symbol_and_currency_metadata():
    with pytest.raises(DataQualityError, match="metadata"):
        YahooChartMarketDataProvider().normalize("S", "OTHER", body([row(27, 100)]), NOW)
