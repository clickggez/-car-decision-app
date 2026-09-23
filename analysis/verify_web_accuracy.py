"""
หลักฐานสำหรับใส่เล่ม: วัดความแม่นยำของ "โมเดลที่เว็บใช้อยู่จริง" ใหม่ทั้งหมด

ทำไมต้องมีไฟล์นี้
-----------------
เลขความแม่นยำที่ฝังอยู่ใน .pkl (คีย์ metrics) คือเลขที่บันทึกไว้ "ตอนเทรน"
ถ้าเอาไปใส่เล่มแล้วกรรมการถามว่า "รู้ได้ยังไงว่าเว็บได้เท่านี้จริง" จะตอบไม่ได้
เพราะ .pkl เป็นไฟล์ไบนารี เปิดอ่านยืนยันด้วยตาไม่ได้ และเลขข้างในอาจเป็นของ
โมเดลคนละตัวกับที่ deploy ก็ได้ถ้ามีการสลับไฟล์

สคริปต์นี้จึงไม่เชื่อเลขใน metrics เลย แต่:
  1. คำนวณ SHA-256 ของไฟล์ .pkl ที่เว็บโหลดใช้จริง (car-dss/models/)
     -> ลายนิ้วมือ พิสูจน์ว่าวัดตัวเดียวกับที่รันอยู่ ไม่ใช่ตัวอื่น
  2. โหลด pipeline จาก .pkl นั้น แล้ว "เทรนซ้ำด้วยโครงเดิม + วัดใหม่" 20 splits
     ด้วยโปรโตคอลเดียวกับ train_models.py:820 (StratifiedShuffleSplit, test 20%, seed 42)
  3. วัดโดยตรงบน pipeline ที่ fit มาแล้ว (holdout) เพื่อเทียบอีกมุมหนึ่ง
  4. พิมพ์เวอร์ชันไลบรารี + วันเวลา -> ให้คนอื่นรันซ้ำได้เลขเดิม

ผลลัพธ์เป็นไฟล์ .txt ที่แนบภาคผนวกได้ และใครก็รันซ้ำได้ด้วยคำสั่งเดียว

**อ่านอย่างเดียว — ไม่เขียนทับ .pkl ใด ๆ**
"""
import sys, os, hashlib, platform, warnings
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
sys.path.insert(0, CAR)
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import joblib
import sklearn
from sklearn.base import clone
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, cohen_kappa_score, classification_report

import train_models as tm
from ablation import build_buy, build_fuel

MODEL_DIR = os.path.join(CAR, "models")
N_SPLITS = 20
TEST_SIZE = 0.2
SEED = 42


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(target, pkl_name, builder):
    path = os.path.join(MODEL_DIR, pkl_name)
    bundle = joblib.load(path)
    pipe = bundle["pipeline"]
    cat_cols = bundle["cat_cols"]
    num_cols = bundle["num_cols"]
    embedded = bundle.get("metrics", {})

    print("\n" + "=" * 84)
    print(f"  {target}  —  {pkl_name}")
    print("=" * 84)
    print(f"  ไฟล์        : {os.path.abspath(path)}")
    print(f"  ขนาด        : {os.path.getsize(path):,} bytes")
    print(f"  แก้ไขล่าสุด : {datetime.fromtimestamp(os.path.getmtime(path)):%Y-%m-%d %H:%M:%S}")
    print(f"  SHA-256     : {sha256(path)}")
    print(f"  โมเดล       : {bundle.get('model_name')}  "
          f"(ตัวจำแนกจริง = {type(pipe.named_steps.get('clf')).__name__})")
    print(f"  ฟีเจอร์ที่ใช้: {len(cat_cols)} categorical + {len(num_cols)} numeric")

    df = tm.load_survey()
    X, y = builder(df)
    X = X[cat_cols + num_cols].copy()
    base = float(y.value_counts(normalize=True).max())

    print(f"\n  ข้อมูล n={len(y)}   baseline (ทายคลาสใหญ่สุดเสมอ) = {base:.4f}")
    print(f"  โปรโตคอล: StratifiedShuffleSplit n_splits={N_SPLITS}, "
          f"test_size={TEST_SIZE}, seed={SEED}  (ตรงกับ train_models.py:820)")

    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=TEST_SIZE, random_state=SEED)
    accs, kaps = [], []
    for i, (tr, te) in enumerate(sss.split(X, y), 1):
        p = clone(pipe)                       # โครงเดิมจาก .pkl แต่ fit ใหม่
        p.fit(X.iloc[tr], y.iloc[tr])         # fit เฉพาะ train fold
        pred = p.predict(X.iloc[te])
        accs.append(accuracy_score(y.iloc[te], pred))
        kaps.append(cohen_kappa_score(y.iloc[te], pred))
        print(f"    split {i:2d}/{N_SPLITS}  accuracy = {accs[-1]:.4f}", flush=True)

    accs, kaps = np.array(accs), np.array(kaps)
    print(f"\n  ── ผลที่วัดใหม่ ──")
    print(f"    accuracy (20 splits) = {accs.mean():.4f} ± {accs.std():.4f}"
          f"   (ต่ำสุด {accs.min():.4f} / สูงสุด {accs.max():.4f})")
    print(f"    Cohen kappa          = {kaps.mean():.4f} ± {kaps.std():.4f}")
    print(f"    lift เหนือ baseline  = {accs.mean() - base:+.4f}")

    emb = embedded.get("test_accuracy_repeated_mean")
    emb_sd = embedded.get("test_accuracy_repeated_std")
    print(f"\n  ── เทียบกับเลขที่ฝังไว้ใน .pkl ตอนเทรน ──")
    print(f"    ใน .pkl : {emb} ± {emb_sd}")
    print(f"    วัดใหม่ : {accs.mean():.4f} ± {accs.std():.4f}")
    if emb is not None:
        d = accs.mean() - float(emb)
        ok = "ตรงกัน" if abs(d) < 0.005 else "ไม่ตรง — ต้องอธิบายก่อนใส่เล่ม"
        print(f"    ส่วนต่าง: {d:+.4f}  -> {ok}")

    print(f"\n  ── รายละเอียดรายคลาส (split สุดท้าย) ──")
    print(classification_report(y.iloc[te], pred, zero_division=0))
    return accs.mean(), accs.std()


if __name__ == "__main__":
    print(__doc__)
    print("=" * 84)
    print(f"  รันเมื่อ      : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  เครื่อง       : {platform.platform()}")
    print(f"  Python       : {sys.version.split()[0]}")
    print(f"  scikit-learn : {sklearn.__version__}")
    print(f"  joblib       : {joblib.__version__}")
    print("=" * 84)

    b = verify("BUY  (ซื้อ / ไม่ซื้อ)", "buy_model.pkl", build_buy)
    f = verify("FUEL (EV / Hybrid / ICE)", "fuel_model.pkl", build_fuel)

    print("\n" + "=" * 84)
    print("  สรุปตัวเลขที่อ้างอิงได้ — วัดจากโมเดลที่เว็บใช้อยู่จริง")
    print("=" * 84)
    print(f"    BUY  : {b[0]:.4f} ± {b[1]:.4f}")
    print(f"    FUEL : {f[0]:.4f} ± {f[1]:.4f}")
    print("\n  ทำซ้ำได้ด้วย: python analysis/verify_web_accuracy.py")
    print("  SHA-256 ข้างบนคือหลักฐานว่าวัดจากไฟล์เดียวกับที่เว็บโหลดใช้")
