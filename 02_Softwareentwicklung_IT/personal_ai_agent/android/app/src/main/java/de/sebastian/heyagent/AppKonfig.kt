package de.sebastian.heyagent

/**
 * Feste Einstellungen der App an EINER Stelle. Keine Geheimnisse hier
 * (der API-Schluessel liegt im verschluesselten Speicher, siehe [KeySpeicher]).
 *
 * Die applicationId steht in app/build.gradle.kts; hier ist nur, was der Code braucht.
 */
object AppKonfig {
    /** Loopback-Adresse des Backends in Termux (uvicorn, Port wie start-termux.sh). */
    const val BACKEND_HOST = "127.0.0.1"
    const val BACKEND_PORT = 8080
    const val START_URL = "http://$BACKEND_HOST:$BACKEND_PORT/"
    const val HEALTH_URL = "http://$BACKEND_HOST:$BACKEND_PORT/health"

    /** Name des Kopfes, den das Backend fuer /api/* verlangt. */
    const val KEY_HEADER = "X-API-Key"

    /** Termux-Paket und Pfade (Termux-Home ist fest, siehe Termux-Wiki RUN_COMMAND). */
    const val TERMUX_PAKET = "com.termux"
    const val TERMUX_HOME = "/data/data/com.termux/files/home"
    const val TERMUX_SKRIPT = "$TERMUX_HOME/agent-ensure.sh"
}
