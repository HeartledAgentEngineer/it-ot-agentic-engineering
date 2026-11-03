package de.sebastian.heyagent

import java.time.Duration
import java.time.Instant
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId

/** Stand aus GET /api/alltag/offen, den die Seite ueber HeyAgentAlltag an die App gibt. */
data class AlltagStand(val letzterEintrag: Instant?, val schlaeft: Boolean)

/** Ergebnis der Pop-up-Regel: offene Stunden und ob ab dem Aufwachen gezaehlt wird (Morgen-Text). */
data class Erinnerung(val stunden: Int, val nachDemAufwachen: Boolean)

/** S13b: Ein Bildschirm-Wechsel aus den Nutzungsdaten (an = eingeschaltet). */
data class Bildschirm(val zeit: Instant, val an: Boolean)

/** S13b: Ein Pulswert der Uhr aus Health Connect (Schlaege pro Minute). */
data class Pulsprobe(val zeit: Instant, val schlaege: Long)

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

    /**
     * S13: Abends geht es stuendlich weiter, bis Sebastian schlaeft - das weiss die Uhr aber erst am
     * Morgen. Deshalb gilt ab 3:00 sicher Nachtruhe; sie endet mit dem ersten Wachsein (Aufwachen laut
     * Uhr oder ein eigener Eintrag), spaetestens um 11:00. Was abends offen war, verfaellt.
     */
    private val RUHE_AB: LocalTime = LocalTime.of(3, 0)
    private val RUHE_SPAETESTENS: Duration = Duration.ofHours(8)

    /** Beginn der laufenden bzw. letzten Ruhezeit (3:00 heute oder gestern, Ortszeit). */
    private fun ruheBeginn(jetzt: Instant, zone: ZoneId): Instant {
        val ort = jetzt.atZone(zone)
        val tag = if (ort.toLocalTime() >= RUHE_AB) ort.toLocalDate() else ort.toLocalDate().minusDays(1)
        return tag.atTime(RUHE_AB).atZone(zone).toInstant()
    }

    /**
     * S13b: Live-Schlaf am Abend. Health Connect kennt eine Schlafsitzung erst nach dem Aufwachen,
     * deshalb zaehlt abends der Bildschirm: seit [STILL] aus, ausgeschaltet zwischen 20:00 und 3:00,
     * und - wenn die Uhr Puls liefert - ein ruhiger Puls. Kurzes Aufleuchten (Nachricht) zaehlt nicht.
     */
    private val STILL: Duration = Duration.ofMinutes(45)
    private val KURZ_AN: Duration = Duration.ofMinutes(2)
    private val PULS_FENSTER: Duration = Duration.ofMinutes(30)
    private val ABEND_AB: LocalTime = LocalTime.of(20, 0)

    /** Annahme: darueber ist Sebastian wach (Sitzen liegt meist darunter, Bewegung darueber). */
    private const val PULS_WACH = 75.0

    /** Beginn der laufenden Aus-Phase des Bildschirms; null, wenn er gerade an ist oder nichts bekannt ist. */
    fun ausSeit(wechsel: List<Bildschirm>, jetzt: Instant): Instant? {
        var aus: Instant? = null
        var an: Instant? = null
        for (w in wechsel.filter { it.zeit <= jetzt }.sortedBy { it.zeit }) {
            if (w.an) {
                if (an == null) an = w.zeit
            } else if (an != null || aus == null) {
                val kurz = an != null && aus != null && Duration.between(an, w.zeit) < KURZ_AN
                if (!kurz) aus = w.zeit
                an = null
            }
        }
        val laeuftAn = an
        if (laeuftAn != null && (aus == null || Duration.between(laeuftAn, jetzt) >= KURZ_AN)) return null
        return aus
    }

    /** Durchschnittspuls der letzten halben Stunde; null ohne Werte. */
    fun pulsSchnitt(proben: List<Pulsprobe>, jetzt: Instant): Double? {
        val ab = jetzt.minus(PULS_FENSTER)
        val werte = proben.filter { it.zeit > ab && it.zeit <= jetzt }.map { it.schlaege }
        return if (werte.isEmpty()) null else werte.average()
    }

    /** Zeitpunkt des Einschlafens, wenn Sebastian laut Bildschirm (und Puls) jetzt schlaeft, sonst null. */
    fun eingeschlafen(ausSeit: Instant?, pulsSchnitt: Double?, jetzt: Instant, zone: ZoneId): Instant? {
        if (ausSeit == null || Duration.between(ausSeit, jetzt) < STILL) return null
        val uhrzeit = ausSeit.atZone(zone).toLocalTime()
        if (uhrzeit < ABEND_AB && uhrzeit >= RUHE_AB) return null
        if (pulsSchnitt != null && pulsSchnitt > PULS_WACH) return null
        return ausSeit
    }

    /** Erste 3:00 nach [zeit] - dort uebernimmt die Nachtruhe. */
    private fun naechsteRuhe(zeit: Instant, zone: ZoneId): Instant {
        val ort = zeit.atZone(zone)
        val tag = if (ort.toLocalTime() < RUHE_AB) ort.toLocalDate() else ort.toLocalDate().plusDays(1)
        return tag.atTime(RUHE_AB).atZone(zone).toInstant()
    }

    /**
     * Offene Stunden fuers Pop-up (S13). In der Nachtruhe ist nichts offen, und die Nacht samt der
     * Luecke vor dem Schlafengehen wird auch danach nie nachgefragt - gezaehlt wird ab dem Ende der
     * Ruhe oder ab einem spaeteren Eintrag. Im Schlaf (Knopf, hoechstens 24 h, oder live erkannt
     * [eingeschlafen] bis 3:00) 0; ohne jeden Eintrag und ohne Aufwachen 1.
     */
    fun erinnerung(
        stand: AlltagStand,
        aufwachen: Instant?,
        jetzt: Instant,
        zone: ZoneId,
        eingeschlafen: Instant? = null,
    ): Erinnerung {
        val letzter = stand.letzterEintrag
        if (stand.schlaeft && (letzter == null || Duration.between(letzter, jetzt) <= MAX_NACHT)) {
            return Erinnerung(0, false)
        }
        if (eingeschlafen != null && eingeschlafen <= jetzt && (letzter == null || letzter <= eingeschlafen) &&
            jetzt < naechsteRuhe(eingeschlafen, zone)
        ) {
            return Erinnerung(0, false)
        }
        val beginn = ruheBeginn(jetzt, zone)
        val spaetestens = beginn.plus(RUHE_SPAETESTENS)
        fun inDerRuhe(zeit: Instant?) = zeit?.takeIf { it > beginn && it <= jetzt && it <= spaetestens }
        val wach = inDerRuhe(aufwachen)
        val ruheEnde = listOfNotNull(wach, inDerRuhe(letzter)).minOrNull() ?: spaetestens
        if (jetzt < ruheEnde) return Erinnerung(0, false)
        if (letzter == null && wach == null) return Erinnerung(1, false)
        val ab = if (letzter == null || letzter < ruheEnde) ruheEnde else letzter
        val rest = Duration.between(ab, jetzt)
        val stunden = if (rest.isNegative) 0 else rest.toHours().toInt()
        return Erinnerung(stunden, wach != null && ab == wach)
    }

    /** Spaetestes Sitzungsende in der laufenden bzw. letzten Ruhezeit - Nickerchen am Tag zaehlen nicht. */
    fun aufwachenAus(enden: List<Instant>, jetzt: Instant, zone: ZoneId): Instant? {
        val beginn = ruheBeginn(jetzt, zone)
        val grenze = minOf(jetzt, beginn.plus(RUHE_SPAETESTENS))
        return enden.filter { it > beginn && it <= grenze }.maxOrNull()
    }

    fun text(stunden: Int, nachDemAufwachen: Boolean = false): String {
        val dauer = if (stunden == 1) "1 Stunde" else "$stunden Stunden"
        return if (nachDemAufwachen) {
            "Guten Morgen! Du bist seit $dauer wach – was hast du gemacht, wie geht's dir?"
        } else {
            "Bitte $dauer nachtragen"
        }
    }

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
