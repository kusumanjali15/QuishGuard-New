"""Stage 12b: one table comparing three defences across every attack.

Columns:
  No protection          - does the secret reach the attacker at all?  (baseline)
  Load-time check        - does a pre-release / static snapshot catch it?  (Stage 12)
  QuishGuard stop layer   - does the runtime guard block the send?  (sensor + network)

Starts all five lab servers itself (127.0.0.1 only) - stop your own copies first.
Usage:  python lab\\run_comparison.py
"""

import asyncio
import contextlib
import csv
import io
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))

import attack_server, bank_server, collector_server, phish_server, ws_collector  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from quishguard.guard import Guard  # noqa: E402
from quishguard.loadcheck import load_time_check  # noqa: E402
from quishguard.netlog import origin_of  # noqa: E402
from quishguard.rules import ScanContext  # noqa: E402
from quishguard.victim import visit_and_interact  # noqa: E402

async def drive_captcha(page) -> None:
    """LAB-ONLY CAPTCHA solver. A human reads the distorted code off the image; our
    automated victim cannot OCR, so it reads the expected code from the lab-only
    window.__LAB_CAPTCHA_CODE hook that exists ONLY on lab test pages and is NEVER
    part of the sensor/guard. A blind decoy-credential probe has no such hook and
    cannot pass the gate (see tests/test_captcha_gate.py)."""
    code = await page.evaluate("() => window.__LAB_CAPTCHA_CODE || null")
    if not code:
        return
    await page.fill("#captcha_input", code)
    await page.click("#verify")
    await page.wait_for_timeout(200)


# Lab pages that need a gate solved before the login form appears.
SOLVERS = {"captcha_ws_leak.html": drive_captcha, "captcha_ws_benign.html": drive_captcha}

ATTACKER_LOG = ROOT / "logs" / "attacker.log"
PASSWORD, OTP, LINK_CODE = "Lab-Pass-4821", "123456", "LINK-7788"

# label shown in the table, page URL, kind, settle_ms, pre_click
ATTACKS = [
    ("Early send",          "beacon_leak.html",      0,    None),
    ("Pixel keylogger",     "pixel_leak.html",       0,    None),
    ("Delayed form",        "otp_late_leak.html",    3000, None),
    ("CAPTCHA + WebSocket", "captcha_ws_leak.html",  0,    None),
    ("Linking-code lure",   "link_scam_leak.html",   0,    None),
    ("Hook evasion",        "iframe_evade_leak.html", 0,   None),
    ("Linking-code (no brand)", "link_scam_nobrand_leak.html", 0, None),
]
BENIGN = [
    "beacon_benign.html", "pixel_benign.html", "otp_late_benign.html",
    "captcha_ws_benign.html", "link_scam_benign.html", "iframe_evade_benign.html",
    "promo_benign.html",
]
BENIGN_SETTLE = {"otp_late_benign.html": 3000}
BENIGN_CLICK = {}  # captcha twin now driven by the SOLVERS gate solver


class ExclusiveHTTPServer(HTTPServer):
    allow_reuse_address = False


def start_servers() -> None:
    ATTACKER_LOG.parent.mkdir(parents=True, exist_ok=True)
    ATTACKER_LOG.write_text("", encoding="utf-8")  # fresh log for a clean count
    for handler, port in [(bank_server.BankHandler, 8000), (phish_server.PhishHandler, 8001),
                          (collector_server.CollectorHandler, 8002), (attack_server.AttackHandler, 8003)]:
        handler.log_message = lambda *a: None
        try:
            srv = ExclusiveHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            sys.exit(f"Port {port} is busy - stop your lab servers first (Ctrl+C), then rerun.")
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(ws_collector.main()), daemon=True).start()


def log_lines() -> list[str]:
    return ATTACKER_LOG.read_text(encoding="utf-8").splitlines() if ATTACKER_LOG.exists() else []


def count_leaks(new: list[str]) -> int:
    return sum(1 for ln in new if any(s in ln for s in (PASSWORD, OTP, LINK_CODE)))


async def run_runtime(url: str, protect: bool, settle_ms: int, pre_click: str | None) -> tuple[int, bool, str]:
    """Run once, protection off or full. Returns (leaks, blocked, stopping_layer).

    The network guard is given NO harness secrets: it learns sensitive values from
    the in-page sensor through a shared `observed` set (Stage 12b, step 2).
    """
    observed: set[str] = set()
    sensor = Guard(scan=ScanContext(from_qr=True), observed=observed) if protect else None
    guard = Guard(scan=ScanContext(from_qr=True), observed=observed) if protect else None
    before = len(log_lines())
    solve = SOLVERS.get(url.rsplit("/", 1)[-1])
    with contextlib.redirect_stdout(io.StringIO()):
        await visit_and_interact(url, guard=guard, sensor=sensor, settle_ms=settle_ms,
                                 pre_click=pre_click, solve=solve)
    await asyncio.sleep(0.5)
    leaked = count_leaks(log_lines()[before:])
    sensor_stop = bool(sensor) and any("BLOCK" in ln or "dropped" in ln for ln in sensor.log)
    net_stop = bool(guard) and any("BLOCK" in ln for ln in guard.log)
    held = bool(sensor) and any(ln.startswith("HELD") for ln in sensor.log)
    layer = "sensor" if sensor_stop else ("network" if net_stop else "")
    return leaked, (sensor_stop or net_stop), layer, held


async def load_time_catches(page, url: str) -> bool:
    """True if the load-time snapshot check would flag this page."""
    await page.goto(url)
    title = await page.title()
    has_sensitive = await page.evaluate(
        """() => !!document.querySelector('input[type="password"], input[autocomplete="one-time-code"]')""")
    actions = await page.evaluate("""() => [...document.querySelectorAll('form[action]')].map(f => f.action)""")
    v = load_time_check(title, has_sensitive, [origin_of(a) for a in actions], origin_of(url))
    return v.decision == "block"


async def main() -> int:
    start_servers()
    await asyncio.sleep(0.5)
    base = "http://127.0.0.1:8003/"
    rows = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(**p.devices["Pixel 7"])
        lt_page = await ctx.new_page()

        for label, page_file, settle_ms, pre_click in ATTACKS:
            url = base + page_file
            leak_none, _, _, _ = await run_runtime(url, False, settle_ms, pre_click)
            lt = await load_time_catches(lt_page, url)
            leak_qg, blocked_qg, layer_qg, _ = await run_runtime(url, True, settle_ms, pre_click)
            rows.append({
                "scenario": label,
                "no_protection": "LEAK" if leak_none else "no leak",
                "load_time": "catch" if lt else "miss",
                "quishguard": "BLOCK" if (blocked_qg and leak_qg == 0) else ("LEAK" if leak_qg else "no leak"),
                "stopped_by": layer_qg if (blocked_qg and leak_qg == 0) else "",
            })

        # Harmless pages: count wrong blocks (false positives) per layer.
        lt_fp = qg_fp = 0
        held_names: list[str] = []
        for f in BENIGN:
            url = base + f
            settle_ms, pre_click = BENIGN_SETTLE.get(f, 0), BENIGN_CLICK.get(f)
            if await load_time_catches(lt_page, url):
                lt_fp += 1
            _, blocked, _, held = await run_runtime(url, True, settle_ms, pre_click)
            if blocked:
                qg_fp += 1
            if held:
                held_names.append(f.replace(".html", ""))
        await browser.close()

    n = len(BENIGN)
    rows.append({"scenario": "Harmless pages blocked", "no_protection": f"0/{n}",
                 "load_time": f"{lt_fp}/{n}", "quishguard": f"{qg_fp}/{n}", "stopped_by": ""})

    w1 = max(len(r["scenario"]) for r in rows)
    print(f"\n{'SCENARIO':{w1}}  {'No protection':13}  {'Load-time check':15}  {'QuishGuard (stop layer)':23}  stopped by")
    for r in rows:
        print(f"{r['scenario']:{w1}}  {r['no_protection']:13}  {r['load_time']:15}  {r['quishguard']:23}  {r['stopped_by']}")

    out = ROOT / "results" / "comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["scenario", "no_protection", "load_time", "quishguard", "stopped_by"])
        wr.writeheader(); wr.writerows(rows)
    HAS_REAL_SENSITIVE = {"beacon_benign", "pixel_benign", "captcha_ws_benign",
                          "iframe_evade_benign", "otp_late_benign"}
    wrong_holds = [h for h in held_names if h not in HAS_REAL_SENSITIVE]
    print(f"\nharmless pages HELD by the sensor: {len(held_names)}/{n}  "
          f"{sorted(held_names)}")
    print("  (holding a page with a real password/OTP field is by design: hold -> judge -> allow)")
    print(f"WRONG holds (no real sensitive field, should be none): {wrong_holds or 'none'}")
    print(f"saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
