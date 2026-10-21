// Zeitgrenze für lesende Abrufe im Fenster „Personen benennen“ (20.10.2026).
// Aufruf: node tests/test_gruppen_zeitgrenze.js gruppen_quiz.js
// Die echten UI-Handler laufen in einer kleinen DOM-Umgebung; Timer und
// HTTP-Antworten sind kontrollierte Attrappen (Timer werden von Hand ausgelöst).
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
    querySelectorAll() { return []; }
    async click() {
        if (this.disabled) return;
        const calls = (this.listeners.get('click') || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {} }));
        await Promise.all(calls);
    }
}

function gruppe(kennung, status = 'offen') {
    return { kennung, groesse: 7, bilder: 6, videos: 1, von: '2018-01-01', bis: '2024-12-31',
        status, name: null, beispiele: [], zwillinge: [], verbunden: [] };
}

/** Fake-Timer: setTimeout merkt sich Rückruf und Dauer, ausgelöst wird von Hand. */
function harness(fetchImpl) {
    const elements = new Map();
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
        addEventListener() {},
    };
    const timer = [];
    const sandbox = {
        document, fetch: fetchImpl, location: { origin: 'http://localhost' },
        URL: { createObjectURL() { return 'blob:test'; }, revokeObjectURL() {} },
        setTimeout(fn, ms) { const t = { fn, ms, id: timer.length + 1, geloescht: false }; timer.push(t); return t.id; },
        clearTimeout(id) { const t = timer.find((x) => x.id === id); if (t) t.geloescht = true; },
        AbortController, console, Date, Map, Set, Promise, encodeURIComponent,
    };
    vm.runInNewContext(source, sandbox, { filename: sourcePath });
    const grenzen = () => timer.filter((t) => t.ms === 20000);
    const ablaufen = () => {
        const t = grenzen().filter((x) => !x.geloescht).pop();
        assert.ok(t, 'keine offene Zeitgrenze');
        t.geloescht = true;
        t.fn();
    };
    return { elements, el: (id) => document.getElementById(id), timer, grenzen, ablaufen };
}

async function settle() {
    for (let i = 0; i < 4; i++) await new Promise((resolve) => setImmediate(resolve));
}

function response(value) { return { json: async () => value }; }

/** fetch, der hängt, bis das Signal abbricht (wie ein echter Browser-fetch). */
function haengt(options, aufrufe) {
    aufrufe.push(options);
    return new Promise((_ok, fehler) => {
        if (options && options.signal) options.signal.addEventListener('abort', () => fehler(new Error('AbortError')));
    });
}

function grundantworten(p) {
    if (p === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
        gruppe: { ...gruppe('G-offen'), war_spaeter: false }, namen: [] });
    if (p === '/api/gruppen/stand') return response({ ok: true, gruppen: 1, benannt: 0, gesichter: 7 });
    if (p.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
    return null;
}

function listeOk(seite = 1) {
    return response({ ok: true, status: 'offen', gesamt: 1, seiten: 1, seite, je_seite: 24,
        gruppen: [{ ...gruppe('G-offen') }] });
}

const pfadVon = (url) => new URL(url).pathname + new URL(url).search;

/** Gruppenübersicht: hängender Abruf -> Zeitgrenze -> Meldung + „Erneut versuchen“ -> Erfolg. */
async function listeZeitgrenzeUndErneut() {
    const listeAufrufe = [];
    let nummer = 0;
    const app = harness(async (url, options = {}) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p.startsWith('/api/gruppen/liste')) {
            nummer += 1;
            if (nummer === 1) return haengt(options, listeAufrufe);
            return listeOk();
        }
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    assert.equal(app.el('gruppen-liste-meldung').textContent, '… lädt');
    assert.equal(app.grenzen().length >= 1, true, 'GET bekommt eine Zeitgrenze von 20 s');
    assert.ok(listeAufrufe[0].signal, 'der Abruf trägt ein Abbruch-Signal');

    app.ablaufen(); await settle();
    const meldung = app.el('gruppen-liste-meldung');
    assert.equal(listeAufrufe[0].signal.aborted, true, 'hängender Abruf wird abgebrochen');
    assert.ok(meldung.textContent.includes('Server antwortet nicht (nach 20 s) – bitte erneut versuchen.'), meldung.textContent);
    assert.equal(meldung.textContent.includes('… lädt'), false, 'keine Endlos-„lädt“-Anzeige');
    assert.ok(meldung.classList.contains('fehler'));
    const knopf = app.elements.get('gruppen-liste-erneut');
    assert.ok(knopf && meldung.children.includes(knopf), 'Erneut-Knopf in der Meldung');
    assert.equal(knopf.textContent, 'Erneut versuchen');

    await knopf.click(); await settle();
    assert.equal(nummer, 2, 'derselbe Ladevorgang läuft erneut');
    assert.equal(meldung.textContent, '');
    assert.equal(meldung.children.length, 0, 'Knopf nach Erfolg weg');
    assert.equal(app.el('gruppen-liste').children.length, 1);
    assert.ok(app.grenzen().every((t) => t.geloescht), 'Zeitgrenzen sind nach Antwort aufgeräumt');
}

/** Netzfehler (fetch wirft) wird übersetzt und bietet ebenfalls „Erneut versuchen“. */
async function listeNetzfehler() {
    let nummer = 0;
    const app = harness(async (url) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p.startsWith('/api/gruppen/liste')) {
            nummer += 1;
            if (nummer === 1) throw new TypeError('Failed to fetch');
            return listeOk();
        }
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    const meldung = app.el('gruppen-liste-meldung');
    assert.ok(meldung.textContent.includes('Keine Verbindung zum Agenten.'), meldung.textContent);
    const knopf = app.elements.get('gruppen-liste-erneut');
    assert.ok(knopf, 'Erneut-Knopf bei Netzfehler');
    await knopf.click(); await settle();
    assert.equal(nummer, 2);
    assert.equal(app.el('gruppen-liste').children.length, 1);
}

/** Fehlerantwort des Servers (kein Verbindungsproblem): Meldung, aber kein Erneut-Knopf. */
async function listeServerfehlerOhneKnopf() {
    const app = harness(async (url) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p.startsWith('/api/gruppen/liste')) return response({ ok: false, fehler: 'Datenbank gesperrt' });
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    const meldung = app.el('gruppen-liste-meldung');
    assert.ok(meldung.textContent.includes('Datenbank gesperrt'));
    assert.equal(meldung.children.length, 0);
    assert.equal(app.elements.has('gruppen-liste-erneut'), false);
}

/** Schreibende Abrufe: keine Zeitgrenze, kein Signal – auch wenn die Antwort lange dauert. */
async function postOhneZeitgrenze() {
    let postOptionen = null;
    let postFertig;
    const app = harness(async (url, options = {}) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p.startsWith('/api/gruppen/liste')) return listeOk();
        if (p === '/api/gruppen/rueckgaengig') {
            postOptionen = options;
            return new Promise((resolve) => {
                postFertig = () => resolve(response({ ok: true, zurueckgenommen: { art: 'offen' } }));
            });
        }
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    const vorher = app.timer.length;
    const klick = app.el('gruppen-liste-undo').click();
    await settle();
    assert.ok(postOptionen, 'POST wurde abgeschickt');
    assert.equal(postOptionen.method, 'POST');
    assert.equal(postOptionen.signal, undefined, 'POST trägt kein Abbruch-Signal');
    assert.equal(app.timer.slice(vorher).some((t) => t.ms === 20000), false, 'POST startet keine Zeitgrenze');
    postFertig(); await klick; await settle();
}

/** Liste „Benannt“: Zeitgrenze -> Meldung + Erneut-Knopf -> Erfolg zeigt die Personen. */
async function benanntZeitgrenzeUndErneut() {
    const aufrufe = [];
    let nummer = 0;
    const app = harness(async (url, options = {}) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p === '/api/gruppen/personen') {
            nummer += 1;
            if (nummer === 1) return haengt(options, aufrufe);
            return response({ ok: true, personen: [{ name: 'Anna', gesichter: 3, bilder: 2, videos: 0 }] });
        }
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    const info = app.el('gruppen-benannt-info');
    assert.equal(info.textContent, '… lädt');
    app.ablaufen(); await settle();
    assert.equal(aufrufe[0].signal.aborted, true);
    assert.ok(info.textContent.includes('Server antwortet nicht (nach 20 s)'), info.textContent);
    assert.equal(info.textContent.includes('… lädt'), false);
    const knopf = app.elements.get('gruppen-benannt-erneut');
    assert.ok(knopf && info.children.includes(knopf), 'Erneut-Knopf an der Benannt-Info');
    await knopf.click(); await settle();
    assert.equal(nummer, 2);
    assert.equal(info.children.length, 0);
    assert.equal(info.textContent.includes('Server antwortet nicht'), false);
    assert.equal(app.el('gruppen-benannt-liste').children.length, 1);
}

/** Netzfehler in „Benannt“: Meldung bleibt stehen (wird nicht von personenZeigen überschrieben). */
async function benanntNetzfehler() {
    const app = harness(async (url) => {
        const p = pfadVon(url);
        const g = grundantworten(p);
        if (g) return g;
        if (p === '/api/gruppen/personen') throw new TypeError('Failed to fetch');
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    const info = app.el('gruppen-benannt-info');
    assert.ok(info.textContent.includes('Keine Verbindung zum Agenten.'), info.textContent);
    assert.ok(app.elements.get('gruppen-benannt-erneut'));
}

/** Quiz-Karte (laden): Zeitgrenze zeigt Fehler statt Endlos-„lädt“. */
async function quizKarteKeinEndlosLaden() {
    const aufrufe = [];
    const app = harness(async (url, options = {}) => {
        const p = pfadVon(url);
        if (p === '/api/gruppen/naechste') return haengt(options, aufrufe);
        if (p === '/api/gruppen/stand') return response({ ok: true });
        if (p.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        throw new Error('Unerwarteter Request: ' + p);
    });
    await app.el('gruppen-btn').click(); await settle();
    assert.equal(app.el('gruppen-meldung').textContent, '… lädt');
    app.ablaufen(); await settle();
    const text = app.el('gruppen-meldung').textContent;
    assert.ok(text.includes('Server antwortet nicht'), text);
    assert.equal(text.includes('… lädt'), false);
}

function quelltextVertrag() {
    const von = source.indexOf('async function vorschauLaden');
    const bis = source.indexOf('async function vollbildOeffnen');
    assert.ok(von > 0 && bis > von);
    const vorschau = source.slice(von, bis);
    assert.equal(/AbortController|setTimeout|signal/.test(vorschau), false, 'Vorschaubilder bleiben ohne Zeitgrenze');
    assert.ok(/GRUPPEN_ABRUF_ZEITGRENZE_MS = 20000/.test(source), 'Standard-Zeitgrenze 20 s');
    const version = /gruppen_quiz\.js\?v=(\d{8}[A-Z])/.exec(html);
    assert.ok(version && version[1] >= '20261020D', 'Cache-Version hochgezählt');
}

(async () => {
    quelltextVertrag();
    await listeZeitgrenzeUndErneut();
    await listeNetzfehler();
    await listeServerfehlerOhneKnopf();
    await postOhneZeitgrenze();
    await benanntZeitgrenzeUndErneut();
    await benanntNetzfehler();
    await quizKarteKeinEndlosLaden();
    console.log('test_gruppen_zeitgrenze: OK');
})().catch((e) => { console.error(e); process.exit(1); });
