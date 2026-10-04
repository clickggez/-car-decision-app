/* CarDSS หน้าใน — ฝนนิ่ง · เมนูมือถือ · ตัวช่วยฟอร์ม · รหัสผ่าน · แท็บรถแนะนำ
   ไม่มีตัวเลขหรือข้อความผลลัพธ์ในไฟล์นี้ ทุกอย่างมาจาก template */
(() => {
  const R = Math.random;
  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  // หน้าผลบอกว่าฟอร์มไหนส่งสำเร็จแล้ว → ล้างคำตอบที่จำไว้ของฟอร์มนั้น
  const clearDrafts = () => document.querySelectorAll('[data-clear-draft]').forEach((el) => {
    try { localStorage.removeItem('cardss:' + el.dataset.clearDraft); } catch (e) { /* ข้าม */ }
  });
  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* ใช้ไม่ได้ก็ข้าม */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ข้าม */ } }
  };
  clearDrafts();

  // ---------- ฝนนิ่ง (ลายเดียวกับหน้าแรก) ----------
  const layer = document.getElementById('rainLayer');
  if (layer) {
    const T = 480, c = document.createElement('canvas');
    c.width = T * DPR; c.height = T * DPR;
    const x = c.getContext('2d'); x.scale(DPR, DPR); x.lineCap = 'round';
    for (let i = 0; i < 75; i++) {
      const px = R() * T, py = R() * T, len = 16 + R() * 42, a = 0.05 + R() * 0.14;
      x.strokeStyle = `rgba(221,235,243,${a})`; x.lineWidth = 0.8 + R() * 0.8;
      for (const [ox, oy] of [[0, 0], [T, 0], [0, T], [T, T], [-T, 0], [0, -T]]) {
        x.beginPath(); x.moveTo(px + ox, py + oy); x.lineTo(px + ox - len * 0.28, py + oy + len); x.stroke();
      }
    }
    layer.style.backgroundImage = `url(${c.toDataURL()})`;
    layer.style.backgroundSize = `${T}px ${T}px`;
  }

  // ---------- เมนูมือถือ ----------
  const mb = document.getElementById('menuBtn'), menu = document.getElementById('menu');
  if (mb && menu) {
    const setMenu = (open) => { menu.classList.toggle('open', open); mb.setAttribute('aria-expanded', String(open)); };
    mb.addEventListener('click', () => setMenu(!menu.classList.contains('open')));
    menu.addEventListener('click', (e) => { if (e.target.closest('a')) setMenu(false); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setMenu(false); });
    window.addEventListener('resize', () => { if (window.innerWidth > 980) setMenu(false); });
  }

  // ---------- จุดสถานะหน้าล็อกอิน: ส้ม ยังไม่กรอก · เหลือง กำลังกรอก · เขียว กรอกครบ ----------
  document.querySelectorAll('[data-auth-status]').forEach((st) => {
    const form = document.getElementById(st.dataset.authStatus);
    if (!form) return;
    const inputs = [...form.querySelectorAll('input[required]')];
    const label = st.querySelector('span'), idleText = label.textContent;
    const TEXT = { idle: idleText, typing: 'กำลังกรอก', ready: 'พร้อมเข้าสู่ระบบ' };
    const update = () => {
      const filled = inputs.filter((i) => i.value.trim() !== '').length;
      const state = filled === 0 ? 'idle' : filled === inputs.length ? 'ready' : 'typing';
      if (st.dataset.state !== state) { st.dataset.state = state; label.textContent = TEXT[state]; }
    };
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    update(); setTimeout(update, 600);   // เผื่อเบราว์เซอร์เติมรหัสให้อัตโนมัติ
  });

  // ---------- ฟอร์มแบบสอบถาม: นับข้อ · จำคำตอบในเครื่อง · บอกข้อที่ขาด · กันกดซ้ำ ----------
  // ข้อที่บังคับ = <fieldset class="field" data-required data-label="ชื่อข้อ">
  // ข้อที่เลือกหลายข้อแต่บังคับอย่างน้อย 1 = data-required data-min="1"
  document.querySelectorAll('form[data-survey]').forEach((form) => {
    const key = 'cardss:' + form.id;
    const fields = [...form.querySelectorAll('.field[data-required]')];
    const bar = form.querySelector('[data-progress-bar]'), txt = form.querySelector('[data-progress-text]');
    const summary = form.querySelector('[data-error-summary]');
    const btn = form.querySelector('button[type="submit"]');

    const answered = (f) => f.querySelector('input:checked, select option:checked:not([value=""])') !== null;
    function update() {
      const done = fields.filter(answered).length;
      if (txt) txt.textContent = `ตอบแล้ว ${done} จาก ${fields.length} ข้อที่จำเป็น`;
      if (bar) bar.style.width = (fields.length ? done * 100 / fields.length : 0) + '%';
      fields.forEach((f) => { if (answered(f)) { f.classList.remove('is-error'); f.querySelectorAll('[aria-invalid]').forEach((i) => i.removeAttribute('aria-invalid')); } });
    }
    function save() {
      const data = {};
      form.querySelectorAll('input[type="radio"]:checked, input[type="checkbox"]:checked').forEach((i) => {
        (data[i.name] = data[i.name] || []).push(i.value);
      });
      store.set(key, data);
    }
    // คืนคำตอบที่เคยกรอกไว้ในเครื่องนี้ (ถ้าเซิร์ฟเวอร์ไม่ได้ติ๊กไว้ก่อน)
    const saved = store.get(key);
    if (saved && !form.querySelector('input:checked')) {
      Object.entries(saved).forEach(([name, vals]) => vals.forEach((v) => {
        const el = form.querySelector(`input[name="${CSS.escape(name)}"][value="${CSS.escape(v)}"]`);
        if (el) el.checked = true;
      }));
    }
    form.addEventListener('change', () => { update(); save(); });
    update();

    // ---------- หลอดบอกตำแหน่งการเลื่อน (ขอบซ้าย เฉพาะจอกว้าง) ----------
    // เติมตามระยะที่เลื่อนมาแล้ว · เส้นขีดคือต้นกล่องแต่ละหมวด (กดเพื่อกระโดดไป) · ขีดเขียว = ตอบครบข้อที่จำเป็นในหมวดนั้นแล้ว
    const panels = [...form.querySelectorAll('.panel')];
    if (panels.length) {
      const rail = document.createElement('nav');
      rail.className = 'scrollrail';
      rail.setAttribute('aria-label', 'ตำแหน่งที่เลื่อนมาในแบบสอบถาม');
      rail.innerHTML = '<span class="sr-end sr-top">เริ่ม</span><div class="sr-track"><i class="sr-fill"></i><b class="sr-thumb"></b></div><span class="sr-end sr-bot">ท้ายหน้า</span><output class="sr-read" aria-live="off"></output>';
      const track = rail.querySelector('.sr-track'), fill = rail.querySelector('.sr-fill'), thumb = rail.querySelector('.sr-thumb'), read = rail.querySelector('.sr-read');
      const ticks = panels.map((p, i) => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'sr-tick';
        const h = p.querySelector('.panel-head h2'), sm = p.querySelector('.panel-head small');
        b.innerHTML = '<span></span><em>' + (sm ? sm.textContent : 'หมวด ' + (i + 1)) + '</em>';
        b.setAttribute('aria-label', 'ไปที่ ' + (h ? h.textContent : 'หมวด ' + (i + 1)));
        b.addEventListener('click', () => p.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' }));
        track.appendChild(b);
        return b;
      });
      document.body.appendChild(rail);
      // ระยะเลื่อนนับถึงท้ายฟอร์มเท่านั้น (ไม่รวมท้ายเว็บ) · เลื่อนเลยท้ายฟอร์มแล้วหลอดค้างเต็ม และไหลขึ้นไปพร้อมหน้า ไม่ตามลงไปทับท้ายเว็บ
      const range = () => Math.max(1, form.getBoundingClientRect().bottom + scrollY - innerHeight);
      function place() {                     // วางขีดตามตำแหน่งจริงของแต่ละหมวด (เรียกใหม่เมื่อขนาดหน้าเปลี่ยน)
        panels.forEach((p, i) => {
          const top = p.getBoundingClientRect().top + scrollY - 110;
          ticks[i].style.top = Math.min(96, Math.max(0, top * 100 / range())) + '%';
        });
      }
      function mark() {
        const R = range(), pct = Math.min(1, Math.max(0, scrollY / R));
        fill.style.height = (pct * 100) + '%';
        thumb.style.top = (pct * 100) + '%';
        const n = Math.round(pct * 100);
        read.textContent = n >= 98 ? 'ถึงท้ายฟอร์มแล้ว' : '';   // ไม่แสดงเปอร์เซ็นต์ · บอกเฉพาะตอนถึงท้าย
        read.style.top = (pct * 100) + '%';
        rail.classList.toggle('is-end', pct > 0.9);       // ใกล้ท้าย: ซ่อนคำ "ท้ายหน้า" ไม่ให้ซ้อนกับข้อความข้างจุด
        rail.classList.toggle('is-start', pct < 0.06);
        rail.style.setProperty('--sr-off', Math.min(0, R - scrollY) + 'px');
        ticks.forEach((b, i) => {
          const req = [...panels[i].querySelectorAll('.field[data-required]')];
          b.classList.toggle('is-done', req.length > 0 && req.every(answered));
        });
      }
      let raf = 0;
      const tick = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(mark); };
      addEventListener('scroll', tick, { passive: true });
      addEventListener('resize', () => { place(); tick(); });
      form.addEventListener('change', () => { place(); tick(); });
      addEventListener('load', () => { place(); mark(); });
      place(); mark();
    }

    form.addEventListener('submit', (e) => {
      const missing = fields.filter((f) => !answered(f));
      if (missing.length) {
        e.preventDefault();
        missing.forEach((f) => { f.classList.add('is-error'); f.querySelectorAll('input').forEach((i) => i.setAttribute('aria-invalid', 'true')); });
        if (summary) {
          summary.hidden = false;
          const list = summary.querySelector('ul');
          list.innerHTML = '';
          missing.forEach((f) => {
            const li = document.createElement('li'), a = document.createElement('a');
            a.href = '#' + f.id; a.textContent = f.dataset.label;
            a.addEventListener('click', (ev) => { ev.preventDefault(); focusField(f); });
            li.appendChild(a); list.appendChild(li);
          });
          const lead = summary.querySelector('[data-count]');
          if (lead) lead.textContent = `ยังไม่ได้ตอบ ${missing.length} ข้อ`;
        }
        focusField(missing[0]);
        return;
      }
      if (btn) {                                  // กำลังวิเคราะห์… และกันกดซ้ำ
        btn.disabled = true; btn.classList.add('is-loading');
        btn.innerHTML = '<span class="spin" aria-hidden="true"></span>กำลังวิเคราะห์…';
      }
      // ไม่ลบคำตอบที่จำไว้ตรงนี้ — ถ้าเซิร์ฟเวอร์ตีกลับ (ตรวจไม่ผ่าน) คำตอบต้องยังอยู่ (Codex #52)
      // ลบเมื่อหน้าผลโหลดแล้วเท่านั้น ดู [data-clear-draft] ด้านล่าง
    });
    function focusField(f) {
      f.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const first = f.querySelector('input, select');
      if (first) first.focus({ preventScroll: true });
    }
  });

  // ---------- แสดง/ซ่อนรหัสผ่าน ----------
  document.querySelectorAll('[data-peek]').forEach((b) => b.addEventListener('click', () => {
    const inp = document.getElementById(b.dataset.peek);
    const show = inp.type === 'password';
    inp.type = show ? 'text' : 'password';
    b.textContent = show ? 'ซ่อน' : 'แสดง';
    b.setAttribute('aria-pressed', String(show));
    const lab = b.dataset.label || (b.dataset.label = b.getAttribute('aria-label') || 'แสดงรหัสผ่าน');
    b.setAttribute('aria-label', show ? lab.replace('แสดง', 'ซ่อน') : lab);
  }));

  // ---------- ความแข็งแรงรหัสผ่าน ----------
  const pw = document.querySelector('[data-pw-meter]');
  if (pw) {
    const meter = document.getElementById(pw.dataset.pwMeter), label = document.getElementById(pw.dataset.pwText);
    const words = ['', 'อ่อนมาก', 'อ่อน', 'ปานกลาง', 'แข็งแรง'];
    pw.addEventListener('input', () => {
      const v = pw.value; let s = 0;
      if (v.length >= 8) s++; if (/[A-Z]/.test(v)) s++; if (/[0-9]/.test(v)) s++; if (/[^A-Za-z0-9]/.test(v)) s++;
      if (v && !s) s = 1;
      meter.dataset.level = String(s);
      label.textContent = v ? 'ความปลอดภัยของรหัสผ่าน: ' + words[s] : '';
    });
  }

  // ---------- ตรวจฟอร์มสมัคร/ล็อกอินก่อนส่ง ----------
  document.querySelectorAll('form[data-auth]').forEach((form) => form.addEventListener('submit', (e) => {
    let bad = null;
    form.querySelectorAll('[data-check]').forEach((inp) => {
      const f = inp.closest('.field'), err = f.querySelector('.field-err span');
      let msg = '';
      const v = inp.value.trim();
      if (!v) msg = 'กรุณากรอก' + (f.dataset.label || 'ช่องนี้');
      else if (inp.dataset.check === 'username' && !/^[a-zA-Z0-9_]{3,30}$/.test(v)) msg = 'ชื่อผู้ใช้ใช้ได้เฉพาะตัวอังกฤษ a–z ตัวเลข 0–9 และขีดล่าง _ ยาว 3–30 ตัว';
      else if (inp.dataset.check === 'newpass' && inp.value.length < 8) msg = 'รหัสผ่านต้องยาวอย่างน้อย 8 ตัว';
      else if (inp.dataset.check === 'confirm' && inp.value !== form.querySelector('#password').value) msg = 'รหัสผ่านทั้งสองช่องไม่ตรงกัน';
      f.classList.toggle('is-error', !!msg);
      if (err) err.textContent = msg;
      const errBox = f.querySelector('.field-err');
      if (errBox && errBox.id) inp.setAttribute('aria-describedby', errBox.id);
      inp.setAttribute('aria-invalid', msg ? 'true' : 'false');
      if (msg && !bad) bad = inp;
    });
    if (bad) { e.preventDefault(); bad.focus(); return; }
    const btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.classList.add('is-loading'); btn.innerHTML = '<span class="spin" aria-hidden="true"></span>' + (btn.dataset.busy || 'กำลังดำเนินการ…'); }
  }));

  // ---------- แท็บประเภทรถ (หน้ารถแนะนำ) ----------
  const tabs = [...document.querySelectorAll('[data-tab]')];
  if (tabs.length) {
    const show = (k) => {
      tabs.forEach((t) => t.setAttribute('aria-pressed', String(t.dataset.tab === k)));
      document.querySelectorAll('[data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== k; });
    };
    tabs.forEach((t) => t.addEventListener('click', () => show(t.dataset.tab)));
  }
})();
