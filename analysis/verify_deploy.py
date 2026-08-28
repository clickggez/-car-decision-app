"""
ตรวจก่อน deploy: เทียบผลทำนายจริงระหว่างโมเดลเดิม (บนเว็บ) กับโมเดลใหม่ (Bagging)
[2026-08-09]

ที่มา — บทเรียนจริง 2026-08-02 (00-READ-FIRST.md §3.1.1)
--------------------------------------------------------
Round 2 รัน unit tests ผ่าน 41/41 แล้ว deploy → เว็บแนะนำผิดทันที
(ผู้ใช้ที่ขับ EV อยู่ ได้รับคำแนะนำให้ซื้อ ICE ด้วยความมั่นใจ 98%)
เพราะ tests ตรวจแค่ API contract ไม่ได้ตรวจว่าคำแนะนำสมเหตุสมผล

สคริปต์นี้จึงรัน `feature_encoding` + pipeline จริงบนโปรไฟล์ที่ออกแบบไว้
แล้วเทียบผลของสองโมเดลแบบเคียงข้างกัน **ไม่แก้ไฟล์ใด ๆ — อ่านอย่างเดียว**

โปรไฟล์ทดสอบรวมเคสที่เคยพังจริงเมื่อ 2026-08-02 ไว้ด้วย (P1)
"""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
CAR = os.path.join(_HERE, "..", "car-dss")
sys.path.insert(0, CAR)
sys.stdout.reconfigure(encoding="utf-8")

import joblib
import pandas as pd
from models import feature_encoding as fe

OLD_DIR = os.path.join(CAR, "models")
NEW_DIR = os.path.join(CAR, "_models_2026-08-09_bagging")

# ---- โปรไฟล์ทดสอบ (ครบทุกช่องรวมคำถามใหม่ เหมือนที่ฟอร์มเว็บจะส่งมาจริง) ----
BASE_BUY = dict(
    gender="male", age="27-30", children="0", education="bachelor",
    occupation="private", family_size="1-2", housing_type="condo",
    housing_status="rent", parking="common", income="35001-50000",
    budget="800001-1200000", concern="fuel_price", purpose="commute",
    charging_access="cannot", tco_awareness="unknown", incentive_awareness="unknown",
    intention="4", attitude="4", subjective_norm="4", pbc_financial="4",
    life_events=[],
)
BASE_FUEL = dict(
    usage_type="city", frequency="5-6days", distance="10-30", prev_car="ice",
    tech_env_concern="3", resale_maintenance_concern="3",
    priority=["price", "fuel_cost"],
    ev_exposure="none", range_anxiety="4", nep_score=3.0,
    charging_access="cannot", tco_awareness="unknown", incentive_awareness="unknown",
)

PROFILES = [
    ("P1 คนขับ EV อยู่แล้ว ทางไกล สนใจเทคโนโลยีสูง  [เคสที่เคยพัง 2026-08-02]",
     dict(BASE_BUY, housing_type="house", housing_status="own", parking="private",
          income="50001-75000", budget="1200001-1500000", charging_access="has",
          tco_awareness="much_cheaper", incentive_awareness="aware_considered",
          intention="6", attitude="6", subjective_norm="5", pbc_financial="6"),
     dict(BASE_FUEL, prev_car="ev", distance="90+", usage_type="highway",
          tech_env_concern="5", resale_maintenance_concern="2",
          priority=["technology", "electricity_cost"], ev_exposure="both",
          range_anxiety="2", nep_score=4.6, charging_access="has",
          tco_awareness="much_cheaper", incentive_awareness="aware_considered")),

    ("P2 คนขับ ICE ในเมือง คอนโดไม่มีที่ชาร์จ งบน้อย",
     dict(BASE_BUY, budget="lt500000", income="15001-25000", intention="2",
          attitude="3", pbc_financial="2"),
     dict(BASE_FUEL, prev_car="ice", distance="lt10", tech_env_concern="2",
          resale_maintenance_concern="5", priority=["price", "maintenance_cost"])),

    ("P3 ครอบครัวมีบุตร บ้านเดี่ยว ติดตั้งที่ชาร์จได้ สนใจ Hybrid",
     dict(BASE_BUY, children="2", family_size="3-4", housing_type="house",
          housing_status="own", parking="private", charging_access="installable",
          tco_awareness="slightly_cheaper", incentive_awareness="aware_only",
          intention="5", attitude="6", subjective_norm="6", pbc_financial="5",
          life_events=["child"]),
     dict(BASE_FUEL, prev_car="hybrid", usage_type="both", distance="31-50",
          tech_env_concern="4", resale_maintenance_concern="4",
          priority=["value", "warranty", "performance"], ev_exposure="hybrid_only",
          range_anxiety="4", nep_score=3.8, charging_access="installable",
          tco_awareness="slightly_cheaper", incentive_awareness="aware_only")),

    ("P4 ค่ากลางทุกช่อง (ทดสอบว่าไม่ยุบไปทางเดียว)", dict(BASE_BUY), dict(BASE_FUEL)),
]


def load(d):
    return (joblib.load(os.path.join(d, "buy_model.pkl")),
            joblib.load(os.path.join(d, "fuel_model.pkl")))


def predict(bundle, feat_fn, form):
    feat = feat_fn(form)
    X = pd.DataFrame([feat], columns=bundle["feature_cols"])
    pipe = bundle["pipeline"]
    label = pipe.predict(X)[0]
    proba = pipe.predict_proba(X)[0]
    classes = list(pipe.classes_)
    dist = sorted(zip(classes, proba), key=lambda t: -t[1])
    return label, dist


if __name__ == "__main__":
    ob, of_ = load(OLD_DIR)
    nb, nf = load(NEW_DIR)

    print("=" * 88)
    print("เทียบผลทำนายจริง: โมเดลเดิม (บนเว็บ) vs โมเดลใหม่ (Bagging)")
    print(f"  เดิม : {OLD_DIR}")
    print(f"  ใหม่ : {NEW_DIR}")
    print("=" * 88)

    for name, bform, fform in PROFILES:
        print(f"\n{'-'*88}\n{name}\n{'-'*88}")
        for tag, ob_, nb_, fn, form in (
            ("BUY ", ob, nb, fe.buy_features_from_web, bform),
            ("FUEL", of_, nf, fe.fuel_features_from_web, fform),
        ):
            ol, od = predict(ob_, fn, form)
            nl, nd = predict(nb_, fn, form)
            mark = "  " if ol == nl else " <-- ต่างกัน"
            print(f"  {tag} เดิม : {str(ol):<10s} " +
                  " | ".join(f"{c}={p*100:.0f}%" for c, p in od))
            print(f"  {tag} ใหม่ : {str(nl):<10s} " +
                  " | ".join(f"{c}={p*100:.0f}%" for c, p in nd) + mark)

    print(f"\n{'='*88}")
    print("เกณฑ์ตรวจ (ต้องผ่านทุกข้อก่อน deploy):")
    print("  1. P1 (คนขับ EV มีที่ชาร์จ ทางไกล สนใจเทคโนโลยี) ต้องไม่ได้ ICE ด้วยความมั่นใจสูง")
    print("  2. ผลรวมทุกโปรไฟล์ต้องไม่ยุบไปคลาสเดียวทั้งหมด")
    print("  3. ความน่าจะเป็นต้องกระจายสมเหตุสมผล ไม่ใช่ 98%/1%/1% ทุกเคส")
    print("=" * 88)
