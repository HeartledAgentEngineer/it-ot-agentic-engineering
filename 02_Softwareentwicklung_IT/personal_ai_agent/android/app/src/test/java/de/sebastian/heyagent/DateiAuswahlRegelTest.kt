package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Reine JVM-Tests der Dateiauswahl fuer die Bueroklammer (kein Android-SDK noetig). */
class DateiAuswahlRegelTest {

    private val bilderUndPdf = listOf("image/*", "application/pdf")

    @Test
    fun einzelneEintraegeWerdenUebersetzt() {
        assertEquals(bilderUndPdf, DateiAuswahlRegel.mimeTypen(arrayOf("image/*", ".pdf")))
    }

    @Test
    fun einEintragMitKommasWirdZerlegt() {
        assertEquals(bilderUndPdf, DateiAuswahlRegel.mimeTypen(arrayOf("image/*, .PDF")))
    }

    @Test
    fun leeresAcceptBietetAllesAn() {
        assertEquals(listOf(DateiAuswahlRegel.ALLES), DateiAuswahlRegel.mimeTypen(null))
        assertEquals(listOf(DateiAuswahlRegel.ALLES), DateiAuswahlRegel.mimeTypen(arrayOf("")))
    }

    @Test
    fun unbekannteEndungVerstecktNichts() {
        assertEquals(listOf(DateiAuswahlRegel.ALLES), DateiAuswahlRegel.mimeTypen(arrayOf("image/*", ".xyz")))
    }

    @Test
    fun intentTypEinzelnOderAlles() {
        assertEquals("image/*", DateiAuswahlRegel.intentTyp(listOf("image/*")))
        assertEquals(DateiAuswahlRegel.ALLES, DateiAuswahlRegel.intentTyp(bilderUndPdf))
    }

    @Test
    fun abgebrochenGibtNull() {
        assertNull(DateiAuswahlRegel.gewaehlt(false, "a", listOf("b")))
    }

    @Test
    fun nichtsGewaehltGibtNull() {
        assertNull(DateiAuswahlRegel.gewaehlt(true, null, emptyList<String>()))
    }

    @Test
    fun einzelauswahl() {
        assertEquals(listOf("a"), DateiAuswahlRegel.gewaehlt(true, "a", emptyList()))
    }

    @Test
    fun mehrfachauswahlOhneDoppelte() {
        // Manche Auswahl-Apps liefern die erste Datei zusaetzlich einzeln - dann zaehlt die Liste.
        assertEquals(listOf("a", "b"), DateiAuswahlRegel.gewaehlt(true, "a", listOf("a", "b")))
    }

    @Test
    fun bueroklammerDerSeiteWirdVollstaendigVerstanden() {
        // Waechter ueber die Grenze App <-> Seite: Jede Dateiart, die frontend/index.html an der
        // Bueroklammer erlaubt, muss die App kennen - sonst faellt sie auf "alles" zurueck.
        val seite = File("../../frontend/index.html")
        assertTrue("frontend/index.html nicht gefunden: ${seite.absolutePath}", seite.isFile)
        val eingabe = Regex("<input[^>]*type=\"file\"[^>]*>").find(seite.readText())
        assertTrue("Keine Datei-Eingabe in index.html", eingabe != null)
        val accept = Regex("accept=\"([^\"]*)\"").find(eingabe!!.value)?.groupValues?.get(1)
        assertTrue("Datei-Eingabe ohne accept", accept != null)
        val typen = DateiAuswahlRegel.mimeTypen(arrayOf(accept!!))
        assertTrue("Unbekannte Dateiart in accept=\"$accept\" -> $typen", DateiAuswahlRegel.ALLES !in typen)
    }
}
