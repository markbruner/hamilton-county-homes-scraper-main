from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from hch_scraper.pipelines import daily_scraper


def test_fixed_backfill_range_is_inclusive():
    args = daily_scraper.parse_args(
        ["--start-date", "2026-06-04", "--end-date", "2026-11-10", "--dry-run"]
    )
    dates = daily_scraper.resolve_dates(args, date(2026, 11, 11))
    assert dates == daily_scraper.Dates(date(2026, 6, 4), date(2026, 11, 10))
    windows = daily_scraper._initialize_ranges("06/04/2026", "11/10/2026")
    assert len(windows) == 20
    assert windows[0][0] == "06/04/2026"
    assert windows[-1][-1] == "11/10/2026"


@pytest.mark.parametrize("arguments", [
    ["--start-date", "2026-06-04"],
    ["--start-date", "2026-06-04", "--end-date", "2026-11-11"],
    ["--start-date", "2026-06-04", "--end-date", "2026-11-10", "--max_days_ago", "4"],
])
def test_rejects_invalid_fixed_backfill_ranges(arguments):
    with pytest.raises(ValueError):
        daily_scraper.resolve_dates(daily_scraper.parse_args(arguments), date(2026, 11, 11))


@pytest.mark.parametrize("dry_run", [True, False])
def test_scheduled_pipeline_prepares_sales_after_an_empty_range(monkeypatch, dry_run):
    empty_range = ("11/01/2026", "11/01/2026")
    sales_range = ("11/02/2026", "11/02/2026")
    sales = pd.DataFrame(
        [{"Parcel Number": "001-0001-0001-00", "Address": "100 MAIN ST",
          "Transfer Date": "11/02/2026", "Amount": 100000}]
    )
    scrape = Mock(side_effect=[
        (pd.DataFrame(), [sales_range], None, False),
        (sales, [], None, False),
    ])
    monkeypatch.setattr(daily_scraper, "main", scrape)
    credentials = Mock(return_value={"SUPABASE_URL": "mock", "SUPABASE_SERVICE_ROLE_KEY": "mock"})
    monkeypatch.setattr(daily_scraper, "_get_required_env", credentials)
    supabase = Mock()
    supabase.rpc.return_value.execute.return_value.error = None
    create_client = Mock(return_value=supabase)
    monkeypatch.setattr(daily_scraper, "create_client", create_client)
    prepare = Mock(wraps=daily_scraper.prepare_sales_records)
    monkeypatch.setattr(daily_scraper, "prepare_sales_records", prepare)

    daily_scraper._scrape_all_dates(
        [empty_range, sales_range], robots_txt_allowed=True, dry_run=dry_run
    )

    assert scrape.call_count == 2
    if dry_run:
        credentials.assert_not_called()
        create_client.assert_not_called()
        supabase.rpc.assert_not_called()
        prepare.assert_called_once()
    else:
        rpc_name, body = supabase.rpc.call_args.args
        assert rpc_name == "upsert_sales_hamilton"
        assert body["p"]["transfer_date"] == "2026-11-02"
        assert body["p"]["parcel_number"] == "001-0001-0001-00"
        assert len(body["p"]["record_key"]) == 64
        assert len(body["p"]["row_hash"]) == 64
        supabase.rpc.return_value.execute.assert_called_once()
