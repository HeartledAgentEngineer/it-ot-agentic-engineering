package de.sebastian.heyagent

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Process
import java.time.Duration
import java.time.Instant

/**
 * S13b: Liest nur "Bildschirm an/aus" aus den Nutzungsdaten (Erlaubnis "Nutzungsdatenzugriff").
 * Keine App-Namen, keine Inhalte - die Auswertung steckt in [AlltagErinnerungRegel.ausSeit].
 */
object BildschirmLeser {

    private val FENSTER: Duration = Duration.ofHours(12)

    fun erlaubt(ctx: Context): Boolean = try {
        val ops = ctx.getSystemService(AppOpsManager::class.java)
        ops?.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), ctx.packageName) ==
            AppOpsManager.MODE_ALLOWED
    } catch (e: Exception) {
        false
    }

    /** Bildschirm-Wechsel der letzten 12 Stunden; ohne Erlaubnis oder bei Fehler leer. Wirft nie. */
    fun wechsel(ctx: Context, jetzt: Instant): List<Bildschirm> {
        if (!erlaubt(ctx)) return emptyList()
        return try {
            val manager = ctx.getSystemService(UsageStatsManager::class.java) ?: return emptyList()
            val ereignisse = manager.queryEvents(jetzt.minus(FENSTER).toEpochMilli(), jetzt.toEpochMilli())
            val liste = mutableListOf<Bildschirm>()
            val e = UsageEvents.Event()
            while (ereignisse.hasNextEvent()) {
                ereignisse.getNextEvent(e)
                when (e.eventType) {
                    UsageEvents.Event.SCREEN_INTERACTIVE -> liste += Bildschirm(Instant.ofEpochMilli(e.timeStamp), true)
                    UsageEvents.Event.SCREEN_NON_INTERACTIVE -> liste += Bildschirm(Instant.ofEpochMilli(e.timeStamp), false)
                }
            }
            liste
        } catch (e: Exception) {
            emptyList()
        }
    }
}
