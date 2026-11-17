// Offline cache: pages, data and photos are kept after the first visit, so the player works in a gym with
// one bar of signal. Bump VERSION when files change so phones refresh.
const VERSION = 'vault-v4';
const CORE = ['./', './index.html', './play.html', './print.html', './start.html', './install.html', './week.html', './climb.html', './spice.html', './journal.html', './checklist.html', './guide.html', './videos.html', './vault.css', './vault.js', './data/vault.json', './manifest.json'];
self.addEventListener('install', e => { e.waitUntil(caches.open(VERSION).then(c => Promise.all(CORE.map(u => fetch(u, { cache: 'no-cache' }).then(r => c.put(u, r)).catch(() => {})))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin) return;             // YouTube and fonts go straight through
  if (/\.(json|html|css|js)$/.test(u.pathname) || u.pathname.endsWith('/')) {
    // network first, cache as fallback. cache:'no-cache' makes the phone ask the server whether the page changed.
    e.respondWith(fetch(e.request.url, { cache: 'no-cache', credentials: 'same-origin' }).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); return r; }).catch(() => caches.match(e.request)));
  } else {
    // photos: cache first, they rarely change
    e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => { const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); return r; })));
  }
});
