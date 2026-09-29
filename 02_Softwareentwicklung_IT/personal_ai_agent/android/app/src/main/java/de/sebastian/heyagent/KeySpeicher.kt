package de.sebastian.heyagent

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Speichert den API-Schluessel des Backends verschluesselt (Android-Keystore,
 * AES-256). Der Schluessel steht nie im Code oder im Repo.
 */
class KeySpeicher(context: Context) {
    private val app = context.applicationContext

    private val prefs by lazy {
        val master = MasterKey.Builder(app)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            app,
            DATEI,
            master,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    /** Gespeicherter Schluessel oder null (auch bei Keystore-Problemen: dann wie "nicht gesetzt"). */
    fun holen(): String? = try {
        prefs.getString(SCHLUESSEL, null)?.takeIf { it.isNotBlank() }
    } catch (e: Exception) {
        null
    }

    fun speichern(wert: String): Boolean = try {
        prefs.edit().putString(SCHLUESSEL, wert.trim()).apply()
        true
    } catch (e: Exception) {
        false
    }

    fun loeschen() {
        try {
            prefs.edit().remove(SCHLUESSEL).apply()
        } catch (_: Exception) {
        }
    }

    /** "Später" gewaehlt: kein Schluessel noetig, solange die Seite ihn selbst holt. */
    fun frageUebersprungen(): Boolean =
        app.getSharedPreferences(EINSTELLUNGEN, Context.MODE_PRIVATE)
            .getBoolean(UEBERSPRUNGEN, false)

    fun merkeUebersprungen() {
        app.getSharedPreferences(EINSTELLUNGEN, Context.MODE_PRIVATE)
            .edit().putBoolean(UEBERSPRUNGEN, true).apply()
    }

    private companion object {
        const val DATEI = "heyagent_geheim"
        const val SCHLUESSEL = "api_key"
        const val EINSTELLUNGEN = "heyagent_einstellungen"
        const val UEBERSPRUNGEN = "key_frage_uebersprungen"
    }
}
