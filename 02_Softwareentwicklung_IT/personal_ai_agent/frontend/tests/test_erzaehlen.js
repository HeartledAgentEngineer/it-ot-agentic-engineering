// Erzähl-Diashow: Prüfblatt (Auftrag E8a, 28.09.2026).
//
// Dieser Test prüft:
//   * die drei REINEN Funktionen werden wörtlich aus dem ECHTEN erzaehlen.js
//     geschnitten und in Node ausgeführt (wie test_selbsttest.js/test_foto_galerie.js) —
//     es wird nichts nachgebaut,
//   * erzaehlSprachbefehl: nur EXAKTE Treffer auf weiter/zurück/speichern
//     (samt Varianten) lösen einen Befehl aus, alles andere ist Diktat-Text,
//   * erzaehlTitel: event -> thema -> "Ohne Titel", nimmt ein vorhandenes
//     titel-Feld direkt an,
//   * erzaehlIndex: geklemmt an den Rändern (kein Überlauf), n<=0 -> 0,
//   * index.html lädt erzaehlen.js mit ?v= und enthält #erzaehlen-btn.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_erzaehlen.js erzaehlen.js
const fs = require('fs');
const path = require('path');

const pfadJs = process.argv[2] || path.join(__dirname, '..', 'erzaehlen.js');
const src = fs.readFileSync(pfadJs, 'utf8');
const verzeichnis = path.dirname(path.resolve(pfadJs));
let html = '';
try { html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8'); } catch (_) {}

let fehler = 0;
function pruefe(name, bedingung, detail) {
  if (bedingung) { console.log('  OK   ' + name); }
  else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Funktion exakt aus dem Quelltext schneiden (Klammern zählen). */
function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('nicht gefunden: ' + name);
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

// Die reinen Funktionen aus dem ECHTEN Quelltext laden und ausführen.
// erzaehlSprachbefehl ruft den privaten Helfer _erzaehlNormalisieren —
// beide zusammen ausschneiden, damit nichts nachgebaut wird.
eval(extractFn('_erzaehlNormalisieren'));
eval(extractFn('erzaehlSprachbefehl'));
eval(extractFn('erzaehlTitel'));
eval(extractFn('erzaehlSeite'));
eval(extractFn('erzaehlIndex'));

console.log('\n1) erzaehlSprachbefehl — nur exakte Treffer sind ein Befehl');
pruefe('null -> null', erzaehlSprachbefehl(null) === null);
pruefe('undefined -> null', erzaehlSprachbefehl(undefined) === null);
pruefe('leer -> null', erzaehlSprachbefehl('') === null);
pruefe('nur Leerzeichen -> null', erzaehlSprachbefehl('   ') === null);
pruefe('Zahl als Eingabe -> null (kein Wurf)', erzaehlSprachbefehl(42) === null);

pruefe('"weiter" -> weiter', erzaehlSprachbefehl('weiter') === 'weiter');
pruefe('"Weiter" (Groß) -> weiter', erzaehlSprachbefehl('Weiter') === 'weiter');
pruefe('"weiter." (Punkt) -> weiter', erzaehlSprachbefehl('weiter.') === 'weiter');
pruefe('"  weiter  " (Leerzeichen) -> weiter', erzaehlSprachbefehl('  weiter  ') === 'weiter');
pruefe('"nächstes" -> weiter', erzaehlSprachbefehl('nächstes') === 'weiter');
pruefe('"naechstes" -> weiter', erzaehlSprachbefehl('naechstes') === 'weiter');

pruefe('"zurück" -> zurueck', erzaehlSprachbefehl('zurück') === 'zurueck');
pruefe('"zurueck" -> zurueck', erzaehlSprachbefehl('zurueck') === 'zurueck');
pruefe('"vorheriges" -> zurueck', erzaehlSprachbefehl('vorheriges') === 'zurueck');

pruefe('"speichern" -> speichern', erzaehlSprachbefehl('speichern') === 'speichern');
pruefe('"Speichern!" -> speichern', erzaehlSprachbefehl('Speichern!') === 'speichern');

pruefe('"Heute war ein schöner Tag" -> null (Diktat)', erzaehlSprachbefehl('Heute war ein schöner Tag') === null);
pruefe('"bitte weiter machen" -> null (kein exaktes Wort)', erzaehlSprachbefehl('bitte weiter machen') === null);
pruefe('"weitergehen" -> null (kein exaktes Wort)', erzaehlSprachbefehl('weitergehen') === null);
pruefe('"ich möchte speichern und dann..." -> null', erzaehlSprachbefehl('ich möchte speichern und dann weiterreden') === null);

console.log('\n2) erzaehlTitel — event -> thema -> "Ohne Titel"');
pruefe('nimmt vorhandenes titel-Feld direkt', erzaehlTitel({ titel: 'Schon fertig' }) === 'Schon fertig');
pruefe('event hat Vorrang', erzaehlTitel({ event: 'Geburtstag', thema: 'Feiern' }) === 'Geburtstag');
pruefe('ohne event -> thema', erzaehlTitel({ event: null, thema: 'Haus und Garten' }) === 'Haus und Garten');
pruefe('ohne event/thema -> Ohne Titel', erzaehlTitel({ event: null, thema: null }) === 'Ohne Titel');
pruefe('leere Zeichenketten zählen nicht', erzaehlTitel({ event: '   ', thema: '' }) === 'Ohne Titel');
pruefe('null -> Ohne Titel (kein Wurf)', erzaehlTitel(null) === 'Ohne Titel');
pruefe('undefined -> Ohne Titel (kein Wurf)', erzaehlTitel(undefined) === 'Ohne Titel');
pruefe('Zahl -> Ohne Titel (kein Wurf)', erzaehlTitel(42) === 'Ohne Titel');

console.log('\n2b) erzaehlSeite — Blättern der Ereignisliste (über 2.000 Ereignisse)');
const s1 = erzaehlSeite(2127, 200, 200);
pruefe('2127 gesamt, 200 geladen -> Knopf nötig', s1.kannMehr === true);
pruefe('Rest = 1927', s1.rest === 1927);
pruefe('nächste Seite holt 200', s1.naechste === 200);
pruefe('Hinweis nennt beide Zahlen', s1.text === '200 von 2127 Ereignissen · 1927 noch nicht geladen');
pruefe('Knopf-Text nennt Rest', s1.knopfText === 'Weitere 200 laden (1927 übrig)');

const s2 = erzaehlSeite(2127, 2100, 200);
pruefe('letzte Seite holt nur den Rest (27)', s2.naechste === 27);
pruefe('letzte Seite: Knopf-Text passt', s2.knopfText === 'Weitere 27 laden (27 übrig)');

const s3 = erzaehlSeite(150, 150, 200);
pruefe('alles geladen -> kein Knopf', s3.kannMehr === false);
pruefe('alles geladen: Hinweis ohne Zusatz', s3.text === '150 von 150 Ereignissen');
pruefe('alles geladen: kein Knopf-Text', s3.knopfText === '');

const s4 = erzaehlSeite(0, 0, 200);
pruefe('keine Ereignisse -> kein Knopf (kein Wurf)', s4.kannMehr === false && s4.rest === 0);
pruefe('Unsinn wird geklemmt', erzaehlSeite(-5, -3, 0).kannMehr === false);
pruefe('geladen > gesamt wird geklemmt', erzaehlSeite(10, 99, 200).rest === 0);
pruefe('null-Eingaben werfen nicht', erzaehlSeite(null, null, null).text === '0 von 0 Ereignissen');
pruefe('undefined -> Ohne Titel (kein Wurf)', erzaehlTitel(undefined) === 'Ohne Titel');
pruefe('Zahl -> Ohne Titel (kein Wurf)', erzaehlTitel(42) === 'Ohne Titel');

console.log('\n3) erzaehlIndex — geklemmt an den Rändern, kein Überlauf');
pruefe('Mitte vor', erzaehlIndex(2, 5, 1) === 3);
pruefe('Mitte zurück', erzaehlIndex(2, 5, -1) === 1);
pruefe('am Ende "vor" bleibt am Ende (kein Umlauf)', erzaehlIndex(4, 5, 1) === 4);
pruefe('am Anfang "zurück" bleibt am Anfang (kein Umlauf)', erzaehlIndex(0, 5, -1) === 0);
pruefe('n=0 -> 0', erzaehlIndex(0, 0, 1) === 0);
pruefe('n negativ -> 0', erzaehlIndex(3, -1, 1) === 0);
pruefe('unbekannte Richtung -> vor', erzaehlIndex(2, 5, 0) === 3);
pruefe('nicht-numerischer Index -> wie 0', erzaehlIndex('x', 5, 1) === 1);
pruefe('n=1 bleibt immer 0', erzaehlIndex(0, 1, 1) === 0 && erzaehlIndex(0, 1, -1) === 0);

console.log('\n4) Verdrahtung: index.html lädt erzaehlen.js mit Cache-Bust und den Knopf');
pruefe('index.html bindet erzaehlen.js mit ?v= ein', /erzaehlen\.js\?v=\d{8}[A-Z]/.test(html), 'nicht gefunden');
pruefe('#erzaehlen-btn existiert', /id="erzaehlen-btn"/.test(html));
pruefe('erzaehlen.js wird NACH app.js eingebunden (API-Key-Patch zuerst)',
  html.indexOf('app.js?v=') < html.indexOf('erzaehlen.js?v='));
pruefe('#erzaehlen-sheet existiert', /id="erzaehlen-sheet"/.test(html));

console.log('\n5) Quelltext-Regeln: fetch -> Blob -> Objekt-URL, kein direktes thumb-URL in src, Freigabe vorhanden');
pruefe('nutzt URL.createObjectURL', src.includes('URL.createObjectURL'));
pruefe('nutzt URL.revokeObjectURL (Freigabe)', src.includes('URL.revokeObjectURL'));
pruefe('lädt Bilder über /api/cloud/thumb', src.includes('/api/cloud/thumb'));
pruefe('nutzt /api/sprache/transkript wie app.js (kein neuer Anbieter)', src.includes('/api/sprache/transkript'));
pruefe('MediaRecorder wird bewusst NICHT instanziiert', !src.includes('new MediaRecorder'));
pruefe('nutzt pcm-recorder.js (AudioWorklet, wie app.js)', src.includes('pcm-recorder.js'));
pruefe('app.js wird NICHT verändert (diese Datei ist eigenständig)', !src.includes('function sendMessage'));

// Fehler 06.10.2026 (am Handy gemessen): .erzaehl-spalte { display: flex } hebelte das
// hidden-Attribut aus — Liste blieb stehen, Diashow lag 20 px hoch darunter.
let css = '';
try { css = fs.readFileSync(path.join(verzeichnis, 'style.css'), 'utf8'); } catch (_) {}
pruefe('hidden blendet die Spalten wirklich aus (.erzaehl-spalte[hidden] { display: none; })',
    /\.erzaehl-spalte\[hidden\]\s*\{\s*display:\s*none;?\s*\}/.test(css));
pruefe('Antippen versteckt am Handy die Liste und zeigt die Diashow',
    /listeSpalte\.hidden = window\.matchMedia/.test(src) && /diashowSpalte\.hidden = false/.test(src));

// Übersicht (Wunsch 06.10.2026): erst alle Bilder der Gruppe, Geschichte zur
// ganzen Gruppe; Antippen öffnet ein Bild einzeln mit eigener Geschichte.
eval(extractFn('erzaehlGeschichteKoerper'));
eval(extractFn('erzaehlGeschichtenJeBild'));

console.log('\n6) erzaehlGeschichteKoerper — Gruppe ohne Bild, Einzelbild mit Bild');
const gruppe = erzaehlGeschichteKoerper('ev-1', 'Alle zusammen am See', null);
pruefe('Übersicht: keine datei_kennung (gilt der ganzen Gruppe)', !('datei_kennung' in gruppe));
pruefe('Übersicht: undefined zählt wie null', !('datei_kennung' in erzaehlGeschichteKoerper('ev-1', 'x', undefined)));
pruefe('Übersicht: Ereignis, Text, Quelle stimmen',
    gruppe.ereignis_kennung === 'ev-1' && gruppe.text === 'Alle zusammen am See' && gruppe.quelle === 'tippen');
const einzeln = erzaehlGeschichteKoerper('ev-1', 'Papa und ich', 4711);
pruefe('Einzelbild: datei_kennung gesetzt', einzeln.datei_kennung === 4711);
pruefe('Einzelbild: Kennung 0 bleibt erhalten (kein falsy-Fehler)',
    erzaehlGeschichteKoerper('ev-1', 'x', 0).datei_kennung === 0);

console.log('\n7) erzaehlGeschichtenJeBild — ✎ auf den Kacheln');
const zahlen = erzaehlGeschichtenJeBild([
    { datei_kennung: 11, text: 'a' }, { datei_kennung: 11, text: 'b' },
    { datei_kennung: 12, text: 'c' }, { datei_kennung: null, text: 'Gruppe' },
    null, 'kaputt', { text: 'ohne Feld' },
]);
pruefe('zwei Geschichten an Bild 11', zahlen['11'] === 2);
pruefe('eine Geschichte an Bild 12', zahlen['12'] === 1);
pruefe('Gruppen-Geschichten und kaputte Einträge zählen nicht', Object.keys(zahlen).length === 2);
pruefe('keine Liste -> leeres Objekt (kein Wurf)', Object.keys(erzaehlGeschichtenJeBild(null)).length === 0);

console.log('\n8) Verdrahtung Übersicht / Einzelansicht');
pruefe('index.html hat Raster, Übersicht und Einzelansicht',
    /id="erzaehl-raster"/.test(html) && /id="erzaehl-uebersicht"/.test(html) && /id="erzaehl-einzel"[^>]*hidden/.test(html));
pruefe('index.html hat „← Alle Bilder" und den Platz für Gruppen-Geschichten',
    /id="erzaehl-zur-uebersicht"/.test(html) && /id="erzaehl-gruppen-geschichten"/.test(html));
pruefe('Öffnen eines Ereignisses zeigt zuerst die Übersicht',
    /rasterAufbauen\(\);\s*ansichtUmschalten\('uebersicht'\)/.test(src));
pruefe('Kachel-Antippen öffnet das Bild einzeln', /addEventListener\('click', \(\) => bildOeffnen\(i\)\)/.test(src));
pruefe('Speichern: Übersicht ohne Bild, Einzelansicht mit Bild',
    /zustand\.ansicht === 'einzel' \? aktuelleDateiKennung\(\) : null/.test(src));
pruefe('Kacheln laden erst beim Hineinscrollen (IntersectionObserver)', src.includes('new IntersectionObserver'));
pruefe('Kachel-URLs werden beim Verlassen freigegeben', /function rasterFreigeben[\s\S]*?revokeObjectURL/.test(src));
pruefe('in der Übersicht wird nicht geblättert', /function diashowSchritt\(richtung\) \{\s*if \(zustand\.ansicht !== 'einzel'\) return;/.test(src));
// Lehre aus dem Fehler oben: jede neue Regel mit display braucht ihr [hidden]-Gegenstück.
pruefe('CSS: [hidden] wirkt auf Übersicht, Einzelansicht und Zurück-Knöpfe',
    /\.erzaehl-uebersicht\[hidden\],\s*\.erzaehl-einzel\[hidden\],\s*\.erzaehl-back\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));

// Wer ist auf den Bildern (Wunsch 06.10.2026): Anzeige + 🔊.
eval(extractFn('_erzaehlAufzaehlen'));
eval(extractFn('_erzaehlOhneNamen'));
eval(extractFn('erzaehlPersonenUebersicht'));
eval(extractFn('erzaehlPersonenBild'));
eval(extractFn('erzaehlSprechtext'));
eval(extractFn('erzaehlAllesText'));

console.log('\n9) Personen-Zeilen — Übersicht, Einzelbild, Sprechtext');
pruefe('Übersicht: Namen mit Bildzahl, Unbenannte dahinter',
    erzaehlPersonenUebersicht({ benannt: [{ name: 'Testperson A', bilder: 12 }, { name: 'Testperson B', bilder: 1 }],
        ohne_namen: { personen: 3, bilder: 5 } })
    === 'Erkannt: Testperson A (12 Bilder), Testperson B (1 Bild) · 3 Personen noch ohne Namen');
pruefe('Übersicht: nur Unbenannte', erzaehlPersonenUebersicht({ benannt: [], ohne_namen: { personen: 1 } })
    === '1 Person noch ohne Namen');
pruefe('Übersicht: niemand erkannt', erzaehlPersonenUebersicht({ benannt: [], ohne_namen: { personen: 0 } })
    === 'Auf diesen Bildern wurde niemand erkannt.');
const viele = Array.from({ length: 11 }, (_, i) => ({ name: 'P' + i, bilder: 2 }));
pruefe('Übersicht: höchstens 8 Namen, Rest als „und N weitere"', /P7 \(2 Bilder\) und 3 weitere$/.test(erzaehlPersonenUebersicht({ benannt: viele })));
pruefe('Übersicht: ohne Daten -> leer (kein Wurf)',
    erzaehlPersonenUebersicht(null) === '' && erzaehlPersonenUebersicht({}) === '' && erzaehlPersonenUebersicht('x') === '');
pruefe('Bild: zwei Namen mit „und"', erzaehlPersonenBild({ namen: ['A', 'B'], ohne_namen: [] }) === 'Auf diesem Bild: A und B');
pruefe('Bild: drei Namen mit Komma und „und"', erzaehlPersonenBild({ namen: ['A', 'B', 'C'], ohne_namen: [] }) === 'Auf diesem Bild: A, B und C');
pruefe('Bild: Name plus Unbenannte', erzaehlPersonenBild({ namen: ['A'], ohne_namen: ['Person_1'] })
    === 'Auf diesem Bild: A · 1 Person noch ohne Namen');
pruefe('Bild: nur Unbenannte', erzaehlPersonenBild({ namen: [], ohne_namen: ['Person_1', 'Person_2'] })
    === 'Auf diesem Bild: 2 Personen noch ohne Namen');
pruefe('Bild: kein Eintrag -> niemand erkannt', erzaehlPersonenBild(undefined) === 'Auf diesem Bild wurde niemand erkannt.');
pruefe('Sprechtext: „·" wird Satzpause', erzaehlSprechtext('Auf diesem Bild: A · 1 Person noch ohne Namen')
    === 'Auf diesem Bild: A. 1 Person noch ohne Namen');
pruefe('Sprechtext: kein Text -> leer', erzaehlSprechtext(null) === '');

console.log('\n9b) Alles vorlesen — Tagebuch-Fassung des Eintrags (07.10.2026)');
pruefe('Titel, Bildzahl, Personen, Notiz in dieser Reihenfolge, je als Satz',
    erzaehlAllesText(['Festival 2022', '12 Bilder · Antippen öffnet ein Bild einzeln',
        'Auf diesem Bild: A und B', 'Das war ein schöner Abend'])
    === 'Festival 2022. 12 Bilder. Antippen öffnet ein Bild einzeln. '
        + 'Auf diesem Bild: A und B. Das war ein schöner Abend.');
pruefe('leere Teile fallen weg (keine Lücken, keine Punkte ohne Satz)',
    erzaehlAllesText(['', '   ', null, undefined, 'Nur eins']) === 'Nur eins.');
pruefe('doppelter Teil nur einmal (Personen stehen im Baum doppelt)',
    erzaehlAllesText(['A', 'A', 'B']) === 'A. B.');
pruefe('vorhandener Schlusspunkt wird nicht verdoppelt', erzaehlAllesText(['Schon fertig.']) === 'Schon fertig.');
pruefe('Fragezeichen bleibt', erzaehlAllesText(['Wie war das?']) === 'Wie war das?');
pruefe('kein Array -> leer (kein Wurf)', erzaehlAllesText(null) === '' && erzaehlAllesText('x') === '' && erzaehlAllesText(7) === '');
pruefe('Zahlen/Objekte in der Liste werden übergangen', erzaehlAllesText([42, {}, 'Text']) === 'Text.');

console.log('\n10) Verdrahtung Personen + Vorlesen');
pruefe('index.html: Personen-Zeilen in Übersicht und Einzelbild, versteckt bis Daten da sind',
    /id="erzaehl-personen"[^>]*hidden/.test(html) && /id="erzaehl-bild-personen"[^>]*hidden/.test(html));
pruefe('index.html: 🔊 in beiden Zeilen', /id="erzaehl-personen-vorlesen"/.test(html) && /id="erzaehl-bild-personen-vorlesen"/.test(html));
pruefe('lädt die Personen über die eigene Route', src.includes('/personen`') && src.includes('personenLaden(kennung)'));
pruefe('veraltete Personen-Antwort wird verworfen', /if \(zustand\.aktuellesEreignis !== kennung\) return;/.test(src));
pruefe('Vorlesen: zuerst Browser-Stimme, sonst /api/speak',
    /function vorlesen[\s\S]*?speechSynthesis[\s\S]*?\/api\/speak/.test(src));
pruefe('Vorlesen nur auf Tipp (kein Aufruf außer in den Knopf-Handlern)',
    (src.match(/vorlesen\('/g) || []).length === 4);
pruefe('index.html: Notizen-Kopf mit 🔊 in Übersicht und Einzelbild (versteckt)',
    /id="erzaehl-gruppen-geschichten-kopf"[^>]*hidden/.test(html)
    && /id="erzaehl-gruppen-geschichten-vorlesen"/.test(html)
    && /id="erzaehl-geschichten-kopf"[^>]*hidden/.test(html)
    && /id="erzaehl-geschichten-vorlesen"/.test(html));
pruefe('index.html: „alles vorlesen" in der Titelzeile', /id="erzaehl-alles-vorlesen"/.test(html));
pruefe('Notizen-Kopf erscheint nur, wenn Notizen da sind', /container\.childElementCount === 0/.test(src));
pruefe('Alles-Vorlesen nimmt nur die Notiztexte, nicht die Abschnitts-Köpfe',
    /erzaehl-geschichte-zeile > div:first-child/.test(src));
pruefe('CSS: [hidden] wirkt auf den Notizen-Kopf',
    /\.erzaehl-geschichten-kopf\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));
pruefe('Namen nur per textContent (kein innerHTML)', !/innerHTML/.test(src));
pruefe('CSS: [hidden] wirkt auf die Personen-Zeile', /\.erzaehl-personen\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));

// Eigener Titel (Wunsch 06.10.2026): ✏️ antippen und ändern; leer = automatischer Titel.
eval(extractFn('erzaehlTitelSaeubern'));

console.log('\n11) Eigener Titel');
pruefe('Leerraum wird zusammengezogen', erzaehlTitelSaeubern('  Festival \n 2022  mit   Freunden ') === 'Festival 2022 mit Freunden');
pruefe('höchstens 120 Zeichen', erzaehlTitelSaeubern('x'.repeat(200)).length === 120);
pruefe('leer/kein Text -> "" (= automatischer Titel)', erzaehlTitelSaeubern('   ') === '' && erzaehlTitelSaeubern(null) === '');
pruefe('index.html: Titelzeile mit ✏️ und Eingabe (versteckt)',
    /id="erzaehl-titel"/.test(html) && /id="erzaehl-titel-aendern"/.test(html) && /id="erzaehl-titel-bearbeiten"[^>]*hidden/.test(html));
pruefe('index.html: Speichern, Abbrechen, Zurücksetzen', /id="erzaehl-titel-speichern"/.test(html)
    && /id="erzaehl-titel-abbrechen"/.test(html) && /id="erzaehl-titel-zuruecksetzen"[^>]*hidden/.test(html));
pruefe('speichert über die Titel-Route', src.includes('/titel`') && /titelSpeichern\(''\)/.test(src));
pruefe('Enter speichert, Escape schließt zuerst das Titelfeld',
    /ev\.key === 'Enter'[\s\S]{0,80}titelSpeichern/.test(src) && /titelBlock && !titelBlock\.hidden\) titelBearbeitenSchliessen/.test(src));
pruefe('Pfeiltasten im Eingabefeld blättern nicht', /\^\(INPUT\|TEXTAREA\)\$/.test(src));
pruefe('Liste wird nach dem Speichern mitgezogen', /erzaehl-row-titel[\s\S]{0,80}daten\.titel/.test(src));
pruefe('CSS: [hidden] wirkt auf das Titelfeld', /\.erzaehl-titel-bearbeiten\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));

// Zwischen Anlässen blättern (#18, 07.10.2026): ◀ ▶, Pfeiltasten, Wischen, Android-Zurück.
eval(extractFn('_erzaehlZahl'));
eval(extractFn('erzaehlAnlassNav'));
eval(extractFn('erzaehlWischRichtung'));
eval(extractFn('erzaehlZurueckEntscheiden'));

console.log('\n12) Zwischen Anlässen blättern');
const navMitte = erzaehlAnlassNav(['a', 'b', 'c'], 'b', 2127);
pruefe('Mitte: voriger und nächster Anlass', navMitte.vor === 'a' && navMitte.weiter === 'c' && navMitte.index === 1);
pruefe('Zähler mit Tausenderpunkt', navMitte.text === 'Anlass 2 von 2.127', navMitte.text);
const navEnde = erzaehlAnlassNav(['a', 'b', 'c'], 'c', 2127);
pruefe('Ende der geladenen Liste, Server kennt mehr -> nachladen', navEnde.weiter === null && navEnde.mehrLaden === true);
const navLetzter = erzaehlAnlassNav(['a', 'b', 'c'], 'c', 3);
pruefe('wirklich letzter Anlass -> nichts mehr', navLetzter.weiter === null && navLetzter.mehrLaden === false);
pruefe('erster Anlass -> kein voriger', erzaehlAnlassNav(['a', 'b'], 'a', 2).vor === null);
pruefe('Anlass nicht in der Liste (Filter geändert) -> keine Nachbarn',
    erzaehlAnlassNav(['a'], 'x', 9).index === -1 && erzaehlAnlassNav(['a'], 'x', 9).weiter === null);
pruefe('kaputte Eingaben werfen nicht', erzaehlAnlassNav(null, null, 'x').text === '');
pruefe('gesamt kleiner als Liste -> Liste zählt', erzaehlAnlassNav(['a', 'b'], 'a', 0).text === 'Anlass 1 von 2');
pruefe('Zahl: 0, 999, 1000, 1234567', _erzaehlZahl(0) === '0' && _erzaehlZahl(999) === '999'
    && _erzaehlZahl(1000) === '1.000' && _erzaehlZahl(1234567) === '1.234.567');

pruefe('nach links wischen = vor', erzaehlWischRichtung(-120, 10) === 1);
pruefe('nach rechts wischen = zurück', erzaehlWischRichtung(120, -10) === -1);
pruefe('kurzer Wisch zählt nicht', erzaehlWischRichtung(-30, 0) === 0);
pruefe('schräges Scrollen blättert nicht', erzaehlWischRichtung(-80, 70) === 0);
pruefe('senkrechtes Scrollen blättert nicht', erzaehlWischRichtung(5, 300) === 0);
pruefe('kaputte Werte -> 0', erzaehlWischRichtung(undefined, null) === 0);

pruefe('Zurück aus dem Einzelbild landet auf dem Anlass', erzaehlZurueckEntscheiden('anlass', 'bild') === 'anwenden');
pruefe('Zurück aus dem Anlass landet auf der Liste', erzaehlZurueckEntscheiden('liste', 'anlass') === 'anwenden');
pruefe('Zurück aus der Liste schließt das Blatt', erzaehlZurueckEntscheiden('zu', 'liste') === 'anwenden');
pruefe('veralteter Eintrag (Blatt schon zu) -> noch ein Schritt', erzaehlZurueckEntscheiden('anlass', 'zu') === 'weiter');
pruefe('veralteter Eintrag gleicher Ebene -> noch ein Schritt', erzaehlZurueckEntscheiden('anlass', 'anlass') === 'weiter');
pruefe('Grundseite erreicht -> nichts (nie über die Seite hinaus)', erzaehlZurueckEntscheiden('zu', 'zu') === 'nichts');
pruefe('fremder Verlaufseintrag zählt als Grundseite', erzaehlZurueckEntscheiden('quatsch', 'zu') === 'nichts');

pruefe('index.html: Anlass-Leiste mit ◀ Zähler ▶', /id="erzaehl-anlass-nav"/.test(html)
    && /id="erzaehl-anlass-vor"/.test(html) && /id="erzaehl-anlass-zaehler"/.test(html) && /id="erzaehl-anlass-weiter"/.test(html));
pruefe('Pfeiltasten und Sprache blättern über blaettern()',
    /ev\.key === 'ArrowRight'\) \{ blaettern\(1\)/.test(src) && /befehl === 'weiter'\) \{ blaettern\(1\)/.test(src));
pruefe('blaettern: Einzelansicht = Bild, Übersicht = Anlass',
    /function blaettern\(richtung\) \{\s*if \(zustand\.ansicht === 'einzel'\) diashowSchritt\(richtung\);\s*else anlassSchritt\(richtung\);/.test(src));
pruefe('Wischen über die ganze Spalte, Abbruch wird beachtet',
    /wischFlaeche = el\('erzaehl-diashow-spalte'\)/.test(src) && /'touchcancel', wischAbbruch/.test(src));
pruefe('am Ende der geladenen Liste wird erst nachgeladen', /nav\.mehrLaden\) \{\s*await ereignislisteLaden\(true\)/.test(src));
pruefe('Ebenen legen Verlaufseinträge an (Liste, Anlass, Bild)',
    /verlaufRein\('liste'\)/.test(src) && /if \(vonListe\) verlaufRein\('anlass'\)/.test(src) && /verlaufRein\('bild'\)/.test(src));
pruefe('Zurück-Geste läuft über popstate', /addEventListener\('popstate', verlaufZurueck\)/.test(src));
pruefe('Knöpfe gehen über den Verlauf eine Ebene hoch',
    /zurueckBtn\.addEventListener\('click', ebeneHoch\)/.test(src) && /zurUebersichtBtn\.addEventListener\('click', ebeneHoch\)/.test(src));
pruefe('✕ baut die eigenen Einträge ab', /schliessenBtn\.addEventListener\('click', sheetSchliessenMitVerlauf\)/.test(src)
    && /history\.go\(-rang\)/.test(src));
pruefe('Entwurf je Anlass: vor dem Wechsel sichern, danach holen',
    /entwurfSichern\(\);[^\n]*\n\s*zustand\.aktuellesEreignis = kennung;/.test(src) && /entwurfHolen\(kennung\)/.test(src));
pruefe('Speichern nach Weiterwischen schreibt nicht ins neue Feld',
    /if \(zustand\.aktuellesEreignis !== kennung\) \{[\s\S]{0,200}entwurfJeAnlass\.delete\(kennung\)/.test(src));
pruefe('spätes Diktat landet im Entwurf des richtigen Anlasses', /entwurfAnhaengen\(kennungVorher, ansichtVorher, text\)/.test(src));
pruefe('offener Anlass ist in der Liste markiert', /classList\.toggle\('aktiv', an\)/.test(src));
pruefe('CSS: [hidden] wirkt auf die Anlass-Leiste', /\.erzaehl-anlass-nav\[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));
pruefe('CSS: senkrechtes Scrollen bleibt beim Wischen', /\.erzaehl-diashow-spalte\s*\{\s*touch-action:\s*pan-y pinch-zoom;\s*\}/.test(css));
pruefe('CSS: Animation entfällt bei „weniger Bewegung"', /prefers-reduced-motion: reduce\)[\s\S]{0,160}animation: none/.test(css));
pruefe('index.html lädt erzaehlen.js mit ?v=20261007C', /erzaehlen\.js\?v=20261007C/.test(html));

// Was und wo (07.10.2026): Ort und Beschreibung je Bild, Orte der Gruppe.
eval(extractFn('erzaehlOrtText'));
eval(extractFn('erzaehlOrteUebersicht'));

console.log('\n13) Was und wo');
pruefe('Landmarke und Ort', erzaehlOrtText({ landmarke: 'Gasthaus am See', art: 'restaurant', ort: 'Testdorf' }) === 'Gasthaus am See, Testdorf');
pruefe('nur Ort', erzaehlOrtText({ landmarke: null, ort: 'Testdorf' }) === 'Testdorf');
pruefe('gleicher Name nur einmal', erzaehlOrtText({ landmarke: 'Testdorf', ort: 'testdorf' }) === 'Testdorf');
pruefe('Flug', erzaehlOrtText({ art: 'flug', landmarke: 'x' }) === 'Während des Flugs');
pruefe('nichts -> leer', erzaehlOrtText(null) === '' && erzaehlOrtText({}) === '');
pruefe('Orte der Gruppe', erzaehlOrteUebersicht({ orte: ['A', 'B', 'C'] }) === 'Orte: A, B und C');
pruefe('keine Orte -> leer', erzaehlOrteUebersicht({ orte: [] }) === '' && erzaehlOrteUebersicht(null) === '');
pruefe('lädt über die eigene Route, veraltete Antwort wird verworfen',
    src.includes('/bilder-info`') && /bilderInfoLaden\(kennung\)/.test(src)
    && /async function bilderInfoLaden[\s\S]{0,400}if \(zustand\.aktuellesEreignis !== kennung\) return;/.test(src));
pruefe('Anzeige bei jedem Ansichts- und Bildwechsel', (src.match(/bildInfoAnzeigen\(\);/g) || []).length >= 4);
pruefe('index.html: Orte-Zeile und Bild-Info (versteckt)',
    /id="erzaehl-orte"[^>]*hidden/.test(html) && /id="erzaehl-bild-info"[^>]*hidden/.test(html)
    && /id="erzaehl-bild-ort"[^>]*hidden/.test(html) && /id="erzaehl-bild-beschreibung"[^>]*hidden/.test(html));
pruefe('Alles vorlesen liest Orte bzw. Ort und Beschreibung mit',
    /imRaster \? \['erzaehl-orte-text'\] : \['erzaehl-bild-ort-text', 'erzaehl-bild-beschreibung'\]/.test(src));
pruefe('CSS: [hidden] wirkt auf den Info-Block und seine Zeilen',
    /\.erzaehl-info\[hidden\],\s*\.erzaehl-info > \[hidden\]\s*\{\s*display:\s*none;\s*\}/.test(css));

console.log(fehler ? `\n${fehler} FEHLER` : '\nAlle Prüfungen bestanden.');
process.exit(fehler ? 1 : 0);
