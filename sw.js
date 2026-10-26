// オフライン対応: アプリ本体は「通信できれば最新、できなければ保存分」、
// 地図タイル(国土地理院)は「保存分があればそれを使う」。
const SHELL = 'manhole-shell-v1';
const TILES = 'manhole-tiles-v1';
const SHELL_URLS = [
  './',
  './index.html',
  './apple-touch-icon.png',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet@1.9.4/dist/images/layers.png',
  'https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png'
];
const TILE_HOST = 'cyberjapandata.gsi.go.jp';

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SHELL).then((c) => Promise.all(SHELL_URLS.map((u) => c.add(u).catch(() => {})))).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('manhole-shell-') && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.hostname === TILE_HOST) {
    e.respondWith(
      caches.open(TILES).then((c) =>
        c.match(req.url).then((hit) => hit || fetch(req).then((res) => {
          if (res.ok) c.put(req.url, res.clone());
          return res;
        }).catch(() => new Response('', { status: 504 })))
      )
    );
    return;
  }

  if (url.origin === self.location.origin || url.hostname === 'unpkg.com') {
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req, { ignoreSearch: true }).then((hit) => hit || caches.match('./index.html')))
    );
  }
});
