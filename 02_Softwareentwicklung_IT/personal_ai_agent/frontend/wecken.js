/**
 * Weck-Overlay: der große Sprachknopf fürs Handy (30.09.2026)
 * ============================================================
 * Auftrag (Sebastian): „Am Handy mit einem großen Knopf sprechen – ohne
 * Fremdanbieter für die Spracherkennung.“ Dieser Knopf löst die BESTEHENDE
 * Sprachaufnahme aus; es entsteht KEIN zweiter Audio-Weg.
 *
 * Wie das Overlay mit dem Bestand arbeitet:
 *   - Es baut unten rechts einen schwebenden, runden Knopf (72 px) samt
 *     großer Zustandsanzeige auf.
 *   - Ein Tipp tippt programmatisch auf den vorhandenen Mikrofon-Knopf
 *     `#mic-btn` (index.html:122; Verdrahtung app.js:7059). Genau dieser
 *     Klick startet die vorhandene Aufnahme (app.js:6785: getUserMedia ->
 *     AudioWorklet pcm-recorder.js -> WAV -> POST /api/sprache/transkript,
 *     app.js:6610) und beendet sie beim nächsten Klick (app.js:6845) –
 *     app.js unterscheidet selbst anhand von `state.isRecording`.
 *   - Der angezeigte Zustand („bereit“ / „hört zu“ / „denkt nach“ /
 *     „spricht“) wird NICHT erfunden: Er wird live aus dem Text der
 *     bestehenden Zustandszeile `#mic-status` gelesen, die app.js über
 *     setMicStatus() pflegt (app.js:1152–1174). Ein MutationObserver zieht
 *     die Anzeige nach, sobald der Text sich ändert.
 *
 * Datenschutz (Begründung):
 *   - Diese Datei enthält WEDER getUserMedia NOCH MediaRecorder NOCH
 *     AudioWorklet NOCH fetch – sie drückt nur den vorhandenen Knopf. Das
 *     Mikrofon öffnet sich daher weiterhin ausschließlich durch einen
 *     ausdrücklichen Klick auf die bestehende Aufnahme; kein Dauer-Mithören.
 *   - Keine externen Quellen (kein CDN, kein Fremdanbieter), kein neues Netz.
 *
 * Bewusste Entscheidungen:
 *   - Eigene Datei nach dem Muster von erzaehlen.js; app.js (9431 Zeilen,
 *     Quiz-/Sprach-Logik) wird NICHT umgebaut.
 *   - KEINE Brücke nötig: `element.click()` auf #mic-btn ist der bestehende
 *     öffentliche Weg – kein window.-Handle, keine app.js-Änderung.
 *   - Aussehen inline (style-Attribute), damit keine zweite Bestandsdatei
 *     (style.css) geändert werden muss. Dasselbe Muster benutzt app.js beim
 *     Feld-Diktat (btn.style.background = '#c33').
 *   - Doppel-Tipp-Schutz: app.js setzt `state.isRecording` erst NACH dem
 *     asynchronen getUserMedia um, und der MutationObserver läuft als
 *     Mikrotask. Ohne Sperre könnte ein zweiter schneller Tipp eine ZWEITE
 *     Aufnahme starten; die beiden Sperren unten sind begründet.
 *
 * Aufbau wie erzaehlen.js: oben REINE Funktionen (ohne DOM – von
 * frontend/tests/test_wecken.js wörtlich ausgeschnitten und geprüft), unten
 * die Verdrahtung in einer sofort ausgeführten Funktion.
 */

// =========================================================================
// Reine Funktionen (ohne DOM)
// =========================================================================

/** Phase des Overlays aus dem Text von #mic-status ableiten.
 *  Quelle sind ausschließlich die Texte, die app.js setzt (MIC_STATUS,
 *  app.js:1143):
 *    ''               -> 'bereit'      (app.js zeigt nichts an)
 *    'Mikrofon offen' -> 'hoert_zu'    (app.js:1145, Zugriff steht)
 *    'hört zu'        -> 'hoert_zu'    (app.js:1146, erste Blöcke treffen ein)
 *    'denkt nach'     -> 'denkt_nach'  (app.js:1147/1148, Erkennung/Glättung)
 *    'spricht'        -> 'spricht'     (app.js:1149, Browser-Stimme liest)
 *  „Mikrofon offen“ und „hört zu“ beschreiben beide die LAUFENDE Aufnahme;
 *  das Overlay zeigt dafür „hört zu“. Es wird also nur übersetzt, nichts
 *  erfunden. Unbekannte/fehlende Texte fallen ehrlich auf 'bereit' zurück –
 *  mehr kann diese Anzeige ohne eigene Zustandsquelle nicht wissen. */
function weckenPhase(statusText) {
    const text = typeof statusText === 'string' ? statusText.trim() : '';
    if (text === 'Mikrofon offen' || text === 'hört zu') return 'hoert_zu';
    if (text === 'denkt nach') return 'denkt_nach';
    if (text === 'spricht') return 'spricht';
    return 'bereit';
}

/** Groß angezeigter Text je Phase – genau die vier Zustände. */
function weckenPhasentext(phase) {
    if (phase === 'hoert_zu') return 'hört zu';
    if (phase === 'denkt_nach') return 'denkt nach';
    if (phase === 'spricht') return 'spricht';
    return 'bereit';
}

/** Was soll ein Tipp auf das Overlay in dieser Phase auslösen?
 *  'starten' = Aufnahme starten, 'stoppen' = laufende Aufnahme beenden,
 *  '' = nichts. Während „denkt nach“ (Erkennung läuft) und „spricht“
 *  (Antwort wird vorgelesen) bewusst nicht dazwischenfunken: Ein Start
 *  würde nur eine zweite Aufnahme neben der laufenden Erkennung öffnen. */
function weckenAktion(phase) {
    if (phase === 'bereit') return 'starten';
    if (phase === 'hoert_zu') return 'stoppen';
    return '';
}

// =========================================================================
// Verdrahtung (DOM). Läuft nur im Browser – die Node-Tests führen diese
// Datei mit einer DOM-Attrappe aus (frontend/tests/test_wecken.js).
// =========================================================================
(function () {
    // Ohne DOM (Node) oder ohne Beobachter (uralte Browser) gibt es nichts
    // zu bauen – dann bleibt alles beim Bestand.
    if (typeof document === 'undefined') return;
    if (typeof MutationObserver === 'undefined') return;

    const mikKnopf = document.getElementById('mic-btn');
    const mikZeile = document.getElementById('mic-status');
    // Fehlt der BESTEHENDE Mikrofon-Knopf oder seine Zustandszeile, wird gar
    // nichts gebaut. Absicht: keinen Ersatz-Weg anlegen, wenn die Quelle
    // fehlt – es bleibt allein bei der vorhandenen Aufnahme.
    if (!mikKnopf || !mikZeile) return;

    const GROESSE_PX = 72;   // Vorgabe mindestens 64 px; 72 ist am Handy gut treffbar

    const overlay = document.createElement('div');
    overlay.id = 'wecken-overlay';
    overlay.style.cssText = 'position:fixed;right:14px;'
        // Falls ein älterer Browser env() nicht kennt, gilt die erste Zeile.
        + 'bottom:124px;bottom:calc(124px + env(safe-area-inset-bottom, 0px));'
        + 'z-index:210;display:flex;flex-direction:column;align-items:center;gap:6px;'
        + 'touch-action:manipulation';

    const anzeige = document.createElement('div');
    anzeige.id = 'wecken-status';
    anzeige.textContent = 'bereit';
    anzeige.setAttribute('role', 'status');
    anzeige.setAttribute('aria-live', 'polite');
    anzeige.style.cssText = 'font-size:1.05rem;font-weight:600;color:#d0d0e0;'
        + 'background:rgba(15,15,26,0.92);border:1px solid #3a3a4a;border-radius:999px;'
        + 'padding:2px 12px;white-space:nowrap;pointer-events:none';

    const knopf = document.createElement('button');
    knopf.id = 'wecken-btn';
    knopf.type = 'button';
    knopf.textContent = '🎤';
    knopf.style.cssText = 'width:' + GROESSE_PX + 'px;height:' + GROESSE_PX + 'px;'
        + 'border-radius:50%;border:2px solid #4a4a5a;background:#1d1d2b;color:#e8e8f0;'
        + 'font-size:30px;line-height:1;padding:0;cursor:pointer;'
        + 'display:flex;align-items:center;justify-content:center;'
        + 'box-shadow:0 6px 18px rgba(0,0,0,0.45);touch-action:manipulation';

    overlay.appendChild(anzeige);
    overlay.appendChild(knopf);
    document.body.appendChild(overlay);

    // Farben je Phase (nur Anzeige, keine Zustandsquelle): ruhig = bereit,
    // rot = Aufnahme läuft, bernstein = Erkennung, violett = Stimme.
    const FARBEN = {
        bereit:     { rand: '#4a4a5a', grund: '#1d1d2b', schrift: '#d0d0e0' },
        hoert_zu:   { rand: '#cc4444', grund: '#2a1212', schrift: '#ff8a8a' },
        denkt_nach: { rand: '#cc7700', grund: '#2a1f0d', schrift: '#ffc266' },
        spricht:    { rand: '#aa66ff', grund: '#201733', schrift: '#c9a0ff' },
    };

    let angezeigtePhase = null;

    /** IMMER live aus dem bestehenden #mic-status-Text lesen – nie aus einer
     *  eigenen Zustandsvariablen schätzen. app.js setzt den Text synchron
     *  (setMicStatus, app.js:1172); der Beobachter zieht nur die Anzeige nach. */
    function phaseJetzt() {
        return weckenPhase(mikZeile.textContent);
    }

    function anzeigeNachziehen() {
        const phase = phaseJetzt();
        if (phase === angezeigtePhase) return;
        angezeigtePhase = phase;
        const farbe = FARBEN[phase] || FARBEN.bereit;
        anzeige.textContent = weckenPhasentext(phase);
        knopf.style.borderColor = farbe.rand;
        knopf.style.background = farbe.grund;
        knopf.style.color = farbe.schrift;
        overlay.setAttribute('data-phase', phase);
        const hinweis = phase === 'bereit' ? 'Sprachaufnahme starten'
            : phase === 'hoert_zu' ? 'Aufnahme stoppen'
            : 'läuft schon – abwarten';
        knopf.setAttribute('aria-label', anzeige.textContent + ' – ' + hinweis);
        knopf.title = anzeige.textContent + ' – ' + hinweis;
    }

    const beobachter = new MutationObserver(anzeigeNachziehen);
    beobachter.observe(mikZeile, {
        childList: true,
        characterData: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['hidden'],
    });
    anzeigeNachziehen();   // Startbild: „bereit“ (app.js zeigt beim Laden nichts an)

    // Doppel-Tipp-Schutz (Begründung im Kopfkommentar):
    const TIPP_SPERRE_MS = 700;    // zwischen zwei ausgelösten Tipps
    const START_FRIST_MS = 3000;   // „Start ist unterwegs, Zustand noch nicht sichtbar“
    let letzteAusloesung = 0;
    let startAusgeloestAm = 0;

    knopf.addEventListener('click', () => {
        const jetzt = Date.now();
        const phase = phaseJetzt();   // live lesen statt der Anzeige vertrauen

        // Ein bereits ausgelöster Start ist noch nicht sichtbar (app.js stellt
        // `state.isRecording` erst nach dem asynchronen getUserMedia um):
        // nicht doppelt starten.
        if (phase === 'bereit' && startAusgeloestAm
                && jetzt - startAusgeloestAm < START_FRIST_MS) {
            return;
        }
        // Unmittelbar nach einer Auslösung: app.js hat den neuen Text zwar
        // synchron gesetzt, aber ein zweiter Tipp (z. B. Stopp -> sofort
        // Start) würde eine zweite Aufnahme öffnen. Kurz sperren.
        if (jetzt - letzteAusloesung < TIPP_SPERRE_MS) return;

        const aktion = weckenAktion(phase);
        if (aktion === '') return;    // denkt nach / spricht: abwarten
        if (aktion === 'starten') startAusgeloestAm = jetzt;
        letzteAusloesung = jetzt;
        // Der BESTEHENDE Weg: ein Klick auf den vorhandenen Mikrofon-Knopf.
        // app.js entscheidet selbst, ob das startet oder stoppt (app.js:7059).
        mikKnopf.click();
    });
})();
