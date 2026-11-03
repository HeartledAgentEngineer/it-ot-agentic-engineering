package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneOffset

/** Reine JVM-Tests der Schlaf-Uebergabe an die Seite (erfundene Daten, kein Android-SDK noetig). */
class SchlafUebertragungTest {

    private val plusEins = ZoneOffset.ofHours(1)

    private fun nacht(kennung: String = "abc-1", app: String = "com.beispiel.uhr") = SchlafNachtRoh(
        kennung = kennung,
        beginn = Instant.parse("2026-11-02T22:10:00Z"),
        ende = Instant.parse("2026-11-03T05:40:00Z"),
        offset = plusEins,
        app = app,
        phasen = listOf(
            SchlafPhaseRoh(Instant.parse("2026-11-02T22:10:00Z"), Instant.parse("2026-11-02T23:00:00Z"), 4),
            SchlafPhaseRoh(Instant.parse("2026-11-02T23:00:00Z"), Instant.parse("2026-11-03T00:30:00Z"), 5),
        ),
    )

    @Test
    fun stufenWerdenWieHealthConnectUebersetzt() {
        // Werte von SleepSessionRecord.STAGE_TYPE_* (0..7)
        val erwartet = listOf("unbekannt", "wach", "schlafend", "aus_dem_bett", "leicht", "tief", "rem", "wach")
        assertEquals(erwartet, (0..7).map { SchlafUebertragung.stufe(it) })
        assertEquals("unbekannt", SchlafUebertragung.stufe(99))
        assertEquals("unbekannt", SchlafUebertragung.stufe(-1))
    }

    @Test
    fun zeitHatImmerEinenOffset() {
        val t = Instant.parse("2026-11-02T22:10:00Z")
        assertEquals("2026-11-02T23:10:00+01:00", SchlafUebertragung.zeit(t, plusEins))
        // Auch bei UTC "+00:00" statt "Z" - eindeutig fuer jeden ISO-Leser.
        assertEquals("2026-11-02T22:10:00+00:00", SchlafUebertragung.zeit(t, ZoneOffset.UTC))
    }

    @Test
    fun jsonHatDieFelderDesBackends() {
        val json = SchlafUebertragung.json(listOf(nacht()))
        assertTrue(json.startsWith("{\"naechte\":[{"))
        assertTrue(json.contains("\"quelle_kennung\":\"abc-1\""))
        assertTrue(json.contains("\"beginn\":\"2026-11-02T23:10:00+01:00\""))
        assertTrue(json.contains("\"ende\":\"2026-11-03T06:40:00+01:00\""))
        assertTrue(json.contains("\"app\":\"com.beispiel.uhr\""))
        assertTrue(json.contains("{\"stufe\":\"leicht\",\"beginn\":\"2026-11-02T23:10:00+01:00\",\"ende\":\"2026-11-03T00:00:00+01:00\"}"))
        assertTrue(json.contains("\"stufe\":\"tief\""))
    }

    @Test
    fun leereListeIstGueltigesJson() {
        assertEquals("{\"naechte\":[]}", SchlafUebertragung.json(emptyList()))
    }

    @Test
    fun sonderzeichenWerdenMaskiert() {
        val json = SchlafUebertragung.json(listOf(nacht(kennung = "a\"b\\c\nd", app = "x\u0001y")))
        assertTrue(json.contains("\"quelle_kennung\":\"a\\\"b\\\\c\\nd\""))
        assertTrue(json.contains("\"app\":\"x\\u0001y\""))
    }

    @Test
    fun jsAufrufUebergibtEinenTextUndBrichtNichtAus() {
        val aufruf = SchlafUebertragung.jsAufruf("{\"a\":\"</script>' \"}")
        assertTrue(aufruf.startsWith("window.heyAgentSchlafEmpfangen && window.heyAgentSchlafEmpfangen(\""))
        assertTrue(aufruf.endsWith("\")"))
        assertFalse(aufruf.contains("</script>"))
        assertFalse(aufruf.contains(" "))
        assertFalse(aufruf.contains("'"))
    }

    @Test
    fun meldungRuftDieMeldeFunktionAuf() {
        val aufruf = SchlafUebertragung.meldungAufruf("Keine \"Erlaubnis\"")
        assertEquals(
            "window.heyAgentSchlafMeldung && window.heyAgentSchlafMeldung(\"Keine \\\"Erlaubnis\\\"\")",
            aufruf,
        )
    }
}
