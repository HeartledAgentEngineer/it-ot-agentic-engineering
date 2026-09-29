package de.sebastian.heyagent

import java.net.HttpURLConnection
import java.net.URL

/** Prueft, ob das Backend antwortet. Austauschbar fuer Tests. */
interface HealthPruefer {
    fun istErreichbar(timeoutMs: Long): Boolean
}

/** Startet das Backend (in der App: ueber Termux). Austauschbar fuer Tests. */
interface BackendStarter {
    /** true, wenn der Startauftrag abgeschickt wurde (nicht, dass das Backend schon laeuft). */
    fun starte(): Boolean
}

/** Ergebnis von [BackendWaechter.sicherstellen]. */
data class StartErgebnis(
    val bereit: Boolean,
    /** Gesamtdauer bis "bereit" bzw. bis zum Aufgeben, in Millisekunden. */
    val dauerMs: Long,
    val grund: FehlerGrund? = null,
)

/**
 * Health-Check ueber HTTP GET (keine Android-Klassen noetig). /health ist im Backend
 * ohne API-Schluessel erreichbar.
 */
class HttpHealthPruefer(private val url: String = AppKonfig.HEALTH_URL) : HealthPruefer {
    override fun istErreichbar(timeoutMs: Long): Boolean {
        var verbindung: HttpURLConnection? = null
        return try {
            verbindung = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = timeoutMs.toInt()
                readTimeout = timeoutMs.toInt()
                requestMethod = "GET"
                useCaches = false
            }
            verbindung.responseCode in 200..299
        } catch (e: Exception) {
            false
        } finally {
            verbindung?.disconnect()
        }
    }
}

/**
 * Ablauf: /health pruefen -> bei Fehler Backend starten -> bis zum Limit pollen.
 * Blockiert; in der App laeuft es auf einem Hintergrund-Thread. Uhr und Schlaf sind
 * einsetzbar, damit der Ablauf ohne echte Wartezeit testbar ist.
 */
class BackendWaechter(
    private val pruefer: HealthPruefer,
    private val starter: BackendStarter,
    private val logik: BackendStartLogik = BackendStartLogik(),
    private val jetztMs: () -> Long = System::currentTimeMillis,
    private val schlafen: (Long) -> Unit = { Thread.sleep(it) },
) {
    /**
     * @param abgebrochen wird vor jedem Wartezyklus gefragt (Activity beendet -> true)
     * @param meldung bekommt Phase + Text fuer den Ladebildschirm (Aufrufer-Thread!)
     */
    fun sicherstellen(
        abgebrochen: () -> Boolean = { false },
        meldung: (Phase, String) -> Unit = { _, _ -> },
    ): StartErgebnis {
        val start = jetztMs()
        fun dauer() = jetztMs() - start

        meldung(Phase.PRUEFE, logik.statusText(Phase.PRUEFE))
        if (logik.nachErstemCheck(pruefer.istErreichbar(logik.healthTimeoutMs)) == Aktion.FERTIG) {
            meldung(Phase.BEREIT, logik.statusText(Phase.BEREIT))
            return StartErgebnis(true, dauer())
        }

        meldung(Phase.TERMUX_STARTEN, logik.statusText(Phase.TERMUX_STARTEN))
        if (!starter.starte()) {
            meldung(Phase.FEHLER, logik.fehlerText(FehlerGrund.TERMUX_INTENT_FEHLGESCHLAGEN))
            return StartErgebnis(false, dauer(), FehlerGrund.TERMUX_INTENT_FEHLGESCHLAGEN)
        }

        val wartenAb = jetztMs()
        while (!abgebrochen()) {
            meldung(Phase.WARTEN, logik.statusText(Phase.WARTEN, jetztMs() - wartenAb))
            schlafen(logik.pollIntervalMs)
            val ok = pruefer.istErreichbar(logik.healthTimeoutMs)
            when (logik.nachPoll(ok, jetztMs() - wartenAb)) {
                Aktion.FERTIG -> {
                    meldung(Phase.BEREIT, logik.statusText(Phase.BEREIT))
                    return StartErgebnis(true, dauer())
                }
                Aktion.AUFGEBEN -> {
                    meldung(Phase.FEHLER, logik.fehlerText(FehlerGrund.ZEITUEBERSCHREITUNG))
                    return StartErgebnis(false, dauer(), FehlerGrund.ZEITUEBERSCHREITUNG)
                }
                else -> Unit
            }
        }
        return StartErgebnis(false, dauer(), FehlerGrund.ZEITUEBERSCHREITUNG)
    }
}
