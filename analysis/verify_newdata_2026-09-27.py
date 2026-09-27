"""
วัดผลโมเดลที่เทรนจากข้อมูลแบบสอบถามชุด 27 ก.ย. 2569 (n=514) — 2026-09-27

================================================================================
🔒 โปรโตคอลการประเมิน + เกณฑ์ — เขียนและล็อกไว้ "ก่อน" แก้ train_models.py และก่อนเทรน
================================================================================
ที่มา: ผู้ใช้อนุมัติ 2026-09-27 ให้ใช้ข้อมูลชุด n=514 แทนชุด n=511 (2026-09-26)
ชุด n=511 ถูกถอดเพราะ Likert 21 ข้อมีการแจกแจงเท่ากันทุกข้อ (302/126/52/22/9) — ห้องประชุม #32–#36
ผลของชุด n=511 (verify_newdata_2026-09-26.txt) ถือเป็นประวัติ ไม่ใช้อ้างอิงต่อ

ข้อมูล
  ไฟล์   : files/user_from/survey_2026-09-27_n514.csv
  SHA-256: 7d6196f2fbec3bb818335723e2b589fd72cd9be8520d9992665e8f34912eff02
  514 แถว × 44 คอลัมน์ ไม่มี timestamp · คอลัมน์สุดท้าย "คอลัมน์ 1" ว่างทั้งคอลัมน์ -> ทิ้ง
  ดึงคอลัมน์ด้วยชื่อหัวคอลัมน์ (train_models.SURVEY_HEADERS) ไม่ใช้ตำแหน่ง
  BUY  : ผู้ตอบทุกคน (n=514) label = "4. ท่านมีแนวโน้มจะซื้อรถยนต์ตามประเภทเชื้อเพลิงที่ท่านสนใจหรือไม่"
  FUEL : เฉพาะผู้ที่มีรถยนต์ (ตอบคำถามการใช้รถ) — ออกแบบเดิมไม่เปลี่ยน
         label = "5. หากต้องเลือกซื้อรถยนต์ ท่านสนใจรถประเภทใดมากที่สุด"

การเปลี่ยนแปลงการเข้ารหัสฟีเจอร์ (ตัดสินก่อนเทรน ตามคำสั่ง coordinator/ผู้ใช้ 2026-09-27)
  - คำถามเลือกได้หลายข้อ (คั่นด้วย ", ") เข้ารหัสแบบ multi-hot ไม่ยุบเหลือตัวเลือกแรกอีกต่อไป
      prev_car -> prev_ice / prev_hybrid / prev_ev      (เดิม _first_mapped ทำให้ ICE กลืนคำตอบผสม)
      concern  -> concern_<token> 7 ตัว                 (ผู้ไม่มีรถไม่ได้ตอบ = 0 ทุกตัว เลิก mode-fill)
      purpose  -> purpose_<token> 5 ตัว
      priority -> prio_<token> (เป็น multi-hot อยู่แล้ว)
  - ตัด purpose_housing (ฟีเจอร์ผสมที่ต้องใช้ purpose ค่าเดียว — นิยามไม่ได้เมื่อ purpose เป็น multi-hot)
  - FUEL บังคับเก็บ prev_ice/prev_hybrid/prev_ev ในขั้นคัดฟีเจอร์ (แทน force_keep prev_car เดิม เหตุผลเดิม)
  - ไม่มีคำถาม TPB / กลุ่ม EV / NEP (ข้อมูลไม่มี และอาจารย์ไม่ต้องการ)

โมเดล (train_models.py)
  - ขั้นเลือกชุดฟีเจอร์/จูนพารามิเตอร์ด้วย CV ภายในเหมือนเดิมทุกอย่าง
  - meta-classifier = BaggingClassifier x25 เท่านั้น (META_MODEL_NAMES = ("BAGGING",))
  - base learner = โมเดลเดี่ยวที่ CV ดีที่สุดที่ไม่ใช่ ANN (กลไกเดิม) random_state=42
  - เทรนลง car-dss/_models_2026-09-27_n514/ (CARDSS_MODEL_DIR) — ไม่ทับ car-dss/models/*.pkl

การวัด (สคริปต์นี้)
  - StratifiedShuffleSplit n_splits=20, test_size=0.2, random_state=42
  - ทุก split: clone pipeline จาก .pkl แล้ว fit ใหม่เฉพาะ train fold วัดบน test fold
  - รายงาน: accuracy mean ± sd (min–max), Cohen kappa mean ± sd, balanced accuracy mean ± sd,
    majority baseline (สัดส่วนคลาสใหญ่สุดของข้อมูลเต็ม), lift = accuracy เฉลี่ย − baseline,
    SHA-256 ของ .pkl แต่ละไฟล์, เทียบกับเลขที่ฝังใน .pkl
  - np.std แบบ population (ddof=0) เหมือน verify_web_accuracy.py

เกณฑ์ (ล็อกก่อนเห็นผล)
  - **ไม่มีเกณฑ์ "สำเร็จ" ที่ผูกกับ accuracy** — รายงานผลตามจริงทุกกรณี
  - ห้ามเปลี่ยน random_state / threshold / ชุดฟีเจอร์ / label / กลุ่มตัวอย่าง / การเข้ารหัส หลังเห็นผล
  - ห้ามเทียบ accuracy ข้ามชุดข้อมูล (สัดส่วนคลาสต่างกัน) — เทียบได้เฉพาะ lift และ kappa
  - ตัวเลขวินิจฉัยของ coordinator (analysis/eval_new514_2026-09-27.py) เป็นคนละ pipeline — ไม่ใช้เป็นเกณฑ์
  - lift ≤ 0 หรือ kappa ≈ 0 ให้รายงานตรง ๆ ไม่ใช่เหตุผลให้จูนใหม่
  - เงื่อนไขทางเทคนิคก่อนเสนอ deploy (ไม่ใช่เกณฑ์ผลงาน):
      (1) model_name ของทั้งสองไฟล์ = BAGGING
      (2) feature_cols ใน .pkl ตรงกับ feature_encoding ปัจจุบัน
      (3) ค่าเฉลี่ยที่วัดใหม่ ต่างจากค่าที่ฝังใน .pkl < 0.005
      (4) เทสต์ car-dss/tests ผ่านทั้งหมดเมื่อชี้ไปที่โฟลเดอร์โมเดลใหม่

ข้อจำกัดที่รู้ล่วงหน้า
  - ชุดฟีเจอร์และพารามิเตอร์ถูกเลือกด้วย CV บนข้อมูลเต็มก่อนแบ่ง 20 splits (โปรโตคอลเดิม) อาจมองโลกในแง่ดีเล็กน้อย

รัน:
    python analysis/verify_newdata_2026-09-27.py > analysis/verify_newdata_2026-09-27.txt
**อ่านอย่างเดียว — ไม่เขียนทับ .pkl ใด ๆ**
"""
import sys, os, hashlib, platform, warnings
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
sys.path.insert(0, CAR)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import joblib
import sklearn
from sklearn.base import clone
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import (accuracy_score, cohen_kappa_score,
                             balanced_accuracy_score, classification_report)

import contextlib, io
import train_models as tm
from models import feature_encoding as fe

MODEL_DIR = os.environ.get("CARDSS_EVAL_MODEL_DIR") or os.path.join(CAR, "_models_2026-09-27_n514")
N_SPLITS = 20
TEST_SIZE = 0.2
SEED = 42
EXPECTED_CSV_SHA256 = "7d6196f2fbec3bb818335723e2b589fd72cd9be8520d9992665e8f34912eff02"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(target, pkl_name, builder, expected_feature_cols):
    path = os.path.join(MODEL_DIR, pkl_name)
    bundle = joblib.load(path)
    pipe = bundle["pipeline"]
    cat_cols, num_cols = bundle["cat_cols"], bundle["num_cols"]
    embedded = bundle.get("metrics", {})

    print("\n" + "=" * 84)
    print(f"  {target}  —  {pkl_name}")
    print("=" * 84)
    print(f"  ไฟล์        : {os.path.normpath(os.path.abspath(path))}")
    print(f"  ขนาด        : {os.path.getsize(path):,} bytes")
    print(f"  SHA-256     : {sha256(path)}")
    clf = pipe.named_steps.get("clf")
    base = getattr(clf, "estimator", None)
    print(f"  โมเดล       : {bundle.get('model_name')}  (ตัวจำแนกจริง = {type(clf).__name__}"
          f"{', ฐาน = ' + type(base).__name__ if base is not None else ''})")
    print(f"  best_params : {embedded.get('best_params')}")
    print(f"  ชุดฟีเจอร์   : '{embedded.get('feature_mode')}'  "
          f"{len(cat_cols)} categorical + {len(num_cols)} numeric")
    print(f"    cat : {cat_cols}")
    print(f"    num : {num_cols}")
    print(f"  CV (ภายใน, balanced_accuracy) ทุกผู้สมัคร:")
    for k, v in sorted(embedded.get("cv_all", {}).items(), key=lambda kv: -kv[1]):
        print(f"      {k:22s} {v:.4f}")

    # เงื่อนไขทางเทคนิค (1)(2)
    ok_name = bundle.get("model_name") == "BAGGING"
    ok_cols = list(bundle["feature_cols"]) == list(expected_feature_cols)
    print(f"\n  [เงื่อนไข 1] model_name == BAGGING           : {'ผ่าน' if ok_name else 'ไม่ผ่าน'}")
    print(f"  [เงื่อนไข 2] feature_cols ตรง feature_encoding : {'ผ่าน' if ok_cols else 'ไม่ผ่าน'}")

    df = tm.load_survey()
    with contextlib.redirect_stdout(io.StringIO()):
        X, y = builder(df)
    X = X[cat_cols + num_cols].copy()
    counts = y.value_counts()
    baseline = float(counts.max() / counts.sum())
    print(f"\n  ข้อมูล n={len(y)}  สัดส่วนคลาส: {dict(counts)}")
    print(f"  baseline (ทายคลาสใหญ่สุด '{counts.idxmax()}' เสมอ) = {baseline:.4f}")

    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=TEST_SIZE, random_state=SEED)
    accs, kaps, bals = [], [], []
    for i, (tr, te) in enumerate(sss.split(X, y), 1):
        p = clone(pipe)
        p.fit(X.iloc[tr], y.iloc[tr])
        pred = p.predict(X.iloc[te])
        accs.append(accuracy_score(y.iloc[te], pred))
        kaps.append(cohen_kappa_score(y.iloc[te], pred))
        bals.append(balanced_accuracy_score(y.iloc[te], pred))
        print(f"    split {i:2d}/{N_SPLITS}  accuracy = {accs[-1]:.4f}  kappa = {kaps[-1]:+.4f}", flush=True)

    accs, kaps, bals = map(np.array, (accs, kaps, bals))
    lift = accs.mean() - baseline
    print(f"\n  ── ผล 20 splits ──")
    print(f"    accuracy          = {accs.mean():.4f} ± {accs.std():.4f}  ({accs.min():.4f}–{accs.max():.4f})")
    print(f"    Cohen kappa       = {kaps.mean():+.4f} ± {kaps.std():.4f}")
    print(f"    balanced accuracy = {bals.mean():.4f} ± {bals.std():.4f}")
    print(f"    baseline          = {baseline:.4f}")
    print(f"    lift              = {lift:+.4f}")

    emb = embedded.get("test_accuracy_repeated_mean")
    d = None if emb is None else accs.mean() - float(emb)
    ok_emb = d is not None and abs(d) < 0.005
    print(f"\n  เลขที่ฝังใน .pkl : {emb} ± {embedded.get('test_accuracy_repeated_std')}")
    print(f"  [เงื่อนไข 3] ส่วนต่างกับที่วัดใหม่ < 0.005       : "
          f"{'ผ่าน' if ok_emb else 'ไม่ผ่าน'} ({'n/a' if d is None else f'{d:+.4f}'})")

    print(f"\n  ── รายละเอียดรายคลาส (split สุดท้าย ใช้ดูประกอบเท่านั้น) ──")
    print(classification_report(y.iloc[te], pred, zero_division=0))
    return {
        "n": len(y), "acc": accs, "kap": kaps, "bal": bals,
        "baseline": baseline, "lift": lift, "sha": sha256(path),
    }


if __name__ == "__main__":
    print(__doc__)
    print("=" * 84)
    print(f"  รันเมื่อ      : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  เครื่อง       : {platform.platform()}")
    print(f"  Python       : {sys.version.split()[0]}")
    print(f"  scikit-learn : {sklearn.__version__}")
    print(f"  โฟลเดอร์โมเดล : {os.path.normpath(os.path.abspath(MODEL_DIR))}")
    csv_path = tm.survey_path()
    csv_sha = sha256(csv_path)
    print(f"  ไฟล์ข้อมูล    : {os.path.normpath(csv_path)}")
    print(f"  SHA-256 ข้อมูล: {csv_sha}  ({'ตรงกับที่ล็อกไว้' if csv_sha == EXPECTED_CSV_SHA256 else '⚠️ ไม่ตรงกับที่ล็อกไว้'})")
    print("=" * 84)

    b = verify("BUY  (ซื้อ / ไม่ซื้อ)", "buy_model.pkl", tm.build_buy_xy, fe.buy_feature_columns())
    f = verify("FUEL (EV / Hybrid / ICE)", "fuel_model.pkl", tm.build_fuel_xy, fe.fuel_feature_columns())

    print("\n" + "=" * 84)
    print("  สรุป (20 random splits, seed 42, test 20%)")
    print("=" * 84)
    print(f"  {'โมเดล':6s} {'n':>4s}  {'accuracy (min–max)':34s} {'kappa':18s} {'baseline':>8s} {'lift':>8s}")
    for name, r in (("BUY", b), ("FUEL", f)):
        a, k = r["acc"], r["kap"]
        print(f"  {name:6s} {r['n']:>4d}  {a.mean():.4f} ± {a.std():.4f} ({a.min():.3f}–{a.max():.3f})   "
              f"{k.mean():+.4f} ± {k.std():.4f}  {r['baseline']:>8.4f} {r['lift']:>+8.4f}")
    print(f"\n  SHA-256 BUY  : {b['sha']}")
    print(f"  SHA-256 FUEL : {f['sha']}")
    print("\n  ทำซ้ำได้ด้วย: python analysis/verify_newdata_2026-09-27.py")
