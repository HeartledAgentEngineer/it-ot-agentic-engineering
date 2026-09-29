package de.sebastian.heyagent

import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * Startet ~/agent-ensure.sh in Termux per RUN_COMMAND-Intent (im Hintergrund, ohne
 * Terminalfenster) und kann Termux sichtbar oeffnen (Rueckfall-Knopf).
 *
 * Voraussetzungen (siehe android/README.md): Permission com.termux.permission.RUN_COMMAND
 * (Manifest + einmalige Freigabe durch den Nutzer) und allow-external-apps=true in
 * ~/.termux/termux.properties.
 */
class TermuxLauncher(private val context: Context) : BackendStarter {

    override fun starte(): Boolean {
        val intent = Intent("com.termux.RUN_COMMAND").apply {
            setClassName(AppKonfig.TERMUX_PAKET, "com.termux.app.RunCommandService")
            putExtra("com.termux.RUN_COMMAND_PATH", AppKonfig.TERMUX_SKRIPT)
            putExtra("com.termux.RUN_COMMAND_WORKDIR", AppKonfig.TERMUX_HOME)
            putExtra("com.termux.RUN_COMMAND_BACKGROUND", true)
        }
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
            true
        } catch (e: Exception) {
            // SecurityException (Permission fehlt), IllegalStateException (Hintergrundstart) u. a.:
            // nur den Klassennamen loggen, die App zeigt die Meldung.
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
