package de.sebastian.heyagent

import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.util.Log
import android.view.View
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

/**
 * Vollbild-WebView auf das lokale Backend (Termux, 127.0.0.1:8080).
 *
 * Ablauf: (ggf. einmalig API-Schluessel erfragen) -> BackendWaechter prueft /health,
 * startet bei Bedarf Termux und wartet bis zu 60 s -> WebView laedt die Seite.
 * Waehrenddessen zeigt ein Ladebildschirm den Status; bei Misserfolg eine klare
 * Meldung mit den Knoepfen "Termux oeffnen" und "Erneut versuchen".
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var ladeAnsicht: View
    private lateinit var ladeFortschritt: ProgressBar
    private lateinit var ladeStatus: TextView
    private lateinit var knopfTermux: Button
    private lateinit var knopfErneut: Button

    private lateinit var keySpeicher: KeySpeicher
    private lateinit var termux: TermuxLauncher

    @Volatile
    private var beendet = false

    @Volatile
    private var laeuft = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        ladeAnsicht = findViewById(R.id.lade_ansicht)
        ladeFortschritt = findViewById(R.id.lade_fortschritt)
        ladeStatus = findViewById(R.id.lade_status)
        knopfTermux = findViewById(R.id.knopf_termux)
        knopfErneut = findViewById(R.id.knopf_erneut)

        keySpeicher = KeySpeicher(this)
        termux = TermuxLauncher(this)

        webViewEinrichten()

        knopfTermux.setOnClickListener {
            if (!termux.termuxOeffnen()) {
                Toast.makeText(this, "Termux ist nicht installiert.", Toast.LENGTH_LONG).show()
            }
        }
        knopfErneut.setOnClickListener { backendStarten() }

        // Zurueck-Taste = WebView-Verlauf; erst wenn kein Verlauf mehr da ist, beendet sie die App.
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.visibility == View.VISIBLE && webView.canGoBack()) {
                    webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        if (keySpeicher.holen() == null && !keySpeicher.frageUebersprungen()) {
            keyAbfragen { backendStarten() }
        } else {
            backendStarten()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun webViewEinrichten() {
        // Chrome-Inspektion (chrome://inspect) nur in Debug-Builds.
        if ((applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true)
        }
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            // Vorlesen (TTS-MP3) in der Seite soll ohne Extra-Tipp starten duerfen (Spec 5.5).
            mediaPlaybackRequiresUserGesture = false
            setSupportMultipleWindows(false)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest,
            ): Boolean {
                val uri = request.url
                if (istBackend(uri)) return false
                // Fremde Adressen nie in unserer WebView (hat Zugriff auf den lokalen Server) laden.
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, uri))
                } catch (e: Exception) {
                    Log.w(TAG, "Externe Adresse nicht geoeffnet: ${e.javaClass.simpleName}")
                }
                return true
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                // Nur Fehler der Hauptseite (nicht einzelner Bilder) fuehren zur Fehleransicht.
                if (request.isForMainFrame) {
                    zeigeFehler("Die Seite konnte nicht geladen werden (${error.description}).")
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            // Mikrofon/Kamera gehoeren nicht der WebView (spaeter: nativer Dienst, Schritt A1c).
            override fun onPermissionRequest(request: PermissionRequest) {
                request.deny()
            }
        }
    }

    private fun istBackend(uri: Uri): Boolean =
        uri.scheme == "http" &&
            (uri.host == AppKonfig.BACKEND_HOST || uri.host == "localhost") &&
            uri.port == AppKonfig.BACKEND_PORT

    /** Einfache Eingabemaske fuer den API-Schluessel (Passwortfeld). */
    private fun keyAbfragen(danach: () -> Unit) {
        val feld = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            hint = getString(R.string.key_titel)
            setSingleLine(true)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.key_titel)
            .setMessage(R.string.key_hinweis)
            .setView(feld)
            .setCancelable(false)
            .setPositiveButton(R.string.key_speichern) { _, _ ->
                val wert = feld.text.toString().trim()
                if (wert.isEmpty() || !keySpeicher.speichern(wert)) {
                    keySpeicher.merkeUebersprungen()
                }
                danach()
            }
            .setNegativeButton(R.string.key_spaeter) { _, _ ->
                keySpeicher.merkeUebersprungen()
                danach()
            }
            .show()
    }

    /** Health-Check + ggf. Termux-Start im Hintergrund-Thread, Status auf dem UI-Thread. */
    private fun backendStarten() {
        if (laeuft) return
        laeuft = true
        zeigeLaden("")
        Thread {
            val waechter = BackendWaechter(HttpHealthPruefer(), termux)
            val ergebnis = waechter.sicherstellen(
                abgebrochen = { beendet },
                meldung = { phase, text ->
                    if (phase != Phase.FEHLER) runOnUiThread { ladeStatus.text = text }
                },
            )
            // Messwert fuer das Pruefkriterium A1b: Zeit bis "bereit".
            Log.i(TAG, "Backend-Start: bereit=${ergebnis.bereit} dauer=${ergebnis.dauerMs} ms grund=${ergebnis.grund}")
            laeuft = false
            if (beendet) return@Thread
            runOnUiThread {
                if (ergebnis.bereit) {
                    seiteLaden()
                } else {
                    val text = BackendStartLogik().fehlerText(
                        ergebnis.grund ?: FehlerGrund.ZEITUEBERSCHREITUNG,
                    )
                    zeigeFehler(text)
                }
            }
        }.start()
    }

    private fun seiteLaden() {
        // Der Kopf gilt nur fuer die erste Anfrage (Dokument). Die Seite holt sich den Schluessel
        // fuer ihre fetch-Aufrufe selbst (window.__API_KEY__ per /api/konfig) - siehe README.
        val kopf = keySpeicher.holen()?.let { mapOf(AppKonfig.KEY_HEADER to it) } ?: emptyMap()
        webView.visibility = View.VISIBLE
        ladeAnsicht.visibility = View.GONE
        webView.loadUrl(AppKonfig.START_URL, kopf)
    }

    private fun zeigeLaden(text: String) {
        webView.visibility = View.INVISIBLE
        ladeAnsicht.visibility = View.VISIBLE
        ladeFortschritt.visibility = View.VISIBLE
        knopfTermux.visibility = View.GONE
        knopfErneut.visibility = View.GONE
        ladeStatus.text = text
    }

    private fun zeigeFehler(text: String) {
        webView.visibility = View.INVISIBLE
        ladeAnsicht.visibility = View.VISIBLE
        ladeFortschritt.visibility = View.GONE
        ladeStatus.text = text
        knopfTermux.visibility = View.VISIBLE
        knopfErneut.visibility = View.VISIBLE
    }

    override fun onDestroy() {
        beendet = true
        webView.destroy()
        super.onDestroy()
    }

    private companion object {
        const val TAG = "HeyAgent"
    }
}
