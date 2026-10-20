// Runtime-Vertrag für die Personenauswahl als alphabetische Liste (S8, 18.10.2026,
// To-do Punkt 10): sortiert, Suchzeile, Sprungmarken — und die Vorschlags-Zahl
// steht nicht mehr in der Zeile. Seit 20.10.2026: kein Gruppenfilter mehr, dafür
// die Sortierung „Alphabetisch“ / „Meiste Fotos zuerst“. Die echten UI-Handler laufen in einer kleinen
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
    return { elements, el: (id) => document.getElementById(id), sandbox };
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

/** Nur die Namen der angezeigten Zeilen, in Listen-Reihenfolge. */
function namen(app) {
    return app.el('gruppen-benannt-liste').children.map((z) => {
        const text = z.children.find((c) => c.classList && c.classList.contains('gruppen-benannt-text'));
        const name = text && text.children.find((c) => c.classList && c.classList.contains('gruppen-treffer-name'));
        return name ? name.textContent : '';
    });
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

async function erinnerungsFilterTrenntUndZuruecksetzenLeert() {
    // S8-Rest (18.10.2026): „Erinnerung" ist eine aufgenommene Sprachnotiz im
    // Profil. Der Server liefert die Zahl (``erinnerungen``); gefiltert wird in
    // der Liste. Fehlt das Feld ganz, gilt die Person als „ohne Erinnerung".
    const block = (html.match(/<select id="gruppen-benannt-erinnerung"[\s\S]*?<\/select>/) || [])[0] || '';
    assert.ok(block, 'das Auswahlfeld „Erinnerung" fehlt im HTML');
    assert.ok(/<option value="">/.test(block), 'die Auswahl „alle" fehlt');
    assert.ok(/<option value="mit">/.test(block), 'die Auswahl „mit" fehlt');
    assert.ok(/<option value="ohne">/.test(block), 'die Auswahl „ohne" fehlt');
    assert.ok(/aria-label="[^"]*Erinnerung[^"]*"/.test(block), 'die Auswahl hat keine Beschriftung');

    const app = personenApp([person('Anna', { erinnerungen: 2 }), person('Bea', { erinnerungen: 0 }),
        person('Cem', { erinnerungen: 1 }), person('Dana')]);
    await listeOeffnen(app);
    assert.equal(zeilenTexte(app).length, 4, 'ohne Filter stehen alle Personen da');
    const feld = app.el('gruppen-benannt-erinnerung');
    const suche = app.el('gruppen-benannt-filter');
    const wechsle = (wert) => {
        feld.value = wert;
        (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    };

    wechsle('ohne');
    assert.deepEqual(namen(app), ['Bea', 'Dana'], 'ohne Erinnerung: ' + namen(app).join());
    let info = app.el('gruppen-benannt-info').textContent;
    assert.ok(info.includes('2 Personen') && info.includes('ohne Erinnerung'), 'Infozeile: ' + info);

    wechsle('mit');
    assert.deepEqual(namen(app), ['Anna', 'Cem'], 'mit Erinnerung: ' + namen(app).join());
    info = app.el('gruppen-benannt-info').textContent;
    assert.ok(info.includes('2 Personen') && info.includes('mit Erinnerung'), 'Infozeile: ' + info);

    // Suche und Erinnerungsfilter wirken zusammen (UND).
    suche.value = 'an';
    (suche.listeners.get('input') || []).forEach((fn) => fn({ target: suche }));
    assert.deepEqual(namen(app), ['Anna'], 'Suche und Erinnerungsfilter zusammen');

    // „Filter zurücksetzen" leert Suche UND Erinnerung.
    await app.el('gruppen-benannt-filter-zuruecksetzen').click();
    assert.equal(feld.value, '', 'der Erinnerungsfilter bleibt stehen');
    assert.equal(suche.value, '', 'die Suchzeile bleibt stehen');
    assert.equal(zeilenTexte(app).length, 4, 'nach dem Zurücksetzen fehlen Personen');
    assert.equal(app.el('gruppen-benannt-info').textContent.includes('Erinnerung'), false,
        'die Infozeile nennt weiter einen Erinnerungsfilter');
}

// ── S8-Rest 2 (18.10.2026): Personen ohne Erinnerung nacheinander durchgehen ──
// Der Knopf im Profil fuehrt zur naechsten Person ohne Erinnerung — innerhalb
// der gerade gesetzten Filter. Er darf nur da sein, wenn es wirklich eine gibt.

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

function weiterKnopf(app) { return app.el('gruppen-person-weiter'); }

async function personAusListeOeffnen(app, name) {
    const zeile = app.el('gruppen-benannt-liste').children.find((z) => z.textContent.includes(name));
    assert.ok(zeile, 'keine Zeile fuer ' + name);
    await zeile.click();
    await settle();
}

async function erinnerungenNacheinanderDurchgehen() {
    const block = (html.match(/<button id="gruppen-person-weiter"[\s\S]*?<\/button>/) || [])[0] || '';
    assert.ok(block, 'der Weiter-Knopf fehlt im HTML (das Durcharbeiten ist nicht erreichbar)');
    assert.ok(/\shidden/.test(block), 'der Weiter-Knopf steht von Anfang an sichtbar da');
    assert.equal(/class="gruppen-knopf"/.test(block), true, 'der Weiter-Knopf hat keinen Knopf-Stil');
    const vQuiz = (html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vQuiz >= '20261018D', 'gruppen_quiz.js-Cache-Schluessel zu alt: ' + vQuiz);

    const protokoll = [];
    const app = personenAppMitProfil([person('Anna', { erinnerungen: 2 }), person('Bea'),
        person('Cem'), person('Dana')], protokoll);
    await listeOeffnen(app);
    // Die Arbeitsliste: nur Personen ohne Erinnerung.
    const feld = app.el('gruppen-benannt-erinnerung');
    feld.value = 'ohne';
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    assert.deepEqual(namen(app), ['Bea', 'Cem', 'Dana']);

    // Bei einer Person OHNE Erinnerung: der Knopf nennt den Rest ohne sie.
    await personAusListeOeffnen(app, 'Bea');
    assert.equal(app.el('gruppen-person-titel').textContent, 'Bea');
    let knopf = weiterKnopf(app);
    assert.equal(knopf.hidden, false, 'der Weiter-Knopf fehlt bei „Bea\"');
    assert.ok(knopf.textContent.includes('(2)'), 'Rest nicht genannt: ' + knopf.textContent);
    assert.ok(String(knopf.attributes['aria-label'] || '').includes('Cem'), 'Ziel nicht angekuendigt');

    // Weiter zum naechsten — und genau der wird geladen.
    protokoll.length = 0;
    await knopf.click();
    await settle();
    assert.deepEqual(protokoll.filter((p) => p.startsWith('/api/gruppen/person')), ['/api/gruppen/person?name=Cem']);
    assert.equal(app.el('gruppen-person-titel').textContent, 'Cem');
    assert.ok(weiterKnopf(app).textContent.includes('(1)'), 'Rest nach dem Wechsel: ' + weiterKnopf(app).textContent);

    // Die letzte Person ohne Erinnerung: kein Weiter mehr, kein Ringlauf.
    await weiterKnopf(app).click();
    await settle();
    assert.equal(app.el('gruppen-person-titel').textContent, 'Dana');
    assert.equal(weiterKnopf(app).hidden, true, 'bei der letzten Person steht der Weiter-Knopf noch da');

    // Bei einer Person MIT Erinnerung beginnt der Weg bei der ersten ohne.
    await app.el('gruppen-person-zurueck').click();
    await settle();
    feld.value = '';
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    await personAusListeOeffnen(app, 'Anna');
    knopf = weiterKnopf(app);
    assert.equal(knopf.hidden, false, 'bei „Anna\" fehlt der Weg zur ersten Person ohne Erinnerung');
    assert.ok(knopf.textContent.includes('(3)'), 'Rest bei „Anna\": ' + knopf.textContent);

    // Der Weg folgt den gesetzten Filtern: mit Suche „d\" gibt es kein Weiter.
    await app.el('gruppen-person-zurueck').click();
    await settle();
    const suche = app.el('gruppen-benannt-filter');
    suche.value = 'd';
    (suche.listeners.get('input') || []).forEach((fn) => fn({ target: suche }));
    assert.deepEqual(namen(app), ['Dana']);
    await personAusListeOeffnen(app, 'Dana');
    assert.equal(weiterKnopf(app).hidden, true, 'der Weiter-Knopf ignoriert die Suchzeile');

    // Und die reine Regel selbst: kein Ringlauf, unbekannter Name beginnt vorne.
    const rein = app.sandbox;
    const reihe = [person('Bea'), person('Cem'), person('Dana'), person('Anna', { erinnerungen: 1 })];
    assert.equal(rein.gruppenNaechsteOhneErinnerung(reihe, 'Bea'), 'Cem');
    assert.equal(rein.gruppenNaechsteOhneErinnerung(reihe, 'Dana'), '', 'es gibt einen Ringlauf');
    assert.equal(rein.gruppenNaechsteOhneErinnerung(reihe, 'Anna'), 'Bea');
    assert.equal(rein.gruppenNaechsteOhneErinnerung([person('Anna', { erinnerungen: 1 })], 'Anna'), '');
    assert.deepEqual(rein.gruppenReiheOhneErinnerung(reihe), ['Bea', 'Cem', 'Dana']);
    assert.deepEqual(rein.gruppenRestOhneErinnerung(reihe, 'Bea'), ['Cem', 'Dana']);
    assert.deepEqual(rein.gruppenRestOhneErinnerung(reihe, 'Dana'), []);
    assert.deepEqual(rein.gruppenRestOhneErinnerung(reihe, 'Anna'), ['Bea', 'Cem', 'Dana'],
        'ohne Position in der Reihe zaehlt die ganze Reihe');
    assert.equal(rein.gruppenWeiterText(0), '', 'ohne Rest steht eine Beschriftung da');
    assert.ok(rein.gruppenWeiterText(3).includes('(3)'));
}

async function erinnerungsFilterOhneTreffer() {
    const app = personenApp([person('Anna', { erinnerungen: 3 }), person('Bea')]);
    await listeOeffnen(app);
    const feld = app.el('gruppen-benannt-erinnerung');
    feld.value = 'ohne';
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    assert.deepEqual(namen(app), ['Bea']);
    feld.value = 'mit';
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    assert.deepEqual(namen(app), ['Anna']);
    // Unsinnige Werte filtern nicht (ehrlich: „alle").
    feld.value = 'vielleicht';
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
    assert.equal(zeilenTexte(app).length, 2, 'unbekannter Wert filtert weg');
}

// ── Sortierung „Alphabetisch“ / „Meiste Fotos zuerst“ (20.10.2026) ──────────

function sortierungWaehlen(app, wert) {
    const feld = app.el('gruppen-benannt-sortierung');
    feld.value = wert;
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
}

function erinnerungWaehlen(app, wert) {
    const feld = app.el('gruppen-benannt-erinnerung');
    feld.value = wert;
    (feld.listeners.get('change') || []).forEach((fn) => fn({ target: feld }));
}

function suchen(app, text) {
    const feld = app.el('gruppen-benannt-filter');
    feld.value = text;
    (feld.listeners.get('input') || []).forEach((fn) => fn({ target: feld }));
}

function sortierungImHtml() {
    // Der Gruppenfilter ist weg, an seiner Stelle steht die Sortierung (kein Filter).
    assert.equal(html.includes('gruppen-benannt-gruppe'), false, 'der Gruppenfilter steht noch im HTML');
    assert.equal(source.includes('gruppen-benannt-gruppe'), false, 'der Gruppenfilter steht noch im Skript');
    assert.equal(html.includes('<option value="">Alle Gruppen</option>'), false,
        'die Auswahl „Alle Gruppen“ steht noch im HTML');
    const block = (html.match(/<select id="gruppen-benannt-sortierung"[\s\S]*?<\/select>/) || [])[0] || '';
    assert.ok(block, 'das Auswahlfeld für die Sortierung fehlt im HTML');
    assert.ok(/aria-label="Sortierung der Personenliste"/.test(block), 'die Auswahl hat nicht die erwartete Beschriftung');
    assert.ok(/<option value="">Alphabetisch<\/option>/.test(block), 'die Auswahl „Alphabetisch“ fehlt');
    assert.ok(/<option value="meiste">Meiste Fotos zuerst<\/option>/.test(block), 'die Auswahl „Meiste Fotos zuerst“ fehlt');
    assert.ok(html.includes('id="gruppen-benannt-erinnerung"'), 'der Erinnerungsfilter muss bleiben');
    assert.ok(html.includes('id="gruppen-benannt-filter"'), 'die Personensuche muss bleiben');
    assert.ok(html.indexOf('id="gruppen-benannt-sortierung"') < html.indexOf('id="gruppen-benannt-erinnerung"'),
        'die Sortierung steht nicht an der Stelle des Gruppenfilters');
    const vQuiz = (html.match(/gruppen_quiz\.js\?v=([0-9A-Z]+)/) || [])[1] || '';
    assert.ok(vQuiz >= '20261020B', 'gruppen_quiz.js-Cache-Schluessel zu alt: ' + vQuiz);
}

async function sortierungMeisteFotosZuerst() {
    // Server liefert ungeordnet; „gesichter“ = Zahl der erkannten Gesichter.
    const app = personenApp([person('Cem', { gesichter: 10 }), person('Anna', { gesichter: 120 }),
        person('Bea', { gesichter: 10 }), person('Dana', { gesichter: 300 }), person('Emil')]);
    await listeOeffnen(app);
    assert.deepEqual(namen(app), ['Anna', 'Bea', 'Cem', 'Dana', 'Emil'].map((n) => n), 'Standard ist alphabetisch');
    assert.equal(app.el('gruppen-benannt-sortierung').value, '', 'Standard der Auswahl ist „Alphabetisch“');
    assert.equal(app.el('gruppen-benannt-sprung').hidden, false, 'alphabetisch zeigt die Sprungleiste');

    sortierungWaehlen(app, 'meiste');
    // 300, 120, dann Gleichstand (10) alphabetisch: Bea vor Cem, dann Emil (5).
    assert.deepEqual(namen(app), ['Dana', 'Anna', 'Bea', 'Cem', 'Emil'], 'meiste Fotos: ' + namen(app).join());
    const info = app.el('gruppen-benannt-info').textContent;
    assert.ok(info.includes('meiste Fotos zuerst') && !info.includes('alphabetisch'), 'Infozeile: ' + info);
    const leiste = app.el('gruppen-benannt-sprung');
    assert.equal(leiste.hidden, true, 'bei „Meiste Fotos“ bleibt die Sprungleiste weg');
    assert.equal(leiste.children.length, 0, 'es stehen noch Sprungmarken da');
    const liste = app.el('gruppen-benannt-liste');
    assert.equal(liste.children.some((z) => z.attributes && z.attributes['data-sprung']), false,
        'die Zeilen tragen noch Sprungmarken');

    sortierungWaehlen(app, '');
    assert.deepEqual(namen(app), ['Anna', 'Bea', 'Cem', 'Dana', 'Emil'], 'zurück zu alphabetisch');
    assert.ok(app.el('gruppen-benannt-info').textContent.includes('alphabetisch'));
    assert.equal(app.el('gruppen-benannt-sprung').hidden, false, 'die Sprungleiste kommt zurück');
    assert.ok(liste.children.some((z) => z.attributes && z.attributes['data-sprung']), 'Sprungmarken fehlen wieder');
    // Unsinniger Wert = alphabetisch.
    sortierungWaehlen(app, 'zufall');
    assert.deepEqual(namen(app), ['Anna', 'Bea', 'Cem', 'Dana', 'Emil']);
}

async function filterUndSortierungWirkenZusammen() {
    const app = personenApp([person('Anna', { gesichter: 50, erinnerungen: 1 }), person('Bea', { gesichter: 200 }),
        person('Cem', { gesichter: 80 }), person('Dana', { gesichter: 90, erinnerungen: 2 }),
        person('Dario', { gesichter: 10 })]);
    await listeOeffnen(app);
    sortierungWaehlen(app, 'meiste');
    assert.deepEqual(namen(app), ['Bea', 'Dana', 'Cem', 'Anna', 'Dario']);
    // Erinnerungsfilter + Sortierung.
    erinnerungWaehlen(app, 'ohne');
    assert.deepEqual(namen(app), ['Bea', 'Cem', 'Dario'], 'ohne Erinnerung, meiste zuerst');
    // Suche + Erinnerungsfilter + Sortierung.
    erinnerungWaehlen(app, '');
    suchen(app, 'da');
    assert.deepEqual(namen(app), ['Dana', 'Dario'], 'Suche „da“, meiste zuerst');
    erinnerungWaehlen(app, 'mit');
    assert.deepEqual(namen(app), ['Dana']);
    // Alphabetisch wirkt mit denselben Filtern.
    erinnerungWaehlen(app, '');
    sortierungWaehlen(app, '');
    assert.deepEqual(namen(app), ['Dana', 'Dario'], 'Suche „da“, alphabetisch');
}

async function zuruecksetzenLaesstDieSortierungStehen() {
    const app = personenApp([person('Anna', { gesichter: 5 }), person('Bea', { gesichter: 50, erinnerungen: 1 }),
        person('Cem', { gesichter: 20 })]);
    await listeOeffnen(app);
    sortierungWaehlen(app, 'meiste');
    erinnerungWaehlen(app, 'ohne');
    suchen(app, 'c');
    assert.deepEqual(namen(app), ['Cem']);
    await app.el('gruppen-benannt-filter-zuruecksetzen').click();
    assert.equal(app.el('gruppen-benannt-filter').value, '', 'die Suche bleibt stehen');
    assert.equal(app.el('gruppen-benannt-erinnerung').value, '', 'der Erinnerungsfilter bleibt stehen');
    assert.equal(app.el('gruppen-benannt-sortierung').value, 'meiste', 'das Zurücksetzen hat die Sortierung verstellt');
    assert.deepEqual(namen(app), ['Bea', 'Cem', 'Anna'], 'Sortierung gilt nach dem Zurücksetzen weiter');
    assert.equal(app.el('gruppen-benannt-sprung').hidden, true);
    // Auch nach dem Neuladen der Liste (Ansichtswechsel) bleibt die Wahl.
    await app.el('gruppen-reiter-offen').click(); await settle();
    await app.el('gruppen-reiter-benannt').click(); await settle();
    assert.deepEqual(namen(app), ['Bea', 'Cem', 'Anna'], 'die Sortierung überlebt das Neuladen');
}

function reineSortierung() {
    const rein = personenApp([]).sandbox;
    const roh = [{ name: 'Cem', gesichter: 10 }, { name: 'Anna', gesichter: 120 }, { name: 'Bea', gesichter: 10 },
        { name: 'Öde', gesichter: '30' }, { name: 'Zoe' }, { name: 'Max', gesichter: 'viele' },
        { name: 'Neg', gesichter: -4 }, { name: 'Leer', gesichter: null }];
    const vorher = roh.map((p) => p.name).join('|');
    const meiste = rein.gruppenPersonenSortiert(roh, 'meiste').map((p) => p.name);
    // 120, 30, 10 (Bea vor Cem), dann alle ohne gültige Zahl (= 0) alphabetisch.
    assert.deepEqual(meiste, ['Anna', 'Öde', 'Bea', 'Cem', 'Leer', 'Max', 'Neg', 'Zoe'], meiste.join());
    assert.equal(roh.map((p) => p.name).join('|'), vorher, 'die Eingabeliste wurde verändert');
    assert.notEqual(rein.gruppenPersonenSortiert(roh, 'meiste'), roh, 'es wird dieselbe Liste zurückgegeben');
    const alpha = rein.gruppenPersonenSortiert(roh).map((p) => p.name);
    assert.deepEqual(alpha, ['Anna', 'Bea', 'Cem', 'Leer', 'Max', 'Neg', 'Öde', 'Zoe'], alpha.join());
    assert.deepEqual(rein.gruppenPersonenSortiert(roh, '').map((p) => p.name), alpha);
    assert.deepEqual(rein.gruppenPersonenSortiert(roh, 'unsinn').map((p) => p.name), alpha, 'unbekannte Art = alphabetisch');
    assert.equal(rein.gruppenPersonenSortiert(null, 'meiste').length, 0);
    assert.equal(rein.gruppenPersonenSortiert('x', 'meiste').length, 0);
    assert.equal(rein.gruppenGesichterZahl({ gesichter: 7 }), 7);
    assert.equal(rein.gruppenGesichterZahl({ gesichter: 'x' }), 0);
    assert.equal(rein.gruppenGesichterZahl(null), 0);
    // Zusammen mit den Filtern: dieselbe Regel für Liste, Weiter-Weg und Wischen.
    const gefiltert = rein.gruppenPersonenGefiltert(roh, 'c', '', 'meiste').map((p) => p.name);
    assert.deepEqual(gefiltert, ['Cem']);
    const ohne = rein.gruppenPersonenGefiltert([{ name: 'Anna', gesichter: 5, erinnerungen: 1 },
        { name: 'Bea', gesichter: 9 }, { name: 'Cem', gesichter: 20 }], '', 'ohne', 'meiste').map((p) => p.name);
    assert.deepEqual(ohne, ['Cem', 'Bea']);
    assert.deepEqual(rein.gruppenPersonenGefiltert([{ name: 'Bea', gesichter: 9 }, { name: 'Anna', gesichter: 5 }],
        '', '', '').map((p) => p.name), ['Anna', 'Bea'], 'ohne Sortierart alphabetisch');
}

let beendet = false;
process.on('exit', () => {
    if (!beendet) { console.error('FEHLER: Prüfung wurde nicht beendet (hängende Anfrage?)'); process.exitCode = 1; }
});
(async () => {
    const pruefungen = [alphabetischSortiertMitUmlauten, nurBenannteAnsichtWirdGerollt,
        sprungmarkenNurVorhandeneUndZumZiel, einBuchstabeOhneLeiste,
        vorschlaegeStehenNichtMehrInDerZeile, suchzeileFiltertUndSortiertNeu,
        erinnerungenNacheinanderDurchgehen,
        erinnerungsFilterTrenntUndZuruecksetzenLeert, erinnerungsFilterOhneTreffer,
        sortierungImHtml, sortierungMeisteFotosZuerst, filterUndSortierungWirkenZusammen,
        zuruecksetzenLaesstDieSortierungStehen, reineSortierung];
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
        + 'Vorschlags-Zahl aus der Zeile entfernt, Filter mit/ohne Erinnerung, '
        + 'Weiter-Knopf fuehrt der Reihe nach zu den Personen ohne Erinnerung, '
        + 'kein Gruppenfilter mehr, Sortierung alphabetisch / meiste Fotos zuerst '
        + '(Gleichstand alphabetisch, Sprungleiste nur alphabetisch, Zurücksetzen lässt sie stehen) grün');
})().catch((error) => { console.error(error); process.exitCode = 1; });
