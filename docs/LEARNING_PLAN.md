# QuishGuard learning plan

Build the prototype stage by stage. Tick a stage only when its "Done when" is true.
Each stage: **Learn** = concepts to understand, **Build** = what to make, **Done when** = check.

## Part A - Foundations

- [x] **Stage 0 - Set up the workspace**
  - Learn: virtual environments, git basics, how pytest finds tests, how Claude Code's Learning mode works (`TODO(human)`).
  - Build: `.venv`, `requirements.txt` with `pytest`, `src/quishguard/` package, `tests/test_sanity.py`.
  - Done when: `pytest` passes one trivial test and the first commit exists.

- [x] **Stage 1 - How a login page sends data**
  - Learn: HTTP GET vs POST, HTML forms, what "origin" and "same-origin" mean, what a server receives.
  - Build: a tiny local server (Python `http.server`) on 127.0.0.1 that serves a fictional
    Formosa Demo Bank login page and prints what it receives.
  - Done when: submitting the form with fake credentials prints them in the terminal.

- [x] **Stage 2 - The lab: legit bank vs phishing site vs attacker**
  - Learn: why phishing kits often post to their own domain; how a second "collector" domain works.
  - Build: run three servers on different ports (official bank, phishing page, attacker collector)
    and a log file recording everything attacker servers receive.
  - Done when: one fake phishing page leaks the fake password into the attacker log.

- [x] **Stage 3 - QR codes**
  - Learn: what's inside a QR code, how phones decode them, why QR hides the URL from the user.
  - Build: generate a QR for a lab URL (`qrcode`) and decode it from the image (`opencv`).
  - Done when: a function `decode_qr(path) -> str` is tested on your generated images.

## Part B - Watching a page

- [ ] **Stage 4 - Open pages like a phone**
  - Learn: browser automation, headless browsers, mobile emulation, async/await basics.
  - Build: open a decoded URL in Playwright with a phone profile, type fake credentials, click.
  - Done when: your script reproduces the Stage 2 leak automatically.

- [ ] **Stage 5 - See every request a page makes**
  - Learn: network requests, request types (document, fetch, xhr, image, ping), destination vs body.
  - Build: log every outgoing request with method, destination and body.
  - Done when: you can point to the exact request that carries the password.

- [ ] **Stage 6 - Spot sensitive data in a request**
  - Learn: sensitive fields (password, one-time code, card), matching typed values in requests, false matches.
  - Build: `carries_sensitive(request, typed_values) -> bool` with tests.
  - Done when: tests pass for form, query-string and URL-encoded cases.

## Part C - Deciding and blocking

- [ ] **Stage 7 - Explainable risk rules**
  - Learn: rule-based scoring, weights, thresholds, why every verdict needs reasons.
  - Build: `score_send(page_info, destination, scan_context) -> Verdict(decision, score, reasons)`.
    Rules to design yourself: untrusted site, brand impersonation, cross-site send, scan context mismatch.
  - Done when: unit tests cover the official bank (allow), a fake bank (block), an unknown shop sign-up (allow).

- [ ] **Stage 8 - Block the send (network layer)**
  - Learn: request interception (`route.abort` / `route.continue_`), containment, why blocking only
    other domains misses same-origin theft. Android equivalent: `shouldInterceptRequest` (destination only).
  - Build: block risky sensitive sends; once a page is judged malicious, block everything it sends.
  - Done when: the Stage 2 attack leaks nothing, the official bank login still works.

- [ ] **Stage 9 - The experiment runner**
  - Learn: baselines, why you compare "no protection" vs "protection", measuring leaks instead of assuming.
  - Build: `run_experiment.py` running each scenario with and without protection; a results table.
  - Done when: one command prints a pass/fail table.

## Part D - Harder attacks

- [ ] **Stage 10 - In-page sensor (JavaScript layer)**
  - Learn: JavaScript basics, init scripts, wrapping `fetch`/`XMLHttpRequest`/`sendBeacon`,
    hold-by-default. Android equivalent: `addDocumentStartJavaScript`.
  - Build: a small `sensor.js` that reports sensitive input and holds sends until Python decides.
  - Done when: a send is held, judged and released or dropped.

- [ ] **Stage 11 - Attacks that evade simple checks** (add one at a time, each with a harmless counterpart)
  - Password sent before any button press (sendBeacon on blur)
  - Keylogger via image pixels
  - Page harmless at load, OTP form appears after 3 seconds
  - CAPTCHA first, then login sent over WebSocket
  - "Shared photos" lure asking for an app linking code (non-credential scam)
  - Hook evasion (borrowing an untouched `fetch` from an iframe)
  - Done when: each has a result in the table and you can explain which layer caught it, or why it got through.

- [ ] **Stage 12 - A load-time check for comparison**
  - Learn: pre-release checking (as in WHALE), what it can and cannot see.
  - Build: a simple check that inspects a page once at load, as an extra column. Call it a
    "load-time stand-in", not WHALE.
  - Done when: the table shows which attacks the load-time check misses.

## Part E - Real data and ML

- [ ] **Stage 13 - URL baseline from Hugging Face**
  - Learn: using a pretrained model, tokenizers, inference, what a URL-only model can't know.
  - Build: add `CrabInHoney/urlbert-tiny-v4-phishing-classifier` as a column.

- [ ] **Stage 14 - How do real phishing pages send data? (RQ2 start)**
  - Learn: HAR files, pandas, counting and plotting.
  - Build: analyse network traffic in `nyuuzyou/phishing-snapshots`: share of pages that post
    credentials same-origin, cross-origin, by WebSocket.
  - Done when: you have numbers you could put in the paper.

- [ ] **Stage 15 - From rules to LightGBM**
  - Learn: features, train/test splits by domain or time, recall at fixed false-positive rate, SHAP.
  - Build: behaviour features recorded by your own sensor, a LightGBM model, comparison with your rules.

## Part F - Android

- [ ] **Stage 16 - Android interception test (Gate 1 on a phone)**
  - Learn: Android Studio, Kotlin basics, WebView, `addDocumentStartJavaScript`, `shouldInterceptRequest`.
  - Build: a minimal app that opens a lab page and tries to block each channel.
  - Done when: a per-channel table says what Android can and cannot block.
