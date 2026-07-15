const CACHE = "va-shell-v1";
const ASSETS = ["/", "/assets/styles.css", "/assets/app.js", "/assets/favicon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) return;
  event.respondWith(
    caches.match(req).then((cached) => cached || fetch(req).catch(() => caches.match("/")))
  );
});
