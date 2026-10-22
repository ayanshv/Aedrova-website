"""Countdown follows server deadlines, including reload, clock skew and expiry."""

from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import expect
from test_checkout_flow import client  # noqa: F401
from test_early_access import clock  # noqa: F401
from test_preparation_browser import ui  # noqa: F401

from aedrova_site import promotion


def test_countdown_price_switch_reload_and_exact_expiry(ui, clock):  # noqa: F811
    page, _, _, _ = ui
    page.clock.install(time=datetime(2000, 1, 1, tzinfo=UTC))
    page.goto("https://aedrova.test/plans")
    page.get_by_role("button", name="Essential only", exact=True).click()
    expect(page.locator("[data-offer-price]:visible")).to_have_count(2)
    expect(page.locator("[data-offer-countdown]")).to_contain_text("60d")
    assert page.locator("[data-early-access]").get_attribute("data-remaining") == str(
        promotion.ENDS_AT - clock[0]
    )
    page.locator('[data-billing-choice="annual"]').click()
    expect(page.locator(".regular-price:visible").first).to_contain_text("$120")
    expect(page.locator("[data-offer-price]:visible")).to_have_count(2)
    clock[0] += 86400
    page.reload()
    expect(page.locator("[data-offer-countdown]")).to_contain_text("59d")
    assert page.locator("[data-early-access]").get_attribute("data-remaining") == str(
        promotion.ENDS_AT - clock[0]
    )
    page.set_viewport_size({"width": 1440, "height": 1100})
    output = Path("work/early-access-oct21")
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(output / "mobile.png"), full_page=True)
    clock[0] = promotion.ENDS_AT - 2
    page.reload()
    page.clock.run_for(3000)
    expect(page.locator("[data-early-access]")).to_be_hidden()
    expect(page.locator("[data-offer-price]:visible")).to_have_count(0)
    expect(page.locator("[data-regular-note]:visible")).to_have_count(2)
    expect(page.locator("[data-pricing]")).not_to_have_class("plans early-access-active")
    clock[0] = promotion.ENDS_AT
    page.reload()
    expect(page.locator("[data-offer-price]")).to_have_count(0)
