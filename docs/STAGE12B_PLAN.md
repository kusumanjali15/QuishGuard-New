# Stage 12b plan - WHALE-inspired baseline vs the live guard (PRE-REGISTERED)

Written BEFORE any run. The dual thresholds and the decoy decision rule below are
FIXED and will NOT be changed after seeing results.

## What we compare
A WHALE-INSPIRED baseline (NOT a reimplementation of WHALE's 54-feature model) against
the live, always-on guard (QuishGuard), across open cases 1-6, on the lab attack pages
and their harmless twins. The baseline runs in three cumulative configs:
- (a) static only
- (b) static + bounded window
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
### (b) static + bounded window
Within the window, hold and judge the page's OWN real-credential sends exactly as the
live guard does, but STOP at the end of the window; after the window, sends pass.

### (c) static + decoy probe + bounded window
Within the window, actively submit DECOY credentials into the page's fields and watch
where they go; STOP at the end of the window. Real credentials never reach the page.

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
