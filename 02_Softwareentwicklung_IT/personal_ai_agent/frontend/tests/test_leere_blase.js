// Leere Blase im Chat (Sebastians Befund 16.10.2026):
//
//   „Wenn der Agent zu arbeiten beginnt, erscheint eine Blase mit ‚…' und
//    daneben steht, was er gerade tut. Das ist gut. Fehler: Darüber erscheint
//    eine LEERE Blase."
//
// Ursache im Code: die Antwort-Blase wird im Stream-Weg beim ERSTEN Häppchen
// eingeblendet (`zeigeAntwortBlase()`), ohne den Inhalt anzusehen. Liefert das
// Modell zuerst nur einen Zeilenumbruch/Leerzeichen (oder einen Markdown-Rest wie
// „**", der nichts Sichtbares rendert), steht danach eine sichtbare, leere Blase
// im Verlauf — genau die gemeldete.
//
// Dieser Test fährt den ECHTEN Weg: `frontend/app.js` läuft in einer kleinen
// DOM-Umgebung (Elemente aus der echten `index.html`), `sendMessage()` wird
// wirklich aufgerufen, nur die HTTP-Antwort ist eine kontrollierte Attrappe.
// Geprüft wird am DOM, nicht im Quelltext.
//
// Aufruf (aus dem Ordner frontend):
//   node tests/test_leere_blase.js app.js               # NEU -> grün
//   git show HEAD:frontend/app.js > "$TMPDIR/alt_app.js"
//   node tests/test_leere_blase.js "$TMPDIR/alt_app.js" # ALT -> rot (Beleg)
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { TextDecoder } = require('node:util');

const quelle = process.argv[2] || path.join(__dirname, '..', 'app.js');
const src = fs.readFileSync(quelle, 'utf8');
const verzeichnis = path.dirname(path.resolve(quelle));
const html = fs.readFileSync(path.join(verzeichnis, 'index.html'), 'utf8');

let fehler = 0;
function pruefe(name, bedingung, detail) {
    if (bedingung) { console.log('  OK   ' + name); }
    else { fehler++; console.log('  FEHL ' + name + (detail ? '  -> ' + detail : '')); }
}

/** Minimales DOM-Element: nur so viel, wie app.js beim Senden wirklich anfasst. */
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
        this.parentNode = null;
        this.style = new Proxy(
            { cssText: '', setProperty() {}, removeProperty() {}, getPropertyValue() { return ''; } },
            { get: (t, k) => (k in t ? t[k] : ''), set: (t, k, v) => { t[k] = v; return true; } },
        );
        this.classList = {
            add: (...n) => { this._class = [...new Set((this._class + ' ' + n.join(' ')).trim().split(/\s+/))].filter(Boolean).join(' '); },
            remove: (...n) => { this._class = this._class.split(/\s+/).filter((x) => x && !n.includes(x)).join(' '); },
            contains: (n) => this._class.split(/\s+/).includes(n),
            toggle: (n, f) => { const a = f === undefined ? !this.classList.contains(n) : f; this.classList[a ? 'add' : 'remove'](n); return a; },
        };
    }
    get lastChild() { return this.children[this.children.length - 1] || null; }
    get childNodes() { return this.children; }
    get parentElement() { return this.parentNode; }
    set className(v) { this._class = v || ''; }
    get className() { return this._class; }
    set textContent(v) { this._text = String(v ?? ''); this.children = []; }
    set innerHTML(v) { this._text = ''; this._html = String(v); this.children = []; }
    get innerHTML() { return this._html || ''; }
    // Wie im echten DOM: was per `innerHTML` gesetzt wurde, ist auch als Text
    // lesbar (nur ohne Markup) — der Code prüft genau das (textContent).
    get textContent() {
        const eigen = this._text + this.children.map((c) => c.textContent).join('');
        return eigen || String(this._html || '').replace(/<[^>]*>/g, '');
    }
    get offsetWidth() { return 800; }
    get clientWidth() { return 800; }
    get scrollHeight() { return 400; }
    get scrollTop() { return 0; }
    set scrollTop(_v) {}
    addEventListener(t, fn) { if (!this.listeners.has(t)) this.listeners.set(t, []); this.listeners.get(t).push(fn); }
    removeEventListener() {}
    setAttribute(k, v) { this.attributes[k] = String(v); }
    getAttribute(k) { return this.attributes[k] === undefined ? null : this.attributes[k]; }
    removeAttribute(k) { delete this.attributes[k]; }
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
    insertBefore(c, ref) { c.parentNode = this; const i = this.children.indexOf(ref); if (i === -1) this.children.push(c); else this.children.splice(i, 0, c); return c; }
    removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; }
    remove() { if (this.parentNode) this.parentNode.removeChild(this); }
    querySelector() { return null; }
    querySelectorAll() { return []; }
    closest(sel) {
        const namen = String(sel).split(',').map((s) => s.trim().replace(/^\./, ''));
        let n = this;
        while (n) { if (n._class && namen.some((w) => n._class.split(/\s+/).includes(w))) return n; n = n.parentNode; }
        return null;
    }
    contains() { return false; }
    focus() {}
    blur() {}
    getBoundingClientRect() { return { top: 0, left: 0, right: 800, bottom: 10, width: 800, height: 10 }; }
    scrollTo() {}
    scrollIntoView() {}
    animate() { return { finished: Promise.resolve(), cancel() {} }; }
    getContext() { return null; }
}

/** Baut die Umgebung: Elemente mit den Kennungen der echten index.html. */
function umgebung(fetchAttrappe) {
    const elemente = new Map();
    for (const m of html.matchAll(/<([a-z][\w-]*)[^>]*\bid="([^"]+)"[^>]*>/gi)) {
        const e = new Element(m[1], m[2]);
        e.hidden = /\shidden(\s|>)/i.test(m[0]);
        const c = m[0].match(/\bclass="([^"]*)"/i);
        if (c) e.className = c[1];
        elemente.set(e.id, e);
    }
    const dokument = {
        readyState: 'complete',
        body: new Element('body'),
        documentElement: new Element('html'),
        getElementById(id) { if (!elemente.has(id)) elemente.set(id, new Element('div', id)); return elemente.get(id); },
        createElement(tag) { return new Element(tag); },
        createTextNode(t) { const e = new Element('#text'); e.textContent = t; return e; },
        querySelector(sel) { return String(sel).startsWith('#') ? this.getElementById(String(sel).slice(1)) : null; },
        querySelectorAll() { return []; },
        addEventListener() {}, removeEventListener() {},
        hidden: false, cookie: '', title: 'test',
    };
    // Der Verlauf braucht ein Elternelement: `scrollToBottom` scrollt dessen
    // Container (`dom.messages.parentElement`).
    dokument.getElementById('messages').parentNode = dokument.getElementById('chat-container');
    const lager = () => ({ _d: {}, getItem(k) { return this._d[k] === undefined ? null : this._d[k]; }, setItem(k, v) { this._d[k] = String(v); }, removeItem(k) { delete this._d[k]; } });
    const sandbox = {
        document: dokument,
        location: { origin: 'http://localhost', href: 'http://localhost/', protocol: 'http:' },
        localStorage: lager(),
        sessionStorage: lager(),
        navigator: { userAgent: 'node', language: 'de-DE', mediaDevices: { getUserMedia: async () => { throw new Error('kein Mikrofon'); } }, clipboard: { writeText: async () => {} }, vibrate() {} },
        fetch: fetchAttrappe,
        setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
        console, Date, Math, JSON, Map, Set, Promise, Object, Array, String, Number, Boolean, RegExp, Error, Symbol,
        TextDecoder,
        URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} },
        Blob: function () {}, FormData: function () {}, FileReader: function () { this.readAsDataURL = () => {}; },
        TextEncoder: class { encode() { return new Uint8Array(); } },
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        performance: { now: () => Date.now() },
        requestAnimationFrame: (f) => setTimeout(() => f(Date.now()), 0),
        getComputedStyle: () => ({ getPropertyValue: () => '' }),
        matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
        IntersectionObserver: class { observe() {} disconnect() {} unobserve() {} },
        MutationObserver: class { observe() {} disconnect() {} },
        ResizeObserver: class { observe() {} disconnect() {} },
        CustomEvent: class { constructor(t, o) { this.type = t; Object.assign(this, o || {}); } },
        Event: class { constructor(t, o) { this.type = t; Object.assign(this, o || {}); } },
        KeyboardEvent: class { constructor(t, o) { this.type = t; Object.assign(this, o || {}); } },
        PointerEvent: class { constructor(t, o) { this.type = t; Object.assign(this, o || {}); } },
        Image: class { set src(v) { this._src = v; } get src() { return this._src; } },
        alert() {}, confirm: () => false, prompt: () => null,
        Audio: class { play() { return Promise.resolve(); } pause() {} },
        speechSynthesis: { speak() {}, cancel() {}, getVoices: () => [] },
        SpeechSynthesisUtterance: function () {},
        MediaRecorder: class { start() {} stop() {} },
        innerWidth: 1400, innerHeight: 900,
        addEventListener() {}, removeEventListener() {},
    };
    sandbox.window = Object.assign({}, sandbox, {
        document: dokument,
        innerWidth: 1400, innerHeight: 900,
        addEventListener() {}, removeEventListener() {},
        scrollTo() {}, getComputedStyle: () => ({}),
        matchMedia: () => ({ matches: false, addEventListener() {} }),
        requestAnimationFrame: (f) => setTimeout(() => f(Date.now()), 0),
    });
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(src, sandbox, { filename: path.basename(quelle) });
    return sandbox;
}

const tick = () => new Promise((r) => setTimeout(r, 5));

/** Die Antwort-Blasen im Verlauf (ohne Zwischenmeldungen/Gedanken). */
function antwortBlasen(sandbox) {
    const liste = sandbox.document.getElementById('messages').children.filter(
        (k) => k.classList.contains('message') && k.classList.contains('assistant')
            && !k.classList.contains('agent-zwischenmeldung'),
    );
    return liste.filter((k) => !k.classList.contains('gedanken-strom'));
}

function istSichtbar(k) {
    return k.hidden === false && k.style.display !== 'none';
}

(async () => {
    // ── Der echte Sendeweg mit einem Stream, der mit einem Leerzeichen beginnt ──
    let freigabeText;
    const tor = new Promise((r) => { freigabeText = r; });
    let aufruf = 0;
    const kodiere = (t) => new TextEncoder().encode(t);
    const fetchAttrappe = async (url) => {
        const pfad = String(url);
        if (pfad.indexOf('/api/chat/stream') !== -1) {
            return {
                ok: true, status: 200,
                body: {
                    getReader() {
                        return {
                            read: async () => {
                                aufruf += 1;
                                if (aufruf === 1) return { done: false, value: kodiere('data: {"delta": "\\n"}\n\n') };
                                if (aufruf === 2) { await tor; return { done: false, value: kodiere('data: {"delta": "Hallo"}\n\n') }; }
                                if (aufruf === 3) return { done: false, value: kodiere('data: {"done": true, "conversation_id": "conv_test"}\n\n') };
                                return { done: true, value: undefined };
                            },
                        };
                    },
                },
            };
        }
        return { ok: true, status: 200, json: async () => ({ ok: true, conversations: [] }) };
    };
    const sandbox = umgebung(fetchAttrappe);
    const lauf = sandbox.sendMessage('Testnachricht');
    // Warten, bis das erste (leere) Häppchen verarbeitet ist.
    for (let i = 0; i < 200 && aufruf < 2; i++) await tick();

    const nachLeer = antwortBlasen(sandbox);
    const sichtbarLeer = nachLeer.filter(istSichtbar);
    pruefe('Nach einem Häppchen mit nur einem Zeilenumbruch steht KEINE sichtbare Blase im Verlauf',
        sichtbarLeer.length === 0,
        'sichtbare Antwort-Blasen: ' + sichtbarLeer.length
            + ' (Inhalt „' + (sichtbarLeer[0] ? sichtbarLeer[0].textContent : '') + '")');

    freigabeText();
    await lauf.catch(() => {});
    await tick();

    const nachText = antwortBlasen(sandbox).filter(istSichtbar);
    pruefe('Sobald echter Text kommt, erscheint EINE sichtbare Blase',
        nachText.length === 1, 'sichtbare Blasen: ' + nachText.length);
    pruefe('… und sie trägt den gestreamten Text',
        nachText.length === 1 && /Hallo/.test(nachText[0].textContent),
        nachText.length === 1 ? nachText[0].textContent : 'keine Blase');

    console.log(fehler === 0 ? '\nAlle Prüfungen grün.' : '\n' + fehler + ' Prüfung(en) fehlgeschlagen.');
    process.exit(fehler === 0 ? 0 : 1);
})();
