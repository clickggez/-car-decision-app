"""
เทรน BUY ใหม่บนชุด n786 = n514 + รอบเก็บเพิ่ม 28 ก.ย. 2569 (272 คน, คนทั่วไป ส่วนใหญ่ไม่มีรถ)
ผู้ใช้สั่ง 2026-09-28 ("ไฟล์ตอบกลับมาใหม่แล้ว ... เทรนมาที่คุยกันไว้")

โปรโตคอล — ล็อกก่อนรัน ห้ามแก้หลังเห็นผล
  - ใช้ train_models.train_buy() เดิมทุกอย่าง (คัดฟีเจอร์ Chi-square/ANOVA alpha 0.1, Bagging, 20 splits seed 42 test 20%)
  - เทรนลง car-dss/_models_2026-09-28_buy_n786/ ไม่แตะ car-dss/models/*.pkl · FUEL ไม่เทรนใหม่ (ยังเป็น n630)
  - เกณฑ์ขึ้นเว็บ: lift (acc − baseline) ของ n786 ต้อง "มากกว่า" +0.0505 ของ BUY n514 ปัจจุบัน
    เทียบที่ lift ไม่ใช่ accuracy เพราะสัดส่วนคลาสต่างกัน (AGENTS.md)
  - รายงานแยกตามที่มาของแถว (n514 เดิม / รอบใหม่ 272) บน test fold ของ 20 splits เดียวกัน
    ตามที่ codex แนะนำในห้องประชุม #33 — ไม่ใช้เลขรวมอย่างเดียว
  - ข้อจำกัดเดิม: เติมค่าหาย/คัดฟีเจอร์จากข้อมูลทั้งชุดก่อนแบ่ง split (ห้องประชุม #40) → เลขอาจสูงกว่าจริงเล็กน้อย
"""
import sys, os, glob
_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
OUT = os.path.join(CAR, "_models_2026-09-28_buy_n786")
os.environ["CARDSS_MODEL_DIR"] = OUT
sys.path.insert(0, CAR)
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, pandas as pd, joblib, hashlib
from sklearn.base import clone
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, cohen_kappa_score
import train_models as tm

F = os.path.join(_HERE, "..", "files")
P514 = os.path.join(F, "archive_2026-09-28", "survey_2026-09-27_n514.csv")
PNEW = glob.glob(os.path.join(F, "user_from_archive", "28_9_2569*.csv"))[0]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

if __name__ == "__main__":
    print(__doc__)
    a, b = pd.read_csv(P514), pd.read_csv(PNEW)
    b.columns = a.columns
    df = pd.concat([a, b], ignore_index=True)
    df = df.drop(columns=[c for c in df.columns if str(c).strip().startswith("คอลัมน์") and df[c].isna().all()])
    src = np.array(["n514"] * len(a) + ["รอบใหม่"] * len(b))
    print(f"n514 SHA-256 {sha(P514)}\nรอบใหม่ SHA-256 {sha(PNEW)}\nรวม {len(df)} แถว\n")
    tm.train_buy(df)

    bundle = joblib.load(os.path.join(OUT, "buy_model.pkl"))
    X, y = tm.build_buy_xy(df)
    s = src[X.index.values] if len(X) == len(df) else src[:len(X)]
    X = X[bundle["cat_cols"] + bundle["num_cols"]]
    base = y.value_counts(normalize=True).max()
    print(f"\n=== สรุป BUY n786 · baseline {base:.4f} · ฟีเจอร์ {bundle['feature_cols'] and bundle['cat_cols'] + bundle['num_cols']}")
    acc, per = [], {"n514": [], "รอบใหม่": []}
    for tr, te in StratifiedShuffleSplit(20, test_size=0.2, random_state=42).split(X, y):
        p = clone(bundle["pipeline"]).fit(X.iloc[tr], y.iloc[tr]).predict(X.iloc[te])
        acc.append(accuracy_score(y.iloc[te], p))
        for k in per:
            m = s[te] == k
            per[k].append(accuracy_score(y.iloc[te][m], p[m]))
    acc = np.array(acc)
    print(f"accuracy {acc.mean():.4f} ± {acc.std():.4f} · lift {acc.mean() - base:+.4f} (เกณฑ์: ต้อง > +0.0505)")
    for k, v in per.items():
        yk = y[s == k]
        print(f"  แถวจาก {k:7s}: acc {np.mean(v):.4f} ± {np.std(v):.4f} · baseline ของกลุ่มนี้ {yk.value_counts(normalize=True).max():.4f}")
    print("\nผ่านเกณฑ์ขึ้นเว็บ" if acc.mean() - base > 0.0505 else "\nไม่ผ่านเกณฑ์ — คง BUY n514 ไว้")
