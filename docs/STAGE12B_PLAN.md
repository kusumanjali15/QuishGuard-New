# Stage 12b plan - WHALE-inspired baseline vs the live guard (PRE-REGISTERED)

Written BEFORE any run. The dual thresholds and the decoy decision rule below are
FIXED and will NOT be changed after seeing results.

## What we compare
A WHALE-INSPIRED baseline (NOT a reimplementation of WHALE's 54-feature model) against
the live, always-on guard (QuishGuard), across open cases 1-6, on the lab attack pages
and their harmless twins. The baseline runs in three cumulative configs:
- (a) static only
- (b) bounded-window ABLATION of the live guard (real credentials)
- (c) static + decoy-credential probe + bounded window

## Observation window
Configurable; default 5000 ms; swept at 3000 / 5000 / 10000 ms. In the paper this is
described as "near WHALE's reported average dynamic runtime (~4.2 s)", NOT "WHALE's window".

## Static stage (INTERIM - to be replaced by the Stage 13 model)
Reuses the existing `score_send` weights (untrusted 20, impersonation 50, cross_site 30,
scan_mismatch 30) applied to what is visible AT LOAD:
- untrusted: page origin is not a known official origin.
- impersonation: a protected brand in the title AND a password / one-time-code field
  present at load (same condition as the load-time check).
- cross_site: a form action declared at load that resolves to a different origin.
- scan_mismatch: as in score_send; not exercised in these runs.

### Dual thresholds (FIXED)
- static score >= 70  -> BLOCK (confident malicious; blocks BEFORE the user types).
- static score <  20  -> ALLOW and skip the dynamic stage (confident benign: clean,
  on an official origin).
- 20 <= static score < 70 -> UNCERTAIN -> dynamic stage (configs b, c).
  In config (a) there is no dynamic stage, so UNCERTAIN defaults to ALLOW.

Note: with this interim static stage the confident-benign band is narrow, so most pages
reach the dynamic stage. The Stage 13 model is expected to widen it.

## Dynamic stage
### (b) bounded-window ablation of the live guard (real credentials)
NOT WHALE-like - this is the LIVE GUARD with a time bound, to isolate the "bounded vs
unbounded" variable. Within the window it holds and judges the page's OWN real-credential
sends by the SAME rule as the live guard (score_send >= BLOCK_THRESHOLD = 60); it STOPS at
the end of the window, after which sends pass. Real credentials reach the page.

### (c) static + decoy probe + bounded window
Within the window, actively submit DECOY credentials into the page's fields and watch
where they go; STOP at the end of the window. Real credentials never reach the page.

### Generic decoy probe (config c) - one heuristic, no per-page code
The same heuristic drives every page (documented BEFORE the first run):
- Fields: every VISIBLE <input> of a fillable type is filled with a decoy by role -
  type=password -> decoy password; autocomplete=one-time-code or name/placeholder/id
  matching /otp|code|pin/ -> decoy code; text/email/tel/untyped -> decoy identifier.
  Decoy values: decoy_user_00 / Decoy-Pass-0000 / 000000 (NEVER the real lab creds).
- Submit: click the first VISIBLE <button> or input[type=submit] whose text matches
  /sign ?in|log ?in|continue|submit|verify|next|view|apply/, else the first visible button.
- Retry within the window: if no fillable input or submit target is present yet, retry every
  200 ms until one appears or the window ends (so a delayed form that appears BEFORE the
  window ends is still probed).
Observation within the window: decoy_left_cross_site = a request to a non-page, non-official
origin carries a decoy value; auth_error = the submit response status is 401/403/400 OR the
post-submit page shows an error marker; accepts = no error AND a new password/one-time-code/
card field appears or a success marker shows. Verdict by the ordered rule below.

### Decoy decision rule (FIXED)
After the decoy submit, within the window, evaluate IN THIS ORDER (first match wins):
1. MALICIOUS if a decoy value appears in an outgoing request whose destination origin is
   NEITHER the page's origin NOR a known official / trusted origin (decoy leaves cross-site).
2. BENIGN if an AUTHENTICATION ERROR is detected - the page rejected the decoy.
3. MALICIOUS if the page ACCEPTS the decoy - no error, and it advances.
4. BENIGN if the window ends with no submit (no reachable submit target: a delayed form not
   yet present, or an unsolvable CAPTCHA).

Why stronger than destination-only: rule 3 catches SAME-ORIGIN credential harvesting (a kit
that accepts the decoy and advances), which the old rule wrongly called benign and which
matters because 68% of forms in our Stage 14 data post to their own URL (WHALE states it
handles same-page harvesting). Rules 2+3 also make hypothesis 6 testable: a realistic AiTM
forwards the decoy to the real bank, which returns a genuine "wrong password", so rule 2
fires and the decoy probe calls the AiTM BENIGN (misses it) - only the live guard catches it.

"AUTHENTICATION ERROR" is detected (any of), within the window after the submit:
- the submit's HTTP response status is a failure (401 / 403, or 400 with an error body); OR
- the post-submit page shows an error marker: visible text matching
  /incorrect|invalid|wrong|failed|denied|not recognized|try again/i, or the same login form
  re-rendered carrying such a message.

"ACCEPTS THE DECOY" is detected (any of), and ONLY when no authentication error was detected:
- the page advances to a NEW credential / verification step - a password, one-time-code, or
  card-number field appears that was NOT present before the submit, or the form is replaced
  by a different one; OR
- the page shows a success marker: visible text matching
  /success|welcome|logged ?in|verified|dashboard|approved/i, or a 2xx response with no error
  marker plus a navigation / URL change.

Caveat (for the paper, not a change to the rule): rule 1 is aggressive - ANY cross-site
decoy exfil counts malicious. In the lab the harmless twins send same-origin, so no false
positives here; on real pages that legitimately post cross-site it could.

Known evasion (intended, not a bug): a kit that shows a FAKE "wrong password" on the first
submit is judged BENIGN by rule 2 - the decoy probe cannot tell a real rejection from a
staged one. This matches WHALE's own stated "imitate benign validation and retry" limitation.

## What we report, per open case x per config (+ the live guard)
1. Outcome: BLOCK / MISS; for harmless twins, false BLOCK.
2. Blocks-before-typing: does it stop the attack before real credentials would be typed?
   (static block = yes; dynamic = no.)
3. Real-credentials-reach-the-page: yes / no (decoy-only config (c): no).
4. Time-until-usable: report BOTH - the FULL window for ALLOWED pages (not declared safe
   until the window ends) AND the ACTUAL time-to-verdict for BLOCKED pages (e.g. a cross-site
   decoy leak / accept / error seen at 1.2 s -> 1.2 s). Static block = instant verdict; live
   guard = no added wait, only the sensitive send is held.

## Hypothesis (to be confirmed, not asserted)
- Bounded configs (b, c) MISS the past-window delayed form (8 s > window); config (c)
  MISSES the distorted-CAPTCHA page (a decoy probe cannot solve it). The live guard catches both.
- Hypothesis 6 (realistic AiTM - page served by the relay origin, same-origin post, relay
  forwards server-side to the bank and returns its genuine response): the decoy gets a real
  "wrong password" (rule 2) so config (c) calls it BENIGN (MISS). The live guard still blocks
  it; which signal does so is REPORTED from the rerun, not assumed here.
- The baseline is BETTER where the static stage blocks a brand-impersonating login at load
  (before typing; real creds never entered), and where config (c)'s behavioural decoy rule
  catches the no-brand lure that the live guard's score (50 < 60) misses.

---

## Stage 12c pre-registration: password-reuse baseline (RQ3 / E3)

A fourth comparison column (prior art: SpoofGuard / AntiPhish / Google Password Alert /
Microsoft Enhanced Phishing Protection), FIXED before the run.
- "Known" password = the lab bank credential `Lab-Pass-4821` (previously used on the official
  bank origin http://127.0.0.1:8000).
- ALERT (block) when that known value is TYPED into a field, OR appears in a send, on ANY
  non-official origin (anything other than :8000).
- It does NOT cover OTPs, linking codes, card numbers, or brand-new passwords - only the one
  known password.
- Victim password choice (fixed): the user reuses the bank password on pages that ask for a
  login (all attack pages model this), and on ONE dedicated harmless page where legitimate
  reuse is modelled (`reuse_benign`); on the other harmless twins the user uses a DIFFERENT
  password (good hygiene, no reuse).
- False positive = an alert on a harmless page: `reuse_benign` (a legitimate third-party login
  where the user reuses the bank password) - report it.
- Expected (to confirm by the run, not asserted): catches the password-carrying attacks
  (Early, Pixel, CAPTCHA, Hook, AiTM brand + no-brand); misses the non-password ones
  (Delayed = OTP, both linking-code lures); one false positive (`reuse_benign`). It BEATS
  QuishGuard on the NO-BRAND AiTM (the reused bank password leaves to a non-official origin,
  which QuishGuard's score of 20 misses). It does NOT beat QuishGuard on the no-brand LURE:
  that carries a linking code, not the password, so a password-reuse detector is blind to it
  (both miss).

---

## Stage 11 open case 2 - decoy-/sandbox-aware page (pre-registered choice)

The attack page keys on `navigator.webdriver`: for an automated session (a decoy probe / sandbox)
it reveals NOTHING (stays a benign "Verifying your device..." page); for a non-automated session
it reveals a Formosa login and exfiltrates cross-site.
CHOICE (option b, fixed before the run): the REAL-USER victim - config (b), the live guard and the
password-reuse baseline - runs with `navigator.webdriver` spoofed FALSE (a stand-in for a human on
a real device); the decoy probe (config c) keeps the Playwright default (true). We do NOT key the
page only on webdriver while leaving our victim as a default Playwright client, because our victim
is also automation and the page would then hide from the live guard too.
Expected (to confirm, not asserted): config (c) decoy probe MISSES it (sees only the benign page);
config (b), the live guard and the reuse baseline CATCH it (the page reveals the login and the real
send is judged with the live title = Formosa, score 70). Static-only (a) MISSES it (nothing
sensitive at load). The point: a page that detects pre-release dynamic analysis is caught by a
defence that runs in the REAL session, not before it.

## Static stage: decision (resolves the "use the Stage 13 model?" question)

The 12b/12c static stage uses the interim `score_send`; the Stage 13 model is NOT swapped in for
the LAB run. This is a DECISION, not a TODO, for three concrete reasons:
1. The Stage 13 model is an 87-feature classifier with 7 EXTERNAL features (whois, domain
   registration length, domain age, web traffic, DNS record, Google index, PageRank). None exist
   for 127.0.0.1 lab pages.
2. All lab pages share ONE host (127.0.0.1); its 56 URL-syntax features are identical across attack
   and benign pages, so a URL model cannot separate them by construction.
3. The model has no single-URL predict path; it trains/tests on the Mendeley benchmark's own split,
   where its evaluation lives (STAGE13_NOTES.md), on real domains.
The Stage 13 model therefore belongs on REAL URLs/pages (its Mendeley test split, done; and the
future DynaPD / real-capture evaluation), not the localhost lab. A learned static stage for the lab
would need real-domain pages, not 127.0.0.1.

DECISION (final, not a pending swap): the lab comparison KEEPS the rule-based `score_send` static
stage. Beyond the three reasons above, a model trained on real phishing pages would not transfer to
our small set of author-written lab pages (a different distribution with no real domains), so lab
numbers from it would measure transfer failure, not static-stage quality. The Stage 13 model's
accuracy is reported SEPARATELY on its own real-data test split (STAGE13_NOTES.md); it is not rerun
as the 12b/12c static stage. This supersedes any earlier "rerun 12b with the Stage 13 model" item.

---

## Deviations from pre-registration

1. **otp_late_benign false-positive fix** (2026-11-23, AFTER the first full run).
   - What changed: the config (c) "accepts -> a new credential field appeared" check in the runner.
   - Why: the code compared the credential-field state against the page's LOAD state, so the
     benign delayed-OTP twin's field simply *appearing* (it is injected ~8 s after load) counted
     as a "new step". The LOCKED rule says a new field "that was NOT present before the SUBMIT" -
     the comparison must be pre-SUBMIT, not pre-load. So this aligned the CODE with the
     pre-registered rule; the rule itself did not change.
   - When: after seeing the first full matrix (3/5/10 s), before committing.
   - Before: `otp_late_benign` -> F (false block) under config (c) at the 10 s window ONLY
     (unaffected at 3/5 s, where the 8 s form never appears within the window).
   - After: `otp_late_benign` -> allowed (.) at all windows. The only remaining config (c)
     false-block is `signup_benign` (the intended accept-any limitation). No ATTACK outcome
     changed at any window.
