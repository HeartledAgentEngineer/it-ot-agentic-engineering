package de.sebastian.heyagent

/** Was die App gerade zeigt. */
enum class Ansicht { SEITE, LADEN, FEHLER }

/** Was nach der Nachkontrolle zu tun ist. */
enum class Wiederkehr { NICHTS, NEU_STARTEN, SEITE_LADEN }

/**
 * Nachkontrolle beim Zurueckkehren in die App (onResume). Reine Logik, JUnit-getestet.
 *
 * Anlass (30.09.2026, am Handy belegt): Android hat die Termux-Sitzung unter Speichermangel
 * hart beendet ("[Process completed (signal 9)]"), das Backend lief darin und war mit weg.
 * Die App merkte das nicht - sie prueft /health bisher nur beim Kaltstart. Jetzt:
 * - Seite sichtbar, Backend weg -> neu starten (Ladebildschirm, Termux, warten).
 * - Fehleransicht sichtbar, Backend inzwischen wieder da (z. B. nach dem Widget) -> Seite laden,
 *   statt auf "Erneut versuchen" zu warten.
 * - Waehrend ein Start laeuft, nie eingreifen.
 */
object Nachkontrolle {

    /** So oft wird geprueft, bevor "weg" gilt - ein einzelner Aussetzer startet nichts neu. */
    const val VERSUCHE = 2

    /** Zeitlimit je Versuch (Loopback antwortet in Millisekunden). */
    const val TIMEOUT_MS = 1_500L

    /** Pause zwischen zwei Versuchen. */
    const val PAUSE_MS = 500L

    fun sollPruefen(ansicht: Ansicht, startLaeuft: Boolean): Boolean =
        !startLaeuft && ansicht != Ansicht.LADEN

    fun entscheide(ansicht: Ansicht, erreichbar: Boolean): Wiederkehr = when {
        ansicht == Ansicht.SEITE && !erreichbar -> Wiederkehr.NEU_STARTEN
        ansicht == Ansicht.FEHLER && erreichbar -> Wiederkehr.SEITE_LADEN
        else -> Wiederkehr.NICHTS
    }

    /**
     * Erreichbar, sobald ein Versuch klappt; "weg" erst nach [versuche] Fehlschlaegen.
     * [schlafen] ist einsetzbar, damit der Test ohne echte Wartezeit laeuft.
     */
    fun erreichbar(
        pruefer: HealthPruefer,
        versuche: Int = VERSUCHE,
        schlafen: (Long) -> Unit = { Thread.sleep(it) },
    ): Boolean {
        repeat(versuche) { nr ->
            if (pruefer.istErreichbar(TIMEOUT_MS)) return true
            if (nr < versuche - 1) schlafen(PAUSE_MS)
        }
        return false
    }
}
