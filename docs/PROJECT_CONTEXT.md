# QuishGuard - project context

Last updated: 2026-11-06. Background for anyone (human or Claude) working in this repo.

## The problem

QR phishing moves victims from protected email onto phones, where checks judge the **link**, not
what the page **does**. Blocklists miss new and per-victim URLs; pages hide from scanners
(cloaking, CAPTCHA, delayed forms); device-code lures and AiTM proxies use real login pages.
Every attack still has to **collect data and send it somewhere** - that behaviour is the signal
QuishGuard watches.

Local focus: Taiwan (TWQR payment fraud; LINE account takeover via "shared photos" QR + code lures).

## Closest prior work: WHALE (Sensors, July 2026)

https://www.mdpi.com/1424-8220/26/14/4412 - QR-triggered, on-device Android WebView analysis.
It opens each QR-decoded URL in a sandbox WebView **before** the user sees it, scores it, and
probes unclear pages with decoy credentials, then releases or blocks the URL.

What WHALE leaves open (our space):
- No monitoring after the page is released to the user.
- CAPTCHA/MFA-gated flows and non-credential QR scams are out of its scope.
- About 4.2 s of dynamic analysis before the user can use the page.
- No per-channel enforcement; whole-URL block or allow only.

We cannot claim "first on-device QR behaviour detection". We position as **complementary**:
a pre-release check plus live-session protection.

## Research paper (working title)

*Beyond Pre-Release Sandboxing: Runtime Interception Limits and AiTM-Resilient Detection for
QR-Triggered Phishing in Android In-App WebViews*

| RQ | Question | Evidence needed |
|---|---|---|
| RQ1 | Which outbound channels in an Android in-app WebView can be observed and blocked (JS hooks vs native), incl. under hook evasion? | Per-channel interception success rate |
| RQ2 | How common are sandbox-evading behaviours in live QR-reachable phishing, and does live monitoring catch what a WHALE-inspired check misses? | Prevalence numbers from real samples; detection comparison |
| RQ3 | How well are AiTM, CAPTCHA/MFA-gated and non-credential QR scams handled? | Results per hard category |
| RQ4 | Robustness to unseen campaigns, cloaking, adaptive attackers | Recall drop on time-split / adaptive sets |
| RQ5 | On-device latency, memory, battery cost | Measurements on low- and mid-range Android |

Event-sequence model (CNN/GRU) = ablation only; keep it only if it beats LightGBM on
order-dependent cases.

Metrics: recall, precision, F1, false-positive rate, **recall at fixed FPR (e.g. 0.1%)**,
detection latency, **interception success rate**.

Datasets: (1) general phishing for baselines; (2) **QR-reachable** phishing for the main
evaluation. Candidate sources: `phreshphish/phreshphish` (HTML + URL pairs, base-rate
benchmarks), `nyuuzyou/phishing-snapshots` (full HTML + HAR network traffic, CC0),
CIC-Trap4Phish (QR attachments), Taiwan 165 anti-fraud notices, our own lab pages.

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
3. Gate 3 - results hold on unseen campaigns, cloaked and adaptive pages.
4. Gate 4 (startup track, later) - one observe-only pilot partner. Patent outlook is low;
   advantage must come from results, Taiwan focus and partnerships.

## Open questions for the professor

- Relationship between this journal paper and the already-submitted QuishGuard conference paper
  (avoid duplicate publication).
- Can the lab provide an Android developer and test phones?
- Agreement on the revised RQs before heavy implementation.
