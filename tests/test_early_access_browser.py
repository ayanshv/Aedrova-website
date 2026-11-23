"""The plans page no longer advertises a free early-access period."""

from playwright.sync_api import expect
from test_checkout_flow import client  # noqa: F401
from test_early_access import clock  # noqa: F401
from test_preparation_browser import ui  # noqa: F401


def test_plans_page_has_no_gift_banner_or_zero_price(ui, clock):  # noqa: F811
    page, _, _, _ = ui
    page.goto("https://aedrova.test/plans")
    page.get_by_role("button", name="Essential only", exact=True).click()
    expect(page.locator("[data-early-access]")).to_have_count(0)
    expect(page.locator("[data-offer-price]")).to_have_count(0)
    expect(page.locator("[data-regular-note]:visible")).to_have_count(2)
    page.locator('[data-billing-choice="annual"]').click()
    expect(page.locator(".regular-price:visible").first).to_contain_text("$144")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
