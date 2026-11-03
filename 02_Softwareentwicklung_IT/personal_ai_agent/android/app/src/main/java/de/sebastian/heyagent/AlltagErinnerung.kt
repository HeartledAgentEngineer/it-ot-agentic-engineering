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
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.time.Instant
import java.util.concurrent.TimeUnit

/**
 * Alltags-Pop-up (S7): EINE Benachrichtigung mit fester ID, die sich aktualisiert.
 *
 * Die Seite (alltag.js) gibt nach jedem Speichern den Stand aus /api/alltag/offen ueber
 * HeyAgentAlltag an die App; er liegt hier in den SharedPreferences. Der stuendliche Worker
 * rechnet daraus die offenen Stunden ([AlltagErinnerungRegel]) - ohne Backend. Gespeichert wird
 * nur der Zeitpunkt des letzten Eintrags und ob geschlafen wird, nie ein Inhalt.
 */
object AlltagErinnerung {

    const val EXTRA_AUFNAHME = "alltag_aufnahme"
    private const val KANAL = "alltag_erinnerung"
    private const val BENACHRICHTIGUNG_ID = 4711
    private const val ARBEIT = "alltag-erinnerung"
    private const val SPEICHER = "alltag_stand"
    private const val TAG = "HeyAgent"

    /** Stand von der Seite merken und das Pop-up sofort anpassen (nach dem Eintragen weg). */
    fun standSetzen(ctx: Context, json: String): Boolean {
        val stand = AlltagErinnerungRegel.standLesen(json) ?: return false
        ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE).edit()
            .putBoolean("bekannt", true)
            .putLong("letzter_ms", stand.letzterEintrag?.toEpochMilli() ?: -1L)
            .putBoolean("schlaeft", stand.schlaeft)
            .apply()
        aktualisieren(ctx)
        return true
    }

    private fun standHolen(ctx: Context): AlltagStand? {
        val p = ctx.getSharedPreferences(SPEICHER, Context.MODE_PRIVATE)
        // Ohne je einen Stand (Alltagsprotokoll nie geoeffnet) gibt es kein Pop-up.
        if (!p.getBoolean("bekannt", false)) return null
        val ms = p.getLong("letzter_ms", -1L)
        return AlltagStand(if (ms < 0) null else Instant.ofEpochMilli(ms), p.getBoolean("schlaeft", false))
    }

    fun darfBenachrichtigen(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /** Pop-up zeigen, aktualisieren oder entfernen - je nach offenen Stunden. */
    fun aktualisieren(ctx: Context) {
        val manager = NotificationManagerCompat.from(ctx)
        val stand = standHolen(ctx)
        val stunden = if (stand == null) 0 else AlltagErinnerungRegel.offeneStunden(stand, Instant.now())
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
        val meldung = NotificationCompat.Builder(ctx, KANAL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(ctx.getString(R.string.alltag_titel))
            .setContentText(AlltagErinnerungRegel.text(stunden))
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

/** Stuendlicher Lauf ohne Netz und ohne Backend: nur gespeicherten Stand auswerten. */
class AlltagErinnerungWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        AlltagErinnerung.aktualisieren(applicationContext)
        return Result.success()
    }
}
