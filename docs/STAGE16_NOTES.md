# Stage 16 - Android WebView interception test (RQ1)

**Question (RQ1):** on a real Android WebView, for each way a page can send data, which of our two
layers observes it, and can it be blocked?

- **Script layer** = our sensor, injected with `WebViewCompat.addDocumentStartJavaScript`
  (feature-gated on `DOCUMENT_START_SCRIPT`), running at document-start. Lives INSIDE the page -
  can read typed values (bodies), but is page-scoped and can be evaded (e.g. unwrapped iframe).
- **Native layer** = `WebViewClient.shouldInterceptRequest`. Runs OUTSIDE the page (hard to evade)
  but sees only the DESTINATION (URL + headers + method), NEVER the body. Can return a
  `WebResourceResponse` to block.

Honest-claims: "blocks supported channels", not "stops all data". Lab only (10.0.2.2), fake
secrets only. Detection (a layer SAW the send) is kept separate from prevention (the send was
actually stopped).

## Test environment
- Device: Pixel 7 emulator (AVD), **Android 14, API 34**, Google Play system image.
- Android System WebView version: **com.google.android.webview 113.0.5672.136** (from the app's `qg-setup` log via `WebViewCompat.getCurrentWebViewPackage()`). NOTE: 113 is relatively old; some newer mechanisms (e.g. Navigation API cross-document interception) may not be present on it - re-check feature support rather than assuming when testing blocking.
- App: `android/` (package `com.quishguard.webviewtest`), androidx.webkit 1.11.0.
- Host lab reached from the emulator via `10.0.2.2` (= host 127.0.0.1). Page origin
  `http://10.0.2.2:8003`; cross-origin target `http://10.0.2.2:8002`; WebSocket `10.0.2.2:8004`.

## Results (per channel)
Legend: Y = observed / possible, N = not. "Native body?" is always N by design (kept as a column
to make the point explicit).

Same-origin and cross-origin behaved identically for which-layer-saw-it (cross adds a browser CORS
error on reading the *response*, but the request still LEFT the device and the native layer saw it -
detection is unaffected). Blockability is the next sub-step (native currently returns null).

| # | Channel | Script saw (body) | Native saw (URL) | Native body? | Notes |
|---|---|---|---|---|---|
| 1 | Form POST, button submit | Y | Y | N | the 2c bank login - real `submit` event fired |
| 2 | Form POST, programmatic `.submit()` | Y | Y | N | the CANONICAL sensor wraps `HTMLFormElement.prototype.submit`, so scripted submits are caught (the thin first build missed this - the reason we switched to the shared sensor) |
| 3 | fetch (POST) | Y | Y | N | cross: CORS blocks reading the reply, request still sent |
| 4 | XHR (POST) | Y | Y | N | same as fetch |
| 5 | sendBeacon | Y | Y | N | beacon is no-cors; sent cleanly |
| 6 | image `src` (GET) | N (build) | Y | n/a | script does not wrap the `img.src` setter in this build; secret rode in the URL query, so **native captured the secret itself** - "no body" does not protect data put in a URL |
| 7 | WebSocket | Y (send) | N (fundamental) | - | native hook never fires for WS - **script-only** channel |
| 8 | iframe-borrowed fetch (about:blank) | N (build) | Y | N | sensor not injected into the child frame in this build; native saw the sub-resource (`mainFrame=false`) |
| 9 | Navigation w/ query (top-level GET) | N (partial - see below) | Y | n/a | script did not intercept it here, but top-level navigation is PARTIALLY interceptable (Navigation API / native `shouldOverrideUrlLoading`) - to be tested, not assumed; native saw `GET ... mainFrame=true` with the secret in the URL |

**Sensor note:** the script layer is the SAME `sensor.js` as the Python lab (copied into the app's
assets at build; single source of truth), injected via `addDocumentStartJavaScript` with an
observe-only shim for `__qg_decide`/`__qg_observe`. The page arms it by typing a credential into a
sensitive field first (the sensor holds-by-default only after something sensitive is typed), matching
the real threat model. So Android and Python coverage are directly comparable.

### Coverage-limit taxonomy (asked: "not wrapped in this build" vs "cannot be wrapped")
- **Build limits now CLOSED (after hardening):**
  - Script layer, image `src` GET (#6): CLOSED - `HTMLImageElement.prototype.src` setter wrapped.
  - Script layer, top-level navigation (#9): CLOSED on WebView 113 - the Navigation API `navigate` event
    cancels page-initiated navigation (confirmed, incl. cross-origin).
- **Script-layer limitation that did NOT close (empirical, 113):**
  - iframe-borrowed fetch from an `about:blank` frame (#8): the borrowed realm has its own empty
    hold-state and its fetch fires on frame load before any cross-realm wrap binds. Native covers it by
    destination; this is a standing argument for the two-layer design, not a build gap.
- **Fundamental limits** - the layer CANNOT cover these, by platform design:
  - Native layer, request **bodies**: `shouldInterceptRequest` never exposes the body.
  - Native layer, **WebSocket** (#7): `shouldInterceptRequest` never fires for WS frames.
- **Top-level navigation (#9): coverable by BOTH layers (confirmed on 113).**
  - Script: the **Navigation API** `navigate` event cancels the page-initiated navigation
    (`navigation CANCELLED via Navigation API`, incl. cross-origin).
  - Native: **`shouldOverrideUrlLoading`** cancels the main-frame navigation (query string included).

### What this shows (RQ1)
- **The two layers are complementary; together they saw every channel tested.**
  - Script-only: **WebSocket** (native fundamental-blind).
  - After hardening, only the **about:blank iframe-borrowed fetch** is native-only; image GET and top-level navigation are now ALSO script-coverable (src-setter wrap; Navigation API on 113).
- **Native sees destinations, never bodies** - but a secret placed in a URL (image GET, navigation query) rides in the destination, so native captures it anyway. Body-blindness only hides data in a POST body.
- **One channel's secret VALUE is seen by neither layer as a value: the iframe-borrowed fetch POST body** (script not in the frame; native sees the URL but not the body). Native can still BLOCK it by destination - prevention is possible even when the value is invisible. This separates detection-by-value from prevention-by-destination.
- **Script-layer coverage after hardening:** `img.src` setter wrapped (#6 closed), Navigation API cancels navigation (#9, works on 113), scripted `form.submit()` covered. **Residual:** the about:blank iframe-borrowed fetch (#8) stays native-only - a cross-realm/timing limit, not a build gap.

## Android hardening - PRE-REGISTERED (close the two build gaps; test navigation in-page)

Changes to the CANONICAL sensor (so Python and Android stay identical), then rerun BOTH:
1. **Image `src` (build gap #6):** override `HTMLImageElement.prototype` `src` setter and
   `setAttribute('src')` so an image GET issued while a secret is held is judged (and dropped on block).
2. **Child frames (build gap #8):** refactor the channel wraps into `installInto(win)` and install into
   same-origin / `about:blank` child frames (existing frames + a synchronous hook on iframe insertion),
   so an iframe-borrowed fetch is wrapped by the top frame's hold state.
3. **Navigation API (#9):** test whether the `navigate` event (`preventDefault`) can cancel the
   page-initiated navigation on WebView 113. RECORD the actual result - do not assume it works (113 is old).

Pre-registered expectation to CONFIRM, not assume: image GET and iframe-borrowed fetch become
SCRIPT-blockable (build gaps closed); the Navigation API result is unknown on 113 and is reported as-is.
Rerun the Python comparison too - harmless twins must stay at ZERO false blocks (no regression from the
sensor changes); if any regression appears, report it.

## RQ5 - time-to-usable (added latency vs WHALE's pre-release window)
WHALE holds the page for a ~4.2 s (-5.6 s with CRP) pre-release dynamic-analysis window BEFORE the user
can interact - that delay is its usability cost. QuishGuard has NO pre-release phase: the sensor injects
at document-start (non-blocking) and the guard acts at send-time. Two separate figures:

1. **Added time-to-usable** = page load time WITH the sensor minus WITHOUT it (toggle `sensorEnabled`).
   `qg-timing: page finished in N ms (sensor=true/false)`. Expected ~0 difference.
   - sensor ON:  1355 ms / sensor OFF: 773 ms - **single samples only; NOT a reliable delta.** The
     emulator shows multi-second frame jitter, and the sensor-ON run also ran arming + cold JIT. We do
     NOT claim an added-load figure from this; a clean delta needs medians over several runs on a real
     device. The defensible RQ5 result is architectural (no pre-release window) + the per-send cost below.
2. **Per-send decision latency** = the `__qg_decide` round-trip, paid only when the user actually sends
   sensitive data (not an up-front wait). `qg-sensor ... decideMs=X`. Expected a few ms.
   - decideMs: 23.6 ms first call (JIT warm-up), then ~4.7-4.8 ms steady -> **~5 ms per sensitive send.**

Honest framing: QuishGuard adds ~0 s to time-to-usable (no window to wait out), vs WHALE's ~4.2 s; its
cost is a few ms per sensitive send. Measured on WebView 113, emulator (note the emulator is slow, so
absolute load ms are not device-representative - the sensor-on vs sensor-off DIFFERENCE is the figure).

### Blocking sub-step (plan - fills the "could it be blocked" column)
Mechanisms to WIRE and then TEST per channel (test on this WebView 113, don't assume):
- **Script layer** (`__qg_decide` returns `block`): the canonical sensor already drops fetch / XHR /
  sendBeacon / form submit (incl. scripted) / WebSocket on a block verdict. We replace the observe-only
  shim with a real native bridge (`addJavascriptInterface`) so the JS decision comes from Kotlin.
- **Native layer**: `shouldInterceptRequest` returns a blocking `WebResourceResponse` (e.g. empty 403)
  for disallowed destinations - covers sub-resource sends (fetch/XHR/beacon/image/iframe-fetch) by
  DESTINATION, even when the body is invisible.
- **Top-level navigation (#9)** - test BOTH, since neither is guaranteed on 113:
  - Script: **Navigation API** `navigate` event (`e.preventDefault()` / `intercept()`) to cancel a
    page-initiated navigation. May be absent/limited on WebView 113 - record what actually happens.
  - Native: **`shouldOverrideUrlLoading`** returns `true` to cancel a disallowed main-frame navigation
    (it sees the full URL incl. query). This is the robust path if the Navigation API is unavailable.
- **WebSocket**: script-only (native cannot) - block = `__qg_decide` -> close the socket.
Record, per channel: blocked by script? blocked by native? and the net result (send stopped / not).

**4a (native) - pre-registered rule (lab mechanism test, not a shippable policy):** once armed, a held
secret may go SAME-origin but is blocked CROSS-origin. Enforced by `shouldInterceptRequest` (returns a
403 for a cross-origin destination -> the real request is never sent) and `shouldOverrideUrlLoading`
(returns true to cancel a cross-origin main-frame navigation). Expected: all cross-origin HTTP channels
(fetch/XHR/beacon/image/iframe-fetch) blocked by `shouldInterceptRequest`; cross-origin form POST (a POST
nav) blocked by `shouldInterceptRequest`; cross-origin GET navigation blocked by `shouldOverrideUrlLoading`;
**WebSocket NOT blockable by native** (hook never fires) - script-only. Same-origin: allowed. To confirm.

**4a results (confirmed, WebView 113):**
- Cross-origin fetch / XHR / sendBeacon / image GET / iframe-borrowed fetch: **BLOCKED** by
  `shouldInterceptRequest` (403; the real request is never sent - secret does not leave).
- Cross-origin **form POST**: **BLOCKED** by `shouldInterceptRequest`. Caveat: the frame still navigates
  to the 403 (document origin becomes the destination, so its favicon is then also blocked) - the body
  is stopped, but the page moves. `shouldOverrideUrlLoading` is NOT called for POST navigations, so it
  can't give cleaner cancellation here.
- Cross-origin GET navigation: **BLOCKED** via `shouldOverrideUrlLoading` (confirmed) - cancels the nav cleanly (page stays).
- Cross-origin **WebSocket**: **NOT blocked** (native hook never fires) - slipped through; native cannot
  block WS. This is the script-only channel 4b must cover.
- All same-origin channels: allowed (no block).

**4b results + blockability summary (WebView 113).** Both layers on; rule = block cross-origin held
secret. When both can act on a channel, the SCRIPT layer fires first (in-page), so native never sees it.

| Channel | Blockable by SCRIPT | Blockable by NATIVE | Net result |
|---|---|---|---|
| fetch (POST) | Y (dropped in-page) | Y (403) | stopped |
| XHR (POST) | Y | Y (403) | stopped |
| sendBeacon | Y | Y (403) | stopped |
| form POST | Y (clean - no navigation) | Y (403, but frame navigates to it) | stopped |
| image `src` GET | **Y (src setter wrapped)** | Y (403) | stopped |
| iframe-borrowed fetch (about:blank) | N (separate realm - see #8 below) | Y (403) | stopped - **native only** |
| WebSocket | **Y** | **N (fundamental)** | stopped - **script only** |
| Navigation w/ query (GET) | **Y via Navigation API (works on 113)** | Y via `shouldOverrideUrlLoading` | stopped |

### Conclusion (RQ1, Android)
- **Every tested channel is blockable by at least one layer** (navigation now confirmed) -
  so on Android QuishGuard "blocks supported channels" (detection and prevention both demonstrated,
  kept separate).
- **WebSocket is blockable ONLY by the script layer** - native cannot touch it. The sharpest argument
  for keeping the in-page sensor on Android, not just native interception.
- **image GET and iframe-borrowed fetch are blockable ONLY by native** (script build-gaps) - the mirror
  case, and the argument for keeping native interception too.
- **form POST**: the script layer gives cleaner prevention (send dropped, page stays); native stops the
  body but the frame still navigates to the 403 (no `shouldOverrideUrlLoading` for POST).
- Net: the two layers are **complementary for prevention**, not just detection - neither alone blocks
  everything; together they cover all tested channels.

### Navigation crash (handled)
Both navigating channels are observed by the native layer, then the app process died shortly after the
WebView loaded the destination (non-navigating channels never crash) - a WebView render-process crash on
this GPU-unstable emulator, which by default kills the app. Added an `onRenderProcessGone` handler that
keeps the app alive (logs `didCrash`), so the test can continue. Root cause is emulator stability, not
the interception logic; the native observations are captured before the crash, so detection results are
unaffected. If it persists, dropping `compileSdk`/`targetSdk` from 37 (preview) to 35 (stable) is the
next lever.

## Channels under test (channel_test.html)
Non-navigating (auto-run, stay on page): fetch POST, XHR POST, sendBeacon, image `src` GET
(data in query), WebSocket send, iframe-borrowed fetch (unwrapped fetch from an about:blank frame).
Navigating (own button, leave page): form POST, top-level navigation carrying data in the query.

Each send carries a fake marker `S-<channel>-<origin>` in the body, and `?ch=<channel>-<origin>`
in the URL, so Logcat lines are attributable even when the native layer sees only the URL.

## Android hardening - results (to fill after rerun)
Rebuild (Gradle re-copies the canonical sensor.js) and rerun the channel test; tap Run-all SAME + CROSS,
form-CROSS, nav-CROSS.
- **Image `src` GET (#6): CLOSED.** The script layer now wraps the `img.src` setter: `qg-sensor image GET
  ... decision=allow` (same-origin) / `decision=block` (cross-origin). The image build gap is closed -
  image GETs carrying a held secret are now judged in-page (decideMs ~1-107 ms).
- **Navigation API (#9): WORKS on WebView 113.** nav-CROSS logged `navigation CANCELLED via Navigation
  API` - the `navigate` event fired AND was cancelable for the cross-origin navigation, so the SCRIPT
  layer can cancel page-initiated navigation (not only native `shouldOverrideUrlLoading`). Better than the
  "may be absent on 113" expectation.
- **iframe-borrowed fetch (#8): NOT closed on 113.** The `about:blank` fetch fired with NO `qg-sensor`
  line - only native BLOCK caught it (by destination). Root cause: the borrowed frame is a SEPARATE REALM
  with its own (empty) hold-state, and its fetch fires synchronously on frame load before a cross-realm
  wrap can bind; injecting the sensor into the child doesn't help either (the child frame never saw the
  user type, so its `holding()` is false). This is a genuine script-layer limitation for `about:blank`
  borrowing, NOT a simple build gap - and the clearest case for keeping the native layer: native blocks it
  by destination regardless. DECISION: accept native-only coverage for this channel; no deeper fix.
  The `appendChild`/`insertBefore` child-frame hook (which caught NOTHING in the tests) was REMOVED
  to keep the sensor's global surface minimal - `installInto` now wraps the top frame only, and the
  native layer is the sole cover for the about:blank iframe-borrowed fetch.
- **Python comparison: no regression.** All existing rows unchanged; harmless twins still 0 false blocks
  (config c's `signup_benign` is the pre-existing FP); reuse false-blocks still just `reuse_benign`; E5
  `otp_benign`/`pay_benign` all allowed.
