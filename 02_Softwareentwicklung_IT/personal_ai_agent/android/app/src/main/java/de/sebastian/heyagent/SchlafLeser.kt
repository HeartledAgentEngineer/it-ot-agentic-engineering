package de.sebastian.heyagent

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.HealthConnectFeatures
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Duration
import java.time.Instant
import java.time.ZoneId

/**
 * Liest die Schlafsitzungen der letzten [TAGE] Tage aus Health Connect (nur READ_SLEEP).
 * Duenne Schicht ueber dem SDK; die Uebersetzung fuer das Backend steckt in [SchlafUebertragung]
 * (JUnit-getestet).
 */
class SchlafLeser(private val kontext: Context) {

    private val client by lazy { HealthConnectClient.getOrCreate(kontext) }

    suspend fun hatErlaubnis(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(ERLAUBNIS)

    /** S13: Kann Health Connect auf diesem Handy im Hintergrund gelesen werden? Wirft nie. */
    fun hintergrundMoeglich(): Boolean = try {
        client.features.getFeatureStatus(HealthConnectFeatures.FEATURE_READ_HEALTH_DATA_IN_BACKGROUND) ==
            HealthConnectFeatures.FEATURE_STATUS_AVAILABLE
    } catch (e: Exception) {
        false
    }

    /** Was der Knopf erfragt: Schlaf und Puls lesen und, wenn das Handy es kann, auch im Hintergrund. */
    fun anzufragen(): Set<String> = if (hintergrundMoeglich()) ERLAUBNIS + PULS + HINTERGRUND else ERLAUBNIS + PULS

    /** Ist alles erteilt, was der Knopf erfragt? Sonst fragt der Knopf erneut. */
    suspend fun hatAlles(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(anzufragen())

    suspend fun darfImHintergrund(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(ERLAUBNIS + HINTERGRUND)

    suspend fun darfPulsImHintergrund(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(PULS + HINTERGRUND)

    /** S13b: Pulswerte der letzten Stunde (nur Zeit und Schlaege, fuer den Live-Schlaf am Abend). */
    suspend fun pulsProben(): List<Pulsprobe> {
        val ab = Instant.now().minus(Duration.ofHours(1))
        return client.readRecords(ReadRecordsRequest(HeartRateRecord::class, TimeRangeFilter.after(ab)))
            .records.flatMap { r -> r.samples.map { Pulsprobe(it.time, it.beatsPerMinute) } }
    }

    /** S13: nur die Enden der Sitzungen der letzten zwei Tage (fuer die Aufwachzeit), keine Phasen. */
    suspend fun enden(): List<Instant> {
        val ab = Instant.now().minus(Duration.ofDays(2))
        return client.readRecords(ReadRecordsRequest(SleepSessionRecord::class, TimeRangeFilter.after(ab)))
            .records.map { it.endTime }
    }

    suspend fun naechte(): List<SchlafNachtRoh> {
        val ab = Instant.now().minus(Duration.ofDays(TAGE))
        val liste = mutableListOf<SchlafNachtRoh>()
        var seite: String? = null
        var runden = 0
        do {
            val antwort = client.readRecords(
                ReadRecordsRequest(SleepSessionRecord::class, TimeRangeFilter.after(ab), pageToken = seite),
            )
            antwort.records.forEach { r ->
                liste += SchlafNachtRoh(
                    kennung = r.metadata.id,
                    beginn = r.startTime,
                    ende = r.endTime,
                    offset = r.startZoneOffset ?: ZoneId.systemDefault().rules.getOffset(r.startTime),
                    app = r.metadata.dataOrigin.packageName,
                    phasen = r.stages.map { SchlafPhaseRoh(it.startTime, it.endTime, it.stage) },
                )
            }
            seite = antwort.pageToken
            runden++
        } while (!seite.isNullOrEmpty() && runden < MAX_SEITEN)
        return liste
    }

    companion object {
        const val TAGE = 30L
        private const val MAX_SEITEN = 20
        val ERLAUBNIS = setOf(HealthPermission.getReadPermission(SleepSessionRecord::class))
        val HINTERGRUND = setOf(HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND)
        val PULS = setOf(HealthPermission.getReadPermission(HeartRateRecord::class))

        fun verfuegbar(kontext: Context): Boolean =
            HealthConnectClient.getSdkStatus(kontext) == HealthConnectClient.SDK_AVAILABLE
    }
}
