# Stage 14 notes - load-time characteristics of real phishing

Source: `nyuuzyou/phishing-snapshots` (CC0), 136,414 headless-Chromium captures,
**July-August 2024**. PASSIVE / at-capture only: no interaction, no credential sends.
General phishing, **NOT** QR-reachable pages specifically. Numbers reported both
per-capture and per-loose-unique-kit (the dataset is ~84% duplicate pages).

## Key finding - static form action is not a usable destination signal

Among pages WITH a form action (n = 28,879):
- **empty / "#" / relative action: 68.27%** (95% CI 67.73-68.81) - destination unknown
  at load; JS decides at submit time and can send anywhere.
- **cross-site action: 19.75%** (19.29-20.21)
- **explicit same-site action: 11.98%** (11.61-12.36)

So for ~2/3 of pages with a form, the captured markup does not reveal where credentials
go, and among the pages that DO declare a destination, **cross-site (19.75%) exceeds
explicit same-site (11.98%)**. This undercuts any static-form-action analysis and supports
QuishGuard's runtime-interception approach: the send destination must be observed at
submit time, not read off the page.
(Caveat: form `action` at capture only; JS/AiTM sends are not in passive captures.)

## Other load-time prevalence (per-capture / per-unique-kit)

Tag: [DET] = deterministic (reads a dataset column; precision ~100% by construction,
report freely). [HEUR] = heuristic keyword/host/threshold match; precision NOT YET
VALIDATED - report as a detector FIRING rate, not confirmed prevalence (see Claim status).

- [DET]  password field present: 24.34% / 17.72%  (~ the dataset's has_password_field column)
- [HEUR] identifier field, no password (multi-step): 9.32% / 15.58%
- [DET]  no input fields at all: 49.67% / 46.64%
- [DET]  **live pages with no inputs at capture (open-case-1 pool): 26.15% / 37.15%**
- [HEUR] CAPTCHA widget (recaptcha/hcaptcha/turnstile or human-gate text): 4.18% / 4.22%
- [HEUR] Cloudflare interstitial: 3.13% / 1.83%
- [HEUR] non-credential lure (linking-code/payment, EN+zh-TW): 0.33% / 0.76%  (rare in en-dominated data)
- [HEUR] script-driven / empty at capture: ~1.3-2.0% (threshold-dependent)
- [DET]  dead/parked strong (HTTP>=400 or no HTML): 13.88% / 3.00%  (dead hosts heavily re-captured)
- [HEUR] dead/parked weak (low text / parked title): 19.64% / 10.24%
- [HEUR] brand mention (Check Point Q2-Q3 2024 top brands + LINE): 19.03% / 17.62%

## Claim status - detector precision (flagged supplement, measured 2026-11-17)

[DET] numbers above, and the form-action breakdown, are safe to report as prevalence.

[HEUR] detectors were precision-validated on the flagged supplement: 20 rows each that
the detector FIRED on, hand-labelled against the saved HTML rendered offline (JS off, all
network blocked). "Precision" = of the pages a detector flags, the fraction that genuinely
are that thing (Wilson 95% CI):

Per flagged row (n = rows labelled; 1 row of 2a was skipped - an invisible-reCAPTCHA
notice only, not a visible gate):

| detector | n | skipped | precision | 95% CI |
|---|---|---|---|---|
| 2a CAPTCHA widget          | 19 | 1 | 10.5% | 2.9-31.4 |
| 2b Cloudflare interstitial | 20 | 0 | 20.0% | 8.1-41.6 |
| 3 non-credential lure      | 20 | 0 | 40.0% | 21.9-61.3 |
| 4 script-driven            | 20 | 0 | 30.0% | 14.5-51.9 |

Per UNIQUE page (dedup by domain; several flagged rows are the same page/template repeated
- e.g. yenib508.top x5 in #3, sunebech.dk x3 in 2b, summit-dsm.com x2 in 2a):

| detector | unique n | precision | 95% CI |
|---|---|---|---|
| 2a CAPTCHA widget          | 18 | 11.1% | 3.1-32.8 |
| 2b Cloudflare interstitial | 17 | 17.6% | 6.2-41.0 |
| 3 non-credential lure      | 13 | 38.5% | 17.7-64.5 |
| 4 script-driven            | 18 | 33.3% | 16.3-56.3 |

Per-row and per-unique are close here, so the duplication did not materially bias precision;
both are reported so the reader can see that.

**These are low.** The raw [HEUR] firing rates OVERCOUNT: most flags are keyword/host
matches that are not the thing (a page that merely loads a Cloudflare CDN; "not a robot"
text that is not a gate; "payment" wording on a normal page).

firing_rate x precision is a ROUGH LOWER ESTIMATE of true prevalence, NOT a corrected
prevalence: it counts only pages the detector flagged AND got right and ignores pages the
detector MISSED (recall was never measured), so true prevalence is AT LEAST this (modulo
sampling):
- 2a captcha:      4.18% x 10.5% ~ >= 0.4% (very rough)
- 2b cloudflare:   3.13% x 20.0% ~ >= 0.6%
- 3 non-cred lure: 0.33% x 40.0% ~ >= 0.1%
- 4 script-driven: ~1.3-2.0% x 30.0% ~ >= 0.4-0.6%

So cite each [HEUR] figure as "detector flagged X%; precision ~P% (n<=20, wide CI)", never
as confirmed prevalence. With n=13-20 the CIs are very wide - these bound the order of
magnitude, not a precise value. The low precision is itself a finding: hand-written
keyword/host heuristics on raw phishing snapshots are noisy, which is exactly why accurate
detection needs real labelled data and trained models, not rules.

**Do NOT re-tune the detectors on these labels** - that would be fitting to the test set and
would invalidate these precision numbers. Any improved detector must be evaluated on a FRESH
labelled sample.

### Labeling protocol & codebook

Single annotator (the author); no second labeller, so no inter-annotator agreement was
measured - a limitation. Rows were judged against the saved HTML rendered offline (JS off,
all network blocked), not the live site. Rules applied:
- invisible reCAPTCHA notice only, no visible challenge -> skip (1 row, 2a).
- kit page with an embedded Turnstile / hCaptcha / reCAPTCHA widget -> 2a=1, 2b=0.
- fake Cloudflare / reCAPTCHA look-alike (imitation, not the real widget) -> 0.
- real Cloudflare ERROR page (451 / 522 etc.) -> 2b=0 (an error page, not a "checking your
  browser" challenge interstitial).
- fake-shop homepage with "credit card" only in the footer -> 3=0 (incidental mention, not a
  page asking for a code or payment).
- maintenance / under-construction placeholder -> 4=0 (a placeholder, not a JS-rendered kit).

STILL UNVALIDATED: the random 100-row sheet (`lab/labels.csv`) is NOT yet labelled, so the
common detectors not in the supplement (1a multi-step, 5b dead-weak, 7 brand mention) have
no precision estimate. Label `labels.csv` and rerun `--precision` to close that gap.

Note (both ways): even validated, these are DETECTED prevalence = a lower bound on true
prevalence, since recall (missed cases) was never measured; precision only bounds the
false-positive side.

## Dedup

Loose structural dedup -> 21,230 / 136,414 unique (16%). Loose may OVER-MERGE dead and
near-identical pages; exact-dedup (heavy sample) gives a conservative upper bound. True
distinct-page count sits between the two.

## Heavy-sample (descriptive, time-biased - earliest rows per shard)

- OC2 sandbox/automation probe (navigator.webdriver / userAgent in inline JS): ~6% (112-row sample; re-running at ~1000 for tighter CIs)
- exfil endpoint declared in inline JS (telegram/discord/mailto): ~1% (floor; most kits exfil server-side)

## Validation

The `1c_password_present` match to the dataset's 24.3% is NOT independent (same column).
The real check is the HTML parse verification (`--verify`): 0/30 mismatches on
has_password_field and input_count.
