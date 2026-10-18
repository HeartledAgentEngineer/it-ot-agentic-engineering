// Runtime-Vertrag für die Personenauswahl als alphabetische Liste (S8, 18.10.2026,
// To-do Punkt 10): sortiert, Suchzeile, Sprungmarken — und die Vorschlags-Zahl
// steht nicht mehr in der Zeile. Die echten UI-Handler laufen in einer kleinen
// DOM-Umgebung; nur HTTP-Antworten sind kontrollierte Attrappen.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sourcePath = process.argv[2] && process.argv[2].endsWith('gruppen_quiz.js')
    ? process.argv[2] : path.join(__dirname, '..', 'gruppen_quiz.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'style.css'), 'utf8');

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
    /** Der echte Browser rollt hierhin — in der Attrappe wird der Aufruf festgehalten. */
    scrollIntoView(optionen) { Element.rollAufrufe.push({ ziel: this, optionen }); }
    querySelectorAll() { return []; }
    async click() {
        if (this.disabled) return;
        const calls = (this.listeners.get('click') || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {} }));
        await Promise.all(calls);
    }
}

function person(name, extra = {}) {
    return { name, gesichter: 5, vorschlaege: 1, beispiel: null,
        gruppen: [{ kennung: 'G-' + name, groesse: 5, von: null, bis: null }], ...extra };
}

function harness(fetchImpl) {
    const elements = new Map();
    Element.registry = elements;
    Element.rollAufrufe = [];
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
        addEventListener() {},
    };
    const sandbox = {
        document, fetch: fetchImpl, location: { origin: 'http://localhost' },
        URL: { createObjectURL() { return 'blob:test'; }, revokeObjectURL() {} },
        setTimeout, clearTimeout, console, Date, Map, Set, Promise, encodeURIComponent,
    };
    vm.runInNewContext(source, sandbox, { filename: sourcePath });
    return { elements, el: (id) => document.getElementById(id) };
}

async function settle() {
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
}

function response(value) { return { json: async () => value }; }

/** Attrappe mit einer festen Personenliste; /naechste und /stand sind Pflichtwege. */
function personenApp(personen) {
    return harness(async (url) => {
        const path = new URL(url).pathname + new URL(url).search;
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 3, namen: [],
            gruppe: { kennung: 'G-quiz', groesse: 5, bilder: 5, videos: 0, von: null, bis: null,
                status: 'offen', name: null, beispiele: [], zwillinge: [], verbunden: [] } });
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (path === '/api/gruppen/personen') return response({ ok: true, personen });
        throw new Error('Unerwarteter Request: ' + path);
    });
}

async function listeOeffnen(app) {
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
}

function zeilenTexte(app) {
    return app.el('gruppen-benannt-liste').children.map((z) => z.textContent);
}

function springe(app, marke) {
    const knopf = app.el('gruppen-benannt-sprung').children.find((k) => k.textContent === marke);
    assert.ok(knopf, 'keine Sprungmarke ' + marke);
    knopf.click();
    return knopf;
}

// ── Die Prüfungen ─────────────────────────────────────────────────────────

async function alphabetischSortiertMitUmlauten() {
    // Der Server liefert ungeordnet; angezeigt wird alphabetisch, Umlaute wie im
    // Telefonbuch aufgeloest (Öztürk unter O), Ziffern/Zeichen am Ende.
    const app = personenApp([
        person('Tim'), person('Zoe'), person('Öztürk'), person('anna'), person('Anna'),
        person('9er-Club'), person('Özkan'),
    ]);
    await listeOeffnen(app);
    const texte = zeilenTexte(app);
    assert.equal(texte.length, 7);
    // Gleiche Schluessel behalten ihre Ordnung (stabil) — „anna" stand vor „Anna".
    assert.ok(texte[0].includes('nna') && texte[0].includes('anna'), 'erwartet „anna" zuerst: ' + texte[0]);
    assert.ok(texte[1].includes('nna') && texte[1].includes('Anna'), 'dann „Anna": ' + texte[1]);
    assert.ok(texte[2].includes('Özkan'));
    assert.ok(texte[3].includes('Öztürk'));
    assert.ok(texte[4].includes('Tim'));
    assert.ok(texte[5].includes('Zoe'));
    assert.ok(texte[6].includes('9er-Club'), 'Ziffern am Ende: ' + texte[6]);
    // Die Reihenfolge der Server-Antwort bleibt unberuehrt (nur die Anzeige sortiert).
    assert.ok(app.el('gruppen-benannt-info').textContent.includes('alphabetisch'));
}

function nurBenannteAnsichtWirdGerollt() {
    // Der Rollbereich gilt NUR fuer den Reiter „Benannt": die Gruppenuebersicht
    // traegt dieselbe Klassenkette und bleibt, wie Sebastian sie mag.
    assert.ok(/\.gruppen-benannt-ansicht\s+\.gruppen-benannt-liste\s*\{[^}]*max-height/.test(css),
        'kein eigener Rollbereich fuer die Personenauswahl');
    assert.equal(/^\.gruppen-benannt-liste\s*\{[^}]*max-height/m.test(css), false,
        'der Rollbereich trifft auch die Gruppenuebersicht');
    assert.ok(/\.gruppen-sprung\s*\{[^}]*flex-wrap/.test(css), 'Sprungleiste hat keine Regel');
    assert.ok(/\.gruppen-sprung\[hidden\]\s*\{\s*display:\s*none/.test(css), 'Sprungleiste bleibt trotz hidden sichtbar');
    assert.ok(/\.gruppen-sprung-knopf\s*\{/.test(css), 'Sprungmarken haben keine Regel');
    assert.ok(/\.gruppen-sprung-ziel\s*\{/.test(css), 'angesprungener Eintrag wird nicht hervorgehoben');
    assert.ok(html.includes('id="gruppen-benannt-sprung"'), 'Sprungleiste fehlt im HTML');
    const vQuiz = (html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vQuiz >= '20261018B', 'gruppen_quiz.js-Cache-Schluessel zu alt: ' + vQuiz);
    const vCss = (html.match(/style\.css\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vCss >= '20261018B', 'style.css-Cache-Schluessel zu alt: ' + vCss);
}

async function sprungmarkenNurVorhandeneUndZumZiel() {
    const app = personenApp([person('Tim'), person('Anna'), person('Bea'), person('9er-Club'), person('Zoe')]);
    await listeOeffnen(app);
    const leiste = app.el('gruppen-benannt-sprung');
    const marken = leiste.children.map((k) => k.textContent);
    assert.deepEqual(marken, ['A', 'B', 'T', 'Z', '#'], 'Marken: ' + marken.join(''));
    assert.equal(leiste.hidden, false);
    assert.ok(leiste.children.every((k) => k.classList.contains('gruppen-sprung-knopf')));

    Element.rollAufrufe.length = 0;
    springe(app, 'T');
    const liste = app.el('gruppen-benannt-liste');
    const ziel = liste.children[2];
    assert.ok(ziel.textContent.includes('Tim'), 'Sprungziel ist nicht der erste T-Eintrag');
    assert.ok(ziel.classList.contains('gruppen-sprung-ziel'));
    assert.equal(liste.children.filter((z) => z.classList.contains('gruppen-sprung-ziel')).length, 1,
        'genau ein Eintrag ist markiert');
    assert.equal(Element.rollAufrufe.length, 1, 'es wird nicht zum Ziel gerollt');
    assert.equal(Element.rollAufrufe[0].ziel, ziel);
    assert.equal(Element.rollAufrufe[0].optionen.block, 'start');

    springe(app, '#');
    assert.ok(liste.children[4].classList.contains('gruppen-sprung-ziel'), '# springt zum letzten Eintrag');
    assert.equal(liste.children.filter((z) => z.classList.contains('gruppen-sprung-ziel')).length, 1,
        'die vorige Marke bleibt stehen');
    // Die Sprungleiste waehlt nichts aus: die Liste bleibt unveraendert.
    assert.equal(liste.children.length, 5);
}

async function einBuchstabeOhneLeiste() {
    // Bei einem einzigen Buchstaben waere die Leiste nur Laerm.
    const app = personenApp([person('Anna'), person('Anton')]);
    await listeOeffnen(app);
    assert.equal(app.el('gruppen-benannt-sprung').hidden, true);
    assert.deepEqual(app.el('gruppen-benannt-sprung').children.map((k) => k.textContent), ['A']);
    assert.equal(app.el('gruppen-benannt-liste').children.length, 2);
}

async function vorschlaegeStehenNichtMehrInDerZeile() {
    const app = personenApp([person('Anna', { vorschlaege: 4, gesichter: 130, erinnerungen: 2 }),
        person('Bea', { vorschlaege: 3 })]);
    await listeOeffnen(app);
    const texte = zeilenTexte(app);
    assert.equal(texte.some((t) => t.includes('Vorschläge')), false,
        'die Vorschlags-Zahl steht weiter in der Zeile: ' + texte.join(' | '));
    assert.ok(texte[0].includes('130 Gesichter'));
    assert.ok(texte[0].includes('2 Erinnerungen'));
}

async function suchzeileFiltertUndSortiertNeu() {
    const app = personenApp([person('Tim'), person('Anna'), person('Bea')]);
    await listeOeffnen(app);
    assert.equal(zeilenTexte(app).length, 3);
    const feld = app.el('gruppen-benannt-filter');
    feld.value = 'ti';
    (feld.listeners.get('input') || []).forEach((fn) => fn({ target: feld }));
    assert.equal(zeilenTexte(app).length, 1, 'Suchzeile filtert weiterhin');
    assert.ok(zeilenTexte(app)[0].includes('Tim'));
    assert.deepEqual(app.el('gruppen-benannt-sprung').children.map((k) => k.textContent), ['T']);
    assert.equal(app.el('gruppen-benannt-sprung').hidden, true, 'eine Marke ist keine Sprungleiste');
    assert.ok(app.el('gruppen-benannt-info').textContent.includes('1 Person'));
    feld.value = '';
    (feld.listeners.get('input') || []).forEach((fn) => fn({ target: feld }));
    assert.deepEqual(zeilenTexte(app).map((t) => (t.match(/Anna|Bea|Tim/) || [''])[0]), ['Anna', 'Bea', 'Tim']);
}

let beendet = false;
process.on('exit', () => {
    if (!beendet) { console.error('FEHLER: Prüfung wurde nicht beendet (hängende Anfrage?)'); process.exitCode = 1; }
});
(async () => {
    const pruefungen = [alphabetischSortiertMitUmlauten, nurBenannteAnsichtWirdGerollt,
        sprungmarkenNurVorhandeneUndZumZiel, einBuchstabeOhneLeiste,
        vorschlaegeStehenNichtMehrInDerZeile, suchzeileFiltertUndSortiertNeu];
    let rot = 0;
    for (const pruefung of pruefungen) {
        try { await pruefung(); } catch (error) {
            rot += 1;
            console.error('FEHLER in ' + pruefung.name + ': ' + (error && error.message ? error.message : error));
        }
    }
    beendet = true;
    if (rot) { process.exitCode = 1; return; }
    console.log('Personenauswahl: alphabetisch sortiert (Umlaute aufgeloest, Ziffern am Ende), '
        + 'Sprungmarken nur fuer vorhandene Buchstaben mit Markierung und Rollen, '
        + 'Vorschlags-Zahl aus der Zeile entfernt, Suchzeile und Gruppenfilter unveraendert grün');
})().catch((error) => { console.error(error); process.exitCode = 1; });
