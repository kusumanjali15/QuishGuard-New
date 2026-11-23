"""Stage 12b runner: WHALE-inspired baseline (configs a/b/c) + the live guard, over the open
cases and harmless twins, at 3/5/10 s windows, N reps. See docs/STAGE12B_PLAN.md (pre-registered).

Starts the lab itself (via run_comparison.start_servers) - stop your own lab first.
  python lab\\run_stage12b.py --smoke     # shakedown: 1 rep, 5s, attacks only
  python lab\\run_stage12b.py             # full: configs a/b/c, 3/5/10s, 5 reps, +harmless

Outcome codes per run:  B = blocked (attack caught) | M = missed (attack allowed)
                        F = FALSE block (harmless blocked) | . = allowed (harmless ok)
"""

import argparse
import asyncio
import contextlib
import io
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lab"))
sys.path.insert(0, str(ROOT / "src"))

from playwright.async_api import async_playwright          # noqa: E402
import run_comparison as rc                                # noqa: E402
from quishguard.guard import Guard                         # noqa: E402
from quishguard.netlog import origin_of                    # noqa: E402
from quishguard.rules import ScanContext, TRUSTED_ORIGINS  # noqa: E402
from quishguard.victim import PHONE, visit_and_interact    # noqa: E402
from quishguard.whale_baseline import decoy_decision, static_decision, static_score_at_load  # noqa: E402

BASE = "http://127.0.0.1:8003/"
DECOY = {"user": "decoy_user_00", "pass": "Decoy-Pass-0000", "code": "000000"}
ERR_RE = re.compile(r"incorrect|invalid|wrong|failed|denied|not recognized|try again", re.I)
OK_RE = re.compile(r"success|welcome|logged ?in|verified|dashboard|approved|created", re.I)
SENS_JS = "() => !!document.querySelector('input[type=\"password\"], input[autocomplete=\"one-time-code\"]')"
FIELDS_JS = ("() => [...document.querySelectorAll('input')].filter(el =>"
             " el.type === 'password' || el.getAttribute('autocomplete') === 'one-time-code'"
             " || el.getAttribute('autocomplete') === 'cc-number')"
             ".map(el => el.type + '|' + (el.name||'') + '|' + (el.getAttribute('autocomplete')||''))")

PROBE_JS = r"""(d) => {
  const vis = el => el.offsetParent !== null || el.getClientRects().length > 0;
  const ins = [...document.querySelectorAll('input')].filter(vis);
  let filled = false;
  for (const el of ins) {
    const hay = ((el.name||'')+' '+(el.placeholder||'')+' '+(el.id||'')+' '+(el.getAttribute('autocomplete')||'')).toLowerCase();
    if (el.type === 'password') el.value = d.pass;
    else if (el.getAttribute('autocomplete') === 'one-time-code' || /otp|code|pin/.test(hay)) el.value = d.code;
    else if (['text','email','tel',''].includes(el.type)) el.value = d.user;
    else continue;
    el.dispatchEvent(new Event('input', {bubbles:true}));
    filled = true;
  }
  if (!filled) return false;
  const btns = [...document.querySelectorAll('button, input[type=submit]')].filter(vis);
  const re = /sign ?in|log ?in|continue|submit|verify|next|view|apply|create/i;
  const b = btns.find(x => re.test((x.textContent||x.value||''))) || btns[0];
  if (b) { b.click(); return true; }
  return false;
}"""


def url_of(pf):
    return pf if pf.startswith("http") else BASE + pf


def build_cases():
    attacks = [(lbl, url_of(pf), "attack", sm, pc) for (lbl, pf, sm, pc) in rc.ATTACKS]
    benign = [(pf.split("?")[0].replace(".html", ""), url_of(pf), "benign",
               rc.BENIGN_SETTLE.get(pf, 0), rc.BENIGN_CLICK.get(pf)) for pf in rc.BENIGN]
    benign.append(("signup_benign", BASE + "signup_benign.html", "benign", 0, None))
    return attacks, benign


def code(verdict, kind):
    if kind == "attack":
        return "B" if verdict == "block" else "M"
    return "F" if verdict == "block" else "."


async def static_run(browser, device, url):
    ctx = await browser.new_context(**device)
    try:
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        has_sens = await page.evaluate(SENS_JS)
        actions = await page.evaluate("() => [...document.querySelectorAll('form[action]')].map(f => f.action)")
        ao = origin_of(actions[0]) if actions else None
        score = static_score_at_load(url, title, has_sens, ao)
    finally:
        await ctx.close()
    return static_decision(score), score


async def decoy_run(browser, device, url, window_s):
    ctx = await browser.new_context(**device)
    page = await ctx.new_page()
    po = origin_of(url)
    st = {"leak": False, "autherr": False}

    def on_req(req):
        o = origin_of(req.url)
        if o != po and o not in TRUSTED_ORIGINS:
            blob = req.url + " " + (req.post_data or "")
            if any(x in blob for x in DECOY.values()):
                st["leak"] = True

    def on_resp(resp):
        with contextlib.suppress(Exception):
            if resp.request.method == "POST" and resp.status in (400, 401, 403):
                st["autherr"] = True

    page.on("request", on_req)
    page.on("response", on_resp)
    verdict, vt, submitted = None, None, False
    pre_fields: set = set()
    t0 = time.monotonic()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        while (time.monotonic() - t0) < window_s:
            if not submitted:
                with contextlib.suppress(Exception):
                    fields_at = set(await page.evaluate(FIELDS_JS))
                    submitted = await page.evaluate(PROBE_JS, DECOY)
                    if submitted:
                        pre_fields = fields_at   # credential fields present AT submit time
            txt = ""
            if submitted:
                with contextlib.suppress(Exception):
                    txt = (await page.inner_text("body")).lower()
            if st["leak"]:
                verdict, vt = "malicious", time.monotonic() - t0
                break
            if st["autherr"] or (submitted and ERR_RE.search(txt)):
                verdict, vt = "benign", time.monotonic() - t0
                break
            if submitted and not ERR_RE.search(txt):
                post_fields = set(await page.evaluate(FIELDS_JS))
                new_step = bool(post_fields - pre_fields)   # a NEW credential field after the submit
                if OK_RE.search(txt) or new_step:
                    verdict, vt = "malicious", time.monotonic() - t0
                    break
            await page.wait_for_timeout(150)
        if verdict is None:
            verdict = decoy_decision(submitted=submitted, decoy_left_cross_site=st["leak"],
                                     auth_error=st["autherr"], accepts=False)
            vt = window_s
    finally:
        await ctx.close()
    return ("block" if verdict == "malicious" else "allow"), vt


async def guard_run(url, settle_ms, solve, window_s):
    """Config (b) when window_s is set; the live guard when window_s is None."""
    sensor = Guard(scan=ScanContext(from_qr=True))
    guard = Guard(scan=ScanContext(from_qr=True))
    observed: set = set()
    sensor.observed = observed
    guard.observed = observed
    before = len(rc.log_lines())
    with contextlib.redirect_stdout(io.StringIO()):
        await visit_and_interact(url, guard=guard, sensor=sensor, settle_ms=settle_ms,
                                 solve=solve, window_s=window_s)
    leaked = rc.count_leaks(rc.log_lines()[before:]) > 0
    blocked = (any("BLOCK" in ln for g in (sensor, guard) for ln in g.log)
               or any("dropped" in ln for ln in sensor.log))
    loaded = next((g.loaded_at for g in (guard, sensor) if g.loaded_at), None)
    btimes = [g.blocked_at for g in (sensor, guard) if g.blocked_at is not None]
    if blocked and btimes and loaded is not None:
        vt = min(btimes) - loaded                    # time-to-verdict from page load
    elif window_s is not None:
        vt = window_s                                # allowed under a bounded window
    else:
        vt = 0.0                                     # live guard, allowed: no added wait
    return ("block" if (blocked and not leaked) else "allow"), vt


async def run_cell(browser, device, case, config, window_s):
    _, url, _, settle, _ = case
    solve = rc.SOLVERS.get(url.rsplit("/", 1)[-1])
    sdec, _ = await static_run(browser, device, url)
    if sdec in ("block", "allow"):
        return (sdec if sdec == "block" else "allow"), 0.0
    if config == "a":
        return "allow", 0.0                              # no dynamic stage
    if config == "b":
        return await guard_run(url, settle, solve, window_s)
    return await decoy_run(browser, device, url, window_s)


def cell_str(codes, times):
    med = statistics.median(times) if times else 0.0
    return f"{''.join(codes):<{len(codes)}}  {med:4.1f}s"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--windows", default="3000,5000,10000")
    ap.add_argument("--configs", default="a,b,c")
    args = ap.parse_args()
    if args.smoke:
        args.reps, args.windows = 1, "5000"

    reps = args.reps
    windows = [int(w) for w in args.windows.split(",")]
    configs = args.configs.split(",")

    rc.start_servers()
    await asyncio.sleep(0.5)
    attacks, benign = build_cases()
    cases = attacks if args.smoke else attacks + benign

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        device = p.devices[PHONE]

        print("\nLive guard (always-on, unbounded) - computed once per case:")
        live = {}
        for case in cases:
            codes, ts = [], []
            for _ in range(reps):
                v, vt = await guard_run(case[1], case[3], rc.SOLVERS.get(case[1].rsplit("/", 1)[-1]), None)
                codes.append(code(v, case[2]))
                ts.append(vt)
            live[case[0]] = cell_str(codes, ts)
            print(f"  {case[0]:28} {live[case[0]]}")

        for W in windows:
            w1 = max(len(c[0]) for c in cases)
            print(f"\n==== window {W/1000:g}s  (reps={reps}; codes B/M/F/.) ====")
            print(f"{'CASE':{w1}}  " + "  ".join(f"config {c:<10}" for c in configs) + "  live")
            fp = {c: [] for c in configs}
            for case in cases:
                cells = []
                for cfg in configs:
                    codes, ts = [], []
                    for _ in range(reps):
                        v, vt = await run_cell(browser, device, case, cfg, W / 1000)
                        codes.append(code(v, case[2]))
                        ts.append(vt)
                    cells.append(cell_str(codes, ts))
                    if case[2] == "benign" and any(x == "F" for x in codes):
                        fp[cfg].append(case[0])
                print(f"{case[0]:{w1}}  " + "  ".join(f"{c:<17}" for c in cells) + f"  {live[case[0]]}")
            print("harmless FALSE-blocked (per config): "
                  + "; ".join(f"{c}: {fp[c] or 'none'}" for c in configs))

        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
