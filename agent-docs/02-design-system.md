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
