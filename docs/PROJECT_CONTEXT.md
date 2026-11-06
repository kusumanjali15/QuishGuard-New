# QuishGuard - project context

Last updated: 2026-11-06 (after a full reading of the WHALE paper). Background for anyone
(human or Claude) working in this repo.

## The problem

QR phishing moves victims from protected email onto phones, where checks judge the **link**, not
what the page **does**. Blocklists miss new and per-victim URLs; pages hide from scanners
(cloaking, CAPTCHA, delayed forms); device-code lures and AiTM proxies use real login pages.
Every attack still has to **collect data and send it somewhere** - that behaviour is the signal
QuishGuard watches.

Local focus: Taiwan (TWQR payment fraud; LINE account takeover via "shared photos" QR + code lures).

## Closest prior work: WHALE (Sensors 2026, 26, 4412)

https://www.mdpi.com/1424-8220/26/14/4412 - QR-triggered, on-device Android WebView analysis.
Opens each QR-decoded URL in a sandbox WebView **before** the user sees it:
- Static stage: 54 URL/HTML features (TFLite), dual threshold ALLOW / AMBIGUOUS / BLOCK.
- Dynamic stage (ambiguous pages that reach a credential page only): types **decoy credentials**,
  records 59 state-transition features (form, role, hidden, response, handler, consumption),
  HGB classifier. Dynamic F1 0.920; ~4.2 s (~5.6 s including credential-page detection).

**WHALE already handles** (never claim it misses these): delayed redirection within its window,
same-page harvesting, handler mutation, interaction-gated pages, user-agent filtering.

**Open cases WHALE's authors list** (our space):
1. Pages allowed by the static stage get no dynamic check and no monitoring after release.
2. Sandbox- or decoy-aware evasion.
3. CAPTCHA/MFA-gated flows.
4. Non-credential scams (linking codes, payments).
5. Behaviour after the analysis window; kits whose backend is dead.
6. **Our hypothesis (not yet tested):** an AiTM relay forwards decoy credentials to the real site,
   which returns a genuine "wrong password"; decoy-based response features may read this as benign.

Positioning: **complementary (hybrid)**, not "first". A pre-release check can stay in front;
QuishGuard adds live-session protection behind it. Trade-off to report honestly: in a live session
real credentials enter the page, so protection depends on stopping the send - report residual
exposure per channel.

## Research paper (working title)

*Beyond Pre-Release Sandboxing: Runtime Interception Limits and AiTM-Resilient Detection for
QR-Triggered Phishing in Android In-App WebViews*

| RQ | Question | Evidence needed |
|---|---|---|
| RQ1 | Which outbound channels in an Android in-app WebView can be observed and blocked (JS hooks vs native), incl. same-origin sends and hook evasion? | Per-channel interception success rate, residual exposure |
| RQ2 | How common are WHALE's stated open cases in real phishing pages? | Prevalence numbers from real samples |
| RQ3 | How well does live-session protection cover the open cases and AiTM, and at what false-positive cost on benign SSO/OTP/payment flows? | Results per case vs a WHALE-inspired pipeline; FPR on benign flows |
| RQ4 | Robustness on unseen kit families | Recall on kit-family-disjoint test sets |
| RQ5 | Cost and usability | On-device latency/memory/battery; "time until usable" vs WHALE's ~4.2 / ~5.6 s |

Experiments: E1 channel interception, E2 prevalence, E3 open cases, E4 AiTM relay (isolated lab,
own test accounts), E5 false positives, E6 robustness, E7 cost/usability, E8 sequence-model
ablation (CNN/GRU kept only if it beats LightGBM on order-dependent cases).

Method rules: kit-family-disjoint splits (WHALE protocol), threshold chosen on training data only,
no URL/domain/origin features in the behaviour model (origin rules only as an ablation),
confusion matrix, 10-run rolling evaluation, recall at fixed FPR, interception success rate.

## Datasets

| Source | Use | Notes |
|---|---|---|
| DynaPD (github.com/code-philia/DynaPD) | Main behaviour traces | 6,000+ de-weaponized PHP kits, CC0. Run **isolated**: no internet, mail disabled |
| Mendeley web page phishing (doi 10.17632/c2gw7fy2j4.3) | Static stage of the WHALE-inspired baseline | HF `pirocheto/phishing-url` may be the same source - verify |
| `nyuuzyou/phishing-snapshots` | Prevalence (RQ2) | Passive captures; no credential sends recorded |
| `phreshphish/phreshphish` | Extra baseline data | HTML + URL pairs |
| Tranco / Taiwan login pages, benign SSO/OTP/payment flows | False-positive tests | Benign only |
| Own lab pages (open cases, AiTM) | E3, E4 | Fictional brands, fake or own test accounts |

## Planned design (to be built step by step)

Two layers, so bypassing one does not bypass protection:
- **Layer 1 - in-page sensor (JavaScript):** injected before the page's own code; tracks
  sensitive fields; wraps the ways a page can send data; holds sensitive sends until judged.
  Android: `addDocumentStartJavaScript`.
- **Layer 2 - network layer:** sees every request leaving the page; after a block, stops
  everything (same-origin included). Android: `shouldInterceptRequest` - destination only,
  no POST body, no WebSocket messages.

Enforcement once a page is judged risky:
1. **Prevention** - hold any send carrying typed sensitive data until scored.
2. **Containment** - block all further requests from the page, same-origin included.
3. **Recovery** - if data may already have left, tell the user to change the password or call the bank.

## Roadmap gates

1. Gate 1 - the mechanism works on lab scenarios (Python), then on Android.
2. Gate 2 - a trained model beats the hand-written rules at a fixed false-positive rate.
3. Gate 3 - results hold on unseen kit families, cloaked and adaptive pages.
4. Gate 4 (startup track, later) - one observe-only pilot partner. Patent outlook is low;
   advantage must come from results, Taiwan focus and partnerships.

## Open questions for the professor

- Relationship between this journal paper and the already-submitted QuishGuard conference paper
  (avoid duplicate publication).
- Can the lab provide an Android developer and test phones?
- Agreement on the revised RQs before heavy implementation.
