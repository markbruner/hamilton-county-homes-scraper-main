from hch_scraper.pipelines.scrape import _initialize_ranges


def test_initialize_ranges_basic():
    ranges = _initialize_ranges("01/01/2026", "01/05/2026", window_days=2)
    assert ranges == [
        ("01/01/2026", "01/03/2026"),
        ("01/04/2026", "01/05/2026"),
    ]


def test_initialize_ranges_start_after_end():
    try:
        _initialize_ranges("01/10/2026", "01/05/2026", window_days=2)
    except ValueError as exc:
        assert "`start` must be on or before `end`." in str(exc)
    else:
        raise AssertionError("Expected ValueError for start > end")
