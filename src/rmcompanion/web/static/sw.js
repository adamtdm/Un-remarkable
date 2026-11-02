// Self-destructing Service Worker: purges all rmc-shell caches and unregisters itself
const CACHE_PREFIX = "rmc-shell";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(keys.map((key) => caches.delete(key)));
    }).then(() => {
      return self.registration.unregister();
    }).then(() => {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", (event) => {
  // Always bypass cache and go straight to network
  event.respondWith(fetch(event.request));
});
