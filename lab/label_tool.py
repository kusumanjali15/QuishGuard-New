"""Interactive labeller - no Excel needed. Saves after every answer.

  python lab\\label_tool.py          # label labels_supplement.csv (the 80 flagged rows)
  python lab\\label_tool.py --main   # label flagged rows in labels.csv (heuristic detectors)
  python lab\\label_tool.py --main --only 1a,5b   # only those detectors (name or prefix)

For each page: 1 = it really IS this characteristic, 0 = false flag, s = skip, q = save & quit.
You may type an optional note after the answer, e.g. `1 embedded turnstile` - saved to a notes column.
"""

import sys
import textwrap
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
QUESTIONS = {
    "2a_captcha_widget": "Real CAPTCHA / 'prove you're human' gate?",
    "2b_cloudflare_interstitial": "Cloudflare 'checking your browser' interstitial?",
    "3_non_credential_lure": "Asking for a CODE or PAYMENT (not a normal login)?",
    "4_script_driven": "Capture basically empty / JS-rendered (tiny text, no form)?",
    "1a_multi_step_no_password": "First step of a login (asks for email/username, no password yet)?",
    "5b_dead_weak": "Empty / parked / placeholder page?",
    "7_brand_mention": "Does the page actually use/impersonate that brand?",
}


def ask(detector: str, ctx: dict) -> tuple[str, str]:
    print("\n" + "-" * 72)
    print(f"detector : {detector}")
    print(f"url      : {ctx['url']}")
    print(f"title    : {ctx['title']}")
    print(f"evidence : {ctx['evidence']}")
    if ctx.get("screenshot"):
        print(f"screenshot: {ctx['screenshot']}   <- open this image to see the page")
    print(f"numbers  : {ctx['nums']}")
    print("text     : " + textwrap.shorten(ctx["text"], width=500, placeholder=" ..."))
    q = QUESTIONS.get(detector, f"Does this page really have '{detector}'?")
    while True:
        raw = input(f"\n{q}  [1/0/s/q; optional note after the answer]: ").strip()
        parts = raw.split(maxsplit=1)
        a = parts[0].lower() if parts else ""
        note = parts[1].strip() if len(parts) > 1 else ""
        if a in ("1", "0", "s", "q"):
            return a, note


def _nums(r, extra=True) -> str:
    base = f"pw={r.get('has_password_field')}, inputs={r.get('input_count')}, textlen={r.get('text_length')}"
    if extra:
        base += f", forms={r.get('form_count')}, jsbytes={r.get('inline_scripts_bytes')}"
    return base


def label_supplement() -> None:
    path = HERE / "labels_supplement.csv"
    df = pd.read_csv(path, dtype=str).fillna("")
    todo = list(df[df["truth"] == ""].index)
    print(f"{len(todo)} unlabelled of {len(df)} rows.")
    for i, idx in enumerate(todo, 1):
        r = df.loc[idx]
        print(f"\n[{i}/{len(todo)}]", end="")
        a, note = ask(r["detector"], {"url": r["url"], "title": r["title"], "evidence": r["evidence"],
                                      "screenshot": r.get("screenshot", ""), "nums": _nums(r), "text": r["text"]})
        if a == "q":
            break
        if a == "s":
            continue
        df.loc[idx, "truth"] = a
        if note:
            df.loc[idx, "notes"] = note
        df.to_csv(path, index=False, encoding="utf-8-sig")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nSaved {path.name}.")


def _only_filter() -> list[str] | None:
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            return [t.strip() for t in sys.argv[i + 1].split(",") if t.strip()]
    return None


def label_main(only: list[str] | None = None) -> None:
    path = HERE / "labels.csv"
    df = pd.read_csv(path, dtype=str).fillna("")
    focus = ["1a_multi_step_no_password", "2a_captcha_widget", "2b_cloudflare_interstitial",
             "3_non_credential_lure", "4_script_driven", "5b_dead_weak", "7_brand_mention"]
    if only:  # keep only detectors whose name matches a requested token (exact or prefix)
        focus = [d for d in focus if any(d == t or d.startswith(t) or t in d for t in only)]
        print(f"labelling only: {focus}")
    present = [c.split("::", 1)[1] for c in df.columns if c.startswith("flag::")]
    for det in [d for d in focus if d in present]:
        fcol, ecol, tcol = f"flag::{det}", f"evidence::{det}", f"truth::{det}"
        todo = list(df[(df[fcol] == "1") & (df[tcol] == "")].index)
        if not todo:
            continue
        print(f"\n==== {det}: {len(todo)} flagged rows ====")
        for i, idx in enumerate(todo, 1):
            r = df.loc[idx]
            print(f"\n[{i}/{len(todo)}]", end="")
            a, note = ask(det, {"url": r["url"], "title": r["title"], "evidence": r[ecol],
                                "screenshot": r.get("screenshot", ""), "nums": _nums(r, extra=False), "text": r["text"]})
            if a == "q":
                df.to_csv(path, index=False, encoding="utf-8-sig")
                print(f"\nSaved {path.name}.")
                return
            if a == "s":
                continue
            df.loc[idx, tcol] = a
            if note:
                df.loc[idx, f"notes::{det}"] = note
            df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nSaved {path.name}.")


if __name__ == "__main__":
    if "--main" in sys.argv:
        label_main(only=_only_filter())
    else:
        label_supplement()
