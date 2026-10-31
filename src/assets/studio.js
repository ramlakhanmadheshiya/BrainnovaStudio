// Brainnova Studio pages: theme toggle, filters, details sheet,
// tester checklist, share and QR. No dependencies (qr.js is optional).
(() => {
	'use strict';
	const $ = (s, r = document) => r.querySelector(s);
	const $$ = (s, r = document) => [...r.querySelectorAll(s)];
	const platform = document.documentElement.dataset.platform || 'other';
	const games = window.BN_GAMES || [];
	const studio = window.BN_STUDIO || {};
	const store = {
		get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (_) { return d; } },
		set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* private mode */ } },
	};

	// ------------------------------------------------------------ nav + reveal
	const nav = $('[data-nav]');
	const onScroll = () => nav && nav.classList.toggle('is-scrolled', scrollY > 8);
	addEventListener('scroll', onScroll, { passive: true });
	onScroll();

	function toast(text) {
		let t = $('.toast');
		if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); document.body.append(t); }
		t.textContent = text;
		t.classList.add('is-on');
		clearTimeout(t._h);
		t._h = setTimeout(() => t.classList.remove('is-on'), 2200);
	}

	// ------------------------------------------------------------ theme
	// The first visit follows the system; the toggle then remembers the choice.
	const root = document.documentElement;
	const systemDark = matchMedia('(prefers-color-scheme: dark)');
	const isDark = () => (root.dataset.theme ? root.dataset.theme === 'dark' : systemDark.matches);
	const paintToggle = () => $$('[data-theme-toggle]').forEach((b) => {
		b.setAttribute('aria-label', isDark() ? 'Switch to light theme' : 'Switch to dark theme');
	});
	$$('[data-theme-toggle]').forEach((b) => b.addEventListener('click', () => {
		root.dataset.theme = isDark() ? 'light' : 'dark';
		try { localStorage.setItem('bn-theme', root.dataset.theme); } catch (_) { /* private mode */ }
		paintToggle();
	}));
	systemDark.addEventListener('change', paintToggle);
	paintToggle();

	// ------------------------------------------------------------ warm the game engine
	// Every browser game shares one engine. While the visitor looks around, the
	// service worker quietly downloads and keeps it, so "Play in browser" then only
	// needs the game's own small pack. Not on Android (no browser play there) and
	// not when the visitor asked to save data.
	const conn = navigator.connection || {};
	if (window.BN_WARM && window.BN_WARM.length && platform !== 'android' && 'serviceWorker' in navigator
		&& !conn.saveData && !/(^|-)2g$/.test(conn.effectiveType || '')) {
		addEventListener('load', () => setTimeout(() => {
			navigator.serviceWorker.register(window.BN_SW || '/BrainnovaStudio/sw.js', { scope: '/BrainnovaStudio/' })
				.then(() => navigator.serviceWorker.ready)
				.then((reg) => reg.active && reg.active.postMessage({ warm: window.BN_WARM }))
				.catch(() => {});
		}, 2500));
	}

	// ------------------------------------------------------------ device line
	const device = $('[data-device]');
	if (device) {
		const free = (window.BN_STUDIO && window.BN_STUDIO.free_levels) || 10;
		const say = {
			android: 'You’re on Android, so every game comes straight from Google Play.',
			apple: 'You’re on an Apple device: play every level right here in your browser.',
			other: `You’re on a computer: try the first ${free} levels of any game in your browser.`,
		}[platform];
		device.innerHTML = '<span></span>';
		device.lastChild.textContent = say;
	}

	// ------------------------------------------------------------ filters
	const grid = $('[data-grid]');
	$$('[data-filter]').forEach((chip) => chip.addEventListener('click', () => {
		const f = chip.dataset.filter;
		$$('[data-filter]').forEach((c) => c.setAttribute('aria-selected', String(c === chip)));
		let shown = 0;
		$$('.game', grid).forEach((card) => {
			const on = f === 'all' || card.dataset.status === f;
			card.classList.toggle('is-hidden', !on);
			if (on) shown++;
		});
		const empty = $('[data-empty]');
		if (empty) empty.hidden = shown > 0;
	}));

	// ------------------------------------------------------------ details sheet
	const sheet = $('[data-sheet]');
	const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
	const nice = (s) => (s ? new Date(s + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '');

	function openDetails(slug, opener) {
		const g = games.find((x) => x.slug === slug);
		if (!g || !sheet) return;
		const step = { development: 0, 'closed-testing': 1, published: 2 }[g.status];
		const stage = (i, title, date, idle) => `<li class="${i < step ? 'done' : i === step ? 'now done' : ''}"><b>${title}</b><span>${date ? esc(nice(date)) : esc(idle)}</span></li>`;
		const shots = (g.shots || []).map((s) => `<img src="${esc(g.links.icon.split('?')[0].replace('icon.svg', s))}" alt="" loading="lazy">`).join('');
		const actions = opener && opener.closest('.game') ? $('.actions', opener.closest('.game')).cloneNode(true) : null;
		if (actions) actions.querySelector('[data-details]')?.remove();
		const live = g.status !== 'development';
		sheet.style.cssText = `--g-bg:${g.colors.bg};--g-accent:${g.colors.accent};--g-glow:${g.colors.glow}`;
		$('[data-sheet-body]', sheet).innerHTML = `
			<div class="sheet-hero">
				<img src="${esc(g.links.icon)}" alt="">
				<div><h2 id="sheet-title">${esc(g.name)}</h2><p>${esc(g.tagline)}</p></div>
				<button class="sheet-close" type="button" aria-label="Close" data-close>×</button></div>
			<div class="sheet-content">
				<p>${esc(g.blurb)}</p>
				${shots ? `<div><h3>Look inside</h3><div class="shots">${shots}</div></div>` : ''}
				<div><h3>Journey</h3><ol class="journey" style="--p:0">
					${stage(0, 'Started', g.dates.started, '')}
					${stage(1, 'Closed testing', g.dates.testing, step >= 1 ? 'Now' : 'Next')}
					${stage(2, 'Google Play', g.dates.published, 'Soon')}
				</ol></div>
				<div><h3>How to play</h3><p>${esc(g.hint)}</p></div>
				<div data-sheet-actions></div>
				${live ? `<nav class="sheet-links" aria-label="${esc(g.name)} links"><a href="${esc(g.links.page)}">More about ${esc(g.name)}</a><a href="${esc(g.links.help)}">How to play</a><a href="${esc(g.links.privacy)}">Privacy</a></nav>` : ''}
			</div>`;
		if (actions) $('[data-sheet-actions]', sheet).append(actions);
		sheet.showModal();
		requestAnimationFrame(() => requestAnimationFrame(() => $('.journey', sheet).style.setProperty('--p', String(step / 2))));
		history.replaceState(null, '', '#' + slug);
	}
	if (sheet) {
		document.addEventListener('click', (ev) => {
			const b = ev.target.closest('[data-details]');
			if (b) openDetails(b.dataset.details, b);
			if (ev.target.closest('[data-close]')) sheet.close();
		});
		sheet.addEventListener('click', (ev) => { if (ev.target === sheet) sheet.close(); });
		sheet.addEventListener('close', () => history.replaceState(null, '', location.pathname + location.search));
		const deep = decodeURIComponent(location.hash.slice(1));
		if (deep && games.some((g) => g.slug === deep)) {
			const btn = $(`[data-details="${CSS.escape(deep)}"]`);
			setTimeout(() => openDetails(deep, btn), 300);
		}
	}

	// ------------------------------------------------------------ tester steps
	$$('[data-steps]').forEach((list) => {
		const key = 'bn-steps-' + list.dataset.steps;
		const done = new Set(store.get(key, []));
		const steps = $$('.step', list);
		const paint = () => {
			steps.forEach((s) => s.classList.toggle('is-done', done.has(s.dataset.step)));
			const bar = $('[data-progress]');
			const txt = $('[data-progress-text]');
			if (bar) bar.style.width = `${(done.size / steps.length) * 100}%`;
			if (txt) txt.textContent = done.size === steps.length ? 'All set. Thank you for testing!' : `${done.size} of ${steps.length} done`;
		};
		steps.forEach((s) => $('[data-done]', s)?.addEventListener('click', () => {
			done.add(s.dataset.step);
			store.set(key, [...done]);
			setTimeout(paint, 400);
		}));
		paint();
	});

	// ------------------------------------------------------------ share + QR
	$$('[data-share]').forEach((b) => b.addEventListener('click', async () => {
		const url = ($('[data-invite]') || {}).value || location.href;
		const data = { title: b.dataset.title, text: b.dataset.text, url };
		try {
			if (navigator.share) { await navigator.share(data); return; }
			await navigator.clipboard.writeText(url);
			toast('Link copied');
		} catch (_) { /* cancelled */ }
	}));
	$$('[data-invite]').forEach((i) => i.addEventListener('focus', () => i.select()));

	function drawQR() {
		$$('[data-qr]').forEach((box) => {
			const holder = $('[data-qr-box]', box);
			if (!holder || holder.firstChild || typeof window.qrcode !== 'function') return;
			const q = window.qrcode(0, 'M');
			q.addData(box.dataset.qr);
			q.make();
			holder.innerHTML = q.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
		});
	}
	if ($('[data-qr]') && platform !== 'android') {
		if (typeof window.qrcode === 'function') drawQR();
		else {
			const s = document.createElement('script');
			s.src = (studio.base || '/BrainnovaStudio') + '/assets/qr.js';
			s.onload = drawQR;
			document.head.append(s);
		}
	}

})();
