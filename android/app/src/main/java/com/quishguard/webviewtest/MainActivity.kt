package com.quishguard.webviewtest

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    // One lab page, reached via 10.0.2.2 — the emulator's alias for the PC's 127.0.0.1.
    private val labUrl = "http://10.0.2.2:8000/"

    @SuppressLint("SetJavaScriptEnabled")   // lab pages (and our future sensor) need JS
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val web = WebView(this)
        setContentView(web)                     // the WebView fills the whole screen
        web.settings.javaScriptEnabled = true
        web.loadUrl(labUrl)
    }
}