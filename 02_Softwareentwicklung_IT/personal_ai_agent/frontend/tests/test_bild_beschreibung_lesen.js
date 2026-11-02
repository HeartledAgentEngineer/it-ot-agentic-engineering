// Bildbeschreibung im Vollbild-Editor: zuerst lesen, dann bearbeiten, neu beschreiben (G2, 02.11.2026).
//
// Plan: .hermes/plans/2026-11-02_geschichte-sprachmodell.md, Schritt G2, Prüfkriterien
//   (a) vorhandene Beschreibung erscheint lesend, ohne Textarea;
//   (b) „Bearbeiten“ öffnet die Textarea MIT Inhalt;
//   (c) leerer Zustand zeigt Hinweis und Knöpfe, keine fokussierte leere Textarea;
//   (e) „Übernehmen“ speichert, „Verwerfen“ lässt alles unverändert;
//   (g2) die Kostenanzeige erscheint VOR dem Vision-Aufruf, ohne Bestätigung wird nicht aufgerufen.
//
// Die ECHTE Funktion baueBeschreibungKasten wird wörtlich aus bild_beschreibung.js geschnitten (eigene
// Datei, vor app.js geladen) und gegen eine
// kleine Schein-Oberfläche (Elemente mit Kindern, Klicks, Fokus) und ein Schein-Backend (fetch)
// ausgeführt. Kein Netz, keine Nutzerdaten, erfundene fileids und Texte.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_bild_beschreibung_lesen.js bild_beschreibung.js
const fs = require('fs');
const path = require('path');

const kastenPfad = path.resolve(process.argv[2] || path.join(__dirname, '..', 'bild_beschreibung.js'));
const verz = path.dirname(kastenPfad);
const src = fs.readFileSync(kastenPfad, 'utf8');
const appSrc = fs.readFileSync(path.join(verz, 'app.js'), 'utf8');
const erzSrc = fs.readFileSync(path.join(verz, 'erzaehlen.js'), 'utf8');
const html = fs.readFileSync(path.join(verz, 'index.html'), 'utf8');

let fehler = 0;
let zaehler = 0;
function pruefe(bed, text, detail) {
    zaehler++;
    if (bed) { console.log('  OK   ' + text); }
    else { fehler++; console.log('  FEHL ' + text + (detail !== undefined ? '  -> ' + detail : '')); }
}
async function fall(name, fn) {
    console.log('\n' + name);
    try { await fn(); } catch (e) {
        fehler++; zaehler++;
        console.log('  FEHL Ausnahme: ' + (e && e.stack ? e.stack : e));
    }
}

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
function konstante(quelle, name) {
    const m = new RegExp('const ' + name + ' = [^;]*;').exec(quelle);
    if (!m) throw new Error('Konstante nicht gefunden: ' + name);
    return m[0];
}

// ── Schein-Oberfläche ───────────────────────────────────────────────────────
class El {
    constructor(tag) {
        this.tag = tag; this.children = []; this.style = {}; this.className = '';
        this._text = ''; this.listeners = {}; this.value = ''; this.disabled = false;
        this.focused = false; this.attrs = {};
    }
    appendChild(c) { this.children.push(c); return c; }
    set textContent(v) { this.children = []; this._text = String(v); }
    get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
    setAttribute(k, v) { this.attrs[k] = v; }
    focus() { this.focused = true; }
    async klick() {
        const ev = { stopPropagation() {}, preventDefault() {} };
        for (const f of (this.listeners.click || [])) await f(ev);
    }
}
function alle(wurzel, pred, aus = []) {
    if (pred(wurzel)) aus.push(wurzel);
    wurzel.children.forEach((c) => alle(c, pred, aus));
    return aus;
}
const knoepfe = (k) => alle(k, (e) => e.tag === 'button');
function knopf(k, teil) {
    const t = knoepfe(k).filter((b) => b.textContent.includes(teil));
    return t[0] || null;
}
const areas = (k) => alle(k, (e) => e.tag === 'textarea');
const mitKlasse = (k, kl) => alle(k, (e) => (' ' + e.className + ' ').includes(' ' + kl + ' '))[0] || null;
const dokument = { createElement: (tag) => new El(tag) };

// ── Schein-Backend ──────────────────────────────────────────────────────────
function backend(antworten) {
    const aufrufe = [];
    const fetchFn = async (url, opt) => {
        const methode = (opt && opt.method) || 'GET';
        const body = opt && opt.body ? JSON.parse(opt.body) : null;
        aufrufe.push({ url, methode, body });
        let a = antworten(url, methode, body);
        if (a instanceof Error) throw a;
        return { ok: true, json: async () => a };
    };
    return { fetchFn, aufrufe };
}
const vorschlagAufrufe = (b) => b.aufrufe.filter((a) => a.url.includes('/vorschlag'));
const uebernehmenAufrufe = (b) => b.aufrufe.filter((a) => a.url.includes('/uebernehmen'));
const speichernAufrufe = (b) => b.aufrufe.filter((a) => a.methode === 'POST' && a.url.endsWith('/bild-beschreibung'));

const baue = new Function(
    konstante(src, 'BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD') + '\n'
    + konstante(src, 'BESCHREIBUNG_HERKUNFT_TEXT').replace(/;$/, ';') + '\n'
    + funktionAusschneiden(src, 'beschreibungKostenText') + '\n'
    + funktionAusschneiden(src, 'baueBeschreibungKasten') + '\n'
    + 'return { baueBeschreibungKasten, beschreibungKostenText, kosten: BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD };');

function kasten(antworten, extra) {
    const b = backend(antworten);
    const log = { vorgelesen: [], gemeldet: [], text: [], offen: [] };
    const teile = baue();
    const k = teile.baueBeschreibungKasten(Object.assign({
        document: dokument, fetch: b.fetchFn, fileid: () => '4711',
        vorlesen: (t) => log.vorgelesen.push(t),
        melde: (t, ok) => log.gemeldet.push([t, ok]),
        beiText: (t) => log.text.push(t),
        beiOffen: (o) => log.offen.push(o),
    }, extra || {}));
    return { k, b, log, teile };
}
const GET_KI = (url, m) => (m === 'GET'
    ? { ok: true, fileid: '4711', beschreibung: 'Zwei Personen am Steg.', gefunden: true, quelle: 'ki' } : { ok: true });
const GET_LEER = (url, m) => (m === 'GET'
    ? { ok: true, fileid: '4711', beschreibung: '', gefunden: false, quelle: null } : { ok: true });

(async () => {
    await fall('K0) Kostenkonstante und Text', async () => {
        const { teile } = kasten(GET_KI);
        pruefe(teile.kosten === 0.001, 'benannte Konstante BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD = 0.001');
        pruefe(teile.beschreibungKostenText() === 'Kostet ca. 0,001 $ – fortfahren?', 'Text', teile.beschreibungKostenText());
    });

    await fall('(a) vorhandene Beschreibung erscheint lesend, ohne Textarea', async () => {
        const { k, log } = kasten(GET_KI);
        await k.oeffnen();
        pruefe(k.kasten.style.display === 'block', 'Kasten sichtbar');
        pruefe(areas(k.kasten).length === 0, 'keine Textarea');
        const text = mitKlasse(k.kasten, 'beschr-text');
        pruefe(text && text.textContent === 'Zwei Personen am Steg.', 'Text sichtbar', text && text.textContent);
        pruefe(mitKlasse(k.kasten, 'beschr-herkunft').textContent === 'KI-Beschreibung', 'Herkunft KI-Beschreibung');
        pruefe(!!knopf(k.kasten, '✏️ Bearbeiten') && !!knopf(k.kasten, '✨ Neu beschreiben lassen'), 'Knöpfe Bearbeiten und Neu beschreiben');
        await knopf(k.kasten, '🔊 Vorlesen').klick();
        pruefe(log.vorgelesen.length === 1 && log.vorgelesen[0] === 'Zwei Personen am Steg.', '🔊 liest den Text vor', JSON.stringify(log.vorgelesen));
        pruefe(log.offen[0] === true, 'Rückruf: Kasten offen');
        await k.oeffnen();
        pruefe(k.kasten.style.display === 'none' && log.offen[1] === false, 'zweiter Klick schließt');
    });

    await fall('(a2) Herkunftstexte hand / einzel_ki', async () => {
        for (const [quelle, erwartet] of [['hand', 'von dir bearbeitet'], ['einzel_ki', 'KI, von dir übernommen'], ['ki', 'KI-Beschreibung']]) {
            const { k } = kasten((u, m) => (m === 'GET'
                ? { ok: true, beschreibung: 'Text', gefunden: true, quelle } : { ok: true }));
            await k.oeffnen();
            pruefe(mitKlasse(k.kasten, 'beschr-herkunft').textContent === erwartet, quelle + ' -> ' + erwartet,
                mitKlasse(k.kasten, 'beschr-herkunft').textContent);
        }
    });

    await fall('(b) Bearbeiten öffnet die Textarea MIT Inhalt, Speichern schickt den Text', async () => {
        const { k, b, log } = kasten(GET_KI);
        await k.oeffnen();
        await knopf(k.kasten, '✏️ Bearbeiten').klick();
        const a = areas(k.kasten);
        pruefe(a.length === 1 && a[0].value === 'Zwei Personen am Steg.', 'Textarea mit Text gefüllt', a[0] && a[0].value);
        pruefe(a[0].maxLength === 600, 'Länge 600 wie im Backend');
        a[0].value = '  Zwei Personen am Steg, Abendlicht.  ';
        await knopf(k.kasten, '💾 Speichern').klick();
        const s = speichernAufrufe(b);
        pruefe(s.length === 1 && s[0].body.fileid === '4711' && s[0].body.beschreibung === 'Zwei Personen am Steg, Abendlicht.',
            'POST /bild-beschreibung mit getrimmtem Text', JSON.stringify(s));
        pruefe(log.text.length === 1 && log.text[0] === 'Zwei Personen am Steg, Abendlicht.', 'Rückruf beiText');
        pruefe(areas(k.kasten).length === 0, 'danach wieder lesend');
        pruefe(mitKlasse(k.kasten, 'beschr-herkunft').textContent === 'von dir bearbeitet', 'Herkunft jetzt „von dir bearbeitet“');
        pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Zwei Personen am Steg, Abendlicht.', 'neuer Text sichtbar');
    });

    await fall('(b2) Abbrechen beim Bearbeiten ändert nichts, leerer Text wird nicht gespeichert', async () => {
        const { k, b } = kasten(GET_KI);
        await k.oeffnen();
        await knopf(k.kasten, '✏️ Bearbeiten').klick();
        await knopf(k.kasten, 'Abbrechen').klick();
        pruefe(speichernAufrufe(b).length === 0, 'nichts gespeichert');
        pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Zwei Personen am Steg.', 'alter Text bleibt');
        await knopf(k.kasten, '✏️ Bearbeiten').klick();
        areas(k.kasten)[0].value = '   ';
        await knopf(k.kasten, '💾 Speichern').klick();
        pruefe(speichernAufrufe(b).length === 0, 'leerer Text wird nicht gesendet');
        pruefe(areas(k.kasten).length === 1, 'Editor bleibt offen');
    });

    await fall('(c) leerer Zustand: Hinweis und Knöpfe, keine fokussierte leere Textarea', async () => {
        const { k } = kasten(GET_LEER);
        await k.oeffnen();
        pruefe(k.kasten.textContent.includes('Für dieses Bild gibt es noch keine KI-Beschreibung.'), 'Hinweistext');
        pruefe(!!knopf(k.kasten, '✨ Neu beschreiben lassen') && !!knopf(k.kasten, '✏️ Selbst schreiben'), 'beide Knöpfe');
        pruefe(areas(k.kasten).length === 0, 'KEINE Textarea beim Öffnen');
        pruefe(alle(k.kasten, (e) => e.focused).length === 0, 'nichts fokussiert');
        await knopf(k.kasten, '✏️ Selbst schreiben').klick();
        pruefe(areas(k.kasten).length === 1 && areas(k.kasten)[0].value === '', 'erst auf Wunsch eine leere Textarea');
    });

    await fall('(c2) Abruf scheitert -> ehrlicher Leerzustand, kein Absturz', async () => {
        const { k } = kasten(() => new Error('Netz weg'));
        await k.oeffnen();
        pruefe(k.kasten.textContent.includes('noch keine KI-Beschreibung') || k.kasten.textContent.includes('nicht geladen'),
            'Hinweis statt Absturz', k.kasten.textContent);
        pruefe(areas(k.kasten).length === 0, 'keine Textarea');
    });

    await fall('(g2) Kosten VOR dem Aufruf; ohne Bestätigung kein Vision-Aufruf', async () => {
        const { k, b } = kasten((u, m) => {
            if (u.includes('/vorschlag')) return { ok: true, vorschlag: 'Ein Boot auf dem See.', modell: 'x/y', kosten_usd: 0.0009 };
            return GET_KI(u, m);
        });
        await k.oeffnen();
        await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
        pruefe(k.kasten.textContent.includes('Kostet ca. 0,001 $ – fortfahren?'), 'Kostenfrage sichtbar');
        pruefe(vorschlagAufrufe(b).length === 0, 'noch KEIN Vorschlag-Aufruf');
        await knopf(k.kasten, 'Abbrechen').klick();
        pruefe(vorschlagAufrufe(b).length === 0, 'nach Abbrechen weiter kein Aufruf');
        pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Zwei Personen am Steg.', 'zurück zur Lese-Ansicht');
        await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
        await knopf(k.kasten, 'Fortfahren').klick();
        const v = vorschlagAufrufe(b);
        pruefe(v.length === 1 && v[0].methode === 'POST' && v[0].body.fileid === '4711', 'erst nach „Fortfahren“ genau ein Aufruf', JSON.stringify(v));
    });

    await fall('(e) Vorschlag lesend; Verwerfen lässt alles unverändert; Übernehmen speichert', async () => {
        const antw = (u, m) => (u.includes('/vorschlag')
            ? { ok: true, vorschlag: 'Ein Boot auf dem See.', modell: 'x/y', kosten_usd: 0.0009 }
            : u.includes('/uebernehmen') ? { ok: true, fileid: 4711, beschreibung: 'Ein Boot auf dem See.' }
                : GET_KI(u, m));
        {
            const { k, b, log } = kasten(antw);
            await k.oeffnen();
            await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
            await knopf(k.kasten, 'Fortfahren').klick();
            pruefe(areas(k.kasten).length === 0, 'Vorschlag ohne Textarea (lesend)');
            pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Ein Boot auf dem See.', 'Vorschlagstext sichtbar');
            pruefe(k.kasten.textContent.includes('noch nicht gespeichert'), 'Hinweis: noch nicht gespeichert');
            pruefe(uebernehmenAufrufe(b).length === 0 && speichernAufrufe(b).length === 0, 'bis hier nichts gespeichert');
            await knopf(k.kasten, 'Verwerfen').klick();
            pruefe(uebernehmenAufrufe(b).length === 0 && speichernAufrufe(b).length === 0, 'Verwerfen speichert nichts');
            pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Zwei Personen am Steg.', 'alter Text unverändert');
            pruefe(log.text.length === 0, 'beiText nicht aufgerufen');
        }
        {
            const { k, b, log } = kasten(antw);
            await k.oeffnen();
            await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
            await knopf(k.kasten, 'Fortfahren').klick();
            await knopf(k.kasten, 'Übernehmen').klick();
            const u = uebernehmenAufrufe(b);
            pruefe(u.length === 1 && u[0].methode === 'POST' && u[0].body.fileid === '4711'
                && u[0].body.beschreibung === 'Ein Boot auf dem See.', 'Übernehmen: genau ein POST /uebernehmen', JSON.stringify(u));
            pruefe(speichernAufrufe(b).length === 0, 'der Hand-Weg wird nicht benutzt');
            pruefe(log.text[0] === 'Ein Boot auf dem See.', 'Rückruf beiText');
            pruefe(mitKlasse(k.kasten, 'beschr-herkunft').textContent === 'KI, von dir übernommen', 'Herkunft „KI, von dir übernommen“');
            pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Ein Boot auf dem See.', 'Text übernommen');
        }
    });

    await fall('(e2) Fehler beim Vorschlag: Grund sichtbar, nichts gespeichert, Zurück möglich', async () => {
        const { k, b } = kasten((u, m) => (u.includes('/vorschlag')
            ? { ok: false, grund: 'Die Zeitgrenze von 30 Sekunden wurde überschritten.' } : GET_KI(u, m)));
        await k.oeffnen();
        await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
        await knopf(k.kasten, 'Fortfahren').klick();
        pruefe(k.kasten.textContent.includes('Zeitgrenze von 30 Sekunden'), 'Grund sichtbar');
        pruefe(uebernehmenAufrufe(b).length === 0 && !knopf(k.kasten, 'Übernehmen'), 'kein Übernehmen angeboten');
        await knopf(k.kasten, 'Zurück').klick();
        pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Zwei Personen am Steg.', 'zurück zum alten Text');
    });

    await fall('(e3) Leerer Zustand: Neu beschreiben + Übernehmen ergibt Lese-Ansicht', async () => {
        const { k } = kasten((u, m) => (u.includes('/vorschlag') ? { ok: true, vorschlag: 'Ein Hund im Garten.', modell: 'm', kosten_usd: null }
            : u.includes('/uebernehmen') ? { ok: true } : GET_LEER(u, m)));
        await k.oeffnen();
        await knopf(k.kasten, '✨ Neu beschreiben lassen').klick();
        await knopf(k.kasten, 'Fortfahren').klick();
        await knopf(k.kasten, 'Übernehmen').klick();
        pruefe(mitKlasse(k.kasten, 'beschr-text').textContent === 'Ein Hund im Garten.', 'Text steht');
    });

    await fall('Verdrahtung: eigene Datei vor app.js, zeigeBildVollbild nutzt den Kasten, Cache-Bump', async () => {
        const zeigen = funktionAusschneiden(appSrc, 'zeigeBildVollbild');
        pruefe(/baueBeschreibungKasten\(/.test(zeigen), 'zeigeBildVollbild baut den Kasten');
        pruefe(!/beschrArea\.focus/.test(zeigen) && !/beschrArea/.test(zeigen), 'die alte sofort fokussierte Textarea ist weg');
        pruefe(/📝 Beschreibung/.test(zeigen), 'Knopf „📝 Beschreibung“ bleibt');
        const v = /app\.js\?v=(\d{8}[A-Z])/.exec(html);
        const w = /erzaehlen\.js\?v=(\d{8}[A-Z])/.exec(html);
        pruefe(v && v[1] >= '20261102E', 'app.js?v= mindestens 20261102E', v && v[1]);
        const b = /bild_beschreibung\.js\?v=(\d{8}[A-Z])/.exec(html);
        pruefe(!!b, 'index.html lädt bild_beschreibung.js mit ?v=JJJJMMTT+Buchstabe', b && b[1]);
        pruefe(html.indexOf('bild_beschreibung.js') !== -1 && html.indexOf('bild_beschreibung.js') < html.indexOf('app.js?v='),
            'bild_beschreibung.js steht VOR app.js');
        pruefe(!/function (baueBeschreibungKasten|beschreibungKostenText|bildBeschreibungVorlesen)\(/.test(appSrc)
            && !/const BESCHREIBUNG_(KOSTEN_SCHAETZUNG_USD|HERKUNFT_TEXT)/.test(appSrc),
            'app.js definiert den Kasten nicht mehr selbst (nur Nutzung)');
        pruefe(w && w[1] >= '20261102D', 'erzaehlen.js?v= mindestens 20261102D', w && w[1]);
    });

    await fall('erzaehlen.js: Hinweis bei beschreibung_gefunden === false', async () => {
        const f = new Function(funktionAusschneiden(erzSrc, 'erzaehlBeschreibungFehltHinweis')
            + '; return erzaehlBeschreibungFehltHinweis;')();
        const text = 'Für dieses Bild gibt es noch keine Bildbeschreibung';
        pruefe(f({ daten: { beschreibung_gefunden: false } }) === text, 'false -> Hinweis', f({ daten: { beschreibung_gefunden: false } }));
        pruefe(f({ daten: { beschreibung_gefunden: true } }) === '', 'true -> kein Hinweis');
        pruefe(f({ daten: {} }) === '' && f({}) === '' && f(null) === '', 'unbekannt/alte Antwort -> kein Hinweis, kein Wurf');
        const erz = funktionAusschneiden(erzSrc, 'geschichteErzeugen');
        pruefe(/erzaehlBeschreibungFehltHinweis\(res\)/.test(erz) && /erzaehl-bild-beschreibung/.test(erz),
            'geschichteErzeugen schreibt den Hinweis dorthin, wo die Beschreibung steht');
    });

    console.log('\n' + (fehler ? 'FEHLER: ' + fehler + ' von ' + zaehler + ' Pruefungen rot' : 'alle ' + zaehler + ' Pruefungen bestanden'));
    process.exit(fehler ? 1 : 0);
})();
