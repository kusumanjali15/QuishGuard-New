"""Stage 14.5 helper: build label sheets WITH offline screenshots.

Renders each page's SAVED html with Playwright - JavaScript DISABLED and ALL network
requests BLOCKED (route.abort) - so nothing loads from the internet. Writes a PNG per
row to lab/label_shots/ and a `screenshot` column. Safe: the live (dead) phishing URLs
are never opened.

  python lab\\build_label_shots.py
"""

import asyncio
import re
import sys
from pathlib import Path

import pandas as pd
from playwright.async_api import Error as PwError
from playwright.async_api import async_playwright

from quishguard.detectors import LIGHT_DETECTORS, row_evidence
from quishguard.snapshots import input_summary, load_label_pool

HERE = Path(__file__).parent
SHOTS = HERE / "label_shots"
SUPP_DETECTORS = ["2a_captcha_widget", "2b_cloudflare_interstitial",
                  "3_non_credential_lure", "4_script_driven"]
N_RANDOM, SUPP_PER = 100, 20


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))[:120]


async def render_all(rows: pd.DataFrame) -> dict:
    """Render each row's html offline; return {id: screenshot_path}."""
    SHOTS.mkdir(exist_ok=True)
    paths = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for _, r in rows.iterrows():
            png = SHOTS / f"{_safe(r['id'])}.png"
            if png.exists() and "--refresh" not in sys.argv:
                paths[r["id"]] = str(png)
                continue
            ctx = await browser.new_context(java_script_enabled=False,
                                            viewport={"width": 412, "height": 915})
            page = await ctx.new_page()
            await page.route("**/*", lambda route: route.abort())   # block ALL network
            try:
                await page.set_content(r["html"] or "", wait_until="domcontentloaded", timeout=5000)
            except PwError:
                pass
            try:
                await page.screenshot(path=str(png), full_page=False, timeout=5000)
                paths[r["id"]] = str(png)
            except PwError:
                paths[r["id"]] = ""
            await ctx.close()
        await browser.close()
    return paths


def _context_cols(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "id": df["id"], "domain": df["domain"], "url": df["final_url"],
        "title": df["title"].fillna("").astype(str).str.slice(0, 200),
        "text": df["extracted_text"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.slice(0, 300),
        "input_fields": df["input_fields"].map(input_summary),
        "has_password_field": df["has_password_field"], "input_count": df["input_count"],
        "form_count": df["form_count"], "text_length": df["text_length"],
        "inline_scripts_bytes": df["inline_scripts_total_bytes"],
    })


async def main() -> None:
    pool_cache = HERE / "_label_pool.pkl"
    if pool_cache.exists() and "--refresh" not in sys.argv:
        print("Reusing cached pool (pass --refresh to re-download)...")
        pool = pd.read_pickle(pool_cache)
    else:
        print("Loading first-pages pool WITH html (a few hundred MB)...")
        pool = load_label_pool()
        pool.to_pickle(pool_cache)
    for name, fn in LIGHT_DETECTORS.items():
        pool[f"flag::{name}"] = fn(pool).astype(int).values

    random_set = pool.sample(n=min(N_RANDOM, len(pool)), random_state=7)
    supp_parts = []
    for name in SUPP_DETECTORS:
        flagged = pool[pool[f"flag::{name}"] == 1]
        s = flagged.sample(n=min(SUPP_PER, len(flagged)), random_state=11).copy()
        s["detector"] = name
        s["evidence"] = [row_evidence(r, name) for _, r in s.iterrows()]
        supp_parts.append(s)
    supp = pd.concat(supp_parts, ignore_index=True)

    to_render = pd.concat([random_set, supp]).drop_duplicates(subset="id")
    print(f"Rendering {len(to_render)} offline screenshots (JS off, network blocked)...")
    shots = await render_all(to_render)

    # labels.csv (100 random): context + screenshot + per-detector flag/evidence/truth
    out = _context_cols(random_set)
    out.insert(3, "screenshot", random_set["id"].map(shots).fillna(""))
    for name, fn in LIGHT_DETECTORS.items():
        flags = random_set[f"flag::{name}"].values
        out[f"flag::{name}"] = flags
        out[f"evidence::{name}"] = [row_evidence(random_set.iloc[i], name) if flags[i] else ""
                                    for i in range(len(random_set))]
        out[f"truth::{name}"] = ""
    out.to_csv(HERE / "labels.csv", index=False, encoding="utf-8-sig")

    # supplement: context + evidence + screenshot + single truth
    sout = _context_cols(supp)
    sout.insert(0, "detector", supp["detector"].values)
    sout["evidence"] = supp["evidence"].values
    sout["screenshot"] = supp["id"].map(shots).fillna("").values
    sout["flag"] = 1
    sout["truth"] = ""
    sout.to_csv(HERE / "labels_supplement.csv", index=False, encoding="utf-8-sig")

    print(f"wrote labels.csv ({len(out)}) + labels_supplement.csv ({len(sout)}); "
          f"screenshots in {SHOTS.name}/")


if __name__ == "__main__":
    asyncio.run(main())
