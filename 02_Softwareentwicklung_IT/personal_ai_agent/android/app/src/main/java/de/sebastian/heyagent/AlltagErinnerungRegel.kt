package de.sebastian.heyagent

import java.time.Duration
import java.time.Instant
import java.time.OffsetDateTime

/** Stand aus GET /api/alltag/offen, den die Seite ueber HeyAgentAlltag an die App gibt. */
data class AlltagStand(val letzterEintrag: Instant?, val schlaeft: Boolean)

/**
 * Reine Regel des Alltags-Pop-ups (S7, Plan .hermes/plans/alltagsprotokoll.md).
 *
 * Der Worker rechnet die offenen Stunden selbst aus dem gespeicherten Stand - so erscheint das
 * Pop-up auch, wenn Termux/Backend gerade nicht laeuft. Gleiche Rechnung wie
 * alltag_rechnen.offene_stunden/letzter_stand im Backend. Kein Android-SDK, JUnit-getestet.
 */
object AlltagErinnerungRegel {

    /** Wie MAX_NACHT im Backend: ein Schlaf-Knopf gilt hoechstens so lange. */
    private val MAX_NACHT: Duration = Duration.ofHours(24)

    /** Volle Stunden seit dem letzten Eintrag; im Schlaf 0; ohne jeden Eintrag 1. */
    fun offeneStunden(stand: AlltagStand, jetzt: Instant): Int {
        val letzter = stand.letzterEintrag ?: return if (stand.schlaeft) 0 else 1
        val rest = Duration.between(letzter, jetzt)
        if (stand.schlaeft && rest <= MAX_NACHT) return 0
        if (rest.isNegative || rest.isZero) return 0
        return rest.toHours().toInt()
    }

    fun text(stunden: Int): String =
        if (stunden == 1) "Bitte 1 Stunde nachtragen" else "Bitte $stunden Stunden nachtragen"

    fun startUrl(aufnahme: Boolean): String =
        if (aufnahme) AppKonfig.START_URL + "?alltag=aufnahme" else AppKonfig.START_URL

    /**
     * Liest {ok, schlaeft, letzter_eintrag} aus der Antwort von /offen. Alles, was nicht genau
     * passt (ok fehlt, schlaeft fehlt, Zeit ohne Offset), ergibt null - dann bleibt der alte Stand.
     * Bewusst ohne org.json: das ist im JVM-Test nur eine Attrappe.
     */
    fun standLesen(json: String): AlltagStand? {
        if (!Regex("\"ok\"\\s*:\\s*true").containsMatchIn(json)) return null
        val schlaeft = Regex("\"schlaeft\"\\s*:\\s*(true|false)").find(json)
            ?.groupValues?.get(1)?.toBoolean() ?: return null
        if (Regex("\"letzter_eintrag\"\\s*:\\s*null").containsMatchIn(json)) {
            return AlltagStand(null, schlaeft)
        }
        val roh = Regex("\"letzter_eintrag\"\\s*:\\s*\"([^\"]{1,40})\"").find(json)
            ?.groupValues?.get(1) ?: return null
        val zeit = try {
            OffsetDateTime.parse(roh).toInstant()
        } catch (e: Exception) {
            return null
        }
        return AlltagStand(zeit, schlaeft)
    }
}
