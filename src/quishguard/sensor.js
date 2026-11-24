// QuishGuard in-page sensor (Stage 10; E5 + Android-hardening update).
// Injected at document start, BEFORE the page's own scripts (Android: addDocumentStartJavaScript).
// 1. Watches typing in sensitive fields.  2. Holds every send once something sensitive is typed.
// 3. Asks the host (window.__qg_decide) to judge it, then releases or drops it.
// Channel wraps are installed via installInto(win) into the top frame AND same-origin / about:blank
// child frames, so an iframe-borrowed send is covered by the TOP frame's hold state.
(() => {
  // Sensitive fields: password & one-time-code always; card number / CVV (card is in scope:
  // password / OTP / card); a "code/pin" field only with a credential-ish word. promo/postal/zip
  // and country codes are NOT sensitive. (Mirrored by tests/sensor_fields.test.mjs.)
  function isSensitiveField(el) {
    if (!(el instanceof HTMLInputElement)) return false;
    if (el.type === "password") return true;
    if (el.autocomplete === "one-time-code") return true;
    if (el.autocomplete === "cc-number" || el.autocomplete === "cc-csc") return true;
    const hay = `${el.name} ${el.placeholder} ${el.id} ${el.getAttribute("aria-label") || ""}`.toLowerCase();
    if (/\b(otp|one[\s-]?time|2fa)\b/.test(hay)) return true;
    return /\b(code|pin)\b/.test(hay) && /\b(linking|verification|verify|pairing|auth)/.test(hay);
  }

  const typed = new Map(); // input element -> typed value (lives in the TOP frame)
  const typedValues = () => [...typed.values()].filter((v) => v);
  const holding = () => typedValues().length > 0; // hold-by-default once anything sensitive is typed

  // Watch typing in the top frame (capture phase).
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (isSensitiveField(el)) {
      typed.set(el, el.value);
      if (window.__qg_observe) window.__qg_observe(typedValues()); // share with the network layer
    }
  }, true);

  function bodyText(body) {
    if (body == null) return null;
    if (typeof body === "string") return body;
    if (body instanceof URLSearchParams) return body.toString();
    if (body instanceof FormData) return new URLSearchParams(body).toString();
    return String(body); // e.g. Blob -> "[object Blob]" (not readable here: known limitation)
  }

  // Always calls the TOP frame's __qg_decide (host bridge lives there), even for child frames.
  async function judge(channel, method, url, body) {
    const verdict = await window.__qg_decide({
      channel, method, body,
      url: new URL(url, location.href).href,
      pageUrl: location.href, title: document.title, typed: typedValues(),
    });
    return verdict === "allow";
  }

  // Install channel wraps into one window (top frame or a same-origin / about:blank child frame).
  function installInto(win) {
    if (!win) return;
    try { if (win.__qg_installed) return; win.__qg_installed = true; } catch (e) { return; }

    // --- fetch ---
    const originalFetch = win.fetch;
    if (originalFetch) win.fetch = async function (input, init = {}) {
      if (!holding()) return originalFetch.call(this, input, init);
      const url = (win.Request && input instanceof win.Request) ? input.url : String(input);
      const method = (init.method || ((win.Request && input instanceof win.Request) ? input.method : "GET")).toUpperCase();
      if (await judge("fetch", method, url, bodyText(init.body))) return originalFetch.call(this, input, init);
      throw new TypeError("QuishGuard blocked this request");
    };

    // --- XMLHttpRequest ---
    const XP = win.XMLHttpRequest && win.XMLHttpRequest.prototype;
    if (XP) {
      const originalOpen = XP.open, originalSend = XP.send;
      XP.open = function (method, url, ...rest) {
        this.__qg = { method: String(method).toUpperCase(), url: String(url) };
        return originalOpen.call(this, method, url, ...rest);
      };
      XP.send = function (body) {
        if (!holding() || !this.__qg) return originalSend.call(this, body);
        const { method, url } = this.__qg;
        judge("xhr", method, url, bodyText(body)).then((ok) => (ok ? originalSend.call(this, body) : this.abort()));
      };
    }

    // --- navigator.sendBeacon ---
    const nav = win.navigator;
    if (nav && nav.sendBeacon) {
      const originalBeacon = nav.sendBeacon.bind(nav);
      nav.sendBeacon = function (url, data) {
        if (!holding()) return originalBeacon(url, data);
        judge("beacon", "POST", url, bodyText(data)).then((ok) => { if (ok) originalBeacon(url, data); });
        return true; // beacons must answer at once; the real send happens later, if allowed
      };
    }

    // --- image src (Android build-gap #4): setter + setAttribute('src') ---
    const IP = win.HTMLImageElement && win.HTMLImageElement.prototype;
    if (IP) {
      const desc = Object.getOwnPropertyDescriptor(IP, "src");
      if (desc && desc.set) Object.defineProperty(IP, "src", {
        configurable: true, enumerable: desc.enumerable, get: desc.get,
        set: function (v) {
          if (!holding()) return desc.set.call(this, v);
          judge("image", "GET", v, null).then((ok) => { if (ok) desc.set.call(this, v); });
        },
      });
      const originalSetAttr = IP.setAttribute;
      IP.setAttribute = function (name, value) {
        if (holding() && name && String(name).toLowerCase() === "src") {
          judge("image", "GET", value, null).then((ok) => { if (ok) originalSetAttr.call(this, name, value); });
          return;
        }
        return originalSetAttr.call(this, name, value);
      };
    }

    // --- form submit (button press, and form.submit() called by scripts) ---
    const FP = win.HTMLFormElement && win.HTMLFormElement.prototype;
    if (FP && win.document) {
      const originalSubmit = FP.submit;
      const judgeForm = (form) => {
        const method = (form.method || "get").toUpperCase();
        const data = new URLSearchParams(new FormData(form)).toString();
        const url = method === "GET" ? `${form.action}?${data}` : form.action;
        judge("form", method, url, method === "GET" ? null : data)
          .then((ok) => { if (ok) originalSubmit.call(form); });
      };
      win.document.addEventListener("submit", (event) => {
        if (!holding()) return;
        event.preventDefault(); // hold it
        judgeForm(event.target);
      }, true);
      FP.submit = function () { if (!holding()) return originalSubmit.call(this); judgeForm(this); };
    }

    // --- WebSocket ---
    // Android note: shouldInterceptRequest cannot see WebSocket, so this JS layer is the ONLY cover.
    const OriginalWebSocket = win.WebSocket;
    if (OriginalWebSocket) {
      function GuardedWebSocket(url, protocols) {
        const ws = protocols === undefined
          ? new OriginalWebSocket(url) : new OriginalWebSocket(url, protocols);
        const realSend = ws.send.bind(ws);
        ws.send = function (data) {
          if (!holding()) return realSend(data);
          judge("websocket", "SEND", url, bodyText(data))
            .then((ok) => { if (ok) realSend(data); else ws.close(); });
        };
        return ws;
      }
      GuardedWebSocket.prototype = OriginalWebSocket.prototype;
      ["CONNECTING", "OPEN", "CLOSING", "CLOSED"].forEach((k) => { GuardedWebSocket[k] = OriginalWebSocket[k]; });
      win.WebSocket = GuardedWebSocket;
    }
  }

  installInto(window); // the top frame

  // Navigation API (Android build-gap #9, TEST on WebView 113 - do not assume it works).
  // The 'navigate' event needs a SYNCHRONOUS verdict to preventDefault in-event; the Android host
  // bridge (window.QG.decide) is sync. In Python/Playwright there is no sync bridge, so this is a
  // no-op there (navigation is covered by the network guard). Records whether it actually cancels.
  try {
    if (window.navigation && typeof window.navigation.addEventListener === "function") {
      window.navigation.addEventListener("navigate", (e) => {
        if (!holding()) return;
        const sync = (window.QG && typeof window.QG.decide === "function")
          ? window.QG.decide("navigation", "GET", e.destination ? e.destination.url : "", null) : "allow";
        if (sync === "block") {
          if (e.cancelable) { e.preventDefault();
            console.log("[qg-sensor] navigation CANCELLED via Navigation API -> " + (e.destination && e.destination.url));
          } else {
            console.log("[qg-sensor] navigation NOT cancelable via Navigation API (113?) -> " + (e.destination && e.destination.url));
          }
        }
      });
    }
  } catch (err) {}

  // NOTE: an earlier build also hooked Node.prototype.appendChild/insertBefore to install into
  // child frames (Android build-gap #5). It caught NOTHING in the tests - the about:blank
  // iframe-borrowed fetch fired before any cross-realm wrap could bind and was blocked by the
  // native layer instead - so it was removed to keep the sensor's global surface minimal. The
  // about:blank iframe channel is accepted as NATIVE-ONLY (see docs/STAGE16_NOTES.md #8).
})();
