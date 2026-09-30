package de.sebastian.heyagent

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.util.Log
import android.view.View
import android.webkit.PermissionRequest
import android.webkit.ValueCallback
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
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

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

    /** Was gerade angezeigt wird (nur auf dem UI-Thread gesetzt). Start = Ladebildschirm. */
    private var ansicht = Ansicht.LADEN

    /** Laeuft gerade eine Nachkontrolle (onResume)? Verhindert doppelte Pruefungen. */
    @Volatile
    private var nachkontrolleLaeuft = false

    /** Mikrofon-Anfrage der Seite, die auf den Android-Dialog wartet. */
    private var offeneMikrofonAnfrage: PermissionRequest? = null

    /**
     * Android-Dialog "Hey Agent darf Audio aufnehmen?". Nach zweimaligem Ablehnen zeigt Android
     * ihn nicht mehr (shouldShowRequestPermissionRationale ist dann false) - dann bietet die App
     * die App-Einstellungen an.
     */
    private val mikrofonErlaubnis =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { erlaubt ->
            val anfrage = offeneMikrofonAnfrage
            offeneMikrofonAnfrage = null
            if (erlaubt) {
                anfrage?.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
            } else {
                anfrage?.deny()
                if (!shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO)) {
                    einstellungenAnbieten()
                }
            }
        }

    /** Datei-Anfrage der Seite (Bueroklammer), die auf die Android-Dateiauswahl wartet. */
    private var offeneDateiAuswahl: ValueCallback<Array<Uri>>? = null

    /**
     * Android-Dateiauswahl (Fotos, Downloads, Drive ...). Sie braucht keine Speicher-Erlaubnis:
     * Android gibt der App nur die gewaehlten Dateien frei, und nur fuer diesen einen Zugriff.
     */
    private val dateiAuswahl =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { ergebnis ->
            val rueckruf = offeneDateiAuswahl
            offeneDateiAuswahl = null
            val daten = ergebnis.data
            val clip = daten?.clipData
            val mehrere = if (clip == null) emptyList() else (0 until clip.itemCount).mapNotNull { clip.getItemAt(it).uri }
            val auswahl = DateiAuswahlRegel.gewaehlt(ergebnis.resultCode == Activity.RESULT_OK, daten?.data, mehrere)
            rueckruf?.onReceiveValue(auswahl?.toTypedArray())
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        randAbstaendeSetzen()

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

    /**
     * Android 15 (targetSdk 35) zeichnet jede App bis unter Status- und Navigationsleiste.
     * Ohne Abstand lag die Kopfzeile der Seite unter der Benachrichtigungsleiste. Der Abstand
     * nimmt auch die Tastatur (ime) mit, damit das Eingabefeld sichtbar bleibt.
     */
    private fun randAbstaendeSetzen() {
        val wurzel = findViewById<View>(android.R.id.content)
        ViewCompat.setOnApplyWindowInsetsListener(wurzel) { v, insets ->
            val rand = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() or
                    WindowInsetsCompat.Type.displayCutout() or
                    WindowInsetsCompat.Type.ime(),
            )
            v.setPadding(rand.left, rand.top, rand.right, rand.bottom)
            WindowInsetsCompat.CONSUMED
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
            // Mikrofon fuer die Seite des eigenen Backends (Sprachaufnahme im Chat). Kamera und
            // fremde Seiten nie. Regel: MikrofonRegel (JUnit-getestet).
            override fun onPermissionRequest(request: PermissionRequest) {
                val erlaubt = ContextCompat.checkSelfPermission(
                    this@MainActivity, Manifest.permission.RECORD_AUDIO,
                ) == PackageManager.PERMISSION_GRANTED
                when (MikrofonRegel.entscheide(istBackend(request.origin), request.resources.toList(), erlaubt)) {
                    Freigabe.ERLAUBEN -> request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))
                    Freigabe.ANDROID_FRAGEN -> {
                        offeneMikrofonAnfrage?.deny()
                        offeneMikrofonAnfrage = request
                        mikrofonErlaubnis.launch(Manifest.permission.RECORD_AUDIO)
                    }
                    Freigabe.ABLEHNEN -> request.deny()
                }
            }

            // Bueroklammer der Seite: Ohne diese Methode tut <input type="file"> in einer WebView
            // still gar nichts (kein Dialog, keine Fehlermeldung). Nur fuer das eigene Backend.
            override fun onShowFileChooser(
                view: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: WebChromeClient.FileChooserParams,
            ): Boolean {
                if (!istBackend(Uri.parse(view.url ?: ""))) return false
                // Eine noch offene Anfrage beantworten, sonst reagiert die Seite nie wieder.
                offeneDateiAuswahl?.onReceiveValue(null)
                val typen = DateiAuswahlRegel.mimeTypen(fileChooserParams.acceptTypes)
                val absicht = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = DateiAuswahlRegel.intentTyp(typen)
                    if (typen.size > 1) putExtra(Intent.EXTRA_MIME_TYPES, typen.toTypedArray())
                    putExtra(
                        Intent.EXTRA_ALLOW_MULTIPLE,
                        fileChooserParams.mode == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE,
                    )
                }
                return try {
                    offeneDateiAuswahl = filePathCallback
                    dateiAuswahl.launch(absicht)
                    true
                } catch (e: ActivityNotFoundException) {
                    // false = WebView behandelt es selbst; der Rueckruf darf dann nicht kommen.
                    offeneDateiAuswahl = null
                    Log.w(TAG, "Keine Dateiauswahl auf dem Geraet: ${e.javaClass.simpleName}")
                    false
                }
            }
        }
    }

    private fun istBackend(uri: Uri): Boolean =
        uri.scheme == "http" &&
            (uri.host == AppKonfig.BACKEND_HOST || uri.host == "localhost") &&
            uri.port == AppKonfig.BACKEND_PORT

    /** Mikrofon dauerhaft abgelehnt: direkt in die App-Einstellungen (Berechtigungen) fuehren. */
    private fun einstellungenAnbieten() {
        AlertDialog.Builder(this)
            .setTitle(R.string.mikro_titel)
            .setMessage(R.string.mikro_hinweis)
            .setPositiveButton(R.string.mikro_einstellungen) { _, _ ->
                try {
                    startActivity(
                        Intent(
                            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                            Uri.fromParts("package", packageName, null),
                        ),
                    )
                } catch (e: Exception) {
                    Log.w(TAG, "App-Einstellungen nicht geoeffnet: ${e.javaClass.simpleName}")
                }
            }
            .setNegativeButton(R.string.mikro_abbrechen, null)
            .show()
    }

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

    /**
     * Zurueck in der App (auch ueber heyagent://start oder aus der Dateiauswahl): pruefen, ob
     * das Backend noch lebt. Android kann die Termux-Sitzung samt Backend jederzeit beenden;
     * Regel und Begruendung stehen in [Nachkontrolle].
     */
    override fun onResume() {
        super.onResume()
        if (nachkontrolleLaeuft || !Nachkontrolle.sollPruefen(ansicht, laeuft)) return
        nachkontrolleLaeuft = true
        val ansichtVorher = ansicht
        Thread {
            val erreichbar = Nachkontrolle.erreichbar(HttpHealthPruefer())
            nachkontrolleLaeuft = false
            if (beendet) return@Thread
            runOnUiThread {
                // Hat sich inzwischen etwas geaendert (Start laeuft, andere Ansicht), nichts tun.
                if (laeuft || ansicht != ansichtVorher) return@runOnUiThread
                when (Nachkontrolle.entscheide(ansicht, erreichbar)) {
                    Wiederkehr.NEU_STARTEN -> {
                        Log.i(TAG, "Nachkontrolle: Backend weg - starte neu")
                        backendStarten()
                    }
                    Wiederkehr.SEITE_LADEN -> {
                        Log.i(TAG, "Nachkontrolle: Backend wieder da - lade Seite")
                        seiteLaden()
                    }
                    Wiederkehr.NICHTS -> Unit
                }
            }
        }.start()
    }

    private fun seiteLaden() {
        ansicht = Ansicht.SEITE
        // Der Kopf gilt nur fuer die erste Anfrage (Dokument). Die Seite holt sich den Schluessel
        // fuer ihre fetch-Aufrufe selbst (window.__API_KEY__ per /api/konfig) - siehe README.
        val kopf = keySpeicher.holen()?.let { mapOf(AppKonfig.KEY_HEADER to it) } ?: emptyMap()
        webView.visibility = View.VISIBLE
        ladeAnsicht.visibility = View.GONE
        webView.loadUrl(AppKonfig.START_URL, kopf)
    }

    private fun zeigeLaden(text: String) {
        ansicht = Ansicht.LADEN
        webView.visibility = View.INVISIBLE
        ladeAnsicht.visibility = View.VISIBLE
        ladeFortschritt.visibility = View.VISIBLE
        knopfTermux.visibility = View.GONE
        knopfErneut.visibility = View.GONE
        ladeStatus.text = text
    }

    private fun zeigeFehler(text: String) {
        ansicht = Ansicht.FEHLER
        webView.visibility = View.INVISIBLE
        ladeAnsicht.visibility = View.VISIBLE
        ladeFortschritt.visibility = View.GONE
        ladeStatus.text = text
        knopfTermux.visibility = View.VISIBLE
        knopfErneut.visibility = View.VISIBLE
    }

    override fun onDestroy() {
        beendet = true
        offeneMikrofonAnfrage?.deny()
        offeneMikrofonAnfrage = null
        offeneDateiAuswahl?.onReceiveValue(null)
        offeneDateiAuswahl = null
        webView.destroy()
        super.onDestroy()
    }

    private companion object {
        const val TAG = "HeyAgent"
    }
}
