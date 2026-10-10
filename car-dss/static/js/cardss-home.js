(() => {
  const R = Math.random;
  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- still rain: one tile, repeated down the page ----------
  (function paintRain() {
    const T = 480, c = document.createElement('canvas');
    c.width = T * DPR; c.height = T * DPR;
    const x = c.getContext('2d'); x.scale(DPR, DPR); x.lineCap = 'round';
    for (let i = 0; i < 75; i++) {
      const px = R() * T, py = R() * T, len = 16 + R() * 42, a = 0.05 + R() * 0.14;
      x.strokeStyle = `rgba(221,235,243,${a})`; x.lineWidth = 0.8 + R() * 0.8;
      for (const [ox, oy] of [[0, 0], [T, 0], [0, T], [T, T], [-T, 0], [0, -T]]) { // wrap edges so the tile is seamless
        x.beginPath(); x.moveTo(px + ox, py + oy); x.lineTo(px + ox - len * 0.28, py + oy + len); x.stroke();
      }
    }
    const layer = document.getElementById('rainLayer');
    layer.style.backgroundImage = `url(${c.toDataURL()})`;
    layer.style.backgroundSize = `${T}px ${T}px`;
  })();


  // (ส่วน "คุณเป็นคนบางขุนเทียนสายไหน?" + คำถาม 3 ข้อ ถูกตัดออก 4 ต.ค. 2569 ตามคำสั่งผู้ใช้)

  // ---------- floodwater in the hero: spring-column surface ----------
  const hero = document.getElementById('hero');
  const cv = document.getElementById('water');
  const g = cv.getContext('2d');
  const DEPTH = 112;         // resting water depth above the hero's bottom edge, px
  const K = 0.02, DAMP = 0.012, SPREAD = 0.25;
  const DRAFT = 0.3;         // share of a km stone's height that sits under water when floating
  let W = 0, H = 0, N = 0, dx = 6, h = [], v = [], drops = [], lights = [], stones = [];
  let level = 0, t0 = performance.now(), time = 0;
  const stoneEls = [...hero.querySelectorAll('.stone')];

  function measure() {
    for (const el of stoneEls) el.style.transform = '';
    W = hero.clientWidth; H = cv.clientHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    g.setTransform(DPR, 0, 0, DPR, 0, 0);
    N = Math.max(40, Math.round(W / 6)); dx = W / (N - 1);
    h = new Float32Array(N); v = new Float32Array(N);
    const hb = hero.getBoundingClientRect(), cb = cv.getBoundingClientRect();
    const rel = (sel) => { const el = hero.querySelector(sel); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left - hb.left + r.width / 2, w: r.width }; };
    lights = [
      [rel('.sign'), '30,158,94', 0.55],
      [rel('.btn-primary'), '244,124,32', 0.55],
      [rel('.btn-ghost'), '238,243,245', 0.18],
    ].filter(l => l[0]);
    const old = stones;
    stones = stoneEls.map((el, i) => {
      const r = el.getBoundingClientRect();
      return { el, x: r.left - cb.left + r.width / 2, w: r.width, hgt: r.height, ground: r.bottom - cb.top,
               lift: old[i] ? old[i].lift : 0, vy: 0, ang: 0, sway: R() * 6.28 };
    });
  }
  const col = (x) => Math.max(0, Math.min(N - 1, Math.round(x / dx)));
  const swell = (x) => 6.5 * Math.sin(x * 0.0065 + time * 1.5) + 3 * Math.sin(x * 0.019 - time * 2.1);
  const surfaceY = (x) => H - level + h[col(x)] + swell(x);
  function poke(x, force, spread = 2) {
    const i = col(x);
    for (let j = -spread; j <= spread; j++) { const k = i + j; if (k >= 0 && k < N) v[k] += force * (1 - Math.abs(j) / (spread + 1)); }
  }

  function physics() {
    for (let i = 0; i < N; i++) { v[i] += -K * h[i] - DAMP * v[i]; h[i] = Math.max(-40, Math.min(40, h[i] + v[i])); }
    const L = new Float32Array(N), Rr = new Float32Array(N);
    for (let pass = 0; pass < 4; pass++) {
      for (let i = 0; i < N; i++) {
        if (i > 0) { L[i] = SPREAD * (h[i] - h[i - 1]); v[i - 1] += L[i]; }
        if (i < N - 1) { Rr[i] = SPREAD * (h[i] - h[i + 1]); v[i + 1] += Rr[i]; }
      }
      for (let i = 0; i < N; i++) { if (i > 0) h[i - 1] += L[i]; if (i < N - 1) h[i + 1] += Rr[i]; }
    }
    // floating km stones: buoyancy spring toward the waterline, resting on the ground when the water is too low
    for (const s of stones) {
      const yL = surfaceY(s.x - s.w * 0.4), yR = surfaceY(s.x + s.w * 0.4), yC = surfaceY(s.x);
      const target = Math.min(0, (yC + s.hgt * DRAFT) - s.ground);   // negative = lifted up
      const acc = (target - s.lift) * 0.035 - s.vy * 0.08;
      s.vy += acc; s.lift += s.vy;
      if (s.lift > 0) { s.lift = 0; s.vy = 0; }
      if (s.lift < 0) s.lift = Math.max(s.lift, -90);
      if (Math.abs(s.vy) > 0.2) poke(s.x, -s.vy * 0.12, 3);          // bobbing sends small waves out
      const want = target < 0 ? Math.atan2(yR - yL, s.w * 0.8) * 0.8 : 0;
      s.ang += (want - s.ang) * 0.08;
    }
    for (const d of drops) {
      d.vy += 0.28; d.x += d.vx; d.y += d.vy;
      if (d.vy > 0 && d.y > surfaceY(d.x)) { poke(d.x, 1.4 + d.r * 0.5, 1); d.dead = true; }
    }
    drops = drops.filter(d => !d.dead && d.x > -10 && d.x < W + 10);
  }

  function placeStones() {
    for (const s of stones) {
      s.sway += 0.02;
      const on = !reduce && s.lift < -1;   // ลดภาพเคลื่อนไหว: หินลอยนิ่ง ไม่โยก
      const sx = on ? Math.sin(s.sway) * 2.5 : 0;
      const by = on ? Math.sin(s.sway * 1.5) * 3 : 0;   // gentle bob so the floating stays visible after the water settles
      s.el.style.transform = `translate(${sx.toFixed(2)}px, ${(s.lift + by).toFixed(2)}px) rotate(${((s.ang + (on ? Math.sin(s.sway * 1.3) * 0.025 : 0)) * 57.3).toFixed(2)}deg)`;
    }
  }

  function draw() {
    g.clearRect(0, 0, W, H);
    if (level < 1) return;
    const top = H - level;
    g.beginPath(); g.moveTo(0, H);
    for (let i = 0; i < N; i++) { const x = i * dx; g.lineTo(x, top + h[i] + swell(x)); }
    g.lineTo(W, H); g.closePath();
    const grd = g.createLinearGradient(0, top - 8, 0, H);
    grd.addColorStop(0, 'rgba(100,150,180,0.30)');
    grd.addColorStop(0.45, 'rgba(34,76,100,0.66)');
    grd.addColorStop(1, 'rgba(12,34,48,0.88)');
    g.fillStyle = grd; g.fill();
    g.save(); g.clip();
    g.beginPath();
    for (let i = 0; i < N; i++) { const x = i * dx; g.lineTo(x, top + h[i] + swell(x) + 7); }
    g.strokeStyle = 'rgba(255,255,255,0.08)'; g.lineWidth = 8; g.stroke();
    g.restore();
    g.beginPath();
    for (let i = 0; i < N; i++) { const x = i * dx; const y = top + h[i] + swell(x); i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.strokeStyle = 'rgba(235,245,250,0.6)'; g.lineWidth = 1.5; g.stroke();
    g.fillStyle = 'rgba(225,240,248,0.85)';
    for (const d of drops) { g.beginPath(); g.arc(d.x, d.y, d.r, 0, 6.283); g.fill(); }
  }

  // pointer: moving through the water pushes it, a click or tap splashes
  let last = null;
  hero.addEventListener('pointermove', (e) => {
    if (reduce) return;
    const r = cv.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
    if (last && level > 5) {
      const sy = surfaceY(x);
      if (y > sy - 30) {
        const sp = Math.max(-22, Math.min(22, (x - last.x) * 0.35 + (y - last.y) * 0.8));
        poke(x, Math.abs(sp) * 0.7 * (y < last.y ? -1 : 1), 3);
      }
    }
    last = { x, y };
  });
  hero.addEventListener('pointerleave', () => { last = null; });
  hero.addEventListener('pointerdown', (e) => {
    if (reduce) return;
    const r = cv.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
    if (y < surfaceY(x) - 80) return;
    poke(x, 12, 4);
    for (let i = 0; i < 14; i++) drops.push({ x, y: surfaceY(x) - 2, vx: (R() - 0.5) * 6, vy: -3 - R() * 6, r: 1 + R() * 2.4 });
  });

  let raf = 0, visible = true, nextDrip = 0, nextSwell = 0, acc = 0, prev = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - prev) / 1000); prev = now; time += dt;
    const p = Math.min(1, (now - t0) / 5000);
    level = DEPTH * (1 - Math.pow(1 - p, 3));
    if (now > nextDrip) { poke(R() * W, 2 + R() * 2.5, 1); nextDrip = now + 250 + R() * 700; }
    if (now > nextSwell) { poke(R() < 0.5 ? 0 : W, 7, 6); nextSwell = now + 3500 + R() * 2500; }
    acc += dt;
    while (acc > 1 / 60) { physics(); acc -= 1 / 60; }
    draw(); placeStones();
    raf = visible ? requestAnimationFrame(frame) : 0;
  }

  // ผู้ใช้ตั้งเครื่องให้ลดภาพเคลื่อนไหว (กฎออกแบบข้อ 6): น้ำขึ้นเต็มทันที คำนวณให้นิ่งแล้ววาดภาพเดียว ไม่วนลูป
  function still() { level = DEPTH; for (let i = 0; i < 400; i++) physics(); draw(); placeStones(); }

  let rt;
  const mb = document.getElementById('menuBtn'), menu = document.getElementById('menu');
  const setMenu = (open) => { menu.classList.toggle('open', open); mb.setAttribute('aria-expanded', open); };
  mb.addEventListener('click', () => setMenu(!menu.classList.contains('open')));
  menu.addEventListener('click', (e) => { if (e.target.closest('a')) setMenu(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setMenu(false); });
  window.addEventListener('resize', () => { if (window.innerWidth > 1180) setMenu(false); });  // ตรงกับจุดพับเมนูใน cardss.css
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { measure(); if (reduce) still(); }, 150); });
  measure();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); if (reduce) still(); });
  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible && !raf && !reduce) { prev = performance.now(); raf = requestAnimationFrame(frame); }
  }).observe(hero);
  if (reduce) still(); else raf = requestAnimationFrame(frame);
})();
