"""Stage 4: open a page like a phone and sign in with fake credentials."""

from playwright.async_api import async_playwright

PHONE = "Pixel 7"  # Android profile: Chromium engine, same family as Android WebView


async def visit_and_login(
    url: str, username: str, password: str, headless: bool = True
) -> str:
    """Open url as a phone, fill the login form, submit it.

    Returns the URL the browser ends up on (after any redirects).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(**p.devices[PHONE])  # phone screen, touch, user agent
        page = await context.new_page()

        await page.goto(url)
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)

        # Clicking submits the form, which navigates away (POST, then redirect).
        async with page.expect_navigation():
            await page.click('button[type="submit"]')

        final_url = page.url
        await browser.close()
        return final_url
