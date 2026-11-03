// Schlaf von der Uhr (03.11.2026, Issue #12).
//
// Hey Agent (Android) liest die Schlafsitzungen aus Health Connect und ruft
// window.heyAgentSchlafEmpfangen(jsonText) auf. Diese Seite ist angemeldet und schickt die
// Nächte an POST /api/alltag/schlaf (idempotent). Das Checks-Fenster zeigt den Stand und einen
// Knopf, der den Abgleich in der App anstößt (window.HeyAgentSchlaf.abgleichen()).
// Kein Polling, Text nur über textContent. Test: frontend/tests/test_schlaf.js.

/** Übergabe der App lesen: Liste oder {naechte: [...]}; sonst null. */
function schlafNaechteLesen(text) {
    if (typeof text !== 'string') return null;
    let daten;
    try { daten = JSON.parse(text); } catch (_) { return null; }
    if (Array.isArray(daten)) return daten;
    if (daten && Array.isArray(daten.naechte)) return daten.naechte;
    return null;
}

/** Antwort von POST /api/alltag/schlaf als Klartext. */
function schlafAbgleichText(antwort) {
    if (!antwort || antwort.ok !== true) return 'Schlaf von der Uhr nicht übernommen.';
    const zahl = (v) => (typeof v === 'number' && isFinite(v) ? v : 0);
    const neu = zahl(antwort.neu), akt = zahl(antwort.aktualisiert);
    const gleich = zahl(antwort.unveraendert), weg = zahl(antwort.abgelehnt);
    const teile = [];
    if (neu) teile.push(neu + (neu === 1 ? ' neue Nacht' : ' neue Nächte'));
    if (akt) teile.push(akt + ' aktualisiert');
    let text;
    if (teile.length) {
        if (gleich) teile.push(gleich + ' unverändert');
        text = 'Uhr abgeglichen: ' + teile.join(', ') + '.';
    } else {
        text = 'Uhr abgeglichen: nichts Neues' + (gleich ? ' (' + gleich + (gleich === 1 ? ' Nacht' : ' Nächte') + ' schon da).' : '.');
    }
    if (weg) text += ' ' + weg + ' unlesbar.';
    return text;
}

/** Kopfzeile aus GET /api/alltag/schlaf/stand. */
function schlafStandText(stand) {
    if (!stand || stand.ok !== true) return 'Schlaf (Uhr): Stand nicht abrufbar';
    if (!stand.anzahl) return 'Schlaf (Uhr): noch keine Nächte';
    let text = 'Schlaf (Uhr): ' + stand.anzahl + (stand.anzahl === 1 ? ' Nacht' : ' Nächte');
    if (typeof stand.letzte_nacht_zum === 'string') {
        const [j, m, t] = stand.letzte_nacht_zum.split('-');
        text += ', zuletzt Nacht zum ' + t + '.' + m + '.' + j;
    }
    return text;
}

/** Leer, wenn die App-Brücke da ist; sonst ein ehrlicher Hinweis. */
function schlafBrueckeHinweis(bruecke) {
    return bruecke && typeof bruecke.abgleichen === 'function'
        ? '' : 'Der Abgleich mit der Uhr geht nur in der Hey-Agent-App am Handy.';
}

function _schlafEl(id) { return document.getElementById(id); }

function _schlafMeldung(text) {
    const el = _schlafEl('schlaf-status');
    if (!el) return;
    el.textContent = text;
    el.hidden = !text;
}

/** Stand und die letzten 7 Tage holen (beim Öffnen des Checks-Fensters, kein Polling). */
async function ladeSchlaf() {
    if (!_schlafEl('schlaf-block')) return;
    const kopf = _schlafEl('schlaf-stand');
    const text = _schlafEl('schlaf-text');
    try {
        const res = await fetch(`${API_BASE}/api/alltag/schlaf/stand`, { credentials: 'same-origin', cache: 'no-store' });
        const stand = res.ok ? await res.json() : null;
        if (kopf) kopf.textContent = schlafStandText(stand);
        if (stand && stand.anzahl) {
            const von = new Date(Date.now() - 6 * 864e5).toISOString().slice(0, 10);
            const r2 = await fetch(`${API_BASE}/api/alltag/schlaf?von=${von}`, { credentials: 'same-origin', cache: 'no-store' });
            const daten = r2.ok ? await r2.json() : null;
            if (text) text.textContent = daten && daten.text ? daten.text : '';
        } else if (text) {
            text.textContent = '';
        }
    } catch (_) {
        if (kopf) kopf.textContent = schlafStandText(null);
    }
}

/** Von Hey Agent aufgerufen: Nächte an das Backend schicken und Ergebnis melden. */
async function schlafEmpfangen(jsonText) {
    const naechte = schlafNaechteLesen(jsonText);
    if (naechte === null) {
        _schlafMeldung('Schlafdaten der App nicht lesbar.');
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/api/alltag/schlaf`, {
            method: 'POST', credentials: 'same-origin', cache: 'no-store',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ naechte: naechte }),
        });
        const antwort = await res.json().catch(() => null);
        _schlafMeldung(schlafAbgleichText(res.ok ? antwort : null));
    } catch (_) {
        _schlafMeldung(schlafAbgleichText(null));
    }
    ladeSchlaf();
}

window.heyAgentSchlafEmpfangen = schlafEmpfangen;
// Hinweise der App (keine Erlaubnis, Health Connect fehlt …) als Klartext unter dem Knopf.
window.heyAgentSchlafMeldung = _schlafMeldung;

(function () {
    const knopf = _schlafEl('schlaf-abgleichen');
    if (!knopf) return;
    knopf.addEventListener('click', () => {
        const bruecke = window.HeyAgentSchlaf;
        const hinweis = schlafBrueckeHinweis(bruecke);
        if (hinweis) { _schlafMeldung(hinweis); return; }
        _schlafMeldung('Frage die Uhr-Daten bei Health Connect an …');
        bruecke.abgleichen();
    });
})();
