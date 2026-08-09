from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

import uvicorn

from .models import CollectionRequest, ResolvedEntity
from .service import FIXTURE_SCENARIOS, CollectorService


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="market-structure-scraper")
    commands = root.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("query")
    collect.add_argument("--fixture", action="store_true")
    collect.add_argument("--scenario", choices=FIXTURE_SCENARIOS, default="normal")
    collect.add_argument("--sec-name")
    collect.add_argument("--sec-exchange")
    collect.add_argument("--sec-shares", type=int)
    collect.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        choices=["symbol_directory", "short_volume", "reconciliation"],
    )
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "serve":
        uvicorn.run("market_structure_scraper.api:app", host=args.host, port=args.port)
        return 0
    data = {
        "query": args.query,
        "fixture_mode": args.fixture,
        "fixture_scenario": args.scenario,
    }
    if args.datasets:
        data["requested_datasets"] = args.datasets
    if args.sec_name or args.sec_exchange or args.sec_shares is not None:
        data["resolved_entity"] = ResolvedEntity(
            ticker=args.query,
            name=args.sec_name,
            exchange=args.sec_exchange,
            shares_outstanding=args.sec_shares,
        )
    response = asyncio.run(CollectorService().collect(CollectionRequest(**data)))
    print(json.dumps(response.model_dump(mode="json"), indent=2))
    return 0 if response.run.status in {"complete", "partial"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

