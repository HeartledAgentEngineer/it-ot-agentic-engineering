// Server-Zustand (18.10.2026, To-do Punkt 12): kleine, dauerhaft sichtbare
// Anzeige am oberen Rand.
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
// Abruf-Takt, ehrliche Meldung ohne Server).
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
pruefe(src.indexOf("setAttribute('data-zustand', serverZustandPunkt(daten))") !== -1,
    'der Punkt folgt dem gemessenen Zustand');

console.log('Server-Zustand: Darstellung (Farben je Zustand)');
pruefe(css.indexOf('.server-zustand') !== -1, 'style.css gestaltet die Anzeige');
['ok', 'kein-modell', 'weg'].forEach((zustand) => {
    pruefe(css.indexOf('.server-zustand[data-zustand="' + zustand + '"] .server-punkt') !== -1,
        'eigene Punktfarbe für "' + zustand + '"');
});
pruefe(/\.server-zustand\s*\{[^}]*background:\s*var\(--bg-secondary\)/.test(css),
    'eigener Hintergrund (lesbar auch im Dunkelmodus, kein durchscheinender Kasten)');

if (fehler) { console.log(`\n${fehler} Prüfung(en) fehlgeschlagen.`); process.exit(1); }
console.log('\nAlle Prüfungen bestanden.');
