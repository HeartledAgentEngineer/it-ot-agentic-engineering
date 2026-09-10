/**
 * Personal AI Agent – Frontend Application
 * 
 * Features:
 * - Chat-UI mit Nachrichtenverlauf
 * - Verbindung zum FastAPI-Backend
 * - TTS (Text-to-Speech) via SpeechSynthesis API
 * - Auto-Resize der Texteingabe
 * - Markdown-Unterstützung für Antworten
 * - Spracheingabe via AudioWorklet (WAV) + OpenRouter (wie TypeFREE)
 */

/**
 * BACKEND-ADRESSE
 * ----------------
 * Standardmäßig dieselbe Adresse, von der die Seite geladen wurde. Das
 * Backend liefert das Frontend selbst aus, also stimmt das immer – egal ob
 * man am Handy über localhost draufgeht oder vom PC über die Heimnetz-IP.
 *
 * Vorher stand hier fest 'http://localhost:8080'. Vom PC aus zeigte das auf
 * den PC selbst, wo kein Server läuft – die App meldete "Offline".
 *
 * Abweichender Server nur zum Ausprobieren:
 *   localStorage.setItem('api_base', 'http://192.168.178.118:8080')
 *
 * Sicherheit: Der API-Key liegt NUR auf dem Handy in .env,
 *             nie im Frontend-Code.
 */
const API_BASE = localStorage.getItem('api_base')
    || (location.origin.startsWith('http') ? location.origin : 'http://localhost:8080');

/** API-Key, den das Backend serverseitig in die index.html injiziert hat.
 *  Ohne gesetzten Key (__API_KEY__ leer) bleibt der Schutz deaktiviert. */
const API_KEY = (typeof window !== 'undefined' && window.__API_KEY__)
    ? window.__API_KEY__
    : '';

/**
 * Zentrale fetch-Kapselung: hängt den X-API-Key an alle Anfragen an unser
 * eigenes Backend (/api/*) an, damit der Server den Key verlangen darf.
 * Andere URLs (z.B. externe) bleiben unangetastet.
 *
 * Statt alle ~25 fetch-Aufrufe umzuschreiben, wird der GLOBAL window.fetch
 * einmal gepatcht — so sind auch künftige Aufrufe automatisch abgedeckt.
 */
(function () {
    if (!API_KEY) return;              // kein Key konfiguriert -> nichts patchen
    const originalFetch = window.fetch;
    window.fetch = (url, options = {}) => {
        const u = String(url);
        const istApi = u.startsWith(`${API_BASE}/api/`) || u.startsWith('/api/');
        if (istApi) {
            const headers = new Headers(options.headers || {});
            if (!headers.has('X-API-Key')) headers.set('X-API-Key', API_KEY);
            options = { ...options, headers };
        }
        return originalFetch(url, options);
    };
})();

// =========================================
// Websuche – drei Zustände
// =========================================
const WEB_MODI = ['off', 'manual', 'auto'];

const WEB_TEXTE = {
    off: {
        label: 'Web',
        titel: 'Websuche aus – antippen für „bei jeder Nachricht"',
    },
    manual: {
        label: 'Web an',
        titel: 'Sucht bei JEDER Nachricht – rund 0,8 Cent pro Stück, auch bei „danke"',
    },
    auto: {
        label: 'Web auto',
        titel: 'Das Modell entscheidet selbst, ob es sucht – kostet nur bei echter Suche',
    },
};

/** Gespeicherten Modus lesen. Übersetzt die frühere Ja/Nein-Speicherung mit. */
function ladeWebModus() {
    const gespeichert = localStorage.getItem('web_search');
    if (gespeichert === '1') return 'manual';   // alte Fassung: eingeschaltet
    if (WEB_MODI.includes(gespeichert)) return gespeichert;
    return 'off';
}

// =========================================
// State
// =========================================
const state = {
    // Merkt sich, welches Gespräch zuletzt lief. Ohne das stünde die
    // Oberfläche nach jedem Neuladen vor einem leeren Fenster, obwohl der
    // Server den Verlauf noch hat.
    conversationId: localStorage.getItem('conversation_id') || null,
    isOnline: false,
    messages: [],
    isRecording: false,
    isTranscribing: false,
    // Websuche kostet je Anfrage extra – Wunsch bleibt zwischen Sitzungen erhalten.
    webSearch: ladeWebModus(),
    // Gewähltes Modell. null = das aus der Server-Konfiguration.
    model: localStorage.getItem('model') || null,
    // Katalog, wie ihn /api/models liefert. Wird beim ersten Öffnen geholt.
    katalog: null,
    favoriten: [],
    modellHinweis: '',
    // Aktive Filter-Chips im Auswahl-Blatt, kombinierbar (UND-Verknüpfung).
    filters: new Set(),
    // Kennt das Backend die Anbieter-Whitelist des Kontos? Ohne sie beziehen
    // sich alle Anbieterzahlen auf den Weltmarkt, nicht auf die eigene Lage.
    whitelistAktiv: false,
    // Datenschutz-Riegel: schickt provider.data_collection="deny" mit.
    //
    // Fest auf an, und der Schalter ist aus der Leiste genommen. Der frühere
    // Wert aus dem Speicher wird bewusst ignoriert: Ausgeblendet UND
    // abschaltbar wäre die gefährliche Kombination – man hielte sich für
    // geschützt, weil man den Schalter nicht mehr sieht.
    noRetention: true,
    // Der AbortController der laufenden Antwort, sonst null. Dient zugleich
    // als Antwort auf die Frage "schreibt der Agent gerade?" – die
    // Denke-nach-Anzeige taugt dafuer nicht, die verschwindet schon beim
    // ersten Textstueck.
    abbruch: null,
    // Nachrichten, die waehrend einer laufenden Antwort abgeschickt wurden.
    // Eintraege: { text, element } – element ist die graue Wartet-Blase.
    warteschlange: [],
    // Vom Nutzer ausgewählte, aber noch nicht abgeschickte Dateien
    // Eintraege: { id, filename, type, url, mime, data_url, text, file }
    pendingFiles: [],
};

// =========================================
// DOM References
// =========================================
const dom = {
    messages: document.getElementById('messages'),
    loading: document.getElementById('loading'),
    input: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    micBtn: document.getElementById('mic-btn'),
    newChatBtn: document.getElementById('new-chat-btn'),
    chatsBtn: document.getElementById('chats-btn'),
    chatSheet: document.getElementById('chat-sheet'),
    chatsClose: document.getElementById('chats-close'),
    chatList: document.getElementById('chat-list'),
    chatHint: document.getElementById('chat-hint'),
    webBtn: document.getElementById('web-btn'),
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.querySelector('.status-text'),
    modelBtn: document.getElementById('model-btn'),
    modelLabel: document.getElementById('model-label'),
    modelSheet: document.getElementById('model-sheet'),
    modelClose: document.getElementById('model-close'),
    modelSearch: document.getElementById('model-search'),
    modelList: document.getElementById('model-list'),
    modelHint: document.getElementById('model-hint'),
    modelFilters: document.getElementById('model-filters'),
    privacyBtn: document.getElementById('privacy-btn'),
    privacyLabel: document.getElementById('privacy-label'),
    loopBtn: document.getElementById('loop-btn'),
    loopLabel: document.getElementById('loop-label'),
    streamSettingsBtn: document.getElementById('stream-settings-btn'),
    streamMenu: document.getElementById('stream-menu'),
    codechatBtn: document.getElementById('codechat-btn'),
    // Datei-Upload
    uploadBtn: document.getElementById('upload-btn'),
    fileInput: document.getElementById('file-input'),
    filePreview: document.getElementById('file-preview'),
    filePreviewList: document.getElementById('file-preview-list'),
};
// JEDES im Chat sichtbare Foto per Klick maximierbar (Vollbild) machen — auch
// hochgeladene/gezeigte Bilder in Nachrichten, nicht nur Quiz (Wunsch Sebastian
// 2026-09-10). Global über den #messages-Container: jeder Klick auf ein <img>
// (ohne Button/Öffn-Child) öffnet das Vollbild. Quiz-Bilder liefern dabei ihre
// Gesicht-Kästen (dataset.quizKarte), alle anderen nur das Bild.
if (dom.messages) {
    dom.messages.addEventListener('click', (ev) => {
        // nur direkte Klicks auf ein Bild (nicht auf Buttons darin)
        const t = ev.target;
        if (!t || t.tagName !== 'IMG') return;
        if (ev.button !== undefined && ev.button !== 0) return; // nur linke Taste
        // Quiz-Bilder haben ihren eigenen Antipper (macheBildAntippbar) mit
        // Gesicht-Kästen — den NICHT unterdrücken: nur öffnen, wenn kein
        // .quiz-marke-Umbruch/eigener Handler das Bild bereits behandelt.
        // Erkennung: Bild liegt in einer Quiz-Karte (dataset.quizKarte) -> lassen.
        let inQuizKarte = false;
        try {
            let node = t.parentElement;
            while (node && node !== document.body) {
                if (node.dataset && node.dataset.quizKarte === '1') { inQuizKarte = true; break; }
                node = node.parentElement;
            }
        } catch (_e) {}
        if (inQuizKarte) return;   // Quiz-Handler (mit Kästen) übernimmt
        ev.preventDefault();
        ev.stopPropagation();
        // Alle anderen Chat-Bilder: nur Vollbild (kein Gesicht-Editor).
        zeigeBildVollbild(t, []);
    }, true); // capture, damit es vor inneren Handlern greift
}
// Coding-/Hermes-Chat-Umschalter (conv_code <-> conv_main).
if (dom.codechatBtn) {
    dom.codechatBtn.addEventListener('click', () => {
        const ziel = (state.conversationId === 'conv_code') ? 'conv_main' : 'conv_code';
        chatWechseln(ziel);
    });
}

// =========================================
// Utility: Simple Markdown Parser
// =========================================
/** Zeichenweise Auszeichnung – auch innerhalb von Tabellenzellen gebraucht.
 *  Links (Markdown-Links + rohe URLs) werden klickbar gemacht: http/https/www →
 *  <a target="_blank" rel="noopener noreferrer">. */
function inlineMarkdown(text) {
    let t = text;
    // 1) Markdown-Links [text](url) → parken (Platzhalter), damit der Roh-URL-
    //    Schritt sie nicht doppelt auseinanderreißt.
    const geparkt = [];
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (m, text_, url) => {
        geparkt.push(`<a href="${url}" target="_blank" rel="noopener noreferrer">${text_}</a>`);
        return `\u0000L${geparkt.length - 1}\u0000`;
    });
    // 2) Roh-URLs (https://…, http://…, www.…) → klickbar (außer die geparkten).
    t = t.replace(/(^|[^"\u0000])(https?:\/\/[^\s<"'\u0000]+|www\.[^\s<"'\u0000]+)/g, (_m, davor, url) => {
        const href = url.startsWith('www.') ? 'https://' + url : url;
        return `${davor}<a href="${href}" target="_blank" rel="noopener noreferrer">${url}</a>`;
    });
    // 3) Geparkte Markdown-Links wieder einsetzen.
    t = t.replace(/\u0000L(\d+)\u0000/g, (_, i) => geparkt[parseInt(i, 10)] || '');
    return t
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>');
}

/** Eine Markdown-Tabelle in HTML umsetzen. */
function tabelleZuHtml(kopfZeile, koerper) {
    const zellen = (zeile) =>
        zeile.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(z => inlineMarkdown(z.trim()));

    const kopf = zellen(kopfZeile);
    const zeilen = koerper.trim().split('\n').filter(z => z.trim());

    let html = '<div class="table-wrap"><table><thead><tr>';
    kopf.forEach(z => { html += `<th>${z}</th>`; });
    html += '</tr></thead><tbody>';
    zeilen.forEach(zeile => {
        html += '<tr>';
        zellen(zeile).forEach(z => { html += `<td>${z}</td>`; });
        html += '</tr>';
    });
    return html + '</tbody></table></div>';
}

function parseMarkdown(text) {
    // Fertige Blöcke werden geparkt und erst ganz am Ende wieder eingesetzt.
    // Sonst zerlegt die Absatz- und Zeilenumbruch-Behandlung weiter unten
    // ihr Innenleben – aus Tabellenzeilen würden <br> mitten im <table>.
    const geparkt = [];
    const parke = (html) => `\u0000${geparkt.push(html) - 1}\u0000`;

    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
        parke(`<pre><code>${escapeHtml(code.trim())}</code></pre>`));

    // Tabelle: Kopfzeile, Trennzeile aus Strichen, dann beliebig viele Zeilen.
    text = text.replace(
        /^[ \t]*\|(.+)\|[ \t]*\r?\n[ \t]*\|[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)*\|[ \t]*\r?\n((?:[ \t]*\|.*\|[ \t]*\r?\n?)*)/gm,
        (_, kopf, koerper) => parke(tabelleZuHtml(kopf, koerper)));

    text = inlineMarkdown(text);
    text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    text = text.replace(/\n\n/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');

    let html = `<p>${text}</p>`;
    // Blockelemente gehören nicht in einen Absatz – <table> in <p> ist
    // ungültig und der Browser würde den Absatz vorzeitig schließen.
    html = html.replace(/<p>\s*(\u0000\d+\u0000)\s*<\/p>/g, '$1');
    html = html.replace(/<br>\s*(\u0000\d+\u0000)/g, '$1');
    html = html.replace(/(\u0000\d+\u0000)\s*<br>/g, '$1');
    return html.replace(/\u0000(\d+)\u0000/g, (_, i) => geparkt[i]);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Markdown für einen noch unfertigen Text.
 *
 * Ein angefangener Codeblock wird für die Anzeige provisorisch geschlossen –
 * sonst stünden die drei Backticks als roher Text da, bis das Gegenstück
 * eintrifft. Halbfertige Sternchen brauchen keine Behandlung: Sie finden
 * kein Gegenstück, bleiben sichtbar und formatieren sich von selbst,
 * sobald es ankommt.
 */
function parseMarkdownPartial(text) {
    const fences = (text.match(/```/g) || []).length;
    return parseMarkdown(fences % 2 === 1 ? text + '\n```' : text);
}

// =========================================
// UI Functions
// =========================================
/** Steht die Ansicht nah genug am unteren Rand? */
function isAtBottom(toleranz = 80) {
    const el = dom.messages.parentElement;
    return el.scrollHeight - el.scrollTop - el.clientHeight < toleranz;
}

/**
 * Nach unten scrollen.
 *
 * Ohne `force` nur dann, wenn der Nutzer ohnehin unten steht. Scrollt er
 * während einer laufenden Antwort nach oben, um etwas nachzulesen, bleibt
 * die Ansicht dort stehen, statt ihm ständig weggerissen zu werden.
 *
 * Wichtig: Der Zustand muss VOR dem Einfügen neuen Inhalts geprüft werden –
 * danach ist die Seite bereits gewachsen und man steht nie mehr "unten".
 */
function scrollToBottom(force = false) {
    if (!force && !isAtBottom()) return;
    const el = dom.messages.parentElement;
    el.scrollTop = el.scrollHeight;
}

/** Erkennt ein Options-/Auswahl-Menü in einer rohen Hermes-Ausgabe und liefert
 *  { frage, optionen:[{nummer,text}...] } oder null. Wandelt Layout-Pipes in
 *  Zeilen, extrahiert nummerierte Optionen ("1. …", "1) …", "❯ 1. …"). */
function parseOptionsMenue(roh) {
    if (!roh || typeof roh !== 'string') return null;
    const text = roh.replace(/\|/g, '\n');
    const zeilen = text.split('\n').map(z => z.trim()).filter(Boolean);
    const ersteOptIdx = zeilen.findIndex(z => /^[❯>\s]*\d+[.)]/.test(z));
    const frage = ersteOptIdx > 0
        ? zeilen.slice(0, ersteOptIdx).join(' ').replace(/[❯>]+/g, '').trim()
        : '';
    const optionen = [];
    for (const zeile of zeilen) {
        const m = zeile.match(/^[❯>\s]*(\d+)[.)]\s*(.+)$/);
        if (m) optionen.push({ nummer: parseInt(m[1], 10), text: m[2].trim() });
    }
    if (optionen.length < 2) return null;
    return { frage, optionen };
}

/** Baut klickbare Options-Buttons für ein erkanntes Auswahl-Menü. Klick sendet
 *  die gewählte Option als Nachricht an den Agenten (nicht den rohen String). */
function bauOptionsUi(menu) {
    const box = document.createElement('div');
    box.className = 'options-menu';
    box.style.cssText = 'display:flex;flex-direction:column;gap:6px;margin-top:4px';
    if (menu.frage) {
        const f = document.createElement('div');
        f.style.cssText = 'font-weight:600;margin-bottom:4px';
        f.textContent = menu.frage;
        box.appendChild(f);
    }
    menu.optionen.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'option-button';
        btn.textContent = `${opt.nummer}. ${opt.text}`;
        btn.style.cssText =
            'text-align:left;padding:8px 10px;border:1px solid #3a3a3a;border-radius:8px;' +
            'background:#1e1e1e;color:inherit;cursor:pointer;font-size:0.85rem';
        btn.addEventListener('click', () => {
            // Option als Antwort senden (geht an den laufenden Hermes-Auftrag
            // bzw. als normale Nachricht an den Agenten).
            sendMessage(opt.text);
        });
        box.appendChild(btn);
    });
    return box;
}

/**
 * A/B-Wahl bei erkannten Hermes-Aufgaben im normalen Chat(Wunsch Sebastian
 * 2026-09-07): Statt stiller Auto-Delegation wählen, ob die Aufgabe an
 *  den Coding-Chat(A) oder als eigener paralleler Hermes-Thread hier(B)
 *  geht. Wird nach finishReply wieder in die Blase eingehängt(die
 *  Markdown-Uebernahme würde die Buttons sonst wegloeschen).
 */
function bauWahlUi(contentDiv, aufgabe) {
    const zeile = document.createElement('div');
    zeile.className = 'wahl-zeile';
    zeile.style.cssText =
        'display:flex;flex-wrap:wrap;gap:8px;margin-top:8px';
    // A: An den Coding-Chat übergeben (conv_code delegiert immer direkt
    //    an Hermes; Hermes baut seinen Kontext dort selbst auf).
    const btnA = document.createElement('button');
    btnA.className = 'wahl-knopf';
    btnA.textContent = '⎇ An Coding-Chat übergeben';
    btnA.style.cssText =
        'flex:1;min-width:150px;padding:10px 12px;border:1px solid #4a7;' +
        'border-radius:10px;background:#1f3a2a;color:#8f8;cursor:pointer;' +
        'font-size:0.85rem;text-align:center';
    btnA.addEventListener('click', () => {
        btnA.disabled = true;
        btnA.textContent = '… wechsle zum Coding-Chat';
        if (typeof chatWechseln === 'function') chatWechseln('conv_code');
        setTimeout(() => {
            if (typeof sendMessage === 'function' && aufgabe) {
                const nurNachricht = (aufgabe.split('\n\n[Kontext')[0] || aufgabe).trim();
                sendMessage(nurNachricht);
            }
        }, 250);
    });

    // B: Als eigener paralleler Hermes-Thread hier starten(Daemon-Thread;
    //    man kann parallel weiterfragen und eingreifen,/eingabe-Kommentare).
    const btnB = document.createElement('button');
    btnB.className = 'wahl-knopf';
    btnB.textContent = '⚙  Hier parallel bearbeiten(Hermes-Thread)';
    btnB.style.cssText =
        'flex:1;min-width:170px;padding:10px 12px;border:1px solid #57a;' +
        'border-radius:10px;background:#1f2a3a;color:#9cf;cursor:pointer;' +
        'font-size:0.85rem;text-align:center';
    btnB.addEventListener('click', async () => {
        btnB.disabled = true;
        btnB.textContent = '… Hermes-Thread startet';
        try {
            const res = await fetch(`${API_BASE}/api/hermes/aktivieren`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ aufgabe, kontext: '' }),
            });
            const dat = await res.json().catch(() => ({}));
            if (res.ok && dat.auftrag_id) {
                _laufenderAuftragKurz = dat.auftrag_id;
                aktualisiereStatusAnzeige();
                addMessage(
                    '▶️ Hermes-Thread läuft im Hintergrund – parallel weiterfragen möglich. ' +
                    'Um einzugreifen, einfach eine Nachricht schreiben.'
                );
            } else {
                addMessage('⚠️ Hermes-Thread konnte nicht gestartet werden.');
            }
        } catch (_) {
            addMessage('⚠️ Hermes-Thread konnte nicht gestartet werden.');
        }
    });

    zeile.appendChild(btnA);
    zeile.appendChild(btnB);
    contentDiv.appendChild(zeile);
    scrollToBottom(true);
}

/** Baut einen Korrektur-Button für fälschlich erkannte Hermes-Aufgaben.
 *  Klick leitet die ursprüngliche Nutzer-Nachricht an den normalen LLM weiter
 *  (die alte Hermes-Meldung bleibt sichtbar, um den Fehler zu belegen). */
function baueKorrekturButton(fehlerFall) {
    const btn = document.createElement('button');
    btn.className = 'korrektur-button';
    btn.textContent = fehlerFall
        ? '↩️ An lokalen Agenten senden'
        : '⚠️ Keine Hermes-Aufgabe – an LLM weitergeben';
    btn.style.cssText =
        'margin-top:8px;padding:8px 10px;border:1px solid #555;border-radius:8px;' +
        'background:#2a2a2a;color:inherit;cursor:pointer;font-size:0.8rem';
    btn.addEventListener('click', async () => {
        // Ursprüngliche Nutzer-Nachricht = letzte 'user'-Nachricht im Verlauf.
        let frag = '';
        for (let i = state.messages.length - 1; i >= 0; i--) {
            if (state.messages[i].role === 'user') { frag = state.messages[i].content; break; }
        }
        if (!frag) return;
        btn.disabled = true;
        btn.textContent = '… Hermes wird beendet, Hermes antwortet';
        // 1) Laufenden Hermes-Auftrag abbrechen (tmux-Session + Buch-Status),
        //    damit nicht im Hintergrund weitergearbeitet wird.
        if (_laufenderAuftragKurz) {
            try {
                await fetch(`${API_BASE}/api/auftraege/${_laufenderAuftragKurz}/abbrechen`, { method: 'POST' });
            } catch (_) { /* Abbruch-Fehlschlag ist nicht kritisch */ }
            _laufenderAuftragKurz = null;
            aktualisiereStatusAnzeige();
        }
        // 2) Aufgabe an den normalen LLM weiterleiten (force_agent=true:
        //    NICHT durch den Hermes-Router — sonst erkennt er die Aufgabe
        //    wieder als Hermes-Aufgabe und es geht erneut an den PC (Loop).
        sendMessage(frag, false, false, true);
        btn.textContent = '… wird vom Agenten beantwortet';
    });
    // Umlenk-Buttons IMMER nebeneinander (Flex-Reihe) — auch wenn kein
    // Auftrag mehr "läuft" (der Agent-Button sendet die Frage einfach
    // neu an den normalen LLM; der Handy-Button nur bei laufendem Job).
    const zeile = document.createElement('div');
    zeile.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:6px';
    // Klare Labels (Nutzervorgabe): nebeneinander, Handy-Format ist breit.
    btn.textContent = '↩️ An Agent zurückgeben';
    btn.style.cssText =
        'flex:1;min-width:130px;padding:8px 10px;border:1px solid #555;' +
        'border-radius:8px;background:#2a2a2a;color:inherit;cursor:pointer;font-size:0.8rem;text-align:center';
    zeile.appendChild(btn);
    // "↪️ An lokalen Hermes übergeben" — IMMER sichtbar (nicht nur bei
    // laufendem Auftrag): sendet die Frage explizit an den Handy-Hermes
    // (ziel=handy → Backend startet Track C direkt, kein PC-Versuch).
    const btnHandy = document.createElement('button');
    btnHandy.className = 'korrektur-button';
    btnHandy.textContent = '↪️ An lokalen Hermes übergeben';
    btnHandy.style.cssText =
        'flex:1;min-width:130px;padding:8px 10px;border:1px solid #4a7;' +
        'border-radius:8px;background:#1f3a2a;color:#8f8;cursor:pointer;font-size:0.8rem;text-align:center';
    btnHandy.addEventListener('click', async () => {
        // Ursprüngliche Nutzer-Nachricht = letzte 'user'-Nachricht.
        let frag = '';
        for (let i = state.messages.length - 1; i >= 0; i--) {
            if (state.messages[i].role === 'user') { frag = state.messages[i].content; break; }
        }
        if (!frag) return;
        btnHandy.disabled = true;
        btnHandy.textContent = '… wird an lokalen Hermes übergeben';
        // Laufenden Auftrag abbrechen (falls vorhanden), dann lokal senden.
        if (_laufenderAuftragKurz) {
            try {
                await fetch(`${API_BASE}/api/auftraege/${_laufenderAuftragKurz}/abbrechen`, { method: 'POST' });
            } catch (_) {}
            _laufenderAuftragKurz = null;
            aktualisiereStatusAnzeige();
        }
        sendMessage(frag, false, false, false, 'handy');
    });
    zeile.appendChild(btnHandy);
    return zeile;
}

/** Ziel-Etiketten für die „Wohin wurde delegiert?"-Pille (Passend zu den
 *  ziel-Werten des Backends: pc / handy / buch). */
const ZIEL_LABELS = {
    pc: '→ Hermes (PC)',
    handy: '→ Hermes (Handy)',
    buch: '→ Hermes',
};

/** Kleine Ziel-Pille unter einer Delegations-Antwort: zeigt auf einen Blick,
 *  wohin die Hermes-Aufgabe weitergeleitet wurde. `ziel` kommt aus dem
 *  SSE-done-Event bzw. aus der ChatResponse (Fallback-Weg). */
function addZielChip(contentDiv, ziel) {
    if (!ziel || !ZIEL_LABELS[ziel]) return;
    // Ziel merken (pc/handy/buch) → Status-Badge zeigt "Hermes (PC/Handy)".
    _zielAktuell = ziel;
    // Automatische Delegation an Hermes (pc/handy) → Hermes-Button aktivieren
    // und den Zustand feuern (ohne die /aktivieren-API erneut zu starten):
    // Der nochmalige Klick auf "Hermes" schaltet danach wieder AUS.
    // Wunsch Sebastian: im Übergabefall steht der Button auf an.
    if ((ziel === 'pc' || ziel === 'handy') && typeof loopAktiv !== 'undefined' && !loopAktiv) {
        _setzeLoopZustand(true);
    }
    const chip = document.createElement('div');
    chip.className = 'ziel-chip';
    chip.textContent = ZIEL_LABELS[ziel];
    chip.style.cssText =
        'display:inline-block;margin-top:8px;padding:3px 10px;' +
        'border:1px solid #444;border-radius:999px;font-size:0.75rem;' +
        'color:#bbb;background:#222';
    contentDiv.appendChild(chip);
    aktualisiereStatusAnzeige();
}

/** Legt eine Nachrichtenblase an und gibt ihren Inhaltsbereich zurück,
 *  damit der Streaming-Weg sie nachträglich befüllen kann. */
function addMessage(content, role, zeit, bildPfad, opts) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    // Roh-Text der Blase fürs Kontextmenü (Kopieren/Bearbeiten): bei
    // User-Nachrichten exakt wie getippt, bei Assistant der Markdown-Rohtext.
    // Gestreamte Blasen haben hier zunächst '' — dort greift der Fallback
    // auf den sichtbaren Text (siehe kontextTextAusBlase).
    div.dataset.klarText = content;
    // Innere Spalte: Blaseninhalt über dem Zeitstempel-Label. Ohne sie lägen
    // Content und Uhrzeit im flex-row nebeneinander statt untereinander.
    // Klein, deshalb inline statt style.css (die Konvention bei Mini-Stilen).
    const inner = document.createElement('div');
    inner.style.cssText = 'display:flex;flex-direction:column';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (role === 'assistant') {
        // Ist die Antwort ein erkanntes Auswahl-Menü, render klickbare Buttons
        // statt des rohen Textes (Smart-Output). Sonst normale Markdown-Blase.
        const options = parseOptionsMenue(content);
        if (options) {
            contentDiv.appendChild(bauOptionsUi(options));
        } else {
            contentDiv.innerHTML = parseMarkdown(content);
        }
        // Falsch erkannte Hermes-Aufgabe korrigierbar machen: Zeigt die
        // Meldung "Hermes-Aufgabe erkannt"/"Coding-Auftrag erkannt", gibt es
        // einen Button, der die Aufgabe stattdessen an den normalen LLM
        // weiterleitet (kein Umbau der alten Meldung — sie bleibt als Beleg).
        // NUR bei LIVE-Nachrichten (zeit === undefined): beim Laden der
        // History (zeit gesetzt) erscheint der Button nicht — sonst sähe es
        // nach F5 so aus, als liefe gerade ein Auftrag (Button auf alten
        // Blasen), obwohl nichts mehr läuft.
        if ((zeit === undefined
            && (/Hermes-Aufgabe erkannt|Coding-Auftrag erkannt/.test(content)
                || /Fehler im lokalen Hermes-Job|Abbruch-Fehlschlag|⚠️ Fehler/.test(content)
                || /wurde an den PC-Hermes übergeben/.test(content)
                || /arbeitet länger als das Timeout/.test(content)
                || /arbeitet gerade an der Aufgabe/.test(content)))
            // "Übergeben"-Blasen im VERLAUF: Button auch nach Reload zeigen,
            // wenn wirklich noch ein Auftrag läuft (der PC könnte arbeiten;
            // man will umlenken können).
            || (/wurde an den PC-Hermes übergeben/.test(content)
                && _laufenderAuftragKurz)) {
            contentDiv.appendChild(baueKorrekturButton(
                /Fehler im lokalen Hermes-Job|Abbruch-Fehlschlag/.test(content)
            ));
                }
    } else {
        contentDiv.innerHTML = `<p>${escapeHtml(content)}</p>`;
    }
    inner.appendChild(contentDiv);
    // WhatsApp-artige Datumstrennung: Immer wenn sich der Kalendertag ändert,
    // kommt vor der Blase eine dezente zentrierte Pille (Heute/Gestern/Datum).
    // Live versendete Blasen (zeit === undefined) hängen am aktuellen Tag.
    const bannerIso = (zeit === undefined) ? new Date().toISOString() : (zeit || null);
    if (bannerIso) {
        const tagKey = datumSchluessel(bannerIso);
        if (tagKey !== _letzteBannerDatum) {
            dom.messages.appendChild(baueDatumBanner(bannerIso));
            _letzteBannerDatum = tagKey;
        }
    }
    // Zeitstempel unter dem Text, dezent, NUR die Uhrzeit mit Sekunden – das
    // Datum steht in der Pille darüber. Sekunden sind wichtig, wenn Hermes
    // viele Nachrichten kurz hintereinander schickt. „undefined" (live
    // versendet) → jetzt; ein explizit leeres (null/'') lässt die Blase ohne
    // Label – für alte Verlaufs-Nachrichten ohne bekannte Uhrzeit.
    const label = (zeit === undefined)
        ? formatUhrzeit(new Date().toISOString())
        : (zeit ? formatUhrzeit(zeit) : null);
    if (label) {
        const zeitDiv = document.createElement('div');
        zeitDiv.style.cssText = 'font-size:0.7rem;color:#9a9a9a;text-align:right;margin-top:4px;padding:0 4px';
        zeitDiv.textContent = label;
        inner.appendChild(zeitDiv);
    }
    // WhatsApp-artiger '↩ Antworten'-Knopf: erlaubt, auf genau diese
    // Nachricht (Text ODER Bild) konkret zu antworten. Nur bei realem Inhalt.
    const zitatText = (content || '').trim();
    if (zitatText) {
        const antBtn = document.createElement('button');
        antBtn.type = 'button';
        antBtn.textContent = '↩ Antworten';
        antBtn.title = 'Auf diese Nachricht antworten (Zitat-Kontext)';
        antBtn.style.cssText =
            'background:none;border:none;color:#7aaa;font-size:0.7rem;cursor:pointer;' +
            'padding:2px 4px;text-align:right;align-self:flex-end;border-radius:6px;opacity:0.75';
        antBtn.addEventListener('mouseenter', () => { antBtn.style.color = '#8cf'; antBtn.style.opacity = '1'; });
        antBtn.addEventListener('mouseleave', () => { antBtn.style.color = '#7aaa'; antBtn.style.opacity = '0.75'; });
        antBtn.addEventListener('click', () => {
            const zeitRef = (zeit === undefined) ? new Date().toISOString() : (zeit || '');
            setzeAntwortAuf(role, zitatText, zeitRef, bildPfad);
        });
        inner.appendChild(antBtn);
    }
    div.appendChild(inner);
    // Vorlese-Knopf auch fuer fertige/geladene Assistant-Nachrichten (History-
    // Replay, Hermes-Replies etc.): Nur bei vorhandenem Text. Der Live-Stream
    // steigt UEBER eine leere Blase ein (content===''), deren Vorleser separat
    // in der Stream-Logik an den Text gekoppelt wird (kein Doppel-Button).
    if (role === 'assistant' && content) {
        addSpeakControls(div, () => content, () => true);
    }
    dom.messages.appendChild(div);
    // Stiller Modus (opts.silent): kein Auto-Scroll, kein state.messages-Push
    // — für den schnellen Chat-Wechsel, bei dem der Verlauf in einem Rutsch
    // (Fragment) gebaut und danach einmal nach unten gescrollt wird. Beim
    // normalen Streaming (Standard) bleibt das alte Verhalten erhalten.
    if (!opts || !opts.silent) {
        scrollToBottom(true);   // eigene Aktion – hier wird immer nachgezogen
        state.messages.push({ role, content });
    }
    return contentDiv;
}

/** Wem schreibt der Nutzer gerade? — sichtbares Badge im Header.
 *  - Hermes läuft (_laufenderAuftragKurz) → 🔴 Hermes (direkt)
 *  - normale Antwort/Stream läuft → 🟡 Agent (antwortet)
 *  - sonst → 🟢 Agent (LLM + Gedächtnis)
 *  Wird bei jedem relevanten Zustandswechsel aufgerufen. */
function setzeTutZeile(text) {
    // Seit 2026-09-06 (Auftrag Sebastian): Der Arbeitsschritt-Text (z. B.
    // "🔍 Agent liest deine Nachricht…" / "⚙️ Hermes bearbeitet deine Aufgabe…")
    // wandert in die untere animierte "Denke nach…"-Bubble (#loading) statt
    // unscheinbar oben im Header zu stehen. Die alte Header-Zeile
    // (#agent-tut-zeile) wird ausgeblendet, damit nichts doppelt erscheint.
    const el = document.getElementById('agent-tut-zeile');
    if (el) { el.style.display = 'none'; el.textContent = ''; }
    const bubbleText = document.querySelector('#loading .loading-text');
    if (bubbleText) bubbleText.textContent = text ? text : 'Denke nach...';
}

function aktualisiereStatusAnzeige() {
    const badge = document.getElementById('chat-modus-badge');
    if (!badge) return;
    if (_laufenderAuftragKurz) {
        // Konkret zeigen, WER arbeitet (PC-Hermes vs. Handy-Hermes).
        const ziel = _zielAktuell || '';
        badge.textContent = ziel === 'pc'
            ? '🔴 Hermes (PC) arbeitet'
            : ziel === 'handy'
                ? '🔴 Hermes (Handy) arbeitet'
                : '🔴 Hermes arbeitet';
        badge.style.color = '#f88';
        badge.style.borderColor = '#f55';
        badge.style.background = '#2a1515';
    } else if (_hermesArbeitetAussen) {
        // Hermes-Auftrag laeuft, aber nicht ueber dieses Frontend gestartet
        // (z. B. aus Termux/der Session selbst). Header-Badge trotzdem rot.
        badge.textContent = '🔴 Hermes arbeitet';
        badge.style.color = '#f88';
        badge.style.borderColor = '#f55';
        badge.style.background = '#2a1515';
    } else if (typeof hermesStreamBereit !== 'undefined' && hermesStreamBereit) {
        // Stream von DIESER Hermes-Session ist bereit/laueft (Wunsch:
        // "Hermes denkt (Stream bereit)") - sichtbar, bevor/waerend Text
        // gestreamt wird.
        badge.textContent = '🔴 Hermes denkt (Stream bereit)';
        badge.style.color = '#fff';
        badge.style.borderColor = '#4a7';
        badge.style.background = '#1f3a2a';
    } else if (state.abbruch) {
        // Loop-Modus oder laufender Hermes-Auftrag -> "Hermes antwortet";
        // sonst normaler Chat -> "Agent antwortet". (Wunsch Sebastian:
        // bei loop aus wieder Agent, ausser automatisch an Hermes delegiert.)
        badge.textContent = (typeof loopAktiv !== 'undefined' && loopAktiv)
            ? '🟡 Hermes antwortet'
            : '🟡 Agent antwortet';
        badge.style.color = '#fc6';
        badge.style.borderColor = '#c90';
        badge.style.background = '#2a2215';
    } else {
        // Ruhezustand: kein dauerhaftes "🟢 Agent"-Badge nötig — der
        // Status ist nur bei Aktivität interessant (Hermes/Agent arbeitet).
        badge.textContent = '';
        badge.style.color = '';
        badge.style.borderColor = '';
        badge.style.background = '';
        badge.style.fontSize = '0';
        badge.style.padding = '0';
    }
}

/** Schaltet die animierte "Denke nach..."-Bubble unten im Chat (#loading).
 *  WhatsApp-"Tippt gerade"-Stil (Stand 2026-09-06, Auftrag Sebastian): Waehrend
 *  eine Antwort verarbeitet wird, erscheint am unteren Rand des Chats eine
 *  animierte Bubble (drei Punkte + Text), sobald das erste Textstueck da ist
 *  bzw. die Antwort fertig ist, verschwindet sie wieder. Gilt fuer Haupt- und
 *  Coding-/Hermes-Chat (conv_code) gleichermassen. */
function setLoading(loading) {
    // #loading ist das am Ende von chat-container liegende Element: sichtbar
    // machen beim Start, verstecken sobald etwas angekommen/fertig ist.
    if (dom.loading) {
        dom.loading.classList.toggle('hidden', !loading);
        if (loading) scrollToBottom(true);
    }
    // Die Eingabe bleibt absichtlich offen: Waehrend der Agent schreibt, soll
    // man schon die naechste Nachricht tippen und anhaengen koennen.
    updateSendButton();
    aktualisiereStatusAnzeige();
}

// =========================================
// Health-Check: Drei-Phasen-Logik
// =========================================
// Phase 1 (checkAndAutoClose) laeuft EINMAL beim Seitenstart:
//   Wenn der Server nach 5s nicht erreichbar ist, wird der Tab geschlossen.
//   Das verhindert leere Fenster, wenn der Server noch nicht da ist.
//
// Phase 2 (checkHealth) laeuft alle 30s per Intervall:
//   Zeigt Online/Offline an und laedt die Seite NICHT automatisch neu.
//   Frueher wurde bei Server-Rueckkehr window.location.reload() gerufen,
//   was bei schnellen Neustarts (--reload) eine Reload-Schleife ausloeste.
//
// Phase 3: Nach 5s ohne Server-Kontakt wird der Tab geschlossen.
//   Der Timer wird abgebrochen, sobald der Server wieder antwortet.

// Merkt sich, ob der Server gerade offline war. Sobald er nach einem
// Neustart wieder da ist, wird die UI aktualisiert, statt die Seite
// neu zu laden – das verhindert Reload-Schleifen und neue Tabs.
let serverWarOffline = false;
let neuladenInArbeit = false;

const SYMBOL_SENDEN = '<svg viewBox="0 0 24 24" width="24" height="24">'
    + '<path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

const SYMBOL_ABBRECHEN = '<svg viewBox="0 0 24 24" width="24" height="24">'
    + '<path fill="currentColor" d="M7 7h10v10H7z"/></svg>';

function setOnline(online) {
    state.isOnline = online;
    // Status-Punkt/-Text sind entfernt (Agent-Gesicht zeigt den Status).
    // Guards, damit der Health-Check nicht an null crasht.
    if (dom.statusIndicator) {
        dom.statusIndicator.className = `status ${online ? 'online' : 'offline'}`;
        dom.statusText.textContent = online ? 'Online' : 'Offline';
    }
    // Agent-Gesicht: lächelt/grün bei online, schläft/grau bei offline.
    const face = document.getElementById('agent-face');
    if (face) {
        face.textContent = online ? '🤖' : '😴';
        face.style.filter = online ? '' : 'grayscale(0.9)';
        face.title = online ? 'Agent ist online' : 'Agent ist offline';
    }
}

/**
 * Der Sende-Knopf hat drei Gesichter, je nach Lage:
 *
 *   Antwort laeuft, Eingabe leer   → Stopp: bricht die Antwort ab
 *   Antwort laeuft, Eingabe gefuellt → Senden: haengt an die Warteschlange an
 *   nichts laeuft                  → Senden: schickt sofort ab
 *
 * Ein eigener dritter Knopf waere auf dem Handy nur verlorene Daumenflaeche.
 */
function updateSendButton() {
    // Während der Aufnahme bleibt der Knopf bedienbar: Ein Druck darauf
    // beendet die Aufnahme und schickt das Diktat gleich ab.
    if (state.isRecording) {
        dom.sendBtn.disabled = false;
        return;
    }
    const hatText = !!dom.input.value.trim();
        // Stopp-Modus auch, wenn nur ein Hermes-Auftrag läuft (_laufenderAuftragKurz),
        // auch ohne aktiven Stream (state.abbruch) — sonst verschwindet der
        // Abbrechen-Knopf, während Hermes noch arbeitet.
        const stoppModus = (!!state.abbruch || !!_laufenderAuftragKurz) && !hatText;

    dom.sendBtn.innerHTML = stoppModus ? SYMBOL_ABBRECHEN : SYMBOL_SENDEN;
    dom.sendBtn.classList.toggle('stopping', stoppModus);
    dom.sendBtn.title = stoppModus
        ? 'Antwort abbrechen'
        : (state.abbruch ? 'Nachricht anhängen – wird danach gesendet' : 'Nachricht senden (Strg+Enter)');
    dom.sendBtn.disabled = !hatText && !stoppModus;
}

function setWebSearch(modus) {
    if (!WEB_MODI.includes(modus)) modus = 'off';
    state.webSearch = modus;
    localStorage.setItem('web_search', modus);

    const texte = WEB_TEXTE[modus];
    dom.webBtn.classList.toggle('active', modus !== 'off');
    dom.webBtn.classList.toggle('auto', modus === 'auto');
    dom.webBtn.setAttribute('aria-pressed', modus !== 'off' ? 'true' : 'false');
    dom.webBtn.title = texte.titel;

    const beschriftung = dom.webBtn.querySelector('span');
    if (beschriftung) beschriftung.textContent = texte.label;
}

/** Reihum: aus → bei jeder Nachricht → Modell entscheidet → aus */
function naechsterWebModus() {
    const i = WEB_MODI.indexOf(state.webSearch);
    return WEB_MODI[(i + 1) % WEB_MODI.length];
}

/** Hängt die Fundstellen unter eine Antwort. */
function addSources(contentDiv, quellen) {
    if (!quellen || !quellen.length) return;
    const box = document.createElement('div');
    box.className = 'sources';

    const titel = document.createElement('span');
    titel.className = 'sources-title';
    titel.textContent = quellen.length === 1 ? 'Quelle' : 'Quellen';
    box.appendChild(titel);

    quellen.forEach((q, i) => {
        const a = document.createElement('a');
        a.href = q.url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = `${i + 1}. ${q.title}`;
        box.appendChild(a);
    });
    contentDiv.appendChild(box);
}

/** Fundstellen zusammenführen, doppelte Adressen fliegen raus. */
function mergeQuellen(...listen) {
    const gesehen = new Set();
    const ergebnis = [];
    for (const liste of listen) {
        for (const q of liste || []) {
            if (q && q.url && !gesehen.has(q.url)) {
                gesehen.add(q.url);
                ergebnis.push(q);
            }
        }
    }
    return ergebnis;
}

function setMicStatus(status) {
    dom.micBtn.classList.remove('recording', 'transcribing', 'polishing');
    if (status) {
        dom.micBtn.classList.add(status);
    }
    const titles = {
        '': 'Spracheingabe',
        'recording': 'Aufnahme läuft ... (Klicken zum Stoppen)',
        'transcribing': 'Transkribiere ...',
        'polishing': 'Glätte Text ...',
    };
    dom.micBtn.title = titles[status] || 'Spracheingabe';
}

// =========================================
// Datei-Upload
// =========================================

/** Maximale Anzahl gleichzeitig ausgewählter Dateien */
const MAX_DATEIEN = 5;

/**
 * Büroklammer-Klick: Dateiauswahl öffnen.
 * Ist bereits die Maximalzahl erreicht, wird stattdessen der Nutzer
 * darauf hingewiesen – sonst stapeln sich die Dateien unsichtbar.
 */
dom.uploadBtn.addEventListener('click', () => {
    if (state.pendingFiles.length >= MAX_DATEIEN) {
        // Kurze Rückmeldung ohne Browser-Dialog. Der Hinweis verschwindet
        // nach dem nächsten Klick von selbst.
        const rest = dom.uploadBtn.querySelector('span');
        if (!rest) {
            const badge = document.createElement('span');
            badge.textContent = `Max ${MAX_DATEIEN}`;
            badge.style.cssText = 'position:absolute;top:-6px;right:-6px;font-size:0.6rem;background:var(--error);color:#fff;border-radius:8px;padding:0 5px;line-height:1.4';
            dom.uploadBtn.style.position = 'relative';
            dom.uploadBtn.appendChild(badge);
            setTimeout(() => badge.remove(), 2000);
        }
        return;
    }
    dom.fileInput.click();
});

/**
 * Datei(en) ausgewählt → hochladen zum Backend.
 */
dom.fileInput.addEventListener('change', async () => {
    const files = dom.fileInput.files;
    if (!files || files.length === 0) return;

    // Prüfen, wie viele noch hinzukommen dürfen
    const platz = MAX_DATEIEN - state.pendingFiles.length;
    const auswahl = Array.from(files).slice(0, platz);

    for (const file of auswahl) {
        // Validierung schon clientseitig
        const isImage = file.type.startsWith('image/');
        const isPdf = file.type === 'application/pdf';
        if (!isImage && !isPdf) {
            console.warn('Nicht unterstützter Dateityp:', file.type);
            continue;
        }
        if (file.size > 20 * 1024 * 1024) {
            console.warn('Datei zu groß (>20 MB):', file.name);
            continue;
        }

        // Hochladen
        try {
            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                console.warn('Upload fehlgeschlagen:', err.detail || res.status);
                continue;
            }

            const data = await res.json();

            // Für PDFs haben wir den extrahierten Text bereits
            state.pendingFiles.push({
                id: data.id,
                filename: data.filename,
                type: data.type,
                url: data.url,
                mime: data.mime,
                data_url: data.data_url,  // base64 image für Vision-API
                text: data.konvertiert,   // extrahierter PDF-Text
                file: file,               // Referenz für lokale Vorschau
            });

            _fuegeVorschauHinzu(data, file);
            // Bild angehängt, aber das Modell kann keine Vision?
            _warneFallsModellKeinBild();
        } catch (err) {
            console.warn('Netzwerkfehler beim Upload:', err);
        }
    }

    // Input zurücksetzen, damit dieselbe Datei erneut gewählt werden kann
    dom.fileInput.value = '';
    _aktualisiereUploadKnopf();
});

/**
 * Vorschau-Element für eine hochgeladene Datei hinzufügen.
 */
function _fuegeVorschauHinzu(data, file) {
    dom.filePreview.classList.remove('hidden');

    const item = document.createElement('div');
    item.className = 'file-preview-item';
    item.dataset.fileId = data.id;

    if (data.type === 'image') {
        const img = document.createElement('img');
        img.src = URL.createObjectURL(file);
        img.alt = data.filename;
        img.loading = 'lazy';
        item.appendChild(img);
    } else {
        const icon = document.createElement('span');
        icon.className = 'pdf-icon';
        icon.textContent = '📄';
        item.appendChild(icon);
    }

    const name = document.createElement('span');
    name.className = 'file-name';
    name.textContent = data.filename;
    name.title = data.filename;
    item.appendChild(name);

    const remove = document.createElement('button');
    remove.className = 'file-remove';
    remove.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
    remove.title = 'Entfernen';
    remove.addEventListener('click', () => _entferneDatei(data.id));
    item.appendChild(remove);

    dom.filePreviewList.appendChild(item);
}

/**
 * Eine Datei aus der Vorschau und der pending-Liste entfernen.
 */
function _entferneDatei(fileId) {
    state.pendingFiles = state.pendingFiles.filter(f => f.id !== fileId);
    const item = dom.filePreviewList.querySelector(`[data-file-id="${fileId}"]`);
    if (item) item.remove();
    if (state.pendingFiles.length === 0) {
        dom.filePreview.classList.add('hidden');
    }
    _aktualisiereUploadKnopf();

    // Datei auf dem Server löschen (fehlertolerant)
    fetch(`${API_BASE}/api/uploads/${fileId}`, { method: 'DELETE' })
        .catch(() => {});
}

/**
 * Upload-Knopf-Styling aktualisieren.
 */
function _aktualisiereUploadKnopf() {
    dom.uploadBtn.classList.toggle('has-files', state.pendingFiles.length > 0);
}

// =========================================
// Vision-Prüfung: Kann das Modell Bilder?
// =========================================
// Der häufigste Grund, warum „Bilder nicht gelesen werden“, ist kein
// Upload-Fehler, sondern das Modell: DeepSeek V4 Flash (Standard) hat
// keine Vision-Modalität. Der Katalog kennt das Feld `bilder` – die
// Oberfläche muss es nur vor dem Senden abfragen.

/** Kann das aktuell gewählte Modell Bilder verarbeiten?
 *  true/false aus dem Katalog; null, wenn unbekannt (Katalog nicht geladen). */
function modellKannBilder() {
    if (!state.katalog || !state.model) return null;
    const m = state.katalog.find(x => x.id === state.model);
    if (!m) return null;
    return Boolean(m.bilder || m.dateien);
}

// Verhindert, dass dieselbe Warnung bei jedem Senden erneut erscheint.
// Wird zurückgesetzt, sobald keine Dateien mehr anhängen.
let visionHinweisGezeigt = false;

/** Warnt im Chat, wenn Bilder angehängt sind, das Modell aber keine
 *  verarbeiten kann. Tut nichts, wenn das Modell Vision kann oder die
 *  Fähigkeit unbekannt ist (dann entscheidet der Server-Fehlertext). */
function _warneFallsModellKeinBild() {
    const kann = modellKannBilder();
    if (kann === null || kann || visionHinweisGezeigt) return;
    visionHinweisGezeigt = true;
    addMessage(
        `⚠️ **${kurzName(state.model)} kann keine Bilder verarbeiten**\n\n`
        + `Du hast ein Bild angehängt, aber das gewählte Modell unterstützt `
        + `keine Bild-Eingabe – es wird das Bild nicht sehen. Wechsle in der `
        + `Modellauswahl zu einem Vision-Modell (Filter „Bilder/Dateien“), `
        + `z. B. \`openai/gpt-5-nano\` oder \`anthropic/claude-sonnet-5\`.`,
        'assistant'
    );
}

/**
 * Zeigt die angehängten Dateien in einer Chat-Nachricht an.
 * Ruft man nach addMessage() auf, um das contentDiv zu befüllen.
 */
function _zeigeDateienInNachricht(contentDiv, files) {
    if (!files || files.length === 0) return;

    files.forEach(f => {
        if (f.type === 'image' && f.data_url) {
            // Bild direkt anzeigen (Base64 data URL)
            const img = document.createElement('img');
            img.src = f.data_url;
            img.alt = f.filename;
            img.loading = 'lazy';
            img.title = f.filename;
            contentDiv.appendChild(img);
        } else if (f.type === 'image' && f.url) {
            // Bild vom Server laden
            const img = document.createElement('img');
            img.src = `${API_BASE}${f.url}`;
            img.alt = f.filename;
            img.loading = 'lazy';
            img.title = f.filename;
            contentDiv.appendChild(img);
        } else {
            // PDF-Icon anzeigen
            const fileDiv = document.createElement('div');
            fileDiv.className = 'message-file';
            fileDiv.innerHTML = `<span class="file-icon">📄</span><span class="file-meta">${escapeHtml(f.filename)}</span>`;
            contentDiv.appendChild(fileDiv);
        }
    });
}

/**
 * Vorschau nach erfolgreichem Senden leeren.
 */
function _raeumeDateiVorschau() {
    state.pendingFiles = [];
    dom.filePreviewList.innerHTML = '';
    dom.filePreview.classList.add('hidden');
    _aktualisiereUploadKnopf();
}

// =========================================
// API Calls
// =========================================

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
            // Server erreichbar – Auto-Close-Timer ggf. abbrechen
            if (autoCloseTimer) {
                clearTimeout(autoCloseTimer);
                autoCloseTimer = null;
            }
            if (serverWarOffline) {
                serverWarOffline = false;
                // Server war weg und ist jetzt wieder da → Status aktualisieren,
                // aber NICHT die Seite neu laden. Das verhindert Reload-Schleifen
                // bei schnellen Server-Neustarts (--reload) und öffnet keine neuen Tabs.
            }
            const data = await res.json();
            setOnline(true);
            if (data.memory_count !== undefined) {
                updateFooterNote(data.memory_count);
            }
            return data;
        }
    } catch (err) {
        console.warn('Health check failed:', err);
    }
    serverWarOffline = true;
    setOnline(false);

    // Auto-Close: Nach 5 Sekunden ohne Server-Verbindung Tab schließen.
    // Läuft der Timer bereits (vorheriger Fehlversuch), tickt er weiter –
    // kein neuer Timer, damit sich nicht mehrere überlagern.
    if (!autoCloseTimer) {
        autoCloseTimer = setTimeout(() => {
            autoCloseTimer = null;
            // Vor dem Schließen noch einmal prüfen – Server könnte
            // inzwischen wieder da sein.
            fetch(`${API_BASE}/api/health`)
                .then(res => {
                    if (res.ok) {
                        // Server doch erreichbar – Tab offen lassen
                        setOnline(true);
                        serverWarOffline = false;
                    } else {
                        _tryCloseTab();
                    }
                })
                .catch(() => {
                    _tryCloseTab(); // Server immer noch weg
                });
        }, 5000);
    }
    return null;
}

/**
 * Versucht den Tab zu schließen. window.close() funktioniert nur bei
 * JS-geöffneten Tabs. Bei normalen Tabs zeigt es stattdessen eine
 * Vollbild-Warnung mit self-destruct nach 30s.
 */
function _tryCloseTab() {
    try {
        window.close();
        // Wenn window.close() erfolgreich war, landen wir nie hier
    } catch (_) {}
    // window.close() hat nicht funktioniert → Vollbild-Warnung anzeigen
    _showCloseOverlay();
}

function _showCloseOverlay() {
    // Prüfen, ob bereits ein Overlay existiert
    if (document.getElementById('hermes-close-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'hermes-close-overlay';
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: #1a1a2e; color: #fff; z-index: 99999;
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; font-family: sans-serif;
        animation: fadeIn 0.3s ease;
    `;
    overlay.innerHTML = `
        <div style="font-size:64px;margin-bottom:20px">🛑</div>
        <h1 style="margin:0 0 10px 0;font-size:24px">Server nicht erreichbar</h1>
        <p style="color:#aaa;margin:0 0 20px 0;text-align:center;max-width:400px">
            Der Personal AI Agent wurde beendet oder ist nicht erreichbar.<br>
            Bitte schließe diesen Tab manuell.
        </p>
        <div id="close-countdown" style="font-size:48px;font-weight:bold;color:#ff6b6b">30</div>
        <p style="color:#888;font-size:12px;margin-top:10px">
            Automatische Schließung in <span id="close-countdown-label">30</span>s
        </p>
        <button onclick="window.close();document.getElementById('hermes-close-overlay').remove()"
                style="margin-top:20px;padding:10px 30px;background:#ff6b6b;color:#fff;
                       border:none;border-radius:8px;cursor:pointer;font-size:16px">
            Tab jetzt schließen
        </button>
    `;
    document.body.innerHTML = '';
    document.body.appendChild(overlay);

    // Countdown von 30s
    let count = 30;
    const counter = document.getElementById('close-countdown');
    const label = document.getElementById('close-countdown-label');
    const timer = setInterval(() => {
        count--;
        if (counter) counter.textContent = String(count);
        if (label) label.textContent = String(count);
        if (count <= 0) {
            clearInterval(timer);
            try { window.close(); } catch (_) {}
        }
    }, 1000);
}

function updateFooterNote(memoryCount) {
    const note = document.querySelector('.footer-note');
    if (note) {
        note.textContent = `${memoryCount} Erinnerungen`;
    }
}

// =========================================
// Modellauswahl
// =========================================
/* Hier stand der Modellname früher fest verdrahtet in der Fußzeile – und
   zwar ein anderer als der, der tatsächlich lief. Deshalb kommt der Name
   jetzt ausschließlich vom Server. */

/** Kurzform für den Knopf: "anthropic/claude-sonnet-5" → "claude-sonnet-5"
 *
 *  Bewusst aus der ID abgeleitet und nicht aus dem Katalognamen: der lautet
 *  etwa "DeepSeek: DeepSeek V4 Flash 0423" und beansprucht zwei Drittel der
 *  Werkzeugleiste. Der volle Name steht in der Auswahlliste. */
const LABEL_MAX = 18;

function kurzName(id) {
    if (!id) return 'Modell';
    const kurz = id.includes('/') ? id.split('/').pop() : id;
    return kurz.length > LABEL_MAX ? kurz.slice(0, LABEL_MAX - 1) + '…' : kurz;
}

function setModelLabel() {
    if (dom.modelLabel) dom.modelLabel.textContent = kurzName(state.model);
    if (dom.modelBtn) {
        dom.modelBtn.classList.toggle('active', Boolean(state.model));
        dom.modelBtn.title = state.model
            ? `Modell: ${state.model} – antippen zum Wechseln`
            : 'Modell wählen';
    }
}

/** Preis lesbar machen. null bedeutet "variabel", nicht "kostenlos". */
function preisText(m) {
    if (m.eingabe_pro_mio === null && m.ausgabe_pro_mio === null) return 'Preis variabel';
    const ein = m.eingabe_pro_mio === null ? '?' : m.eingabe_pro_mio;
    const aus = m.ausgabe_pro_mio === null ? '?' : m.ausgabe_pro_mio;
    return `$${ein} ein / $${aus} aus je Mio`;
}

function kontextText(m) {
    if (!m.context_length) return '';
    const k = m.context_length;
    return k >= 1000000 ? `${(k / 1000000).toFixed(1)} Mio Kontext`
         : k >= 1000    ? `${Math.round(k / 1000)}k Kontext`
         : `${k} Kontext`;
}

/** Wissensstand lesbar: "2024-05-31" → "Stand 05/2024". */
function wissensstandText(kc) {
    if (!kc) return '';
    const t = String(kc).slice(0, 7);               // JJJJ-MM
    return /^\d{4}-\d{2}$/.test(t)
        ? `Stand ${t.slice(3, 5)}/${t.slice(0, 4)}`
        : `Stand ${String(kc).slice(0, 10)}`;
}

/** Laengste Antwort in einem Zug, lesbar. */
function maxAusgabeText(n) {
    if (!n) return '';
    return n >= 1000000 ? `bis ${(n / 1000000).toFixed(1)} Mio Ausgabe`
         : n >= 1000    ? `bis ${Math.round(n / 1000)}k Ausgabe`
         : `bis ${n} Ausgabe`;
}

/** Cache-Preis fuer schon gesehenen Kontext, lesbar. */
function cacheText(p) {
    if (p === null || p === undefined) return '';
    return `Cache $${p}/Mio`;
}

async function ladeKatalog(erzwingen = false) {
    if (state.katalog && !erzwingen) return state.katalog;
    try {
        const res = await fetch(`${API_BASE}/api/models`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const daten = await res.json();
        state.katalog = daten.models || [];
        state.favoriten = daten.favoriten || [];
        state.whitelistAktiv = Boolean(daten.whitelist_aktiv);
        state.modellHinweis = daten.hinweis || '';
        // Ohne eigene Wahl gilt das Modell aus der Server-Konfiguration.
        if (!state.model && daten.aktuell) state.model = daten.aktuell;
        if (daten.notliste) {
            state.modellHinweis =
                'Der Modellkatalog war nicht erreichbar – dies ist eine Notliste. '
                + state.modellHinweis;
        }
        setModelLabel();
        return state.katalog;
    } catch (err) {
        console.warn('Modellkatalog konnte nicht geladen werden:', err);
        state.katalog = [];
        state.modellHinweis = 'Modellliste nicht erreichbar. Läuft das Backend?';
        return [];
    }
}

/** Grobe Schätzung der bisherigen Gesprächslänge in Token. */
function geschaetzteToken() {
    const zeichen = state.messages.reduce((s, m) => s + (m.content || '').length, 0);
    return Math.round(zeichen / 3);
}

function zeileFuer(m, nutzbar = true) {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'model-row'
        + (m.id === state.model ? ' selected' : '')
        + (nutzbar ? '' : ' unavailable');

    // Zeile 1: Modellname – eigene Zeile, vollständig, nichts abschneiden.
    const name = document.createElement('div');
    name.className = 'model-name';
    name.textContent = m.name || m.id;
    row.appendChild(name);

    // Zeile 2: Info-Labels (Badges) in eigener Reihe unter dem Namen. So hat
    // der Name die volle Breite und die Plaketten wickeln sich bei Bedarf um.
    const badges = document.createElement('div');
    badges.className = 'model-badges';

    // Bei aktivem Riegel stehen ohnehin nur speicherfreie Modelle in der
    // Liste – dann ist die Plakette an jedem Eintrag reines Rauschen. Sie
    // erscheint nur, wenn der Riegel aus ist und die Liste gemischt wäre.
    if (m.speicherfrei && !state.noRetention) {
        const b = document.createElement('span');
        b.className = 'badge eu';
        b.textContent = 'kein Speichern';
        b.title = 'Keiner der möglichen Anbieter speichert Prompts';
        badges.appendChild(b);
    } else if (m.anbieter_speichernd) {
        const b = document.createElement('span');
        b.className = 'badge warn';
        // "weltweit" ist kein Beiwerk: Ohne bekannte Whitelist zählt die Zahl
        // alle Anbieter der Welt, nicht die, die dein Konto erreichen kann.
        b.textContent = state.whitelistAktiv
            ? `${m.anbieter_speichernd}/${m.anbieter_gesamt} speichern`
            : `${m.anbieter_speichernd}/${m.anbieter_gesamt} weltweit`;
        b.title = state.whitelistAktiv
            ? 'Ohne Datenschutz-Riegel kann die Anfrage bei einem dieser Anbieter landen'
            : 'Gezählt über alle Anbieter weltweit – deine Whitelist ist dem Backend nicht bekannt';
        badges.appendChild(b);
    }
    if (m.eu) {
        const b = document.createElement('span');
        b.className = 'badge eu';
        // Bewusst "EU-fähig", nicht "EU": Das Routing selbst ist für dieses
        // Konto gesperrt (403) und braucht einen Enterprise-Vertrag.
        b.textContent = 'EU-fähig';
        b.title = 'Würde über den EU-Endpunkt bedient – erfordert einen Enterprise-Vertrag';
        badges.appendChild(b);
    }
    if (m.tools === false) {
        const b = document.createElement('span');
        b.className = 'badge warn';
        b.textContent = 'ohne Werkzeuge';
        b.title = 'Beherrscht keine Werkzeugaufrufe';
        badges.appendChild(b);
    }
    // Stärke-Profil als gut sichtbarer Marker (für die Gruppierung).
    if (m.staerke && STAERKE_LABEL[m.staerke]) {
        const prof = document.createElement('span');
        prof.className = 'badge st' + m.staerke;
        prof.textContent = STAERKE_LABEL[m.staerke];
        badges.appendChild(prof);
    }
    // Preis-Leistungs-Abzeichen aus den echten Preisen.
    if (m.preis_leistung) {
        const pl = document.createElement('span');
        const positiv = m.preis_leistung === 'sehr günstig' || m.preis_leistung === 'günstig';
        pl.className = 'badge ' + (positiv ? 'eu' : 'warn');
        pl.textContent = 'Preis-Leistung: ' + m.preis_leistung;
        pl.title = 'Grobe Einstufung anhand des Eingabepreises pro Mio Token';
        badges.appendChild(pl);
    }
    row.appendChild(badges);

    // Wofuer das Modell gedacht ist. VOLLER Text, nichts kürzen, damit die
    // Frage "wofür" wirklich mit vollständigen Sätzen beantwortet wird.
    if (m.beschreibung) {
        const desc = document.createElement('p');
        desc.className = 'model-desc';
        desc.textContent = m.beschreibung;
        row.appendChild(desc);
    }
    // Benchmark-Referenz (falls gepflegt) als nüchterne Zusatzinfo.
    if (m.benchmark_ref) {
        const bm = document.createElement('p');
        bm.className = 'model-benchmark';
        bm.textContent = '📊 ' + m.benchmark_ref;
        row.appendChild(bm);
    }

    // Eigene Einsatzempfehlung (deutsch) – die Antwort auf "wofür nehme ich das?"
    if (m.verwendung) {
        const use = document.createElement('p');
        use.className = 'model-usecase';
        use.innerHTML = '<b>Beste für:</b> ';
        use.appendChild(document.createTextNode(m.verwendung));
        row.appendChild(use);
    }

    const meta = document.createElement('span');
    meta.className = 'model-meta';
    if (!nutzbar) {
        meta.textContent = 'nicht mehr mit deinen Einstellungen nutzbar';
    } else {
        const teile = [preisText(m), kontextText(m),
                       wissensstandText(m.wissensstand),
                       maxAusgabeText(m.max_ausgabe),
                       cacheText(m.cache_pro_mio)].filter(Boolean);
        meta.textContent = teile.join(' · ');
    }
    row.appendChild(meta);

    if (nutzbar) {
        row.addEventListener('click', () => waehleModell(m));
    }
    return row;
}

function gruppenTitel(text) {
    const h = document.createElement('div');
    h.className = 'sheet-group';
    h.textContent = text;
    return h;
}

/** Filter-Chips sind UND-verknüpft: jeder weitere schränkt weiter ein. */
function passtZuFiltern(m) {
    // Bei aktivem Riegel sind speichernde Anbieter ohnehin gesperrt. Sie
    // trotzdem aufzulisten hieße, Modelle anzubieten, die beim Absenden
    // scheitern – und die Angabe "1/2 speichern" beantwortet die einzige
    // Frage nicht, die zählt: kann ich das nehmen oder nicht.
    if (state.noRetention && !m.speicherfrei) return false;

    for (const f of state.filters) {
        // Stärke-Profil-Filter: "staerke:bilder" → m.staerke === 'bilder'
        if (f.startsWith('staerke:')) {
            const profil = f.slice('staerke:'.length);
            if (!m.staerke || m.staerke !== profil) return false;
            continue;
        }
        if (f === 'bilder') {
            if (!m.bilder && !m.dateien) return false;
        } else if (!m[f]) {
            return false;
        }
    }
    return true;
}

/** Ranking: Reihung nach Stärke-Profil und Preis-Leistung.
 * Ziel: Die "beste für den Job"-Modelle stehen oben, teure/unpassende unten.
 * Primaer: Stärke-Profil (preis_leistung/bilder/coding/reasoning/alltag),
 * Sekundaer: Preis-Leistungs-Stufe (sehr günstig > günstig > mittel > teuer),
 * Tertiaer: Eingabepreis aufsteigend.
 */
const STAERKE_RANG = { preis_leistung: 0, bilder: 1, coding: 2, reasoning: 3, alltag: 4 };
const PREIS_RANG = { 'sehr günstig': 0, 'günstig': 1, 'mittel': 2, 'teuer': 3 };

function staerkeWert(m) {
    return STAERKE_RANG[m.staerke] ?? STAERKE_RANG.alltag;
}
function preisWert(m) {
    return PREIS_RANG[m.preis_leistung] ?? 3;
}
function sortiereNachRanking(a, b) {
    const s = staerkeWert(a) - staerkeWert(b);
    if (s !== 0) return s;
    const p = preisWert(a) - preisWert(b);
    if (p !== 0) return p;
    return (a.eingabe_pro_mio ?? Infinity) - (b.eingabe_pro_mio ?? Infinity);
}

/** Gruppen-Label für das Stärke-Profil eines Modells (deutsch). */
const STAERKE_LABEL = {
    preis_leistung: 'Preis-Leistung-Fokus',
    bilder: 'Bilder verstehen / multimodal',
    coding: 'Programmieren / Coding',
    reasoning: 'Denken / Analyse (Reasoning)',
    alltag: 'Allrounder',
};

function zeichneListe() {
    const suche = (dom.modelSearch.value || '').trim().toLowerCase();
    dom.modelList.innerHTML = '';
    const alle = state.katalog || [];

    if (!alle.length) {
        dom.modelList.appendChild(gruppenTitel('Keine Modelle verfügbar'));
        return;
    }

    const gefiltert = alle.filter(passtZuFiltern);
    const aktiv = state.filters.size > 0;

    // Favoriten nur zeigen, wenn weder gesucht noch gefiltert wird – sonst
    // stehen oben Einträge, die der Filter gerade ausschließen sollte.
    if (!suche && !aktiv) {
        dom.modelList.appendChild(gruppenTitel('Favoriten'));
        state.favoriten.forEach(id => {
            const treffer = alle.find(m => m.id === id);
            // Nicht mehr verfügbare Favoriten bleiben sichtbar und ausgegraut –
            // sonst verschwinden sie still und man rätselt, warum.
            dom.modelList.appendChild(
                treffer ? zeileFuer(treffer) : zeileFuer({ id, name: id }, false)
            );
        });
        dom.modelList.appendChild(gruppenTitel(`Alle ${alle.length} Modelle`));
    }

    const treffer = gefiltert.filter(m =>
        !suche || m.id.toLowerCase().includes(suche)
               || (m.name || '').toLowerCase().includes(suche));

    if (aktiv || suche) {
        let trefferTitel;
        if (treffer.length) {
            trefferTitel = `${treffer.length} von ${alle.length} Modellen`;
        } else {
            // Mehrere „Stärke“-Chips sind unerfüllbar, weil jedes Modell genau
            // EINE primäre Stärke hat – der Hinweis erklärt das statt zu raten.
            const staerkeChips = [...state.filters].filter(f => f.startsWith('staerke:')).length;
            trefferTitel = staerkeChips > 1
                ? 'Keine Treffer – ein Modell hat genau EINE Stärke; nur ein „Stärke“-Profil wählen'
                : 'Keine Treffer – Filter lockern';
        }
        dom.modelList.appendChild(gruppenTitel(trefferTitel));
    }

    // Ranking: Treffer nach Stärke-Profil + Preis-Leistung sortieren.
    treffer.sort(sortiereNachRanking);

    if (aktiv || suche) {
        // Gruppierte Anzeige nach Stärke-Profil (nur wenn sortiert wird).
        let letzteGruppe = null;
        treffer.slice(0, 120).forEach(m => {
            const grp = STAERKE_LABEL[m.staerke] || STAERKE_LABEL.alltag;
            if (grp !== letzteGruppe) {
                dom.modelList.appendChild(gruppenTitel(grp));
                letzteGruppe = grp;
            }
            dom.modelList.appendChild(zeileFuer(m));
        });
    } else {
        treffer.slice(0, 120).forEach(m => dom.modelList.appendChild(zeileFuer(m)));
    }
}

function setPrivacy(an) {
    state.noRetention = an;
    localStorage.setItem('no_retention', an ? '1' : '0');
    dom.privacyBtn.classList.toggle('active', an);
    dom.privacyBtn.setAttribute('aria-pressed', an ? 'true' : 'false');
    dom.privacyLabel.textContent = an ? 'Riegel an' : 'Riegel';
    dom.privacyBtn.title = an
        ? 'Nur Anbieter ohne Speicherung. Passt keiner, wird die Anfrage abgelehnt statt still weitergereicht.'
        : 'Datenschutz-Riegel aus – OpenRouter darf zu Anbietern routen, die Prompts speichern';
}

async function waehleModell(m) {
    // Modelle unterscheiden sich um den Faktor 100 in der Kontextlänge. Ein
    // Wechsel mitten in einem langen Gespräch kann sofort scheitern.
    const belegt = geschaetzteToken();
    if (m.context_length && belegt > m.context_length * 0.7) {
        const weiter = confirm(
            `Dieses Gespräch ist bereits rund ${belegt.toLocaleString('de-DE')} Token lang.\n`
            + `${m.name || m.id} fasst ${m.context_length.toLocaleString('de-DE')}.\n\n`
            + 'Der Verlauf passt möglicherweise nicht mehr. Trotzdem wechseln?'
        );
        if (!weiter) return;
    }

    state.modelVorher = state.model;
    state.model = m.id;
    localStorage.setItem('model', m.id);
    // Nach einem Wechsel darf die Vision-Warnung neu bewertet werden.
    visionHinweisGezeigt = false;
    setModelLabel();
    schliesseBlatt();
    await zeigeDetails(m.id);
}

/** Datenschutz-Profil unter der Antwort einblenden, wenn gewechselt wurde. */
async function zeigeDetails(modelId) {
    try {
        const res = await fetch(`${API_BASE}/api/models/${modelId}/details`);
        if (!res.ok) return;
        const daten = await res.json();
        const alleAnbieter = daten.anbieter || [];
        if (!alleAnbieter.length) return;

        // Nur die Anbieter beurteilen, die dieses Konto auch erreichen kann.
        // Die übrigen stehen als Fußnote darunter – sie sind der Grund, eine
        // Whitelist später zu ändern, aber nicht Teil der aktuellen Lage.
        const anbieter = alleAnbieter.filter(a => a.erreichbar !== false);
        const gesperrt = alleAnbieter.filter(a => a.erreichbar === false);

        // Drei Zustände, nicht zwei: true, false und "kein Profil gefunden".
        // Unbekanntes als "speichert nicht" zu zeigen wäre ein falsches
        // Sicherheitsversprechen.
        const speichernd = anbieter.filter(a => a.speichert === true);
        const unbekannt = anbieter.filter(a => a.speichert === null);
        const zeilen = [
            `**Modell gewechselt:** ${daten.name || modelId}`,
            '',
            `${anbieter.length} ${daten.whitelist_aktiv ? 'für dich erreichbare' : 'mögliche'} `
            + `Anbieter, davon ${speichernd.length} mit Speicherung.`,
        ];
        if (speichernd.length) {
            const namen = speichernd
                .map(a => a.aufbewahrung_tage ? `${a.name} (${a.aufbewahrung_tage} T.)` : a.name)
                .slice(0, 6);
            zeilen.push(`Speichern Prompts: ${namen.join(', ')}`);
        }
        const trainierend = anbieter.filter(a => a.trainiert === true);
        if (trainierend.length) {
            zeilen.push(`⚠️ Trainieren auf Daten: ${trainierend.map(a => a.name).join(', ')}`);
        }
        if (unbekannt.length) {
            zeilen.push(`❓ Ohne Angabe: ${unbekannt.map(a => a.name).join(', ')}`);
        }
        if (gesperrt.length) {
            zeilen.push('', `_Nicht in deiner Whitelist (${gesperrt.length}): `
                + `${gesperrt.map(a => a.name).slice(0, 8).join(', ')}_`);
        }
        zeilen.push('', `_${daten.hinweis || ''}_`);
        addMessage(zeilen.join('\n'), 'assistant');
    } catch (err) {
        console.warn('Modell-Details nicht abrufbar:', err);
    }
}

function schliesseBlatt() {
    dom.modelSheet.hidden = true;
}

async function oeffneBlatt() {
    dom.modelSheet.hidden = false;
    dom.modelSearch.value = '';
    dom.modelList.innerHTML = '';
    dom.modelList.appendChild(gruppenTitel('Lade Modelle …'));
    await ladeKatalog();
    dom.modelHint.textContent = state.modellHinweis;
    zeichneListe();
}

const SYMBOL_LAUTSPRECHER = '<svg viewBox="0 0 24 24" width="16" height="16">'
    + '<path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05'
    + 'c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06'
    + 'c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>';

const SYMBOL_PAUSE = '<svg viewBox="0 0 24 24" width="16" height="16">'
    + '<path fill="currentColor" d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

// Nur ein Vorleser gleichzeitig – sonst reden zwei Antworten durcheinander.
let aktiverVorleser = null;

// ── Schwebendes Mini-Audio-Control ─────────────────────────────────────────
// Solange ein Vorleser AKTIV ist (spielt oder pausiert), bleibt unten rechts
// ein kompakter Knopf sichtbar, der beim Scrollen durch den ganzen Chat
// weiterläuft (position:fixed). So verliert man den laufenden Vorleser nie.
let _schwebeVorleser = null;      // steuerung des aktiven Vorlesers
let _schwebeSpielt = false;       // true = gerade abspielend
let schwebendesControl = null;

function baueSchwebendesControl() {
    const c = document.createElement('button');
    c.id = 'schwebendes-audio';
    c.type = 'button';
    c.title = 'Vorlesen steuern';
    c.setAttribute('aria-label', 'Vorlesen steuern');
    c.innerHTML = SYMBOL_LAUTSPRECHER;
    c.style.cssText =
        'position:fixed;right:22px;bottom:158px;z-index:900;display:none;'
        + 'align-items:center;justify-content:center;width:60px;height:60px;'
        + 'border-radius:50%;background:var(--accent);color:#fff;border:none;'
        + 'box-shadow:0 4px 16px rgba(0,0,0,.45);cursor:pointer;'
        + 'font-size:26px;line-height:1';
    c.addEventListener('click', () => {
        if (_schwebeVorleser) _schwebeVorleser.toggle();
        _aktualisiereSchwebendesControl();
    });
    document.body.appendChild(c);
    return c;
}

/** Synchronisiert das schwebende Control mit dem Zustand des aktiven Vorlesers.
 *  Wird bei jedem Zustandswechsel des Vorlesers aufgerufen (zeigeZustand). */
function _aktualisiereSchwebendesControl() {
    if (!schwebendesControl) schwebendesControl = baueSchwebendesControl();
    const sichtbar = Boolean(aktiverVorleser);
    _schwebeVorleser = aktiverVorleser;
    _schwebeSpielt = Boolean(aktiverVorleser && !(aktiverVorleser._pausiert));
    schwebendesControl.style.display = sichtbar ? 'flex' : 'none';
    schwebendesControl.title = _schwebeSpielt ? 'Pause' : 'Vorlesen';
    schwebendesControl.setAttribute('aria-label', _schwebeSpielt ? 'Audio pausieren' : 'Audio vorlesen');
    schwebendesControl.innerHTML = _schwebeSpielt ? SYMBOL_PAUSE : SYMBOL_LAUTSPRECHER;
}

// Ab dieser Länge wird ein Stück abgeschickt. Kürzere Sätze werden gesammelt,
// sonst entsteht für jedes "Ja." eine eigene Anfrage.
const MIN_STUECK_LAENGE = 60;

/** Räumt Markdown aus einem Stück, damit die Stimme keine Sternchen liest. */
function textFuerStimme(text) {
    return text
        .replace(/```/g, '')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/[*_#>]/g, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Vorlese-Bedienung oben rechts an einer Antwort.
 *
 * Liest mit, während die Antwort noch geschrieben wird: Sobald ein Stück
 * Text abgeschlossen ist, wird es geholt und in eine Warteschlange gelegt.
 * Die Stimme läuft dem Text hinterher, statt auf das Ende zu warten.
 *
 * @param messageDiv  Die Nachrichten-Hülle (Geschwister der Sprechblase)
 * @param holeText    Liefert den bisher eingetroffenen Volltext
 * @param istFertig   Sagt, ob die Antwort vollständig ist
 */
function addSpeakControls(messageDiv, holeText, istFertig) {
    const leiste = document.createElement('div');
    leiste.className = 'speak-controls';

    // Ein einziger Knopf steuert alles: Vorlesen starten, dann pausieren und
    // fortsetzen. Ein zweiter Stopp-Knopf war daneben nur Ballast — auf dem
    // Handy zaehlt jeder Millimeter Daumenflaeche.
    const abspielBtn = document.createElement('button');
    abspielBtn.className = 'speak-btn';
    abspielBtn.title = 'Vorlesen';
    abspielBtn.innerHTML = SYMBOL_LAUTSPRECHER;
    // Baumuster ohne sichtbaren Text: das aria-label ist die einzige
    // Beschriftung für Screenreader und muss IMMER gesetzt sein.
    abspielBtn.setAttribute('aria-label', 'Audio vorlesen');

    leiste.appendChild(abspielBtn);
    messageDiv.appendChild(leiste);

    let aktiv = false;        // Vorlesen überhaupt eingeschaltet?
    let pausiert = false;
    let gelesenBis = 0;       // Position im Rohtext, bis wohin abgeschickt wurde
    let warteschlange = [];
    let aktuellesAudio = null;
    let holtGerade = false;

    const zeigeZustand = () => {
        const spielt = aktiv && !pausiert;
        abspielBtn.innerHTML = spielt ? SYMBOL_PAUSE : SYMBOL_LAUTSPRECHER;
        abspielBtn.title = spielt ? 'Pause' : 'Vorlesen';
        // aria-label parallel zum title halten – der Knopf trägt nur ein SVG.
        abspielBtn.setAttribute('aria-label', spielt ? 'Audio pausieren' : 'Audio vorlesen');
        // Farbe über .playing, Vergrößerung über .active (nur an 'spielt'
        // gekoppelt – halte(true) setzt pausiert/aktiv zurück, wodurch .active
        // via zeigeZustand automatisch wieder entfernt wird).
        abspielBtn.classList.toggle('playing', spielt);
        abspielBtn.classList.toggle('active', spielt);
        // Zustand für das globale schwebende Control spiegeln + aktualisieren.
        if (aktiverVorleser) {
            aktiverVorleser._aktiv = aktiv;
            aktiverVorleser._pausiert = pausiert;
        }
        _aktualisiereSchwebendesControl();
    };

    /** Nächstes abgeschlossenes Stück, oder null wenn noch nichts fertig ist. */
    const naechstesStueck = () => {
        const rest = holeText().slice(gelesenBis);
        if (!rest) return null;

        // Ein Stück endet an einem Satzzeichen oder Absatz. Ist die Antwort
        // fertig, wird der Rest genommen, auch ohne Satzzeichen.
        const treffer = rest.match(/^[\s\S]*?(?:[.!?…:](?=\s|$)|\n)/);
        let stueck = treffer ? treffer[0] : (istFertig() ? rest : null);
        if (stueck === null) return null;

        // Kurze Sätze sammeln, bis genug beisammen ist – sonst entsteht für
        // jedes "Ja." eine eigene Anfrage.
        if (!istFertig() && stueck.trim().length < MIN_STUECK_LAENGE
            && stueck.length < rest.length) {
            return null;
        }

        gelesenBis += stueck.length;
        return stueck;
    };

    /** Holt fortlaufend fertige Stücke, solange welche da sind. */
    const nachfuellen = async () => {
        if (holtGerade || !aktiv) return;
        holtGerade = true;
        try {
            while (aktiv) {
                const stueck = naechstesStueck();
                if (stueck === null) break;

                const sauber = textFuerStimme(stueck);
                if (sauber.length < 2 || !/[a-zA-ZäöüÄÖÜß]/.test(sauber)) continue;

                const res = await fetch(`${API_BASE}/api/speak`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: sauber.slice(0, 2000) }),
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                if (!aktiv) break;   // während des Holens gestoppt

                warteschlange.push(new Audio(URL.createObjectURL(await res.blob())));
                spieleWeiter();
            }
        } catch (err) {
            console.warn('Vorlesen abgebrochen:', err);
            if (!warteschlange.length && !aktuellesAudio) {
                // Nichts konnte geholt werden – Browser-Stimme als Rückfall.
                if (!speakResponse(holeText())) {
                    abspielBtn.classList.add('failed');
                    abspielBtn.title = 'Vorlesen fehlgeschlagen – Grund steht im Server-Log';
                }
                halte(true);
            }
        } finally {
            holtGerade = false;
            abspielBtn.classList.remove('busy');
        }
    };

    function spieleWeiter() {
        if (!aktiv || pausiert || aktuellesAudio) return;
        const naechstes = warteschlange.shift();
        if (!naechstes) return;
        aktuellesAudio = naechstes;
        aktuellesAudio.onended = () => {
            aktuellesAudio = null;
            spieleWeiter();
            // Am Ende angekommen und nichts mehr zu erwarten? Zurücksetzen.
            if (!aktuellesAudio && !warteschlange.length && istFertig()
                && gelesenBis >= holeText().length) {
                halte(true);
            }
        };
        aktuellesAudio.play().catch(err => console.warn('Wiedergabe:', err));
    }

    /** Anhalten. Mit zuruecksetzen=true wird auch der Fortschritt verworfen. */
    function halte(zuruecksetzen) {
        if (aktuellesAudio) {
            aktuellesAudio.pause();
            aktuellesAudio = null;
        }
        warteschlange = [];
        aktiv = false;
        pausiert = false;
        if (zuruecksetzen) gelesenBis = 0;
        if (aktiverVorleser === steuerung) aktiverVorleser = null;
        zeigeZustand();
    }

    abspielBtn.addEventListener('click', () => {
        if (aktiv && !pausiert) {
            pausiert = true;
            if (aktuellesAudio) aktuellesAudio.pause();
            zeigeZustand();
            return;
        }
        if (aktiv && pausiert) {
            pausiert = false;
            if (aktuellesAudio) aktuellesAudio.play();
            else spieleWeiter();
            zeigeZustand();
            return;
        }
        // Neu starten – ein anderer laufender Vorleser wird abgelöst.
        if (aktiverVorleser && aktiverVorleser !== steuerung) aktiverVorleser.stopp();
        aktiverVorleser = steuerung;
        aktiv = true;
        pausiert = false;
        abspielBtn.classList.add('busy');
        zeigeZustand();
        nachfuellen();
    });


    const steuerung = {
        /** Wird gerufen, wenn neuer Text eingetroffen ist. */
        neuerText: () => { if (aktiv && !pausiert) nachfuellen(); },
        stopp: () => halte(true),
        /** Toggle Play/Pause für ein externes (schwebendes) Steuer-Control. */
        toggle: () => {
            if (aktiv && !pausiert) {
                pausiert = true;
                if (aktuellesAudio) aktuellesAudio.pause();
                zeigeZustand();
                return;
            }
            if (aktiv && pausiert) {
                pausiert = false;
                if (aktuellesAudio) aktuellesAudio.play();
                else spieleWeiter();
                zeigeZustand();
                return;
            }
            // Neu starten – ein anderer laufender Vorleser wird abgelöst.
            if (aktiverVorleser && aktiverVorleser !== steuerung) aktiverVorleser.stopp();
            aktiverVorleser = steuerung;
            aktiv = true;
            pausiert = false;
            abspielBtn.classList.add('busy');
            zeigeZustand();
            nachfuellen();
        },
    };
    return steuerung;
}

/** Zeigt eine Hermes-Zwischenmeldung (gedanke).
 *  Hinweis: Frueher trug jede Zwischenmeldung einen eigenen "⏹ Hermes abbrechen"-
 *  Knopf (fuegeGedankeMitAbbruchHinzu). Stand 2026-09-06 (Auftrag Sebastian):
 *  der Knopf in der Coding-Ansicht ist ueberfluessig — der Abbruch laeuft ueber
 *  brichAb (globale Stop-Geste, z. B. leere Eingabe). Die Funktion rendert die
 *  Zwischenmeldung jetzt ohne eigenen Abbruch-Button. */
function fuegeGedankeMitAbbruchHinzu(text, zeitIso) {
    const div = document.createElement('div');
    div.className = 'message agent-zwischenmeldung';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = parseMarkdown(text || '');
    div.appendChild(contentDiv);

    // Zeit-Label (WhatsApp-artig) wie bei normalen Blasen.
    const zeitSpan = document.createElement('div');
    zeitSpan.className = 'message-time';
    zeitSpan.textContent = formatZeit(zeitIso);
    zeitSpan.style.cssText = 'font-size:0.65rem;color:#888;margin-top:2px';
    div.appendChild(zeitSpan);

    dom.messages.appendChild(div);
    scrollToBottom(true);
}

/** Zeigt eine fluechtige Bild-Miniatur in der Antwortblase (WhatsApp-Stil).
 *  Nach BILD_ANZEIGE_MS verschwindet sie automatisch; es bleibt ein
 *  Platzhalter "Bild wieder anzeigen", der das Bild FRISCH vom Speicher
 *  laedt (GET /api/dateien/daten?pfad=) — nichts wird persistiert. */
const BILD_ANZEIGE_MS = 10000;

function zeigeBildVorschau(container, dataUrl, pfad, rahmen) {
    if (!container) return;
    // Beim Nachladen (Rekursion aus dem '… lädt'-Knopf) den BESTEHENDEN
    // Rahmen wiederverwenden und leeren. Vorher wurde ein zweiter Rahmen
    // an container angehängt, wodurch der '… lädt'-Knopf des alten Rahmens
    // dauerhaft sichtbar blieb, statt nach dem Laden zu verschwinden.
    if (rahmen) {
        rahmen.innerHTML = '';
    } else {
        rahmen = document.createElement('div');
        rahmen.className = 'bild-vorschau';
        rahmen.style.cssText =
            'margin-top:8px;max-width:100%;display:flex;flex-direction:column;gap:6px';
        container.appendChild(rahmen);
    }

    const img = document.createElement('img');
    img.src = dataUrl;
    img.alt = 'Bildvorschau';
    img.style.cssText =
        'max-width:100%;max-height:220px;border-radius:10px;border:1px solid #444;object-fit:cover';
    rahmen.appendChild(img);

    const hinweis = document.createElement('span');
    hinweis.textContent = '🖼️ Bild wird kurz angezeigt (flüchtig)';
    hinweis.style.cssText = 'font-size:0.7rem;color:#888';
    rahmen.appendChild(hinweis);

    container.appendChild(rahmen);

    // Nach-Reload-Quiz: Ist diese Blase eine wiederhergestellte, offene Quiz-
    // Karte (dataset.quizRekon gesetzt), wird der gelbe bbox-Rahmen + der
    // Gesicht-Ausschnitt JETZT nachgezeichnet — hier existiert das <img>.
    try {
        const qr = container.dataset && container.dataset.quizRekon;
        if (qr) {
            const qd = JSON.parse(qr);
            if (qd && qd.ui && qd.pfad) {
                const gs = (qd.ui.gesichter) || [];
                if (gs.length) {
                    markiereGesichtImBild(img, gs, 0);
                    try { img.addEventListener('load', () => markiereGesichtImBild(img, gs, 0)); } catch (_) {}
                    // Gesicht-Ausschnitt (flüchtig) auch in der wiederhergestellten Karte
                    const bb = gs[0] && gs[0].bbox;
                    if (bb && bb.length >= 4) zeigeGesichtCropIn(container, dataUrl, bb, 240);
                }
            }
        }
    } catch (_) {}

    // Nach BILD_ANZEIGE_MS: Bild weg, Platzhalter zum Nachladen da.
    // ABER: HOCHGELADENE Bilder (upload-Pfad) bleiben dauerhaft angezeigt
    // (Screenshots/Fehlerbilder im Coding-Chat etc.), kein 10s-Platzhalter.
    // Ebenfalls dauerhaft: WIEHERGESTELLTE offene Quiz-Karten (quizRekon) —
    // deren Bild ist die aktive Quiz-Frage und darf nicht nach 10s verschwinden.
    // Nur fluechtige Dateisuche-Vorschauen werden nach 10s durch den
    // 'Bild wieder anzeigen'-Knopf ersetzt.
    const istQuizRekon = !!(container.dataset && container.dataset.quizRekon);
    const istUpload = (pfad || '').indexOf('/uploads/') !== -1 || (pfad || '').indexOf('uploads/') === 0;
    if (istUpload || istQuizRekon) {
        return; // dauerhaft, kein 10s-Timer/Platzhalter
    }
    let timer = setTimeout(() => {
        rahmen.innerHTML = '';
        const btn = document.createElement('button');
        btn.className = 'bild-nachladen';
        btn.textContent = '🖼️ Bild wieder anzeigen';
        btn.style.cssText =
            'padding:6px 10px;border:1px solid #555;border-radius:8px;background:#2a2a2a;' +
            'color:inherit;cursor:pointer;font-size:0.8rem';
        btn.addEventListener('click', async () => {
            if (!pfad) return;
            btn.disabled = true;
            btn.textContent = '… lädt';
            try {
                const res = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(pfad)}`);
                const daten = await res.json();
                if (daten.data_url) {
                    zeigeBildVorschau(container, daten.data_url, pfad, rahmen); // gleicher Rahmen (loop)
                } else {
                    btn.textContent = '⚠️ Bild nicht verfügbar';
                }
            } catch (_) {
                btn.textContent = '⚠️ Laden fehlgeschlagen';
            }
        });
        rahmen.appendChild(btn);
    }, BILD_ANZEIGE_MS);
}

/** Beendet eine Antwortblase: Markdown rendern, Verlauf und Fußzeile setzen. */
function finishReply(contentDiv, entry, antwort, abschluss, vorleser) {
    const untenGewesen = isAtBottom();
    contentDiv.innerHTML = parseMarkdown(antwort);
    entry.content = antwort;
    // Muss nach dem Setzen von innerHTML kommen, sonst wird es überschrieben.
    if (abschluss) addSources(contentDiv, abschluss.sources);
    // Ziel-Pille: zeigt unter Delegations-Antworten, wohin der Auftrag ging
    // (PC-Hermes / Handy-Hermes / Auftragsbuch) — `ziel` tragen die
    // SSE-done-Events bzw. die ChatResponse (Fallback-Weg).
    if (abschluss && abschluss.ziel) addZielChip(contentDiv, abschluss.ziel);
    if (abschluss) {
        if (abschluss.conversation_id) {
            state.conversationId = abschluss.conversation_id;
            localStorage.setItem('conversation_id', abschluss.conversation_id);
        }
        if (abschluss.memory_count !== undefined) updateFooterNote(abschluss.memory_count);
        // Bild-Vorschau (flüchtig): Miniatur kurz anzeigen, dann verschwinden.
        if (abschluss.bild_vorschau) {
            zeigeBildVorschau(contentDiv, abschluss.bild_vorschau, abschluss.bild_pfad);
        }
    }
    // Der Vorleser darf jetzt auch den letzten Rest ohne Satzzeichen holen.
    if (vorleser) vorleser.neuerText();
    if (untenGewesen) scrollToBottom(true);

    // Automatischer Auftrag-Tracker: Enthält die Antwort eine Auftrag-ID?
    // Er startet nur, wenn der /chat/stream NICHT schon selbst die Strecke
    // bis zum Abschluss durchgereicht hat (sonst würden seine Zwischenschritte
    // zusätzlich echoen, obwohl sie längst als Stream-Häppchen da waren).
    const match = antwort.match(/Auftrags-ID:\s*`?([a-f0-9]{8})/i);
    if (match && !_auftragStreckeDirekt) {
        startAuftragTracking(match[1], contentDiv);
    }
    _auftragStreckeDirekt = false; // Flag für die nächste Nachricht zurücksetzen
}

/** Formatiert einen ISO-Zeitstempel ("2026-08-22T23:04:47+02:00")
 * WhatsApp-artig: Datum + Uhrzeit mit Sekunden, z. B. "23.08.2026 · 23:04:47".
 * Unbrauchbares (kein Datum) bleibt stehen. */
function formatZeit(iso) {
    try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        const datum = d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const zeit = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        return `${datum} · ${zeit}`;
    } catch (e) {
        return iso;
    }
}

/** Kalendartag der übergebenen Zeit, als lokaler Tages-Schlüssel (YYYY-MM-DD).
 *  Wird genutzt, um zu erkennen, wann eine neue Datums-Pille nötig ist. */
function datumSchluessel(iso) {
    try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return null;
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const t = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${t}`;
    } catch (e) {
        return null;
    }
}

/** WhatsApp-artige Datumspille: „Heute", „Gestern" oder „23.08.2026". */
function formatDatumBanner(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const heute = new Date();
    const startHeute = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate()).getTime();
    const startTag = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const tage = Math.round((startHeute - startTag) / 86400000);
    if (tage === 0) return 'Heute';
    if (tage === 1) return 'Gestern';
    // Wochentag + Datum; Jahr nur, wenn die Nachricht nicht aus dem aktuellen
    // Jahr stammt (WhatsApp-Stil: bei älteren Tagen/anderen Jahren wird das
    // Jahr ergänzt, beim laufenden Jahr weggelassen).
    const wochentag = d.toLocaleDateString('de-DE', { weekday: 'long' });
    // Wochentag großschreiben (de-DE liefert klein: "samstag")
    const wt = wochentag.charAt(0).toUpperCase() + wochentag.slice(1);
    const tag = d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
    if (d.getFullYear() !== heute.getFullYear()) {
        return `${wt}, ${tag} ${d.getFullYear()}`;
    }
    return `${wt}, ${tag}`;
}

/** Baut die zentrierte Datums-Pille als <div class="date-divider">. */
function baueDatumBanner(iso) {
    const pill = document.createElement('div');
    pill.className = 'date-divider';
    pill.textContent = formatDatumBanner(iso);
    return pill;
}

/** Setzt den Merker für die Datums-Pillen zurück – immer dann, wenn die
 *  Anzeige neu aufgebaut wird (neues Gespräch / geladener Verlauf). */
function zuruecksetzenDatumBanner() {
    _letzteBannerDatum = null;
}

/** Kalendertag, auf dem die zuletzt gezeichnete Datums-Pille steht. */
let _letzteBannerDatum = null;

/** Nur die Uhrzeit mit Sekunden („23:04:47") – fürs Label unter der Blase.
 *  Das Datum steht in der Datums-Pille darüber. Unbrauchbares bleibt stehen. */
function formatUhrzeit(iso) {
    try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
        return iso;
    }
}

/** Zerlegt eine rohe Hermes-Meldung ("[ISO] text") in reinen Text und die
 *  Zeitangabe getrennt – fürs Zeitstempel-Label unter der Chat-Blase. So
 *  bleibt jede Hermes-Meldung optisch getrennt (kein hässlicher ISO-String
 *  vor dem Text). */
function zerlegeHermesMeldung(m) {
    const roh = (m || '').trim();
    const isoMatch = roh.match(/^\[([^\]]+)\]\s*/);
    return {
        text: roh.replace(/^\[[^\]]+\]\s*/, ''),
        zeitIso: (isoMatch && isoMatch[1]) || null,
    };
}

/**
 * Pollt alle 3 Sekunden den Status eines Coding-Auftrags und zeigt
 * Live-Updates im Chat an – jede neue Meldung als eigene Chat-Blase.
 */
// ==== WhatsApp-artige Antwort-Zitat (↩ Antworten) ====
let _antwortAuf = null; // { rolle, text, zeit, bildPfad }

function setzeAntwortAuf(rolle, text, zeit, bildPfad) {
    const t = (text || '').trim();
    if (!t) return;
    _antwortAuf = { rolle, text: t, zeit: zeit || '', bildPfad: bildPfad || '' };
    const v = document.getElementById('antwort-vorschau');
    if (!v) return;
    v.innerHTML = '';
    const inhalt = document.createElement('div'); inhalt.className = 'av-inhalt';
    const rolleD = document.createElement('div'); rolleD.className = 'av-rolle';
    rolleD.textContent = rolle === 'user' ? 'Du' : 'Agent';
    const textD = document.createElement('div'); textD.className = 'av-text'; textD.textContent = t;
    inhalt.appendChild(rolleD); inhalt.appendChild(textD);
    if (bildPfad) {
        const img = document.createElement('img'); img.className = 'av-bild'; img.alt = '';
        fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(bildPfad)}`)
            .then(r => r.json()).then(d => { if (d && d.data_url) img.src = d.data_url; })
            .catch(() => {});
        v.appendChild(img);
    }
    const x = document.createElement('button'); x.className = 'av-x'; x.textContent = '✕';
    x.title = 'Antwort entfernen'; x.type = 'button';
    x.onclick = clearAntwortAuf;
    v.appendChild(inhalt); v.appendChild(x);
    v.classList.remove('hidden');
    const inp = document.getElementById('message-input'); if (inp) inp.focus();
}
function clearAntwortAuf() {
    _antwortAuf = null;
    const v = document.getElementById('antwort-vorschau');
    if (v) { v.classList.add('hidden'); v.innerHTML = ''; }
}

let _auftragTimer = null;
// Kurz-ID des aktuell laufenden Hermes-Auftrags (für den Kommunikationskanal:
// solange gesetzt, wird eine neue Chat-Nachricht als Kommentar an die Session
// geschickt statt einen neuen Auftrag zu starten).
let _laufenderAuftragKurz = null;
// Ziel des laufenden Hermes-Auftrags (pc/handy/buch) — fürs Status-Badge.
let _zielAktuell = '';
// True, wenn die DIESE-Session-Antwort gerade als Stream ins Frontend geht
// (Badge "Hermes denkt (Stream bereit)"). Wird beim Streambeginn gesetzt.
let hermesStreamBereit = false;
// True, wenn ausserhalb dieser Session gerade ein Hermes-Auftrag offen/laeuft
// (vom /api/auftraege-Poller gesetzt). Lässt den Header-Badge rot „Hermes
// arbeitet" zeigen, auch wenn die Aufgabe NICHT über dieses Frontend gestartet
// wurde. Wunsch Sebastian: oben soll sichtbar sein, wann Hermes tut.
let _hermesArbeitetAussen = false;
/** Header-Badge mit dem externen Hermes-Status synchronisieren. Wird vom
 *  /api/auftraege-Poller gerufen, sobald ein offener/laufender Auftrag
 *  erkannt bzw. keiner mehr da ist. */
function _setzeHermesAussen(aktiv) {
    if (_hermesArbeitetAussen === aktiv) return;
    _hermesArbeitetAussen = aktiv;
    if (typeof aktualisiereStatusAnzeige === 'function') aktualisiereStatusAnzeige();
}
// True, wenn der /chat/stream die Live-Strecke selbst bis zum Abschluss
// geführt hat (done mit auftrag_strecke). Dann braucht der 3s-Poller nicht
// zusätzlich zu laufen – er bleibt nur Rückfall, wenn der Stream wegbrichst.
let _auftragStreckeDirekt = false;

function startAuftragTracking(aidKurz, contentDiv) {
    if (_auftragTimer) clearInterval(_auftragTimer);
    let letzteAnzahl = 0;       // Wie viele Meldungen wir schon gesehen haben
    let ersteBlase = contentDiv; // Die ursprüngliche "Auftrag erkannt"-Blase
    // Kommunikationskanal: solange dieser Auftrag läuft, gehen neue
    // Chat-Nachrichten als Kommentar an die Session (nicht als neuer Auftrag).
    _laufenderAuftragKurz = aidKurz;
    aktualisiereStatusAnzeige();
    // Status-Wechsel merken: nur einmal pro Übergang anzeigen (kein Spam).
    let letzterStatus = null;

    _auftragTimer = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/auftraege/${aidKurz}/chat`);
            if (!res.ok) return;
            const data = await res.json();
            const meldungen = data.meldungen || [];
            const anzahl = data.meldungen_count || 0;

            // Status-Wechsel sichtbar machen: "laeuft/fertig/fehler" → einmalige Blase
            const status = data.status || '';
            if (status !== letzterStatus) {
                letzterStatus = status;
                if (status === 'laeuft') {
                    addMessage('⚙️ **Hermes arbeitet an dem Auftrag…**', 'assistant');
                } else if (status === 'fehler') {
                    addMessage('❌ **Hermes konnte den Auftrag nicht abschließen**', 'assistant');
                }
            }

            // Neue Meldungen seit letztem Poll?
            if (anzahl > letzteAnzahl) {
                const neue = meldungen.slice(letzteAnzahl);
                for (const meldung of neue) {
                    // Jede neue Meldung als eigene Chat-Blase; die in der
                    // Meldung steckende [ISO]-Zeit wandert ins Label.
                    const { text: htext, zeitIso } = zerlegeHermesMeldung(meldung);
                    addMessage(htext, 'assistant', zeitIso || null);
                }
                letzteAnzahl = anzahl;
                scrollToBottom(true);
            }

            // Auftrag fertig/fehler → Zusammenfassung zeigen + stoppen
            if (data.status === 'fertig' || data.status === 'fehler') {
                let summary = '';
                if (data.status === 'fertig') {
                    summary = '✅ **Auftrag abgeschlossen!**';
                } else {
                    summary = '❌ **Auftrag fehlgeschlagen**';
                }

                if (data.ergebnis_details) {
                    const d = data.ergebnis_details;
                    if (d.commit) summary += `\n📤 **Commit:** \`${d.commit}\``;
                    if (d.gepusht !== undefined) {
                        summary += d.gepusht
                            ? '\n✅ **Push:** Erfolgreich zu GitHub'
                            : '\n⚠️ **Push:** Fehlgeschlagen – in Termux manuell pushen';
                    }
                    if (d.text_kurz) {
                        const lines = d.text_kurz.split('\n').filter(l => l.includes('Nächste') || l.includes('git pull') || l.includes('neustart'));
                        if (lines.length) summary += '\n\n' + lines.join('\n');
                    }
                }

                // Standard-Hinweis falls nichts geparst wurde
                if (!summary.includes('git')) {
                    summary += '\n\n📋 **Nächste Schritte in Termux:**\n`cd ~/it-ot-agentic-engineering && git pull origin main`\nDanach Server neustarten.';
                }

                addMessage(summary, 'assistant');
                scrollToBottom(true);
                clearInterval(_auftragTimer);
                _auftragTimer = null;
                // Auftrag beendet → Kommunikationskanal wieder frei.
                _laufenderAuftragKurz = null;
                aktualisiereStatusAnzeige();
            }
        } catch (_) {
            // Server kurz weg → ignorieren
        }
    }, 3000);
}

/** Rückfallweg auf den nicht-streamenden Endpunkt. */
async function sendMessageFallback(text, contentDiv, entry, zustand, vorleser) {
    const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: text,
            conversation_id: state.conversationId,
            web_search: state.webSearch,
            model: state.model,
            no_retention: state.noRetention,
            // WhatsApp-artiges Antwort-Zitat (falls gesetzt)
            antwort_auf: _antwortAuf ? _antwortAuf.text : undefined,
            // Auch im Fallback müssen Dateien mit – sonst fehlt das Bild
            // beim zweiten Versuch, wenn der Streaming-Weg scheiterte.
            files: state.pendingFiles.length > 0
                ? state.pendingFiles
                    .filter(f => f.type === 'image' || f.type === 'pdf')
                    .map(f => ({
                    id: f.id,
                    filename: f.filename,
                    type: f.type,
                    url: f.url,
                    mime: f.mime,
                    data_url: f.data_url,
                    text: f.text,
                }))
                : undefined,
        }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    zustand.text = data.reply;
    zustand.fertig = true;
    // Dateivorschau leeren – die Dateien wurden nun versendet
    if (state.pendingFiles.length > 0) _raeumeDateiVorschau();
    finishReply(contentDiv, entry, data.reply, data, vorleser);
    return data;
}


// ============================== GESICHTER-QUIZ (Anlernspiel) ==================
// Startet das spielerische Anlernen ueber die Lieblingsbilder: zeigt ein Bild,
// der Nutzer benennt die Person, die Antwort festigt das Gesicht als Referenz.
let _quizAktiv = false;
let _quizGesehen = [];   // bereits bearbeitete Bildpfade (um durchzuschreiten)
let _letzteQuizKarte = null;  // zuletzt erzeugte Quiz-Karte (fuer Ergebnis-Umschreiben)

// Zeichnet den gelben bbox-Rahmen um das Gesicht (Index `idx`) im Bild `img`
// und gibt die Markierung zurueck (oder null).
// Die Face-Engine liefert `bbox` als [x, y, w, h] in ORIGINAL-Pixeln -> die
// %-Position wird gegen die NATIV-Groesse des Bildes gerechnet (nicht gegen
// die gerenderte Breite, sonst verschiebt sich der Rahmen bei skalierten und
// bei max-height:300px gestauchten Bildern).
function markiereGesichtImBild(img, gesichter, idx) {
    if (!img) return null;
    const gs = gesichter || [];
    const b = (gs[idx] && gs[idx].bbox) || [];
    if (b.length < 4) return null;
    const pa = img.parentNode;
    if (!pa) return null;
    // alte Markierung im selben Bildbereich entfernen (Gruppen-Durchlauf)
    const alt = pa.querySelector('.quiz-marke');
    if (alt) alt.remove();
    let iw = img.naturalWidth || img.width || 0;
    let ih = img.naturalHeight || img.height || 0;
    if (!iw || !ih) {
        try {
            const rc = img.getBoundingClientRect();
            if (rc && rc.width > 0 && rc.height > 0) { iw = rc.width; ih = rc.height; }
        } catch (_) {}
    }
    if (!iw || !ih) return null;   // Bild noch nicht gerendert
    if (pa.style) {
        pa.style.position = 'relative';
        // Der Container darf die Markierung NICHT abschneiden (Scroll erlaubt
        // grosse Bilder scrollbar zu halten, ohne den Kasten zu beschneiden).
        // overflow wird nur gesetzt, wenn der Wrapper ihn nicht selbst hat.
    }
    // bbox erweitern, damit der Rahmen den GANZEN Kopf umschliesst (die
    // Face-Engine markiert oft nur das Gesichtsfeld: Kinn bis Haaransatz).
    // Oben mehr Platz (Haare/Kopf), unten etwas (Kinn); seitlich leicht. Werte
    // werden an den Bildrand geklemmt, damit der Rahmen nie aus dem Bild ragt.
    const bx = b[0], by = b[1], bw = b[2], bh = b[3];
    const erx = bw * 0.06;   // seitlich je 6%
    const ery = bh * 0.10;   // unten 10% (Kinn)
    const ert = bh * 0.28;   // oben 28% (Kopf/Haare)
    const nx = Math.max(0, bx - erx);
    const ny = Math.max(0, by - ert);
    const nw = Math.min(iw - nx, bw + erx * 2);
    const nh = Math.min(ih - ny, bh + erx * 2 + ert + ery);
    const r = document.createElement('div');
    r.className = 'quiz-marke';
    r.style.cssText = 'position:absolute;border:2px solid #ff6;box-shadow:0 0 0 1px #d80;pointer-events:none;z-index:5;box-sizing:border-box';
    r.style.left = (nx / iw * 100) + '%';
    r.style.top = (ny / ih * 100) + '%';
    r.style.width = (nw / iw * 100) + '%';
    r.style.height = (nh / ih * 100) + '%';
    pa.appendChild(r);
    // Kasten ins Sichtfeld holen, damit er beim Sprung zum naechsten Gesicht
    // sichtbar wird (nicht nur im verdeckten Randbereich eines grossen Bilds).
    try {
        // Naechsten scrollbaren Vorfahr (Element mit overflow:auto/scroll) suchen
        // und so ausrichten, dass die Marke mittig sichtbar wird.
        let node = pa;
        while (node && node !== document.body && node !== document.documentElement) {
            const st = getComputedStyle(node).overflowY;
            if (st === 'auto' || st === 'scroll') break;
            node = node.parentNode;
        }
        if (node && node !== pa && node.scrollLeft !== undefined) {
            const rect = r.getBoundingClientRect();
            const wrap = node.getBoundingClientRect();
            node.scrollLeft += (rect.left - wrap.left) - (wrap.width / 2);
            node.scrollTop  += (rect.top  - wrap.top ) - (wrap.height / 2);
        }
    } catch (_) {}
    return r;
}

// Schneidet das Gesicht (bbox; x,y,w,h in Original-Pixeln) aus `dataUrl` aus
// und liefert eine vergroesserte Daten-URL (JPEG). REIN im Arbeitsspeicher des
// Browsers (Canvas) — es wird NICHTS auf Platte geschrieben und nichts dauerhaft
// gespeichert. Wunsch Sebastian: keine Quizbilder auf dem Speicher sammeln.
function erzeugeGesichtCrop(dataUrl, bbox, maxPx) {
    return new Promise((resolve) => {
        try {
            const b = bbox || [];
            if (b.length < 4 || !dataUrl) return resolve(null);
            const img = new Image();
            img.onload = () => {
                let iw = img.naturalWidth || img.width || 0;
                let ih = img.naturalHeight || img.height || 0;
                if (!iw || !ih || iw <= 0 || ih <= 0) return resolve(null);
                let x = Math.max(0, Math.floor(b[0]));
                let y = Math.max(0, Math.floor(b[1]));
                let w = Math.min(Math.max(0, Math.floor(b[2])), iw - x);
                let h = Math.min(Math.max(0, Math.floor(b[3])), ih - y);
                if (w < 4 || h < 4) return resolve(null);
                // Prominenter Ausschnitt: auf maxPx hochskalieren
                const tm = maxPx || 240;
                const scale = tm / Math.max(w, h);
                const c = document.createElement('canvas');
                c.width = Math.max(4, Math.round(w * scale));
                c.height = Math.max(4, Math.round(h * scale));
                const ctx = c.getContext('2d');
                ctx.fillStyle = '#111';
                ctx.fillRect(0, 0, c.width, c.height);
                ctx.drawImage(img, x, y, w, h, 0, 0, c.width, c.height);
                resolve(c.toDataURL('image/jpeg', 0.9));
            };
            img.onerror = () => resolve(null);
            img.src = dataUrl;
        } catch (_) { resolve(null); }
    });
}

// Fuegt der Quiz-Karte den grossen, transienten Gesichts-Ausschnitt hinzu.
function zeigeGesichtCropIn(container, dataUrl, bbox, maxPx) {
    const box = document.createElement('div');
    box.style.cssText = 'text-align:center;margin:6px 0';
    const lbl = document.createElement('div');
    lbl.style.cssText = 'font-size:0.75rem;color:#ff6;margin-bottom:2px';
    lbl.textContent = '🔍 Gesicht-Ausschnitt, den du beschriftest:';
    const cimg = document.createElement('img');
    cimg.alt = 'Gesicht';
    cimg.style.cssText = 'max-width:100%;max-height:240px;border:1px solid #555;border-radius:10px;background:#000';
    box.appendChild(lbl);
    box.appendChild(cimg);
    if (container) container.appendChild(box);
    macheBildAntippbar(cimg);  // Tipp auf Ausschnitt -> Vollbild
    erzeugeGesichtCrop(dataUrl, bbox, maxPx || 240).then(u => { if (u) cimg.src = u; });
    return box;
}

// Bild-Vollbild (WhatsApp-nahe): Ein Tipp auf ein Quiz-/Chat-Bild oeffnet ein
// dunkles Fullscreen-Overlay mit dem grossen Bild. Das Bild ist NATIV per
// Zwei-Finger-Pinch zoombar (touch-action/gestures frei) — Tippen auf das
// Bild selbst zoomt NICHT sofort zu (kein Button-Overlay). Geschlossen wird
// ueber das X oben rechts oder Tipp auf den dunklen Rand.
let _quizVollbild = null;
// RAM-Editor-Zustand: vom Nutzer im Vollbild korrigierte Gesichts-Boxen
// (Wunsch Sebastian 2026-09-09: Rahmen antippen/verschieben/löschen). Die
// bbox-Werte (in Original-Pixeln) liest die Antwort-Logik (quizBeantworten /
// antworten) beim Senden aus, damit das korrigierte Gesicht ans Backend
// geht und die Erkennung sauberer wird. NUR im Arbeitsspeicher flüchtig.
let _quizEditor = null;   // { muenzen_bools: [], bbox_live: [[x,y,w,h], ...] }
function zeigeBildVollbild(imgEl, gesichter) {
    if (!imgEl) return;
    const src = imgEl.src || (imgEl.getAttribute && imgEl.getAttribute('src')) || '';
    if (!src) return;
    if (_quizVollbild) { schliesseBildVollbild(); return; }
    // Editor-Initialisierung an den aktuellen Gesichten (nur falls nicht
    // schon ein laufender Editor existiert — beim erneuten Oeffnen fundiert).
    if (!_quizEditor) {
        _quizEditor = { bbox_live: [] };
    }
    if (gesichter && gesichter.length) {
        const vor = _quizEditor.bbox_live || [];
        const neu = [];
        for (let i = 0; i < gesichter.length; i++) {
            if (i < vor.length && vor[i] === null) { neu.push(null); continue; }  // geloescht bleibt geloescht
            if (i < vor.length && Array.isArray(vor[i]) && vor[i].length >= 4) { neu.push(vor[i]); continue; }  // live-Aenderung
            neu.push(gesichter[i].bbox || []);
        }
        _quizEditor.bbox_live = neu;
    }
    const ov = document.createElement('div');
    _quizVollbild = ov;
    ov.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.93);z-index:99998;display:flex;align-items:center;justify-content:center;flex-direction:column;animation:fadeIn 0.2s ease';
    // X-Button zum Schliessen (Tipp aufs Bild zoomt per Pinch, nicht schliessen)
    const x = document.createElement('div');
    x.style.cssText = 'position:fixed;top:12px;right:16px;z-index:99999;width:38px;height:38px;border-radius:50%;background:rgba(0,0,0,.5);color:#fff;font-size:20px;display:flex;align-items:center;justify-content:center;cursor:pointer';
    x.textContent = '✕';
    x.addEventListener('click', schliesseBildVollbild);
    // Wrapper fuer das Bild: native pinch-zoom erlauben; das Bild liegt in einer
    // position:relative-`bildBox`, damit die Overlay-Rahmen exakt am Bild
    // haften (auch bei Hoch-/Querformatwechsel — Wunsch Sebastian: Kästen
    // müssen immer zu den Personen passen).
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;align-items:center;justify-content:center;overflow:auto;width:100%;height:100%;touch-action:manipulation';
    const bildBox = document.createElement('div');
    bildBox.style.cssText = 'position:relative;display:inline-block;line-height:0;touch-action:manipulation';
    const big = document.createElement('img');
    big.src = src;
    big.alt = 'Vollbild';
    big.style.cssText = 'max-width:100%;max-height:100%;object-fit:contain;touch-action:manipulation;user-select:none';
    bildBox.appendChild(big);
    wrap.appendChild(bildBox);
    ov.appendChild(x);
    ov.appendChild(wrap);
    // "Nächstes Bild ➡️"-Steuerung im Vollbild (Vollbild-Durchlauf, 2026-09-10):
    // erspart das Schliessen, um zur naechsten Quizrunde zu gelangen. Erscheint
    // NUR waehrend einer aktiven Quiz-Sitzung (_quizAktiv). Beim Klick wird eine
    // evtl. noch offene Frage des aktuellen Bildes als 'uebersprungen' persistiert
    // und die naechste Runde geladen; das neue Bild oeffnet sich danach direkt
    // wieder als Vollbild (idealer Durchlauf).
    if (_quizAktiv && _quizGesehen && _quizGesehen.length) {
        const weiterBtn = document.createElement('div');
        weiterBtn.style.cssText = 'position:fixed;left:auto;right:auto;width:auto;bottom:18px;z-index:99999;text-align:center;padding:12px 26px;border-radius:30px;background:#1f3a2a;border:1px solid #2e8b57;color:#9f9;font-weight:700;font-size:0.95rem;cursor:pointer;box-shadow:0 3px 12px rgba(0,0,0,.6);left:50%;transform:translateX(-50%)';
        weiterBtn.textContent = 'Nächstes Bild ➡️';
        weiterBtn.addEventListener('click', (ev) => { ev.stopPropagation(); naechstesBildAusVollbild(); });
        ov.appendChild(weiterBtn);
    }
    // Korrigierbare Gesicht-Rahmen ins Vollbild (Wunsch Sebastian 2026-09-09):
    // jeder Rahmen antippbar -> Auswahl + Loeschen; mit Finger verschiebbar
    // (Drag). Die Positionen speichern live in `_quizEditor.bbox_live`
    // (Original-Pixel), damit die Antwort-Logik das korrigierte Gesicht an
    // das Backend melden kann (fuehrt zu saubererer Erkennung).
    try {
        if (gesichter && gesichter.length) {
            big.addEventListener('load', () => {
                var iw = big.naturalWidth || 0, ih = big.naturalHeight || 0;
                if (!iw || !ih) return;
                var sel = -1;
                var rahmenEls = [];
                for (var i = 0; i < gesichter.length; i++) {
                    var re = document.createElement('div');
                    re.setAttribute('data-frei', String(i));
                    re.style.cssText = 'position:absolute;border:2px solid #ff6;z-index:7;box-sizing:border-box;cursor:pointer;touch-action:manipulation';
                    var marke = document.createElement('div');
                                        marke.style.cssText = 'position:absolute;top:-18px;right:-14px;width:20px;height:20px;border-radius:50%;background:#d33;color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center;cursor:pointer';
                                        marke.textContent = '✕';
                                        // idx via Closure binden (Bugfix 2026-09-10: vorher stand
                                        // fälschlich `idx` im Scope, das war undefined -> ✕ tat nichts)
                                        (function(ix){
                                            marke.addEventListener('click', function(ev){
                                                ev.stopPropagation();
                                                _quizEditor.bbox_live[ix] = null;
                                                resync();
                                            });
                                        })(i);
                                        re.appendChild(marke);
                    bildBox.appendChild(re);
                    rahmenEls.push(re);
                }
                // Positionen setzen: bildBox wird exakt auf die GERICHTETE Bildgroesse des
                // `big`-Bilds gelegt (getBoundingClientRect), die Rahmen damit in
                // px bezogen auf bildBox. So bleiben die Kästen auch bei Hoch-/
                // Querformatwechsel korrekt an den Personen (Wunsch Sebastian).
                var letzteBigW = 0, letzteBigH = 0;
                function resync() {
                    var bboxes = _quizEditor.bbox_live || [];
                    // aktuelle gerenderete Bildbox ermitteln
                    try {
                        var rb = big.getBoundingClientRect();
                        if (rb && rb.width > 0 && rb.height > 0) {
                            letzteBigW = rb.width; letzteBigH = rb.height;
                        }
                    } catch (_e) {}
                    if (letzteBigW <= 0 || letzteBigH <= 0) return;
                    // bildBox auf die Bildgroesse festnageln (left/top gesetzt)
                    bildBox.style.width = letzteBigW + 'px';
                    bildBox.style.height = letzteBigH + 'px';
                    for (var i = 0; i < rahmenEls.length; i++) {
                        var b = bboxes[i] || [];
                        var el = rahmenEls[i];
                        if (!b || b.length < 4) { el.style.display = 'none'; continue; }
                        el.style.display = 'block';
                        // bbox ist in NATIVEN Pixeln; Skala = gerendert/nativ
                        var skw = letzteBigW / (iw || 1);
                        var skh = letzteBigH / (ih || 1);
                        el.style.left = (b[0] * skw) + 'px';
                        el.style.top = (b[1] * skh) + 'px';
                        el.style.width = (b[2] * skw) + 'px';
                        el.style.height = (b[3] * skh) + 'px';
                        el.style.borderColor = (i === sel) ? '#4f4' : '#ff6';
                    }
                }
                // Griffe (Ecken+Seiten) für den AUSGEWÄHLTEN Rahmen: damit kann
                // man den Rahmen größer/kleiner ziehen (Wunsch Sebastian
                // 2026-09-10). Jeder Griff skaliert die bbox in Original-Pixeln.
                var griffe = [];
                function baueGriffe(reIdx) {
                    // alte Griffe entfernen
                    for (var g of griffe) { try { g.el.remove(); } catch(_e){} }
                    griffe = [];
                    if (reIdx < 0) return;
                    var b = (_quizEditor.bbox_live[reIdx] || []);
                    if (b.length < 4) return;
                    var skw = letzteBigW / (iw || 1), skh = letzteBigH / (ih || 1);
                    var pos = [
                        ['tl', 0, 0], ['tr', 1, 0], ['bl', 0, 1], ['br', 1, 1],
                        ['t', 0.5, 0], ['b', 0.5, 1], ['l', 0, 0.5], ['r', 1, 0.5]
                    ];
                    for (var p of pos) {
                        var g = document.createElement('div');
                        var x = b[0] * skw + (p[2] === 0 ? 0 : (p[2] === 1 ? b[2]*skw : b[2]*skw/2));
                        var y = b[1] * skh + (p[1] === 0 ? 0 : (p[1] === 1 ? b[3]*skh : b[3]*skh/2));
                        // mittig an der Eck-/Seiten-Position
                        g.style.cssText = 'position:absolute;width:22px;height:22px;z-index:9;background:rgba(30,30,30,.0);border:2px solid #fff;border-radius:50%;box-sizing:border-box;cursor:nwse-resize;transform:translate(-50%,-50%)';
                        g.style.left = x + 'px';
                        g.style.top = y + 'px';
                        g.dataset.griff = p[0];
                        bildBox.appendChild(g);
                        griffe.push({ el: g, name: p[0] });
                    }
                }
                // zeigt Griffe beim Auswählen / versteckt bei keiner Auswahl
                function zeigeAuswahlGriffe() { baueGriffe(sel); }

                // Auswahl + Drag-Target (Verschieben NUR am Rahmenkörper) +
                // Größen-Griffe + Pinch-Zoom des ausgewählten Rahmens
                for (var i = 0; i < rahmenEls.length; i++) {
                    rahmenEls[i].addEventListener('pointerdown', (function(idx){
                        return function(ev){
                            sel = idx; resync(); zeigeAuswahlGriffe();
                            var reEl = rahmenEls[idx];
                            var startX = ev.clientX, startY = ev.clientY;
                            var b = (_quizEditor.bbox_live[idx] || []).slice();
                            // Pinch: 2. Finger kommt rein -> Rahmengröße zoomen
                            var finger2Start = null;
                            var bewegen = function(mev){
                                if (mev.buttons && mev.buttons > 2) return;
                                var dx = mev.clientX - startX, dy = mev.clientY - startY;
                                var rb = reEl.getBoundingClientRect();
                                var px_per_w = (b[2]) / (rb.width || 1);
                                var px_per_h = (b[3]) / (rb.height || 1);
                                _quizEditor.bbox_live[idx] = [
                                    Math.max(0, b[0] + dx*px_per_w),
                                    Math.max(0, b[1] + dy*px_per_h),
                                    b[2], b[3]
                                ];
                                resync(); zeigeAuswahlGriffe();
                            };
                            reEl.setPointerCapture && reEl.setPointerCapture(ev.pointerId);
                            var loslassen = function(){
                                try { reEl.releasePointerCapture && reEl.releasePointerCapture(ev.pointerId); } catch(_e){}
                                wrap.removeEventListener('pointermove', bewegen);
                                wrap.removeEventListener('pointerup', loslassen);
                                wrap.removeEventListener('pointercancel', loslassen);
                                wrap.removeEventListener('lostpointercapture', loslassen);
                            };
                            wrap.addEventListener('pointermove', bewegen);
                            wrap.addEventListener('pointerup', loslassen);
                            wrap.addEventListener('pointercancel', loslassen);
                            wrap.addEventListener('lostpointercapture', loslassen);
                        };
                    })(i));
                }
                // Griff-Drag: Größe ziehen (skaliert bbox an Rand-/Eckenloser)
                wrap.addEventListener('pointerdown', (ev) => {
                    var g = ev.target;
                    if (!g || !g.dataset || !g.dataset.griff || sel < 0) return;
                    ev.stopPropagation();
                    var griffName = g.dataset.griff;
                    var startX = ev.clientX, startY = ev.clientY;
                    var sx = ev.clientX, sy = ev.clientY;
                    var aktB = (_quizEditor.bbox_live[sel] || []).slice();
                    var skw2 = letzteBigW / (iw || 1), skh2 = letzteBigH / (ih || 1);
                    var bewegenGr = (mev) => {
                        var dx = (mev.clientX - sx) / (skw2 || 1);   // Original-px
                        var dy = (mev.clientY - sy) / (skh2 || 1);
                        var nx = aktB[0], ny = aktB[1], nw = aktB[2], nh = aktB[3];
                        if (griffName.indexOf('l') !== -1){ nx = aktB[0] + dx; nw = aktB[2] - dx; }
                        if (griffName.indexOf('r') !== -1){ nw = aktB[2] + dx; }
                        if (griffName.indexOf('t') !== -1){ ny = aktB[1] + dy; nh = aktB[3] - dy; }
                        if (griffName.indexOf('b') !== -1){ nh = aktB[3] + dy; }
                        if (nw > 8) _quizEditor.bbox_live[sel] = [Math.max(0, nx), Math.max(0, ny), nw, nh];
                        resync(); zeigeAuswahlGriffe();
                    };
                    var losGr = () => {
                        wrap.removeEventListener('pointermove', bewegenGr);
                        wrap.removeEventListener('pointerup', losGr);
                    };
                    wrap.addEventListener('pointermove', bewegenGr);
                    wrap.addEventListener('pointerup', losGr);
                }, true);
                resync();
                // Bei Formatwechsel (Hoch/Quer) die Kästen neu an das gerenderte
                // Bild koppeln (Wunsch Sebastian: Kästen müssen stimmen).
                const _neuLayouten = () => { try { resync(); } catch (_e) {} };
                window.addEventListener('resize', _neuLayouten);
                window.addEventListener('orientationchange', _neuLayouten);
                // einmal kurz nach dem vollständigen Layout sicherstellen
                setTimeout(_neuLayouten, 250);
            });
        }
    } catch (_) {}
    document.body.appendChild(ov);
}
function schliesseBildVollbild() {
    if (_quizVollbild) {
        try { _quizVollbild.remove(); } catch (e) {}
        _quizVollbild = null;
    }
}

// Findet in einer Quiz-Karte das HAUPT-Quizbild (Vollbild-Quelle). Die Karte
// enthaelt bei einem Einzelgesicht auch den kleinen 'Gesicht-Ausschnitt'
// (erzeugeGesichtCrop), daher waehlen wir das groesste Bild nach NATIV-Flaechen-
// grosse — der Crop hat kleinere natuerliche Masse, das Hauptbild ist groesser.
function findeHauptQuizBild(karte) {
    if (!karte) return null;
    try {
        const imgs = Array.from(karte.querySelectorAll('img'));
        if (!imgs.length) return null;
        let best = imgs[0], bestFl = -1;
        for (const im of imgs) {
            const w = im.naturalWidth || im.width || 0;
            const h = im.naturalHeight || im.height || 0;
            const fl = (w && h) ? (w * h) : 0;
            if (fl > bestFl) { bestFl = fl; best = im; }
        }
        return best;
    } catch (_e) { return null; }
}

// Vom Vollbild aus zur naechsten Quizrunde (Vollbild-Durchlauf, 2026-09-10):
// beendet die aktuelle Runde und laedt die naechste, ohne das Vollbild zu
// verlassen. Eine noch offene Ja/Nein-Frage des aktuellen Bildes wird beim
// Durchklicken als 'uebersprungen' persistiert (POST /api/gesichter/quiz/antwort
// mit ueberspringen:true), damit sie nicht blind verloren geht. Danach wird das
// neue Bild direkt wieder als Vollbild geoeffnet (idealer Durchlauf). Funktioniert
// fuer Einzelbild (anzahl_gesichter 0/1) und Gruppenbild (>=2, starteGruppenQuiz)
// gleichermassen, da die Analyse je Runde einheitlich ueber naechsteQuizRunde laeuft.
async function naechstesBildAusVollbild() {
    // (a) evtl. offene Frage des aktuellen Bildes als 'uebersprungen' sichern.
    //     Der aktuelle Bildpfad ist der zuletzt von naechsteQuizRunde erfasste.
    const aktuellerPfad = (_quizGesehen && _quizGesehen.length)
        ? _quizGesehen[_quizGesehen.length - 1] : null;
    if (aktuellerPfad) {
        try {
            fetch(`${API_BASE}/api/gesichter/quiz/antwort`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bild_pfad: aktuellerPfad, person: '', ist_neu: false, rolle: '', ueberspringen: true }),
            }).catch(() => {});
        } catch (_e) {}
    }
    // Vollbild schliessen; die naechste Runde wird gleich wieder geoeffnet.
    schliesseBildVollbild();
    // (b) naechste Runde laden; sobald das neue Bild gerendert ist, es wieder
    //     als Vollbild anzeigen (Callback von naechsteQuizRunde).
    naechsteQuizRunde((imgNeu, gesichterNeu) => {
        if (imgNeu && imgNeu.src) {
            try { zeigeBildVollbild(imgNeu, gesichterNeu || []); } catch (_e) {}
        }
    });
}

// Macht ein <img> antippbar (Vollbild) - nutzt den nativen dataURL-String,
// den das Quiz-Bild bereits im DOM haelt.
function macheBildAntippbar(imgEl, gesichter) {
    if (!imgEl) return;
    try {
        imgEl.style.cursor = 'zoom-in';
        imgEl.addEventListener('click', (ev) => {
            ev.stopPropagation();
            zeigeBildVollbild(imgEl, gesichter);
        });
    } catch (_) {}
}

// Einheitliche Quiz-Button-Stile (Sebastian: aufgeraeumt, keine wilden Styles):
// typ = 'person' (bekannte Person, grün) | 'neu' (neue Person, rot) |
//       'skip' (ueberspringen, grau) | 'akt' (primär-Aktion, grün markant)
function macheQuizButton(text, typ, onclick) {
    const b = document.createElement('button');
    b.textContent = text;
    const basis = 'border-radius:9px;font-size:0.84rem;cursor:pointer;font-weight:600';
    const farben = {
        person:  'border:1px solid #2e8b57;background:#1f3a2a;color:#8f8',
        akt:     'border:1px solid #2e8b57;background:#2a5338;color:#9f9',
        neu:     'border:1px solid #f88;background:#2a1515;color:#f88',
        skip:    'border:1px solid #666;background:#2b2b2b;color:#bbb',
    };
    b.style.cssText = basis + ';' + (farben[typ] || farben.person);
    if (onclick) b.onclick = onclick;
    return b;
}

// Kleine Abschnitts-Überschrift innerhalb der Quiz-Karte fuer klare Struktur.
function macheQuizLabel(text) {
    const s = document.createElement('div');
    s.style.cssText = 'margin:8px 0 4px;font-size:0.7rem;letter-spacing:.03em;color:#9f9;opacity:.75;text-transform:uppercase';
    s.textContent = text;
    return s;
}

/** Baut die "Suche andere Person"-Eingabe mit LIVE-Vorschlägen, wie sie in
 *  Einzelbild- UND Gruppenbild-Quiz einheitlich erscheint (Wunsch Sebastian:
 *  Optionen nach Wahrscheinlichkeit, 5 Kacheln + Suche). Liefert einen <div>
 *  mit Eingabefeld + darunter filtern de Vorschlags-Kacheln; Enter/Klick sendet
 *  den gewählten Namen über `onwaehl`. */
function baueSuchMitVorschlaegen(alleNamen, onwaehl) {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:relative;margin-top:6px';
    // Eingabefeld mit Dropdown (Suchmaschinen-/Autocomplete-Stil):
    // Beim Tippen erscheinen die Treffer als auswählbare Optionen darunter.
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.autocomplete = 'off';
    inp.placeholder = '🔍 Andere Person suchen…';
    inp.style.cssText = 'width:100%;padding:7px 10px;border:1px solid #2e8b57;border-radius:8px;background:#0e1a14;color:inherit;font-size:0.85rem';
    wrap.appendChild(inp);
    const dd = document.createElement('div');
    dd.style.cssText = 'position:absolute;top:100%;left:0;right:0;z-index:50;max-height:240px;overflow-y:auto;background:#0b1a12;border:1px solid #2e8b57;border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.55)';
    dd.style.display = 'none';
    wrap.appendChild(dd);
    const zeigen = (sichtbar) => { dd.style.display = sichtbar ? 'block' : 'none'; };
    const aktualisieren = () => {
        const q = (inp.value || '').trim().toLowerCase();
        dd.innerHTML = '';
        const treffer = (alleNamen || []).filter(n => {
            const t = (n || '').toLowerCase();
            return !q || t.indexOf(q) !== -1;
        });
        if (!q || !treffer.length) { zeigen(false); return; }
        treffer.slice(0, 8).forEach(n => {
            const opt = document.createElement('div');
            opt.textContent = '👤  ' + n;
            opt.style.cssText = 'padding:7px 10px;cursor:pointer;display:flex;align-items:center;border-bottom:1px solid #1f3a2a;font-size:0.85rem;color:#eee';
            opt.addEventListener('pointerup', (ev) => {
                ev.stopPropagation();
                onwaehl(n.trim());
                inp.value = '';
                dd.innerHTML = '';
                zeigen(false);
            });
            dd.appendChild(opt);
        });
        zeigen(true);
    };
    inp.addEventListener('input', aktualisieren);
    inp.addEventListener('focus', (e) => { if ((inp.value||'').trim()) aktualisieren(); });
    inp.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { zeigen(false); }
        if (e.key === 'Enter') {
            const n = (inp.value || '').trim();
            if (n) { onwaehl(n); inp.value=''; dd.innerHTML=''; zeigen(false); }
        }
        // Pfeil-Highlight (basisch): erster Treffer bei Enter->Pfeilunten
        if (e.key === 'ArrowDown' && dd.children && dd.children.length) {
            e.preventDefault();
            const erster = dd.children[0];
            erster.style.background = '#1f3a2a';
        }
    });
    // beim Wegklicken schliessen
    inp.addEventListener('blur', () => setTimeout(() => zeigen(false), 150));
    return wrap;
}

function starteGruppenQuiz(frageEl, karte, img, dataUrl, pfad, optionen, gesichter, erkannte) {
    // Gruppenbild (>=2 Gesichter): jedes Gesicht einzeln markieren + beschriften.
    const gs = gesichter || [];
    let idx = 0;
    // Bereits gestellte Vermutungen dieses BILDES: dieselbe Person nur EINMAL
    // fragen (Stand 2026-09-09, Auftrag Sebastian). Sonst erscheint bei
    // zwei Gesichts-Boxen derselben Person die Frage doppelt — und eine
    // falsche Vermutung (lockere Erkennungsschwelle) verwirrt doppelt.
    const geseheneVermutungen = new Set();
    // Beim Durchlauf gesammelte Personen für die Abschluss-Bildunterschrift
    // ("… das ist Person1, Person2") — Wunsch Sebastian 2026-09-09.
    const verarbeitetePersonen = [];
    const umbruch = document.createElement('div');
    umbruch.style.cssText = 'margin-top:8px;padding:10px;border:1px solid #2e8b57;border-radius:10px;background:#0f1f14';
    karte.appendChild(umbruch);

    function maleRahmen() {
        markiereGesichtImBild(img, gs, idx);
    }
    try { img.addEventListener('load', () => maleRahmen()); } catch (_) {}

    // Fortschritt + aktuelles Gesicht markieren
    function zeigeFortschritt() {
        umbruch.innerHTML = '';
        const fortschritt = document.createElement('div');
        fortschritt.style.cssText = 'font-size:0.78rem;color:#9f9;font-weight:600';
        fortschritt.textContent = `Gesicht ${idx+1} von ${gs.length}`;
        umbruch.appendChild(fortschritt);
    }

    // Vermutungs-Frage für das aktuelle Gesicht (falls eine vorliegt).
    // Wenn ja -> direkte Antwort; wenn nein -> Antwort-Zeile einblenden.
    function zeigeVermutungsFrage() {
        const g = gs[idx] || {};
        const vm = g.vermutung || null;
        // Keine Vermutung für dieses Gesicht: Beim Wechsel NICHT automatisch
        // die volle Chip-Liste zeigen (das wirkte wie 'immer dieselbe Frage
        // mehrfach'). Stattdessen nur Fortschritt + gelber Rahmen + ein
        // dezenter Aufklapp-Knopf; die Namens-Chips erscheinen erst auf
        // Wunsch (Stand 2026-09-09, Auftrag Sebastian).
        if (!vm || !vm.person) {
            const aufklapp = macheQuizButton('✏️ Dieses Gesicht benennen', 'person', () => {
                aufklapp.remove();
                zeigeAntwortZeile();
            });
            umbruch.appendChild(aufklapp);
            return;
        }
        // Vermutung da: dieselbe Person nur EINMAL als Ja/Nein-Frage stellen;
        // wurde sie bei einem früheren Gesicht schon gefragt, direkt zur
        // Antwortauswahl (keine doppelte/wiederholte "Ist das X?"-Frage).
        if (geseheneVermutungen.has(vm.person)) {
            zeigeAntwortZeile();
            return;
        }
        geseheneVermutungen.add(vm.person);
        baueVermutungsBox(vm);
    }
        // Baut die "Ist das X?"-Ja/Nein-Box für eine Vermutung und zeigt sie.
    // Pro Bild wird jede vermutete Person nur EINMAL gefragt (Set oben);
    // nach "Nein" klappt die Antwortauswahl auf (zeigeAntwortZeile).
    function baueVermutungsBox(v) {
        const box = document.createElement('div');
        box.style.cssText = 'margin-top:6px;padding:8px;border:1px solid #2e8b57;border-radius:9px;background:#12251a';
        const sh = (v.sicherheit || '');
        const txt = document.createElement('div');
        txt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600';
        txt.textContent = `🔎 Ist das ${v.person}?` + (sh ? ` (Sicherheit: ${sh})` : '');
        box.appendChild(txt);
        const zeile = document.createElement('div');
        zeile.style.cssText = 'display:flex;gap:6px;margin-top:6px;flex-wrap:wrap';
        zeile.appendChild(macheQuizButton('✅ Ja', 'akt', () => antworten(v.person, false, false)));
        zeile.appendChild(macheQuizButton('❌ Nein', 'neu', () => {
            box.remove();
            zeigeAntwortZeile();
        }));
        box.appendChild(zeile);
        // "Keine Person vorhanden" soll IMMER direkt unter Ja/Nein stehen
        // (Wunsch Sebastian 2026-09-09) - springt SOFORT zum nächsten BILD
        // (persistiert erledigt + naechsteQuizRunde), nicht zum nächsten
        // Gesicht.
        const skipDirekt = macheQuizButton('🚫 Keine Person vorhanden', 'skip', () => markiereBildErledigt());
        skipDirekt.style.cssText += ';margin-top:6px;width:100%;text-align:center';
        box.appendChild(skipDirekt);
        umbruch.appendChild(box);
    }

    // Antwort-Zeile (Person wählen / neu / überspringen)
    function zeigeAntwortZeile() {
        const label = macheQuizLabel('Dieses Gesicht gehört zu:');
        umbruch.appendChild(label);
        const zeile = document.createElement('div');
        zeile.style.cssText = 'display:flex;flex-direction:column;gap:6px';
        // Optionen sortiert (Backend nach Wahrscheinlichkeit) — nur die ersten
        // 5 als Kacheln, konsistent zum Einzelbild (Wunsch Sebastian).
        const kacheln = document.createElement('div');
        kacheln.style.cssText = 'display:flex;flex-direction:column;gap:6px';
        (optionen || []).slice(0, 5).forEach(o => {
            const b = macheQuizButton(o, 'person', () => antworten((o||'').trim(), false, false));
            kacheln.appendChild(b);
        });
        if ((optionen || []).length > 5) {
            const mehr = document.createElement('div');
            mehr.style.cssText = 'font-size:0.72rem;color:#9f9;opacity:.8;margin-top:2px';
            mehr.textContent = `… und ${(optionen || []).length - 5} weitere (siehe Suche).`;
            kacheln.appendChild(mehr);
        }
        zeile.appendChild(kacheln);
        // "Suche andere Person": freie Eingabe mit Live-Vorschlägen (wie Einzelbild)
        zeile.appendChild(baueSuchMitVorschlaegen(optionen, (n) => antworten(n, false, false)));
        // 'Neue Person' als volle, aufklappbare Eingabebox (Name + Rolle + EIN
        // Textfeld für alle Infos) — gleiches Menue wie im Einzelbild-Quiz.
        // Beschreibung/Lebensinfos war doppelt gemoppelt, alles geht in das
        // Infos-Feld (Wunsch Sebastian 2026-09-09).
        const neuBtn = macheQuizButton('➕ Neue Person', 'neu', null);
        const form = document.createElement('div');
        form.style.display = 'none';
        form.style.cssText = 'display:none;margin:8px 0;padding:10px;border:2px solid #f88;border-radius:10px;background:#221010';
        const inp = document.createElement('input');
        inp.placeholder = 'Name* (z. B. Julian)';
        inp.style.cssText = 'width:100%;padding:7px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.88rem';
        const inpRolle = document.createElement('input');
        inpRolle.placeholder = 'Rolle / Bedeutung (z. B. Bruder, Mutter)';
        inpRolle.style.cssText = 'width:100%;padding:7px;margin-top:6px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.88rem';
        const bezWrap = document.createElement('div');
        bezWrap.style.cssText = 'display:flex;align-items:center;gap:4px;margin-top:6px';
        const inpBez = document.createElement('textarea');
        inpBez.placeholder = 'Infos über die Person — Beziehung + alles, was du weißt (Diktat möglich)';
        inpBez.rows = 2;
        inpBez.style.cssText = 'width:100%;padding:7px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.85rem;resize:vertical;flex:1';
        bezWrap.appendChild(inpBez);
        fuegeFeldMikrofonHinzu(inpBez, bezWrap, 'Infos über die Person diktieren');
        const speichern = macheQuizButton('✅ Person speichern', 'neu', () => {
            const n = (inp.value || '').trim();
            if (!n) { inp.style.borderColor = '#f55'; return; }
            // rolle/beziehung an das Backend durchreichen (beschreibung leer)
            antworten(n, true, false, (inpRolle.value || '').trim(), (inpBez.value || '').trim(), '');
        });
        speichern.style.cssText += ';margin-top:8px;width:100%;padding:8px';
        form.appendChild(inp);
        form.appendChild(inpRolle);
        form.appendChild(bezWrap);
        form.appendChild(speichern);
        neuBtn.onclick = () => { form.style.display = form.style.display === 'none' ? 'block' : 'none'; };
        zeile.appendChild(neuBtn);
        umbruch.appendChild(form);
        const skip = macheQuizButton('🚫 Keine Person vorhanden', 'skip', () => antworten('', true, true));
        skip.style.cssText += ';margin-top:6px;width:100%;text-align:center';
        umbruch.appendChild(zeile);
        umbruch.appendChild(skip);
    }

    function weiter() {
        // letztes Gesicht des Bildes fertig -> automatisch naechstes Bild.
        // Davor das Bild EINMAL als 'gesehen/uebersprungen' persistieren
        // (POST ans Backend), damit NICHT nur-gruppenskippte Bilder bei einem
        // Server-Neustart erneut erscheinen -> keine staendigen
        // Bildwiederholungen (Wunsch Sebastian 2026-09-09).
        if (idx >= gs.length - 1) {
            markiereBildErledigt();
            return;
        }
        idx++;
        maleRahmen();        // Kasten springt zum naechsten Gesicht im Hauptbild
        zeigeFortschritt();
        zeigeVermutungsFrage(); // erst Ja/Nein, bei Nein dann Chips
    }

    // Markiert das Gruppenbild beim Durchlaufen als persistent 'gesehen'
    // (uebersprungen), wenn nicht jede Person einzeln benannt wurde. Verhindert
    // Wiederholungen derselben Bilder im Quiz. NUR der Bild-Pfad geht raus.
    // Zeigt danach die Karte als BILD + Bildunterschrift "… das ist Person1,
    // Person2" an (Wunsch Sebastian 2026-09-09): Menü- und Beenden-Buttons
    // verschwinden (überflüssig), die nächste Quizrunde kommt als NEUE
    // Chatblase darunter (naechsteQuizRunde).
    function markiereBildErledigt() {
        // ganze Karte leeren (inkl. Kopf mit Menü/Beenden) -> Bildunterschrift
        karte.innerHTML = '';
        // Bildtitel (Menü) weg, dafür direkt das Bild + Bildunterschrift
        const zeile = document.createElement('div');
        zeile.style.cssText = 'padding:8px;border:1px solid #2e8b57;border-radius:10px;background:#0f1f14;font-weight:600;color:#8f8';
        zeile.textContent = '✅ Alle Personen dieses Bildes verarbeitet.';
        karte.appendChild(zeile);
        const cap = document.createElement('div');
        cap.style.cssText = 'margin-top:6px;padding:6px;border:1px solid #4a7;border-radius:8px;background:#0f1f14';
        const capImg = document.createElement('img');
        capImg.src = dataUrl || '';
        capImg.alt = 'Quiz-Bild';
        capImg.style.cssText = 'display:block;max-width:100%;max-height:220px;border-radius:8px;border:1px solid #4a7';
        cap.appendChild(capImg);
        const capTxt = document.createElement('div');
        capTxt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600;margin-top:4px';
        capTxt.textContent = (verarbeitetePersonen && verarbeitetePersonen.length)
            ? '… das ist ' + verarbeitetePersonen.join(', ')
            : '… keine Person zugeordnet';
        cap.appendChild(capTxt);
        karte.appendChild(cap);
        try {
            fetch(`${API_BASE}/api/gesichter/quiz/antwort`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bild_pfad: pfad, person: '', ist_neu: false, rolle: '', ueberspringen: true }),
            }).catch(() => {});
        } catch (_) {}
        setTimeout(() => { try { naechsteQuizRunde(); } catch (_) {} }, 1600);
    }

    function antworten(person, istNeu, skip, rolle, beziehung, beschreibung) {
        if (skip) { weiter(); return; }
        // Person für die Abschluss-Bildunterschrift sammeln (einmalig je Name)
        if (person && verarbeitetePersonen.indexOf(person) === -1) verarbeitetePersonen.push(person);
        // SOFORT sichtbares Feedback (Wunsch Sebastian 2026-09-09): Den
        // Umbruch-Bereich auf eine grüne Bestätigung umschalten, damit der
        // Klick sofort sichtbar ist, bevor die Server-Antwort/der Folge-Start
        // das Bild wechseln.
        umbruch.innerHTML = '';
        const best = document.createElement('div');
        best.style.cssText = 'font-size:0.85rem;color:#9f9;font-weight:600;margin-top:2px';
        best.textContent = '✓ Gespeichert (' + (person || 'Person') + ') – weiter…';
        umbruch.appendChild(best);
        // Live-korrigierte bbox des aktuellen Gesichts (idx) mitsenden, falls
        // der Nutzer den Rahmen im Vollbild verändert hat
        let liveBbox = null;
        try {
            if (_quizEditor && _quizEditor.bbox_live && Array.isArray(_quizEditor.bbox_live[idx])
                && _quizEditor.bbox_live[idx].length >= 4) liveBbox = _quizEditor.bbox_live[idx];
        } catch (_e) {}
        quizBeantwortenSilent(pfad, person, istNeu, rolle || '', beziehung || '', beschreibung || '', liveBbox).then(() => weiter());
    }

    zeigeFortschritt();
    zeigeVermutungsFrage();
    maleRahmen();
}

function zeigeQuizKarte(pfad, name, dataUrl, optionen, vermutung, anzahl, erkannte, gesichter, zielContainer) {
    // ML-Quiz-Karte: KI stellt eine Vermutung vor, der Nutzer bestaetigt/korrigiert.
    // Aufgeraeumtes Layout (Sebastian): Bild -> Gesicht-Crop -> Vermutung ->
    // Antwort-Choices -> Neue Person -> Ueberspringen, einheitliche Buttons.
    // `zielContainer` (optional): vorhandene Antwortblase wiederverwenden statt
    // eine NEUE zu erzeugen — genutzt fuer die wiederhergestellte, offene Frage.
    const karte = zielContainer
        ? zielContainer
        : addMessage('', 'assistant', undefined, pfad);
    karte.innerHTML = '';
    // global merken (fuer quizBeantworten, um die Karte nach der Antwort auf
    // das Ergebnis umzuschreiben und die Buttons zu entfernen)
    // eslint-disable-next-line no-global-assign
    _letzteQuizKarte = karte;
    // Blase als Quiz-Karte markieren: ermoeglicht das gezielte Aufraeumen der
    // fluechtigen Bildkopie (base64-DatenURL) nach Antwort/Weiter/Beenden,
    // damit keine angehaeuften Mega-URLs im Chat-Speicher bleiben.
    try { karte.dataset.quizKarte = '1'; } catch (_) {}

    // Kopfzeile: Menue-Symbol (Personen verwalten) links, Titel, Stopp rechts.
    const kopf = document.createElement('div');
    kopf.style.cssText = 'display:flex;justify-content:space-between;align-items:center';
    // Menue-Knopf oben links: oeffnet das Personen-Bearbeitsmenue direkt aus
    // der Quiz-Bubble (Sebastian: Menue-Symbol oben links).
    const menue = macheQuizButton('👥', 'person', zeigePersonenVerwaltung);
    menue.title = 'Personen verwalten (Rollen/Referenzen)';
    menue.style.cssText += ';padding:2px 9px;font-size:0.85rem;background:transparent;border:1px solid #2e8b57;color:#8f8';
    const titel = document.createElement('div');
    titel.style.cssText = 'flex:1;text-align:center;font-weight:700;font-size:0.86rem;color:#9f9';
    titel.textContent = '🧠 Gesichter-Quiz';
    const stopp = macheQuizButton('✕', 'skip', beendeQuizAktiv);
    stopp.title = 'Quiz beenden';
    stopp.style.cssText += ';padding:1px 8px;font-size:0.95rem;background:transparent;border:1px solid #555;color:#bbb';
    kopf.appendChild(menue);
    kopf.appendChild(titel);
    kopf.appendChild(stopp);
    karte.appendChild(kopf);

    // Bild in einem eigenen, scrollbaren Wrapper mit position:relative: So ist
    // das Foto proportional skaliert (kein object-fit:cover, das den gelben
    // bbox-Rahmen verrutschen liess) und grosse Bilder sind per Scroll bar.
    // Der gelbe Kasten (markiereGesichtImBild) liegt als Overlay darüber.
    const imgWrap = document.createElement('div');
    imgWrap.style.cssText = 'position:relative;display:block;width:100%;max-height:320px;overflow:auto;background:#000;border-radius:10px;margin-top:6px;border:1px solid #444';
    const img = document.createElement('img');
    img.src = dataUrl;
    img.alt = 'Quiz-Bild';
    img.style.cssText = 'display:block;width:100%;height:auto;border-radius:10px';
    macheBildAntippbar(img, gesichter || []);   // Tipp -> Vollbild (Person wirklich erkennen)
    imgWrap.appendChild(img);
    karte.appendChild(imgWrap);

    const frage = document.createElement('div');
    frage.style.cssText = 'margin-top:6px;font-weight:600;color:#eef';
    frage.textContent = 'Wer ist auf diesem Bild?';
    karte.appendChild(frage);

    // --- Gesicht/er im Bild markieren (gelber Rahmen) + prominenter Ausschnitt ---
    const anzahlGes = (anzahl && anzahl >= 1) ? anzahl : 0;
    if (anzahlGes >= 2) {
        // Gruppenbild (>=2): Gesicht fuer Gesicht durchgehen + je markieren.
        starteGruppenQuiz(frage, karte, img, dataUrl, pfad, optionen, gesichter || [], erkannte || []);
        return;  // Gruppen-Flow baut seine eigene Antwort-Sektion
    } else if (anzahlGes === 1 && gesichter && gesichter.length) {
        markiereGesichtImBild(img, gesichter, 0);
        try { img.addEventListener('load', () => markiereGesichtImBild(img, gesichter, 0)); } catch (_) {}
        zeigeGesichtCropIn(karte, dataUrl, gesichter[0].bbox, 240);
    }

    // --- Vermutung: erst reine Ja/Nein-Frage stellen (kein aufdringliches
    //     "eigenes Raten"). Name/Auswahl/Neue Person/Kein Gesicht erscheinen
    //     erst NACH "Nein" (Sebastian: erst Ja/Nein, wenn Nein dann 'wer ist das'). ---
    const v = vermutung ? (vermutung.person ? vermutung : null) : null;
    if (v) {
        const vbox = document.createElement('div');
        vbox.style.cssText = 'margin-top:8px;padding:8px;border:1px solid #2e8b57;border-radius:9px;background:#12251a';
        const sh = (v.sicherheit || '');
        const txt = document.createElement('div');
        txt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600';
        txt.textContent = `🔎 Ist das ${v.person}?` + (sh ? ` (Sicherheit: ${sh})` : '');
        vbox.appendChild(txt);
        const zeile = document.createElement('div');
        zeile.style.cssText = 'display:flex;gap:6px;margin-top:6px;flex-wrap:wrap';
        zeile.appendChild(macheQuizButton('✅ Ja', 'akt', () => {
            // SOFORT sichtbares Feedback (Wunsch Sebastian 2026-09-09): die
            // Ja/Nein-Box auf eine grüne Bestätigung umschalten, damit der
            // Klick nicht "taub" wirkt, bevor der Server antwortet.
            vbox.innerHTML = '';
            const best = document.createElement('div');
            best.style.cssText = 'font-size:0.85rem;color:#9f9;font-weight:600';
            best.textContent = `✓ ${v.person} gespeichert – weiter…`;
            vbox.appendChild(best);
            // Live-korrigierte bbox des Einzelgesichts (Index 0) mitsenden
            let liveBbox = null;
            try {
                if (_quizEditor && _quizEditor.bbox_live && Array.isArray(_quizEditor.bbox_live[0])
                    && _quizEditor.bbox_live[0].length >= 4) liveBbox = _quizEditor.bbox_live[0];
            } catch (_e) {}
            quizBeantworten(pfad, v.person, false, '', '', '', liveBbox);
        }));
        zeile.appendChild(macheQuizButton('❌ Nein', 'neu', () => {
            vbox.style.display = 'none';
            zeigeAntwortEingabe();   // erst jetzt: Wer ist es denn?
        }));
        vbox.appendChild(zeile);
        // "Keine Person vorhanden" soll IMMER direkt unter Ja/Nein stehen
        // (Wunsch Sebastian 2026-09-09) - nicht erst nach "Nein". Wechselt
        // zum nächsten BILD (überspringt dieses).
        const skipDirekt = macheQuizButton('🚫 Keine Person vorhanden', 'skip', () => quizUeberspringen(pfad));
        skipDirekt.style.cssText += ';margin-top:6px;width:100%;text-align:center';
        vbox.appendChild(skipDirekt);
        karte.appendChild(vbox);
    }

    // Baut den Antwort-Block (Namen + Neue Person + Kein Gesicht). Wird bei
    // einer Vermutung erst nach "Nein" eingeblendet, sonst direkt gezeigt.
    function zeigeAntwortEingabe() {
        auswahlBox.style.display = 'flex';
        neu.style.display = '';
        skip.style.display = '';
        frage.textContent = 'Wer ist auf diesem Bild?';
    }

    // --- Antwort-Sektion: die 5 wahrscheinlichsten Namen (Kacheln) + Suche ---
    const auswahlBox = document.createElement('div');
    auswahlBox.style.cssText = 'display:' + (v ? 'none' : 'flex') + ';flex-direction:column;gap:6px;margin-top:8px';
    // Optionen sind im Backend nach Wahrscheinlichkeit sortiert — nur die
    // ersten 5 zeigen (Wunsch Sebastian: 5 Namen untereinander reicht).
    const kacheln = document.createElement('div');
    kacheln.style.cssText = 'display:flex;flex-direction:column;gap:6px';
    (optionen || []).slice(0, 5).forEach(o => {
        // Bekannte Person: deren gemerkte Rolle bleibt erhalten -> leerer String.
        kacheln.appendChild(macheQuizButton(o, 'person', () => quizBeantworten(pfad, o, false, '')));
    });
    if ((optionen || []).length > 5) {
        const mehr = document.createElement('div');
        mehr.style.cssText = 'font-size:0.72rem;color:#9f9;opacity:.8;margin-top:2px';
        mehr.textContent = `… und ${(optionen || []).length - 5} weitere (siehe Suche).`;
        kacheln.appendChild(mehr);
    }
    auswahlBox.appendChild(kacheln);
    // "Suche andere Person": freie Eingabe mit LIVE-Vorschlägen (wie Gruppenbild)
    auswahlBox.appendChild(baueSuchMitVorschlaegen(optionen, (n) => quizBeantworten(pfad, n, false, '')));
    karte.appendChild(auswahlBox);

    // 'Neue Person' als eingebettetes, GROESSERES Formular (kein prompt(), PWA-
    // sicher): Name + Rolle + EIN Textfeld für alle Infos über die Person +
    // Speicherknopf. Beschreibung/Lebensinfos war doppelt gemoppelt — alles
    // geht jetzt in das Zusatzkontext-Feld (Wunsch Sebastian 2026-09-09).
    const neu = macheQuizButton('➕ Neue Person', 'neu', null);
    const neuForm = document.createElement('div');
    neuForm.style.display = 'none';
    neuForm.style.cssText = 'display:none;margin-top:6px;padding:10px;border:2px solid #f88;border-radius:10px;background:#221010';
    const neuName = document.createElement('input');
    neuName.placeholder = 'Name* (z. B. Julian)';
    neuName.style.cssText = 'width:100%;padding:7px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.88rem';
    const neuRolle = document.createElement('input');
    neuRolle.placeholder = 'Rolle / Bedeutung (z. B. Bruder, Mutter)';
    neuRolle.style.cssText = 'width:100%;padding:7px;margin-top:6px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.88rem';
    const neuBezWrap = document.createElement('div');
    neuBezWrap.style.cssText = 'display:flex;align-items:center;gap:4px;margin-top:6px';
    const neuBez = document.createElement('textarea');
    neuBez.placeholder = 'Infos über die Person — Beziehung + alles, was du weißt (Diktat möglich)';
    neuBez.rows = 3;
    neuBez.style.cssText = 'width:100%;padding:7px;border:1px solid #f88;border-radius:7px;background:#1a0d0d;color:inherit;font-size:0.85rem;resize:vertical;flex:1';
    neuBezWrap.appendChild(neuBez);
    fuegeFeldMikrofonHinzu(neuBez, neuBezWrap, 'Infos über die Person diktieren');
    const neuSpeichern = macheQuizButton('✅ Person speichern', 'neu', () => {
        const n = (neuName.value || '').trim();
        if (!n) { neuName.style.borderColor = '#f55'; return; }
        quizBeantworten(pfad, n, true, (neuRolle.value || '').trim(), (neuBez.value || '').trim(), '');
    });
    neuSpeichern.style.cssText += ';margin-top:8px;width:100%;padding:8px';
    neuForm.appendChild(neuName);
    neuForm.appendChild(neuRolle);
    neuForm.appendChild(neuBezWrap);
    neuForm.appendChild(neuSpeichern);
    neu.onclick = () => { neuForm.style.display = neuForm.style.display === 'none' ? 'block' : 'none'; };
    karte.appendChild(neu);
    karte.appendChild(neuForm);

    const skip = macheQuizButton('🚫 Keine Person vorhanden', 'skip', () => quizUeberspringen(pfad));
    skip.style.cssText += ';margin-top:6px;width:100%;text-align:center';
    karte.appendChild(skip);

    // Vermutung vorhanden? Dann Antwort-Block anfangs verstecken (nur Ja/Nein
    // sichtbar); erst "Nein" blendet den Antwort-Block ein.
    if (v) {
        auswahlBox.style.display = 'none';
        neu.style.display = 'none';
        skip.style.display = 'none';
    } else {
        zeigeAntwortEingabe();
    }
}

// Ergebnis der Quiz-Runde in der Karte anzeigen: Ersetzt den Antwortbereich
// (Buttons verschwinden) durch eine Bildunterschrift "… das ist [Person]".
// Verhindert so das versehentliche MEHRFACH-Speichern durch wiederholte
// Klicks auf dieselbe Antwort (Buttons sind danach weg).
// Wunsch Sebastian 2026-09-09: auch beim Einzelbild das BILD + "das ist …"
// als Bildunterschrift zeigen statt nur nacktem Text.
function macheQuizFertig(karte, text, ok, bildSrc) {
    if (!karte) return;
    try {
        // gesamten Karten-Inhalt durch das Ergebnis ersetzen
        karte.innerHTML = '';
        const zeile = document.createElement('div');
        zeile.style.cssText = 'padding:10px;border:1px solid ' + (ok ? '#2e8b57' : '#f88')
            + ';border-radius:10px;background:' + (ok ? '#0f1f14' : '#221010')
            + ';font-weight:600;color:' + (ok ? '#8f8' : '#f88');
        zeile.textContent = ok ? ('✅ ' + text) : ('⚠️ ' + text);
        karte.appendChild(zeile);
        // Bildunterschrift: kleines Bild oben + darunter "… das ist X" (falls
        // ein Bild-Src vorhanden ist). Bei Erfolg wird das aktuelle Bild
        // kompakt als Bestaetigung gezeigt, mit der zugeordneten Person als
        // Bildunterschrift darunter.
        if (ok && bildSrc) {
            const cap = document.createElement('div');
            cap.style.cssText = 'margin-top:6px;padding:6px;border:1px solid #4a7;border-radius:8px;background:#0f1f14';
            const capImg = document.createElement('img');
            capImg.src = bildSrc;
            capImg.alt = 'Bestätigt';
            capImg.style.cssText = 'max-width:90px;max-height:90px;border-radius:8px;border:1px solid #4a7;vertical-align:middle';
            const capTxt = document.createElement('span');
            capTxt.style.cssText = 'color:#8f8;font-size:0.82rem;font-weight:600;margin-left:8px';
            capTxt.textContent = '… das ist ' + (text || '');
            cap.appendChild(capImg);
            cap.appendChild(capTxt);
            karte.appendChild(cap);
        }
        // nach kurzer Zeit automatisch zur naechsten Runde
        setTimeout(() => { try { naechsteQuizRunde(); } catch (_) {} }, 1500);
    } catch (_) {}
}

async function quizUeberspringen(pfad) {
    try {
        const r = await fetch(`${API_BASE}/api/gesichter/quiz/antwort`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bild_pfad: pfad, person: '', ist_neu: false, rolle: '', ueberspringen: true }),
        });
        const d = await r.json();
        addMessage((d && d.ok) ? '👌 Übersprungen (kein Gesicht/keine Person).' : `⚠️ ${(d && d.fehler) || 'Fehler'}`, 'assistant');
        naechsteQuizRunde();  // weiter zur naechsten Frage (ohne Guard-Resettierung)
    } catch (e) {
        addMessage('⚠️ Überspringen fehlgeschlagen: ' + (e && e.message), 'assistant');
    }
}

function beendeQuizAktiv() {
    if (_quizAktiv) {
        _quizAktiv = false;
        raeumeQuizKopienAuf();  // Bildkopie der stehengebliebenen Frage freigeben
        addMessage('🛑 **Quiz beendet** — du kannst jederzeit neu starten.', 'assistant');
    }
}

async function quizFortsetzen() {
    // Zeigt den LETZTEN Stand wieder: die letzte offene Quiz-Frage aus dem
    // Verlauf (conv_main) mit Bild + Antwort-Optionen + Vermutung.
    try {
        const res = await fetch(`${API_BASE}/api/conversations/conv_main`);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const nachrichten = (await res.json()).messages || [];
        // letzte [QUIZ-OFFEN]-Nachricht finden
        let offen = -1;
        for (let i = 0; i < nachrichten.length; i++) {
            if ((nachrichten[i].content || '').indexOf('[QUIZ-OFFEN]') !== -1) offen = i;
        }
        if (offen === -1) {
            addMessage('ℹ️ Keine offene Quiz-Frage im Verlauf. Sag "quiz starten" für ein neues.', 'assistant');
            return;
        }
        const m = nachrichten[offen];
        const pfad = m.bild_pfad;
        if (!pfad) { addMessage('ℹ️ Offene Frage hat kein Bild.', 'assistant'); return; }
        addMessage(`🔄 **Quiz fortgesetzt** – letzte offene Frage wieder angezeigt.`, 'assistant');
        // Vorbereiten: bekannte Personen als Optionen holen
        const gr = await fetch(`${API_BASE}/api/gesichter`);
        const gd = await gr.json();
        const optionen = (gd && gd.personen || []).map(p => p.name).filter(Boolean);
        const ui = m.ui || null;
        const vermutung = ui && ui.vermutung && ui.vermutung.person ? ui.vermutung : (null);
        // Gesicht-Bboxen aus dem persistierten ui-Block holen (sonst keiner):
        // so zeichnet zeigeQuizKarte den gelben bbox-Rahmen ueber dem Bild.
        const gesichterUi = (ui && ui.gesichter) || [];
        const anzahlGes = gesichterUi.length;
        // data_url laden
        const dr = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(pfad)}`);
        const dd = await dr.json();
        const dataUrl = (dd && dd.data_url) || '';
        if (!dataUrl) {
            addMessage('🖼 Bild nicht (mehr) ladbar (gelöscht/verschoben).', 'assistant');
        }
        zeigeQuizKarte(pfad, m.name || '', dataUrl, optionen, vermutung, anzahlGes, [], gesichterUi);
        // interaktive Antworten rekonstruieren (nur die letzte -> hier genau diese)
        const letzte = document.querySelectorAll('.message.assistant');
        // Nach der neuen Karte die Antwort-Buttons ergaenzen (ui-basiert)
        // -> wiederherstellenQuizAntworten auf die zuletzt hinzugefuegte Karte
        const alle = Array.from(document.querySelectorAll('.message.assistant .message-content'));
        const cz = alle[alle.length - 1] || null;
        if (cz) wiederherstellenQuizAntworten(cz, pfad, ui);
    } catch (e) {
        addMessage('⚠️ Quiz konnte nicht fortgesetzt werden: ' + (e && e.message), 'assistant');
    }
}

// Raeumt die fluechtigen base64-Bildkopien ABGESCHLOSSENER Quiz-Karten auf.
// Nur Blasen mit dataset.quizKarte (= per zeigeQuizKarte erzeugt) und deren
// <img src="data:..."> werden geleert + der gelbe Rahmen entfernt. So bleibt
// jede beantwortete/uebersprungene Frage nicht als Mega-DatenURL im DOM/
// Arbeitsspeicher haengen (Sebastian: Bilder fluechtig, nie anhaeufen).
function raeumeQuizKopienAuf() {
    try {
        const blasen = Array.from(document.querySelectorAll('.message.assistant'));
        for (const blas of blasen) {
            if (!(blas.dataset && blas.dataset.quizKarte)) continue;
            const imgs = blas.querySelectorAll('img');
            for (const im of imgs) {
                const src = im.src || '';
                if (src.indexOf('data:') === 0) {  // nur base64-DatenURLs, nicht http
                    try { im.removeAttribute('src'); } catch (e) {}
                    im.src = '';
                }
            }
            const marke = blas.querySelector('.quiz-marke');
            if (marke) { try { marke.remove(); } catch (e) {} }
        }
    } catch (_) {}
}

// Holt die naechste Quiz-Runde vom Server und zeigt sie. KEIN _quizAktiv-Guard:
// diese Funktion ist die FORTSETZUNG innerhalb einer bereits laufenden Sitzung
// (nach "weiter"/"Naechstes Bild"/"Keine Person drauf"). _quizAktiv bleibt true,
// solange die Sitzung laeuft; nur der echte Neustart (quizStart) guardet.
// Liefert true, wenn eine Runde angezeigt wurde; false, wenn Quiz zu Ende/Fehler.
async function naechsteQuizRunde(nachRunde) {
    // `nachRunde` (optional): wird nach dem Anzeigen einer Runde aufgerufen mit
    // (hauptQuizImg, gesichter). Nutzt der Vollbild-Durchlauf ("Nächstes Bild ➡️"),
    // um das neue Bild direkt wieder als Vollbild zu oeffnen. Ohne Callback
    // verhaelt sich die Funktion exakt wie zuvor.
    raeumeQuizKopienAuf();  // verbrauchte Quiz-Karte(n): Bildkopie freigeben
    const warteblase = addMessage('', 'assistant');
    // Gleiche animierte Dreipunkt-Blase wie beim Agenten-Denken (siehe Typing-Indicator
    // weiter unten): zeigt "Quiz lädt" als pulsierende Bubble statt nacktem Text und wird
    // direkt nach der Server-Antwort wieder entfernt.
    warteblase.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div><span class="loading-text">🧠 Quiz lädt – prüfe Gesichter …</span>';
    try {
        const r = await fetch(`${API_BASE}/api/gesichter/quiz/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ausgeschlossen: _quizGesehen }),
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        if (warteblase) { const b = warteblase.closest ? warteblase.closest('.message') : null; if (b) b.remove(); }
        if (d && d.keine) { addMessage('⚠️ Kein Lieblingsbilder-Ordner gefunden.', 'assistant'); _quizAktiv = false; return false; }
        if (d && d.fertig) {
            addMessage(`🎉 **Quiz beendet!** Du hast ${d.verarbeitet||0} von ${d.gesamt||0} Lieblingsbildern durchgespielt. Die Gesichter sind jetzt robuster gelernt. Danke fürs Trainieren!`, 'assistant');
            _quizAktiv = false;
            return false;
        }
        const pfad = d.bild_pfad;
        _quizGesehen.push(pfad);
        const name = d.name || '';
        const dataUrl = d.data_url || '';
        const optionen = d.optionen || [];
        // Wunsch Sebastian: Bild SOFORT anzeigen (start_runde blockiert nicht
        // mehr auf die Gesichtserkennung); darunter die "Quiz lädt"-Animation;
        // sobald die Analyse fertig ist, ersetzt die Ja/Nein-Frage die Animation.
        if (d.analyse_ausstehend) {
            // 1) Karte sofort mit Bild erstellen (dataUrl ist lokal -> sofort)
            const sofortKarte = addMessage('', 'assistant', undefined, pfad);
            try { sofortKarte.dataset.quizKarte = '1'; } catch (_e) {}
            const imgWrap = document.createElement('div');
            imgWrap.style.cssText = 'position:relative;display:block;width:100%;max-height:320px;overflow:auto;background:#000;border-radius:10px;border:1px solid #444';
            const img = document.createElement('img');
            img.src = dataUrl;
            img.alt = 'Quiz-Bild';
            img.style.cssText = 'display:block;width:100%;height:auto;border-radius:10px';
            imgWrap.appendChild(img);
            sofortKarte.appendChild(imgWrap);
            // 2) Lade-Animation direkt UNTER dem Bild
            const ladewrap = document.createElement('div');
            ladewrap.style.cssText = 'margin-top:6px;padding:8px;background:#0f1f14;border-radius:10px;text-align:center';
            ladewrap.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div><span class="loading-text">🧠 Quiz lädt – prüfe Gesichter …</span>';
            sofortKarte.appendChild(ladewrap);
            // "Keine Person vorhanden" schon jetzt anbieten (auch waehrend die
            // Analyse laeuft) — Wunsch Sebastian 2026-09-10: kann sofort zum
            // naechsten Bild durchdruecken.
            const skipSofort = macheQuizButton('🚫 Keine Person vorhanden', 'skip', () => quizUeberspringen(pfad));
            skipSofort.style.cssText += ';margin-top:6px;width:100%;text-align:center';
            sofortKarte.appendChild(skipSofort);
            scrollToBottom(true);
            // 3) Analyse nachholen, danach die Karte fertig rendern (Ja/Nein
            //    ersetzt die Animation).
            try {
                const ar = await fetch(`${API_BASE}/api/gesichter/quiz/analysiere`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bild_pfad: pfad }),
                });
                const a = await ar.json();
                zeigeQuizKarte(pfad, name, dataUrl, optionen,
                    a.vermutung, a.anzahl_gesichter || 0, a.erkannte_personen || [], a.gesichter || [],
                    sofortKarte);
                // Vollbild-Durchlauf: neues Bild nach der Analyse direkt wieder als
                // Vollbild anzeigen (mit den analysierten Gesichtern fuer die Rahmen).
                if (typeof nachRunde === 'function') {
                    try { nachRunde(findeHauptQuizBild(sofortKarte), a.gesichter || []); } catch (_c) {}
                }
            } catch (e2) {
                // Analyse fehlgeschlagen: zumindest die Antwort-Chips anbieten
                zeigeQuizKarte(pfad, name, dataUrl, optionen, null, 0, [], [], sofortKarte);
                if (typeof nachRunde === 'function') {
                    try { nachRunde(findeHauptQuizBild(sofortKarte), []); } catch (_c) {}
                }
            }
            return true;
        }
        zeigeQuizKarte(pfad, name, dataUrl, optionen, d.vermutung, d.anzahl_gesichter || 0, (d.erkannte_personen || []), (d.gesichter || []));
        // Vollbild-Durchlauf: neues Bild direkt wieder als Vollbild anzeigen.
        if (typeof nachRunde === 'function') {
            try { nachRunde(findeHauptQuizBild(_letzteQuizKarte), d.gesichter || []); } catch (_c) {}
        }
        return true;
    } catch (e) {
        if (warteblase) { const b = warteblase.closest ? warteblase.closest('.message') : null; if (b) b.remove(); }
        addMessage('⚠️ Quiz konnte nicht starten: ' + (e && e.message), 'assistant');
        _quizAktiv = false;
        return false;
    }
}

async function quizStart() {
    // NUR EINE Quiz-Instanz erlauben: kein zweites starten, solange eines laeuft.
    if (_quizAktiv) {
        addMessage('⚠️ Es läuft bereits eine Quiz-Sitzung. Beende sie erst mit "quiz beenden", bevor du neu startest.', 'assistant');
        return;
    }
    _quizAktiv = true;
    naechsteQuizRunde();
}

async function quizBeantwortenSilent(pfad, person, istNeu, rolle, beziehung, beschreibung, bbox) {
    try {
        const payload = { bild_pfad: pfad, person: (person||'').trim(), ist_neu: !!istNeu, rolle: (rolle||'').trim(), beziehung: (beziehung||'').trim(), beschreibung: (beschreibung||'').trim() };
        // Korrigierte/geänderte Gesichts-box aus dem Vollbild-Editor mitsenden
        // (Wunsch Sebastian 2026-09-09: Ausschnitt im Originalbild nachjustieren)
        if (Array.isArray(bbox) && bbox.length >= 4) payload.bbox = bbox;
        const r = await fetch(`${API_BASE}/api/gesichter/quiz/antwort`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        return await r.json();
    } catch (e) {
        return { ok: false, fehler: e && e.message };
    }
}

async function quizBeantworten(pfad, person, istNeu, rolle, beziehung, beschreibung, bbox) {
    try {
        const payload = { bild_pfad: pfad, person, ist_neu: istNeu, rolle: (rolle || ''), beziehung: (beziehung||''), beschreibung: (beschreibung||'') };
        if (Array.isArray(bbox) && bbox.length >= 4) payload.bbox = bbox;
        const r = await fetch(`${API_BASE}/api/gesichter/quiz/antwort`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const d = await r.json();
        const meldung = (d && d.ok)
            ? `✓ **${person}** gespeichert${d.ist_neu ? ' (neu)' : ''} — ${d.referenzen} Referenz(en).`
            : (`⚠️ ${(d && d.fehler) || 'Unbekannter Fehler'}`);
        if (d && d.ok && _letzteQuizKarte) {
            // Bildunterschrift in der BESTEHENDEN Karte: Bild + "… das ist X"
            // (Wunsch Sebastian 2026-09-09). Buttons weg, Bild bleibt als
            // kompakte Bestaetigung mit der zugeordneten Person darunter.
            _letzteQuizKarte.innerHTML = '';
            const zeile = document.createElement('div');
            zeile.style.cssText = 'padding:8px;border:1px solid #2e8b57;border-radius:10px;background:#0f1f14;font-weight:600;color:#8f8';
            zeile.textContent = meldung;
            _letzteQuizKarte.appendChild(zeile);
            const cap = document.createElement('div');
            cap.style.cssText = 'margin-top:6px;padding:6px;border:1px solid #4a7;border-radius:8px;background:#0f1f14';
            // aktuelle Quiz-Bild-DatenURL aus der Karte entnehmen
            let src = '';
            const imgAlt = _letzteQuizKarte.querySelector('img');
            if (imgAlt && imgAlt.src && ('' + imgAlt.src).indexOf('data:') === 0) src = imgAlt.src;
            if (src) {
                const capImg = document.createElement('img');
                capImg.src = src;
                capImg.style.cssText = 'max-width:120px;max-height:120px;border-radius:8px;border:1px solid #4a7;vertical-align:middle';
                cap.appendChild(capImg);
            }
            const capTxt = document.createElement('span');
            capTxt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600;margin-left:8px';
            capTxt.textContent = '… das ist ' + (person || '');
            cap.appendChild(capTxt);
            _letzteQuizKarte.appendChild(cap);
            setTimeout(() => { try { naechsteQuizRunde(); } catch (_) {} }, 1500);
            return;
        }
        addMessage(meldung, 'assistant');
        // naechste Frage (Moeglichkeit, durchzuspielen) — kleiner Quick-Link:
        const weiter = document.createElement('button');
        weiter.textContent = 'Nächstes Bild ➡️';
        weiter.style.cssText = 'align:left;padding:6px 10px;border:1px solid #4a7;border-radius:8px;background:#1f3a2a;color:#8f8;cursor:pointer;font-size:0.8rem';
        weiter.onclick = naechsteQuizRunde;
        const c = addMessage('', 'assistant');
        c.appendChild(weiter);
    } catch (e) {
        addMessage('⚠️ Antwort fehlgeschlagen: ' + (e && e.message), 'assistant');
    }
}

// Referenz-Check: interaktive Liste aller gelernten Referenzen je Person,
// mit Bild-Vorschau und Loesch-Button fuer falsche Referenzen.
function zeigeReferenzen() {
    addMessage('🔎 **Referenz-Check** – lade gelernte Referenzen …', 'assistant');
    (async () => {
        try {
            const res = await fetch(`${API_BASE}/api/gesichter/referenzen`);
            const d = await res.json();
            const personen = (d && d.personen) || [];
            if (!personen.length) { addMessage('ℹ️ Noch keine Personen mit Referenzen gelernt.', 'assistant'); return; }
            // pro Person eine Karte
            for (const p of personen) {
                const karte = addMessage('', 'assistant');
                const head = document.createElement('div');
                head.style.cssText = 'font-weight:700;margin-bottom:4px';
                head.textContent = `👤 ${p.name}` + (p.rolle ? ` (${p.rolle})` : '') + ` – ${p.anzahl} Referenz(en)`;
                karte.appendChild(head);
                if (p.miniatur) {
                    const img = document.createElement('img');
                    img.src = p.miniatur;
                    img.style.cssText = 'max-width:80px;max-height:80px;border-radius:8px;border:1px solid #555;margin-right:6px;vertical-align:top';
                    karte.appendChild(img);
                }
                const liste = document.createElement('div');
                liste.style.cssText = 'margin-top:4px;font-size:0.8rem;color:#bbb';
                if (!p.referenzen.length) {
                    liste.textContent = '– keine Einzel-Referenzen (nur alte Embeddings) –';
                } else {
                    p.referenzen.forEach(r => {
                        const zeile = document.createElement('div');
                        zeile.style.cssText = 'display:flex;align-items:center;gap:6px;margin:2px 0';
                        const txt = document.createElement('span');
                        txt.textContent = `#{${r.index}} Aufnahmejahr: ${r.jahr || 'unbekannt'} `;
                        zeile.appendChild(txt);
                        const del = document.createElement('button');
                        del.textContent = '✕ löschen';
                        del.style.cssText = 'padding:2px 8px;border:1px solid #f88;border-radius:6px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.75rem';
                        del.onclick = () => referenzLoeschen(p.name, r.ref_id, del);
                        zeile.appendChild(del);
                        liste.appendChild(zeile);
                    });
                }
                karte.appendChild(liste);
            }
            addMessage('💡 **Passe auf:** Nicht geloeschte Referenzen bleiben als Erkennungs-Basis. Gelöschte Einzel-Referenzen vernichte ich nur fuer diese Person.', 'assistant');
        } catch (e) {
            addMessage('⚠️ Referenzen konnten nicht geladen werden: ' + (e && e.message), 'assistant');
        }
    })();
}

async function referenzLoeschen(name, refId, btn) {
    if (!window.confirm && typeof confirm === 'function' && !confirm(`Diese Referenz von ${name} wirklich löschen?`)) return;
    try {
        const r = await fetch(`${API_BASE}/api/gesichter/referenzen/${encodeURIComponent(name)}/${encodeURIComponent(refId)}`, { method: 'DELETE' });
        const d = await r.json();
        if (d && d.ok) { btn.textContent = '✓ gelöscht'; btn.disabled = true; btn.style.opacity = 0.5; }
        else { alert('Fehler: ' + ((d && d.fehler) || 'unbekannt')); }
    } catch (e) { alert('Löschen fehlgeschlagen: ' + (e && e.message)); }
}

/** Öffnet die Referenzen EINER Person als scrollbares VOLLBILD-Overlay mit den
 *  gespeicherten Gesichts-Ausschnitten (je Referenz Bild/Hinweis + ✕ löschen +
 *  "Alle löschen"), statt als Chat-Blase (Wunsch Sebastian 2026-09-10). */
function zeigeReferenzenVollbild(name) {
    let ov = document.createElement('div');
    ov.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);z-index:99998;display:flex;flex-direction:column;animation:fadeIn 0.2s ease';
    // Kopf
    const kopf = document.createElement('div');
    kopf.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px;color:#8f8;font-weight:700;font-size:1rem';
    kopf.textContent = `👤 ${name} — Referenzen`;
    ov.appendChild(kopf);
    const schliess = document.createElement('div');
    schliess.textContent = '✕';
    schliess.style.cssText = 'position:fixed;top:12px;right:16px;z-index:99999;width:38px;height:38px;border-radius:50%;background:rgba(0,0,0,.5);color:#fff;font-size:20px;display:flex;align-items:center;justify-content:center;cursor:pointer';
    schliess.addEventListener('click', () => { try { ov.remove(); } catch(_e){} });
    ov.appendChild(schliess);
    // scrollbare Liste
    const liste = document.createElement('div');
    liste.style.cssText = 'flex:1;overflow-y:auto;padding:12px';
    liste.textContent = '… lade Referenzen …';
    ov.appendChild(liste);
    // "Alle löschen" (unten, warnend)
    const footer = document.createElement('div');
    footer.style.cssText = 'display:flex;gap:8px;padding:10px';
    const alleBtn = document.createElement('button');
    alleBtn.textContent = '🗑 Alle Referenzen löschen';
    alleBtn.style.cssText = 'padding:8px 12px;border:1px solid #f88;border-radius:8px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.9rem';
    alleBtn.addEventListener('click', async () => {
        if (typeof confirm === 'function' && !confirm(`Wirklich ALLE Referenzen von ${name} löschen? (Erkennung dieser Person geht verloren)`)) return;
        const res = await fetch(`${API_BASE}/api/gesichter/referenzen`);
        const d = await res.json();
        const p = (d && d.personen || []).find(x => (x.name||'').trim().toLowerCase() === (name||'').trim().toLowerCase());
        for (const r of (p && p.referenzen || [])) {
            try { await fetch(`${API_BASE}/api/gesichter/referenzen/${encodeURIComponent(name)}/${encodeURIComponent(r.ref_id)}`, { method: 'DELETE' }); } catch(_e){}
        }
        liste.innerHTML = '';
        const fertig = document.createElement('div');
        fertig.style.cssText = 'color:#9f9;font-size:0.9rem;padding:12px';
        fertig.textContent = '✅ Alle Referenzen von ' + name + ' gelöscht.';
        liste.appendChild(fertig);
    });
    footer.appendChild(alleBtn);
    ov.appendChild(footer);
    document.body.appendChild(ov);

    // Laden + Rendern (erfolgt asynchron über die bestehende API)
    (async () => {
        try {
            const res = await fetch(`${API_BASE}/api/gesichter/referenzen`);
            const d = await res.json();
            const p = (d && d.personen || []).find(x => (x.name||'').trim().toLowerCase() === (name||'').trim().toLowerCase());
            liste.innerHTML = '';
            if (!p || !p.referenzen || !p.referenzen.length) {
                const leer = document.createElement('div');
                leer.style.cssText = 'color:#999;font-style:italic;padding:12px';
                leer.textContent = '– keine Referenzen –';
                liste.appendChild(leer);
                return;
            }
            // Miniatur der Person als Header-Hinweis, falls vorhanden
            if (p.miniatur) {
                const m = document.createElement('img');
                m.src = p.miniatur;
                m.style.cssText = 'max-width:64px;max-height:64px;border-radius:50%;border:2px solid #2e8b57;vertical-align:middle;display:block;margin:4px auto';
                liste.appendChild(m);
            }
            // keine Bilder in Referenzen -> Hinweis (Hauptproblem von Sebastian)
            const hinweis = document.createElement('div');
            hinweis.style.cssText = 'font-size:0.78rem;color:#9a9;padding:6px;font-style:italic';
            hinweis.textContent = `${p.referenzen.length} Referenz(en). Ohne hinterlegtes Bild (alt gelernt) → kein Ausschnitt zu sehen.`;
            liste.appendChild(hinweis);
            for (const r of p.referenzen) {
                const z = document.createElement('div');
                z.style.cssText = 'display:flex;align-items:center;gap:8px;margin:6px 0;padding:8px;border:1px solid #2e8b57;border-radius:10px;background:#0f1f14';
                const jahrTxt = document.createElement('span');
                jahrTxt.style.cssText = 'color:#eee;font-size:0.85rem';
                jahrTxt.textContent = `#{${r.index}} · ${r.jahr || 'Jahr unbekannt'}`;
                z.appendChild(jahrTxt);
                // Bild, falls vorhanden (s. api/dateien/daten); sonst Platzhalter
                if (r.bild_pfad) {
                    try {
                        const dr = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(r.bild_pfad)}`);
                        const dd = await dr.json();
                        if (dd && dd.data_url) {
                            const im = document.createElement('img');
                            im.src = dd.data_url;
                            im.style.cssText = 'max-width:72px;max-height:72px;border-radius:6px;border:1px solid #4a7;vertical-align:middle';
                            z.appendChild(im);
                        } else {
                            const ph = document.createElement('span');
                            ph.style.cssText = 'color:#777;font-size:0.75rem';
                            ph.textContent = '(Bild fehlt)';
                            z.appendChild(ph);
                        }
                    } catch (_e) {
                        const ph = document.createElement('span');
                        ph.style.cssText = 'color:#777;font-size:0.75rem';
                        ph.textContent = '(Bild fehlt)';
                        z.appendChild(ph);
                    }
                } else {
                    const ph = document.createElement('span');
                    ph.style.cssText = 'color:#777;font-size:0.75rem';
                    ph.textContent = '(kein Bild gespeichert)';
                    z.appendChild(ph);
                }
                const del = document.createElement('button');
                del.textContent = '✕ löschen';
                del.style.cssText = 'padding:3px 9px;border:1px solid #f88;border-radius:6px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.78rem;margin-left:auto';
                del.addEventListener('click', async () => {
                    await fetch(`${API_BASE}/api/gesichter/referenzen/${encodeURIComponent(name)}/${encodeURIComponent(r.ref_id)}`, { method: 'DELETE' });
                    z.style.opacity = 0.35;
                    del.textContent = '✓ gelöscht';
                    del.disabled = true;
                });
                z.appendChild(del);
                liste.appendChild(z);
            }
        } catch (e) {
            liste.innerHTML = '';
            const fehlt = document.createElement('div');
            fehlt.style.cssText = 'color:#f88;padding:12px';
            fehlt.textContent = '⚠️ Referenzen laden fehlgeschlagen: ' + (e && e.message);
            liste.appendChild(fehlt);
        }
    })();
}

// PERSONEN-ANPASSUNGSMODUL: Katalog deiner Wissensdatenbank durchsuchbar
// anzeigen, Rolle/Beziehung/Zusatzinfos je Person zuweisen/ändern/löschen,
// und mit "mehr laden" auch grosse Listen handhabbar halten. Bildet die
// Grundlage fuer die spaetere Foto-Sortierung (pCloud): Jede Person traegt
// ihren Kontext (Rolle, Beziehung, Beschreibung, Referenzbilder/Jahre).
// Speichert ueber POST /api/gesichter (legt an oder aktualisiert nach Name)
// bzw. DELETE /api/gesichter/{name}.
let _personenKatalog = [];   // letzter geladener Katalog (fuer Suche/Paging)

function zeigePersonenVerwaltung() {
    addMessage('🔎 **Personen-Katalog** – lade …', 'assistant');
    _personenKatalog = [];
    const panel = addMessage('', 'assistant');
    (async () => {
        try {
            const res = await fetch(`${API_BASE}/api/gesichter`);
            const d = await res.json();
            const personen = (d && d.personen) || [];
            _personenKatalog = personen.slice();
            panel.innerHTML = '';
            if (!personen.length) {
                panel.textContent = 'ℹ️ Noch keine Personen gespeichert. Sag „neue Person" im Quiz oder „neue person [Name]" im Chat.';
                return;
            }
            // Suchfeld (filtert online ueber alle)
            const suche = document.createElement('input');
            suche.placeholder = '🔍 Person suchen …';
            suche.style.cssText = 'width:100%;padding:8px;margin-bottom:6px;border:1px solid #2e8b57;border-radius:8px;background:#0e1a14;color:inherit;font-size:0.9rem';
            panel.appendChild(suche);
            const counter = document.createElement('div');
            counter.style.cssText = 'font-size:0.75rem;color:#9f9;margin:2px 0 6px';
            counter.textContent = `👥 ${personen.length} Personen im Katalog (Basis fürs Foto-Sortieren in der Cloud).`;
            panel.appendChild(counter);

            const liste = document.createElement('div');
            liste.style.cssText = 'margin-top:4px';
            panel.appendChild(liste);

            const LIMIT = 5;   // zuerst nur die 5 wahrscheinlichsten/ersten
            let angezeigt = 0;
            let _maxAngezeigt = LIMIT;   // inkrementelles Paging (5, 10, 15, …)

            function zeichenlöschen(name, karte) {
                if (typeof confirm === 'function' && !confirm(`Person '${name}' wirklich löschen?`)) return;
                fetch(`${API_BASE}/api/gesichter/${encodeURIComponent(name)}`, { method: 'DELETE' })
                    .then(r => r.json())
                    .then(dd => {
                        addMessage(dd && dd.status === 'deleted' ? `🗑 **${name}** entfernt.` : `⚠️ ${(dd && dd.detail) || 'Fehler'}`, 'assistant');
                        karte.style.opacity = '0.35';
                    })
                    .catch(e => addMessage('⚠️ Löschen fehlgeschlagen: ' + (e && e.message), 'assistant'));
            }

            // Baut eine Personen-Karte mit Bearbeiten-Formular
            function bauePersonKarte(p) {
                const karte = document.createElement('div');
                karte.style.cssText = 'margin:4px 0;padding:6px;border:1px solid #2e8b57;border-radius:8px;background:#0f1f14';
                const name = (p.name || '').trim();
                const head = document.createElement('div');
                head.style.cssText = 'font-weight:700;font-size:0.9rem;color:#8f8';
                head.textContent = `👤 ${name}` + (p.rolle ? ` · ${p.rolle}` : '') + (p.beziehung ? ` · ${p.beziehung}` : '');
                karte.appendChild(head);
                const meta = document.createElement('div');
                meta.style.cssText = 'font-size:0.72rem;color:#888;margin-top:2px';
                const jahre = (p.referenzen || []).filter(r => r && r.jahr).map(r => r.jahr).filter((v, i, a) => a.indexOf(v) === i).sort();
                meta.textContent = (jahre.length ? `📅 ${jahre.join(', ')} · ` : '') + `${(p.referenzen || p.embedding || []).length} Referenz(en)`;
                karte.appendChild(meta);

                // Bearbeiten-Formular (Rolle/Beziehung/Beschreibung/Zusatzkontext)
                const btn = macheQuizButton('✏️ Anpassen', 'akt', null);
                const form = document.createElement('div');
                form.style.display = 'none';
                form.style.cssText = 'display:none;margin:6px 0;padding:8px;border:1px solid #2e8b57;border-radius:8px;background:#12251a';
                const mk = (ph, val) => {
                    const i = document.createElement('input');
                    i.placeholder = ph; i.value = val || '';
                    i.style.cssText = 'width:100%;padding:5px;margin-bottom:4px;border:1px solid #2e8b57;border-radius:6px;background:#0e1a14;color:inherit;font-size:0.8rem';
                    return i;
                };
                const inpRolle = mk('Rolle / Beziehung (z. B. Bruder, Mutter)', p.rolle || '');
                const inpBez = mk('Infos über die Person (Beziehung + alles, was du weißt)', p.beziehung || (p.beschreibung || ''));
                const speichern = macheQuizButton('✅ Speichern', 'akt', async () => {
                    try {
                        const r = await fetch(`${API_BASE}/api/gesichter`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, rolle: inpRolle.value.trim(), beziehung: inpBez.value.trim(), beschreibung: (p.beschreibung || ''), referenz_bild_pfad: p.referenz_bild_pfad || '' }),
                        });
                        const dd = await r.json();
                        addMessage(dd && dd.person ? `✅ **${name}** aktualisiert.` : `⚠️ ${(dd && dd.fehler) || 'Fehler'}`, 'assistant');
                        form.style.display = 'none';
                    } catch (e) { addMessage('⚠️ Speichern fehlgeschlagen: ' + (e && e.message), 'assistant'); }
                });
                form.appendChild(inpRolle);
                form.appendChild(inpBez);
                form.appendChild(speichern);
                btn.onclick = () => { form.style.display = form.style.display === 'none' ? 'block' : 'none'; };
                karte.appendChild(btn);
                karte.appendChild(form);
                // Loeschen
                karte.appendChild(macheQuizButton('🗑', 'neu', () => zeichenlöschen(name, karte)));
                // Miniatur (falls vorhanden)
                const mini = p.referenz_bild_miniatur || p.miniatur || '';
                if (mini) {
                    const m = document.createElement('img');
                    m.src = mini;
                    m.style.cssText = 'max-width:64px;max-height:64px;border-radius:50%;border:2px solid #2e8b57;vertical-align:middle;margin-left:6px';
                    karte.appendChild(m);
                }
                // --- Referenz-Bilder ansehen / bearbeiten als VOLLBILD-Overlay (Wunsch
                //     Sebastian 2026-09-10): nicht mehr als Chat-Blase, sondern
                //     scrollbares Vollbild mit Gesichter-Ausschnitten) ---
                const refBtn = macheQuizButton('🖼 Referenzen ansehen/löschen', 'skip', () => zeigeReferenzenVollbild(name));
                refBtn.style.cssText += ';margin-top:6px;width:100%;text-align:center';
                karte.appendChild(refBtn);
                return karte;
            }

            function rendereListe() {
                liste.innerHTML = '';
                const q = (suche.value || '').trim().toLowerCase();
                const gefilert = _personenKatalog.filter(p => {
                    if (!q) return true;
                    const hay = `${p.name || ''} ${p.rolle || ''} ${p.beziehung || ''} ${p.beschreibung || ''}`.toLowerCase();
                    return hay.indexOf(q) !== -1;
                });
                angezeigt = 0;
                const show = gefilert.slice(0, _maxAngezeigt);
                show.forEach(p => { liste.appendChild(bauePersonKarte(p)); angezeigt++; });
                // "mehr laden"-Knopf: naechste 5, bis alle da sind
                if (gefilert.length > angezeigt) {
                    const mehr = document.createElement('button');
                    mehr.textContent = `↓ weitere laden (${_maxAngezeigt}/${gefilert.length})`;
                    mehr.style.cssText = 'display:block;width:100%;margin:4px 0;padding:6px;border:1px dashed #2e8b57;border-radius:8px;background:transparent;color:#8f8;cursor:pointer;font-size:0.8rem';
                    mehr.onclick = () => { _maxAngezeigt += LIMIT; rendereListe(); };
                    liste.appendChild(mehr);
                }
                if (!show.length) {
                    const leer = document.createElement('div');
                    leer.style.cssText = 'font-size:0.8rem;color:#888;margin-top:6px;font-style:italic';
                    leer.textContent = '– keine Person gefunden –';
                    liste.appendChild(leer);
                }
            }

            suche.addEventListener('input', () => { _maxAngezeigt = LIMIT; rendereListe(); });
            rendereListe();
            addMessage('💡 **Wissensdatenbank:** Der Katalog speichert zu jeder Person Referenzbilder + Aufnahmejahre. Nach dem Kontroll-Durchlauf kannst du Fotos später in der Cloud gezielt zuordnen/sortieren.', 'assistant');
        } catch (e) {
            panel.textContent = '⚠️ Katalog konnte nicht geladen werden: ' + (e && e.message);
        }
    })();
}

async function sendMessage(text, ausWarteschlange = false, blaseSchonGezeigt = false, forceAgent = false, ziel = '') {
    // QUIZ-KOMMANDO: "quiz starten", "anlernspiel", "lernspiel", "gesichtsspiel"
    if (text && typeof text === 'string') {
        const t = text.trim().toLowerCase();
        // QUIZ FORTSETZEN: haengenden _quizAktiv-Zustand zuruecksetzen und an
        // der letzten ungesehenen Frage weitermachen (quiz/start nutzt den
        // persistenten Fortschritt).
        if (t.indexOf('quiz fortsetzen') !== -1 || t.indexOf('quiz weiter') !== -1
            || t.indexOf('quiz fortführen') !== -1 || t.indexOf('quiz wieder') !== -1
            || t.indexOf('quiz weiter machen') !== -1 || t.indexOf('quiz wieder aufnehmen') !== -1) {
            _quizAktiv = false;
            quizFortsetzen();
            return;
        }
        if (t.indexOf('quiz starten') !== -1 || t.indexOf('anlernspiel') !== -1
            || t.indexOf('quiz start') !== -1 || t === 'quiz') {
            quizStart();
            return;
        }
        if (t.indexOf('quiz beenden') !== -1 || t.indexOf('quiz beenden') !== -1
            || t.indexOf('quiz stoppen') !== -1 || t.indexOf('quiz aus') !== -1
            || t.indexOf('quiz aufhören') !== -1 || t === 'stopp') {
            if (_quizAktiv) {
                addMessage('🛑 **Quiz beendet** — danke fürs Trainieren!', 'assistant');
                _quizAktiv = false;
            } else {
                addMessage('Es läuft gerade keine Quiz-Sitzung. Sag "quiz starten", um zu beginnen.', 'assistant');
            }
            return;
        }
        // Referenz-Management: "zeige referenzen" -> interaktive Liste zum Loeschen.
        if (t.indexOf('zeige referenzen') !== -1 || t.indexOf('referenzen anzeigen') !== -1
            || t === 'referenzen' || t.indexOf('referenz check') !== -1) {
            zeigeReferenzen();
            return;
        }
        // PERSONEN-VERWALTUNG: Rollen/Namen/Infos anlegen/aendern/loeschen.
        if (t === 'personen' || t === 'personenliste'
            || t.indexOf('personen verwalten') !== -1 || t.indexOf('personen bearbeiten') !== -1
            || t.indexOf('personen anzeigen') !== -1 || t.indexOf('personen manager') !== -1
            || t.indexOf('person ändern') !== -1 || t.indexOf('person aendern') !== -1) {
            zeigePersonenVerwaltung();
            return;
        }
    }

    // Abbruch-Guard: Während eine Antwort läuft (state.abbruch) wird NUR dann
    // eingereiht, wenn wir NICHT selbst eine Warteschlangen-Nachricht senden
    // (ausWarteschlange=true), kein laufender Hermes-Auftrag existiert UND es
    // kein Diktat ist, dessen Blase schon gezeigt wurde.
    // - Hermes-Auftrag (Track C) läuft → sendMessage geht weiter an POST /eingabe
    // - Normale Antwort läuft → in die Warteschlange (sichtbar)
    // - ausWarteschlange=true → durchreichen (sendeUndArbeiteAb)
    // - blaseSchonGezeigt=true (Diktat) → durchreichen, Blase ist schon da
    if (state.abbruch && !ausWarteschlange && !blaseSchonGezeigt && !_laufenderAuftragKurz) {
        if (!text.trim()) return;
        const element = zeigeWartendeNachricht(text);
        state.warteschlange.push({ text, element });
        return;
    }
    if (!text.trim()) return;
    // Sichtbar machen, WAS der Agent/Hermes gerade tut (Wunsch: nach jedem
    // Absenden Blase/Status zeigt den Arbeitsschritt).
    try {
        const hermesModus = (typeof loopAktiv !== 'undefined' && loopAktiv) || _laufenderAuftragKurz;
        const zielk = _zielAktuell || '';
        setzeTutZeile(hermesModus
            ? (zielk === 'pc' ? '⚙️ Hermes (PC) bearbeitet deine Aufgabe…'
               : zielk === 'handy' ? '⚙️ Hermes (Handy) bearbeitet deine Aufgabe…'
               : '⚙️ Hermes bearbeitet deine Aufgabe…')
            : '🔍 Agent liest deine Nachricht…');
    } catch (_) {}
    // Der Controller ist zugleich das Kennzeichen "hier laeuft etwas" und der
    // Griff, an dem der Stopp-Knopf zieht.
    const controller = new AbortController();
    state.abbruch = controller;
    setLoading(true);
    const userContentDiv = blaseSchonGezeigt ? null : addMessage(text, 'user');
    // Dateivorschau in der Nachricht anzeigen, falls vorhanden.
    // WICHTIG: Bei Diktat (blaseSchonGezeigt=true) ist userContentDiv null —
    // die Blase wurde schon vorab erzeugt. Bei Dateien (z. B. Screenshot +
    // Spracheingabe gleichzeitig) darf appendChild NICHT auf null laufen.
    if (state.pendingFiles.length > 0 && userContentDiv) {
        _zeigeDateienInNachricht(userContentDiv, state.pendingFiles);
        // Sicherheitsnetz: War der Katalog beim Upload noch nicht geladen,
        // kam die Warnung dort nicht – jetzt beim Senden nachholen.
        _warneFallsModellKeinBild();
    }

    // Kommunikationskanal zur laufenden Hermes-Session: Solange ein
    // Programmierauftrag von Hermes bearbeitet wird, geht die neue
    // Nachricht als Kommentar direkt an die offene Session (POST /eingabe),
    // statt einen neuen Auftrag zu starten. So kann man Hermes während
    // der Arbeit steuern/zurufen.
    // Ausnahme: In der Coding-/Hermes-Ansicht (conv_code) ist DIESE Session
    // selbst der Kanal — der Kommentar/POST-/eingabe-Umweg ist dort
    // ueberfluessig (Stand 2026-09-06, Auftrag Sebastian). Nachrichten nehmen
    // dort den normalen Sende-/Streamweg.
    if (_laufenderAuftragKurz && state.conversationId !== 'conv_code') {
        const eingabeText = text.trim();
        let gesendet = false;
        try {
            const resE = await fetch(`${API_BASE}/api/auftraege/${_laufenderAuftragKurz}/eingabe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: eingabeText }),
            });
            gesendet = resE.ok;
        } catch (_) { gesendet = false; }
        addMessage(
            gesendet
                ? '📨 **An den laufenden Hermes gesendet** (Kommentar zur Session)'
                : '⚠️ Kommentar konnte nicht an die Session gesendet werden',
            'assistant'
        );
        setLoading(false);
        state.abbruch = null;
        clearAntwortAuf(); // Zitat an einen laufenden Hermes-Kommentar ist wirkungslos
        return;
    }

    // Leere Blase anlegen, die sich während des Streams füllt. KEINE eigene
    // "Denke nach..."-Animation hier drin: der Lade-/Arbeitsschritt läuft in
    // der unteren #loading-Bubble (setzeTutZeile → "Agent liest…" +
    // setLoading). So gibt es statt zwei konkurrierender Ladeanzeigen nur
    // EINE (Stand 2026-09-09, Auftrag Sebastian).
    const contentDiv = addMessage('', 'assistant');
    // Abbrechen-Button: Für normale LLM-Antworten bewusst KEIN eigener
    // '⏹ Abbrechen'-Button mehr (Stand 2026-08-30, Auftrag Sebastian) — der
    // Stream-Abbruch läuft über den Bearbeiten-Flow bzw. die leere-Eingabe-
    // Abbruchlogik. Auch die Hermes-Zwischenmeldungen tragen seit 2026-09-06
    // keinen eigenen Abbruch-Knopf mehr (schon vorhanden, brichAb deckt den
    // laufenden Hermes-Auftrag ab).
    const entry = state.messages[state.messages.length - 1];
    _auftragStreckeDirekt = false;   // pro Nachricht neu entscheiden

    let antwort = '';
    let abschluss = null;
    let letztesRendern = 0;   // Zeitbremse fürs Neuzeichnen während des Streams
    let quellen = [];         // Fundstellen der Websuche, während sie eintreffen

    // Gemeinsamer Zustand für den Vorleser – er muss auch aus dem Rückfallweg
    // heraus erreichbar sein, deshalb ein Objekt statt einfacher Variablen.
    const zustand = { text: '', fertig: false };

    // Bedienung steht sofort bereit: Man kann das Vorlesen starten, während
    // die Antwort noch geschrieben wird.
    const vorleser = addSpeakControls(
        contentDiv.parentElement.parentElement,
        () => zustand.text,
        () => zustand.fertig,
    );

    try {
        // Loop-Modus (Hermes) aktiv: Nachricht ueber den aktiv-Kanal/Daemon
        // (diese Hermes-Session) beantworten statt DeepSeek-Chat. Nicht
        // streamend - Antwort kommt als fertiger reply.
        if (typeof loopAktiv !== 'undefined' && loopAktiv) {
            // Hermes-Modus aktiv (Wunsch Sebastian): Die Nachricht geht an
            // DIESE Termux-Session (/api/hermes/chat), deren Antwort als
            // Blase erscheint + mit Hermes-Badge (denkt/antwortet).
            hermesStreamBereit = true;
            aktualisiereStatusAnzeige();
            try {
                const hres = await fetch(`${API_BASE}/api/hermes/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nachricht: text,
                        kontext: `Modell=${state.model || ''}, conversation=${state.conversationId || 'conv_main'}`,
                    }),
                    signal: controller.signal,
                });
                const hd = await hres.json().catch(() => ({}));
                const reply = (hd && hd.reply) || '⚠️ Keine Antwort (Hermes).';
                dom.filePreviewList.innerHTML = '';
                dom.filePreview.classList.add('hidden');
                _aktualisiereUploadKnopf();
                zustand.text = reply;
                zustand.fertig = true;
                // Schoene Formatierung: Markdown sauber rendern und die
                // Antwort zeichenweise im eingestellten Stream-Tempo
                // (state.streamMs, Zahnrad) aufbauen - damit man die
                // Geschwindigkeit sieht statt einen ploetzlichen Textblock.
                (async () => {
                    const ms = (typeof state.streamMs === 'number' && state.streamMs > 0)
                        ? state.streamMs : 120;
                    let sichtbar = '';
                    // Haeppchenweise je ein paar Zeichen einfuegen.
                    const anzeige = () => {
                        contentDiv.innerHTML = (typeof parseMarkdownPartial === 'function')
                            ? parseMarkdownPartial(sichtbar)
                            : sichtbar;
                        if (isAtBottom()) scrollToBottom(true);
                    };
                    const chunk = Math.max(2, Math.round(3 * ms / 120));
                    while (sichtbar.length < reply.length) {
                        sichtbar = reply.slice(0, Math.min(reply.length, sichtbar.length + chunk));
                        anzeige();
                        await new Promise(r => setTimeout(r, ms));
                    }
                    anzeige();
                })();
            } finally {
                hermesStreamBereit = false;
                aktualisiereStatusAnzeige();
                // Untere animierte "Denke nach..."-Bubble nach der
                // Hermes-Antwort sicher ausblenden (dieser Zweig macht
                // sonst `return`, ohne setLoading(false) zu rufen). Stand
                // 2026-09-06: Bubble hing sonst im Hermes-/Loop-Modus fest.
                setLoading(false);
            }
            return;
        }
        const res = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                conversation_id: state.conversationId,
                web_search: state.webSearch,
                model: state.model,
                force_agent: forceAgent === true,
                ziel: ziel || undefined,
                // WhatsApp-artiges Antwort-Zitat (falls gesetzt)
                antwort_auf: _antwortAuf ? _antwortAuf.text : undefined,
                // Nur image/pdf senden (sonst 422 am ChatRequest-Literal["image","pdf"].
                files: state.pendingFiles.length > 0
                    ? state.pendingFiles
                        .filter(f => f.type === 'image' || f.type === 'pdf')
                        .map(f => ({
                        id: f.id,
                        filename: f.filename,
                        type: f.type,
                        url: f.url,
                        mime: f.mime,
                        data_url: f.data_url,
                        text: f.text,
                    }))
                    : undefined,
            }),
            signal: controller.signal,
        });
        // NICHT sofort die Vorschau leeren — die Files müssen im Request
        // bleiben, bis das done-Ereignis wirklich kam (siehe letzter Block).
        // Nur die Chips entfernen, damit die nächste Nachricht vorbereitet
        // werden kann; die Daten bleiben in pendingFiles bis zum Abschluss.
        dom.filePreviewList.innerHTML = '';
        dom.filePreview.classList.add('hidden');
        _aktualisiereUploadKnopf();
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}: ${res.statusText}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let puffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            puffer += decoder.decode(value, { stream: true });

            // Ereignisse sind durch eine Leerzeile getrennt; ein
            // unvollständiger Rest bleibt für die nächste Runde liegen.
            const bloecke = puffer.split('\n\n');
            puffer = bloecke.pop();

            for (const block of bloecke) {
                const zeile = block.split('\n').find(z => z.startsWith('data: '));
                if (!zeile) continue;
                let daten;
                try {
                    daten = JSON.parse(zeile.slice(6));
                } catch {
                    continue;
                }

                if (daten.art === 'wahl') {
                    // A/B-Wahl bei erkannten Hermes-Aufgaben im normalen Chat
                    // (Wunsch Sebastian 2026-09-07): Statt stiller Delegation
                    // selbst entscheiden, ob die Aufgabe an den Coding-Chat
                    // (A) oder als eigener paralleler Hermes-Thread hier (B)
                    // geht. Die User-Runde hat das Backend schon persistiert;
                    // die Buttons sind reine UI-Transporte (kein Eintrag).
                    state._wahlAufgabe = daten.aufgabe || '';
                    antwort = '🤔 **Wohin mit dieser Aufgabe?**';
                    zustand.text = antwort;
                    contentDiv.innerHTML = parseMarkdown(antwort);
                    continue;
                }

                if (daten.message) {
                    // Eigenständige Meldung (z. B. "Hermes-Aufgabe übergeben"):
                    // EIGENE Blase mit frischem Zeitstempel + Umlenk-Buttons,
                    // nicht in die Antwort-Blase gemischt. KEIN Ziel-Chip —
                    // die Überschrift ("an den PC-Hermes übergeben") sagt das
                    // Ziel schon; der Chip wäre redundant.
                    // Umlenk-Meldung: EIGENE Blase mit frischem Zeitstempel.
                    // Die untere animierte "Denke nach..."-Bubble (#loading)
                    // bleibt bewusst stehen, bis der finale Abschluss (finally)
                    // sie leert (Stand 2026-09-06: nicht verfrueht ausblenden).
                    const div = addMessage(daten.message, 'assistant');
                    // Kommunikationskanal merken, damit die Umlenk-Buttons
                    // (lokal/Hermes) erscheinen + Eingaben als Kommentar gehen.
                    if (daten.auftrag_id) {
                        _laufenderAuftragKurz = daten.auftrag_id;
                        aktualisiereStatusAnzeige();
                    }
                    continue;
                }

                if (daten.delta) {
                    // Die untere animierte "Denke nach..."-Bubble bleibt bis zum
                    // finalen Abschluss sichtbar (finally-Block), statt
                    // schon beim ersten Textstueck zu verschwinden.
                    // Track C (Hermes live): Beim ersten Event kommt die
                    // auftrag_id mit → den Kommunikationskanal setzen, damit
                    // Nachrichten während des Laufens als /eingabe-Kommentar
                    // an Hermes gehen statt in eine Warteschlange zu rutschen.
                    if (daten.auftrag_id && !_laufenderAuftragKurz) {
                        _laufenderAuftragKurz = daten.auftrag_id;
                        aktualisiereStatusAnzeige();
                    }
                    antwort += daten.delta;
                    zustand.text = antwort;
                    vorleser.neuerText();
                    // Nicht bei jedem Häppchen neu zeichnen – das Neuaufbauen
                    // der Blase würde auf dem Handy ruckeln. Der endgültige
                    // Aufbau passiert ohnehin in finishReply().
                    const jetzt = performance.now();
                    // Streaming-Geschwindigkeit einstellbar (Zahnrad): Die
                    // Render-Frequenz des sichtbaren Texts folgt state.streamMs
                    // (gross = langsamer, zum Mitlesen). Standard 120 ms.
                    const renderIntervall = (typeof state.streamMs === 'number' && state.streamMs > 0)
                        ? state.streamMs : 120;
                    if (jetzt - letztesRendern > renderIntervall) {
                        letztesRendern = jetzt;
                        const untenGewesen = isAtBottom();
                        contentDiv.innerHTML = parseMarkdownPartial(antwort);
                        if (untenGewesen) scrollToBottom(true);
                    }
                } else if (daten.art === 'gedanke' && daten.text) {
                    // Live-Zwischenmeldung von Hermes (Track C): IMMER als
                    // eigene Bubble mit Sekunden-Zeitstempel – nie in die
                    // laufende Antwort-Blase haengen. Den [ISO]-Präfix aus der
                    // Meldung entfernen (Zeit steht schon im Label darunter),
                    // sonst steht der lange String doppelt in der Blase.
                    const { text: htext, zeitIso } = zerlegeHermesMeldung(daten.text);
                    fuegeGedankeMitAbbruchHinzu(
                        htext || daten.text,
                        zeitIso || new Date().toISOString()
                    );
                } else if (daten.done) {
                    // WICHTIG: VOR `daten.sources` pruefen! Das done-Ereignis
                    // traegt selbst sources UND bild_vorschau (Backend chat.py:
                    // Quellen werden im done-Ereignis nochmals mitgeschickt).
                    // Stand die Quellen-Abfrage vorher, schluckte sie das
                    // done-Ereignis, `abschluss` blieb null und die
                    // Bild-Vorschau (zeigeBildVorschau in finishReply) kam nie an.
                    abschluss = daten;
                    if (daten.sources) quellen = mergeQuellen(quellen, daten.sources);
                    // Bild-Vorschau rendert finishReply (nach dem innerHTML).
                    // Hier KEIN redundanter Aufruf — das würde doppelt/uberschrieben.
                    // Der Stream hat die Strecke selbst bis zum Ende geführt
                    // (Track C live) – der 3s-Poller ist dafür nicht nötig.
                    if (daten.auftrag_strecke) {
                        _auftragStreckeDirekt = true;
                        // Auftrag beendet → Kommunikationskanal wieder frei,
                        // damit spätere Nachrichten einen neuen Auftrag starten
                        // statt an die geschlossene Session zu gehen.
                        _laufenderAuftragKurz = null;
                        aktualisiereStatusAnzeige();
                    }
                } else if (daten.sources) {
                    // Können an jedem Häppchen hängen, deshalb laufend sammeln.
                    quellen = mergeQuellen(quellen, daten.sources);
                } else if (daten.error) {
                    // Fehler (z. B. "Fehler im lokalen Hermes-Job"): Kanal
                    // wieder freigeben + Stop-Button weg — sonst bleibt der
                    // rote Stopp-Zustand hängen, obwohl nichts mehr läuft.
                    _laufenderAuftragKurz = null;
                    aktualisiereStatusAnzeige();
                    updateSendButton();
                    throw new Error(daten.error);
                } else if (daten.done) {
                    abschluss = daten;
                    // Bild-Vorschau rendert finishReply (nach dem innerHTML).
                    // Hier KEIN redundanter Aufruf — das würde doppelt/uberschrieben.
                    // Der Stream hat die Strecke selbst bis zum Ende geführt
                    // (Track C live) – der 3s-Poller ist dafür nicht nötig.
                    if (daten.auftrag_strecke) {
                        _auftragStreckeDirekt = true;
                        // Auftrag beendet → Kommunikationskanal wieder frei,
                        // damit spätere Nachrichten einen neuen Auftrag starten
                        // statt an die geschlossene Session zu gehen.
                        _laufenderAuftragKurz = null;
                        aktualisiereStatusAnzeige();
                    }
                }
            }
        }

        if (!antwort) throw new Error('Leere Antwort vom Server');
        zustand.fertig = true;

        // Hochgeladene Dateien aus der Vorschau entfernen – ABER nur, wenn
        // der Abschluss wirklich sauber durchlief (ein done-Ereignis kam).
        // Blieb der Stream stehen / wurde abgebrochen (kein done), behalten
        // wir die Dateien in der Vorschau, damit der Nutzer sie nicht verliert.
        if (abschluss) _raeumeDateiVorschau();

        // Zwischendurch eingetroffene Quellen mit denen aus dem Abschluss
        // zusammenführen – doppelte Adressen fallen dabei weg.
        abschluss = Object.assign({}, abschluss, {
            sources: mergeQuellen(quellen, abschluss && abschluss.sources),
        });
        finishReply(contentDiv, entry, antwort, abschluss, vorleser);
        // A/B-Wahl: Nach dem Markdown-Rebuild von finishReply die Wahl-
        // Buttons wieder in die Blase einhängen (finishReply überschreibt
        // contentDiv.innerHTML und würde sie sonst wegwerfen).
        if (state._wahlAufgabe) {
            bauWahlUi(contentDiv, state._wahlAufgabe);
            state._wahlAufgabe = '';
        }
        return abschluss;

    } catch (err) {
        // Selbst abgebrochen: Das ist kein Fehler, sondern der ausdrückliche
        // Wunsch. Kein Rückfallweg – der würde die Anfrage neu stellen und
        // damit genau das tun, was gerade gestoppt werden sollte.
        if (err.name === 'AbortError') {
            zustand.fertig = true;
            entry.content = antwort;
            contentDiv.innerHTML = parseMarkdown(
                (antwort ? antwort + '\n\n' : '') + '*Abgebrochen.*'
            );
            return null;
        }

        // Fehler (kein Abbruch): Kanal freigeben + Stop-Button zurücksetzen,
        // damit nach einem Fehler (z. B. Hermes-Job) kein roter Zustand hängt.
        _laufenderAuftragKurz = null;
        aktualisiereStatusAnzeige();
        updateSendButton();

        // Kam schon Text an, ist der Stream mittendrin gerissen – dann steht
        // das Bruchstück da und ein zweiter Anlauf würde doppelt abrechnen.
        if (!antwort) {
            console.warn('Streaming fehlgeschlagen, versuche Normalweg:', err);
            try {
                return await sendMessageFallback(text, contentDiv, entry, zustand, vorleser);
            } catch (err2) {
                err = err2;
            }
        }
        zustand.fertig = true;   // Vorleser soll nicht ewig auf Nachschub warten
        console.error('Chat error:', err);

        // Lehnt OpenRouter das Modell ab, hilft eine Verbindungsfehler-Meldung
        // nicht weiter – dann muss das Modell zurück, sonst scheitert auch die
        // nächste Nachricht wieder.
        const abgelehnt = /nicht nutzbar|allowed providers|Enterprise/i.test(err.message || '');
        if (abgelehnt && state.model) {
            const zurueck = state.modelVorher || null;
            state.model = zurueck;
            if (zurueck) localStorage.setItem('model', zurueck);
            else localStorage.removeItem('model');
            setModelLabel();
            contentDiv.innerHTML = parseMarkdown(
                `${err.message}\n\n*Zurückgewechselt auf ${kurzName(zurueck)}.*`
            );
        } else {
            contentDiv.innerHTML = parseMarkdown(
                (antwort ? antwort + '\n\n' : '')
                + `⚠️ **Verbindungsfehler**\n\nKonnte den Agenten nicht erreichen.\n`
                + `- URL: ${API_BASE}\n`
                + `- Fehler: ${err.message}`
            );
        }
        entry.content = antwort;
    } finally {
        // Tut-Zeile zuruecksetzen, sobald die Antwort abgeschlossen ist.
        try { setzeTutZeile(''); } catch (_) {}
        // Nur zuruecksetzen, wenn niemand zwischenzeitlich einen neuen Lauf
        // gestartet hat (kein Stopp-Knopf mehr für normale Antworten).
        if (state.abbruch === controller) state.abbruch = null;
        setLoading(false);
        // WhatsApp-Zitat nach dem Absenden weg (wie WhatsApp).
        clearAntwortAuf();
    }
}

async function sendAudioForTranscription(audioBlob) {
    if (state.isTranscribing) return;
    state.isTranscribing = true;
    setMicStatus('transcribing');
    try {
        const formData = new FormData();
        formData.append('file', audioBlob, 'audio.wav');
        const res = await fetch(`${API_BASE}/api/transcribe`, {
            method: 'POST',
            body: formData,
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        // /critic #7: data.text muss ein String sein
        if (typeof data.text === 'string' && data.text.trim()) {
            setMicStatus('polishing');
            // Diktat SOFORT als echte User-Blase zeigen (wie beim Tippen) —
            // egal ob es an den Agenten, in die Warteschlange oder an Hermes
            // als Kommentar geht. Sonst wirkt es wie "verschluckt".
            const diktat = data.text.trim();
            // Diktat AN vorhandenen Text ANHÄNGEN statt ihn zu ersetzen:
            // Wer vor der Aufnahme schon getippt (oder Dateien angehängt)
            // hat, schickt beim Loslassen die GESAMTE Nachricht (Text +
            // Diktat + Anhang) — die Dateien reisen in state.pendingFiles
            // ohnehin mit dem Request mit.
            const vorhanden = dom.input.value.trim();
            const gesamt = (vorhanden ? vorhanden + ' ' : '') + diktat;
            addMessage(gesamt, 'user');
            dom.input.value = '';
            dom.input.style.height = 'auto';
            await sendMessage(gesamt, false, true); // drittes Flag: Diktat (Blase schon gezeigt)
        } else if (data.error) {
            addMessage(`⚠️ **Spracherkennung fehlgeschlagen**\n\n${data.error}`, 'assistant');
        }
    } catch (err) {
        console.error('Transcription error:', err);
        addMessage(
            `⚠️ **Transkriptionsfehler**\n\nKonnte Audio nicht verarbeiten.\n`
            + `- Fehler: ${err.message}`,
            'assistant'
        );
    } finally {
        state.isTranscribing = false;
        setMicStatus('');
    }
}

// =========================================
// TTS (Text-to-Speech)
// =========================================
/** Rückfall-Vorleser über die Browser-Stimme. Gibt zurück, ob es geklappt hat. */
function speakResponse(text) {
    if (!window.speechSynthesis) {
        console.warn('Browser-Stimme nicht verfügbar.');
        return false;
    }
    const plainText = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/[*_#]/g, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\n+/g, ' ')
        .trim();
    // Obergrenze großzügig: Als Rückfall ist eine lange Vorlesung besser
    // als gar keine. Vorher lag sie bei 500 Zeichen und hat den Rückfall
    // bei fast jeder Antwort stillschweigend verschluckt.
    if (!plainText) return false;
    if (plainText.length > 3000) {
        console.warn('Text zu lang für die Browser-Stimme (%d Zeichen).', plainText.length);
        return false;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(plainText);
    utterance.lang = 'de-DE';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    const voices = window.speechSynthesis.getVoices();
    const germanVoice = voices.find(v => v.lang.startsWith('de'));
    if (germanVoice) utterance.voice = germanVoice;
    window.speechSynthesis.speak(utterance);
    return true;
}

if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
    };
}

// =========================================
// Spracheingabe – WAV-Aufnahme (wie TypeFREE)
// =========================================
// MediaRecorder liefert nur WebM/Opus; der Transkriptions-Anbieter lehnt das
// mit HTTP 400 ab. WAV/PCM-16 geht zuverlässig durch – genau wie bei TypeFREE.
// Deshalb greifen wir die rohen PCM-Blöcke über einen AudioWorklet ab und
// bauen die WAV-Datei selbst. Mono, 16 Bit, native Abtastrate des Geräts.
let audioContext = null;
let workletNode = null;
let sourceNode = null;
let audioStream = null;
let pcmChunks = [];

function releaseAudioStream() {
    if (workletNode) {
        workletNode.port.onmessage = null;
        workletNode.disconnect();
        workletNode = null;
    }
    if (sourceNode) {
        sourceNode.disconnect();
        sourceNode = null;
    }
    if (audioContext) {
        audioContext.close().catch(() => {});
        audioContext = null;
    }
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
}

/** Float32-Blöcke [-1,1] → WAV-Datei (PCM 16 Bit, Mono). */
function encodeWav(chunks, sampleRate) {
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
    view.setUint32(16, 16, true);              // Länge des fmt-Blocks
    view.setUint16(20, 1, true);               // Format: unkomprimiertes PCM
    view.setUint16(22, 1, true);               // Kanäle: Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);  // Bytes pro Sekunde
    view.setUint16(32, 2, true);               // Bytes pro Sample-Frame
    view.setUint16(34, 16, true);              // Bits pro Sample
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

async function startRecording() {
    // Ohne sicheren Kontext (localhost oder HTTPS) entfernt der Browser die
    // Mikrofon-Schnittstelle ersatzlos – sie fehlt dann, statt eine
    // Berechtigung zu verweigern. Es gibt also nichts zu erlauben.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        addMessage(
            '⚠️ **Spracheingabe ist hier nicht möglich.**\n\n'
            + 'Der Browser gibt das Mikrofon nur über `localhost` oder HTTPS frei. '
            + `Diese Seite läuft über \`${location.origin}\`.\n\n`
            + 'Zum Diktieren die App direkt am Handy öffnen: `http://localhost:8080`',
            'assistant'
        );
        setMicStatus('');
        return;
    }

    try {
        audioStream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1 },
        });

        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        // Auf Android startet der Context oft angehalten.
        if (audioContext.state === 'suspended') await audioContext.resume();
        await audioContext.audioWorklet.addModule('pcm-recorder.js');

        pcmChunks = [];
        sourceNode = audioContext.createMediaStreamSource(audioStream);
        workletNode = new AudioWorkletNode(audioContext, 'pcm-recorder');
        workletNode.port.onmessage = (event) => pcmChunks.push(event.data);
        sourceNode.connect(workletNode);
        // Ohne Verbindung zur destination zieht die Audio-Engine keine Daten.
        // Der Worklet schreibt nichts in seine Ausgänge – bleibt also stumm.
        workletNode.connect(audioContext.destination);

        state.isRecording = true;
        setMicStatus('recording');
        dom.input.placeholder = 'Aufnahme läuft – Senden beendet sie';
        updateSendButton();
    } catch (err) {
        console.warn('Aufnahme konnte nicht gestartet werden:', err);
        releaseAudioStream();
        state.isRecording = false;
        setMicStatus('');
        dom.input.placeholder = 'Nachricht eingeben...';
        addMessage(
            '⚠️ **Mikrofon nicht verfügbar.**\n\n'
            + 'Bitte erlaube den Mikrofon-Zugriff in den Browser-Einstellungen.\n'
            + `- Fehler: ${err.message}`,
            'assistant'
        );
    }
}

function stopRecording() {
    if (!state.isRecording) return;

    const sampleRate = audioContext ? audioContext.sampleRate : 48000;
    const chunks = pcmChunks;
    pcmChunks = [];

    state.isRecording = false;
    dom.input.placeholder = 'Nachricht eingeben...';
    releaseAudioStream();
    updateSendButton();

    if (!chunks.length) {
        setMicStatus('');
        return;
    }
    sendAudioForTranscription(encodeWav(chunks, sampleRate));
}

// ── Spracheingabe fuer Formular-FELDER (Neue-Person-Zusatzkontext u. a.) ────
// Wie die Chat-Zeile, aber unabhaengig: nimmt Audio auf und schreibt das
// Transkript in das angegebene Text-Element (input/textarea). Nur EIN Feld kann
// gleichzeitig aufnehmen; erneuter Tipp auf denselben Knopf stoppt.
let _feldDiktatZiel = null;    // aktuell besprochenes Feld-Element
let _feldDiktatBtn = null;     // dessen Mikrofon-Knopf
async function starteFeldDiktat(zielElem, btn) {
    if (_feldDiktatZiel) { stopFeldDiktat(); return; }   // laeuft schon -> stoppen
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        addMessage('⚠️ **Spracheingabe hier nicht möglich.** Mikrofon nur über `localhost` oder HTTPS. → App direkt auf `http://localhost:8080` öffnen.', 'assistant');
        return;
    }
    try {
        _feldDiktatZiel = zielElem;
        _feldDiktatBtn = btn;
        _feldDiktatPcm = [];
        _feldDiktatAudioStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 } });
        _feldDiktatCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (_feldDiktatCtx.state === 'suspended') await _feldDiktatCtx.resume();
        await _feldDiktatCtx.audioWorklet.addModule('pcm-recorder.js');
        const srcN = _feldDiktatCtx.createMediaStreamSource(_feldDiktatAudioStream);
        const wk = new AudioWorkletNode(_feldDiktatCtx, 'pcm-recorder');
        wk.port.onmessage = (event) => _feldDiktatPcm.push(event.data);
        srcN.connect(wk);
        wk.connect(_feldDiktatCtx.destination);
        _feldDiktatTrackNode = wk;
        if (btn) {
            btn.style.background = '#c33'; btn.style.color = '#fff';
            btn.textContent = '⬤ Aufnahme läuft…';
        }
    } catch (err) {
        _feldDiktatRelease();
        _feldDiktatZiel = null;
        if (btn) { btn.textContent = '🎙'; btn.style.background = ''; }
        addMessage('⚠️ **Mikrofon nicht verfügbar.** ' + (err && err.message ? err.message : ''), 'assistant');
    }
}
let _feldDiktatPcm = [];
let _feldDiktatAudioStream = null;
let _feldDiktatCtx = null;
let _feldDiktatTrackNode = null;
function _feldDiktatRelease() {
    try { if (_feldDiktatTrackNode) _feldDiktatTrackNode.disconnect(); } catch (e) {}
    _feldDiktatTrackNode = null;
    try { if (_feldDiktatAudioStream) _feldDiktatAudioStream.stop(); } catch (e) {}
    _feldDiktatAudioStream = null;
    try { if (_feldDiktatCtx) _feldDiktatCtx.close && _feldDiktatCtx.close(); } catch (e) {}
    _feldDiktatCtx = null;
}
function stopFeldDiktat() {
    const ziel = _feldDiktatZiel;
    const btn = _feldDiktatBtn;
    const sampleRate = _feldDiktatCtx ? _feldDiktatCtx.sampleRate : 48000;
    const chunks = _feldDiktatPcm;
    _feldDiktatPcm = [];
    _feldDiktatRelease();
    _feldDiktatZiel = null;
    _feldDiktatBtn = null;
    if (btn) { btn.textContent = '🎙'; btn.style.background = ''; }
    if (!chunks.length || !ziel) return;
    // Auf Transkription warten und ins ZIEL-Feld schreiben
    transkribiereFeld(chunks, sampleRate, ziel);
}
async function transkribiereFeld(chunks, sampleRate, ziel) {
    try {
        const formData = new FormData();
        formData.append('file', encodeWav(chunks, sampleRate), 'audio.wav');
        const res = await fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        const txt = (typeof data.text === 'string' ? data.text.trim() : '');
        if (txt && ziel) {
            const alt = (ziel.value || '').trim();
            ziel.value = alt ? alt + ' ' + txt : txt;   // ANHAENGEN an Bestehendes
        }
    } catch (e) {
        addMessage('⚠️ **Feld-Spracherkennung fehlgeschlagen:** ' + (e && e.message), 'assistant');
    }
}
// Kleiner Mikrofon-Knopf, der ein Textfeld zum Diktieren oeffnet (WhatsApp-artig).
// Fuegt rechts neben dem Feld einen 🎙-Button hinzu.
function fuegeFeldMikrofonHinzu(zielElem, container, mt) {
    if (!zielElem || typeof navigator.mediaDevices === 'undefined') return;
    const b = document.createElement('button');
    b.textContent = '🎙';
    b.title = mt || 'Diktieren';
    b.type = 'button';
    b.style.cssText = 'margin-left:4px;padding:2px 8px;border:1px solid #f88;border-radius:6px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.8rem;vertical-align:middle';
    b.addEventListener('click', () => starteFeldDiktat(zielElem, b));
    (container || (zielElem.parentNode || null)).appendChild(b);
}

dom.webBtn.addEventListener('click', () => setWebSearch(naechsterWebModus()));

dom.modelBtn.addEventListener('click', oeffneBlatt);
dom.modelClose.addEventListener('click', schliesseBlatt);
dom.modelSearch.addEventListener('input', zeichneListe);
dom.privacyBtn.addEventListener('click', () => setPrivacy(!state.noRetention));

// ── Streaming-Geschwindigkeit (Zahnrad oben rechts, Wunsch Sebastian) ──
// Die Verzoegerung zwischen SSE-delta-Haeppchen ist einstellbar (moeglichst
// langsam, damit man mitlesen kann). Gespeichert in localStorage.
state.streamMs = parseInt(localStorage.getItem('stream_ms') || '120', 10);
dom.streamSettingsBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dom.streamMenu.hidden = !dom.streamMenu.hidden;
});
document.addEventListener('click', () => { if (dom.streamMenu && !dom.streamMenu.hidden) dom.streamMenu.hidden = true; });
document.querySelectorAll('.stream-opt').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        state.streamMs = parseInt(btn.dataset.ms || '120', 10);
        localStorage.setItem('stream_ms', String(state.streamMs));
        dom.streamMenu.hidden = true;
    });
});

// Loop-Button: startet/beendet manuell den lokalen Hermes-Loop (end-to-end).
// An:   kein Auftrag noetig, nur aktivieren (Session wird bei Bedarf
//       persistent in tmux erzeugt; im query-Kanal Subprozess je Auftrag).
// Aus:  POST /api/hermes/beenden killt die (persistente) Session.
// Loop-Zustand ueber Reload hinweg persistent halten (Wunsch Sebastian:
// ein Reload soll die Hermes-Aktivierung NICHT zuruecksetzen).
let loopAktiv = localStorage.getItem('hermes_loop_aktiv') === 'true';
function _setzeLoopZustand(aktiv) {
    loopAktiv = aktiv;
    localStorage.setItem('hermes_loop_aktiv', String(aktiv));
    if (dom.loopBtn) dom.loopBtn.classList.toggle('active', aktiv);
    if (dom.loopBtn) dom.loopBtn.setAttribute('aria-pressed', String(aktiv));
    if (dom.loopLabel) dom.loopLabel.textContent = aktiv ? 'Hermes: an' : 'Hermes';
}
async function toggleLoop() {
    const aktiv = !loopAktiv;
    _setzeLoopZustand(aktiv);
    try {
        if (aktiv) {
            const res = await fetch(`${API_BASE}/api/hermes/aktivieren`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    aufgabe: 'Bereit: verarbeite die naechsten Nachrichten als Aufgabe. Antworte nach jeder Eingabe kurz, was du tust.',
                }),
            });
            const d = await res.json().catch(() => ({}));
            addMessage(`🔁 **Hermes aktiviert**. Der lokale Hermes ist end-to-end verbunden.`, 'assistant');
        } else {
            const res = await fetch(`${API_BASE}/api/hermes/beenden`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const d = await res.json().catch(() => ({}));
            addMessage(
                `⬛ **Hermes gestoppt**.\n${d.hinweis || `(Session ${d.session || 'hermes_termux'} bleibt bestehen — du kannst weiter in Termux schreiben.)`}`,
                'assistant'
            );
        }
    } catch (err) {
        // Bei Fehler Zustand zuruecksetzen.
        _setzeLoopZustand(!loopAktiv);
        addMessage(`⚠️ Hermes-Umschaltung fehlgeschlagen: ${err.message || err}`, 'assistant');
    }
}
dom.loopBtn.addEventListener('click', toggleLoop);

// Beim Laden den persistenten Hermes-Zustand sichtbar machen (Wunsch:
// Reload setzt die Aktivierung nicht zurueck). Funktion, falls vorhanden.
if (typeof _setzeLoopZustand === 'function') _setzeLoopZustand(loopAktiv);

dom.modelFilters.addEventListener('click', (e) => {
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    const f = chip.dataset.filter;
    if (state.filters.has(f)) state.filters.delete(f);
    else state.filters.add(f);
    chip.classList.toggle('on', state.filters.has(f));
    zeichneListe();
});

// Tippen auf den abgedunkelten Hintergrund schließt – auf dem Handy die
// natürlichste Geste, um ein Blatt wieder loszuwerden.
dom.modelSheet.addEventListener('click', (e) => {
    if (e.target === dom.modelSheet) schliesseBlatt();
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !dom.modelSheet.hidden) schliesseBlatt();
    if (e.key === 'Escape' && !dom.chatSheet.hidden) schliesseChatBlatt();
});

dom.micBtn.addEventListener('click', () => {
    if (state.isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

// =========================================
// Event Handlers
// =========================================
dom.input.addEventListener('input', () => {
    dom.input.style.height = 'auto';
    dom.input.style.height = Math.min(dom.input.scrollHeight, 120) + 'px';
    updateSendButton();
});

dom.input.addEventListener('keydown', (e) => {
    // Enter erzeugt eine neue Zeile (Standard des <textarea>), wie bei
    // WhatsApp/Telegram. Gesendet wird nur über den Senden-Button — oder
    // bequem per Strg+Enter (Cmd+Enter am Mac).
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
    }
});

dom.sendBtn.addEventListener('click', handleSubmit);

// =========================================
// Kontextmenü für Chat-Blasen: Kopieren & Bearbeiten
// =========================================
// Rechtsklick (am Handy: langes Drücken) auf eine Nachricht öffnet ein
// kleines Menü. „Nachricht kopieren" gibt es für jede Blase, „Nachricht
// bearbeiten" nur für User-Nachrichten (legt den Text zurück in die
// Eingabe). Das Menü ist ein Mini-Element und bekommt nach Repo-Konvention
// Inline-Stile statt style.css-Einträge.
const kontextMenue = document.createElement('div');
kontextMenue.style.cssText =
    'position:fixed;z-index:1000;min-width:210px;background:#1e1e2e;'
    + 'border:1px solid #444;border-radius:10px;'
    + 'box-shadow:0 8px 24px rgba(0,0,0,.5);padding:6px;display:none;'
    + 'font-size:13px;user-select:none';
kontextMenue.innerHTML =
    `<button type="button" data-aktion="kopieren" style="display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;background:none;border:none;border-radius:7px;color:#ddd;font:inherit;text-align:left;cursor:pointer">`
        + `📋 Nachricht kopieren</button>`
    + `<button type="button" data-aktion="teil_kopieren" style="display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;background:none;border:none;border-radius:7px;color:#ddd;font:inherit;text-align:left;cursor:pointer">`
        + `✂️ Teil auswählen & kopieren</button>`
    + `<button type="button" data-aktion="bearbeiten" style="display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;background:none;border:none;border-radius:7px;color:#ddd;font:inherit;text-align:left;cursor:pointer">`
        + `✏️ Nachricht bearbeiten</button>`;
document.body.appendChild(kontextMenue);

let kontextZielText = '';
let kontextZielBlase = null;   // die .message-Blasen, aus der das Menü geöffnet wurde
let kontextKopierTimer = null;

/** Liefert den kopierbaren Text einer Blase: User exakt wie getippt,
 *  Assistant roh (Markdown) bzw. sichtbarer Text bei gestreamten Blasen. */
function kontextTextAusBlase(blase) {
    const roh = blase.dataset.klarText || '';
    if (roh) return roh;
    const inhalt = blase.querySelector('.message-content');
    return inhalt && inhalt.innerText ? inhalt.innerText.trim() : '';
}

// ── Teil-Kopie: markierbare Blase + Kopier-Leiste ─────────────────────────
// Quelle: eine bestehende .message-Blase (lang gedrückt) ODER ein roher Text.
// Leerer/roher-Text-Fall: die Leiste kopiert dann die Textauswahl, falls der
// Nutzer Text anderswo markiert hat.
let teilKopieLeiste = null;
let teilKopieBlase = null;

function leisteTeilKopieAktivieren(quelle) {
    if (teilKopieLeiste) teilKopieLeiste.remove();
    teilKopieLeiste = document.createElement('div');
    teilKopieLeiste.style.cssText =
        'position:fixed;left:0;right:0;bottom:0;z-index:1100;'
        + 'display:flex;justify-content:center;gap:10px;padding:12px 16px;'
        + 'background:#1e1e2e;border-top:1px solid #444;'
        + 'box-shadow:0 -4px 16px rgba(0,0,0,.4);font-size:14px';
    const btnKopieren = document.createElement('button');
    btnKopieren.type = 'button';
    btnKopieren.textContent = '✂️ Auswahl kopieren';
    btnKopieren.style.cssText = kopierLeisteBtnStyle(true);
    const btnAbbrechen = document.createElement('button');
    btnAbbrechen.type = 'button';
    btnAbbrechen.textContent = 'Abbrechen';
    btnAbbrechen.style.cssText = kopierLeisteBtnStyle(false);
    teilKopieLeiste.appendChild(btnKopieren);
    teilKopieLeiste.appendChild(btnAbbrechen);
    document.body.appendChild(teilKopieLeiste);

    // Blase markierbar machen (falls vorhanden), damit man den Teil wählen kann.
    teilKopieBlase = (quelle && quelle.nodeType === 1) ? quelle : null;
    const inhalt = teilKopieBlase ? teilKopieBlase.querySelector('.message-content') : null;
    if (inhalt) {
        inhalt.style.userSelect = 'text';
        inhalt.style.webkitUserSelect = 'text';
        inhalt.style.cursor = 'text';
        teilKopieBlase.setAttribute('data-teilkopie', '1');
    }

    const schliessen = () => {
        if (teilKopieBlase) {
            const i = teilKopieBlase.querySelector('.message-content');
            if (i) { i.style.userSelect = ''; i.style.webkitUserSelect = ''; i.style.cursor = ''; }
            teilKopieBlase.removeAttribute('data-teilkopie');
        }
        teilKopieLeiste.remove();
        teilKopieLeiste = null;
        teilKopieBlase = null;
    };

    btnAbbrechen.addEventListener('click', schliessen);
    btnKopieren.addEventListener('click', () => {
        const sel = (window.getSelection && window.getSelection().toString()) || '';
        const text = sel.trim() || teilKopieBlaseText(teilKopieBlase);
        kopiereText(text).then(() => {
            btnKopieren.textContent = '✓ Kopiert';
            setTimeout(schliessen, 800);
        }).catch(() => { btnKopieren.textContent = '⚠️ Fehler'; });
    });

    // Klick außerhalb schließt die Teil-Kopie-Leiste.
    setTimeout(() => {
        document.addEventListener('click', function teilkopieAussen(e) {
            if (teilKopieLeiste && !teilKopieLeiste.contains(e.target)) {
                schliessen();
                document.removeEventListener('click', teilkopieAussen);
            }
        });
    }, 0);
    kontextMenueSchliessen();
}

function kopierLeisteBtnStyle(primär) {
    return primär
        ? 'padding:10px 18px;border:none;border-radius:9px;background:#4c6ef5;'
          + 'color:#fff;font:inherit;font-weight:600;cursor:pointer'
        : 'padding:10px 18px;border:none;border-radius:9px;background:#333;'
          + 'color:#ccc;font:inherit;cursor:pointer';
}

function teilKopieBlaseText(blase) {
    if (!blase) return '';
    return kontextTextAusBlase(blase);
}

function kopiereText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
    }
    const helfer = document.createElement('textarea');
    helfer.value = text;
    helfer.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(helfer);
    helfer.select();
    try { document.execCommand('copy'); } catch (_) {}
    helfer.remove();
    return Promise.resolve();
}

function kontextMenueZeigen(x, y) {
    kontextMenue.style.display = 'block';
    // Nicht über den Bildschirmrand hinausragen lassen.
    const rect = kontextMenue.getBoundingClientRect();
    kontextMenue.style.left = Math.max(4, Math.min(x, window.innerWidth - rect.width - 8)) + 'px';
    kontextMenue.style.top = Math.max(4, Math.min(y, window.innerHeight - rect.height - 8)) + 'px';
}

function kontextMenueSchliessen() {
    kontextMenue.style.display = 'none';
    // „Kopiert"-Rückmeldung zurücksetzen, falls noch sichtbar.
    const kopiert = kontextMenue.querySelector('[data-aktion="kopieren"]');
    if (kopiert.textContent !== '📋 Nachricht kopieren') {
        clearTimeout(kontextKopierTimer);
        kopiert.textContent = '📋 Nachricht kopieren';
    }
}

kontextMenue.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn || !kontextZielText) return;
    if (btn.dataset.aktion === 'kopieren') {
        const kopieren = () => {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(kontextZielText);
            }
            // Rückfall für ältere Browser/WebViews ohne Clipboard-API.
            const helfer = document.createElement('textarea');
            helfer.value = kontextZielText;
            helfer.style.cssText = 'position:fixed;opacity:0';
            document.body.appendChild(helfer);
            helfer.select();
            try { document.execCommand('copy'); } catch (_) {}
            helfer.remove();
            return Promise.resolve();
        };
        kopieren()
            .then(() => {
                btn.textContent = '✓ Kopiert';
                clearTimeout(kontextKopierTimer);
                kontextKopierTimer = setTimeout(() => {
                    btn.textContent = '📋 Nachricht kopieren';
                }, 1500);
            })
            .catch(() => { btn.textContent = '⚠️ Kopieren fehlgeschlagen'; });
        kontextMenueSchliessen();
    } else if (btn.dataset.aktion === 'teil_kopieren') {
        // Teil-Kopie: Die Blase wird markierbar (Textauswahl), unten erscheint
        // eine Leiste „✂️ Auswahl kopieren“ / „Abbrechen“. Kopiert wird genau
        // der markierte Teil (window.getSelection) statt des ganzen Textes.
        kontextMenueSchliessen();
        leisteTeilKopieAktivieren(kontextZielBlase || kontextZielText);
    } else if (btn.dataset.aktion === 'bearbeiten') {
        // Bearbeiten-Flow: User-Nachricht zum Neu-Formulieren zurück in die
        // Eingabe legen. Dabei wird (a) ein noch laufender Antwort-Stream
        // gestoppt, (b) die bearbeitete User-Blase samt ihrer Antwort aus
        // dem Verlauf/DOM entfernt und (c) die Runde serverseitig gelöscht —
        // damit nach dem erneuten Absenden der neue Stream frisch startet und
        // nach einem Reload keine alte Fassung wieder auftaucht.
        // NUR den LLM-Stream stoppen; ein laufender Hermes-Auftrag bleibt
        // davon unberührt (das Abbruch-Recht liegt beim Abbrechen-Button).
        if (state.abbruch && state.abbruch.abort) {
            state.abbruch.abort();
            state.abbruch = null;
        }
        // Die bearbeitete Runde immer aus DOM + state.messages entfernen —
        // egal ob ein Stream lief (dann wird auch die „Denke nach…"-Antwort-
        // Blase entfernt) oder die Antwort schon fertig war.
        entferneLetzteRundeAusDom();
        // Die alte Runde (User + Antwort) dauerhaft aus dem Server-Verlauf
        // löschen, damit nach Reload nichts Falsches steht.
        try {
            fetch(`${API_BASE}/api/chat/letzte-runde`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ conversation_id: state.conversationId || undefined }),
            }).catch(() => {});
        } catch (_) {}

        // User-Nachricht zurück in die Eingabe legen (Cursor ans Ende).
        dom.input.value = kontextZielText;
        dom.input.style.height = 'auto';
        dom.input.style.height = Math.min(dom.input.scrollHeight, 120) + 'px';
        const ende = dom.input.value.length;
        dom.input.setSelectionRange(ende, ende);
        dom.input.focus();
        updateSendButton();
        kontextMenueSchliessen();
        kontextZielBlase = null;
    }
});

/** Entfernt die letzte Runde (letzte User-Blase + die direkt folgende
 *  Assistant-Blase) aus dem DOM und aus `state.messages`. Dazu gehören auch
 *  zwischenliegende Blasen einer laufenden Antwort (z. B. die leere
 *  Antwort-Blase im „Denke nach…"-Zustand). Liefert true, wenn etwas entfernt
 *  wurde. */
function entferneLetzteRundeAusDom() {
    // Letzte User-Blase im DOM finden.
    const alle = Array.from(dom.messages.querySelectorAll('.message'));
    let letzterUser = null;
    let letzterUserIdx = -1;
    for (let i = alle.length - 1; i >= 0; i--) {
        if (alle[i].classList.contains('user')) { letzterUser = alle[i]; letzterUserIdx = i; break; }
    }
    if (!letzterUser) return false;

    // User-Blase + alle folgenden Blasen bis zur nächsten User-Blase entfernen
    // (das ist die Antwort-Runde; meist genau eine Assistant-Blase, bei
    // gestreamten/mehrteiligen Antworten auch mehrere).
    let entfernt = false;
    for (let i = alle.length - 1; i >= letzterUserIdx; i--) {
        alle[i].remove();
        entfernt = true;
    }
    // state.messages entsprechend bereinigen: Einträge von hinten, deren Rolle
    // zur entfernten Runde gehört (die letzte User-Nachricht + alles danach).
    // Wir entfernen vom Ende bis einschließlich der letzten user-Nachricht.
    if (state.messages.length) {
        let start = state.messages.length - 1;
        while (start >= 0 && state.messages[start].role !== 'user') start--;
        if (start >= 0) {
            // Sonderfall: Läuft gerade eine Antwort (letzer Eintrag ist eine
            // nicht-user-Zeile), sind alle Einträge ab `start` die Runde.
            state.messages.splice(start);
        }
    }
    return entfernt;
}

// Rechtsklick (langes Drücken) auf eine Blase öffnet das Menü.
dom.messages.addEventListener('contextmenu', (e) => {
    const blase = e.target.closest('.message');
    if (!blase || !dom.messages.contains(blase)) return;
    const text = kontextTextAusBlase(blase);
    if (!text) return;   // z. B. noch leere Streaming-Blase
    e.preventDefault();
    kontextZielText = text;
    kontextZielBlase = blase;
    // Bearbeiten gibt es nur für User-Nachrichten.
    const istUser = blase.classList.contains('user');
    kontextMenue.querySelector('[data-aktion="bearbeiten"]').style.display = istUser ? '' : 'none';
    // Label zurücksetzen (falls vorher „✓ Kopiert" angezeigt wurde).
    const kopiert = kontextMenue.querySelector('[data-aktion="kopieren"]');
    if (kopiert.textContent !== '📋 Nachricht kopieren') {
        clearTimeout(kontextKopierTimer);
        kopiert.textContent = '📋 Nachricht kopieren';
    }
    kontextMenueZeigen(e.clientX, e.clientY);
});

// Klick woanders, Escape oder Scrollen schließt das Menü wieder.
document.addEventListener('click', () => kontextMenueSchliessen());
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') kontextMenueSchliessen();
});
window.addEventListener('scroll', () => kontextMenueSchliessen(), true);
    // Ein-Chat: newChatBtn/chatsBtn existieren nicht mehr (Buttons entfernt).
    // Guard, damit die Initialisierung nicht an null-Referenzen crasht.
    if (dom.newChatBtn) dom.newChatBtn.addEventListener('click', neuesGespraech);
    if (dom.chatsBtn) dom.chatsBtn.addEventListener('click', oeffneChatBlatt);
    if (dom.chatsClose) dom.chatsClose.addEventListener('click', schliesseChatBlatt);
// Tippen auf den abgedunkelten Hintergrund schließt – auf dem Handy die
// natürlichste Geste, um ein Blatt wieder loszuwerden.
dom.chatSheet.addEventListener('click', (e) => {
    if (e.target === dom.chatSheet) schliesseChatBlatt();
});

/**
 * Legt eine Nachricht als graue Blase in den Verlauf, die noch nicht
 * abgeschickt ist. Sie kommt bewusst nicht in state.messages – dort steht
 * nur, was der Agent auch wirklich gesehen hat.
 */
function zeigeWartendeNachricht(text) {
    const div = document.createElement('div');
    div.className = 'message user queued';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${escapeHtml(text)}</p>`;
    div.appendChild(contentDiv);

    const verwerfen = document.createElement('button');
    verwerfen.type = 'button';
    verwerfen.className = 'queued-note';
    verwerfen.textContent = 'wartet – tippen zum Verwerfen';
    verwerfen.addEventListener('click', () => {
        state.warteschlange = state.warteschlange.filter(e => e.element !== div);
        div.remove();
    });
    div.appendChild(verwerfen);

    dom.messages.appendChild(div);
    scrollToBottom(true);
    return div;
}

/** Bricht die laufende Antwort ab und legt Wartendes zurück in die Eingabe.
 *  Läuft dabei ein Hermes-Auftrag (Track C), wird er auch backend-seitig
 *  beendet (POST /abbrechen: tmux-Session killen + Buch auf 'fehler') — sonst
 *  arbeitet Hermes im Hintergrund weiter, auch wenn man ihn stoppen will. */
function brichAb() {
    // Stream abbrechen (falls einer läuft) — aber NICHT früh returnen,
    // wenn nur ein Hermes-Auftrag ohne aktiven Stream läuft: der Auftrag
    // muss trotzdem beendet werden (Stopp-Button bleibt verfügbar).
    if (state.abbruch) state.abbruch.abort();

    // Laufenden Hermes-Auftrag sauber beenden (auch bei offener Rückfrage).
    if (_laufenderAuftragKurz) {
        const id = _laufenderAuftragKurz;
        _laufenderAuftragKurz = null;
        aktualisiereStatusAnzeige();
        fetch(`${API_BASE}/api/auftraege/${id}/abbrechen`, { method: 'POST' })
            .then(() => addMessage('🛑 **Hermes-Aufgabe abgebrochen.**', 'assistant'))
            .catch(() => addMessage('⚠️ Abbruch-Fehlschlag – Hermes arbeitet evtl. weiter.', 'assistant'));
    }

    // Was noch wartete, darf nicht stillschweigend verschwinden – es landet
    // zurück im Eingabefeld, damit nichts Getipptes verloren geht.
    if (state.warteschlange.length) {
        const offen = state.warteschlange.map(e => e.text);
        state.warteschlange.forEach(e => e.element.remove());
        state.warteschlange = [];
        const bestand = dom.input.value.trim();
        dom.input.value = (bestand ? bestand + '\n' : '') + offen.join('\n');
        dom.input.dispatchEvent(new Event('input'));
    }
}

/** Schickt ab und arbeitet danach nach und nach ab, was sich angesammelt hat. */
async function sendeUndArbeiteAb(text) {
    await sendMessage(text);
    while (state.warteschlange.length) {
        const naechste = state.warteschlange.shift();
        naechste.element.remove();
        // ausWarteschlange=true → nicht erneut einreihen, sondern wirklich senden
        // (auch wenn währenddessen wieder ein Stream läuft).
        await sendMessage(naechste.text, true);
    }
}

async function handleSubmit() {
    // Läuft gerade eine Aufnahme, bedeutet Senden bzw. Enter: Aufnahme
    // beenden. Transkription und Absenden laufen danach von selbst weiter.
    if (state.isRecording) {
        stopRecording();
        return;
    }
    const text = dom.input.value.trim();

    // Leere Eingabe bei laufender Antwort/Auftrag heißt: abbrechen.
        if (!text) {
            if (state.abbruch || _laufenderAuftragKurz) brichAb();
            return;
        }

    dom.input.value = '';
    dom.input.style.height = 'auto';

    // Schreibt der Agent noch, wird angehängt statt dazwischenzufunken.
    if (state.abbruch) {
        // Läuft ein Hermes-Auftrag (Track C), geht die Nachricht sofort als
        // Kommentar an die Session (sendMessage → POST /eingabe) — so kann man
        // Hermes während der Arbeit direkt steuern/Zwischenfragen stellen.
        // Sonst in die sichtbare Warteschlange legen (nach Stream-Ende senden).
        if (_laufenderAuftragKurz) {
            await sendMessage(text);
        } else {
            state.warteschlange.push({ text, element: zeigeWartendeNachricht(text) });
            updateSendButton();
        }
        return;
    }

    updateSendButton();
    await sendeUndArbeiteAb(text);
}

// =========================================
// Periodic Health Check
// =========================================
let healthCheckInterval = null;
let autoCloseTimer = null;
let startupCloseTimer = null;    // eigener Timer fuer checkAndAutoClose

/** Schließt den Tab automatisch, wenn der Server nach dem Laden nicht
 *  erreichbar ist. Verhindert, dass sich beim erneuten Öffnen eines
 *  Localhost-Tabs immer neue leere Fenster ansammeln. */
async function checkAndAutoClose() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
            // Server erreichbar – Tab soll offen bleiben.
            if (startupCloseTimer) {
                clearTimeout(startupCloseTimer);
                startupCloseTimer = null;
            }
            return;
        }
    } catch (_) {
        // Server nicht erreichbar – Timeout starten/austicken lassen
    }
    if (!startupCloseTimer) {
        startupCloseTimer = setTimeout(() => {
            // Nur schließen, wenn der Server immer noch weg ist
            fetch(`${API_BASE}/api/health`).catch(() => window.close());
            startupCloseTimer = null;
        }, 5000);
    }
}

function startHealthChecks() {
    checkAndAutoClose();
    checkHealth();
    healthCheckInterval = setInterval(checkHealth, 30000);
}

// =========================================
// PWA: Register Service Worker
// =========================================
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('sw.js')
        .then(() => console.log('Service Worker registered'))
        .catch(err => console.warn('Service Worker registration failed:', err));
}

// =========================================
// Init
// =========================================
/**
 * Holt das zuletzt geführte Gespräch zurück in die Oberfläche.
 *
 * Der Server hält den Verlauf seit Neuestem auf der Platte. Ohne diesen
 * Schritt wäre er zwar gespeichert, aber unsichtbar – nach jedem Neustart
 * stünde wieder ein leeres Fenster da.
 */
/**
 * Beginnt ein neues Gespräch: Anzeige leeren, Verweis lösen.
 *
 * Das alte Gespräch bleibt auf der Platte liegen — hier wird nichts
 * gelöscht, nur beiseitegelegt. Die neue Kennung vergibt der Server beim
 * nächsten Absenden von allein.
 */
function neuesGespraech() {
    // Ein-Chat-Modus (seit 2026-08): Es gibt genau EINE fortlaufende
    // Conversation. Der '+'-Button ist ausgeblendet; sollte diese Funktion
    // trotzdem erreicht werden (z. B. alte UI), tut sie NICHTS zerstörerisches —
    // der laufende Thread bleibt erhalten (kein conversationId-Reset).
    addMessage('ℹ️ Ein-Chat-Modus: Es gibt nur dieses eine Gespräch – es wird fortgeführt.', 'assistant');
}

/** Holt die Kennung des zuletzt geführten Gesprächs vom Server. */
async function letzteGespraechsId() {
    try {
        const res = await fetch(`${API_BASE}/api/conversations`);
        if (!res.ok) return null;
        const daten = await res.json();
        const liste = daten.conversations || [];
        // Der Server hängt neue Gespräche hinten an, das letzte ist das jüngste.
        const letztes = liste.filter(c => c.message_count > 0).pop();
        return letztes ? letztes.id : null;
    } catch {
        return null;
    }
}

/**
 * Streamt einen von DIESER Session erzeugten Text zeichenweise ins Frontend
 * und zeigt vorher das "Hermes denkt (Stream bereit)"-Badge. Wunsch Sebastian:
 * Hermes-Antworten live im Frontend, mit Denk-Status.
 */
async function streamHermesText(text, conversationId) {
    if (!text) return;
    hermesStreamBereit = true;
    aktualisiereStatusAnzeige();
    const contentDiv = addMessage('', 'assistant');
    const entry = state.messages[state.messages.length - 1];
    let antwort = '';
    try {
        const res = await fetch(`${API_BASE}/api/hermes/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                conversation_id: conversationId || 'conv_main',
                delay_ms: (typeof state.streamMs === 'number') ? state.streamMs : 120,
            }),
        });
        if (!res.ok || !res.body) throw new Error('Hermes-Stream nicht verfügbar');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let puffer = '';
        let _einzuBlenden = '';   // noch nicht angezeigte (gepufferte) deltas
        const _fps = typeof state.streamMs === 'number' && state.streamMs > 0 ? state.streamMs : 120;
        // Zwischenpuffer-Renderer: zeigt den gepufferten Text in LESBAREN
        // Bloecken (mehrere Zeichen je Frame) statt Zeichen-fuer-Zeichen -
        // 'von alt zu neu in menschlicher Geschwindigkeit' (Wunsch Sebastian).
        const _zeigeEingeblendet = () => {
            if (!_einzuBlenden) return;
            const block = _einzuBlenden.slice(0, 8); // lesbarer Block je Frame
            _einzuBlenden = _einzuBlenden.slice(8);
            antwort += block;
            contentDiv.textContent = antwort;
            if (isAtBottom()) scrollToBottom(true);
        };
        const _renderTimer = setInterval(() => { _zeigeEingeblendet(); }, Math.max(_fps, 40));
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            puffer += decoder.decode(value, { stream: true });
            let idx;
            while ((idx = puffer.indexOf('\n\n')) !== -1) {
                const block = puffer.slice(0, idx);
                puffer = puffer.slice(idx + 2);
                const zeile = block.split('\n').find(z => z.startsWith('data: '));
                if (!zeile) continue;
                let daten;
                try { daten = JSON.parse(zeile.slice(6)); } catch { continue; }
                if (daten.delta) {
                    _einzuBlenden += daten.delta;   // in den Puffer, nicht sofort anzeigen
                } else if (daten.done) {
                    break;
                }
            }
            if (puffer.includes('"done"')) break;
        }
        // Rest aus dem Puffer sofort (Stream-Ende) + Timer stoppen
        while (_einzuBlenden) _zeigeEingeblendet();
        clearInterval(_renderTimer);
        // finalisieren
        contentDiv.innerHTML = parseMarkdownPartial ? parseMarkdownPartial(antwort) : antwort;
        state.messages[state.messages.length - 1] = entry;
        if (isAtBottom()) scrollToBottom(true);
    } catch (err) {
        contentDiv.textContent = antwort || '⚠️ Hermes-Stream fehlgeschlagen: ' + (err && err.message);
    } finally {
        hermesStreamBereit = false;
        aktualisiereStatusAnzeige();
    }
}

/**
 * Pollt alle paar Sekunden GET /api/hermes/letzte (die neueste Nachricht
 * von DIESER Termux-Session). Ist eine NEUE id da, wird sie via
 * streamHermesText mit Denk-Badge im Frontend angezeigt. Wunsch Sebastian:
 * "server kann von dir pollen" - einfacher/robuster als Skript pro Antwort.
 */
let _letzteHermesId = sessionStorage.getItem('hermes_letzte_id') || null;
let _hermesPollAktiv = false;
async function pollHermesLetzte() {
    try {
        const res = await fetch(`${API_BASE}/api/hermes/letzte`);
        if (!res.ok) return;
        const d = await res.json();
        const id = d && d.id;
        const text = d && d.text;
        if (id && text && id !== _letzteHermesId) {
            _letzteHermesId = id;
            sessionStorage.setItem('hermes_letzte_id', id);
            const conv = (typeof state !== 'undefined' && state.conversationId) || 'conv_main';
            await streamHermesText(text, conv);
        }
    } catch (_) { /* Netzwerk/Poll-Fehler ignorieren */ }
}
function starteHermesPoll() {
    if (_hermesPollAktiv) return;
    _hermesPollAktiv = true;
    // Initial einmal pruefen, dann alle 4s.
    pollHermesLetzte();
    setInterval(pollHermesLetzte, 4000);
}

/** Zeigt die Nachrichten eines Gesprächs an. True, wenn es sie gab. */
// Rekonstruiert nach Reload eine persistierte, noch offene Quiz-Frage:
// rendert die Antwort-Auswahl (Personen + Neue Person + Keine Person) in die
// bereits angezeigte Blase (mit bild_pfad), damit man auch nach Neustart
// weiter antworten kann. Optionen frisch von /api/gesichter.
// Zeichnet den gelben bbox-Rahmen um die Person im Bild einer wiederhergestellten
// Quiz-Nachricht (nutzt die im ui-Block persistierte 'gesichter'-bbox). Findet
// das Bild im Container und legt den absolut positionierten Rahmen darueber.
function quizRahmenFuerBild(root, ui) {
    try {
        const img = root && root.querySelector('img');
        if (!img) return;
        const gs = (ui && ui.gesichter) || [];
        if (!gs.length) return;
        // gemeinsamer Helfer: positioniert gegen Naturgroesse, zeichnet gelben bbox
        markiereGesichtImBild(img, gs, 0);
    } catch (_) {}
}

async function wiederherstellenQuizAntworten(contentDiv, pfad, ui) {
    if (!contentDiv || !pfad) return;
    try {
        const res = await fetch(`${API_BASE}/api/gesichter`);
        const d = await res.json();
        const optionen = (d && d.personen || []).map(p => p.name).filter(Boolean);
        const uiV = (ui && ui.typ === 'quiz') ? ui : null;
        // Eine Auswahl, in Reihenfolge der Vermutung: die vermutete Person zuerst,
        // Rest danach. Keine doppelte Vermutungs-Box + volle Liste mehr (sonst
        // redurndant). Die vermutete Person wird als erster Button hervorgehoben.
        const vermutPerson = (uiV && uiV.vermutung && uiV.vermutung.person) || null;
        let optionenGeordnet = (d && d.personen || []).map(p => p.name).filter(Boolean);
        if (vermutPerson) {
            // vermutete Person nach vorn ziehen (falls im Katalog vorhanden)
            const index = optionenGeordnet.indexOf(vermutPerson);
            if (index > 0) {
                const [v] = optionenGeordnet.splice(index, 1);
                optionenGeordnet.unshift(v);
            }
        }
        const leiste = document.createElement('div');
        leiste.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:8px';
        // Erst NUR die Vermutung als Ja/Nein-Frage; die restliche Auswahl
        // erscheint erst nach "Nein" (Sebastian: vermutete zuerst, Rest versteckt).
        const auswahl = document.createElement('div');
        auswahl.style.cssText = 'display:none;flex-wrap:wrap;gap:6px;margin-top:6px';
        if (vermutPerson) {
            const box = document.createElement('div');
            box.style.cssText = 'padding:8px;border:1px solid #2e8b57;border-radius:9px;background:#12251a;flex-wrap:wrap;display:flex;gap:6px';
            const txt = document.createElement('div');
            txt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600';
            txt.textContent = `🔎 Ist das ${vermutPerson}?`;
            box.appendChild(txt);
            // Ja -> direkt vermuten; Nein -> Auswahl zeigen
            const ja = document.createElement('button');
            ja.textContent = '✅ Ja';
            ja.style.cssText = 'padding:6px 12px;border:1px solid #2e8b57;border-radius:8px;background:#2a5338;color:#9f9;cursor:pointer;font-size:0.82rem;font-weight:600';
            ja.onclick = () => quizBeantworten(pfad, vermutPerson, false, '');
            const nein = document.createElement('button');
            nein.textContent = '❌ Nein';
            nein.style.cssText = 'padding:6px 12px;border:1px solid #f88;border-radius:8px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.82rem;font-weight:600';
            nein.onclick = () => {
                box.style.display = 'none';
                auswahl.style.display = 'flex';
            };
            box.appendChild(ja);
            box.appendChild(nein);
            // "Keine Person drauf" auch direkt in der ersten Ja/Nein-Ansicht,
            // damit man ohne Umweg ueberspringen kann.
            const keinPers = document.createElement('button');
            keinPers.textContent = '🚫 Keine Person drauf';
            keinPers.style.cssText = 'padding:5px 10px;border:1px solid #888;border-radius:8px;background:#333;color:#ccc;cursor:pointer;font-size:0.8rem';
            keinPers.onclick = () => quizUeberspringen(pfad);
            box.appendChild(keinPers);
            leiste.appendChild(box);
        }
        // Die geordnete Auswahl (ohne die vermutete Person, die war ja die Frage) —
        // anfangs versteckt, erscheint erst nach "Nein".
        const frage = document.createElement('div');
        frage.textContent = 'Person wählen:';
        frage.style.cssText = 'font-size:0.82rem;color:#8f8;margin-bottom:4px';
        auswahl.appendChild(frage);
        (vermutPerson ? optionenGeordnet.filter(o => o !== vermutPerson) : optionenGeordnet).forEach(o => {
            const b = document.createElement('button');
            b.textContent = o;
            b.style.cssText = 'padding:6px 10px;border:1px solid #4a7;border-radius:8px;background:#1f3a2a;color:#8f8;cursor:pointer;font-size:0.82rem';
            b.onclick = () => quizBeantworten(pfad, o, false, '');
            auswahl.appendChild(b);
        });
        leiste.appendChild(auswahl);
        // "Andere Person" (fehlt in der Rekonstruktion des Screenshots) + eingebettetes Formular.
        const andere = document.createElement('button');
        andere.textContent = '➕ Andere Person';
        andere.style.cssText = 'padding:6px 10px;border:1px solid #f88;border-radius:8px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.82rem';
        const form = document.createElement('div');
        form.style.display = 'none';
        form.style.cssText = 'display:none;margin-top:6px;padding:6px;border:1px solid #f88;border-radius:6px;background:#1a0d0d';
        const inp = document.createElement('input');
        inp.placeholder = 'Name der Person auf diesem Bild';
        inp.style.cssText = 'width:100%;padding:5px;border:1px solid #f88;border-radius:6px;background:#1a0d0d;color:inherit;font-size:0.8rem';
        const speichern = document.createElement('button');
        speichern.textContent = '✅ Person speichern';
        speichern.style.cssText = 'padding:5px 9px;border:1px solid #f88;border-radius:6px;background:#2a1515;color:#f88;cursor:pointer;font-size:0.8rem;margin-top:5px;width:100%';
        speichern.onclick = () => {
            const n = (inp.value || '').trim();
            if (!n) { inp.style.borderColor = '#f55'; return; }
            quizBeantworten(pfad, n, true, '');
        };
        form.appendChild(inp);
        form.appendChild(speichern);
        andere.onclick = () => { form.style.display = form.style.display === 'none' ? 'block' : 'none'; };
        auswahl.appendChild(andere);
        auswahl.appendChild(form);
        const skip = document.createElement('button');
        skip.textContent = '🚫 Keine Person drauf';
        skip.style.cssText = 'padding:6px 10px;border:1px solid #888;border-radius:8px;background:#333;color:#ccc;cursor:pointer;font-size:0.82rem';
        skip.onclick = () => quizUeberspringen(pfad);
        auswahl.appendChild(skip);
        contentDiv.appendChild(leiste);
    } catch (_) { /* Rekonstruktion nicht moeglich: Text bleibt */ }
}

// Setzt die Optik/Zustand des CodeChat-Buttons je nach aktuellem Chat.
function setzeChatButtonStatus() {
    const btn = document.getElementById('codechat-btn');
    if (!btn) return;
    const imCode = (state.conversationId === 'conv_code');
    btn.setAttribute('aria-pressed', imCode ? 'true' : 'false');
    btn.title = imCode
        ? 'Im Programmier-/Hermes-Chat (conv_code) – klick: zum Haupt-Chat'
        : 'Im Haupt-Chat – klick: zum Programmier-/Hermes-Chat (</>) wechseln';
    btn.style.background = imCode ? '#1f3a2a' : '';
    btn.style.color = imCode ? '#8f8' : '';
    btn.style.borderColor = imCode ? '#4a7' : '';
    // Symbol je nach aktuellem Chat: Coding-Chat -> Sprechblase, Haupt-Chat -> </>
    const spr = document.getElementById('sym-sprech');
    const cod = document.getElementById('sym-code');
    if (spr) spr.style.display = imCode ? 'inline' : 'none';
    if (cod) cod.style.display = imCode ? 'none' : 'inline';
    // Hermes-/Loop-Button unten im Coding-Chat ausblenden (conv_code ist
    // ohnehin immer an Hermes; der Toggle wäre dort irreführend).
    const lb = document.getElementById('loop-btn');
    if (lb) lb.style.display = imCode ? 'none' : '';
    // Web- und Modell-Tools im Coding-Chat ausblenden: conv_code beantwortet
    // alles ueber die lokale Hermes-CLI (eigenes, festes LLM), Web-Suche und
    // Chat-Modellwahl sind dort wirkungslos/irrefuehrend.
    const wb = document.getElementById('web-btn');
    if (wb) wb.style.display = imCode ? 'none' : '';
    const mb = document.getElementById('model-btn');
    if (mb) mb.style.display = imCode ? 'none' : '';
}

// Wechselt zwischen Haupt-Chat (conv_main) und Coding-/Hermes-Chat (conv_code).
function chatWechseln(target) {
    const g = (target === 'conv_code') ? 'conv_code' : 'conv_main';
    state.conversationId = g;
    localStorage.setItem('conversation_id', g);
    setzeChatButtonStatus();
    zeigeGespraech(g);
}

// Laedt das Bild einer Nachricht erst, wenn sie (naeherungsweise) sichtbar
// ist - reduziert die Initiallast beim Chat-Wechsel (Ruckler, wenn alle Bilder
// auf einmal per fetch nachgeladen werden). Fallback: nach kurzem Verzug laden.
let _lazyBildObs = null;
function ladeBildLazy(contentDiv, pfad) {
    let geladen = false;
    const wirdSichtbar = () => {
        if (geladen) return;
        geladen = true;
        (async () => {
            try {
                const res = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(pfad)}`);
                const daten = await res.json();
                if (daten.data_url) {
                    zeigeBildVorschau(contentDiv, daten.data_url, pfad);
                } else {
                    const fehlt = document.createElement('div');
                    fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                    fehlt.textContent = '🖼 Bild nicht (mehr) vorhanden – gelöscht oder verschoben.';
                    contentDiv.appendChild(fehlt);
                }
            } catch (_) {
                const fehlt = document.createElement('div');
                fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                fehlt.textContent = '🖼 Bild nicht ladbar – gelöscht oder verschoben.';
                contentDiv.appendChild(fehlt);
            }
        })();
    };
    try {
        if (!_lazyBildObs) {
            if ('IntersectionObserver' in window) {
                _lazyBildObs = new IntersectionObserver((entries) => {
                    entries.forEach(e => { if (e.isIntersecting) wirdSichtbar(); });
                }, { root: dom.messages, rootMargin: '600px' });
            }
        }
        if (_lazyBildObs) {
            _lazyBildObs.observe(contentDiv);
            return;
        }
    } catch (_) {}
    setTimeout(wirdSichtbar, 300); // Fallback ohne Observer
}

async function zeigeGespraech(id) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}`);
        if (!res.ok) return false;
        const nachrichten = (await res.json()).messages || [];
        if (!nachrichten.length) {
            // Gültiger, (noch) leerer bekannter Chat (conv_main/conv_code): leeren
            // Kanal anzeigen statt auf false/alten Inhalt zurückzufallen.
            dom.messages.innerHTML = '';
            const willkommen2 = document.getElementById('welcome');
            if (willkommen2) dom.messages.appendChild(willkommen2);
            state.messages = [];
            state.conversationId = id;
            localStorage.setItem('conversation_id', id);
            setzeChatButtonStatus();
            return true;
        }

        const willkommen = document.getElementById('welcome');
        dom.messages.innerHTML = '';
        if (willkommen) dom.messages.appendChild(willkommen);
        state.messages = [];
        zuruecksetzenDatumBanner();

        // Indizes aller persistenten, noch offenen Quiz-Fragen: NUR die letzte
        // soll bedienbar sein; aeltere nur als Historie (Bild+Text).
        const offeneQuiz = [];
        for (let i = 0; i < nachrichten.length; i++) {
            if ((nachrichten[i].content || '').indexOf('[QUIZ-OFFEN]') !== -1) offeneQuiz.push(i);
        }
        const letzteOffene = offeneQuiz.length ? offeneQuiz[offeneQuiz.length - 1] : -1;

        // Nur die letzten MAX_VERLAUF Nachrichten sofort rendern -> der Wechsel
        // zum Coding-/Haupt-Chat wird flüssig (kein Synchron-Aufbau von
        // tausenden Blasen + kein Sprung durch Dauer-Scroll). Ältere werden
        // über einen Knopf chunkweise nachgeladen (prepend).
        const MAX_VERLAUF = 60;
        const anzahl = nachrichten.length;
        let _geladenBis = Math.max(0, anzahl - MAX_VERLAUF); // Index-Bereich davor bleibt ausstehend

        /** Baut EINE Nachrichtenblase für die Chronik; rendert sämtliche
         *  Nebeneffekte (Bild lazy, offene Quiz-Karte) wie zuvor. */
        function _baueChronikBlase(mi, m, istLetzteOffene) {
            const role = m.role === 'user' ? 'user' : 'assistant';
            // silent: während des Bündelns NICHT scrollen/pushen (s. addMessage)
            const contentDiv = addMessage(m.content || '', role, m.zeit || null, m.bild_pfad || undefined, { silent: true });
            const istOffeneQuizFrage = (m.content || '').indexOf('[QUIZ-OFFEN]') !== -1 && m.bild_pfad;

            // Die LETZTE offene Quiz-Frage wird NACH dem Aufbau mit der echten,
            // sauberen Quiz-Karte versehen (proportionales Bild + gelber Rahmen in
            // imgWrap). Das ist robuster als der ladeBildLazy-Wege, der das Bild
            // in einen flachen rahmen-Div ohne relative Position steckt und dort
            // den gelben bbox-Rahmen verrutschen liess / teils kein Bild zeigt.
            const alsOffeneQuizKarte = istOffeneQuizFrage && istLetzteOffene;

            if (m.bild_pfad && (role === 'assistant' || role === 'user') && !alsOffeneQuizKarte) {
                ladeBildLazy(contentDiv, m.bild_pfad);
            }

            // Ergebnis einer bereits abgeschlossenen Quiz-Runde: nicht nur den
            // nackten Text zeigen, sondern die SCHÖNE Bildunterschrift-Karte
            // (Bild + "… das ist Person") rekonstruieren (Wunsch Sebastian:
            // nach Reload den Quiz-Verlauf mit Bildern sehen).
            if (m.ui && m.ui.typ === 'quiz_ergebnis' && m.bild_pfad) {
                _baueQuizErgebnisKarte(contentDiv, m);
            }

            if (istOffeneQuizFrage) {
                if (alsOffeneQuizKarte) {
                    // Daten-URL holen und die interaktive Quiz-Karte (Bild + Rahmen
                    // + Antworten) noninteraktiv-nachladen. Async nachladen, damit
                    // der Chronik-Aufbau nicht blockiert.
                    _baueOffeneQuizKarte(contentDiv, m);
                }
            }
            return contentDiv;
        }

        // Laedt die offene Quiz-Karte (letzte offene Frage) mit dem sauberen
        // zeigeQuizKarte-Pfad. Wird NACH dem Blasen-Aufbau aufgerufen, damit das
        // Bild via data_url (proportional im imgWrap) + gelbem Rahmen erscheint.
        async function _baueOffeneQuizKarte(contentDiv, m) {
            try {
                const pfad = m.bild_pfad;
                if (!pfad) return;
                // bekannte Personen für die Antwort-Chips holen
                const gr = await fetch(`${API_BASE}/api/gesichter`);
                const gd = await gr.json();
                const optionen = (gd && gd.personen || []).map(p => p.name).filter(Boolean);
                const ui = m.ui || null;
                const vermutung = ui && ui.vermutung && ui.vermutung.person ? ui.vermutung : null;
                const gesichterUi = (ui && ui.gesichter) || [];
                // Daten-URL frisch laden (nicht persistiert, in-memory)
                const dr = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(pfad)}`);
                const dd = await dr.json();
                const dataUrl = (dd && dd.data_url) || '';
                if (!dataUrl) {
                    const fehlt = document.createElement('div');
                    fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                    fehlt.textContent = '🖼 Bild nicht (mehr) ladbar (gelöscht/verschoben).';
                    contentDiv.appendChild(fehlt);
                    return;
                }
                // In die BESTEHENDE Blase bauen (zielContainer), keine neue Karte.
                zeigeQuizKarte(pfad, ui && ui.name || '', dataUrl, optionen, vermutung, gesichterUi.length, [], gesichterUi, contentDiv);
            } catch (e) {
                // Fehlschlag sanft melden (Bild bleibt Textblase)
                const fehlt = document.createElement('div');
                fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                fehlt.textContent = '🖼 Quiz-Bild nicht ladbar (gelöscht/verschoben).';
                contentDiv.appendChild(fehlt);
            }
        }

        /** Rekonstruiert eine abgeschlossene Quiz-Runde als schöne Bildunterschrift-
         *  Karte: Bild + grüner Rahmen "… das ist Person" (statt nacktem Text).
         *  Ruft sich auf Basis des persistierten ui-Felds (typ:"quiz_ergebnis"). */
        async function _baueQuizErgebnisKarte(contentDiv, m) {
            try {
                const ui = m.ui || {};
                const person = ui.person || '';
                const pfad = m.bild_pfad;
                if (!pfad) return;
                const dr = await fetch(`${API_BASE}/api/dateien/daten?pfad=${encodeURIComponent(pfad)}`);
                const dd = await dr.json();
                const dataUrl = (dd && dd.data_url) || '';
                if (!dataUrl) {
                    const fehlt = document.createElement('div');
                    fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                    fehlt.textContent = '🖼 Bild nicht (mehr) ladbar (gelöscht/verschoben).';
                    contentDiv.appendChild(fehlt);
                    return;
                }
                // Text-Blase durch die Bildunterschrift-Karte ersetzen
                contentDiv.innerHTML = '';
                const zeile = document.createElement('div');
                zeile.style.cssText = 'padding:8px;border:1px solid #2e8b57;border-radius:10px;background:#0f1f14;font-weight:600;color:#8f8';
                zeile.textContent = `✅ **${person}** gelernt` + (ui.jahr ? ` · ${ui.jahr}` : '');
                contentDiv.appendChild(zeile);
                const cap = document.createElement('div');
                cap.style.cssText = 'margin-top:6px;padding:6px;border:1px solid #4a7;border-radius:8px;background:#0f1f14';
                const capImg = document.createElement('img');
                capImg.src = dataUrl;
                capImg.alt = 'Quiz-Bild';
                capImg.style.cssText = 'display:block;max-width:100%;max-height:200px;border-radius:8px;border:1px solid #4a7';
                cap.appendChild(capImg);
                const capTxt = document.createElement('div');
                capTxt.style.cssText = 'color:#8f8;font-size:0.85rem;font-weight:600;margin-top:4px';
                capTxt.textContent = '… das ist ' + (person || '?');
                cap.appendChild(capTxt);
                contentDiv.appendChild(cap);
                macheBildAntippbar(capImg, []);
            } catch (e) {
                const fehlt = document.createElement('div');
                fehlt.style.cssText = 'font-size:0.78rem;color:#999;font-style:italic;margin-top:4px';
                fehlt.textContent = '🖼 Quiz-Ergebnis-Bild nicht ladbar.';
                contentDiv.appendChild(fehlt);
            }
        }

        /** Hängt den „Ältere Nachrichten laden“-Knopf ganz oben ein (falls
         *  noch ältere ausstehen) und verbindet ihn mit dem aeltesten DOM-Knoten. */
        function _ergaenzeAeltereKnopf() {
            if (_geladenBis <= 0) return;
            const knopf = document.createElement('button');
            knopf.className = 'aeltere-laden';
            knopf.textContent = '↑ Ältere Nachrichten laden…';
            knopf.style.cssText =
                'display:block;width:100%;margin:6px auto;padding:8px;border:1px dashed #555;' +
                'border-radius:10px;background:transparent;color:#9aa;cursor:pointer;font-size:0.75rem';
            knopf.addEventListener('click', () => {
                knopf.disabled = true;
                knopf.textContent = '… lade ältere Nachrichten';
                const bis = _geladenBis;
                const von = Math.max(0, bis - MAX_VERLAUF);
                const frag = document.createDocumentFragment();
                for (let mi = von; mi < bis; mi++) {
                    _baueChronikBlase(mi, nachrichten[mi], mi === letzteOffene);
                }
                // vor den ältesten bereits gerenderten Knoten einschieben
                const erste = dom.messages.querySelector('.message');
                dom.messages.insertBefore(frag, erste);
                _geladenBis = von;
                knopf.remove();
                _ergaenzeAeltereKnopf.call(this); // neu einsetzen, falls weitere ausstehen
            });
            dom.messages.insertBefore(knopf, dom.messages.querySelector('.message'));
        }

        // Weg 1: leer -> Willkommen (schon oben erledigt).
        if (anzahl > 0) {
            _ergaenzeAeltereKnopf();          // Knopf nur bei > MAX_VERLAUF (geladenBis>0)
            const frag = document.createDocumentFragment();
            for (let mi = _geladenBis; mi < anzahl; mi++) {
                _baueChronikBlase(mi, nachrichten[mi], mi === letzteOffene);
            }
            dom.messages.appendChild(frag);
        }
        state.conversationId = id;
        setzeChatButtonStatus();
        localStorage.setItem('conversation_id', id);
        scrollToBottom(true);
        return true;
    } catch (err) {
        console.warn('Gespräch nicht abrufbar:', err);
        return false;
    }
}

/** Füllt das Blatt mit den gespeicherten Gesprächen, jüngstes zuerst. */
async function zeichneGespraeche() {
    dom.chatList.innerHTML = '';
    dom.chatHint.textContent = '';
    try {
        const res = await fetch(`${API_BASE}/api/conversations`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const liste = (await res.json()).conversations || [];
        const mitInhalt = liste.filter(c => c.message_count > 0).reverse();

        if (!mitInhalt.length) {
            dom.chatHint.textContent = 'Noch keine gespeicherten Gespräche.';
            return;
        }

        for (const c of mitInhalt) {
            const knopf = document.createElement('button');
            knopf.type = 'button';
            knopf.className = 'chat-row' + (c.id === state.conversationId ? ' aktiv' : '');
            knopf.innerHTML =
                `<strong>${escapeHtml(c.id)}</strong> · ${c.message_count} Nachrichten`
                + `<span class="chat-vorschau">${escapeHtml(c.last_message || '')}</span>`;
            knopf.addEventListener('click', async () => {
                if (await zeigeGespraech(c.id)) schliesseChatBlatt();
            });
            dom.chatList.appendChild(knopf);
        }
    } catch (err) {
        dom.chatHint.textContent = 'Gespräche nicht abrufbar – läuft der Server?';
        console.warn('Gesprächsliste:', err);
    }
}

function oeffneChatBlatt() {
    dom.chatSheet.hidden = false;
    zeichneGespraeche();
}

function schliesseChatBlatt() {
    dom.chatSheet.hidden = true;
}

async function stelleVerlaufWiederHer() {
    // Zuerst das gemerkte Gespräch. Klappt das nicht – unbekannte Kennung,
    // neues Gerät, geleerter Browserspeicher –, wird das jüngste geholt.
    //
    // WICHTIG (Fix 2026-08): Bei einem Fehlschlag (Netzwerk kurz weg, Server
    // noch am Starten) wird die gemerkte Kennung NICHT mehr gelöscht. Vorher
    // führte das dazu, dass nach einem Reload eine NEUE leere Conversation
    // entstand und der bisherige Verlauf (conv_8) aus der Anzeige verschwand,
    // obwohl er im Backend noch existierte.
    if (state.conversationId) {
        if (await zeigeGespraech(state.conversationId)) { setzeChatButtonStatus(); return; }
        // Laden fehlgeschlagen (404 ODER Netzwerk): Kennung BEHALTEN.
        // Der Rückfall unten lädt die jüngste; das localStorage bleibt intakt,
        // damit die nächste Nachricht weiter an die bekannte Conversation geht.
    }

    const juengste = await letzteGespraechsId();
    if (juengste) await zeigeGespraech(juengste);
}

document.addEventListener('DOMContentLoaded', () => {
    setWebSearch(state.webSearch);   // gespeicherten Wunsch wiederherstellen
    setModelLabel();                 // zeigt vorerst die gespeicherte Wahl
    setPrivacy(state.noRetention);   // Riegel-Zustand wiederherstellen
    startHealthChecks();
    stelleVerlaufWiederHer();
    if (typeof starteHermesPoll === 'function') starteHermesPoll();
    aktualisiereStatusAnzeige();
    // Status-Badge beim Start zuruecksetzen: das hartkodierte „🟢 Agent“ im
    // HTML (falls ueberhaupt geladen) wird durch den echten Zustand ersetzt
    // bzw. im Ruhezustand ausgeblendet. (Fix: vorher blieb ein gruener
    // „Agent“ stehen, obwohl Hermes arbeitete.)
    dom.input.focus();
    updateSendButton();
    // Katalog im Hintergrund holen: Danach steht der richtige Anzeigename am
    // Knopf, und das Blatt geht beim ersten Antippen ohne Wartezeit auf.
    ladeKatalog();
});
// ── Hermes Live-Status (unabhängiger Poller, zeigt Hermes-Gedanken live) ──
(function() {
    const container = document.getElementById('hermes-live-status');
    const msgDiv = document.getElementById('hermes-live-msg');
    const meldungenDiv = document.getElementById('hermes-live-meldungen');
    const indicator = document.getElementById('hermes-live-indicator');
    if (!container) return;

    let letzteId = '';
    let letzteAnzahl = 0;

    async function pollHermes() {
        try {
            const res = await fetch('/api/auftraege');
            if (!res.ok) { container.style.display = 'none'; _setzeHermesAussen(false); return; }
            const data = await res.json();
            const jobs = data.auftraege || [];
            // Neuesten offenen/laufenden Job finden
            const relevant = jobs.filter(j => j.status === 'offen' || j.status === 'laeuft');
            if (relevant.length === 0) {
                container.style.display = 'none';
                _setzeHermesAussen(false);
                return;
            }
            _setzeHermesAussen(true);
            const job = relevant[relevant.length - 1]; // neuester
            const id = job.id.substring(0, 8);
            const meldungen = job.status_meldungen || [];
            const status = job.status;

            container.style.display = 'block';
            indicator.textContent = status === 'laeuft' ? '⚡ arbeitet' : '⏳ wartet';

            if (id !== letzteId || meldungen.length > letzteAnzahl) {
                if (id !== letzteId) {
                    letzteAnzahl = 0;
                    meldungenDiv.innerHTML = '';
                }
                // Neue Meldungen seit letztem Check
                for (let i = letzteAnzahl; i < meldungen.length; i++) {
                    const div = document.createElement('div');
                    div.style.cssText = 'padding:4px 6px;margin:2px 0;background:#222;border-radius:4px;font-size:12px;white-space:pre-wrap;border-left:2px solid #0f0';
                    const { text: htext, zeitIso } = zerlegeHermesMeldung(meldungen[i]);
                    div.textContent = htext;
                    if (zeitIso) {
                        const z = document.createElement('span');
                        z.style.cssText = 'display:block;font-size:0.65rem;color:#9a9a9a;margin-top:2px';
                        z.textContent = formatZeit(zeitIso);
                        div.appendChild(z);
                    }
                    meldungenDiv.appendChild(div);
                }
                letzteAnzahl = meldungen.length;
                letzteId = id;

                // Scroll to bottom
                if (typeof scrollToBottom === 'function') scrollToBottom(true);
            }

            if (status === 'fertig' || status === 'fehler') {
                indicator.textContent = status === 'fertig' ? '✅ fertig' : '❌ fehler';
                setTimeout(() => { container.style.display = 'none'; }, 30000);
            }
        } catch(_) { /* Server kurz weg */ _setzeHermesAussen(false); }
    }

    // Alle 3s polln
    pollHermes();
    setInterval(pollHermes, 3000);
})();

// =========================================
// (Kanban-Board/Auftragsbuch-Anzeige entfernt – Sebastian nutzt den
//  Assistenten direkt über Hermes, kein sichtbares Auftragskonzept mehr.)
