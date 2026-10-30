// BILD-EDITOR B4 (27.10.2026) — Editor Cloud-Weg + Einstieg Gruppen-Quiz.
//
// Plan: .hermes/plans/2026-10-25_bild-editor-ueberall.md, Abschnitt "Editor (Frontend)".
// Der Editor (zeigeBildVollbild) bekommt einen neuen Speicherweg `weg: 'cloud'`, sobald
// `{fileid}` mitgegeben wird: 💾 schickt ALLE Aenderungen gesammelt an
// POST /api/gruppen/bild-rahmen, "Neu erkennen" ruft POST /api/gruppen/bild-erkennen,
// das Gruppen-Quiz (Fotoansicht + Gesamtansicht) oeffnet den Editor mit fileid und den
// Gesichtern aus GET /api/gruppen/bild-gesichter.
//
// Wie die uebrigen Editor-Tests: die ECHTEN Funktionen werden aus app.js ausgeschnitten
// und gegen Attrappen ausgefuehrt (Zaehler statt Behauptungen); die Verdrahtung im
// Quelltext und in index.html prueft ein Waechter (zeilenende-tolerant: CRLF oder LF).
// Das Gruppen-Quiz laeuft in einer kleinen DOM-Umgebung (vm), nur HTTP ist Attrappe.
// Kein Netz, keine Nutzerdaten, erfundene fileids und Namen.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_bild_editor_b4.js app.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const appPfad = path.resolve(process.argv[2] || path.join(__dirname, '..', 'app.js'));
const verz = path.dirname(appPfad);
const src = fs.readFileSync(appPfad, 'utf8');
const gqPfad = path.join(verz, 'gruppen_quiz.js');
const gqSrc = fs.readFileSync(gqPfad, 'utf8');
const html = fs.readFileSync(path.join(verz, 'index.html'), 'utf8');

let fehler = 0;
let zaehler = 0;
function pruefe(bed, text, detail) {
    zaehler++;
    if (bed) { console.log('  OK   ' + text); }
    else { fehler++; console.log('  FEHL ' + text + (detail !== undefined ? '  -> ' + detail : '')); }
}
function gleich(a, b) { return JSON.stringify(a) === JSON.stringify(b); }
const j = (x) => JSON.stringify(x);

/** Ein Testfall: ein Wurf (z. B. fehlende Funktion) zaehlt als roter Fall, nicht als Abbruch. */
async function fall(name, fn) {
    console.log('\n' + name);
    try { await fn(); } catch (e) {
        fehler++; zaehler++;
        console.log('  FEHL Ausnahme: ' + (e && e.message ? e.message : e));
    }
}

// ── Funktionen aus app.js ausschneiden ──────────────────────────────────────
function funktionAusschneiden(quelle, name) {
    const start = quelle.indexOf('function ' + name + '(');
    if (start === -1) throw new Error('Funktion nicht gefunden: ' + name);
    const davor = quelle.slice(Math.max(0, start - 6), start) === 'async ' ? start - 6 : start;
    let tiefe = 0;
    for (let i = quelle.indexOf('{', start); i < quelle.length; i++) {
        if (quelle[i] === '{') tiefe++;
        else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(davor, i + 1);
    }
    throw new Error('Funktionsende nicht gefunden: ' + name);
}

const NAMEN = ['pfadKennung', 'dateiAnzeigeName', 'rahmenPersonWahl', 'editorSpeicherZiel', 'rahmenIndizes',
    'rahmenPersonSetzen', 'rahmenPersonMenueListe', 'bboxNormClampen', 'bboxUeberdeckung',
    'cloudFileidGueltig', 'cloudBboxFuerServer', 'cloudStartAuswahl', 'bildEditorCloudZustand',
    'bildEditorCloudAenderungen', 'bildEditorCloudMeldung', 'cloudGesichterLaden', 'speichereBildCloud',
    'cloudErkennenAbrufen', 'bildEditorCloudErkennung', 'bildEditorCloudVorschlagUebernehmen',
    'cloudVorschlagElement', 'cloudPersonenNamen', 'ladeCloudPersonenNamen', 'cloudNeuePersonOptionText',
    'cloudNameHinweis'];

/** Fehlende Funktionen werden zu Attrappen, die beim Aufruf werfen — jeder Fall wird einzeln rot. */
function quelleBauen() {
    return NAMEN.map((n) => {
        try { return funktionAusschneiden(src, n); } catch (_e) {
            return 'function ' + n + '() { throw new Error("Funktion fehlt in app.js: ' + n + '"); }';
        }
    }).join('\n');
}
const QUELLE = quelleBauen();

/** Attrappe fuer ein DOM-Element: genug fuer cloudVorschlagElement; innerHTML ist verboten. */
class FakeEl {
    constructor(tag) {
        this.tag = tag; this.style = {}; this.children = []; this.dataset = {}; this.attributes = {};
        this.listeners = {}; this.className = ''; this._text = '';
    }
    set textContent(v) { this._text = String(v); this.children = []; }
    get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
    set innerHTML(_v) { throw new Error('innerHTML darf mit Daten nicht benutzt werden'); }
    setAttribute(k, v) { this.attributes[k] = String(v); }
    appendChild(c) { this.children.push(c); return c; }
    addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
    click() { (this.listeners.click || []).forEach((fn) => fn({ stopPropagation() {}, preventDefault() {} })); }
}

/** Sandkasten: die echten Funktionen gegen eine Netz-Attrappe. `antworten`: Funktion (url, options) -> Antwort. */
function baue(antworten) {
    const aufrufe = [];
    const fetchAttrappe = (url, options) => {
        aufrufe.push({ url: String(url), options: options || {}, methode: ((options && options.method) || 'GET').toUpperCase() });
        const a = antworten ? antworten(String(url), options || {}) : undefined;
        if (a instanceof Error) return Promise.reject(a);
        const roh = a === undefined ? { ok: true } : a;
        const status = (roh && roh.__status) || 200;
        return Promise.resolve({ ok: status < 400, status: status, json: () => Promise.resolve(roh) });
    };
    const dokument = { createElement: (t) => new FakeEl(t) };
    const timer = [];
    const koerper = `
        let _quizEditor = null, _aktuelleQuizPerson = '', _aktuellerQuizPfad = '';
        let _cloudPersonenNamen = null, _cloudPersonenZeit = 0;
        const API_BASE = '';
        ${QUELLE}
        return {
            ziel: (e, i) => editorSpeicherZiel(e, i),
            setzePerson: (p, pfad) => { _aktuelleQuizPerson = p; _aktuellerQuizPfad = pfad; },
            zustand: (e, g, m) => bildEditorCloudZustand(e, g, m),
            aenderungen: (e) => bildEditorCloudAenderungen(e),
            meldung: (a, n) => bildEditorCloudMeldung(a, n),
            speichern: (e, btn) => { _quizEditor = e; return speichereBildCloud(btn); },
            abrufen: (f) => cloudErkennenAbrufen(f),
            erkennung: (e, a) => bildEditorCloudErkennung(e, a),
            uebernehmen: (e, i) => bildEditorCloudVorschlagUebernehmen(e, i),
            element: (v, fn) => cloudVorschlagElement(v, fn),
            namen: (e, i) => cloudPersonenNamen(e, i),
            ladeNamen: () => ladeCloudPersonenNamen(),
            optionText: () => cloudNeuePersonOptionText(),
            hinweis: (e, n) => cloudNameHinweis(e, n),
            gueltig: (f) => cloudFileidGueltig(f),
            bboxServer: (n) => cloudBboxFuerServer(n),
            auswahl: (g, m) => cloudStartAuswahl(g, m),
            laden: (f) => cloudGesichterLaden(f),
        };
    `;
    const api = new Function('fetch', 'document', 'setTimeout', koerper)(
        fetchAttrappe, dokument, (fn, ms) => { timer.push([fn, ms]); return timer.length; });
    api.aufrufe = aufrufe;
    api.timer = timer;
    return api;
}

// Erfundene Gesichter eines erfundenen Bildes 111 (bild-gesichter, Form wie im Backend).
function gesichtServer(index, bbox, name, extra) {
    return Object.assign({ gid: '111:' + index, index: index, kennung: 'Person_90' + index, name: name || null,
        bbox_norm: bbox, bbox: [bbox[0] * 800, bbox[1] * 600, bbox[2] * 800, bbox[3] * 600], breite: 800, hoehe: 600,
        name_quelle: name ? 'gruppe' : null, quelle: 'erkennung' }, extra || {});
}
const A = [0.10, 0.10, 0.20, 0.20];
const B = [0.40, 0.10, 0.20, 0.20];
const C = [0.70, 0.10, 0.20, 0.20];
const D = [0.10, 0.50, 0.20, 0.20];
const E = [0.40, 0.50, 0.20, 0.20];
function fuenf() {
    return [gesichtServer(0, A), gesichtServer(1, B, 'Person B'), gesichtServer(2, C),
        gesichtServer(3, D), gesichtServer(4, E, 'Person E')];
}

// ════════════════════════════════════════════════════════════════════════════
(async () => {

await fall('K1) editorSpeicherZiel: mit fileid weg "cloud", ohne fileid unveraendert quiz/referenz', async () => {
    const s = baue();
    const mit = s.ziel({ fileid: '111', bbox_norm_live: [A], personen: [] }, 0);
    pruefe(mit.ok === true && mit.weg === 'cloud', 'gueltige fileid -> {ok:true, weg:"cloud"}', j(mit));
    pruefe(mit.fileid === '111', 'das Ziel nennt die fileid', j(mit));
    const zahl = s.ziel({ fileid: 111, bbox_norm_live: [A], personen: [] }, 0);
    pruefe(zahl.ok === true && zahl.weg === 'cloud' && zahl.fileid === '111', 'auch eine Zahl als fileid zaehlt', j(zahl));
    const schlecht = s.ziel({ fileid: '12#t=3', bbox_norm_live: [A], personen: [] }, 0);
    pruefe(schlecht.ok === false && /Bildkennung/.test(schlecht.grund), 'ungueltige fileid -> kein Ziel mit ehrlichem Grund', j(schlecht));
    pruefe(s.gueltig('4711') && s.gueltig(4711) && !s.gueltig('') && !s.gueltig('abc') && !s.gueltig('1:2') && !s.gueltig(null),
        'cloudFileidGueltig: nur Ziffern');

    // ohne fileid bleibt alles wie vorher
    s.setzePerson('Anna', '/bilder/A.jpg');
    const quiz = s.ziel({ bbox_norm_live: [A], personen: [], bildPfad: '/bilder/A.jpg' }, 0);
    pruefe(quiz.ok === true && quiz.weg === 'quiz' && quiz.person === 'Anna', 'ohne fileid: Quiz-Weg unveraendert', j(quiz));
    s.setzePerson('', '');
    const ohne = s.ziel({ bbox_norm_live: [A], personen: [], bildPfad: '' }, 0);
    pruefe(ohne.ok === false && ohne.weg === 'quiz', 'ohne fileid und ohne Ziel: weiter "Kein Speicherziel"', j(ohne));
    const ref = s.ziel({ bbox_norm_live: [A], personen: [], refKontext: { name: 'Anna', ref_id: 'r1' } }, 0);
    pruefe(ref.ok === true && ref.weg === 'referenz', 'Referenz-Weg unveraendert', j(ref));
    const refVorn = s.ziel({ fileid: '111', refKontext: { name: 'Anna', ref_id: 'r1' } }, 0);
    pruefe(refVorn.weg === 'referenz', 'die Referenz-Nachbearbeitung geht der fileid vor', j(refVorn));
});

await fall('K2) Verdrahtung: 💾 nur mit gueltigem Ziel, ohne fileid keine Cloud-Bearbeitungsknoepfe', async () => {
    const zeigen = funktionAusschneiden(src, 'zeigeBildVollbild');
    pruefe(/_quizEditor\.fileid\s*=\s*''/.test(zeigen), 'bei jedem Oeffnen wird die fileid zurueckgesetzt (kein Rest vom letzten Bild)');
    pruefe(/optionen\.fileid/.test(zeigen) && /cloudFileidGueltig\(/.test(zeigen), 'zeigeBildVollbild liest {fileid} und prueft sie');
    pruefe(/bildEditorCloudZustand\(_quizEditor, gesichter, optionen\.markiere\)/.test(zeigen),
        'die Gesichter aus bild-gesichter bauen den Editorzustand (mit markiertem Gruppengesicht)');
    pruefe(/\(gesichter && gesichter\.length\) \|\| _quizEditor\.fileid/.test(zeigen),
        'der Editor entsteht im Cloud-Weg auch bei einem Bild ohne erkannte Gesichter');
    pruefe(/speicherZiel\.weg === 'cloud'/.test(zeigen) && /speichereBildCloud\(speichernBtn\)/.test(zeigen),
        '💾 ruft im Cloud-Weg speichereBildCloud');
    pruefe(/speichereEditorRahmen\(sel, iw, ih, speichernBtn\)/.test(zeigen), 'der Quiz-Weg ruft weiter speichereEditorRahmen');
    pruefe(/const rahmenZahl = \(speicherZiel\.weg === 'cloud'\) \? 0 : rahmenIndizes\(_quizEditor\)\.length;/.test(zeigen),
        'im Cloud-Weg gibt es keinen "alle speichern"-Knopf (ein 💾 schickt alles)');
    const ziel = zeigen.indexOf('const speicherZiel = editorSpeicherZiel(_quizEditor, sel);');
    const knopf = zeigen.indexOf("speichernBtn.textContent = '💾 Speichern'");
    const wenn = zeigen.indexOf('if (speicherZiel.ok)');
    pruefe(ziel > 0 && wenn > ziel && knopf > wenn, '💾 entsteht erst NACH der Zielpruefung (kein Knopf ohne Ziel)');
    pruefe(/if \(_quizEditor\.fileid\) \{[^}]*vollbild-neue-person/s.test(zeigen),
        'das Eingabefeld "Neue Person" entsteht nur im Cloud-Weg');
    pruefe(/_quizAktiv && _quizGesehen && _quizGesehen\.length && !_quizEditor\.refKontext && !_quizEditor\.fileid/.test(zeigen),
        '"Naechstes Bild" (Handy-Quiz) erscheint nicht im Cloud-Weg');
    // Chat-Bilder: Ansicht ohne fileid und ohne Gesichter -> kein Editor, keine Cloud-Knoepfe
    pruefe(/zeigeBildVollbild\(t, \[\]\)/.test(src), 'Chat-Bilder oeffnen weiter ohne fileid und ohne Gesichter (nur Ansicht)');
    pruefe(/function erkenneDiesesBildNeu\(\) \{\s*if \(_quizEditor\.fileid\)/.test(src) ||
           /async function erkenneDiesesBildNeu\(\) \{\s*if \(_quizEditor\.fileid\)/.test(src),
        'der Neu-erkennen-Knopf verzweigt im Cloud-Weg, der Quiz-Weg bleibt dahinter');
    pruefe(/\/api\/gesichter\/quiz\/analysiere/.test(funktionAusschneiden(src, 'erkenneDiesesBildNeu')),
        'der Quiz-Weg ruft weiter die Quiz-Analyse-Route');
});

await fall('K3) 💾 sammelt alle Aenderungen in EINEN bild-rahmen-Aufruf', async () => {
    const s = baue((url) => {
        if (url.indexOf('/api/gruppen/bild-rahmen') >= 0) return { ok: true, geschrieben: true, neu: ['111:1000', '111:1001'], aktion: 'abc' };
        if (url.indexOf('/api/gruppen/bild-gesichter') >= 0) return { ok: true, fileid: '111', gesichter: fuenf() };
        return { ok: true };
    });
    const e = {};
    s.zustand(e, fuenf(), null); e.fileid = '111';
    pruefe(e.bbox_norm_live.length === 5 && gleich(e.gids, ['111:0', '111:1', '111:2', '111:3', '111:4']),
        'Zustand: 5 Rahmen mit ihren gids', j(e.gids));
    pruefe(gleich(e.personen, ['', 'Person B', '', '', 'Person E']), 'Zustand: Namen der Gesichter', j(e.personen));
    pruefe(s.aenderungen(e).aenderungen.length === 0, 'unveraendert -> nichts zu schicken');

    e.bbox_norm_live[0] = [0.12, 0.10, 0.20, 0.20];           // A verschoben
    e.bbox_norm_live[1] = null;                               // B geloescht
    e.personen[2] = 'Person C';                               // C benannt
    e.personen[4] = 'Person E2';                              // E umbenannt (D und E-Rahmen bleiben)
    e.bbox_norm_live[5] = [0.60, 0.60, 0.20, 0.20]; e.personen[5] = 'Neue Person';   // neuer Rahmen mit Name
    e.bbox_norm_live[6] = [0.30, 0.80, 0.10, 0.10]; e.personen[6] = '';              // neuer Rahmen ohne Name
    const plan = s.aenderungen(e);
    const soll = [
        { gid: '111:0', bbox_norm: [0.12, 0.1, 0.2, 0.2] },
        { gid: '111:1', entfernen: true },
        { gid: '111:2', name: 'Person C' },
        { gid: '111:4', name: 'Person E2' },
        { neu: true, bbox_norm: [0.6, 0.6, 0.2, 0.2], name: 'Neue Person' },
        { neu: true, bbox_norm: [0.3, 0.8, 0.1, 0.1] },
    ];
    pruefe(gleich(plan.aenderungen, soll), 'verschoben/geloescht/benannt/neu, unveraenderte Gesichter (D) fehlen', j(plan.aenderungen));
    pruefe(!plan.aenderungen.some((a) => a.gid === '111:3'), 'das unveraenderte Gesicht D wird nicht geschickt');
    pruefe(plan.zuViele === false, 'sechs Aenderungen sind nicht zu viele');

    const knopf = { textContent: '💾 Speichern' };
    const r = await s.speichern(e, knopf);
    // e.melde fehlt -> Meldung geht ins Leere; die Zaehlung steht in den Aufrufen
    const posts = s.aufrufe.filter((a) => a.methode === 'POST');
    pruefe(posts.length === 1, 'genau EIN Sendeversuch', String(posts.length));
    pruefe(posts.length === 1 && /\/api\/gruppen\/bild-rahmen$/.test(posts[0].url), 'an /api/gruppen/bild-rahmen', posts[0] && posts[0].url);
    const body = posts.length ? JSON.parse(posts[0].options.body) : {};
    pruefe(body.fileid === '111' && gleich(body.aenderungen, soll), 'Body: fileid und alle Aenderungen gesammelt', j(body));
    pruefe(r && r.ok === true, 'Ergebnis ok', j(r));
});

await fall('K3b) Namenswahl: Name nur, wenn er sich geaendert hat; Name zuruecksetzen schickt nichts', async () => {
    const s = baue();
    const e = {};
    s.zustand(e, fuenf(), null);
    e.personen[1] = 'Person B';              // gleicher Name wie vorher
    e.personen[4] = '';                      // leer = nichts zu senden (kein Namen-Loeschen)
    pruefe(s.aenderungen(e).aenderungen.length === 0, 'gleicher oder leerer Name erzeugt keine Aenderung', j(s.aenderungen(e).aenderungen));
    pruefe(gleich(s.bboxServer([0.5, 0.5, 0.0, 0.0]), [0.5, 0.5, 0.01, 0.01]), 'zu kleine Rahmen werden auf die Mindestgroesse 1 % gebracht',
        j(s.bboxServer([0.5, 0.5, 0.0, 0.0])));
    const r = s.bboxServer([0.9, 0.9, 0.5, 0.5]);
    pruefe(r[0] + r[2] <= 1 && r[1] + r[3] <= 1, 'Rahmen bleiben im Bild (Summe <= 1)', j(r));
});

await fall('K3c) mehr als 30 Aenderungen: klare Meldung statt Senden', async () => {
    const viele = [];
    for (let i = 0; i < 31; i++) viele.push(gesichtServer(i, [0.01 + i * 0.03, 0.1, 0.02, 0.2]));
    const s = baue();
    const e = {}; const meldungen = [];
    s.zustand(e, viele, null);
    e.melde = (t, ok) => meldungen.push([t, ok]);
    e.fileid = '111';
    for (let i = 0; i < 31; i++) e.bbox_norm_live[i] = [0.01 + i * 0.03, 0.12, 0.02, 0.2];
    pruefe(s.aenderungen(e).zuViele === true, '31 Aenderungen sind zu viele');
    const r = await s.speichern(e, null);
    pruefe(s.aufrufe.length === 0, 'es wird NICHTS gesendet', String(s.aufrufe.length));
    pruefe(meldungen.length === 1 && /30/.test(meldungen[0][0]) && /31/.test(meldungen[0][0]) && meldungen[0][1] === false,
        'die Meldung nennt 31 und die Grenze 30', j(meldungen));
    pruefe(r && r.ok === false, 'Ergebnis nicht ok', j(r));

    // genau 30 gehen
    const s2 = baue((url) => (url.indexOf('bild-rahmen') >= 0 ? { ok: true, geschrieben: true } : { ok: true, gesichter: viele.slice(0, 30) }));
    const e2 = {};
    s2.zustand(e2, viele.slice(0, 30), null);
    e2.fileid = '111';
    for (let i = 0; i < 30; i++) e2.bbox_norm_live[i] = [0.01 + i * 0.03, 0.12, 0.02, 0.2];
    await s2.speichern(e2, null);
    const posts = s2.aufrufe.filter((a) => a.methode === 'POST');
    pruefe(posts.length === 1 && JSON.parse(posts[0].options.body).aenderungen.length === 30, 'genau 30 Aenderungen werden gesendet');
});

await fall('K3d) ohne Aenderung wird nichts gesendet', async () => {
    const s = baue();
    const e = {}; const meldungen = [];
    s.zustand(e, fuenf(), null);
    e.fileid = '111';
    e.melde = (t, ok) => meldungen.push([t, ok]);
    const r = await s.speichern(e, null);
    pruefe(s.aufrufe.length === 0, 'kein Netzaufruf ohne Aenderung');
    pruefe(meldungen.length === 1 && /Keine Änderung/.test(meldungen[0][0]), 'ehrliche Meldung "Keine Änderungen"', j(meldungen));
    pruefe(r && r.gesendet === 0, 'Ergebnis nennt 0 gesendet', j(r));
});

await fall('K4) Meldung aus der Server-Antwort', async () => {
    const s = baue();
    const ok3 = s.meldung({ ok: true, geschrieben: true }, 3);
    pruefe(ok3.ok === true && ok3.text === '✓ 3 Änderungen gespeichert', 'Erfolg nennt die Anzahl', j(ok3));
    pruefe(s.meldung({ ok: true, geschrieben: true }, 1).text === '✓ 1 Änderung gespeichert', 'Einzahl');
    const teil = s.meldung({ ok: false, teilweise: true, geschrieben: true,
        fehler: 'Nicht alles gespeichert – wurde nicht übernommen: Zuordnung zu „Person B“ (Beispiel).' }, 4);
    pruefe(teil.ok === false && teil.text.indexOf('Zuordnung zu „Person B“ (Beispiel)') >= 0, 'Teilfehler: der Klartext des Servers steht drin', j(teil));
    pruefe(teil.neuLaden === true, 'nach Teilfehler wird neu geladen (ein Teil ist gespeichert)');
    const aus = s.meldung({ ok: false, geschrieben: false, fehler: 'Änderung 2: Das Gesicht gehört zu einem anderen Bild.' }, 2);
    pruefe(aus.ok === false && aus.text.indexOf('Änderung 2: Das Gesicht gehört zu einem anderen Bild.') >= 0, 'ok:false: der fehler-Text steht drin', j(aus));
    pruefe(aus.neuLaden === false, 'nichts geschrieben -> nicht neu laden (die Eingaben bleiben stehen)');
    pruefe(s.meldung(null, 2).ok === false && s.meldung(undefined, 2).text.length > 0, 'keine Antwort -> ehrliche Fehlermeldung');
    pruefe(s.meldung({ ok: false }, 2).text.length > 0, 'ok:false ohne Text -> trotzdem eine Meldung');
});

await fall('K4b) nach Erfolg: Gesichter neu laden, neue gids uebernehmen', async () => {
    const nachher = fuenf();
    nachher.push(gesichtServer(1000, [0.6, 0.6, 0.2, 0.2], 'Neue Person', { quelle: 'hand', kennung: null, name_quelle: 'handy' }));
    const s = baue((url) => {
        if (url.indexOf('/api/gruppen/bild-rahmen') >= 0) return { ok: true, geschrieben: true, neu: ['111:1000'] };
        if (url.indexOf('/api/gruppen/bild-gesichter') >= 0) return { ok: true, fileid: '111', gesichter: nachher };
        return { ok: true };
    });
    const e = {}; const meldungen = []; let aufgebaut = 0;
    s.zustand(e, fuenf(), null);
    e.fileid = '111';
    e.melde = (t, ok) => meldungen.push([t, ok]);
    e.cloudNeuAufbauen = () => { aufgebaut++; };
    e.bbox_norm_live[5] = [0.60, 0.60, 0.20, 0.20]; e.personen[5] = 'Neue Person';
    await s.speichern(e, { textContent: '' });
    const gets = s.aufrufe.filter((a) => a.methode === 'GET');
    pruefe(gets.length === 1 && /\/api\/gruppen\/bild-gesichter\?fileid=111$/.test(gets[0].url), 'danach GET bild-gesichter?fileid=111', j(gets.map((g) => g.url)));
    pruefe(e.gids.length === 6 && e.gids[5] === '111:1000', 'die vom Server vergebene gid ist uebernommen', j(e.gids));
    pruefe(e.basis[5] && e.basis[5].name === 'Neue Person', 'der neue Stand ist jetzt die Basis (kein erneutes Senden)', j(e.basis[5]));
    pruefe(s.aenderungen(e).aenderungen.length === 0, 'direkt danach ist nichts mehr zu speichern');
    pruefe(aufgebaut === 1, 'die Anzeige wird neu aufgebaut');
    pruefe(meldungen.length >= 1 && meldungen[meldungen.length - 1][0] === '✓ 1 Änderung gespeichert' && meldungen[meldungen.length - 1][1] === true,
        'Meldung "✓ 1 Änderung gespeichert"', j(meldungen));
});

await fall('K4c) Teilfehler / Fehler / Netz: ehrliche Meldung, Eingaben bleiben', async () => {
    // Teilfehler: neu laden, Klartext zeigen
    const teilFehler = 'Nicht alles gespeichert – wurde nicht übernommen: Zuordnung zu „Person B“ (Testfehler).';
    const s = baue((url) => (url.indexOf('bild-rahmen') >= 0
        ? { ok: false, teilweise: true, geschrieben: true, fehler: teilFehler }
        : { ok: true, gesichter: fuenf() }));
    const e = {}; const m = [];
    s.zustand(e, fuenf(), null); e.fileid = '111'; e.melde = (t, ok) => m.push([t, ok]);
    e.bbox_norm_live[0] = [0.12, 0.10, 0.20, 0.20];
    await s.speichern(e, null);
    pruefe(m.length && m[m.length - 1][0].indexOf('Zuordnung zu „Person B“ (Testfehler)') >= 0 && m[m.length - 1][1] === false,
        'Teilfehler: Klartext steht in der Meldung', j(m));
    pruefe(s.aufrufe.filter((a) => a.methode === 'GET').length === 1, 'Teilfehler: Anzeige wird neu geladen');

    // ok:false ohne Schreiben: KEIN Neuladen, Eingaben bleiben
    const s2 = baue((url) => (url.indexOf('bild-rahmen') >= 0 ? { ok: false, geschrieben: false, fehler: 'Änderung 1: Der Rahmen liegt nicht im Bild oder ist kleiner als 1 %.' } : { ok: true }));
    const e2 = {}; const m2 = [];
    s2.zustand(e2, fuenf(), null); e2.fileid = '111'; e2.melde = (t, ok) => m2.push([t, ok]);
    e2.bbox_norm_live[0] = [0.12, 0.10, 0.20, 0.20];
    await s2.speichern(e2, null);
    pruefe(m2.length && /kleiner als 1 %/.test(m2[m2.length - 1][0]) && m2[m2.length - 1][1] === false, 'ok:false: der fehler-Text wird gezeigt', j(m2));
    pruefe(s2.aufrufe.filter((a) => a.methode === 'GET').length === 0, 'ok:false ohne Schreiben: nicht neu geladen');
    pruefe(gleich(e2.bbox_norm_live[0], [0.12, 0.10, 0.20, 0.20]) && s2.aenderungen(e2).aenderungen.length === 1, 'die Eingaben bleiben erhalten');

    // Netz reisst ab
    const s3 = baue(() => new Error('offline'));
    const e3 = {}; const m3 = [];
    s3.zustand(e3, fuenf(), null); e3.fileid = '111'; e3.melde = (t, ok) => m3.push([t, ok]);
    e3.bbox_norm_live[0] = [0.12, 0.10, 0.20, 0.20];
    const r3 = await s3.speichern(e3, null);
    pruefe(r3 && r3.ok === false && m3.length && m3[m3.length - 1][1] === false, 'Netzfehler: ehrliche Fehlermeldung', j(m3));
    pruefe(e3.cloudSpeichert === false, 'die Sperre gegen Doppelklick ist wieder frei');
    const erneut = await s3.speichern(e3, null);
    pruefe(s3.aufrufe.filter((a) => a.methode === 'POST').length === 2, 'danach ist ein erneutes Speichern moeglich');
});

await fall('K5) "Neu erkennen" im Cloud-Weg: bild-erkennen, gestrichelter Vorschlag, nichts aendert sich ohne Antippen', async () => {
    const neuNorm = [0.70, 0.60, 0.15, 0.15];
    const antwort = { ok: true, fileid: '111', quelle: 'vorschau_800', breite: 800, hoehe: 600, abgleich: true, gesichter: [
        { bbox_norm: A, status: 'bekannt', gid: '111:0', name: null, vorschlaege: [] },
        { bbox_norm: neuNorm, status: 'neu', vorschlaege: [{ name: 'Person X', abstand: 0.31 }, { name: 'Person Y', abstand: 0.4 }] },
        { bbox_norm: [0.101, 0.101, 0.2, 0.2], status: 'neu', vorschlaege: [] },          // liegt auf Rahmen A
    ] };
    const s = baue((url) => (url.indexOf('bild-erkennen') >= 0 ? antwort : { ok: true }));
    const e = {};
    s.zustand(e, fuenf(), null); e.fileid = '111';
    const vorher = j([e.bbox_norm_live, e.personen, e.gids, e.basis]);
    const roh = await s.abrufen('111');
    const posts = s.aufrufe.filter((a) => a.methode === 'POST');
    pruefe(posts.length === 1 && /\/api\/gruppen\/bild-erkennen$/.test(posts[0].url), 'ruft POST /api/gruppen/bild-erkennen', j(posts.map((p) => p.url)));
    pruefe(!s.aufrufe.some((a) => /quiz\/analysiere/.test(a.url)), 'NICHT die Quiz-Analyse-Route');
    pruefe(posts.length === 1 && gleich(JSON.parse(posts[0].options.body), { fileid: '111' }), 'Body ist {fileid}');
    const m = s.erkennung(e, roh);
    pruefe(m.ok === true && m.neu === 1, 'ein neuer Vorschlag (der auf Rahmen A zaehlt als schon vorhanden)', j(m));
    pruefe(e.vorschlaege.length === 1 && gleich(e.vorschlaege[0].bbox_norm, neuNorm), 'der Vorschlag steht in e.vorschlaege', j(e.vorschlaege));
    pruefe(gleich(e.vorschlaege[0].namen, ['Person X', 'Person Y']), 'mit den Namensvorschlaegen', j(e.vorschlaege[0].namen));
    pruefe(j([e.bbox_norm_live, e.personen, e.gids, e.basis]) === vorher, 'vor dem Antippen aendert sich NICHTS an Rahmen/Personen');
    pruefe(s.aenderungen(e).aenderungen.length === 0, 'und es ist nichts zu speichern');
    pruefe(/\d/.test(m.text) && /gestrichelt/.test(m.text) && /antippen/i.test(m.text), 'die Meldung erklaert: gestrichelt, antippen', m.text);

    // gestricheltes Element
    let getippt = 0;
    const el = s.element(e.vorschlaege[0], () => { getippt++; });
    pruefe(/dashed/.test(el.style.cssText) && !/solid/.test(el.style.cssText), 'das Vorschlags-Element ist gestrichelt', el.style.cssText);
    pruefe(/Vorschlag/.test(el.textContent) && /Person X/.test(el.textContent), 'beschriftet als Vorschlag (mit dem ersten Namen)', el.textContent);
    pruefe(el.attributes['data-vorschlag'] === '1', 'traegt data-vorschlag (kein Zieh-/Zoom-Rahmen)');
    el.click();
    pruefe(getippt === 1, 'Antippen ruft den Rueckruf');

    // Antippen = uebernehmen als neuer Rahmen
    const idx = s.uebernehmen(e, 0);
    pruefe(idx === 5 && gleich(e.bbox_norm_live[5], neuNorm), 'uebernommen als neuer Rahmen am Ende', String(idx));
    pruefe(e.gids[5] === '' && e.basis[5] == null && e.personen[5] === '', 'ohne gid, ohne Basis, ohne Person (= neues Gesicht)');
    pruefe(e.vorschlaege.length === 0, 'der Vorschlag ist verbraucht');
    pruefe(s.uebernehmen(e, 0) === -1, 'ein zweites Antippen ins Leere tut nichts');
    const plan = s.aenderungen(e).aenderungen;
    pruefe(gleich(plan, [{ neu: true, bbox_norm: neuNorm }]), 'beim Speichern geht er als {neu:true, bbox_norm} raus', j(plan));
    pruefe(gleich(s.namen(e, 5).slice(0, 2), ['Person X', 'Person Y']), 'seine Namensvorschlaege stehen oben im Personenmenue', j(s.namen(e, 5)));
});

await fall('K5b) Fehlertext der Route wird gezeigt (HTTP-Fehlerstatus, Netz)', async () => {
    const fehlerAntwort = { ok: false, grund: 'bild_zu_gross', fehler: 'Bild zu groß (über 25 MB).', __status: 413 };
    const s = baue(() => fehlerAntwort);
    const e = {};
    s.zustand(e, fuenf(), null); e.fileid = '111';
    const vorher = j([e.bbox_norm_live, e.personen]);
    const roh = await s.abrufen('111');
    pruefe(roh && roh.ok === false && roh.fehler === 'Bild zu groß (über 25 MB).', 'der fehler-Text der Route kommt durch', j(roh));
    const m = s.erkennung(e, roh);
    pruefe(m.ok === false && m.text.indexOf('Bild zu groß (über 25 MB).') >= 0, 'die Meldung zeigt den Fehlertext', m.text);
    pruefe(e.vorschlaege.length === 0 && j([e.bbox_norm_live, e.personen]) === vorher, 'bei Fehler bleibt alles unveraendert');
    const s2 = baue(() => new Error('offline'));
    const roh2 = await s2.abrufen('111');
    pruefe(roh2 && roh2.ok === false && /erreichbar/.test(roh2.fehler), 'Netzfehler: "nicht erreichbar"', j(roh2));
    const leer = s.erkennung(e, { ok: true, gesichter: [] });
    pruefe(leer.ok === true && leer.neu === 0, 'keine neuen Gesichter: ok, 0 neu', j(leer));
});

await fall('K6) Personenmenue: benannte Personen + "Neue Person …" mit Hinweis "nur am Handy"', async () => {
    const s = baue((url) => (url.indexOf('/api/gruppen/personen') >= 0
        ? { ok: true, personen: [{ name: 'Person Z' }, { name: 'Person B' }, { name: 'Person A' }] } : { ok: true }));
    const e = {};
    s.zustand(e, fuenf(), null); e.fileid = '111';
    await s.ladeNamen();
    const gets = s.aufrufe.filter((a) => /\/api\/gruppen\/personen$/.test(a.url));
    pruefe(gets.length === 1, 'die benannten Personen kommen von /api/gruppen/personen', j(s.aufrufe.map((a) => a.url)));
    const namen = s.namen(e, 0);
    pruefe(['Person A', 'Person B', 'Person E', 'Person Z'].every((n) => namen.indexOf(n) >= 0), 'benannte Personen werden angeboten', j(namen));
    pruefe(namen.filter((n) => n === 'Person B').length === 1, 'jeder Name nur einmal');
    await s.ladeNamen();
    pruefe(s.aufrufe.filter((a) => /\/api\/gruppen\/personen$/.test(a.url)).length === 1, 'die Liste wird zwischengespeichert');
    const opt = s.optionText();
    pruefe(/Neue Person/.test(opt) && /nur am Handy/.test(opt), 'Option "Neue Person …" nennt "nur am Handy"', opt);
    pruefe(/nur am Handy/.test(s.hinweis(e, 'Voellig Neu')), 'neuer Name -> Hinweis "nur am Handy"', s.hinweis(e, 'Voellig Neu'));
    pruefe(s.hinweis(e, 'person z') === '' && s.hinweis(e, 'Person B') === '', 'bekannter Name -> kein "nur am Handy"-Hinweis');
    const zeigen = funktionAusschneiden(src, 'zeigeBildVollbild');
    pruefe(zeigen.indexOf("'__neue_person__'") > 0 && /cloudNeuePersonOptionText\(\)/.test(zeigen), 'die Option steckt im Menue');
    pruefe(/placeholder = '[^']*nur am Handy/.test(zeigen), 'das Eingabefeld traegt den Hinweis "nur am Handy"');
    pruefe(/cloudPersonenNamen\(_quizEditor, sel\)/.test(zeigen), 'das Menue nimmt im Cloud-Weg die Cloud-Namen');
});

await fall('K7) Gruppen-Quiz: Fotoansicht und Gesamtansicht oeffnen den Editor mit {fileid} + bild-gesichter', async () => {
    class Element {
        constructor(tag = 'div', id = '') {
            this.tagName = String(tag).toUpperCase(); this.id = id; this.children = []; this.listeners = new Map();
            this.attributes = {}; this.dataset = {}; this.hidden = false; this.disabled = false; this.value = '';
            this._text = ''; this._class = ''; this.style = {};
            this.classList = {
                add: (...n) => { this._class = [...new Set((this._class + ' ' + n.join(' ')).trim().split(/\s+/))].join(' '); },
                remove: (...n) => { this._class = this._class.split(/\s+/).filter((x) => x && !n.includes(x)).join(' '); },
                contains: (n) => this._class.split(/\s+/).includes(n),
                toggle: (n, f) => { const a = f === undefined ? !this.classList.contains(n) : f; this.classList[a ? 'add' : 'remove'](n); return a; },
            };
        }
        get lastChild() { return this.children[this.children.length - 1] || null; }
        set className(v) { this._class = v || ''; }
        get className() { return this._class; }
        set textContent(v) { this._text = String(v ?? ''); this.children = []; }
        get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
        set innerHTML(v) { this._text = ''; this.children = []; this._html = String(v); }
        get innerHTML() { return this._html || ''; }
        addEventListener(t, fn) { if (!this.listeners.has(t)) this.listeners.set(t, []); this.listeners.get(t).push(fn); }
        setAttribute(k, v) { this.attributes[k] = String(v); }
        appendChild(c) { c.parentNode = this; this.children.push(c); if (c.id && Element.registry) Element.registry.set(c.id, c); return c; }
        remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((x) => x !== this); }
        closest() { return null; }
        focus() {}
        querySelectorAll() { return []; }
        async click() {
            if (this.disabled) return;
            await Promise.all((this.listeners.get('click') || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {} })));
        }
    }
    const antw = (v) => ({ ok: true, json: async () => v });
    const fotoGesicht = { gid: '111:0', fileid: '111', index: 0, bbox: [80, 60, 160, 120], breite: 800, hoehe: 600,
        aufnahme: '2020-01-01', kennung: 'G-1' };
    const videoGesicht = { gid: '222:0', fileid: '222', index: 0, bbox: [80, 60, 160, 120], breite: 800, hoehe: 600,
        aufnahme: '2020-01-02', kennung: 'G-1', video: true, zeit_s: 4 };
    const kaputt = { gid: 'x:0', fileid: 'abc', index: 0, bbox: [80, 60, 160, 120], breite: 800, hoehe: 600, kennung: 'G-1' };
    const serverListe = fuenf();

    function app(optionen) {
        const o = optionen || {};
        const aufrufe = []; const editor = [];
        const elemente = new Map();
        Element.registry = elemente;
        for (const t of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"[^>]*>/gi)) {
            const e = new Element(t[1], t[2]); e.hidden = /\shidden(?:\s|>)/i.test(t[0]);
            const k = t[0].match(/\bclass="([^"]*)"/i); if (k) e.className = k[1];
            elemente.set(e.id, e);
        }
        const document = {
            readyState: 'complete', getElementById(id) { if (!elemente.has(id)) elemente.set(id, new Element('div', id)); return elemente.get(id); },
            createElement(tag) { return new Element(tag); }, addEventListener() {},
        };
        const fetchImpl = async (url, options = {}) => {
            const p = new URL(url);
            const voll = p.pathname + p.search;
            aufrufe.push({ pfad: voll, methode: (options.method || 'GET').toUpperCase() });
            if (p.pathname === '/api/gruppen/naechste') return antw({ ok: true, fertig: false, offen: 1,
                gruppe: { kennung: 'G-1', groesse: 3, bilder: 3, videos: 0, status: 'offen', name: null, war_spaeter: false,
                    beispiele: [fotoGesicht, videoGesicht, kaputt], zwillinge: [], verbunden: [] }, namen: ['Anna'] });
            if (p.pathname === '/api/gruppen/stand' || p.pathname.startsWith('/api/gruppen/suche')) return antw({ ok: true, treffer: [] });
            if (p.pathname === '/api/gruppen/liste') return antw({ ok: true, status: 'offen', gesamt: 1, seiten: 1, seite: 1, je_seite: 24,
                gruppen: [{ kennung: 'G-1', groesse: 3, bilder: 3, videos: 0, von: '2018-01-01', bis: '2024-12-31', status: 'offen', name: null, beispiele: [], zwillinge: [], verbunden: [] }] });
            if (/^\/api\/gruppen\/detail\/G-1$/.test(p.pathname)) return antw({ ok: true, fertig: false, offen: 1, namen: ['Anna'],
                gruppe: { kennung: 'G-1', groesse: 3, bilder: 3, videos: 0, status: 'offen', name: null, war_spaeter: false, beispiele: [], zwillinge: [], verbunden: [] } });
            if (p.pathname === '/api/gruppen/gesichter') return antw({ ok: true, seite: 1, seiten: 1, gesamt: 3, ausschlossen: 0,
                gesichter: [{ ...fotoGesicht, gid: '111:1', index: 1, bbox: [320, 60, 160, 120] }, videoGesicht, kaputt] });
            if (p.pathname === '/api/gruppen/bild-gesichter') {
                if (o.gesichterFehler) return antw({ ok: false, fehler: 'Gesichter nicht ladbar (Test).' });
                return antw({ ok: true, fileid: p.searchParams.get('fileid'), gesichter: serverListe });
            }
            if (p.pathname === '/api/cloud/thumb') return { ok: true, blob: async () => ({ size: 1 }) };
            throw new Error('Unerwarteter Request: ' + voll);
        };
        class Image { constructor() { this.onload = null; this.onerror = null; } set src(_v) {} }
        const sandbox = {
            document, fetch: fetchImpl, location: { origin: 'http://localhost' }, Image,
            URL: { createObjectURL() { return 'blob:test'; }, revokeObjectURL() {} },
            zeigeBildVollbild(img, gesichter, opts) { editor.push({ img, gesichter, opts }); },
            setTimeout, clearTimeout, console, Date, Map, Set, Promise, encodeURIComponent, Number, Math, JSON, Array, Object, String,
        };
        vm.runInNewContext(gqSrc, sandbox, { filename: gqPfad });
        return { el: (id) => document.getElementById(id), aufrufe, editor };
    }
    const settle = async () => { await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r)); };

    // — Fotoansicht (Quiz-Karte) —
    const a = app();
    await a.el('gruppen-btn').click(); await settle();
    const kacheln = a.el('gruppen-kacheln').children;
    pruefe(kacheln.length === 3, 'die Quiz-Karte zeigt drei Kacheln', String(kacheln.length));
    await kacheln[0].click(); await settle(); await settle();
    pruefe(a.aufrufe.some((c) => /^\/api\/gruppen\/bild-gesichter\?fileid=111$/.test(c.pfad)), 'Fotoansicht: GET bild-gesichter?fileid=111', j(a.aufrufe.map((c) => c.pfad)));
    pruefe(a.editor.length === 1, 'der Editor wird genau einmal geoeffnet', String(a.editor.length));
    const ed = a.editor[0] || {};
    pruefe(ed.opts && ed.opts.fileid === '111', 'mit {fileid: "111"}', j(ed.opts));
    pruefe(ed.gesichter && gleich(ed.gesichter.map((g) => g.gid), serverListe.map((g) => g.gid)), 'mit den Gesichtern aus bild-gesichter', j(ed.gesichter && ed.gesichter.map((g) => g.gid)));
    pruefe(ed.opts && ed.opts.markiere && gleich(ed.opts.markiere.bbox_norm, [0.1, 0.1, 0.2, 0.2]) && ed.opts.markiere.gid === '111:0',
        'das Gruppengesicht bleibt markiert (bbox_norm + gid)', j(ed.opts && ed.opts.markiere));

    // — Video-Standbild und kaputte Kennung: nur Ansicht wie bisher —
    await kacheln[1].click(); await settle(); await settle();
    const v = a.editor[1] || {};
    pruefe(a.editor.length === 2 && v.opts === undefined && gleich(v.gesichter && v.gesichter.length, 1), 'Video-Standbild: nur Ansicht (ohne fileid), nur das Gruppengesicht', j(v.opts));
    pruefe(!a.aufrufe.some((c) => /bild-gesichter\?fileid=222/.test(c.pfad)), 'fuer Videos wird bild-gesichter nicht gerufen');
    await kacheln[2].click(); await settle(); await settle();
    pruefe(a.editor.length === 3 && a.editor[2].opts === undefined, 'nicht-numerische Kennung: nur Ansicht', j(a.editor[2] && a.editor[2].opts));
    pruefe(!a.aufrufe.some((c) => /bild-gesichter\?fileid=abc/.test(c.pfad)), 'fuer nicht-numerische Kennungen wird nichts abgerufen');

    // — Gesamtansicht (Alle Gesichter) —
    const b = app();
    await b.el('gruppen-btn').click(); await settle();
    await b.el('gruppen-uebersicht').click(); await settle();
    await b.el('gruppen-liste-zeile-G-1').click(); await settle();
    await b.el('gruppen-alle').click(); await settle();
    const raster = b.el('gruppen-alle-raster').children;
    const k = raster.find((x) => x.dataset.gid === '111:1');
    pruefe(!!k, 'Gesamtansicht zeigt die Kachel 111:1');
    if (k) { await k.click(); await settle(); await settle(); }
    pruefe(b.aufrufe.some((c) => /^\/api\/gruppen\/bild-gesichter\?fileid=111$/.test(c.pfad)), 'Gesamtansicht: GET bild-gesichter?fileid=111', j(b.aufrufe.map((c) => c.pfad)));
    const eb = b.editor[0] || {};
    pruefe(eb.opts && eb.opts.fileid === '111' && eb.gesichter && eb.gesichter.length === 5, 'Gesamtansicht: Editor mit {fileid} und den Gesichtern', j(eb.opts));
    pruefe(eb.opts && eb.opts.markiere && eb.opts.markiere.gid === '111:1' && gleich(eb.opts.markiere.bbox_norm, [0.4, 0.1, 0.2, 0.2]),
        'Gesamtansicht: das angetippte Gesicht bleibt markiert', j(eb.opts && eb.opts.markiere));

    // — bild-gesichter nicht ladbar: ehrlich auf die reine Ansicht zurueck —
    const c = app({ gesichterFehler: true });
    await c.el('gruppen-btn').click(); await settle();
    await c.el('gruppen-kacheln').children[0].click(); await settle(); await settle();
    const ec = c.editor[0] || {};
    pruefe(c.editor.length === 1 && ec.opts === undefined && ec.gesichter && ec.gesichter.length === 1, 'bild-gesichter nicht ladbar: Ansicht wie bisher, ohne Cloud-Bearbeitung', j(ec.opts));
    pruefe(/nicht ladbar|nur Ansicht/.test(c.el('gruppen-meldung').textContent), 'und eine ehrliche Meldung', c.el('gruppen-meldung').textContent);
});

await fall('K8) Werte nur per textContent (kein innerHTML mit Daten)', async () => {
    const von = src.indexOf('// ── Bild-Editor B4');
    const bis = src.indexOf('// ── Ende Bild-Editor B4');
    pruefe(von > 0 && bis > von, 'der B4-Block in app.js ist markiert');
    const block = von > 0 && bis > von ? src.slice(von, bis) : '';
    pruefe(block.length > 0 && !/innerHTML|insertAdjacentHTML|outerHTML|document\.write/.test(block), 'der B4-Block benutzt kein innerHTML');
    const zeigen = funktionAusschneiden(src, 'zeigeBildVollbild');
    const cloudTeil = zeigen.slice(zeigen.indexOf('cloudVorschlaegeMalen'));
    pruefe(!/innerHTML/.test(cloudTeil), 'die Cloud-Teile im Editor benutzen kein innerHTML');
    const gqVoll = funktionAusschneiden(gqSrc, 'vollbildOeffnen');
    pruefe(!/innerHTML/.test(gqVoll), 'vollbildOeffnen benutzt kein innerHTML');
    // Gegenprobe mit Giftname: im Vorschlags-Element nur als Text
    const s = baue();
    const el = s.element({ bbox_norm: A, namen: ['<img src=x onerror=alert(1)>'] }, () => {});
    pruefe(el.textContent.indexOf('<img src=x onerror=alert(1)>') >= 0 && el.children.length === 1, 'Giftname steht als reiner Text im Element (kein HTML)');
});

await fall('K9) Cache-Schluessel in index.html erhoeht', async () => {
    const vApp = (html.match(/app\.js\?v=(\d{8}[A-Z])/) || [])[1] || '';
    const vGq = (html.match(/gruppen_quiz\.js\?v=(\d{8}[A-Z])/) || [])[1] || '';
    pruefe(vApp >= '20261027A', 'app.js?v= mindestens 20261027A (Format JJJJMMTT+Buchstabe)', vApp);
    pruefe(vGq >= '20261027A', 'gruppen_quiz.js?v= mindestens 20261027A (Format JJJJMMTT+Buchstabe)', vGq);
});

await fall('K10) Handybreite: neue Knoepfe brechen um und bleiben im Fenster', async () => {
    pruefe(/leiste\.style\.cssText = 'position:fixed;bottom:74px;left:0;right:0;margin:0 auto;width:fit-content;[^']*flex-wrap:wrap[^']*max-width:96vw/.test(src),
        'die Werkzeugleiste bricht weiter um und bleibt im Fenster');
    const zeigen = funktionAusschneiden(src, 'zeigeBildVollbild');
    const stellen = [];
    const re = /(neuePersonFeld|neuePersonOk|neuePersonZeile)\.style\.cssText = '([^']*)'/g;
    let m;
    while ((m = re.exec(zeigen)) !== null) stellen.push([m[1], m[2]]);
    pruefe(stellen.length >= 2, 'die neuen Bedienelemente setzen ihren Stil (Feld + OK)', String(stellen.length));
    for (const [name, css] of stellen) {
        const vw = /max-width:\s*(\d+)vw/.exec(css);
        pruefe(!!vw && Number(vw[1]) <= 96 && !/position:\s*fixed/.test(css), name + ': max-width in vw (<= 96) und nicht fixed', css);
        pruefe(!/(^|;)\s*width:\s*\d{3,}px/.test(css), name + ': keine feste Pixelbreite ueber 100 px');
    }
    pruefe(/leiste\.appendChild\(neuePersonFeld\)/.test(zeigen) && /leiste\.appendChild\(neuePersonOk\)/.test(zeigen),
        'die Bedienelemente haengen in der umbrechenden Werkzeugleiste');
});

console.log('\n' + (fehler ? 'FEHLER: ' + fehler + ' von ' + zaehler + ' Pruefungen rot' : 'alle ' + zaehler + ' Pruefungen bestanden'));
process.exit(fehler ? 1 : 0);
})();
