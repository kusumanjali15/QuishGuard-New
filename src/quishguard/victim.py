"""Stage 4: open a page like a phone and sign in with fake credentials."""

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from quishguard.guard import Guard
from quishguard.netlog import RequestRecord, record_from_playwright
from quishguard.rules import PageInfo

PHONE = "Pixel 7"  # Android profile: Chromium engine, same family as Android WebView


async def visit_and_login(
    url: str,
    username: str,
    password: str,
    headless: bool = True,
    record: list[RequestRecord] | None = None,
    guard: Guard | None = None,
) -> str:
    """Open url as a phone, fill the login form, submit it.

    Returns the URL the browser ends up on (after any redirects).
    If `record` is a list, every request the page starts is appended to it.
    If `guard` is given, every request is held and allowed or blocked (Stage 8).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(**p.devices[PHONE])  # phone screen, touch, user agent
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
            async with page.expect_navigation(timeout=10_000):
                await page.click('button[type="submit"]')
        except PlaywrightError:
            pass  # navigation was blocked by the guard: stay on the current page

        final_url = page.url
        await browser.close()
        return final_url
