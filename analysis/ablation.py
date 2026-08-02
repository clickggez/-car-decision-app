"""
Ablation: ฟีเจอร์ใหม่ (2026-08-01) ช่วยเพิ่ม accuracy จริงหรือไม่
เทียบบนข้อมูลชุดเดียวกัน (n=500) ระหว่าง
  (ก) ฟีเจอร์เดิมเท่านั้น  (ข) เดิม+ใหม่
วัดด้วย 20 random splits เหมือน pipeline หลัก + baseline (ทายคลาสใหญ่สุดเสมอ)
"""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score
from sklearn.base import clone

import train_models as tm
from models import feature_encoding as fe

OLD_BUY_CAT = ["gender", "age", "children", "education", "occupation", "family_size",
               "housing_type", "housing_status", "parking", "income", "budget",
               "concern", "purpose", "purpose_housing"]
OLD_BUY_NUM = ["income_budget_gap"]
NEW_BUY_CAT = ["charging_access", "tco_awareness", "incentive_awareness"]
NEW_BUY_NUM = ["intention", "attitude", "subjective_norm", "pbc_financial",
               "evt_job", "evt_move", "evt_child", "evt_income"]

OLD_FUEL_CAT = ["usage_type", "frequency", "distance", "prev_car"]
OLD_FUEL_NUM = ["tech_env_concern", "resale_maintenance_concern", "priority_count",
                "mileage_intensity", "tech_cost_balance"] + ["prio_" + t for t in fe.PRIORITY_TOKENS]
NEW_FUEL_CAT = ["charging_access", "ev_exposure", "tco_awareness", "incentive_awareness"]
NEW_FUEL_NUM = ["range_anxiety", "nep_score"]


def build_buy(df):
    rows, labels = [], []
    for _, r in df.iterrows():
        lab = tm.BUY_LABEL.get(str(r.iloc[20]).strip())
        if lab is None:
            continue
        web = {
            "gender": tm.GENDER.get(str(r.iloc[1]).strip(), ""),
            "age": tm.AGE.get(str(r.iloc[2]).strip(), ""),
            "children": tm.CHILDREN.get(str(r.iloc[3]).strip(), ""),
            "education": tm.EDUCATION.get(str(r.iloc[4]).strip(), ""),
            "occupation": tm.OCCUPATION.get(str(r.iloc[5]).strip(), ""),
            "family_size": tm.FAMILY_SIZE.get(str(r.iloc[6]).strip(), ""),
            "housing_type": tm.HOUSING_TYPE.get(str(r.iloc[7]).strip(), ""),
            "housing_status": tm.HOUSING_STATUS.get(str(r.iloc[8]).strip(), ""),
            "parking": tm.PARKING.get(str(r.iloc[9]).strip(), ""),
            "income": tm.INCOME.get(str(r.iloc[10]).strip(), ""),
            "budget": tm.BUDGET.get(str(r.iloc[18]).strip(), ""),
            "concern": tm._first_mapped(r.iloc[15], tm.CONCERN),
            "purpose": tm._first_mapped(r.iloc[19], tm.PURPOSE),
            "intention": tm._likert(r.iloc[tm.COL_INTENTION]),
            "attitude": tm._likert(r.iloc[tm.COL_ATTITUDE]),
            "subjective_norm": tm._likert(r.iloc[tm.COL_SUBJ_NORM]),
            "pbc_financial": tm._likert(r.iloc[tm.COL_PBC]),
            "life_events": tm._all_mapped(r.iloc[tm.COL_LIFE_EVENTS], tm.LIFE_EVENTS),
            "charging_access": tm.CHARGING_ACCESS.get(str(r.iloc[tm.COL_CHARGING]).strip(), ""),
            "tco_awareness": tm.TCO_AWARENESS.get(str(r.iloc[tm.COL_TCO]).strip(), ""),
            "incentive_awareness": tm.INCENTIVE_AWARENESS.get(str(r.iloc[tm.COL_INCENTIVE]).strip(), ""),
        }
        rows.append(fe.buy_features_from_web(web))
        labels.append(lab)
    X = pd.DataFrame(rows, columns=fe.buy_feature_columns())
    for c in fe.BUY_CAT_COLS:
        X[c] = X[c].replace("", np.nan)
        X[c] = X[c].fillna(tm._mode(X[c]))
    X = tm.handle_missing_and_outliers(X, fe.BUY_NUM_COLS)
    return X, pd.Series(labels)


def build_fuel(df):
    rows, labels = [], []
    for _, r in df.iterrows():
        lab = tm.FUEL_LABEL.get(str(r.iloc[21]).strip())
        usage = tm.USAGE_TYPE.get(str(r.iloc[12]).strip(), "")
        if lab is None or usage == "":
            continue
        pris = []
        if not pd.isna(r.iloc[17]):
            for t in str(r.iloc[17]).split(","):
                t = t.strip()
                if t in tm.PRIORITY:
                    pris.append(tm.PRIORITY[t])
        web = {
            "usage_type": usage,
            "frequency": tm.FREQUENCY.get(str(r.iloc[13]).strip(), ""),
            "distance": tm.DISTANCE.get(str(r.iloc[14]).strip(), ""),
            "prev_car": tm._first_mapped(r.iloc[16], tm.PREV_CAR) or "none",
            "priority": pris,
            "tech_env_concern": r.iloc[tm.COL_LIKERT_ENERGY_FIT],
            "resale_maintenance_concern": r.iloc[tm.COL_LIKERT_MAINTENANCE],
            "charging_access": tm.CHARGING_ACCESS.get(str(r.iloc[tm.COL_CHARGING]).strip(), ""),
            "ev_exposure": tm.EV_EXPOSURE.get(str(r.iloc[tm.COL_EV_EXPOSURE]).strip(), ""),
            "tco_awareness": tm.TCO_AWARENESS.get(str(r.iloc[tm.COL_TCO]).strip(), ""),
            "incentive_awareness": tm.INCENTIVE_AWARENESS.get(str(r.iloc[tm.COL_INCENTIVE]).strip(), ""),
            "range_anxiety": tm._likert(r.iloc[tm.COL_RANGE_ANXIETY]),
            "nep_score": tm._nep_score(r),
        }
        rows.append(fe.fuel_features_from_web(web))
        labels.append(lab)
    X = pd.DataFrame(rows, columns=fe.fuel_feature_columns())
    for c in fe.FUEL_CAT_COLS:
        X[c] = X[c].replace("", np.nan)
        X[c] = X[c].fillna(tm._mode(X[c]))
    X = tm.handle_missing_and_outliers(X, fe.FUEL_NUM_COLS)
    return X, pd.Series(labels)


def evaluate(X, y, cat_cols, num_cols, alpha, force_keep, tag):
    """เทรน+เลือกโมเดลด้วย pipeline เดียวกับ train_models.py แล้ววัด 20 random splits"""
    print(f"\n{'='*70}\n### {tag}  (cat={len(cat_cols)}, num={len(num_cols)})\n{'='*70}")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, metrics, sc, sn = tm.build_and_select(
            X, y, cat_cols, num_cols, alpha=alpha, force_keep=force_keep)
    print(f"  โมเดลที่เลือก : {name} (ชุดฟีเจอร์ '{metrics['feature_mode']}')")
    print(f"  CV bal.acc    : {metrics['cv_accuracy']:.4f}")
    print(f"  test 1 split  : {metrics['test_accuracy']:.4f}")
    print(f"  test 20 splits: {metrics['test_accuracy_repeated_mean']:.4f} "
          f"+/- {metrics['test_accuracy_repeated_std']:.4f}")
    return metrics


if __name__ == "__main__":
    df = tm.load_survey()
    print(f"ข้อมูล: {len(df)} แถว\n")

    Xb, yb = build_buy(df)
    base_b = yb.value_counts(normalize=True).max()
    print(f"[BUY]  n={len(yb)}  baseline (ทายคลาสใหญ่สุดเสมอ) = {base_b:.4f}")
    r1 = evaluate(Xb, yb, OLD_BUY_CAT, OLD_BUY_NUM, 0.10, None, "BUY (ก) ฟีเจอร์เดิมเท่านั้น")
    r2 = evaluate(Xb, yb, OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM, 0.10, None,
                  "BUY (ข) เดิม + ใหม่")

    Xf, yf = build_fuel(df)
    base_f = yf.value_counts(normalize=True).max()
    print(f"\n\n[FUEL] n={len(yf)}  baseline (ทายคลาสใหญ่สุดเสมอ) = {base_f:.4f}")
    r3 = evaluate(Xf, yf, OLD_FUEL_CAT, OLD_FUEL_NUM, 0.15, ["prev_car"], "FUEL (ก) ฟีเจอร์เดิมเท่านั้น")
    r4 = evaluate(Xf, yf, OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM, 0.15,
                  ["prev_car"], "FUEL (ข) เดิม + ใหม่")

    print(f"\n\n{'='*70}\nสรุป ablation (test accuracy เฉลี่ยจาก 20 random splits)\n{'='*70}")
    print(f"{'':28s} {'เดิม':>10s} {'เดิม+ใหม่':>12s} {'ส่วนต่าง':>10s} {'baseline':>10s}")
    print(f"{'BUY  (ซื้อ/ไม่ซื้อ)':28s} "
          f"{r1['test_accuracy_repeated_mean']:>10.4f} {r2['test_accuracy_repeated_mean']:>12.4f} "
          f"{r2['test_accuracy_repeated_mean']-r1['test_accuracy_repeated_mean']:>+10.4f} {base_b:>10.4f}")
    print(f"{'FUEL (EV/Hybrid/ICE)':28s} "
          f"{r3['test_accuracy_repeated_mean']:>10.4f} {r4['test_accuracy_repeated_mean']:>12.4f} "
          f"{r4['test_accuracy_repeated_mean']-r3['test_accuracy_repeated_mean']:>+10.4f} {base_f:>10.4f}")
