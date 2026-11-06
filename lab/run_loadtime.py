"""Stage 12: run the LOAD-TIME STAND-IN check over every attack page.

Takes a snapshot right after load (no delay, no interaction) and reports which
attacks a pre-release-only check would catch vs miss.
Start the lab first:  python lab\\start_lab.py
Then:                 python lab\\run_loadtime.py
"""

import asyncio

from playwright.async_api import async_playwright

from quishguard.loadcheck import load_time_check
from quishguard.netlog import origin_of

PAGES = [
    ("beacon-on-blur", "http://127.0.0.1:8003/beacon_leak.html", "attack"),
    ("pixel keylogger", "http://127.0.0.1:8003/pixel_leak.html", "attack"),
    ("otp-appears-late", "http://127.0.0.1:8003/otp_late_leak.html", "attack"),
    ("captcha+websocket", "http://127.0.0.1:8003/captcha_ws_leak.html", "attack"),
    ("link-code scam", "http://127.0.0.1:8003/link_scam_leak.html", "attack"),
    ("iframe hook-evade", "http://127.0.0.1:8003/iframe_evade_leak.html", "attack"),
]


async def snapshot(page) -> tuple[str, bool, list[str]]:
    """What a load-time checker sees right after load."""
    title = await page.title()
    has_sensitive = await page.evaluate(
        """() => !!document.querySelector('input[type="password"], input[autocomplete="one-time-code"]')"""
    )
    actions = await page.evaluate(
        """() => [...document.querySelectorAll('form[action]')].map(f => f.action)"""
    )
    action_origins = [origin_of(a) for a in actions]
    return title, has_sensitive, action_origins


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(**p.devices["Pixel 7"])
        page = await context.new_page()

        print(f"\n{'ATTACK':18} {'LOAD-TIME CHECK':16} note")
        for name, url, _ in PAGES:
            await page.goto(url)                       # snapshot immediately, no delay
            title, has_sensitive, action_origins = await snapshot(page)
            v = load_time_check(title, has_sensitive, action_origins, origin_of(url))
            note = v.reasons[0] if v.reasons else "nothing visible to flag at load"
            print(f"{name:18} {v.decision.upper():16} {note}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
