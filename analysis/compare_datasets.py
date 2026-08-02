"""
เทียบข้อมูลเก่า (n=715) กับข้อมูลใหม่ (n=500) ด้วยวิธีวัดเดียวกัน (2026-08-02)

เหตุผล: ตัวเลขที่ใช้เทียบกันมาตลอดวัดคนละวิธี
  - ข้อมูลเก่า FUEL 48.7% = 1 split (random_state=42)
  - ข้อมูลใหม่ FUEL 44.3% = ค่าเฉลี่ย 20 splits
สคริปต์นี้วัดทั้งสองชุดด้วย 20 splits เหมือนกัน เพื่อตอบว่า
"ควรเอาโมเดล BUY จากชุดใหม่ + FUEL จากชุดเก่ามารวมกันหรือไม่"

หมายเหตุ: ข้อมูลเก่ามี 44 คอลัมน์ (ไม่มีคำถามใหม่ 10 ข้อ) จึงใช้ได้เฉพาะฟีเจอร์เดิม
"""
import sys, os, io, contextlib, glob, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import train_models as tm
from models import feature_encoding as fe
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      OLD_FUEL_CAT, OLD_FUEL_NUM)

ARCHIVE = os.path.join(_HERE, "..", "files", "user_from_archive")


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def build_buy_oldcols(df):
    """สร้างฟีเจอร์ BUY จากคอลัมน์เดิมเท่านั้น (ใช้ได้กับข้อมูลเก่าที่มี 44 คอลัมน์)"""
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
        }
        rows.append(fe.buy_features_from_web(web))
        labels.append(lab)
    X = pd.DataFrame(rows, columns=fe.buy_feature_columns())
    for c in fe.BUY_CAT_COLS:
        X[c] = X[c].replace("", np.nan); X[c] = X[c].fillna(tm._mode(X[c]))
    X = tm.handle_missing_and_outliers(X, fe.BUY_NUM_COLS)
    return X, pd.Series(labels)


def build_fuel_oldcols(df):
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
        }
        rows.append(fe.fuel_features_from_web(web))
        labels.append(lab)
    X = pd.DataFrame(rows, columns=fe.fuel_feature_columns())
    for c in fe.FUEL_CAT_COLS:
        X[c] = X[c].replace("", np.nan); X[c] = X[c].fillna(tm._mode(X[c]))
    X = tm.handle_missing_and_outliers(X, fe.FUEL_NUM_COLS)
    return X, pd.Series(labels)


def evaluate(X, y, cat, num, alpha, fk, tag):
    _, name, m, _, _ = quiet(tm.build_and_select, X, y, cat, num, alpha=alpha, force_keep=fk)
    base = y.value_counts(normalize=True).max()
    print(f"  {tag:34s} n={m['n_samples']:3d} | {name:5s} | "
          f"1 split {m['test_accuracy']:.4f} | 20 splits {m['test_accuracy_repeated_mean']:.4f} "
          f"± {m['test_accuracy_repeated_std']:.4f} | baseline {base:.4f} | "
          f"lift {m['test_accuracy_repeated_mean']-base:+.4f}")
    return m['test_accuracy_repeated_mean'], base


if __name__ == "__main__":
    old_path = [p for p in glob.glob(ARCHIVE + r"\*.csv") if "(500)" in p][0]
    df_old = pd.read_csv(old_path, encoding="utf-8")
    df_new = tm.load_survey()
    print(f"ข้อมูลเก่า: {len(df_old)} แถว, {len(df_old.columns)} คอลัมน์")
    print(f"ข้อมูลใหม่: {len(df_new)} แถว, {len(df_new.columns)} คอลัมน์")
    print("\n*** วัดด้วยวิธีเดียวกันทั้งหมด (ฟีเจอร์เดิมล้วน, 20 random splits) ***\n")

    Xb_o, yb_o = quiet(build_buy_oldcols, df_old)
    Xf_o, yf_o = quiet(build_fuel_oldcols, df_old)
    Xb_n, yb_n = quiet(build_buy_oldcols, df_new)
    Xf_n, yf_n = quiet(build_fuel_oldcols, df_new)

    print("[BUY]")
    bo, bbo = evaluate(Xb_o, yb_o, OLD_BUY_CAT, OLD_BUY_NUM, 0.10, None, "ข้อมูลเก่า n=715")
    bn, bbn = evaluate(Xb_n, yb_n, OLD_BUY_CAT, OLD_BUY_NUM, 0.10, None, "ข้อมูลใหม่ n=500")
    print("\n[FUEL]")
    fo, bfo = evaluate(Xf_o, yf_o, OLD_FUEL_CAT, OLD_FUEL_NUM, 0.15, ["prev_car"], "ข้อมูลเก่า n=715")
    fn, bfn = evaluate(Xf_n, yf_n, OLD_FUEL_CAT, OLD_FUEL_NUM, 0.15, ["prev_car"], "ข้อมูลใหม่ n=500")

    print("\n" + "=" * 78)
    print("สรุป — ชุดไหนดีกว่าเมื่อวัดด้วยวิธีเดียวกัน")
    print("=" * 78)
    print(f"  BUY  : เก่า {bo:.4f} (lift {bo-bbo:+.4f})  vs  ใหม่ {bn:.4f} (lift {bn-bbn:+.4f})"
          f"  -> {'ใหม่ดีกว่า' if bn>bo else 'เก่าดีกว่า'}")
    print(f"  FUEL : เก่า {fo:.4f} (lift {fo-bfo:+.4f})  vs  ใหม่ {fn:.4f} (lift {fn-bfn:+.4f})"
          f"  -> {'ใหม่ดีกว่า' if fn>fo else 'เก่าดีกว่า'}")
