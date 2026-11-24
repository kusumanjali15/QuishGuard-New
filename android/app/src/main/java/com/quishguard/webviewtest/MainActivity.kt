package com.quishguard.webviewtest

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

class MainActivity : AppCompatActivity() {

    private val labUrl = "http://10.0.2.2:8003/channel_test.html"
    private val labOrigin = "http://10.0.2.2:8003"

    // Blocking sub-step 4a (native). LAB MECHANISM TEST, not a deployable policy: once armed, a held
    // secret may go SAME-origin but is blocked CROSS-origin. (A real page legitimately loads
    // cross-origin resources, so this exact rule is not shippable - we are testing whether the native
    // layer CAN stop each channel.)
    private val blockingEnabled = true

    private fun originOf(url: String): String = try {
        val u = java.net.URI(url)
        (u.scheme ?: "") + "://" + (u.host ?: "") + (if (u.port == -1) "" else ":" + u.port)
    } catch (e: Exception) { "" }

    private fun blocked(): WebResourceResponse = WebResourceResponse(
        "text/plain", "utf-8", 403, "Blocked", emptyMap(),
        java.io.ByteArrayInputStream("blocked by QuishGuard".toByteArray()))

    private fun authorityOf(url: String): String = try {
        val u = java.net.URI(url)
        (u.host ?: "") + (if (u.port == -1) "" else ":" + u.port)
    } catch (e: Exception) { "" }

    // Bridge exposed to the page as window.QG. SECURITY: addJavascriptInterface exposes native code
    // to JS - only safe for TRUSTED / lab pages (which ours are). The sensor's __qg_decide calls this
    // and gets a synchronous allow/block back. Rule mirrors 4a (cross-authority = block when armed),
    // but here the SCRIPT layer enforces it - covering WebSocket, which native cannot.
    inner class QgBridge {
        @JavascriptInterface
        fun decide(channel: String, method: String, url: String, body: String?): String {
            val labAuthority = authorityOf(labOrigin)                 // 10.0.2.2:8003
            val dest = authorityOf(url)
            val block = blockingEnabled && dest.isNotEmpty() && dest != labAuthority
            Log.i("qg-decide", channel + " " + method + " -> " + url + " => " + (if (block) "block" else "allow"))
            return if (block) "block" else "allow"
        }
    }

    // Observe-only shim. The CANONICAL sensor (assets/sensor.js, copied from
    // src/quishguard/sensor.js) calls window.__qg_decide / window.__qg_observe. Until the native
    // decision bridge is wired (blocking sub-step), these stubs LOG each judged send and allow it,
    // so Android coverage is measured with the SAME sensor logic as the Python lab.
    private val observeShim = """
        (function () {
          if (!window.__qg_decide) window.__qg_decide = function (info) {
            var d = (window.QG && window.QG.decide)
              ? window.QG.decide(info.channel, info.method || '', info.url || '',
                                 info.body == null ? '' : String(info.body))
              : 'allow';
            console.log('[qg-sensor] ' + info.channel + ' ' + info.method + ' -> ' + info.url
                        + ' body=' + (info.body == null ? '' : info.body) + ' decision=' + d);
            return d;
          };
          if (!window.__qg_observe) window.__qg_observe = function (vals) {
            console.log('[qg-sensor] observed ' + (vals ? vals.length : 0) + ' sensitive value(s)');
          };
        })();
    """.trimIndent()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Record the WebView provider (package + version) - the feature set depends on it.
        val pkg = WebViewCompat.getCurrentWebViewPackage(this)
        Log.i("qg-setup", "WebView package=" + pkg?.packageName + " version=" + pkg?.versionName)

        val web = WebView(this)
        setContentView(web)
        web.settings.javaScriptEnabled = true

        // Pipe the page's console.log (incl. the sensor) into Android Logcat.
        web.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                Log.i("qg-console", m.message() + "  (" + m.sourceId() + ":" + m.lineNumber() + ")")
                return true
            }
        }

        // NATIVE LAYER: fires for requests the WebView makes. Sees destination only, never the body.
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView?,
                request: WebResourceRequest?,
            ): WebResourceResponse? {
                if (request != null) {
                    Log.i("qg-native", request.method + " -> " + request.url +
                        "  mainFrame=" + request.isForMainFrame)   // no body is available here
                    if (blockingEnabled && originOf(request.url.toString()) != labOrigin) {
                        Log.w("qg-native", "BLOCK (cross-origin dest) via shouldInterceptRequest -> " + request.url)
                        return blocked()   // WebView uses this 403; the real request is never sent
                    }
                }
                return null
            }

            // Second native hook, specifically for navigations (GET main-frame loads that
            // shouldInterceptRequest may not catch on every version). Return true = cancel.
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: return false
                if (blockingEnabled && request.isForMainFrame && originOf(url) != labOrigin) {
                    Log.w("qg-native", "BLOCK (cross-origin nav) via shouldOverrideUrlLoading -> " + url)
                    return true
                }
                return false
            }

            // If the WebView render process dies (emulator instability, or a real risk in
            // production), the DEFAULT is to kill our whole app. Handle it so the app survives.
            override fun onRenderProcessGone(view: WebView?, detail: RenderProcessGoneDetail?): Boolean {
                Log.e("qg-native", "WebView render process gone (didCrash=" +
                    (detail?.didCrash()) + "); keeping the app alive")
                (view?.parent as? android.view.ViewGroup)?.removeView(view)
                view?.destroy()
                return true
            }
        }

        // SCRIPT LAYER: inject the shim + the CANONICAL sensor (same sensor.js as the Python lab),
        // only if the installed WebView supports document-start scripts.
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            val core = assets.open("sensor.js").bufferedReader().use { it.readText() }
            WebViewCompat.addDocumentStartJavaScript(web, observeShim + "\n" + core, setOf(labOrigin))
            Log.i("qg-setup", "DOCUMENT_START_SCRIPT supported: canonical sensor injected")
        } else {
            Log.w("qg-setup", "DOCUMENT_START_SCRIPT NOT supported - update Android System WebView")
        }

        web.addJavascriptInterface(QgBridge(), "QG")   // lab-only native bridge for __qg_decide

        web.loadUrl(labUrl)
    }
}
