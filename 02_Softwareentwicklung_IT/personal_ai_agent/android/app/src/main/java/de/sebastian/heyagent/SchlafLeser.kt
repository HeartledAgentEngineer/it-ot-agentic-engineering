package de.sebastian.heyagent

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
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

        fun verfuegbar(kontext: Context): Boolean =
            HealthConnectClient.getSdkStatus(kontext) == HealthConnectClient.SDK_AVAILABLE
    }
}
