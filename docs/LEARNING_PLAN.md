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

- [x] **Stage 4 - Open pages like a phone**
  - Learn: browser automation, headless browsers, mobile emulation, async/await basics.
  - Build: open a decoded URL in Playwright with a phone profile, type fake credentials, click.
  - Done when: your script reproduces the Stage 2 leak automatically.

- [x] **Stage 5 - See every request a page makes**
  - Learn: network requests, request types (document, fetch, xhr, image, ping), destination vs body.
  - Build: log every outgoing request with method, destination and body.
  - Done when: you can point to the exact request that carries the password.

- [x] **Stage 6 - Spot sensitive data in a request**
  - Learn: sensitive fields (password, one-time code, card), matching typed values in requests, false matches.
  - Build: `carries_sensitive(request, typed_values) -> bool` with tests.
  - Done when: tests pass for form, query-string and URL-encoded cases.

## Part C - Deciding and blocking

- [x] **Stage 7 - Explainable risk rules**
  - Learn: rule-based scoring, weights, thresholds, why every verdict needs reasons.
  - Build: `score_send(page_info, destination, scan_context) -> Verdict(decision, score, reasons)`.
    Rules to design yourself: untrusted site, brand impersonation, cross-site send, scan context mismatch.
  - Done when: unit tests cover the official bank (allow), a fake bank (block), an unknown shop sign-up (allow).

- [x] **Stage 8 - Block the send (network layer)**
  - Learn: request interception (`route.abort` / `route.continue_`), containment, why blocking only
    other domains misses same-origin theft. Android equivalent: `shouldInterceptRequest` (destination only).
  - Build: block risky sensitive sends; once a page is judged malicious, block everything it sends.
  - Done when: the Stage 2 attack leaks nothing, the official bank login still works.

- [x] **Stage 9 - The experiment runner**
  - Learn: baselines, why you compare "no protection" vs "protection", measuring leaks instead of assuming.
  - Build: `run_experiment.py` running each scenario with and without protection; a results table.
  - Done when: one command prints a pass/fail table.

## Part D - Harder attacks

- [x] **Stage 10 - In-page sensor (JavaScript layer)**
  - Learn: JavaScript basics, init scripts, wrapping `fetch`/`XMLHttpRequest`/`sendBeacon`,
    hold-by-default. Android equivalent: `addDocumentStartJavaScript`.
  - Build: a small `sensor.js` that reports sensitive input and holds sends until Python decides.
  - Done when: a send is held, judged and released or dropped.

- [ ] **Stage 11 - Attacks that evade simple checks** (add one at a time, each with a harmless counterpart)
  - Built set (done):
    - Password sent before any button press (sendBeacon on blur)
    - Keylogger via image pixels
    - Page harmless at load, OTP form appears after 3 seconds
    - CAPTCHA first, then login sent over WebSocket
    - "Shared photos" lure asking for an app linking code (non-credential scam)
    - Hook evasion (borrowing an untouched `fetch` from an iframe)
  - To add (pending - map each to an OPEN CASE 1-6 in PROJECT_CONTEXT):
    - Harmless-at-load page with a CONFIGURABLE delay (2.5 / 5 / 10 / 20 / 30 s) before any malicious
      behaviour. Record what the static stand-in scores AT LOAD (if it ALLOWs -> open case 1), and
      which delays fall beyond WHALE's reported analysis time (~4.2 / ~5.6 s -> open case 5).
      Measure, don't assume a fixed window.
    - Decoy-/automation-aware page: behaves well if it detects the sandbox or decoy creds (open case 2)
    - Revise the CAPTCHA page: replace the one-click button with a distorted-code IMAGE the user must
      type - a "lab approximation of a human gate" (open case 3)
    - Benign counterparts for the FP set: SSO/OAuth cross-domain redirect; a legit OTP step; a legit payment page
  - Done when: each has a result in the table and you can explain which layer caught it, or why it got through.

- [x] **Stage 12 - WHALE static-stage stand-in**
  - Learn: WHALE's STATIC stage only (a load-time snapshot) - what it can and cannot see. This is NOT
    WHALE; the dynamic decoy stage and the real WHALE comparison are Stage 12b. A miss here is NOT a
    WHALE gap - WHALE's dynamic stage may still catch it.
  - Build: a snapshot check (title/brand, sensitive field present, form action) as an extra column,
    labelled "WHALE static-stage stand-in".
  - Done when: the table shows which pages the static stand-in passes at load (candidates for open case 1).

- [ ] **Stage 12b - WHALE-inspired baseline** (label it "WHALE-inspired", not a reproduction)
  - Learn: WHALE's pipeline - a static score, a DUAL threshold (allow / block / "unclear"),
    a decoy-credential probe on unclear pages, and a BOUNDED observation window.
  - Build: a baseline that chains those four pieces over a page, as a column next to our live guard.
  - Done when: the table shows where the WHALE-inspired baseline (static score from Stage 13) and
    our live guard differ, on the open cases 1-6 (PROJECT_CONTEXT).

## Part E - Real data and ML

- [x] **Stage 13 - Reproduce WHALE's static stage (sklearn, no torch)**
  - Learn: WHALE's static features, a simple classifier (logistic regression / gradient boosting),
    train/test discipline. Reproduce the static stage on the Mendeley "Web page phishing detection"
    dataset (check if HF `pirocheto/phishing-url` is the same version).
  - Build: a sklearn static-stage classifier, as the static half of the Stage 12b baseline.
  - Done when: you can report its accuracy on a held-out split and feed it into the WHALE-inspired baseline.
  - (Parked/optional, later: the URL BERT model `CrabInHoney/urlbert-tiny-v4-phishing-classifier`,
    already prototyped in `src/quishguard/urlmodel.py` - an optional extra signal, not on the main path.)

- [ ] **Stage 14 - Load-time characteristics of real phishing (phishing-snapshots)**
  - Learn: HAR files, pandas, counting and plotting - AND the passive-capture caveat:
    `nyuuzyou/phishing-snapshots` has NO interaction, so it shows load-time structure, not what a
    page sends after a user types. Do NOT report credential-send channel shares from it.
  - Build: from the snapshots, measure load-time characteristics (forms present at load, sensitive
    fields, where form actions point, third-party resources), with the caveat stated.
  - Done when: you have load-time numbers you could put in the paper, clearly labelled passive.

- [ ] **Stage 14b - DynaPD live-behaviour lab (RQ2 core)**
  - Learn: running real de-weaponized kits safely - PHP in Docker, NO internet egress, mail
    disabled, isolated network; driving each kit with our victim + sensor to record send traces.
  - Build: a DynaPD Docker lab and a recorder that captures, per kit, which channels carry the
    (fake) credentials and when - the evidence for RQ2 (how common the open cases are) and RQ3 (coverage).
  - Done when: you have per-kit behaviour traces recorded by our own sensor.

- [ ] **Stage 15 - From rules to a behaviour model**
  - Learn: behaviour features, recall at fixed false-positive rate, SHAP, and the methodology in
    PROJECT_CONTEXT - **no origin/URL/domain/IP/HTTPS features** (origin rules kept only as an
    ablation), kit-family-disjoint split,
    threshold frozen on training data, confusion matrix, 10-run rolling evaluation.
  - Build: behaviour-only features from the Stage 14b traces, a model (e.g. LightGBM), compared
    with the hand-written rules at a fixed FPR, on a kit-family-disjoint split.
  - Done when: you can report the model vs rules at a fixed FPR, with no origin features used.

- [ ] **Stage 15b - AiTM relay (open case 6, experiment E4)**
  - Learn: adversary-in-the-middle - a relay that forwards submitted credentials to the REAL login and
    mirrors the response, so a decoy probe gets a genuine "wrong password" and may look benign to a
    decoy-based check.
  - Build: a lab relay on 127.0.0.1 that forwards to OUR OWN Formosa Demo Bank server (no real sites
    or accounts). Test whether the WHALE-inspired decoy stage is fooled while our live guard still
    stops the real send.
  - Done when: the table shows the AiTM relay's effect on the decoy-based baseline vs our live guard.

## Part F - Android

- [ ] **Stage 16 - Android interception test (Gate 1 on a phone)**
  - Learn: Android Studio, Kotlin basics, WebView, `addDocumentStartJavaScript`, `shouldInterceptRequest`.
  - Build: a minimal app that opens a lab page and tries to block each channel.
  - Also measure **time until the page is usable** by the user, to compare against WHALE's
    ~4.2 s dynamic (~5.6 s with CRP detection) pre-release delay (RQ5).
  - Done when: a per-channel table says what Android can and cannot block, plus a time-to-usable figure.
