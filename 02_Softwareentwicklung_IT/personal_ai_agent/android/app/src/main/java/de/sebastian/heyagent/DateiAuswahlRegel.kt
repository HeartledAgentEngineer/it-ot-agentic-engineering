package de.sebastian.heyagent

/**
 * Reine Regeln fuer die Bueroklammer der Seite (`<input type="file" multiple>` in
 * frontend/index.html, accept = alle Bilder und .pdf).
 * Achtung beim Kommentieren: Stern-Schraegstrich-Folgen oeffnen/schliessen in Kotlin Kommentare.
 *
 * Der Android-Teil (Intent starten, Ergebnis lesen) steht in MainActivity. Hier steht nur, was
 * ohne Android testbar ist: welche Dateiarten die Auswahl anbietet und was an die Seite zurueckgeht.
 */
object DateiAuswahlRegel {

    /** Steht fuer "alle Dateiarten" (Android-Schreibweise Stern/Stern). */
    const val ALLES = "*/*"

    /** Dateiendungen aus dem accept-Attribut der Seite und ihr MIME-Typ fuer Android. */
    private val ENDUNGEN = mapOf(
        ".pdf" to "application/pdf",
        ".jpg" to "image/jpeg",
        ".jpeg" to "image/jpeg",
        ".png" to "image/png",
        ".webp" to "image/webp",
        ".gif" to "image/gif",
        ".txt" to "text/plain",
        ".md" to "text/markdown",
        ".csv" to "text/csv",
    )

    /**
     * accept-Werte der Seite in MIME-Typen uebersetzen. Die WebView liefert sie je nach Version
     * als einzelne Eintraege oder als einen Eintrag mit Kommas, deshalb wird beides zerlegt.
     * Leeres accept oder eine unbekannte Endung ergibt ALLES: lieber zu viel anbieten als eine
     * gewollte Datei verstecken.
     */
    fun mimeTypen(accept: Array<String>?): List<String> {
        val teile = accept.orEmpty()
            .flatMap { it.split(",") }
            .map { it.trim().lowercase() }
            .filter { it.isNotEmpty() }
        if (teile.isEmpty()) return listOf(ALLES)
        val typen = teile.map { if (it.contains("/")) it else ENDUNGEN[it] ?: ALLES }.distinct()
        return if (ALLES in typen) listOf(ALLES) else typen
    }

    /**
     * Typ des Intents: genau ein Typ geht direkt hinein, mehrere Typen stehen im Extra
     * EXTRA_MIME_TYPES, der Intent selbst bekommt dann ALLES.
     */
    fun intentTyp(typen: List<String>): String = typen.singleOrNull() ?: ALLES

    /**
     * Was an die Seite zurueckgeht. Abgebrochen oder nichts gewaehlt -> null (die Seite sieht
     * "keine Datei"). Eine Mehrfachauswahl kommt als Liste, eine Einzelauswahl als einzelne
     * Adresse; manche Auswahl-Apps liefern beides, dann zaehlt die Liste (keine Doppelten).
     */
    fun <T> gewaehlt(ok: Boolean, einzeln: T?, mehrere: List<T>): List<T>? {
        if (!ok) return null
        val alle = mehrere.ifEmpty { listOfNotNull(einzeln) }
        return alle.ifEmpty { null }
    }
}
