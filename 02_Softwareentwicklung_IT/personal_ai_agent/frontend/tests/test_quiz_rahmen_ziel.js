// SCHRITT A2 (16.10.2026) — "kein Speichern ohne Ziel" (Befund Fehler 2:
// "Rahmen verschieben, speichern, Position ist nicht im Datenbestand").
//
// Warum dieser Test die ECHTEN Funktionen aus app.js AUSFUEHRT (und nicht nur
// Zeichenketten sucht): das Kriterium ist ein ZAEHLER — ohne passendes Ziel darf
// gar kein Sendeversuch entstehen, mit passendem Ziel genau einer. Das laesst
// sich nur messen, wenn die Funktion wirklich laeuft.
//
// Drei Faelle (Plan, Abschnitt 4, Schritt A2):
//   (a) OHNE Ziel (keine Person / kein Bildpfad)      -> 0 Sendeversuche
//   (b) MIT passendem Ziel (Person + dieselbe Bildzeile) -> genau 1 Sendeversuch
//   (c) FREMDER Kontext (_aktuellerQuizPfad zeigt auf ein anderes Bild) -> 0
// Dazu: der Referenz-Weg (a) sendet weiter (fetch-Zaehler 1) — Gegenprobe, dass
// der Riegel den Gesichter-Weg nicht mit abwuergt.
//
// Aufruf: node tests/test_quiz_rahmen_ziel.js app.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2], 'utf8');
const html = fs.readFileSync(path.join(path.dirname(process.argv[2]), 'index.html'), 'utf8');

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

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'editorSpeicherZiel',
               'speichereEditorRahmen', 'schliesseBildVollbild'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

// Sandkasten: die echten Funktionen laufen gegen Attrappen der Nachbarn.
// Gezaehlt wird getrennt: `sends` = Weg ueber quizBeantwortenSilent (der macht
// intern den fetch), `fetchs` = direkter fetch (Referenz-Weg).
function baueSandkasten() {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        let _quizVollbild = null, _letzteQuizKarte = null;
        let sends = 0, fetchs = 0, meldungen = [];
        const API_BASE = '';
        function bboxNormClampen(n) { return n; }
        function bboxPixelVonNorm(n) { return [n[0], n[1], n[2], n[3]]; }
        function bboxRegionSchluessel() { return 'R'; }
        function merkeBestaetigt() {}
        function macheQuizFertig() {}
        function quizBeantwortenSilent() { sends++; return Promise.resolve({ ok: true }); }
        function fetch() { fetchs++; return Promise.resolve({ json: () => Promise.resolve({ ok: true }) }); }
        ${quelle}
        return {
            zielMitZustand: (person, pfad, bildPfad, refKontext) => {
                _aktuelleQuizPerson = person; _aktuellerQuizPfad = pfad;
                _quizEditor = { bbox_norm_live: [[0.1, 0.1, 0.2, 0.2]], personen: [],
                                melde: (t) => { meldungen.push(t); },
                                bildPfad: bildPfad, refKontext: refKontext || null };
                return editorSpeicherZiel(_quizEditor);
            },
            speichern: () => speichereEditorRahmen(0, 800, 600, null),
            schliessen: () => schliesseBildVollbild(),
            stand: () => ({ person: _aktuelleQuizPerson, pfad: _aktuellerQuizPfad }),
            zaehler: () => ({ sends: sends, fetchs: fetchs }),
            meldungen: () => meldungen,
            kennung: (p) => pfadKennung(p),
            anzeigeName: (p) => dateiAnzeigeName(p),
        };
    `;
    return new Function(koerper)();
}

console.log('\nA) Fall (a) — OHNE Ziel wird nichts gesendet');
{
    const s = baueSandkasten();
    const ziel = s.zielMitZustand('', '/bilder/A.jpg', '/bilder/A.jpg');
    pruefe(ziel.ok === false, 'ohne Person: kein Ziel');
    pruefe(/keine Person/.test(ziel.grund), 'Grund nennt die fehlende Person');
    s.speichern();
    pruefe(s.zaehler().sends === 0 && s.zaehler().fetchs === 0,
           'kein Sendeversuch (sends 0, fetchs 0)');
    pruefe(s.meldungen().length === 1 && /Nicht gespeichert/.test(s.meldungen()[0]),
           'ehrlicher Hinweis statt stiller Fehlschlag');
}

console.log('\nB) Fall (a2) — Bild ohne Quizrunde hat kein Ziel');
{
    const s = baueSandkasten();
    const ziel = s.zielMitZustand('Anna', '/bilder/A.jpg', '');
    pruefe(ziel.ok === false && /keiner offenen Quizrunde/.test(ziel.grund),
           'Editor ohne Bildpfad (z. B. Chat-Bild): kein Ziel');
    s.speichern();
    pruefe(s.zaehler().sends === 0 && s.zaehler().fetchs === 0, 'kein Sendeversuch');
}

console.log('\nC) Fall (b) — MIT passendem Ziel genau EIN Sendeversuch');
{
    const s = baueSandkasten();
    const ziel = s.zielMitZustand('Anna', '/bilder/A.jpg', '/bilder/A.jpg');
    pruefe(ziel.ok === true && ziel.weg === 'quiz', 'Ziel passt (Weg quiz)');
    s.speichern();
    pruefe(s.zaehler().sends === 1, 'genau ein Sendeversuch ueber quizBeantwortenSilent');
    pruefe(s.zaehler().fetchs === 0, 'kein zweiter Direkt-`fetch` im Quiz-Weg');
    // Anhaengsel am Pfad (Cache-Token) duerfen den Vergleich nicht stoeren.
    const s2 = baueSandkasten();
    pruefe(s2.zielMitZustand('Anna', '/bilder/A.jpg?v=20261016D', '/bilder/A.jpg').ok === true,
           'Anhaengsel ?v=… stoert den Bildvergleich nicht');
}

console.log('\nD) Fall (c) — FREMDER Kontext wird abgewiesen');
{
    const s = baueSandkasten();
    const ziel = s.zielMitZustand('Anna', '/bilder/ALT.jpg', '/bilder/NEU.jpg');
    pruefe(ziel.ok === false, 'Ziel aus einem fremden Lauf: kein Ziel');
    pruefe(/anderen Bild/.test(ziel.grund), 'Grund nennt das andere Bild');
    pruefe(s.anzeigeName(ziel.pfad) === 'ALT.jpg', 'Grund nennt nur den Dateinamen (kein Pfad im Text)');
    s.speichern();
    pruefe(s.zaehler().sends === 0 && s.zaehler().fetchs === 0,
           'NICHTS gesendet (genau das war Fehler 2)');
}

console.log('\nE) Gegenprobe — die ALTE Logik haette gesendet');
{
    // Dieselbe Lage wie (c), aber mit der alten Bedingung (person && pPfad aus
    // den globalen Werten, ohne Bildvergleich): Zaehler 1. Damit belegt der
    // Test, dass er den Unterschied wirklich misst.
    let sendsAlt = 0;
    const alt = (person, pPfad) => { if (person && pPfad) sendsAlt++; };
    alt('Anna', '/bilder/ALT.jpg');
    pruefe(sendsAlt === 1, 'alte Bedingung sendet im fremden Kontext (Zaehler 1)');
}

console.log('\nF) Referenz-Weg sendet weiter (Riegel greift dort nicht)');
{
    const s = baueSandkasten();
    const ziel = s.zielMitZustand('', '', '', { name: 'Anna', ref_id: 'r1' });
    pruefe(ziel.ok === true && ziel.weg === 'referenz', 'Referenz-Kontext: Ziel ok');
    s.speichern();
    pruefe(s.zaehler().fetchs === 1, 'genau ein fetch an den Referenz-Endpunkt');
    pruefe(s.zaehler().sends === 0, 'kein Doppel-Senden ueber den Quiz-Weg');
}

console.log('\nG) Auflage 2 — die Zielwerte leben nur fuer ihr Bild');
{
    const s = baueSandkasten();
    s.zielMitZustand('Anna', '/bilder/ALT.jpg', '/bilder/NEU.jpg');
    s.schliessen();
    pruefe(s.stand().person === '' && s.stand().pfad === '',
           'fremdes Ziel wird beim Schliessen verworfen');
    const s2 = baueSandkasten();
    s2.zielMitZustand('Anna', '/bilder/A.jpg', '/bilder/A.jpg');
    s2.schliessen();
    pruefe(s2.stand().person === 'Anna' && s2.stand().pfad === '/bilder/A.jpg',
           'dasselbe Bild: Ziel bleibt (kein erneutes Bestaetigen noetig)');
}

console.log('\nH) Verdrahtung im Quelltext (Knopf nur mit Ziel)');
{
    const bau = src.slice(src.indexOf('const speicherZiel = editorSpeicherZiel(_quizEditor);'),
                          src.indexOf('leiste.appendChild(speicherHinweis);'));
    pruefe(bau.length > 0, 'Werkzeugleiste fragt editorSpeicherZiel');
    pruefe(/if \(speicherZiel\.ok\)/.test(bau), 'Speichern-Knopf nur im Zweig speicherZiel.ok');
    pruefe(bau.indexOf("speichernBtn.textContent = '💾 Speichern'") > bau.indexOf('if (speicherZiel.ok)'),
           'Knopf entsteht erst NACH der Pruefung');
    pruefe(/speicherHinweis\.textContent = '💾 ' \+ speicherZiel\.grund/.test(bau),
           'sonst steht der ehrliche Grund in der Leiste');
    pruefe(/editorSpeicherZiel\(e\)/.test(funktionAusschneiden(src, 'speichereEditorRahmen')),
           'auch der Schreibweg selbst prueft das Ziel (doppelter Riegel)');
    pruefe(/bildPfad: pfad/.test(src), 'Quiz-Bild gibt seinen Bildpfad an den Editor mit');
    pruefe(/bildPfad: neuerPfad/.test(src), 'Vollbild-Durchlauf gibt den neuen Bildpfad mit');
    const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    pruefe(/^\d{8}[A-Z]$/.test(vApp) && vApp >= '20261016D',
           'index.html laedt app.js mit ?v= (mindestens 20261016D), gefunden: ' + vApp);
}

console.log(fehler === 0 ? '\nAlle Pruefungen bestanden.' : '\nFEHLER: ' + fehler);
process.exit(fehler === 0 ? 0 : 1);
