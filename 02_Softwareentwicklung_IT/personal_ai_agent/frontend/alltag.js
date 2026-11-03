// Alltagsprotokoll S6 (03.11.2026, Plan .hermes/plans/alltagsprotokoll.md).
//
// Ein Blatt im Agenten: sprechen (startet sofort bei ?alltag=aufnahme aus dem Pop-up) oder über
// den großen Knopf „Tastatur" tippen; POST /api/alltag/eintrag strukturiert und speichert.
// Fehlt etwas, fragt eine Einblendung je Feld nach (überspringbar, PATCH je Antwort).
// Darunter der Tagesablauf mit Ergänzen/Löschen und den Nächten der Uhr. S9: Schlaf nur noch von
// der Uhr (keine Schlafknöpfe), Gefühle nur aus der Ekman-Liste, 🎙 an jedem Textfeld über
// denselben Rekorder wie „Sprechen". Nach jedem Speichern geht der Stand aus
// /api/alltag/offen an die App (window.HeyAgentAlltag, S7). Text nur über textContent.
// Test: frontend/tests/test_alltag.js.

const ALLTAG_EREIGNIS_TEXT = {
    schlafen: 'Schlafen gegangen', aufwachen: 'Aufgewacht',
    wach_liegen: 'Wach gelegen', wieder_schlafen: 'Wieder eingeschlafen',
};
const ALLTAG_FELDER = ['stimmung', 'anspannung', 'gefuehle', 'aktivitaet'];
const ALLTAG_FRAGEN = {
    stimmung: 'Wie war deine Stimmung?',
    anspannung: 'Wie angespannt warst du (0–100)?',
    gefuehle: 'Welche Gefühle waren da? Das erste ist das stärkste.',
    aktivitaet: 'Was hast du gemacht?',
};

// ── Rein und testbar ────────────────────────────────────────────────────

/** Kopfzeile aus GET /api/alltag/offen. */
function alltagOffenText(offen) {
    if (!offen || offen.ok !== true) return '';
    if (offen.schlaeft) return 'Du schläfst — keine Erinnerung.';
    const n = offen.offene_stunden;
    if (!n) return 'Alles eingetragen.';
    return n + (n === 1 ? ' Stunde offen' : ' Stunden offen');
}

/** "HH:MM" aus einer ISO-Zeit mit Zeitzone (so, wie sie gespeichert ist). */
function alltagUhrzeit(iso) {
    return typeof iso === 'string' && iso.length >= 16 ? iso.slice(11, 16) : '';
}

/** Eine Zeile im Tagesablauf. ``stufen``: {wert: wort} aus /api/alltag/vorgaben. */
function alltagEintragText(e, stufen) {
    if (!e) return '';
    if (e.art === 'schlaf') {
        return alltagUhrzeit(e.zeit) + ' · ' + (ALLTAG_EREIGNIS_TEXT[e.ereignis] || e.ereignis);
    }
    const teile = [alltagUhrzeit(e.von) + '–' + alltagUhrzeit(e.bis)];
    if (e.aktivitaet) teile.push(e.aktivitaet);
    if (typeof e.stimmung === 'number' && stufen && stufen[e.stimmung]) teile.push('Stimmung ' + stufen[e.stimmung]);
    if (typeof e.anspannung === 'number') teile.push('Anspannung ' + e.anspannung);
    if (Array.isArray(e.gefuehle) && e.gefuehle.length) teile.push(e.gefuehle.join(', '));
    if (teile.length === 1 && e.originalworte) teile.push('„' + e.originalworte + '"');
    return teile.join(' · ');
}

/** Nacht der Uhr als Zeile. */
function alltagNachtText(n) {
    const min = n && typeof n.schlaf_min === 'number' ? n.schlaf_min : 0;
    return 'Uhr: ' + n.einschlafen + '–' + n.aufwachen + ' · ' + Math.floor(min / 60) + ' Std. ' + (min % 60) + ' Min. Schlaf';
}

/** Fehlende Felder in fester Reihenfolge der Rückfragen. */
function alltagRueckfragen(fehlt) {
    const liste = Array.isArray(fehlt) ? fehlt : [];
    return ['stimmung', 'anspannung', 'gefuehle', 'aktivitaet'].filter((f) => liste.includes(f));
}

/** Gewählte Grundgefühle, nur aus ``erlaubt`` (Ekman, /api/alltag/vorgaben), ohne Doppelte. */
function alltagGefuehle(gewaehlt, erlaubt) {
    const liste = Array.isArray(erlaubt) ? erlaubt : [];
    const erg = [];
    for (const g of gewaehlt || []) {
        if (liste.includes(g) && !erg.includes(g)) erg.push(g);
    }
    return erg;
}

/** Diktierten Text an ein Feld anhängen. */
function alltagAnhaengen(alt, neu) {
    const a = String(alt || '').trim();
    const n = String(neu || '').trim();
    return a && n ? a + ' ' + n : (a || n);
}

/** Meldung nach POST /api/alltag/eintrag. */
function alltagAntwortText(antwort) {
    if (!antwort) return 'Nicht gespeichert — bitte noch einmal.';
    if (antwort.ok !== true) {
        return (antwort.grund || 'Nicht erkannt.') + (antwort.eintrag ? ' Deine Worte sind gesichert.' : '');
    }
    const n = Array.isArray(antwort.fehlt) ? antwort.fehlt.length : 0;
    if (!n) return 'Eingetragen.';
    return 'Eingetragen — ' + (n === 1 ? 'eine Frage' : n + ' Fragen') + ' noch.';
}

/** Öffnet das Pop-up der App die Seite mit ?alltag=aufnahme? */
function alltagAufnahmeGewuenscht(suche) {
    try { return new URLSearchParams(suche || '').get('alltag') === 'aufnahme'; } catch (_) { return false; }
}

// ── Mikrofon (AudioWorklet wie app.js) ──────────────────────────────────

/** Mikrofon + AudioWorklet öffnen. Scheitert ein Schritt, wird das schon Geöffnete wieder
 *  freigegeben und der Fehler weitergereicht — sonst bliebe das Mikrofon an (Hermes S9 R2). */
async function alltagMikrofonOeffnen(medien, AudioKontext, WorkletKnoten) {
    let strom = null;
    let ctx = null;
    try {
        strom = await medien.getUserMedia({ audio: { channelCount: 1 } });
        ctx = new AudioKontext();
        if (ctx.state === 'suspended') await ctx.resume();
        await ctx.audioWorklet.addModule('pcm-recorder.js');
        const quelle = ctx.createMediaStreamSource(strom);
        const knoten = new WorkletKnoten(ctx, 'pcm-recorder');
        const stuecke = [];
        knoten.port.onmessage = (ev) => stuecke.push(ev.data);
        quelle.connect(knoten);
        knoten.connect(ctx.destination);
        return { strom, ctx, quelle, knoten, stuecke };
    } catch (err) {
        alltagMikrofonSchliessen({ strom, ctx });
        throw err;
    }
}

/** Alles freigeben, was ``alltagMikrofonOeffnen`` geöffnet hat (auch teilweise). */
function alltagMikrofonSchliessen(a) {
    if (!a) return;
    try { if (a.knoten) { a.knoten.port.onmessage = null; a.knoten.disconnect(); } } catch (_) {}
    try { if (a.quelle) a.quelle.disconnect(); } catch (_) {}
    try { if (a.ctx) a.ctx.close(); } catch (_) {}
    try { if (a.strom) a.strom.getTracks().forEach((t) => t.stop()); } catch (_) {}
}

// ── API ─────────────────────────────────────────────────────────────────

/** Satz eintragen; Antwort des Backends oder null bei Netzfehler. */
async function alltagSenden(text, quelle) {
    try {
        const res = await fetch(`${API_BASE}/api/alltag/eintrag`, {
            method: 'POST', credentials: 'same-origin', cache: 'no-store',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, quelle: quelle }),
        });
        return await res.json().catch(() => null);
    } catch (_) { return null; }
}

/** Ein Feld ergänzen; liefert die Kennung der neuen Fassung oder null. */
async function alltagFeldSpeichern(kennung, feld, wert) {
    try {
        const res = await fetch(`${API_BASE}/api/alltag/eintrag/${encodeURIComponent(kennung)}`, {
            method: 'PATCH', credentials: 'same-origin', cache: 'no-store',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [feld]: wert }),
        });
        const daten = await res.json().catch(() => null);
        return res.ok && daten && daten.eintrag ? daten.eintrag.id : null;
    } catch (_) { return null; }
}

async function _alltagHole(pfad) {
    try {
        const res = await fetch(`${API_BASE}${pfad}`, { credentials: 'same-origin', cache: 'no-store' });
        return res.ok ? await res.json() : null;
    } catch (_) { return null; }
}

// ── Oberfläche ──────────────────────────────────────────────────────────

(function () {
    const el = (id) => document.getElementById(id);
    if (!el('alltag-sheet')) return;

    const zustand = { datum: _heute(), stufen: { 5: 'sehr gut', 4: 'gut', 3: 'mittel', 2: 'schlecht', 1: 'sehr schlecht' },
        stufenListe: null, gefuehle: [], aufnahme: null, frage: null };

    function _heute() {
        const d = new Date();
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    function meldung(text) { el('alltag-meldung').textContent = text || ''; }
    function micStatus(text) { const z = el('alltag-mic-status'); z.textContent = text || ''; z.hidden = !text; }

    function knopf(id, text, klick, klasse) {
        const b = document.createElement('button');
        b.type = 'button';
        b.id = id;
        b.className = klasse || 'alltag-knopf';
        b.textContent = text;
        b.addEventListener('click', klick);
        return b;
    }

    // Blatt
    function oeffnen(mitAufnahme) {
        const sheet = el('alltag-sheet');
        if (sheet.hidden) {
            sheet.hidden = false;
            try { history.pushState({ alltag: true }, ''); } catch (_) { /* ohne Verlauf */ }
        }
        vorgabenLaden();
        aktualisieren();
        if (mitAufnahme) aufnahmeStarten();
    }

    function schliessen() {
        aufnahmeAbbrechen();
        el('alltag-sheet').hidden = true;
    }

    async function vorgabenLaden() {
        if (zustand.stufenListe) return;
        const v = await _alltagHole('/api/alltag/vorgaben');
        if (!v || !v.ok) return;
        zustand.stufenListe = v.stimmung;
        zustand.gefuehle = v.grundgefuehle || [];
        zustand.stufen = {};
        for (const s of v.stimmung) zustand.stufen[s.wert] = s.wort;
    }

    async function aktualisieren() {
        const offen = await _alltagHole('/api/alltag/offen');
        el('alltag-offen').textContent = alltagOffenText(offen);
        if (offen && offen.ok && window.HeyAgentAlltag && typeof window.HeyAgentAlltag.standSetzen === 'function') {
            try { window.HeyAgentAlltag.standSetzen(JSON.stringify(offen)); } catch (_) { /* App ohne S7 */ }
        }
        tagZeichnen(await _alltagHole('/api/alltag/tag?datum=' + zustand.datum));
    }

    // Tagesablauf
    function tagZeichnen(tag) {
        const liste = el('alltag-tag-liste');
        liste.replaceChildren();
        el('alltag-datum').textContent = zustand.datum === _heute() ? 'Heute'
            : zustand.datum.slice(8, 10) + '.' + zustand.datum.slice(5, 7) + '.';
        const eintraege = tag && tag.ok ? tag.eintraege : [];
        const naechte = tag && tag.ok ? tag.naechte_uhr : [];
        for (const n of naechte) {
            const li = document.createElement('li');
            li.className = 'alltag-zeile alltag-zeile-uhr';
            li.textContent = alltagNachtText(n);
            liste.appendChild(li);
        }
        for (const e of eintraege) {
            const li = document.createElement('li');
            li.className = 'alltag-zeile' + (e.fehlt && e.fehlt.length ? ' alltag-zeile-luecke' : '');
            const text = document.createElement('span');
            text.className = 'alltag-zeile-text';
            text.textContent = alltagEintragText(e, zustand.stufen);
            li.appendChild(text);
            const leiste = document.createElement('span');
            leiste.className = 'alltag-zeile-leiste';
            if (e.art === 'stunde') {
                const felder = e.fehlt && e.fehlt.length ? alltagRueckfragen(e.fehlt) : ALLTAG_FELDER;
                leiste.appendChild(knopf('alltag-ergaenzen-' + e.id, e.fehlt && e.fehlt.length ? 'Ergänzen' : 'Ändern',
                    () => rueckfrageStarten(e.id, felder)));
            }
            leiste.appendChild(knopf('alltag-loeschen-' + e.id, 'Löschen', () => loeschen(e.id), 'alltag-knopf alltag-leise'));
            li.appendChild(leiste);
            liste.appendChild(li);
        }
        el('alltag-tag-leer').hidden = eintraege.length + naechte.length > 0;
    }

    async function loeschen(kennung) {
        if (!window.confirm('Diesen Eintrag löschen?')) return;
        try {
            await fetch(`${API_BASE}/api/alltag/eintrag/${encodeURIComponent(kennung)}`,
                { method: 'DELETE', credentials: 'same-origin', cache: 'no-store' });
        } catch (_) { meldung('Löschen ging nicht.'); }
        aktualisieren();
    }

    function tagWechseln(schritt) {
        const d = new Date(zustand.datum + 'T12:00:00');
        d.setDate(d.getDate() + schritt);
        const neu = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
        if (neu > _heute()) return;
        zustand.datum = neu;
        aktualisieren();
    }

    // Rückfragen: ein Feld nach dem anderen, überspringbar
    function rueckfrageStarten(kennung, felder) {
        zustand.frage = { kennung: kennung, felder: felder.slice() };
        naechsteFrage();
    }

    function rueckfrageEnde() {
        if (zustand.frage) meldung('Alles gespeichert.');
        zustand.frage = null;
        el('alltag-rueckfrage').hidden = true;
        el('alltag-antworten').replaceChildren();
        aktualisieren();
    }

    async function antworten(feld, wert) {
        const neu = await alltagFeldSpeichern(zustand.frage.kennung, feld, wert);
        if (!neu) { meldung('Nicht gespeichert — bitte noch einmal.'); return; }
        zustand.frage.kennung = neu;
        naechsteFrage();
    }

    function naechsteFrage() {
        const z = zustand.aufnahme && zustand.aufnahme.ziel;
        if (z && el('alltag-antworten').contains(z)) aufnahmeAbbrechen();   // Feld verschwindet gleich
        const f = zustand.frage;
        if (!f || !f.felder.length) { rueckfrageEnde(); return; }
        const feld = f.felder.shift();
        el('alltag-rueckfrage').hidden = false;
        el('alltag-frage').textContent = ALLTAG_FRAGEN[feld];
        const box = el('alltag-antworten');
        box.replaceChildren();
        if (feld === 'stimmung') {
            const stufen = zustand.stufenListe || Object.keys(zustand.stufen).sort().reverse()
                .map((w) => ({ wert: Number(w), wort: zustand.stufen[w] }));
            for (const s of stufen) {
                box.appendChild(knopf('alltag-stimmung-' + s.wert, s.wort, () => antworten('stimmung', s.wert), 'alltag-knopf alltag-wahl'));
            }
        } else if (feld === 'anspannung') {
            const regler = document.createElement('input');
            regler.type = 'range'; regler.min = '0'; regler.max = '100'; regler.step = '5'; regler.value = '30';
            regler.id = 'alltag-anspannung-regler';
            regler.className = 'alltag-regler';
            const wert = document.createElement('output');
            wert.id = 'alltag-anspannung-wert';
            wert.textContent = regler.value;
            regler.addEventListener('input', () => { wert.textContent = regler.value; });
            box.append(regler, wert,
                knopf('alltag-anspannung-ok', 'OK', () => antworten('anspannung', Number(regler.value)), 'alltag-knopf alltag-primaer'));
        } else if (feld === 'gefuehle') {
            const gewaehlt = [];
            zustand.gefuehle.forEach((g, i) => {
                const b = knopf('alltag-gefuehl-' + i, g, () => {
                    const pos = gewaehlt.indexOf(g);
                    if (pos === -1) gewaehlt.push(g); else gewaehlt.splice(pos, 1);
                    b.setAttribute('aria-pressed', String(pos === -1));
                }, 'alltag-knopf alltag-wahl');
                b.setAttribute('aria-pressed', 'false');
                box.appendChild(b);
            });
            box.append(knopf('alltag-gefuehle-ok', 'OK', () => {
                const liste = alltagGefuehle(gewaehlt, zustand.gefuehle);
                if (liste.length) antworten('gefuehle', liste); else naechsteFrage();
            }, 'alltag-knopf alltag-primaer'));
        } else {
            const text = document.createElement('input');
            text.type = 'text'; text.id = 'alltag-aktivitaet-feld'; text.className = 'alltag-feld';
            text.placeholder = 'z. B. Wäsche gemacht';
            const mic = knopf('alltag-aktivitaet-mic', '🎙', () => aufnahmeStarten(text, mic), 'alltag-knopf alltag-feld-mic');
            mic.setAttribute('aria-label', 'Tätigkeit diktieren');
            box.append(text, mic, knopf('alltag-aktivitaet-ok', 'OK', () => {
                const wert = text.value.trim();
                if (wert) antworten('aktivitaet', wert); else naechsteFrage();
            }, 'alltag-knopf alltag-primaer'));
        }
    }

    // Eintragen
    async function eintragen(text, quelle) {
        if (!text || !text.trim()) return;
        meldung('Wird eingetragen …');
        const antwort = await alltagSenden(text.trim(), quelle);
        meldung(alltagAntwortText(antwort));
        if (antwort && antwort.eintrag) {
            const fragen = alltagRueckfragen(antwort.fehlt);
            if (fragen.length) { rueckfrageStarten(antwort.eintrag.id, fragen); return; }
        }
        aktualisieren();
    }

    // Aufnahme (AudioWorklet wie app.js; WAV über dessen encodeWav). Ohne ``ziel`` wird der Text
    // ein Eintrag; mit ``ziel`` (Textfeld) wird er dort angehängt. Immer nur eine Aufnahme.
    function aufnahmeFreigeben() {
        const a = zustand.aufnahme;
        if (!a) return;
        alltagMikrofonSchliessen(a);
        zustand.aufnahme = null;
        el('alltag-aufnahme').textContent = '🎙 Sprechen';
        el('alltag-aufnahme').classList.remove('alltag-hoert');
        if (a.knopf) { a.knopf.textContent = '🎙'; a.knopf.classList.remove('alltag-hoert'); }
    }

    function aufnahmeAbbrechen() { aufnahmeFreigeben(); micStatus(''); }

    async function aufnahmeStarten(ziel, feldKnopf) {
        if (zustand.oeffnet) return;   // Mikrofon öffnet noch (Freigabe-Dialog) — Doppeltipp ignorieren
        if (zustand.aufnahme) { aufnahmeStoppen(); return; }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            micStatus('Mikrofon nur über localhost/HTTPS — bitte „Tastatur" nehmen.');
            return;
        }
        let offen;
        zustand.oeffnet = true;
        try {
            offen = await alltagMikrofonOeffnen(navigator.mediaDevices,
                window.AudioContext || window.webkitAudioContext, window.AudioWorkletNode);
        } catch (err) {
            micStatus('Mikrofon nicht verfügbar — bitte „Tastatur" nehmen.');
            return;
        } finally {
            zustand.oeffnet = false;
        }
        if (el('alltag-sheet').hidden || (ziel && !ziel.isConnected)) {   // inzwischen geschlossen
            alltagMikrofonSchliessen(offen);
            return;
        }
        zustand.aufnahme = Object.assign(offen, { ziel: ziel || null, knopf: feldKnopf || null });
        if (feldKnopf) {
            feldKnopf.textContent = '■';
            feldKnopf.classList.add('alltag-hoert');
            micStatus('Ich höre zu — noch einmal 🎙 tippen, wenn du fertig bist.');
        } else {
            el('alltag-aufnahme').textContent = '■ Fertig';
            el('alltag-aufnahme').classList.add('alltag-hoert');
            micStatus('Ich höre zu — erzähl von der letzten Stunde.');
        }
    }

    async function aufnahmeStoppen() {
        const a = zustand.aufnahme;
        if (!a) return;
        const rate = a.ctx.sampleRate || 48000;
        const stuecke = a.stuecke;
        const ziel = a.ziel;
        aufnahmeFreigeben();
        if (!stuecke.length) { micStatus(''); return; }
        micStatus('Wird verschriftet …');
        let text = '';
        try {
            const form = new FormData();
            form.append('file', encodeWav(stuecke, rate), 'audio.wav');
            const res = await fetch(`${API_BASE}/api/sprache/transkript`, { method: 'POST', credentials: 'same-origin', body: form });
            const daten = await res.json().catch(() => ({}));
            text = typeof daten.text === 'string' ? daten.text.trim() : '';
        } catch (_) { /* unten gemeldet */ }
        micStatus('');
        if (!text) { meldung('Nichts verstanden — noch einmal oder „Tastatur".'); return; }
        if (ziel) {
            if (!ziel.isConnected) return;   // Feld ist inzwischen weg
            ziel.value = alltagAnhaengen(ziel.value, text);
            ziel.focus();
            return;
        }
        eintragen(text, 'sprache');
    }

    function tastatur() {
        aufnahmeAbbrechen();
        el('alltag-text-block').hidden = false;
        el('alltag-text').focus();
    }

    // Verdrahtung
    el('alltag-btn').addEventListener('click', () => oeffnen(false));
    el('alltag-close').addEventListener('click', () => { schliessen(); try { history.back(); } catch (_) {} });
    el('alltag-sheet').addEventListener('click', (ev) => { if (ev.target === el('alltag-sheet')) schliessen(); });
    window.addEventListener('popstate', () => { if (!el('alltag-sheet').hidden) schliessen(); });
    el('alltag-aufnahme').addEventListener('click', () => aufnahmeStarten());
    el('alltag-text-mic').addEventListener('click', () => aufnahmeStarten(el('alltag-text'), el('alltag-text-mic')));
    el('alltag-tastatur').addEventListener('click', tastatur);
    el('alltag-senden').addEventListener('click', () => {
        const feld = el('alltag-text');
        const text = feld.value;
        feld.value = '';
        eintragen(text, 'tastatur');
    });
    el('alltag-ueberspringen').addEventListener('click', naechsteFrage);
    el('alltag-tag-vor').addEventListener('click', () => tagWechseln(-1));
    el('alltag-tag-weiter').addEventListener('click', () => tagWechseln(1));

    if (alltagAufnahmeGewuenscht(window.location.search)) oeffnen(true);
})();
