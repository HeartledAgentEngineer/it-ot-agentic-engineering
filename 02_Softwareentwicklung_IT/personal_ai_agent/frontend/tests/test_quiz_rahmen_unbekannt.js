// SCHRITT E (18.10.2026) — Rahmen von Hand aufziehen; der Rahmen startet als
// "unbekannt" (Plan "Rahmeneditor im Detailbild", Fassung 13, Abschnitt 4,
//  Schritt E, Auftragspunkt 2b) und der belegte Verwerf-Pfad ist an den Test
//  gebunden.
//
// Pruefkriterium (Plan, Fassung 13): "Test, dass ein manuell gezogener Rahmen
// ohne Vektor gespeichert und als 'unbekannt' angezeigt wird." Auflage 10 der
// Fassung-2-Pruefung verlangt zusaetzlich, dass der Pfad, der einen manuell
// gezogenen Rahmen verwerfen koennte, ERST BELEGT und DANN an den Test gebunden
// wird - der Beleg steht in
// docs/changelog-2026-10-18-handrahmen-verwerfpfade.md:
//   Pfad 1  `frontend/app.js`, `baueBildEditor`: die Rahmenliste wurde
//           AUSSCHLIESSLICH ueber die Serverliste gebaut -> alles ab
//           `gesichter.length` fiel beim naechsten Oeffnen weg.
//   Pfad 2  `backend/app/services/gesicht_quiz.py:392`: Bestaetigungen halten
//           nur die letzten 500 Bilder -> ein unbekannter Rahmen haengt deshalb
//           am lokalen Browserspeicher, nicht am Server-Fortschritt.
// Daraus die Abschnitte dieses Tests:
//   A) Anzeigetext + Markierung ("unbekannt" statt erfundener Person)
//   B) Anhaengen eines gezogenen Rahmens (keine Person, kein Sendeversuch)
//   C) Pfad 1: der Rahmen ueberlebt das erneute Oeffnen DESSELBEN Bildes
//      (+ Gegenprobe mit der alten Regel, damit der Test nicht leer-gruen ist)
//   D) Pfad 2: der lokale Speicher haelt ihn, unabhaengig vom Server-Fenster
//      (und: gesperrter Browserspeicher stuerzt NICHT ab, sondern meldet ehrlich)
//   E) der Speicher-Riegel: ein unbekannter Rahmen wird NICHT als globale
//      Zielperson gespeichert (sonst falsche Zuordnung)
//   F) Verdrahtung im Quelltext (Knopf, Zeichenfeld, Cache-Schluessel)
//
// Aufruf: node tests/test_quiz_rahmen_unbekannt.js app.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2], 'utf8');
const html = fs.readFileSync(path.join(path.dirname(process.argv[2]), 'index.html'), 'utf8');

function funktionAusschneiden(quelle, name) {
    const treffer = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(').exec(quelle);
    if (!treffer) throw new Error('Funktion nicht gefunden: ' + name);
    const start = treffer.index;
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

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'bboxRegionSchluessel', 'bboxNormClampen',
               'bboxPixelVonNorm', 'rahmenPersonText', 'rahmenUnbekannt',
               'unbekannteRahmenLaden', 'unbekannteRahmenSchreiben',
               'unbekannteRahmenMerken', 'unbekannteRahmenVergessen',
               'rahmenListeVerschmelzen', 'rahmenUnbekanntAnhaengen',
               'rahmenIndizes', 'rahmenPersonWahl', 'editorSpeicherZiel', 'speichereEditorRahmen'];
const quelle = NAMEN.map((n) => funktionAusschneiden(src, n)).join('\n');

// Sandkasten: die echten Funktionen laufen gegen Attrappen der Nachbarn.
// `sperre` = Browserspeicher gesperrt (localStorage wirft) — der ehrliche Fall.
function baueSandkasten(sperre) {
    const koerper = `
        let _aktuelleQuizPerson = '', _aktuellerQuizPfad = '', _quizEditor = null;
        let _letzteQuizKarte = null, _quizVollbild = null;
        let sends = 0, fetchs = 0, meldungen = [], bestaetigt = [];
        const speicher = {};
        const localStorage = {
            getItem: (k) => { if (${sperre ? 'true' : 'false'}) throw new Error('Speicher gesperrt');
                              return Object.prototype.hasOwnProperty.call(speicher, k) ? speicher[k] : null; },
            setItem: (k, v) => { if (${sperre ? 'true' : 'false'}) throw new Error('Speicher gesperrt');
                                 speicher[k] = String(v); },
            removeItem: (k) => { delete speicher[k]; },
        };
        const API_BASE = '';
        function merkeBestaetigt(p, r, per) { bestaetigt.push([p, r, per]); }
        function macheQuizFertig() {}
        function quizBeantwortenSilent() {
            sends++;
            return Promise.resolve({ ok: true, referenz_geschrieben: true,
                                     rahmen_gespeichert: 'gesendet' });
        }
        function fetch() {
            fetchs++;
            return Promise.resolve({ json: () => Promise.resolve({ ok: true, vektor_erneuert: true }) });
        }
        ${quelle}
        return {
            // Ein Editor wie ihn baueBildEditor hinterlaesst (ohne DOM).
            setze: (rahmen, personen, person, pfad) => {
                _aktuelleQuizPerson = person;
                _aktuellerQuizPfad = pfad;
                _quizEditor = { bbox_norm_live: rahmen, personen: personen || [],
                                melde: (t) => { meldungen.push(t); },
                                bildPfad: pfad, refKontext: null, dreh: 0, px_rest: [] };
                return _quizEditor;
            },
            editor: () => _quizEditor,
            personText: (p) => rahmenPersonText(p),
            unbekannt: (p) => rahmenUnbekannt(p),
            anhaengen: (pfad, norm) => rahmenUnbekanntAnhaengen(_quizEditor, pfad, norm),
            verschmelzen: (ges, vor) => rahmenListeVerschmelzen(ges, vor),
            merken: (pfad, norm) => unbekannteRahmenMerken(pfad, norm),
            laden: (pfad) => unbekannteRahmenLaden(pfad),
            vergessen: (pfad, norm) => unbekannteRahmenVergessen(pfad, norm),
            schreiben: (pfad, liste) => unbekannteRahmenSchreiben(pfad, liste),
            roh: () => JSON.parse(JSON.stringify(_quizEditor.bbox_norm_live || [])),
            personen: () => (_quizEditor.personen || []).slice(),
            einRahmen: (idx) => speichereEditorRahmen(idx, 800, 600, null),
            meldungen: () => meldungen,
            zaehler: () => ({ sends: sends, fetchs: fetchs }),
            bestaetigt: () => bestaetigt,
            speicherInhalt: () => JSON.stringify(speicher),
        };
    `;
    return new Function(koerper)();
}

const ZWEI_SERVER = [{ bbox_norm: [0.10, 0.10, 0.20, 0.20] }, { bbox_norm: [0.30, 0.30, 0.20, 0.20] }];
const OHNE_NORM = [{ bbox: [80, 60, 160, 120] }];      // nur Pixel -> Rest-Weg
const UNBEKANNT = [0.55, 0.15, 0.18, 0.22];            // von Hand gezogen

(async () => {
    console.log('\nA) Anzeigetext: ohne Person heisst der Rahmen "unbekannt"');
    {
        const s = baueSandkasten(false);
        pruefe(s.personText('') === 'unbekannt', 'leere Person -> "unbekannt"');
        pruefe(s.personText(null) === 'unbekannt', 'fehlende Person -> "unbekannt"');
        pruefe(s.personText('Anna') === 'Anna', 'echte Person bleibt ihr Name');
        pruefe(s.unbekannt('') === true, 'leerer String ist AUSDRUECKLICH unbekannt');
        pruefe(s.unbekannt(undefined) === false, 'undefined ist KEINE Aussage (Server-Rahmen ohne Person)');
    }

    console.log('\nB) Ein gezogener Rahmen wird angehaengt — ohne Person, ohne Sendeversuch');
    {
        const s = baueSandkasten(false);
        s.setze([ZWEI_SERVER[0].bbox_norm.slice(), ZWEI_SERVER[1].bbox_norm.slice()], [], 'Anna', '/bilder/A.jpg');
        const idx = s.anhaengen('/bilder/A.jpg', UNBEKANNT);
        pruefe(idx === 2, 'der neue Rahmen sitzt HINTER der Serverliste (Index 2)');
        pruefe(JSON.stringify(s.roh()[2]) === JSON.stringify(UNBEKANNT), 'er traegt die gezeichnete Region');
        pruefe(s.personen()[2] === '', 'er ist ausdruecklich als "unbekannt" markiert');
        pruefe(s.zaehler().sends === 0 && s.zaehler().fetchs === 0,
               'kein Server-Schreibvorgang (ohne Person gibt es keine Referenz und keinen Vektor)');
        pruefe(s.bestaetigt().length === 0, 'er wird NICHT als bestaetigt gemerkt');
    }

    console.log('\nC) Pfad 1: der Rahmen ueberlebt das erneute Oeffnen DESSELBEN Bildes');
    {
        const s = baueSandkasten(false);
        // Stand beim ersten Oeffnen: 2 Server-Rahmen + 1 gezogener (Index 2),
        // Rahmen 0 wurde verschoben (live-Aenderung), Rahmen 1 geloescht.
        const liveAend = [0.12, 0.12, 0.20, 0.20];
        const vor = [liveAend.slice(), null, UNBEKANNT.slice()];
        const gemischt = s.verschmelzen(ZWEI_SERVER, vor);
        pruefe(gemischt.neu.length === 3, 'beim Wieder-Oeffnen bleiben 3 Rahmen (vorher: 2 = Serverlaenge)');
        pruefe(JSON.stringify(gemischt.neu[0]) === JSON.stringify(liveAend), 'die Live-Aenderung gewinnt');
        pruefe(gemischt.neu[1] === null, 'geloescht bleibt geloescht');
        pruefe(JSON.stringify(gemischt.neu[2]) === JSON.stringify(UNBEKANNT),
               'der von Hand gezogene Rahmen ist noch da');
        // Gegenprobe: die ALTE Regel (nur ueber die Serverliste) hat ihn verloren.
        const alt = [];
        for (let i = 0; i < ZWEI_SERVER.length; i++) alt.push(gemischt.neu[i]);
        pruefe(alt.length === 2 && alt.indexOf(UNBEKANNT) < 0,
               'Gegenprobe alte Fassung: der gezogene Rahmen faellt weg (Test waere sonst leer-gruen)');
        // Bildwechsel: der Aufrufer uebergibt dann eine LEERE Vorlage.
        const anderes = s.verschmelzen(ZWEI_SERVER, []);
        pruefe(anderes.neu.length === 2, 'bei einem ANDEREN Bild wird nichts faelschlich mitgenommen');
        // Pixel-Rest bleibt erhalten (Rahmen ohne bbox_norm).
        const rest = s.verschmelzen(OHNE_NORM, []);
        pruefe(JSON.stringify(rest.rest[0]) === '[80,60,160,120]' && rest.neu[0] === null,
               'Rahmen mit nur Pixel-bbox kommen weiter als Rest zurueck');
        pruefe(rest.rest.length === rest.neu.length, 'Rahmen- und Rest-Liste bleiben gleich lang');
    }

    console.log('\nD) Pfad 2: der lokale Speicher haelt ihn — auch mit gesperrtem Browserspeicher ehrlich');
    {
        const s = baueSandkasten(false);
        s.setze([], [], 'Anna', '/bilder/A.jpg');
        s.anhaengen('/bilder/A.jpg', UNBEKANNT);
        pruefe(s.laden('/bilder/A.jpg').length === 1, 'der Rahmen steht im lokalen Speicher');
        pruefe(s.laden('/bilder/B.jpg').length === 0, 'und NUR fuer dieses Bild');
        pruefe(s.merken('/bilder/A.jpg', UNBEKANNT) === true
               && s.laden('/bilder/A.jpg').length === 1, 'dieselbe Region wird nicht doppelt gemerkt (idempotent)');
        s.merken('/bilder/A.jpg', [0.80, 0.80, 0.10, 0.10]);
        pruefe(s.laden('/bilder/A.jpg').length === 2, 'eine zweite Region kommt dazu');
        s.vergessen('/bilder/A.jpg', UNBEKANNT);
        const uebrig = s.laden('/bilder/A.jpg');
        pruefe(uebrig.length === 1 && Math.round(uebrig[0][0] * 100) === 80,
               'Vergessen nimmt GENAU die eine Region (Loeschen im Editor)');
        pruefe(s.laden('')  .length === 0, 'ohne Bildpfad wird nichts gelesen');
        pruefe(s.merken('', UNBEKANNT) === false, 'ohne Bildpfad wird nichts geschrieben');

        const gesperrt = baueSandkasten(true);
        gesperrt.setze([], [], 'Anna', '/bilder/A.jpg');
        let abgestuerzt = false;
        try { gesperrt.anhaengen('/bilder/A.jpg', UNBEKANNT); } catch (_e) { abgestuerzt = true; }
        pruefe(!abgestuerzt, 'gesperrter Browserspeicher stuerzt NICHT ab');
        pruefe(gesperrt.roh().length === 1, 'der Rahmen steht trotzdem im Editor (nur nicht dauerhaft)');
        pruefe(gesperrt.laden('/bilder/A.jpg').length === 0, 'und der Speicher meldet ehrlich: nichts gemerkt');
    }

    console.log('\nE) Speicher-Riegel: "unbekannt" wird NICHT als globale Zielperson gesendet');
    {
        const s = baueSandkasten(false);
        s.setze([ZWEI_SERVER[0].bbox_norm.slice(), UNBEKANNT.slice()], [undefined, ''], 'Anna', '/bilder/A.jpg');
        const r = await s.einRahmen(1);
        pruefe(s.zaehler().sends === 0, 'kein Sendeversuch fuer den unbekannten Rahmen');
        pruefe(r.ok === false && r.grund === 'unbekannt', 'Ergebnis: nicht gespeichert, Grund "unbekannt"');
        pruefe(s.meldungen().some((t) => /unbekannt — keine Person zugeordnet/.test(t)),
               'die Meldung nennt den ehrlichen Grund');
        // Gegenprobe: ein normaler Server-Rahmen (keine Aussage) wird weiter gespeichert.
        const s2 = baueSandkasten(false);
        s2.setze([ZWEI_SERVER[0].bbox_norm.slice(), ZWEI_SERVER[1].bbox_norm.slice()], [], 'Anna', '/bilder/A.jpg');
        const r2 = await s2.einRahmen(0);
        pruefe(s2.zaehler().sends === 1 && r2.ok === true,
               'Gegenprobe: ein Rahmen ohne "unbekannt"-Markierung wird ganz normal gespeichert');
    }

    console.log('\nF) Verdrahtung im Quelltext (Knopf, Zeichenfeld, Cache-Schluessel)');
    {
        pruefe(/rahmenBtn\.textContent = '＋ Rahmen'/.test(src), 'der Editor hat den Knopf "＋ Rahmen"');
        pruefe(/rahmenBtn\.addEventListener\('click'/.test(src)
               && /rahmenZeichnenStarten\(\);/.test(src), 'der Knopf startet das Zeichenfeld');
        pruefe(/function rahmenZeichnenStarten\(\)/.test(src), 'das Zeichenfeld ist als Funktion vorhanden');
        pruefe(/rahmenAusZeichenfeld\(x, y, w, h\)/.test(src), 'das gezeichnete Rechteck wird uebernommen');
        pruefe(/zeichenFeld\.addEventListener\('pointerup', fertigMit\)/.test(src)
               && /zeichenFeld\.addEventListener\('pointercancel', fertigMit\)/.test(src),
               'Abbruch (pointercancel) wird wie Loslassen behandelt');
        // Pfad 1 ist WIRKLICH gebunden: der Editor baut die Elemente nicht mehr
        // ueber die Serverlaenge, sondern ueber die verschmolzene Liste.
        pruefe(/for \(var i = 0; i < \(\(_quizEditor\.bbox_norm_live \|\| \[\]\)\.length\); i\+\+\)/.test(src),
               'die Rahmen-Elemente entstehen ueber ALLE Rahmen (nicht nur die Server-Rahmen)');
        pruefe(!/for \(var i = 0; i < gesichter\.length; i\+\+\) \{\s*var re = document\.createElement/.test(src),
               'die alte, auf die Serverliste begrenzte Schleife ist weg');
        pruefe(/const gemischt = rahmenListeVerschmelzen\(gesichter, vorNorm\);/.test(src),
               'der Editor nutzt die pruefbare Verschmelzung');
        pruefe(/hinter der Serverliste|HINTER der Serverliste/.test(src),
               'der Grund steht als Kommentar am Code');
        pruefe(/unbekannt — keine Person zugeordnet, deshalb nichts gespeichert/.test(src),
               'der Speicher-Riegel ist im Speicherweg verdrahtet');
        // Die Referenz-Nachbearbeitung bleibt sauber: dort gilt "genau DIESE
        // Referenz" — gemerkte fremde Rahmen werden dort NICHT angehaengt.
        pruefe(/if \(!_quizEditor\.refKontext\) \{/.test(src)
               && /if \(!_quizEditor\.refKontext\) \{[\s\S]{0,200}const unbekanntPfad/.test(src),
               'in der Referenz-Nachbearbeitung werden keine fremden Rahmen angehaengt');
        // Schritt G (18.10.2026): die Nummer als Muster + Mindeststand pruefen —
        // ein fest verdrahteter Buchstabe wurde bei jedem legitimen Bump rot.
        const vApp = (html.match(/app\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
        pruefe(/^\d{8}[A-Z]$/.test(vApp) && vApp >= '20261018I',
               'der Cache-Schluessel in index.html ist hochgezogen (mindestens 20261018I), gefunden: ' + vApp);
    }

    console.log('');
    if (fehler) { console.log('FEHLGESCHLAGEN: ' + fehler + ' Pruefung(en) rot.'); process.exit(1); }
    console.log('Alle Pruefungen bestanden.');
})();
