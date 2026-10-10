package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM-Tests fuer den App-Knopf bei LAUFENDEM Backend (10.10.2026).
 *
 * Befund: Bei dauerhaft laufendem Server wurde beim App-Oeffnen gar nichts
 * angestossen - git pull und Wissensdatei-Uebernahme liefen nie. Jetzt feuert die
 * App in dem Fall EINEN stillen Anstoss (RUN_COMMAND ohne sichtbares Termux); den
 * Serverstart ueberspringt sie weiterhin (kein Kill, kein Neustart).
 */
class BackendWaechterTest {

    /** Simulierte Uhr, damit die Tests ohne echte Wartezeit laufen. */
    private class Uhr {
        var jetzt = 0L
        val schlafen: (Long) -> Unit = { jetzt += it }
        val lesen: () -> Long = { jetzt }
    }

    /** Attrappe: zaehlt Start UND stillen Anstoss getrennt. */
    private class Attrappe(
        private val uhr: Uhr,
        /** Ab dieser Uhrzeit (ms) antwortet das Backend; null = nie. */
        private val antwortetAb: Long?,
        private val stillOk: Boolean = true,
    ) : HealthPruefer, BackendStarter {
        var pruefungen = 0
        var starts = 0
        var stille = 0

        override fun istErreichbar(timeoutMs: Long): Boolean {
            pruefungen++
            return antwortetAb != null && uhr.jetzt >= antwortetAb
        }

        override fun starte(): Boolean {
            starts++
            return true
        }

        override fun stillerAnstoss(): Boolean {
            stille++
            return stillOk
        }
    }

    @Test
    fun laeuftBackendWirdStillAngestossenUndNichtGestartet() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = 0)
        val e = BackendWaechter(a, a, BackendStartLogik(), uhr.lesen, uhr.schlafen).sicherstellen()
        assertTrue(e.bereit)
        assertEquals(0, a.starts)     // kein (Neu-)Start
        assertEquals(1, a.stille)     // genau ein stiller Anstoss (Vorbereitung)
        assertEquals(1, a.pruefungen)
    }

    @Test
    fun stillerAnstossFehlschlagVerhindertDasBereitNicht() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = 0, stillOk = false)
        val e = BackendWaechter(a, a, BackendStartLogik(), uhr.lesen, uhr.schlafen).sicherstellen()
        assertTrue(e.bereit)          // der Anstoss ist ein Extra; die App laeuft trotzdem
        assertEquals(1, a.stille)
    }

    @Test
    fun ohneBackendWirdGestartetUndNichtStillAngestossen() {
        val uhr = Uhr()
        val a = Attrappe(uhr, antwortetAb = 9_000)
        val e = BackendWaechter(a, a, BackendStartLogik(), uhr.lesen, uhr.schlafen).sicherstellen()
        assertTrue(e.bereit)
        assertEquals(1, a.starts)     // echter Startweg (mit sichtbarem Rueckfall)
        assertEquals(0, a.stille)     // kein zusaetzlicher stiller Anstoss
    }

    @Test
    fun attrappeOhneStillenAnstossBleibtMoeglich() {
        // Die neue Methode hat einen Standard (false): bestehende Attrappen ohne
        // sie funktionieren unveraendert.
        val nurStart = object : BackendStarter {
            override fun starte(): Boolean = true
        }
        assertFalse(nurStart.stillerAnstoss())
    }
}
