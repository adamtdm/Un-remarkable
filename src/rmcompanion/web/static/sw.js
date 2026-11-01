// Service Worker for reMarkable Companion PWA
const CACHE_NAME = "rmc-shell-v20261101c";
const STATIC_ASSETS = [
  "/",
  "/index.html",
  "/style.css?v=20261101c",
  "/app.js?v=20261101c",
  "/manifest.json",
  "/icon.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Network-only for API calls, MCP endpoints, and dynamic SVG pages
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/mcp")) {
    return;
  }

  // Network-first for static shell assets with offline fallback
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request);
      })
  );
});
