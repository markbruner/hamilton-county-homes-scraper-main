import os
import sys
import types
from datetime import datetime

import pytest

# Provide a minimal pandas stub so the module under test can be imported
sys.modules.setdefault("pandas", types.SimpleNamespace(to_datetime=lambda x: x))
sys.modules.setdefault(
    "yaml",
    types.SimpleNamespace(
        safe_load=lambda f: {
            "search": {
                "conventional_home_type": "",
                "form_search_button": "",
            }
        }
    )
)

# Stub selenium package hierarchy so datetime_utils can be imported without the
# real selenium dependency
selenium = types.ModuleType("selenium")
webdriver = types.ModuleType("selenium.webdriver")
webdriver_support = types.ModuleType("selenium.webdriver.support")
webdriver_support.expected_conditions = types.SimpleNamespace()
webdriver_common = types.ModuleType("selenium.webdriver.common")
webdriver_common_by = types.SimpleNamespace(By=type("By", (), {}))
selenium_common = types.ModuleType("selenium.common")
selenium_common_exceptions = types.ModuleType("selenium.common.exceptions")
for exc in [
    "ElementClickInterceptedException",
    "TimeoutException",
    "StaleElementReferenceException",
]:
    setattr(selenium_common_exceptions, exc, type(exc, (), {}))
selenium_common.exceptions = selenium_common_exceptions

sys.modules.setdefault("selenium", selenium)
sys.modules.setdefault("selenium.webdriver", webdriver)
sys.modules.setdefault("selenium.webdriver.support", webdriver_support)
sys.modules.setdefault(
    "selenium.webdriver.support.expected_conditions",
    webdriver_support.expected_conditions,
)
sys.modules.setdefault("selenium.webdriver.common", webdriver_common)
sys.modules.setdefault("selenium.webdriver.common.by", webdriver_common_by)
sys.modules.setdefault("selenium.common", selenium_common)
sys.modules.setdefault("selenium.common.exceptions", selenium_common_exceptions)


# Stub selenium_utils to avoid importing selenium dependency
selenium_utils = types.ModuleType("selenium_utils")
selenium_utils.get_text = lambda *args, **kwargs: ""
selenium_utils.safe_quit = lambda *args, **kwargs: None
sys.modules.setdefault(
    "hch_scraper.utils.data_extraction.form_helpers.selenium_utils",
    selenium_utils,
)

# Allow tests to import from the src package
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from hch_scraper.utils.data_extraction.form_helpers.datetime_utils import str_format_date


def test_str_format_date_returns_formatted_string():
    dt = datetime(2020, 12, 31)
    assert str_format_date(dt) == "12/31/2020"


def test_str_format_date_raises_value_error_on_string():
    with pytest.raises(ValueError):
        str_format_date("2020-12-31")
