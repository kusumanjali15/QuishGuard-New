# Stage 14b - DynaPD live-behaviour lab (PRE-REGISTERED)

Fixed before running on the isolated machine. Do not change the design/thresholds to fit results.

## Objective & RQ mapping
Drive real **de-weaponized** phishing kits (DynaPD, github.com/code-philia/DynaPD, 6,000+ PHP kits,
CC0) with OUR victim + sensor, and record, per kit, which channels carry the (FAKE) credentials and
when. Evidence for **RQ3** (coverage of the open cases on real kits) and **RQ4** (robustness on unseen
kit FAMILIES); training data for **Stage 15**. **NOT RQ2** - prevalence comes from the phishing
snapshots (Stage 14).

## Safety / isolation - NON-NEGOTIABLE (verify BEFORE any kit runs)
Running real kits is only safe fully contained. All of these must hold:
1. **Host**: the isolated machine only. No production network, no shared drives with live data.
2. **No egress (WSL + disconnect model)**: the lab runs in **WSL2 (Ubuntu) on a dedicated Windows box**.
   The PRIMARY egress guarantee is that the **physical machine is disconnected from the network**
   (Ethernet unplugged / adapter disabled) whenever REAL kits run - a boundary that cannot be subtly
   misconfigured. SECONDARY containment: kits run in Docker on an INTERNAL network inside WSL
   (`docker network create --internal`). Workflow: build/debug the harness while ONLINE (egress test +
   our own safe pages only, never real kits); DISCONNECT to run real DynaPD kits; re-run the egress gate
   in the disconnected state immediately before each kit-run session; reconnect only when no kit is
   running (to pull fixes), then disconnect and re-verify before resuming.
3. **Mail disabled**: PHP `sendmail_path` set to a no-op/logging stub; the kit's `mail()` cannot send.
4. **Egress sinkhole (so we can RECORD without forwarding)**: DynaPD kits were de-weaponized to send
   credentials by **EMAIL to a configurable address** (Telegram code replaced). So the PRIMARY capture
   is a local **SMTP sink** on :25 that logs the full message (to/subject/body) and never relays;
   PHP's `sendmail_path` is pointed at it and the kit's configurable attacker email is set to a local
   address. SECONDARY: a local DNS resolver (all A -> sink IP) + a catch-all HTTP/HTTPS sink logging
   `method+host+path+body` and returning 200, for any kit that still exfils over HTTP. Nothing is
   forwarded; every send is captured locally. This is how the behaviour is recorded.
5. **Fake data only**: demo_user_01 / Lab-Pass-4821 / OTP 123456 / LINK-7788 / test card 4111...4111.
   No real account, email, or secret ever typed.
6. **Verify-before-run GATE**: `lab14b/egress_test.py` runs and is logged BEFORE each kit-run session -
   from the WSL host (and, once built, from inside the kit container) it attempts several external
   reaches (DNS, TCP:443, HTTP); ALL must fail. If anything is reachable, STOP and fix isolation. The
   recorder refuses to proceed unless the egress test reported ISOLATED.

## Data governance
Kits embed REAL attacker exfil endpoints (emails, bot tokens, URLs). Traces/sink logs will contain
them. Treat like labels.csv: commit traces ONLY to the PRIVATE repo; scrub/redact (hash) attacker
identifiers before any public release. Never publish raw kit exfil targets.

## Lab architecture
- `lab14b/` (new): Docker lab + recorder (built on the current machine, run on the isolated one).
  - `sinkhole/`: DNS resolver (all -> sink IP) + catch-all HTTP(S) sink (logs body, returns 200).
  - kit server: PHP's built-in server `php -S 127.0.0.1:<port> -t <kit-dir>` (php-cli) serving one kit
    at a time; no XAMPP needed. CAVEAT: `php -S` does not process `.htaccess`/mod_rewrite, so kits that
    depend on Apache rewrites may not serve correctly - flagged per kit; revisit with Apache if many fail.
    `sendmail_path` set to the SMTP sink (or a logging stub) so `mail()` is captured, never sent.
  - `record_kit.py`: for each kit - start the kit container, drive it with OUR victim
    (Playwright Pixel 7 + sensor + guard, fake creds), capture the behaviour trace, tear down.
- Reuse the existing `quishguard` sensor/guard unchanged (same code as Android/Python lab).

## Per-kit trace schema (fixed)
One JSON per kit: `{kit_id, kit_family, sends: [{t_ms, channel, method, dest_host, carries_fake_value}],
guard_verdict, notes}`. `channel` taxonomy = the Stage 16 set (fetch/xhr/form/beacon/websocket/
image/navigation/iframe). `carries_fake_value` = the typed fake value appears in the send (sensor
observed-value match) OR in the sink's captured body. `kit_family` from the kit's directory/family,
never random.

## Pre-registered analysis rules
- Split by **kit family** (disjoint) for any Stage 15 train/test - never random by kit or URL.
- Thresholds/features are NOT tuned on these traces for evaluation; Stage 15 freezes thresholds on a
  training split and does a kit-family-disjoint, 10-run rolling evaluation (PROJECT_CONTEXT).
- Report coverage per channel and per kit family; keep detection (channel seen) separate from
  prevention (send blockable).

## Done when
Per-kit behaviour traces are recorded by our own sensor for a documented set of kits, with the
egress-test gate logged as PASSED (i.e. egress correctly blocked), in docs/STAGE14B_NOTES.md.
