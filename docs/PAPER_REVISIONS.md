# QuishGuard paper — replacement passages (revision 1)

How to use this file: each block names the section and what it replaces. Paste the text over the old passage.
`[DATA NEEDED: …]` = a value that still has to be measured; do not fill it with a guess.
`[NEW REF: …]` = a reference to add to the bibliography (check every one before submitting).
`[VERIFY: …]` = a claim I could not confirm; check it before keeping it.

Lab facts used below come from the code in `quishguard-fresh` (sensor.js, guard.py, sensitive.py, run_comparison.py, lab/attacks/*.html), not from a new run.

---

## 1. Abstract — replace the whole abstract

> QR-code phishing (quishing) moves victims from protected e-mail clients onto mobile phones, where most defences judge the link rather than what the opened page does. The closest prior work, WHALE, analyses each QR-decoded page in a sandboxed WebView before releasing it to the user; its authors report that non-credential scams, backend-dead kits, CAPTCHA- or MFA-gated flows, sandbox-aware pages and behaviour beyond the observation window remain outside its evaluation. Send-time protection of typed passwords is an older idea, realised in SpoofGuard, AntiPhish, Google Password Alert and Microsoft Enhanced Phishing Protection, but these tools protect previously known passwords on desktop browsers or operating systems. This paper presents the design of QuishGuard, which brings send-time protection to Android in-app WebViews opened from QR scans. A script injected before the page's own code is designed to hold any request that carries a typed secret, such as a password, one-time code, card number or account-linking code, until the request is judged; a native network layer is designed to block every further request on supported channels once a page is judged malicious, including requests to the page's own origin. We describe the design, a Python laboratory implementation (the Android implementation is in progress) and an evaluation methodology that measures which outbound channels Android can block and tests whether adversary-in-the-middle (AiTM) relays defeat decoy-credential probing. In an initial analysis of 136,414 phishing-page captures, 68.3% of the 28,879 pages with a form declared no explicit submission address, so the data is either posted back to the page's own URL or handled by script. In a laboratory suite of six evasive attack pages written by the author, the prototype prevented the fake secret from leaving in four scenarios; in one of them the block relied on reading the request body, which Android's native interception cannot do. It did not stop a WebSocket send behind a CAPTCHA or an account-linking-code lure.

*Changes:* "is designed to" for unbuilt Android parts; "supported channels"; "initial" not "first"; 68.3% reworded; Android caveat on the four; the 0/6 false-positive result moved out of the abstract (six author-written benign pages are too little for an abstract claim).

---

## 2. Introduction — replace the first contribution bullet

> • A two-layer design that brings send-time protection to Android in-app WebViews, is intended to protect any typed secret rather than known passwords only, targets modern send channels and contains the page after a malicious verdict, same-origin requests included (Section IV). Coverage of the WebSocket and linking-code cases is a design goal not yet met by the prototype (Section VII).

## 2b. Introduction — replace the prevalence bullet

> • An initial prevalence analysis of 136,414 phishing page captures that characterises what pages expose at load time (Section VII).

---

## 3. Section II-B — add at the end of "URL-based and visual detection"

> A further line of pre-release work classifies the QR code image itself, before any URL is opened, from pixel patterns or structural features [NEW REF: arXiv 2505.03451, "Detecting quishing attacks with machine learning techniques through QR code analysis"], [NEW REF: QRïS, arXiv 2510.17175], including custom-designed "fancy" codes [NEW REF: ALFA, arXiv 2601.06768]. Browsers also ship client-side page classifiers that score a page once it has loaded [NEW REF: Chrome client-side phishing detection — find a citable source]. Like the systems above, these decide before or at load and do not observe where typed data is sent.

## 3b. Section II-D — add after the Microsoft Enhanced Phishing Protection sentence

> [VERIFY: whether Chrome's password protection / phished-password warnings run in Chrome on Android. If yes, add:] Chrome's password protection service warns when a saved or Google-account password is entered on a page classified as phishing [NEW REF], but it covers passwords the browser already knows and runs in the browser, not in the WebViews of other applications.

*Also in II-D:* if the check above shows Android coverage, change "run on desktop browsers or the desktop operating system" to "run in browsers or the operating system rather than in third-party WebViews".

---

## 4. Section III-A — add at the end of the threat model

> Several attacker strategies fall outside what QuishGuard can observe, and we state them explicitly. First, the injected script recognises a secret by finding the typed value in an outgoing request; a kit that encrypts or otherwise transforms the value in the page before sending it (for example, XOR with a server-supplied nonce) defeats this matching, and a request that carries no recognisable value is released by Algorithm 1. A defence against this case must judge sends by page state, for example by holding every send made after a sensitive field has been filled, rather than by content; we treat this as an open design question and test it in E3. Second, QR-login hijacking, in which the victim scans a device-linking QR code that grants the attacker a session, involves no typed secret and is out of scope. Third, phishing-resistant authentication such as passkeys removes the password from the attack altogether; QuishGuard targets the secrets that remain typed, such as one-time codes, card numbers and linking codes. Finally, QuishGuard protects only the path in which a QR scan opens an in-app WebView; scans made with the system camera usually open the default browser or a Custom Tab, which a host application cannot instrument. [DATA NEEDED: share of QR scans that end in an in-app WebView, or a citation estimating it.]

---

## 5. Section IV-B (Layer 1) — replace the last two sentences

> Any send whose content carries a sensitive value is held until the risk engine has judged it. The value is read from the field at send time rather than reconstructed from keystrokes, so that autofilled and pasted values are also covered [DATA NEEDED: confirm the sensor reads field values, not only key events]. "Holding" differs by channel: a fetch call can be delayed by withholding its promise, whereas sendBeacon returns immediately and form.submit() or an assignment to location navigates at once, so for these channels the script must decide synchronously or cancel and replay the send. Which channels can be held, and how, is measured in E1. Matching looks for the typed value in its plain and URL-encoded forms, in the spirit of Senol et al. [17]; values that the page transforms before sending are not matched (Section III-A).

## 6. Section IV-C (Layer 2) — replace the whole subsection text

> Native interception, available on Android through the shouldInterceptRequest callback [19], sees most HTTP(S) requests that leave the page, including requests issued by code that escapes the script hooks. It has documented gaps: it exposes the destination of a request but not its body, it does not expose WebSocket messages, requests made by service workers require a separate client interface, and WebRTC data channels are not visible at all. The network layer therefore serves as a backstop rather than a complete view. After a malicious verdict it refuses every further request it can see, and it lets the evaluation measure which sends the script layer failed to observe. Before a verdict it can still match typed values that appear in a request URL, for example in query parameters, because the URL is available on Android; values carried only in a request body can be matched on Android only by the script layer.

## 7. Section IV-E (Enforcement) — replace the "Containment" sentence

> Containment then blocks every further request the network layer can see from the page, including requests to its own origin, because a kit may post to the domain that hosts it; in our prevalence sample, 68.3% of pages with a form declare no explicit submission address and therefore post to their own URL unless a script intervenes, and a further 12.0% submit to an explicit same-site address (Section VII). Refusing new requests does not close a WebSocket connection that is already open, so containment also closes open sockets from the injected script and, if that fails, navigates the WebView away from the page [DATA NEEDED: confirm this is implemented, or state it as planned].

---

## 8. Section V (Implementation) — replace from "It wraps fetch, XMLHttpRequest and sendBeacon…" to the end of the section

> It wraps fetch, XMLHttpRequest, sendBeacon and form submission, both through the submit event and through scripted calls to form.submit(), and holds sends that carry sensitive values until the Python side returns a verdict. WebSocket.send and image-request URLs are not wrapped in the current build. The network layer uses Playwright request routing to abort requests; unlike Android's native interception, it can read request bodies, so laboratory results for this layer are an upper bound on what Android can achieve. Sensitive-value matching has unit tests for form-encoded, query-string and URL-encoded values; JSON bodies and other encodings are not yet covered.
>
> In the laboratory runs reported in Section VII, the network layer was given the fake password and one-time code in advance by the test harness, rather than learning them from the in-page sensor. This isolates the blocking mechanism from field detection, but it means the results do not yet test whether the sensor identifies the right fields; in particular, the linking code was not among the supplied values (Section VII). Wiring the sensor's observed values into the network layer is in progress. QR codes are generated with the qrcode library and decoded with OpenCV.
>
> [DATA NEEDED: software versions (Python, Playwright, Chromium), hardware used, number of unit tests and lines of code]

---

## 9. Section VI-A — replace the "Each scenario runs under three conditions…" sentence onward

> Each scenario runs under three conditions: no protection, a load-time check that inspects the page once at load, and QuishGuard. The load-time check is a stand-in for a static pre-release stage only, not for WHALE as a whole; by construction it cannot see content that appears after load, so its misses on delayed content show what a single inspection cannot observe rather than a weakness of WHALE, whose dynamic stage runs for several seconds. For each run we record two outcomes separately: detection, meaning the condition judged the page malicious, and prevention, meaning the fake secret did not reach the attacker collector. When a send is stopped we also record which layer stopped it.

*Also fill Table IV's "Harmless counterpart" column from the lab files:* early send → `beacon_benign.html`; pixel keylogger → `pixel_benign.html`; delayed form → `otp_late_benign.html`; CAPTCHA + WebSocket → `captcha_ws_benign.html`; linking-code lure → `link_scam_benign.html`; hook evasion → `iframe_evade_benign.html`. Describe in one line each what the benign page does (e.g. "same flow, sends to the page's own legitimate endpoint").

---

## 10. Section VI-B (Prevalence) — replace the first two sentences, and add a sentence at the end

> To estimate how often the open cases may arise (RQ2), we analysed the phishing-snapshots dataset [22], a third-party collection of 136,414 captures of phishing pages made with a headless browser in July and August 2024 [DATA NEEDED: source feeds of the dataset and how pages were labelled as phishing; if unknown, say so]. Each capture is a single snapshot without interaction.

Add at the end:

> Captures of the same kit are not independent, so confidence intervals computed per capture understate the true uncertainty; we therefore also report shares among structurally unique pages.

---

## 11. Section VII-A — replace the whole subsection text

> Table VI reports the outcome of each scenario. Without protection, the fake secret reached the collector in all six scenarios. The load-time check judged three attack pages malicious at load: the early send, the pixel keylogger and the hook-evasion page, which show a brand and a password field when they load. It did not flag the delayed form, the CAPTCHA-gated WebSocket page or the linking-code lure, whose relevant content is either absent at load or not credential-like. [DATA NEEDED: whether a load-time flag also prevented the send in each case.]
>
> QuishGuard prevented the leak in four scenarios: the early send, the pixel keylogger, the delayed form and the hook-evasion page. These results do not transfer to Android equally. The hook-evasion page sends through a fetch borrowed from an inline frame, which the script does not wrap, and places the password in the request body; it was stopped by the laboratory network layer reading that body, which Android's native interception cannot do. The pixel keylogger places the password in an image-request URL, which is also unwrapped; it was stopped by the network layer matching the URL, which Android does expose. The early send and the delayed form use wrapped interfaces (sendBeacon and fetch) and can be stopped by the script layer. [DATA NEEDED: confirm the stopping layer per scenario by logging it in run_comparison.py; the attributions above are derived from the page code and the wrapped-interface list.]
>
> QuishGuard did not stop the WebSocket send behind the CAPTCHA, because WebSocket.send is not wrapped and native interception does not see WebSocket messages, or the linking-code lure, because the linking code was not among the values supplied to the network layer (Section V). No harmless counterpart page was blocked under any condition (0 of 6). These results come from six pages written by the author [DATA NEEDED: number of runs per scenario]; they show whether the mechanism works on these behaviours, not detection rates on real phishing pages.

### Table VI — new title and columns

**Title:** LABORATORY RESULTS. PREVENTION: DID THE FAKE SECRET REACH THE COLLECTOR? (DETECTION BY THE LOAD-TIME CHECK SHOWN SEPARATELY)

| Scenario | No protection (prevention) | Load-time check (detection) | QuishGuard (prevention) | Stopping layer* | Android feasible? |
|---|---|---|---|---|---|
| Early send | Leaked | Flagged | Not leaked | Script or network | Yes (script) |
| Pixel keylogger | Leaked | Flagged | Not leaked | Network (URL) | Likely (URL visible) |
| Delayed form | Leaked | Missed | Not leaked | Script or network | Yes (script) |
| CAPTCHA + WebSocket | Leaked | Missed | Leaked | – | – |
| Linking-code lure | Leaked | Missed | Leaked | – | – |
| Hook evasion | Leaked | Flagged | Not leaked | Network (body) | No (body not visible) |
| Harmless pages blocked | 0/6 | 0/6 | 0/6 | – | – |

*Footnote:* \*Derived from the page code and the list of wrapped interfaces; to be confirmed by per-send logging.

---

## 12. Section VII-B — replace from "Among the 28,879 pages that contain a form…" to the end of the subsection

> Among the 28,879 pages that contain a form element, 68.3% have an empty or "#" action. Under the HTML specification such a form submits to the page's own URL, unless a script intercepts the submission and sends the data elsewhere; the markup alone therefore does not show whether the data stays on the page's origin or is redirected by script. A further 19.8% submit to another registrable domain and 12.0% to an explicit address on the same site. Two consequences follow. First, a large majority of forms either post to their own origin or are script-driven, which supports containing same-origin requests after a malicious verdict. Second, for these forms the final destination of the data can only be observed when the data is sent, which is the point at which QuishGuard acts. Pages that collect input without a form element are not counted in these figures [DATA NEEDED: number of pages with input fields but no form element]. Requests for codes or payments without a password are rare in this predominantly English-language dataset, so the evaluation of such scams relies on laboratory pages.

*Also in VII-B, after Table VII:* add one sentence saying what the remaining captures are, e.g. "The remaining [DATA NEEDED]% of captures are error pages, parked domains or pages that had been taken down at capture time."

*Also:* change "For each percentage of captures, the 95% confidence interval lies within ±0.3 percentage points" to "For each percentage of captures, the nominal 95% confidence interval lies within ±0.3 percentage points; because captures of the same kit are correlated, the true uncertainty is larger."

---

## 13. Section VIII (Discussion) — replace the second paragraph

> The prevalence analysis is consistent with the motivation for send-time protection: for most forms in the sample, the markup does not show whether data will stay on the page's origin or be redirected by script, and the destination becomes certain only at send time. This does not imply that pre-release analysis is ineffective, since a dynamic stage such as WHALE's performs a real submission and can observe the destination; nor does it show that QuishGuard detects more attacks. That question is addressed by E3 and depends on results not yet available. The laboratory suite is designed to show whether the mechanism holds a send and contains a page under evasive behaviours, but it uses scripted pages written by the author and cannot stand in for the diversity of real kits, which is why the DynaPD experiments are planned.

## 13b. Section VIII — replace the last sentence of the third paragraph

> …but it inherits a dependence on script hooks that a page may try to evade [18], and on recognising the typed value in the outgoing request, which a page can defeat by transforming the value before sending (Section III-A). Native interception limits but does not remove the first risk, because on Android it sees only destinations, and it does not address the second.

---

## 14. Section IX — add to "Internal validity"

> In the laboratory runs the network layer was given the fake secrets by the test harness rather than learning them from the in-page sensor (Section V), so field detection was not tested end to end.

## 14b. Section IX — add to "Limitations of the approach", after the first sentence

> One of the four laboratory blocks, the hook-evasion page, depended on reading the request body and would not have been prevented by Android's native interception (Table VI). Value matching covers plain and URL-encoded values only; JSON bodies and values transformed by the page are not matched.

---

## 15. Section XI (Conclusion) — replace the third and fourth sentences

> A laboratory implementation realises the mechanism for the channels it wraps, and an initial prevalence analysis indicates that most phishing forms either post back to their own page or are handled by script, so that where the data finally goes is certain only when it is sent.

---

## 16. Small fixes anywhere in the text

- **Section II-C, WHALE results:** use one format, e.g. "an F1-score of 0.939 for the static model and 0.920 for the dynamic model".
- **"pages written by the authors"** → "pages written by the author" (single-author paper). "We" is fine.
- **Section VIII, first paragraph:** "the coverage claims in Sections IV and III remain design goals" — keep, and put the claims in order: "Sections III and IV".
- **Reference [1] (WHALE):** [VERIFY: I could not find this paper by web search; confirm the DOI resolves.]
- **Reference [7]:** [VERIFY: the Microsoft support URL for Enhanced Phishing Protection.]
- **Introduction, Taiwan sentence:** the [REFERENCE NEEDED] is the only evidence for the linking-code scenario; fill it before anyone else reads the draft.
