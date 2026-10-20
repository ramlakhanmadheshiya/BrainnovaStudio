// The browser-play page for every Brainnova game: theramlakhan.com/BrainnovaStudio/play/<slug>/
//
// It decides what this device may do, shows a loader, then boots the game with the
// shared engine (engine/<godot>/) and the game's own pack (play/<slug>/data/), both
// published by build.py from the game's latest build.
// Rules (games.json decides the status, the device decides the rest):
//
//   status development       "Coming soon" card. ?preview plays it anyway (for you).
//   Android / Chromebook     never downloads the engine: a card sends them to Google Play,
//                            or to the testing page while the game is in closed testing.
//                            ?play lets Android through (for your own testing).
//   iPhone, iPad, Mac        the whole game, with every ad type including full-screen ones.
//   everything else          the first web.free_levels levels, no full-screen ads.
//
// The game reads all of this through window.Brainnova (see the API at the bottom),
// so changing a rule here never needs a game rebuild.
(() => {
	'use strict';
	const C = window.BN_CONFIG;
	const g = C.game;
	const L = g.links;
	const params = new URLSearchParams(location.search);
	const platform = window.BN_PLATFORM || 'other';
	const full = platform === 'apple';
	const $ = (s) => document.querySelector(s);
	const loader = $('#bn-loader');
	const statusEl = $('[data-status]');
	const ring = $('[data-ring]');
	const card = $('[data-card]');
	const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

	const policy = {
		platform,
		levelCap: full ? 0 : (C.web.free_levels | 0),
		interstitials: full,
		rewarded: true,
		banner: true,
	};
	// ?cap=N previews a smaller free-level limit (it can only lower it, never lift it).
	const capParam = parseInt(params.get('cap'), 10);
	if (capParam > 0 && (policy.levelCap === 0 || capParam < policy.levelCap)) policy.levelCap = capParam;

	// ------------------------------------------------------------------ cards on the loader
	function showCard(html) {
		loader.classList.add('is-card');
		ring.closest('.loader-ring').classList.add('is-still');
		statusEl.hidden = true;
		$('[data-hint]').hidden = true;
		card.innerHTML = html;
		card.hidden = false;
	}

	const playCta = () => (g.status === 'published'
		? { href: 'https://play.google.com/store/apps/details?id=' + g.package, label: 'Get it on Google Play' }
		: { href: L.test, label: 'Play early on Android' });

	function gate() {
		if (g.status === 'development' && !params.has('preview')) {
			showCard(`<p>${esc(g.name)} is still being made. It lands here as soon as it's ready.</p>
				<a class="cta" href="${esc(C.studio.base)}/games/">See all games</a>`);
			return true;
		}
		if (platform === 'android' && !params.has('play')) {
			const cta = playCta();
			const line = g.status === 'published'
				? `${esc(g.name)} is on Google Play: it plays best as the app.`
				: `${esc(g.name)} is in testing on Google Play. Join in three steps and play it before anyone else.`;
			showCard(`<p>${line}</p><a class="cta" href="${esc(cta.href)}">${esc(cta.label)}</a>
				<a class="more" href="${esc(C.studio.base)}/games/">All games</a>`);
			return true;
		}
		return false;
	}

	// ------------------------------------------------------------------ loading
	// The engine (shared by every game, so it's cached after the first one) and the
	// game's own small pack download together. Music and other big assets are not
	// in the pack: the game streams them afterwards (Brainnova.assetUrl), so it can
	// start as soon as these two arrive. sw.js keeps all of it for the next visit.
	const B = C.build;
	const MB = (n) => (n / 1048576).toFixed(n >= 10485760 ? 0 : 1);
	let shown = 0;
	function progress(cur, total) {
		if (!(total > 0)) return;
		const p = Math.min(100, (cur / total) * 100);
		if (p < shown) return;
		shown = p;
		ring.style.strokeDashoffset = String(100 - p);
		statusEl.textContent = p >= 99.5 ? 'Starting…' : `Loading ${MB(cur)} of ${MB(total)} MB`;
	}

	// Count the bytes of the engine and pack as they arrive, for an honest progress ring.
	// The count reads a clone, so the engine still gets the browser's original
	// response (which lets the browser keep the compiled engine for next time).
	function trackDownloads(urls, total) {
		const done = {};
		const original = window.fetch.bind(window);
		window.fetch = (input, init) => original(input, init).then((res) => {
			const url = new URL(typeof input === 'string' ? input : input.url, location.href).pathname;
			if (!urls.includes(url) || !res.body) return res;
			done[url] = 0;
			const reader = res.clone().body.getReader();
			(function pump() {
				reader.read().then(({ done: end, value }) => {
					if (end) return;
					done[url] += value.byteLength;
					progress(Object.values(done).reduce((a, b) => a + b, 0), total);
					pump();
				}).catch(() => {});
			}());
			return res;
		});
	}

	function fail(err) {
		console.error(err);
		showCard(`<p>The game couldn't start in this browser.</p><p class="small">${esc(err && err.message ? err.message : err)}</p>
			<a class="cta" href="">Try again</a><a class="more" href="${esc(C.studio.base)}/games/">All games</a>`);
	}

	function loadScript(src) {
		return new Promise((ok, no) => {
			const s = document.createElement('script');
			s.src = src; s.onload = ok; s.onerror = () => no(new Error('Could not load ' + src));
			document.head.append(s);
		});
	}

	async function boot() {
		if (!B) {
			showCard(`<p>${esc(g.name)} isn't ready to play in the browser yet.</p><a class="cta" href="${esc(L.page)}">About ${esc(g.name)}</a>`);
			return;
		}
		if ('serviceWorker' in navigator) navigator.serviceWorker.register(C.studio.base + '/sw.js').catch(() => {});
		const slow = setTimeout(() => {
			$('[data-hint]').textContent = 'The first visit downloads the game once. Next time it opens in a moment.';
		}, 6000);
		try {
			trackDownloads([B.engine.wasm, B.pack.url], B.engine.wasmSize + B.pack.size);
			await loadScript(B.engine.js);
			const config = Object.assign({}, B.config || {}, {
				executable: B.engine.exe,
				mainPack: B.pack.url,
				canvas: document.getElementById('canvas'),
				canvasResizePolicy: 2,
				focusCanvas: true,
				fileSizes: {},
			});
			const missing = window.Engine.getMissingFeatures({ threads: false });
			if (missing.length) throw new Error('This browser is missing: ' + missing.join(', '));
			const engine = new window.Engine(config);
			statusEl.textContent = 'Loading…';
			await engine.startGame({ onProgress: () => {} });
			clearTimeout(slow);
			loader.classList.add('is-gone');
			setTimeout(() => loader.remove(), 700);
			config.canvas.focus();
		} catch (err) {
			clearTimeout(slow);
			fail(err);
		}
	}

	// ------------------------------------------------------------------ ads
	// Providers: "house" (our own games, until a real network is set), "none",
	// "adsense" (banner via AdSense; rewarded/interstitial via Google's H5 Games
	// Ads once web.ads.rewarded / web.ads.interstitial are set to "h5").
	const adsCfg = C.web.ads || {};
	const banner = $('#bn-banner');
	let bannerOn = false;
	const resizeListeners = [];
	const bannerHeight = () => (innerWidth >= 768 && innerHeight >= 640 ? 90 : 50);

	function house() {
		// A gentle, tappable strip about our own games, same size as a real banner.
		const pool = C.games.filter((o) => o.status !== 'development');
		const pick = pool.find((o) => o.slug === g.slug) || pool[0];
		if (!pick) return '';
		const go = pick.status === 'published' ? 'Get it on Google Play' : 'Play early on Android';
		const href = pick.status === 'published' ? pick.links.store : pick.links.test;
		return `<a class="house" href="${esc(href)}" target="_blank" rel="noopener">
			<img src="${esc(pick.links.icon)}" alt="" width="34" height="34"><span><b>${esc(pick.name)}</b><small>${esc(go)}</small></span><em>Brainnova</em></a>`;
	}

	function fillBanner() {
		const provider = adsCfg.provider || 'house';
		if (provider === 'adsense' && adsCfg.adsense_client && adsCfg.banner_slot) {
			if (!document.querySelector('script[data-adsense]')) {
				const s = document.createElement('script');
				s.async = true; s.dataset.adsense = '1'; s.crossOrigin = 'anonymous';
				s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(adsCfg.adsense_client);
				document.head.append(s);
			}
			banner.innerHTML = `<ins class="adsbygoogle" style="display:block;width:100%;height:100%" data-ad-client="${esc(adsCfg.adsense_client)}" data-ad-slot="${esc(adsCfg.banner_slot)}" data-full-width-responsive="false"></ins>`;
			(window.adsbygoogle = window.adsbygoogle || []).push({});
			return true;
		}
		if (provider === 'house') { banner.innerHTML = house(); return banner.innerHTML !== ''; }
		return false;
	}

	function fraction() { return bannerOn ? bannerHeight() / Math.max(1, innerHeight) : 0; }
	addEventListener('resize', () => {
		if (!bannerOn) return;
		banner.style.setProperty('--bh', bannerHeight() + 'px');
		resizeListeners.forEach((cb) => { try { cb(fraction()); } catch (_) { /* game gone */ } });
	});

	// H5 Games Ads (Ad Placement API). Only loads once configured.
	const h5 = (adsCfg.rewarded === 'h5' || adsCfg.interstitial === 'h5') && adsCfg.adsense_client;
	if (h5) {
		window.adsbygoogle = window.adsbygoogle || [];
		window.adBreak = window.adConfig = function (o) { window.adsbygoogle.push(o); };
		const s = document.createElement('script');
		s.async = true; s.crossOrigin = 'anonymous';
		s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(adsCfg.adsense_client);
		s.dataset.adFrequencyHint = '60s';
		document.head.append(s);
	}

	// ------------------------------------------------------------------ the free-levels card
	function capReached() {
		const modal = $('#bn-modal');
		const cta = playCta();
		modal.innerHTML = `<div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="cap-title">
			<img src="${esc(L.icon)}" alt="" width="88" height="88">
			<h2 id="cap-title">You've played the free levels</h2>
			<p>That's the first ${policy.levelCap} levels of ${esc(g.name)} on the web. The whole game is waiting on Android.</p>
			<div class="modal-qr" data-qr hidden><div data-qr-box></div><span>Scan with your Android phone</span></div>
			<a class="cta" href="${esc(cta.href)}" target="_blank" rel="noopener">${esc(cta.label)}</a>
			<button class="more" type="button" data-close>Back to the game</button>
		</div>`;
		modal.hidden = false;
		requestAnimationFrame(() => modal.classList.add('is-on'));
		const qr = modal.querySelector('[data-qr]');
		const target = new URL(cta.href, location.href).href;
		if (typeof window.qrcode === 'function') {
			const q = window.qrcode(0, 'M'); q.addData(target); q.make();
			qr.querySelector('[data-qr-box]').innerHTML = q.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
			qr.hidden = false;
		}
		const close = () => {
			modal.classList.remove('is-on');
			setTimeout(() => { modal.hidden = true; modal.innerHTML = ''; }, 300);
			document.getElementById('canvas').focus();
		};
		modal.querySelector('[data-close]').addEventListener('click', close);
		modal.addEventListener('click', (ev) => { if (ev.target === modal) close(); }, { once: true });
	}

	// ------------------------------------------------------------------ the API the game uses
	// From GDScript (JavaScriptBridge):
	//   Brainnova.policyJSON()           -> '{"platform":"apple","levelCap":0,"interstitials":true,...}'
	//   Brainnova.capReached()           shows the "get the full game" card
	//   Brainnova.assetUrl("music/ch1.ogg") -> URL to stream it from ("" if none)
	//   Brainnova.ads.bannerShow()       -> fraction of the screen height the banner takes (0 = none)
	//   Brainnova.ads.bannerHide()
	//   Brainnova.ads.onBannerResize(cb) cb(fraction) when the window changes size
	//   Brainnova.ads.rewardedReady()    -> bool
	//   Brainnova.ads.rewardedShow(cb)   cb(true) if the reward was earned
	//   Brainnova.ads.interstitialReady() -> bool (always false where policy says no)
	//   Brainnova.ads.interstitialShow(cb) cb() when it's closed
	window.Brainnova = {
		version: 1,
		platform,
		policy,
		game: { slug: g.slug, name: g.name, status: g.status },
		// URL of a streamed asset ("music/ch1.ogg"), or "" if this build has none.
		assetUrl: (rel) => (B && B.assets && B.assets[rel] ? new URL(B.assets[rel], location.href).href : ''),
		policyJSON: () => JSON.stringify(policy),
		capReached,
		ads: {
			bannerShow() {
				if (bannerOn) return fraction();
				if (!fillBanner()) return 0;
				bannerOn = true;
				banner.style.setProperty('--bh', bannerHeight() + 'px');
				banner.hidden = false;
				return fraction();
			},
			bannerHide() { bannerOn = false; banner.hidden = true; banner.innerHTML = ''; },
			onBannerResize(cb) { resizeListeners.push(cb); },
			rewardedReady: () => !!(h5 && adsCfg.rewarded === 'h5'),
			rewardedShow(cb) {
				if (!(h5 && adsCfg.rewarded === 'h5')) { cb(false); return; }
				let earned = false;
				window.adBreak({
					type: 'reward', name: 'reward-' + g.slug,
					beforeReward: (show) => show(),
					adViewed: () => { earned = true; },
					adDismissed: () => { earned = false; },
					adBreakDone: () => cb(earned),
				});
			},
			interstitialReady: () => !!(policy.interstitials && h5 && adsCfg.interstitial === 'h5'),
			interstitialShow(cb) {
				if (!this.interstitialReady()) { cb(); return; }
				window.adBreak({ type: 'next', name: 'next-' + g.slug, adBreakDone: () => cb() });
			},
		},
	};

	if (!gate()) boot();
})();
