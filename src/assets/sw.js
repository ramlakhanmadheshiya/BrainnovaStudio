// Keeps the heavy, never-changing game files so a second visit starts at once:
// the shared engine (engine/<godot>/...) and each game's pack and streamed assets
// (play/<slug>/data/<hash>/...). Their URLs change whenever their content does,
// so a cached copy is always the right one. Everything else goes to the network.
const CACHE = 'brainnova-games-v1';
const KEEP = /\/BrainnovaStudio\/(engine\/|play\/[^/]+\/data\/)/;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET' || !KEEP.test(new URL(req.url).pathname)) return;
	event.respondWith(caches.open(CACHE).then(async (cache) => {
		const hit = await cache.match(req);
		if (hit) return hit;
		const res = await fetch(req);
		if (res.ok) {
			cache.put(req, res.clone());
			prune(cache, req.url);
		}
		return res;
	}));
});

// Drop older builds of the same game once a newer one is cached.
async function prune(cache, url) {
	const m = new URL(url).pathname.match(/^(\/BrainnovaStudio\/play\/[^/]+\/data\/)([0-9a-f]{10})\//);
	if (!m) return;
	for (const key of await cache.keys()) {
		const k = new URL(key.url).pathname.match(/^(\/BrainnovaStudio\/play\/[^/]+\/data\/)([0-9a-f]{10})\//);
		if (k && k[1] === m[1] && k[2] !== m[2]) cache.delete(key);
	}
}
