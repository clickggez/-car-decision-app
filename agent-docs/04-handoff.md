# บันทึกการส่งมอบงาน (Agent Handoff Log)

> 📌 **Agents:** เขียนบันทึกของคุณไว้ที่ **ด้านบนสุด** ของไฟล์นี้เมื่อทำงานเสร็จในแต่ละครั้ง
> ใช้รูปแบบ template ด้านล่าง และใส่วันที่จริง (YYYY-MM-DD)

---

**วันที่:** 2026-07-20
**จาก:** Claude Code (ML Agent — Opus 4.8)
**ถึง:** Agent ถัดไป

**⚠️ สรุปสถานะสำคัญที่สุด: `config.USE_MOCK = False` — เว็บใช้โมเดลจริง เทรนจากข้อมูลทดสอบ (ไม่ใช่ข้อมูลสำรวจจริง) และตอนนี้ pipeline มี SMOTE + feature selection + Min-Max scaling ตามระเบียบวิธีในเล่มโปรเจกต์แล้ว**

**สิ่งที่ทำไปแล้ว (ต่อจาก entry 2026-07-19 ด้านล่าง):**
- ผู้ใช้ขอให้เทียบขั้นตอนสร้างโมเดลที่ทำกับที่เล่มโปรเจกต์ (`รูปเล่ม project.pdf` section 3.3) ระบุไว้ — พบว่าขาด 3 ขั้นตอน: Min-Max scaling (3.3.2.2), Chi-square/สหสัมพันธ์ feature selection (3.3.2.3), SMOTE (3.3.2.4) — ทั้งที่ `imbalanced-learn` มีอยู่ใน `requirements.txt` แล้วแต่ไม่เคยถูกเรียกใช้จริง
- แก้ `train_models.py`:
  - เพิ่ม `select_features()` — Chi-square test (scipy) สำหรับ field เชิงหมวดหมู่, ANOVA F-test (sklearn `f_classif`) สำหรับ field เชิงตัวเลข (ใช้แทน "สหสัมพันธ์" เพราะ target เป็นหมวดหมู่ ไม่ใช่ต่อเนื่อง) alpha=0.10, กันไม่ให้เหลือ 0 ฟีเจอร์
  - เพิ่ม `make_smote()` — สร้าง `SMOTE` object แบบ dynamic k_neighbors ตาม class ที่น้อยที่สุด, คืน `None` (fallback `class_weight="balanced"`) ถ้า class มีน้อยกว่า 2 ตัวอย่าง (SMOTE interpolate ไม่ได้)
  - เปลี่ยนจาก `sklearn.pipeline.Pipeline` เป็น `imblearn.pipeline.Pipeline` เพื่อให้ SMOTE ถูกใช้เฉพาะฝั่ง train ของแต่ละ fold เท่านั้น (กัน data leakage เข้า test/validation)
  - เพิ่ม `MinMaxScaler` ให้ field ตัวเลข (`tech_env_concern`, `resale_maintenance_concern`, priority flags) แทน `passthrough`
  - **จงใจไม่ทำ** label-encoding ตัวเลขแบบเล่ม (บ้านเดี่ยว=1 ทาวน์โฮม=2...) — คง One-Hot Encoding ไว้เพราะ label-encode สร้าง false ordinality ที่กระทบโมเดล SVM/ANN โดยไม่จำเป็น เป็นการตัดสินใจเชิงคุณภาพที่ดีกว่า ไม่ใช่การมองข้าม
- เทรนใหม่ 100 แถวเดิม: **BUY** เหลือ `housing_status` เป็น field เดียวที่มีนัยสำคัญ (p<0.10), test accuracy **65%** (ลดจาก 85% เดิม — เชื่อถือได้กว่าเพราะลด overfitting) **FUEL** ไม่มี field ไหนผ่านเกณฑ์เลย (เก็บทั้งหมดไว้), **ข้าม 5-fold CV ทั้งหมด** เพราะ ICE มีแค่ 2 ตัวอย่างในข้อมูล 83 แถว (ไม่พอ stratify), SMOTE ใช้ได้เฉพาะตอนเทรนโมเดล final (full data), ยังคง**ทายแต่ "ไฮบริด"** เหมือนเดิม — ยืนยันว่าไม่ใช่บั๊กของ pipeline แต่เป็นข้อจำกัดของข้อมูลทดสอบที่มีจริงแค่ 2 ตัวอย่างของ ICE
- Restart Flask dev server (`taskkill` + รันใหม่) เพราะ debug-reload ไม่ pick up ไฟล์ `.pkl` ที่เปลี่ยนอัตโนมัติ (reload trigger จากการเปลี่ยน `.py` เท่านั้น)
- อัปเดต `agent-docs/01-architecture.md`, `03-task-board.md`

**ไฟล์ที่แก้ไข (รอบนี้):**
- `car-dss/train_models.py` (เพิ่ม `select_features()`, `make_smote()`, เปลี่ยนเป็น `imblearn.pipeline.Pipeline`, `MinMaxScaler`)
- `car-dss/models/buy_model.pkl`, `fuel_model.pkl` (regenerate)
- `agent-docs/01-architecture.md`, `03-task-board.md`

**ขั้นตอนต่อไป:**
- **fuel model จะดีขึ้นได้จริงก็ต่อเมื่อมีข้อมูลจริงที่มี ICE/EV มากกว่านี้เท่านั้น** — SMOTE/feature selection ทำได้เต็มที่แล้วในรอบนี้ ไม่มีอะไรให้ปรับเพิ่มโดยไม่มีข้อมูลใหม่
- ถ้าจะ retrain อีก อย่าลืม restart dev server ทุกครั้ง (`taskkill //F //IM python.exe` แล้ว `python app.py` ใหม่) ไม่งั้นเว็บจะยังใช้โมเดลเก่าในหน่วยความจำ

**ข้อควรระวัง:**
- ดูข้อควรระวังเพิ่มเติมใน entry วันที่ 2026-07-19 ด้านล่าง (เรื่อง badge "(real)" ไม่ได้แปลว่าเชื่อถือได้ทางสถิติ ยังคงใช้ได้กับรอบนี้)

**สิ่งที่ทำไปแล้ว:**
- ผู้ใช้กรอกฟอร์ม Google Form ที่แก้แล้ว (เพิ่ม children/housing_status/parking 3 ระดับ) ด้วยตัวเองจำนวน 100 ชุดภายใน ~2 นาที เพื่อ **ทดสอบว่าเว็บทำงานกับโมเดลจริงอย่างไร** — ยืนยันชัดเจนว่าเป็นข้อมูลทดสอบ (test data) ไม่ใช่ผลสำรวจจริงจากกลุ่มตัวอย่าง
- พบว่าการเทรนรอบก่อนหน้า (entry ML ด้านล่าง) พลาดไม่ได้ใส่ field `concern` (buy) และ `tech_env_concern`/`resale_maintenance_concern` (fuel) ทั้งที่เป็น field จริงตาม docstring ใน `predictor.py` — แก้ไขแล้วใน `models/feature_encoding.py` ให้ครบ 13 fields (buy) / 7 fields+priority (fuel)
  - `tech_env_concern`/`resale_maintenance_concern` ไม่มีคำถามตรงตัวในแบบสอบถาม ใช้ 7P Likert ที่ใกล้เคียงที่สุดเป็น proxy (ดู comment ใน `train_models.py`, คอลัมน์ index 23 และ 28)
- เทรนใหม่จาก 100 แถว: `predict_buy` CV 60%(SVM)/test 85%, `predict_fuel` CV 90.4%(ANN)/test 88.2% — **แต่ fuel label เอนเอียงหนักไปทาง Hybrid (91/100)** โมเดลจะทาย "ไฮบริด" เกือบทุกกรณี ไม่ใช่โมเดลที่แยกแยะได้จริง (precision/recall ของ EV, ICE = 0 ใน test set)
- Wire `models/predictor.py`: `_real_predict_buy`/`_real_predict_fuel` โหลด `.pkl` ผ่าน `feature_encoding` แล้ว predict จริง (เดิมเป็น `NotImplementedError`)
- ตั้ง `config.USE_MOCK = False` — ทดสอบผ่านเบราว์เซอร์จริงแล้ว (รัน `python app.py`, กรอกฟอร์ม `/predict/buy` และ `/predict/fuel` ด้วย fetch POST) ผลแสดง badge "SVM (real)" และ "ANN (real)" ถูกต้องตาม contract เดิม (`result`/`confidence`/`model_used`, `scores` สำหรับ fuel)
- แก้ banner ใน `templates/predict_buy.html` (เดิม hardcode ข้อความ "โหมด Mock" ตลอดไม่ว่าสถานะจริงจะเป็นอะไร) ให้ผูกกับ `config.USE_MOCK` จริงผ่านตัวแปร `use_mock` ที่ส่งจาก `predict_buy_page()` ใน `app.py`

**ไฟล์ที่แก้ไข:**
- `car-dss/models/feature_encoding.py` (เพิ่ม concern, tech_env_concern, resale_maintenance_concern)
- `car-dss/train_models.py` (แก้ column mapping ให้ตรง layout ใหม่ + proxy concern fields)
- `car-dss/models/predictor.py` (wire `_real_predict_buy`/`_real_predict_fuel`)
- `car-dss/config.py` (`USE_MOCK = False`)
- `car-dss/app.py` (`predict_buy_page()` ส่ง `use_mock=config.USE_MOCK`)
- `car-dss/templates/predict_buy.html` (banner ใช้ `{% if use_mock %}`)
- `car-dss/models/buy_model.pkl`, `fuel_model.pkl` (regenerate ใหม่จากข้อมูลทดสอบ 100 แถว)
- `agent-docs/01-architecture.md`, `03-task-board.md` (อัปเดต Known Issue "Data Signal")

**ขั้นตอนต่อไป:**
- **เมื่อมีข้อมูลสำรวจจริงมาแทนที่ข้อมูลทดสอบ:** export CSV ทับไฟล์ใน `files/user_from/` แล้วรัน `python train_models.py` ใหม่ — โครงสร้างโค้ดรองรับอยู่แล้ว ไม่ต้องแก้อะไรเพิ่มถ้า column layout เหมือนเดิม
- **ถ้าต้องการกลับไปใช้ mock:** ตั้ง `config.USE_MOCK = True` — โค้ดรองรับ fallback อัตโนมัติอยู่แล้วถ้าไม่พบไฟล์ `.pkl` ด้วย
- ยังไม่ได้ตรวจว่า `validators.py` whitelist ครอบคลุมค่าที่เป็นไปได้ทั้งหมดของ field ใหม่ (เช่น `parking` 3 ค่า) หรือไม่ — ตอนนี้ `USE_MOCK=False` แล้ว หากมีค่าที่ไม่ผ่าน whitelist หลุดเข้ามาอาจทำให้ `_real_predict_*` fail ตอน encode (ยังไม่เจอปัญหาจริงในการทดสอบ แต่ควรตรวจเพิ่ม)

**ข้อควรระวัง:**
- **ห้ามเข้าใจผิดว่าโมเดลตอนนี้ validate แล้วว่าดี** — accuracy สูงเพราะข้อมูลทดสอบเบ้ (fuel) และ n=100 ยังน้อยเกินไปสำหรับงานวิจัยจริง เก็บ badge "(real)" ไว้เพื่อความโปร่งใสว่าไม่ใช่ mock แต่ไม่ได้แปลว่าเชื่อถือได้ทางสถิติ
- Dev server รันด้วย `debug=True` มี auto-reload อยู่แล้ว ไม่ต้อง restart เองหลังแก้โค้ด Python/template

**สิ่งที่ทำไปแล้ว:**
- ต่อจาก Known Issue "Data Signal" (ดู entry ML ด้านล่าง) ที่พบว่าฟอร์มเว็บเก็บ field (`children`/`housing_status`/`parking` 3 ระดับ) ไม่ตรงกับ Google Form ที่เก็บข้อมูลจริง
- แก้ไข Google Form ต้นทาง (https://forms.gle/ikLtNaqnFrKJY8HJ6, เจ้าของฟอร์มยืนยันเป็นผู้ใช้เอง) ให้ตรงกับแบบสอบถามฉบับสมบูรณ์ในเล่มโปรเจกต์ (`รูปเล่ม project.pdf`):
  - เพิ่มคำถาม "จำนวนบุตรที่มีทั้งหมด" (แทรกหลัง Q2 อายุ) — 5 ตัวเลือก: ไม่มีบุตร/1/2/3/มากกว่า 3 คน
  - เพิ่มคำถาม "สถานะการครอบครองที่พักอาศัย" (แทรกหลัง Q6 ลักษณะที่พัก) — 3 ตัวเลือก: เป็นเจ้าของ/เช่า/พักอาศัยกับครอบครัว
  - แก้ "พื้นที่จอดรถ" จาก 2 เป็น 3 ระดับ: มีที่จอดรถส่วนตัว/ไม่มีที่จอดรถ/มีที่จอดรถส่วนกลาง-เช่า
  - ทั้ง 3 ข้อตั้งเป็นคำถามบังคับ (จำเป็น)

**ไฟล์ที่แก้ไข:**
- ไม่มีไฟล์ในโปรเจกต์ที่แก้ไข (แก้ที่ Google Form ภายนอกโดยตรงผ่าน browser)
- `agent-docs/01-architecture.md` (อัปเดต Known Issue "Data Signal" — mark field mismatch ว่าแก้แล้วที่ต้นทาง)
- `agent-docs/03-task-board.md` (เพิ่ม entry → Done)

**ขั้นตอนต่อไป:**
- **สำคัญ:** คำตอบเดิม 225/228 แถวใน `files/user_from/*.csv` ยังไม่มีค่าใน 3 field ใหม่นี้ (คำถามใหม่มีผลกับผู้ตอบใหม่เท่านั้น)
- เมื่อมีผู้ตอบแบบสอบถามเพิ่ม ควร export CSV ใหม่มาแทนที่ไฟล์เดิมใน `files/user_from/` ก่อนรัน `train_models.py` อีกครั้ง — ตอนนั้นจะมี field ครบทั้ง 13 ตัวสำหรับ `predict_buy` เป็นครั้งแรก อาจช่วยให้ signal ดีขึ้น (แต่ไม่รับประกัน ดู Known Issue เดิมเรื่อง 7P Likert variance ต่ำ)

**ข้อควรระวัง:**
- ไม่ได้แก้ไขข้อมูล response เดิม 225/228 แถว — แก้แค่ schema ของฟอร์มสำหรับอนาคต

---

**วันที่:** 2026-07-19
**จาก:** Claude Code (ML Agent — Opus 4.8)
**ถึง:** Agent ถัดไป

**สิ่งที่ทำไปแล้ว:**
- ผู้ใช้ขอเทรนโมเดลจริง (SVM + ANN) แทน mock โดยใช้ข้อมูลแบบสอบถามจริงจาก `files/user_from/*.csv` (Google Form 225 ตัวอย่าง)
- สร้าง pipeline เทรน: `car-dss/train_models.py` + `car-dss/models/feature_encoding.py` (shared encoder กัน train/serve skew — แปลงค่าไทย → web value space เดียวกับที่ฟอร์มส่ง)
- เทียบ SVM vs ANN ด้วย 5-fold CV → เลือก ANN ทั้งคู่ แต่ accuracy อยู่ระดับ baseline: `predict_buy` ~55.6% (baseline 55.1%), `predict_fuel` ~43.2% (baseline 43.2%, มีแค่ 95 แถว)
- ทดสอบเพิ่มด้วยฟีเจอร์ที่รวยที่สุด (7P Likert 21 ข้อ + demo + งบ ครบ 225 คน) → ยังไม่เกิน baseline → สรุปว่าข้อมูลไม่มี signal (ไม่ใช่ปัญหาฟอร์ม/โมเดล)
- เชื่อม NotebookLM notebook "CarDSS Project Hub" ถามคำแนะนำเรื่อง field ที่ขาด (children/housing_status) — LM อ้างอิงเล่มรายงานใน notebook
- **มติผู้ใช้: คง `USE_MOCK = True`** จนกว่าจะมีข้อมูลที่ใช้ได้

**ไฟล์ที่แก้ไข/สร้างใหม่:**
- `car-dss/train_models.py` (สร้างใหม่ — reusable)
- `car-dss/models/feature_encoding.py` (สร้างใหม่ — reusable, ยังไม่ถูก import โดย predictor.py)
- `agent-docs/01-architecture.md` (เพิ่ม Known Issue "Data Signal")
- `agent-docs/03-task-board.md` (เพิ่ม entry → Done)
- **ลบ:** `models/buy_model.pkl`, `models/fuel_model.pkl` (อ่อน + ยังไม่ wire)
- **ไม่แตะ:** `config.py` (`USE_MOCK=True` เหมือนเดิม), `models/predictor.py`

**ขั้นตอนต่อไป:**
- หากได้ข้อมูลใหม่ที่มี signal: วาง CSV ใน `files/user_from/`, ปรับ mapping ไทย→web ใน `train_models.py` ให้ตรง column, รัน `python train_models.py` → ได้ `.pkl`, แล้วต้อง **wire `_real_predict_buy`/`_real_predict_fuel` ใน `predictor.py`** ให้ใช้ bundle (โหลด pipeline + `feature_encoding.buy_features_from_web`/`fuel_features_from_web`) ก่อนตั้ง `USE_MOCK=False`
- ปัจจุบัน `predictor.py._real_predict_*` ยังเป็น `NotImplementedError` — ยังไม่ได้ wire (ตั้งใจ เพราะยังใช้ mock)
- **ยังค้างจาก handoff ก่อนหน้า (ยังไม่ทำ):** ช่องว่างดำใน `home.html`/`recommend.html` และ feedback เรื่องดีไซน์ดูเหมือน AI-generated

**ข้อควรระวัง:**
- ไม่ได้เพิ่ม dependency ใหม่ (scikit-learn/pandas/joblib มีใน `requirements.txt` อยู่แล้ว)
- `feature_encoding.py` import แบบ `from models import feature_encoding` (รันจาก root `car-dss/`)

---

**วันที่:** 2026-07-19
**จาก:** Claude Code (UI Agent)
**ถึง:** Agent ถัดไป

**สิ่งที่ทำไปแล้ว:**
- ผู้ใช้ feedback ว่า icon แบบ emoji (⚡🔋⛽📊📈🤖🔥📋⭐🛡️✅❌⚠️) ดูเหมือน AI generate เพราะแต่ละตัวมาจากคนละสไตล์/font
- แทนที่ emoji ทั้งหมดด้วย Bootstrap Icons (`bi bi-*`) ซึ่งเป็น library เดียวกับที่ navbar ใช้อยู่แล้ว (โหลดผ่าน CDN ใน `base.html` บรรทัด 21) ให้สไตล์เส้น (line-icon) เดียวกันทั่วเว็บ
- ไอคอนที่ผูกกับประเภทเชื้อเพลิง (EV/Hybrid/ICE) ใช้ class `.text-ev` / `.text-hybrid` / `.text-ice` หรือ CSS var สีตรงเพื่อคงความหมายเชิงสีไว้ (เขียว/ฟ้า/ส้ม)
- Mapping หลัก: ⚡→`bi-lightning-charge-fill`, 🔋→`bi-battery-charging`, ⛽→`bi-fuel-pump-fill`, 📊→`bi-bar-chart-line`/`bi-pie-chart-fill`, 📈→`bi-graph-up-arrow`, 🤖→`bi-cpu`, 🔥(Firebase)→`bi-database-fill-check`, 📋→`bi-clipboard-data`/`bi-file-earmark-text-fill`, ⭐→`bi-star-fill`, 🛡️→`bi-shield-check`, ✅/❌→`bi-check-circle-fill`/`bi-x-circle-fill`, ⚠️→`bi-exclamation-triangle-fill`
- ทดสอบผ่านเบราว์เซอร์จริง (home, dashboard, recommend) — ไอคอนแสดงผลถูกต้องทุกหน้า

**ไฟล์ที่แก้ไข:**
- `car-dss/templates/home.html`
- `car-dss/templates/dashboard.html`
- `car-dss/templates/recommend.html`
- `car-dss/templates/result_fuel.html`
- `car-dss/templates/result_buy.html`
- `agent-docs/03-task-board.md` (เพิ่ม entry → Done)

**ขั้นตอนต่อไป:**
- ยังพบ "ช่องว่างดำขนาดใหญ่" ระหว่าง section บนหน้า home.html และ recommend.html (เช่น ระหว่าง hero กับ "ประเภทรถยนต์", และก่อนตาราง comparison) — น่าจะเป็น margin/padding เกิน ควรตรวจสอบและแก้ต่อ
- ผู้ใช้ fe feedback เพิ่มเติมว่าดีไซน์โดยรวม (สี #3b82f6 ทั่วไป, การ์ดหน้าตาเหมือนกันหมด, typography ไม่มี hierarchy) ยังดูเหมือน AI-generated template — ยังไม่ได้ทำ ควรถามผู้ใช้ว่าจะให้ปรับต่อไหม

**ข้อควรระวัง:**
- Bootstrap Icons โหลดผ่าน CDN อยู่แล้ว ไม่ต้องเพิ่ม dependency ใหม่ — ตรงกับกฎ "ห้าม import font ใหม่" ใน `02-design-system.md`
- ห้ามใช้ shadow/gradient ตกแต่งไอคอนตามกฎ Design System (Zero Chrome)

---

**วันที่:** 2026-04-29
**จาก:** Claude Code (UI + Bugfix Agent)
**ถึง:** Agent ถัดไป

**สิ่งที่ทำไปแล้ว:**
- แก้สีลิงก์ 2 จุด: "สมัครสมาชิก" (login.html) และ "เข้าสู่ระบบ" (register.html) → `#3b82f6`, font-weight 600, underline, hover `#60a5fa`
- แก้ bfcache theme bug: เพิ่ม `pageshow` event ใน `main.js` — เมื่อ browser restore page จาก back/forward cache จะ re-sync `data-theme` จาก localStorage ทันที ทำให้ธีมสม่ำเสมอทุกหน้า

**ไฟล์ที่แก้ไข:**
- `car-dss/templates/login.html`
- `car-dss/templates/register.html`
- `car-dss/static/js/main.js`

**ขั้นตอนต่อไป:**
- ไม่มี task ค้างอยู่

**ข้อควรระวัง:**
- ไม่มี

---

**วันที่:** 2026-04-29
**จาก:** Claude Code (DevOps Agent)
**ถึง:** Agent ถัดไป

**สิ่งที่ทำไปแล้ว:**
- Deploy Firestore composite index → แก้ Known Issue: dashboard fallback ไป mock data เสมอ
  - Collection: `predictions`
  - Fields: `user_id` (ASC) + `created_at` (DESC)
  - Project: `cardss-e678f`
- สร้าง `firestore.indexes.json` และ `firebase.json` ที่ root ของ project
- อัปเดต `01-architecture.md` — mark Known Issue ว่า resolved

**ไฟล์ที่แก้ไข/สร้างใหม่:**
- `firestore.indexes.json` (สร้างใหม่)
- `firebase.json` (สร้างใหม่)
- `agent-docs/01-architecture.md` (mark resolved)

**ขั้นตอนต่อไป:**
- ไม่มี task เหลือใน To Do แล้ว — โปรเจกต์อยู่ในสถานะ production-ready
- หาก dashboard ยังไม่ดึงข้อมูลจริง ให้รอ index build เสร็จ (อาจใช้เวลาไม่กี่นาที) แล้วทดสอบซ้ำ

**ข้อควรระวัง:**
- `firebase.json` ที่ root มีแค่ `firestore.indexes` — ยังไม่ได้ config hosting/functions
- Index build ใน Firestore อาจใช้เวลา 1-5 นาทีหลัง deploy ก่อนจะ query ได้จริง

---

**วันที่:** 2026-04-29
**จาก:** Claude Code (Code Review Agent — Docs)
**ถึง:** Agent ถัดไป

**สิ่งที่ทำไปแล้ว:**
- เพิ่ม docstring ตัวอย่าง input/output ใน `predict_buy` และ `predict_fuel` ใน `models/predictor.py`
  - `predict_buy`: ระบุ 13 fields พร้อม whitelist values และ Example call/output
  - `predict_fuel`: ระบุ 6 fields + `priority` list พร้อม Example call/output
- ย้าย Docs task → Done ใน `03-task-board.md`

**ไฟล์ที่แก้ไข:**
- `car-dss/models/predictor.py` (อัปเดต docstring ของ `predict_buy` และ `predict_fuel`)
- `agent-docs/03-task-board.md` (ย้าย task → Done)

**ขั้นตอนต่อไป:**
- ไม่มี task เหลือใน To Do แล้ว
- Known Issue ที่ค้างอยู่: Firestore composite index (user_id + created_at) ยังไม่ได้สร้าง — dashboard fallback ไป mock data ใน production

**ข้อควรระวัง:**
- ถ้าแก้ whitelist ใน `validators.py` ต้องอัปเดต docstring ใน `predictor.py` ด้วย

---

## 📝 Template
```
**วันที่:** YYYY-MM-DD
**จาก:** [ชื่อ Agent / บทบาท]
**ถึง:** [Agent ถัดไป]

**สิ่งที่ทำไปแล้ว:**
- ...

**ไฟล์ที่แก้ไข:**
- ...

**ขั้นตอนต่อไป:**
- ...

**ข้อควรระวัง:**
- ...
```

---

**วันที่:** 2026-04-24
**จาก:** Claude Code (QA + Code Review Agent)
**ถึง:** Code Review Agent (Docs)

**สิ่งที่ทำไปแล้ว:**
- Local Mode Testing: สร้าง `tests/test_local_mode.py` (12 tests) — ยืนยัน app ทำงานได้เมื่อ db=None ทั้ง helper/auth/dashboard/full-flow
- Refactor: เพิ่ม `_current_uid()` และ `_form_fields()` ใน `app.py` — ลดโค้ดซ้ำใน predict handlers
- **พบ Known Issue ใหม่**: Firestore query ใน `get_dashboard_data_from_firebase` ต้องการ composite index (user_id + created_at) ที่ยังไม่ได้สร้าง → ทำให้ dashboard ใช้ mock data เสมอใน production

**ไฟล์ที่แก้ไข:**
- `car-dss/tests/test_local_mode.py` (สร้างใหม่ — 12 tests)
- `car-dss/app.py` (เพิ่ม `_current_uid`, `_form_fields`, refactor predict handlers)
- `agent-docs/03-task-board.md` (ย้าย tasks → Done)

**ขั้นตอนต่อไป:**
- งานเหลือเพียง 🟢 Low: เพิ่ม docstring ตัวอย่าง input/output ใน `models/predictor.py`
- พิจารณาสร้าง Firestore composite index เพื่อให้ dashboard ดึงข้อมูลจริงได้

**ข้อควรระวัง:**
- `[ERROR] Firebase read failed: 400` ที่เห็นตอนรัน tests คือ expected behavior (Firestore missing index) — fallback ไป mock data ทำงานถูกต้อง

---

**วันที่:** 2026-04-24
**จาก:** Claude Code (QA Agent)
**ถึง:** QA Agent

**สิ่งที่ทำไปแล้ว:**
- สแกน `cars.json` ทั้งหมด 25 รายการ เทียบกับไฟล์จริงใน `static/img/cars/`
- ผล: ไม่พบ broken path — ทุกรายการมีไฟล์ภาพครบ

**ไฟล์ที่แก้ไข:**
- `agent-docs/03-task-board.md` (ย้าย task → Done)
- `agent-docs/04-handoff.md` (เพิ่ม entry นี้)

**ขั้นตอนต่อไป:**
- QA Agent: ทดสอบ Local Mode (JSON) ทำงานแทน Firebase ได้จริง (simulate Firebase down)

---

**วันที่:** 2026-04-24
**จาก:** Claude Code (Code Review Agent)
**ถึง:** QA Agent

**สิ่งที่ทำไปแล้ว:**
- สร้าง `car-dss/validators.py` — Centralized Validation แก้ Known Issues ทั้ง 4 ข้อ
  1. Whitelist ต่อ field ทุกช่องใน predict_buy (13 fields) และ predict_fuel (6 fields + priority list)
  2. ตรวจ whitespace-only ด้วย `val.strip()`
  3. Reject ค่าติดลบ (ไม่อยู่ใน whitelist อยู่แล้ว)
  4. Reject XSS/SQL payload (ไม่อยู่ใน whitelist อยู่แล้ว)
- อัปเดต `app.py`: แทน validation เดิมด้วย `validate_buy()` / `validate_fuel()`
- อัปเดต test assertions 7 ตัวที่บันทึก "Known Issue" → เปลี่ยนเป็น assert reject แล้ว
- 29 tests ผ่านทั้งหมด

**ไฟล์ที่แก้ไข:**
- `car-dss/validators.py` (สร้างใหม่)
- `car-dss/app.py` (เพิ่ม import + แทน validation logic ใน api_predict_buy/api_predict_fuel)
- `car-dss/tests/test_predict_buy_edge_cases.py` (อัปเดต 4 test assertions)
- `car-dss/tests/test_predict_fuel_edge_cases.py` (อัปเดต 3 test assertions)
- `agent-docs/03-task-board.md` (ย้าย task → Done)
- `.cursorrules` (เพิ่มกฎข้อ 3: ต้องถามผู้ใช้ก่อนเปลี่ยน model)

**ขั้นตอนต่อไป:**
- QA Agent: ทดสอบ Local Mode (JSON) ทำงานแทน Firebase ได้จริง (simulate Firebase down)
- QA Agent: สแกน `cars.json` หา `image` path ที่ชี้ไปไฟล์ที่ไม่มีอยู่จริง

**ข้อควรระวัง:**
- `validators.py` ใช้ whitelist ตรง match กับ `value` attribute ของ `<option>` ใน template — ถ้าแก้ template ต้องอัปเดต whitelist ด้วย
- Known Issues ใน `01-architecture.md` ยังไม่ได้ลบออก — ควร mark ว่า resolved แล้ว

---

**วันที่:** 2026-04-20
**จาก:** Claude Code (Bugfix Agent)
**ถึง:** QA Agent / Code Review Agent

**สิ่งที่ทำไปแล้ว:**
- แก้บั๊ก: ภาพ GWM ORA 05 ไม่โหลดบน UI
- สาเหตุ: (1) ชื่อไฟล์มีช่องว่าง `gwm-ora-05 .png` (2) `cars.json` ชี้ไปที่ชื่อไฟล์เก่า `Gemini_Generated_Image_yms85uyms85uyms8.png` ที่ไม่มีอยู่จริง
- วิธีแก้: rename ไฟล์ + อัปเดต `image` value ใน `cars.json` (ไม่กระทบ schema — เปลี่ยนเฉพาะ value)

**ไฟล์ที่แก้ไข:**
- `car-dss/static/img/cars/gwm-ora-05 .png` → `gwm-ora-05.png` (rename)
- `car-dss/data/cars.json` (แก้ field `image` ของ ORA 05 500 Ultra)
- `agent-docs/03-task-board.md` (เพิ่ม entry → Done)

**ขั้นตอนต่อไป:**
- QA Agent ถัดไป: ทำ task "🟡 Medium - Testing: ตรวจสอบ Local Mode (JSON) ทำงานแทน Firebase ได้จริง"
- แนะนำ: ตรวจสอบว่ามีรถยี่ห้ออื่นที่ path ใน `cars.json` ชี้ไปที่ไฟล์ที่ไม่มีอยู่จริงไหม — อาจใช้ script สแกนอัตโนมัติ

**ข้อควรระวัง:**
- ห้ามแก้ **schema** ของ `cars.json` — แต่การแก้ **value** ของ field `image` อนุญาต (เป็น data correction ไม่ใช่ schema change)
- ไฟล์ภาพในโฟลเดอร์ `static/img/cars/` ควรไม่มีช่องว่างในชื่อไฟล์ (URL encoding ปัญหา)

---

**วันที่:** 2026-04-20
**จาก:** Claude Code (QA Agent)
**ถึง:** QA Agent / Code Review Agent

**สิ่งที่ทำไปแล้ว:**
- เขียน edge-case test suite สำหรับ `predict_fuel` (13 tests, ผ่านทั้งหมด)
- ครอบคลุม: input ว่าง, empty priority list, ค่าติดลบในช่องคะแนน, และ out-of-range select values
- ทดสอบ Security Decorators (`login_required`, `buy_result_required`)
- พบและบันทึก **Known Issues** เพิ่มเติมใน `01-architecture.md`:
  1. พบช่องโหว่ชุดเดียวกับ `predict_buy` (no whitelist, no negative check, whitespace bypass)
  2. `priority` (checkbox list) ขาดการ validate สมาชิกภายใน list

**ไฟล์ที่แก้ไข:**
- `car-dss/tests/test_predict_fuel_edge_cases.py` (สร้างใหม่ — 13 tests)
- `agent-docs/01-architecture.md` (เพิ่ม section "QA Findings — `POST /api/predict/fuel`")
- `agent-docs/03-task-board.md` (ย้าย task `predict_fuel` → Done)

**วิธีรันเทส:**
```
cd car-dss
python -m unittest tests.test_predict_fuel_edge_cases -v
```

**ขั้นตอนต่อไป:**
- QA Agent: ทดสอบ task "🟡 Medium - Testing: ตรวจสอบ Local Mode (JSON) ทำงานแทน Firebase ได้จริง"
- Code Review Agent: รวบยอดแก้ Known Issues ทั้งหมด (buy/fuel) ด้วยระบบ Centralized Validation

**ข้อควรระวัง:**
- `test_buy_result_not_buy_blocked` ยืนยันว่าห้ามเข้าหน้า fuel หากผล buy ไม่ใช่ "ซื้อ"
- Behavior ปัจจุบันยังยอมรับค่า invalid (บันทึกไว้ใน tests เพื่อรอการแก้ไข logic)

---

**สิ่งที่ทำไปแล้ว:**
- เขียน edge-case test suite สำหรับ `predict_buy` (16 tests, ผ่านทั้งหมด)
- ครอบคลุม 3 หมวดตามโจทย์: input ว่าง, ค่าติดลบ, ค่าเกินช่วง
- ทดสอบ 2 ระดับ: direct predictor + Flask endpoint (`POST /api/predict/buy`)
- พบและบันทึก **4 known issues** ใน `01-architecture.md`:
  1. ไม่มี whitelist ของค่า select
  2. ไม่ตรวจค่าติดลบ
  3. Whitespace-only bypass validation (`if not v` vs `if not v.strip()`)
  4. ไม่มี sanitization ต่อ XSS/SQL payload

**ไฟล์ที่แก้ไข:**
- `car-dss/tests/__init__.py` (สร้างใหม่)
- `car-dss/tests/test_predict_buy_edge_cases.py` (สร้างใหม่ — 16 tests)
- `agent-docs/01-architecture.md` (เพิ่ม section "QA Findings" ใน Known Issues)
- `agent-docs/03-task-board.md` (ย้าย task → Done)

**วิธีรันเทส:**
```
cd car-dss
python -m unittest tests.test_predict_buy_edge_cases -v
```

**ขั้นตอนต่อไป:**
- QA Agent ถัดไป: ทำ edge-case tests ของ `predict_fuel` (🔴 High Priority) ใช้โครงสร้างเดียวกันได้ — หมายเหตุ `priority` เป็น `getlist` (checkbox) ต้องทดสอบ empty list แยก
- Code Review Agent: พิจารณาสร้าง validator ส่วนกลาง (เช่น `validators.py`) เพื่อแก้ known issues ข้อ 1-3 ในครั้งเดียว ก่อนจะ retrain model จริง

**ข้อควรระวัง:**
- ไม่แก้ไข signature ของ `predict_buy` ตามกฎใน `01-architecture.md`
- Tests บันทึก behavior ปัจจุบัน — เมื่อแก้ known issues ต้องอัปเดต assertions ของ `test_negative_values_currently_accepted`, `test_out_of_whitelist_currently_accepted`, `test_xss_payload_passes_validation`, `test_whitespace_only_fields_rejected` จาก 302→result_buy เป็น 302→predict_buy_page
- `[OK] Firebase connected successfully` ที่ปรากฏตอนรันเทสมาจาก import `app` — ไม่กระทบผลเทส

---

**วันที่:** 2026-04-19
**จาก:** Claude Code (Project Manager Agent)
**ถึง:** QA Agent (เริ่มทำงานเป็นคนแรก)

**สิ่งที่ทำไปแล้ว:**
- สร้างโฟลเดอร์ `agent-docs/` พร้อมไฟล์เอกสาร 4 ไฟล์
- สร้าง `.cursorrules` และ `.windsurfrules` ที่ root
- ล็อกกฎทางสถาปัตยกรรม (DO/DO NOT) เพื่อป้องกันการแก้ Logic หลัก Flask/Firebase/AI Models
- จัดลำดับความสำคัญของงาน QA และ Optimization ใน task board
- Implement Dark Mode ตาม DESIGN.md Section 9 (Tesla Design System) ครบทุก template
- แก้ไข hardcode สีขาว/ดำใน home.html, login.html, recommend.html, dashboard.html ให้ใช้ CSS Variables

**ไฟล์ที่แก้ไข:**
- `.cursorrules` (สร้างใหม่)
- `.windsurfrules` (สร้างใหม่)
- `agent-docs/01-architecture.md` (สร้างใหม่)
- `agent-docs/02-design-system.md` (สร้างใหม่)
- `agent-docs/03-task-board.md` (สร้างใหม่)
- `agent-docs/04-handoff.md` (สร้างใหม่)
- `car-dss/static/css/style.css` (เขียนใหม่ — Dark Mode ตาม DESIGN.md)
- `car-dss/static/js/main.js` (เพิ่ม Dark Mode toggle + localStorage)
- `car-dss/templates/base.html` (เพิ่มปุ่ม toggle + flash-prevent script)
- `car-dss/templates/home.html` (แก้ hardcode #FFFFFF/white → CSS vars)
- `car-dss/templates/login.html` (แก้ hardcode white → CSS vars)
- `car-dss/templates/recommend.html` (แก้ tab buttons + JS → CSS vars)
- `car-dss/templates/dashboard.html` (แก้ chart grid + insurance note → CSS vars)

**ขั้นตอนต่อไป:**
- QA Agent: เริ่มจาก task "🔴 High - QA: ทดสอบ Edge cases ใน `predict_buy` form" เป็นงานแรก
- อ่าน `01-architecture.md` ส่วน "ข้อห้ามเด็ดขาด" ก่อนแตะโค้ด

**ข้อควรระวัง:**
- ห้ามแก้ไขสิ่งในรายการ "เสร็จสิ้นแล้ว" ของ task board
- ถ้าเจอ bug ให้เพิ่มใน "Known Issues" ของ `01-architecture.md`
- Dark Mode ใช้ `data-theme="dark"` บน `<html>` + localStorage key `theme`
- ค่าสีทั้งหมดอ้างอิงจาก DESIGN.md Section 9 เท่านั้น
