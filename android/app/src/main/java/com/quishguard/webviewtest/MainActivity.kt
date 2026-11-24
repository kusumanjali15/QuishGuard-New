package com.quishguard.webviewtest

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebView
import androidx.appcompat.app.AppCompatActivity
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature

class MainActivity : AppCompatActivity() {

    // One lab page, reached via 10.0.2.2 — the emulator's alias for the PC's 127.0.0.1.
    private val labUrl = "http://10.0.2.2:8000/"
    private val labOrigin = "http://10.0.2.2:8000"

    // The SCRIPT LAYER: our sensor, injected to run BEFORE the page's own scripts.
    // It lives inside the page, so it can see TYPED VALUES (form/fetch bodies) — the
    // thing the native layer (2c) cannot. Minimal for now: a boot line + wrap fetch +
    // capture form submits, all reported via console.log.
    private val sensorJs = """
        (function () {
          const tag = '[qg-sensor]';
          console.log(tag + ' installed at document-start on ' + location.origin);

          const origFetch = window.fetch;
          window.fetch = function (input, init) {
            const url = (typeof input === 'string') ? input : input.url;
            const body = (init && init.body) ? init.body : '';
            console.log(tag + ' fetch -> ' + url + ' body=' + body);
            return origFetch.apply(this, arguments);
          };

          document.addEventListener('submit', function (e) {
            const data = new FormData(e.target);
            const pairs = [];
            for (const [k, v] of data.entries()) pairs.push(k + '=' + v);
            console.log(tag + ' form submit -> ' + (e.target.action || location.href)
                        + ' body=' + pairs.join('&'));
          }, true);
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
