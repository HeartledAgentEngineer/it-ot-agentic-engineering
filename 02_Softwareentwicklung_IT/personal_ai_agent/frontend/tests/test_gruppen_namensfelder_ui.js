// Runtime-Vertrag für die Namensfelder im Profil (20.10.2026, Schritt 3).
//
// Sebastian (20.10.2026): Personenbuch mit Vorname / Nachname / Spitznamen.
// Das Backend fuehrt die Felder (backend/tests/test_namensfelder_schreiben.py);
// hier laufen die ECHTEN Handler: Person öffnen, Felder sehen, „Profil speichern"
// drücken — und der abgeschickte Rumpf wird geprüft. Nur HTTP-Antworten sind
// kontrollierte Attrappen. Reine Funktionen: test_gruppen_namensfelder.js.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_gruppen_namensfelder_ui.js gruppen_quiz.js
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
}

function person(name, extra = {}) {
    return { name, gesichter: 5, vorschlaege: 1, beispiel: null, erinnerungen: 0,
        gruppen: [{ kennung: 'G-' + name, groesse: 5, von: null, bis: null }], ...extra };
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
    return { elements, el: (id) => document.getElementById(id), sandbox };
}

async function settle() {
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
}

function response(value) { return { json: async () => value }; }

/** Attrappe: eine Personenliste, je Person ihr Profil — und ein Protokoll der
 *  abgeschickten Rümpfe (URL + Rumpf), damit die Prüfung den POST sieht. */
function appMitProfilen(personen, protokoll) {
    const profile = new Map(personen.map((p) => [p.name, { ...(p.profil || {}) }]));
    const app = harness(async (url, optionen) => {
        const u = new URL(url);
        const pfad = u.pathname + u.search;
        let rumpf = null;
        if (optionen && optionen.body) rumpf = JSON.parse(optionen.body);
        if (protokoll) protokoll.push({ pfad, rumpf });
        if (u.pathname === '/api/gruppen/person') {
            const name = u.searchParams.get('name');
            if (!profile.has(name)) return response({ ok: false, fehler: 'unbekannt' });
            return response({ ok: true, name, vorschlaege: [], gruppen: [],
                profil: { beziehung: '', notizen: [], ...profile.get(name) } });
        }
        if (u.pathname === '/api/gruppen/profil' && rumpf) {          // Speichern
            const alt = profile.get(rumpf.name) || {};
            const neu = { ...alt };
            ['vorname', 'nachname'].forEach((feld) => {
                if (feld in rumpf) { if (rumpf[feld]) { neu[feld] = rumpf[feld]; } else { delete neu[feld]; } }
            });
            if ('spitznamen' in rumpf) { if (rumpf.spitznamen.length) { neu.spitznamen = rumpf.spitznamen; } else { delete neu.spitznamen; } }
            // Wie im Backend: fehlende Felder werden aus dem Namen ABGELEITET
            // (``name_zerlegen``; hier die einfache Regel „letztes Wort = Nachname").
            const worte = String(rumpf.name).split(/\s+/).filter(Boolean);
            if (!neu.vorname) neu.vorname = worte.length > 1 ? worte[0] : rumpf.name;
            if (!neu.nachname) neu.nachname = worte.length > 1 ? worte[worte.length - 1] : '';
            neu.namensfelder_quelle = (('vorname' in rumpf && rumpf.vorname) || ('nachname' in rumpf && rumpf.nachname)
                || alt.vorname || alt.nachname) ? 'profil' : 'abgeleitet';
            neu.ok = true;
            profile.set(rumpf.name, neu);
            return response(neu);
        }
        if (pfad === '/api/gruppen/naechste') return response({ ok: true, fertig: false, offen: 3, namen: [],
            gruppe: { kennung: 'G-quiz', groesse: 5, bilder: 5, videos: 0, von: null, bis: null,
                status: 'offen', name: null, beispiele: [], zwillinge: [], verbunden: [] } });
        if (pfad === '/api/gruppen/stand' || pfad.startsWith('/api/gruppen/suche')) return response({ ok: true, personen: [], kontakte: [] });
        if (pfad === '/api/gruppen/personen') return response({ ok: true, personen });
        throw new Error('Unerwarteter Request: ' + pfad);
    });
    return app;
}

async function listeOeffnen(app) {
    await app.el('gruppen-btn').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
}

async function personOeffnen(app, name) {
    const zeile = app.el('gruppen-benannt-liste').children.find((z) => z.textContent.includes(name));
    assert.ok(zeile, 'keine Zeile fuer ' + name);
    await zeile.click();
    await settle();
}

const feld = (app, id) => app.el(id).value;
const meldung = (app) => app.el('gruppen-meldung').textContent;

let fehler = 0;
async function pruefung(name, fn) {
    try {
        await fn();
        console.log('  ✓ ' + name);
    } catch (e) {
        console.log('  ✗ ' + name + ' — ' + e.message);
        fehler++;
    }
}

const ANNA = { vorname: 'Anni', nachname: 'Beispiel', spitznamen: ['Mausi'],
               namensfelder_quelle: 'profil' };
const TIM = { vorname: 'Tim', nachname: 'Beispiel', spitznamen: [], namensfelder_quelle: 'abgeleitet' };

(async () => {
    console.log('Namensfelder im Profil (echte Handler)');

    await pruefung('die drei Felder stehen beim Öffnen im Profil', async () => {
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA }), person('Tim Beispiel', { profil: TIM })]);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        assert.equal(feld(app, 'gruppen-person-vorname'), 'Anni');
        assert.equal(feld(app, 'gruppen-person-nachname'), 'Beispiel');
        assert.equal(feld(app, 'gruppen-person-spitznamen'), 'Mausi');
        assert.ok(app.el('gruppen-person-namensfelder-hinweis').textContent.includes('Von Hand'),
            'Herkunft der Felder steht nicht dran: ' + app.el('gruppen-person-namensfelder-hinweis').textContent);
    });

    await pruefung('abgeleitete Felder werden als abgeleitet gekennzeichnet', async () => {
        const app = appMitProfilen([person('Tim Beispiel', { profil: TIM })]);
        await listeOeffnen(app);
        await personOeffnen(app, 'Tim Beispiel');
        assert.equal(feld(app, 'gruppen-person-vorname'), 'Tim');
        assert.ok(app.el('gruppen-person-namensfelder-hinweis').textContent.includes('abgeleitet'));
    });

    await pruefung('Speichern schickt nur das geänderte Feld (mit Name und Beziehung zusammen)', async () => {
        const protokoll = [];
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA })], protokoll);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        app.el('gruppen-person-vorname').value = 'Anne';
        app.el('gruppen-person-beziehung').value = 'Schwester';
        protokoll.length = 0;
        await app.el('gruppen-person-speichern').click();
        await settle();
        const post = protokoll.find((p) => p.pfad === '/api/gruppen/profil');
        assert.ok(post, 'es wurde nichts gespeichert: ' + JSON.stringify(protokoll));
        assert.equal(post.rumpf.name, 'Anna Beispiel');
        assert.equal(post.rumpf.vorname, 'Anne');
        assert.equal(post.rumpf.beziehung, 'Schwester');
        assert.ok(!('nachname' in post.rumpf), 'unverändertes Feld wurde mitgeschickt');
        assert.ok(!('spitznamen' in post.rumpf), 'unveränderte Spitznamen wurden mitgeschickt');
        assert.ok(meldung(app).includes('gespeichert'), 'keine Rückmeldung: ' + meldung(app));
        assert.equal(feld(app, 'gruppen-person-vorname'), 'Anne', 'das Feld zeigt den neuen Stand nicht');
    });

    await pruefung('leeren gibt die Ableitung zurück (leerer Wert wird geschickt)', async () => {
        const protokoll = [];
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA })], protokoll);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        app.el('gruppen-person-vorname').value = '';
        protokoll.length = 0;
        await app.el('gruppen-person-speichern').click();
        await settle();
        const post = protokoll.find((p) => p.pfad === '/api/gruppen/profil');
        assert.ok(post, 'es wurde nichts gespeichert');
        assert.equal(post.rumpf.vorname, '', 'das Leeren kommt nicht als leerer Wert an');
        assert.equal(feld(app, 'gruppen-person-vorname'), 'Anna',
            'nach dem Leeren zeigt das Feld nicht wieder den abgeleiteten Vornamen');
        assert.ok(app.el('gruppen-person-namensfelder-hinweis').textContent.includes('Von Hand'),
            'der Nachname ist noch von Hand — der Hinweis muss das sagen: '
            + app.el('gruppen-person-namensfelder-hinweis').textContent);
    });

    await pruefung('Spitznamen kommen komma-getrennt, doppelte fallen weg', async () => {
        const protokoll = [];
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA })], protokoll);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        app.el('gruppen-person-spitznamen').value = 'Mausi, Anna , mausi';
        protokoll.length = 0;
        await app.el('gruppen-person-speichern').click();
        await settle();
        const post = protokoll.find((p) => p.pfad === '/api/gruppen/profil');
        assert.ok(post && Array.isArray(post.rumpf.spitznamen), 'Spitznamen fehlen im Rumpf');
        assert.deepEqual(post.rumpf.spitznamen, ['Mausi', 'Anna']);
        assert.equal(feld(app, 'gruppen-person-spitznamen'), 'Mausi, Anna');
    });

    await pruefung('elf Spitznamen werden abgelehnt, ohne den Server zu fragen', async () => {
        const protokoll = [];
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA })], protokoll);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        app.el('gruppen-person-spitznamen').value = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10', 'S11'].join(', ');
        protokoll.length = 0;
        await app.el('gruppen-person-speichern').click();
        await settle();
        assert.equal(protokoll.some((p) => p.pfad === '/api/gruppen/profil'), false,
            'zu viele Spitznamen wurden trotzdem geschickt');
        assert.ok(meldung(app).includes('10'), 'die Meldung nennt die Grenze nicht: ' + meldung(app));
        assert.equal(feld(app, 'gruppen-person-vorname'), 'Anni', 'die Felder wurden verwürfelt');
    });

    await pruefung('ohne Änderung passiert kein Schreiben', async () => {
        const protokoll = [];
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA })], protokoll);
        await listeOeffnen(app);
        await personOeffnen(app, 'Anna Beispiel');
        protokoll.length = 0;
        await app.el('gruppen-person-speichern').click();
        await settle();
        assert.equal(protokoll.some((p) => p.pfad === '/api/gruppen/profil'), false, 'es wurde unnötig geschrieben');
        assert.ok(meldung(app).includes('Nichts geändert'), 'keine ehrliche Meldung: ' + meldung(app));
    });

    await pruefung('die Suchzeile der Liste findet über den Spitznamen', async () => {
        const app = appMitProfilen([person('Anna Beispiel', { profil: ANNA, ...ANNA }),
            person('Tim Beispiel', { profil: TIM, ...TIM })]);
        await listeOeffnen(app);
        const suche = app.el('gruppen-benannt-filter');
        suche.value = 'mausi';
        (suche.listeners.get('input') || []).forEach((fn) => fn({ target: suche }));
        await settle();
        const texte = app.el('gruppen-benannt-liste').children.map((z) => z.textContent);
        assert.equal(texte.length, 1, 'die Suche filtert nicht: ' + texte.join(' | '));
        assert.ok(texte[0].includes('Anna Beispiel'));
        suche.value = 'beispiel';
        (suche.listeners.get('input') || []).forEach((fn) => fn({ target: suche }));
        await settle();
        assert.equal(app.el('gruppen-benannt-liste').children.length, 2, 'Nachname findet nicht beide Personen');
    });

    console.log(fehler ? '\n' + fehler + ' Prüfung(en) rot' : '\nAlle Prüfungen grün');
    process.exit(fehler ? 1 : 0);
})();
