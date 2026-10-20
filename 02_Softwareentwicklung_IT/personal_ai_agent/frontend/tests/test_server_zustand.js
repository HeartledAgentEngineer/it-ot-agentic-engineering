// Server-Zustand (18.10.2026, To-do Punkt 12): kleine Anzeige. Seit
// 20.10.2026 (Wunsch Sebastian) im Fenster "Checks" (#selbsttest-sheet) statt
// am oberen Rand; der Zustand steckt zusätzlich im Roboter-Symbol (#agent-face).
//
// Befund (Sebastian): "Kann ich gar nicht mehr überprüfen, ob der Server
// läuft. Im Frontend sehe ich es nicht, außer wenn irgendwas nicht lädt."
// Die Anzeige fragt GET /api/health ab und nennt im Klartext: Server läuft /
// nicht erreichbar, Modell bereit / nicht geladen, Zahl der Erinnerungen,
// Stand. Bewusst flach im Fluss (kein Kasten über dem Chat) und ohne
// Häkchen-/Statussymbole — der farbige Punkt trägt den Zustand.
//
// Dieser Test schneidet die REINEN Text-Funktionen aus dem echten app.js und
// prüft Texte, Robustheit und die Verdrahtung (index.html, style.css,
// Abruf-Takt, ehrliche Meldung ohne Server) sowie (20.10.2026) den Ort der vier
// Blöcke im Checks-Fenster und das Roboter-Symbol (drei Zustände, setOnline).
//
// Aufruf (aus dem Ordner frontend):  node tests/test_server_zustand.js
const fs = require('fs');
const path = require('path');

const pfadApp = process.argv[2] || path.join(__dirname, '..', 'app.js');
const pfadHtml = path.join(__dirname, '..', 'index.html');
const pfadCss = path.join(__dirname, '..', 'style.css');
const src = fs.readFileSync(pfadApp, 'utf8');
const html = fs.readFileSync(pfadHtml, 'utf8');
const css = fs.readFileSync(pfadCss, 'utf8');

function funktionAusschneiden(quelle, name) {
    const start = quelle.indexOf('function ' + name + '(');
    if (start === -1) throw new Error('Funktion nicht gefunden: ' + name);
    let tiefe = 0;
    for (let i = quelle.indexOf('{', start); i < quelle.length; i++) {
        if (quelle[i] === '{') tiefe++;
        else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(start, i + 1);
    }
    throw new Error('Funktionsende nicht gefunden: ' + name);
}

const f = (function () {
    const namen = ['serverZustandPunkt', 'serverZustandText'];
    const teile = namen.map((n) => funktionAusschneiden(src, n)).join('\n');
    return new Function(teile + '\nreturn {' + namen.join(', ') + '};')();
})();
const punkt = f.serverZustandPunkt;
const text = f.serverZustandText;

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ✓ ' + txt); } else { console.log('  ✗ ' + txt); fehler++; }
}

// Keine Häkchen-/Statussymbole und keine Emojis in den Anzeigetexten
// (Sebastians Regel: Klartext statt Symbole).
const verboteneSymbole = /[\u2713\u2714\u2705\u274C\u26A0\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

console.log('Server-Zustand: Punkt (Ampel)');
pruefe(punkt({ status: 'ok', llm_configured: true }) === 'ok',
    'Server läuft, Modell bereit -> "ok"');
pruefe(punkt({ status: 'ok', llm_configured: false }) === 'kein-modell',
    'Server läuft, Modell nicht geladen -> "kein-modell"');
pruefe(punkt(null) === 'weg', 'keine Antwort (Server weg) -> "weg"');
pruefe(punkt(undefined) === 'weg', 'undefined -> "weg"');
pruefe(punkt({}) === 'weg', 'leeres Objekt ohne status -> "weg"');
pruefe(punkt({ status: 'kaputt' }) === 'weg', 'fremder status -> "weg"');
pruefe(punkt('ok') === 'weg', 'Zeichenkette statt Objekt -> "weg" (kein Absturz)');

console.log('Server-Zustand: Text');
pruefe(text(null) === 'Server nicht erreichbar',
    'ohne Server: "Server nicht erreichbar" (kein stilles Stehenbleiben)');
pruefe(text(undefined) === 'Server nicht erreichbar', 'undefined -> ehrliche Meldung');
pruefe(text({}) === 'Server nicht erreichbar', 'leere Antwort -> ehrliche Meldung');
const voll = { status: 'ok', llm_configured: true, memory_count: 42, version: '0.1.0' };
pruefe(text(voll) === 'Server läuft · Modell bereit · 42 Erinnerungen · Stand 0.1.0',
    'voller Zustand in EINER Zeile, gefunden: ' + text(voll));
pruefe(text({ status: 'ok', llm_configured: false, memory_count: 0, version: '0.1.0' })
    === 'Server läuft · Modell nicht geladen · 0 Erinnerungen · Stand 0.1.0',
    'Modell nicht geladen wird benannt, nicht verschwiegen');
pruefe(text({ status: 'ok', llm_configured: true, memory_count: 1 }) === 'Server läuft · Modell bereit · 1 Erinnerung',
    'Einzahl bei genau einer Erinnerung');
pruefe(text({ status: 'ok', llm_configured: true }) === 'Server läuft · Modell bereit',
    'fehlende Zahl/Stand werden weggelassen statt "undefined" zu zeigen');
pruefe(text({ status: 'ok', llm_configured: true, memory_count: 'viele' }).indexOf('viele') === -1,
    'unbrauchbare Zahl wird nicht ausgegeben');
pruefe(!verboteneSymbole.test(text(voll)) && !verboteneSymbole.test(text(null)),
    'Anzeigetexte ohne Symbole/Emojis');
pruefe(text(voll).indexOf('\n') === -1, 'eine Zeile (kein Umbruch im Text)');

console.log('Server-Zustand: Verdrahtung');
pruefe(html.indexOf('id="server-zustand"') !== -1, 'index.html enthält die Anzeige');
pruefe(html.indexOf('id="server-zustand-text"') !== -1, 'Textfeld steht im HTML');
pruefe(html.indexOf('id="server-punkt"') !== -1, 'farbiger Punkt steht im HTML');
pruefe(/id="server-zustand"[^>]*data-zustand="unbekannt"/.test(html),
    'Startzustand ist "unbekannt" (nichts wird vorgetäuscht)');
pruefe(/fetch\(`\$\{API_BASE\}\/api\/health`\)/.test(src), 'Abruf von GET /api/health');
pruefe(src.indexOf('SERVER_ZUSTAND_TAKT_MS = 5000') !== -1
    && src.indexOf('setInterval(laden, SERVER_ZUSTAND_TAKT_MS)') !== -1,
    'erneuert sich regelmäßig selbst (5 s)');
pruefe(src.indexOf('SERVER_ZUSTAND_TAKT_MS') !== -1
    && src.indexOf("document.getElementById('server-zustand')") !== -1,
    'die Anzeige ist angeschlossen (Element + Takt)');
pruefe(src.indexOf("const zustand = serverZustandPunkt(daten);") !== -1
    && src.indexOf("setAttribute('data-zustand', zustand)") !== -1,
    'der Punkt folgt dem gemessenen Zustand');

console.log('Server-Zustand: Darstellung (Farben je Zustand)');
pruefe(css.indexOf('.server-zustand') !== -1, 'style.css gestaltet die Anzeige');
['ok', 'kein-modell', 'weg'].forEach((zustand) => {
    pruefe(css.indexOf('.server-zustand[data-zustand="' + zustand + '"] .server-punkt') !== -1,
        'eigene Punktfarbe für "' + zustand + '"');
});
pruefe(/\.server-zustand\s*\{[^}]*background:\s*var\(--bg-secondary\)/.test(css),
    'eigener Hintergrund (lesbar auch im Dunkelmodus, kein durchscheinender Kasten)');

// ── Ort der vier Blöcke (20.10.2026): im Checks-Fenster, nicht mehr im Kopf ──
console.log('Checks-Fenster: Ort der vier Blöcke');
const iSheet = html.indexOf('id="selbsttest-sheet"');
const iSheetEnde = html.indexOf('id="selbsttest-text"');
const iKopfEnde = html.indexOf('</header>');
const iChat = html.indexOf('id="chat-container"');
pruefe(iSheet !== -1 && iSheetEnde > iSheet, 'Checks-Fenster (#selbsttest-sheet) mit Textfeld vorhanden');
const reihenfolge = ['server-zustand', 'hintergrund-leiste', 'datenstand', 'server-protokoll'];
let letzte = iSheet;
reihenfolge.forEach((id) => {
    const i = html.indexOf('id="' + id + '"');
    pruefe(i > iSheet && i < iSheetEnde, '#' + id + ' liegt im Fenster, vor dem Selbsttest-Text');
    pruefe(i > letzte, '#' + id + ' steht in der vorgesehenen Reihenfolge');
    pruefe(i > iKopfEnde, '#' + id + ' liegt nicht mehr im Kopfbereich');
    letzte = i;
    pruefe(html.indexOf('id="' + id + '"', i + 1) === -1, '#' + id + ' kommt nur einmal vor');
});
const vorChat = html.slice(0, iChat);
pruefe(vorChat.indexOf('id="server-zustand"') === -1
    && vorChat.indexOf('id="hintergrund-leiste"') === -1
    && vorChat.indexOf('id="datenstand"') === -1
    && vorChat.indexOf('id="server-protokoll"') === -1,
    'vor dem Chat steht keiner der vier Blöcke mehr');
pruefe(/<h2>Checks<\/h2>/.test(html) && !/<h2>Selbsttest<\/h2>/.test(html),
    'Fenster-Überschrift heißt "Checks"');
pruefe(/id="selbsttest-btn"[^>]*title="Checks – Zustand des Systems"\s+aria-label="Checks anzeigen"/.test(html),
    'Knopf: title und aria-label "Checks"');
pruefe(/role="dialog"[^>]*aria-label="Checks"/.test(html), 'Fenster: aria-label "Checks"');
pruefe(/id="system-update-status"/.test(html) && html.indexOf('id="system-update-status"') < iChat,
    '#system-update-status bleibt im Kopfbereich');

// ── Roboter-Symbol (#agent-face) ─────────────────────────────────────────────
console.log('Roboter-Symbol: drei Zustände, setOnline, Bedienung');
const g = (function () {
    const namen = ['agentGesichtFuer', 'agentZustandFuerOnline'];
    const teile = namen.map((n) => funktionAusschneiden(src, n)).join('\n');
    return new Function(teile + '\nreturn {' + namen.join(', ') + '};')();
})();
const gOk = g.agentGesichtFuer('ok');
pruefe(gOk.zeichen === '🤖' && gOk.klasse === 'agent-face-ok'
    && gOk.titel === 'Server läuft · Modell bereit', "'ok' -> Roboter, Titel 'Server läuft · Modell bereit'");
const gKm = g.agentGesichtFuer('kein-modell');
pruefe(gKm.zeichen === '🤖' && gKm.klasse === 'agent-face-kein-modell'
    && gKm.titel === 'Server läuft · Modell nicht geladen',
    "'kein-modell' -> Roboter mit eigener Klasse (oranger Ton), Titel 'Modell nicht geladen'");
const gWeg = g.agentGesichtFuer('weg');
pruefe(gWeg.zeichen === '😴' && gWeg.klasse === 'agent-face-weg'
    && gWeg.titel === 'Server nicht erreichbar', "'weg' -> Schlafgesicht, grau, Titel 'Server nicht erreichbar'");
pruefe(g.agentGesichtFuer('unbekannt').klasse === 'agent-face-ok'
    && g.agentGesichtFuer(undefined).zeichen === '🤖',
    'unbekannter Zustand fällt auf "ok" (kein Absturz)');
pruefe(g.agentZustandFuerOnline(false, 'ok') === 'weg'
    && g.agentZustandFuerOnline(false, 'kein-modell') === 'weg', 'offline -> "weg"');
pruefe(g.agentZustandFuerOnline(true, 'kein-modell') === 'kein-modell',
    'setOnline(true) nach Detailzustand "kein-modell" bleibt "kein-modell"');
pruefe(g.agentZustandFuerOnline(true, 'ok') === 'ok' && g.agentZustandFuerOnline(true, 'weg') === 'ok',
    'setOnline(true) sonst "ok"');

// setOnline selbst, mit Attrappen für state/dom/document (kein echtes DOM).
function setOnlineLauf(detail, online) {
    const face = { textContent: '', className: '', title: '', style: { filter: 'x' } };
    const teile = ['agentGesichtFuer', 'agentZustandFuerOnline', 'zeichneAgentGesicht', 'setOnline']
        .map((n) => funktionAusschneiden(src, n)).join('\n');
    const bauen = new Function('state', 'dom', 'document', 'letzterServerDetail',
        teile + '\nreturn setOnline;');
    const state = {};
    bauen(state, { statusIndicator: null }, { getElementById: (id) => (id === 'agent-face' ? face : null) },
        detail)(online);
    return { face, state };
}
let lauf = setOnlineLauf('kein-modell', true);
pruefe(lauf.face.className === 'agent-face-kein-modell' && lauf.face.title === 'Server läuft · Modell nicht geladen'
    && lauf.face.textContent === '🤖' && lauf.state.isOnline === true,
    'setOnline(true) nach "kein-modell": Symbol bleibt orange, isOnline true');
lauf = setOnlineLauf('ok', true);
pruefe(lauf.face.className === 'agent-face-ok' && lauf.face.style.filter === '',
    'setOnline(true) nach "ok": normaler Roboter, kein Inline-Filter');
lauf = setOnlineLauf('ok', false);
pruefe(lauf.face.className === 'agent-face-weg' && lauf.face.textContent === '😴' && lauf.state.isOnline === false,
    'setOnline(false): schlafend/grau, isOnline false');

// Verdrahtung: Takt und setOnline benutzen dieselbe Zeichenfunktion.
pruefe(/letzterServerDetail = zustand;\s*zeichneAgentGesicht\(zustand\);/.test(src),
    'der Health-Takt merkt den Detailzustand und zeichnet das Symbol (auch bei geschlossenem Fenster)');
pruefe(/zeichneAgentGesicht\(agentZustandFuerOnline\(online, letzterServerDetail\)\)/.test(src),
    'setOnline nutzt dieselbe Zeichenfunktion');
pruefe(/id="agent-face"[^>]*role="button"[^>]*tabindex="0"/.test(html), 'Symbol: role="button" und tabindex="0"');
pruefe(/agentGesicht\.addEventListener\('click', oeffneSelbsttestBlatt\)/.test(src),
    'Antippen öffnet das Checks-Fenster (gleiche Funktion wie der Knopf)');
pruefe(/agentGesicht\.addEventListener\('keydown'[\s\S]*?e\.key === 'Enter'[\s\S]*?e\.key === ' '[\s\S]*?oeffneSelbsttestBlatt\(\)/.test(src),
    'Enter und Leertaste öffnen ebenfalls');
pruefe(/#agent-face \{[^}]*cursor: pointer/.test(css), 'Symbol hat cursor: pointer');
pruefe(/#agent-face\.agent-face-kein-modell \{[^}]*filter:/.test(css)
    && /#agent-face\.agent-face-weg \{[^}]*grayscale/.test(css), 'CSS: oranger Ton und Grau');

console.log('Checks-Fenster: Darstellung');
pruefe(/#selbsttest-sheet #datenstand-liste,\s*#selbsttest-sheet #server-protokoll-zeilen \{[^}]*max-height: 40vh[^}]*overflow: auto/.test(css),
    'Datenstand-Liste und Protokoll rollen im Fenster selbst (40vh)');
pruefe(/#selbsttest-sheet \.server-zustand,[\s\S]*?#selbsttest-sheet \.server-protokoll \{[^}]*width: 100%/.test(css),
    'die vier Blöcke haben im Fenster volle Breite');
pruefe(/\.datenstand\[hidden\],\s*\.server-protokoll\[hidden\] \{\s*display: none/.test(css),
    'hidden wird bei Datenstand/Protokoll nicht von display:flex überstimmt');
pruefe(/app\.js\?v=20261020A/.test(html) && /style\.css\?v=20261020A/.test(html), 'Cache-Schlüssel 20261020A');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
