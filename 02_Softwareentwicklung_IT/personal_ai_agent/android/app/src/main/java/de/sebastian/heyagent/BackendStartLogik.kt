package de.sebastian.heyagent

/** Phasen des Backend-Starts (fuer die Anzeige). */
enum class Phase { PRUEFE, TERMUX_STARTEN, WARTEN, BEREIT, FEHLER }

/** Was nach einem Health-Check zu tun ist. */
enum class Aktion { FERTIG, TERMUX_STARTEN, WEITER_WARTEN, AUFGEBEN }

/** Warum der Start scheiterte. */
enum class FehlerGrund { TERMUX_INTENT_FEHLGESCHLAGEN, ZEITUEBERSCHREITUNG }

/**
 * Reine Zeit- und Textlogik des Backend-Starts. Bewusst OHNE Android-Abhaengigkeit,
 * damit sie als normaler JVM-Test laeuft (siehe app/src/test).
 *
 * @param healthTimeoutMs Zeitlimit eines einzelnen /health-Aufrufs (Vorgabe 2 s)
 * @param pollIntervalMs Abstand der Wiederholungen beim Warten (Vorgabe 2 s)
 * @param gesamtTimeoutMs Gesamtzeit nach dem Termux-Start, bis aufgegeben wird (Vorgabe 60 s)
 */
class BackendStartLogik(
    val healthTimeoutMs: Long = 2_000,
    val pollIntervalMs: Long = 2_000,
    val gesamtTimeoutMs: Long = 60_000,
) {
    /** Erster Check beim App-Start: laeuft das Backend schon, ist alles fertig. */
    fun nachErstemCheck(ok: Boolean): Aktion =
        if (ok) Aktion.FERTIG else Aktion.TERMUX_STARTEN

    /**
     * Check waehrend des Wartens.
     * @param verstrichenMs Zeit seit dem Termux-Start
     */
    fun nachPoll(ok: Boolean, verstrichenMs: Long): Aktion = when {
        ok -> Aktion.FERTIG
        verstrichenMs >= gesamtTimeoutMs -> Aktion.AUFGEBEN
        else -> Aktion.WEITER_WARTEN
    }

    /** Anzeigetext fuer den Ladebildschirm. [verstrichenMs] zaehlt ab Termux-Start. */
    fun statusText(phase: Phase, verstrichenMs: Long = 0): String = when (phase) {
        Phase.PRUEFE -> "Prüfe, ob das Backend läuft …"
        Phase.TERMUX_STARTEN -> "Backend läuft nicht – starte es über Termux …"
        Phase.WARTEN -> {
            val s = sekunden(verstrichenMs)
            val von = sekunden(gesamtTimeoutMs)
            "Warte auf das Backend … ($s s von $von s)"
        }
        Phase.BEREIT -> "Backend bereit."
        Phase.FEHLER -> "Backend nicht erreichbar."
    }

    /** Klare deutsche Fehlermeldung mit dem naechsten Schritt fuer den Nutzer. */
    fun fehlerText(grund: FehlerGrund): String = when (grund) {
        FehlerGrund.TERMUX_INTENT_FEHLGESCHLAGEN ->
            "Termux konnte nicht gestartet werden. Prüfe: Termux ist installiert, " +
                "die App hat die Berechtigung „Termux-Befehle ausführen“, und in " +
                "~/.termux/termux.properties steht allow-external-apps=true. " +
                "Du kannst Termux auch selbst öffnen und das Widget „agent“ antippen."
        FehlerGrund.ZEITUEBERSCHREITUNG ->
            "Das Backend antwortet nach ${sekunden(gesamtTimeoutMs)} Sekunden nicht. " +
                "Steht in Termux „Process completed“, hat Android die Sitzung beendet: dort " +
                "Enter drücken und Hey Agent neu öffnen. Sonst das Widget „agent“ antippen " +
                "(oder ~/agent-ensure.log prüfen). Sobald das Backend wieder läuft, lädt die " +
                "App die Seite beim Zurückkehren selbst."
    }

    private fun sekunden(ms: Long): Long = ms.coerceAtLeast(0) / 1000
}
