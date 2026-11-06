// QuishGuard in-page sensor (Stage 10).
// Injected at document start, BEFORE the page's own scripts (Android: addDocumentStartJavaScript).
// 1. Watches typing in sensitive fields.  2. Holds every send once something sensitive is typed.
// 3. Asks Python (window.__qg_decide) to judge it, then releases or drops it.
(() => {
  const SENSITIVE = 'input[type="password"], input[autocomplete="one-time-code"]';
  const typed = new Map(); // input element -> what the user has typed in it

  // 1. Watch typing (capture phase: we see it before the page's own handlers).
  document.addEventListener("input", (event) => {
    const el = event.target;
    if (el instanceof HTMLInputElement && el.matches(SENSITIVE)) typed.set(el, el.value);
  }, true);

  const typedValues = () => [...typed.values()].filter((v) => v);
  const holding = () => typedValues().length > 0; // hold-by-default once anything sensitive is typed

  // Turn a send's body into text Python can check.
  function bodyText(body) {
    if (body == null) return null;
    if (typeof body === "string") return body;
    if (body instanceof URLSearchParams) return body.toString();
    if (body instanceof FormData) return new URLSearchParams(body).toString();
    return String(body); // e.g. Blob -> "[object Blob]" (not readable here: known limitation)
  }

  // 2+3. Ask Python. Resolves to true (release) or false (drop).
  async function judge(channel, method, url, body) {
    const verdict = await window.__qg_decide({
      channel, method, body,
      url: new URL(url, location.href).href,
      pageUrl: location.href, title: document.title, typed: typedValues(),
    });
    return verdict === "allow";
  }

  // --- fetch ---
  const originalFetch = window.fetch;
  window.fetch = async function (input, init = {}) {
    if (!holding()) return originalFetch.call(this, input, init);
    const url = input instanceof Request ? input.url : String(input);
    const method = (init.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
    if (await judge("fetch", method, url, bodyText(init.body))) return originalFetch.call(this, input, init);
    throw new TypeError("QuishGuard blocked this request");
  };

  // --- XMLHttpRequest ---
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__qg = { method: String(method).toUpperCase(), url: String(url) };
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function (body) {
    if (!holding()) return originalSend.call(this, body);
    const { method, url } = this.__qg;
    judge("xhr", method, url, bodyText(body)).then((ok) => (ok ? originalSend.call(this, body) : this.abort()));
  };

  // --- navigator.sendBeacon ---
  const originalBeacon = navigator.sendBeacon.bind(navigator);
  navigator.sendBeacon = function (url, data) {
    if (!holding()) return originalBeacon(url, data);
    judge("beacon", "POST", url, bodyText(data)).then((ok) => { if (ok) originalBeacon(url, data); });
    return true; // beacons must answer at once; the real send happens later, if allowed
  };

  // --- form submit (button press, and form.submit() called by scripts) ---
  const originalSubmit = HTMLFormElement.prototype.submit;
  function judgeForm(form) {
    const method = (form.method || "get").toUpperCase();
    const data = new URLSearchParams(new FormData(form)).toString();
    const url = method === "GET" ? `${form.action}?${data}` : form.action;
    judge("form", method, url, method === "GET" ? null : data)
      .then((ok) => { if (ok) originalSubmit.call(form); });
  }
  document.addEventListener("submit", (event) => {
    if (!holding()) return;
    event.preventDefault(); // hold it
    judgeForm(event.target);
  }, true);
  HTMLFormElement.prototype.submit = function () {
    if (!holding()) return originalSubmit.call(this);
    judgeForm(this);
  };
})();
