from types import SimpleNamespace

import pytest

from hch_scraper.utils.data_extraction.form_helpers import datetime_utils as du


class _DummyDriver:
    def execute_script(self, _script):
        return None


class _DummyElem:
    text = "No matching records found"


class _DummyWait:
    def until(self, _condition):
        return _DummyElem()


def test_check_reset_needed_handles_unknown_total_entries():
    dates = [("01/01/2026", "01/07/2026")]

    result = du.check_reset_needed(
        driver=_DummyDriver(),
        wait=_DummyWait(),
        start="01/01/2026",
        end="01/07/2026",
        dates=dates,
    )

    assert result.reset_needed is False
    assert result.modified is False
    assert result.dates == dates
    assert result.total_entries is None


def test_check_reset_needed_splits_when_entries_meet_threshold(monkeypatch):
    dates = [("01/01/2026", "01/07/2026")]
    monkeypatch.setattr(du, "_get_dt_record_count", lambda _driver: 1000)

    result = du.check_reset_needed(
        driver=_DummyDriver(),
        wait=_DummyWait(),
        start="01/01/2026",
        end="01/07/2026",
        dates=dates,
    )

    assert result.reset_needed is True
    assert result.modified is True
    assert result.dates == [
        ("01/01/2026", "01/04/2026"),
        ("01/05/2026", "01/07/2026"),
    ]
    assert result.total_entries == 1000


@pytest.mark.parametrize(
    ("status", "expected_count"),
    [
        ("Showing 1–10 of 136", 136),
        ("Showing 991–1,000 of 1,000", 1000),
        ("No results found. Try a new search.", 0),
    ],
)
def test_extract_wedge_sales_count(status, expected_count):
    class ResultsWait:
        def until(self, _condition):
            return SimpleNamespace(text=status)

    assert du._extract_total_entries_once(_DummyDriver(), ResultsWait()) == expected_count


def test_capped_single_day_cannot_be_split(monkeypatch):
    monkeypatch.setattr(du, "_get_dt_record_count", lambda _driver: 1000)
    with pytest.raises(ValueError, match="limit for 01/01/2026"):
        du.check_reset_needed(
            _DummyDriver(), _DummyWait(), "01/01/2026", "01/01/2026",
            [("01/01/2026", "01/01/2026")],
        )


def test_check_reset_needed_retries_until_count_available(monkeypatch):
    dates = [("01/01/2026", "01/07/2026")]
    calls = {"n": 0}

    def _mock_get_count(_driver):
        calls["n"] += 1
        if calls["n"] < 3:
            return None
        return 1000

    monkeypatch.setattr(du, "_get_dt_record_count", _mock_get_count)
    monkeypatch.setattr(du.time, "sleep", lambda _seconds: None)

    result = du.check_reset_needed(
        driver=_DummyDriver(),
        wait=_DummyWait(),
        start="01/01/2026",
        end="01/07/2026",
        dates=dates,
        max_attempts=3,
        retry_delay_seconds=0,
    )

    assert calls["n"] == 3
    assert result.reset_needed is True
    assert result.total_entries == 1000
