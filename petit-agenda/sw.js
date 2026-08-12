const CACHE = "petit-agenda-v1";
const ASSETS = [
  "./",
  "index.html",
  "css/app.css",
  "js/app.js",
  "manifest.webmanifest",
  "fonts/baloo2.woff2",
  "fonts/nunito.woff2",
  "fonts/caveat.woff2",
  "img/icon-180.png",
  "img/icon-192.png",
  "img/icon-512.png"
];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// cache d'abord (l'app marche hors-ligne), mise à jour en arrière-plan
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET" || !e.request.url.startsWith(self.location.origin)) return;
  e.respondWith(
    caches.match(e.request).then(hit => {
      const net = fetch(e.request).then(res => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
