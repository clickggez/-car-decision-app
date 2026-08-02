"""
Sensitivity analysis: ผลของการคัดผู้ตอบที่ไม่ผ่าน attention check (2026-08-02)
เทียบโมเดลบนข้อมูลเต็ม (n=500) กับข้อมูลที่คัดแล้ว (n=222)
รายงานเป็น sensitivity analysis ไม่ใช่ผลหลัก
"""
import sys, os, io, contextlib
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import train_models as tm
from models import feature_encoding as fe
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      NEW_BUY_CAT, NEW_BUY_NUM, OLD_FUEL_CAT, OLD_FUEL_NUM,
                      NEW_FUEL_CAT, NEW_FUEL_NUM)

CLEANED = os.path.join(_HERE, "cleaned.csv")


def run(df, tag):
    print("\n" + "=" * 70)
    print(f"### {tag}  (n={len(df)} แถว)")
    print("=" * 70)
    out = {}

    Xb, yb = build_buy(df)
    base_b = yb.value_counts(normalize=True).max()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _, nameb, mb, _, _ = tm.build_and_select(
            Xb, yb, OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM, alpha=0.10)
    print(f"  BUY  n={len(yb):3d} | {nameb:9s} | test(20 splits) = "
          f"{mb['test_accuracy_repeated_mean']:.4f} ± {mb['test_accuracy_repeated_std']:.4f}"
          f" | baseline {base_b:.4f} | lift {mb['test_accuracy_repeated_mean']-base_b:+.4f}")
    out["buy"] = (mb["test_accuracy_repeated_mean"], base_b)

    Xf, yf = build_fuel(df)
    base_f = yf.value_counts(normalize=True).max()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _, namef, mf, _, _ = tm.build_and_select(
            Xf, yf, OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM,
            alpha=0.15, force_keep=["prev_car"])
    print(f"  FUEL n={len(yf):3d} | {namef:9s} | test(20 splits) = "
          f"{mf['test_accuracy_repeated_mean']:.4f} ± {mf['test_accuracy_repeated_std']:.4f}"
          f" | baseline {base_f:.4f} | lift {mf['test_accuracy_repeated_mean']-base_f:+.4f}")
    out["fuel"] = (mf["test_accuracy_repeated_mean"], base_f)
    return out


if __name__ == "__main__":
    full = tm.load_survey()
    clean = pd.read_csv(CLEANED, encoding="utf-8")

    r_full = run(full, "ข้อมูลเต็ม (ผลหลัก)")
    r_clean = run(clean, "หลังคัดผู้ไม่ผ่าน attention check (sensitivity)")

    print("\n" + "=" * 70)
    print("สรุปเปรียบเทียบ")
    print("=" * 70)
    for k, label in (("buy", "BUY "), ("fuel", "FUEL")):
        a, ba = r_full[k]
        b, bb = r_clean[k]
        print(f"  {label}: {a:.4f} (lift {a-ba:+.4f})  ->  {b:.4f} (lift {b-bb:+.4f})"
              f"   | accuracy เปลี่ยน {b-a:+.4f}, lift เปลี่ยน {(b-bb)-(a-ba):+.4f}")
