from fastapi.testclient import TestClient

from market_structure_scraper.api import app

client = TestClient(app)


def request(scenario: str = "normal") -> dict:
    return {
        "query": "EXMPL",
        "fixture_mode": True,
        "fixture_scenario": scenario,
        "resolved_entity": {
            "cik": "0001234567",
            "ticker": "EXMPL",
            "name": "Example Technology Corporation",
            "exchange": "NASDAQ",
            "shares_outstanding": 1000000,
        },
    }


def test_health_and_capabilities() -> None:
    assert client.get("/health").json()["status"] == "ok"
    capabilities = client.get("/v1/capabilities").json()
    assert capabilities["contract_version"] == "0.1.0"
    assert capabilities["limits"]["requests_per_second"] <= 5
    assert "short_volume" in capabilities["datasets"]


def test_normal_fixture_is_deterministic_and_explained() -> None:
    first = client.post("/v1/collect", json=request())
    second = client.post("/v1/collect", json=request())
    assert first.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["run"]["status"] == "complete"
    assert body["records"]["listings"][0]["exchange"] == "NASDAQ"
    position = body["records"]["positioning"][0]
    assert position["short_volume"] == 25000
    assert position["short_volume_ratio"] == 0.25
    warnings = position["provenance"]["warnings"]
    assert any("not consolidated short interest" in warning for warning in warnings)
    assert position["provenance"]["source_url"].startswith("https://cdn.finra.org/")


def test_conflicting_exchange_ticker_and_share_values_are_retained() -> None:
    payload = request("conflict")
    evidence_provenance = {
        "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json",
        "retrieved_at": "2026-01-15T12:00:00Z",
        "effective_date": "2025-12-31",
        "units": "shares",
        "parser_version": "sec-parser/0.1.0",
        "confidence": 1,
        "warnings": [],
    }
    payload["comparison_evidence"] = [
        {"field": "shares_outstanding", "value": 1200000, "provenance": evidence_provenance},
        {"field": "ticker", "value": "EXM2", "provenance": evidence_provenance},
    ]
    body = client.post("/v1/collect", json=payload).json()
    assert body["run"]["status"] == "complete"
    conflicts = {conflict["field"]: conflict for conflict in body["records"]["conflicts"]}
    assert set(conflicts) == {"ticker", "exchange", "shares_outstanding"}
    assert set(conflicts["shares_outstanding"]["values"]) == {1000000, 1200000}
    assert {listing["exchange"] for listing in body["records"]["listings"]} == {
        "NASDAQ",
        "NYSE",
    }


def test_malformed_sources_are_isolated_failures() -> None:
    body = client.post("/v1/collect", json=request("malformed")).json()
    assert body["run"]["status"] == "failed"
    assert "parse_error" in {failure["error_code"] for failure in body["partial_failures"]}
    assert {failure["source"] for failure in body["partial_failures"]} == {
        "nasdaq-trader-symbol-directory",
        "finra-regsho-daily-short-volume",
    }


def test_stale_records_reduce_confidence() -> None:
    body = client.post("/v1/collect", json=request("stale")).json()
    evidence = body["records"]["listings"] + body["records"]["positioning"]
    assert evidence
    assert all(item["provenance"]["confidence"] < 1 for item in evidence)
    assert all(
        any("stale" in warning.lower() for warning in item["provenance"]["warnings"])
        for item in evidence
    )


def test_rate_limit_is_retryable_and_does_not_raise_http_error() -> None:
    response = client.post("/v1/collect", json=request("rate_limited"))
    assert response.status_code == 200
    body = response.json()
    assert body["run"]["status"] == "failed"
    rate_failures = [
        failure for failure in body["partial_failures"] if failure["error_code"] == "http_429"
    ]
    assert len(rate_failures) == 3
    assert all(failure["retryable"] for failure in rate_failures)


def test_unknown_fixture_scenario_returns_422() -> None:
    response = client.post("/v1/collect", json=request("unknown"))
    assert response.status_code == 422

