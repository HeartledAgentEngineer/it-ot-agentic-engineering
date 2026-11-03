package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** Reine JVM-Tests der Pop-up-Regel (S7). Erfundene Zeiten, kein Android-SDK noetig. */
class AlltagErinnerungRegelTest {

    private val jetzt = Instant.parse("2026-11-03T15:40:00Z")

    @Test
    fun volleStundenSeitDemLetztenEintrag() {
        // Wie alltag_rechnen.offene_stunden im Backend
        val stand = AlltagStand(Instant.parse("2026-11-03T12:10:00Z"), schlaeft = false)
        assertEquals(3, AlltagErinnerungRegel.offeneStunden(stand, jetzt))
    }

    @Test
    fun wenigerAlsEineStundeIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T14:50:00Z"), schlaeft = false)
        assertEquals(0, AlltagErinnerungRegel.offeneStunden(stand, jetzt))
    }

    @Test
    fun eintragInDerZukunftIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T16:00:00Z"), schlaeft = false)
        assertEquals(0, AlltagErinnerungRegel.offeneStunden(stand, jetzt))
    }

    @Test
    fun imSchlafIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T02:00:00Z"), schlaeft = true)
        assertEquals(0, AlltagErinnerungRegel.offeneStunden(stand, jetzt))
    }

    @Test
    fun schlafVerfaelltNach24Stunden() {
        // Backend: schlaeft gilt hoechstens 24 Stunden (MAX_NACHT)
        val stand = AlltagStand(Instant.parse("2026-11-02T13:40:00Z"), schlaeft = true)
        assertEquals(26, AlltagErinnerungRegel.offeneStunden(stand, jetzt))
    }

    @Test
    fun ohneJedenEintragEineStunde() {
        assertEquals(1, AlltagErinnerungRegel.offeneStunden(AlltagStand(null, schlaeft = false), jetzt))
    }

    @Test
    fun textSagtWievieleStunden() {
        assertEquals("Bitte 1 Stunde nachtragen", AlltagErinnerungRegel.text(1))
        assertEquals("Bitte 4 Stunden nachtragen", AlltagErinnerungRegel.text(4))
    }

    @Test
    fun standAusDerAntwortVonOffen() {
        val stand = AlltagErinnerungRegel.standLesen(
            "{\"ok\":true,\"offene_stunden\":2,\"schlaeft\":false,\"letzter_eintrag\":\"2026-11-03T14:40:00+01:00\"}",
        )
        assertEquals(Instant.parse("2026-11-03T13:40:00Z"), stand!!.letzterEintrag)
        assertFalse(stand.schlaeft)
    }

    @Test
    fun standImSchlafUndOhneEintrag() {
        val schlaf = AlltagErinnerungRegel.standLesen("{\"ok\":true,\"schlaeft\":true,\"letzter_eintrag\":\"2026-11-03T23:10:00+01:00\"}")
        assertTrue(schlaf!!.schlaeft)
        val leer = AlltagErinnerungRegel.standLesen("{\"ok\":true,\"schlaeft\":false,\"letzter_eintrag\":null}")
        assertNull(leer!!.letzterEintrag)
    }

    @Test
    fun kaputterStandWirdVerworfen() {
        assertNull(AlltagErinnerungRegel.standLesen("kein json"))
        assertNull(AlltagErinnerungRegel.standLesen("{\"ok\":false,\"grund\":\"x\"}"))
        assertNull(AlltagErinnerungRegel.standLesen("{\"ok\":true,\"schlaeft\":false,\"letzter_eintrag\":\"gestern\"}"))
        assertNull(AlltagErinnerungRegel.standLesen("{\"ok\":true,\"letzter_eintrag\":null}"))
    }

    @Test
    fun startadresseMitAufnahmeAusDemPopup() {
        assertEquals("http://127.0.0.1:8080/?alltag=aufnahme", AlltagErinnerungRegel.startUrl(aufnahme = true))
        assertEquals("http://127.0.0.1:8080/", AlltagErinnerungRegel.startUrl(aufnahme = false))
    }
}
