package de.sebastian.heyagent

import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * Stoesst den Backend-Start in Termux an.
 *
 * Weg 1: ~/agent-ensure.sh per RUN_COMMAND-Intent (unsichtbar). Das geht nur mit der
 * F-Droid-/GitHub-Fassung von Termux (Permission com.termux.permission.RUN_COMMAND und
 * allow-external-apps=true, siehe android/README.md).
 * Weg 2 (Rueckfall): Termux sichtbar oeffnen. Das Play-Store-Termux hat keinen
 * RunCommandService; dort startet der Eintrag in ~/.bashrc beim Oeffnen der Sitzung
 * agent-ensure.sh --app-zurueck, und Termux holt die App danach ueber heyagent://start zurueck.
 */
class TermuxLauncher(private val context: Context) : BackendStarter {

    override fun starte(): Boolean = perRunCommand() || termuxOeffnen()

    /**
     * Still anstossen (10.10.2026): nur der unsichtbare RUN_COMMAND, KEIN sichtbares
     * Termux als Rueckfall. Laeuft das Backend schon, stoesst der App-Knopf so die
     * Start-Vorbereitung an (git pull + Uebernahmen im Hintergrund), ohne etwas zu
     * oeffnen. Fehlt der Termux-Dienst (Play-Store-Termux), passiert nichts.
     */
    override fun stillerAnstoss(): Boolean = perRunCommand()

    /**
     * true nur, wenn Android den Termux-Dienst wirklich gefunden hat. Fehlt er (Play-Store-
     * Termux), liefert startForegroundService null statt einer Ausnahme.
     */
    private fun perRunCommand(): Boolean {
        val intent = Intent("com.termux.RUN_COMMAND").apply {
            setClassName(AppKonfig.TERMUX_PAKET, "com.termux.app.RunCommandService")
            putExtra("com.termux.RUN_COMMAND_PATH", AppKonfig.TERMUX_SKRIPT)
            putExtra("com.termux.RUN_COMMAND_WORKDIR", AppKonfig.TERMUX_HOME)
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
        }
        return try {
            val komponente = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
            if (komponente == null) Log.i(TAG, "RUN_COMMAND nicht verfuegbar - oeffne Termux sichtbar")
            komponente != null
        } catch (e: Exception) {
            // SecurityException (Permission fehlt), IllegalStateException (Hintergrundstart) u. a.:
            // nur den Klassennamen loggen, dann greift der sichtbare Rueckfall.
            Log.w(TAG, "RUN_COMMAND fehlgeschlagen: ${e.javaClass.simpleName}")
            false
        }
    }

    /** Oeffnet die Termux-App sichtbar. false, wenn Termux nicht installiert ist. */
    fun termuxOeffnen(): Boolean {
        val intent = context.packageManager.getLaunchIntentForPackage(AppKonfig.TERMUX_PAKET)
            ?: return false
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.w(TAG, "Termux oeffnen fehlgeschlagen: ${e.javaClass.simpleName}")
            false
        }
    }

    private companion object {
        const val TAG = "HeyAgent"
    }
}
