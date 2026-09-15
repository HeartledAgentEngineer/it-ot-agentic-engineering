// Testet, dass der Coding-Chat (conv_code) NICHT im blockierenden
// /api/hermes/chat-Zweig landet, sondern live gestreamt wird.
//
// Gemeldeter Fall (Sebastian 2026-09-15): „Es hängt, alles auf einmal, kein
// Feedback beim Mitlesen." Ursache: Bei aktivem Hermes-Modus (`loopAktiv`)
// nahm auch conv_code den Zweig POST /api/hermes/chat — der wartet den
// KOMPLETTEN Hermes-Lauf ab und tippt die fertige Antwort danach kuenstlich
// Zeichen fuer Zeichen nach. Kein Zwischengedanke, kein Lebenszeichen.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_conv_code_live_stream.js app.js               # NEU -> grün
//   git show HEAD:frontend/app.js > "$TMPDIR/alt_app.js"
//   node tests/test_conv_code_live_stream.js "$TMPDIR/alt_app.js" # ALT -> rot
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

// 1) Der loopAktiv-Zweig (blockierendes /api/hermes/chat) muss conv_code
//    ausdruecklich ausschliessen. Zeilenumbruch/Einrueckung sind erlaubt.
const guard = /if\s*\(typeof loopAktiv !== 'undefined' && loopAktiv\s*&&\s*state\.conversationId !== 'conv_code'\)/;
pruefe('loopAktiv-Zweig schliesst conv_code aus', guard.test(src),
  'Guard "state.conversationId !== \'conv_code\'" fehlt im loopAktiv-Zweig');

// 2) Der Live-Stream-Weg (Track C) muss weiterhin vorhanden sein — der Fix
//    darf ihn nicht mitentfernt haben.
pruefe('Live-Stream-Weg /api/chat/stream bleibt erhalten',
  src.includes('/api/chat/stream'));

// 3) Der blockierende Weg darf nicht ganz verschwunden sein: fuer den
//    HAUPT-Chat (conv_main) ist /api/hermes/chat weiterhin richtig.
pruefe('blockierender Weg /api/hermes/chat bleibt fuer den Haupt-Chat vorhanden',
  src.includes("${API_BASE}/api/hermes/chat`"));

// 4) Genau EIN Vorkommen des Guards: keine zweite, widersprechende Weiche.
//    (Ein weiteres "conversationId !== 'conv_code'" gibt es bewusst an anderer
//    Stelle — der /eingabe-Kommentarweg —, deshalb wird hier der Guard selbst
//    gezaehlt, nicht der Teilausdruck.)
const treffer = (src.match(/typeof loopAktiv !== 'undefined' && loopAktiv\s*&&\s*state\.conversationId !== 'conv_code'/g) || []).length;
pruefe('conv_code-Ausschluss genau einmal vorhanden', treffer === 1,
  'gefundene Vorkommen: ' + treffer);

// 5) Der Live-Gedanken-Zweig (eigene Blase je Zwischenmeldung) muss bleiben.
pruefe('Gedanken werden als eigene Blase gerendert',
  src.includes("daten.art === 'gedanke'") && src.includes('fuegeGedankeMitAbbruchHinzu'));

console.log('\nERGEBNIS: ' + (fehler ? fehler + ' Prüfungen rot' : 'alle Prüfungen grün'));
process.exit(fehler ? 1 : 0);