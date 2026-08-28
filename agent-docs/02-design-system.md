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

---

## 🌙 โหมดมืด (Dark Mode) — อัปเดต 2026-08-28

เว็บมี **2 layout ที่แยกจากกันคนละระบบ** ต้องรู้ก่อนแก้อะไร

| layout | ไฟล์ | ระบบธีม |
|---|---|---|
| เว็บหลัก | `templates/base.html` + `static/css/style.css` | CSS variables + `[data-theme="dark"]` |
| หน้า admin | `templates/admin/base.html` (มี CSS ในตัว) | `[data-theme="dark"]` + **`data-bs-theme` ของ Bootstrap 5.3** |

**ทั้งสอง layout ใช้ `localStorage['theme']` คีย์เดียวกัน** → สลับธีมที่ไหนก็จำข้ามหน้ากันได้
ทั้งคู่มีสคริปต์กันจอกระพริบขาวใน `<head>` (ตั้ง attribute ก่อน render) — **ห้ามย้ายสคริปต์นี้ไปท้ายไฟล์**

### ⛔ ห้ามใช้คลาส Bootstrap ที่บังคับสีตายตัวในหน้า admin

`bg-white` · `table-light` · `bg-light` · `text-dark`

คลาสพวกนี้ **ไม่ตามธีม** จะสว่างจ้าค้างอยู่แม้เปิดโหมดมืด
(เคยพลาดมาแล้วใน `admin/explain.html` — ถอดออกไปแล้ว 2026-08-28)
ให้ปล่อยว่างไว้เฉย ๆ แล้วให้ `data-bs-theme` จัดการเอง

### ค่าสีโหมดมืดที่ใช้ (ตรงกับ `DESIGN.md`)

| บทบาท | ค่า |
|---|---|
| พื้นหลังหลัก | `#0D0D0D` *(ไม่ใช่ `#000` ล้วน)* |
| พื้นผิวรอง / การ์ด | `#1E2127` |
| เส้นขอบ | `#2a2e37` |
| ตัวอักษรหลัก | `#E8E8E8` *(ไม่ใช่ `#FFF` ล้วน)* |

ยังคงกฎเดิมทุกข้อ — **ไม่มีเงา ไม่มีการไล่สี ไม่มีขอบตกแต่ง**
