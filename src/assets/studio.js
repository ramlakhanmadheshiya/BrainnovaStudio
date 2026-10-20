// Brainnova Studio pages: theme toggle, the neural field, filters, details sheet,
// tester checklist, share and QR. No dependencies (qr.js is optional).
(() => {
	'use strict';
	const $ = (s, r = document) => r.querySelector(s);
	const $$ = (s, r = document) => [...r.querySelectorAll(s)];
	const platform = document.documentElement.dataset.platform || 'other';
	const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
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
		device.innerHTML = `<i aria-hidden="true">✦</i><span></span>`;
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

	// ------------------------------------------------------------ card tilt + light
	if (!reduced && matchMedia('(hover: hover)').matches) {
		$$('[data-tilt]').forEach((m) => {
			m.addEventListener('pointermove', (ev) => {
				const r = m.getBoundingClientRect();
				const x = (ev.clientX - r.left) / r.width;
				const y = (ev.clientY - r.top) / r.height;
				m.style.setProperty('--mx', `${x * 100}%`);
				m.style.setProperty('--my', `${y * 100}%`);
				m.style.setProperty('--ry', `${(x - .5) * 10}deg`);
				m.style.setProperty('--rx', `${(.5 - y) * 8}deg`);
			});
			m.addEventListener('pointerleave', () => {
				m.style.setProperty('--ry', '0deg');
				m.style.setProperty('--rx', '0deg');
			});
		});
	}

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
			<div class="sheet-hero"><div class="aura" aria-hidden="true"></div>
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

	// ------------------------------------------------------------ the neural field
	// Neurons drift; the pointer pulls on them and draws synapses; a tap fires a
	// nova that ripples outward and lights every neuron it passes.
	const canvas = $('[data-field]');
	if (canvas) field(canvas);

	function field(cv) {
		const ctx = cv.getContext('2d');
		let w = 0, h = 0, dpr = 1, nodes = [], waves = [], pointer = null, running = false, visible = true, last = 0, idle = 0;
		const LINK = 130;

		function size() {
			const r = cv.getBoundingClientRect();
			dpr = Math.min(2, devicePixelRatio || 1);
			w = r.width; h = r.height;
			cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
			ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
			const n = Math.round(Math.min(150, Math.max(40, (w * h) / 9000)));
			nodes = Array.from({ length: n }, () => ({
				x: Math.random() * w, y: Math.random() * h,
				vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25,
				r: 1.2 + Math.random() * 1.8, e: 0, hue: Math.random(),
			}));
		}

		function nova(x, y, power = 1) {
			waves.push({ x, y, r: 0, power, max: Math.hypot(w, h) * .7 });
			idle = 0;
		}

		function color(t, a) {
			// violet -> pink -> coral across the field
			const c = [[123, 92, 255], [194, 92, 255], [255, 107, 91]];
			const i = t < .5 ? 0 : 1, k = (t < .5 ? t : t - .5) * 2;
			const m = c[i].map((v, j) => Math.round(v + (c[i + 1][j] - v) * k));
			return `rgba(${m[0]},${m[1]},${m[2]},${a})`;
		}

		function frame(now) {
			if (!running) return;
			const dt = Math.min(50, now - (last || now)); last = now;
			idle += dt;
			if (idle > 4200 && !reduced) nova(w * (.2 + Math.random() * .6), h * (.25 + Math.random() * .5), .7);
			const base = isDark() ? '255,255,255' : '29,29,31';
			ctx.clearRect(0, 0, w, h);

			for (const wv of waves) wv.r += dt * .55;
			waves = waves.filter((wv) => wv.r < wv.max);

			for (const n of nodes) {
				n.x += n.vx * dt * .06; n.y += n.vy * dt * .06;
				if (n.x < -10) n.x = w + 10; if (n.x > w + 10) n.x = -10;
				if (n.y < -10) n.y = h + 10; if (n.y > h + 10) n.y = -10;
				if (pointer) {
					const dx = pointer.x - n.x, dy = pointer.y - n.y, d = Math.hypot(dx, dy);
					if (d < 180 && d > 1) { n.x += (dx / d) * .18; n.y += (dy / d) * .18; n.e = Math.max(n.e, (1 - d / 180) * .6); }
				}
				for (const wv of waves) {
					const d = Math.hypot(n.x - wv.x, n.y - wv.y);
					if (Math.abs(d - wv.r) < 18) n.e = Math.max(n.e, wv.power * (1 - wv.r / wv.max));
				}
				n.e *= .965;
			}

			ctx.lineWidth = 1;
			for (let i = 0; i < nodes.length; i++) {
				const a = nodes[i];
				for (let j = i + 1; j < nodes.length; j++) {
					const b = nodes[j];
					const dx = a.x - b.x, dy = a.y - b.y;
					if (Math.abs(dx) > LINK || Math.abs(dy) > LINK) continue;
					const d = Math.hypot(dx, dy);
					if (d > LINK) continue;
					const k = 1 - d / LINK, glow = Math.max(a.e, b.e);
					ctx.strokeStyle = glow > .05 ? color((a.x / w + glow * .3) % 1, k * (.12 + glow * .7)) : `rgba(${base},${k * .09})`;
					ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
				}
			}
			if (pointer) {
				for (const n of nodes) {
					const d = Math.hypot(pointer.x - n.x, pointer.y - n.y);
					if (d < 150) { ctx.strokeStyle = color(n.x / w, (1 - d / 150) * .45); ctx.beginPath(); ctx.moveTo(pointer.x, pointer.y); ctx.lineTo(n.x, n.y); ctx.stroke(); }
				}
			}
			for (const n of nodes) {
				ctx.fillStyle = n.e > .05 ? color(n.x / w, .35 + n.e * .65) : `rgba(${base},.28)`;
				ctx.beginPath(); ctx.arc(n.x, n.y, n.r + n.e * 2.6, 0, 6.283); ctx.fill();
				if (n.e > .3) { ctx.fillStyle = color(n.x / w, n.e * .12); ctx.beginPath(); ctx.arc(n.x, n.y, n.r + n.e * 14, 0, 6.283); ctx.fill(); }
			}
			for (const wv of waves) {
				const k = 1 - wv.r / wv.max;
				ctx.strokeStyle = color(wv.x / w, k * .35 * wv.power); ctx.lineWidth = 1.5;
				ctx.beginPath(); ctx.arc(wv.x, wv.y, wv.r, 0, 6.283); ctx.stroke();
			}
			requestAnimationFrame(frame);
		}

		function start() { if (!running && visible && !document.hidden) { running = true; last = 0; requestAnimationFrame(frame); } }
		function stop() { running = false; }

		size();
		if (reduced) { running = true; frame(performance.now()); running = false; }
		else start();
		let rz;
		addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { size(); if (reduced) { running = true; frame(performance.now()); running = false; } }, 150); });
		document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
		new IntersectionObserver(([en]) => { visible = en.isIntersecting; visible ? start() : stop(); }).observe(cv);

		const at = (ev) => { const r = cv.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; };
		const hero = cv.parentElement;
		hero.addEventListener('pointermove', (ev) => { if (ev.pointerType === 'mouse') pointer = at(ev); });
		hero.addEventListener('pointerleave', () => { pointer = null; });
		hero.addEventListener('pointerdown', (ev) => { if (ev.target.closest('a,button')) return; const p = at(ev); nova(p.x, p.y, 1); });
		window.bnNova = (x, y) => nova(x ?? w / 2, y ?? h / 2, 1.4);
	}

	// ------------------------------------------------------------ type "nova"
	let typed = '';
	addEventListener('keydown', (ev) => {
		if (ev.target.closest && ev.target.closest('input,textarea')) return;
		typed = (typed + ev.key.toLowerCase()).slice(-4);
		if (typed === 'nova') {
			const s = document.createElement('div');
			s.className = 'supernova';
			s.style.setProperty('--x', '50%'); s.style.setProperty('--y', '40%');
			document.body.append(s);
			setTimeout(() => s.remove(), 1500);
			if (window.bnNova) for (let i = 0; i < 3; i++) setTimeout(() => window.bnNova(), i * 260);
		}
	});
})();
