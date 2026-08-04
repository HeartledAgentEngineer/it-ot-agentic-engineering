/**
 * Personal AI Agent – Frontend Application
 * 
 * Features:
 * - Chat-UI mit Nachrichtenverlauf
 * - Verbindung zum FastAPI-Backend
 * - TTS (Text-to-Speech) via SpeechSynthesis API
 * - Auto-Resize der Texteingabe
 * - Markdown-Unterstützung für Antworten
 * - Spracheingabe via MediaRecorder + OpenRouter Whisper (wie TypeFREE)
 */

/**
 * BACKEND-ADRESSE
 * ----------------
 * Lokaler PC-Test:     'http://localhost:8080'
 * Handy (Heimnetz):    'http://192.168.178.XX:8080'  (IP deines Handys)
 * 
 * Sicherheit: Der API-Key liegt NUR auf dem Handy in .env,
 *             nie im Frontend-Code.
 */
const API_BASE = localStorage.getItem('api_base') || 'http://localhost:8080';

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

// =========================================
// UI Functions
// =========================================
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
    dom.messages.parentElement.scrollTop = dom.messages.parentElement.scrollHeight;
    state.messages.push({ role, content });
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
    dom.sendBtn.disabled = !dom.input.value.trim() || state.isProcessing || state.isRecording;
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

async function sendMessage(text) {
    if (state.isProcessing || !text.trim()) return;
    setLoading(true);
    addMessage(text, 'user');
    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                conversation_id: state.conversationId,
            }),
        });
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const data = await res.json();
        state.conversationId = data.conversation_id;
        addMessage(data.reply, 'assistant');
        if (data.memory_count !== undefined) {
            updateFooterNote(data.memory_count);
        }
        speakResponse(data.reply);
        return data;
    } catch (err) {
        console.error('Chat error:', err);
        addMessage(
            `⚠️ **Verbindungsfehler**\n\nKonnte den Agenten nicht erreichen.\n`
            + `Stelle sicher, dass der Server läuft:\n`
            + `- URL: ${API_BASE}\n`
            + `- Fehler: ${err.message}`,
            'assistant'
        );
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
        formData.append('file', audioBlob, 'audio.webm');
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
function speakResponse(text) {
    if (!window.speechSynthesis || document.hidden) return;
    const plainText = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/[*_#]/g, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\n+/g, ' ')
        .trim();
    if (!plainText || plainText.length > 500) return;
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
}

if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
    };
}

// =========================================
// MediaRecorder – Spracheingabe (wie TypeFREE)
// =========================================
let mediaRecorder = null;
let audioChunks = [];
let audioStream = null;

function releaseAudioStream() {
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
}

async function startRecording() {
    try {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const options = {};
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
            options.mimeType = 'audio/webm;codecs=opus';
        }
        mediaRecorder = new MediaRecorder(audioStream, options);
        audioChunks = [];
        state.isRecording = true;
        setMicStatus('recording');
        dom.input.placeholder = 'Aufnahme läuft ...';

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            state.isRecording = false;
            dom.input.placeholder = 'Nachricht eingeben...';
            releaseAudioStream();
            const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
            audioChunks = [];
            if (audioBlob.size > 0) sendAudioForTranscription(audioBlob);
        };

        mediaRecorder.onerror = () => {
            state.isRecording = false;
            setMicStatus('');
            dom.input.placeholder = 'Nachricht eingeben...';
            releaseAudioStream();
            addMessage('⚠️ Fehler bei der Audio-Aufnahme.', 'assistant');
        };

        mediaRecorder.start();
    } catch (err) {
        console.warn('Mikrofon-Zugriff verweigert:', err);
        setMicStatus('');
        dom.input.placeholder = 'Nachricht eingeben...';
        addMessage(
            '⚠️ **Mikrofon-Zugriff verweigert.**\n\n'
            + 'Bitte erlaube den Mikrofon-Zugriff in den Browser-Einstellungen.',
            'assistant'
        );
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
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