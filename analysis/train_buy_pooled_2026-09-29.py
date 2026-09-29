"""
เทรน BUY บนชุดผสม = ชุดเดิม n500 (ก.ค.–ส.ค. 2569) + ชุด n514 (27 ก.ย.) — ผู้ใช้สั่ง 2026-09-29
("ถ้าไม่ใช่เพราะคำถาม EV ก็เอาผสมกันแล้วเทรนเลย")
ที่มา: ชุดเดิมตัดคำถาม EV แล้ว BUY ยัง lift +0.0735 (analysis/diagnose_newdata_2026-09-26.txt) · n514 lift +0.0505

โปรโตคอล — ล็อกก่อนรัน ห้ามแก้หลังเห็นผล
  - ใช้เฉพาะคำถามร่วม: train_models.build_buy_xy() ดึงคอลัมน์ด้วยชื่อหัวคอลัมน์ คำถาม EV/TPB/NEP ของชุดเดิมไม่ถูกใช้
  - ใช้ train_models.train_buy() เดิมทุกอย่าง (คัดฟีเจอร์ Chi-square/ANOVA alpha 0.1, Bagging, 20 splits seed 42 test 20%)
  - เทรนลง car-dss/_models_2026-09-29_buy_pooled/ ไม่แตะ car-dss/models/*.pkl · FUEL ไม่เกี่ยว
  - เกณฑ์ "ผสมแล้วดีขึ้นจริง" ต้องผ่านครบ 3 ข้อ:
      (1) lift รวมของชุดผสม > +0.0505 (BUY n514 บนเว็บปัจจุบัน)
      (2) บนแถวของชุด n514 ใน test fold เดียวกัน: acc − baseline ของ n514 (0.5078) > +0.0505
          = คนแบบชุดใหม่ต้องได้ผลดีขึ้นจริง ไม่ใช่เลขรวมสูงเพราะชุดเดิมพาไป
      (3) ทายข้ามชุด: fit โครงเดียวกันบนชุดเดิมทั้งหมด → ทายชุด n514 ได้ lift > 0 (สัญญาณย้ายข้ามชุดได้จริง)
          (ห้องประชุม #33: ผสมแล้วโมเดลอาจแค่จำที่มาของแถว — ข้อ 3 กันเรื่องนี้)
  - รายงานกลับทิศ (n514 → ชุดเดิม) ด้วยเพื่อความครบ แต่ไม่ใช้เป็นเกณฑ์
  - ข้อจำกัดเดิม: เติมค่าหาย/คัดฟีเจอร์จากข้อมูลทั้งชุดก่อนแบ่ง split (ห้องประชุม #40) → เลขอาจสูงกว่าจริงเล็กน้อย
"""
import sys, os, glob, hashlib
_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
OUT = os.path.join(CAR, "_models_2026-09-29_buy_pooled")
os.environ["CARDSS_MODEL_DIR"] = OUT
sys.path.insert(0, CAR)
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, pandas as pd, joblib
from sklearn.base import clone
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score
import train_models as tm

F = os.path.join(_HERE, "..", "files")
POLD = [f for f in glob.glob(os.path.join(F, "archive_2026-09-26", "*.csv")) if "n511" not in f][0]
PNEW = os.path.join(F, "archive_2026-09-28", "survey_2026-09-27_n514.csv")
BASE_N514, LIFT_N514 = 0.5078, 0.0505


def load(p):
    d = pd.read_csv(p, encoding="utf-8")
    d = d.drop(columns=[c for c in d.columns if str(c).strip().startswith("คอลัมน์") and d[c].isna().all()])
    d.columns = [" ".join(str(c).split()) for c in d.columns]   # ให้หัวคอลัมน์สองชุดตรงกันก่อนต่อกัน
    return d


def lift(y_true, pred):
    return accuracy_score(y_true, pred), y_true.value_counts(normalize=True).max()


if __name__ == "__main__":
    print(__doc__)
    old, new = load(POLD), load(PNEW)
    for name, p in (("ชุดเดิม", POLD), ("n514", PNEW)):
        print(f"{name}: {os.path.basename(p)[:60]}… SHA-256 {hashlib.sha256(open(p,'rb').read()).hexdigest()}")
    df = pd.concat([old, new], ignore_index=True, sort=False)
    src = np.array(["เดิม"] * len(old) + ["n514"] * len(new))
    print(f"รวม {len(df)} แถว\n")
    tm.train_buy(df)

    bundle = joblib.load(os.path.join(OUT, "buy_model.pkl"))
    cols = bundle["cat_cols"] + bundle["num_cols"]
    X, y = tm.build_buy_xy(df)
    X = X[cols]
    assert len(X) == len(df), "build_buy_xy ทิ้งแถว — ต้องจับคู่ที่มาใหม่"
    base = y.value_counts(normalize=True).max()
    print(f"\n=== สรุป BUY ชุดผสม n={len(y)} · baseline {base:.4f} · ฟีเจอร์ที่ผ่านคัด {cols}")

    acc, per = [], {"เดิม": [], "n514": []}
    for tr, te in StratifiedShuffleSplit(20, test_size=0.2, random_state=42).split(X, y):
        p = clone(bundle["pipeline"]).fit(X.iloc[tr], y.iloc[tr]).predict(X.iloc[te])
        acc.append(accuracy_score(y.iloc[te], p))
        for k in per:
            m = src[te] == k
            per[k].append(accuracy_score(y.iloc[te][m], p[m]))
    acc = np.array(acc); L_all = acc.mean() - base
    print(f"(1) รวม: acc {acc.mean():.4f} ± {acc.std():.4f} · lift {L_all:+.4f}  เกณฑ์ > +{LIFT_N514}  → {'ผ่าน' if L_all > LIFT_N514 else 'ไม่ผ่าน'}")
    for k, v in per.items():
        bk = y[src == k].value_counts(normalize=True).max()
        print(f"    แถว{k:5s}: acc {np.mean(v):.4f} ± {np.std(v):.4f} · baseline {bk:.4f} · lift {np.mean(v) - bk:+.4f}")
    L_new = np.mean(per["n514"]) - BASE_N514
    print(f"(2) แถว n514: lift {L_new:+.4f}  เกณฑ์ > +{LIFT_N514}  → {'ผ่าน' if L_new > LIFT_N514 else 'ไม่ผ่าน'}")

    mo, mn = src == "เดิม", src == "n514"
    p_on = clone(bundle["pipeline"]).fit(X[mo], y[mo]).predict(X[mn]); a, b = lift(y[mn], p_on)
    print(f"(3) ทายข้ามชุด เดิม→n514: acc {a:.4f} · baseline {b:.4f} · lift {a - b:+.4f}  เกณฑ์ > 0  → {'ผ่าน' if a - b > 0 else 'ไม่ผ่าน'}")
    p_no = clone(bundle["pipeline"]).fit(X[mn], y[mn]).predict(X[mo]); a2, b2 = lift(y[mo], p_no)
    print(f"    (อ้างอิง) n514→เดิม: acc {a2:.4f} · baseline {b2:.4f} · lift {a2 - b2:+.4f}")
    ok = L_all > LIFT_N514 and L_new > LIFT_N514 and a - b > 0
    print("\nผ่านครบ 3 ข้อ — เสนอผู้ใช้พิจารณาขึ้นเว็บ" if ok else "\nไม่ผ่านครบ 3 ข้อ — คง BUY n514 ไว้")
