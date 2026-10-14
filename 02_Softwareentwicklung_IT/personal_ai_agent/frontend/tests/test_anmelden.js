// Anmelden aus dem Heim-WLAN — Oberfläche (HTTPS-Plan H2, 14.10.2026).
//
// Prüft die reinen Funktionen aus anmelden.js und die Verdrahtung in index.html
// (Formular für Bitwarden, Ladereihenfolge vor app.js).
// Backend-Tests: backend/tests/test_anmelden_sitzung.py.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_anmelden.js anmelden.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2] && process.argv[2].endsWith('anmelden.js')
    ? process.argv[2] : path.join(__dirname, '..', 'anmelden.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');

// Ohne document läuft nur der reine Teil (die Selbststart-Funktion kehrt sofort zurück).
const modul = new Function(src + '\nreturn { anmeldenZustand, anmeldenMeldung };')();
const { anmeldenZustand, anmeldenMeldung } = modul;

let fehler = 0;
let geprueft = 0;
function pruefe(name, bedingung) {
    geprueft++;
    if (!bedingung) {
        fehler++;
        console.error('FEHLER: ' + name);
    }
}

// ── anmeldenZustand ────────────────────────────────────────────────────────
pruefe('Schlüssel im Meta-Feld (Handy selbst) = frei, ohne Abfrage',
    anmeldenZustand('abc', null) === 'frei');
pruefe('ohne Schutz in der .env = frei',
    anmeldenZustand('', { angemeldet: true, https: false, schutz: false }) === 'frei');
pruefe('schon angemeldet = frei',
    anmeldenZustand('', { angemeldet: true, https: true, schutz: true }) === 'frei');
pruefe('nicht angemeldet über HTTPS = Formular',
    anmeldenZustand('', { angemeldet: false, https: true, schutz: true }) === 'anmelden');
pruefe('nicht angemeldet über HTTP = nur Hinweis, kein Passwortfeld',
    anmeldenZustand('', { angemeldet: false, https: false, schutz: true }) === 'nur_https');
pruefe('Abfrage gescheitert = unbekannt (keine Sperre)',
    anmeldenZustand('', null) === 'unbekannt');
pruefe('Unsinn als Antwort = unbekannt', anmeldenZustand('', 'kaputt') === 'unbekannt');
pruefe('https nur bei echtem true',
    anmeldenZustand('', { angemeldet: false, https: 'ja', schutz: true }) === 'nur_https');

// ── anmeldenMeldung ────────────────────────────────────────────────────────
pruefe('401 = Passwort falsch', anmeldenMeldung(401) === 'Passwort falsch.');
pruefe('429 nennt die Wartezeit', anmeldenMeldung(429).includes('10 Minuten'));
pruefe('403 nennt HTTPS', anmeldenMeldung(403).includes('HTTPS'));
pruefe('409 nennt den fehlenden Schlüssel', anmeldenMeldung(409).includes('Schlüssel'));
pruefe('sonst mit Code', anmeldenMeldung(500).includes('500'));

// ── Verdrahtung in index.html ──────────────────────────────────────────────
const posAnmelden = html.indexOf('<script src="anmelden.js?v=');
const posApp = html.indexOf('<script src="app.js?v=');
pruefe('anmelden.js eingebunden', posAnmelden !== -1);
pruefe('anmelden.js vor app.js', posAnmelden !== -1 && posApp !== -1 && posAnmelden < posApp);
pruefe('Hülle #anmelden ist anfangs versteckt', /<section id="anmelden"[^>]*\shidden[\s>]/.test(html));
pruefe('Formular mit POST, damit Bitwarden es erkennt',
    /<form id="anmelden-formular"[^>]*method="post"/.test(html));
pruefe('Benutzerfeld autocomplete=username mit Wert agent',
    /<input[^>]*id="anmelden-benutzer"[^>]*autocomplete="username"[^>]*value="agent"/.test(html));
pruefe('Passwortfeld type=password autocomplete=current-password',
    /<input[^>]*id="anmelden-passwort"[^>]*type="password"[^>]*autocomplete="current-password"/.test(html));
pruefe('Knopf #anmelden-knopf vom Typ submit',
    /<button[^>]*id="anmelden-knopf"[^>]*type="submit"/.test(html));
pruefe('Meldungszeile mit aria-live', /id="anmelden-meldung"[^>]*aria-live="polite"/.test(html));
pruefe('Hinweis nur über HTTPS vorhanden', html.includes('id="anmelden-nur-https"'));
pruefe('Stil der Hülle vorhanden', css.includes('#anmelden'));
pruefe('kein Schlüssel im Quelltext', !/agent-schluessel" content="[^"]/.test(html));

console.log(`${geprueft - fehler}/${geprueft} Prüfungen bestanden`);
process.exit(fehler ? 1 : 0);
