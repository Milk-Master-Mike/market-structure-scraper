from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable
from datetime import date, datetime

from . import PARSER_VERSION
from .models import (
    ComparisonFact,
    Conflict,
    ListingRecord,
    PositioningSnapshot,
    Provenance,
    ResolvedEntity,
)

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
FINRA_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"

EXCHANGES = {
    "A": "NYSE American",
    "N": "NYSE",
    "P": "NYSE Arca",
    "Q": "NASDAQ",
    "Z": "Cboe BZX",
    "V": "IEX",
}

SHORT_VOLUME_WARNING = (
    "FINRA daily short-sale volume is transaction volume reported for the day; "
    "it is not consolidated short interest, an open-position measure, or a bearish-position estimate."
)


def provenance(
    url: str,
    retrieved_at: datetime,
    effective_date: str | None,
    units: str | None,
    as_of: datetime,
    base_warnings: list[str] | None = None,
) -> Provenance:
    warnings = list(base_warnings or [])
    confidence = 1.0
    if effective_date:
        try:
            age = (as_of.date() - date.fromisoformat(effective_date)).days
            if age > 7:
                warnings.append(f"Evidence is stale: effective date is {age} days before as-of date.")
                confidence = 0.65
        except ValueError:
            warnings.append("Effective date could not be parsed.")
            confidence = 0.75
    return Provenance(
        source_url=url,
        retrieved_at=retrieved_at,
        effective_date=effective_date,
        units=units,
        parser_version=PARSER_VERSION,
        confidence=confidence,
        warnings=warnings,
    )


def _directory_date(text: str) -> str | None:
    match = re.search(r"File Creation Time:\s*(\d{8})", text)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def parse_symbol_directory(
    text: str, source_url: str, retrieved_at: datetime, as_of: datetime
) -> list[ListingRecord]:
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    headers = set(reader.fieldnames or [])
    is_nasdaq = "Symbol" in headers and "Market Category" in headers
    is_other = "ACT Symbol" in headers and "Exchange" in headers
    if not (is_nasdaq or is_other):
        raise ValueError("Symbol directory has an unsupported or malformed header")
    effective_date = _directory_date(text)
    records: list[ListingRecord] = []
    for row in reader:
        symbol = (row.get("Symbol") or row.get("ACT Symbol") or "").strip().upper()
        if not symbol or symbol.startswith("FILE CREATION TIME"):
            continue
        try:
            round_lot_raw = (row.get("Round Lot Size") or "").strip()
            round_lot = int(round_lot_raw) if round_lot_raw else None
        except ValueError:
            round_lot = None
        exchange = "NASDAQ" if is_nasdaq else EXCHANGES.get((row.get("Exchange") or "").strip(), (row.get("Exchange") or "Unknown").strip())
        etf_raw = (row.get("ETF") or "").strip().upper()
        warnings = [] if effective_date else ["Directory creation date was missing."]
        records.append(
            ListingRecord(
                symbol=symbol,
                security_name=(row.get("Security Name") or "").strip(),
                exchange=exchange,
                market_category=(row.get("Market Category") or "").strip() or None,
                etf=True if etf_raw == "Y" else False if etf_raw == "N" else None,
                test_issue=(row.get("Test Issue") or "").strip().upper() == "Y",
                round_lot_size=round_lot,
                provenance=provenance(
                    source_url,
                    retrieved_at,
                    effective_date,
                    "shares per round lot" if round_lot is not None else None,
                    as_of,
                    warnings,
                ),
            )
        )
    return records


def parse_short_volume(
    text: str, source_url: str, retrieved_at: datetime, as_of: datetime
) -> list[PositioningSnapshot]:
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    required = {"Date", "Symbol", "ShortVolume", "ShortExemptVolume", "TotalVolume", "Market"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("FINRA daily short-volume file has a malformed header")
    records: list[PositioningSnapshot] = []
    for row in reader:
        try:
            raw_date = row["Date"]
            trade_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
            short = int(row["ShortVolume"])
            exempt = int(row["ShortExemptVolume"])
            total = int(row["TotalVolume"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("FINRA daily short-volume file contains an invalid row") from exc
        records.append(
            PositioningSnapshot(
                symbol=row["Symbol"].strip().upper(),
                trade_date=trade_date,
                short_volume=short,
                short_exempt_volume=exempt,
                total_volume=total,
                reporting_market=row["Market"].strip(),
                short_volume_ratio=(short / total) if total else None,
                provenance=provenance(
                    source_url,
                    retrieved_at,
                    trade_date.isoformat(),
                    "shares",
                    as_of,
                    [SHORT_VOLUME_WARNING],
                ),
            )
        )
    return records


def _normalized_exchange(value: str) -> str:
    normalized = value.strip().upper()
    aliases = {"NASDAQ GLOBAL SELECT": "NASDAQ", "NASDAQ GLOBAL MARKET": "NASDAQ", "XNAS": "NASDAQ"}
    return aliases.get(normalized, normalized)


def reconcile(
    entity: ResolvedEntity | None,
    listings: Iterable[ListingRecord],
    comparison_evidence: Iterable[ComparisonFact],
) -> list[Conflict]:
    facts: dict[str, list[tuple[str | int, str]]] = {
        "ticker": [],
        "exchange": [],
        "shares_outstanding": [],
    }
    if entity:
        facts["ticker"].append((entity.ticker.upper(), "resolved SEC identity"))
        if entity.exchange:
            facts["exchange"].append((_normalized_exchange(entity.exchange), "resolved SEC identity"))
        if entity.shares_outstanding is not None:
            facts["shares_outstanding"].append((entity.shares_outstanding, "resolved SEC identity"))
    for listing in listings:
        facts["ticker"].append((listing.symbol.upper(), listing.provenance.source_url))
        facts["exchange"].append((_normalized_exchange(listing.exchange), listing.provenance.source_url))
    for evidence in comparison_evidence:
        value = evidence.value
        if evidence.field == "ticker":
            value = str(value).upper()
        elif evidence.field == "exchange":
            value = _normalized_exchange(str(value))
        facts[evidence.field].append((value, evidence.provenance.source_url))

    conflicts: list[Conflict] = []
    explanations = {
        "ticker": "Sources identify different symbols for the resolved security.",
        "exchange": "Sources identify different listing exchanges for the resolved security.",
        "shares_outstanding": "Normalized sources report different dated shares-outstanding values; retain each value and compare effective dates.",
    }
    for field, values_and_sources in facts.items():
        unique_values = list(dict.fromkeys(value for value, _ in values_and_sources))
        if len(unique_values) > 1:
            conflicts.append(
                Conflict(
                    field=field,  # type: ignore[arg-type]
                    values=unique_values,
                    sources=list(dict.fromkeys(source for _, source in values_and_sources)),
                    explanation=explanations[field],
                )
            )
    return conflicts
