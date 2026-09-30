package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Reine JVM-Tests der Nachkontrolle beim Zurueckkehren in die App. */
class NachkontrolleTest {

    /** Attrappe: liefert die Antworten der Reihe nach und zaehlt die Aufrufe. */
    private class Folge(vararg antworten: Boolean) : HealthPruefer {
        private val rest = ArrayDeque(antworten.toList())
        var aufrufe = 0
        override fun istErreichbar(timeoutMs: Long): Boolean {
            aufrufe++
            return rest.removeFirstOrNull() ?: false
        }
    }

    @Test
    fun waehrendDesStartsWirdNieGeprueft() {
        assertFalse(Nachkontrolle.sollPruefen(Ansicht.SEITE, startLaeuft = true))
        assertFalse(Nachkontrolle.sollPruefen(Ansicht.FEHLER, startLaeuft = true))
        assertFalse(Nachkontrolle.sollPruefen(Ansicht.LADEN, startLaeuft = false))
    }

    @Test
    fun seiteUndFehleransichtWerdenGeprueft() {
        assertTrue(Nachkontrolle.sollPruefen(Ansicht.SEITE, startLaeuft = false))
        assertTrue(Nachkontrolle.sollPruefen(Ansicht.FEHLER, startLaeuft = false))
    }

    @Test
    fun seiteMitTotemBackendStartetNeu() {
        assertEquals(Wiederkehr.NEU_STARTEN, Nachkontrolle.entscheide(Ansicht.SEITE, erreichbar = false))
    }

    @Test
    fun seiteMitLebendemBackendBleibtInRuhe() {
        assertEquals(Wiederkehr.NICHTS, Nachkontrolle.entscheide(Ansicht.SEITE, erreichbar = true))
    }

    @Test
    fun fehleransichtLaedtDieSeiteSobaldDasBackendWiederDaIst() {
        assertEquals(Wiederkehr.SEITE_LADEN, Nachkontrolle.entscheide(Ansicht.FEHLER, erreichbar = true))
        assertEquals(Wiederkehr.NICHTS, Nachkontrolle.entscheide(Ansicht.FEHLER, erreichbar = false))
    }

    @Test
    fun einAussetzerGiltNichtAlsTot() {
        val p = Folge(false, true)
        var geschlafen = 0L
        assertTrue(Nachkontrolle.erreichbar(p, schlafen = { geschlafen += it }))
        assertEquals(2, p.aufrufe)
        assertEquals(Nachkontrolle.PAUSE_MS, geschlafen)
    }

    @Test
    fun totErstNachAllenVersuchenOhneSchlussPause() {
        val p = Folge(false, false)
        var pausen = 0
        assertFalse(Nachkontrolle.erreichbar(p, schlafen = { pausen++ }))
        assertEquals(Nachkontrolle.VERSUCHE, p.aufrufe)
        assertEquals(Nachkontrolle.VERSUCHE - 1, pausen)
    }

    @Test
    fun ersterTrefferReicht() {
        val p = Folge(true)
        assertTrue(Nachkontrolle.erreichbar(p, schlafen = { error("darf nicht warten") }))
        assertEquals(1, p.aufrufe)
    }
}
