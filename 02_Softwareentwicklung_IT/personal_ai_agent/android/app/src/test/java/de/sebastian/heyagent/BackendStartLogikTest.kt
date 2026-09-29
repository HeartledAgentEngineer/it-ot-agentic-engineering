package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Reine JVM-Tests (kein Android-SDK noetig, nur JUnit). */
class BackendStartLogikTest {

    private val logik = BackendStartLogik()

    @Test
    fun vorgabewerteSindZweiZweiSechzig() {
        assertEquals(2_000L, logik.healthTimeoutMs)
        assertEquals(2_000L, logik.pollIntervalMs)
        assertEquals(60_000L, logik.gesamtTimeoutMs)
    }

    @Test
    fun ersterCheckOkIstFertigSonstTermuxStarten() {
        assertEquals(Aktion.FERTIG, logik.nachErstemCheck(true))
        assertEquals(Aktion.TERMUX_STARTEN, logik.nachErstemCheck(false))
    }

    @Test
    fun pollOkIstImmerFertigAuchNachAblauf() {
        assertEquals(Aktion.FERTIG, logik.nachPoll(true, 0))
        assertEquals(Aktion.FERTIG, logik.nachPoll(true, 999_999))
    }

    @Test
    fun pollOhneAntwortWartetBisZumLimit() {
        assertEquals(Aktion.WEITER_WARTEN, logik.nachPoll(false, 0))
        assertEquals(Aktion.WEITER_WARTEN, logik.nachPoll(false, 59_999))
        assertEquals(Aktion.AUFGEBEN, logik.nachPoll(false, 60_000))
        assertEquals(Aktion.AUFGEBEN, logik.nachPoll(false, 61_000))
    }

    @Test
    fun statusTexteSindDeutschUndNennenFortschritt() {
        assertTrue(logik.statusText(Phase.PRUEFE).contains("Prüfe"))
        assertTrue(logik.statusText(Phase.TERMUX_STARTEN).contains("Termux"))
        assertEquals(
            "Warte auf das Backend … (12 s von 60 s)",
            logik.statusText(Phase.WARTEN, 12_400),
        )
        assertEquals("Backend bereit.", logik.statusText(Phase.BEREIT))
    }

    @Test
    fun negativeZeitWirdAlsNullAngezeigt() {
        assertEquals(
            "Warte auf das Backend … (0 s von 60 s)",
            logik.statusText(Phase.WARTEN, -5),
        )
    }

    @Test
    fun fehlertexteNennenNaechstenSchritt() {
        val zeit = logik.fehlerText(FehlerGrund.ZEITUEBERSCHREITUNG)
        assertTrue(zeit.contains("60 Sekunden"))
        assertTrue(zeit.contains("Termux"))
        val intent = logik.fehlerText(FehlerGrund.TERMUX_INTENT_FEHLGESCHLAGEN)
        assertTrue(intent.contains("allow-external-apps=true"))
        assertTrue(intent.contains("Berechtigung"))
    }

    // ---- BackendWaechter mit Attrappen und simulierter Uhr ----

    private class Uhr {
        var jetzt = 0L
        val schlafen: (Long) -> Unit = { jetzt += it }
        val lesen: () -> Long = { jetzt }
    }

    private class Attrappe(
        private val uhr: Uhr,
        /** Ab dieser Uhrzeit (ms) antwortet das Backend; null = nie. */
        private val antwortetAb: Long?,
        var startOk: Boolean = true,
    ) : HealthPruefer, BackendStarter {
        var pruefungen = 0
        var starts = 0

        override fun istErreichbar(timeoutMs: Long): Boolean {
            pruefungen++
            return antwortetAb != null && uhr.jetzt >= antwortetAb
        }

        override fun starte(): Boolean {
            starts++
            return startOk
        }
    }

    @Test
    fun laeuftBackendSchonWirdTermuxNichtGestartet() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = 0)
        val e = BackendWaechter(a, a, logik, uhr.lesen, uhr.schlafen).sicherstellen()
        assertTrue(e.bereit)
        assertEquals(0, a.starts)
        assertEquals(1, a.pruefungen)
        assertNull(e.grund)
    }

    @Test
    fun startetTermuxUndWartetBisBackendAntwortet() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = 9_000)
        val phasen = mutableListOf<Phase>()
        val e = BackendWaechter(a, a, logik, uhr.lesen, uhr.schlafen)
            .sicherstellen(meldung = { p, _ -> phasen.add(p) })
        assertTrue(e.bereit)
        assertEquals(1, a.starts)
        assertEquals(10_000L, e.dauerMs) // erster Poll ab 10 s (Takt 2 s) erfolgreich
        assertEquals(Phase.PRUEFE, phasen.first())
        assertEquals(Phase.BEREIT, phasen.last())
        assertTrue(phasen.contains(Phase.TERMUX_STARTEN))
        assertTrue(phasen.contains(Phase.WARTEN))
    }

    @Test
    fun gibtNachSechzigSekundenAuf() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = null)
        val e = BackendWaechter(a, a, logik, uhr.lesen, uhr.schlafen).sicherstellen()
        assertFalse(e.bereit)
        assertEquals(FehlerGrund.ZEITUEBERSCHREITUNG, e.grund)
        assertEquals(60_000L, e.dauerMs)
        assertEquals(1, a.starts)
        assertEquals(31, a.pruefungen) // 1 Erstcheck + 30 Polls
    }

    @Test
    fun scheitertDerTermuxStartWirdSofortAufgegeben() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = null, startOk = false)
        var letzterText = ""
        val e = BackendWaechter(a, a, logik, uhr.lesen, uhr.schlafen)
            .sicherstellen(meldung = { _, t -> letzterText = t })
        assertFalse(e.bereit)
        assertEquals(FehlerGrund.TERMUX_INTENT_FEHLGESCHLAGEN, e.grund)
        assertEquals(1, a.pruefungen) // kein Polling nach gescheitertem Start
        assertTrue(letzterText.contains("allow-external-apps=true"))
    }

    @Test
    fun abbruchBeendetDasWartenOhneWeitereChecks() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = null)
        val e = BackendWaechter(a, a, logik, uhr.lesen, uhr.schlafen)
            .sicherstellen(abgebrochen = { true })
        assertFalse(e.bereit)
        assertEquals(1, a.pruefungen)
    }
}
