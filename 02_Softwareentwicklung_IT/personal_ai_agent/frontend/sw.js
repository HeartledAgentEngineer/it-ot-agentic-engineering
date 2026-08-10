/**
 * Personal AI Agent – Service Worker
 * 
 * Minimaler Service Worker für PWA-Funktionalität:
 * - Offline-Fallback
 * - Cache für statische Assets
 */

// Version hochzählen, sobald sich eine Datei aus STATIC_ASSETS ändert –
// sonst liefert der Cache-first-Handler unten weiter die alte Fassung aus.
const CACHE_NAME = 'personal-ai-agent-v10';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/style.css',
    '/app.js',
    '/pcm-recorder.js',
    '/manifest.json',
];

// Install: Cache statische Assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate: Alte Caches löschen
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        })
    );
    self.clients.claim();
});

// Fetch: Cache-first für statische Assets, Network-first für API
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Streaming gar nicht anfassen: Ginge die Antwort durch den Service
    // Worker, könnte sie gepuffert werden – dann erschiene der Text wieder
    // als Block statt nach und nach.
    if (url.pathname === '/api/chat/stream') {
        return;
    }

    // API-Calls: Network-first (nie cachen)
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request).catch(() => {
                return new Response(
                    JSON.stringify({ error: 'Offline – Server nicht erreichbar' }),
                    { status: 503, headers: { 'Content-Type': 'application/json' } }
                );
            })
        );
        return;
    }

    // Statische Assets: Cache-first
    event.respondWith(
        caches.match(request).then((cached) => {
            return cached || fetch(request).then((response) => {
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(request, response.clone());
                    return response;
                });
            }).catch(() => {
                // Offline-Fallback
                if (request.mode === 'navigate') {
                    return caches.match('/index.html');
                }
                return new Response('Offline', { status: 503 });
            });
        })
    );
});