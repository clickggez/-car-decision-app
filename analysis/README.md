# สคริปต์วิเคราะห์เพิ่มเติม (Reproducibility)

สคริปต์ในโฟลเดอร์นี้ใช้ผลิตตัวเลขทุกตัวที่อ้างอิงใน
`agent-docs/รายงานเสนออาจารย์_ทบทวนวรรณกรรม_2026-08-02.md`
เก็บไว้เพื่อให้ทำซ้ำผลได้ (reproducible) หากกรรมการสอบขอตรวจสอบ

## วิธีรัน

```
cd C:\Users\click\Desktop\car-decision-app\analysis
python <ชื่อสคริปต์>.py
```

ทุกสคริปต์ใช้ path แบบสัมพัทธ์ (อ้างอิงจากตำแหน่งไฟล์เอง) จึงย้ายโฟลเดอร์โปรเจกต์ได้
และ **ไม่แก้ไข `.pkl` ที่ deploy อยู่** — เป็นการวิเคราะห์อย่างเดียว

## รายการสคริปต์

| ไฟล์ | หน้าที่ | อ้างอิงในรายงานหัวข้อ |
|---|---|---|
| `ablation.py` | เทียบผลระหว่างฟีเจอร์เดิม vs เดิม+คำถามใหม่ 10 ข้อ บนข้อมูลชุดเดียวกัน | 2 |
| `quality_screen.py` | ตรวจคุณภาพการตอบ (straight-lining, longstring, NEP attention check) | 7.3 |
| `sensitivity.py` | เทียบผลก่อน/หลังคัดผู้ที่ไม่ผ่าน attention check | 7.3 |
| `alt_framing.py` | ตัวชี้วัดทางเลือก (balanced acc, macro F1, ROC-AUC, top-2) | 4 |
| `full_analysis.py` | การวิเคราะห์ 8 รายการ (nested CV, selective, learning curve, pairwise, hierarchical, ordinal, confident learning, clustering) | 7.5 |
| `cl_correct.py` | Confident Learning เวอร์ชันถูกต้องตามระเบียบวิธี | 7.5 (7) |
| `compare_datasets.py` | เทียบชุดข้อมูลเก่า n=715 กับใหม่ n=500 ด้วยวิธีวัดเดียวกัน | 7.6 |
| `fuel_binary.py` | เทียบ FUEL 3 คลาส vs 2 คลาส (EV+Hybrid vs ICE) — 2 คลาสได้ accuracy สูงกว่า 11.25 จุดและชนะ baseline แต่ kappa/ROC-AUC ลดลง = ได้จากโจทย์ง่ายลง ผล: `fuel_binary_2026-08-09.txt` | 4 |
| `alt_framing_bagging_2026-08-09.txt` | ผลของ `alt_framing.py` ด้วยโมเดลชุดปัจจุบัน — **top-2 accuracy 0.7523 แพ้ baseline ของ top-2 (0.7848) ห้ามใช้** · ROC-AUC FUEL 0.5837 / BUY 0.7203 | 4 |
| `selective_calibration.py` | selective classification (coverage 50/70/90 ตรึงเท่า `full_analysis.py`) + calibration/ECE ของโมเดลชุดปัจจุบัน — **BUY ใช้ selective ได้ (0.7800 ที่ 50%) แต่ FUEL ใช้ไม่ได้ (accuracy ลดลง)** ผล: `selective_calibration_2026-08-09.txt` | 4, 7.5 |
| `model_health_check.py` | ตรวจสุขภาพโมเดลชุดปัจจุบัน — เสถียร/เดามั่ว/เดาคลาสใหญ่ ด้วย kappa + permutation test + recall รายคลาส + confusion matrix (ผล: `model_health_2026-08-09.txt`) | 4, 7.5 |
| `balanced_results_bagging_2026-08-09.txt` | ผลของ `balanced_subsample.py` หลังเปิด meta-classifier — **เป็นตัวเลขอ้างอิงชุดปัจจุบัน** (ดู `00-READ-FIRST.md` §1) ส่วน `balanced_results.txt` คือชุดเก่าเก็บไว้เทียบ | 7.5 |
| `meta_voting_bagging.py` | เทียบ meta-classifier voting vs bagging vs โมเดลเดี่ยว บน 20 splits (ตามคำสั่งอาจารย์ 2026-08-09) — ผล: bagging ดีที่สุดทุกตัวชี้วัดบน BUY แต่ส่วนต่างไม่มีนัยสำคัญ | — |
| `meta_voting_bagging_results_2026-08-09.txt` | ผลลัพธ์ดิบจาก `meta_voting_bagging.py` | — |
| `run_autoweka_kappa.ps1` | รัน Auto-WEKA ซ้ำด้วย `-metric kappa` (ผลลง `autoweka_results_kappa/`) — หักล้างสมมติฐานว่า `errorRate` คือต้นตอของ kappa ติดลบ | — |
| `fuel_threshold.py` | per-class decision threshold (prior correction) บน FUEL — ผล: ไม่ช่วย (inner CV เลือก alpha=0 ใน 18-20/20 splits) และยืนยันว่าโมเดล sklearn ไม่มีอาการ majority-class collapse (kappa +0.1264) | — |
| `fuel_threshold_results_2026-08-08.txt` | ผลลัพธ์ดิบจาก `fuel_threshold.py` | — |
| `results_8analyses_2026-08-02.txt` | ผลลัพธ์ดิบที่ได้จาก `full_analysis.py` | — |

## ⚠️ ข้อควรระวังเชิงระเบียบวิธีที่บันทึกไว้ในโค้ด

1. **ระดับ coverage ของ selective classification (50%, 70%, 90%) กำหนดตายตัวในโค้ด
   ก่อนรัน** และรายงานครบทุกจุด — ห้ามแก้เป็นค่าที่ให้ตัวเลขสวยที่สุดภายหลัง
   (จะเป็น outcome switching แบบแนบเนียน)

2. **`cl_correct.py` มีไว้แทน `full_analysis.py` ส่วน Confident Learning**
   เวอร์ชันใน `full_analysis.py` คัดตัวอย่างที่ต้องสงสัยออกจาก *ทั้งชุด* แล้ววัดใหม่
   ซึ่งทำให้ได้ 86.7% แบบไม่มีความหมาย (เอาเคสยากออกจาก test ด้วย = circular)
   เวอร์ชันที่ถูกต้องคัดเฉพาะใน train แล้ววัดบน test ที่ไม่ถูกแตะ → ได้ 68.05% (p=0.46)
   **เก็บทั้งสองเวอร์ชันไว้เป็นตัวอย่างประกอบการอภิปรายเรื่องกับดักเชิงระเบียบวิธี**

3. **เหตุผลของ ordinal treatment (ICE < Hybrid < EV ตามระดับการใช้ไฟฟ้า)
   เขียนไว้ในโค้ดก่อนดูผล** ไม่ได้เลือกใช้เพราะเห็นว่าตัวเลขดีขึ้น

4. **การเทียบข้ามชุดข้อมูลต้องเทียบที่ lift ไม่ใช่ accuracy ดิบ** เพราะสัดส่วนคลาส
   ต่างกันทำให้ baseline ต่างกันมาก (ดู `compare_datasets.py`)

## ไฟล์ที่สคริปต์สร้างขึ้น

- `cleaned.csv` — ชุดข้อมูลหลังคัดผู้ไม่ผ่าน attention check (สร้างโดย `quality_screen.py`,
  ใช้ต่อโดย `sensitivity.py`) **ไม่ใช่ข้อมูลหลักของงานวิจัย** เป็นไฟล์ระหว่างทางเท่านั้น
