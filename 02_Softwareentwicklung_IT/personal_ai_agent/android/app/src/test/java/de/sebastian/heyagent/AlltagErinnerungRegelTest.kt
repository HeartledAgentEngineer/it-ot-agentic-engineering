package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset

/** Reine JVM-Tests der Pop-up-Regel (S7). Erfundene Zeiten, kein Android-SDK noetig. */
class AlltagErinnerungRegelTest {

    private val jetzt = Instant.parse("2026-11-03T15:40:00Z")

    /** Alte Faelle (S7) am Tag, ohne Aufwachzeit, in UTC gerechnet. */
    private fun stunden(stand: AlltagStand) =
        AlltagErinnerungRegel.erinnerung(stand, null, jetzt, ZoneOffset.UTC).stunden

    @Test
    fun volleStundenSeitDemLetztenEintrag() {
        // Wie alltag_rechnen.offene_stunden im Backend
        val stand = AlltagStand(Instant.parse("2026-11-03T12:10:00Z"), schlaeft = false)
        assertEquals(3, stunden(stand))
    }

    @Test
    fun wenigerAlsEineStundeIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T14:50:00Z"), schlaeft = false)
        assertEquals(0, stunden(stand))
    }

    @Test
    fun eintragInDerZukunftIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T16:00:00Z"), schlaeft = false)
        assertEquals(0, stunden(stand))
    }

    @Test
    fun imSchlafIstNichtsOffen() {
        val stand = AlltagStand(Instant.parse("2026-11-03T02:00:00Z"), schlaeft = true)
        assertEquals(0, stunden(stand))
    }

    @Test
    fun schlafVerfaelltNach24Stunden() {
        // Backend: schlaeft gilt hoechstens 24 Stunden (MAX_NACHT). Seit S13 zaehlt die Nacht
        // nicht mehr mit: gezaehlt wird ab dem Ende der Ruhezeit (11:00), also 4 statt 26 Stunden.
        val stand = AlltagStand(Instant.parse("2026-11-02T13:40:00Z"), schlaeft = true)
        assertEquals(4, stunden(stand))
    }

    @Test
    fun ohneJedenEintragEineStunde() {
        assertEquals(1, stunden(AlltagStand(null, schlaeft = false)))
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

    // ── S13: nachts still, Meldung eine Stunde nach dem Aufwachen (Zeiten in deutscher Winterzeit) ──

    private val berlin: ZoneId = ZoneId.of("Europe/Berlin")

    private fun um(text: String): Instant = OffsetDateTime.parse("${text}+01:00").toInstant()

    private fun erinnerung(letzter: String?, aufwachen: String?, jetzt: String) =
        AlltagErinnerungRegel.erinnerung(
            AlltagStand(letzter?.let { um(it) }, schlaeft = false), aufwachen?.let { um(it) }, um(jetzt), berlin,
        )

    @Test
    fun abendsGehtEsStuendlichWeiter() {
        // Sebastian: Meldungen bis zum Schlafengehen, keine feste Ruhe am Abend.
        assertEquals(2, erinnerung("2026-11-03T21:00:00", null, "2026-11-03T23:30:00").stunden)
        assertEquals(4, erinnerung("2026-11-03T21:00:00", null, "2026-11-04T01:10:00").stunden)
    }

    @Test
    fun abDreiUhrNachtsVerfaelltDieOffeneMeldung() {
        assertEquals(0, erinnerung("2026-11-03T23:10:00", null, "2026-11-04T03:30:00").stunden)
    }

    @Test
    fun eintragInDerNachtBeendetDieRuhe() {
        // Wer nach 3 Uhr noch etwas eintraegt, ist wach: ab da wieder stuendlich.
        assertEquals(1, erinnerung("2026-11-04T04:10:00", null, "2026-11-04T05:30:00").stunden)
    }

    @Test
    fun morgensOhneAufwachenStill() {
        assertEquals(0, erinnerung("2026-11-03T21:00:00", null, "2026-11-04T08:00:00").stunden)
    }

    @Test
    fun eineStundeNachDemAufwachenMitMorgenText() {
        assertEquals(0, erinnerung("2026-11-03T21:00:00", "2026-11-04T06:50:00", "2026-11-04T07:30:00").stunden)
        val e = erinnerung("2026-11-03T21:00:00", "2026-11-04T06:50:00", "2026-11-04T07:55:00")
        assertEquals(1, e.stunden)
        assertTrue(e.nachDemAufwachen)
    }

    @Test
    fun abendlueckeWirdNichtNachgefragt() {
        // Letzter Eintrag 22:10, Aufwachen 06:50: offen sind nur die Stunden seit dem Aufwachen.
        assertEquals(2, erinnerung("2026-11-03T22:10:00", "2026-11-04T06:50:00", "2026-11-04T09:00:00").stunden)
    }

    @Test
    fun ohneUhrZaehltEsAbElfUhr() {
        val e = erinnerung("2026-11-03T21:00:00", null, "2026-11-04T12:30:00")
        assertEquals(1, e.stunden)
        assertFalse(e.nachDemAufwachen)
    }

    @Test
    fun eintragNachDemAufwachenZaehltNormal() {
        val e = erinnerung("2026-11-04T08:10:00", "2026-11-04T06:50:00", "2026-11-04T09:30:00")
        assertEquals(1, e.stunden)
        assertFalse(e.nachDemAufwachen)
    }

    @Test
    fun alteAufwachzeitBeendetKeineNeueRuhezeit() {
        assertEquals(0, erinnerung("2026-11-02T21:00:00", "2026-11-03T06:50:00", "2026-11-04T08:00:00").stunden)
    }

    @Test
    fun aufwachenIstDasSpaetesteEndeDerLetztenNacht() {
        val enden = listOf(um("2026-11-03T14:30:00"), um("2026-11-04T03:10:00"), um("2026-11-04T06:50:00"))
        assertEquals(um("2026-11-04T06:50:00"), AlltagErinnerungRegel.aufwachenAus(enden, um("2026-11-04T09:00:00"), berlin))
    }

    @Test
    fun nickerchenBeendetKeineRuhezeit() {
        // Ein Nickerchen am Nachmittag liegt in keiner Ruhezeit (3:00 bis 11:00).
        assertNull(AlltagErinnerungRegel.aufwachenAus(listOf(um("2026-11-04T14:30:00")), um("2026-11-04T15:00:00"), berlin))
    }

    @Test
    fun textNachDemAufwachen() {
        assertEquals("Guten Morgen! Du bist seit 1 Stunde wach – was hast du gemacht, wie geht's dir?",
            AlltagErinnerungRegel.text(1, nachDemAufwachen = true))
        assertEquals("Guten Morgen! Du bist seit 3 Stunden wach – was hast du gemacht, wie geht's dir?",
            AlltagErinnerungRegel.text(3, nachDemAufwachen = true))
        assertEquals("Bitte 2 Stunden nachtragen", AlltagErinnerungRegel.text(2, nachDemAufwachen = false))
    }

    // ── S13b: abends live erkennen, ob Sebastian schlaeft (Bildschirm aus, Puls der Uhr) ──

    private fun an(zeit: String) = Bildschirm(um(zeit), an = true)
    private fun aus(zeit: String) = Bildschirm(um(zeit), an = false)

    @Test
    fun bildschirmAusSeitDemLetztenAusschalten() {
        val wechsel = listOf(an("2026-11-03T21:00:00"), aus("2026-11-03T22:40:00"))
        assertEquals(um("2026-11-03T22:40:00"), AlltagErinnerungRegel.ausSeit(wechsel, um("2026-11-03T23:30:00")))
    }

    @Test
    fun bildschirmGeradeAnIstNichtAus() {
        val wechsel = listOf(aus("2026-11-03T22:00:00"), an("2026-11-03T23:00:00"))
        assertNull(AlltagErinnerungRegel.ausSeit(wechsel, um("2026-11-03T23:30:00")))
    }

    @Test
    fun kurzesAufleuchtenZaehltNicht() {
        // Eine Nachricht laesst den Bildschirm kurz angehen - Sebastian schlaeft trotzdem weiter.
        val wechsel = listOf(
            aus("2026-11-03T22:40:00"), an("2026-11-03T23:10:00"), aus("2026-11-03T23:10:30"),
        )
        assertEquals(um("2026-11-03T22:40:00"), AlltagErinnerungRegel.ausSeit(wechsel, um("2026-11-03T23:30:00")))
    }

    @Test
    fun laengeresBenutzenStartetNeu() {
        val wechsel = listOf(
            aus("2026-11-03T22:40:00"), an("2026-11-03T23:10:00"), aus("2026-11-03T23:20:00"),
        )
        assertEquals(um("2026-11-03T23:20:00"), AlltagErinnerungRegel.ausSeit(wechsel, um("2026-11-04T00:30:00")))
    }

    @Test
    fun ohneWechselKeinSignal() {
        assertNull(AlltagErinnerungRegel.ausSeit(emptyList(), um("2026-11-03T23:30:00")))
    }

    private fun eingeschlafen(ausSeit: String?, puls: Double?, jetzt: String) =
        AlltagErinnerungRegel.eingeschlafen(ausSeit?.let { um(it) }, puls, um(jetzt), berlin)

    @Test
    fun abendsDreiviertelstundeAusHeisstSchlaf() {
        assertEquals(um("2026-11-03T22:40:00"), eingeschlafen("2026-11-03T22:40:00", null, "2026-11-03T23:30:00"))
    }

    @Test
    fun kuerzerAlsDreiviertelstundeNochWach() {
        assertNull(eingeschlafen("2026-11-03T23:00:00", null, "2026-11-03T23:30:00"))
    }

    @Test
    fun amTagAusIstKeinSchlaf() {
        // Handy liegt am Nachmittag weg: das ist kein Schlaf, die Meldungen laufen weiter.
        assertNull(eingeschlafen("2026-11-03T15:00:00", null, "2026-11-03T21:30:00"))
        assertNull(eingeschlafen("2026-11-03T14:00:00", null, "2026-11-03T16:00:00"))
    }

    @Test
    fun hoherPulsHeisstWach() {
        assertNull(eingeschlafen("2026-11-03T22:40:00", 92.0, "2026-11-03T23:30:00"))
        assertEquals(um("2026-11-03T22:40:00"), eingeschlafen("2026-11-03T22:40:00", 58.0, "2026-11-03T23:30:00"))
    }

    @Test
    fun pulsSchnittNurDerLetztenHalbenStunde() {
        val proben = listOf(
            Pulsprobe(um("2026-11-03T22:30:00"), 110), Pulsprobe(um("2026-11-03T23:10:00"), 60),
            Pulsprobe(um("2026-11-03T23:20:00"), 56),
        )
        assertEquals(58.0, AlltagErinnerungRegel.pulsSchnitt(proben, um("2026-11-03T23:30:00"))!!, 0.001)
        assertNull(AlltagErinnerungRegel.pulsSchnitt(proben.take(1), um("2026-11-03T23:30:00")))
    }

    private fun mitSchlaf(letzter: String?, eingeschlafen: String?, jetzt: String) =
        AlltagErinnerungRegel.erinnerung(
            AlltagStand(letzter?.let { um(it) }, schlaeft = false), null, um(jetzt), berlin,
            eingeschlafen = eingeschlafen?.let { um(it) },
        )

    @Test
    fun imLiveSchlafKeineMeldung() {
        // Ohne Schlaf waeren um 01:10 vier Stunden offen; erkannt eingeschlafen: still.
        assertEquals(0, mitSchlaf("2026-11-03T21:00:00", "2026-11-03T22:40:00", "2026-11-04T01:10:00").stunden)
    }

    @Test
    fun eintragNachDemEinschlafenHebtDenSchlafAuf() {
        assertEquals(1, mitSchlaf("2026-11-03T23:00:00", "2026-11-03T22:40:00", "2026-11-04T00:10:00").stunden)
    }

    @Test
    fun abDreiUhrGiltWiederDieNachtregel() {
        // Nach 3:00 uebernimmt die Nachtruhe; ohne Aufwachen bleibt es still, ab 11:00 wird gezaehlt.
        assertEquals(0, mitSchlaf("2026-11-03T21:00:00", "2026-11-03T22:40:00", "2026-11-04T08:00:00").stunden)
        assertEquals(1, mitSchlaf("2026-11-03T21:00:00", "2026-11-03T22:40:00", "2026-11-04T12:30:00").stunden)
    }

    @Test
    fun startadresseMitAufnahmeAusDemPopup() {
        assertEquals("http://127.0.0.1:8080/?alltag=aufnahme", AlltagErinnerungRegel.startUrl(aufnahme = true))
        assertEquals("http://127.0.0.1:8080/", AlltagErinnerungRegel.startUrl(aufnahme = false))
    }
}
