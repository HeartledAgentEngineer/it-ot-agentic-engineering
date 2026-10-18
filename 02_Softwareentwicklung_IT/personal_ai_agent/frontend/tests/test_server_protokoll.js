// Server-Protokoll (18.10.2026, To-do Punkt 16) — Anzeige in der Oberfläche.
//
// Befund Sebastian: „Früher war es so, dass in Termux der Server gesteuert
// wurde und ich den Verlauf sehen konnte … Das ist nicht mehr möglich."
// Der Server schreibt jetzt in ein Protokoll; der Bereich zeigt die letzten
// Zeilen (selbst aktualisierend), dazu die Angaben aus /api/health und die
// Knöpfe „Aktualisieren" und „Neu starten".
//
// Dieser Test schneidet die REINEN Funktionen aus dem echten app.js und prüft:
// Texte, Robustheit (kein Wurf bei Unsinn), ehrliche Meldungen ohne Protokoll,
// keine Symbole (Sebastians Regel: Klartext) und die Verdrahtung im echten
// index.html/app.js/style.css. Kein Netz, kein DOM, keine Nutzerdaten.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_server_protokoll.js
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

const namen = ['serverProtokollStand', 'serverProtokollZeilenText'];
const teile = namen.map((n) => funktionAusschneiden(src, n)).join('\n');
const f = new Function(teile + '\nreturn {' + namen.join(', ') + '};')();
const stand = f.serverProtokollStand;
const zeilen = f.serverProtokollZeilenText;

let fehler = 0;
function pruefe(bed, txt) {
    if (bed) { console.log('  ok  ' + txt); } else { console.log('  FEHLER ' + txt); fehler++; }
}

// Keine Häkchen-/Statussymbole (Sebastians Regel: Klartext statt Symbole).
const verboteneSymbole = /[\u2713\u2714\u2705\u274C\u26A0\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}]/u;

const antwortOk = {
    ok: true,
    pfad: '/data/data/com.termux/files/home/agent-server.log',
    eingeschaltet: true,
    vorhanden: true,
    groesse: 3072,
    gekappt: false,
    zeilen: ['2026-10-18 09:00:00 INFO uvicorn.error: Uvicorn running on http://127.0.0.1:8080',
        '2026-10-18 09:00:01 INFO uvicorn.access: 127.0.0.1 - GET /api/health 200'],
    hinweis: null,
};

console.log('Server-Protokoll: Kopfzeile');
pruefe(stand(antwortOk).includes('agent-server.log'), 'nennt die Protokolldatei');
pruefe(stand(antwortOk).includes('3,0 kB'), 'nennt die Groesse in kB mit Komma');
pruefe(stand(antwortOk).includes('2 Zeilen'), 'nennt die Zahl der Zeilen');
pruefe(stand({ ...antwortOk, zeilen: ['x'] }).includes('1 Zeile'), 'Einzahl bei einer Zeile');
pruefe(stand({ ...antwortOk, gekappt: true }).includes('nur das Dateiende gelesen'),
    'sagt es, wenn nur das Dateiende gelesen wurde');
pruefe(stand({ ...antwortOk, eingeschaltet: false }).includes('in diesem Start nicht eingeschaltet'),
    'sagt es, wenn das Protokoll in diesem Start nicht eingeschaltet ist');
pruefe(stand({ ...antwortOk, hinweis: 'Kein Protokoll vorhanden.' }).includes('Kein Protokoll vorhanden.'),
    'nimmt den Hinweis des Servers auf');
pruefe(stand(null) === 'Protokoll nicht abrufbar.', 'ohne Antwort: klare Meldung');
pruefe(stand({ zeilen: [] }) === 'Protokoll nicht abrufbar.', 'Antwort ohne ok: klare Meldung');
pruefe(stand(undefined) === 'Protokoll nicht abrufbar.', 'undefined: klare Meldung');

console.log('Server-Protokoll: Zeilen');
const ausgabe = zeilen(antwortOk);
pruefe(Array.isArray(ausgabe) && ausgabe.length === 2, 'gibt die Serverzeilen weiter');
pruefe(ausgabe[0].includes('Uvicorn running'), 'erste Zeile unveraendert');
pruefe(zeilen({ ...antwortOk, zeilen: ['', '  ', 'echt'] }).length === 1,
    'leere Zeilen werden nicht angezeigt');
pruefe(zeilen({ ...antwortOk, zeilen: [] })[0].includes('leer'),
    'leeres Protokoll: ehrlicher Grund statt leerer Flaeche');
pruefe(zeilen({ ok: true, vorhanden: false, zeilen: [], hinweis: 'Kein Protokoll vorhanden.' })[0]
    === 'Kein Protokoll vorhanden.', 'fehlendes Protokoll: Hinweis des Servers');
pruefe(zeilen(null)[0] === 'Protokoll nicht abrufbar.', 'ohne Antwort: klare Meldung');
pruefe(zeilen({ ...antwortOk, zeilen: 'kein Feld' })[0].includes('leer'),
    'unsinnige Zeilenliste: ehrlicher Grund statt Absturz');
pruefe(zeilen({ ok: true, zeilen: [1, null, {}, 'nur das'] }).length === 1,
    'Nicht-Zeichenketten werden nicht angezeigt');

console.log('Server-Protokoll: Klartext ohne Symbole');
for (const text of [stand(antwortOk), stand(null), ...zeilen(antwortOk), ...zeilen(null)]) {
    pruefe(!verboteneSymbole.test(text), 'ohne Symbol: ' + JSON.stringify(text.slice(0, 40)));
}

console.log('Server-Protokoll: Verdrahtung');
pruefe(html.includes('id="server-protokoll"'), 'index.html hat den Bereich');
pruefe(html.includes('id="server-protokoll-btn"'), 'index.html hat den Knopf im Zustandsstreifen');
pruefe(html.includes('id="server-protokoll-aktualisieren"'), 'Knopf "Aktualisieren" vorhanden');
pruefe(html.includes('id="server-protokoll-neustart"'), 'Knopf "Neu starten" vorhanden');
pruefe(/id="server-protokoll"[^>]*hidden/.test(html), 'Bereich ist zugeklappt (hidden)');
pruefe(/<pre id="server-protokoll-zeilen"/.test(html), 'Protokoll steht in einem pre (feste Zeilen)');
pruefe(/id="server-protokoll-btn"[^>]*aria-expanded="false"/.test(html),
    'Knopf meldet den Zustand ueber aria-expanded');

pruefe(src.includes('/api/system/protokoll?zeilen='), 'app.js fragt das Server-Protokoll ab');
pruefe(src.includes('/api/system/update'), 'app.js kann den Server neu starten (bestehender Weg)');
pruefe(/const SERVER_PROTOKOLL_TAKT_MS = \d+;/.test(src), 'fester Takt fuer die Erneuerung');
pruefe(src.includes('serverProtokollStand') && src.includes('serverProtokollZeilenText'),
    'die reinen Funktionen werden benutzt');
const blockStart = src.indexOf('// ── Server-Protokoll');
const block = src.slice(blockStart, src.indexOf('// (Kanban-Board', blockStart));
pruefe(block.includes('textContent'), 'Protokollzeilen gehen als Text in die Seite');
pruefe(!/\.innerHTML/.test(block), 'Protokollzeilen werden nie als HTML eingesetzt');
pruefe(/umschalten\(bereich\.hidden\)/.test(block), 'derselbe Knopf klappt auf und zu');
pruefe(/taktStoppen\(\)/.test(block) && /taktStarten\(\)/.test(block),
    'der Takt laeuft nur, solange der Bereich offen ist');
pruefe(/neustartBtn\.disabled = true/.test(block), 'Neu starten sperrt sich gegen Doppelstart');

console.log('Server-Protokoll: Stil');
pruefe(/\.server-protokoll \{/.test(css), 'eigener Stil fuer den Bereich');
pruefe(/#server-protokoll-zeilen \{[\s\S]*?max-height[\s\S]*?overflow: auto/.test(css),
    'das Protokoll hat einen eigenen Rollbereich');
pruefe(/#server-protokoll-zeilen \{[\s\S]*?white-space: pre-wrap/.test(css),
    'lange Zeilen brechen um statt den Chat zu schieben');
pruefe(/\.server-protokoll-kopf \{[\s\S]*?flex-wrap: wrap/.test(css),
    'die Kopfzeile bricht auf Handybreite um');
pruefe(/\.server-protokoll-knoepfe button \{[\s\S]*?min-height: 28px/.test(css),
    'die Knoepfe sind mit dem Finger bedienbar');

console.log(fehler === 0 ? '\nAlle Pruefungen bestanden.' : '\n' + fehler + ' Pruefungen rot.');
process.exit(fehler === 0 ? 0 : 1);
