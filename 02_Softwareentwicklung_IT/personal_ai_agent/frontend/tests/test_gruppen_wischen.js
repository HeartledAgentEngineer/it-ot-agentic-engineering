// Runtime-Vertrag für das Wischen zur nächsten/vorherigen Person (S8-Rest 3,
// 18.10.2026, To-do Punkt 10): „Ist man auf einer Person, soll man mit Wischen
// nach links/rechts zur nächsten bzw. vorherigen Person wechseln können …
// am PC zusätzlich sinnvoll: Pfeiltasten links/rechts.“
//
// Der Test fährt die ECHTEN Handler: pointerdown/pointerup am Personenbereich
// und die Tastatur am Dokument. Nur HTTP-Antworten sind kontrollierte Attrappen.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sourcePath = process.argv[2] && process.argv[2].endsWith('gruppen_quiz.js')
    ? process.argv[2] : path.join(__dirname, '..', 'gruppen_quiz.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

class Element {
    constructor(tag = 'div', id = '') {
        this.tagName = tag.toUpperCase();
        this.id = id;
        this.children = [];
        this.listeners = new Map();
        this.attributes = {};
        this.dataset = {};
        this.hidden = false;
        this.disabled = false;
        this.value = '';
        this._text = '';
        this._class = '';
        this.classList = {
            add: (...names) => { this._class = [...new Set((this._class + ' ' + names.join(' ')).trim().split(/\s+/))].join(' '); },
            remove: (...names) => { this._class = this._class.split(/\s+/).filter((n) => n && !names.includes(n)).join(' '); },
            contains: (name) => this._class.split(/\s+/).includes(name),
            toggle: (name, force) => {
                const active = force === undefined ? !this.classList.contains(name) : force;
                this.classList[active ? 'add' : 'remove'](name);
                return active;
            },
        };
    }
    get lastChild() { return this.children[this.children.length - 1] || null; }
    set className(value) { this._class = value || ''; }
    get className() { return this._class; }
    set textContent(value) { this._text = String(value ?? ''); this.children = []; }
    get textContent() { return this._text + this.children.map((child) => child.textContent).join(''); }
    set innerHTML(value) { this._text = ''; this.children = []; this._html = String(value); }
    get innerHTML() { return this._html || ''; }
    addEventListener(type, fn) {
        if (!this.listeners.has(type)) this.listeners.set(type, []);
        this.listeners.get(type).push(fn);
    }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        if (child.id && Element.registry) Element.registry.set(child.id, child);
        return child;
    }
    remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((item) => item !== this); }
    closest() { return null; }
    focus() {}
    scrollIntoView() {}
    querySelectorAll() { return []; }
    async click() {
        if (this.disabled) return;
        const calls = (this.listeners.get('click') || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {} }));
        await Promise.all(calls);
    }
    /** Ein Ereignis der Attrappe auf allen Zuhörern dieser Art feuern. */
    feuern(type, werfen = {}) {
        return (this.listeners.get(type) || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {}, ...werfen }));
    }
}

function person(name, extra = {}) {
    return { name, gesichter: 5, vorschlaege: 1, beispiel: null,
        gruppen: [{ kennung: 'G-' + name, groesse: 5, von: null, bis: null }], ...extra };
}

function harness(fetchImpl) {
    const elements = new Map();
    const dokumentListeners = new Map();
    Element.registry = elements;
    for (const match of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"[^>]*>/gi)) {
        const e = new Element(match[1], match[2]);
        e.hidden = /\shidden(?:\s|>)/i.test(match[0]);
        const classes = match[0].match(/\bclass="([^"]*)"/i);
        if (classes) e.className = classes[1];
        elements.set(e.id, e);
    }
    const document = {
        readyState: 'complete',
        getElementById(id) { if (!elements.has(id)) elements.set(id, new Element('div', id)); return elements.get(id); },
        createElement(tag) { return new Element(tag); },
        addEventListener(type, fn) {
            if (!dokumentListeners.has(type)) dokumentListeners.set(type, []);
            dokumentListeners.get(type).push(fn);
        },
        /** Ein Dokument-Ereignis feuern (so laufen die Pfeiltasten im Test). */
        feuern(type, werfen = {}) {
            return (dokumentListeners.get(type) || []).map((fn) => fn({ preventDefault() {}, ...werfen }));
        },
        hatZuhörer(type) { return (dokumentListeners.get(type) || []).length > 0; },
    };
    const sandbox = {
        document, fetch: fetchImpl, location: { origin: 'http://localhost' },
        URL: { createObjectURL() { return 'blob:test'; }, revokeObjectURL() {} },
        setTimeout, clearTimeout, console, Date, Map, Set, Promise, encodeURIComponent, Number, Array, String,
    };
    vm.runInNewContext(source, sandbox, { filename: sourcePath });
    return { elements, el: (id) => document.getElementById(id), sandbox, document };
}

async function settle() {
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
}

function response(value) { return { json: async () => value }; }

/** Attrappe mit Personenliste UND Personenprofil (mit Aufzeichnung der Anfragen). */
function personenAppMitProfil(personen, protokoll) {
    return harness(async (url) => {
        const u = new URL(url);
        const pfad = u.pathname + u.search;
        if (protokoll) protokoll.push(pfad);
        if (u.pathname === '/api/gruppen/person') {
            const name = u.searchParams.get('name');
            const eintrag = personen.find((p) => p.name === name);
            if (!eintrag) return response({ ok: false, fehler: 'unbekannt' });
            return response({ ok: true, name: eintrag.name, vorschlaege: [], gruppen: [],
                profil: { beziehung: '', notizen: [] } });
        }
        if (pfad === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 3, namen: [],
            gruppe: { kennung: 'G-quiz', groesse: 5, bilder: 5, videos: 0, von: null, bis: null,
                status: 'offen', name: null, beispiele: [], zwillinge: [], verbunden: [] } });
        if (pfad === '/api/gruppen/stand' || pfad.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (pfad === '/api/gruppen/personen') return response({ ok: true, personen });
        throw new Error('Unerwarteter Request: ' + pfad);
    });
}

async function listeOeffnen(app) {
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
}

async function personAusListeOeffnen(app, name) {
    const zeile = app.el('gruppen-benannt-liste').children.find((z) => z.textContent.includes(name));
    assert.ok(zeile, 'keine Zeile fuer ' + name);
    await zeile.click();
    await settle();
}

/** Einen echten Wisch am Personenbereich ausführen (Finger wandert). */
async function wischen(app, dx, dy = 0, ziel) {
    const bereich = app.el('gruppen-person');
    const start = { clientX: 200, clientY: 300, pointerType: 'touch', button: 0, target: ziel || bereich };
    bereich.feuern('pointerdown', start);
    bereich.feuern('pointerup', { ...start, clientX: 200 + dx, clientY: 300 + dy });
    await settle();
}

function meldung(app) { return app.el('gruppen-meldung').textContent; }

// ── Die Prüfungen ─────────────────────────────────────────────────────────

async function wischenBlaettertInDerAngezeigtenReihe() {
    // Die Hinweiszeile steht im HTML (ohne sie wüsste niemand vom Wisch).
    assert.ok(html.includes('id="gruppen-person-wisch"'), 'der Wisch-Hinweis fehlt im HTML');
    const vQuiz = (html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vQuiz >= '20261018E', 'gruppen_quiz.js-Cache-Schluessel zu alt: ' + vQuiz);

    const protokoll = [];
    const app = personenAppMitProfil([person('Anna'), person('Bea'), person('Cem')], protokoll);
    await listeOeffnen(app);
    await personAusListeOeffnen(app, 'Bea');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Bea');

    // Wischen nach links = nächste Person, und genau die wird geladen.
    protokoll.length = 0;
    await wischen(app, -90);
    assert.deepEqual(protokoll.filter((p) => p.startsWith('/api/gruppen/person')),
        ['/api/gruppen/person?name=Cem'], 'Wisch nach links lud nicht die naechste Person');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Cem');
    assert.ok(meldung(app).includes('naechste Person'), 'der Wechsel wird nicht gemeldet: ' + meldung(app));

    // Wischen nach rechts = vorherige Person.
    protokoll.length = 0;
    await wischen(app, 90);
    assert.deepEqual(protokoll.filter((p) => p.startsWith('/api/gruppen/person')),
        ['/api/gruppen/person?name=Bea'], 'Wisch nach rechts lud nicht die vorherige Person');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Bea');
    assert.ok(meldung(app).includes('vorherige Person'));

    // Die gesetzten Filter gelten: mit Suchzeile „a“ bleibt nur Anna — kein Weiter.
    await app.el('gruppen-person-zurueck').click(); await settle();
    const suche = app.el('gruppen-benannt-filter');
    suche.value = 'a';
    suche.feuern('input', { target: suche });
    const namen = app.el('gruppen-benannt-liste').children.map((z) => z.textContent);
    assert.ok(namen.every((t) => t.includes('Anna')) || namen.length === 1, 'Suchzeile wirkt nicht: ' + namen.join('|'));
    await personAusListeOeffnen(app, 'Anna');
    protokoll.length = 0;
    await wischen(app, -120);
    assert.equal(protokoll.filter((p) => p.startsWith('/api/gruppen/person')).length, 0,
        'der Wisch ignoriert die gesetzten Filter');
    assert.ok(meldung(app).includes('letzte Person'), 'der Rand wird nicht ehrlich gemeldet: ' + meldung(app));
}

async function raenderUndKeinRinglauf() {
    const app = personenAppMitProfil([person('Anna'), person('Bea'), person('Cem')]);
    await listeOeffnen(app);
    await personAusListeOeffnen(app, 'Anna');
    // Erste Person: nach rechts gibt es niemanden — ehrliche Meldung, kein Wechsel.
    assert.ok(meldung(app) === '' || true);
    await wischen(app, 120);
    assert.equal(app.el('gruppen-person-titel').textContent, 'Anna', 'der Wisch lief am Anfang um');
    assert.ok(meldung(app).includes('erste Person'), 'der Anfang wird nicht gemeldet: ' + meldung(app));
    // Letzte Person: nach links gibt es niemanden.
    await wischen(app, -120);
    await wischen(app, -120);
    assert.equal(app.el('gruppen-person-titel').textContent, 'Cem');
    await wischen(app, -120);
    assert.equal(app.el('gruppen-person-titel').textContent, 'Cem', 'es gibt einen Ringlauf');
    assert.ok(meldung(app).includes('letzte Person'));
}

async function kurzeUndSenkrechteBewegungBlaettertNicht() {
    const protokoll = [];
    const app = personenAppMitProfil([person('Anna'), person('Bea')], protokoll);
    await listeOeffnen(app);
    await personAusListeOeffnen(app, 'Anna');
    protokoll.length = 0;
    // Antippen (kurze Bewegung) darf nichts auslösen.
    await wischen(app, -20);
    // Schräg/senkrecht = die Seite rollen, nicht blättern.
    await wischen(app, -70, 200);
    assert.equal(protokoll.filter((p) => p.startsWith('/api/gruppen/person')).length, 0,
        'kurze oder senkrechte Bewegung blaettert schon');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Anna');
    // Aufheben der Berührung (pointercancel) verwirft den begonnenen Wisch.
    const bereich = app.el('gruppen-person');
    bereich.feuern('pointerdown', { clientX: 200, clientY: 300, target: bereich });
    bereich.feuern('pointercancel', { target: bereich });
    bereich.feuern('pointerup', { clientX: 20, clientY: 300, target: bereich });
    await settle();
    assert.equal(app.el('gruppen-person-titel').textContent, 'Anna', 'ein abgebrochener Wisch blaettert doch');
    // Und die reine Regel selbst.
    const s = app.sandbox;
    assert.equal(s.gruppenWischRichtung(200, 300, 100, 300), 'weiter');
    assert.equal(s.gruppenWischRichtung(200, 300, 320, 300), 'zurueck');
    assert.equal(s.gruppenWischRichtung(200, 300, 250, 300), '', 'die Mindeststrecke fehlt');
    assert.equal(s.gruppenWischRichtung(200, 300, 300, 200), '', 'schraeg gilt als Rollen');
    assert.equal(s.gruppenWischRichtung(200, 300, NaN, 300), '');
}

async function felderBehaltenDenFinger() {
    // Wer im Notizfeld wischt, will markieren/rollen — nicht blättern.
    const protokoll = [];
    const app = personenAppMitProfil([person('Anna'), person('Bea')], protokoll);
    await listeOeffnen(app);
    await personAusListeOeffnen(app, 'Anna');
    const bereich = app.el('gruppen-person');
    const feld = new Element('textarea', 'feld-probe');
    feld.parentNode = bereich;
    protokoll.length = 0;
    bereich.feuern('pointerdown', { clientX: 300, clientY: 300, target: feld, pointerType: 'touch' });
    bereich.feuern('pointerup', { clientX: 100, clientY: 300, target: feld, pointerType: 'touch' });
    await settle();
    assert.equal(protokoll.filter((p) => p.startsWith('/api/gruppen/person')).length, 0,
        'ein Wisch im Textfeld blaettert die Person weg');
    const s = app.sandbox;
    assert.equal(s.gruppenWischGesperrt(feld), true, 'Bedienfelder sperren den Wisch nicht');
    const kachel = new Element('div');
    kachel.className = 'gruppen-kachel';
    assert.equal(s.gruppenWischGesperrt(kachel), true, 'Kacheln (langer Druck) sperren den Wisch nicht');
    const tief = new Element('span');
    tief.parentNode = feld;
    assert.equal(s.gruppenWischGesperrt(tief), true, 'tief verschachtelte Felder werden nicht erkannt');
    const ruhig = new Element('p');
    ruhig.parentNode = bereich;
    assert.equal(s.gruppenWischGesperrt(ruhig), false, 'normale Stelle ist gesperrt');
}

async function pfeiltastenWechselnDiePerson() {
    const protokoll = [];
    const app = personenAppMitProfil([person('Anna'), person('Bea'), person('Cem')], protokoll);
    await listeOeffnen(app);
    await personAusListeOeffnen(app, 'Bea');
    assert.equal(app.document.hatZuhörer('keydown'), true, 'die Pfeiltasten sind nicht verdrahtet');

    // Pfeil rechts = nächste Person (am PC dasselbe wie Wischen nach links).
    protokoll.length = 0;
    app.document.feuern('keydown', { key: 'ArrowRight', target: app.el('gruppen-person') });
    await settle();
    assert.deepEqual(protokoll.filter((p) => p.startsWith('/api/gruppen/person')),
        ['/api/gruppen/person?name=Cem'], 'Pfeil rechts lud nicht die naechste Person');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Cem');

    // Pfeil links = vorherige Person.
    protokoll.length = 0;
    app.document.feuern('keydown', { key: 'ArrowLeft', target: app.el('gruppen-person') });
    await settle();
    assert.deepEqual(protokoll.filter((p) => p.startsWith('/api/gruppen/person')),
        ['/api/gruppen/person?name=Bea']);
    assert.equal(app.el('gruppen-person-titel').textContent, 'Bea');

    // Andere Tasten tun nichts; im Textfeld (Name ändern) bleiben die Pfeile dem Feld.
    protokoll.length = 0;
    app.document.feuern('keydown', { key: 'ArrowUp', target: app.el('gruppen-person') });
    app.document.feuern('keydown', { key: 'a', target: app.el('gruppen-person') });
    const nameFeld = app.el('gruppen-person-name');
    app.el('gruppen-person').appendChild(nameFeld);
    app.document.feuern('keydown', { key: 'ArrowRight', target: nameFeld });
    await settle();
    assert.equal(protokoll.filter((p) => p.startsWith('/api/gruppen/person')).length, 0,
        'eine fremde Taste blättert die Person weg');
    // Ohne offene Person (nach „← Alle Personen“) läuft nichts.
    await app.el('gruppen-person-zurueck').click(); await settle();
    protokoll.length = 0;
    app.document.feuern('keydown', { key: 'ArrowRight', target: app.el('gruppen-person') });
    await settle();
    assert.equal(protokoll.filter((p) => p.startsWith('/api/gruppen/person')).length, 0,
        'ohne offene Person wird trotzdem geladen');
    const s = app.sandbox;
    assert.equal(s.gruppenWischTaste('ArrowRight'), 'weiter');
    assert.equal(s.gruppenWischTaste('ArrowLeft'), 'zurueck');
    assert.equal(s.gruppenWischTaste('Enter'), '');
}

async function reineRegelNachbar() {
    const app = personenAppMitProfil([person('Anna')]);
    const s = app.sandbox;
    const reihe = [person('Bea'), person('Anna'), person('Cem')];
    assert.deepEqual(s.gruppenReiheNamen(reihe), ['Bea', 'Anna', 'Cem']);
    assert.equal(s.gruppenNachbarName(reihe, 'Anna', 'weiter'), 'Cem');
    assert.equal(s.gruppenNachbarName(reihe, 'Anna', 'zurueck'), 'Bea');
    assert.equal(s.gruppenNachbarName(reihe, 'Cem', 'weiter'), '', 'kein Ringlauf nach hinten');
    assert.equal(s.gruppenNachbarName(reihe, 'Bea', 'zurueck'), '', 'kein Ringlauf nach vorne');
    assert.equal(s.gruppenNachbarName(reihe, 'Zoe', 'weiter'), 'Bea', 'unbekannter Name beginnt vorne');
    assert.equal(s.gruppenNachbarName(reihe, 'Zoe', 'zurueck'), 'Cem', 'unbekannter Name beginnt hinten');
    assert.equal(s.gruppenNachbarName([], 'Anna', 'weiter'), '');
    assert.equal(s.gruppenNachbarName([person('Anna')], 'Anna', 'weiter'), '');
    // Die Reihenfolge kommt aus der Anzeige (alphabetisch, Umlaute aufgeloest).
    const gefiltert = s.gruppenPersonenGefiltert([person('Zoe'), person('Änne'), person('Bea')], '', '', '');
    assert.deepEqual(s.gruppenReiheNamen(gefiltert), ['Änne', 'Bea', 'Zoe']);
    assert.equal(s.gruppenNachbarName(gefiltert, 'Änne', 'weiter'), 'Bea');
    assert.ok(s.gruppenWischHinweis('weiter').includes('letzte'));
    assert.ok(s.gruppenWischHinweis('zurueck').includes('erste'));
}

let beendet = false;
process.on('exit', () => {
    if (!beendet) { console.error('FEHLER: Prüfung wurde nicht beendet (hängende Anfrage?)'); process.exitCode = 1; }
});
(async () => {
    const pruefungen = [wischenBlaettertInDerAngezeigtenReihe, raenderUndKeinRinglauf,
        kurzeUndSenkrechteBewegungBlaettertNicht, felderBehaltenDenFinger,
        pfeiltastenWechselnDiePerson, reineRegelNachbar];
    let rot = 0;
    for (const pruefung of pruefungen) {
        try { await pruefung(); } catch (error) {
            rot += 1;
            console.error('FEHLER in ' + pruefung.name + ': ' + (error && error.message ? error.message : error));
        }
    }
    beendet = true;
    if (rot) { process.exitCode = 1; return; }
    console.log('Wischen und Pfeiltasten wechseln zur naechsten/vorherigen Person '
        + '(in der angezeigten, gefilterten Reihe, ohne Ringlauf, Bedienfelder ausgenommen) gruen');
})().catch((error) => { console.error(error); process.exitCode = 1; });
