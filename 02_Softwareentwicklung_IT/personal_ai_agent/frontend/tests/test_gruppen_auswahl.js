// S4 (16.10.2026) — Auftrag „Kachelbedienung" der Gesichterliste:
// langer Druck (~500 ms) startet den Auswahlmodus und wählt die Kachel, solange er
// läuft schaltet jeder kurze Klick um, außerhalb öffnet der kurze Klick das Bild;
// die Vergrößerungs-Symbole auf den Kacheln sind entfernt. Der echte Code läuft in
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

function gesicht(gid, extra) {
    return Object.assign({ gid, fileid: gid, index: 0, bbox: null, breite: null, hoehe: null,
        aufnahme: '2020-01-01', kennung: 'G-1' }, extra || {});
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
        // ``vollbildOeffnen`` bricht ohne diese Funktion von app.js sofort ab
        // (``typeof zeigeBildVollbild !== 'function'``). Der Abruf des Vollbilds
        // ist der Beleg dafür, dass ein kurzer Klick wirklich geöffnet hat.
        zeigeBildVollbild() {},
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

/** App mit einer Gesichterliste (a1, a2, a3 und ein Video-Gesicht a9); alle
 *  Thumb-Abrufe werden protokolliert: ``groesse=480x480`` = Kachelbild,
 *  ``groesse=800x800`` = Vollbild (Öffnen). */
function app() {
    const calls = [];
    const instanz = harness(async (url, options = {}) => {
        const parsed = new URL(url);
        const p = parsed.pathname + parsed.search;
        calls.push({ path: p, options });
        if (p === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 1,
            gruppe: { ...gruppe('G-1'), war_spaeter: false }, namen: ['Anna'] });
        if (p === '/api/gruppen/stand' || p.startsWith('/api/gruppen/suche')) return response({ ok: true, treffer: [] });
        if (parsed.pathname === '/api/gruppen/liste') return response({ ok: true, status: 'offen', gesamt: 1,
            seiten: 1, seite: 1, je_seite: 24, gruppen: [gruppe('G-1')] });
        if (/^\/api\/gruppen\/detail\/(G-1)$/.test(p)) return response({ ok: true, fertig: false, offen: 1,
            namen: ['Anna'], gruppe: { ...gruppe('G-1'), war_spaeter: false } });
        if (parsed.pathname === '/api/gruppen/gesichter') return response({ ok: true, seite: 1, seiten: 1,
            gesamt: 4, ausschlossen: 0, gesichter: [gesicht('a1'), gesicht('a2'), gesicht('a3'), gesicht('a9', { video: true })] });
        if (p === '/api/gruppen/ausschliessen') return response({ ok: true, ausgeschlossen: 1, gesamt: 3 });
        if (parsed.pathname === '/api/cloud/thumb') return { ok: false };
        throw new Error('Unerwarteter Request: ' + p);
    });
    return { ...instanz, calls };
}

async function alleOeffnen(a) {
    await a.el('gruppen-btn').click(); await settle();
    await a.el('gruppen-uebersicht').click(); await settle();
    await a.el('gruppen-liste-zeile-G-1').click(); await settle();
    await a.el('gruppen-alle').click(); await settle();
}

function kachel(a, gid) {
    return a.el('gruppen-alle-raster').children.find((k) => k.dataset.gid === gid);
}

function zeiger(element, art, extra) {
    return (element.listeners.get(art) || []).map((fn) => fn(Object.assign({
        target: element, clientX: 0, clientY: 0, button: 0, pointerType: 'touch',
        preventDefault() {}, stopPropagation() {},
    }, extra || {})));
}

async function halten(element, ms = 600) {
    zeiger(element, 'pointerdown');
    await new Promise((resolve) => setTimeout(resolve, ms));
    zeiger(element, 'pointerup');
    // Die Klickfolge, die der Browser nach dem Loslassen nachschiebt. Sie gehört
    // zum langen Druck und darf die gerade gestartete Auswahl nicht wieder aufheben.
    await element.click();
}

function vollbildAbrufe(a) {
    return a.calls.filter((c) => c.path.includes('/api/cloud/thumb') && c.path.includes('groesse=800x800'));
}

// ── Quelltext-Wächter (die Symbole sind wirklich weg, die Werte stehen fest) ──

function quelleUndDoku() {
    assert.equal(/gruppen-lupe/.test(source), false, 'gruppen_quiz.js baut noch ein Vergrößerungs-Symbol');
    assert.equal(/gruppen-lupe/.test(css), false, 'style.css führt noch die Regel .gruppen-lupe');
    assert.ok(source.includes('const AUSWAHL_LANGDRUCK_MS = 500'), 'Langer Druck nicht auf 500 ms festgelegt');
    assert.ok(source.includes('const AUSWAHL_BEWEGUNG_PX = 8'), 'Bewegungsgrenze (8 px) fehlt');
    assert.ok(source.includes("box.addEventListener('pointercancel', abbrechen)"), 'pointercancel bricht den Timer nicht ab');
    assert.ok(source.includes("box.addEventListener('lostpointercapture', abbrechen)"), 'lostpointercapture bricht den Timer nicht ab');
    assert.ok(/id="gruppen-alle-auswahl-ende"/.test(html), '„Auswahl beenden" fehlt in index.html');
    assert.ok(html.indexOf('id="gruppen-alle-auswahl-ende"') < html.indexOf('id="gruppen-alle-raster"'),
        '„Auswahl beenden" steht nicht bei den Werkzeugen der Ansicht');
    const vQuiz = (html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vQuiz >= '20261016C', 'gruppen_quiz.js-Cache-Schlüssel zu alt: ' + vQuiz);
    const vCss = (html.match(/style\.css\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vCss >= '20261016D', 'style.css-Cache-Schlüssel zu alt: ' + vCss);
}

// ── Laufzeit ─────────────────────────────────────────────────────────────

async function langerDruckStartetAuswahl() {
    const a = app();
    await alleOeffnen(a);
    const k1 = kachel(a, 'a1');
    assert.ok(k1, 'Kachel a1 fehlt');
    assert.ok((k1.listeners.get('pointerdown') || []).length, 'Kachel ohne Pointer-Verdrahtung');
    assert.equal(k1.attributes['aria-pressed'], 'false');
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, true, '„Auswahl beenden" schon vor der Auswahl sichtbar');
    assert.equal(a.el('gruppen-alle-ausschliessen').disabled, true);

    await halten(k1);
    assert.ok(k1.classList.contains('markiert'), 'langer Druck hat nicht ausgewählt');
    assert.equal(k1.attributes['aria-pressed'], 'true');
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, false, '„Auswahl beenden" bleibt verborgen');
    assert.equal(a.el('gruppen-alle-ausschliessen').disabled, false);
    assert.equal(vollbildAbrufe(a).length, 0, 'langer Druck hat das Bild geöffnet');
}

async function synthetischerKlickNachLangdruck() {
    const a = app();
    await alleOeffnen(a);
    const k1 = kachel(a, 'a1');
    await halten(k1);                                  // enthält die Klickfolge des Browsers
    assert.ok(k1.classList.contains('markiert'), 'die Auswahl wurde durch die Klickfolge aufgehoben');
    assert.equal(vollbildAbrufe(a).length, 0, 'die Klickfolge nach dem Halten hat das Bild geöffnet');
    const vorher = a.el('gruppen-alle-ausschliessen').disabled;
    await k1.click();                                  // der nächste Klick ist ein echter kurzer Klick
    assert.equal(k1.classList.contains('markiert'), false, 'der kurze Klick danach schaltet nicht mehr um');
    assert.equal(a.el('gruppen-alle-ausschliessen').disabled, true,
        'die Auswahl blieb bestehen (vorher disabled=' + vorher + ')');
}

async function kurzerKlickSchaltetImModusUm() {
    const a = app();
    await alleOeffnen(a);
    const k1 = kachel(a, 'a1');
    const k2 = kachel(a, 'a2');
    await halten(k1);
    await k2.click();
    assert.ok(k2.classList.contains('markiert'), 'kurzer Klick schaltet im Modus nicht dazu');
    assert.equal(vollbildAbrufe(a).length, 0, 'kurzer Klick im Modus hat das Bild geöffnet');
    await k2.click();
    assert.equal(k2.classList.contains('markiert'), false, 'kurzer Klick schaltet nicht wieder ab');
    assert.ok(k1.classList.contains('markiert'), 'a1 wurde durch a2 abgewählt');
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, false, 'Modus endete, obwohl noch eine Kachel markiert ist');
}

async function letzteKachelAbgewaehltBeendetModus() {
    const a = app();
    await alleOeffnen(a);
    const k3 = kachel(a, 'a3');
    await halten(k3);
    await k3.click();                                  // letzte Kachel abwählen
    assert.equal(k3.classList.contains('markiert'), false);
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, true, 'Modus läuft ohne Auswahl weiter');
    const vorher = vollbildAbrufe(a).length;
    await k3.click();                                  // jetzt öffnet der kurze Klick wieder
    assert.equal(k3.classList.contains('markiert'), false, 'ohne Modus wird weiter markiert');
    assert.equal(vollbildAbrufe(a).length, vorher + 1, 'kurzer Klick öffnet außerhalb des Modus nicht');
}

async function auswahlBeendenKnopf() {
    const a = app();
    await alleOeffnen(a);
    const k1 = kachel(a, 'a1');
    const k2 = kachel(a, 'a2');
    await halten(k1);
    await k2.click();
    await a.el('gruppen-alle-auswahl-ende').click();
    assert.equal(k1.classList.contains('markiert'), false, 'Markierung blieb nach „Auswahl beenden"');
    assert.equal(k2.classList.contains('markiert'), false, 'Markierung blieb nach „Auswahl beenden"');
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, true);
    assert.equal(a.el('gruppen-alle-ausschliessen').disabled, true);
    const vorher = vollbildAbrufe(a).length;
    await k1.click();
    assert.equal(k1.classList.contains('markiert'), false);
    assert.equal(vollbildAbrufe(a).length, vorher + 1, 'nach „Auswahl beenden" öffnet der kurze Klick nicht');
}

async function bewegungBrichtDenTimerAb() {
    const a = app();
    await alleOeffnen(a);
    const k2 = kachel(a, 'a2');
    zeiger(k2, 'pointerdown');
    zeiger(k2, 'pointermove', { clientX: 40, clientY: 0 });      // Scrollen/Ziehen
    await new Promise((resolve) => setTimeout(resolve, 600));
    zeiger(k2, 'pointerup');
    assert.equal(k2.classList.contains('markiert'), false, 'Bewegung ab 8 px startet die Auswahl trotzdem');
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, true);

    zeiger(k2, 'pointerdown');
    zeiger(k2, 'pointercancel');
    await new Promise((resolve) => setTimeout(resolve, 600));
    assert.equal(k2.classList.contains('markiert'), false, 'pointercancel bricht den Timer nicht ab');
}

async function videoGesichtBleibtBeimOeffnen() {
    const a = app();
    await alleOeffnen(a);
    const k9 = kachel(a, 'a9');
    assert.ok(k9, 'Video-Kachel fehlt');
    assert.equal((k9.listeners.get('pointerdown') || []).length, 0,
        'Video-Kachel ist verdrahtet, obwohl der Server Ausschließen/Zuordnen ablehnt');
    await halten(k9);
    assert.equal(k9.classList.contains('markiert'), false, 'Video-Gesicht wurde ausgewählt');
    assert.equal(vollbildAbrufe(a).length, 1, 'Video-Standbild öffnet nicht per kurzem Klick');
}

async function neueListeBeginntOhneModus() {
    const a = app();
    await alleOeffnen(a);
    await halten(kachel(a, 'a1'));
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, false);
    await a.el('gruppen-alle-zurueck').click(); await settle();
    assert.equal(a.el('gruppen-alle-auswahl-ende').hidden, true, 'Modus überlebt das Verlassen der Ansicht');
    await a.el('gruppen-alle').click(); await settle();
    const k1 = kachel(a, 'a1');
    const vorher = vollbildAbrufe(a).length;
    await k1.click();                                  // neue Liste: kurzer Klick öffnet wieder
    assert.equal(k1.classList.contains('markiert'), false, 'die neue Liste startet im Auswahlmodus');
    assert.equal(vollbildAbrufe(a).length, vorher + 1);
}

async function main() {
    quelleUndDoku();
    await langerDruckStartetAuswahl();
    await synthetischerKlickNachLangdruck();
    await kurzerKlickSchaltetImModusUm();
    await letzteKachelAbgewaehltBeendetModus();
    await auswahlBeendenKnopf();
    await bewegungBrichtDenTimerAb();
    await videoGesichtBleibtBeimOeffnen();
    await neueListeBeginntOhneModus();
    console.log('test_gruppen_auswahl.js: alle Prüfungen grün');
}

main().catch((fehler) => { console.error(fehler); process.exit(1); });
