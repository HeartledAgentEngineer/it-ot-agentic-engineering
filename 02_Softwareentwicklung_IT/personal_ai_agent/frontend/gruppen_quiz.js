/**
 * Personen benennen im Gruppenmodus (Plan Foto-Gedächtnis Schritt 2, 01.10.2026)
 * ------------------------------------------------------------------------------
 * Statt Bild für Bild: ganze Gesichter-Gruppen auf einmal benennen, die größte
 * offene zuerst. Backend: app/services/gruppen_quiz.py, Routen /api/gruppen.
 *
 * Bewusst eine EIGENE Datei (wie erzaehlen.js / wecken.js) — der Quiz-Code in
 * app.js bleibt unberührt. app.js ergänzt window.fetch global um den API-Key
 * (Skript-Reihenfolge in index.html: app.js VOR dieser Datei).
 *
 * Gesichter: Vorschaubild 480x480 aus der pCloud (/api/cloud/thumb), der
 * Ausschnitt wird im Browser auf ein <canvas> gezeichnet und die Objekt-URL
 * sofort wieder freigegeben — nichts wird gespeichert. Antippen zeigt das
 * ganze Foto (800x800) im Vollbild von app.js (zeigeBildVollbild, mit Zoom).
 */

// =========================================================================
// Reine Funktionen (ohne DOM) — geprüft von frontend/tests/test_gruppen_quiz.js
// =========================================================================

/**
 * Quadratischer Ausschnitt um ein Gesicht im Vorschaubild.
 * bbox = [x, y, w, h] in Originalpixeln (breite x hoehe); bildW/bildH = Maße
 * des geladenen Vorschaubilds. Passt das Seitenverhältnis nicht (Vorschau
 * anders gedreht als die Erkennung), kommt null — dann zeigt die Oberfläche
 * das ganze Bild statt eines falschen Ausschnitts.
 * @returns {{x:number,y:number,w:number,h:number}|null}
 */
function gruppenAusschnitt(bbox, breite, hoehe, bildW, bildH, rand) {
    if (!Array.isArray(bbox) || bbox.length < 4 || !(breite > 0) || !(hoehe > 0)
        || !(bildW > 0) || !(bildH > 0)) return null;
    const sx = bildW / breite, sy = bildH / hoehe;
    if (Math.abs(sx - sy) / Math.max(sx, sy) > 0.06) return null;
    const r = (typeof rand === 'number') ? rand : 0.35;
    const cx = (bbox[0] + bbox[2] / 2) * sx;
    const cy = (bbox[1] + bbox[3] / 2) * sy;
    let seite = Math.max(bbox[2] * sx, bbox[3] * sy) * (1 + 2 * r);
    seite = Math.min(seite, bildW, bildH);
    if (!(seite > 0)) return null;
    const x = Math.max(0, Math.min(cx - seite / 2, bildW - seite));
    const y = Math.max(0, Math.min(cy - seite / 2, bildH - seite));
    return { x: x, y: y, w: seite, h: seite };
}

/** Dateikennung eines Beispiels: die Gesichterliste liefert ``fileid``, die
 *  Personenvorschläge (personen_beispiele.json) liefern ``bild_id``. Ohne
 *  diese Fallunterscheidung bleiben die Kacheln bei benannten Personen leer. */
function gesichtKennung(beispiel) {
    if (!beispiel) return null;
    const id = (beispiel.fileid != null && beispiel.fileid !== '')
        ? beispiel.fileid : beispiel.bild_id;
    return (id != null && id !== '') ? id : null;
}

/** Rahmen des referenzierten Gesichts für die Gesamtansicht (normiert 0..1).
 *  bbox = [x, y, w, h] in Originalpixeln (breite x hoehe); gerechnet wird mit
 *  bbox_norm, damit Zoom und Drehung den Rahmen am Gesicht lassen. Fehlen die
 *  Maße oder ist die bbox unbrauchbar, kommt null — dann wird nichts markiert
 *  (kein Rahmen auf dem falschen Fleck). */
function gesichtRahmen(beispiel) {
    if (!beispiel) return null;
    const b = beispiel.bbox;
    const br = Number(beispiel.breite), ho = Number(beispiel.hoehe);
    if (!Array.isArray(b) || b.length < 4 || !(br > 0) || !(ho > 0)) return null;
    const werte = [Number(b[0]), Number(b[1]), Number(b[2]), Number(b[3])];
    if (!werte.every(function (w) { return Number.isFinite(w); })
        || !(werte[2] > 0) || !(werte[3] > 0)) return null;
    return {
        bbox_norm: [werte[0] / br, werte[1] / ho, werte[2] / br, werte[3] / ho],
        bbox: werte,
    };
}

/** Zeitraum einer Gruppe: „2016–2025", „2022" oder "" (ohne Daten). */
function gruppenZeitraum(von, bis) {
    const a = (typeof von === 'string') ? von.slice(0, 4) : '';
    const b = (typeof bis === 'string') ? bis.slice(0, 4) : '';
    if (a && b) return a === b ? a : a + '–' + b;
    return a || b || '';
}

/** Ganze Zahl mit deutschem Tausenderpunkt. */
function gruppenZahl(n) {
    const z = Math.round(Number(n) || 0);
    return String(z).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/** Fortschrittszeile aus /api/gruppen/stand. */
function gruppenFortschritt(stand) {
    if (!stand || stand.ok !== true) return '';
    const teile = [gruppenZahl(stand.benannt) + ' von ' + gruppenZahl(stand.gruppen) + ' Vorschlägen benannt'];
    if (stand.gesichter) {
        teile.push(gruppenZahl(stand.gesichter_benannt) + ' von ' + gruppenZahl(stand.gesichter) + ' Gesichtern');
    }
    if (stand.unbekannt) teile.push(gruppenZahl(stand.unbekannt) + ' unbekannt');
    return teile.join(' · ');
}

/** Kopfzeile einer Gruppe: Größe, Fotos, Zeitraum. */
function gruppenMeta(g) {
    if (!g) return '';
    const teile = [gruppenZahl(g.groesse) + ' Gesichter'];
    if (g.bilder) teile.push(gruppenZahl(g.bilder) + (g.bilder === 1 ? ' Foto' : ' Fotos'));
    if (g.videos) teile.push(gruppenZahl(g.videos) + (g.videos === 1 ? ' Video' : ' Videos'));
    const zr = gruppenZeitraum(g.von, g.bis);
    if (zr) teile.push(zr);
    return teile.join(' · ');
}

/** Hinweis zu einem Zwillings-Kandidaten. Gemeinsame Fotos = zwei Menschen. */
function gruppenZwillingText(z) {
    if (!z) return '';
    const wer = z.name ? z.name : 'ein noch unbenannter Vorschlag';
    let text = 'Ähnlich: ' + wer + ' – dieselbe Person?';
    if (z.gemeinsame_bilder > 0) {
        text += ' — beide zusammen auf ' + gruppenZahl(z.gemeinsame_bilder)
            + (z.gemeinsame_bilder === 1 ? ' Foto' : ' Fotos')
            + ', also wohl zwei Menschen (z. B. Geschwister)';
        text = text.replace(' – dieselbe Person?', '');
    }
    return text;
}

/** Sichtbare Nummer eines Vorschlags: „Person_1003" → „Vorschlag 1003". */
function gruppenNummer(kennung) {
    const m = /(\d+)\s*$/.exec(String(kennung || ''));
    return m ? 'Vorschlag ' + m[1] : '';
}

/** Kopfzeile der verbundenen Vorschläge („= dieselbe Person" ohne Namen). */
function gruppenVerbundenText(verbunden) {
    const n = Array.isArray(verbunden) ? verbunden.length : 0;
    if (!n) return '';
    return '🔗 Verbunden mit ' + (n === 1 ? '1 weiteren Vorschlag' : n + ' weiteren Vorschlägen')
        + ' — der Name gilt für alle';
}

/** Rückmeldung nach einer Antwort; ``wechsel`` = ein anderer Vorschlag ist jetzt dran. */
function gruppenAntwortText(art, s, wechsel) {
    s = s || {};
    const weitere = s.weitere > 0
        ? ' · auch für ' + (s.weitere === 1 ? '1 verbundenen Vorschlag' : s.weitere + ' verbundene Vorschläge')
        : '';
    const texte = {
        name: '✓ ' + (s.name || '') + ' gespeichert' + (s.notiz ? ' · Erinnerung angelegt' : '') + weitere,
        gleich: s.name
            ? '✓ als dieselbe Person gemerkt (' + s.name + ')' + weitere
            : '✓ verbunden — der Name, den du jetzt vergibst, gilt für beide',
        verschieden: '✓ als zwei Menschen gemerkt',
        spaeter: '⏭ zurückgestellt — kommt zum Schluss wieder',
        unbekannt: '🚫 wird nicht mehr gefragt',
    };
    return (texte[art] || '✓ gespeichert') + (wechsel ? ' → nächster Vorschlag' : '');
}

/** Infozeile der Gesamtansicht. */
function gruppenAlleInfo(antwort, geladen) {
    if (!antwort || antwort.ok !== true) return '';
    const teile = ['Tippe die Gesichter an, die NICHT zu dieser Person gehören.',
                   gruppenZahl(antwort.gesamt) + ' Gesichter'];
    if (geladen < antwort.gesamt) teile.push(gruppenZahl(geladen) + ' geladen');
    if (antwort.ausgeschlossen) teile.push(gruppenZahl(antwort.ausgeschlossen) + ' schon ausgeschlossen');
    return teile.join(' · ');
}

/** Beschriftung des Ausschluss-Knopfs. */
function gruppenAusschlussKnopf(anzahl) {
    if (!anzahl) return 'Gesichter antippen zum Ausschließen';
    return '🚫 ' + gruppenZahl(anzahl) + (anzahl === 1 ? ' Gesicht ausschließen' : ' Gesichter ausschließen');
}

/** Geburtstag aus dem Telefonbuch lesbar: „1997-03-14“ → „14.03.1997“, „--08-02“ → „02.08.“. */
function gruppenGeburtstagText(gb) {
    if (typeof gb !== 'string') return '';
    let m = gb.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return m[3] + '.' + m[2] + '.' + m[1];
    m = gb.match(/^--(\d{2})-(\d{2})$/);
    return m ? m[2] + '.' + m[1] + '.' : '';
}

/** Zweite Zeile eines Suchtreffers (nur Hinweise, keine Nummern). */
function gruppenTrefferInfo(eintrag, art) {
    if (!eintrag) return '';
    if (art === 'person') {
        const teile = ['schon benannt'];
        if (eintrag.beziehung) teile.push(eintrag.beziehung);
        if (eintrag.kontakt) teile.push('📇 verknüpft');
        return teile.join(' · ');
    }
    const teile = ['📇 Kontakt'];
    const gb = gruppenGeburtstagText(eintrag.geburtstag);
    if (gb) teile.push('🎂 ' + gb);
    if (eintrag.nummern) teile.push(eintrag.nummern === 1 ? '1 Nummer' : eintrag.nummern + ' Nummern');
    if (eintrag.verknuepft_mit) teile.push('schon bei ' + eintrag.verknuepft_mit);
    return teile.join(' · ');
}

/**
 * Läuft am Erinnerungsfeld noch ein Diktat? Ja, solange aufgenommen wird oder
 * nach dem Stopp die Erkennung noch nichts ins Feld geschrieben hat (höchstens
 * bis ``offen.bis``). Sonst landete der Text erst im Feld des NÄCHSTEN
 * Vorschlags — also bei der falschen Person.
 */
function gruppenDiktatOffen(aufnahme, offen, wertJetzt, jetztMs) {
    if (aufnahme) return true;
    if (!offen || typeof offen.bis !== 'number') return false;
    return jetztMs < offen.bis && wertJetzt === offen.wert;
}

/** Kurzinfo zu einem vorhandenen Profil (Beziehung, Zahl der Erinnerungen). */
function gruppenProfilText(p) {
    if (!p || p.ok !== true) return '';
    const teile = [];
    if (p.beziehung) teile.push(p.beziehung);
    const n = (p.notizen || []).length;
    if (n) teile.push(n + (n === 1 ? ' Erinnerung' : ' Erinnerungen'));
    return teile.length ? 'Bekannt: ' + teile.join(' · ') : '';
}

// ── Benannte Personen wieder aufrufen (02.10.2026) ─────────────────────────

/** Suchformen eines Textes: klein, „ä→ae“ und ohne Akzente („ä→a“) — wie im Backend. */
function gruppenSuchformen(text) {
    const klein = String(text || '').toLowerCase();
    const ersetzt = klein.replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss');
    const ohne = klein.normalize('NFD').replace(/\p{M}/gu, '');
    return ersetzt === ohne ? [ersetzt] : [ersetzt, ohne];
}

/** Passt ``frage`` an einen Wortanfang im Namen? Jedes Wort der Frage muss passen; leer passt immer. */
function gruppenPersonPasst(name, frage) {
    const worte = String(frage || '').trim().split(/\s+/).filter(Boolean);
    if (!worte.length) return true;
    const namensWorte = [];
    gruppenSuchformen(name).forEach((form) => form.split(/[\s\-.,()]+/).forEach((w) => { if (w) namensWorte.push(w); }));
    return worte.every((wort) => gruppenSuchformen(wort)
        .some((f) => namensWorte.some((w) => w.indexOf(f) === 0)));
}

/** Zweite Zeile in der Liste „Benannt“. */
function gruppenPersonInfo(p) {
    if (!p) return '';
    const teile = [gruppenZahl(p.gesichter) + ' Gesichter'];
    if (p.vorschlaege > 1) teile.push(p.vorschlaege + ' Vorschläge');
    if (p.beziehung) teile.push(p.beziehung);
    if (p.erinnerungen) teile.push(p.erinnerungen + (p.erinnerungen === 1 ? ' Erinnerung' : ' Erinnerungen'));
    if (p.kontakt) teile.push('📇');
    return teile.join(' · ');
}

/** Kopf eines Vorschlags in der Personenansicht. */
function gruppenVorschlagKopf(v) {
    if (!v) return '';
    const teile = [gruppenNummer(v.kennung), gruppenZahl(v.groesse) + ' Gesichter'];
    const zr = gruppenZeitraum(v.von, v.bis);
    if (zr) teile.push(zr);
    return teile.filter(Boolean).join(' · ');
}

/** Verknüpfter Kontakt (aus dem Profil, ``nummern`` als Liste) — ohne Nummern im Klartext. */
function gruppenKontaktText(k) {
    if (!k || !k.name) return 'Kein Kontakt verknüpft – unten suchen und antippen.';
    const teile = ['📇 ' + k.name];
    const gb = gruppenGeburtstagText(k.geburtstag);
    if (gb) teile.push('🎂 ' + gb);
    const n = Array.isArray(k.nummern) ? k.nummern.length : (Number(k.nummern) || 0);
    if (n) teile.push(n === 1 ? '1 Nummer' : n + ' Nummern');
    return teile.join(' · ');
}

/** Rückmeldung nach „↩ Rückgängig“, je nachdem, was zurückgenommen wurde. */
function gruppenRueckgaengigText(z) {
    const texte = {
        umbenennen: '↩ Umbenennen zurückgenommen',
        loesen: '↩ Lösen zurückgenommen – der Vorschlag gehört wieder zur Person',
        profil: '↩ Profiländerung zurückgenommen',
        ausschliessen: '↩ Ausschließen zurückgenommen',
    };
    return texte[z && z.art] || '↩ letzte Antwort zurückgenommen';
}

/** „2026-10-02T11:45:00“ → „02.10.2026“. */
function gruppenNotizZeit(zeit) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(zeit || ''));
    return m ? m[3] + '.' + m[2] + '.' + m[1] : '';
}

// =========================================================================
// Oberfläche
// =========================================================================
(function () {
    'use strict';

    const zustand = { gruppe: null, beschaeftigt: false, objektUrls: new Set(), namen: [], diktat: null,
                      reiter: 'offen', personen: [], person: null };
    const DIKTAT_WARTEN_MS = 20000;

    function el(id) { return document.getElementById(id); }

    function apiBase() {
        try {
            return localStorage.getItem('api_base')
                || (location.origin.startsWith('http') ? location.origin : 'http://localhost:8080');
        } catch (_e) {
            return location.origin;
        }
    }

    async function jsonHolen(pfad, optionen) {
        const res = await fetch(`${apiBase()}${pfad}`, optionen || {});
        return res.json().catch(() => ({ ok: false, fehler: 'Antwort nicht lesbar' }));
    }

    function melde(text, gut) {
        const m = el('gruppen-meldung');
        if (!m) return;
        m.textContent = text || '';
        m.classList.toggle('fehler', gut === false);
    }

    async function vorschauLaden(fileid, groesse) {
        try {
            const res = await fetch(`${apiBase()}/api/cloud/thumb?fileid=${encodeURIComponent(fileid)}&groesse=${groesse}`);
            if (!res || res.ok !== true) return null;
            const blob = await res.blob();
            return blob ? URL.createObjectURL(blob) : null;
        } catch (_e) {
            return null;
        }
    }

    async function vollbildOeffnen(fileid, gesicht) {
        if (typeof zeigeBildVollbild !== 'function') return;
        const url = await vorschauLaden(fileid, '800x800');
        if (!url) { melde('⚠️ Foto konnte nicht geladen werden.', false); return; }
        zustand.objektUrls.add(url);
        const gross = new Image();
        gross.src = url;
        // Der gelbe Rahmen markiert GENAU das Gesicht, das zu dieser Gruppe
        // gehört (Sebastian 06.10.2026): auf Gruppenfotos ist sonst nicht zu
        // erkennen, ob das richtige Gesicht zugeordnet wurde. Ohne brauchbare
        // Daten wird nichts markiert.
        zeigeBildVollbild(gross, gesicht ? [gesicht] : []);
    }

    /** Kachel mit Gesichtsausschnitt. Standard: Antippen zeigt das ganze Foto.
     *  optionen.beiTipp ersetzt das (Gesamtansicht: markieren), dann öffnet die
     *  Lupe in der Ecke das Foto; optionen.verzoegert lädt erst, wenn sichtbar. */
    function kachel(beispiel, klein, optionen) {
        const opt = optionen || {};
        // Die Kennung heißt je nach Quelle ``fileid`` (Gesichterliste) oder
        // ``bild_id`` (Personenvorschläge); ``rahmen`` markiert im Vollbild
        // genau das Gesicht, das zu dieser Gruppe gehört.
        const kennung = gesichtKennung(beispiel);
        const rahmen = gesichtRahmen(beispiel);
        const box = document.createElement('button');
        box.type = 'button';
        box.className = 'gruppen-kachel' + (klein ? ' klein' : '');
        box.title = beispiel.aufnahme ? ('Aufnahme ' + beispiel.aufnahme) : 'Foto';
        const leinwand = document.createElement('canvas');
        leinwand.width = 160;
        leinwand.height = 160;
        box.appendChild(leinwand);
        const laden = async () => {
            const url = await vorschauLaden(kennung, '480x480');
            if (!url) { box.classList.add('leer'); return; }
            const bild = new Image();
            bild.onload = () => {
                const a = gruppenAusschnitt(beispiel.bbox, beispiel.breite, beispiel.hoehe,
                                            bild.naturalWidth, bild.naturalHeight);
                const ctx = leinwand.getContext('2d');
                if (a) {
                    ctx.drawImage(bild, a.x, a.y, a.w, a.h, 0, 0, 160, 160);
                } else {        // Ausschnitt nicht sicher -> ganzes Bild einpassen
                    const s = Math.min(160 / bild.naturalWidth, 160 / bild.naturalHeight);
                    const w = bild.naturalWidth * s, h = bild.naturalHeight * s;
                    ctx.drawImage(bild, (160 - w) / 2, (160 - h) / 2, w, h);
                }
                try { URL.revokeObjectURL(url); } catch (_e) { /* schon weg */ }
            };
            bild.onerror = () => { box.classList.add('leer'); try { URL.revokeObjectURL(url); } catch (_e) { /* */ } };
            bild.src = url;
        };
        if (opt.verzoegert && typeof IntersectionObserver === 'function') {
            const beobachter = new IntersectionObserver((eintraege) => {
                if (eintraege.some((e) => e.isIntersecting)) { beobachter.disconnect(); laden(); }
            }, { rootMargin: '200px' });
            beobachter.observe(box);
        } else {
            laden();
        }
        if (typeof opt.beiTipp === 'function' && opt.ohneLupe) {
            box.addEventListener('click', () => opt.beiTipp(box));
        } else if (typeof opt.beiTipp === 'function') {
            box.addEventListener('click', () => opt.beiTipp(box));
            const lupe = document.createElement('span');
            lupe.className = 'gruppen-lupe';
            lupe.setAttribute('role', 'button');
            lupe.setAttribute('aria-label', 'Ganzes Foto ansehen');
            lupe.textContent = '⤢';
            lupe.addEventListener('click', (ev) => { ev.stopPropagation(); vollbildOeffnen(kennung, rahmen); });
            box.appendChild(lupe);
        } else {
            box.addEventListener('click', () => vollbildOeffnen(kennung, rahmen));
        }
        return box;
    }

    // ── Alle Gesichter eines Vorschlags (02.10.2026) ──────────────────────
    // Seitenweise (48) aus /api/gruppen/gesichter; Antippen markiert, „🚫 …
    // ausschließen“ schickt die Markierten an /api/gruppen/ausschliessen. Am
    // Handy sind sie sofort raus, der nächste Gruppierlauf am PC ordnet sie neu.
    const alle = { kennung: null, seite: 0, seiten: 0, geladen: 0, letzte: null, markiert: new Set() };

    function alleKnopfAktualisieren() {
        const k = el('gruppen-alle-ausschliessen');
        if (!k) return;
        k.textContent = gruppenAusschlussKnopf(alle.markiert.size);
        k.disabled = alle.markiert.size === 0;
    }

    async function alleSeiteLaden() {
        if (!alle.kennung || (alle.seiten && alle.seite >= alle.seiten)) return;
        const antwort = await jsonHolen('/api/gruppen/gesichter?kennung=' + encodeURIComponent(alle.kennung)
            + '&seite=' + (alle.seite + 1)).catch(() => null);
        const info = el('gruppen-alle-info');
        if (!antwort || antwort.ok !== true) {
            if (info) info.textContent = '⚠️ ' + ((antwort && antwort.fehler) || 'Gesichter nicht ladbar.');
            return;
        }
        alle.seite = antwort.seite;
        alle.seiten = antwort.seiten;
        alle.letzte = antwort;
        const raster = el('gruppen-alle-raster');
        (antwort.gesichter || []).forEach((g) => {
            raster.appendChild(kachel(g, false, {
                verzoegert: true,
                beiTipp: (box) => {
                    if (alle.markiert.has(g.gid)) { alle.markiert.delete(g.gid); box.classList.remove('markiert'); }
                    else { alle.markiert.add(g.gid); box.classList.add('markiert'); }
                    box.dataset.gid = g.gid;
                    alleKnopfAktualisieren();
                },
            }));
            raster.lastChild.dataset.gid = g.gid;
        });
        alle.geladen = raster.children.length;
        if (info) info.textContent = gruppenAlleInfo(antwort, alle.geladen);
        const mehr = el('gruppen-alle-mehr');
        if (mehr) mehr.hidden = alle.seite >= alle.seiten;
    }

    /** Gesamtansicht eines Vorschlags; ``vonPerson`` = aus „Benannt“ geöffnet (Zurück führt dorthin). */
    function alleOeffnen(kennung, vonPerson) {
        const k = (typeof kennung === 'string' && kennung) ? kennung : (zustand.gruppe && zustand.gruppe.kennung);
        if (!k) return;
        Object.assign(alle, { kennung: k, seite: 0, seiten: 0, geladen: 0, letzte: null, vonPerson: Boolean(vonPerson) });
        alle.markiert.clear();
        const raster = el('gruppen-alle-raster');
        if (raster) raster.innerHTML = '';
        nurZeigen('alle');
        alleKnopfAktualisieren();
        alleSeiteLaden();
    }

    function alleSchliessen() {
        el('gruppen-alle-ansicht').hidden = true;
        alle.kennung = null;
        // Neu laden: Beispiele ohne die gerade Ausgeschlossenen
        if (alle.vonPerson && zustand.person) personOeffnen(zustand.person.name);
        else laden();
    }

    // ── Reiter „Offen“ / „Benannt“ (02.10.2026) ─────────────────────────────
    // Wunsch Sebastian: schon benannte Personen wieder aufrufen und bearbeiten
    // wie ein Dokument, dann beim nächsten offenen Vorschlag weitermachen.
    const BEREICHE = { karte: 'gruppen-karte', fertig: 'gruppen-fertig', alle: 'gruppen-alle-ansicht',
                       benannt: 'gruppen-benannt-ansicht', person: 'gruppen-person' };

    function nurZeigen(name) {
        Object.keys(BEREICHE).forEach((k) => { const e = el(BEREICHE[k]); if (e) e.hidden = (k !== name); });
    }

    function reiterSetzen(name) {
        zustand.reiter = name === 'benannt' ? 'benannt' : 'offen';
        [['gruppen-reiter-offen', 'offen'], ['gruppen-reiter-benannt', 'benannt']].forEach(([id, r]) => {
            const k = el(id);
            if (!k) return;
            k.classList.toggle('aktiv', zustand.reiter === r);
            k.setAttribute('aria-selected', zustand.reiter === r ? 'true' : 'false');
        });
        melde('');
        if (zustand.reiter === 'benannt') {
            nurZeigen('benannt');
            personenLaden();
        } else {
            nurZeigen('');
            laden();
        }
    }

    async function personenLaden() {
        const info = el('gruppen-benannt-info');
        if (info) info.textContent = '… lädt';
        const antwort = await jsonHolen('/api/gruppen/personen').catch(() => null);
        if (!antwort || antwort.ok !== true) {
            zustand.personen = [];
            if (info) info.textContent = '⚠️ ' + ((antwort && antwort.fehler) || 'Keine Verbindung zum Agenten.');
            personenZeigen();
            return;
        }
        zustand.personen = antwort.personen || [];
        personenZeigen();
    }

    function personenZeigen() {
        const liste = el('gruppen-benannt-liste');
        const info = el('gruppen-benannt-info');
        if (!liste) return;
        liste.innerHTML = '';
        const frage = (el('gruppen-benannt-filter') || {}).value || '';
        const passend = zustand.personen.filter((p) => gruppenPersonPasst(p.name, frage));
        if (info) {
            info.textContent = !zustand.personen.length
                ? 'Noch niemand benannt – im Reiter „Offen“ geht es los.'
                : gruppenZahl(passend.length) + (passend.length === 1 ? ' Person' : ' Personen')
                  + ' · antippen zum Ansehen und Bearbeiten';
        }
        passend.forEach((p) => {
            const zeile = document.createElement('div');
            zeile.className = 'gruppen-benannt-zeile';
            zeile.setAttribute('role', 'listitem');
            zeile.tabIndex = 0;
            if (p.beispiel) zeile.appendChild(kachel(p.beispiel, true, { verzoegert: true, ohneLupe: true, beiTipp: () => {} }));
            const text = document.createElement('div');
            text.className = 'gruppen-benannt-text';
            const n = document.createElement('span');
            n.className = 'gruppen-treffer-name';
            n.textContent = p.name;
            const i = document.createElement('span');
            i.className = 'gruppen-treffer-info';
            i.textContent = gruppenPersonInfo(p);
            text.appendChild(n);
            text.appendChild(i);
            zeile.appendChild(text);
            zeile.addEventListener('click', () => personOeffnen(p.name));
            zeile.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') personOeffnen(p.name); });
            liste.appendChild(zeile);
        });
    }

    /** Person laden und zeigen; ``leise`` = bei Fehlschlag still zur Liste (z. B. nach Rückgängig). */
    async function personOeffnen(name, leise) {
        const antwort = await jsonHolen('/api/gruppen/person?name=' + encodeURIComponent(name)).catch(() => null);
        if (!antwort || antwort.ok !== true) {
            if (!leise) melde('⚠️ ' + ((antwort && antwort.fehler) || 'Keine Verbindung zum Agenten.'), false);
            zustand.person = null;
            nurZeigen('benannt');
            personenLaden();
            return false;
        }
        zustand.person = antwort;
        nurZeigen('person');
        personZeigen(antwort);
        return true;
    }

    function personZeigen(p) {
        el('gruppen-person-titel').textContent = p.name;
        const vorschlaege = p.vorschlaege || [];
        const gesichter = vorschlaege.reduce((s, v) => s + (Number(v.groesse) || 0), 0);
        el('gruppen-person-meta').textContent = gruppenZahl(gesichter) + ' Gesichter'
            + (vorschlaege.length > 1 ? ' in ' + vorschlaege.length + ' Vorschlägen' : '');
        const box = el('gruppen-person-vorschlaege');
        box.innerHTML = '';
        vorschlaege.forEach((v) => {
            const teil = document.createElement('div');
            teil.className = 'gruppen-person-vorschlag';
            const kopf = document.createElement('p');
            kopf.className = 'gruppen-meta';
            kopf.textContent = gruppenVorschlagKopf(v);
            teil.appendChild(kopf);
            const kacheln = document.createElement('div');
            kacheln.className = 'gruppen-kacheln';
            (v.beispiele || []).forEach((b) => kacheln.appendChild(kachel(b, false, { verzoegert: true })));
            teil.appendChild(kacheln);
            const knoepfe = document.createElement('div');
            knoepfe.className = 'gruppen-leiste';
            const ansehen = document.createElement('button');
            ansehen.type = 'button';
            ansehen.className = 'gruppen-knopf';
            ansehen.textContent = '🔍 Alle ' + gruppenZahl(v.groesse) + ' Gesichter';
            ansehen.addEventListener('click', () => alleOeffnen(v.kennung, true));
            const loesen = document.createElement('button');
            loesen.type = 'button';
            loesen.className = 'gruppen-knopf';
            loesen.textContent = '✂ Gehört nicht zu ' + p.name;
            loesen.addEventListener('click', () => vorschlagLoesen(v.kennung, loesen));
            knoepfe.appendChild(ansehen);
            knoepfe.appendChild(loesen);
            teil.appendChild(knoepfe);
            box.appendChild(teil);
        });
        const profil = p.profil || {};
        el('gruppen-person-name').value = p.name;
        el('gruppen-person-beziehung').value = profil.beziehung || '';
        el('gruppen-person-notiz').value = '';
        const notizen = el('gruppen-person-notizen');
        notizen.innerHTML = '';
        (profil.notizen || []).slice().reverse().forEach((n) => {
            const zeile = document.createElement('div');
            zeile.className = 'gruppen-person-notiz';
            const zeit = document.createElement('span');
            zeit.className = 'gruppen-meta';
            zeit.textContent = gruppenNotizZeit(n.zeit);
            const text = document.createElement('p');
            text.textContent = n.text || '';
            zeile.appendChild(zeit);
            zeile.appendChild(text);
            notizen.appendChild(zeile);
        });
        el('gruppen-person-kontakt').textContent = gruppenKontaktText(profil.kontakt);
        el('gruppen-person-kontaktsuche').value = '';
        el('gruppen-person-kontakttreffer').innerHTML = '';
    }

    /** POST an eine Bearbeiten-Route; sperrt Doppel-Tipps. */
    async function bearbeiten(pfad, koerper) {
        if (zustand.beschaeftigt) return null;
        zustand.beschaeftigt = true;
        try {
            const antwort = await jsonHolen(pfad, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(koerper || {}),
            });
            if (!antwort || antwort.ok !== true) {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Speichern fehlgeschlagen'), false);
                return null;
            }
            return antwort;
        } catch (_e) {
            melde('⚠️ Keine Verbindung zum Agenten.', false);
            return null;
        } finally {
            zustand.beschaeftigt = false;
        }
    }

    /** „✂ Gehört nicht zu …“: zweimal tippen (Schutz vor Versehen), dann ist der Vorschlag wieder offen. */
    async function vorschlagLoesen(kennung, knopf) {
        const jetzt = Date.now();
        if (!(Number(knopf.dataset.bereit) > jetzt - 4000)) {
            knopf.dataset.bereit = String(jetzt);
            knopf.textContent = 'Wirklich lösen? Noch einmal tippen';
            return;
        }
        const antwort = await bearbeiten('/api/gruppen/loesen', { kennung: kennung });
        if (!antwort) return;
        const name = zustand.person ? zustand.person.name : '';
        await personOeffnen(name, true);
        melde('✓ ' + gruppenNummer(kennung) + ' gelöst – er steht wieder unter „Offen“ (↩ Rückgängig möglich).');
    }

    async function umbenennen() {
        if (!zustand.person) return;
        const neu = el('gruppen-person-name').value.trim();
        if (!neu || neu === zustand.person.name) { melde('Bitte einen neuen Namen eingeben.', false); return; }
        const antwort = await bearbeiten('/api/gruppen/umbenennen', { alt: zustand.person.name, neu: neu });
        if (!antwort) return;
        zustand.person = antwort;
        personZeigen(antwort);
        melde(antwort.zusammengefuehrt ? '✓ mit ' + antwort.name + ' zusammengeführt' : '✓ umbenannt in ' + antwort.name);
    }

    async function profilSpeichern() {
        if (!zustand.person) return;
        const vorher = (zustand.person.profil || {}).beziehung || '';
        const beziehung = el('gruppen-person-beziehung').value.trim();
        const notiz = el('gruppen-person-notiz').value.trim();
        const koerper = { name: zustand.person.name };
        if (beziehung && beziehung !== vorher) koerper.beziehung = beziehung;
        if (notiz) koerper.notiz = notiz;
        if (!koerper.beziehung && !koerper.notiz) { melde('Nichts geändert.', false); return; }
        const antwort = await bearbeiten('/api/gruppen/profil', koerper);
        if (!antwort) return;
        zustand.person.profil = antwort;
        personZeigen(zustand.person);
        melde('✓ Profil gespeichert' + (koerper.notiz ? ' · Erinnerung angelegt' : ''));
    }

    let _kontaktUhr = null;
    let _kontaktNr = 0;

    async function kontaktSuchen() {
        const frage = el('gruppen-person-kontaktsuche').value.trim();
        const box = el('gruppen-person-kontakttreffer');
        const nr = ++_kontaktNr;
        if (!frage) { box.innerHTML = ''; return; }
        const antwort = await jsonHolen('/api/gruppen/suche?limit=8&q=' + encodeURIComponent(frage)).catch(() => null);
        if (nr !== _kontaktNr) return;                      // nur die neueste Antwort zeigen
        box.innerHTML = '';
        const kontakte = (antwort && antwort.ok === true && antwort.kontakte) || [];
        kontakte.forEach((k) => box.appendChild(trefferZeile(k.name, gruppenTrefferInfo(k, 'kontakt'),
            () => kontaktVerknuepfen(k.id))));
        if (!kontakte.length) {
            const leer = document.createElement('p');
            leer.className = 'gruppen-treffer-leer';
            leer.textContent = antwort && antwort.kontakte_vorhanden === false
                ? 'Telefonbuch noch nicht übertragen.' : 'Kein Kontakt gefunden.';
            box.appendChild(leer);
        }
    }

    async function kontaktVerknuepfen(kontaktId) {
        if (!zustand.person) return;
        const antwort = await bearbeiten('/api/gruppen/profil', { name: zustand.person.name, kontakt_id: String(kontaktId) });
        if (!antwort) return;
        zustand.person.profil = antwort;
        personZeigen(zustand.person);
        melde('✓ Kontakt verknüpft');
    }

    async function personRueckgaengig() {
        const antwort = await bearbeiten('/api/gruppen/rueckgaengig', {});
        if (!antwort) return;
        const z = antwort.zurueckgenommen || {};
        const ziel = (z.art === 'umbenennen' && z.name) ? z.name : (zustand.person && zustand.person.name);
        if (ziel) await personOeffnen(ziel, true);
        melde(gruppenRueckgaengigText(z));
    }

    async function personDiktat() {
        const feld = el('gruppen-person-notiz');
        const knopf = el('gruppen-person-mikro');
        if (typeof starteFeldDiktat !== 'function') {
            melde('⚠️ Spracheingabe ist hier nicht verfügbar — bitte das Mikrofon der Tastatur nutzen.', false);
            return;
        }
        await starteFeldDiktat(feld, knopf);
    }

    async function alleAusschliessen() {
        if (!alle.kennung || !alle.markiert.size || zustand.beschaeftigt) return;
        zustand.beschaeftigt = true;
        try {
            const liste = Array.from(alle.markiert);
            const antwort = await jsonHolen('/api/gruppen/ausschliessen', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kennung: alle.kennung, gesichter: liste }),
            });
            if (antwort && antwort.ok === true) {
                el('gruppen-alle-raster').querySelectorAll('.gruppen-kachel.markiert')
                    .forEach((k) => k.remove());
                alle.markiert.clear();
                alle.geladen = el('gruppen-alle-raster').children.length;
                if (alle.letzte) {
                    alle.letzte.gesamt = antwort.gesamt;
                    alle.letzte.ausgeschlossen = (alle.letzte.ausgeschlossen || 0) + antwort.ausgeschlossen;
                    el('gruppen-alle-info').textContent = gruppenAlleInfo(alle.letzte, alle.geladen);
                }
                melde('✓ ' + gruppenZahl(antwort.ausgeschlossen) + ' ausgeschlossen – sie gehören nicht mehr zu diesem Vorschlag (↩ Rückgängig in der Karte).');
                alleKnopfAktualisieren();
            } else {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Ausschließen fehlgeschlagen'), false);
            }
        } catch (_e) {
            melde('⚠️ Keine Verbindung zum Agenten.', false);
        } finally {
            zustand.beschaeftigt = false;
        }
    }

    function namenListeSetzen(namen) {
        zustand.namen = namen || [];
    }

    // ── Suchfeld (02.10.2026, Issue #3 B) ─────────────────────────────────
    // Tippen fragt /api/gruppen/suche (Wortanfang, Umlaute egal, rein lokal):
    // zuerst schon benannte Personen, dann Telefonbuch-Kontakte. Ein Tipp auf
    // einen Treffer ordnet zu — bei einem Kontakt mit Verknüpfung (kontakt_id).
    // Leeres Feld: die schon benannten Personen (ersetzt die Namensknöpfe).
    let _suchUhr = null;
    let _suchNr = 0;

    function trefferZeile(titel, info, beiTipp) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'gruppen-treffer-zeile';
        b.setAttribute('role', 'option');
        const t = document.createElement('span');
        t.className = 'gruppen-treffer-name';
        t.textContent = titel;
        const i = document.createElement('span');
        i.className = 'gruppen-treffer-info';
        i.textContent = info;
        b.appendChild(t);
        b.appendChild(i);
        b.addEventListener('click', beiTipp);
        return b;
    }

    function trefferZeigen(antwort) {
        const box = el('gruppen-treffer');
        if (!box) return;
        box.innerHTML = '';
        if (!antwort || antwort.ok !== true) return;
        const personen = antwort.personen || [];
        const kontakte = antwort.kontakte || [];
        personen.forEach((p) => box.appendChild(trefferZeile(p.name, gruppenTrefferInfo(p, 'person'),
            () => nameSpeichern(p.name))));
        kontakte.forEach((k) => box.appendChild(trefferZeile(k.name, gruppenTrefferInfo(k, 'kontakt'),
            () => nameSpeichern(k.verknuepft_mit || k.name, k.id))));
        if (antwort.frage && !personen.length && !kontakte.length) {
            const leer = document.createElement('p');
            leer.className = 'gruppen-treffer-leer';
            leer.textContent = antwort.kontakte_vorhanden
                ? 'Kein Treffer – „Speichern“ legt den Namen neu an.'
                : 'Kein Treffer. Telefonbuch noch nicht übertragen – „Speichern“ legt den Namen neu an.';
            box.appendChild(leer);
        }
    }

    async function suchen() {
        const feld = el('gruppen-name');
        const frage = feld ? feld.value.trim() : '';
        const nr = ++_suchNr;
        const antwort = await jsonHolen('/api/gruppen/suche?limit=8&q=' + encodeURIComponent(frage))
            .catch(() => null);
        if (nr === _suchNr) trefferZeigen(antwort);      // nur die neueste Antwort zeigen
    }

    function sucheVormerken() {
        if (_suchUhr) clearTimeout(_suchUhr);
        _suchUhr = setTimeout(suchen, 150);
    }

    function zeigen(antwort) {
        const karte = el('gruppen-karte');
        const fertig = el('gruppen-fertig');
        namenListeSetzen(antwort && antwort.namen);
        if (zustand.reiter !== 'offen') return;          // inzwischen auf „Benannt“ gewechselt
        if (!antwort || antwort.ok !== true) {
            zustand.gruppe = null;
            if (karte) karte.hidden = true;
            if (fertig) fertig.hidden = true;
            melde('⚠️ ' + ((antwort && antwort.fehler) || 'Keine Verbindung zum Agenten.'), false);
            return;
        }
        if (antwort.fertig || !antwort.gruppe) {
            zustand.gruppe = null;
            if (karte) karte.hidden = true;
            if (fertig) fertig.hidden = false;
            return;
        }
        const g = antwort.gruppe;
        const vorher = zustand.gruppe ? zustand.gruppe.kennung : null;
        zustand.gruppe = g;
        if (fertig) fertig.hidden = true;
        if (karte) {
            karte.hidden = false;
            if (vorher && vorher !== g.kennung) {
                // Neu auslösen: Klasse weg, Reflow, Klasse wieder dran.
                karte.classList.remove('gruppen-wechsel');
                void karte.offsetWidth;
                karte.classList.add('gruppen-wechsel');
                const body = karte.closest('.gruppen-body');
                if (body) body.scrollTop = 0;
            }
        }
        const nummer = el('gruppen-nummer');
        if (nummer) nummer.textContent = gruppenNummer(g.kennung);
        el('gruppen-meta').textContent = gruppenMeta(g) + (g.war_spaeter ? ' · zurückgestellt' : '');
        el('gruppen-offen').textContent = gruppenZahl(antwort.offen) + ' offen';
        const kacheln = el('gruppen-kacheln');
        kacheln.innerHTML = '';
        if (!g.beispiele.length) {
            const leer = document.createElement('p');
            leer.className = 'sheet-note';
            leer.textContent = 'Zu dieser Gruppe gibt es nur Video-Standbilder — kein Vorschaubild.';
            kacheln.appendChild(leer);
        }
        g.beispiele.forEach((b) => kacheln.appendChild(kachel(b, false)));
        const vb = el('gruppen-verbunden');
        if (vb) {
            vb.innerHTML = '';
            const verbunden = g.verbunden || [];
            if (verbunden.length) {
                const text = document.createElement('span');
                text.textContent = gruppenVerbundenText(verbunden);
                vb.appendChild(text);
                verbunden.forEach((v) => { if (v.beispiel) vb.appendChild(kachel(v.beispiel, true)); });
            }
        }
        const zw = el('gruppen-zwillinge');
        zw.innerHTML = '';
        (g.zwillinge || []).forEach((z) => {
            const zeile = document.createElement('div');
            zeile.className = 'gruppen-zwilling';
            if (z.beispiel) zeile.appendChild(kachel(z.beispiel, true));
            const text = document.createElement('span');
            text.textContent = gruppenZwillingText(z);
            zeile.appendChild(text);
            const gleich = document.createElement('button');
            gleich.type = 'button';
            gleich.className = 'gruppen-knopf';
            gleich.textContent = '= dieselbe Person';
            gleich.addEventListener('click', () => antworten('gleich', { ziel: z.kennung }));
            const andere = document.createElement('button');
            andere.type = 'button';
            andere.className = 'gruppen-knopf';
            andere.textContent = '≠ andere Person';
            andere.addEventListener('click', () => antworten('verschieden', { ziel: z.kennung }));
            const knoepfe = document.createElement('div');
            knoepfe.className = 'gruppen-zwilling-knoepfe';
            knoepfe.appendChild(gleich);
            knoepfe.appendChild(andere);
            zeile.appendChild(knoepfe);
            zw.appendChild(zeile);
        });
        const alleKnopf = el('gruppen-alle');
        if (alleKnopf) alleKnopf.textContent = '🔍 Alle ' + gruppenZahl(g.groesse) + ' Gesichter ansehen';
        ['gruppen-name', 'gruppen-beziehung', 'gruppen-notiz'].forEach((id) => { const f = el(id); if (f) f.value = ''; });
        const info = el('gruppen-profil-info');
        if (info) info.textContent = '';
        suchen();
    }

    async function fortschrittLaden() {
        const stand = await jsonHolen('/api/gruppen/stand').catch(() => null);
        const f = el('gruppen-fortschritt');
        if (f) f.textContent = gruppenFortschritt(stand);
    }

    async function laden() {
        melde('… lädt');
        const antwort = await jsonHolen('/api/gruppen/naechste').catch(() => null);
        melde('');
        zeigen(antwort);
        fortschrittLaden();
    }

    async function antworten(art, extra) {
        if (zustand.beschaeftigt || !zustand.gruppe) return;
        // Jede Antwort wechselt (meist) den Vorschlag — ein offenes Diktat
        // landete dann im Erinnerungsfeld der NÄCHSTEN Person.
        if (diktatOffen()) {
            melde(nimmtAuf()
                ? '🎙 Erst die Aufnahme beenden (⬤ antippen), dann weiter.'
                : '… Das Diktat wird noch übertragen — gleich noch einmal tippen.', false);
            return;
        }
        const koerper = Object.assign({ kennung: zustand.gruppe.kennung, art: art }, extra || {});
        zustand.beschaeftigt = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/antwort', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(koerper),
            });
            if (antwort && antwort.ok === true) {
                const vorher = zustand.gruppe ? zustand.gruppe.kennung : null;
                zeigen(antwort);
                const jetzt = zustand.gruppe ? zustand.gruppe.kennung : null;
                melde(gruppenAntwortText(art, antwort.gespeichert, Boolean(jetzt && jetzt !== vorher)));
                fortschrittLaden();
            } else {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Speichern fehlgeschlagen'), false);
            }
        } catch (_e) {
            melde('⚠️ Keine Verbindung zum Agenten.', false);
        } finally {
            zustand.beschaeftigt = false;
        }
    }

    async function rueckgaengig() {
        if (zustand.beschaeftigt) return;
        zustand.beschaeftigt = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/rueckgaengig', { method: 'POST' });
            if (antwort && antwort.ok === true) {
                zeigen(antwort);
                melde(gruppenRueckgaengigText(antwort.zurueckgenommen));
                fortschrittLaden();
            } else {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Nichts zurückzunehmen'), false);
            }
        } catch (_e) {
            melde('⚠️ Keine Verbindung zum Agenten.', false);
        } finally {
            zustand.beschaeftigt = false;
        }
    }

    /** Nimmt der Sprechknopf gerade auf? (starteFeldDiktat beschriftet ihn mit ⬤.) */
    function nimmtAuf() {
        const b = el('gruppen-notiz-mikro');
        return Boolean(b && String(b.textContent || '').indexOf('⬤') === 0);
    }

    function diktatOffen() {
        const feld = el('gruppen-notiz');
        return gruppenDiktatOffen(nimmtAuf(), zustand.diktat, feld ? feld.value : '', Date.now());
    }

    /** 🎙 am Erinnerungsfeld: Aufnahme starten bzw. stoppen (Erkennung wie die Chat-Zeile). */
    async function diktatUmschalten() {
        const feld = el('gruppen-notiz');
        const knopf = el('gruppen-notiz-mikro');
        if (!feld || !knopf) return;
        if (typeof starteFeldDiktat !== 'function') {
            melde('⚠️ Spracheingabe ist hier nicht verfügbar — bitte das Mikrofon der Tastatur nutzen.', false);
            return;
        }
        const stoppt = nimmtAuf();
        if (stoppt) zustand.diktat = { wert: feld.value, bis: Date.now() + DIKTAT_WARTEN_MS };
        await starteFeldDiktat(feld, knopf);
        if (!stoppt && nimmtAuf()) melde('🎙 Sprich jetzt — zum Beenden noch einmal auf ⬤ tippen.');
        if (stoppt) melde('… Erinnerung wird übertragen');
    }

    function nameSpeichern(vorgabe, kontaktId) {
        const feld = el('gruppen-name');
        const name = (typeof vorgabe === 'string' && vorgabe.trim())
            ? vorgabe.trim() : (feld ? feld.value.trim() : '');
        if (!name) { melde('Bitte einen Namen eingeben.', false); if (feld) feld.focus(); return; }
        const beziehung = (el('gruppen-beziehung') || {}).value || '';
        const notiz = (el('gruppen-notiz') || {}).value || '';
        const koerper = { name: name, beziehung: beziehung.trim(), notiz: notiz.trim() };
        if (kontaktId) koerper.kontakt_id = String(kontaktId);
        antworten('name', koerper);
    }

    /** Bekannter Name eingegeben? Dann das vorhandene Profil kurz zeigen. */
    async function profilZeigen() {
        const info = el('gruppen-profil-info');
        const feld = el('gruppen-name');
        if (!info || !feld) return;
        const name = feld.value.trim();
        if (!name || !zustand.namen.some((n) => n.toLowerCase() === name.toLowerCase())) {
            info.textContent = '';
            return;
        }
        const p = await jsonHolen('/api/gruppen/profil?name=' + encodeURIComponent(name)).catch(() => null);
        info.textContent = gruppenProfilText(p);
    }

    function oeffnen() {
        const sheet = el('gruppen-sheet');
        if (!sheet) return;
        sheet.hidden = false;
        reiterSetzen(zustand.reiter);
    }

    function schliessen() {
        const sheet = el('gruppen-sheet');
        if (sheet) sheet.hidden = true;
        zustand.objektUrls.forEach((u) => { try { URL.revokeObjectURL(u); } catch (_e) { /* */ } });
        zustand.objektUrls.clear();
    }

    function init() {
        const knopf = el('gruppen-btn');
        if (knopf) knopf.addEventListener('click', oeffnen);
        const zu = el('gruppen-close');
        if (zu) zu.addEventListener('click', schliessen);
        const sheet = el('gruppen-sheet');
        if (sheet) sheet.addEventListener('click', (ev) => { if (ev.target === sheet) schliessen(); });
        const speichern = el('gruppen-speichern');
        if (speichern) speichern.addEventListener('click', () => nameSpeichern());
        const mikro = el('gruppen-notiz-mikro');
        if (mikro) mikro.addEventListener('click', diktatUmschalten);
        const feld = el('gruppen-name');
        if (feld) {
            feld.addEventListener('keydown', (ev) => {
                if (ev.key !== 'Enter') return;
                ev.preventDefault();
                const bez = el('gruppen-beziehung');
                if (bez) bez.focus(); else nameSpeichern();
            });
            feld.addEventListener('change', profilZeigen);
            feld.addEventListener('input', sucheVormerken);
        }
        const spaeter = el('gruppen-spaeter');
        if (spaeter) spaeter.addEventListener('click', () => antworten('spaeter'));
        const unbekannt = el('gruppen-unbekannt');
        if (unbekannt) unbekannt.addEventListener('click', () => antworten('unbekannt'));
        const zurueck = el('gruppen-zurueck');
        if (zurueck) zurueck.addEventListener('click', rueckgaengig);
        const alleKnopf = el('gruppen-alle');
        if (alleKnopf) alleKnopf.addEventListener('click', alleOeffnen);
        const alleZurueck = el('gruppen-alle-zurueck');
        if (alleZurueck) alleZurueck.addEventListener('click', alleSchliessen);
        const alleMehr = el('gruppen-alle-mehr');
        if (alleMehr) alleMehr.addEventListener('click', alleSeiteLaden);
        const alleAus = el('gruppen-alle-ausschliessen');
        if (alleAus) alleAus.addEventListener('click', alleAusschliessen);
        const zurueckFertig = el('gruppen-zurueck-fertig');
        if (zurueckFertig) zurueckFertig.addEventListener('click', rueckgaengig);
        // Reiter + Benannt (02.10.2026)
        const anklick = (id, fn) => { const e = el(id); if (e) e.addEventListener('click', fn); };
        anklick('gruppen-reiter-offen', () => reiterSetzen('offen'));
        anklick('gruppen-reiter-benannt', () => reiterSetzen('benannt'));
        anklick('gruppen-person-zurueck', () => { zustand.person = null; nurZeigen('benannt'); personenLaden(); });
        anklick('gruppen-person-umbenennen', umbenennen);
        anklick('gruppen-person-speichern', profilSpeichern);
        anklick('gruppen-person-mikro', personDiktat);
        anklick('gruppen-person-rueckgaengig', personRueckgaengig);
        const filter = el('gruppen-benannt-filter');
        if (filter) filter.addEventListener('input', personenZeigen);
        const kontaktFeld = el('gruppen-person-kontaktsuche');
        if (kontaktFeld) {
            kontaktFeld.addEventListener('input', () => {
                if (_kontaktUhr) clearTimeout(_kontaktUhr);
                _kontaktUhr = setTimeout(kontaktSuchen, 150);
            });
        }
        const neuName = el('gruppen-person-name');
        if (neuName) neuName.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); umbenennen(); } });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
