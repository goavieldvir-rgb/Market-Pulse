// Bump the version whenever the page shell changes so old caches are cleared.
const CACHE = "market-pulse-shell-v3";
const STATIC_SHELL = ["./manifest.json", "./icons/icon-192.png", "./icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Copy the response BEFORE handing it to the page: a body can only be read
// once, so cloning later (after the page started reading) throws.
function networkThenCache(request) {
  return fetch(request).then((res) => {
    if (res && res.ok) {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
    }
    return res;
  });
}

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;   // fonts etc. go straight to the network

  // Data files: always the network (the page adds a cache-busting ?t=). The last good copy is
  // kept under the bare path (one entry per file) and used only when offline.
  if (url.pathname.includes("/data/")) {
    const key = url.origin + url.pathname;
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(key, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(key))
    );
    return;
  }

  // Pages: network first so updates show immediately; cached copy when offline.
  const isDocument = e.request.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith("/");
  if (isDocument) {
    e.respondWith(networkThenCache(e.request).catch(() => caches.match(e.request)));
    return;
  }

  // Icons / manifest: serve from cache, refresh in the background.
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const refreshed = networkThenCache(e.request).catch(() => cached);
      return cached || refreshed;
    })
  );
});
