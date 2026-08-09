from datetime import UTC, datetime
from pathlib import Path

import pytest

from market_structure_scraper.parser import (
    FINRA_URL,
    NASDAQ_LISTED_URL,
    parse_short_volume,
    parse_symbol_directory,
)

FIXTURES = Path(__file__).parents[1] / "src" / "market_structure_scraper" / "fixture_data"
NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


def test_symbol_directory_parser_skips_footer() -> None:
    text = (FIXTURES / "nasdaqlisted.txt").read_text(encoding="utf-8")
    records = parse_symbol_directory(text, NASDAQ_LISTED_URL, NOW, NOW)
    assert [record.symbol for record in records] == ["EXMPL", "OTHER"]
    assert records[0].round_lot_size == 100


def test_finra_parser_rejects_bad_numbers() -> None:
    malformed = (
        "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
        "20260114|EXMPL|not-a-number|0|100|Q\n"
    )
    with pytest.raises(ValueError, match="invalid row"):
        parse_short_volume(malformed, FINRA_URL.format(date="20260114"), NOW, NOW)

