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
    // Datei-Upload
    uploadBtn: document.getElementById('upload-btn'),
    fileInput: document.getElementById('file-input'),
    filePreview: document.getElementById('file-preview'),
    filePreviewList: document.getElementById('file-preview-list'),
};

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
        btn.textContent = '… Hermes wird beendet, Agent antwortet';
        // 1) Laufenden Hermes-Auftrag abbrechen (tmux-Session + Buch-Status),
        //    damit nicht im Hintergrund weitergearbeitet wird.
        if (_laufenderAuftragKurz) {
            try {
                await fetch(`${API_BASE}/api/auftraege/${_laufenderAuftragKurz}/abbrechen`, { method: 'POST' });
            } catch (_) { /* Abbruch-Fehlschlag ist nicht kritisch */ }
            _laufenderAuftragKurz = null;
            aktualisiereStatusAnzeige();
        }
        // 2) Aufgabe an den normalen LLM weiterleiten.
        sendMessage(frag);
        btn.textContent = '… wird vom Agenten beantwortet';
    });
    // Controller: Zusätzlicher Umlenk-Button zu Hermes-Lokal (Handy), wenn
    // ein Auftrag läuft — der PC-Hermes liefert die Antwort evtl. nicht
    // zurück, dann wechselt man auf den Handy-Hermes.
    if (_laufenderAuftragKurz) {
        const btnHandy = document.createElement('button');
        btnHandy.className = 'korrektur-button';
        btnHandy.textContent = '↪️ Zu Hermes-Lokal (Handy) wechseln';
        btnHandy.style.cssText =
            'margin-top:6px;margin-left:6px;padding:8px 10px;border:1px solid #4a7;' +
            'border-radius:8px;background:#1f3a2a;color:#8f8;cursor:pointer;font-size:0.8rem';
        btnHandy.addEventListener('click', async () => {
            const id = _laufenderAuftragKurz;
            if (!id) return;
            btnHandy.disabled = true;
            btnHandy.textContent = '… wechselt auf Handy-Hermes';
            try {
                await fetch(`${API_BASE}/api/auftraege/${id}/wechseln-handy`, { method: 'POST' });
                addMessage('↪️ **Auf den Handy-Hermes gewechselt** – die Aufgabe läuft jetzt lokal auf deinem Smartphone.', 'assistant');
            } catch (_) {
                btnHandy.textContent = '⚠️ Wechsel fehlgeschlagen';
            }
        });
        // Umlenk-Buttons nebeneinander (Flex-Container).
        const zeile = document.createElement('div');
        zeile.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-top:6px';
        // Bestehenden btn in die Zeile verschieben + Handy-Button dazu.
        btn.parentNode && btn.parentNode.removeChild(btn);
        zeile.appendChild(btn);
        zeile.appendChild(btnHandy);
        return zeile;
    }
    return btn;
}

/** Ziel-Etiketten für die „Wohin wurde delegiert?"-Pille (Passend zu den
 *  ziel-Werten des Backends: pc / handy / buch). */
const ZIEL_LABELS = {
    pc: '→ Hermes (PC)',
    handy: '→ Hermes (Handy)',
    buch: '→ Auftragsbuch',
};

/** Kleine Ziel-Pille unter einer Delegations-Antwort: zeigt auf einen Blick,
 *  wohin die Hermes-Aufgabe weitergeleitet wurde. `ziel` kommt aus dem
 *  SSE-done-Event bzw. aus der ChatResponse (Fallback-Weg). */
function addZielChip(contentDiv, ziel) {
    if (!ziel || !ZIEL_LABELS[ziel]) return;
    // Ziel merken (pc/handy/buch) → Status-Badge zeigt "Hermes (PC/Handy)".
    _zielAktuell = ziel;
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
function addMessage(content, role, zeit) {
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
        if (zeit === undefined
            && (/Hermes-Aufgabe erkannt|Coding-Auftrag erkannt/.test(content)
                || /Fehler im lokalen Hermes-Job|Abbruch-Fehlschlag|⚠️ Fehler/.test(content)
                || /wurde an den PC-Hermes übergeben/.test(content)
                || /arbeitet länger als das Timeout/.test(content)
                || /arbeitet gerade an der Aufgabe/.test(content))) {
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
    div.appendChild(inner);
    dom.messages.appendChild(div);
    scrollToBottom(true);   // eigene Aktion – hier wird immer nachgezogen
    state.messages.push({ role, content });
    return contentDiv;
}

/** Wem schreibt der Nutzer gerade? — sichtbares Badge im Header.
 *  - Hermes läuft (_laufenderAuftragKurz) → 🔴 Hermes (direkt)
 *  - normale Antwort/Stream läuft → 🟡 Agent (antwortet)
 *  - sonst → 🟢 Agent (LLM + Gedächtnis)
 *  Wird bei jedem relevanten Zustandswechsel aufgerufen. */
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
    } else if (state.abbruch) {
        badge.textContent = '🟡 Agent antwortet';
        badge.style.color = '#fc6';
        badge.style.borderColor = '#c90';
        badge.style.background = '#2a2215';
    } else {
        badge.textContent = '🟢 Agent';
        badge.style.color = '#9f9';
        badge.style.borderColor = '#3a3a3a';
        badge.style.background = '#152a15';
    }
}

/** Schaltet nur die "Denke nach..."-Anzeige. Ob wirklich etwas laeuft,
 *  steht in state.abbruch – die Anzeige verschwindet schon beim ersten
 *  Textstueck, die Antwort laeuft danach aber weiter.
 *  Seit v20260817 sitzen die drei animierten Punkte DIREKT in der
 *  Assistant-Blase (siehe sendMessage) – nicht mehr in einem separaten
 *  #loading-Bereich unterhalb. Hier bleibt nur noch die Button-Logik. */
function setLoading(loading) {
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
        abspielBtn.classList.toggle('playing', spielt);
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
    };
    return steuerung;
}

/** Zeigt eine Hermes-Zwischenmeldung (gedanke) mit optionalem Abbruch-Button.
 *  Läuft gerade ein Hermes-Auftrag (_laufenderAuftragKurz), bekommt JEDE
 *  Zwischenmeldung einen kleinen "⏹ Abbrechen"-Knopf — so ist der Hermes-
 *  Flow an jeder sichtbaren Stelle stopperbar, nicht nur über den globalen
 *  Stop im Eingabefeld. */
function fuegeGedankeMitAbbruchHinzu(text, zeitIso) {
    const div = document.createElement('div');
    div.className = 'message agent-zwischenmeldung';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = parseMarkdown(text || '');
    div.appendChild(contentDiv);

    // Abbruch-Button, wenn ein Hermes-Auftrag läuft.
    if (_laufenderAuftragKurz) {
        const btn = document.createElement('button');
        btn.className = 'gedanke-abbrechen';
        btn.textContent = '⏹ Hermes abbrechen';
        btn.style.cssText =
            'margin-top:6px;padding:4px 10px;border:1px solid #b44;border-radius:8px;' +
            'background:#3a1f1f;color:#f99;cursor:pointer;font-size:0.75rem';
        btn.addEventListener('click', () => brichAb());
        contentDiv.appendChild(btn);
    }

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

function zeigeBildVorschau(container, dataUrl, pfad) {
    if (!container) return;
    const rahmen = document.createElement('div');
    rahmen.className = 'bild-vorschau';
    rahmen.style.cssText =
        'margin-top:8px;max-width:100%;display:flex;flex-direction:column;gap:6px';

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

    // Nach BILD_ANZEIGE_MS: Bild weg, Platzhalter zum Nachladen da.
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
                    zeigeBildVorschau(container, daten.data_url, pfad); // erneut (loop)
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
let _auftragTimer = null;
// Kurz-ID des aktuell laufenden Hermes-Auftrags (für den Kommunikationskanal:
// solange gesetzt, wird eine neue Chat-Nachricht als Kommentar an die Session
// geschickt statt einen neuen Auftrag zu starten).
let _laufenderAuftragKurz = null;
// Ziel des laufenden Hermes-Auftrags (pc/handy/buch) — fürs Status-Badge.
let _zielAktuell = '';
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
            // Auch im Fallback müssen Dateien mit – sonst fehlt das Bild
            // beim zweiten Versuch, wenn der Streaming-Weg scheiterte.
            files: state.pendingFiles.length > 0
                ? state.pendingFiles.map(f => ({
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

async function sendMessage(text, ausWarteschlange = false, blaseSchonGezeigt = false) {
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
    if (_laufenderAuftragKurz) {
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
        return;
    }

    // Leere Blase anlegen, die sich während des Streams füllt.
    // Seit v20260817: Typing-Indicator (drei Punkte) direkt in der Blase,
    // nicht mehr im separaten #loading-Bereich.
    const contentDiv = addMessage('', 'assistant');
    contentDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div><span class="loading-text">Denke nach...</span>';
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
        const res = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                conversation_id: state.conversationId,
                web_search: state.webSearch,
                model: state.model,
                files: state.pendingFiles.length > 0
                    ? state.pendingFiles.map(f => ({
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

                if (daten.delta) {
                    if (!antwort) setLoading(false);   // Tipp-Anzeige ausblenden
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
                    if (jetzt - letztesRendern > 80) {
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
        // Nur zuruecksetzen, wenn niemand zwischenzeitlich einen neuen Lauf
        // gestartet hat – sonst wuerde dessen Stopp-Knopf ins Leere greifen.
        if (state.abbruch === controller) state.abbruch = null;
        setLoading(false);
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

dom.webBtn.addEventListener('click', () => setWebSearch(naechsterWebModus()));

dom.modelBtn.addEventListener('click', oeffneBlatt);
dom.modelClose.addEventListener('click', schliesseBlatt);
dom.modelSearch.addEventListener('input', zeichneListe);
dom.privacyBtn.addEventListener('click', () => setPrivacy(!state.noRetention));

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
    + `<button type="button" data-aktion="bearbeiten" style="display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;background:none;border:none;border-radius:7px;color:#ddd;font:inherit;text-align:left;cursor:pointer">`
        + `✏️ Nachricht bearbeiten</button>`;
document.body.appendChild(kontextMenue);

let kontextZielText = '';
let kontextKopierTimer = null;

/** Liefert den kopierbaren Text einer Blase: User exakt wie getippt,
 *  Assistant roh (Markdown) bzw. sichtbarer Text bei gestreamten Blasen. */
function kontextTextAusBlase(blase) {
    const roh = blase.dataset.klarText || '';
    if (roh) return roh;
    const inhalt = blase.querySelector('.message-content');
    return inhalt && inhalt.innerText ? inhalt.innerText.trim() : '';
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
    } else if (btn.dataset.aktion === 'bearbeiten') {
        // User-Nachricht zurück in die Eingabe legen (Cursor ans Ende).
        dom.input.value = kontextZielText;
        dom.input.style.height = 'auto';
        dom.input.style.height = Math.min(dom.input.scrollHeight, 120) + 'px';
        const ende = dom.input.value.length;
        dom.input.setSelectionRange(ende, ende);
        dom.input.focus();
        updateSendButton();
        kontextMenueSchliessen();
    }
});

// Rechtsklick (langes Drücken) auf eine Blase öffnet das Menü.
dom.messages.addEventListener('contextmenu', (e) => {
    const blase = e.target.closest('.message');
    if (!blase || !dom.messages.contains(blase)) return;
    const text = kontextTextAusBlase(blase);
    if (!text) return;   // z. B. noch leere Streaming-Blase
    e.preventDefault();
    kontextZielText = text;
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

/** Zeigt die Nachrichten eines Gesprächs an. True, wenn es sie gab. */
async function zeigeGespraech(id) {
    try {
        const res = await fetch(`${API_BASE}/api/conversations/${id}`);
        if (!res.ok) return false;
        const nachrichten = (await res.json()).messages || [];
        if (!nachrichten.length) return false;

        const willkommen = document.getElementById('welcome');
        dom.messages.innerHTML = '';
        if (willkommen) dom.messages.appendChild(willkommen);
        state.messages = [];
        zuruecksetzenDatumBanner();

        for (const m of nachrichten) {
            addMessage(m.content, m.role === 'user' ? 'user' : 'assistant', m.zeit || null);
        }
        state.conversationId = id;
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
        if (await zeigeGespraech(state.conversationId)) return;
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
            if (!res.ok) { container.style.display = 'none'; return; }
            const data = await res.json();
            const jobs = data.auftraege || [];
            // Neuesten offenen/laufenden Job finden
            const relevant = jobs.filter(j => j.status === 'offen' || j.status === 'laeuft');
            if (relevant.length === 0) { container.style.display = 'none'; return; }
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
        } catch(_) { /* Server kurz weg */ }
    }

    // Alle 3s polln
    pollHermes();
    setInterval(pollHermes, 3000);
})();

// =========================================
// Kanban-Board — Aufgaben (Auftragsbuch) als Spalten
// =========================================
(function () {
    const sheet = document.getElementById('kanban-sheet');
    const btn = document.getElementById('kanban-btn');
    const close = document.getElementById('kanban-close');
    const hint = document.getElementById('kanban-hint');
    if (!sheet || !btn || !close) return;

    const spalten = {
        offen: document.getElementById('kanban-offen'),
        laeuft: document.getElementById('kanban-laeuft'),
        fertig: document.getElementById('kanban-fertig'),
        fehler: document.getElementById('kanban-fehler'),
    };

    function zeichne(auftraege) {
        // Spalten leeren
        Object.values(spalten).forEach(el => { if (el) el.innerHTML = ''; });
        let zaehler = 0;
        (auftraege || []).forEach(a => {
            // Status normalisieren: BACKEND liefert OFFEN/LAEUFT/FERTIG/FEHLER
            const roh = (a.status || 'offen').toLowerCase();
            const status = ({ fertig: 'fertig', fehler: 'fehler', laeuft: 'laeuft' }[roh]) || 'offen';
            const ziel = spalten[status] || spalten.offen;
            if (!ziel) return;
            zaehler++;
            const karte = document.createElement('div');
            karte.style.cssText =
                'padding:8px;margin-bottom:6px;background:#1e1e1e;border:1px solid #3a3a3a;' +
                'border-radius:8px;font-size:12px;white-space:pre-wrap';
            const aufgabe = (a.auftrag || '').slice(0, 140);
            karte.textContent = aufgabe || '(ohne Text)';
            karte.title = a.auftrag || '';
            ziel.appendChild(karte);
        });
        if (hint) hint.textContent = zaehler === 0
            ? 'Keine Aufgaben – alles erledigt.'
            : `${zaehler} Aufgabe(n) im Buch.`;
    }

    async function lade() {
        try {
            const res = await fetch(`${API_BASE}/api/auftraege`);
            if (!res.ok) return;
            const daten = await res.json();
            zeichne(daten.auftraege || []);
        } catch (_) { /* Server kurz weg */ }
    }

    function oeffne() {
        sheet.hidden = false;
        lade();
    }
    function schliesse() {
        sheet.hidden = true;
    }

    btn.addEventListener('click', oeffne);
    close.addEventListener('click', schliesse);
    // Tippen auf Hintergrund schließt
    sheet.addEventListener('click', (e) => { if (e.target === sheet) schliesse(); });
    // Live-Aktualisierung alle 3s, solange offen
    setInterval(() => { if (!sheet.hidden) lade(); }, 3000);
})();
