"""Storage, accessibility and public trust flow checks in an isolated real browser."""

from playwright.sync_api import expect
from test_checkout_flow import client  # noqa: F401
from test_preparation_browser import ui  # noqa: F401


def test_preference_storage_is_opt_in_and_reversible(ui):  # noqa: F811
    page, _, _, _ = ui
    page.goto("https://aedrova.test/plans")
    expect(page.locator("#storage-notice")).to_be_visible()
    page.locator(".desktop-nav .theme-toggle").click()
    assert page.evaluate("localStorage.getItem('aedrova-theme')") is None
    page.get_by_role("button", name="Essential only", exact=True).click()
    expect(page.locator("#storage-notice")).to_be_hidden()
    page.get_by_role("button", name="Storage choices", exact=True).click()
    page.get_by_role("button", name="Allow preferences", exact=True).click()
    assert page.evaluate("JSON.parse(localStorage.getItem('aedrova-theme'))") == "dark"
    # Another tab can withdraw consent; this open page must stop persisting too.
    page.evaluate(
        "localStorage.setItem('aedrova-storage-choice',JSON.stringify('essential'));localStorage.removeItem('aedrova-theme')"
    )
    page.locator(".desktop-nav .theme-toggle").click()
    assert page.evaluate("localStorage.getItem('aedrova-theme')") is None
    page.get_by_role("button", name="Storage choices", exact=True).click()
    page.get_by_role("button", name="Essential only", exact=True).click()
    assert page.evaluate("localStorage.getItem('aedrova-theme')") is None


def test_mobile_choices_keyboard_and_public_images(ui):  # noqa: F811
    page, _, _, _ = ui
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("https://aedrova.test/refunds")
    page.keyboard.press("Tab")
    expect(page.locator(".skip")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()
    page.get_by_role("button", name="Essential only", exact=True).focus()
    page.keyboard.press("Enter")
    expect(page.locator("#storage-notice")).to_be_hidden()
    for path in [
        "/",
        "/plans",
        "/waitlist",
        "/privacy",
        "/terms",
        "/cookies",
        "/refunds",
        "/support",
        "/unsubscribe",
    ]:
        page.goto("https://aedrova.test" + path)
        assert page.locator("h1").count() == 1, path
        assert page.locator("img:not([alt])").count() == 0, path
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), path
        assert page.locator("input:not([type=hidden])").evaluate_all(
            "els=>els.every(e=>e.labels.length||e.getAttribute('aria-label'))"
        ), path


def test_connector_confirmation_honors_essential_storage_choice(ui):  # noqa: F811
    page, _, _, _ = ui
    page.goto("https://aedrova.test/plans")
    page.get_by_role("button", name="Essential only", exact=True).click()
    page.set_content('<button class="theme-toggle">Change appearance</button>')
    page.add_script_tag(url="https://aedrova.test/static/bud-connected.js")
    page.locator(".theme-toggle").click()
    assert page.locator("html").get_attribute("data-theme") == "dark"
    assert page.evaluate("localStorage.getItem('aedrova-theme')") is None
