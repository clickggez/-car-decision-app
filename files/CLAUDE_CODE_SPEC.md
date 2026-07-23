# 🚗 PROJECT SPEC — ระบบสนับสนุนการตัดสินใจซื้อรถยนต์
# Car Purchase Decision Support System (CarDSS)
# สำหรับใช้กับ Claude Code

---

## 📌 ภาพรวมโปรเจค

ระบบเว็บแอปพลิเคชันสำหรับช่วยตัดสินใจซื้อรถยนต์ในเขตบางขุนเทียน กรุงเทพมหานคร
ใช้หลักการทำเหมืองข้อมูล (Data Mining) ด้วย SVM และ ANN เพื่อพยากรณ์:
1. ควรซื้อ หรือ ไม่ควรซื้อ รถยนต์
2. ควรซื้อรถยนต์ประเภทเชื้อเพลิงใด (สันดาป / ไฮบริด / ไฟฟ้า)
3. แสดง Dashboard แผนภาพข้อมูลสนับสนุนการตัดสินใจ

---

## 🛠 Tech Stack

| ส่วน | เทคโนโลยี |
|------|-----------|
| Frontend | HTML5 + CSS3 + JavaScript + Bootstrap 5 |
| Backend | Flask (Python) |
| Database | Firebase Firestore |
| ML Model | scikit-learn (SVM), TensorFlow/Keras (ANN) |
| Dashboard | Power BI Embedded หรือ Chart.js (ทดแทน) |
| Auth | Firebase Authentication |

---

## 📁 โครงสร้างโฟลเดอร์ที่ต้องสร้าง

```
car-dss/
├── app.py                    # Flask main app
├── config.py                 # Firebase config, secret keys
├── requirements.txt          # Python dependencies
├── models/
│   ├── train_model.py        # Script สร้างและ train โมเดล
│   ├── buy_model.pkl         # โมเดลพยากรณ์ ซื้อ/ไม่ซื้อ
│   └── fuel_model.pkl        # โมเดลพยากรณ์ ประเภทเชื้อเพลิง
├── static/
│   ├── css/
│   │   └── style.css         # Custom CSS
│   ├── js/
│   │   └── main.js           # Frontend JavaScript
│   └── img/                  # รูปภาพ/ไอคอน
├── templates/
│   ├── base.html             # Base template (navbar, footer)
│   ├── login.html            # หน้าเข้าสู่ระบบ
│   ├── register.html         # หน้าสมัครสมาชิก
│   ├── predict_buy.html      # ฟอร์มพยากรณ์ ซื้อ/ไม่ซื้อ
│   ├── predict_fuel.html     # ฟอร์มพยากรณ์ ประเภทเชื้อเพลิง
│   ├── result_buy.html       # แสดงผล ซื้อ/ไม่ซื้อ
│   ├── result_fuel.html      # แสดงผล ประเภทรถ
│   └── dashboard.html        # Dashboard แผนภาพข้อมูล
└── data/
    └── survey_data.csv       # ข้อมูลแบบสอบถาม 500 ชุด
```

---

## 👥 ผู้ใช้งานระบบ (Actors)

### 1. ผู้ใช้งานทั่วไป (User)
- สมัครสมาชิก
- เข้าสู่ระบบ
- กรอกข้อมูลพยากรณ์ ซื้อ/ไม่ซื้อ
- กรอกข้อมูลพยากรณ์ ประเภทเชื้อเพลิง (extend จากผลลัพธ์ "ซื้อ")
- ดู Dashboard แผนภาพข้อมูล

### 2. ผู้ดูแลระบบ (Admin)
- สร้าง/อัปเดตโมเดล
- สร้างแผนภาพข้อมูล

---

## 📄 รายละเอียดแต่ละหน้า

### หน้า 1: Login (`/login`)
- ฟอร์ม: ชื่อผู้ใช้, รหัสผ่าน
- ปุ่ม: เข้าสู่ระบบ
- ลิงก์: ไปหน้าสมัครสมาชิก
- Auth ผ่าน Firebase Authentication
- เมื่อ login สำเร็จ → redirect ไป `/predict/buy`

### หน้า 2: Register (`/register`)
- ฟอร์ม: ชื่อผู้ใช้, รหัสผ่าน, ยืนยันรหัสผ่าน
- Validate: รหัสผ่านต้องตรงกัน
- เมื่อสมัครสำเร็จ → redirect ไป `/login`

### หน้า 3: พยากรณ์ซื้อ/ไม่ซื้อ (`/predict/buy`)
- ต้อง login ก่อน (ใส่ @login_required)
- ฟอร์มแบ่ง 2 ส่วน:

**ส่วนที่ 1 — ข้อมูลส่วนบุคคล:**
| ฟิลด์ | ประเภท | ตัวเลือก |
|-------|--------|---------|
| เพศ | select | ชาย, หญิง |
| อายุ | select | 20-23, 24-26, 27-30, 31-40, 41-50, 51-60, 60+ |
| จำนวนบุตร | select | ไม่มี, 1, 2, 3, 3+ |
| ระดับการศึกษา | select | ต่ำกว่า ม.3, ม.3, ม.6, ปวช./ปวส., ป.ตรี, ป.โท, ป.เอก |
| อาชีพ | select | นักศึกษา, อาชีพอิสระ, รัฐวิสาหกิจ, พนักงานเอกชน, ข้าราชการ, เจ้าของกิจการ, ค้าขาย, ชาวประมง/เกษตร, อื่นๆ |
| จำนวนสมาชิกครอบครัว | select | 1-2, 3-4, 5+ |
| ลักษณะที่พักอาศัย | select | บ้านเดี่ยว, ทาวน์โฮม, คอนโด/อพาร์ตเมนต์, หอพัก |
| สถานะการครอบครองที่พัก | select | เจ้าของ, เช่า, พักกับครอบครัว |
| พื้นที่จอดรถ | select | มีส่วนตัว, มีส่วนกลาง, ไม่มี |
| รายได้เฉลี่ยต่อเดือน | select | ต่ำกว่า 15,000 / 15,001-25,000 / 25,001-35,000 / 35,001-50,000 / 50,001-75,000 / 75,000+ |

**ส่วนที่ 2 — ปัจจัยการเลือกซื้อ:**
| ฟิลด์ | ประเภท | ตัวเลือก |
|-------|--------|---------|
| งบประมาณซื้อรถ | select | ต่ำกว่า 500,000 / 500,001-800,000 / 800,001-1,200,000 / 1,200,001-1,500,000 / 1,500,000+ |
| ข้อกังวล/ปัญหาการใช้งาน | select | ราคาน้ำมัน, ค่าไฟฟ้า, สถานีชาร์จ, ปั้มน้ำมัน, ศูนย์บริการ/อะไหล่, อายุแบตเตอรี่, ค่าซ่อมบำรุง, มูลค่าขายต่อ |
| วัตถุประสงค์การใช้รถ | select | เดินทางไปทำงาน, ค้าขาย, ท่องเที่ยว, ความสะดวก, หลีกเลี่ยงขนส่งมวลชน |

- ปุ่ม: "วิเคราะห์ผล" → POST ไป Flask API → ส่งข้อมูลเข้าโมเดล
- Validate: ทุกช่องต้องกรอก, งบประมาณต้องเป็นตัวเลข

### หน้า 4: ผลพยากรณ์ซื้อ/ไม่ซื้อ (`/result/buy`)
- แสดงผลลัพธ์: "ซื้อ" หรือ "ไม่ซื้อ"
- แสดงค่าความมั่นใจ (confidence %)
- แสดงโมเดลที่ใช้ (SVM หรือ ANN)
- **ถ้าผล = "ซื้อ"** → แสดงปุ่ม "วิเคราะห์ประเภทเชื้อเพลิง →" (ไปหน้า `/predict/fuel`)
- **ถ้าผล = "ไม่ซื้อ"** → ไม่แสดงปุ่มนี้ (ซ่อนไว้ ตาม Use Case <<extend>>)
- ปุ่ม: "ดู Dashboard" (ไปหน้า `/dashboard`)
- บันทึกผลลงฐานข้อมูล Firebase

### หน้า 5: พยากรณ์ประเภทเชื้อเพลิง (`/predict/fuel`)
- ต้อง login + ต้องผ่านผลลัพธ์ "ซื้อ" ก่อน
- ฟอร์มแบ่ง 2 ส่วน:

**ส่วนที่ 1 — พฤติกรรมการใช้งานรถยนต์:**
| ฟิลด์ | ประเภท | ตัวเลือก |
|-------|--------|---------|
| ลักษณะการใช้งาน | select | ขับในเมือง, ขับนอกเมือง, ทั้งในและนอกเมือง |
| ความถี่ใช้รถ | select | เป็นครั้งคราว, 1-2 วัน/สัปดาห์, 3-4 วัน/สัปดาห์, 5-6 วัน/สัปดาห์, ทุกวัน |
| ระยะทางเฉลี่ยต่อวัน | select | น้อยกว่า 10 กม., 10-30, 31-50, 51-70, 71-90, 90+ |
| ประสบการณ์รถที่เคยใช้ | select | สันดาป, ไฮบริด, ไฟฟ้า |

**ส่วนที่ 2 — ทัศนคติและความกังวล:**
| ฟิลด์ | ประเภท | ตัวเลือก |
|-------|--------|---------|
| สิ่งสำคัญในการเลือกซื้อ | checkbox (เลือกได้หลายข้อ) | ราคา, ผ่อนชำระ, ค่าน้ำมัน, ค่าไฟฟ้า, ค่าซ่อมบำรุง, สมรรถนะ, ดีไซน์, เทคโนโลยี, ความคุ้มค่า, การรับประกัน |
| ความใส่ใจด้านเทคโนโลยีและสิ่งแวดล้อม | select | 5=มากที่สุด, 4=มาก, 3=ปานกลาง, 2=น้อย, 1=น้อยที่สุด |
| ความกังวลเรื่องราคาขายต่อและค่าบำรุงรักษา | select | 5-1 (เหมือนข้อบน) |

- ปุ่ม: "วิเคราะห์ประเภทรถ" → POST ไป Flask API

### หน้า 6: ผลพยากรณ์ประเภทรถ (`/result/fuel`)
- แสดงผล: รถยนต์ประเภทไหนเหมาะสมที่สุด (ไฟฟ้า / ไฮบริด / สันดาป)
- แสดง % ความเหมาะสมของแต่ละประเภท (เรียงจากมากไปน้อย)
- ติดแท็ก "แนะนำ" ที่ประเภทอันดับ 1
- แสดงค่าความมั่นใจ, โมเดลที่ใช้
- ปุ่ม: "ดู Dashboard สรุปผล" (ไปหน้า `/dashboard`)
- บันทึกผลลงฐานข้อมูล Firebase

### หน้า 7: Dashboard (`/dashboard`)
- แสดงผลลัพธ์รถยนต์ที่ระบบแนะนำ (เด่นชัด)
- กราฟวงกลม: สัดส่วนความเหมาะสม EV / Hybrid / ICE
- กราฟแท่ง: เปรียบเทียบค่าใช้จ่าย (ค่าเชื้อเพลิง, ค่าบำรุงรักษา, ค่าประกัน)
- คะแนนความสอดคล้องกับพฤติกรรม (ประหยัดพลังงาน, ความสะดวก, ค่าบำรุง, มูลค่าขายต่อ)
- ข้อความสรุปเหตุผลแนะนำ
- ใช้ Chart.js สำหรับสร้างกราฟ (ทดแทน Power BI ในเวอร์ชันเว็บ)

---

## 🔌 Flask API Routes

```python
# Auth
POST /register          # สมัครสมาชิก
POST /login             # เข้าสู่ระบบ
GET  /logout            # ออกจากระบบ

# Pages (render template)
GET  /predict/buy       # แสดงฟอร์มพยากรณ์ซื้อ/ไม่ซื้อ
GET  /predict/fuel      # แสดงฟอร์มพยากรณ์ประเภทเชื้อเพลิง
GET  /dashboard         # แสดง Dashboard

# API (รับ-ส่งข้อมูล)
POST /api/predict/buy   # รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → คืนผลลัพธ์ ซื้อ/ไม่ซื้อ
POST /api/predict/fuel  # รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → คืนผลลัพธ์ ประเภทรถ
GET  /api/dashboard     # ดึงข้อมูลสำหรับ Dashboard จาก Firebase
```

---

## 🗂 Class Diagram (7 คลาส)

```
class User:
    - user_id: String
    - username: String
    - password: String (hashed)
    + register(): void
    + login(): Boolean

class InputData:
    - distance_per_day: Float
    - budget: Integer
    - fuel_type_pref: String
    - travel_frequency: Integer
    + validate(): Boolean

class FlaskAPI:
    + receive_request(data): Response
    + send_result(result): Response
    + save_history(data): Boolean

class Model:
    - model_type: String       # "SVM" หรือ "ANN"
    - trained_params: Object
    + load_model(): void
    + predict(features): String

class PredictionResult:
    - recommended_type: String  # "ซื้อ"/"ไม่ซื้อ" หรือ "EV"/"Hybrid"/"ICE"
    - prediction_date: Date
    - confidence: Float
    + get_result(): String

class FirebaseDatabase:
    - connection_status: Boolean
    + connect(): void
    + save_record(...): Boolean
    + get_report(...): Object

class Dashboard:           # Chart.js แทน Power BI
    + fetch_data(): Object
    + render_charts(): void
```

---

## 🤖 ML Model Details

### โมเดลที่ 1: ซื้อ/ไม่ซื้อ (Binary Classification)
- Input features: ข้อมูลจากฟอร์มหน้า predict_buy (encode เป็นตัวเลข)
- Output: 0 = ไม่ซื้อ, 1 = ซื้อ
- เปรียบเทียบ SVM (kernel=RBF) vs ANN (ReLU + Softmax)
- เลือกโมเดลที่ Accuracy สูงกว่า
- Train/Test split: 80/20
- ใช้ SMOTE แก้ class imbalance

### โมเดลที่ 2: ประเภทเชื้อเพลิง (Multi-class Classification)
- Input features: ข้อมูลจากฟอร์มหน้า predict_fuel
- Output: 0 = สันดาป(ICE), 1 = ไฮบริด(HEV), 2 = ไฟฟ้า(BEV)
- เปรียบเทียบ SVM vs ANN
- Output layer: 3 nodes + Softmax
- ใช้ SMOTE แก้ class imbalance

### Data Preprocessing Pipeline:
1. จัดการค่า missing → ค่าเฉลี่ย (ตัวเลข) / ฐานนิยม (หมวดหมู่)
2. Encode ข้อมูลหมวดหมู่ → ตัวเลข (Label Encoding)
3. Min-Max Scaling → ทุกค่าอยู่ระหว่าง 0-1
4. ตรวจ outlier → ใช้ median แทนที่
5. Feature selection → Chi-square (หมวดหมู่) / Correlation (ตัวเลข)
6. SMOTE → สร้างข้อมูลสังเคราะห์ให้ class สมดุล

### Model Evaluation:
- Accuracy, Precision, Recall, F1-Score
- Confusion Matrix

---

## 🔥 Firebase Structure

```
Firestore Collections:

users/
  └── {user_id}/
      ├── username: String
      ├── created_at: Timestamp

predictions/
  └── {prediction_id}/
      ├── user_id: String
      ├── type: "buy" | "fuel"
      ├── input_data: Map
      ├── result: String
      ├── confidence: Number
      ├── model_used: String
      ├── created_at: Timestamp
```

---

## 📋 requirements.txt

```
flask
flask-login
firebase-admin
scikit-learn
tensorflow
pandas
numpy
joblib
imbalanced-learn
gunicorn
```

---

## ⚡ สิ่งสำคัญที่ต้องทำ (สรุป)

### Phase 1: Frontend (HTML/CSS/Bootstrap 5) ← ทำตอนนี้
1. สร้าง base.html (navbar + footer + Bootstrap CDN)
2. สร้างหน้า login.html, register.html
3. สร้างหน้า predict_buy.html (ฟอร์มตัวเลือกตามแบบสอบถาม)
4. สร้างหน้า predict_fuel.html
5. สร้างหน้า result_buy.html, result_fuel.html
6. สร้างหน้า dashboard.html (ใช้ Chart.js + ข้อมูลจำลอง)

### Phase 2: Backend Skeleton (Flask) ← ทำตอนนี้
1. สร้าง app.py (routes ทั้งหมด)
2. เชื่อมต่อ Firebase Auth + Firestore
3. สร้าง API endpoint รับ-ส่งข้อมูลพยากรณ์
4. ใช้ mock prediction (ผลจำลอง) แทนโมเดลจริง
5. สร้าง models/predictor.py พร้อม flag USE_MOCK
6. บันทึกผลลง Firebase

### Phase 3: ML Model ← ทำทีหลัง (พอได้ข้อมูล 500 ชุด)
1. สร้าง train_model.py
2. Preprocessing pipeline (encode, scale, SMOTE)
3. Train SVM + ANN ทั้ง 2 โมเดล
4. เปรียบเทียบ Accuracy → เลือกตัวที่ดีกว่า
5. Export เป็น .pkl (joblib)
6. เปลี่ยน USE_MOCK = False → ระบบใช้โมเดลจริง

### Phase 4: Integration + Deploy ← ทำทีหลัง
1. ทดสอบ flow ทั้งหมดกับโมเดลจริง
2. Dashboard ดึงข้อมูลจริงจาก Firebase
3. Deploy

---

## 🎨 Design Notes

- **ดู DESIGN_GUIDELINE.md สำหรับรายละเอียด Design ทั้งหมด**
- ถอดแบบจาก Toyota.com — Automotive Premium, สะอาด, น่าเชื่อถือ
- ธีม: Light mode (พื้นขาว-เทา) สี accent แดง Toyota-style
- ภาษาทั้งหมดเป็นภาษาไทย
- Responsive: รองรับ Desktop + Mobile
- ใช้ Bootstrap 5 grid system
- Font: Noto Sans Thai (Google Fonts)
- กราฟ Dashboard: ใช้ Chart.js (pie chart, bar chart)
- Navbar: ขาว sticky, เส้นใต้แดง active
- Hero: รูปรถใหญ่ + gradient overlay
- Card: ขอบบาง เงาเบา มุมโค้งน้อย (4-8px)
- ปุ่ม: เหลี่ยมเล็กน้อย (radius 4px), CTA สีแดง

---

## ⚠️ สถานะปัจจุบัน: โครงร่าง (Skeleton Mode)

**ยังไม่มีข้อมูลแบบสอบถาม 500 ชุด** (กำหนดเก็บ มี.ค. - ก.ค. 2569)
ดังนั้นให้สร้างโครงร่างทั้งระบบไว้ก่อน โดย:

### สิ่งที่ต้องทำตอนนี้:
1. ✅ Frontend ทุกหน้า (HTML/CSS/Bootstrap) — ทำเต็ม ใช้งานได้จริง
2. ✅ Flask routes + โครงสร้าง Backend — ทำเต็ม
3. ✅ Firebase Auth (สมัคร/เข้าสู่ระบบ) — เชื่อมจริง
4. ✅ Firebase Firestore (บันทึกผล) — เชื่อมจริง
5. ✅ Dashboard (Chart.js) — ทำเต็ม แต่ใช้ข้อมูลจำลอง
6. ⏳ ML Model — **ใช้ mock prediction ไปก่อน** (return ผลสุ่มหรือค่าตายตัว)

### Mock Prediction Logic (ใช้ชั่วคราวแทนโมเดลจริง):
```python
# ใน app.py — แทนที่ model.predict() ด้วย placeholder
def mock_predict_buy(input_data):
    """ผลจำลอง: ซื้อ/ไม่ซื้อ — ใช้ชั่วคราวจนกว่าจะมีโมเดลจริง"""
    return {
        "result": "ซื้อ",          # ค่าตายตัว หรือ random
        "confidence": 0.875,       # ค่าจำลอง
        "model_used": "SVM (mock)" # ระบุว่าเป็น mock
    }

def mock_predict_fuel(input_data):
    """ผลจำลอง: ประเภทเชื้อเพลิง — ใช้ชั่วคราว"""
    return {
        "result": "ไฟฟ้า (EV)",
        "scores": {"EV": 78, "Hybrid": 65, "ICE": 42},
        "confidence": 0.78,
        "model_used": "ANN (mock)"
    }
```

### สิ่งที่ทำทีหลัง (พอได้ข้อมูล 500 ชุด):
1. นำข้อมูลจริงมา train โมเดล SVM + ANN
2. เปรียบเทียบ Accuracy → เลือกตัวที่ดีกว่า
3. Export เป็น .pkl แล้ววางใน /models/
4. เปลี่ยน mock_predict → model.predict() จริง
5. Dashboard ดึงข้อมูลจริงจาก Firebase แทนข้อมูลจำลอง

### เตรียมไว้ให้เปลี่ยนง่าย:
- แยก function predict ไว้ในไฟล์ `models/predictor.py`
- ใส่ flag `USE_MOCK = True` ไว้ใน config.py
- พอโมเดลจริงพร้อม แค่เปลี่ยน `USE_MOCK = False` ระบบจะสลับไปใช้โมเดลจริงอัตโนมัติ

---

## 📝 หมายเหตุเพิ่มเติม

- Use Case สำคัญ: ฟังก์ชัน "พยากรณ์ประเภทเชื้อเพลิง" เป็น <<extend>> ของ "พยากรณ์ซื้อ/ไม่ซื้อ" → จะเรียกได้ก็ต่อเมื่อผล = "ซื้อ" เท่านั้น
- ทุกหน้าต้องทำงานได้จริง (กดปุ่มแล้วไปหน้าถัดไป, แสดงผลลัพธ์) แม้จะยังเป็น mock data
