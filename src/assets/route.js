// Forgiving addresses for theramlakhan.com. Loaded by the 404 pages (this site's
// and the home site's), it reads the address loosely and redirects to the real page:
// any letter case, with or without dashes, old addresses and short ones.
//
//   /brainnovastudio/            -> /BrainnovaStudio/games/
//   /singleshot, /Single-Shot/   -> /BrainnovaStudio/games/single-shot/
//   /single-shot/privacy/        -> /BrainnovaStudio/games/single-shot/privacy/
//   /BrainnovaStudio/Test/SingleShot -> /BrainnovaStudio/test/single-shot/
//   /games/..., /test/...        -> the same under /BrainnovaStudio/
//
// If nothing matches, the page shows its own "not found" message.
(function () {
	'use strict';
	const BASE = '/BrainnovaStudio';
	const key = (s) => decodeURIComponent(s).toLowerCase().replace(/[^a-z0-9.]/g, '').replace(/\.html?$/, '');
	const show = () => {
		const miss = () => document.querySelectorAll('[data-route-miss]').forEach((el) => { el.hidden = false; });
		if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', miss); else miss();
	};

	fetch(BASE + '/games.json', { cache: 'no-cache' })
		.then((r) => (r.ok ? r.json() : Promise.reject()))
		.then((data) => {
			const slugs = {};
			data.games.forEach((g) => {
				slugs[key(g.slug)] = g.slug;
				slugs[key(g.name)] = g.slug;
				(g.aliases || []).forEach((a) => { slugs[key(a)] = g.slug; });
			});
			const to = resolve(location.pathname.split('/').filter(Boolean).map(key).filter((s) => s && s !== 'index'), slugs);
			if (to && to !== location.pathname) location.replace(to + location.search + location.hash);
			else show();
		})
		.catch(show);

	function resolve(seg, slugs) {
		if (seg[0] === 'brainnovastudio' || seg[0] === 'brainnova') seg = seg.slice(1);
		const [a, b, c, d] = seg;
		const game = (s) => s && slugs[s.replace(/\.apk$/, '')];
		const sub = (slug, rest) => {
			const r = rest[0];
			if (!r) return `${BASE}/games/${slug}/`;
			if (r === 'privacy' || r === 'help') return `${BASE}/games/${slug}/${r}/`;
			if (r === 'play') return `${BASE}/play/${slug}/`;
			if (r === 'test') return `${BASE}/test/${slug}/`;
			if (r.endsWith('.apk')) return `${BASE}/games/${slug}/${slug}.apk`;
			if (r === 'images') return null;
			return `${BASE}/games/${slug}/`;
		};
		if (!a) return `${BASE}/games/`;
		if (a === 'games' || a === 'game') {
			if (!b) return `${BASE}/games/`;
			if (b === 'test') return game(c) ? `${BASE}/test/${game(c)}/` : `${BASE}/test/`;
			if (game(b)) return sub(game(b), seg.slice(2));
			return `${BASE}/games/`;
		}
		if (a === 'test' || a === 'playearly') return game(b) ? `${BASE}/test/${game(b)}/` : `${BASE}/test/`;
		if (a === 'play') return game(b) ? `${BASE}/play/${game(b)}/` : `${BASE}/games/`;
		if (game(a)) return sub(game(a), seg.slice(1));
		return null;
	}
}());
