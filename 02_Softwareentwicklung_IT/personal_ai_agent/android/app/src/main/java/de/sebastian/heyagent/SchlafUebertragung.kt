package de.sebastian.heyagent

import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/** Eine Schlafphase aus Health Connect (Stufe = SleepSessionRecord.STAGE_TYPE_*). */
data class SchlafPhaseRoh(val beginn: Instant, val ende: Instant, val stufe: Int)

/** Eine Schlafsitzung aus Health Connect, ohne SDK-Typen (JUnit-tauglich). */
data class SchlafNachtRoh(
    val kennung: String,
    val beginn: Instant,
    val ende: Instant,
    val offset: ZoneOffset,
    val app: String,
    val phasen: List<SchlafPhaseRoh>,
)

/**
 * Uebersetzt Schlafsitzungen in das Format von POST /api/alltag/schlaf und baut den
 * JavaScript-Aufruf fuer die Seite. Reine Funktionen, kein Android-SDK (Issue #12).
 */
object SchlafUebertragung {

    private val ZEIT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssxxx")

    /** Health-Connect-Stufen 0..7 auf die Stufen des Alltagsprotokolls. */
    fun stufe(typ: Int): String = when (typ) {
        1, 7 -> "wach"          // AWAKE, AWAKE_IN_BED
        2 -> "schlafend"        // SLEEPING (ohne Phasen)
        3 -> "aus_dem_bett"     // OUT_OF_BED
        4 -> "leicht"
        5 -> "tief"
        6 -> "rem"
        else -> "unbekannt"
    }

    /** ISO-Zeit mit Offset, auch bei UTC "+00:00". */
    fun zeit(zeitpunkt: Instant, offset: ZoneOffset): String =
        OffsetDateTime.ofInstant(zeitpunkt, offset).format(ZEIT)

    fun json(naechte: List<SchlafNachtRoh>): String =
        naechte.joinToString(",", prefix = "{\"naechte\":[", postfix = "]}") { n ->
            val phasen = n.phasen.joinToString(",", prefix = "[", postfix = "]") { p ->
                "{\"stufe\":${text(stufe(p.stufe))}," +
                    "\"beginn\":${text(zeit(p.beginn, n.offset))}," +
                    "\"ende\":${text(zeit(p.ende, n.offset))}}"
            }
            "{\"quelle_kennung\":${text(n.kennung)}," +
                "\"beginn\":${text(zeit(n.beginn, n.offset))}," +
                "\"ende\":${text(zeit(n.ende, n.offset))}," +
                "\"app\":${text(n.app)},\"phasen\":$phasen}"
        }

    /** Uebergibt den JSON-Text als EINEN JavaScript-String an die Seite (schlaf.js). */
    fun jsAufruf(json: String): String =
        "window.heyAgentSchlafEmpfangen && window.heyAgentSchlafEmpfangen(${text(json)})"

    fun meldungAufruf(meldung: String): String =
        "window.heyAgentSchlafMeldung && window.heyAgentSchlafMeldung(${text(meldung)})"

    /**
     * JSON-String-Literal, zugleich gueltig als JavaScript-String: Steuerzeichen, U+2028/2029,
     * "<" und "'" werden als \\uXXXX geschrieben (kein Ausbruch aus dem Aufruf).
     */
    private fun text(wert: String): String {
        val aus = StringBuilder(wert.length + 2).append('"')
        for (z in wert) {
            when (z) {
                '"' -> aus.append("\\\"")
                '\\' -> aus.append("\\\\")
                '\n' -> aus.append("\\n")
                '\r' -> aus.append("\\r")
                '\t' -> aus.append("\\t")
                else -> if (z < ' ' || z == ' ' || z == ' ' || z == '<' || z == '\'') {
                    aus.append(String.format("\\u%04x", z.code))
                } else {
                    aus.append(z)
                }
            }
        }
        return aus.append('"').toString()
    }
}
