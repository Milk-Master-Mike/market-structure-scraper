from __future__ import annotations

from pathlib import Path

from .client import SourceError

FIXTURE_DIR = Path(__file__).with_name("fixture_data")
FIXTURE_RETRIEVED_AT = "2026-01-15T12:00:00Z"
FIXTURE_TRADE_DATE = "2026-01-14"


class FixtureSource:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    async def get_text(self, url: str) -> str:
        if self.scenario == "rate_limited":
            raise SourceError("http_429", "Fixture source rate limit", True)

        if url.endswith("nasdaqlisted.txt"):
            text = (FIXTURE_DIR / "nasdaqlisted.txt").read_text(encoding="utf-8")
            if self.scenario == "malformed":
                return "unexpected|columns\nbroken|row\n"
            if self.scenario == "stale":
                return text.replace("20260114", "20190114")
            return text

        if url.endswith("otherlisted.txt"):
            text = (FIXTURE_DIR / "otherlisted.txt").read_text(encoding="utf-8")
            if self.scenario == "conflict":
                return text.replace(
                    "ALT|Alternative Example Incorporated Common Stock|N|ALT",
                    "EXMPL|Example Technology Corporation Common Stock|N|EXMPL",
                ).replace("|ALT\n", "|EXMPL\n")
            if self.scenario == "malformed":
                return "ACT Symbol|Security Name\nALT\n"
            if self.scenario == "stale":
                return text.replace("20260114", "20190114")
            return text

        if "CNMSshvol" in url:
            text = (FIXTURE_DIR / "CNMSshvol20260114.txt").read_text(encoding="utf-8")
            if self.scenario == "malformed":
                return "Date|Symbol|ShortVolume\nnot-a-date|EXMPL|NaN\n"
            if self.scenario == "stale":
                return text.replace("20260114", "20190114")
            return text

        raise SourceError("fixture_not_found", f"No sanitized fixture for {url}")

