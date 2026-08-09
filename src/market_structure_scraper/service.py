from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from . import CONTRACT_VERSION, __version__
from .client import SourceClient, SourceError
from .config import Settings
from .fixtures import FIXTURE_RETRIEVED_AT, FIXTURE_TRADE_DATE, FixtureSource
from .models import (
    Capabilities,
    CollectedRecords,
    CollectionRequest,
    CollectionResponse,
    PartialFailure,
    ScrapeRun,
)
from .parser import (
    FINRA_URL,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    SHORT_VOLUME_WARNING,
    parse_short_volume,
    parse_symbol_directory,
    reconcile,
)

FIXTURE_SCENARIOS = ["normal", "conflict", "malformed", "stale", "rate_limited"]


def capabilities(settings: Settings | None = None) -> Capabilities:
    configured = settings or Settings()
    return Capabilities(
        collector="market-structure-scraper",
        version=__version__,
        contract_version=CONTRACT_VERSION,
        datasets=["symbol_directory", "short_volume", "reconciliation"],
        fixture_scenarios=FIXTURE_SCENARIOS,
        source_ids=["nasdaq-trader-symbol-directory", "finra-regsho-daily-short-volume"],
        limits={
            "max_concurrency": configured.max_concurrency,
            "requests_per_second": configured.requests_per_second,
        },
    )


class CollectorService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    @staticmethod
    def _failure(dataset: str, source: str, exc: Exception) -> PartialFailure:
        if isinstance(exc, SourceError):
            return PartialFailure(
                dataset=dataset,
                source=source,
                error_code=exc.code,
                message=str(exc),
                retryable=exc.retryable,
            )
        return PartialFailure(
            dataset=dataset,
            source=source,
            error_code="parse_error",
            message=str(exc),
        )

    @staticmethod
    def _run_id(request: CollectionRequest, started_at: datetime) -> str:
        if request.fixture_mode:
            stable = f"{request.query}:{request.fixture_scenario}:{started_at.isoformat()}"
            return str(uuid.uuid5(uuid.NAMESPACE_URL, stable))
        return str(uuid.uuid4())

    async def collect(self, request: CollectionRequest) -> CollectionResponse:
        if request.fixture_mode and request.fixture_scenario not in FIXTURE_SCENARIOS:
            raise ValueError(f"Unknown fixture scenario: {request.fixture_scenario}")
        started_at = (
            datetime.fromisoformat(FIXTURE_RETRIEVED_AT)
            if request.fixture_mode
            else datetime.now(UTC)
        )
        as_of = request.as_of or started_at
        trade_date = request.trade_date
        if trade_date is None:
            trade_date = (
                datetime.fromisoformat(FIXTURE_TRADE_DATE).date()
                if request.fixture_mode
                else as_of.date()
            )
        source: Any = FixtureSource(request.fixture_scenario) if request.fixture_mode else SourceClient(self.settings)
        records = CollectedRecords()
        failures: list[PartialFailure] = []
        warnings: list[str] = []

        async def fetch(kind: str, url: str) -> tuple[str, str, str | Exception]:
            try:
                return kind, url, await source.get_text(url)
            except Exception as exc:  # noqa: BLE001 - source failures are isolated by design
                return kind, url, exc

        tasks = []
        if "symbol_directory" in request.requested_datasets:
            tasks.extend(
                [
                    fetch("directory", NASDAQ_LISTED_URL),
                    fetch("directory", OTHER_LISTED_URL),
                ]
            )
        if "short_volume" in request.requested_datasets:
            tasks.append(fetch("short_volume", FINRA_URL.format(date=trade_date.strftime("%Y%m%d"))))

        for kind, url, payload in await asyncio.gather(*tasks):
            source_id = (
                "nasdaq-trader-symbol-directory"
                if kind == "directory"
                else "finra-regsho-daily-short-volume"
            )
            dataset = "symbol_directory" if kind == "directory" else "short_volume"
            if isinstance(payload, Exception):
                failures.append(self._failure(dataset, source_id, payload))
                continue
            try:
                if kind == "directory":
                    parsed = parse_symbol_directory(payload, url, started_at, as_of)
                    records.listings.extend(
                        item for item in parsed if item.symbol == request.query
                    )
                else:
                    parsed_positioning = parse_short_volume(payload, url, started_at, as_of)
                    records.positioning.extend(
                        item for item in parsed_positioning if item.symbol == request.query
                    )
            except Exception as exc:  # noqa: BLE001 - parser failures become partial results
                failures.append(self._failure(dataset, source_id, exc))

        if "symbol_directory" in request.requested_datasets and not records.listings:
            failures.append(
                PartialFailure(
                    dataset="symbol_directory",
                    source="nasdaq-trader-symbol-directory",
                    error_code="missing_evidence",
                    message=f"No Nasdaq Trader directory record matched {request.query}.",
                )
            )
        if "short_volume" in request.requested_datasets and not records.positioning:
            failures.append(
                PartialFailure(
                    dataset="short_volume",
                    source="finra-regsho-daily-short-volume",
                    error_code="missing_evidence",
                    message=f"No FINRA daily short-volume record matched {request.query} for {trade_date}.",
                )
            )

        if "reconciliation" in request.requested_datasets:
            records.conflicts = reconcile(
                request.resolved_entity, records.listings, request.comparison_evidence
            )
            if request.resolved_entity is None:
                warnings.append(
                    "No resolved SEC identity was supplied; ticker and exchange reconciliation is limited."
                )
        if records.positioning:
            warnings.append(SHORT_VOLUME_WARNING)
        if records.conflicts:
            warnings.append("Conflicting evidence was retained; no source was silently selected as authoritative.")

        completed_at = started_at if request.fixture_mode else datetime.now(UTC)
        useful_records = bool(records.listings or records.positioning)
        status = "partial" if failures else "complete"
        if not useful_records and failures:
            status = "failed"
        return CollectionResponse(
            contract_version=CONTRACT_VERSION,
            collector_version=__version__,
            query=request.query,
            run=ScrapeRun(
                run_id=self._run_id(request, started_at),
                started_at=started_at,
                completed_at=completed_at,
                fixture_mode=request.fixture_mode,
                status=status,
            ),
            records=records,
            partial_failures=failures,
            warnings=warnings,
        )
