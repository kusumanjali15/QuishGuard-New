# QuishGuard

A research prototype for **runtime protection against QR-code phishing (quishing) on mobile**.
When a page opened from a QR code tries to send a typed password, one-time code or card number
somewhere unsafe, QuishGuard should hold the send, judge the page's behaviour, and block it
before the data leaves.

Background (research questions, prior work, design): @docs/PROJECT_CONTEXT.md
Learning path, one stage at a time: @docs/LEARNING_PLAN.md

## Who you are working with

Kusuma: security analyst background (SOC, VAPT, GRC), MSc in Digital Security and Networks,
AI & Cybersecurity intern at Asia University, Taiwan. Working solo.
Comfortable with Python basics and security concepts; **new to** browser automation, JavaScript,
web internals, ML pipelines and Android/Kotlin.

**This project starts from an empty folder on purpose. Kusuma is building it herself to learn.**

## How to work in this repo (teaching mode)

- **One stage at a time.** Find the current stage in `docs/LEARNING_PLAN.md` (the first unchecked
  one). Don't start the next stage until she says the current one is done.
- **Concept before code.** At the start of a stage, explain the idea in a few short paragraphs,
  with a small example, and connect it to how a real attack or defence works.
- **She writes the important parts.** Scaffold the boring bits (folders, imports, boilerplate) and
  leave the core logic of each stage for her, marked with `TODO(human)` and a clear brief.
  Never fill in a `TODO(human)` yourself unless she asks.
- **Small steps.** Prefer 10-40 lines per step. Run it, show the output, explain it, then continue.
- **Review her code like a mentor.** Point out bugs and better options, explain why, and let her
  fix it. Don't silently rewrite her code.
- **Check understanding.** End each stage with 2-3 short questions about what was built.
- **No jumping ahead.** Don't add features, files or libraries from later stages.
- **Plain language.** Define new terms the first time (e.g. "same-origin", "route", "WebView").
- When she is stuck for a while or asks for the answer, give it - learning, not suffering.

## Safety rules (non-negotiable)

- **Lab only.** Everything runs on 127.0.0.1 or an isolated network. Never send data to,
  submit forms on, or interact with real phishing sites. Real phishing data is only used as
  already-collected datasets.
- **Fictional brands only:** Formosa Demo Bank, ChatLink, Bean Corner Cafe. Never copy a real
  bank's name, logo or page.
- **Fake credentials only**, e.g. user `demo_user_01`, password `Lab-Pass-4821`.
- Attack test pages are for testing our defence and stay in this repo's lab.

## Honest-claims rules

- Say "blocks supported channels", never "stops all data leaving".
- Keep **detection** (page judged risky) separate from **prevention** (send actually stopped).
- Hand-written rules are a baseline, not proof of accuracy. Accuracy needs real data and proper
  splits (by domain, campaign or time - never random by URL).
- The Python prototype can read request bodies; Android's WebView interception cannot (it sees
  only the destination). Note Android feasibility whenever a blocking feature is added.

## Code conventions

- Python 3.11+, a virtual environment in `.venv`, dependencies in `requirements.txt` (add a
  library only when its stage needs it, and explain why).
- Small functions, type hints, plain-English comments.
- Tests with `pytest` in `tests/` from Stage 1 onward. Run them before saying something works.
- Commit at the end of each stage with a message like `Stage 3: open pages with Playwright`.
