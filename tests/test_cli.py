import json

from market_structure_scraper.cli import main


def test_fixture_cli(capsys) -> None:
    result = main(
        [
            "collect",
            "EXMPL",
            "--fixture",
            "--sec-name",
            "Example Technology Corporation",
            "--sec-exchange",
            "NASDAQ",
        ]
    )
    assert result == 0
    body = json.loads(capsys.readouterr().out)
    assert body["records"]["listings"]
    assert body["records"]["positioning"]

