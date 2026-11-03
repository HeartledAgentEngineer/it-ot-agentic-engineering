package de.sebastian.heyagent

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.time.Instant
import java.time.ZoneId
import java.util.concurrent.TimeUnit

/**
 * Alltags-Pop-up (S7): EINE Benachrichtigung mit fester ID, die sich aktualisiert.
 *
 * Die Seite (alltag.js) gibt nach jedem Speichern den Stand aus /api/alltag/offen ueber
 * HeyAgentAlltag an die App; er liegt hier in den SharedPreferences. Der stuendliche Worker
 * rechnet daraus die offenen Stunden ([AlltagErinnerungRegel]) - ohne Backend. Gespeichert wird
 * nur der Zeitpunkt des letzten Eintrags und ob geschlafen wird, nie ein Inhalt.
 *
 * S13: Nachts still. Der Worker liest (wenn erlaubt) im Hintergrund die Aufwachzeit aus Health
 * Connect; gemerkt wird nur dieser Zeitpunkt. Eine Stunde nach dem Aufwachen kommt der Morgen-Text.
 * S13b: Abends erkennt er live am Bildschirm (und Puls der Uhr), ob Sebastian schon schlaeft.
 */
object AlltagErinnerung {

    const val EXTRA_AUFNAHME = "alltag_aufnahme"
    private const val KANAL = "alltag_erinnerung"
    private const val BENACHRICHTIGUNG_ID = 4711
    private const val ARBEIT = "alltag-erinnerung"
    private const val SPEICHER = "alltag_stand"
    private const val TAG = "HeyAgent"

    /**
     * Stand von der Seite merken. Danach ruft die App [aktualisieren] im Hintergrund auf (Pop-up nach
     * dem Eintragen weg) - nicht hier, weil die Bildschirm-Abfrage nicht in den UI-Thread gehoert.
     */
    fun standSetzen(ctx: Context, json: String): Boolean {
        val stand = AlltagErinnerungRegel.standLesen(json) ?: return false
        ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE).edit()
            .putBoolean("bekannt", true)
            .putLong("letzter_ms", stand.letzterEintrag?.toEpochMilli() ?: -1L)
            .putBoolean("schlaeft", stand.schlaeft)
            .apply()
        return true
    }

    private fun standHolen(ctx: Context): AlltagStand? {
        val p = ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE)
        // Ohne je einen Stand (Alltagsprotokoll nie geoeffnet) gibt es kein Pop-up.
        if (!p.getBoolean("bekannt", false)) return null
        val ms = p.getLong("letzter_ms", -1L)
        return AlltagStand(if (ms < 0) null else Instant.ofEpochMilli(ms), p.getBoolean("schlaeft", false))
    }

    private fun aufwachenHolen(ctx: Context): Instant? {
        val ms = ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE).getLong("aufwachen_ms", -1L)
        return if (ms < 0) null else Instant.ofEpochMilli(ms)
    }

    /** Aufwachzeit der letzten Nacht aus den Sitzungs-Enden merken (nur dieser Zeitpunkt). */
    fun aufwachenMerken(ctx: Context, enden: List<Instant>) {
        val wach = AlltagErinnerungRegel.aufwachenAus(enden, Instant.now(), ZoneId.systemDefault()) ?: return
        ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE).edit()
            .putLong("aufwachen_ms", wach.toEpochMilli())
            .apply()
    }

    /** Im Worker: Aufwachzeit aus Health Connect, nur mit Erlaubnis fuers Hintergrund-Lesen. Wirft nie. */
    suspend fun aufwachenAusHealthConnect(ctx: Context) {
        if (!SchlafLeser.verfuegbar(ctx)) return
        try {
            val leser = SchlafLeser(ctx)
            if (!leser.darfImHintergrund()) return
            val enden = leser.enden()
            // Nur die Anzahl ins Log, keine Zeiten (Gesundheitsdaten).
            Log.i(TAG, "Alltag: ${enden.size} Schlafsitzungen im Hintergrund gelesen")
            aufwachenMerken(ctx, enden)
        } catch (e: Exception) {
            Log.w(TAG, "Alltag: Schlaf im Hintergrund nicht lesbar (${e.javaClass.simpleName})")
        }
    }

    /** S13b: Durchschnittspuls der letzten halben Stunde aus Health Connect, nur mit Erlaubnis. Wirft nie. */
    suspend fun pulsAusHealthConnect(ctx: Context): Double? {
        if (!SchlafLeser.verfuegbar(ctx)) return null
        return try {
            val leser = SchlafLeser(ctx)
            if (!leser.darfPulsImHintergrund()) return null
            val proben = leser.pulsProben()
            // Nur die Anzahl ins Log, keine Werte (Gesundheitsdaten).
            Log.i(TAG, "Alltag: ${proben.size} Pulswerte im Hintergrund gelesen")
            AlltagErinnerungRegel.pulsSchnitt(proben, Instant.now())
        } catch (e: Exception) {
            Log.w(TAG, "Alltag: Puls im Hintergrund nicht lesbar (${e.javaClass.simpleName})")
            null
        }
    }

    fun darfBenachrichtigen(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * Pop-up zeigen, aktualisieren oder entfernen - je nach offenen Stunden. S13b: Schlaeft Sebastian
     * laut Bildschirm (und [puls], vom Worker), bleibt es still; nur dieser Moment zaehlt, nichts wird gemerkt.
     */
    fun aktualisieren(ctx: Context, puls: Double? = null) {
        val manager = NotificationManagerCompat.from(ctx)
        val stand = standHolen(ctx)
        val jetzt = Instant.now()
        val zone = ZoneId.systemDefault()
        val erinnerung = if (stand == null) Erinnerung(0, false) else {
            val ausSeit = AlltagErinnerungRegel.ausSeit(BildschirmLeser.wechsel(ctx, jetzt), jetzt)
            val schlaf = AlltagErinnerungRegel.eingeschlafen(ausSeit, puls, jetzt, zone)
            AlltagErinnerungRegel.erinnerung(stand, aufwachenHolen(ctx), jetzt, zone, eingeschlafen = schlaf)
        }
        val stunden = erinnerung.stunden
        if (stunden < 1) {
            manager.cancel(BENACHRICHTIGUNG_ID)
            return
        }
        if (!darfBenachrichtigen(ctx)) return
        kanalAnlegen(ctx)
        val oeffnen = PendingIntent.getActivity(
            ctx, 0,
            Intent(ctx, MainActivity::class.java)
                .putExtra(EXTRA_AUFNAHME, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        // Auf dem Sperrbildschirm nur "Hey Agent" - das Protokoll ist Therapie-Sache.
        val oeffentlich = NotificationCompat.Builder(ctx, KANAL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(ctx.getString(R.string.app_name))
            .build()
        val text = AlltagErinnerungRegel.text(stunden, erinnerung.nachDemAufwachen)
        val meldung = NotificationCompat.Builder(ctx, KANAL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(ctx.getString(R.string.alltag_titel))
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(oeffnen)
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
            .setPublicVersion(oeffentlich)
            .build()
        try {
            manager.notify(BENACHRICHTIGUNG_ID, meldung)
            Log.i(TAG, "Alltag: Pop-up mit $stunden offenen Stunden")
        } catch (e: SecurityException) {
            Log.w(TAG, "Alltag: Benachrichtigung nicht erlaubt")
        }
    }

    private fun kanalAnlegen(ctx: Context) {
        val kanal = NotificationChannel(
            KANAL, ctx.getString(R.string.alltag_kanal), NotificationManager.IMPORTANCE_LOW,
        ).apply { description = ctx.getString(R.string.alltag_kanal_text) }
        ctx.getSystemService(NotificationManager::class.java)?.createNotificationChannel(kanal)
    }

    /** Stuendliche Pruefung einplanen; KEEP: ein zweiter App-Start legt keinen zweiten Lauf an. */
    fun planen(ctx: Context) {
        val arbeit = PeriodicWorkRequestBuilder<AlltagErinnerungWorker>(1, TimeUnit.HOURS).build()
        WorkManager.getInstance(ctx)
            .enqueueUniquePeriodicWork(ARBEIT, ExistingPeriodicWorkPolicy.KEEP, arbeit)
    }
}

/** Stuendlicher Lauf ohne Netz und ohne Backend: Aufwachzeit holen (S13), gespeicherten Stand auswerten. */
class AlltagErinnerungWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        AlltagErinnerung.aufwachenAusHealthConnect(applicationContext)
        val puls = AlltagErinnerung.pulsAusHealthConnect(applicationContext)
        AlltagErinnerung.aktualisieren(applicationContext, puls)
        return Result.success()
    }
}
