"""Stage 4: open a page like a phone and sign in with fake credentials."""

import time

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from quishguard.guard import Guard
from quishguard.netlog import RequestRecord, origin_of, record_from_playwright
from quishguard.rules import PageInfo
from quishguard.sensor import install_sensor

PHONE = "Pixel 7"  # Android profile: Chromium engine, same family as Android WebView


async def visit_and_login(
    url: str,
    username: str,
    password: str,
    headless: bool = True,
    record: list[RequestRecord] | None = None,
    guard: Guard | None = None,
    sensor: Guard | None = None,
) -> str:
    """Open url as a phone, fill the login form, submit it.

    Returns the URL the browser ends up on (after any redirects).
    If `record` is a list, every request the page starts is appended to it.
    If `guard` is given, every request is held and allowed or blocked (Stage 8).
    If `sensor` is given, sensor.js is injected into the page (Stage 10).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(**p.devices[PHONE])  # phone screen, touch, user agent
        if sensor is not None:
            await install_sensor(context, sensor)  # before any page exists
        page = await context.new_page()

        if record is not None:
            # Called by Playwright every time the page STARTS a request.
            page.on("request", lambda req: record.append(record_from_playwright(req)))

        if guard is not None:
            await page.route("**/*", guard.handle)   # hold EVERY request

        await page.goto(url)
        if guard is not None:
            guard.page = PageInfo(page.url, await page.title())
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)

        # Clicking submits the form, which navigates away (POST, then redirect).
        try:
            async with page.expect_navigation(timeout=4_000):
                await page.click('button[type="submit"]')
        except PlaywrightError:
            pass  # navigation was blocked by the guard: stay on the current page

        final_url = page.url
        await browser.close()
        return final_url


# Fake lab values the automated victim will type into sensitive fields.
VICTIM_VALUES = {
    'input[name="username"]': "demo_user_01",
    'input[type="password"]': "Lab-Pass-4821",
    'input[autocomplete="one-time-code"]': "123456",
    'input[name="code"]': "LINK-7788",   # Stage 11: app-linking code (non-credential scam)
    'input[name="promo"]': "SAVE10NOW",        # Stage 12b: harmless - must NOT be held
    'input[name="postal"]': "100045",          # Stage 12b: harmless - must NOT be held
    'input[name="country_code"]': "886",       # Stage 12b: harmless
}


async def visit_and_interact(
    url: str,
    headless: bool = True,
    guard: Guard | None = None,
    sensor: Guard | None = None,
    settle_ms: int = 0,
    pre_click: str | None = None,
    solve=None,
    window_s: float | None = None,
    human: bool = False,
) -> str:
    """Open a page like a phone, optionally wait for late content, then fill any
    sensitive fields present and submit. Used by the Stage 11 attack harness,
    where field names and timing vary from page to page.

    `solve`, if given, is an async callback(page) the LAB harness provides to pass
    a page-specific gate (e.g. a CAPTCHA). It is only a hook-point: the harness
    supplies the logic; no lab-specific code lives in this module.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(**p.devices[PHONE])
        if human:  # Stage 11 open-case-2: stand in for a real user (not an automated probe)
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
        if sensor is not None:
            await install_sensor(context, sensor)
        page = await context.new_page()
        if guard is not None:
            await page.route("**/*", guard.handle)

        await page.goto(url)
        if guard is not None:
            guard.page = PageInfo(page.url, await page.title())
        loaded = time.monotonic()                # Stage 12b: mark page-load for timing
        for g in (guard, sensor):
            if g is not None:
                g.loaded_at = loaded
                if window_s is not None:             # config (b): bound the watch window
                    g.deadline = loaded + window_s
        if settle_ms:
            await page.wait_for_timeout(settle_ms)  # let delayed forms appear
        if solve is not None:
            await solve(page)                        # lab-provided gate step (e.g. CAPTCHA)
        if pre_click and await page.query_selector(pre_click):
            await page.click(pre_click)              # pass a gate (e.g. CAPTCHA)
            await page.wait_for_timeout(500)         # let the real form appear

        # If a hand-off (e.g. SSO redirect) moved us to a NEW origin, re-read the page the
        # guard judges against - the in-page sensor runs per page, so this is faithful.
        if guard is not None and guard.page is not None and origin_of(page.url) != origin_of(guard.page.url):
            guard.page = PageInfo(page.url, await page.title())

        for selector, value in VICTIM_VALUES.items():
            if await page.query_selector(selector):
                await page.fill(selector, value)

        try:
            async with page.expect_navigation(timeout=4_000):
                await page.click("button")
        except PlaywrightError:
            pass  # no button, or send was blocked: nothing to navigate to

        final_url = page.url
        await browser.close()
        return final_url
