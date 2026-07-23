# 🎨 DESIGN GUIDELINE — CarDSS
# ถอดแบบจาก Toyota.com ปรับให้เข้ากับระบบสนับสนุนการตัดสินใจซื้อรถยนต์
# ใช้คู่กับ CLAUDE_CODE_SPEC.md

---

## 📐 Design Concept

**แนวคิดหลัก:** "Automotive Premium" — ดูเป็นเว็บรถยนต์จริงจัง น่าเชื่อถือ สะอาด
เอา Toyota.com เป็นต้นแบบ แต่ปรับให้เหมาะกับระบบพยากรณ์

**คีย์เวิร์ด:** สะอาด, Premium, น่าเชื่อถือ, ใช้งานง่าย, Professional

---

## 🎨 Color System

### Primary Colors
```css
:root {
  /* พื้นหลังหลัก — ขาวสะอาดแบบ Toyota */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F7F7F7;        /* พื้นหลังเทาอ่อน สำหรับ section สลับ */
  --bg-dark: #1A1A1A;             /* พื้นหลังเข้ม สำหรับ footer/navbar */

  /* สี Brand — แดง Toyota-inspired */
  --brand-primary: #EB0A1E;       /* แดง Toyota */
  --brand-primary-hover: #C40818;  /* แดงเข้มขึ้น hover */
  --brand-primary-light: #FFF0F1;  /* แดงอ่อน สำหรับ background badge */

  /* สีข้อความ */
  --text-primary: #1A1A1A;         /* ดำ — หัวข้อหลัก */
  --text-secondary: #58595B;       /* เทาเข้ม — เนื้อหา */
  --text-muted: #999999;           /* เทาอ่อน — caption, label */
  --text-white: #FFFFFF;

  /* สีเส้นขอบ */
  --border-light: #E5E5E5;
  --border-medium: #CCCCCC;

  /* สีสำหรับประเภทรถยนต์ */
  --color-ev: #00A550;             /* เขียว — รถไฟฟ้า */
  --color-hybrid: #0072CE;         /* น้ำเงิน — ไฮบริด */
  --color-ice: #FF6B00;            /* ส้ม — สันดาป */

  /* สีสถานะ */
  --color-success: #00A550;
  --color-warning: #F5A623;
  --color-danger: #EB0A1E;
  --color-info: #0072CE;
}
```

### Dark Mode (ไม่จำเป็น แต่ถ้าจะทำ)
```css
[data-theme="dark"] {
  --bg-primary: #1A1A1A;
  --bg-secondary: #2D2D2D;
  --text-primary: #FFFFFF;
  --text-secondary: #B3B3B3;
  --border-light: #404040;
}
```

---

## 🔤 Typography

### Font Family
```css
/* ภาษาไทย + อังกฤษ */
--font-heading: 'Noto Sans Thai', 'Toyota Type', 'Helvetica Neue', sans-serif;
--font-body: 'Noto Sans Thai', 'Helvetica Neue', Arial, sans-serif;

/* Google Fonts CDN */
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
```

### Font Sizes (Toyota-style hierarchy)
```css
/* หัวข้อหลัก — ใหญ่ เด่นชัด */
.heading-hero {
  font-size: 48px;       /* Hero banner */
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.heading-1 {
  font-size: 36px;       /* ชื่อหน้า */
  font-weight: 700;
  line-height: 1.2;
}

.heading-2 {
  font-size: 28px;       /* หัวข้อ section */
  font-weight: 600;
  line-height: 1.3;
}

.heading-3 {
  font-size: 20px;       /* หัวข้อย่อย */
  font-weight: 600;
  line-height: 1.4;
}

/* เนื้อหา */
.body-large {
  font-size: 18px;
  font-weight: 400;
  line-height: 1.6;
}

.body-regular {
  font-size: 16px;
  font-weight: 400;
  line-height: 1.6;
}

.body-small {
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5;
}

.caption {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}
```

---

## 📦 Component Design

### 1. Navbar (แบบ Toyota.com)
```
┌──────────────────────────────────────────────────────────────┐
│  🚗 CarDSS       พยากรณ์ซื้อ/ไม่ซื้อ   ประเภทเชื้อเพลิง   Dashboard      👤 Account  │
└──────────────────────────────────────────────────────────────┘
```
- **สไตล์:** พื้นหลังขาว, ขอบล่างเส้นบาง `border-bottom: 1px solid #E5E5E5`
- **โลโก้:** ซ้ายสุด — ไอคอนรถ + "CarDSS"
- **เมนู:** กลาง — ตัวอักษรสีดำ เรียบ ไม่มี background
- **Account:** ขวาสุด — ไอคอน + ชื่อผู้ใช้
- **Hover:** ขีดเส้นใต้สีแดง (`border-bottom: 2px solid var(--brand-primary)`)
- **Active:** ตัวหนา + ขีดเส้นใต้แดง
- **Sticky:** ติดด้านบนเมื่อ scroll (position: sticky)
- **ความสูง:** 64px

```css
.navbar {
  background: #FFFFFF;
  height: 64px;
  border-bottom: 1px solid var(--border-light);
  position: sticky;
  top: 0;
  z-index: 1000;
  padding: 0 40px;
  display: flex;
  align-items: center;
}

.nav-link {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 500;
  text-decoration: none;
  padding: 20px 16px;
  border-bottom: 2px solid transparent;
  transition: border-color 0.2s;
}

.nav-link:hover,
.nav-link.active {
  border-bottom-color: var(--brand-primary);
}
```

### 2. Hero Banner (หน้า Login / หน้าแรก)
```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              [รูปรถยนต์ใหญ่ เต็มจอ]                          │
│                                                              │
│              ระบบสนับสนุนการตัดสินใจ                           │
│                 ซื้อรถยนต์                                    │
│           เขตบางขุนเทียน กรุงเทพมหานคร                        │
│                                                              │
│              [ เข้าสู่ระบบ ]  [ สมัครสมาชิก ]                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
- **รูปพื้นหลัง:** รูปรถยนต์ขนาดใหญ่ + overlay gradient มืด
- **ข้อความ:** กลางจอ ตัวขาว ตัวใหญ่
- **ความสูง:** 100vh (เต็มจอ) หรือ 600px
- **Gradient overlay:** `linear-gradient(to bottom, rgba(0,0,0,0.3), rgba(0,0,0,0.7))`

```css
.hero {
  height: 600px;
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  position: relative;
}

.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, rgba(0,0,0,0.2), rgba(0,0,0,0.6));
}

.hero-content {
  position: relative;
  z-index: 1;
  color: white;
}
```

### 3. Card (Toyota-style vehicle card)
```
┌─────────────────────────┐
│  ⚡ รถยนต์ไฟฟ้า (EV)     │
│                          │
│  ประหยัดค่าใช้จ่าย        │
│  เหมาะกับการขับในเมือง    │
│                          │
│  ████████████░░  78%     │
│                          │
│  [ ดูรายละเอียด ]         │
└─────────────────────────┘
```
- **พื้น:** ขาว
- **ขอบ:** เส้นบางมาก `border: 1px solid #E5E5E5`
- **เงา:** เบามาก `box-shadow: 0 2px 8px rgba(0,0,0,0.06)`
- **มุม:** โค้งเล็กน้อย `border-radius: 8px`
- **Hover:** เงาเพิ่มขึ้น + ยกขึ้นเล็กน้อย

```css
.card {
  background: #FFFFFF;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  padding: 24px;
  transition: box-shadow 0.3s, transform 0.3s;
}

.card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  transform: translateY(-2px);
}
```

### 4. Button (Toyota-style)
```css
/* Primary — แดง Toyota เต็ม */
.btn-primary {
  background: var(--brand-primary);
  color: white;
  border: none;
  padding: 14px 32px;
  border-radius: 4px;       /* Toyota ใช้มุมเหลี่ยมเกือบสี่เหลี่ยม */
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: var(--brand-primary-hover);
}

/* Secondary — ขอบดำ พื้นขาว */
.btn-secondary {
  background: transparent;
  color: var(--text-primary);
  border: 2px solid var(--text-primary);
  padding: 12px 32px;
  border-radius: 4px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: var(--text-primary);
  color: white;
}

/* Ghost — ข้อความอย่างเดียว */
.btn-ghost {
  background: none;
  border: none;
  color: var(--brand-primary);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}
```

### 5. Form / Input (สำหรับฟอร์มพยากรณ์)
```css
.form-group {
  margin-bottom: 24px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.form-control {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-medium);
  border-radius: 4px;
  font-size: 15px;
  font-family: 'Noto Sans Thai', sans-serif;
  color: var(--text-primary);
  background: #FFFFFF;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-control:focus {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px var(--brand-primary-light);
  outline: none;
}

/* Select dropdown */
.form-select {
  appearance: none;
  background-image: url("data:image/svg+xml,...chevron-down...");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 40px;
}
```

### 6. Section Headers (แบ่ง section ชัด)
```css
/* เส้นแดงข้างซ้าย สำหรับแบ่ง section ในฟอร์ม */
.section-header {
  border-left: 4px solid var(--brand-primary);
  padding: 12px 16px;
  background: var(--bg-secondary);
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 24px;
}

/* แบบ EV section */
.section-header--ev {
  border-left-color: var(--color-ev);
}

/* แบบ Hybrid section */
.section-header--hybrid {
  border-left-color: var(--color-hybrid);
}
```

---

## 📐 Layout ทุกหน้า

### หน้า Login
```
┌─ Navbar ──────────────────────────────────────────────┐
├─ Hero Banner (รูปรถใหญ่ + gradient overlay) ───────────┤
│                                                       │
│    ┌─ Login Card (กลางจอ, max-width: 440px) ──────┐    │
│    │  🚗 CarDSS                                   │    │
│    │  ระบบสนับสนุนการตัดสินใจซื้อรถยนต์              │    │
│    │                                              │    │
│    │  [ชื่อผู้ใช้                              ]    │    │
│    │  [รหัสผ่าน                               ]    │    │
│    │  [ ■ เข้าสู่ระบบ ]                            │    │
│    │                                              │    │
│    │  ยังไม่มีบัญชี? สมัครสมาชิก                     │    │
│    └──────────────────────────────────────────────┘    │
│                                                       │
├─ Footer ──────────────────────────────────────────────┤
└───────────────────────────────────────────────────────┘
```

### หน้าฟอร์มพยากรณ์
```
┌─ Navbar ──────────────────────────────────────────────┐
├───────────────────────────────────────────────────────┤
│  max-width: 800px, margin: auto                       │
│                                                       │
│  📋 พยากรณ์การตัดสินใจซื้อรถยนต์                       │
│  กรอกข้อมูลเพื่อให้ระบบวิเคราะห์                       │
│                                                       │
│  ┌─ Section: ข้อมูลส่วนบุคคล (เส้นแดงข้างซ้าย) ────┐   │
│  │                                                 │   │
│  │  [เพศ          ▼]    [อายุ          ▼]           │   │
│  │  [อาชีพ        ▼]    [รายได้        ▼]           │   │
│  │  [ที่พักอาศัย   ▼]    [จอดรถ        ▼]           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ Section: ปัจจัยเลือกซื้อ (เส้นส้มข้างซ้าย) ────┐   │
│  │                                                 │   │
│  │  [งบประมาณ     ▼]    [ข้อกังวล     ▼]           │   │
│  │  [วัตถุประสงค์  ▼]    [สมาชิกครอบครัว ▼]          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                       │
│  [ ■ วิเคราะห์ผล ]                                    │
│                                                       │
├─ Footer ──────────────────────────────────────────────┤
└───────────────────────────────────────────────────────┘
```
- ฟอร์ม 2 คอลัมน์ (Bootstrap `col-md-6`)
- บน Mobile เป็น 1 คอลัมน์

### หน้าผลพยากรณ์
```
┌─ Navbar ──────────────────────────────────────────────┐
├───────────────────────────────────────────────────────┤
│  max-width: 600px, margin: auto, text-align: center   │
│                                                       │
│         ┌────────────┐                                │
│         │    ✅      │  วงกลมใหญ่ + ไอคอน             │
│         └────────────┘                                │
│                                                       │
│         แนะนำ: ซื้อรถยนต์                              │
│         ความมั่นใจ 87.5%                               │
│                                                       │
│    ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐             │
│    │ 87.5%│  │ SVM  │  │ สูง  │  │ 4.2  │  stat cards │
│    └──────┘  └──────┘  └──────┘  └──────┘             │
│                                                       │
│    [ ■ วิเคราะห์ประเภทเชื้อเพลิง → ]                   │
│    [ □ ดู Dashboard ]                                  │
│                                                       │
├─ Footer ──────────────────────────────────────────────┤
└───────────────────────────────────────────────────────┘
```

### หน้า Dashboard
```
┌─ Navbar ──────────────────────────────────────────────┐
├───────────────────────────────────────────────────────┤
│  max-width: 1000px, margin: auto                      │
│                                                       │
│  ┌─ Result Banner (เขียว) ─────────────────────────┐   │
│  │  ⚡ ผลลัพธ์: คุณเหมาะสมกับ รถยนต์ไฟฟ้า (EV)      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                       │
│  ┌─ Pie Chart ────┐  ┌─ Bar Chart ────────────────┐   │
│  │  สัดส่วน        │  │  เปรียบเทียบค่าใช้จ่าย      │   │
│  │  ความเหมาะสม    │  │  EV vs Hybrid vs ICE      │   │
│  │   🟢78% EV     │  │  ████ ██ █               │   │
│  │   🔵17% Hybrid │  │                           │   │
│  │   🟠5% ICE     │  │                           │   │
│  └────────────────┘  └────────────────────────────┘   │
│                                                       │
│  ┌─ Score Cards (คะแนนสอดคล้อง) ────────────────────┐  │
│  │  ■ 92 ประหยัด  ■ 75 สะดวก  ■ 88 บำรุง  ■ 60 ขายต่อ│  │
│  └──────────────────────────────────────────────────┘  │
│                                                       │
│  ┌─ สรุปเหตุผล ────────────────────────────────────┐   │
│  │  ข้อสรุป: แนะนำ EV เนื่องจาก...                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                       │
├─ Footer ──────────────────────────────────────────────┤
└───────────────────────────────────────────────────────┘
```

---

## 📱 Responsive Breakpoints

```css
/* Desktop */
@media (min-width: 992px) {
  .container { max-width: 960px; }
  .form-grid { grid-template-columns: 1fr 1fr; }
}

/* Tablet */
@media (min-width: 768px) and (max-width: 991px) {
  .container { max-width: 720px; }
  .form-grid { grid-template-columns: 1fr 1fr; }
}

/* Mobile */
@media (max-width: 767px) {
  .container { padding: 0 16px; }
  .form-grid { grid-template-columns: 1fr; }  /* 1 คอลัมน์ */
  .heading-hero { font-size: 28px; }
  .hero { height: 400px; }
  .navbar { padding: 0 16px; }
}
```

---

## 🖼 รูปภาพที่ต้องใช้

| ตำแหน่ง | รูปภาพ | แนะนำ |
|---------|--------|------|
| Hero Banner หน้า Login | รูปรถยนต์ขนาดใหญ่ | ใช้รูปฟรีจาก Unsplash (ค้นหา "car road thailand") |
| ไอคอน EV | ⚡ หรือ SVG icon | ใช้ Bootstrap Icons / Lucide |
| ไอคอน Hybrid | 🔋 หรือ SVG icon | |
| ไอคอน ICE | ⛽ หรือ SVG icon | |
| โลโก้ CarDSS | SVG | สร้างเอง — รูปรถ + ตัวอักษร |
| พื้นหลัง Dashboard | - | ใช้สีพื้นเทาอ่อน `#F7F7F7` |

---

## ✨ Animation & Interaction

```css
/* Fade in เมื่อโหลดหน้า */
.fade-in {
  animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Progress bar แบบ animate */
.progress-bar {
  transition: width 1s ease-out;
}

/* Card hover lift */
.card-hover:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.1);
}

/* Button ripple effect */
.btn-primary:active {
  transform: scale(0.97);
}
```

---

## 📝 สรุปจุดเด่น Toyota.com ที่นำมาใช้

1. **Navbar ขาวสะอาด** — sticky, เส้นใต้แดงเมื่อ hover/active
2. **Hero ภาพใหญ่เต็มจอ** — gradient overlay + ข้อความกลาง
3. **พื้นหลังขาว-เทาสลับ** — ทำให้ section แยกชัด ไม่จำเจ
4. **Card เรียบ มุมน้อย** — border-radius: 4-8px ไม่โค้งมาก
5. **ปุ่มเหลี่ยมเล็กน้อย** — border-radius: 4px (ไม่กลมเหมือนเว็บทั่วไป)
6. **สีแดงเป็น accent** — ใช้แค่ปุ่ม CTA หลัก, เส้น active, ลิงก์สำคัญ
7. **Typography ชัด** — หัวข้อใหญ่มาก, body อ่านง่าย, spacing เยอะ
8. **Whitespace เยอะ** — ไม่อัดแน่น ให้หายใจ
9. **Grid 2 คอลัมน์** — การ์ดรถเรียง 2-3 คอลัมน์
10. **Hover มีชีวิต** — ยกขึ้น, เงาเพิ่ม, เส้นใต้ปรากฏ
