/**
 * Erzähl-Diashow (Auftrag E8a, 28.09.2026)
 * -----------------------------------------
 * Sebastian wählt ein Ereignis und sieht zuerst ALLE Bilder als Raster
 * (Übersicht, 06.10.2026) — dort erzählt er zur ganzen Gruppe. Antippen
 * öffnet ein Bild einzeln (Diashow mit ◀ ▶), dort erzählt er zu diesem Bild;
 * „← Alle Bilder" führt zurück. Tippen oder Mikrofon. Eine Geschichte hängt
 * am Ereignis, in der Einzelansicht zusätzlich am Bild (Backend:
 * app/services/erzaehl_service.py, app/router/erzaehlen.py, Präfix
 * /api/erzaehlen). Übersicht und Einzelbild zeigen, wer erkannt wurde
 * (Gesichter-Zuordnung + bestätigte Namen, /ereignisse/{kennung}/personen);
 * 🔊 liest es auf Tipp vor.
 *
 * Bewusst eine EIGENE Datei (kein Umbau von app.js — Quiz-Code, riskant).
 * app.js patcht window.fetch bereits global mit dem API-Key (Skript-
 * Reihenfolge in index.html: app.js VOR erzaehlen.js) — alle fetch-Aufrufe
 * hier profitieren automatisch davon.
 *
 * Bilder werden NUR kurzlebig gezeigt: fetch -> Blob -> Objekt-URL (wie die
 * Galerie in app.js), die Objekt-URL wird beim Bildwechsel und beim
 * Schließen wieder freigegeben (kein Speicherwachstum).
 *
 * Mikrofon: dieselbe Aufnahme-/Transkriptionsweise wie app.js — bewusst OHNE
 * MediaRecorder (WebM/Opus -> HTTP 400 beim Transkriptions-Anbieter):
 * AudioWorklet (pcm-recorder.js) -> PCM -> WAV -> POST /api/sprache/transkript.
 */

// =========================================================================
// Reine Funktionen (ohne DOM) — von frontend/tests/test_erzaehlen.js geprüft.
// =========================================================================

/** Normalisiert einen Text für den Sprachbefehl-Vergleich: klein, getrimmt,
 *  Satzzeichen am Rand weg. Ohne DOM, ohne Netz. */
function _erzaehlNormalisieren(text) {
    if (typeof text !== 'string') return '';
    return text.trim().toLowerCase().replace(/[.!?,;:]+$/g, '').trim();
}

/** REINE Funktion: Erkennt einen Sprachbefehl im (bereits transkribierten)
 *  Text. Nur ein EXAKTES Treffen auf eines der festen Worte zählt — sonst
 *  ist es normaler Diktat-Text, kein Befehl.
 *  @returns {'weiter'|'zurueck'|'speichern'|null} */
function erzaehlSprachbefehl(text) {
    const t = _erzaehlNormalisieren(text);
    if (!t) return null;
    if (t === 'weiter' || t === 'nächstes' || t === 'naechstes') return 'weiter';
    if (t === 'zurück' || t === 'zurueck' || t === 'vorheriges') return 'zurueck';
    if (t === 'speichern') return 'speichern';
    return null;
}

/** REINE Funktion: Titel eines Ereignisses — ``event``, sonst ``thema``,
 *  sonst „Ohne Titel" (derselbe Rückfall wie im Backend-Dienst). Nimmt auch
 *  ein bereits vom Backend geliefertes ``titel``-Feld direkt an, falls
 *  vorhanden. */
function erzaehlTitel(ereignis) {
    if (!ereignis || typeof ereignis !== 'object') return 'Ohne Titel';
    if (typeof ereignis.titel === 'string' && ereignis.titel.trim()) return ereignis.titel.trim();
    if (typeof ereignis.event === 'string' && ereignis.event.trim()) return ereignis.event.trim();
    if (typeof ereignis.thema === 'string' && ereignis.thema.trim()) return ereignis.thema.trim();
    return 'Ohne Titel';
}

/** REINE Funktion: nächster Diashow-Index, GEKLEMMT an den Rändern (kein
 *  Überlauf/Umlauf — am ersten Bild bleibt „zurück" auf 0, am letzten bleibt
 *  „weiter" auf n-1). richtung 1 = vor, -1 = zurück, alles andere -> 1.
 *  n <= 0 -> 0. */
function erzaehlIndex(i, n, richtung) {
    const anzahl = (typeof n === 'number' && isFinite(n)) ? Math.floor(n) : 0;
    if (anzahl <= 0) return 0;
    const start = (typeof i === 'number' && isFinite(i)) ? Math.floor(i) : 0;
    const schritt = (richtung === -1) ? -1 : 1;
    const naechster = start + schritt;
    return Math.max(0, Math.min(anzahl - 1, naechster));
}

/** REINE Funktion: Rumpf für POST /api/erzaehlen/geschichten. Ohne
 *  ``dateiKennung`` (null/undefined) gilt die Geschichte der ganzen Gruppe
 *  (Übersicht), mit ihr dem einen Bild (Einzelansicht). */
function erzaehlGeschichteKoerper(ereignisKennung, text, dateiKennung) {
    const koerper = { ereignis_kennung: ereignisKennung, text, quelle: 'tippen' };
    if (dateiKennung !== null && dateiKennung !== undefined) koerper.datei_kennung = dateiKennung;
    return koerper;
}

/** REINE Funktion: Zahl der Geschichten je Bild (Schlüssel = datei_kennung
 *  als Text) — für das ✎ auf den Kacheln der Übersicht. Geschichten zur
 *  ganzen Gruppe (ohne Bild) und kaputte Einträge zählen nicht. */
function erzaehlGeschichtenJeBild(geschichten) {
    const zaehler = {};
    if (!Array.isArray(geschichten)) return zaehler;
    geschichten.forEach((g) => {
        if (!g || g.datei_kennung === null || g.datei_kennung === undefined) return;
        const k = String(g.datei_kennung);
        zaehler[k] = (zaehler[k] || 0) + 1;
    });
    return zaehler;
}

/** REINE Funktion: „A", „A und B", „A, B und C". */
function _erzaehlAufzaehlen(namen) {
    if (namen.length <= 1) return namen.join('');
    return namen.slice(0, -1).join(', ') + ' und ' + namen[namen.length - 1];
}

/** REINE Funktion: „N Person(en) noch ohne Namen" oder ''. */
function _erzaehlOhneNamen(n) {
    if (!n || n < 1) return '';
    return `${n} ${n === 1 ? 'Person' : 'Personen'} noch ohne Namen`;
}

/** REINE Funktion: Zeile „Wer ist auf diesen Bildern?" für die Übersicht —
 *  aus der Antwort von /api/erzaehlen/ereignisse/{kennung}/personen
 *  (Feld ``personen``). Höchstens 8 Namen, der Rest als „… und N weitere".
 *  Keine Daten -> ''. */
function erzaehlPersonenUebersicht(p) {
    if (!p || typeof p !== 'object' || !Array.isArray(p.benannt)) return '';
    const ohne = (p.ohne_namen && Number(p.ohne_namen.personen)) || 0;
    if (!p.benannt.length && !ohne) return 'Auf diesen Bildern wurde niemand erkannt.';
    const teile = [];
    if (p.benannt.length) {
        const namen = p.benannt.slice(0, 8)
            .filter((e) => e && typeof e.name === 'string' && e.name)
            .map((e) => `${e.name} (${e.bilder} ${e.bilder === 1 ? 'Bild' : 'Bilder'})`);
        const rest = p.benannt.length - namen.length;
        teile.push('Erkannt: ' + namen.join(', ') + (rest > 0 ? ` und ${rest} weitere` : ''));
    }
    if (ohne) teile.push(_erzaehlOhneNamen(ohne));
    return teile.join(' · ');
}

/** REINE Funktion: Zeile für ein einzelnes Bild — ``eintrag`` ist
 *  ``personen.bilder[fileid]`` (fehlt, wenn niemand erkannt wurde). */
function erzaehlPersonenBild(eintrag) {
    const namen = (eintrag && Array.isArray(eintrag.namen))
        ? eintrag.namen.filter((n) => typeof n === 'string' && n) : [];
    const ohne = (eintrag && Array.isArray(eintrag.ohne_namen)) ? eintrag.ohne_namen.length : 0;
    if (!namen.length && !ohne) return 'Auf diesem Bild wurde niemand erkannt.';
    const teile = [];
    if (namen.length) teile.push('Auf diesem Bild: ' + _erzaehlAufzaehlen(namen));
    if (ohne) teile.push(namen.length ? _erzaehlOhneNamen(ohne) : 'Auf diesem Bild: ' + _erzaehlOhneNamen(ohne));
    return teile.join(' · ');
}

/** REINE Funktion: eingegebener Titel -> gespeicherter Titel (Leerraum
 *  zusammengezogen, höchstens 120 Zeichen; '' heißt „automatischer Titel"). */
function erzaehlTitelSaeubern(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/\s+/g, ' ').trim().slice(0, 120);
}

/** REINE Funktion: Anzeige-Zeile -> Sprechtext („·" wird zur Satzpause). */
function erzaehlSprechtext(text) {
    if (typeof text !== 'string') return '';
    return text.replace(/\s*·\s*/g, '. ').replace(/\s+/g, ' ').trim();
}

// =========================================================================
// Verdrahtung (DOM). Läuft nur im Browser — Node-Tests schneiden oben
// stehende Funktionen wörtlich aus und lassen den Rest unangetastet.
// =========================================================================
(function () {
    if (typeof document === 'undefined') return;

    const ERLAUBTE_GROESSEN = ['32x32', '120x120', '480x480', '800x800'];
    const GROESSE_GROSS = '800x800';

    /** Basis-Adresse wie in app.js (dieselbe Herleitung, eigenständig, damit
     *  diese Datei ohne app.js-Umbau auskommt). */
    function apiBase() {
        try {
            return localStorage.getItem('api_base')
                || (location.origin.startsWith('http') ? location.origin : 'http://localhost:8080');
        } catch (_e) {
            return location.origin;
        }
    }

    const zustand = {
        offen: false,
        ereignisse: [],
        aktuellesEreignis: null,   // Kennung des offenen Ereignisses
        detail: null,              // Antwort von GET /ereignisse/{kennung}
        index: 0,                  // Diashow-Index
        objektUrls: new Set(),     // Buchführung, damit sie freigegeben werden
        aufnahmeLaeuft: false,
        ansicht: 'uebersicht',     // 'uebersicht' (alle Bilder) | 'einzel' (ein Bild)
        rasterUrls: new Set(),     // Objekt-URLs der Kacheln — leben bis zum Verlassen der Gruppe
        rasterLauf: 0,             // Zähler: veraltete Kachel-Ladungen verwerfen
        rasterBeobachter: null,
        rasterScroll: 0,           // Scrollstand der Übersicht beim Öffnen eines Bildes
        entwurf: { uebersicht: '', einzel: '' }, // halbfertiger Text je Ansicht
        personen: null,            // Antwort von /ereignisse/{kennung}/personen (Feld personen)
        personenFehler: '',
        audio: null,               // laufende Vorlese-Ausgabe (nur über /api/speak)
    };

    function el(id) { return document.getElementById(id); }

    function bildUrl(fileid, groesse) {
        const g = ERLAUBTE_GROESSEN.indexOf(groesse) !== -1 ? groesse : GROESSE_GROSS;
        return `${apiBase()}/api/cloud/thumb?fileid=${encodeURIComponent(fileid)}&groesse=${g}`;
    }

    /** fetch -> Blob -> Objekt-URL (wie fotoBildLaden in app.js). Fehlschlag
     *  -> null, damit die Diashow beim nächsten/vorigen Bild weiterläuft. */
    async function objektUrlHolen(url) {
        try {
            const res = await fetch(url);
            if (!res || res.ok !== true) return null;
            const blob = await res.blob();
            if (!blob) return null;
            return URL.createObjectURL(blob);
        } catch (_e) {
            return null;
        }
    }

    /** Großbild der Einzelansicht: wird beim nächsten Bildwechsel freigegeben. */
    async function bildLaden(url) {
        const objektUrl = await objektUrlHolen(url);
        if (objektUrl) zustand.objektUrls.add(objektUrl);
        return objektUrl;
    }

    function objekteFreigeben() {
        zustand.objektUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (_e) { /* schon weg */ }
        });
        zustand.objektUrls.clear();
    }

    async function jsonHolen(pfad, optionen) {
        const res = await fetch(`${apiBase()}${pfad}`, optionen || {});
        return res.json().catch(() => ({}));
    }

    // ---- Blatt öffnen/schließen ------------------------------------------

    function sheetOeffnen() {
        const sheet = el('erzaehlen-sheet');
        if (!sheet) return;
        sheet.hidden = false;
        zustand.offen = true;
        ereignislisteLaden();
    }

    function sheetSchliessen() {
        const sheet = el('erzaehlen-sheet');
        if (sheet) sheet.hidden = true;
        zustand.offen = false;
        aufnahmeAbbrechen();
        objekteFreigeben();
        zurZurListe();
    }

    function zurZurListe() {
        const liste = el('erzaehl-liste-spalte');
        const diashow = el('erzaehl-diashow-spalte');
        if (liste) liste.hidden = false;
        if (diashow) diashow.hidden = true;
        rasterFreigeben();
        objekteFreigeben();
        vorlesenStoppen();
        zustand.personen = null;
        zustand.personenFehler = '';
        ansichtUmschalten('uebersicht');
        zustand.aktuellesEreignis = null;
        zustand.detail = null;
    }

    // ---- Ereignisliste ------------------------------------------------

    async function ereignislisteLaden() {
        const hinweis = el('erzaehl-liste-hinweis');
        const liste = el('erzaehl-liste');
        if (!liste) return;
        liste.textContent = '';
        if (hinweis) hinweis.textContent = 'Lädt …';

        const jahrFeld = el('erzaehl-jahr');
        const sucheFeld = el('erzaehl-suche');
        const params = new URLSearchParams();
        if (jahrFeld && jahrFeld.value.trim()) params.set('jahr', jahrFeld.value.trim());
        if (sucheFeld && sucheFeld.value.trim()) params.set('suche', sucheFeld.value.trim());

        let daten;
        try {
            daten = await jsonHolen(`/api/erzaehlen/ereignisse?${params.toString()}`);
        } catch (_e) {
            daten = { ok: false, error: 'Verbindung zum Backend fehlgeschlagen.' };
        }

        if (!daten || daten.ok !== true) {
            if (hinweis) hinweis.textContent = (daten && daten.error) || 'Ereignisse nicht verfügbar.';
            return;
        }

        const eintraege = Array.isArray(daten.eintraege) ? daten.eintraege : [];
        zustand.ereignisse = eintraege;
        if (hinweis) {
            hinweis.textContent = eintraege.length
                ? `${eintraege.length} von ${daten.gesamt} Ereignissen`
                    + (daten.defekte_zeilen ? ` · ${daten.defekte_zeilen} defekte Zeile(n) übersprungen` : '')
                : 'Keine Ereignisse gefunden.';
        }

        eintraege.forEach((ereignis) => {
            const zeile = document.createElement('button');
            zeile.type = 'button';
            zeile.className = 'erzaehl-row';
            zeile.setAttribute('data-kennung', ereignis.kennung || '');
            zeile.setAttribute('role', 'listitem');

            const titel = document.createElement('div');
            titel.className = 'erzaehl-row-titel';
            titel.textContent = erzaehlTitel(ereignis);
            zeile.appendChild(titel);

            const meta = document.createElement('div');
            meta.className = 'erzaehl-row-meta';
            const teile = [];
            if (ereignis.jahr) teile.push(String(ereignis.jahr));
            teile.push(`${ereignis.anzahl_dateien || 0} Bild${ereignis.anzahl_dateien === 1 ? '' : 'er'}`);
            if (ereignis.anzahl_geschichten) {
                const marker = document.createElement('span');
                marker.className = 'erzaehl-row-marker';
                marker.textContent = `✎ ${ereignis.anzahl_geschichten}`;
                meta.textContent = teile.join(' · ') + ' · ';
                meta.appendChild(marker);
            } else {
                meta.textContent = teile.join(' · ');
            }
            zeile.appendChild(meta);

            zeile.addEventListener('click', () => ereignisOeffnen(ereignis.kennung));
            liste.appendChild(zeile);
        });
    }

    // ---- Ereignis / Diashow ------------------------------------------

    async function ereignisOeffnen(kennung) {
        if (!kennung) return;
        const listeSpalte = el('erzaehl-liste-spalte');
        const diashowSpalte = el('erzaehl-diashow-spalte');
        const hinweis = el('erzaehl-hinweis');

        let daten;
        try {
            daten = await jsonHolen(`/api/erzaehlen/ereignisse/${encodeURIComponent(kennung)}`);
        } catch (_e) {
            daten = { ok: false, error: 'Verbindung zum Backend fehlgeschlagen.' };
        }

        if (!daten || daten.ok !== true) {
            if (hinweis) hinweis.textContent = (daten && daten.error) || 'Ereignis nicht verfügbar.';
            return;
        }

        zustand.aktuellesEreignis = kennung;
        zustand.detail = daten.ereignis;
        zustand.index = 0;
        if (hinweis) hinweis.textContent = '';

        // Am Handy: zwei Stufen. Auf dem Desktop bleibt die Liste sichtbar
        // (nebeneinander) — [hidden] auf der Liste stört dort nicht, das
        // CSS zeigt beide Spalten via flex; wir blenden sie hier nur am
        // Handy tatsächlich aus (die Back-Taste holt sie zurück).
        if (listeSpalte) listeSpalte.hidden = window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
        if (diashowSpalte) diashowSpalte.hidden = false;

        // Erst die Übersicht mit allen Bildern (Wunsch 06.10.2026), ein Bild
        // öffnet sich einzeln erst per Antippen.
        objekteFreigeben();
        rasterAufbauen();
        ansichtUmschalten('uebersicht');
        titelBearbeitenSchliessen();
        titelAnzeigen();
        if (diashowSpalte) diashowSpalte.scrollTop = 0;
        personenLaden(kennung);   // kommt nach — die Übersicht steht sofort
    }

    // ---- Eigener Titel (06.10.2026) ----------------------------------------
    // ✏️ öffnet das Eingabefeld; gespeichert wird nur anhängend am Server
    // (POST /ereignisse/{kennung}/titel). Leer = zurück zum automatischen Titel.

    function titelAnzeigen() {
        const ziel = el('erzaehl-titel');
        if (ziel) ziel.textContent = zustand.detail ? erzaehlTitel(zustand.detail) : '';
    }

    function titelBearbeitenOeffnen() {
        const block = el('erzaehl-titel-bearbeiten');
        const eingabe = el('erzaehl-titel-eingabe');
        const zurueck = el('erzaehl-titel-zuruecksetzen');
        if (!block || !eingabe || !zustand.detail) return;
        eingabe.value = erzaehlTitel(zustand.detail);
        if (zurueck) {
            zurueck.hidden = !zustand.detail.titel_eigen;
            zurueck.textContent = '↺ Automatisch: ' + (zustand.detail.titel_automatisch || 'Ohne Titel');
        }
        block.hidden = false;
        eingabe.focus();
        try { eingabe.select(); } catch (_e) { /* ohne Auswahl auch gut */ }
    }

    function titelBearbeitenSchliessen() {
        const block = el('erzaehl-titel-bearbeiten');
        if (block) block.hidden = true;
    }

    async function titelSpeichern(name) {
        const kennung = zustand.aktuellesEreignis;
        const hinweis = el('erzaehl-hinweis');
        if (!kennung) return;
        let daten = {};
        let ok = false;
        try {
            const res = await fetch(`${apiBase()}/api/erzaehlen/ereignisse/${encodeURIComponent(kennung)}/titel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: erzaehlTitelSaeubern(name) }),
            });
            daten = await res.json().catch(() => ({}));
            ok = res.ok && daten.ok === true;
        } catch (_e) {
            daten = { detail: 'Verbindung zum Backend fehlgeschlagen.' };
        }
        if (!ok) {
            if (hinweis) hinweis.textContent = daten.detail || daten.error || 'Titel nicht gespeichert.';
            return;
        }
        if (hinweis) hinweis.textContent = '';
        if (zustand.aktuellesEreignis !== kennung || !zustand.detail) return;   // inzwischen gewechselt
        zustand.detail.titel = daten.titel;
        zustand.detail.titel_eigen = daten.titel_eigen;
        zustand.detail.titel_automatisch = daten.titel_automatisch;
        titelAnzeigen();
        titelBearbeitenSchliessen();
        // Liste links/oben gleich mitziehen.
        zustand.ereignisse.forEach((e) => { if (e && e.kennung === kennung) e.titel = daten.titel; });
        document.querySelectorAll('#erzaehl-liste .erzaehl-row').forEach((zeile) => {
            if (zeile.getAttribute('data-kennung') !== kennung) return;
            const titelFeld = zeile.querySelector('.erzaehl-row-titel');
            if (titelFeld) titelFeld.textContent = daten.titel;
        });
    }

    // ---- Wer ist auf den Bildern (06.10.2026) ------------------------------
    // Quelle: Gesichter-Zuordnung + bestätigte Namen am Handy, nur lesend
    // (GET /api/erzaehlen/ereignisse/{kennung}/personen).

    async function personenLaden(kennung) {
        zustand.personen = null;
        zustand.personenFehler = '';
        personenAnzeigen();
        let daten;
        try {
            daten = await jsonHolen(`/api/erzaehlen/ereignisse/${encodeURIComponent(kennung)}/personen`);
        } catch (_e) {
            daten = { ok: false, error: 'Personen nicht erreichbar.' };
        }
        if (zustand.aktuellesEreignis !== kennung) return;   // inzwischen gewechselt
        if (daten && daten.ok === true && daten.personen) zustand.personen = daten.personen;
        else zustand.personenFehler = (daten && daten.error) || 'Personen nicht verfügbar.';
        personenAnzeigen();
    }

    function personenAnzeigen() {
        const einzel = zustand.ansicht === 'einzel';
        const zeile = el(einzel ? 'erzaehl-bild-personen' : 'erzaehl-personen');
        const text = el(einzel ? 'erzaehl-bild-personen-text' : 'erzaehl-personen-text');
        const andere = el(einzel ? 'erzaehl-personen' : 'erzaehl-bild-personen');
        if (andere) andere.hidden = true;
        if (!zeile || !text) return;
        let inhalt = '';
        if (zustand.personen) {
            inhalt = einzel
                ? erzaehlPersonenBild((zustand.personen.bilder || {})[String(aktuelleDateiKennung())])
                : erzaehlPersonenUebersicht(zustand.personen);
        } else if (zustand.personenFehler && !einzel) {
            inhalt = 'Personen: ' + zustand.personenFehler;
        }
        text.textContent = inhalt;
        zeile.hidden = !inhalt;
        const knopf = zeile.querySelector('.erzaehl-vorlesen');
        if (knopf) knopf.hidden = !zustand.personen;
    }

    function vorlesenStoppen() {
        if (zustand.audio) {
            try { zustand.audio.pause(); } catch (_e) { /* schon aus */ }
            if (typeof zustand.audio.onended === 'function') zustand.audio.onended();
            zustand.audio = null;
        }
        if (window.speechSynthesis) {
            try { window.speechSynthesis.cancel(); } catch (_e) { /* nichts zu tun */ }
        }
    }

    /** Liest die Personen-Zeile vor — nur auf ausdrücklichen Tipp auf 🔊.
     *  Zuerst die Browser-Stimme (bleibt auf dem Gerät; am PC vorhanden). Die
     *  App am Handy hat keine (am 06.10.2026 gemessen: speechSynthesis fehlt
     *  in der Android-WebView) -> dieselbe Strecke wie das Vorlesen im Chat
     *  (POST /api/speak über OpenRouter). */
    async function vorlesen(quelleId) {
        const quelle = el(quelleId);
        const sprech = erzaehlSprechtext(quelle ? quelle.textContent : '');
        if (!sprech) return;
        vorlesenStoppen();
        const hinweis = el('erzaehl-hinweis');
        if (hinweis) hinweis.textContent = '';
        if (window.speechSynthesis && typeof SpeechSynthesisUtterance === 'function') {
            const satz = new SpeechSynthesisUtterance(sprech);
            satz.lang = 'de-DE';
            const deutsch = window.speechSynthesis.getVoices().find((v) => (v.lang || '').startsWith('de'));
            if (deutsch) satz.voice = deutsch;
            window.speechSynthesis.speak(satz);
            return;
        }
        try {
            const res = await fetch(`${apiBase()}/api/speak`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: sprech.slice(0, 2000) }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const url = URL.createObjectURL(await res.blob());
            const audio = new Audio(url);
            audio.onended = () => { try { URL.revokeObjectURL(url); } catch (_e) { /* schon weg */ } };
            audio.onerror = audio.onended;
            zustand.audio = audio;
            await audio.play();
        } catch (_e) {
            if (hinweis) hinweis.textContent = 'Vorlesen gerade nicht möglich.';
        }
    }

    // ---- Übersicht: alle Bilder der Gruppe (06.10.2026) -------------------
    // Kacheln laden erst, wenn sie ins Bild scrollen, höchstens vier zugleich.
    // Ihre Objekt-URLs leben bis zum Verlassen der Gruppe (eigene Buchführung —
    // die Einzelansicht gibt bei jedem Bildwechsel nur ihre eigenen frei).

    const KACHEL_GROESSE = '480x480';
    const KACHEL_PARALLEL = 4;
    const kachelSchlange = [];
    let kachelnLaufend = 0;

    function kachelSchlangeAbarbeiten() {
        while (kachelnLaufend < KACHEL_PARALLEL && kachelSchlange.length) {
            const aufgabe = kachelSchlange.shift();
            kachelnLaufend++;
            Promise.resolve().then(aufgabe).catch(() => {}).finally(() => {
                kachelnLaufend--;
                kachelSchlangeAbarbeiten();
            });
        }
    }

    function rasterFreigeben() {
        zustand.rasterLauf++;                 // laufende Ladungen verwerfen ihr Ergebnis
        kachelSchlange.length = 0;
        if (zustand.rasterBeobachter) {
            zustand.rasterBeobachter.disconnect();
            zustand.rasterBeobachter = null;
        }
        zustand.rasterUrls.forEach((u) => {
            try { URL.revokeObjectURL(u); } catch (_e) { /* schon weg */ }
        });
        zustand.rasterUrls.clear();
        const raster = el('erzaehl-raster');
        if (raster) raster.textContent = '';
    }

    function kachelLaden(kachel) {
        const lauf = zustand.rasterLauf;
        const fileid = kachel.getAttribute('data-datei');
        kachelSchlange.push(async () => {
            if (lauf !== zustand.rasterLauf) return;
            const url = await objektUrlHolen(bildUrl(fileid, KACHEL_GROESSE));
            if (lauf !== zustand.rasterLauf) {
                if (url) { try { URL.revokeObjectURL(url); } catch (_e) { /* schon weg */ } }
                return;
            }
            if (!url) { kachel.classList.add('leer'); return; }
            zustand.rasterUrls.add(url);
            const bild = document.createElement('img');
            bild.alt = '';
            bild.src = url;
            kachel.insertBefore(bild, kachel.firstChild);
        });
        kachelSchlangeAbarbeiten();
    }

    function rasterAufbauen() {
        rasterFreigeben();
        const raster = el('erzaehl-raster');
        const detail = zustand.detail;
        if (!raster || !detail) return;
        const dateien = Array.isArray(detail.datei_kennungen) ? detail.datei_kennungen : [];
        const kacheln = dateien.map((kennung, i) => {
            const kachel = document.createElement('button');
            kachel.type = 'button';
            kachel.className = 'erzaehl-kachel';
            kachel.setAttribute('role', 'listitem');
            kachel.setAttribute('data-datei', String(kennung));
            kachel.setAttribute('aria-label', `Bild ${i + 1} von ${dateien.length} öffnen`);
            const marker = document.createElement('span');
            marker.className = 'erzaehl-kachel-marker';
            marker.hidden = true;
            kachel.appendChild(marker);
            kachel.addEventListener('click', () => bildOeffnen(i));
            raster.appendChild(kachel);
            return kachel;
        });
        if (typeof IntersectionObserver === 'function') {
            const beobachter = new IntersectionObserver((eintraege) => {
                eintraege.forEach((e) => {
                    if (!e.isIntersecting) return;
                    beobachter.unobserve(e.target);
                    kachelLaden(e.target);
                });
            }, { rootMargin: '300px' });
            zustand.rasterBeobachter = beobachter;
            kacheln.forEach((k) => beobachter.observe(k));
        } else {
            kacheln.forEach(kachelLaden);
        }
        kachelMarkerAktualisieren();
    }

    function kachelMarkerAktualisieren() {
        const raster = el('erzaehl-raster');
        if (!raster || !zustand.detail) return;
        const zahlen = erzaehlGeschichtenJeBild(zustand.detail.geschichten);
        raster.querySelectorAll('.erzaehl-kachel').forEach((kachel) => {
            const n = zahlen[kachel.getAttribute('data-datei')] || 0;
            const marker = kachel.querySelector('.erzaehl-kachel-marker');
            if (!marker) return;
            marker.hidden = !n;
            marker.textContent = n ? `✎ ${n}` : '';
        });
    }

    /** Schaltet Übersicht <-> Einzelansicht. Halbfertiger Text bleibt je
     *  Ansicht stehen, damit ein Gruppen-Text nicht versehentlich an einem
     *  Bild landet (und umgekehrt). */
    function ansichtUmschalten(neu) {
        const feld = el('erzaehl-text');
        if (feld && neu !== zustand.ansicht) {
            zustand.entwurf[zustand.ansicht] = feld.value;
            feld.value = zustand.entwurf[neu] || '';
        }
        zustand.ansicht = neu;
        const einzel = neu === 'einzel';
        const uebersicht = el('erzaehl-uebersicht');
        const einzelBlock = el('erzaehl-einzel');
        const zurListe = el('erzaehl-zurueck-zur-liste');
        if (uebersicht) uebersicht.hidden = einzel;
        if (einzelBlock) einzelBlock.hidden = !einzel;
        if (zurListe) zurListe.hidden = einzel;
        if (feld) feld.placeholder = einzel ? 'Erzähl etwas zu diesem Bild …' : 'Erzähl etwas zur ganzen Gruppe …';

        const kopf = el('erzaehl-uebersicht-kopf');
        if (kopf && !einzel) {
            const n = (zustand.detail && Array.isArray(zustand.detail.datei_kennungen))
                ? zustand.detail.datei_kennungen.length : 0;
            kopf.textContent = n === 0 ? 'Keine Bilder in diesem Ereignis.'
                : `${n} Bild${n === 1 ? '' : 'er'} · Antippen öffnet ein Bild einzeln`;
        }
        if (zustand.detail) {
            geschichtenAnzeigen();
            kachelMarkerAktualisieren();
        }
        personenAnzeigen();
    }

    function bildOeffnen(index) {
        const spalte = el('erzaehl-diashow-spalte');
        if (zustand.ansicht === 'uebersicht' && spalte) zustand.rasterScroll = spalte.scrollTop;
        zustand.index = index;
        ansichtUmschalten('einzel');
        if (spalte) spalte.scrollTop = 0;
        bildZeigen();
    }

    function zurUebersicht() {
        objekteFreigeben();                 // Großbild raus, Kacheln bleiben
        const bild = el('erzaehl-bild');
        if (bild) { bild.hidden = true; bild.removeAttribute('src'); }
        ansichtUmschalten('uebersicht');
        const spalte = el('erzaehl-diashow-spalte');
        if (spalte) spalte.scrollTop = zustand.rasterScroll;
    }

    function aktuelleDateiKennung() {
        const detail = zustand.detail;
        if (!detail || !Array.isArray(detail.datei_kennungen)) return null;
        return detail.datei_kennungen[zustand.index];
    }

    async function bildZeigen() {
        const detail = zustand.detail;
        const bild = el('erzaehl-bild');
        const platzhalter = el('erzaehl-bild-platzhalter');
        const zaehler = el('erzaehl-zaehler');
        const zurueckBtn = el('erzaehl-zurueck-zur-liste'); // Back-Taste in der Diashow-Spalte (siehe HTML)

        if (!detail) return;
        const dateien = Array.isArray(detail.datei_kennungen) ? detail.datei_kennungen : [];
        const n = dateien.length;

        if (zaehler) zaehler.textContent = `${n ? zustand.index + 1 : 0} / ${n}`;
        personenAnzeigen();

        if (bild) { bild.hidden = true; }
        if (platzhalter) { platzhalter.hidden = false; platzhalter.textContent = '… lädt'; }

        objekteFreigeben(); // vorheriges Bild raus, bevor das neue kommt

        if (n === 0) {
            if (platzhalter) platzhalter.textContent = 'Keine Bilder in diesem Ereignis.';
            geschichtenAnzeigen();
            return;
        }

        const kennung = dateien[zustand.index];
        const meinIndex = zustand.index;
        const meinDetail = zustand.detail;
        const objektUrl = await bildLaden(bildUrl(kennung, GROESSE_GROSS));
        // Veraltete Antwort (schnell weitergeklickt / Ereignis gewechselt):
        // verwerfen, sonst zeigt die Diashow ein anderes Bild als der Zähler
        // und eine Geschichte landet am falschen Foto.
        if (zustand.index !== meinIndex || zustand.detail !== meinDetail || zustand.ansicht !== 'einzel') {
            if (objektUrl) {
                try { URL.revokeObjectURL(objektUrl); } catch (_e) { /* schon weg */ }
                zustand.objektUrls.delete(objektUrl);
            }
            return;
        }
        if (!objektUrl) {
            if (platzhalter) platzhalter.textContent = 'Bild nicht verfügbar.';
        } else if (bild) {
            bild.src = objektUrl;
            bild.alt = `Bild ${zustand.index + 1} von ${n}`;
            bild.hidden = false;
            if (platzhalter) platzhalter.hidden = true;
        }

        geschichtenAnzeigen();
        void zurueckBtn; // nur Referenz, damit Linter den Namen nicht als unbenutzt meldet
    }

    function geschichtenAnzeigen() {
        // Übersicht: Geschichten zur ganzen Gruppe über dem Raster;
        // Einzelansicht: zu diesem Bild + zur ganzen Gruppe unter dem Bild.
        const imRaster = zustand.ansicht !== 'einzel';
        const container = el(imRaster ? 'erzaehl-gruppen-geschichten' : 'erzaehl-geschichten');
        const anderer = el(imRaster ? 'erzaehl-geschichten' : 'erzaehl-gruppen-geschichten');
        if (anderer) anderer.textContent = '';
        if (!container) return;
        container.textContent = '';
        const detail = zustand.detail;
        if (!detail || !Array.isArray(detail.geschichten)) return;

        const dateiKennung = aktuelleDateiKennung();
        const zumBild = detail.geschichten.filter((g) => g && g.datei_kennung === dateiKennung);
        const zumEreignis = detail.geschichten.filter((g) => g && g.datei_kennung == null);

        const abschnitt = (titel, liste) => {
            if (!liste.length) return;
            const kopf = document.createElement('div');
            kopf.className = 'sheet-group';
            kopf.textContent = titel;
            container.appendChild(kopf);
            liste.forEach((g) => {
                const zeile = document.createElement('div');
                zeile.className = 'erzaehl-geschichte-zeile';
                const text = document.createElement('div');
                text.textContent = g.text || '';
                zeile.appendChild(text);
                const meta = document.createElement('div');
                meta.className = 'erzaehl-geschichte-meta';
                meta.textContent = `${g.zeit || ''} · ${g.quelle || ''}`;
                zeile.appendChild(meta);
                container.appendChild(zeile);
            });
        };

        if (!imRaster) abschnitt('Zu diesem Bild', zumBild);
        abschnitt('Zur ganzen Gruppe', zumEreignis);
    }

    function diashowSchritt(richtung) {
        if (zustand.ansicht !== 'einzel') return; // in der Übersicht gibt es kein Blättern
        const detail = zustand.detail;
        if (!detail || !Array.isArray(detail.datei_kennungen)) return;
        zustand.index = erzaehlIndex(zustand.index, detail.datei_kennungen.length, richtung);
        bildZeigen();
    }

    // ---- Geschichte speichern -------------------------------------------

    async function geschichteSpeichern() {
        const feld = el('erzaehl-text');
        const hinweis = el('erzaehl-hinweis');
        if (!feld) return;
        const text = feld.value.trim();
        if (!text) return;
        if (!zustand.aktuellesEreignis) return;

        // Übersicht -> Geschichte zur ganzen Gruppe (ohne Bild),
        // Einzelansicht -> zu diesem Bild.
        const dk = zustand.ansicht === 'einzel' ? aktuelleDateiKennung() : null;
        const body = erzaehlGeschichteKoerper(zustand.aktuellesEreignis, text, dk);

        try {
            const res = await fetch(`${apiBase()}/api/erzaehlen/geschichten`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const daten = await res.json().catch(() => ({}));
            if (!res.ok || daten.ok !== true) {
                if (hinweis) hinweis.textContent = daten.detail || daten.error || 'Speichern fehlgeschlagen.';
                return;
            }
            feld.value = '';
            if (hinweis) hinweis.textContent = '';
            // Frisch anhängen, damit „Zu diesem Bild"/„Zum Ereignis" sofort
            // die neue Geschichte zeigt — ohne kompletten Nachlade-Rundlauf.
            if (zustand.detail && Array.isArray(zustand.detail.geschichten)) {
                zustand.detail.geschichten.push(daten.geschichte);
            }
            geschichtenAnzeigen();
            kachelMarkerAktualisieren();
        } catch (_e) {
            if (hinweis) hinweis.textContent = 'Verbindung zum Backend fehlgeschlagen.';
        }
    }

    // ---- Mikrofon (wie app.js: AudioWorklet -> WAV -> Transkript) --------

    let audioContext = null;
    let workletNode = null;
    let sourceNode = null;
    let audioStream = null;
    let pcmChunks = [];

    function micStatusSetzen(text) {
        const zeile = el('erzaehl-mic-status');
        if (!zeile) return;
        if (!text) { zeile.hidden = true; zeile.textContent = ''; return; }
        zeile.hidden = false;
        zeile.textContent = text;
    }

    function aufnahmeFreigeben() {
        if (workletNode) { try { workletNode.port.onmessage = null; workletNode.disconnect(); } catch (_e) {} workletNode = null; }
        if (sourceNode) { try { sourceNode.disconnect(); } catch (_e) {} sourceNode = null; }
        if (audioContext) { try { audioContext.close(); } catch (_e) {} audioContext = null; }
        if (audioStream) { try { audioStream.getTracks().forEach((t) => t.stop()); } catch (_e) {} audioStream = null; }
    }

    function aufnahmeAbbrechen() {
        if (!zustand.aufnahmeLaeuft) return;
        zustand.aufnahmeLaeuft = false;
        pcmChunks = [];
        aufnahmeFreigeben();
        micStatusSetzen('');
    }

    /** Float32-Blöcke [-1,1] -> WAV-Datei (PCM 16 Bit, Mono) — wie app.js. */
    function _erzaehlEncodeWav(chunks, sampleRate) {
        let samples = 0;
        for (const chunk of chunks) samples += chunk.length;
        const buffer = new ArrayBuffer(44 + samples * 2);
        const view = new DataView(buffer);
        const writeString = (offset, str) => {
            for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
        };
        writeString(0, 'RIFF');
        view.setUint32(4, 36 + samples * 2, true);
        writeString(8, 'WAVE');
        writeString(12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(36, 'data');
        view.setUint32(40, samples * 2, true);
        let offset = 44;
        for (const chunk of chunks) {
            for (let i = 0; i < chunk.length; i++) {
                const s = Math.max(-1, Math.min(1, chunk[i]));
                view.setInt16(offset, s * 0x7FFF, true);
                offset += 2;
            }
        }
        return new Blob([buffer], { type: 'audio/wav' });
    }

    async function aufnahmeStarten() {
        if (zustand.aufnahmeLaeuft) { aufnahmeStoppen(); return; }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            micStatusSetzen('Mikrofon nur über localhost/HTTPS verfügbar.');
            return;
        }
        try {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (audioContext.state === 'suspended') await audioContext.resume();
            await audioContext.audioWorklet.addModule('pcm-recorder.js');
            pcmChunks = [];
            sourceNode = audioContext.createMediaStreamSource(audioStream);
            workletNode = new AudioWorkletNode(audioContext, 'pcm-recorder');
            workletNode.port.onmessage = (event) => {
                pcmChunks.push(event.data);
                if (zustand.aufnahmeLaeuft) micStatusSetzen('hört zu …');
            };
            sourceNode.connect(workletNode);
            workletNode.connect(audioContext.destination);
            zustand.aufnahmeLaeuft = true;
            micStatusSetzen('Mikrofon offen');
        } catch (err) {
            aufnahmeFreigeben();
            zustand.aufnahmeLaeuft = false;
            micStatusSetzen('Mikrofon nicht verfügbar (' + (err && err.message ? err.message : '?') + ')');
        }
    }

    function aufnahmeStoppen() {
        if (!zustand.aufnahmeLaeuft) return;
        const sampleRate = audioContext ? audioContext.sampleRate : 48000;
        const chunks = pcmChunks;
        pcmChunks = [];
        zustand.aufnahmeLaeuft = false;
        aufnahmeFreigeben();
        if (!chunks.length) { micStatusSetzen(''); return; }
        transkribieren(_erzaehlEncodeWav(chunks, sampleRate));
    }

    async function transkribieren(blob) {
        micStatusSetzen('denkt nach …');
        try {
            const formData = new FormData();
            formData.append('file', blob, 'audio.wav');
            const res = await fetch(`${apiBase()}/api/sprache/transkript`, { method: 'POST', body: formData });
            const daten = await res.json().catch(() => ({}));
            const text = (typeof daten.text === 'string') ? daten.text.trim() : '';
            if (!text) { micStatusSetzen(''); return; }

            const befehl = erzaehlSprachbefehl(text);
            if (befehl === 'weiter') { diashowSchritt(1); }
            else if (befehl === 'zurueck') { diashowSchritt(-1); }
            else if (befehl === 'speichern') { await geschichteSpeichern(); }
            else {
                const feld = el('erzaehl-text');
                if (feld) {
                    const vorhanden = feld.value.trim();
                    feld.value = vorhanden ? vorhanden + ' ' + text : text;
                }
            }
        } catch (_e) {
            // Fehlertolerant: Diashow bleibt bedienbar, Diktat geht einmal verloren.
        } finally {
            micStatusSetzen('');
        }
    }

    // ---- Tastatur / Wischen ----------------------------------------------

    function tastaturBehandeln(ev) {
        if (!zustand.offen || el('erzaehl-diashow-spalte').hidden) return;
        const titelBlock = el('erzaehl-titel-bearbeiten');
        if (ev.key === 'Escape') {
            if (titelBlock && !titelBlock.hidden) titelBearbeitenSchliessen();
            else if (zustand.ansicht === 'einzel') zurUebersicht(); else sheetSchliessen();
            return;
        }
        // Pfeiltasten beim Tippen in einem Feld bewegen den Cursor, nicht die Diashow.
        if (ev.target && /^(INPUT|TEXTAREA)$/.test(ev.target.tagName || '')) return;
        if (ev.key === 'ArrowRight') { diashowSchritt(1); }
        else if (ev.key === 'ArrowLeft') { diashowSchritt(-1); }
    }

    let wischStartX = null;
    function wischStart(ev) {
        wischStartX = (ev.touches && ev.touches[0]) ? ev.touches[0].clientX : null;
    }
    function wischEnde(ev) {
        if (wischStartX === null) return;
        const endX = (ev.changedTouches && ev.changedTouches[0]) ? ev.changedTouches[0].clientX : null;
        if (endX === null) { wischStartX = null; return; }
        const delta = endX - wischStartX;
        wischStartX = null;
        if (Math.abs(delta) < 40) return;
        diashowSchritt(delta < 0 ? 1 : -1);
    }

    // ---- Aufbau ------------------------------------------------------

    function init() {
        const oeffnenBtn = el('erzaehlen-btn');
        if (oeffnenBtn) oeffnenBtn.addEventListener('click', sheetOeffnen);

        const schliessenBtn = el('erzaehlen-close');
        if (schliessenBtn) schliessenBtn.addEventListener('click', sheetSchliessen);

        const sheet = el('erzaehlen-sheet');
        if (sheet) sheet.addEventListener('click', (ev) => { if (ev.target === sheet) sheetSchliessen(); });

        const zurueckBtn = el('erzaehl-zurueck-zur-liste');
        if (zurueckBtn) zurueckBtn.addEventListener('click', zurZurListe);
        const zurUebersichtBtn = el('erzaehl-zur-uebersicht');
        if (zurUebersichtBtn) zurUebersichtBtn.addEventListener('click', zurUebersicht);
        const titelAendern = el('erzaehl-titel-aendern');
        if (titelAendern) titelAendern.addEventListener('click', titelBearbeitenOeffnen);
        const titelEingabe = el('erzaehl-titel-eingabe');
        const titelOk = el('erzaehl-titel-speichern');
        if (titelOk && titelEingabe) titelOk.addEventListener('click', () => titelSpeichern(titelEingabe.value));
        if (titelEingabe) titelEingabe.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') { ev.preventDefault(); titelSpeichern(titelEingabe.value); }
        });
        const titelAbbrechen = el('erzaehl-titel-abbrechen');
        if (titelAbbrechen) titelAbbrechen.addEventListener('click', titelBearbeitenSchliessen);
        const titelZurueck = el('erzaehl-titel-zuruecksetzen');
        if (titelZurueck) titelZurueck.addEventListener('click', () => titelSpeichern(''));

        const vorlesenGruppe = el('erzaehl-personen-vorlesen');
        if (vorlesenGruppe) vorlesenGruppe.addEventListener('click', () => vorlesen('erzaehl-personen-text'));
        const vorlesenBild = el('erzaehl-bild-personen-vorlesen');
        if (vorlesenBild) vorlesenBild.addEventListener('click', () => vorlesen('erzaehl-bild-personen-text'));

        const vorBtn = el('erzaehl-vor');
        if (vorBtn) vorBtn.addEventListener('click', () => diashowSchritt(-1));
        const weiterBtn = el('erzaehl-weiter');
        if (weiterBtn) weiterBtn.addEventListener('click', () => diashowSchritt(1));

        const sucheFeld = el('erzaehl-suche');
        if (sucheFeld) sucheFeld.addEventListener('input', ereignislisteLaden);
        const jahrFeld = el('erzaehl-jahr');
        if (jahrFeld) jahrFeld.addEventListener('input', ereignislisteLaden);

        const speichernBtn = el('erzaehl-speichern-btn');
        if (speichernBtn) speichernBtn.addEventListener('click', geschichteSpeichern);

        const micBtn = el('erzaehl-mic-btn');
        if (micBtn) micBtn.addEventListener('click', aufnahmeStarten);

        document.addEventListener('keydown', tastaturBehandeln);

        const buehne = el('erzaehl-bild-rahmen');
        if (buehne) {
            buehne.addEventListener('touchstart', wischStart, { passive: true });
            buehne.addEventListener('touchend', wischEnde, { passive: true });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
