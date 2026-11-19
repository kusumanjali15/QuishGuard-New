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
After the decoy submit, within the window:
- MALICIOUS (BLOCK) if a decoy value appears in an outgoing request whose destination
  origin is NEITHER the page's origin NOR a known official / trusted origin (the decoy
  leaves to a cross-site / untrusted destination).
- BENIGN (ALLOW) if the window expires without the decoy leaving to such a destination
  (not sent, or sent only same-origin / to an official origin).
A page that never exposes a submit target within the window (gated / delayed / unsolvable
CAPTCHA) therefore ends BENIGN by this rule - i.e. the attack is MISSED.

Caveat (for the paper, not a change to the rule): this rule is aggressive - ANY cross-site
decoy exfil counts as malicious. In the lab the harmless twins send same-origin, so it has
no false positives here; on real pages that legitimately post cross-site it could.

## What we report, per open case x per config (+ the live guard)
1. Outcome: BLOCK / MISS; for harmless twins, false BLOCK.
2. Blocks-before-typing: does it stop the attack before real credentials would be typed?
   (static block = yes; dynamic = no.)
3. Real-credentials-reach-the-page: yes / no (decoy-only config (c): no).
4. Time-until-usable: added latency before the page is usable (static block = instant
   verdict; bounded window = up to the window length; live guard = no added wait, only the
   sensitive send is held).

## Hypothesis (to be confirmed, not asserted)
- Bounded configs (b, c) MISS the past-window delayed form (8 s > window); config (c)
  MISSES the distorted-CAPTCHA page (a decoy probe cannot solve it). The live guard catches
  both.
- The baseline is BETTER where the static stage blocks a brand-impersonating login at load
  (before typing; real creds never entered), and where config (c)'s behavioural decoy rule
  catches the no-brand lure that the live guard's score (50 < 60) misses.
