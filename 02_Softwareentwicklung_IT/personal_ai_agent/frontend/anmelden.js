// Anmelden aus dem Heim-WLAN (HTTPS-Plan H2, 14.10.2026).
//
// Seit H1 setzt der Server den API-Schlüssel nur noch für Loopback-Clients
// (Handy selbst) in die Startseite. PC und Tablet im WLAN sehen ein leeres
// Meta-Feld und melden sich hier an: Benutzer „agent“, Passwort = API-Schlüssel
// (Bitwarden füllt beides aus). Der Server setzt ein Sitzungs-Cookie
// (Secure, HttpOnly, SameSite=Strict); der Browser schickt es bei jeder Anfrage
// an die eigene Adresse von selbst mit — app.js muss dafür nichts tun.
//
// Wird vor app.js geladen. Ohne API_KEY in der .env (``schutz: false``) und am
// Handy selbst (Schlüssel im Meta-Feld) bleibt alles wie bisher.

/** Was ist zu tun? Reine Funktion (Node-Test: tests/test_anmelden.js).
 *  @param {string} schluessel  Inhalt des Meta-Felds ``agent-schluessel``
 *  @param {object|null} sitzung Antwort von GET /api/auth/sitzung (null = Fehler)
 *  @returns {'frei'|'anmelden'|'nur_https'|'unbekannt'} */
function anmeldenZustand(schluessel, sitzung) {
    if (schluessel) return 'frei';
    if (!sitzung || typeof sitzung !== 'object') return 'unbekannt';
    if (sitzung.schutz === false || sitzung.angemeldet === true) return 'frei';
    return sitzung.https === true ? 'anmelden' : 'nur_https';
}

/** Meldung zur Antwort von POST /api/auth/anmelden (Status-Code). */
function anmeldenMeldung(status) {
    if (status === 401) return 'Passwort falsch.';
    if (status === 429) return 'Zu viele Fehlversuche – bitte 10 Minuten warten.';
    if (status === 403) return 'Anmelden geht nur über HTTPS.';
    if (status === 409) return 'Am Handy ist noch kein Schlüssel eingerichtet.';
    return 'Anmelden gerade nicht möglich (' + status + ').';
}

(function () {
    if (typeof document === 'undefined') return;     // Node-Test
    const feld = document.querySelector('meta[name="agent-schluessel"]');
    const schluessel = (feld && feld.getAttribute('content')) || '';
    if (schluessel) return;

    const huelle = document.getElementById('anmelden');
    if (!huelle) return;
    const formular = document.getElementById('anmelden-formular');
    const passwort = document.getElementById('anmelden-passwort');
    const knopf = document.getElementById('anmelden-knopf');
    const meldung = document.getElementById('anmelden-meldung');
    const hinweis = document.getElementById('anmelden-nur-https');

    function zeigen(zustand) {
        if (zustand === 'frei' || zustand === 'unbekannt') return;
        huelle.hidden = false;
        document.body.classList.add('anmelden-offen');
        const nurHttps = zustand === 'nur_https';
        hinweis.hidden = !nurHttps;
        formular.hidden = nurHttps;
        if (!nurHttps) setTimeout(() => passwort.focus(), 50);
    }

    fetch('/api/auth/sitzung', { credentials: 'same-origin', cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
        .then((sitzung) => zeigen(anmeldenZustand(schluessel, sitzung)));

    formular.addEventListener('submit', (ereignis) => {
        ereignis.preventDefault();
        knopf.disabled = true;
        meldung.textContent = '';
        fetch('/api/auth/anmelden', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ passwort: passwort.value }),
        })
            .then((r) => {
                if (r.ok) {
                    location.reload();
                    return;
                }
                meldung.textContent = anmeldenMeldung(r.status);
                passwort.select();
            })
            .catch(() => { meldung.textContent = 'Keine Verbindung zum Agenten.'; })
            .finally(() => { knopf.disabled = false; });
    });
})();
