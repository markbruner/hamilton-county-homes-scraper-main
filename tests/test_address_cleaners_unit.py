from hch_scraper.utils.data_extraction import address_cleaners as ac


def test_detect_address_range_standard():
    low, high, addr_for_tagging, range_type = ac._detect_address_range(
        "1308 1310 WILLIAM H TAFT RD", None
    )

    assert low == "1308"
    assert high == "1310"
    assert addr_for_tagging == "1308 WILLIAM H TAFT RD"
    assert range_type == "range"


def test_detect_address_range_apartment():
    low, high, addr_for_tagging, range_type = ac._detect_address_range(
        "1308 1310 WILLIAM H TAFT RD", "apt"
    )
    assert low == "1308"
    assert addr_for_tagging == "1308 WILLIAM H TAFT RD APT 1310"
    assert range_type == "apt"

def test_detect_street_only():
    low, high, addr_for_tagging, range_type = ac._detect_address_range(
        "FREEMAN AVE", None
    )
    assert low is None
    assert high is None
    assert addr_for_tagging == "FREEMAN AVE"
    assert range_type == None

def test_none_only():
    low, high, addr_for_tagging, range_type = ac._detect_address_range(
       None, None
    )
    assert low is None
    assert high is None
    assert addr_for_tagging is None
    assert range_type == 'unknown'

def test_coerce_address_number_words():
    assert ac._coerce_address_number("one hundred twenty three") == "123"


