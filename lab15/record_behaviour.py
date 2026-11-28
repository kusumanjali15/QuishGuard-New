#!/usr/bin/env python3
"""Stage 15 shared recorder: drive a login flow (phishing kit OR benign app) with the SAME
victim + fill + submit core as lab14b/record_kit.py, logging client-observable BEHAVIOUR only.
Field metadata is TYPES/BOOLEANS only - never values.
  kit:    python lab15/record_behaviour.py --kit <kit-dir>                 (php -S; run DISCONNECTED)
  benign: python lab15/record_behaviour.py --url <login-url> --app <name>  (app already running)
"""
import argparse, asyncio, json, os, socket, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from playwright.async_api import async_playwright                 # noqa: E402
from quishguard.victim import PHONE, VICTIM_VALUES                # noqa: E402

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"; TRACES.mkdir(exist_ok=True)
SENDMAIL = ROOT / "lab14b" / "fake_sendmail.py"
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

FIELDS_JS = r"""() => {
  const inp = [...document.querySelectorAll('input, textarea, select')];
  const nm = el => ((el.name||'')+' '+(el.id||'')+' '+(el.getAttribute('autocomplete')||'')+' '+(el.placeholder||'')).toLowerCase();
  const m = re => inp.some(el => re.test(nm(el)));
  return {
    has_password: inp.some(el => (el.type||'').toLowerCase() === 'password'),
    has_otp: inp.some(el => el.getAttribute('autocomplete') === 'one-time-code')
             || m(/otp|one.?time|2fa|mfa|auth.?code|verif|sms.?code|security.?code|passcode|\bpin\b/),
    has_card: m(/card.?number|cardnum|cc.?num|credit.?card|\bpan\b|cvv|cvc|card.?code|exp.?(date|month|year)/),
    has_hidden_token: inp.some(el => (el.type||'').toLowerCase() === 'hidden'
                       && /token|csrf|nonce|_token|authenticit|xsrf/.test(nm(el))),
    n_inputs: inp.length,
    n_forms: document.querySelectorAll('form').length,
  };
}"""


def find_entry(kit):
    def depth(f): return len(f.relative_to(kit).parts)
    pages = [f for f in kit.rglob("*") if f.is_file()
             and f.suffix.lower() in (".php", ".html", ".htm") and f.stat().st_size < 1_000_000]
    pages.sort(key=depth)
    pw = []
    for f in pages:
        try: txt = f.read_text(errors="ignore").lower()
        except Exception: continue
        if 'type="password"' in txt or "type='password'" in txt or "type=password" in txt:
            pw.append(f)
    rel = lambda f: "/".join(f.relative_to(kit).parts)
    for f in pw:
        if f.name.lower().startswith("index."): return rel(f)
    if pw: return rel(pw[0])
    idx = [f for f in pages if f.name.lower().startswith("index.")]
    return rel(idx[0]) if idx else ""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def wait_port(port, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5): return True
        except OSError: time.sleep(0.1)
    return False


def carries_fake(text): return any(v in text for v in FAKE_VALUES)

EMPTY = {"has_password": False, "has_otp": False, "has_card": False,
         "has_hidden_token": False, "n_inputs": 0, "n_forms": 0}

def merge(acc, f):
    for k in ("has_password", "has_otp", "has_card", "has_hidden_token"):
        acc[k] = acc[k] or bool(f.get(k))
    for k in ("n_inputs", "n_forms"):
        acc[k] = max(acc[k], int(f.get(k, 0)))
    return acc


async def drive(url, settle_ms, headful):
    sends = []; forced = [False]; fields = dict(EMPTY)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful)
        ctx = await browser.new_context(**p.devices[PHONE]); page = await ctx.new_page()
        t0 = time.monotonic()
        def on_request(req):
            body = req.post_data or ""
            sends.append({"t_ms": round((time.monotonic()-t0)*1000), "method": req.method,
                          "url": req.url, "dest_host": urlsplit(req.url).netloc,
                          "carries_fake_value": carries_fake(req.url + " " + body), "post_len": len(body)})
        page.on("request", on_request)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        except Exception as e:
            sends.append({"error": f"goto failed: {e}"}); await browser.close(); return sends, False, fields
        for _step in range(6):
            try: await page.evaluate(FILL_JS, FAKE_FILL)
            except Exception: pass
            try: merge(fields, await page.evaluate(FIELDS_JS))
            except Exception: pass
            before = sum(1 for s in sends if s.get("method") == "POST")
            for sel in ("input[type=image]", "input[type=submit]", "button[type=submit]", "button", "input[type=button]"):
                try: await page.click(sel, timeout=1_200, no_wait_after=True); break
                except Exception: continue
            await page.wait_for_timeout(settle_ms)
            if sum(1 for s in sends if s.get("method") == "POST") == before:
                try:
                    n = await page.evaluate("() => { let n=0; for (const f of document.querySelectorAll('form')){ try{ f.submit(); n++; }catch(e){} } return n; }")
                    if n: forced[0] = True; await page.wait_for_timeout(settle_ms)
                except Exception: pass
            try: remaining = await page.evaluate("() => document.querySelectorAll('form input, form textarea').length")
            except Exception: remaining = 0
            if remaining == 0: break
        await browser.close()
    return sends, forced[0], fields


def run_kit(kit_dir, settle_ms, headful):
    kit = Path(kit_dir).resolve(); kit_id = kit.name
    port = free_port(); mail_log = TRACES / f"{kit_id}.mail.log"; mail_log.unlink(missing_ok=True)
    env = dict(os.environ, QG_MAIL_LOG=str(mail_log), QG_EXFIL_EMAIL="attacker@phishing.localhost")
    php = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(kit),
                            "-d", f"sendmail_path={sys.executable} {SENDMAIL}"],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(port): sys.exit("php -S did not start (is php-cli installed?)")
        entry = find_entry(kit); url = f"http://127.0.0.1:{port}/{entry}"
        print(f"[kit {kit_id}] entry: /{entry or '(root)'}")
        sends, forced, fields = asyncio.run(drive(url, settle_ms, headful))
    finally:
        php.terminate()
        try: php.wait(timeout=5)
        except Exception: php.kill()
    mail_raw = mail_log.read_text(errors="replace") if mail_log.exists() else ""
    return {"id": kit_id, "label": "phishing", "app": None, "entry": entry or "(root)", "sends": sends,
            "fields": fields, "forced_submit": forced, "mail_exfil_captured": bool(mail_raw.strip()),
            "front_end_carried_fake_value": any(s.get("carries_fake_value") for s in sends)}


def run_url(login_url, app, settle_ms, headful):
    print(f"[benign {app}] url: {login_url}")
    sends, forced, fields = asyncio.run(drive(login_url, settle_ms, headful))
    return {"id": app, "label": "benign", "app": app, "entry": login_url, "sends": sends, "fields": fields,
            "forced_submit": forced, "mail_exfil_captured": False,
            "front_end_carried_fake_value": any(s.get("carries_fake_value") for s in sends)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit"); ap.add_argument("--url"); ap.add_argument("--app")
    ap.add_argument("--flow", default="login"); ap.add_argument("--out")
    ap.add_argument("--headful", action="store_true"); ap.add_argument("--settle-ms", type=int, default=2500)
    a = ap.parse_args()
    if a.kit:
        trace = run_kit(a.kit, a.settle_ms, a.headful); stem = f"phishing_{trace['id']}"
    elif a.url and a.app:
        trace = run_url(a.url, a.app, a.settle_ms, a.headful); stem = f"benign_{a.app}_{a.flow}"
    else:
        sys.exit("use --kit <dir>  OR  --url <login-url> --app <name>")
    trace["flow"] = a.flow
    out = Path(a.out) if a.out else TRACES / f"{stem}.json"
    out.write_text(json.dumps(trace, indent=2))
    f = trace["fields"]
    print(f"  sends={len(trace['sends'])} fake_sent={trace['front_end_carried_fake_value']} "
          f"forced={trace['forced_submit']} "
          f"fields={{pw:{f['has_password']}, otp:{f['has_otp']}, card:{f['has_card']}, "
          f"tok:{f['has_hidden_token']}, inp:{f['n_inputs']}, forms:{f['n_forms']}}}")
    print(f"  trace: {out}")


if __name__ == "__main__":
    main()
