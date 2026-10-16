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

/** Marke eines Video-Gesichts (14.10.2026): „🎬 0:04“ aus ``zeit_s``; Fotos → "". */
function gruppenVideoMarke(beispiel) {
    if (!beispiel || beispiel.video !== true) return '';
    const t = Math.max(0, Math.round(Number(beispiel.zeit_s) || 0));
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sek = t % 60;
    const zz = (n) => (n < 10 ? '0' : '') + n;
    return '🎬 ' + (h ? h + ':' + zz(m) : String(m)) + ':' + zz(sek);
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
    // 10.10.2026: Vorschläge nur aus Video-Standbildern blieben leer ohne Erklärung.
    const videos = Number(antwort.videos) || 0;
    if (!antwort.gesamt && videos) {
        return '🎬 Dieser Vorschlag besteht nur aus ' + gruppenZahl(videos)
            + ' Gesichtern aus Videos – für sie gibt es noch keine Standbilder.'
            + ' Bitte mit „⏭ Weiter (später)“ überspringen.';
    }
    const teile = ['Gesichter antippen, dann 🚫 ausschließen oder 👤 einer Person zuordnen.',
                   gruppenZahl(antwort.gesamt) + ' Gesichter'];
    if (geladen < antwort.gesamt) teile.push(gruppenZahl(geladen) + ' geladen');
    if (antwort.ausgeschlossen) teile.push(gruppenZahl(antwort.ausgeschlossen) + ' schon ausgeschlossen');
    // Seit 14.10.2026 zählt ``videos`` nur noch Video-Gesichter OHNE Standbild; seit
    // 15.10.2026 nennt die Zeile den Grund („gezählt, aber nicht angezeigt“ war
    // Sebastians Befund — die Standbilder fehlten, nicht die Anzeige).
    if (videos) teile.push('+ ' + gruppenZahl(videos) + ' aus Videos (noch ohne Standbild)');
    if (antwort.gesichter && antwort.gesichter.some((g) => g && g.video === true)) {
        teile.push('🎬 Video-Gesichter nur ansehen, nicht einzeln ändern');
    }
    if (Array.isArray(antwort.kennungen) && antwort.kennungen.length > 1) {
        teile.push('aus ' + antwort.kennungen.length + ' Vorschlägen');
    }
    return teile.join(' · ');
}

/** Beschriftung des Zuordnen-Knopfs (10.10.2026). */
function gruppenZuordnenKnopf(anzahl) {
    if (!anzahl) return '👤 Zuordnen';
    return '👤 ' + gruppenZahl(anzahl) + (anzahl === 1 ? ' Gesicht zuordnen …' : ' Gesichter zuordnen …');
}

/** Namen zum Zuordnen: ohne die gerade offene Person, ohne Leere/Doppelte (Groß/Klein egal), A–Z. */
function gruppenZuordnenNamen(namen, ohne) {
    const weg = typeof ohne === 'string' ? ohne.trim().toLowerCase() : '';
    const gesehen = new Set();
    const liste = [];
    (Array.isArray(namen) ? namen : []).forEach((n) => {
        const s = typeof n === 'string' ? n.trim() : '';
        const k = s.toLowerCase();
        if (!s || k === weg || gesehen.has(k)) return;
        gesehen.add(k);
        liste.push(s);
    });
    return liste.sort((a, b) => a.localeCompare(b, 'de'));
}

/** Zeitblöcke (10.10.2026): „2004-03-02“ → „2004“, ohne Datum → „ohne Datum“. */
function gruppenJahr(aufnahme) {
    const m = /^(\d{4})/.exec(String(aufnahme || ''));
    return m ? m[1] : 'ohne Datum';
}

/** Umschalter der Sortierung: zeigt, wohin ein Tipp wechselt. */
function gruppenOrdnungKnopf(ordnung) {
    return ordnung === 'zeit' ? '⭐ Beste zuerst' : '📅 Nach Jahren';
}

/** Knopf oben in der Personenansicht (07.10.2026): alle Gesichter über alle Vorschläge. */
function gruppenPersonAlleKnopf(name, anzahl) {
    const n = Number(anzahl) || 0;
    return '🔍 Alle ' + gruppenZahl(n) + (n === 1 ? ' Gesicht' : ' Gesichter') + ' von '
        + (typeof name === 'string' && name.trim() ? name.trim() : 'dieser Person') + ' durchsehen';
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

// ── Gruppenfilter in „Benannt“ (16.10.2026) ─────────────────────────────────
//
// Wunsch Sebastian: die Filterauswahl der Gruppenansicht auch in „Benannt“,
// ohne die Ansicht umzubauen. Der Server liefert dafür je Person nur
// Gruppenmetadaten (``kennung``, ``groesse``, ``von``, ``bis``) — keine Bilder.

/** Gesichtsgruppen einer Person aus /api/gruppen/personen (immer eine Liste). */
function gruppenPersonGruppen(p) {
    return Array.isArray(p && p.gruppen) ? p.gruppen.filter((g) => g && g.kennung) : [];
}

/** Passt die gewählte Gesichtsgruppe? Leer = alle Personen. */
function gruppenPersonPasstGruppe(p, gruppe) {
    if (!gruppe) return true;
    return gruppenPersonGruppen(p).some((g) => g.kennung === gruppe);
}

/** Auswahlzeile einer Gruppe: „Vorschlag 1001 · 120 Gesichter · 2015–2025“. */
function gruppenAuswahlText(g) {
    if (!g) return '';
    const teile = [];
    const nummer = gruppenNummer(g.kennung);
    teile.push(nummer || String(g.kennung));
    teile.push(gruppenZahl(g.groesse) + ' Gesichter');
    const zr = gruppenZeitraum(g.von, g.bis);
    if (zr) teile.push(zr);
    return teile.join(' · ');
}

/** Alle Gesichtsgruppen der geladenen Personen: ohne Doppelte, größte zuerst. */
function gruppenAuswahlEintraege(personen) {
    const nach = new Map();
    (Array.isArray(personen) ? personen : []).forEach((p) => gruppenPersonGruppen(p).forEach((g) => {
        const alt = nach.get(g.kennung);
        if (!alt || (Number(g.groesse) || 0) > (Number(alt.groesse) || 0)) nach.set(g.kennung, g);
    }));
    return Array.from(nach.values()).sort((a, b) => (Number(b.groesse) || 0) - (Number(a.groesse) || 0)
        || String(a.kennung).localeCompare(String(b.kennung)));
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
        zuordnen: '↩ Zuordnen zurückgenommen – die Gesichter sind wieder im alten Vorschlag',
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
                      reiter: 'offen', personen: [], person: null, listeAktiv: false,
                      personenGruppe: '',
                      listeStatus: 'offen', listeSeite: 1, listeSeiten: 0,
                      listenSequenz: 0, detailSequenz: 0, quizSequenz: 0, detailAktiv: false,
                      // Gemeinsamer Mechanismus gegen verspätete Antworten: ``ansichtSequenz``
                      // zählt jeden Ansichtswechsel (nurZeigen, Alle-Gesichter-Neuaufbau, Schließen);
                      // ``personenSequenz``/``personSequenz`` ordnen gleichartige Anfragen.
                      ansichtSequenz: 0, personenSequenz: 0, personSequenz: 0,
                      listeStatusGeaendert: false, listeRueckmeldung: '' };
    const DIKTAT_WARTEN_MS = 20000;

    function el(id) { return document.getElementById(id); }

    /** Ansichtsstand beim Absenden einer Anfrage festhalten. Nach dem Warten fragt
     *  ``ansichtVeraltet`` ab, ob inzwischen Detail, Übersicht, Person, Alle Gesichter,
     *  Reiter oder „Schließen“ gewechselt haben – dann darf die Antwort nichts mehr an
     *  Oberfläche oder Auswahl ändern (serverseitig ausgeführte Aktionen bleiben gültig). */
    function ansichtMerken() {
        return { ansicht: zustand.ansichtSequenz, detail: zustand.detailSequenz, liste: zustand.listenSequenz };
    }

    function ansichtVeraltet(ansicht) {
        // „Schließen“ erhöht alle Zähler, ein eigener Sheet-Test ist daher unnötig.
        return ansicht.ansicht !== zustand.ansichtSequenz || ansicht.detail !== zustand.detailSequenz
            || ansicht.liste !== zustand.listenSequenz;
    }

    /** Immer die eigene Herkunft wie in app.js; seit P0 (12.10.2026) ohne
     *  Umbiegen über localStorage. */
    function apiBase() {
        return location.origin;
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
        const ansicht = ansichtMerken();
        const url = await vorschauLaden(fileid, '800x800');
        if (ansichtVeraltet(ansicht)) {            // inzwischen andere Ansicht: Foto nicht mehr einblenden
            if (url) { try { URL.revokeObjectURL(url); } catch (_e) { /* */ } }
            return;
        }
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
        const marke = gruppenVideoMarke(beispiel);
        if (marke) {        // Standbild aus einem Video (14.10.2026)
            const m = document.createElement('span');
            m.className = 'gruppen-video-marke';
            m.textContent = marke;
            box.appendChild(m);
            box.title = 'Standbild aus einem Video · ' + marke.slice(3)
                + (beispiel.aufnahme ? ' · Aufnahme ' + beispiel.aufnahme : '');
        }
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
        // Seit S4 (16.10.2026) gibt es keine Vergrößerungs-Symbole mehr auf den
        // Kacheln: der kurze Klick öffnet das Bild, der lange Druck startet die
        // Auswahl (siehe ``alleKachelVerdrahten``). ``ohneKlick`` heißt, dass der
        // Aufrufer Klick UND Langdruck selbst verdrahtet — dann darf hier kein
        // zweiter Klick-Handler entstehen (er würde die Auswahl sofort umschalten).
        if (opt.ohneKlick) {
            // nichts: die Verdrahtung übernimmt der Aufrufer
        } else if (typeof opt.beiTipp === 'function') {
            box.addEventListener('click', () => opt.beiTipp(box));
        } else {
            box.addEventListener('click', () => vollbildOeffnen(kennung, rahmen));
        }
        return box;
    }

    // ── Alle Gesichter eines Vorschlags (02.10.2026) ──────────────────────
    // Seitenweise (48) aus /api/gruppen/gesichter; Antippen markiert, „🚫 …
    // ausschließen“ schickt die Markierten an /api/gruppen/ausschliessen. Am
    // Handy sind sie sofort raus, der nächste Gruppierlauf am PC ordnet sie neu.
    // Seit 07.10.2026 auch für eine ganze Person (``name``: alle Vorschläge in einer Liste);
    // die nächste Seite lädt beim Scrollen von selbst (``beobachter`` am Listenende).
    // 10.10.2026: ``ordnung`` „zeit“ zeigt Jahresblöcke (gemischte Kinder-/Zwillingsgruppen
    // zerfallen so in Abschnitte); „👤 Zuordnen“ hängt Markierte fest an eine benannte Person.
    // Die Sortierung bleibt für die Sitzung gewählt, auch beim nächsten Vorschlag.
    const alle = { kennung: null, name: null, seite: 0, seiten: 0, geladen: 0, letzte: null,
                   markiert: new Set(), kennungJeGid: new Map(), laedt: false, beobachter: null,
                   ordnung: 'guete', letztesJahr: null,
                   // S4 (16.10.2026): läuft ein Auswahlmodus, schalten kurze Klicks um,
                   // sonst öffnen sie das Bild (die Vergrößerungs-Symbole entfallen).
                   auswahlModus: false };

    function alleKnopfAktualisieren() {
        const k = el('gruppen-alle-ausschliessen');
        if (k) {
            k.textContent = gruppenAusschlussKnopf(alle.markiert.size);
            k.disabled = alle.markiert.size === 0;
        }
        const z = el('gruppen-alle-zuordnen');
        if (z) {
            z.textContent = gruppenZuordnenKnopf(alle.markiert.size);
            z.disabled = alle.markiert.size === 0;
        }
        const namen = el('gruppen-alle-namen');
        if (namen && !alle.markiert.size) namen.hidden = true;
        const o = el('gruppen-alle-ordnung');
        if (o) o.textContent = gruppenOrdnungKnopf(alle.ordnung);
    }

    function alleKachelZahl() {
        const raster = el('gruppen-alle-raster');
        return raster ? raster.querySelectorAll('.gruppen-kachel').length : 0;
    }

    /** Jahresköpfe ohne Gesichter darunter entfernen (nach Ausschließen/Zuordnen). */
    function alleJahreAufraeumen() {
        const raster = el('gruppen-alle-raster');
        if (!raster) return;
        Array.from(raster.querySelectorAll('.gruppen-alle-jahr')).forEach((kopf) => {
            const nach = kopf.nextElementSibling;
            if (!nach || nach.classList.contains('gruppen-alle-jahr')) kopf.remove();
        });
        const koepfe = raster.querySelectorAll('.gruppen-alle-jahr');
        alle.letztesJahr = koepfe.length ? koepfe[koepfe.length - 1].textContent : null;
    }

    // ── Auswahlmodus der Gesichterliste (S4, 16.10.2026) ─────────────────
    // Auftrag „Kachelbedienung": langer Druck (~500 ms) startet den Modus und wählt
    // diese Kachel; solange er läuft, schaltet jeder kurze Klick um; außerhalb öffnet
    // ein kurzer Klick das Bild — deshalb entfallen die Vergrößerungs-Symbole auf den
    // Kacheln. Bewegung ab 8 px (Scrollen/Ziehen), ``pointercancel`` und
    // ``lostpointercapture`` brechen den Timer ab, damit vertikales Scrollen und der
    // Browser-Langdruck nicht in die Auswahl laufen. Video-Gesichter bleiben
    // unverdrahtet: der Server lehnt Ausschließen/Zuordnen für sie ab (VIDEO_GESPERRT),
    // sie öffnen weiterhin per kurzem Klick.
    const AUSWAHL_LANGDRUCK_MS = 500;
    const AUSWAHL_BEWEGUNG_PX = 8;

    function alleAuswahlSichtbarMachen() {
        const raster = el('gruppen-alle-raster');
        if (raster) raster.classList.toggle('auswahl-aktiv', alle.auswahlModus);
        const ende = el('gruppen-alle-auswahl-ende');
        if (ende) ende.hidden = !alle.auswahlModus;
    }

    function alleAuswahlModusSetzen(an) {
        alle.auswahlModus = Boolean(an);
        alleAuswahlSichtbarMachen();
        alleKnopfAktualisieren();
    }

    function alleKachelMarkeSetzen(box, gid, an) {
        if (!box || !gid) return;
        if (an) { alle.markiert.add(gid); box.classList.add('markiert'); }
        else { alle.markiert.delete(gid); box.classList.remove('markiert'); }
        box.dataset.gid = gid;
        box.setAttribute('aria-pressed', an ? 'true' : 'false');
    }

    /** Auswahl beenden: alle Markierungen weg, kurze Klicks öffnen wieder Bilder. */
    function alleAuswahlBeenden() {
        const raster = el('gruppen-alle-raster');
        if (raster) {
            Array.from(raster.querySelectorAll('.gruppen-kachel')).forEach((k) => {
                alleKachelMarkeSetzen(k, k.dataset.gid, false);
            });
        }
        alle.markiert.clear();
        alleAuswahlModusSetzen(false);
    }

    /** Kurzer Klick: im Auswahlmodus umschalten, sonst das Bild öffnen. */
    function alleKachelKlick(box, g) {
        if (alle.auswahlModus) {
            alleKachelMarkeSetzen(box, g.gid, !alle.markiert.has(g.gid));
            if (alle.markiert.size === 0) alleAuswahlModusSetzen(false);   // letzte Kachel abgewählt
            else alleKnopfAktualisieren();
            return;
        }
        vollbildOeffnen(gesichtKennung(g), gesichtRahmen(g));
    }

    /** Pointer-Verdrahtung einer Kachel: kurzer Klick öffnet, Halten (500 ms) wählt aus. */
    function alleKachelVerdrahten(box, g) {
        let timer = null;
        let gedrueckt = false;
        let langdruck = false;
        let startX = 0;
        let startY = 0;
        const halten = () => {
            if (!gedrueckt || langdruck) return;
            langdruck = true;
            alleAuswahlModusSetzen(true);
            alleKachelMarkeSetzen(box, g.gid, true);
            alleKnopfAktualisieren();     // „Ausschließen“/„Zuordnen“ gehören zur Auswahl
        };
        const abbrechen = () => {
            gedrueckt = false;
            if (timer) { clearTimeout(timer); timer = null; }
        };
        box.setAttribute('aria-pressed', 'false');
        box.addEventListener('pointerdown', (ev) => {
            if (ev && ev.pointerType === 'mouse' && ev.button !== 0) return;   // rechte/ mittlere Taste
            gedrueckt = true;
            langdruck = false;
            startX = ev ? ev.clientX : 0;
            startY = ev ? ev.clientY : 0;
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => { timer = null; halten(); }, AUSWAHL_LANGDRUCK_MS);
        });
        box.addEventListener('pointermove', (ev) => {
            if (!gedrueckt || !ev) return;
            if (Math.abs(ev.clientX - startX) > AUSWAHL_BEWEGUNG_PX
                || Math.abs(ev.clientY - startY) > AUSWAHL_BEWEGUNG_PX) abbrechen();   // Scrollen/Ziehen
        });
        box.addEventListener('pointerup', abbrechen);
        box.addEventListener('pointercancel', abbrechen);
        box.addEventListener('lostpointercapture', abbrechen);
        // Der Browser-Langdruck öffnet sonst sein Kontextmenü über der Auswahl.
        box.addEventListener('contextmenu', (ev) => { if (langdruck && ev) ev.preventDefault(); });
        box.addEventListener('click', (ev) => {
            if (langdruck) {          // synthetischer Klick nach dem langen Druck
                langdruck = false;
                if (ev) { ev.preventDefault(); ev.stopPropagation(); }
                return;
            }
            alleKachelKlick(box, g);
        });
    }

    async function alleSeiteLaden() {
        if ((!alle.kennung && !alle.name) || alle.laedt || (alle.seiten && alle.seite >= alle.seiten)) return;
        alle.laedt = true;
        const ansicht = ansichtMerken();
        const ziel = alle.name ? 'name=' + encodeURIComponent(alle.name) : 'kennung=' + encodeURIComponent(alle.kennung);
        const fuer = (alle.name || alle.kennung) + '|' + alle.ordnung;
        const antwort = await jsonHolen('/api/gruppen/gesichter?' + ziel
            + '&seite=' + (alle.seite + 1) + '&ordnung=' + alle.ordnung).catch(() => null);
        // Ansicht gewechselt oder neu aufgebaut: ``laedt`` gehört jetzt dem neuen Aufruf.
        if (ansichtVeraltet(ansicht)) return;
        alle.laedt = false;
        if ((alle.name || alle.kennung) + '|' + alle.ordnung !== fuer) return;   // geschlossen/gewechselt
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
            if (alle.ordnung === 'zeit') {
                const jahr = gruppenJahr(g.aufnahme);
                if (jahr !== alle.letztesJahr) {
                    const kopf = document.createElement('div');
                    kopf.className = 'gruppen-alle-jahr';
                    kopf.textContent = jahr;
                    raster.appendChild(kopf);
                    alle.letztesJahr = jahr;
                }
            }
            // Video-Gesichter: Ausschließen/Zuordnen sperrt das Backend -> nicht auswählbar
            // (S4: unverdrahtet, Antippen zeigt das Standbild). Alle anderen Kacheln
            // bekommen die Verdrahtung „kurzer Klick öffnet / Halten wählt aus".
            raster.appendChild(kachel(g, false, g.video === true
                ? { verzoegert: true }
                : { verzoegert: true, ohneKlick: true }));
            if (g.video !== true) alleKachelVerdrahten(raster.lastChild, g);
            raster.lastChild.dataset.gid = g.gid;
            if (g.zugeordnet) {
                raster.lastChild.classList.add('zugeordnet');
                raster.lastChild.title += ' · von Hand zugeordnet';
            }
            alle.kennungJeGid.set(g.gid, g.kennung || alle.kennung);
        });
        alle.geladen = alleKachelZahl();
        if (info) info.textContent = gruppenAlleInfo(antwort, alle.geladen);
        alleEndeBeobachten();
    }

    /** Endlos-Scrollen: ein Merker hinter der Liste lädt die nächste Seite, sobald er ins Bild
     *  kommt. Ohne IntersectionObserver bleibt der Knopf „Weitere laden“ als Rückfall. */
    function alleEndeBeobachten() {
        const mehr = el('gruppen-alle-mehr');
        const offen = alle.seite < alle.seiten;
        if (typeof IntersectionObserver !== 'function') {
            if (mehr) mehr.hidden = !offen;
            return;
        }
        if (mehr) mehr.hidden = true;
        const raster = el('gruppen-alle-raster');
        let merker = el('gruppen-alle-ende');
        if (!merker && raster) {
            merker = document.createElement('div');
            merker.id = 'gruppen-alle-ende';
            merker.className = 'gruppen-meta';
            merker.style.minHeight = '1px';
            raster.insertAdjacentElement('afterend', merker);
        }
        if (!merker) return;
        merker.textContent = offen ? 'lädt weitere …' : '';
        if (alle.beobachter) alle.beobachter.disconnect();
        if (!offen) return;
        alle.beobachter = new IntersectionObserver((eintraege) => {
            if (eintraege.some((e) => e.isIntersecting)) alleSeiteLaden();
        }, { rootMargin: '400px' });
        alle.beobachter.observe(merker);          // meldet sofort, falls das Ende schon sichtbar ist
    }

    /** Gesamtansicht eines Vorschlags; ``vonPerson`` = aus „Benannt“ geöffnet (Zurück führt dorthin). */
    /** Liste leeren und ab Seite 1 laden (Öffnen, Sortierung wechseln). */
    function alleVonVorn() {
        zustand.ansichtSequenz++;          // Neuaufbau: Antworten zur alten Liste verwerfen
        Object.assign(alle, { seite: 0, seiten: 0, geladen: 0, letzte: null, letztesJahr: null, laedt: false });
        alle.markiert.clear();
        alle.kennungJeGid.clear();
        const raster = el('gruppen-alle-raster');
        if (raster) raster.innerHTML = '';
        const info = el('gruppen-alle-info');
        if (info) info.textContent = '';
        alleAuswahlModusSetzen(false);     // S4: jede neu geladene Liste beginnt ohne Auswahlmodus
        alleKnopfAktualisieren();
        alleSeiteLaden();
    }

    function alleOeffnen(kennung, vonPerson) {
        const k = (typeof kennung === 'string' && kennung) ? kennung : (zustand.gruppe && zustand.gruppe.kennung);
        if (!k) return;
        Object.assign(alle, { kennung: k, name: null, vonPerson: Boolean(vonPerson) });
        nurZeigen('alle');
        alleVonVorn();
    }

    /** Alle Gesichter einer benannten Person über alle ihre Vorschläge (07.10.2026). */
    function alleOeffnenPerson(name) {
        if (typeof name !== 'string' || !name) return;
        Object.assign(alle, { kennung: null, name, vonPerson: true });
        nurZeigen('alle');
        alleVonVorn();
    }

    function alleOrdnungWechseln() {
        alle.ordnung = alle.ordnung === 'zeit' ? 'guete' : 'zeit';
        alleVonVorn();
    }

    function alleSchliessen() {
        el('gruppen-alle-ansicht').hidden = true;
        if (alle.beobachter) { alle.beobachter.disconnect(); alle.beobachter = null; }
        alleAuswahlModusSetzen(false);    // S4: Ansicht verlassen beendet den Auswahlmodus
        const kennung = alle.kennung;
        alle.kennung = null;
        alle.name = null;
        alle.laedt = false;
        zustand.ansichtSequenz++;          // laufende Gesichter-/Ausschließen-/Zuordnen-Antworten verwerfen
        // Neu laden: Beispiele ohne die gerade Ausgeschlossenen
        if (alle.vonPerson && zustand.person) personOeffnen(zustand.person.name);
        // Gezielt aus der Übersicht geöffnet: zurück zu genau dieser Gruppe (nicht zur
        // nächsten Quizgruppe), „Zur Übersicht“ bleibt; die Statusmarke bleibt erhalten.
        else if (zustand.detailAktiv && kennung) gruppeDetailLaden(kennung, true);
        else laden();
    }

    // ── Reiter „Offen“ / „Benannt“ (02.10.2026) ─────────────────────────────
    // Wunsch Sebastian: schon benannte Personen wieder aufrufen und bearbeiten
    // wie ein Dokument, dann beim nächsten offenen Vorschlag weitermachen.
    const BEREICHE = { karte: 'gruppen-karte', fertig: 'gruppen-fertig', alle: 'gruppen-alle-ansicht',
                       benannt: 'gruppen-benannt-ansicht', person: 'gruppen-person' };

    function nurZeigen(name) {
        Object.keys(BEREICHE).forEach((k) => { const e = el(BEREICHE[k]); if (e) e.hidden = (k !== name); });
        const liste = el('gruppen-liste-ansicht');
        if (liste) liste.hidden = name !== 'liste';
        // „Zur Übersicht“ steht außerhalb der Karte (bleibt auch bei „fertig“ erreichbar)
        // und gehört nur zur Detailansicht.
        const detailZurueck = el('gruppen-detail-zurueck');
        if (detailZurueck) detailZurueck.hidden = !(zustand.detailAktiv && name === 'karte');
        // Jeder Ansichtswechsel macht noch laufende Anfragen (Quiz, Speichern, Person,
        // Ausschließen/Zuordnen, Vollbild …) für die Anzeige ungültig.
        zustand.ansichtSequenz++;
    }

    const LISTEN_STATUS = ['offen', 'spaeter', 'benannt', 'ausgeblendet'];

    function gruppenListeMelden(text, fehler) {
        const meldung = el('gruppen-liste-meldung');
        if (!meldung) return;
        meldung.textContent = text || '';
        meldung.classList.toggle('fehler', fehler === true);
    }

    function gruppenListeZeigen(antwort) {
        const raster = el('gruppen-liste');
        const seite = el('gruppen-liste-seite');
        const vorher = el('gruppen-liste-vorher');
        const weiter = el('gruppen-liste-weiter');
        if (!raster) return;
        raster.innerHTML = '';
        const gruppen = antwort.gruppen || [];
        if (!gruppen.length) {
            const leer = document.createElement('p');
            leer.className = 'sheet-note';
            leer.textContent = 'In dieser Kategorie gibt es keine Gruppen.';
            raster.appendChild(leer);
        }
        gruppen.forEach((g) => {
            const zeile = document.createElement('div');
            zeile.id = 'gruppen-liste-zeile-' + g.kennung;
            zeile.className = 'gruppen-benannt-zeile gruppen-liste-zeile';
            zeile.setAttribute('role', 'button');
            zeile.setAttribute('aria-label', 'Gruppe öffnen: ' + gruppenZahl(g.groesse) + ' Gesichter');
            zeile.tabIndex = 0;
            const text = document.createElement('span');
            text.className = 'gruppen-benannt-text gruppen-liste-text';
            const zeitraum = gruppenZeitraum(g.von, g.bis);
            text.textContent = gruppenZahl(g.groesse) + ' Gesichter'
                + (zeitraum ? ' · ' + zeitraum : '')
                + (g.status === 'benannt' && g.name ? ' · ' + g.name : '');
            zeile.appendChild(text);
            zeile.addEventListener('click', () => gruppeDetailLaden(g.kennung));
            zeile.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') gruppeDetailLaden(g.kennung); });
            if (g.status === 'spaeter' || g.status === 'ausgeblendet') {
                const oeffnen = document.createElement('button');
                oeffnen.id = 'gruppen-liste-reaktivieren-' + g.kennung;
                oeffnen.type = 'button';
                oeffnen.className = 'gruppen-knopf';
                oeffnen.textContent = '↩ Zurück zu Offen';
                oeffnen.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    gruppeReaktivieren(g.kennung, oeffnen);
                });
                zeile.appendChild(oeffnen);
            }
            raster.appendChild(zeile);
        });
        if (seite) seite.textContent = antwort.gesamt
            ? 'Seite ' + antwort.seite + ' von ' + antwort.seiten + ' · ' + gruppenZahl(antwort.gesamt) + ' Gruppen'
            : 'Keine Gruppen';
        if (vorher) vorher.disabled = antwort.seite <= 1;
        if (weiter) weiter.disabled = !antwort.seiten || antwort.seite >= antwort.seiten;
        LISTEN_STATUS.forEach((status) => {
            const knopf = el('gruppen-liste-status-' + status);
            if (knopf) knopf.classList.toggle('aktiv', zustand.listeStatus === status);
            if (knopf) knopf.setAttribute('aria-pressed', zustand.listeStatus === status ? 'true' : 'false');
        });
    }

    async function gruppenListeLaden(seite) {
        if (!zustand.listeAktiv || el('gruppen-sheet').hidden) return;
        if (seite !== undefined) zustand.listeSeite = seite;
        const sequenz = ++zustand.listenSequenz;
        gruppenListeMelden('… lädt');
        const liste = el('gruppen-liste');
        if (liste) liste.innerHTML = '';
        try {
            const antwort = await jsonHolen('/api/gruppen/liste?status=' + encodeURIComponent(zustand.listeStatus)
                + '&seite=' + zustand.listeSeite + '&je_seite=24');
            if (sequenz !== zustand.listenSequenz || !zustand.listeAktiv || el('gruppen-sheet').hidden) return;
            if (!antwort || antwort.ok !== true) {
                gruppenListeMelden('⚠️ ' + ((antwort && antwort.fehler) || 'Gruppenliste nicht ladbar.'), true);
                return;
            }
            zustand.listeSeite = antwort.seite;
            zustand.listeSeiten = antwort.seiten;
            gruppenListeZeigen(antwort);
            gruppenListeMelden(zustand.listeRueckmeldung
                || (antwort.gruppen.length ? '' : 'In dieser Kategorie gibt es keine Gruppen.'));
        } catch (_e) {
            if (sequenz === zustand.listenSequenz && zustand.listeAktiv && !el('gruppen-sheet').hidden) {
                gruppenListeMelden('⚠️ Keine Verbindung zum Agenten.', true);
            }
        }
    }

    /** Zur Übersicht: nach eigenen Statusaktionen ab Seite 1 (die alte Seite kann leer sein). */
    function gruppenUebersichtOeffnen() {
        const seite = zustand.listeStatusGeaendert ? 1 : (zustand.listeSeite || 1);
        zustand.listeStatusGeaendert = false;
        zustand.listeAktiv = true;
        zustand.detailAktiv = false;
        zustand.listenSequenz++;
        zustand.detailSequenz++;
        nurZeigen('liste');
        melde('');
        gruppenListeLaden(seite);
    }

    /** ``behalteStatus``: erneutes Laden derselben Gruppe (z. B. nach „Alle Gesichter“)
     *  vergisst eine schon erfolgte Statusaktion nicht. */
    async function gruppeDetailLaden(kennung, behalteStatus) {
        const sequenz = ++zustand.detailSequenz;
        zustand.detailAktiv = true;
        zustand.listeAktiv = false;
        zustand.listenSequenz++;
        nurZeigen('karte');
        el('gruppen-karte').hidden = true;
        if (!behalteStatus) zustand.listeStatusGeaendert = false;
        // Die Listenansicht ist jetzt verborgen: der Ladestatus gehört in das immer
        // sichtbare Meldungsfeld unter den Bereichen.
        gruppenListeMelden('');
        melde('… lädt Gruppe');
        try {
            const antwort = await jsonHolen('/api/gruppen/detail/' + encodeURIComponent(kennung));
            if (sequenz !== zustand.detailSequenz || !zustand.detailAktiv || el('gruppen-sheet').hidden) return;
            if (!antwort || antwort.ok !== true) {
                zustand.detailAktiv = false;
                zustand.listeAktiv = true;
                nurZeigen('liste');
                melde('');
                gruppenListeMelden('⚠️ ' + ((antwort && antwort.fehler) || 'Gruppe nicht ladbar.'), true);
                return;
            }
            melde('');
            zeigen(antwort, true);
        } catch (_e) {
            if (sequenz === zustand.detailSequenz && zustand.detailAktiv && !el('gruppen-sheet').hidden) {
                zustand.detailAktiv = false;
                zustand.listeAktiv = true;
                nurZeigen('liste');
                melde('');
                gruppenListeMelden('⚠️ Keine Verbindung zum Agenten.', true);
            }
        }
    }

    function gruppeDetailZurueck() {
        zustand.detailAktiv = false;
        zustand.detailSequenz++;
        zustand.listeAktiv = true;
        nurZeigen('liste');
        melde('');
        const seite = zustand.listeStatusGeaendert ? 1 : (zustand.listeSeite || 1);
        zustand.listeStatusGeaendert = false;
        gruppenListeLaden(seite);
    }

    async function gruppeReaktivieren(kennung, knopf) {
        if (zustand.beschaeftigt) return;
        zustand.beschaeftigt = true;
        if (knopf) knopf.disabled = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/antwort', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kennung, art: 'offen' }),
            });
            if (antwort && antwort.ok === true) {
                el('gruppen-liste-undo').hidden = false;
                zustand.listeRueckmeldung = '✓ Zurück zu Offen. Diese Aktion kann rückgängig gemacht werden.';
                gruppenListeMelden(zustand.listeRueckmeldung);
                zustand.listeSeite = 1;
            } else {
                if (knopf) knopf.disabled = false;
                gruppenListeMelden('⚠️ ' + ((antwort && antwort.fehler) || 'Reaktivieren fehlgeschlagen.'), true);
                return;
            }
        } catch (_e) {
            if (knopf) knopf.disabled = false;
            gruppenListeMelden('⚠️ Keine Verbindung zum Agenten.', true);
            return;
        } finally {
            zustand.beschaeftigt = false;
        }
        await gruppenListeLaden(1);
    }

    async function gruppenListeRueckgaengig() {
        if (zustand.beschaeftigt) return;
        zustand.beschaeftigt = true;
        const knopf = el('gruppen-liste-undo');
        if (knopf) knopf.disabled = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/rueckgaengig', { method: 'POST' });
            if (!antwort || antwort.ok !== true) {
                gruppenListeMelden('⚠️ ' + ((antwort && antwort.fehler) || 'Nichts zurückzunehmen.'), true);
                return;
            }
            if (knopf) knopf.hidden = true;
            zustand.listeRueckmeldung = '↩ Reaktivierung zurückgenommen.';
            gruppenListeMelden(zustand.listeRueckmeldung);
            zustand.listeSeite = 1;
        } catch (_e) {
            gruppenListeMelden('⚠️ Keine Verbindung zum Agenten.', true);
        } finally {
            zustand.beschaeftigt = false;
            if (knopf) knopf.disabled = false;
        }
        await gruppenListeLaden(1);
    }

    function reiterSetzen(name) {
        zustand.listeAktiv = false;
        zustand.detailAktiv = false;
        zustand.listenSequenz++;
        zustand.detailSequenz++;
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
        const nr = ++zustand.personenSequenz;
        const antwort = await jsonHolen('/api/gruppen/personen').catch(() => null);
        if (nr !== zustand.personenSequenz) return;          // neuere Personenliste ist unterwegs
        if (!antwort || antwort.ok !== true) {
            zustand.personen = [];
            if (info) info.textContent = '⚠️ ' + ((antwort && antwort.fehler) || 'Keine Verbindung zum Agenten.');
            gruppenAuswahlFuellen();
            personenZeigen();
            return;
        }
        zustand.personen = antwort.personen || [];
        gruppenAuswahlFuellen();
        personenZeigen();
    }

    /** Auswahlfeld „Gruppe“ füllen: alle Gesichtsgruppen der geladenen Personen.
     *  Die gewählte Gruppe bleibt stehen, solange es sie noch gibt; sonst Filter aus. */
    function gruppenAuswahlFuellen() {
        const feld = el('gruppen-benannt-gruppe');
        if (!feld) return;
        const eintraege = gruppenAuswahlEintraege(zustand.personen);
        const gewaehlt = eintraege.some((g) => g.kennung === zustand.personenGruppe) ? zustand.personenGruppe : '';
        feld.innerHTML = '';
        const alle = document.createElement('option');
        alle.value = '';
        alle.textContent = 'Alle Gruppen';
        feld.appendChild(alle);
        eintraege.forEach((g) => {
            const option = document.createElement('option');
            option.value = g.kennung;
            option.textContent = gruppenAuswahlText(g);
            feld.appendChild(option);
        });
        feld.value = gewaehlt;
        zustand.personenGruppe = gewaehlt;
    }

    function personenZeigen() {
        const liste = el('gruppen-benannt-liste');
        const info = el('gruppen-benannt-info');
        if (!liste) return;
        liste.innerHTML = '';
        const frage = (el('gruppen-benannt-filter') || {}).value || '';
        const gruppe = zustand.personenGruppe || '';
        const passend = zustand.personen.filter((p) => gruppenPersonPasst(p.name, frage)
            && gruppenPersonPasstGruppe(p, gruppe));
        if (info) {
            const zusatz = gruppe ? ' · ' + (gruppenNummer(gruppe) || String(gruppe)) : '';
            info.textContent = !zustand.personen.length
                ? 'Noch niemand benannt – im Reiter „Offen“ geht es los.'
                : (passend.length ? gruppenZahl(passend.length) + (passend.length === 1 ? ' Person' : ' Personen') + zusatz
                    : (gruppe || frage.trim() ? 'Keine Person passt zu diesem Filter.' : 'Keine Person'))
                  + ' · antippen zum Ansehen und Bearbeiten';
        }
        passend.forEach((p) => {
            const zeile = document.createElement('div');
            zeile.className = 'gruppen-benannt-zeile';
            zeile.setAttribute('role', 'listitem');
            zeile.tabIndex = 0;
            if (p.beispiel) zeile.appendChild(kachel(p.beispiel, true, { verzoegert: true, beiTipp: () => {} }));
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

    /** Person laden und zeigen; ``leise`` = bei Fehlschlag still zur Liste (z. B. nach Rückgängig).
     *  Rückgabe: true = gezeigt, false = Fehlschlag (Liste), null = Antwort veraltet und verworfen. */
    async function personOeffnen(name, leise) {
        const nr = ++zustand.personSequenz;
        const ansicht = ansichtMerken();
        const antwort = await jsonHolen('/api/gruppen/person?name=' + encodeURIComponent(name)).catch(() => null);
        if (nr !== zustand.personSequenz || ansichtVeraltet(ansicht)) return null;
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
        if (vorschlaege.length) {
            const allesKnopf = document.createElement('button');
            allesKnopf.type = 'button';
            allesKnopf.id = 'gruppen-person-alle';
            allesKnopf.className = 'gruppen-knopf haupt';
            allesKnopf.textContent = gruppenPersonAlleKnopf(p.name, gesichter);
            allesKnopf.addEventListener('click', () => alleOeffnenPerson(p.name));
            box.appendChild(allesKnopf);
        }
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
        const ansicht = ansichtMerken();
        try {
            const antwort = await jsonHolen(pfad, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(koerper || {}),
            });
            if (!antwort || antwort.ok !== true) {
                // Meldungen einer veralteten Anfrage gehören nicht in die neue Ansicht.
                if (!ansichtVeraltet(ansicht)) melde('⚠️ ' + ((antwort && antwort.fehler) || 'Speichern fehlgeschlagen'), false);
                return null;
            }
            return antwort;
        } catch (_e) {
            if (!ansichtVeraltet(ansicht)) melde('⚠️ Keine Verbindung zum Agenten.', false);
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
        const ansicht = ansichtMerken();
        const name = zustand.person ? zustand.person.name : '';
        const antwort = await bearbeiten('/api/gruppen/loesen', { kennung: kennung });
        if (!antwort) return;
        if (ansichtVeraltet(ansicht)) { personenLaden(); return; }     // Aktion gilt, Anzeige gehört woanders hin
        if (await personOeffnen(name, true) === null) return;
        melde('✓ ' + gruppenNummer(kennung) + ' gelöst – er steht wieder unter „Offen“ (↩ Rückgängig möglich).');
    }

    async function umbenennen() {
        if (!zustand.person) return;
        const neu = el('gruppen-person-name').value.trim();
        if (!neu || neu === zustand.person.name) { melde('Bitte einen neuen Namen eingeben.', false); return; }
        const ansicht = ansichtMerken();
        const antwort = await bearbeiten('/api/gruppen/umbenennen', { alt: zustand.person.name, neu: neu });
        if (!antwort) return;
        if (ansichtVeraltet(ansicht)) { personenLaden(); return; }
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
        const ansicht = ansichtMerken();
        const antwort = await bearbeiten('/api/gruppen/profil', koerper);
        if (!antwort || ansichtVeraltet(ansicht) || !zustand.person) return;
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
        const ansicht = ansichtMerken();
        const antwort = await jsonHolen('/api/gruppen/suche?limit=8&q=' + encodeURIComponent(frage)).catch(() => null);
        if (nr !== _kontaktNr || ansichtVeraltet(ansicht)) return;                      // nur die neueste Antwort zeigen
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
        const ansicht = ansichtMerken();
        const antwort = await bearbeiten('/api/gruppen/profil', { name: zustand.person.name, kontakt_id: String(kontaktId) });
        if (!antwort || ansichtVeraltet(ansicht) || !zustand.person) return;
        zustand.person.profil = antwort;
        personZeigen(zustand.person);
        melde('✓ Kontakt verknüpft');
    }

    async function personRueckgaengig() {
        const ansicht = ansichtMerken();
        const aktuellerName = zustand.person && zustand.person.name;
        const antwort = await bearbeiten('/api/gruppen/rueckgaengig', {});
        if (!antwort) return;
        if (ansichtVeraltet(ansicht)) { personenLaden(); return; }
        const z = antwort.zurueckgenommen || {};
        const ziel = (z.art === 'umbenennen' && z.name) ? z.name : aktuellerName;
        if (ziel && await personOeffnen(ziel, true) === null) return;
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
        if ((!alle.kennung && !alle.name) || !alle.markiert.size || zustand.beschaeftigt) return;
        zustand.beschaeftigt = true;
        const ansicht = ansichtMerken();
        const ziel = alle.name ? alle.name : 'diesem Vorschlag';
        try {
            const liste = Array.from(alle.markiert);
            const antwort = alle.name
                ? await jsonHolen('/api/gruppen/person/ausschliessen', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: alle.name,
                                           gesichter: liste.map((gid) => ({ kennung: alle.kennungJeGid.get(gid), gid })) }),
                })
                : await jsonHolen('/api/gruppen/ausschliessen', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ kennung: alle.kennung, gesichter: liste }),
                });
            // Ansicht inzwischen gewechselt: ausgeschlossen ist ausgeschlossen (Server), aber
            // Raster, Auswahl und Meldungen gehören jetzt zu einer anderen Gesichterliste.
            if (ansichtVeraltet(ansicht)) return;
            if (antwort && antwort.ok === true) {
                alleMarkierteEntfernen(liste);       // nur die gesendeten, später Markiertes bleibt
                if (alle.letzte) {
                    alle.letzte.gesamt = antwort.gesamt;
                    alle.letzte.ausgeschlossen = (alle.letzte.ausgeschlossen || 0) + antwort.ausgeschlossen;
                    el('gruppen-alle-info').textContent = gruppenAlleInfo(alle.letzte, alle.geladen);
                }
                melde('✓ ' + gruppenZahl(antwort.ausgeschlossen) + ' ausgeschlossen – sie gehören nicht mehr zu '
                      + ziel + ' (↩ Rückgängig in der Karte).');
                alleKnopfAktualisieren();
                alleEndeBeobachten();          // Liste wurde kürzer: ggf. sofort nachladen
            } else {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Ausschließen fehlgeschlagen'), false);
            }
        } catch (_e) {
            if (!ansichtVeraltet(ansicht)) melde('⚠️ Keine Verbindung zum Agenten.', false);
        } finally {
            zustand.beschaeftigt = false;
        }
    }

    /** Kacheln aus der Liste nehmen; gibt ihre Zahl zurück. Mit ``gids`` nur genau diese
     *  (die abgeschickten), sonst alle markierten. Später Markiertes bleibt markiert. */
    function alleMarkierteEntfernen(gids) {
        const raster = el('gruppen-alle-raster');
        const nur = Array.isArray(gids) ? new Set(gids.map(String)) : null;
        const weg = Array.from(raster.querySelectorAll('.gruppen-kachel')).filter((k) => (nur
            ? nur.has(String(k.dataset && k.dataset.gid)) : k.classList.contains('markiert')));
        weg.forEach((k) => k.remove());
        if (nur) gids.forEach((gid) => alle.markiert.delete(gid)); else alle.markiert.clear();
        alleJahreAufraeumen();
        alle.geladen = alleKachelZahl();
        return weg.length;
    }

    // ── Gesichter fest einer Person zuordnen (10.10.2026) ─────────────────
    // Gemischte Vorschläge (Zwillinge, Geschwister als Kinder, Fotobuch): statt nur
    // auszuschließen, gehen markierte Gesichter direkt an eine schon benannte Person.
    // Am Handy wirkt das sofort, der nächste Gruppierlauf am PC übernimmt es.

    /** Die Person, die gerade offen ist (deren Name taucht in der Auswahl nicht auf). */
    function alleOffenePerson() {
        if (alle.name) return alle.name;
        return (alle.vonPerson && zustand.person && zustand.person.name) || '';
    }

    function alleNamenZeigen() {
        const kasten = el('gruppen-alle-namen');
        if (!kasten || !alle.markiert.size) return;
        if (!kasten.hidden) { kasten.hidden = true; return; }
        kasten.innerHTML = '';
        // Namen aus dem Offen-Reiter UND der Personenliste (wer direkt in „Benannt“ startet)
        const namen = gruppenZuordnenNamen((zustand.namen || []).concat(
            (zustand.personen || []).map((p) => p && p.name)), alleOffenePerson());
        const kopf = document.createElement('p');
        kopf.className = 'gruppen-meta';
        kopf.textContent = namen.length
            ? 'Zu wem gehören die markierten Gesichter?'
            : 'Noch keine andere Person benannt – erst einen Vorschlag benennen.';
        kasten.appendChild(kopf);
        namen.forEach((n) => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'gruppen-knopf gruppen-namen-chip';
            b.textContent = n;
            b.addEventListener('click', () => alleZuordnen(n));
            kasten.appendChild(b);
        });
        kasten.hidden = false;
    }

    async function alleZuordnen(name) {
        if (!alle.markiert.size || zustand.beschaeftigt || typeof name !== 'string' || !name) return;
        zustand.beschaeftigt = true;
        const ansicht = ansichtMerken();
        try {
            const liste = Array.from(alle.markiert);
            const antwort = await jsonHolen('/api/gruppen/zuordnen', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name,
                                       gesichter: liste.map((gid) => ({ kennung: alle.kennungJeGid.get(gid), gid })) }),
            });
            if (ansichtVeraltet(ansicht)) return;       // siehe alleAusschliessen
            if (antwort && antwort.ok === true) {
                const weg = alleMarkierteEntfernen(liste);
                if (alle.letzte) {
                    alle.letzte.gesamt = Math.max(0, (Number(alle.letzte.gesamt) || 0) - weg);
                    el('gruppen-alle-info').textContent = gruppenAlleInfo(alle.letzte, alle.geladen);
                }
                melde(antwort.zugeordnet
                    ? '✓ ' + gruppenZahl(antwort.zugeordnet) + ' zu ' + antwort.name
                      + ' zugeordnet (↩ Rückgängig in der Karte).'
                    : '✓ Die Gesichter gehörten schon zu ' + antwort.name + '.');
                alleKnopfAktualisieren();
                alleEndeBeobachten();
            } else {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Zuordnen fehlgeschlagen'), false);
            }
        } catch (_e) {
            if (!ansichtVeraltet(ansicht)) melde('⚠️ Keine Verbindung zum Agenten.', false);
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

    function zeigen(antwort, direkt) {
        const karte = el('gruppen-karte');
        const fertig = el('gruppen-fertig');
        namenListeSetzen(antwort && antwort.namen);
        if (!direkt && zustand.reiter !== 'offen') return; // inzwischen auf „Benannt“ gewechselt
        // „Zur Übersicht“ nur in der Detailansicht – auch wenn das Backend „fertig“ meldet.
        const detailZurueck = el('gruppen-detail-zurueck');
        if (detailZurueck) detailZurueck.hidden = !direkt;
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
        const statusText = { spaeter: 'Später', benannt: 'Benannt', ausgeblendet: 'Ausgeblendet', offen: 'Offen' };
        el('gruppen-meta').textContent = gruppenMeta(g)
            + (g.war_spaeter ? ' · zurückgestellt' : '')
            + (direkt ? ' · ' + (statusText[g.status] || 'Offen') + (g.name ? ' · ' + g.name : '') : '');
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
        const sequenz = ++zustand.quizSequenz;
        const ansicht = ansichtMerken();
        melde('… lädt');
        const antwort = await jsonHolen('/api/gruppen/naechste').catch(() => null);
        // Verspätete Antwort: inzwischen anderer Ansichtsstand (Detail, Übersicht, andere
        // Ansicht, geschlossen) oder neuere Anfrage – nichts ändern, zustand.gruppe bleibt.
        if (sequenz !== zustand.quizSequenz || ansichtVeraltet(ansicht)
                || zustand.detailAktiv || zustand.listeAktiv) return;
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
        const ansicht = ansichtMerken();
        zustand.beschaeftigt = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/antwort', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(koerper),
            });
            const veraltet = ansichtVeraltet(ansicht);
            if (antwort && antwort.ok === true) {
                const direkt = zustand.detailAktiv;
                if ((direkt || veraltet) && ['name', 'gleich', 'spaeter', 'unbekannt', 'offen'].includes(art)) {
                    zustand.listeStatusGeaendert = true;
                }
                if (veraltet) {
                    // Gespeichert ist gespeichert – aber die Anzeige gehört inzwischen zu
                    // einer anderen Ansicht/Gruppe und bleibt unangetastet.
                    fortschrittLaden();
                    return;
                }
                const vorher = zustand.gruppe ? zustand.gruppe.kennung : null;
                zeigen(antwort, direkt);
                const jetzt = zustand.gruppe ? zustand.gruppe.kennung : null;
                melde(gruppenAntwortText(art, antwort.gespeichert, Boolean(jetzt && jetzt !== vorher)));
                fortschrittLaden();
            } else if (!veraltet) {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Speichern fehlgeschlagen'), false);
            }
        } catch (_e) {
            if (!ansichtVeraltet(ansicht)) melde('⚠️ Keine Verbindung zum Agenten.', false);
        } finally {
            zustand.beschaeftigt = false;
        }
    }


    async function rueckgaengig() {
        if (zustand.beschaeftigt) return;
        const ansicht = ansichtMerken();
        zustand.beschaeftigt = true;
        try {
            const antwort = await jsonHolen('/api/gruppen/rueckgaengig', { method: 'POST' });
            const veraltet = ansichtVeraltet(ansicht);
            if (antwort && antwort.ok === true) {
                const direkt = zustand.detailAktiv;
                if ((direkt || veraltet) && antwort.zurueckgenommen
                        && ['name', 'gleich', 'spaeter', 'unbekannt', 'offen'].includes(antwort.zurueckgenommen.art)) {
                    zustand.listeStatusGeaendert = true;
                }
                if (veraltet) {
                    fortschrittLaden();        // zurückgenommen ist zurückgenommen, Anzeige bleibt
                    return;
                }
                zeigen(antwort, direkt);
                melde(gruppenRueckgaengigText(antwort.zurueckgenommen));
                fortschrittLaden();
            } else if (!veraltet) {
                melde('⚠️ ' + ((antwort && antwort.fehler) || 'Nichts zurückzunehmen'), false);
            }
        } catch (_e) {
            if (!ansichtVeraltet(ansicht)) melde('⚠️ Keine Verbindung zum Agenten.', false);
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
        const ansicht = ansichtMerken();
        if (stoppt) zustand.diktat = { wert: feld.value, bis: Date.now() + DIKTAT_WARTEN_MS };
        await starteFeldDiktat(feld, knopf);
        if (ansichtVeraltet(ansicht)) return;       // Meldung gehört zur früheren Ansicht
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
        const ansicht = ansichtMerken();
        const p = await jsonHolen('/api/gruppen/profil?name=' + encodeURIComponent(name)).catch(() => null);
        // Nur zeigen, wenn Ansicht und eingetippter Name noch dieselben sind.
        if (ansichtVeraltet(ansicht) || feld.value.trim() !== name) return;
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
        zustand.listeAktiv = false;
        zustand.detailAktiv = false;
        zustand.listenSequenz++;
        zustand.detailSequenz++;
        zustand.ansichtSequenz++;
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
        const alleZu = el('gruppen-alle-zuordnen');
        if (alleZu) alleZu.addEventListener('click', alleNamenZeigen);
        const alleOrdnung = el('gruppen-alle-ordnung');
        if (alleOrdnung) alleOrdnung.addEventListener('click', alleOrdnungWechseln);
        const alleAuswahlEnde = el('gruppen-alle-auswahl-ende');
        if (alleAuswahlEnde) alleAuswahlEnde.addEventListener('click', alleAuswahlBeenden);
        const zurueckFertig = el('gruppen-zurueck-fertig');
        if (zurueckFertig) zurueckFertig.addEventListener('click', rueckgaengig);
        const uebersicht = el('gruppen-uebersicht');
        if (uebersicht) uebersicht.addEventListener('click', gruppenUebersichtOeffnen);
        const detailZurueck = el('gruppen-detail-zurueck');
        if (detailZurueck) detailZurueck.addEventListener('click', gruppeDetailZurueck);
        const listeQuiz = el('gruppen-liste-quiz');
        if (listeQuiz) listeQuiz.addEventListener('click', () => reiterSetzen('offen'));
        LISTEN_STATUS.forEach((status) => {
            const filter = el('gruppen-liste-status-' + status);
            if (filter) filter.addEventListener('click', () => {
                zustand.listeStatus = status;
                zustand.listeSeite = 1;
                zustand.listeRueckmeldung = '';
                gruppenListeLaden(1);
            });
        });
        const listeAktualisieren = el('gruppen-liste-aktualisieren');
        if (listeAktualisieren) listeAktualisieren.addEventListener('click', () => {
            zustand.listeRueckmeldung = '';
            gruppenListeLaden();
        });
        const listeVorher = el('gruppen-liste-vorher');
        if (listeVorher) listeVorher.addEventListener('click', () => {
            if (!listeVorher.disabled) { zustand.listeRueckmeldung = ''; gruppenListeLaden(Math.max(1, zustand.listeSeite - 1)); }
        });
        const listeWeiter = el('gruppen-liste-weiter');
        if (listeWeiter) listeWeiter.addEventListener('click', () => {
            if (!listeWeiter.disabled) { zustand.listeRueckmeldung = ''; gruppenListeLaden(Math.min(zustand.listeSeiten, zustand.listeSeite + 1)); }
        });
        const listeUndo = el('gruppen-liste-undo');
        if (listeUndo) listeUndo.addEventListener('click', gruppenListeRueckgaengig);
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
        const gruppeFeld = el('gruppen-benannt-gruppe');
        if (gruppeFeld) gruppeFeld.addEventListener('change', () => {
            zustand.personenGruppe = gruppeFeld.value || '';
            personenZeigen();
        });
        const filterZurueck = el('gruppen-benannt-filter-zuruecksetzen');
        if (filterZurueck) filterZurueck.addEventListener('click', () => {
            // Beide Filter zusammen leeren (Suche UND Gruppe) — Wunsch aus dem Auftrag.
            if (filter) filter.value = '';
            zustand.personenGruppe = '';
            if (gruppeFeld) gruppeFeld.value = '';
            personenZeigen();
            if (filter) filter.focus();
        });
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
