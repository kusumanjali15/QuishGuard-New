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
- Android System WebView version: **TODO - fill exact version** (emulator Chrome -> `chrome://version`,
  or Settings -> Apps -> Android System WebView). The feature set depends on this version.
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
| 2 | Form POST, programmatic `.submit()` | **N** | Y | N | `.submit()` does NOT fire the submit event -> script evaded; native still saw the POST |
| 3 | fetch (POST) | Y | Y | N | cross: CORS blocks reading the reply, request still sent |
| 4 | XHR (POST) | Y | Y | N | same as fetch |
| 5 | sendBeacon | Y | Y | N | beacon is no-cors; sent cleanly |
| 6 | image `src` (GET) | **N** | Y | n/a | not wrapped by script; secret rode in the URL query, so **native captured the secret itself** - "no body" does not protect data put in a URL |
| 7 | WebSocket | Y (connect+send) | **N** | - | native hook never fired for WS - **script-only** channel (same-origin send needs a WS server; cross `:8004` fired send) |
| 8 | iframe-borrowed fetch (about:blank) | **N** | Y | N | sensor not injected in the `about:blank` frame -> script blind; native saw the sub-resource (`mainFrame=false`) - **native-only** channel |
| 9 | Navigation w/ query (top-level GET) | **N** | Y | n/a | not wrapped by script; native saw `GET ... mainFrame=true` with the secret in the URL. (App crashed shortly AFTER navigating - see "Navigation crash" below; the native observation was captured before the crash.) |

### What this shows (RQ1)
- **The two layers are complementary and, together, saw every channel tested.**
  - Script-only: **WebSocket** (native blind).
  - Native-only: **image GET, programmatic form `.submit()`, top-level navigation, iframe-borrowed fetch** (script blind).
- **Native sees destinations, never bodies** - but a secret placed in a URL (image GET, navigation query) is in the destination, so native captures it anyway. The body-blindness only hides data in a POST body.
- **One channel's secret value is seen by neither layer: the iframe-borrowed fetch POST body** (script not in the frame; native sees the URL but not the body). Native can still BLOCK it by destination - so prevention is possible even when the value is invisible. This separates detection-by-value from prevention-by-destination.
- **Sensor-hardening notes for later:** wrap `HTMLFormElement.prototype.submit`/`requestSubmit` (programmatic submit), and inject into same-origin child frames; the `about:blank` iframe case is a genuine script-layer gap.

### Navigation crash (open issue)
Both navigating channels (form POST that navigates, and top-level `location` navigation) are observed
by the native layer, then the app process dies (`PROCESS ENDED` / `beginning of crash`) shortly after
the WebView loads the destination. Non-navigating channels never crash. Likely a WebView render-process
crash on this emulator (the AVD showed GPU instability earlier) taking the app down because
`onRenderProcessGone` is not handled. TODO: capture the crash stack (Java `FATAL EXCEPTION` vs native
`SIGSEGV`), add an `onRenderProcessGone` handler, and retest. Does NOT affect the detection results above.

## Channels under test (channel_test.html)
Non-navigating (auto-run, stay on page): fetch POST, XHR POST, sendBeacon, image `src` GET
(data in query), WebSocket send, iframe-borrowed fetch (unwrapped fetch from an about:blank frame).
Navigating (own button, leave page): form POST, top-level navigation carrying data in the query.

Each send carries a fake marker `S-<channel>-<origin>` in the body, and `?ch=<channel>-<origin>`
in the URL, so Logcat lines are attributable even when the native layer sees only the URL.
