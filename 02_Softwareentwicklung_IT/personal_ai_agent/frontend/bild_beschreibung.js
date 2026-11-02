/* Bildbeschreibung im Vollbild-Editor: zuerst lesen, dann bearbeiten, neu beschreiben (G2, 02.11.2026)
 *
 * Eigene Datei (schlank und modular): app.js ruft nur noch ``baueBeschreibungKasten`` auf
 * (``zeigeBildVollbild``). Klassisches Skript, wird in index.html VOR app.js geladen; alle
 * Abhängigkeiten (document, fetch, Vorlesen, Meldungen, Rückrufe) kommen über ``deps`` herein und
 * sind im Test einspielbar (frontend/tests/test_bild_beschreibung_lesen.js).
 *
 * Enthält: BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD, BESCHREIBUNG_HERKUNFT_TEXT, beschreibungKostenText,
 * bildBeschreibungVorlesen, baueBeschreibungKasten.
 */

// ── Bildbeschreibung im Vollbild-Editor: zuerst lesen, dann bearbeiten (G2, 02.11.2026) ──
// Geschätzte Kosten EINES Vorschlags (Vorschaubild 480x480 + höchstens 400 Ausgabe-Token bei
// google/gemini-3.7-flash, Preise 0,75 / 3,75 USD je 1 Mio Token). Schätzwert, ungemessen;
// Herleitung im Changelog docs/changelog-2026-11-02-bildbeschreibung-lesen-bearbeiten.md.
const BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD = 0.001;
const BESCHREIBUNG_HERKUNFT_TEXT = { ki: 'KI-Beschreibung', hand: 'von dir bearbeitet', einzel_ki: 'KI, von dir übernommen' };

function beschreibungKostenText() {
    return 'Kostet ca. ' + String(BESCHREIBUNG_KOSTEN_SCHAETZUNG_USD).replace('.', ',') + ' $ – fortfahren?';
}

/** Beschreibungstext vorlesen: Umschalter (``window.vorleseTextMitKnopf`` — zweiter Druck auf
 *  denselben Knopf hält an), sonst der alte Vorlese-Weg, sonst Browserstimme. ``knopf`` optional. */
function bildBeschreibungVorlesen(txt, knopf) {
    txt = String(txt || '').trim();
    if (!txt) return;
    if (typeof window.audioVorabFreischalten === 'function') window.audioVorabFreischalten();
    if (typeof window.vorleseTextMitKnopf === 'function') {
        window.vorleseTextMitKnopf(txt, knopf);
    } else if (typeof window.vorlesenText === 'function') {
        window.vorlesenText(txt);
    } else if (window.speechSynthesis && typeof SpeechSynthesisUtterance === 'function') {
        try {
            window.speechSynthesis.cancel();
            const satz = new SpeechSynthesisUtterance(txt);
            satz.lang = 'de-DE';
            window.speechSynthesis.speak(satz);
        } catch (_e) {}
    }
}

/** Baut den Beschreibungs-Kasten des Vollbild-Editors. ``deps``: document, fetch, fileid(),
 *  vorlesen(text), melde(text, ok), beiText(text), beiOffen(offen), bekannterText() — alles
 *  einspielbar (Test mit Schein-Oberfläche). Ansichten: lesen, leer, bearbeiten, Kostenfrage,
 *  Vorschlag (lesend). Der Vision-Aufruf passiert erst nach „Fortfahren“; gespeichert wird
 *  erst durch „Speichern“ bzw. „Übernehmen“. */
function baueBeschreibungKasten(deps) {
    const doc = deps.document;
    const melde = (t, ok) => { if (deps.melde) deps.melde(t, ok); };
    const kasten = doc.createElement('div');
    kasten.className = 'vollbild-beschreibung-kasten';
    kasten.style.cssText = 'position:fixed;top:60px;left:50%;transform:translateX(-50%);width:min(90vw, 500px);max-height:70vh;overflow-y:auto;background:#1a2332;border:1px solid #304562;border-radius:12px;padding:12px;z-index:99999;box-shadow:0 8px 24px rgba(0,0,0,0.6);color:#e0e0e0;font-size:0.9rem;line-height:1.4;';
    kasten.style.display = 'none';
    const titel = doc.createElement('div');
    titel.className = 'beschr-titel';
    titel.style.cssText = 'font-weight:bold;margin-bottom:6px;color:#d9f;font-size:0.95rem;';
    titel.textContent = '📝 Bildbeschreibung';
    const inhalt = doc.createElement('div');
    inhalt.className = 'beschr-inhalt';
    kasten.appendChild(titel);
    kasten.appendChild(inhalt);

    let aktuell = { text: '', quelle: null };
    let lauf = 0;                                  // verwirft Antworten, wenn der Kasten inzwischen zu ist

    function el(tag, klasse, text) {
        const e = doc.createElement(tag);
        if (klasse) e.className = klasse;
        if (text !== undefined) e.textContent = text;
        return e;
    }
    function knopf(text, fn, stil) {
        const b = el('button', 'beschr-knopf', text);
        b.type = 'button';
        b.style.cssText = 'padding:6px 12px;border-radius:6px;border:none;cursor:pointer;color:#fff;background:' + (stil || '#334155') + ';';
        b.addEventListener('click', (ev) => {
            if (ev && ev.stopPropagation) ev.stopPropagation();
            return fn();
        });
        return b;
    }
    function leiste(knoepfe) {
        const l = el('div', 'beschr-leiste');
        l.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;justify-content:flex-end;';
        knoepfe.forEach((k) => l.appendChild(k));
        return l;
    }
    function zeige(kinder) {
        inhalt.textContent = '';
        kinder.forEach((k) => inhalt.appendChild(k));
    }
    async function senden(url, koerper) {
        const antwort = await deps.fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(koerper),
        });
        return antwort.json();
    }

    function zurueck() { return aktuell.text ? zeigeLesen() : zeigeLeer(); }

    function zeigeLesen() {
        const herkunft = el('div', 'beschr-herkunft', BESCHREIBUNG_HERKUNFT_TEXT[aktuell.quelle] || 'Beschreibung');
        herkunft.style.cssText = 'font-size:0.75rem;color:#8f8;margin-bottom:4px;';
        const text = el('div', 'beschr-text', aktuell.text);
        text.style.cssText = 'white-space:pre-wrap;word-break:break-word;text-align:left;';
        // Vorlese-Knopf als Umschalter: reicht sich selbst durch, damit der zweite
        // Druck auf denselben Knopf anhält (vgl. erzaehlen.js, 02.11.2026).
        const vorleseBtn = knopf('🔊 Vorlesen', () => { if (deps.vorlesen) deps.vorlesen(aktuell.text, vorleseBtn); }, '#1a3d28');
        zeige([herkunft, text, leiste([
            vorleseBtn,
            knopf('✏️ Bearbeiten', () => zeigeBearbeiten(aktuell.text), '#334155'),
            knopf('✨ Neu beschreiben lassen', () => zeigeKosten(), '#5b3a7a'),
            knopf('Schließen', () => schliessen(), '#334155'),
        ])]);
    }

    function zeigeLeer() {
        const hinweis = el('div', 'beschr-hinweis', 'Für dieses Bild gibt es noch keine KI-Beschreibung.');
        zeige([hinweis, leiste([
            knopf('✨ Neu beschreiben lassen', () => zeigeKosten(), '#5b3a7a'),
            knopf('✏️ Selbst schreiben', () => zeigeBearbeiten(''), '#334155'),
            knopf('Schließen', () => schliessen(), '#334155'),
        ])]);
    }

    function zeigeNichtGeladen() {
        zeige([el('div', 'beschr-hinweis', 'Die Beschreibung konnte nicht geladen werden.'), leiste([
            knopf('Nochmal laden', () => laden(++lauf), '#334155'),
            knopf('Schließen', () => schliessen(), '#334155'),
        ])]);
    }

    function zeigeBearbeiten(startText) {
        const area = el('textarea', 'beschr-area');
        area.rows = 4;
        area.maxLength = 600;
        area.value = startText || '';
        area.placeholder = 'Beschreibung für dieses Foto eingeben...';
        area.style.cssText = 'width:100%;box-sizing:border-box;border-radius:8px;padding:8px;background:#0f172a;color:#f1f5f9;border:1px solid #334155;font-size:0.9rem;resize:vertical;';
        zeige([area, leiste([
            knopf('Abbrechen', () => zurueck(), '#334155'),
            knopf('💾 Speichern', () => speichern(area), '#2563eb'),
        ])]);
        try { area.focus(); } catch (_e) {}
    }

    async function speichern(area) {
        const txt = String(area.value || '').trim();
        const fid = deps.fileid();
        if (!txt) { melde('Ein leerer Text wird nicht gespeichert.', false); return; }
        if (!fid) { melde('Keine Bildkennung vorhanden', false); return; }
        let d = null;
        try { d = await senden('/api/erzaehlen/bild-beschreibung', { fileid: fid, beschreibung: txt }); } catch (_e) {}
        if (d && d.ok) {
            aktuell = { text: (typeof d.beschreibung === 'string' && d.beschreibung) ? d.beschreibung : txt, quelle: 'hand' };
            if (deps.beiText) deps.beiText(aktuell.text);
            melde('✓ Bildbeschreibung gespeichert', true);
            zeigeLesen();
        } else {
            melde('Fehler beim Speichern', false);
        }
    }

    function zeigeKosten() {
        zeige([el('div', 'beschr-kosten', beschreibungKostenText()), leiste([
            knopf('Abbrechen', () => zurueck(), '#334155'),
            knopf('Fortfahren', () => vorschlagHolen(), '#5b3a7a'),
        ])]);
    }

    async function vorschlagHolen() {
        const fid = deps.fileid();
        if (!fid) { melde('Keine Bildkennung vorhanden', false); return; }
        const token = ++lauf;
        zeige([el('div', 'beschr-lade', 'Das Bild wird beschrieben …')]);
        let d = null;
        try { d = await senden('/api/erzaehlen/bild-beschreibung/vorschlag', { fileid: fid }); } catch (_e) {}
        if (token !== lauf) return;
        if (d && d.ok && typeof d.vorschlag === 'string' && d.vorschlag.trim()) {
            zeigeVorschlag(d);
        } else {
            zeigeFehler((d && d.grund) ? d.grund : 'Der Vorschlag konnte nicht erstellt werden.');
        }
    }

    function zeigeVorschlag(d) {
        const kopf = el('div', 'beschr-herkunft', 'Vorschlag der KI – noch nicht gespeichert');
        kopf.style.cssText = 'font-size:0.75rem;color:#fd9;margin-bottom:4px;';
        const text = el('div', 'beschr-text', d.vorschlag.trim());
        text.style.cssText = 'white-space:pre-wrap;word-break:break-word;text-align:left;';
        const teile = [kopf, text];
        if (typeof d.kosten_usd === 'number') {
            const k = el('div', 'beschr-kosten-ist', 'Kosten dieses Aufrufs: ca. ' + d.kosten_usd.toFixed(4).replace('.', ',') + ' $');
            k.style.cssText = 'font-size:0.72rem;color:#9aa;margin-top:4px;';
            teile.push(k);
        }
        teile.push(leiste([
            knopf('Verwerfen', () => zurueck(), '#334155'),
            knopf('Übernehmen', () => uebernehmen(d.vorschlag.trim()), '#2563eb'),
        ]));
        zeige(teile);
    }

    function zeigeFehler(grund) {
        zeige([el('div', 'beschr-fehler', String(grund)), leiste([
            knopf('Zurück', () => zurueck(), '#334155'),
            knopf('Nochmal', () => zeigeKosten(), '#5b3a7a'),
        ])]);
    }

    async function uebernehmen(text) {
        const fid = deps.fileid();
        if (!fid) { melde('Keine Bildkennung vorhanden', false); return; }
        let d = null;
        try { d = await senden('/api/erzaehlen/bild-beschreibung/uebernehmen', { fileid: fid, beschreibung: text }); } catch (_e) {}
        if (d && d.ok) {
            aktuell = { text: (typeof d.beschreibung === 'string' && d.beschreibung) ? d.beschreibung : text, quelle: 'einzel_ki' };
            if (deps.beiText) deps.beiText(aktuell.text);
            melde('✓ Bildbeschreibung übernommen', true);
            zeigeLesen();
        } else {
            melde('Fehler beim Übernehmen', false);
        }
    }

    async function laden(token) {
        const fid = deps.fileid();
        zeige([el('div', 'beschr-lade', 'Lade …')]);
        if (!fid) { aktuell = { text: '', quelle: null }; zeigeLeer(); return; }
        let d = null;
        try {
            const antwort = await deps.fetch('/api/erzaehlen/bild-beschreibung?fileid=' + encodeURIComponent(fid));
            d = await antwort.json();
        } catch (_e) {}
        if (token !== lauf) return;
        if (d && d.ok !== false && typeof d.beschreibung === 'string') {
            aktuell = d.gefunden && d.beschreibung.trim()
                ? { text: d.beschreibung.trim(), quelle: d.quelle || null }
                : { text: '', quelle: null };
            zurueck();
            return;
        }
        const bekannt = deps.bekannterText ? String(deps.bekannterText() || '').trim() : '';
        if (bekannt) { aktuell = { text: bekannt, quelle: null }; zeigeLesen(); } else { zeigeNichtGeladen(); }
    }

    function schliessen() {
        lauf++;
        kasten.style.display = 'none';
        if (deps.beiOffen) deps.beiOffen(false);
    }

    async function oeffnen() {
        if (kasten.style.display === 'block') { schliessen(); return; }
        const token = ++lauf;
        kasten.style.display = 'block';
        if (deps.beiOffen) deps.beiOffen(true);
        await laden(token);
    }

    return { kasten, oeffnen, schliessen };
}
