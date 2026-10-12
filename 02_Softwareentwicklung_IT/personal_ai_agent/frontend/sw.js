/**
 * Personal AI Agent – Service Worker
 * 
 * Minimaler Service Worker für PWA-Funktionalität:
 * - Offline-Fallback
 * - Cache für statische Assets
 */

// Version hochzählen, wenn sich die Liste unten ändert. Für Änderungen an
// index.html, app.js oder style.css ist das seit v11 nicht mehr nötig: Der
// Fetch-Handler holt sie zuerst aus dem Netz (siehe unten).
//
// Warum die Umstellung: Die alte Cache-first-Strategie verlangte, bei jeder
// Frontend-Änderung diese Zahl von Hand zu erhöhen. Wird es vergessen –
// und es wird vergessen –, liefert das Handy nach einem `git pull`
// weiterhin die alte Oberfläche aus, ohne jeden Hinweis darauf.
//
// v18 (P0, 12.10.2026): '/' und '/index.html' stehen NICHT mehr in der Liste.
// Der Server setzt den API-Schlüssel in index.html ein; ein rohes addAll legte
// ihn sonst dauerhaft im Cache ab. Die Seite kommt über den Fetch-Zweig in den
// Cache, und zwar nur ohne Schlüssel (schluesselEntfernen).
const CACHE_NAME = 'personal-ai-agent-v18';
const STATIC_ASSETS = [
    '/style.css',
    '/app.js',
    '/pcm-recorder.js',
    '/manifest.json',
    '/icon-192.png',
    '/icon-512.png',
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

    // Statische Assets: Netzwerk zuerst, Cache als Rückfall.
    //
    // Umgekehrt zur früheren Fassung. Cache-first war schneller, lieferte aber
    // nach einem Update so lange die alte Oberfläche aus, bis jemand daran
    // dachte, CACHE_NAME hochzuzählen. Offline bleibt voll erhalten – der
    // Cache wird bei jeder erfolgreichen Antwort aufgefrischt und greift,
    // sobald das Netz wegfällt. Der Preis ist ein Roundtrip beim Start,
    // im Heimnetz nicht spürbar.
    event.respondWith(
        fetch(request)
            .then((response) => {
                // Nur brauchbare Antworten in den Cache legen. Eine 404 als
                // Offline-Fassung zu konservieren wäre schlimmer als nichts.
                if (response && response.ok) {
                    const kopie = response.clone();
                    const typ = response.headers.get('Content-Type') || '';
                    // HTML trägt den API-Schlüssel im Meta-Feld: nur ohne ablegen.
                    const ablage = typ.includes('text/html')
                        ? kopie.text().then((text) => new Response(schluesselEntfernen(text), {
                            status: kopie.status,
                            statusText: kopie.statusText,
                            headers: kopie.headers,
                        }))
                        : Promise.resolve(kopie);
                    ablage.then((eintrag) => caches.open(CACHE_NAME)
                        .then((cache) => cache.put(request, eintrag)));
                }
                return response;
            })
            .catch(() => caches.match(request).then((cached) => {
                if (cached) return cached;
                if (request.mode === 'navigate') {
                    // Offline-Hülle: die zuletzt geladene Startseite (ohne Schlüssel).
                    return caches.match('/').then((seite) => seite || caches.match('/index.html'));
                }
                return new Response('Offline', { status: 503 });
            }))
    );
});

/** Leert das Meta-Feld agent-schluessel einer HTML-Seite (P0, 12.10.2026).
 *  Der übrige Text bleibt Zeichen für Zeichen gleich. Offline startet die App
 *  damit ohne Schlüssel – der Server ist dann ohnehin nicht erreichbar. */
function schluesselEntfernen(html) {
    return String(html).replace(
        /(<meta\s+name="agent-schluessel"\s+content=")[^"]*(")/gi, '$1$2');
}