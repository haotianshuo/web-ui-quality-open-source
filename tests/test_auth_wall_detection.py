from __future__ import annotations

import pytest

from web_ui_quality.auth_detection import AUTH_WALL_HINT_SCRIPT
from web_ui_quality.browser_locator import resolve_browser_executable


def _browser_page():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        decision = resolve_browser_executable("chromium")
        if not decision.get("available"):
            pytest.skip("No local Chromium-compatible executable is available")
        browser = playwright.chromium.launch(headless=True, executable_path=decision["executable"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        yield page
        browser.close()


def test_offscreen_security_password_is_not_an_auth_wall() -> None:
    pages = _browser_page()
    page = next(pages)
    try:
        page.set_content(
            """
            <main><h1>Public dashboard</h1><p>Public content.</p>
              <div style="height:1400px"></div>
              <form><label>Current Password <input type="password"></label>
                <button type="submit">Update Security</button></form>
              <p>Sign in to a different account</p>
            </main>
            """
        )
        assert page.evaluate(AUTH_WALL_HINT_SCRIPT) is False
    finally:
        pages.close()


def test_visible_password_field_without_login_context_is_not_an_auth_wall() -> None:
    pages = _browser_page()
    page = next(pages)
    try:
        page.set_content(
            """
            <main><h1>Account settings</h1>
              <form><label>Current Password <input type="password"></label>
                <button type="submit">Update security</button></form>
            </main>
            """
        )
        assert page.evaluate(AUTH_WALL_HINT_SCRIPT) is False
    finally:
        pages.close()


def test_visible_login_form_is_an_auth_wall() -> None:
    pages = _browser_page()
    page = next(pages)
    try:
        page.set_content(
            """
            <main><h1>Sign in</h1>
              <form><label>Email <input type="email"></label>
                <label>Password <input type="password"></label>
                <button type="submit">Sign in</button></form>
            </main>
            """
        )
        assert page.evaluate(AUTH_WALL_HINT_SCRIPT) is True
    finally:
        pages.close()


def test_visible_oauth_login_wall_without_password_remains_an_auth_wall() -> None:
    pages = _browser_page()
    page = next(pages)
    try:
        page.set_content(
            """
            <main><h1>Sign in</h1><p>Continue to your account.</p>
              <button type="button">Continue with Google</button>
            </main>
            """
        )
        assert page.evaluate(AUTH_WALL_HINT_SCRIPT) is True
    finally:
        pages.close()


def test_login_form_below_initial_viewport_can_still_be_an_auth_wall() -> None:
    pages = _browser_page()
    page = next(pages)
    try:
        page.set_content(
            """
            <header style="height:1100px">Product hero</header>
            <main><h1>Sign in</h1>
              <form><label>Email <input type="email"></label>
                <label>Password <input type="password"></label>
                <button type="submit">Sign in</button></form>
            </main>
            """
        )
        assert page.evaluate(AUTH_WALL_HINT_SCRIPT) is True
    finally:
        pages.close()
