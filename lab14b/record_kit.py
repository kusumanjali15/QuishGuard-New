"""Stage 14b recorder: serve ONE DynaPD kit, drive it with our victim, record its behaviour.

Captures, per kit:
  - the FRONT-END sends the page makes when fake creds are submitted (every browser request:
    method, dest, whether it carries a fake value), via Playwright request logging; and
  - the kit's SERVER-SIDE exfil by email, via the sendmail capture (lab14b/fake_sendmail.py).

Nothing leaves the machine: mail() is captured by sendmail_path; run with the box DISCONNECTED
and after lab14b/egress_test.py prints ISOLATED (the real safety basis - this script does not
enforce the network boundary). Serves with `php -S` (no XAMPP); kits that need .htaccess rewrites
may not serve fully - noted per kit.

Usage:
  python lab14b/record_kit.py <kit-dir> [--out traces/<id>.json] [--headful] [--settle-ms 2500]
"""

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from playwright.async_api import async_playwright          # noqa: E402
from quishguard.victim import PHONE, VICTIM_VALUES         # noqa: E402

HERE = Path(__file__).resolve().parent
SENDMAIL = HERE / "fake_sendmail.py"
# the fake sensitive values we type - a send/mail "carries a fake value" if one appears in it
FAKE_VALUES = sorted({v for v in VICTIM_VALUES.values() if len(v) >= 4}, key=len, reverse=True)

FAKE_FILL = {"user": "demo_user_01", "pass": "Lab-Pass-4821", "otp": "123456",
             "code": "LINK-7788", "card": "4111111111111111"}
FILL_JS = r"""(d) => {
  const vis = el => el.offsetParent !== null || el.getClientRects().length > 0;
  let filled = 0;
  for (const el of document.querySelectorAll('input, textarea')) {
    if (!vis(el)) continue;
    const t = (el.type || '').toLowerCase();
    const hay = ((el.name||'')+' '+(el.id||'')+' '+(el.placeholder||'')+' '+(el.getAttribute('autocomplete')||'')).toLowerCase();
    if (t === 'password') el.value = d.pass;
    else if (el.getAttribute('autocomplete') === 'one-time-code' || /otp|token/.test(hay)) el.value = d.otp;
    else if (/card|cc-|cardnum/.test(hay)) el.value = d.card;
    else if (/code|pin/.test(hay)) el.value = d.code;
    else if (['text','email','tel',''].includes(t)) el.value = d.user;
    else continue;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    filled++;
  }
  return filled;
}"""


def find_entry(kit: Path) -> str:
    """URL path (relative to the kit root) of the login page: a file with a password field,
    preferring index.* and shallower paths. DynaPD kits bury the login deep in the tree, so we
    search. Returns '' (serve root) if nothing obvious is found. Reads files as text only."""
    def depth(f: Path) -> int:
        return len(f.relative_to(kit).parts)
    pages = [f for f in kit.rglob("*")
             if f.is_file() and f.suffix.lower() in (".php", ".html", ".htm")
             and f.stat().st_size < 1_000_000]
    pages.sort(key=depth)
    pw_pages = []
    for f in pages:
        try:
            txt = f.read_text(errors="ignore").lower()
        except Exception:
            continue
        if "type=\"password\"" in txt or "type='password'" in txt or "type=password" in txt:
            pw_pages.append(f)
    rel = lambda f: "/".join(f.relative_to(kit).parts)
    for f in pw_pages:                                  # a password-form index.* wins
        if f.name.lower().startswith("index."):
            return rel(f)
    if pw_pages:                                        # else shallowest password-form page
        return rel(pw_pages[0])
    idx = [f for f in pages if f.name.lower().startswith("index.")]
    return rel(idx[0]) if idx else ""                  # else shallowest index.*, else root


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port: int, timeout: float = 8.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def carries_fake(text: str) -> bool:
    return any(v in text for v in FAKE_VALUES)


async def drive(url: str, settle_ms: int, headful: bool) -> list[dict]:
    """Load the kit, submit fake creds, and return every browser request as a dict."""
    sends: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful)
        ctx = await browser.new_context(**p.devices[PHONE])
        page = await ctx.new_page()
        t0 = time.monotonic()

        def on_request(req):
            body = req.post_data or ""
            sends.append({
                "t_ms": round((time.monotonic() - t0) * 1000),
                "method": req.method,
                "url": req.url,
                "dest_host": urlsplit(req.url).netloc,
                "carries_fake_value": carries_fake(req.url + " " + body),
                "post_len": len(body),
            })
        page.on("request", on_request)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        except Exception as e:
            sends.append({"error": f"goto failed: {e}"})
            await browser.close()
            return sends

        # multi-step: fill + submit, then follow the kit's next-step pages (next1.php -> ... -> finish)
        for _step in range(6):
            try:
                await page.evaluate(FILL_JS, FAKE_FILL)
            except Exception:
                pass
            submitted = False
            for sel in ("input[type=image]", "input[type=submit]", "button[type=submit]", "button"):
                try:
                    await page.click(sel, timeout=1_500, no_wait_after=True)
                    submitted = True
                    break
                except Exception:
                    continue
            if not submitted:
                try:
                    await page.evaluate("() => { const f = document.querySelector('form'); if (f) f.submit(); }")
                except Exception:
                    pass
            await page.wait_for_timeout(settle_ms)
            try:
                remaining = await page.evaluate("() => document.querySelectorAll('form input, form textarea').length")
            except Exception:
                remaining = 0
            if remaining == 0:
                break
        await browser.close()
    return sends


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kit_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--settle-ms", type=int, default=2500)
    args = ap.parse_args()

    kit = Path(args.kit_dir).resolve()
    if not kit.is_dir():
        sys.exit(f"not a directory: {kit}")
    kit_id = kit.name
    out = Path(args.out) if args.out else (HERE / "traces" / f"{kit_id}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    port = free_port()
    mail_log = HERE / "traces" / f"{kit_id}.mail.log"
    mail_log.unlink(missing_ok=True)
    env = dict(os.environ, QG_MAIL_LOG=str(mail_log), QG_EXFIL_EMAIL="attacker@phishing.localhost")
    php = subprocess.Popen(
        ["php", "-S", f"127.0.0.1:{port}", "-t", str(kit),
         "-d", f"sendmail_path={sys.executable} {SENDMAIL}"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(port):
            sys.exit("php -S did not start (is php-cli installed?)")
        entry = find_entry(kit)
        entry_url = f"http://127.0.0.1:{port}/{entry}"
        print(f"[{kit_id}] entry: /{entry or '(root)'}")
        sends = asyncio.run(drive(entry_url, args.settle_ms, args.headful))
    finally:
        php.terminate()
        try:
            php.wait(timeout=5)
        except Exception:
            php.kill()

    mail_raw = mail_log.read_text(encoding="utf-8", errors="replace") if mail_log.exists() else ""
    trace = {
        "kit_id": kit_id,
        "kit_family": None,                 # fill from the dataset's family grouping in analysis
        "entry": entry or "(root)",
        "sends": sends,
        "mail_exfil_captured": bool(mail_raw.strip()),
        "mail_carried_fake_value": carries_fake(mail_raw),
        "front_end_carried_fake_value": any(s.get("carries_fake_value") for s in sends),
        "notes": "php -S has no .htaccess; verify the login page actually rendered.",
    }
    out.write_text(json.dumps(trace, indent=2))
    print(f"[{kit_id}] sends={len(sends)} "
          f"front_end_fake={trace['front_end_carried_fake_value']} "
          f"mail_exfil={trace['mail_exfil_captured']} mail_fake={trace['mail_carried_fake_value']}")
    print(f"  trace: {out}")
    print(f"  mail log (PRIVATE - may contain attacker address): {mail_log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
