package de.sebastian.heyagent

import org.junit.Assert.assertEquals
import org.junit.Test

/** Reine JVM-Tests der Mikrofon-Freigabe (kein Android-SDK noetig). */
class MikrofonRegelTest {

    private val audio = listOf(MikrofonRegel.AUDIO)

    @Test
    fun backendMitErlaubnisBekommtDasMikrofon() {
        assertEquals(Freigabe.ERLAUBEN, MikrofonRegel.entscheide(true, audio, true))
    }

    @Test
    fun ohneAndroidErlaubnisWirdAndroidGefragt() {
        assertEquals(Freigabe.ANDROID_FRAGEN, MikrofonRegel.entscheide(true, audio, false))
    }

    @Test
    fun fremdeSeiteBekommtNie() {
        assertEquals(Freigabe.ABLEHNEN, MikrofonRegel.entscheide(false, audio, true))
        assertEquals(Freigabe.ABLEHNEN, MikrofonRegel.entscheide(false, audio, false))
    }

    @Test
    fun kameraWirdAbgelehntAuchZusammenMitMikrofon() {
        val kamera = "android.webkit.resource.VIDEO_CAPTURE"
        assertEquals(Freigabe.ABLEHNEN, MikrofonRegel.entscheide(true, listOf(kamera), true))
        assertEquals(Freigabe.ABLEHNEN, MikrofonRegel.entscheide(true, audio + kamera, true))
    }

    @Test
    fun leereAnfrageWirdAbgelehnt() {
        assertEquals(Freigabe.ABLEHNEN, MikrofonRegel.entscheide(true, emptyList(), true))
    }

    @Test
    fun konstanteEntsprichtAndroid() {
        // Wert von android.webkit.PermissionRequest.RESOURCE_AUDIO_CAPTURE
        assertEquals("android.webkit.resource.AUDIO_CAPTURE", MikrofonRegel.AUDIO)
    }
}
