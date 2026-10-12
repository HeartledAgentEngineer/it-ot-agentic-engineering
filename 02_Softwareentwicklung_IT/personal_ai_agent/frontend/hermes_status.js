/**
 * Hermes Live-Status — Skript zu hermes_status.html.
 *
 * Bis P0 (12.10.2026) stand es inline in der Seite, mit fester Adresse
 * http://127.0.0.1:8080 und mit Auftragstexten per innerHTML. Jetzt:
 * - eigene Datei, weil die Inhaltsrichtlinie (CSP script-src 'self')
 *   Inline-Skripte sperrt;
 * - Adresse = eigene Herkunft (location.origin);
 * - alle Ausgaben über textContent: Auftragstexte und Ergebnisse können
 *   Modelltext enthalten und dürfen nie als HTML laufen;
 * - der API-Schlüssel kommt aus dem Meta-Feld, das der Server einsetzt.
 */
(function () {
    'use strict';

    const API = location.origin;
    const meta = document.querySelector('meta[name="agent-schluessel"]');
    const SCHLUESSEL = meta ? (meta.getAttribute('content') || '') : '';
    const STATUS_KLASSEN = ['offen', 'laeuft', 'fertig', 'fehler'];

    let letzteId = '';    // Aktuelle Auftrags-ID
    let letzteAnzahl = 0; // Gesehene Meldungen
    const statusDiv = document.getElementById('status');
    const hermesDiv = document.getElementById('hermes');
    const thoughtsDiv = document.getElementById('hermes-thoughts');
    const ergebnisDiv = document.getElementById('ergebnis');
    const infoSpan = document.getElementById('info');

    /** Element mit Text bauen — nie innerHTML. */
    function knoten(tag, text, klasse) {
        const el = document.createElement(tag);
        if (klasse) el.className = klasse;
        if (text !== undefined) el.textContent = text;
        return el;
    }

    // Formatiert einen ISO-Zeitstempel (z. B. "2026-08-22T11:21:51.123456+02:00")
    // zu lokaler Uhrzeit "HH:MM". Unbrauchbares bleibt stehen.
    function formatZeit(iso) {
        try {
            const d = new Date(iso);
            if (isNaN(d.getTime())) return iso;
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return iso;
        }
    }

    // Aus einer rohen Status-Meldung ("[ISO] text") den Text ohne Zeitstempel liefern.
    function meldungOhneZeit(m) {
        return (m || '').trim().replace(/^\[([^\]]+)\]\s*/, '');
    }

    async function poll() {
        try {
            // 1. Alle Aufträge holen → offene/laufende finden
            const optionen = SCHLUESSEL ? { headers: { 'X-API-Key': SCHLUESSEL } } : {};
            const res = await fetch(API + '/api/auftraege', optionen);
            if (!res.ok) { infoSpan.textContent = 'Server nicht erreichbar'; return; }
            const data = await res.json();
            const jobs = data.auftraege || [];

            // Letzten relevanten Job finden (offen oder laeuft oder neuester fertig)
            const relevant = jobs.filter(j => j.status === 'offen' || j.status === 'laeuft');
            const letzterJob = relevant.length > 0 ? relevant[relevant.length - 1] : jobs[jobs.length - 1];

            if (!letzterJob) { statusDiv.textContent = 'Keine Aufträge'; return; }

            const id = String(letzterJob.id || '');
            const status = String(letzterJob.status || '');
            const aufgabe = String(letzterJob.auftrag || '').substring(0, 100);
            const meldungen = letzterJob.status_meldungen || [];
            const ergebnis = String(letzterJob.ergebnis || '');

            // Status anzeigen
            statusDiv.className = STATUS_KLASSEN.includes(status) ? status : '';
            statusDiv.replaceChildren(
                knoten('b', 'Status:'), ` ${status} · `,
                knoten('span', id.substring(0, 8), 'aid'),
                document.createElement('br'),
                knoten('b', 'Aufgabe:'), ` ${aufgabe}…`
            );

            // Neue Meldungen?
            if (meldungen.length > letzteAnzahl || id !== letzteId) {
                if (id !== letzteId) {
                    // Neue ID → zurücksetzen
                    letzteAnzahl = 0;
                    thoughtsDiv.replaceChildren();
                    hermesDiv.classList.remove('aktiv');
                    ergebnisDiv.style.display = 'none';
                }

                for (const m of meldungen.slice(letzteAnzahl)) {
                    const div = knoten('div', meldungOhneZeit(m), 'hermes-thought');
                    // Zeitzeile mit lokal formatierter Uhrzeit (falls ein ISO-Timestamp drin war)
                    const isoMatch = (m || '').match(/^\[([^\]]+)\]\s*/);
                    if (isoMatch) div.appendChild(knoten('span', ' · ' + formatZeit(isoMatch[1]), 'zeit'));
                    thoughtsDiv.appendChild(div);
                    hermesDiv.classList.add('aktiv');
                }
                letzteAnzahl = meldungen.length;
                letzteId = id;
            }

            // Ergebnis?
            if (ergebnis && (status === 'fertig' || status === 'fehler')) {
                ergebnisDiv.style.display = 'block';
                ergebnisDiv.replaceChildren(
                    knoten('b', status === 'fertig' ? '✅ Fertig!' : '❌ Fehler'),
                    document.createElement('br'),
                    knoten('pre', ergebnis.substring(0, 500))
                );
            }

            infoSpan.textContent = `Aktualisiert ${new Date().toLocaleTimeString()}`;
        } catch (e) {
            infoSpan.textContent = 'Fehler: ' + e.message;
        }
    }

    // Alle 3s abfragen
    poll();
    setInterval(poll, 3000);
})();
