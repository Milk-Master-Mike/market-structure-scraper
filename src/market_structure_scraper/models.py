from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Dataset = Literal["symbol_directory", "short_volume", "reconciliation"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Provenance(StrictModel):
    source_url: str
    retrieved_at: datetime
    effective_date: str | None
    units: str | None
    parser_version: str
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ResolvedEntity(StrictModel):
    cik: str | None = Field(default=None, pattern=r"^\d{10}$")
    ticker: str
    name: str | None = None
    exchange: str | None = None
    shares_outstanding: int | None = Field(default=None, ge=0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class ComparisonFact(StrictModel):
    field: Literal["ticker", "exchange", "shares_outstanding"]
    value: str | int
    provenance: Provenance


class CollectionRequest(StrictModel):
    query: str = Field(min_length=1, max_length=32)
    resolved_entity: ResolvedEntity | None = None
    requested_datasets: list[Dataset] = Field(
        default_factory=lambda: ["symbol_directory", "short_volume", "reconciliation"]
    )
    as_of: datetime | None = None
    trade_date: date | None = None
    comparison_evidence: list[ComparisonFact] = Field(default_factory=list)
    source_settings: dict[str, Any] = Field(default_factory=dict)
    fixture_mode: bool = False
    fixture_scenario: str = "normal"

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return value.strip().upper()


class ListingRecord(StrictModel):
    symbol: str
    security_name: str
    exchange: str
    market_category: str | None
    etf: bool | None
    test_issue: bool
    round_lot_size: int | None
    provenance: Provenance


class PositioningSnapshot(StrictModel):
    symbol: str
    trade_date: date
    short_volume: int
    short_exempt_volume: int
    total_volume: int
    reporting_market: str
    short_volume_ratio: float | None
    provenance: Provenance


class Conflict(StrictModel):
    field: Literal["ticker", "exchange", "shares_outstanding"]
    values: list[str | int]
    sources: list[str]
    explanation: str
    severity: Literal["warning", "error"] = "warning"


class PartialFailure(StrictModel):
    dataset: str
    source: str
    error_code: str
    message: str
    retryable: bool = False


class ScrapeRun(StrictModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    fixture_mode: bool
    status: Literal["complete", "partial", "not_found", "failed"]


class CollectedRecords(StrictModel):
    listings: list[ListingRecord] = Field(default_factory=list)
    positioning: list[PositioningSnapshot] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)


class CollectionResponse(StrictModel):
    contract_version: str
    collector_version: str
    query: str
    run: ScrapeRun
    records: CollectedRecords = Field(default_factory=CollectedRecords)
    partial_failures: list[PartialFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Capabilities(StrictModel):
    collector: str
    version: str
    contract_version: str
    datasets: list[Dataset]
    fixture_scenarios: list[str]
    source_ids: list[str]
    limits: dict[str, int | float]

