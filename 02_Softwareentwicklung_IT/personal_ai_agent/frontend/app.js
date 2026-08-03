/**
 * Personal AI Agent – Frontend Application
 * 
 * Features:
 * - Chat-UI mit Nachrichtenverlauf
 * - Verbindung zum FastAPI-Backend
 * - TTS (Text-to-Speech) via SpeechSynthesis API
 * - Auto-Resize der Texteingabe
 * - Markdown-Unterstützung für Antworten
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
    // Code blocks
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
    });

    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Unordered lists
    text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Line breaks
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

    // Scroll to bottom
    dom.messages.parentElement.scrollTop = dom.messages.parentElement.scrollHeight;

    // Store in state
    state.messages.push({ role, content });
}

function setLoading(loading) {
    state.isProcessing = loading;
    dom.loading.classList.toggle('hidden', !loading);
    dom.input.disabled = loading;
    dom.sendBtn.disabled = loading || !dom.input.value.trim();
}

function setOnline(online) {
    state.isOnline = online;
    dom.statusIndicator.className = `status ${online ? 'online' : 'offline'}`;
    dom.statusText.textContent = online ? 'Online' : 'Offline';
}

function updateSendButton() {
    dom.sendBtn.disabled = !dom.input.value.trim() || state.isProcessing;
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

        // Update memory count in footer
        updateFooterNote(
            document.querySelector('.footer-note')
        );

        // Auto-speak the response (TTS)
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

// =========================================
// TTS (Text-to-Speech)
// =========================================
function speakResponse(text) {
    if (!window.speechSynthesis) return;

    // Only speak if the page is visible and not too many messages
    if (document.hidden) return;

    // Extract plain text from markdown (remove formatting)
    const plainText = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/[*_#]/g, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\n+/g, ' ')
        .trim();

    if (!plainText || plainText.length > 500) return; // Don't read very long responses

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(plainText);
    utterance.lang = 'de-DE';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    // Try to find a German voice
    const voices = window.speechSynthesis.getVoices();
    const germanVoice = voices.find(v => v.lang.startsWith('de'));
    if (germanVoice) {
        utterance.voice = germanVoice;
    }

    window.speechSynthesis.speak(utterance);
}

// Also load voices early
if (window.speechSynthesis) {
    window.speechSynthesis.getVoices(); // Trigger loading
    window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.getVoices();
    };
}

// =========================================
// Event Handlers
// =========================================
dom.input.addEventListener('input', () => {
    // Auto-resize textarea
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
    // Check immediately
    checkHealth();

    // Then every 30 seconds
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