# Market Structure Scraper

An independently runnable collector for Nasdaq Trader symbol directories and
FINRA daily short-sale volume files. It reconciles listing evidence against a
resolved SEC identity, retains conflicts, and returns provenance and partial
failures through HTTP or a CLI.

This service provides market-research evidence. It does not provide trading
instructions, expected returns, or personalized financial advice.

## Important FINRA interpretation

FINRA daily short-sale volume is transaction volume reported for a particular
day. It is **not consolidated short interest**, does not measure positions still
open, and must not be treated as a bearish-position estimate. Every FINRA record
and every response containing one repeats this warning.

## Offline quick start

```console
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[test]"
market-structure-scraper collect EXMPL --fixture --sec-exchange NASDAQ
pytest
```

Fixture mode never uses the network. The `normal`, `conflict`, `malformed`,
`stale`, and `rate_limited` scenarios are deterministic and sanitized.

Start the HTTP API with `market-structure-scraper serve`, or run
`docker compose up --build`. Standalone Compose binds to loopback on port 8081;
the research workbench should instead attach the image only to its internal
Docker network.

## API

- `GET /health`
- `GET /v1/capabilities`
- `POST /v1/collect`

```json
{
  "query": "EXMPL",
  "resolved_entity": {
    "cik": "0001234567",
    "ticker": "EXMPL",
    "name": "Example Technology Corporation",
    "exchange": "NASDAQ",
    "shares_outstanding": 1000000
  },
  "requested_datasets": ["symbol_directory", "short_volume", "reconciliation"],
  "trade_date": "2026-01-14",
  "fixture_mode": true,
  "fixture_scenario": "normal"
}
```

Nasdaq directories do not publish shares outstanding. To compare share values,
callers may include already-normalized `comparison_evidence` with its own source
URL, retrieval time, effective date, units, parser version, confidence, and
warnings. The collector never invents a Nasdaq share count and never silently
selects a winner when ticker, exchange, or share evidence conflicts.

Missing symbol or FINRA rows are returned as `missing_evidence`. Malformed,
blocked, unavailable, and rate-limited sources become independent
`partial_failures`, so successful evidence remains available.

## Live collection

Copy `.env.example` to ignored `.env.local` and set an application name plus a
monitored contact address in `MARKET_STRUCTURE_USER_AGENT`. Live mode refuses to
run without it. The client uses an operational on-disk cache, two-request bounded
concurrency, four requests per second, bounded responses, and timeouts.

Reviewed sources and extraction limits are recorded in
`source-acceptance.yaml`: [Nasdaq Trader symbol directory definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
and [FINRA short-sale volume data](https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files).

The strict local models are compatible with
`market-data-contracts >=0.1.0,<0.2.0`, as pinned in `pyproject.toml`, until the
independent contracts release is available.

