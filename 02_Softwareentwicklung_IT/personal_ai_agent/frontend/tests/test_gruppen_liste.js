// Runtime-Vertrag für die Gruppenübersicht. Die echten UI-Handler laufen in
// einer kleinen DOM-Umgebung; nur HTTP-Antworten sind kontrollierte Attrappen.
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
    querySelectorAll(selector) {
        const wanted = selector.startsWith('.') ? selector.slice(1).split('.').at(-1) : '';
        const found = [];
        const visit = (node) => node.children.forEach((child) => {
            if (wanted && child.classList.contains(wanted)) found.push(child);
            visit(child);
        });
        visit(this);
        return found;
    }
    async click() {
        if (this.disabled) return;
        const calls = (this.listeners.get('click') || []).map((fn) => fn({ target: this, preventDefault() {}, stopPropagation() {} }));
        await Promise.all(calls);
    }
}

function gruppe(kennung, status = 'offen') {
    return { kennung, groesse: 7, bilder: 6, videos: 1, von: '2018-01-01', bis: '2024-12-31',
        status, name: status === 'benannt' ? 'Testname' : null, beispiele: [], zwillinge: [], verbunden: [] };
}

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

async function overviewRuntime() {
    const calls = [];
    const state = { status: 'offen', page: 1 };
    const app = harness(async (url, options = {}) => {
        const path = new URL(url).pathname + new URL(url).search;
        calls.push({ path, options });
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
            gruppe: { ...gruppe('G-offen'), war_spaeter: false }, namen: [] });
        if (path === '/api/gruppen/stand') return response({ ok: true, gruppen: 1, benannt: 0, gesichter: 7 });
        if (path.startsWith('/api/gruppen/liste')) {
            const query = new URL(url).searchParams;
            state.status = query.get('status'); state.page = Number(query.get('seite'));
            return response({ ok: true, status: state.status, gesamt: 1, seiten: 1,
                seite: state.page, je_seite: 24, gruppen: [{ ...gruppe('G-' + state.status, state.status) }] });
        }
        if (path.startsWith('/api/gruppen/detail/')) return response({ ok: true, fertig: false, offen: 1,
            namen: [], gruppe: { ...gruppe('G-spaeter', 'spaeter'), war_spaeter: true } });
        if (path === '/api/gruppen/antwort') return response({ ok: true, gespeichert: { kennung: 'G-spaeter', art: 'offen' } });
        if (path === '/api/gruppen/rueckgaengig') return response({ ok: true, zurueckgenommen: { art: 'offen' } });
        if (path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        throw new Error('Unerwarteter Request: ' + path);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    assert.ok(calls.some((c) => c.path === '/api/gruppen/liste?status=offen&seite=1&je_seite=24'));
    assert.equal(app.el('gruppen-liste').children.length, 1);

    await app.el('gruppen-liste-status-spaeter').click(); await settle();
    assert.equal(state.status, 'spaeter');
    await app.el('gruppen-liste-zeile-G-spaeter').click(); await settle();
    assert.ok(calls.some((c) => c.path === '/api/gruppen/detail/G-spaeter'));
    assert.equal(app.el('gruppen-meta').textContent.includes('zurückgestellt'), true);
    await app.el('gruppen-detail-zurueck').click(); await settle();
    assert.equal(state.status, 'spaeter');
    assert.equal(state.page, 1);
    assert.ok(calls.filter((c) => c.path.includes('/api/gruppen/liste?status=spaeter')).length >= 2);

    await app.el('gruppen-liste-reaktivieren-G-spaeter').click(); await settle();
    const write = calls.find((c) => c.path === '/api/gruppen/antwort');
    assert.equal(JSON.parse(write.options.body).art, 'offen');
    assert.equal(JSON.parse(write.options.body).kennung, 'G-spaeter');
    assert.ok(calls.some((c) => c.path === '/api/gruppen/liste?status=spaeter&seite=1&je_seite=24'));
    assert.ok(app.el('gruppen-liste-meldung').textContent.includes('Zurück zu Offen'));
    assert.equal(app.el('gruppen-liste').children[0].textContent.includes('Testname'), false);
}

async function staleResponseAfterFilterAndClose() {
    let spaeterAufloesen;
    let spaeterStart;
    const begonnen = new Promise((resolve) => { spaeterStart = resolve; });
    const app = harness(async (url) => {
        const path = new URL(url).pathname + new URL(url).search;
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
            gruppe: { ...gruppe('G-offen'), war_spaeter: false }, namen: [] });
        if (path === '/api/gruppen/stand') return response({ ok: true });
        if (path === '/api/gruppen/suche?q=') return response({ ok: true, treffer: [] });
        if (path.includes('/api/gruppen/liste?status=spaeter')) {
            spaeterStart();
            return new Promise((resolve) => { spaeterAufloesen = () => resolve(response({ ok: true, status: 'spaeter',
                gruppen: [{ ...gruppe('G-alt', 'spaeter') }], gesamt: 1, seite: 1, seiten: 1, je_seite: 24 })); });
        }
        if (path.includes('/api/gruppen/liste?status=offen')) return response({ ok: true, status: 'offen',
            gruppen: [{ ...gruppe('G-neu') }], gesamt: 1, seite: 1, seiten: 1, je_seite: 24 });
        throw new Error('Unerwarteter Request: ' + path);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-status-spaeter').click();
    await begonnen;
    await app.el('gruppen-liste-status-offen').click(); await settle();
    assert.equal(app.el('gruppen-liste').children[0].id, 'gruppen-liste-zeile-G-neu');
    spaeterAufloesen(); await settle();
    assert.equal(app.el('gruppen-liste').children[0].id, 'gruppen-liste-zeile-G-neu');

    await app.el('gruppen-liste-status-spaeter').click();
    await begonnen;
    await app.el('gruppen-close').click();
    spaeterAufloesen(); await settle();
    assert.equal(app.el('gruppen-sheet').hidden, true);
}

async function paginationRuntime() {
    const calls = [];
    const app = harness(async (url) => {
        const parsed = new URL(url);
        const path = parsed.pathname + parsed.search;
        calls.push(path);
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 25,
            gruppe: { ...gruppe('G-start'), war_spaeter: false }, namen: [] });
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (parsed.pathname === '/api/gruppen/liste') {
            const page = Number(parsed.searchParams.get('seite'));
            const gruppen = page === 1
                ? Array.from({ length: 24 }, (_, n) => gruppe('G-' + String(n).padStart(2, '0')))
                : [gruppe('G-24')];
            return response({ ok: true, status: 'offen', gesamt: 25, seiten: 2,
                seite: page, je_seite: 24, gruppen });
        }
        throw new Error('Unerwarteter Request: ' + path);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    assert.equal(app.el('gruppen-liste').children.length, 24);
    await app.el('gruppen-liste-weiter').click(); await settle();
    assert.ok(calls.includes('/api/gruppen/liste?status=offen&seite=2&je_seite=24'));
    assert.equal(app.el('gruppen-liste').children.length, 1);
    assert.equal(app.el('gruppen-liste').children[0].id, 'gruppen-liste-zeile-G-24');
}

async function staleDetailAfterClose() {
    let detailAufloesen;
    let detailStart;
    const begonnen = new Promise((resolve) => { detailStart = resolve; });
    const app = harness(async (url) => {
        const path = new URL(url).pathname + new URL(url).search;
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
            gruppe: { ...gruppe('G-start'), war_spaeter: false }, namen: [] });
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true });
        if (path.startsWith('/api/gruppen/liste')) return response({ ok: true, status: 'offen',
            gruppen: [{ ...gruppe('G-detail') }], gesamt: 1, seite: 1, seiten: 1, je_seite: 24 });
        if (path === '/api/gruppen/detail/G-detail') {
            detailStart();
            return new Promise((resolve) => { detailAufloesen = () => resolve(response({ ok: true,
                fertig: false, offen: 1, namen: [], gruppe: { ...gruppe('G-detail'), war_spaeter: false } })); });
        }
        throw new Error('Unerwarteter Request: ' + path);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    app.el('gruppen-liste-zeile-G-detail').click();
    await begonnen;
    await app.el('gruppen-close').click();
    detailAufloesen(); await settle();
    assert.equal(app.el('gruppen-sheet').hidden, true);
}

async function failedDetailDoesNotShowPreviousGroup() {
    const app = harness(async (url) => {
        const path = new URL(url).pathname + new URL(url).search;
        if (path === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
            gruppe: { ...gruppe('G-vorher'), war_spaeter: false }, namen: [] });
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true });
        if (path.startsWith('/api/gruppen/liste')) return response({ ok: true, status: 'offen',
            gruppen: [{ ...gruppe('G-fehlt') }], gesamt: 1, seite: 1, seiten: 1, je_seite: 24 });
        if (path === '/api/gruppen/detail/G-fehlt') return response({ ok: false, fehler: 'Gruppe fehlt.' });
        throw new Error('Unerwarteter Request: ' + path);
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-fehlt').click(); await settle();
    assert.equal(app.el('gruppen-liste-ansicht').hidden, false);
    assert.equal(app.el('gruppen-karte').hidden, true);
    assert.ok(app.el('gruppen-liste-meldung').textContent.includes('Gruppe fehlt.'));
}

// ── Ergebnisprüfung Runde 1 – Behebungen ─────────────────────────────────

/** Gemeinsame Attrappe: /naechste (wahlweise verzögert), Liste, Detail, Antwort, Gesichter. */
function pruefApp({ naechste, antwort, detailKennung = 'G-detail', seiten = 1, calls }) {
    return harness(async (url, options = {}) => {
        const parsed = new URL(url);
        const path = parsed.pathname + parsed.search;
        calls.push({ path, options });
        if (path === '/api/gruppen/naechste') return naechste();
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (parsed.pathname === '/api/gruppen/liste') {
            const seite = Number(parsed.searchParams.get('seite'));
            return response({ ok: true, status: parsed.searchParams.get('status'), gesamt: 30, seiten,
                seite, je_seite: 24, gruppen: [{ ...gruppe(detailKennung, 'spaeter') }] });
        }
        if (path === '/api/gruppen/detail/' + detailKennung) return response({ ok: true, fertig: false, offen: 3,
            namen: [], gruppe: { ...gruppe(detailKennung, 'spaeter'), war_spaeter: true } });
        if (path === '/api/gruppen/antwort') return response(antwort(JSON.parse(options.body)));
        if (path.startsWith('/api/gruppen/gesichter')) return response({ ok: true, seite: 1, seiten: 1, gesamt: 0, gesichter: [] });
        throw new Error('Unerwarteter Request: ' + path);
    });
}

function quizGruppe() {
    return response({ ok: true, fertig: false, offen: 9, namen: [],
        gruppe: { ...gruppe('G-quiz'), war_spaeter: false } });
}

async function lateQuizAnswerDoesNotOverwriteDetail() {
    // Befund 1: eine verspätete /naechste-Antwort darf weder die Oberfläche
    // ändern noch zustand.gruppe umsetzen (sonst trifft „Später“ die falsche Gruppe).
    const calls = [];
    let aufloesen;
    const app = pruefApp({
        calls,
        naechste: () => new Promise((resolve) => { aufloesen = () => resolve(quizGruppe()); }),
        antwort: (koerper) => ({ ok: true, fertig: false, offen: 2, namen: [],
            gespeichert: { kennung: koerper.kennung, art: koerper.art },
            gruppe: { ...gruppe('G-3'), war_spaeter: false } }),
    });
    await app.el('gruppen-btn').click(); await settle();           // /naechste hängt
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-detail').click(); await settle();
    const nummerVorher = app.el('gruppen-nummer').textContent;
    const metaVorher = app.el('gruppen-meta').textContent;
    assert.ok(metaVorher.includes('zurückgestellt'));
    aufloesen(); await settle();                                    // verspätet
    assert.equal(app.el('gruppen-nummer').textContent, nummerVorher);
    assert.equal(app.el('gruppen-meta').textContent, metaVorher);
    assert.equal(app.el('gruppen-karte').hidden, false);
    await app.el('gruppen-spaeter').click(); await settle();
    const schreib = calls.find((c) => c.path === '/api/gruppen/antwort');
    assert.equal(JSON.parse(schreib.options.body).kennung, 'G-detail');
}

async function lateQuizAnswerAfterFilterChangeAndCloseIsIgnored() {
    for (const aktion of ['filter', 'schliessen']) {
        const calls = [];
        let aufloesen;
        const app = pruefApp({
            calls,
            naechste: () => new Promise((resolve) => { aufloesen = () => resolve(quizGruppe()); }),
            antwort: () => ({ ok: true }),
        });
        await app.el('gruppen-btn').click(); await settle();
        await app.el('gruppen-uebersicht').click(); await settle();
        if (aktion === 'filter') await app.el('gruppen-liste-status-spaeter').click();
        else await app.el('gruppen-close').click();
        await settle();
        aufloesen(); await settle();
        assert.equal(app.el('gruppen-karte').hidden, true, aktion);
        assert.equal(app.el('gruppen-nummer').textContent, '', aktion);
    }
}

async function allFacesBackReturnsToTargetedGroup() {
    // Befund 2: „Alle Gesichter → Zurück“ führt zur gezielt geöffneten Gruppe,
    // nicht zur nächsten Quizgruppe; „Zur Übersicht“ bleibt sichtbar.
    const calls = [];
    const app = pruefApp({ calls, naechste: quizGruppe, antwort: () => ({ ok: true }) });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-detail').click(); await settle();
    const zaehle = (liste, pfad) => liste.filter((c) => c.path === pfad).length;
    assert.equal(zaehle(calls, '/api/gruppen/detail/G-detail'), 1);
    await app.el('gruppen-alle').click(); await settle();
    assert.ok(calls.some((c) => c.path.startsWith('/api/gruppen/gesichter?kennung=G-detail')));
    const naechsteVorher = zaehle(calls, '/api/gruppen/naechste');
    await app.el('gruppen-alle-zurueck').click(); await settle();
    assert.equal(zaehle(calls, '/api/gruppen/detail/G-detail'), 2);
    assert.equal(zaehle(calls, '/api/gruppen/naechste'), naechsteVorher);
    assert.equal(app.el('gruppen-meta').textContent.includes('zurückgestellt'), true);
    assert.equal(app.el('gruppen-karte').hidden, false);
    assert.equal(app.el('gruppen-detail-zurueck').hidden, false);

    // Ohne Detailkontext (normales Quiz) bleibt es beim bisherigen laden().
    const calls2 = [];
    const quiz = pruefApp({ calls: calls2, naechste: quizGruppe, antwort: () => ({ ok: true }) });
    await quiz.el('gruppen-btn').click(); await settle();
    await quiz.el('gruppen-alle').click(); await settle();
    const n1 = zaehle(calls2, '/api/gruppen/naechste');
    await quiz.el('gruppen-alle-zurueck').click(); await settle();
    assert.equal(zaehle(calls2, '/api/gruppen/naechste'), n1 + 1);
    assert.equal(calls2.some((c) => c.path.startsWith('/api/gruppen/detail/')), false);
    assert.equal(quiz.el('gruppen-detail-zurueck').hidden, true);
}

async function returnToOverviewAfterStatusActionEvenWhenFertig() {
    // Befund 3: Statusaktion im Detail, Backend meldet „fertig“. Die Rückkehr zur
    // Übersicht bleibt möglich und lädt die Kategorie frisch ab Seite 1.
    for (const knopf of ['gruppen-detail-zurueck', 'gruppen-uebersicht']) {
        const calls = [];
        const app = pruefApp({
            calls, seiten: 3, naechste: quizGruppe,
            antwort: (koerper) => ({ ok: true, fertig: true, offen: 0, gruppe: null, namen: [],
                gespeichert: { kennung: koerper.kennung, art: koerper.art } }),
        });
        // Die DOM-Attrappe bildet keine Eltern-Sichtbarkeit nach: der Knopf muss
        // deshalb im HTML außerhalb der (bei „fertig“ versteckten) Karte stehen.
        const knopfPos = html.indexOf('id="gruppen-detail-zurueck"');
        assert.ok(knopfPos > 0 && knopfPos < html.indexOf('id="gruppen-karte"'), 'Knopf liegt in der Karte');
        await app.el('gruppen-btn').click(); await settle();
        await app.el('gruppen-uebersicht').click(); await settle();
        await app.el('gruppen-liste-status-spaeter').click(); await settle();
        await app.el('gruppen-liste-weiter').click(); await settle();       // Seite 2
        assert.ok(calls.some((c) => c.path === '/api/gruppen/liste?status=spaeter&seite=2&je_seite=24'));
        await app.el('gruppen-liste-zeile-G-detail').click(); await settle();
        await app.el('gruppen-spaeter').click(); await settle();             // Backend: fertig
        assert.equal(app.el('gruppen-fertig').hidden, false, knopf);
        assert.equal(app.el('gruppen-detail-zurueck').hidden, false, knopf);
        const vorher = calls.length;
        await app.el(knopf).click(); await settle();
        const neu = calls.slice(vorher).filter((c) => c.path.startsWith('/api/gruppen/liste'));
        assert.deepEqual(neu.map((c) => c.path), ['/api/gruppen/liste?status=spaeter&seite=1&je_seite=24'], knopf);
        assert.equal(app.el('gruppen-liste-ansicht').hidden, false, knopf);
        assert.equal(app.el('gruppen-fertig').hidden, true, knopf);
        assert.equal(app.el('gruppen-detail-zurueck').hidden, true, knopf);
    }
}

// ── Ergebnisprüfung Runde 2 – Behebungen ─────────────────────────────────

/** Attrappe mit zwei Detailgruppen (A, B) und steuerbaren Speicher-/Rückgängig-Antworten. */
function zweiGruppenApp({ calls, antwort, rueckgaengig }) {
    return harness(async (url, options = {}) => {
        const parsed = new URL(url);
        const path = parsed.pathname + parsed.search;
        calls.push({ path, options });
        if (path === '/api/gruppen/naechste') return quizGruppe();
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (parsed.pathname === '/api/gruppen/liste') return response({ ok: true, status: 'spaeter', gesamt: 2,
            seiten: 1, seite: 1, je_seite: 24, gruppen: [gruppe('G-1', 'spaeter'), gruppe('G-2', 'spaeter')] });
        const detail = /^\/api\/gruppen\/detail\/(G-[12])$/.exec(path);
        if (detail) return response({ ok: true, fertig: false, offen: 3, namen: [],
            gruppe: { ...gruppe(detail[1], 'spaeter'), war_spaeter: true } });
        if (path === '/api/gruppen/antwort') return antwort(JSON.parse(options.body));
        if (path === '/api/gruppen/rueckgaengig') return rueckgaengig();
        throw new Error('Unerwarteter Request: ' + path);
    });
}

function naechsteAntwort(extra = {}) {
    return response({ ok: true, fertig: false, offen: 2, namen: [], ...extra,
        gruppe: { ...gruppe('G-3'), war_spaeter: false } });
}

async function aOeffnenAktionAbsendenUndBOeffnen(app, aktionKnopf) {
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-1').click(); await settle();
    app.el(aktionKnopf).click();                                   // Anfrage hängt
    await settle();
    await app.el('gruppen-detail-zurueck').click(); await settle();
    await app.el('gruppen-liste-zeile-G-2').click(); await settle();
    assert.ok(app.el('gruppen-meta').textContent.includes('zurückgestellt'));
}

async function lateSaveAnswerDoesNotReplaceOtherDetail() {
    // Befund R2/1: Antwort für A trifft ein, nachdem B geöffnet wurde.
    const calls = [];
    let aufloesen;
    const app = zweiGruppenApp({
        calls,
        antwort: (koerper) => (koerper.kennung === 'G-1'
            ? new Promise((resolve) => { aufloesen = () => resolve(naechsteAntwort(
                { gespeichert: { kennung: 'G-1', art: koerper.art } })); })
            : naechsteAntwort({ gespeichert: { kennung: koerper.kennung, art: koerper.art } })),
        rueckgaengig: () => response({ ok: true }),
    });
    await aOeffnenAktionAbsendenUndBOeffnen(app, 'gruppen-spaeter');
    const nummerB = app.el('gruppen-nummer').textContent;
    assert.ok(nummerB.length > 0);
    aufloesen(); await settle();                                    // Antwort für A, verspätet
    assert.equal(app.el('gruppen-nummer').textContent, nummerB);    // B bleibt stehen
    assert.equal(app.el('gruppen-karte').hidden, false);
    assert.equal(app.el('gruppen-detail-zurueck').hidden, false);
    // beschaeftigt ist wieder frei und der Zustand gehört zu B: „Später“ trifft B.
    await app.el('gruppen-spaeter').click(); await settle();
    const schreib = calls.filter((c) => c.path === '/api/gruppen/antwort');
    assert.equal(schreib.length, 2);
    assert.equal(JSON.parse(schreib[1].options.body).kennung, 'G-2');
}

async function lateUndoAnswerDoesNotReplaceOtherDetail() {
    const calls = [];
    let aufloesen;
    const app = zweiGruppenApp({
        calls,
        antwort: (koerper) => naechsteAntwort({ gespeichert: { kennung: koerper.kennung, art: koerper.art } }),
        rueckgaengig: () => new Promise((resolve) => { aufloesen = () => resolve(naechsteAntwort(
            { zurueckgenommen: { kennung: 'G-1', art: 'spaeter' } })); }),
    });
    await aOeffnenAktionAbsendenUndBOeffnen(app, 'gruppen-zurueck');
    const nummerB = app.el('gruppen-nummer').textContent;
    aufloesen(); await settle();
    assert.equal(app.el('gruppen-nummer').textContent, nummerB);
    assert.equal(app.el('gruppen-karte').hidden, false);
    await app.el('gruppen-spaeter').click(); await settle();
    const schreib = calls.filter((c) => c.path === '/api/gruppen/antwort');
    assert.equal(schreib.length, 1);
    assert.equal(JSON.parse(schreib[0].options.body).kennung, 'G-2');
}

async function detailLoadingIsVisibleAndErrorToo() {
    // Befund R2/2: „… lädt Gruppe“ steht im immer sichtbaren Meldungsfeld (nicht in der
    // versteckten Liste); Fehler danach landen sichtbar in der Liste.
    const html2 = html.slice(html.indexOf('id="gruppen-liste-ansicht"'));
    const listeEnde = html2.indexOf('</section>');
    assert.equal(html2.slice(0, listeEnde).includes('id="gruppen-meldung"'), false);
    for (const ergebnis of ['ok', 'fehler']) {
        let aufloesen;
        const app = harness(async (url) => {
            const parsed = new URL(url);
            const path = parsed.pathname + parsed.search;
            if (path === '/api/gruppen/naechste') return quizGruppe();
            if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true });
            if (parsed.pathname === '/api/gruppen/liste') return response({ ok: true, status: 'offen', gesamt: 1,
                seiten: 1, seite: 1, je_seite: 24, gruppen: [gruppe('G-1')] });
            if (path === '/api/gruppen/detail/G-1') return new Promise((resolve) => {
                aufloesen = () => resolve(response(ergebnis === 'ok'
                    ? { ok: true, fertig: false, offen: 1, namen: [], gruppe: { ...gruppe('G-1'), war_spaeter: false } }
                    : { ok: false, fehler: 'Gruppe fehlt.' }));
            });
            throw new Error('Unerwarteter Request: ' + path);
        });
        await app.el('gruppen-btn').click(); await settle();
        await app.el('gruppen-uebersicht').click(); await settle();
        app.el('gruppen-liste-zeile-G-1').click(); await settle();
        assert.ok(app.el('gruppen-meldung').textContent.includes('lädt'), ergebnis);
        assert.equal(app.el('gruppen-liste-ansicht').hidden, true, ergebnis);
        aufloesen(); await settle();
        assert.equal(app.el('gruppen-meldung').textContent.includes('lädt'), false, ergebnis);
        if (ergebnis === 'fehler') {
            assert.equal(app.el('gruppen-liste-ansicht').hidden, false);
            assert.ok(app.el('gruppen-liste-meldung').textContent.includes('Gruppe fehlt.'));
        }
    }
}

// ── Befund 1 der Ergebnisprüfung (16.10.2026) ─────────────────────────────
/**
 * Die Ansicht bringt eigene Klassen mit (T2). Fehlten ihre Regeln in style.css, klebte die
 * Liste unformatiert unter dem Quiz — und `display: flex` hebelte das `hidden`-Attribut aus,
 * mit dem die Ansicht ein- und ausgeblendet wird. Genau das wird hier festgehalten.
 */
function ansichtIstGestyltUndBleibtVersteckbar() {
    assert.ok(/\.gruppen-reiter,\s*\.gruppen-liste-filter\s*\{/.test(css),
        'gruppen-liste-filter hat keine Regel (gemeinsamer Selektor mit .gruppen-reiter fehlt)');
    assert.ok(/\.gruppen-liste-ansicht\[hidden\]\s*\{\s*display:\s*none/.test(css),
        'gruppen-liste-ansicht[hidden] wird nicht ausgeblendet');
    assert.ok(/\.gruppen-liste-ansicht\s*\{[^}]*display:\s*flex/.test(css),
        'gruppen-liste-ansicht hat keine Spaltenform');
    assert.ok(/\.gruppen-liste-seiten\s*\{[^}]*display:\s*flex/.test(css),
        'gruppen-liste-seiten hat keine Regel');
    assert.ok(/\.gruppen-liste-seiten\s+\.gruppen-knopf\s*\{/.test(css),
        'die Seiten-Knöpfe bekommen keine Breite');
    assert.ok(/\.gruppen-uebersicht-knopf\s*\{/.test(css),
        'gruppen-uebersicht-knopf hat keine Regel');
    const vCss = (html.match(/style\.css\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vCss >= '20261016A', 'style.css-Cache-Schlüssel zu alt: ' + vCss);
}

// ── Ergebnisprüfung Runde 3 – Behebungen ─────────────────────────────────

/** Attrappe mit Gruppen 1 und 2, Personen (Anna), Gesichterlisten und steuerbaren Antworten. */
function runde3App({ calls, person, ausschliessen, zuordnen }) {
    return harness(async (url, options = {}) => {
        const parsed = new URL(url);
        const path = parsed.pathname + parsed.search;
        calls.push({ path, options });
        if (path === '/api/gruppen/naechste') return quizGruppe();
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (path === '/api/gruppen/personen') return response({ ok: true, personen: [
            { name: 'Anna', vorschlaege: 1, gesichter: 5,
              gruppen: [{ kennung: 'G-1', groesse: 5, von: null, bis: null }], beispiel: null }] });
        if (path.startsWith('/api/gruppen/person?name=')) return person();
        if (parsed.pathname === '/api/gruppen/liste') return response({ ok: true, status: 'spaeter', gesamt: 2,
            seiten: 1, seite: 1, je_seite: 24, gruppen: [gruppe('G-1', 'spaeter'), gruppe('G-2', 'spaeter')] });
        const detail = /^\/api\/gruppen\/detail\/(G-[12])$/.exec(path);
        if (detail) return response({ ok: true, fertig: false, offen: 3, namen: ['Anna'],
            gruppe: { ...gruppe(detail[1], 'spaeter'), war_spaeter: true } });
        if (parsed.pathname === '/api/gruppen/gesichter') {
            const praefix = parsed.searchParams.get('kennung') === 'G-1' ? 'a' : 'b';
            return response({ ok: true, seite: 1, seiten: 1, gesamt: 3, ausschlossen: 0,
                gesichter: [1, 2, 3].map((n) => ({ gid: praefix + n, fileid: praefix + n, index: 0,
                    bbox: null, breite: null, hoehe: null, aufnahme: null,
                    kennung: parsed.searchParams.get('kennung') })) });
        }
        if (path === '/api/gruppen/ausschliessen') return ausschliessen(JSON.parse(options.body));
        if (path === '/api/gruppen/zuordnen') return zuordnen(JSON.parse(options.body));
        if (path.startsWith('/api/cloud/thumb')) return { ok: false };
        throw new Error('Unerwarteter Request: ' + path);
    });
}

function annaAntwort() {
    return response({ ok: true, name: 'Anna', vorschlaege: [], profil: {} });
}

function gesichtKachel(app, gid) {
    return app.el('gruppen-alle-raster').children.find((k) => k.dataset.gid === gid);
}

/** A: Detail → Alle Gesichter, zwei Gesichter markieren, Aktion absenden (hängt);
 *  danach über die Übersicht B → Alle Gesichter öffnen und dort b1 markieren. */
async function aktionFuerAUndAnsichtVonB(app, aktionKnopf) {
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-1').click(); await settle();
    await app.el('gruppen-alle').click(); await settle();
    await gesichtKachel(app, 'a1').click();
    await gesichtKachel(app, 'a2').click();
    if (aktionKnopf === 'gruppen-alle-zuordnen') {
        await app.el('gruppen-alle-zuordnen').click();                 // Namensknöpfe
        const chips = app.el('gruppen-alle-namen').children.filter((c) => c.tagName === 'BUTTON');
        assert.equal(chips[0].textContent, 'Anna');
        chips[0].click();                                              // Anfrage hängt
    } else {
        app.el(aktionKnopf).click();                                   // Anfrage hängt
    }
    await settle();
    // Ansichtswechsel mitten in der Anfrage: A schließen, Übersicht, B, Alle Gesichter von B.
    await app.el('gruppen-alle-zurueck').click(); await settle();
    await app.el('gruppen-detail-zurueck').click(); await settle();
    await app.el('gruppen-liste-zeile-G-2').click(); await settle();
    await app.el('gruppen-alle').click(); await settle();
    assert.ok(gesichtKachel(app, 'b1'));
    await gesichtKachel(app, 'b1').click();
    assert.ok(gesichtKachel(app, 'b1').classList.contains('markiert'));
}

async function latePersonAnswerDoesNotHideGroupDetail() {
    // Befund R3/1: Person öffnen (Antwort hängt), währenddessen zur Übersicht und B öffnen.
    const calls = [];
    let aufloesen;
    const app = runde3App({
        calls,
        person: () => new Promise((resolve) => { aufloesen = () => resolve(annaAntwort()); }),
        ausschliessen: () => response({ ok: true }), zuordnen: () => response({ ok: true }),
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    assert.equal(app.el('gruppen-benannt-liste').children.length, 1);
    app.el('gruppen-benannt-liste').children[0].click(); await settle();   // Person laden, hängt
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-2').click(); await settle();
    assert.equal(app.el('gruppen-karte').hidden, false);
    const nummer = app.el('gruppen-nummer').textContent;
    aufloesen(); await settle();                                            // verspätet
    assert.equal(app.el('gruppen-person').hidden, true);
    assert.equal(app.el('gruppen-karte').hidden, false);
    assert.equal(app.el('gruppen-nummer').textContent, nummer);
    assert.equal(app.el('gruppen-person-titel').textContent, '');
}

async function lateExcludeAnswerDoesNotTouchOtherFaceList() {
    // Befund R3/2 (Ausschließen): Antwort für A darf B's Raster und Markierungen nicht anfassen.
    const calls = [];
    let aufloesen;
    const app = runde3App({
        calls, person: annaAntwort, zuordnen: () => response({ ok: true }),
        ausschliessen: (koerper) => new Promise((resolve) => { aufloesen = () => resolve(response(
            { ok: true, ausschliessen: koerper.gesichter.length, ausgeschlossen: 2, gesamt: 1 })); }),
    });
    await aktionFuerAUndAnsichtVonB(app, 'gruppen-alle-ausschliessen');
    aufloesen(); await settle();
    assert.ok(gesichtKachel(app, 'b1'), 'Gesicht von B wurde entfernt');
    assert.ok(gesichtKachel(app, 'b1').classList.contains('markiert'));
    assert.equal(app.el('gruppen-alle-ausschliessen').disabled, false);
    // Der Server hat A bearbeitet; B's Markierung wird weiter normal gesendet.
    app.el('gruppen-alle-ausschliessen').click(); await settle();   // hängt erneut – nur die Anfrage prüfen
    const posts = calls.filter((c) => c.path === '/api/gruppen/ausschliessen');
    assert.equal(posts.length, 2);
    const koerper = JSON.parse(posts[1].options.body);
    assert.equal(koerper.kennung, 'G-2');
    assert.deepEqual(koerper.gesichter, ['b1']);
}

async function lateAssignAnswerDoesNotTouchOtherFaceList() {
    // Befund R3/2 (Zuordnen): dasselbe für „👤 Zuordnen“.
    const calls = [];
    let aufloesen;
    const app = runde3App({
        calls, person: annaAntwort, ausschliessen: () => response({ ok: true }),
        zuordnen: () => new Promise((resolve) => { aufloesen = () => resolve(response(
            { ok: true, zugeordnet: 2, name: 'Anna' })); }),
    });
    await aktionFuerAUndAnsichtVonB(app, 'gruppen-alle-zuordnen');
    aufloesen(); await settle();
    assert.ok(gesichtKachel(app, 'b1'), 'Gesicht von B wurde entfernt');
    assert.ok(gesichtKachel(app, 'b1').classList.contains('markiert'));
    assert.equal(app.el('gruppen-alle-zuordnen').disabled, false);
}

async function markingsAddedDuringExcludeSurvive() {
    // Gleiche Ansicht: nur die gesendeten Gesichter verschwinden, später markierte bleiben.
    const calls = [];
    let aufloesen;
    const app = runde3App({
        calls, person: annaAntwort, zuordnen: () => response({ ok: true }),
        ausschliessen: () => new Promise((resolve) => { aufloesen = () => resolve(response(
            { ok: true, ausgeschlossen: 1, gesamt: 2 })); }),
    });
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-uebersicht').click(); await settle();
    await app.el('gruppen-liste-zeile-G-1').click(); await settle();
    await app.el('gruppen-alle').click(); await settle();
    await gesichtKachel(app, 'a1').click();
    app.el('gruppen-alle-ausschliessen').click(); await settle();           // sendet nur a1
    await gesichtKachel(app, 'a2').click();                                  // währenddessen markiert
    aufloesen(); await settle();
    assert.equal(gesichtKachel(app, 'a1'), undefined);
    assert.ok(gesichtKachel(app, 'a2'));
    assert.ok(gesichtKachel(app, 'a2').classList.contains('markiert'));
    assert.equal(app.el('gruppen-alle-ausschliessen').disabled, false);
}

/** Gruppenfilter in „Benannt“ (S5, 16.10.2026): Gruppenauswahl, UND mit der
 *  Namenssuche, „Filter zurücksetzen“ leert beide — und die Liste bleibt stabil. */
async function personenGruppenFilterInBenannt() {
    const app = harness(async (url) => {
        const path = new URL(url).pathname + new URL(url).search;
        if (path === '/api/gruppen/naechste') return quizGruppe();
        if (path === '/api/gruppen/stand' || path.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (path === '/api/gruppen/personen') return response({ ok: true, personen: [
            { name: 'Anna', vorschlaege: 2, gesichter: 130, beispiel: null, gruppen: [
                { kennung: 'Person_1001', groesse: 120, von: '2015-01-01', bis: '2025-09-01' },
                { kennung: 'Person_1002', groesse: 10, von: null, bis: null }] },
            { name: 'Tim', vorschlaege: 1, gesichter: 5, beispiel: null, gruppen: [
                { kennung: 'Person_1004', groesse: 5, von: null, bis: null }] }] });
        throw new Error('Unerwarteter Request: ' + path);
    });
    const waehlen = (kennung) => {
        const feld = app.el('gruppen-benannt-gruppe');
        feld.value = kennung;
        (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    };
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    const liste = app.el('gruppen-benannt-liste');
    const feld = app.el('gruppen-benannt-gruppe');
    assert.equal(liste.children.length, 2, 'ohne Filter: beide Personen');
    assert.equal(feld.children.length, 4, 'Auswahl: „Alle Gruppen“ + die drei Gruppen beider Personen');
    assert.equal(feld.children[0].textContent, 'Alle Gruppen');
    assert.equal(feld.children[1].textContent, 'Vorschlag 1001 · 120 Gesichter · 2015–2025');
    waehlen('Person_1001');
    assert.equal(liste.children.length, 1, 'nur die Person mit dieser Gruppe');
    assert.ok(liste.children[0].textContent.includes('Anna'));
    assert.ok(app.el('gruppen-benannt-info').textContent.includes('Vorschlag 1001'));
    app.el('gruppen-benannt-filter').value = 'Tim';                  // Suche UND Gruppe
    waehlen('Person_1001');
    assert.equal(liste.children.length, 0);
    assert.ok(app.el('gruppen-benannt-info').textContent.includes('Keine Person passt'));
    await app.el('gruppen-benannt-filter-zuruecksetzen').click();
    assert.equal(app.el('gruppen-benannt-filter').value, '');
    assert.equal(feld.value, '');
    assert.equal(liste.children.length, 2, 'Zurücksetzen zeigt wieder alle');
    assert.ok(!app.el('gruppen-benannt-info').textContent.includes('Gruppe'));
    waehlen('Person_1004');
    assert.equal(liste.children.length, 1);
    assert.ok(liste.children[0].textContent.includes('Tim'));
    // Ansichtswechsel: die Personenliste wird frisch geladen, der Filter bleibt gültig.
    await app.el('gruppen-reiter-offen').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    assert.equal(liste.children.length, 1, 'gewählte Gruppe überlebt das Neuladen');
    assert.equal(feld.value, 'Person_1004');
}

let beendet = false;
process.on('exit', () => {
    // Eine nie beendete Prüfung (hängendes Promise) darf nicht still als Erfolg zählen.
    if (!beendet) { console.error('FEHLER: Prüfung wurde nicht beendet (hängende Anfrage?)'); process.exitCode = 1; }
});
(async () => {
    // Alle Prüfungen laufen; jede Verletzung wird einzeln gemeldet (Exit 1).
    const pruefungen = [ansichtIstGestyltUndBleibtVersteckbar, lateQuizAnswerDoesNotOverwriteDetail, lateQuizAnswerAfterFilterChangeAndCloseIsIgnored,
        allFacesBackReturnsToTargetedGroup, returnToOverviewAfterStatusActionEvenWhenFertig,
        lateSaveAnswerDoesNotReplaceOtherDetail, lateUndoAnswerDoesNotReplaceOtherDetail,
        detailLoadingIsVisibleAndErrorToo, latePersonAnswerDoesNotHideGroupDetail,
        lateExcludeAnswerDoesNotTouchOtherFaceList, lateAssignAnswerDoesNotTouchOtherFaceList,
        markingsAddedDuringExcludeSurvive, personenGruppenFilterInBenannt,
        overviewRuntime, paginationRuntime, staleResponseAfterFilterAndClose, staleDetailAfterClose,
        failedDetailDoesNotShowPreviousGroup];
    let rot = 0;
    for (const pruefung of pruefungen) {
        try { await pruefung(); } catch (error) {
            rot += 1;
            console.error('FEHLER in ' + pruefung.name + ': ' + (error && error.message ? error.message : error));
        }
    }
    beendet = true;
    if (rot) { process.exitCode = 1; return; }
    console.log('Gruppenübersicht Runtime: Filter, Seiten, Detail, Zurück, Reaktivieren, verspätete Antworten, Alle-Gesichter-Zurück und Rückkehr nach Statusaktion, verspätete Speicher-/Rückgängig-Antworten und sichtbarer Detail-Ladestatus, verspätete Personen-/Ausschließen-/Zuordnen-Antworten grün, Gruppenfilter in „Benannt“ (Gruppenauswahl, UND mit der Suche, Zurücksetzen) grün');
})().catch((error) => { console.error(error); process.exitCode = 1; });
