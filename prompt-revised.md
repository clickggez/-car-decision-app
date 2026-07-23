# Prompt สำหรับสั่ง AI Agent (เวอร์ชันปรับปรุง)

ทำหน้าที่เป็น Project Manager และ System Architect ผู้เชี่ยวชาญ โปรดตั้งค่าพื้นที่ทำงาน Multi-Agent Orchestration โดยสร้างโครงสร้างโฟลเดอร์และไฟล์ที่สะท้อนถึงสถานะ "เกือบสมบูรณ์ (High Maturity)" ของโปรเจกต์ CarDSS ใช้เครื่องมือจัดการไฟล์ของคุณสร้างไฟล์เหล่านี้ใน root directory ทันที

**หมายเหตุสำคัญ:**
- ใส่วันที่จริงของวันที่สร้างไฟล์ใน `04-handoff.md` (ห้ามใส่คำว่า "ปัจจุบัน" ตรงๆ)
- สร้างทั้งไฟล์ `.cursorrules` และ `.windsurfrules` (เนื้อหาเหมือนกัน) เพื่อรองรับทั้งสอง IDE
- สร้างโฟลเดอร์ `agent-docs` และสร้างไฟล์ทั้ง 5 ไฟล์ตามลำดับด้านล่าง

---

## 1. สร้างไฟล์: `.cursorrules` และ `.windsurfrules` (เนื้อหาเหมือนกัน)

```markdown
# โปรโตคอลการทำงานร่วมกันของ MULTI-AGENT

คุณคือ AI Agent ที่ต้องทำงานร่วมกันในพื้นที่ทำงานนี้ เพื่อป้องกันการหลงลืมบริบท (Context Loss) และการทำงานซ้ำซ้อน คุณ **ต้อง** ปฏิบัติตาม Workflow นี้อย่างเคร่งครัด:

## ⚡ Workflow บังคับ

1. **ก่อนเริ่มงานทุกครั้ง (อ่านตามลำดับนี้):**
   - อ่าน `agent-docs/01-architecture.md` เพื่อเข้าใจสถาปัตยกรรมและข้อห้าม
   - อ่าน `agent-docs/02-design-system.md` เพื่อเข้าใจกฎ UI
   - อ่าน `agent-docs/03-task-board.md` เพื่อเลือกงานที่ต้องทำ
   - อ่าน `agent-docs/04-handoff.md` เพื่อดูว่า Agent ก่อนหน้าทำอะไรทิ้งไว้

2. **ระหว่างทำงาน:**
   - ปฏิบัติตามข้อจำกัดใน `01-architecture.md` และ `02-design-system.md` อย่างเคร่งครัด
   - **ห้าม** แก้ไขสิ่งที่อยู่ในรายการ "เสร็จสิ้นแล้ว" ของ `03-task-board.md` เด็ดขาด เว้นแต่ได้รับคำสั่งอย่างชัดเจน
   - **ห้าม** เปลี่ยน signature ของฟังก์ชัน `predict_buy` และ `predict_fuel`
   - **ห้าม** เปลี่ยน schema ของ `data/cars.json`
   - **ห้าม** สร้าง Templates ใหม่เว้นแต่ได้รับคำสั่งชัดเจน

3. **หลังทำงานเสร็จ (บังคับทำทุกครั้ง):**
   - อัปเดตเครื่องหมายกากบาทใน `03-task-board.md` (ย้าย task จาก To Do → In Progress → Done)
   - เขียนบันทึกไว้ที่ **ด้านบนสุด** ของ `04-handoff.md` พร้อมวันที่จริง, ชื่อ Agent, สิ่งที่ทำ, และขั้นตอนต่อไป
   - ถ้าเจอ bug หรือข้อจำกัดใหม่ ให้เพิ่มใน section "Known Issues" ของ `01-architecture.md`
```

---

## 2. สร้างไฟล์: `agent-docs/01-architecture.md`

```markdown
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

- _(ยังไม่มีรายการ)_
```

---

## 3. สร้างไฟล์: `agent-docs/02-design-system.md`

```markdown
# ระบบดีไซน์และกฎของ UI (Design System & UI Rules)

**ธีม:** สไตล์ Tesla เน้นการตัดทอนสิ่งที่ไม่จำเป็น (Radical Subtraction)
**การปรับใช้:** ควบคุมผ่าน CSS Variables ตามที่กำหนดใน `DESIGN.md` รองรับทั้ง Light Mode และ Dark Mode

## 🎨 ปรัชญาหลัก

1. **มินิมอล (Minimalism):** เน้นการใช้พื้นที่ว่าง (Whitespace) รักษารูปแบบตัวอักษรให้สะอาดตา
2. **เรียบง่าย (Zero Chrome):**
   - ❌ ไม่มีเงา (NO shadows)
   - ❌ ไม่มีการไล่สี (NO gradients)
   - ❌ ไม่มีขอบตกแต่ง (NO decorative borders)
3. **Typography:** ใช้ font stack ที่กำหนดใน `DESIGN.md` เท่านั้น ห้าม import font ใหม่

## 📋 สถานะ Templates (สร้างครบแล้ว - ห้ามสร้างใหม่)

- [x] Home
- [x] Login
- [x] Register
- [x] Dashboard
- [x] Predict Forms (buy / fuel)
- [x] Results
- [x] Admin

**กฎ:** ให้ใช้งานและปรับปรุง templates ที่มีอยู่เท่านั้น หากจำเป็นต้องสร้างหน้าใหม่ ต้องขออนุญาตและเพิ่มใน task board ก่อน
```

---

## 4. สร้างไฟล์: `agent-docs/03-task-board.md`

```markdown
# กระดานจัดการงาน (Task Board - High Maturity Phase)

## ⏳ สิ่งที่ต้องทำ (To Do)

| Priority | Task | Owner | หมายเหตุ |
|----------|------|-------|----------|
| 🔴 High | QA: ทดสอบ Edge cases ใน `predict_buy` form (input ว่าง, ค่าติดลบ, ค่าเกินช่วง) | QA Agent | เริ่มจากงานนี้ก่อน |
| 🔴 High | QA: ทดสอบ Edge cases ใน `predict_fuel` form | QA Agent | |
| 🟡 Medium | Testing: ตรวจสอบ Local Mode (JSON) ทำงานแทน Firebase ได้จริง | QA Agent | simulate Firebase down |
| 🟡 Medium | Optimization: Refactor โค้ดซ้ำซ้อนใน `app.py` (route handlers) | Code Review Agent | |
| 🟢 Low | Docs: เพิ่มตัวอย่าง input/output ใน docstring ของ predict functions | Code Review Agent | |

## 🚀 กำลังดำเนินการ (In Progress)

- _(ยังไม่มี - Agent ถัดไปให้ย้าย task จาก To Do มาที่นี่)_

## ✅ เสร็จสิ้นแล้ว (⚠️ ห้ามรื้อทำใหม่)

- [x] Setup: สร้างเอกสาร multi-agent workflow (`agent-docs/`)
- [x] Backend: การตั้งค่า Flask, Routing, และการเชื่อมต่อ Firebase
- [x] AI: รวม Prediction Engine (`predict_buy`, `predict_fuel`) เข้าสู่ระบบ
- [x] UI/UX: นำระบบดีไซน์แบบ Tesla และ Dark mode มาใช้เต็มรูปแบบ
- [x] Database: จับคู่โครงสร้างและรวมข้อมูล `cars.json`
```

---

## 5. สร้างไฟล์: `agent-docs/04-handoff.md`

```markdown
# บันทึกการส่งมอบงาน (Agent Handoff Log)

> 📌 **Agents:** เขียนบันทึกของคุณไว้ที่ **ด้านบนสุด** ของไฟล์นี้เมื่อทำงานเสร็จในแต่ละครั้ง
> ใช้รูปแบบ template ด้านล่าง และใส่วันที่จริง (YYYY-MM-DD)

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

**วันที่:** [ใส่วันที่จริง เช่น 2026-04-19]
**จาก:** Project Manager Agent
**ถึง:** QA Agent (เริ่มทำงานเป็นคนแรก)

**สิ่งที่ทำไปแล้ว:**
- สร้างโฟลเดอร์ `agent-docs/` พร้อมไฟล์เอกสาร 4 ไฟล์
- สร้าง `.cursorrules` และ `.windsurfrules` ที่ root
- ล็อกกฎทางสถาปัตยกรรม (DO/DO NOT) เพื่อป้องกันการแก้ Logic หลัก Flask/Firebase/AI Models
- จัดลำดับความสำคัญของงาน QA และ Optimization ใน task board

**ไฟล์ที่แก้ไข:**
- `.cursorrules` (สร้างใหม่)
- `.windsurfrules` (สร้างใหม่)
- `agent-docs/01-architecture.md` (สร้างใหม่)
- `agent-docs/02-design-system.md` (สร้างใหม่)
- `agent-docs/03-task-board.md` (สร้างใหม่)
- `agent-docs/04-handoff.md` (สร้างใหม่)

**ขั้นตอนต่อไป:**
- QA Agent: เริ่มจาก task "🔴 High - QA: ทดสอบ Edge cases ใน `predict_buy` form" เป็นงานแรก
- อ่าน `01-architecture.md` ส่วน "ข้อห้ามเด็ดขาด" ก่อนแตะโค้ด

**ข้อควรระวัง:**
- ห้ามแก้ไขสิ่งในรายการ "เสร็จสิ้นแล้ว" ของ task board
- ถ้าเจอ bug ให้เพิ่มใน "Known Issues" ของ `01-architecture.md`
```
