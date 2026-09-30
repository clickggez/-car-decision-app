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


  // ---------- route map + quick quiz ----------
  (function route() {
    const ICON = {
      city: '<svg width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="#EEF3F5" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 44h40"/><rect x="8" y="16" width="12" height="28"/><rect x="24" y="6" width="14" height="38"/><path d="M12 22h4M12 28h4M12 34h4M28 12h6M28 18h6M28 24h6M28 30h6"/></svg>',
      traffic: '<svg width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="#EEF3F5" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="18" width="18" height="12" rx="3"/><rect x="26" y="18" width="18" height="12" rx="3"/><circle cx="9" cy="32" r="2.5"/><circle cx="17" cy="32" r="2.5"/><circle cx="31" cy="32" r="2.5"/><circle cx="39" cy="32" r="2.5"/><path d="M8 12h6M22 12h4M34 12h6"/></svg>',
      sea: '<svg width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="#EEF3F5" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 24 L24 10 L40 24"/><path d="M12 22v12h24V22"/><path d="M4 40c4-3 8-3 12 0s8 3 12 0 8-3 12 0 4 2 4 2"/></svg>',
      south: '<svg width="52" height="52" viewBox="0 0 48 48" fill="none" stroke="#EEF3F5" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 44 L22 4"/><path d="M30 44 L26 4"/><path d="M24 40v-4M24 28v-4M24 16v-4"/><circle cx="38" cy="10" r="5"/></svg>'
    };
    const P = [
      { tag: 'สาย 01', icon: 'city', title: 'สายเข้าเมืองทุกวัน',
        text: 'ขับจากพระราม 2 เข้าสาทร สีลม หรือกรุงเทพชั้นในทุกวัน เจอรถติดทั้งขาไปขากลับ บางคนอยู่คอนโดที่ติดตั้งที่ชาร์จเองไม่ได้',
        chips: ['เวลาบนถนน', 'ค่าทางด่วน / ค่าจอด', 'ค่าน้ำมันต่อเดือน'], def: { dist: 1, trip: 0, home: 2 } },
      { tag: 'สาย 02', icon: 'traffic', title: 'สายใช้รถในย่าน',
        text: 'อยู่แถวท่าข้าม แสมดำ ทำงานโรงงานหรือร้านค้าใกล้บ้าน ขับระยะสั้น รับส่งลูก ไปตลาด แทบไม่ได้ขึ้นทางด่วน',
        chips: ['ระยะทางต่อวัน', 'ราคารถ', 'ค่าซ่อมบำรุง'], def: { dist: 0, trip: 1, home: 1 } },
      { tag: 'สาย 03', icon: 'sea', title: 'สายบ้านใกล้ทะเล',
        text: 'บ้านแถวบางขุนเทียนชายทะเล หรือซอยที่น้ำขังหน้าฝน ใช้รถในย่านเป็นหลัก ต้องคิดเรื่องที่จอดและงบประมาณ',
        chips: ['ที่จอดรถ', 'งบประมาณ', 'ระยะทางต่อวัน'], def: { dist: 0, trip: 0, home: 0 } },
      { tag: 'สาย 04', icon: 'south', title: 'สายกลับบ้านต่างจังหวัด',
        text: 'อยู่ฝั่งมหาชัย พระราม 2 คือประตูลงใต้ ถ้าขับไปเพชรบุรี หัวหิน หรือไกลกว่านั้นบ่อย ๆ ต้องคิดเรื่องระยะทางต่อครั้ง',
        chips: ['ทริปไกลต่อเดือน', 'ปั๊ม / ที่ชาร์จระหว่างทาง'], def: { dist: 2, trip: 2, home: 2 } }
    ];
    const ans = { dist: 1, trip: 0, home: 1 };
    const stops = [...document.querySelectorAll('.stop')];
    const $ = (id) => document.getElementById(id);

    // simple, explainable scoring: each answer adds points to a lane
    const W = {
      dist: [{ ev: 2, hev: 0, ice: 3 }, { ev: 2, hev: 2, ice: 1 }, { ev: 1, hev: 3, ice: 0 }],
      trip: [{ ev: 2, hev: 1, ice: 1 }, { ev: 1, hev: 2, ice: 1 }, { ev: -1, hev: 2, ice: 1 }],
      home: [{ ev: 3, hev: 0, ice: 0 }, { ev: 0, hev: 1, ice: 1 }, { ev: -3, hev: 1, ice: 2 }]
    };
    const WHY = {
      ev: 'ชาร์จที่บ้านได้และส่วนใหญ่ขับในเมือง รถไฟฟ้ามักประหยัดที่สุด โดยเฉพาะตอนรถติดที่เครื่องยนต์ต้องเดินเบาเปล่า ๆ',
      hev: 'ขับทั้งรถติดและทางไกล ไฮบริดช่วยประหยัดตอนหยุด ๆ ขยับ ๆ และไม่ต้องกังวลเรื่องจุดชาร์จระหว่างทาง',
      ice: 'ขับไม่มากหรือต้องการรถราคาเริ่มต้นต่ำ รถน้ำมันยังคุ้มได้ ซ่อมง่าย เติมได้ทุกปั๊ม'
    };
    function pick() {
      const sc = { ev: 0, hev: 0, ice: 0 };
      for (const k in ans) { const w = W[k][ans[k]]; for (const l in sc) sc[l] += w[l]; }
      return Object.keys(sc).sort((a, b) => sc[b] - sc[a] || ['hev', 'ev', 'ice'].indexOf(a) - ['hev', 'ev', 'ice'].indexOf(b))[0];
    }
    function render() {
      document.querySelectorAll('.seg').forEach((seg) => seg.querySelectorAll('button').forEach((b) =>
        b.setAttribute('aria-pressed', String(+b.dataset.v === ans[seg.dataset.q]))));
      const l = pick();
      document.querySelectorAll('.lanes-mini span').forEach((s) => s.classList.toggle('on', s.dataset.l === l));
      $('qWhy').textContent = WHY[l];
      document.dispatchEvent(new CustomEvent('cardss:hint', { detail: l }));
    }
    function setPersona(i) {
      const p = P[i];
      stops.forEach((b, j) => { b.setAttribute('aria-checked', String(i === j)); b.tabIndex = i === j ? 0 : -1; });
      $('pTag').textContent = p.tag; $('pIcon').innerHTML = ICON[p.icon];
      $('pTitle').textContent = p.title; $('pText').textContent = p.text;
      $('pChips').innerHTML = p.chips.map((c) => `<span>${c}</span>`).join('');
      Object.assign(ans, p.def); render();
    }
    stops.forEach((b, i) => {
      b.addEventListener('click', () => setPersona(i));
      b.addEventListener('keydown', (e) => {
        const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (d) { e.preventDefault(); const n = (i + d + stops.length) % stops.length; setPersona(n); stops[n].focus(); }
      });
    });
    document.querySelectorAll('.seg').forEach((seg) => seg.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return; ans[seg.dataset.q] = +b.dataset.v; render();
    }));
    setPersona(0);
  })();

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
  window.addEventListener('resize', () => { if (window.innerWidth > 980) setMenu(false); });
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { measure(); if (reduce) still(); }, 150); });
  measure();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); if (reduce) still(); });
  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible && !raf && !reduce) { prev = performance.now(); raf = requestAnimationFrame(frame); }
  }).observe(hero);
  if (reduce) still(); else raf = requestAnimationFrame(frame);
})();
