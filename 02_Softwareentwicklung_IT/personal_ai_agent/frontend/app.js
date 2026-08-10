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
// State
// =========================================
const state = {
    conversationId: null,
    isProcessing: false,
    isOnline: false,
    messages: [],
    isRecording: false,
    isTranscribing: false,
    // Websuche kostet je Anfrage extra – Wunsch bleibt zwischen Sitzungen erhalten.
    webSearch: localStorage.getItem('web_search') === '1',
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
    webBtn: document.getElementById('web-btn'),
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.querySelector('.status-text'),
};

// =========================================
// Utility: Simple Markdown Parser
// =========================================
function parseMarkdown(text) {
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
    });
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    text = text.replace(/\n\n/g, '</p><p>');
    text = text.replace(/\n/g, '<br>');
    return `<p>${text}</p>`;
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

/** Legt eine Nachrichtenblase an und gibt ihren Inhaltsbereich zurück,
 *  damit der Streaming-Weg sie nachträglich befüllen kann. */
function addMessage(content, role) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (role === 'assistant') {
        contentDiv.innerHTML = parseMarkdown(content);
    } else {
        contentDiv.innerHTML = `<p>${escapeHtml(content)}</p>`;
    }
    div.appendChild(contentDiv);
    dom.messages.appendChild(div);
    scrollToBottom(true);   // eigene Aktion – hier wird immer nachgezogen
    state.messages.push({ role, content });
    return contentDiv;
}

function setLoading(loading) {
    state.isProcessing = loading;
    dom.loading.classList.toggle('hidden', !loading);
    dom.input.disabled = loading;
    updateSendButton();
}

function setOnline(online) {
    state.isOnline = online;
    dom.statusIndicator.className = `status ${online ? 'online' : 'offline'}`;
    dom.statusText.textContent = online ? 'Online' : 'Offline';
}

function updateSendButton() {
    // Während der Aufnahme bleibt der Knopf bedienbar: Ein Druck darauf
    // beendet die Aufnahme und schickt das Diktat gleich ab.
    if (state.isRecording) {
        dom.sendBtn.disabled = false;
        return;
    }
    dom.sendBtn.disabled = !dom.input.value.trim() || state.isProcessing;
}

function setWebSearch(an) {
    state.webSearch = an;
    localStorage.setItem('web_search', an ? '1' : '0');
    dom.webBtn.classList.toggle('active', an);
    dom.webBtn.setAttribute('aria-pressed', an ? 'true' : 'false');
    dom.webBtn.title = an
        ? 'Websuche an – jede Suche kostet rund 0,7 Cent'
        : 'Websuche aus – jede Suche kostet rund 0,7 Cent';
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
// API Calls
// =========================================
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
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
    setOnline(false);
    return null;
}

function updateFooterNote(memoryCount) {
    const note = document.querySelector('.footer-note');
    if (note) {
        note.textContent = `DeepSeek V4 Flash · ${memoryCount} Erinnerungen`;
    }
}

const SYMBOL_LAUTSPRECHER = '<svg viewBox="0 0 24 24" width="16" height="16">'
    + '<path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05'
    + 'c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06'
    + 'c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>';

const SYMBOL_PAUSE = '<svg viewBox="0 0 24 24" width="16" height="16">'
    + '<path fill="currentColor" d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

const SYMBOL_STOPP = '<svg viewBox="0 0 24 24" width="16" height="16">'
    + '<path fill="currentColor" d="M6 6h12v12H6z"/></svg>';

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

    const abspielBtn = document.createElement('button');
    abspielBtn.className = 'speak-btn';
    abspielBtn.title = 'Vorlesen';
    abspielBtn.innerHTML = SYMBOL_LAUTSPRECHER;

    const stoppBtn = document.createElement('button');
    stoppBtn.className = 'speak-btn stop';
    stoppBtn.title = 'Stopp';
    stoppBtn.innerHTML = SYMBOL_STOPP;
    stoppBtn.hidden = true;   // erst sichtbar, wenn etwas läuft

    leiste.appendChild(abspielBtn);
    leiste.appendChild(stoppBtn);
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
        stoppBtn.hidden = !aktiv;
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

    stoppBtn.addEventListener('click', () => halte(true));

    const steuerung = {
        /** Wird gerufen, wenn neuer Text eingetroffen ist. */
        neuerText: () => { if (aktiv && !pausiert) nachfuellen(); },
        stopp: () => halte(true),
    };
    return steuerung;
}

/** Beendet eine Antwortblase: Markdown rendern, Verlauf und Fußzeile setzen. */
function finishReply(contentDiv, entry, antwort, abschluss, vorleser) {
    const untenGewesen = isAtBottom();
    contentDiv.innerHTML = parseMarkdown(antwort);
    entry.content = antwort;
    // Muss nach dem Setzen von innerHTML kommen, sonst wird es überschrieben.
    if (abschluss) addSources(contentDiv, abschluss.sources);
    if (abschluss) {
        if (abschluss.conversation_id) state.conversationId = abschluss.conversation_id;
        if (abschluss.memory_count !== undefined) updateFooterNote(abschluss.memory_count);
    }
    // Der Vorleser darf jetzt auch den letzten Rest ohne Satzzeichen holen.
    if (vorleser) vorleser.neuerText();
    if (untenGewesen) scrollToBottom(true);
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
        }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    zustand.text = data.reply;
    zustand.fertig = true;
    finishReply(contentDiv, entry, data.reply, data, vorleser);
    return data;
}

async function sendMessage(text) {
    if (state.isProcessing || !text.trim()) return;
    setLoading(true);
    addMessage(text, 'user');

    // Leere Blase anlegen, die sich während des Streams füllt.
    const contentDiv = addMessage('', 'assistant');
    const entry = state.messages[state.messages.length - 1];

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
        contentDiv.parentElement,
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
        }),
        });
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
                } else if (daten.sources) {
                    // Können an jedem Häppchen hängen, deshalb laufend sammeln.
                    quellen = mergeQuellen(quellen, daten.sources);
                } else if (daten.error) {
                    throw new Error(daten.error);
                } else if (daten.done) {
                    abschluss = daten;
                }
            }
        }

        if (!antwort) throw new Error('Leere Antwort vom Server');
        zustand.fertig = true;
        // Zwischendurch eingetroffene Quellen mit denen aus dem Abschluss
        // zusammenführen – doppelte Adressen fallen dabei weg.
        abschluss = Object.assign({}, abschluss, {
            sources: mergeQuellen(quellen, abschluss && abschluss.sources),
        });
        finishReply(contentDiv, entry, antwort, abschluss, vorleser);
        return abschluss;

    } catch (err) {
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
        contentDiv.innerHTML = parseMarkdown(
            (antwort ? antwort + '\n\n' : '')
            + `⚠️ **Verbindungsfehler**\n\nKonnte den Agenten nicht erreichen.\n`
            + `- URL: ${API_BASE}\n`
            + `- Fehler: ${err.message}`
        );
        entry.content = antwort;
    } finally {
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
            dom.input.value = data.text;
            dom.input.style.height = 'auto';
            dom.input.style.height = Math.min(dom.input.scrollHeight, 120) + 'px';
            await handleSubmit();
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

dom.webBtn.addEventListener('click', () => setWebSearch(!state.webSearch));

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
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
    }
});

dom.sendBtn.addEventListener('click', handleSubmit);

async function handleSubmit() {
    // Läuft gerade eine Aufnahme, bedeutet Senden bzw. Enter: Aufnahme
    // beenden. Transkription und Absenden laufen danach von selbst weiter.
    if (state.isRecording) {
        stopRecording();
        return;
    }
    const text = dom.input.value.trim();
    if (!text || state.isProcessing) return;
    dom.input.value = '';
    dom.input.style.height = 'auto';
    updateSendButton();
    await sendMessage(text);
}

// =========================================
// Periodic Health Check
// =========================================
let healthCheckInterval = null;

function startHealthChecks() {
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
document.addEventListener('DOMContentLoaded', () => {
    setWebSearch(state.webSearch);   // gespeicherten Wunsch wiederherstellen
    startHealthChecks();
    dom.input.focus();
    updateSendButton();
});