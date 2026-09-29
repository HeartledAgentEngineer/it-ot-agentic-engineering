package de.sebastian.heyagent

/** Was mit einer Mikrofon-/Kamera-Anfrage der Seite in der WebView geschieht. */
enum class Freigabe {
    /** Android-Erlaubnis liegt vor: der Seite das Mikrofon geben. */
    ERLAUBEN,

    /** Erst den Android-Dialog "Audio aufnehmen?" zeigen. */
    ANDROID_FRAGEN,

    /** Nie: fremde Seite, Kamera oder leere Anfrage. */
    ABLEHNEN,
}

/**
 * Reine Entscheidungsregel (ohne Android-Klassen, per JUnit testbar).
 *
 * Freigegeben wird nur das Mikrofon und nur fuer das eigene Backend
 * (127.0.0.1:8080). Die Kamera bleibt immer gesperrt, auch wenn sie zusammen mit
 * dem Mikrofon angefragt wird.
 */
object MikrofonRegel {
    /** Wert von android.webkit.PermissionRequest.RESOURCE_AUDIO_CAPTURE. */
    const val AUDIO = "android.webkit.resource.AUDIO_CAPTURE"

    fun entscheide(vomBackend: Boolean, ressourcen: List<String>, androidErlaubt: Boolean): Freigabe {
        if (!vomBackend || ressourcen.isEmpty() || ressourcen.any { it != AUDIO }) {
            return Freigabe.ABLEHNEN
        }
        return if (androidErlaubt) Freigabe.ERLAUBEN else Freigabe.ANDROID_FRAGEN
    }
}
