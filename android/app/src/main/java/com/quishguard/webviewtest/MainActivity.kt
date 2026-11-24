package com.quishguard.webviewtest

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

class MainActivity : AppCompatActivity() {

    // One lab page, reached via 10.0.2.2 — the emulator's alias for the PC's 127.0.0.1.
    private val labUrl = "http://10.0.2.2:8003/channel_test.html"
    private val labOrigin = "http://10.0.2.2:8003"

    // The SCRIPT LAYER: our sensor, injected to run BEFORE the page's own scripts.
    // It lives inside the page, so it can see TYPED VALUES (form/fetch bodies) — the
    // thing the native layer (2c) cannot. Minimal for now: a boot line + wrap fetch +
    // capture form submits, all reported via console.log.
    private val sensorJs = """
        (function () {
          const tag = '[qg-sensor]';
          console.log(tag + ' installed at document-start on ' + location.origin);

          // fetch
          const of = window.fetch;
          window.fetch = function (input, init) {
            const url = (typeof input === 'string') ? input : (input && input.url);
            const body = (init && init.body) ? init.body : '';
            console.log(tag + ' fetch -> ' + url + ' body=' + body);
            return of.apply(this, arguments);
          };

          // XMLHttpRequest
          const xo = XMLHttpRequest.prototype.open;
          XMLHttpRequest.prototype.open = function (m, u) { this.__qg_u = u; return xo.apply(this, arguments); };
          const xs = XMLHttpRequest.prototype.send;
          XMLHttpRequest.prototype.send = function (b) {
            console.log(tag + ' xhr -> ' + this.__qg_u + ' body=' + (b || ''));
            return xs.apply(this, arguments);
          };

          // sendBeacon
          if (navigator.sendBeacon) {
            const ob = navigator.sendBeacon.bind(navigator);
            navigator.sendBeacon = function (u, d) {
              console.log(tag + ' beacon -> ' + u + ' body=' + (d || ''));
              return ob(u, d);
            };
          }

          // WebSocket
          const OW = window.WebSocket;
          if (OW) {
            window.WebSocket = function (url, protocols) {
              console.log(tag + ' websocket connect -> ' + url);
              const ws = protocols ? new OW(url, protocols) : new OW(url);
              const os = ws.send.bind(ws);
              ws.send = function (d) { console.log(tag + ' websocket send body=' + d); return os(d); };
              return ws;
            };
            window.WebSocket.prototype = OW.prototype;
          }

          // form submit (navigating or not)
          document.addEventListener('submit', function (e) {
            const data = new FormData(e.target);
            const pairs = [];
            for (const [k, v] of data.entries()) pairs.push(k + '=' + v);
            console.log(tag + ' form submit -> ' + (e.target.action || location.href)
                        + ' body=' + pairs.join('&'));
          }, true);

          // NOTE: image src GET and top-level navigation are deliberately NOT wrapped here -
          // those are the channels where the script layer is weak; we measure what each layer
          // naturally catches.
        })();
    """.trimIndent()

    @SuppressLint("SetJavaScriptEnabled")   // lab pages (and our sensor) need JS
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val web = WebView(this)
        setContentView(web)
        web.settings.javaScriptEnabled = true

        // Pipe the page's console.log (incl. our sensor) into Android Logcat so we can read it.
        web.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                Log.i("qg-console", m.message() + "  (" + m.sourceId() + ":" + m.lineNumber() + ")")
                return true
            }
        }

        // The NATIVE LAYER: fires for requests the WebView makes. Runs OUTSIDE the page
        // (hard to evade) but sees only the DESTINATION — never the body. Observe only for
        // now (return null = let it proceed). Watch whether a navigating form POST even
        // appears here (it often does NOT).
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView?,
                request: WebResourceRequest?,
            ): WebResourceResponse? {
                if (request != null) {
                    Log.i("qg-native", request.method + " -> " + request.url +
                        "  mainFrame=" + request.isForMainFrame)   // no body is available here
                }
                return null
            }

            // If the WebView's render process dies (common on a slow/unstable emulator, and a real
            // risk in production), the DEFAULT behavior is to kill our whole app. Handle it so the
            // app survives, and we can keep reading Logcat. Returning true = "we handled it".
            override fun onRenderProcessGone(view: WebView?, detail: RenderProcessGoneDetail?): Boolean {
                Log.e("qg-native", "WebView render process gone (didCrash=" +
                    (detail?.didCrash()) + "); keeping the app alive")
                (view?.parent as? android.view.ViewGroup)?.removeView(view)
                view?.destroy()
                return true
            }
        }

        // Script layer: inject ONLY if the installed WebView supports document-start scripts.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            WebViewCompat.addDocumentStartJavaScript(web, sensorJs, setOf(labOrigin))
            Log.i("qg-setup", "DOCUMENT_START_SCRIPT supported: sensor injected")
        } else {
            Log.w("qg-setup", "DOCUMENT_START_SCRIPT NOT supported — update Android System WebView")
        }

        web.loadUrl(labUrl)
    }
}
