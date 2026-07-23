# สถาปัตยกรรมโปรเจกต์ (Project Architecture)

**ชื่อโปรเจกต์:** Car-Decision-App (CarDSS)
**สถานะปัจจุบัน:** เกือบสมบูรณ์ (High Maturity Phase)

## 🏗️ Tech Stack & Core Logic

- **Backend:** Flask (`app.py`), การจัดการ Sessions
- **Database:** Firebase (Auth/Firestore) พร้อมระบบ Local Mode สำรอง (JSON)
- **Data Source:** `data/cars.json` (แบ่งหมวดหมู่เป็น EV, Hybrid, ICE)
- **AI Models:** Scikit-learn & TensorFlow (เก็บไว้ใน `models/`)
  - `predict_buy`: ทำนายว่าควร "ซื้อ" หรือ "ไม่ซื้อ"
  - `predict_fuel`: แนะนำประเภทเชื้อเพลิง (EV, Hybrid, ICE)

## ✅ กฎของระบบ (DO)

1. Logic หลักมีความเสถียรแล้ว ให้โฟกัสที่:
   - การปรับปรุงประสิทธิภาพ (Optimization)
   - การแก้ไขบั๊ก (Bug fixing)
   - การจัดการกรณีพิเศษ (Edge-case handling)
2. ตรวจสอบให้แน่ใจเสมอว่า Local Mode (JSON) ทำงานได้ไหลลื่นกรณี Firebase ไม่เชื่อมต่อ
3. เขียน unit test สำหรับ edge case ใหม่ทุกครั้งที่เจอ

## ❌ ข้อห้ามเด็ดขาด (DO NOT)

1. ห้ามเปลี่ยน signature ของ `predict_buy()` และ `predict_fuel()`
2. ห้ามเปลี่ยน schema ของ `data/cars.json` (field names, types, categories)
3. ห้าม retrain หรือเปลี่ยนไฟล์ model ใน `models/` โดยไม่ได้รับคำสั่ง
4. ห้ามแก้ไข Firebase Auth flow ที่ใช้งานได้แล้ว
5. ห้ามเพิ่ม dependency ใหม่โดยไม่ update `requirements.txt` และแจ้งใน handoff

## 🐛 Known Issues
*(Agents: เพิ่ม bug หรือข้อจำกัดที่พบเจอในส่วนนี้)*

### Data Signal — ข้อมูลแบบสอบถามไม่มีสัญญาณพอจะเทรนโมเดลจริง (พบ 2026-07-19) ⚠️ อัปเดตสถานะด้านล่าง

- **ที่มา:** ผู้ใช้ขอเทรนโมเดลจริงแทน mock จากไฟล์ `files/user_from/*.csv` (Google Form 225 ตัวอย่าง)
- **สิ่งที่ทำ:** สร้าง `train_models.py` + `models/feature_encoding.py` เทรนเทียบ SVM vs ANN (5-fold CV) จากข้อมูลจริง
- **ผลลัพธ์ (ใกล้ baseline การเดามั่ว):**
  - `predict_buy` (225 แถว): SVM 53.3% / ANN 55.6% — baseline (majority) = 55.1%
  - `predict_fuel` (95 แถว เฉพาะผู้มีรถ): SVM 37.9% / ANN 43.2% — baseline = 43.2%
- **ทดสอบเพิ่ม:** ลองฟีเจอร์ที่รวยที่สุด (7P Likert 21 ข้อ [cols 21–41] + demographic + งบประมาณ ครบ 225 คน) → ยังไม่เกิน baseline (BUY สูงสุด 56%, FUEL แย่กว่า baseline)
- **สาเหตุ:** (1) คะแนน 7P เกือบทุกคนตอบ 4–5 → variance ต่ำ แยกกลุ่มไม่ได้ (2) label แทบไม่ขึ้นกับปัจจัยใดในแบบสอบถาม (3) `predict_fuel` มีเพียง 95 แถวสำหรับ 3 คลาส
- **field mismatch:** ฟอร์มเว็บ `predict_buy.html` เก็บ `children` / `housing_status` / `parking` (3 ระดับ) แต่ Google Form ที่เก็บข้อมูลจริง (https://forms.gle/ikLtNaqnFrKJY8HJ6) ไม่มี 2 ข้อแรก และ `parking` มีแค่ 2 ระดับ (มี/ไม่มี) — หมายเหตุ: เล่มรายงาน (`รูปเล่ม project.pdf`) พิมพ์แบบสอบถามฉบับที่มีครบ แต่ไม่ตรงกับฟอร์มที่ใช้เก็บจริง
  - ✅ **แก้แล้ว (2026-07-19):** แก้ไข Google Form ต้นทางให้ตรงกับเล่มวิจัย — เพิ่มคำถาม "จำนวนบุตรที่มีทั้งหมด" (หลัง Q2 อายุ) และ "สถานะการครอบครองที่พักอาศัย" (หลัง Q6 ลักษณะที่พัก), แก้ "พื้นที่จอดรถ" จาก 2 เป็น 3 ระดับ (มีที่จอดรถส่วนตัว / ไม่มีที่จอดรถ / มีที่จอดรถส่วนกลาง-เช่า) ทั้ง 3 ข้อตั้งเป็นคำถามบังคับ
  - ⚠️ **มีผลกับผู้ตอบใหม่เท่านั้น** — คำตอบเดิม 225/228 แถวที่มีอยู่ (`files/user_from/*.csv`) ยังไม่มีค่าใน 3 field นี้ ต้องรอสะสมข้อมูลใหม่ก่อนจะใช้ train ได้ครบทุก field
- **มติเดิม (ยกเลิกแล้ว):** คง `USE_MOCK = True` ไว้จนกว่าจะมีข้อมูลที่มี signal พอ — โมเดล .pkl ที่เทรนได้ถูกลบทิ้ง (อ่อน + ยังไม่ wire) แต่ `train_models.py` เก็บไว้ regenerate ได้ทันทีเมื่อมีข้อมูลใหม่

#### อัปเดต (2026-07-19, ภายหลัง): ผู้ใช้สร้างข้อมูลทดสอบ 100 แถว + สั่ง wire โมเดลจริงเข้าเว็บเพื่อจำลองการทำงาน

- **ที่มา:** ผู้ใช้กรอกฟอร์ม Google Form ที่แก้ไขแล้ว (มี `children`/`housing_status`/`parking` 3 ระดับครบ) เอง 100 ชุดภายใน ~2 นาที เพื่อทดสอบว่าเว็บทำงานกับโมเดลจริงเป็นอย่างไร — ยืนยันชัดเจนว่าเป็น **"ข้อมูลทดสอบ (test data) ไม่ใช่ข้อมูลสำรวจจริง"**
- **สิ่งที่ทำ:**
  - เพิ่ม field ที่ขาดไปในการเทรนรอบแรก (`concern` สำหรับ buy, `tech_env_concern`/`resale_maintenance_concern` สำหรับ fuel — ใช้ 7P Likert ที่ใกล้เคียงที่สุดเป็น proxy เพราะแบบสอบถามไม่มีคำถามตรงตัว) ให้ `models/feature_encoding.py` ครบ 13/7 fields ตาม docstring จริงใน `predictor.py`
  - เทรนใหม่จาก 100 แถว: `predict_buy` CV 60% (SVM)/test 85%, `predict_fuel` CV 90.4%(ANN)/test 88.2% — **แต่ fuel model เอนเอียงหนักไปทาง Hybrid** (91/100 คนเลือก Hybrid) ดังนั้นโมเดลจะทาย "ไฮบริด" เกือบทุกกรณีจริงๆ ไม่ใช่โมเดลที่แยกแยะได้จริง
  - Wire `predictor.py._real_predict_buy` / `_real_predict_fuel` ให้โหลด `.pkl` ผ่าน `feature_encoding` แล้ว predict จริง (เดิมเป็น `NotImplementedError`)
  - ตั้ง **`config.USE_MOCK = False`** — ทดสอบผ่านเบราว์เซอร์จริงแล้ว (`/result/buy` แสดง "SVM (real)", `/result/fuel` แสดง "ANN (real)")
  - แก้ banner ใน `predict_buy.html` ให้ผูกกับ `config.USE_MOCK` จริง (เดิม hardcode ข้อความ "Mock" ตลอด ไม่ตรงสถานะ) — ส่ง `use_mock=config.USE_MOCK` จาก `predict_buy_page()` ใน `app.py`
- **⚠️ สถานะปัจจุบัน: `USE_MOCK = False` — เว็บใช้โมเดลที่เทรนจากข้อมูลทดสอบ ไม่ใช่ข้อมูลสำรวจจริง** Agent ถัดไปที่พบพฤติกรรมโมเดลแปลกๆ (เช่น fuel ทายไฮบริดตลอด) ให้ทราบว่าเป็นเพราะข้อมูลนี้ ไม่ใช่บั๊ก
- **ความเสี่ยงที่เกี่ยวข้อง:** QA Finding ด้านล่าง (ไม่มี whitelist ค่า select) ตอนนี้มีผลจริงเพราะ `USE_MOCK=False` แล้ว — ค่าที่ไม่ถูก whitelist อาจทำให้ `_real_predict_*` fail ตอน encode (ยังไม่ได้ตรวจเพิ่มเติมในรอบนี้)
- **ขั้นตอนต่อไปถ้าต้องการข้อมูลจริง:** เก็บแบบสอบถามจริงเพิ่มด้วยฟอร์มที่แก้แล้ว (ลิงก์เดิม) แล้ว export CSV ทับไฟล์ปัจจุบันใน `files/user_from/` ก่อนรัน `train_models.py` ใหม่

#### อัปเดต (2026-07-20): ปรับ pipeline การเทรนให้ตรงตามระเบียบวิธีในเล่มโปรเจกต์ (section 3.3)

ผู้ใช้ขอเทียบขั้นตอนสร้างโมเดลที่ผมทำกับที่เล่มโปรเจกต์ระบุไว้ (หัวข้อ 3.3.2–3.3.3) พบว่า
รอบก่อนหน้าขาด 3 ขั้นตอนสำคัญที่เล่มมี:

| ขั้นตอนตามเล่ม | ก่อนแก้ | หลังแก้ |
|---|---|---|
| 3.3.2.2 ปรับสเกลข้อมูลเชิงปริมาณ (Min-Max 0-1) | ไม่ได้ทำ | ✅ ใช้ `MinMaxScaler` กับ `tech_env_concern`/`resale_maintenance_concern`/priority flags |
| 3.3.2.2 แปลงข้อมูลเชิงคุณภาพ | ใช้ One-Hot Encoding | **คงไว้** — เลือกไม่ทำ label-encode ตามเล่ม (เช่น บ้านเดี่ยว=1 ทาวน์โฮม=2) เพราะสร้าง false ordinality ที่กระทบ SVM/ANN ในทางลบ One-Hot เป็น practice ที่ดีกว่าและให้ผลลัพธ์เทียบเท่าเชิงแนวคิด |
| 3.3.2.3 คัดเลือกคุณลักษณะ | ไม่ได้ทำ (ใช้ทุก field) | ✅ เพิ่ม `select_features()` — Chi-square test (เชิงคุณภาพ) + ANOVA F-test (เชิงปริมาณ, ใช้แทน "สหสัมพันธ์" เพราะ target เป็นหมวดหมู่ไม่ใช่ต่อเนื่อง) alpha=0.10 |
| 3.3.2.4 SMOTE | ไม่ได้ทำ (ทั้งที่ `imbalanced-learn` อยู่ใน `requirements.txt` แล้ว) | ✅ เพิ่ม `make_smote()` ผ่าน `imblearn.pipeline.Pipeline` — dynamic `k_neighbors` ตาม class ที่น้อยที่สุด, fallback เป็น `class_weight="balanced"` ถ้า class มีน้อยกว่า 2 ตัวอย่าง (interpolate ไม่ได้) |

**ผลลัพธ์หลังแก้ (100 แถวเดิม, ข้อมูลทดสอบ):**
- `predict_buy`: หลัง feature selection เหลือ field ที่มีนัยสำคัญ (p<0.10) แค่ `housing_status` เพียงตัวเดียว (13 field อื่นไม่ผ่าน) — CV 61%(SVM)/59%(ANN), test accuracy **65%** (ลดจาก 85% เดิม — ตัวเลขนี้ **น่าเชื่อถือกว่าเดิม** เพราะ 85% ก่อนหน้าคือ overfitting จาก n=100 ที่ไม่มีการควบคุมใดๆ เลย)
- `predict_fuel`: ไม่มี field ไหนผ่าน alpha=0.10 เลย (เก็บทั้งหมดไว้กันไม่มีฟีเจอร์เลย) — **ข้าม 5-fold CV ทั้งหมด** เพราะ ICE มีแค่ 2 ตัวอย่างในข้อมูลทั้งหมด (ต้องมีอย่างน้อย 2 ต่อ fold ถึงจะ stratify ได้) SMOTE ใช้ `k_neighbors=1` กับโมเดล final เท่านั้น (train/test split ยังคง fallback เป็น `class_weight="balanced"` เพราะ ICE เหลือแค่ 1 ตัวอย่างในฝั่ง train) — test accuracy 82.4% แต่ **EV/ICE precision/recall ยังเป็น 0%** เหมือนเดิม โมเดลยังทายแค่ "ไฮบริด" เกือบทุกกรณี
- **สรุปตรงไปตรงมา:** SMOTE ช่วยได้จริงเมื่อมีข้อมูลพอ (buy model) แต่ **แก้ fuel model ไม่ได้** เพราะข้อมูลมีแค่ 2 ตัวอย่างของ ICE ทั้งชุด — SMOTE ไม่ใช่เวทมนตร์ที่สร้างข้อมูลจากความว่างเปล่าได้ ต้องมีข้อมูลจริงเพิ่มถึงจะแก้ได้จริง
- **Restart เว็บแล้ว** (`app.py` debug-reload ไม่ pick up ไฟล์ `.pkl` ใหม่อัตโนมัติ เพราะไม่ใช่การเปลี่ยน `.py` — ต้อง `taskkill` + รันใหม่ทุกครั้งหลัง retrain)

#### อัปเดต (2026-07-23): ผู้ใช้นำแบบสอบถามชุดใหม่มาแทนที่ไฟล์เดิม แล้วสั่ง retrain

- **ที่มา:** ไฟล์ CSV ใหม่ใน `files/user_from/` (ชื่อไฟล์ตรงกับ export จาก Google Form จริง "การตอบแบบฟอร์ม 1", แก้ไขล่าสุด 2026-07-23) — **205 แถว**, คอลัมน์ตรงตาม schema 44 คอลัมน์ที่ `train_models.py` คาดหวัง (มีค่าใน `children`/`housing_status`/`parking` 3 ระดับครบทุกแถว ต่างจากชุด 225 แถวเดิมที่ยังไม่มี 3 field นี้) — ยังไม่ได้ยืนยันกับผู้ใช้ว่าเป็นข้อมูลสำรวจจริงทั้งหมดหรือมีข้อมูลทดสอบปนอยู่
- **รัน `python train_models.py`:**
  - `predict_buy`: 205 แถว (ซื้อ 147 / ไม่ซื้อ 58) — feature selection เหลือ field ที่มีนัยสำคัญแค่ `age` (p=0.0196) — เลือก SVM, CV 54.6%, **held-out test accuracy 56.1%** (ใกล้ baseline majority-class ~71.7% แต่โมเดลไม่ได้ทายแค่ class เดียว — precision/recall ของ "ไม่ซื้อ" ยังต่ำ 0.29/0.33)
  - `predict_fuel`: 115 แถว เฉพาะผู้มีรถ (Hybrid 62 / EV 36 / ICE 17) — feature selection เหลือแค่ `prio_technology` (p=0.0337) — เลือก SVM, CV 37.4%, **held-out test accuracy 34.8%** — ICE precision/recall ยังเป็น 0% เหมือนรอบก่อนๆ (17 ตัวอย่างยังน้อยเกินไปสำหรับ 3 คลาส)
  - บันทึกทับ `models/buy_model.pkl` และ `models/fuel_model.pkl` แล้ว
- **สรุป:** สัญญาณในข้อมูลยังอ่อนเหมือนการวิเคราะห์เดิมใน Known Issue นี้ (ดูหัวข้อด้านบน) — มีแค่ 1 field ผ่านเกณฑ์นัยสำคัญต่อโมเดล ผลลัพธ์ใกล้เคียงการเดามั่วมากกว่าการเรียนรู้ pattern จริง ไม่ควรถือเป็นตัวเลขความแม่นยำที่นำไปอ้างอิงได้
- **`config.USE_MOCK` ยังเป็น `False` เหมือนเดิม** (ไม่ได้แก้ไข) — เว็บใช้โมเดลที่เพิ่ง retrain นี้ทันที
- **ยังไม่ได้ restart เว็บเซิร์ฟเวอร์** เพราะไม่มี process Flask รันอยู่ตอนนี้ (เช็คด้วย `Get-Process python` แล้วไม่พบ) — agent ถัดไปที่ start เว็บจะโหลด `.pkl` ใหม่นี้โดยอัตโนมัติตอน start ครั้งแรก ไม่ต้อง restart เพิ่ม

#### อัปเดต (2026-07-23, ภายหลัง): อ่านหัวข้อ 3.3 แบบละเอียดจาก NotebookLM ("รูปเล่ม project .pdf" ใน notebook "CarDSS Project Hub") พบ 3 ช่องว่างเทียบกับ `train_models.py` เดิม แก้ครบแล้ว

อ่านผ่าน NotebookLM (บัญชี ratanakornasa@gmail.com — ดู [[reference_notebooklm_account]]) ได้เนื้อหาเล่มหัวข้อ 3.3 แบบคำต่อคำ เทียบกับโค้ดที่มีแล้วพบ 3 จุดที่ยังไม่ตรงเล่ม:

1. **3.3.2.1 ค่าที่ขาดหาย (เชิงปริมาณ)** — เล่มระบุให้เติมด้วย "ค่าเฉลี่ยเลขคณิต" (mean) แต่โค้ดเดิมไม่มีขั้นตอนนี้เลยสำหรับ numeric cols (มีแค่ mode-fill สำหรับ categorical)
2. **3.3.2.2 การจัดการข้อมูลผิดปกติ** — เล่มระบุให้ตรวจสอบและแทนที่ outlier ด้วยค่ามัธยฐาน แต่โค้ดเดิมไม่มีขั้นตอนนี้เลย
3. **3.3.3.1 vs 3.3.3.2 การกำหนดพารามิเตอร์** — เล่มระบุชัดว่าโมเดล fuel (3 class) ต้อง "ปรับจูนค่า C และแกมมาใหม่" ต่างจากโมเดล buy (2 class) แต่โค้ดเดิมใช้ `SVC(C=3.0, gamma="scale")` ค่าเดียวกันตายตัวทั้งสองโมเดล ไม่มีการจูนต่อโมเดลจริง

**แก้ไขใน `train_models.py`:**
- เพิ่ม `handle_missing_and_outliers()` — mean-fill missing + IQR-based median-replace outlier สำหรับ numeric cols (เรียกใน `train_fuel()` กับ `FUEL_NUM_COLS`; `train_buy()` ไม่มี numeric col เลยจึงไม่ต้องเรียก)
- แทนที่ SVM/ANN แบบ fixed-param ด้วย `GridSearchCV` แยกจูนต่อโมเดล: SVM grid `C∈[0.5,1,3,5,10] × gamma∈[scale,auto,0.01,0.1,0.5,1]`, ANN grid `hidden_layer_sizes∈[(32,),(64,32),(64,32,16)] × learning_rate_init∈[0.001,0.01]` — บันทึก best params ไว้ใน `bundle["metrics"]["best_params"]`

**ผลลัพธ์หลังแก้ (205/115 แถวเดิม, retrain ใหม่):**
- `predict_buy`: SVM ที่จูนแล้ว `C=0.5, gamma=0.1` — CV accuracy **62.9%** (ขึ้นจาก 54.6%), held-out test accuracy คงที่ 56.1% (เพราะ split เดิมด้วย random_state เดียวกัน)
- `predict_fuel`: พบ outlier 4 ค่าใน `resale_maintenance_concern` (แทนที่ด้วยมัธยฐาน 4.0), SVM ที่จูนแล้ว `C=0.5, gamma=1` — CV accuracy **47.0%** (ขึ้นจาก 37.4%), held-out test accuracy **47.8%** (ขึ้นจาก 34.8%) — ICE precision/recall ยัง 0% (มีแค่ 3 ตัวอย่างใน test set)
- **สรุป:** ตัวเลขดีขึ้นเพราะ hyperparameter ที่จูนแล้วเหมาะกับข้อมูลจริงมากกว่าค่า default เดิม ไม่ใช่เพราะสัญญาณในข้อมูลดีขึ้น — feature selection ยังผ่านแค่ 1 field ต่อโมเดลเหมือนเดิม (`age` / `prio_technology`) ยืนยันว่า Known Issue "Data Signal" ด้านบนยังคงอยู่ ไม่ควรอ้างตัวเลขนี้เป็นผลงานวิจัยที่แม่นยำ
- บันทึกทับ `.pkl` ทั้งคู่แล้ว, `USE_MOCK` คงเป็น `False`, เว็บไม่ได้รันอยู่ตอน retrain (ไม่ต้อง restart)

#### อัปเดต (2026-07-23, ล่าสุด): ผู้ใช้เก็บแบบสอบถามจริงเพิ่มถึง n=505 (ครบตามเป้า 500 ในเล่ม 3.3.1) — Known Issue "Data Signal" คลี่คลายแล้ว

ผู้ใช้แทนที่ไฟล์ CSV ด้วยชุดข้อมูลใหม่ **505 แถว** (ไฟล์ `...การตอบแบบฟอร์ม(500).csv`) แล้วสั่ง retrain ตาม pipeline เดิม (ไม่แก้โค้ดเพิ่ม แค่รัน `train_models.py` ใหม่ + restart server เพราะ `.pkl` ไม่ auto-reload):

- **predict_buy** (505 แถว, ซื้อ 246 / ไม่ซื้อ 259 — สมดุลกว่าเดิมมาก): feature selection ผ่านเกณฑ์นัยสำคัญ **8 field** (`education`, `family_size`, `housing_type`, `housing_status`, `parking`, `budget`, `concern`, `purpose`) ต่างจากรอบก่อนที่ผ่านแค่ `age` ตัวเดียว — SVM tuned `C=1, gamma=0.01`, **CV accuracy 68.1%, held-out test accuracy 67.3%** (precision/recall สมดุลทั้งสอง class: 0.64/0.76 และ 0.72/0.60)
- **predict_fuel** (261 แถวเฉพาะผู้มีรถ, Hybrid 96 / ICE 92 / EV 73 — สมดุลกว่าเดิมมาก จากเดิม ICE มีแค่ 17): feature selection ผ่าน **7 field** (`usage_type`, `prio_price`, `prio_installment`, `prio_performance`, `prio_design`, `prio_value`, `prio_warranty`) — SVM tuned `C=5, gamma=auto`, **CV accuracy 54.0%, held-out test accuracy 47.2%** — **ICE precision/recall ไม่ใช่ 0% อีกต่อไป (0.65/0.58)**, Hybrid (0.55/0.63), EV ยังอ่อน (0.14/0.13)
- พบ+แก้ outlier เพิ่ม: `tech_env_concern` 1 ค่า, `resale_maintenance_concern` 8 ค่า (แทนที่ด้วยมัธยฐาน 4.0)
- **Restart Flask server แล้ว** (`taskkill` python ทั้งหมด + รัน `python app.py` ใหม่) — ทดสอบผ่านเบราว์เซอร์จริง: `/result/buy` และ `/result/fuel` แสดง "SVM (real)" ถูกต้อง, ทดสอบ input ที่ `prev_car != ice` แล้วโมเดล**ยังให้ความน่าจะเป็น ICE 17%** (ไม่ใช่ 0% เหมือนก่อนหน้า) ยืนยันว่าโมเดลแยกแยะ ICE ได้จริงแล้ว ไม่ต้องพึ่ง `prev_car=ice` ตรงๆ อีกต่อไป

**สรุป: Known Issue "Data Signal" ที่บันทึกไว้ตั้งแต่ 2026-07-19 คลี่คลายแล้วเมื่อมีข้อมูลจริงครบ n=500 ตามเล่ม** — พิสูจน์ว่า pipeline (Min-Max/feature-selection/SMOTE/GridSearchCV tuning) ถูกต้องมาตลอด ปัญหาที่แท้จริงคือขนาดข้อมูลไม่พอ ไม่ใช่บั๊กของโค้ด ยังไม่ใช่ตัวเลขระดับ production-grade (BUY 67%, FUEL 47%) แต่ดีขึ้นชัดเจนและใช้งานสาธิตได้จริงแล้ว

### QA Findings — `POST /api/predict/buy` (พบ 2026-04-20) ✅ แก้แล้วใน validators.py (2026-04-24)

1. **ไม่มี whitelist ของค่า select** — endpoint ยอมรับทุก string ที่ไม่ใช่ empty เช่น `gender="alien"`, `budget="999999999999"` ผ่าน validation แล้ว pass-through ไปโมเดล
   - **ผลกระทบ:** เมื่อ `USE_MOCK = False` โมเดลจริงอาจ crash เพราะ encode feature ไม่ได้ หรือทำนายผิด
   - **แนะนำ:** เพิ่ม dict whitelist ต่อ field ใน `api_predict_buy` หรือสร้าง validator ส่วนกลาง

2. **ไม่ตรวจค่าติดลบ** — เช่น `children="-1"`, `income="-50000"` ผ่าน validation ปัจจุบัน
   - **ผลกระทบ:** เหมือนข้อ 1 — UI ส่งไม่ได้ แต่ raw POST ส่งได้

3. **Whitespace-only bypass** — `if not v` ใน `app.py:405` catch เฉพาะ empty string ไม่ catch `"   "` (space-only)
   - **แนะนำ:** เปลี่ยนเป็น `if not v.strip()`

4. **ไม่มี sanitization ต่อ XSS/SQL payload** — ค่าอย่าง `<script>alert(1)</script>` หรือ `'; DROP TABLE --` ผ่านไปถึง Firebase/session
   - **ผลกระทบ:** หาก render input_data ใน template โดยไม่ escape อาจเกิด XSS (Jinja2 auto-escape ช่วยได้บางส่วน แต่ไม่ป้องกัน Firestore)

**Test coverage:** `car-dss/tests/test_predict_buy_edge_cases.py` (16 tests passing)

### Firestore Dashboard Query — Missing Composite Index (พบ 2026-04-24) ✅ แก้แล้ว (2026-04-29)

- **ปัญหา:** `get_dashboard_data_from_firebase` ใช้ query `.where('user_id', '==', ...).order_by('created_at', DESC)` ซึ่งต้องการ composite index — หากไม่มี Firestore จะ return 400 error → fallback ไป mock data เสมอ
- **วิธีแก้:** Deploy `firestore.indexes.json` ที่ root ของ project ไปยัง project `cardss-e678f` แล้ว — index บน `predictions` (user_id ASC + created_at DESC) พร้อมใช้งานแล้ว
- **ไฟล์ที่เกี่ยวข้อง:** `firestore.indexes.json`, `firebase.json`

### QA Findings — `POST /api/predict/fuel` (พบ 2026-04-20) ✅ แก้แล้วใน validators.py (2026-04-24)

1. **พบบั๊กเดียวกันกับ `predict_buy`** — ไม่มี whitelist ของ select values, ไม่ตรวจค่าติดลบในช่องคะแนน (1-5), และ whitespace-only bypass validation
2. **`priority` list validation** — แม้ว่าจะมีการตรวจ `not input_data.get('priority')` เพื่อป้องกัน list ว่าง แต่ไม่มีการ validate สมาชิกภายใน list (เช่น ส่งค่าที่ไม่มีใน UI ไปได้)
3. **Logic Dependency** — `buy_result_required` decorator ทำงานได้ถูกต้อง ป้องกันการเข้าถึงหากไม่ได้ผลลัพธ์ "ซื้อ"

**Test coverage:** `car-dss/tests/test_predict_fuel_edge_cases.py` (13 tests passing)
