import os

import pytest
from playwright.sync_api import sync_playwright

pytestmark = [pytest.mark.e2e, pytest.mark.browser]


def test_swagger_ui_loads_in_browser() -> None:
    if os.getenv("RUN_BROWSER_E2E_TESTS") != "1":
        pytest.skip("set RUN_BROWSER_E2E_TESTS=1 to run browser e2e tests")

    api_url = os.getenv("E2E_API_URL", "http://localhost:8000")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{api_url}/docs")
            page.get_by_text("Account Balance API Service").wait_for()
            page.get_by_text("/api/v1/auth/login").wait_for()
            page.get_by_text("/api/v1/payments/webhook").wait_for()
        finally:
            browser.close()
