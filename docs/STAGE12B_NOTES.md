# Stage 12b notes - WHALE-inspired baseline vs the live guard (open cases 1-6)

Pre-registration: `docs/STAGE12B_PLAN.md` (dual thresholds + decoy rule fixed BEFORE the run; see
its "Deviations from pre-registration" section for the one post-run fix). Runner:
`lab/run_stage12b.py`. 5 reps per cell at windows 3 / 5 / 10 s; **every cell was unanimous across
the 5 reps** - all five runs agreed on the outcome in every case x config x window. Lab-only,
fictional brands, fake credentials.

## Setup
- Baseline configs (cumulative): **(a)** static dual-threshold only; **(b)** bounded-window
  ABLATION of the live guard (real credentials, judged by `score_send >= 60`, stops after the
  window); **(c)** static + generic decoy probe + bounded window. **Live guard** = always-on,
  unbounded (QuishGuard).
- Static stage is INTERIM (`score_send` weights applied at load). NOTE: the Stage 13 model is NOT a
  usable drop-in here - it is an 87-feature URL classifier (incl. whois / domain-age / web-traffic /
  PageRank) trained on real phishing DOMAINS; our lab pages are all on 127.0.0.1, so its external
  features do not exist and its URL features cannot separate same-host lab pages. The Stage 13 model
  is evaluated on real URLs (its own Mendeley test split, Stage 13), not the localhost lab. Window described in the paper as "near WHALE's reported average dynamic runtime
  (~4.2 s)", NOT "WHALE's window".

## Result  (B = blocked attack, M = missed attack, . = harmless allowed, F = harmless FALSE-block)

Outcomes at 3 s and 5 s are identical (both below the 8 s delay); the delayed form flips at 10 s.

| case | live | (a) static | (b) bounded | (c) decoy |
|---|---|---|---|---|
| Early send | B | B | B | B |
| Pixel keylogger | B | B | B | B |
| Hook evasion | B | B | B | B |
| **AiTM (brand)** | B | B | B | B |
| Linking-code lure (brand) | B | M | B | B |
| **Delayed form (8 s)** | B | M | M @3/5s, **B @10s** | M @3/5s, **B @10s** |
| **CAPTCHA + WebSocket** | B | M | **B** (real user solves) | **M** (decoy can't solve) |
| **Linking-code (no brand)** | **M** | M | M | **B** (behavioural decoy) |
| **AiTM (no brand)** | M | M | M | M (genuine 401) |
| **Decoy-aware (OC2)** | **B** (1.6 s) | M | **B** (real user) | **M** (decoy hides) |
| harmless twins (11, incl. promo/postal/decoy_aware_benign/sso_benign) | . | . | . | . |
| **signup_benign (accept-any)** | . | . | . | **F** |

The **branded AiTM is blocked at the STATIC stage** (impersonation, score 70) in configs a/b/c,
so its decoy stage never runs. Therefore **hypothesis 6 (the decoy probe fooled by a genuine 401)
was exercised ONLY on the no-brand AiTM**, which reaches the decoy stage and is read "auth error
-> benign" (missed). The branded AiTM cannot test hypothesis 6.

## Time-until-usable (median of 5 runs; all 5 runs agreed on outcome)
- **(a) static:** 0.0 s for every case - the static verdict is immediate, and a block lands
  BEFORE the user types.
- **(b) bounded:** static blocks 0.0 s; runtime blocks = time-to-verdict (immediate-exfil attacks
  ~0.1-0.4 s; the delayed form ~8.7 s inside the 10 s window); allowed pages wait the FULL window
  (e.g. 10.0 s at the 10 s setting) - the latency cost of a bounded watch.
- **(c) decoy:** static blocks 0.0 s; decoy verdicts = time-to-verdict (cross-site leak / accept /
  error, ~0.1 s; the delayed form ~8.1 s); allowed benign pages wait the full window EXCEPT where
  an early signal fires (the benign CAPTCHA resolves ~0.1 s on the gate error); `signup_benign`
  false-blocks at ~0.0 s.
- **live guard:** no added wait for allowed pages (0.0 s); caught attacks = time-to-block
  (immediate ~0.1 s; the delayed form ~8.8 s - the guard waits for the send, not a window).

## Findings (RQ3 - coverage of the open cases)
1. **Static-only (a) misses every behavioural attack** - it catches only the 4 brand-impersonation
   logins visible at load. Consistent with Stage 14: most forms do not reveal their destination at
   load.
2. **A bounded window is evadable by delay.** Configs (b)/(c) catch the 8 s delayed form ONLY when
   the window exceeds the delay (missed at 3/5 s, caught at 10 s). An attacker simply waits longer;
   the always-on guard catches it at any delay (blocked at the send). This is the core argument for
   a runtime (not time-boxed pre-release) defence.
3. **The decoy probe cannot pass an unsolvable CAPTCHA** - config (c) misses the distorted-CAPTCHA
   page at every window, while config (b) catches it because a REAL user solves the gate within the
   window. A real (b)-vs-(c) separation.
4. **Hypothesis 6 (realistic AiTM), tested on the no-brand AiTM only:** the relay forwards the decoy
   to the real bank, which returns a genuine 401, so the decoy rule reads "authentication error ->
   benign" and config (c) misses it. The live guard also misses the no-brand AiTM (score 20). The
   branded AiTM is caught earlier, at the static stage.
5. **The behavioural decoy (c) out-detects the live guard on the no-brand lure** (score 50 < 60):
   a case where the WHALE-style baseline catches what the live guard misses. Report it, don't hide it.
6. **False positive.** Config (c) false-blocks a legitimate ACCEPT-ANY sign-up page (`signup_benign`)
   via the "accepts" branch, at every window - the honest cost of the stronger (same-origin-aware)
   decoy rule. Configs (a)/(b) and the live guard have ZERO false blocks on all harmless twins.
7. **Decoy-/sandbox-aware page (open case 2): the pre-release probe MISSES it, the runtime guard
   CATCHES it.** `decoy_aware_leak.html` reveals its Formosa login only when `navigator.webdriver`
   is false, so config (c)'s decoy probe (Playwright default = true) sees only the benign "device
   check" page and MISSES it (timeout at every window). The live guard and config (b) run the
   real-user profile (`webdriver` spoofed false, pre-registered as option b), so the page reveals
   itself and the send is judged with the live title. The block is a BRAND-IMPERSONATION hit
   (title shows "Formosa" on a non-official origin = +50, plus cross-site +30 -> score 70 >= 60);
   both the live guard and config (b) BLOCK (~1.6 s). It is caught because the page impersonates
   the bank once revealed, not by any webdriver signal of ours.
   Static-only (a) misses it (nothing sensitive at load). This is the sharpest (b)-vs-(c)
   separation in the matrix and the direct argument for a defence that runs IN the real session:
   anti-analysis pages defeat a time-boxed pre-release probe by construction.
8. **SSO/OAuth benign (cross-origin login to a trusted IdP): no false alarm from QuishGuard, one
   from the reuse baseline.** `sso_benign.html` posts the bank password cross-origin to the trusted
   identity provider (:8000). The live guard and configs (a)/(b)/(c) ALLOW it (destination is an
   OFFICIAL/trusted origin, score 50 < 60 - cross-origin alone is not enough to block). The
   password-reuse baseline's verdict depends on WHERE the password is typed. In a REALISTIC SSO
   flow the relying app holds no password: it redirects to the IdP's own origin (:8000), the
   password is typed THERE (an official origin), and the send is same-origin to :8000. With that
   flow, BOTH the live guard and the reuse baseline ALLOW `sso_benign` (no false alarm). An
   earlier version typed the password on the relying origin (:8003) and the reuse baseline
   false-alarmed - that `F` was a LAB ARTIFACT of the unrealistic page, now fixed (see
   `lab/bank_sso.html`, `lab/attacks/sso_benign.html`). CAVEAT: the live guard's ALLOW rests on
   the IdP origin being in the trusted list (`OFFICIAL_ORIGINS["Formosa Demo Bank"]` = :8000).
   A federated login to an IdP NOT on that list would be judged cross-site/untrusted; the
   trusted-origin list is the policy input that makes benign SSO distinguishable from exfil.

## Stage 12c - password-reuse baseline (prior art: Password Alert / Enhanced Phishing Protection)

A fourth column (pre-registered in `STAGE12B_PLAN.md`): ALERT when the known bank password
(`Lab-Pass-4821`) is typed or sent on a non-official origin. 5 unanimous reps.
- CATCHES the password-carrying attacks: Early send, Pixel, CAPTCHA, Hook, AiTM (brand),
  **AiTM (no brand)**.
- MISSES every non-password secret: the delayed OTP form and BOTH linking-code lures - a
  password-reuse detector is blind to OTPs, linking codes and card numbers by construction.
- One FALSE POSITIVE: `reuse_benign` (a legitimate third-party login where the user reuses the
  bank password) - the classic weakness of reuse detection: it cannot tell legitimate reuse
  from phishing. (A realistic SSO login is NOT a false positive here: the password is typed on
  the IdP's own official origin, so the reuse check does not fire - see finding 8.)
- vs QuishGuard: the reuse baseline BEATS QuishGuard on exactly ONE case, the **no-brand AiTM**
  (the reused password leaves to a non-official origin, which QuishGuard's score of 20 misses).
  QuishGuard beats it on the delayed OTP and the (brand) linking-code lure, and has zero false
  positives. BOTH miss the no-brand LURE (it carries a linking code, not the reused password).

Takeaway: send-time protection of a single KNOWN password is narrow (no OTP / linking-code /
card cover) and noisy (false-positives on legitimate reuse); QuishGuard protects ANY typed
secret and scores the page, not just the password value.

## Where the baseline is BETTER (not just worse)
- The static stage blocks the 4 impersonation logins BEFORE the user types (time 0), and the decoy
  probe never lets REAL credentials reach the page; the live guard holds the real send at submit
  time (real credentials were typed into the page first).
- Time-until-usable trades latency for proactivity (see the section above): static = instant,
  bounded configs = up to the window for allowed pages, live guard = no added wait.

## Limitations / honest framing
- "WHALE-INSPIRED", not WHALE: the static stage is `score_send`'s hand-picked weights, not WHALE's
  54-feature model - do NOT claim parity with WHALE's accuracy. Static stage to be replaced in
  Stage 13/15.
- Detection vs prevention kept separate; the live guard's catches are prevention (the send is
  actually stopped on the supported channels).
- The decoy rule is aggressive (any cross-site decoy exfil = malicious): no FP in the lab because
  harmless twins post same-origin, but a real benign page that legitimately posts cross-site could
  false-positive.
- Fake-rejection evasion (pre-registered, intended): a kit staging a fake "wrong password" on the
  first try is judged benign by config (c) - WHALE's own "imitate benign validation and retry"
  limitation.
- Numbers are from one lab, 5 unanimous reps per cell, windows 3/5/10 s; not a measured accuracy on
  real traffic.

## Deviations from pre-registration
One post-run fix (the `otp_late_benign` config (c) false-positive) aligned the runner code with the
pre-registered rule (compare credential fields PRE-submit, not pre-load); it changed no attack
outcome. Full what/why/when/before-after in `docs/STAGE12B_PLAN.md` -> "Deviations from
pre-registration".
