"""
fuel_feature_usage_2026-09-23.py
================================
ตอบคำถามเดียว: โมเดลที่ deploy อยู่บนเว็บ **ใช้ฟีเจอร์อะไรจริงบ้าง**
และถ้าตัดคำถามในฟอร์มออก คำตอบของผู้ใช้จะเปลี่ยนไปแค่ไหน

ที่มา: ห้องประชุม #25 (antigravity) ถามว่าตัดฟอร์ม "ส่วนที่ 3" ของ predict_fuel ได้ไหม

วิธี (ทำซ้ำได้ ไม่แตะไฟล์ .pkl):
  1. อ่าน num_cols / cat_cols / remainder จาก bundle ที่ Flask โหลดใช้จริง + SHA-256 กำกับ
  2. permutation test — สลับค่าทีละกลุ่มบนข้อมูลจริง แล้ววัดว่าคำตอบเปลี่ยนกี่ %
     (ฟีเจอร์ที่โมเดลไม่ได้ใช้ ต้องเปลี่ยน 0.0% ถ้าไม่ใช่ 0 แปลว่าอ่าน bundle ผิด)
  3. จำลองการตัดฟอร์มส่วนที่ 3 จริง โดยยัดค่าตาม NEW_FUEL_DEFAULTS + สูตร ev_readiness_index
     ที่ feature_encoding.py:237-240

รัน: python analysis/fuel_feature_usage_2026-09-23.py
"""
import sys, os, hashlib, warnings

warnings.filterwarnings("ignore")

_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
sys.path.insert(0, CAR)
sys.path.insert(0, _HERE)

import numpy as np
import pandas as pd
import joblib

import train_models as tm
from ablation import build_buy, build_fuel

MODEL_DIR = os.path.join(CAR, "models")
SEED = 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def report_declared(name):
    """ข้อ 1 — ฟีเจอร์ที่ประกาศไว้ vs ที่ preprocessor รับเข้าจริง"""
    path = os.path.join(MODEL_DIR, name)
    b = joblib.load(path)
    pre = dict(b["pipeline"].steps)["pre"]
    used = list(b["num_cols"]) + list(b["cat_cols"])
    unused = [c for c in b["feature_cols"] if c not in used]

    print(f"\n{'='*70}\n{name}  ({b['model_name']})\n{'='*70}")
    print(f"  SHA-256        : {sha256(path)}")
    print(f"  feature_cols   : {len(b['feature_cols'])} คอลัมน์ (ที่ predictor.py ส่งเข้า pipeline)")
    print(f"  num_cols       : {b['num_cols']}")
    print(f"  cat_cols       : {b['cat_cols']}")
    print(f"  remainder      : {pre.remainder}")
    print(f"  → ใช้จริง      : {len(used)} คอลัมน์")
    print(f"  → ถูกทิ้ง      : {len(unused)} คอลัมน์ {unused if unused else ''}")
    return b, used, unused


def permutation_test(b, X, used, unused, label):
    """ข้อ 2 — สลับค่าแล้ววัดว่าคำตอบเปลี่ยนกี่ % (ไม่ใช่ accuracy แต่คือ 'ผู้ใช้ได้คำตอบคนละอัน')"""
    pipe = b["pipeline"]
    X = X[b["feature_cols"]]
    base = pipe.predict(X)
    rng = np.random.default_rng(SEED)

    print(f"\n  permutation test — {label} (n={len(X)}, seed={SEED})")
    if unused:
        Xs = X.copy()
        for c in unused:
            Xs[c] = rng.permutation(Xs[c].values)
        pct = (pipe.predict(Xs) != base).mean() * 100
        print(f"    สลับฟีเจอร์ที่ไม่ได้ใช้พร้อมกัน {len(unused)} ตัว → คำตอบเปลี่ยน {pct:.1f}%"
              f"   {'[ตรงตามคาด]' if pct == 0 else '[ผิดคาด — ต้องตรวจซ้ำ]'}")
    for c in sorted(used):
        Xc = X.copy()
        Xc[c] = rng.permutation(Xc[c].values)
        print(f"    สลับ {c:28s} → คำตอบเปลี่ยน {(pipe.predict(Xc) != base).mean()*100:5.1f}%")
    return base


def simulate_drop_section3(b, X, y, base):
    """ข้อ 3 — จำลองว่าถ้าตัดฟอร์มส่วนที่ 3 ทิ้งแล้วยัดค่า default"""
    pipe = b["pipeline"]
    X = X[b["feature_cols"]]
    y = np.asarray(y)

    Xd = X.copy()
    Xd["ev_exposure"] = ""          # predict_fuel.html:229
    Xd["range_anxiety"] = 4         # feature_encoding.py:172 (กลางสเกล 1-7)
    Xd["nep_score"] = 3.0           # feature_encoding.py:173 (กลางสเกล 1-5)
    # ev_readiness_index ตามสูตร feature_encoding.py:237-240 เมื่อไม่มีคำตอบ
    Xd["ev_readiness_index"] = 0.0 + 0.0 + 0.0 + (3.0 / 5.0) - (4 / 7.0)

    alt = pipe.predict(Xd)
    print(f"\n  จำลองตัดฟอร์มส่วนที่ 3 (ev_exposure + range_anxiety + NEP 5 ข้อ)")
    print(f"    คำตอบเปลี่ยนไป      : {(alt != base).mean()*100:.1f}% ของผู้ตอบ")
    print(f"    accuracy (in-sample): {(base == y).mean():.4f} → {(alt == y).mean():.4f}")
    print(f"    การกระจายผล ก่อน    : {dict(pd.Series(base).value_counts())}")
    print(f"    การกระจายผล หลัง    : {dict(pd.Series(alt).value_counts())}")
    print(f"    หมายเหตุ: accuracy in-sample ใช้เทียบ 'ก่อน/หลัง' เท่านั้น")
    print(f"             ห้ามเอาไปแทนเลข 0.4180 ที่วัดด้วย 20 splits ใน verify_web_accuracy.py")


def main():
    print("การใช้ฟีเจอร์จริงของโมเดลที่ deploy อยู่ — 23 ก.ย. 2569")
    print("ตอบห้องประชุม #25 ข้อ 2 (ตัดฟอร์มส่วนที่ 3 ได้ไหม)")

    df = tm.load_survey()

    b, used, unused = report_declared("fuel_model.pkl")
    Xf, yf = build_fuel(df)
    Xf = pd.DataFrame(Xf)
    base = permutation_test(b, Xf, used, unused, "FUEL")
    simulate_drop_section3(b, Xf, yf, base)

    bb, used_b, unused_b = report_declared("buy_model.pkl")
    Xb, yb = build_buy(df)
    permutation_test(bb, pd.DataFrame(Xb), used_b, unused_b, "BUY")

    print(f"\n{'='*70}")
    print("สรุป: ฟีเจอร์ที่ถูก drop สลับค่ายังไงคำตอบก็ไม่ขยับ = โมเดลไม่ได้ใช้จริง")
    print("      คำถามในฟอร์มที่ป้อนฟีเจอร์เหล่านั้น ตัดได้โดยคำตอบไม่เปลี่ยน")
    print("      แต่การตัดคำถาม = เลิกเก็บข้อมูลวิจัยชุดนั้น ผู้ใช้เป็นคนเคาะ")


if __name__ == "__main__":
    main()
