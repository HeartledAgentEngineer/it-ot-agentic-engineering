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
function scrollToBottom() {
    dom.messages.parentElement.scrollTop = dom.messages.parentElement.scrollHeight;
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
    scrollToBottom();
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

/** Hängt einen Vorlese-Knopf an eine fertige Antwort. */
function addSpeakButton(contentDiv, text) {
    const btn = document.createElement('button');
    btn.className = 'speak-btn';
    btn.title = 'Vorlesen';
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16">'
        + '<path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05'
        + 'c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06'
        + 'c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>';

    // Einmal geholtes Audio wird behalten – ein zweiter Klick kostet nichts.
    let audioUrl = null;

    btn.addEventListener('click', async () => {
        if (audioUrl) {
            new Audio(audioUrl).play();
            return;
        }
        btn.disabled = true;
        btn.classList.add('busy');
        try {
            const res = await fetch(`${API_BASE}/api/speak`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text.slice(0, 2000) }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            audioUrl = URL.createObjectURL(await res.blob());
            new Audio(audioUrl).play();
        } catch (err) {
            // Lieber Roboterstimme als gar nichts – und wenn auch die nicht
            // will, muss man das sehen. Vorher scheiterten beide stumm.
            console.warn('Sprachausgabe nicht verfügbar, nutze Browser-Stimme:', err);
            if (!speakResponse(text)) {
                btn.classList.add('failed');
                btn.title = 'Vorlesen fehlgeschlagen – Grund steht im Server-Log';
            }
        } finally {
            btn.disabled = false;
            btn.classList.remove('busy');
        }
    });

    contentDiv.parentElement.appendChild(btn);
}

/** Beendet eine Antwortblase: Markdown rendern, Verlauf und Fußzeile setzen. */
function finishReply(contentDiv, entry, antwort, abschluss) {
    contentDiv.innerHTML = parseMarkdown(antwort);
    entry.content = antwort;
    addSpeakButton(contentDiv, antwort);
    if (abschluss) {
        if (abschluss.conversation_id) state.conversationId = abschluss.conversation_id;
        if (abschluss.memory_count !== undefined) updateFooterNote(abschluss.memory_count);
    }
    scrollToBottom();
}

/** Rückfallweg auf den nicht-streamenden Endpunkt. */
async function sendMessageFallback(text, contentDiv, entry) {
    const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    finishReply(contentDiv, entry, data.reply, data);
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

    try {
        const res = await fetch(`${API_BASE}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, conversation_id: state.conversationId }),
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
                    // Nicht bei jedem Häppchen neu zeichnen – das Neuaufbauen
                    // der Blase würde auf dem Handy ruckeln. Der endgültige
                    // Aufbau passiert ohnehin in finishReply().
                    const jetzt = performance.now();
                    if (jetzt - letztesRendern > 80) {
                        letztesRendern = jetzt;
                        contentDiv.innerHTML = parseMarkdownPartial(antwort);
                        scrollToBottom();
                    }
                } else if (daten.error) {
                    throw new Error(daten.error);
                } else if (daten.done) {
                    abschluss = daten;
                }
            }
        }

        if (!antwort) throw new Error('Leere Antwort vom Server');
        finishReply(contentDiv, entry, antwort, abschluss);
        return abschluss;

    } catch (err) {
        // Kam schon Text an, ist der Stream mittendrin gerissen – dann steht
        // das Bruchstück da und ein zweiter Anlauf würde doppelt abrechnen.
        if (!antwort) {
            console.warn('Streaming fehlgeschlagen, versuche Normalweg:', err);
            try {
                return await sendMessageFallback(text, contentDiv, entry);
            } catch (err2) {
                err = err2;
            }
        }
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
    startHealthChecks();
    dom.input.focus();
    updateSendButton();
});