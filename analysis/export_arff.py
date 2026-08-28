"""
แปลงข้อมูลแบบสอบถามเป็นไฟล์ ARFF สำหรับ WEKA (2026-08-07)

เหตุผล: อาจารย์ให้ทดลองใช้เครื่องมือใน WEKA (คาดว่าเป็น Auto-WEKA) เพื่อดูว่า
ความแม่นยำจะสูงขึ้นหรือไม่ ผลที่ได้จะถูกใช้เป็นหลักฐาน "ข้ามเครื่องมือ" ประกอบ
ข้อสรุปเรื่องเพดานสารสนเทศใน agent-docs/รายงานเสนออาจารย์_ทบทวนวรรณกรรม_2026-08-02.md

⚠️ สำคัญ: สคริปต์นี้เรียก build_buy / build_fuel จาก ablation.py ซึ่งใช้ขั้นตอน
เตรียมข้อมูลชุดเดียวกับ train_models.py ทุกประการ (map ค่าไทย -> web value space,
เติมค่าขาดหายด้วย mode, จัดการ outlier) ห้ามเขียนขั้นตอนเตรียมข้อมูลขึ้นใหม่เอง
มิฉะนั้นตัวเลขจาก WEKA จะเทียบกับผลใน sklearn ไม่ได้

สิ่งที่ *ไม่* ทำในไฟล์ ARFF โดยเจตนา:
  - ไม่ทำ one-hot / scaling / SMOTE / feature selection
    ปล่อยให้ WEKA จัดการเอง เพราะ Auto-WEKA ต้องได้ข้อมูลดิบจึงจะค้นหา pipeline
    ได้เต็มพื้นที่ ถ้าเรา preprocess มาก่อนจะเป็นการล็อกทางเลือกให้มันโดยไม่ตั้งใจ

หมายเหตุ label: WEKA/Auto-WEKA แสดงผลผ่าน console ที่มักเพี้ยนกับภาษาไทย
จึงแปลง label ของ BUY เป็น ASCII:  ซื้อ -> buy , ไม่ซื้อ -> not_buy
(ของ FUEL เป็น EV/Hybrid/ICE อยู่แล้ว ไม่ต้องแปลง)

การใช้งาน:
    cd C:\\Users\\click\\Desktop\\car-decision-app\\analysis
    python export_arff.py
ผลลัพธ์: analysis/arff/*.arff
"""
import sys, os, re, warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import train_models as tm
from models import feature_encoding as fe
from ablation import build_buy, build_fuel

OUT_DIR = os.path.join(_HERE, "arff")
SEED = 42

# BUY label เป็นภาษาไทย -> ASCII เพื่อให้อ่านผลใน WEKA ได้
BUY_LABEL_ASCII = {"ซื้อ": "buy", "ไม่ซื้อ": "not_buy"}

_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _q(v):
    """ครอบ quote ค่า nominal ที่มีอักขระพิเศษ (เช่น '75000+', '3+') ตามสเปก ARFF"""
    s = str(v)
    return s if _SAFE.match(s) else "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _num(v):
    if pd.isna(v):
        return "?"
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:.6g}"


def write_arff(path, relation, X, y, cat_cols, num_cols, class_values):
    """เขียนไฟล์ ARFF — คอลัมน์หมวดหมู่เป็น nominal, ที่เหลือเป็น numeric, class ไว้ท้ายสุด"""
    cat_set = set(cat_cols)
    cols = [c for c in list(cat_cols) + list(num_cols) if c in X.columns]

    lines = [f"@relation {relation}", ""]
    for c in cols:
        if c in cat_set:
            vals = sorted(str(v) for v in X[c].dropna().unique())
            lines.append(f"@attribute {c} {{{','.join(_q(v) for v in vals)}}}")
        else:
            lines.append(f"@attribute {c} numeric")
    lines.append(f"@attribute class {{{','.join(_q(v) for v in class_values)}}}")
    lines += ["", "@data"]

    for i in range(len(X)):
        row = X.iloc[i]
        cells = []
        for c in cols:
            v = row[c]
            if c in cat_set:
                cells.append("?" if (pd.isna(v) or str(v) == "") else _q(v))
            else:
                cells.append(_num(v))
        cells.append(_q(y.iloc[i]))
        lines.append(",".join(cells))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    n_cat = sum(1 for c in cols if c in cat_set)
    dist = dict(y.value_counts())
    base = y.value_counts(normalize=True).max()
    print(f"  {os.path.basename(path):<32} n={len(X):<4} "
          f"attr={len(cols)} (nominal {n_cat} / numeric {len(cols)-n_cat})")
    print(f"      class: {dist}  baseline(ZeroR) = {base:.4f}")


def undersample(X, y, seed=SEED):
    """สุ่มลดคลาสที่มากเกินให้เท่าคลาสน้อยสุด — วิธีเดียวกับ balanced_subsample.py

    หมายเหตุ: balanced_subsample.py ทำซ้ำ 10 seed แล้วเฉลี่ย ที่นี่ต้องเลือก seed
    เดียวเพราะไฟล์ ARFF เป็นชุดข้อมูลตายตัว ตัวเลขจึงอาจต่างจากรายงานเล็กน้อย
    """
    rng = np.random.RandomState(seed)
    k = y.value_counts().min()
    idx = np.concatenate([
        rng.choice(np.where(y.values == c)[0], k, replace=False)
        for c in sorted(y.unique())
    ])
    idx.sort()
    return X.iloc[idx].reset_index(drop=True), y.iloc[idx].reset_index(drop=True)


def main():
    df = tm.load_survey()
    print(f"โหลดข้อมูลแบบสอบถาม: {len(df)} แถว\n")

    # ---------- BUY ----------
    Xb, yb = build_buy(df)
    yb = yb.map(BUY_LABEL_ASCII)
    b_cat, b_num = fe.BUY_CAT_COLS, fe.BUY_NUM_COLS
    b_classes = ["buy", "not_buy"]

    print("[predict_buy]")
    write_arff(os.path.join(OUT_DIR, "cardss_buy.arff"),
               "cardss_buy", Xb, yb, b_cat, b_num, b_classes)
    Xbb, ybb = undersample(Xb, yb)
    write_arff(os.path.join(OUT_DIR, "cardss_buy_balanced.arff"),
               "cardss_buy_balanced", Xbb, ybb, b_cat, b_num, b_classes)

    # ---------- FUEL ----------
    Xf, yf = build_fuel(df)
    f_cat = fe.FUEL_CAT_COLS
    f_num = fe.FUEL_NUM_COLS + ["prio_" + t for t in fe.PRIORITY_TOKENS]
    f_classes = ["EV", "Hybrid", "ICE"]

    print("\n[predict_fuel]")
    write_arff(os.path.join(OUT_DIR, "cardss_fuel.arff"),
               "cardss_fuel", Xf, yf, f_cat, f_num, f_classes)
    Xfb, yfb = undersample(Xf, yf)
    write_arff(os.path.join(OUT_DIR, "cardss_fuel_balanced.arff"),
               "cardss_fuel_balanced", Xfb, yfb, f_cat, f_num, f_classes)

    print(f"\nเสร็จสิ้น — ไฟล์อยู่ที่ {OUT_DIR}")


if __name__ == "__main__":
    main()
