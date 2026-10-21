"""Pricing interactions preserve waitlist gates and per-workspace coverage."""

from pathlib import Path

from playwright.sync_api import expect
from test_checkout_flow import client  # noqa: F401
from test_preparation_browser import ui  # noqa: F401


def test_billing_toggle_prices_icons_and_responsive_layout(ui):  # noqa: F811
    page, _, _, _ = ui
    page.set_viewport_size({"width": 1440, "height": 1080})
    page.goto("https://aedrova.test/plans")
    page.get_by_role("button", name="Essential only", exact=True).click()
    pro = page.locator(".plan").filter(has=page.get_by_role("heading", name="Pro", exact=True))
    team = page.locator(".plan").filter(has=page.get_by_role("heading", name="Team", exact=True))
    expect(pro.locator(".team-visual svg")).to_have_count(3)
    expect(team.locator(".team-visual svg")).to_have_count(5)
    expect(pro.locator(".price > [data-price-interval]:visible")).to_contain_text("$15")
    expect(team.locator(".price > [data-price-interval]:visible")).to_contain_text("$25")
    annual = page.locator('[data-billing-choice="annual"]')
    annual.focus()
    page.keyboard.press("Enter")
    expect(annual).to_have_attribute("aria-current", "true")
    expect(pro.locator(".price > [data-price-interval]:visible")).to_contain_text("$120")
    expect(team.locator(".price > [data-price-interval]:visible")).to_contain_text("$250")
    expect(pro.locator(".price > [data-price-interval]:visible")).not_to_contain_text("$15")
    expect(pro.locator("a.button")).to_have_attribute("href", "/waitlist")
    expect(team.locator("a.button")).to_have_attribute("href", "/waitlist")
    buttons = page.locator(".plans .button").evaluate_all(
        "els=>els.map(e=>e.getBoundingClientRect().top)"
    )
    assert max(buttons) - min(buttons) < 2
    output = Path("work/pricing-oct20")
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / "annual-desktop.png"), full_page=True)
    page.reload()
    expect(annual).to_have_attribute("aria-current", "true")
    page.locator('[data-billing-choice="monthly"]').click()
    expect(pro.locator(".price > [data-price-interval]:visible")).to_contain_text("$15")
    for width in (390, 768):
        page.set_viewport_size({"width": width, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(output / "monthly-mobile.png"), full_page=True)
