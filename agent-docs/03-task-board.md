# กระดานจัดการงาน (Task Board - High Maturity Phase)

## ⏳ สิ่งที่ต้องทำ (To Do)

| Priority | Task | Owner | หมายเหตุ |
|----------|------|-------|----------|

## 🚀 กำลังดำเนินการ (In Progress)

## ✅ เสร็จสิ้นแล้ว (⚠️ ห้ามรื้อทำใหม่)

- [x] Setup: สร้างเอกสาร multi-agent workflow (`agent-docs/`)
- [x] Backend: การตั้งค่า Flask, Routing, และการเชื่อมต่อ Firebase
- [x] AI: รวม Prediction Engine (`predict_buy`, `predict_fuel`) เข้าสู่ระบบ
- [x] UI/UX: นำระบบดีไซน์แบบ Tesla และ Dark mode มาใช้เต็มรูปแบบ
- [x] Database: จับคู่โครงสร้างและรวมข้อมูล `cars.json`
- [x] Dark Mode Implementation (2026-04-19): เขียน `style.css` ใหม่ตาม DESIGN.md Section 9, เพิ่ม toggle + localStorage ใน `main.js` และ `base.html`, แก้ hardcode สี → CSS Variables ใน `home.html`, `login.html`, `recommend.html`, `dashboard.html`
- [x] QA (2026-04-20): Edge-case tests ของ `predict_buy` — 16 tests ผ่าน, พบ 4 known issues (ดู `01-architecture.md`), test file: `car-dss/tests/test_predict_buy_edge_cases.py`
- [x] QA (2026-04-20): Edge-case tests ของ `predict_fuel` — 13 tests ผ่าน, พบบั๊กชุดเดียวกับ `predict_buy` และความเสี่ยงใน `priority` list validation, test file: `car-dss/tests/test_predict_fuel_edge_cases.py`
- [x] Bugfix (2026-04-20): ภาพ GWM ORA 05 ไม่โหลด — rename `gwm-ora-05 .png` (มีช่องว่าง) → `gwm-ora-05.png` + อัปเดต `image` path ใน `cars.json` จาก `Gemini_Generated_Image_yms85uyms85uyms8.png` (ไม่มีอยู่จริง) → `cars/gwm-ora-05.png`
- [x] Security (2026-04-24): Centralized Validation — สร้าง `validators.py` แก้ Known Issues ทั้ง 4 ข้อ (whitelist, negative values, whitespace bypass, XSS pass-through) สำหรับทั้ง predict_buy และ predict_fuel, 29 tests ผ่าน
- [x] Data Integrity (2026-04-24): สแกน `cars.json` ครบ 25 รายการ — ไม่พบ broken image path ใดเลย
- [x] Testing (2026-04-24): Local Mode (JSON) — เขียน 12 tests ครอบคลุม helper/auth/dashboard/full-flow เมื่อ db=None, ทั้งหมดผ่าน
- [x] Optimization (2026-04-24): Refactor app.py — เพิ่ม `_current_uid()` และ `_form_fields()` ลด repetition ใน predict handlers, 41 tests ผ่าน
- [x] Docs (2026-04-29): เพิ่ม docstring ตัวอย่าง input/output ครบทั้ง `predict_buy` (13 fields) และ `predict_fuel` (6 fields + priority list) ใน `models/predictor.py`
- [x] Infra (2026-04-29): Deploy Firestore composite index (user_id ASC + created_at DESC) บน collection `predictions` → แก้ dashboard fallback to mock data issue
- [x] UI (2026-04-29): แก้สีลิงก์ "สมัครสมาชิก" ใน `login.html` และ "เข้าสู่ระบบ" ใน `register.html` → เปลี่ยนจาก `var(--text-muted)` เป็น `#3b82f6` พร้อม underline + hover effect
- [x] Bugfix (2026-04-29): แก้ bfcache theme bug ใน `main.js` → เพิ่ม `pageshow` event listener re-sync theme จาก localStorage เมื่อ browser restore page จาก back/forward cache
- [x] UI (2026-07-19): แทนที่ emoji icon ทั้งหมด (⚡🔋⛽📊📈🤖🔥📋⭐🛡️✅❌⚠️) ด้วย Bootstrap Icons (`bi-*`) ให้สไตล์เดียวกันทั้งเว็บ — ครอบคลุม `home.html`, `dashboard.html`, `recommend.html`, `result_fuel.html`, `result_buy.html`
- [x] ML (2026-07-19): ศึกษาความเป็นไปได้ในการเทรนโมเดลจริงจากข้อมูลแบบสอบถามจริง (`files/user_from/*.csv`, 225 ตัวอย่าง) — สร้าง `train_models.py` + `models/feature_encoding.py` เทียบ SVM vs ANN. ผลอยู่ที่ระดับ baseline ทั้งคู่ (BUY ~56%, FUEL ~43%) เพราะข้อมูลไม่มี signal (ดู Known Issue "Data Signal" ใน `01-architecture.md`). **มติ: คง `USE_MOCK = True`** — ลบ .pkl ที่อ่อนทิ้ง, เก็บสคริปต์ไว้ regenerate เมื่อมีข้อมูลใหม่
- [x] Data (2026-07-19): แก้ไข Google Form ต้นทาง (แบบสอบถามวิจัย) ให้ตรงกับแบบสอบถามฉบับสมบูรณ์ในเล่มโปรเจกต์ — เพิ่ม "จำนวนบุตรที่มีทั้งหมด" และ "สถานะการครอบครองที่พักอาศัย", แก้ "พื้นที่จอดรถ" จาก 2 เป็น 3 ระดับ. มีผลกับผู้ตอบใหม่เท่านั้น ข้อมูล 225 แถวเดิมยังไม่มีค่าใน field เหล่านี้ (ดู `01-architecture.md`)
- [x] ML (2026-07-19): ผู้ใช้กรอกข้อมูลทดสอบ 100 ชุดผ่านฟอร์มที่แก้แล้ว แล้วสั่ง wire โมเดลจริงเข้าเว็บเพื่อจำลองการทำงาน — เพิ่ม field ที่ขาด (`concern`, `tech_env_concern`, `resale_maintenance_concern`) ให้ `feature_encoding.py` ครบ, เทรนใหม่ (BUY 85% test acc, FUEL 88.2% แต่เอนเอียงไป Hybrid หนักเพราะข้อมูลทดสอบ), wire `predictor.py._real_predict_*`, ตั้ง **`USE_MOCK = False`**, แก้ banner ใน `predict_buy.html` ให้ผูกกับ `config.USE_MOCK` จริง (ส่ง `use_mock` จาก `app.py`). **⚠️ ข้อมูลเป็นชุดทดสอบ ไม่ใช่ผลสำรวจจริง — ดู `01-architecture.md`**
- [x] ML (2026-07-20): เทียบขั้นตอนสร้างโมเดลกับเล่มโปรเจกต์ (section 3.3) พบขาด Min-Max scaling, Chi-square/ANOVA feature selection, และ SMOTE — เพิ่มทั้ง 3 ขั้นตอนใน `train_models.py` (`select_features()`, `make_smote()`), เทรนใหม่ (BUY test acc 65% — ตัวเลขน่าเชื่อถือกว่าเดิมเพราะลด overfitting, FUEL ยังทายแต่ Hybrid เพราะ ICE มีแค่ 2 ตัวอย่างในข้อมูลทั้งชุด SMOTE ช่วยไม่ได้จริงในระดับนี้), restart เว็บเซิร์ฟเวอร์ให้โหลดโมเดลใหม่ ดูรายละเอียดใน `01-architecture.md`
- [x] ML (2026-07-23): ผู้ใช้นำแบบสอบถามชุดใหม่มาทับ `files/user_from/*.csv` (205 แถว) แล้วสั่ง retrain — รัน `train_models.py` เดิม (pipeline Min-Max/feature-selection/SMOTE ไม่เปลี่ยน): BUY test acc 56.1% (feature เดียวที่มีนัยสำคัญ = `age`), FUEL test acc 34.8% (feature เดียว = `prio_technology`, ICE precision/recall ยัง 0%) — สัญญาณข้อมูลยังอ่อนเหมือน Known Issue เดิม บันทึกทับ `.pkl` ทั้งคู่แล้ว, `USE_MOCK` คงเป็น `False`, เว็บยังไม่ได้รันอยู่ตอน retrain (ไม่ต้อง restart) ดูรายละเอียดใน `01-architecture.md`
- [x] ML (2026-07-23, ภายหลัง): อ่านหัวข้อ 3.3 ของเล่มโปรเจกต์แบบละเอียดผ่าน NotebookLM ("CarDSS Project Hub" notebook, บัญชี ratanakornasa@gmail.com) พบ 3 ช่องว่าง — ไม่มี mean-fill สำหรับค่าขาดหายเชิงปริมาณ, ไม่มี outlier handling (IQR + median), และ SVM ใช้ `C`/`gamma` ตายตัวค่าเดียวทั้ง buy/fuel ทั้งที่เล่มระบุให้จูนแยกต่อโมเดล — เพิ่ม `handle_missing_and_outliers()` และเปลี่ยนเป็น `GridSearchCV` จูนแยกต่อโมเดลใน `train_models.py`, retrain ใหม่: BUY CV acc 62.9% (จาก 54.6%, C=0.5/gamma=0.1), FUEL CV acc 47.0%/test acc 47.8% (จาก 37.4%/34.8%, C=0.5/gamma=1, พบ+แก้ outlier 4 ค่าใน `resale_maintenance_concern`) — ตัวเลขดีขึ้นเพราะจูน hyperparameter ไม่ใช่สัญญาณข้อมูลดีขึ้น (feature selection ยังผ่านแค่ 1 field/โมเดลเหมือนเดิม) ดูรายละเอียดใน `01-architecture.md`
- [x] ML (2026-07-23, ล่าสุด): ผู้ใช้เก็บแบบสอบถามจริงเพิ่มถึง **n=505** (ครบเป้า 500 ตามเล่ม 3.3.1) แล้วสั่ง retrain — รัน `train_models.py` เดิม (ไม่แก้โค้ด) + restart Flask server: **BUY** feature selection ผ่าน 8 field (จาก 1 field เดิม), CV acc **68.1%**, test acc **67.3%** (C=1/gamma=0.01) — **FUEL** feature selection ผ่าน 7 field, CV acc **54.0%**, test acc **47.2%** (C=5/gamma=auto), **ICE precision/recall ไม่ใช่ 0% อีกต่อไป (0.65/0.58)** เพราะข้อมูล ICE เพิ่มจาก 17→92 ตัวอย่าง — ทดสอบผ่านเบราว์เซอร์จริง: input ที่ `prev_car≠ice` ยังได้ ICE 17% (ไม่ใช่ 0% เหมือนก่อน) **Known Issue "Data Signal" คลี่คลายแล้ว** ดูรายละเอียดใน `01-architecture.md`

