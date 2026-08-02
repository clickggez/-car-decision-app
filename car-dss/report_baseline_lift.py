"""
CarDSS — Baseline/Lift Report
คำนวณ majority-class baseline accuracy และ lift ของโมเดลที่ deploy อยู่ตอนนี้
(ไม่ retrain, ไม่แก้ .pkl — อ่านค่าที่มีอยู่แล้วเท่านั้น) สำหรับใช้ในบทวิเคราะห์ผลการวิจัย
เมื่อ accuracy เดี่ยวไม่ยุติธรรมกับปัญหาที่ class ไม่สมดุล/มีหลาย class

การใช้งาน:
    python report_baseline_lift.py
"""

import joblib
import pandas as pd

import train_models as tm

MODEL_DIR = "models"


def main():
    df = tm.load_survey()

    # ---- BUY ----
    labels = []
    for _, r in df.iterrows():
        lab = tm.BUY_LABEL.get(str(r.iloc[20]).strip())
        if lab is not None:
            labels.append(lab)
    y_buy = pd.Series(labels)
    buy_majority = y_buy.value_counts().idxmax()
    buy_baseline = float((y_buy == buy_majority).mean())

    # ---- FUEL ----
    labels2 = []
    for _, r in df.iterrows():
        lab = tm.FUEL_LABEL.get(str(r.iloc[21]).strip())
        usage = tm.USAGE_TYPE.get(str(r.iloc[12]).strip(), "")
        if lab is not None and usage != "":
            labels2.append(lab)
    y_fuel = pd.Series(labels2)
    fuel_majority = y_fuel.value_counts().idxmax()
    fuel_baseline = float((y_fuel == fuel_majority).mean())

    buy_bundle = joblib.load(f"{MODEL_DIR}/buy_model.pkl")
    fuel_bundle = joblib.load(f"{MODEL_DIR}/fuel_model.pkl")
    buy_acc = buy_bundle["metrics"]["test_accuracy"]
    fuel_acc = fuel_bundle["metrics"]["test_accuracy"]

    print("=" * 72)
    print("Baseline / Lift Report — โมเดลที่ deploy อยู่ตอนนี้ใน models/*.pkl")
    print("=" * 72)
    for name, majority, baseline, acc, model_name in [
        ("BUY", buy_majority, buy_baseline, buy_acc, buy_bundle["model_name"]),
        ("FUEL", fuel_majority, fuel_baseline, fuel_acc, fuel_bundle["model_name"]),
    ]:
        lift_pts = (acc - baseline) * 100
        lift_rel = (acc - baseline) / baseline * 100
        print(f"\n[{name}] โมเดล: {model_name}")
        print(f"  Majority-class baseline (ทาย '{majority}' ทุกครั้ง) = {baseline*100:.1f}%")
        print(f"  Test accuracy ของโมเดล                            = {acc*100:.1f}%")
        print(f"  Lift เหนือ baseline                                = +{lift_pts:.1f} จุด "
              f"(+{lift_rel:.1f}% เชิงสัมพัทธ์)")
    print()


if __name__ == "__main__":
    main()
