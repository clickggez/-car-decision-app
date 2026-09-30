(() => {
  const { Engine, Bodies, Body, Composite, Constraint, Query, Events, Sleeping } = Matter;
  // [brand, model, body style]
  const DATA = {
    ev:  { name: 'EV · รถไฟฟ้า', color: ['#3E8FE0', '#2F74C0', '#5AA9F0'], models: [
      ['Tesla','Model 3','sedan'],['Tesla','Model Y','suv'],['BYD','Atto 3','suv'],['BYD','Dolphin','hatch'],
      ['BYD','Seal','sedan'],['MG','MG4 Electric','hatch'],['GWM','ORA 05','suv'],['Volvo','EX30','suv'] ] },
    hev: { name: 'ไฮบริด · HEV', color: ['#1FA394', '#178678', '#2FBFAE'], models: [
      ['Toyota','Corolla Cross HEV','suv'],['Toyota','Yaris Ativ HEV','sedan'],['Toyota','Yaris Cross HEV','suv'],['Toyota','Camry HEV','sedan'],
      ['Honda','City e:HEV','sedan'],['Honda','Civic e:HEV','sedan'],['Honda','HR-V e:HEV','suv'],['Honda','Accord e:HEV','sedan'],
      ['Honda','CR-V e:HEV','suv'],['Nissan','Kicks e-Power','suv'],['Mitsubishi','Xpander Cross HEV','mpv'],['Hyundai','Stargazer X HEV','mpv'] ] },
    ice: { name: 'สันดาป · รถน้ำมัน', color: ['#C9844A', '#A86A36', '#DB9A62'], models: [
      ['Mazda','Mazda 2','hatch'],['Toyota','Yaris Ativ','sedan'],['Honda','City Turbo','sedan'],['Nissan','Almera Turbo','sedan'],['Mitsubishi','Attrage','sedan'] ] }
  };
  // Flask can pass its own model list: window.CARDSS_MODELS = { ev: [[brand, model, style], ...], hev: [...], ice: [...] }
  if (window.CARDSS_MODELS) for (const t in DATA) if (Array.isArray(window.CARDSS_MODELS[t])) DATA[t].models = window.CARDSS_MODELS[t];
  if (window.CARDSS_MODELS) document.querySelectorAll('.md-type').forEach((b) => { const sm = b.querySelector('small'); if (sm && DATA[b.dataset.t]) sm.textContent = sm.textContent.replace(/^\d+/, DATA[b.dataset.t].models.length); });
  // body-style proportions, all relative to car length L
  const STYLE = {
    sedan: { h: 0.29, roofF: 0.30, roofR: 0.20, beltF: 0.16, beltR: 0.12, hood: 0.30, trunk: 0.20 },
    hatch: { h: 0.33, roofF: 0.28, roofR: 0.10, beltF: 0.18, beltR: 0.18, hood: 0.28, trunk: 0.06 },
    suv:   { h: 0.36, roofF: 0.30, roofR: 0.08, beltF: 0.20, beltR: 0.20, hood: 0.26, trunk: 0.05 },
    mpv:   { h: 0.39, roofF: 0.22, roofR: 0.05, beltF: 0.20, beltR: 0.21, hood: 0.20, trunk: 0.04 }
  };

  const stage = document.getElementById('mdStage'), cv = document.getElementById('mdCv'), g = cv.getContext('2d');
  const tip = document.getElementById('mdTip'), tipName = document.getElementById('mdTipName'), tipSub = document.getElementById('mdTipSub');
  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  let dropped = false;
  let W = 0, H = 0, GROUND = 0, L = 160, engine, walls = [], cars = [], current = 'hev', dropTimer = 0;
  // flood water over the road: same spring-column surface as the hero
  let WD = 48, WN = 0, wdx = 6, wh = new Float32Array(0), wv = new Float32Array(0), wdrops = [], wtime = 0, nextDrip = 0;
  const WK = 0.02, WDAMP = 0.014, WSPREAD = 0.25;
  const wcol = (x) => Math.max(0, Math.min(WN - 1, Math.round(x / wdx)));
  const wswell = (x) => 3 * Math.sin(x * 0.007 + wtime * 1.3) + 1.6 * Math.sin(x * 0.021 - wtime * 1.9);
  const surf = (x) => GROUND - WD + wh[wcol(x)] + wswell(x);
  function wpoke(x, f, spread = 3) {
    const i = wcol(x);
    for (let j = -spread; j <= spread; j++) { const k = i + j; if (k >= 0 && k < WN) wv[k] += f * (1 - Math.abs(j) / (spread + 1)); }
  }
  function splash(x, power) {
    wpoke(x, Math.min(14, power), 5);
    const n = Math.min(18, 6 + power * 1.5);
    for (let i = 0; i < n; i++) wdrops.push({ x: x + (Math.random() - 0.5) * L * 0.6, y: surf(x) - 2, vx: (Math.random() - 0.5) * 5, vy: -2 - Math.random() * power * 0.7, r: 1 + Math.random() * 2.2 });
  }
  function waterStep() {
    wtime += 1 / 60;
    for (let i = 0; i < WN; i++) { wv[i] += -WK * wh[i] - WDAMP * wv[i]; wh[i] = Math.max(-36, Math.min(36, wh[i] + wv[i])); }
    const Lf = new Float32Array(WN), Rf = new Float32Array(WN);
    for (let pass = 0; pass < 4; pass++) {
      for (let i = 0; i < WN; i++) {
        if (i > 0) { Lf[i] = WSPREAD * (wh[i] - wh[i - 1]); wv[i - 1] += Lf[i]; }
        if (i < WN - 1) { Rf[i] = WSPREAD * (wh[i] - wh[i + 1]); wv[i + 1] += Rf[i]; }
      }
      for (let i = 0; i < WN; i++) { if (i > 0) wh[i - 1] += Lf[i]; if (i < WN - 1) wh[i + 1] += Rf[i]; }
    }
    for (const d of wdrops) { d.vy += 0.3; d.x += d.vx; d.y += d.vy; if (d.vy > 0 && d.y > surf(d.x)) { wpoke(d.x, 0.8 + d.r * 0.4, 1); d.dead = true; } }
    wdrops = wdrops.filter((d) => !d.dead && d.x > -10 && d.x < W + 10);
    const now = performance.now();
    if (now > nextDrip) { wpoke(Math.random() * W, 1.5 + Math.random() * 2, 1); nextDrip = now + 300 + Math.random() * 700; }
  }
  // cars sink slowly (buoyancy below their weight), water slows them down, entering the water splashes
  function buoy() {
    const gy = engine.gravity.y * engine.gravity.scale;
    for (const b of cars) {
      const top = b.bounds.min.y, bot = b.bounds.max.y, sy = surf(b.position.x);
      const sub = Math.max(0, Math.min(1, (bot - sy) / Math.max(1, bot - top)));
      const was = b.car.sub || 0; b.car.sub = sub;
      if (!was && sub > 0 && b.velocity.y > 2.5) splash(b.position.x, b.velocity.y * 1.1);
      if (!sub || b.isSleeping) continue;
      Body.applyForce(b, b.position, { x: 0, y: -b.mass * gy * 0.78 * sub });
      Body.setVelocity(b, { x: b.velocity.x * (1 - 0.05 * sub), y: b.velocity.y * (1 - 0.07 * sub) });
      Body.setAngularVelocity(b, b.angularVelocity * (1 - 0.06 * sub));
      const sp = Math.abs(b.velocity.x);
      if (sp > 1.2) wpoke(b.position.x + Math.sign(b.velocity.x) * L * 0.45, Math.min(4, sp * 0.35) * -1, 2);
    }
  }
  let rainTile = null;

  // ---------- car sprite (side view, facing right) ----------
  // Photos (optional): side view, facing right, transparent PNG. Key = "Brand Model" exactly as in DATA.
  // key "Brand Model" -> cut-out photo (facing right) + its outline, normalised to the photo width
  const PHOTOS = {"Honda HR-V e:HEV":{"src":"cars/honda-hr-v-ehev.webp","ar":0.3828,"hull":[[0.002,0.241],[0.012,0.119],[0.138,0.027],[0.223,0.002],[0.475,0.008],[0.591,0.025],[0.952,0.144],[0.991,0.188],[0.997,0.289],[0.845,0.37],[0.825,0.373],[0.159,0.378],[0.131,0.364],[0.02,0.277]]},"BYD Atto 3":{"src":"cars/byd-atto-3.webp","ar":0.3891,"hull":[[0.002,0.247],[0.017,0.109],[0.091,0.027],[0.186,0.002],[0.442,0.005],[0.569,0.027],[0.939,0.161],[0.975,0.178],[0.997,0.217],[0.981,0.317],[0.842,0.386],[0.166,0.383],[0.128,0.369],[0.027,0.298]]},"BYD Dolphin":{"src":"cars/byd-dolphin.webp","ar":0.3803,"hull":[[0.785,0.377],[0.137,0.371],[0.002,0.294],[0.004,0.204],[0.018,0.127],[0.086,0.032],[0.208,0.002],[0.447,0.011],[0.574,0.028],[0.896,0.143],[0.933,0.16],[0.996,0.231],[0.989,0.305],[0.842,0.373]]},"BYD Seal":{"src":"cars/byd-seal.webp","ar":0.3141,"hull":[[0.002,0.184],[0.017,0.083],[0.223,0.019],[0.37,0.002],[0.492,0.005],[0.552,0.016],[0.895,0.127],[0.966,0.158],[0.997,0.186],[0.994,0.266],[0.859,0.309],[0.808,0.311],[0.172,0.308],[0.011,0.238]]},"GWM ORA 05":{"src":"cars/gwm-ora-05.webp","ar":0.3937,"hull":[[0.916,0.15],[0.997,0.214],[0.997,0.319],[0.855,0.388],[0.827,0.392],[0.145,0.392],[0.117,0.383],[0.008,0.302],[0.0,0.209],[0.03,0.13],[0.105,0.031],[0.227,0.008],[0.328,0.0],[0.495,0.003]]},"Honda Accord e:HEV":{"src":"cars/honda-accord-ehev.webp","ar":0.302,"hull":[[0.822,0.297],[0.2,0.297],[0.012,0.23],[0.003,0.225],[0.003,0.176],[0.022,0.087],[0.265,0.005],[0.46,0.002],[0.51,0.005],[0.569,0.017],[0.933,0.119],[0.985,0.143],[0.997,0.203],[0.995,0.242]]},"Honda CR-V e:HEV":{"src":"cars/honda-cr-v-ehev.webp","ar":0.3672,"hull":[[0.811,0.364],[0.189,0.364],[0.17,0.359],[0.017,0.284],[0.002,0.241],[0.016,0.109],[0.07,0.022],[0.153,0.002],[0.442,0.002],[0.536,0.012],[0.952,0.139],[0.994,0.167],[0.998,0.258],[0.984,0.302]]},"Honda City Turbo":{"src":"cars/honda-city-turbo.webp","ar":0.3297,"hull":[[0.002,0.227],[0.017,0.086],[0.25,0.003],[0.395,0.0],[0.514,0.005],[0.577,0.017],[0.927,0.128],[0.977,0.161],[0.989,0.205],[0.994,0.262],[0.814,0.327],[0.208,0.328],[0.183,0.323],[0.017,0.255]]},"Honda City e:HEV":{"src":"cars/honda-city-ehev.webp","ar":0.3375,"hull":[[0.0,0.214],[0.02,0.081],[0.259,0.0],[0.481,0.002],[0.577,0.016],[0.933,0.133],[0.986,0.166],[0.998,0.197],[0.995,0.262],[0.828,0.333],[0.791,0.336],[0.198,0.333],[0.173,0.327],[0.005,0.25]]},"Honda Civic e:HEV":{"src":"cars/honda-civic-ehev.webp","ar":0.3153,"hull":[[0.002,0.191],[0.019,0.073],[0.242,0.008],[0.393,0.002],[0.518,0.005],[0.578,0.016],[0.939,0.124],[0.986,0.151],[0.995,0.193],[0.995,0.253],[0.83,0.309],[0.186,0.312],[0.018,0.245],[0.006,0.237]]},"Hyundai Stargazer X HEV":{"src":"cars/hyundai-stargazer-x-hev.webp","ar":0.4095,"hull":[[0.783,0.406],[0.141,0.392],[0.014,0.304],[0.004,0.282],[0.006,0.135],[0.06,0.026],[0.316,0.002],[0.479,0.008],[0.604,0.038],[0.946,0.165],[0.984,0.209],[0.994,0.28],[0.972,0.334],[0.833,0.4]]},"MG MG4 Electric":{"src":"cars/mg-mg4-electric.webp","ar":0.3672,"hull":[[0.834,0.362],[0.131,0.362],[0.038,0.294],[0.002,0.219],[0.009,0.094],[0.086,0.027],[0.217,0.009],[0.355,0.002],[0.519,0.008],[0.556,0.017],[0.889,0.134],[0.931,0.152],[0.995,0.212],[0.997,0.302]]},"Mazda Mazda 2":{"src":"cars/mazda-mazda-2.webp","ar":0.3547,"hull":[[0.847,0.352],[0.178,0.352],[0.028,0.275],[0.005,0.255],[0.002,0.188],[0.022,0.086],[0.25,0.019],[0.308,0.006],[0.423,0.0],[0.517,0.008],[0.578,0.023],[0.914,0.141],[0.995,0.184],[0.991,0.298]]},"Mitsubishi Attrage":{"src":"cars/mitsubishi-attrage.webp","ar":0.3779,"hull":[[0.002,0.207],[0.053,0.1],[0.265,0.002],[0.513,0.014],[0.612,0.032],[0.924,0.149],[0.975,0.183],[0.996,0.221],[0.993,0.308],[0.866,0.369],[0.835,0.374],[0.192,0.371],[0.181,0.369],[0.002,0.274]]},"Mitsubishi Xpander Cross HEV":{"src":"cars/mitsubishi-xpander-cross-hev.webp","ar":0.3984,"hull":[[0.002,0.244],[0.022,0.125],[0.091,0.02],[0.167,0.006],[0.381,0.002],[0.484,0.006],[0.531,0.016],[0.939,0.159],[0.984,0.2],[0.998,0.266],[0.973,0.32],[0.83,0.394],[0.172,0.388],[0.017,0.292]]},"Nissan Almera Turbo":{"src":"cars/nissan-almera-turbo.webp","ar":0.3656,"hull":[[0.792,0.362],[0.159,0.361],[0.0,0.286],[0.009,0.18],[0.103,0.119],[0.408,0.017],[0.478,0.003],[0.577,0.0],[0.688,0.009],[0.944,0.08],[0.973,0.102],[0.997,0.209],[0.997,0.253],[0.973,0.284]]},"Nissan Kicks e-Power":{"src":"cars/nissan-kicks-e-power.webp","ar":0.381,"hull":[[0.222,0.006],[0.482,0.002],[0.547,0.014],[0.936,0.145],[0.969,0.159],[0.994,0.217],[0.99,0.311],[0.83,0.379],[0.174,0.379],[0.137,0.369],[0.023,0.292],[0.002,0.263],[0.033,0.124],[0.147,0.027]]},"Tesla Model 3":{"src":"cars/tesla-model-3.webp","ar":0.3156,"hull":[[0.855,0.312],[0.181,0.312],[0.161,0.311],[0.03,0.267],[0.006,0.253],[0.002,0.183],[0.019,0.083],[0.212,0.022],[0.345,0.002],[0.438,0.002],[0.562,0.022],[0.923,0.141],[0.997,0.183],[0.997,0.259]]},"Tesla Model Y":{"src":"cars/tesla-model-y.webp","ar":0.3547,"hull":[[0.002,0.217],[0.02,0.084],[0.161,0.041],[0.314,0.008],[0.386,0.002],[0.491,0.005],[0.588,0.028],[0.917,0.152],[0.991,0.197],[0.995,0.289],[0.981,0.3],[0.847,0.353],[0.164,0.35],[0.027,0.288]]},"Toyota Camry HEV":{"src":"cars/toyota-camry-hev.webp","ar":0.3109,"hull":[[0.002,0.169],[0.019,0.077],[0.25,0.002],[0.422,0.0],[0.491,0.003],[0.567,0.016],[0.911,0.119],[0.995,0.164],[0.997,0.256],[0.836,0.305],[0.806,0.308],[0.198,0.305],[0.041,0.245],[0.002,0.217]]},"Toyota Corolla Cross HEV":{"src":"cars/toyota-corolla-cross-hev.webp","ar":0.3752,"hull":[[0.166,0.003],[0.349,0.0],[0.523,0.014],[0.929,0.148],[0.984,0.173],[0.997,0.253],[0.983,0.308],[0.813,0.37],[0.163,0.372],[0.011,0.278],[0.002,0.221],[0.016,0.119],[0.033,0.085],[0.096,0.025]]},"Toyota Yaris Ativ HEV":{"src":"cars/toyota-yaris-ativ-hev.webp","ar":0.3409,"hull":[[0.002,0.232],[0.015,0.089],[0.253,0.008],[0.394,0.002],[0.476,0.002],[0.536,0.006],[0.589,0.018],[0.924,0.135],[0.982,0.167],[0.987,0.183],[0.994,0.282],[0.823,0.336],[0.185,0.336],[0.01,0.265]]},"Toyota Yaris Ativ":{"src":"cars/toyota-yaris-ativ.webp","ar":0.3516,"hull":[[0.014,0.106],[0.227,0.0],[0.508,0.014],[0.594,0.028],[0.917,0.141],[0.972,0.166],[0.992,0.195],[0.998,0.289],[0.839,0.345],[0.82,0.347],[0.188,0.347],[0.011,0.275],[0.002,0.262],[0.002,0.191]]},"Toyota Yaris Cross HEV":{"src":"cars/toyota-yaris-cross-hev.webp","ar":0.3903,"hull":[[0.836,0.383],[0.161,0.387],[0.136,0.378],[0.002,0.285],[0.01,0.126],[0.031,0.093],[0.095,0.031],[0.199,0.002],[0.435,0.007],[0.522,0.014],[0.938,0.147],[0.991,0.173],[0.995,0.323],[0.976,0.335]]},"Volvo EX30":{"src":"cars/volvo-ex30.webp","ar":0.3766,"hull":[[0.847,0.373],[0.152,0.373],[0.042,0.311],[0.014,0.283],[0.002,0.209],[0.012,0.108],[0.061,0.041],[0.194,0.014],[0.344,0.002],[0.453,0.002],[0.561,0.02],[0.933,0.15],[0.992,0.188],[0.997,0.311]]}};
  const photo = {}, ready = {};
  for (const k in PHOTOS) ready[k] = new Promise((res) => { const im = new Image(); im.onload = () => { photo[k] = im; res(); }; im.onerror = () => res(); im.src = (window.CARDSS_IMG || 'cars/') + PHOTOS[k].src.replace(/^cars\//, ''); });
  function photoSprite(im, style, L) {
    const s = STYLE[style], r = L * 0.105, pad = 6, h = s.h * L;
    const w = L + pad * 2, hh = h + r + pad * 2, ih = L * im.naturalHeight / im.naturalWidth;
    const c = document.createElement('canvas'); c.width = Math.ceil(w * DPR); c.height = Math.ceil(hh * DPR);
    const x = c.getContext('2d'); x.scale(DPR, DPR);
    x.drawImage(im, pad, hh - pad - ih, L, ih);          // bottom of the photo sits on the tyres' contact line
    return { img: c, w, hh, ox: pad + L / 2, oy: pad + h, r, h, s };
  }
  function sprite(style, color, L, key) {
    if (key && photo[key]) return photoSprite(photo[key], style, L);
    const s = STYLE[style], r = L * 0.105, pad = 6;
    const h = s.h * L;
    const w = L + pad * 2, hh = h + r + pad * 2;
    const c = document.createElement('canvas'); c.width = Math.ceil(w * DPR); c.height = Math.ceil(hh * DPR);
    const x = c.getContext('2d'); x.scale(DPR, DPR); x.translate(pad + L / 2, pad + h); // origin: centre of car at sill line
    const X = (f) => f * L - L / 2;           // 0..1 along length -> local x (0 = rear, 1 = front)
    const sill = 0, shoulder = -s.beltR * L, shoulderF = -s.beltF * L, roof = -h;
    const wx = [X(0.2), X(0.8)];
    // body
    x.beginPath();
    x.moveTo(X(0.01), sill - 0.03 * L);
    x.lineTo(X(0.0), shoulder + 0.02 * L);
    x.quadraticCurveTo(X(0.0), shoulder, X(0.03), shoulder);
    x.lineTo(X(s.trunk), shoulder);
    x.quadraticCurveTo(X(s.trunk + 0.06), roof + 0.01 * L, X(s.trunk + 0.14 + s.roofR), roof);
    x.lineTo(X(1 - s.hood - s.roofF * 0.35), roof);
    x.quadraticCurveTo(X(1 - s.hood - 0.03), roof + 0.02 * L, X(1 - s.hood + 0.02), shoulderF);
    x.lineTo(X(0.97), shoulderF + 0.03 * L);
    x.quadraticCurveTo(X(1.0), shoulderF + 0.04 * L, X(1.0), shoulderF + 0.08 * L);
    x.lineTo(X(0.99), sill - 0.03 * L);
    x.quadraticCurveTo(X(0.99), sill, X(0.95), sill);
    x.lineTo(X(0.05), sill);
    x.quadraticCurveTo(X(0.01), sill, X(0.01), sill - 0.03 * L);
    x.closePath();
    const grd = x.createLinearGradient(0, roof, 0, sill);
    grd.addColorStop(0, color[2]); grd.addColorStop(0.45, color[0]); grd.addColorStop(1, color[1]);
    x.fillStyle = grd; x.fill();
    x.lineWidth = 1.5; x.strokeStyle = 'rgba(0,0,0,.35)'; x.stroke();
    // windows
    const wTop = roof + 0.035 * L, wBot = Math.max(shoulder, shoulderF) - 0.01 * L;
    x.beginPath();
    x.moveTo(X(s.trunk + 0.07), wBot);
    x.quadraticCurveTo(X(s.trunk + 0.1), wTop + 0.01 * L, X(s.trunk + 0.16 + s.roofR), wTop);
    x.lineTo(X(1 - s.hood - s.roofF * 0.38), wTop);
    x.quadraticCurveTo(X(1 - s.hood - 0.05), wTop + 0.02 * L, X(1 - s.hood - 0.01), wBot);
    x.closePath();
    const gl = x.createLinearGradient(0, wTop, 0, wBot);
    gl.addColorStop(0, '#2B3F4C'); gl.addColorStop(1, '#0D161C');
    x.fillStyle = gl; x.fill();
    // pillar + door line
    const mid = X(0.52);
    x.fillStyle = color[1]; x.fillRect(mid - 0.012 * L, wTop, 0.024 * L, wBot - wTop);
    x.strokeStyle = 'rgba(0,0,0,.28)'; x.lineWidth = 1.2;
    x.beginPath(); x.moveTo(mid, wBot); x.lineTo(mid + 0.01 * L, sill - 0.02 * L); x.stroke();
    // shine
    x.strokeStyle = 'rgba(255,255,255,.35)'; x.lineWidth = 2;
    x.beginPath(); x.moveTo(X(0.12), shoulder + 0.03 * L); x.lineTo(X(0.9), shoulderF + 0.03 * L); x.stroke();
    // lights
    x.fillStyle = '#FFE9B8'; x.beginPath(); x.ellipse(X(0.975), shoulderF + 0.05 * L, 0.02 * L, 0.012 * L, 0, 0, 6.283); x.fill();
    x.fillStyle = '#E23B3B'; x.fillRect(X(0.0), shoulder + 0.025 * L, 0.02 * L, 0.03 * L);
    // wheel arches + wheels
    for (const cx of wx) {
      x.fillStyle = '#0B1014'; x.beginPath(); x.arc(cx, sill, r * 1.18, Math.PI, 0); x.fill();
      x.fillStyle = '#16191B'; x.beginPath(); x.arc(cx, sill, r, 0, 6.283); x.fill();
      x.fillStyle = '#9AA6AE'; x.beginPath(); x.arc(cx, sill, r * 0.58, 0, 6.283); x.fill();
      x.strokeStyle = '#5E6A72'; x.lineWidth = 2;
      for (let k = 0; k < 5; k++) { const a = k * 1.2566; x.beginPath(); x.moveTo(cx, sill); x.lineTo(cx + Math.cos(a) * r * 0.55, sill + Math.sin(a) * r * 0.55); x.stroke(); }
      x.fillStyle = '#2A3136'; x.beginPath(); x.arc(cx, sill, r * 0.16, 0, 6.283); x.fill();
    }
    return { img: c, w, hh, ox: pad + L / 2, oy: pad + h, r, h, s };
  }

  // ---------- physics body matching the sprite ----------
  function makeCar(model, type, i) {
    const [brand, name, style] = model;
    const key = `${brand} ${name}`, P = PHOTOS[key], im = photo[key];
    if (P && im) {                       // real photo: physics outline traced from the photo itself
      const ph = L * P.ar;
      const span = Math.min(W, 1240), x0 = (W - span) / 2 + span * (0.12 + Math.random() * 0.76), top = -ph - 40;
      const verts = P.hull.map(([u, v]) => ({ x: x0 - L / 2 + u * L, y: top + v * L }));
      const c = Matter.Vertices.centre(verts);
      const body = Bodies.fromVertices(c.x, c.y, [verts], { friction: 0.6, frictionAir: 0.01, restitution: 0.15, density: 0.0012 });
      body.car = { brand, name, style, type, photo: im, pw: L, ph, off: { x: x0 - L / 2 - body.position.x, y: top - body.position.y } };
      Body.setAngle(body, (Math.random() - 0.5) * 1.2);
      Body.setAngularVelocity(body, (Math.random() - 0.5) * 0.08);
      return body;
    }
    const col = DATA[type].color;
    const sp = sprite(style, col, L, `${brand} ${name}`);
    const s = STYLE[style], h = sp.h, r = sp.r;
    const span = Math.min(W, 1240), x0 = (W - span) / 2 + span * (0.12 + Math.random() * 0.76), y0 = -h - 40 - i * 30;
    const lower = Bodies.rectangle(x0, y0 - s.beltR * L / 2 - 0.01 * L, L * 0.98, Math.max(s.beltR, s.beltF) * L, { chamfer: { radius: 0.04 * L } });
    const cabTopL = x0 + (s.trunk + 0.14 + s.roofR - 0.5) * L, cabTopR = x0 + (0.5 - s.hood - s.roofF * 0.35) * L;
    const cabBotL = x0 + (s.trunk - 0.5) * L, cabBotR = x0 + (0.5 - s.hood + 0.02) * L;
    const yb = y0 - Math.max(s.beltR, s.beltF) * L + 1, yt = y0 - h;
    const cabin = Bodies.fromVertices((cabTopL + cabTopR + cabBotL + cabBotR) / 4, (yb + yt) / 2,
      [[{ x: cabBotL, y: yb }, { x: cabTopL, y: yt }, { x: cabTopR, y: yt }, { x: cabBotR, y: yb }]]);
    const w1 = Bodies.circle(x0 - 0.3 * L, y0, r), w2 = Bodies.circle(x0 + 0.3 * L, y0, r);
    const body = Body.create({ parts: [lower, cabin, w1, w2], friction: 0.6, frictionAir: 0.01, restitution: 0.15, density: 0.0012 });
    Body.setAngle(body, (Math.random() - 0.5) * 1.2);
    Body.setAngularVelocity(body, (Math.random() - 0.5) * 0.08);
    body.car = { brand, name, style, type, sp, off: { x: x0 - body.position.x, y: y0 - body.position.y } };
    return body;
  }
  const rot = (p, a) => ({ x: p.x * Math.cos(a) - p.y * Math.sin(a), y: p.x * Math.sin(a) + p.y * Math.cos(a) });

  // ---------- scene ----------
  function build() {
    const rect = stage.getBoundingClientRect();
    W = Math.round(rect.width); H = Math.round(Math.min(560, Math.max(380, W * 0.36)));
    cv.width = W * DPR; cv.height = H * DPR; cv.style.height = H + 'px';
    GROUND = H - 84;
    L = Math.max(104, Math.min(180, W / 8));
    WD = Math.round(L * 0.2);
    WN = Math.max(40, Math.round(W / 6)); wdx = W / (WN - 1);
    wh = new Float32Array(WN); wv = new Float32Array(WN); wdrops = [];
    engine = Engine.create({ enableSleeping: true }); engine.gravity.y = 1.1;
    const t = 200;
    walls = [
      Bodies.rectangle(W / 2, GROUND + t / 2, W * 3, t, { isStatic: true, friction: 0.9 }),
      Bodies.rectangle(-t / 2, H / 2 - 600, t, H + 1600, { isStatic: true }),
      Bodies.rectangle(W + t / 2, H / 2 - 600, t, H + 1600, { isStatic: true })
    ];
    Composite.add(engine.world, walls);
    Events.on(engine, 'afterUpdate', keepInside);
    Events.on(engine, 'beforeUpdate', buoy);
    if (dropped) drop(current);
  }
  function keepInside() { // rescue anything thrown out of the stage
    for (const b of cars) if (b.position.y > H + 200 || b.position.x < -300 || b.position.x > W + 300) {
      Body.setPosition(b, { x: W / 2, y: -120 }); Body.setVelocity(b, { x: 0, y: 0 });
    }
  }
  function drop(type) {
    clearTimeout(dropTimer); hideTip(true);
    for (const b of cars) Composite.remove(engine.world, b);
    cars = [];
    const list = DATA[type].models.slice().sort(() => Math.random() - 0.5);
    let i = 0; const token = (drop.token = (drop.token || 0) + 1);
    const next = () => {
      if (token !== drop.token || i >= list.length) return;
      const b = makeCar(list[i], type, 0); cars.push(b); Composite.add(engine.world, b); i++;
      dropTimer = setTimeout(next, 170);
    };
    const wait = list.map((m) => ready[`${m[0]} ${m[1]}`] || Promise.resolve());
    Promise.race([Promise.all(wait), new Promise((r) => setTimeout(r, 2500))]).then(next);
    document.getElementById('mdCount').textContent = `${DATA[type].name} · ${DATA[type].models.length} รุ่น`;
    document.getElementById('mdList').textContent = `${DATA[type].name}: ` + DATA[type].models.map((m) => `${m[0]} ${m[1]}`).join(', ');
  }

  // ---------- drawing ----------
  function paintRain() {
    const T = 360, c = document.createElement('canvas'); c.width = T; c.height = T;
    const x = c.getContext('2d'); x.lineCap = 'round';
    for (let i = 0; i < 50; i++) {
      const px = Math.random() * T, py = Math.random() * T, l = 14 + Math.random() * 34;
      x.strokeStyle = `rgba(221,235,243,${0.05 + Math.random() * 0.12})`; x.lineWidth = 1;
      for (const [ox, oy] of [[0, 0], [T, 0], [0, T], [T, T], [-T, 0], [0, -T]]) { x.beginPath(); x.moveTo(px + ox, py + oy); x.lineTo(px + ox - l * 0.28, py + oy + l); x.stroke(); }
    }
    rainTile = g.createPattern(c, 'repeat');
  }
  function draw() {
    g.setTransform(DPR, 0, 0, DPR, 0, 0);
    g.clearRect(0, 0, W, H);
    // road: asphalt, paper edge lines, dashed centre line (same markings as the rest of the page)
    const rg = g.createLinearGradient(0, GROUND, 0, H);
    rg.addColorStop(0, '#1D1F1E'); rg.addColorStop(1, '#141716');
    g.fillStyle = rg; g.fillRect(0, GROUND, W, H - GROUND);
    g.fillStyle = '#F3EEE3'; g.fillRect(0, GROUND, W, 5); g.fillRect(0, H - 5, W, 5);
    const dash = Math.max(48, W / 16);
    g.fillStyle = 'rgba(243,238,227,.85)';
    for (let x = dash * 0.3; x < W; x += dash * 2) g.fillRect(x, GROUND + (H - GROUND) / 2 - 3, dash, 6);
    // cars
    for (const b of cars) {
      const { sp, off } = b.car;
      g.save(); g.translate(b.position.x, b.position.y); g.rotate(b.angle); g.translate(off.x, off.y);
      if (b === held?.body) { g.shadowColor = 'rgba(243,238,227,.55)'; g.shadowBlur = 18; }
      if (b.car.photo) g.drawImage(b.car.photo, 0, 0, b.car.pw, b.car.ph);
      else g.drawImage(sp.img, -sp.ox, -sp.oy, sp.w, sp.hh);
      g.restore();
    }
    // floodwater over road and cars
    const top = GROUND - WD;
    g.beginPath(); g.moveTo(0, H);
    for (let i = 0; i < WN; i++) { const x = i * wdx; g.lineTo(x, top + wh[i] + wswell(x)); }
    g.lineTo(W, H); g.closePath();
    const wg = g.createLinearGradient(0, top - 10, 0, H);
    wg.addColorStop(0, 'rgba(100,150,180,0.34)'); wg.addColorStop(0.35, 'rgba(34,76,100,0.62)'); wg.addColorStop(1, 'rgba(12,34,48,0.86)');
    g.fillStyle = wg; g.fill();
    g.save(); g.clip();
    g.beginPath();
    for (let i = 0; i < WN; i++) { const x = i * wdx; g.lineTo(x, top + wh[i] + wswell(x) + 7); }
    g.strokeStyle = 'rgba(255,255,255,0.08)'; g.lineWidth = 8; g.stroke();
    g.restore();
    g.beginPath();
    for (let i = 0; i < WN; i++) { const x = i * wdx, y = top + wh[i] + wswell(x); i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.strokeStyle = 'rgba(235,245,250,0.6)'; g.lineWidth = 1.5; g.stroke();
    g.fillStyle = 'rgba(225,240,248,0.85)';
    for (const d of wdrops) { g.beginPath(); g.arc(d.x, d.y, d.r, 0, 6.283); g.fill(); }
  }

  // ---------- label ----------
  let tipBody = null, tipTimer = 0;
  function showTip(b) {
    tipBody = b; clearTimeout(tipTimer);
    tipName.textContent = b.car.name; tipSub.textContent = `${b.car.brand} · ${DATA[b.car.type].name}`;
    tip.hidden = false; placeTip();
  }
  function hideTip(now) { clearTimeout(tipTimer); if (now) { tip.hidden = true; tipBody = null; } else tipTimer = setTimeout(() => { tip.hidden = true; tipBody = null; }, 2200); }
  function placeTip() {
    if (!tipBody) return;
    const top = tipBody.bounds.min.y, x = Math.max(80, Math.min(W - 80, tipBody.position.x));
    tip.style.left = x + 'px'; tip.style.top = Math.max(60, top) + 'px';
  }

  // ---------- drag ----------
  let held = null;
  const pt = (e) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const hit = (p) => { const found = Query.point(cars, p); return found.length ? found[found.length - 1] : null; };
  // touches that start on a car must not scroll the page; everywhere else scrolling still works
  cv.addEventListener('touchstart', (e) => { const t = e.touches[0]; if (hit(pt(t))) e.preventDefault(); }, { passive: false });
  cv.addEventListener('pointerdown', (e) => {
    const p = pt(e), b = hit(p); if (!b) return;
    Sleeping.set(b, false);
    const local = rot({ x: p.x - b.position.x, y: p.y - b.position.y }, -b.angle);
    const c = Constraint.create({ pointA: p, bodyB: b, pointB: rot(local, b.angle), stiffness: 0.12, damping: 0.08, length: 0 });
    Composite.add(engine.world, c);
    held = { body: b, c, local }; cv.classList.add('dragging'); cv.setPointerCapture(e.pointerId);
    showTip(b);
  });
  cv.addEventListener('pointermove', (e) => {
    const p = pt(e);
    if (held) { held.c.pointA = p; held.c.pointB = rot(held.local, held.body.angle); Sleeping.set(held.body, false); return; }
    if (p.y > surf(p.x) - 20) wpoke(p.x, Math.max(-6, Math.min(6, (e.movementX || 0) * 0.25)), 2);
    cv.style.cursor = hit(p) ? 'grab' : 'default';
  });
  const release = () => { if (!held) return; Composite.remove(engine.world, held.c); held = null; cv.classList.remove('dragging'); hideTip(false); };
  cv.addEventListener('pointerup', release); cv.addEventListener('pointercancel', release);

  // ---------- controls + loop ----------
  document.querySelectorAll('.md-type').forEach((btn) => btn.addEventListener('click', () => {
    current = btn.dataset.t;
    document.querySelectorAll('.md-type').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    drop(current);
  }));
  let visible = true, raf = 0, last = performance.now(), acc = 0;
  function frame(now) {
    acc += Math.min(50, now - last); last = now;
    while (acc >= 1000 / 60) { Engine.update(engine, 1000 / 60); waterStep(); acc -= 1000 / 60; }
    draw(); placeTip();
    raf = visible ? requestAnimationFrame(frame) : 0;
  }
  new IntersectionObserver(([en]) => {
    visible = en.isIntersecting;
    if (visible && !dropped) { dropped = true; drop(current); }
    if (visible && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
  }, { threshold: 0.25 }).observe(stage);
  // the quiz above marks which fuel type fits the visitor
  document.addEventListener('cardss:hint', (e) => document.querySelectorAll('.md-type').forEach((b) => b.classList.toggle('is-hint', b.dataset.t === e.detail)));
  let rt; let lastW = 0;
  addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (Math.abs(stage.clientWidth - lastW) > 40) { lastW = stage.clientWidth; Composite.clear(engine.world); Engine.clear(engine); build(); } }, 250); });
  lastW = stage.clientWidth; build();
  raf = requestAnimationFrame(frame);
})();
