"""
เทรน BUY จากชุดเดิม n500 เฉพาะคำถามทั่วไป (ไม่ใช้คำถาม EV/TPB/NEP) — ผู้ใช้เลือก "ทาง 1" 2026-09-29
ที่มา: ชุดเดิมตัด EV แล้ว BUY ยัง lift +0.0735 (Bagging DT ไม่จูน, analysis/diagnose_newdata_2026-09-26.txt)
       ผสมกับ n514 ไม่ช่วย (หลักฐานชิ้นที่ 20) จึงใช้ชุดเดิมอย่างเดียว

โปรโตคอล — ล็อกก่อนรัน ห้ามแก้หลังเห็นผล
  - train_models.build_buy_xy() ดึงคอลัมน์ด้วยชื่อหัวคอลัมน์ → คำถาม EV/TPB/NEP ของชุดเดิมไม่ถูกใช้ (ตรวจรายชื่อฟีเจอร์ในผล)
  - train_models.train_buy() เดิมทุกอย่าง (คัดฟีเจอร์ Chi-square/ANOVA alpha 0.1, Bagging, 20 splits seed 42 test 20%)
  - เทรนลง car-dss/_models_2026-09-29_buy_old500/ · FUEL ไม่เกี่ยว (ยังเป็น n630)
  - เกณฑ์ขึ้นเว็บ: lift (acc − baseline) > +0.0505 (BUY n514 ปัจจุบัน) — เทียบที่ lift เพราะสัดส่วนคลาสต่างกัน
  - ⚠️ ต้องให้อาจารย์ยืนยันว่าใช้ข้อมูลรอบเก่าได้ก่อนเอาไปเขียนเล่ม (ผู้ใช้รับทราบ 29 ก.ย.)
  - ข้อจำกัดเดิม: เติมค่าหาย/คัดฟีเจอร์จากข้อมูลทั้งชุดก่อนแบ่ง split (ห้องประชุม #40)
"""
import sys, os, glob, hashlib
_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
OUT = os.path.join(CAR, "_models_2026-09-29_buy_old500")
os.environ["CARDSS_MODEL_DIR"] = OUT
sys.path.insert(0, CAR)
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd, joblib
import train_models as tm

POLD = [f for f in glob.glob(os.path.join(_HERE, "..", "files", "archive_2026-09-26", "*.csv")) if "n511" not in f][0]

if __name__ == "__main__":
    print(__doc__)
    df = pd.read_csv(POLD, encoding="utf-8")
    df = df.drop(columns=[c for c in df.columns if str(c).strip().startswith("คอลัมน์") and df[c].isna().all()])
    print(f"ไฟล์ {os.path.basename(POLD)[:70]}…\nSHA-256 {hashlib.sha256(open(POLD,'rb').read()).hexdigest()}\n{len(df)} แถว\n")
    tm.train_buy(df)
    b = joblib.load(os.path.join(OUT, "buy_model.pkl"))
    m = b["metrics"]
    X, y = tm.build_buy_xy(df)
    base = y.value_counts(normalize=True).max()
    lift = m["test_accuracy_repeated_mean"] - base
    print(f"\n=== สรุป BUY ชุดเดิม n={len(y)} · acc {m['test_accuracy_repeated_mean']:.4f} ± {m['test_accuracy_repeated_std']:.4f}"
          f" · baseline {base:.4f} · lift {lift:+.4f} (เกณฑ์ > +0.0505)")
    print(f"ฟีเจอร์ที่ใช้: {b['cat_cols'] + b['num_cols']}")
    print("ผ่านเกณฑ์" if lift > 0.0505 else "ไม่ผ่านเกณฑ์ — คง BUY n514")
