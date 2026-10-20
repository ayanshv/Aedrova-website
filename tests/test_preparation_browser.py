"""Real browser flow checks against isolated FastAPI fixtures; no provider calls."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright
from test_checkout_flow import client  # noqa: F401 - shared isolated billing fixture

CHROME = (
    Path.home()
    / ".cache/hyperframes/chrome/chrome-headless-shell"
    / "mac_arm-152.0.7977.30/chrome-headless-shell-mac-arm64/chrome-headless-shell"
)


@pytest.fixture
def ui(client):  # noqa: F811 - shared pytest fixture imported above
    if not CHROME.exists():
        pytest.skip("Local browser binary unavailable")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        held = []
        mode = {
            "hold": "",
            "failure": "",
            "stripe_url": "https://checkout.stripe.com/c/pay_fixture",
        }

        def route(request):
            url = urlsplit(request.request.url)
            if url.hostname == "checkout.stripe.com":
                request.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<h1>Isolated Stripe destination fixture</h1>",
                )
                return
            if url.hostname != "aedrova.test":
                request.abort()
                return
            path = url.path
            if path == mode["hold"] and request.request.resource_type != "document":
                held.append(request)
                return
            if path == mode["failure"]:
                request.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"error":"Please retry checkout."}',
                )
                return
            if path == "/api/checkout":
                request.fulfill(status=200, json={"url": mode["stripe_url"]})
                return
            response = client.request(
                request.request.method,
                path + ("?" + url.query if url.query else ""),
                content=request.request.post_data,
                headers={
                    k: v
                    for k, v in request.request.headers.items()
                    if k.lower() not in {"host", "cookie", "content-length"}
                },
            )
            request.fulfill(
                status=response.status_code,
                body=response.content,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k not in {"content-encoding", "transfer-encoding", "content-length"}
                },
            )

        page.route("**/*", route)
        yield page, held, mode, errors
        browser.close()
        assert errors == []


def finish_questions(page):
    page.goto("https://aedrova.test/onboarding")
    page.get_by_role("button", name="Allow preferences", exact=True).click()
    page.locator("#nickname").fill("Orbit") if page.locator("#nickname").is_visible() else None
    for _ in range(6):
        page.locator("#wizard-next").click()


def test_onboarding_prepares_then_opens_real_plans(ui):
    page, held, mode, _ = ui
    mode["hold"] = "/plans"
    finish_questions(page)
    expect(page.locator("#preparation")).to_be_visible()
    expect(page.locator("li[aria-current=step]")).to_contain_text("plan options")
    assert page.evaluate("JSON.parse(localStorage.getItem('aedrova-intro')).nickname") == "Aedrova"
    page.wait_for_timeout(300)
    page.screenshot(path="work/preparation-preview/onboarding-desktop.png")
    assert len(held) == 1
    held.pop().fulfill(status=200, content_type="text/html", body="Ready")
    expect(page).to_have_url("https://aedrova.test/plans")


def test_skip_can_continue_without_waiting_and_reduced_motion(ui):
    page, held, mode, _ = ui
    mode["hold"] = "/plans"
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    page.goto("https://aedrova.test/onboarding")
    page.evaluate("document.documentElement.dataset.theme='dark'")
    page.locator("#wizard-skip").click()
    expect(page.locator("#preparation")).to_be_visible()
    assert (
        page.locator(".preparation-indicator")
        .nth(1)
        .evaluate("e=>getComputedStyle(e).animationName")
        == "none"
    )
    assert page.locator("#preparation").bounding_box()["width"] <= 390
    page.screenshot(path="work/preparation-preview/onboarding-dark-mobile.png")
    page.locator("#preparation-continue").click()
    expect(page).to_have_url("https://aedrova.test/plans")


def test_failed_preload_has_direct_exit_and_escape_returns_focus(ui):
    page, _, mode, _ = ui
    mode["failure"] = "/plans"
    page.goto("https://aedrova.test/onboarding")
    page.locator("#wizard-skip").click()
    expect(page.locator("#preparation-status")).to_contain_text("taking a moment")
    page.keyboard.press("Escape")
    expect(page.locator("#preparation")).not_to_be_visible()
    expect(page.locator("#wizard-skip")).to_be_focused()


def begin_checkout(page, plan="monthly"):
    page.goto("https://aedrova.test/account")
    expect(page.locator("#account-status")).to_contain_text("Review your selected plan")
    page.locator("#billing-plan").select_option(plan)
    page.locator("#confirm-team-checkout").check()
    page.locator("#checkout").click()


@pytest.mark.parametrize("plan", ["monthly", "annual"])
def test_checkout_waits_for_actual_response_then_navigates(ui, plan):
    page, held, mode, _ = ui
    mode["hold"] = "/api/checkout"
    begin_checkout(page, plan)
    expect(page.locator("#preparation")).to_be_visible()
    expect(page.locator("#preparation-continue")).not_to_be_visible()
    expect(page.locator("#checkout")).to_be_disabled()
    page.keyboard.press("Escape")
    expect(page.locator("#preparation")).to_be_visible()
    assert len(held) == 1
    assert held[0].request.post_data_json["plan"] == plan
    page.wait_for_timeout(300)
    page.screenshot(path="work/preparation-preview/checkout-desktop.png")
    held.pop().fulfill(status=200, json={"url": mode["stripe_url"]})
    expect(page).to_have_url(mode["stripe_url"])


@pytest.mark.parametrize("failure", ["service", "unsafe_url", "timeout"])
def test_checkout_failures_restore_the_review_screen(ui, failure):
    page, _, mode, _ = ui
    if failure == "service":
        mode["failure"] = "/api/checkout"
    elif failure == "unsafe_url":
        mode["stripe_url"] = "https://example.com/untrusted"
    else:
        mode["hold"] = "/api/checkout"
    if failure == "timeout":
        page.clock.install()
    begin_checkout(page)
    if failure == "timeout":
        page.clock.fast_forward(21000)
    expect(page.locator("#preparation")).not_to_be_visible(timeout=25000)
    expect(page.locator("#checkout")).to_be_enabled()
    expect(page.locator(".toast")).to_contain_text(
        {
            "service": "Please retry checkout.",
            "unsafe_url": "unexpected address",
            "timeout": "longer than expected",
        }[failure]
    )
    assert page.url.startswith("https://aedrova.test/account")
