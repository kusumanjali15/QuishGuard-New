"""Stage 12b step 6: the distorted-code CAPTCHA stops a BLIND automated victim.

A victim that can read the image passes the gate and reaches the login form; a
blind victim (just filling fields) cannot, so credentials can never be sent. Here
the "reading" is stood in for by the lab-only window.__LAB_CAPTCHA_CODE hook that
lives ONLY on lab test pages - never in the sensor/guard. This is what lets our
own victim drive the page while a decoy-credential probe cannot.

Run (lab can be stopped; this starts its own server on an ephemeral port):
    pytest tests/test_captcha_gate.py
"""

import asyncio
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
import attack_server  # noqa: E402

PAGE = "captcha_ws_leak.html"


def _start_server() -> HTTPServer:
    attack_server.AttackHandler.log_message = lambda *a: None
    srv = HTTPServer(("127.0.0.1", 0), attack_server.AttackHandler)  # ephemeral port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


async def _login_revealed(url: str, blind: bool) -> bool:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context(**p.devices["Pixel 7"])).new_page()
        await page.goto(url)
        if blind:
            await page.fill("#captcha_input", "00000")        # cannot read the distorted code
        else:
            code = await page.evaluate("() => window.__LAB_CAPTCHA_CODE")  # LAB-ONLY hook
            await page.fill("#captcha_input", code)
        await page.click("#verify")
        await page.wait_for_timeout(200)
        revealed = await page.is_visible('input[type="password"]')
        await browser.close()
        return revealed


def _run(blind: bool) -> bool:
    srv = _start_server()
    port = srv.server_address[1]
    try:
        return asyncio.run(_login_revealed(f"http://127.0.0.1:{port}/{PAGE}", blind))
    finally:
        srv.shutdown()


def test_hooked_victim_passes_captcha():
    assert _run(blind=False) is True


def test_blind_victim_cannot_pass_captcha():
    assert _run(blind=True) is False
