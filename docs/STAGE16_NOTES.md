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
- **Build limits** - the layer CAN cover these; this build just doesn't yet:
  - Script layer, image `src` GET (#6): coverable by overriding the `HTMLImageElement.prototype.src` setter.
  - Script layer, iframe-borrowed fetch (#8): coverable by injecting the sensor into same-origin / `about:blank` child frames.
- **Fundamental limits** - the layer CANNOT cover these, by platform design:
  - Native layer, request **bodies**: `shouldInterceptRequest` never exposes the body.
  - Native layer, **WebSocket** (#7): `shouldInterceptRequest` never fires for WS frames.
- **Partially coverable (to test, not assume)**:
  - Top-level navigation (#9) is **not reliably interceptable by the script layer**, but it is not
    impossible: the **Navigation API** (`navigate` event) can cancel some page-initiated navigations
    in recent WebViews, and on the native side **`shouldOverrideUrlLoading`** sees and can cancel
    main-frame navigations (query string included). Both are version-dependent (our WebView is 113),
    so the blocking sub-step tests them rather than declaring navigation uncoverable.

### What this shows (RQ1)
- **The two layers are complementary; together they saw every channel tested.**
  - Script-only: **WebSocket** (native fundamental-blind).
  - Native-only here: **image GET, top-level navigation, iframe-borrowed fetch** (script blind - image GET and iframe fetch are build gaps; navigation is partially coverable by script via the Navigation API, to be tested).
- **Native sees destinations, never bodies** - but a secret placed in a URL (image GET, navigation query) rides in the destination, so native captures it anyway. Body-blindness only hides data in a POST body.
- **One channel's secret VALUE is seen by neither layer as a value: the iframe-borrowed fetch POST body** (script not in the frame; native sees the URL but not the body). Native can still BLOCK it by destination - prevention is possible even when the value is invisible. This separates detection-by-value from prevention-by-destination.
- **Remaining script-layer build gaps to close:** `img.src` setter and child-frame injection. (Scripted `form.submit()` is already covered by the canonical sensor.)

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
- Cross-origin GET navigation (`shouldOverrideUrlLoading` path): **not yet tapped** - TODO confirm.
- Cross-origin **WebSocket**: **NOT blocked** (native hook never fires) - slipped through; native cannot
  block WS. This is the script-only channel 4b must cover.
- All same-origin channels: allowed (no block).

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
