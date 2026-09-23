"""
ทดลองดัน accuracy รอบ 2026-09-15 — ตามข้อสรุปห้องประชุม #18/#20/#21

โจทย์จากผู้ใช้: "ทำยังไงก็ได้ให้ % สูงขึ้น"
สิ่งที่ยังไม่เคยลอง (ตรวจแล้วใน train_models.py): CatBoost, LightGBM,
SMOTE-Tomek, SMOTE-ENN, tree-based feature selection (SelectFromModel)

กฎที่ตั้งไว้ก่อนรัน (pre-registered — ตามที่ codex เสนอใน #20 ข้อ 4)
  1. ทุกอย่าง (preprocess / resample / feature select / fit) ทำ "เฉพาะ train fold"
     ห้ามเห็น test fold แม้แต่ขั้นเดียว มิฉะนั้นเลขจะสวยแบบหลอก
  2. ใช้ split ชุดเดียวกันทุก arm — StratifiedShuffleSplit(20, test_size=0.2, seed=42)
     ซึ่งเป็นโปรโตคอลเดียวกับ train_models.py:820 จึงเทียบกับเลขในรายงานได้
  3. เกณฑ์ "รับว่าดีขึ้นจริง" ต้องผ่านครบ 3 ข้อ:
       (ก) mean accuracy > CTRL
       (ข) ส่วนต่างแบบจับคู่ (paired ต่อ split เดียวกัน) มี p < 0.05
       (ค) mean ต้องเกินเลขที่รายงานไว้ปัจจุบัน (BUY 0.6925 / FUEL 0.4336)
     ผ่านไม่ครบ = ไม่ดีขึ้นจริง ห้ามเขียนลงเล่มว่าดีขึ้น

ไม่แตะโซนแดง: ไม่ import/รัน train_models.train_and_save, ไม่เขียนทับ .pkl ใด ๆ
"""
import sys, os, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, cohen_kappa_score
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.feature_selection import SelectFromModel
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.over_sampling import SMOTE, BorderlineSMOTE
from imblearn.combine import SMOTETomek, SMOTEENN

import train_models as tm
from ablation import (build_buy, build_fuel,
                      OLD_BUY_CAT, OLD_BUY_NUM, NEW_BUY_CAT, NEW_BUY_NUM,
                      OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM)

SEED = 42
N_SPLITS = 20
REPORTED = {"BUY": 0.6925, "FUEL": 0.4336}   # 00-READ-FIRST.md:18-21


def make_smote_like(sampler_cls, y_tr):
    """สร้าง sampler โดยตั้ง k_neighbors ตามคลาสน้อยสุดของ train fold นั้น ๆ"""
    min_count = int(pd.Series(y_tr).value_counts().min())
    if min_count < 2:
        return None
    k = min(5, min_count - 1)
    if sampler_cls is BorderlineSMOTE:
        return BorderlineSMOTE(k_neighbors=k, random_state=SEED)
    # SMOTETomek/SMOTEENN บังคับว่าตัว over-sampler ข้างในต้องเป็น SMOTE แท้
    # (BorderlineSMOTE เป็นซับคลาสคนละสาย imblearn ปฏิเสธ) จึงใช้ SMOTE ธรรมดา
    inner = SMOTE(k_neighbors=k, random_state=SEED)
    return sampler_cls(smote=inner, random_state=SEED)


def arms_sklearn(cat_cols, num_cols):
    """arm ที่ใช้ preprocessor เดิมของโปรเจกต์ (one-hot + minmax)"""
    pre = tm._make_pre(cat_cols, num_cols)
    rf = lambda: RandomForestClassifier(class_weight="balanced", random_state=SEED)
    out = {}

    out["CTRL  RF + BorderlineSMOTE"] = ("skl", BorderlineSMOTE, [("clf", rf())])
    out["A1    RF + SMOTE-Tomek"]     = ("skl", SMOTETomek,      [("clf", rf())])
    out["A2    RF + SMOTE-ENN"]       = ("skl", SMOTEENN,        [("clf", rf())])
    out["A3    tree-select + RF"]     = ("skl", BorderlineSMOTE, [
        ("sel", SelectFromModel(ExtraTreesClassifier(n_estimators=300,
                                                    class_weight="balanced",
                                                    random_state=SEED))),
        ("clf", rf())])
    return pre, out


def run_target(name, X, y, cat_cols, num_cols):
    print("\n" + "=" * 78)
    print(f"### {name}   n={len(y)}   baseline(ทายคลาสใหญ่สุด)="
          f"{y.value_counts(normalize=True).max():.4f}   "
          f"เลขที่รายงานไว้={REPORTED[name]:.4f}")
    print("=" * 78)

    X = X[cat_cols + num_cols].copy()
    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2, random_state=SEED)
    splits = list(sss.split(X, y))

    pre, skl_arms = arms_sklearn(cat_cols, num_cols)
    scores = {k: [] for k in skl_arms}
    kappas = {k: [] for k in skl_arms}

    # ---- arm ที่ใช้ pipeline เดิม (one-hot) ----
    for label, (_, sampler_cls, tail) in skl_arms.items():
        for tr, te in splits:
            Xtr, Xte = X.iloc[tr], X.iloc[te]
            ytr, yte = y.iloc[tr], y.iloc[te]
            samp = make_smote_like(sampler_cls, ytr)
            steps = [("pre", tm._make_pre(cat_cols, num_cols))]
            if samp is not None:
                steps.append(("samp", samp))
            steps += [(n, c) for n, c in tail]
            pipe = ImbPipeline(steps)
            pipe.fit(Xtr, ytr)                    # <- fit เฉพาะ train fold
            pred = pipe.predict(Xte)
            scores[label].append(accuracy_score(yte, pred))
            kappas[label].append(cohen_kappa_score(yte, pred))

    # ---- CatBoost / LightGBM: รับ categorical เองไม่ต้อง one-hot ----
    try:
        from catboost import CatBoostClassifier
        lab = "A4    CatBoost (categorical native)"
        scores[lab], kappas[lab] = [], []
        Xc = X.copy()
        for c in cat_cols:
            Xc[c] = Xc[c].astype(str)
        cat_idx = [Xc.columns.get_loc(c) for c in cat_cols]
        for tr, te in splits:
            m = CatBoostClassifier(iterations=400, depth=4, learning_rate=0.05,
                                   auto_class_weights="Balanced",
                                   random_seed=SEED, verbose=0, allow_writing_files=False)
            m.fit(Xc.iloc[tr], y.iloc[tr], cat_features=cat_idx)
            pred = m.predict(Xc.iloc[te]).ravel()
            scores[lab].append(accuracy_score(y.iloc[te], pred))
            kappas[lab].append(cohen_kappa_score(y.iloc[te], pred))
    except ImportError:
        print("  [ข้าม] catboost ยังไม่ได้ติดตั้ง")

    try:
        from lightgbm import LGBMClassifier
        lab = "A5    LightGBM + BorderlineSMOTE"
        scores[lab], kappas[lab] = [], []
        for tr, te in splits:
            Xtr, Xte = X.iloc[tr], X.iloc[te]
            ytr, yte = y.iloc[tr], y.iloc[te]
            samp = make_smote_like(BorderlineSMOTE, ytr)
            steps = [("pre", tm._make_pre(cat_cols, num_cols))]
            if samp is not None:
                steps.append(("samp", samp))
            steps.append(("clf", LGBMClassifier(n_estimators=300, learning_rate=0.05,
                                                num_leaves=15, class_weight="balanced",
                                                random_state=SEED, verbose=-1)))
            pipe = ImbPipeline(steps)
            pipe.fit(Xtr, ytr)
            pred = pipe.predict(Xte)
            scores[lab].append(accuracy_score(yte, pred))
            kappas[lab].append(cohen_kappa_score(yte, pred))
    except ImportError:
        print("  [ข้าม] lightgbm ยังไม่ได้ติดตั้ง")

    # ---- รายงาน ----
    ctrl_key = "CTRL  RF + BorderlineSMOTE"
    ctrl = np.array(scores[ctrl_key])
    print(f"\n{'arm':34s} {'accuracy':>18s} {'kappa':>8s} "
          f"{'ต่าง CTRL':>11s} {'p (paired)':>11s}  ผลตัดสิน")
    print("-" * 100)
    verdicts = {}
    for label in scores:
        a = np.array(scores[label])
        if len(a) == 0:
            continue
        diff = a - ctrl
        if label == ctrl_key:
            pv, dtxt, ptxt = None, "     —", "     —"
        else:
            pv = stats.ttest_rel(a, ctrl).pvalue if np.std(diff) > 0 else 1.0
            dtxt, ptxt = f"{diff.mean():+.4f}", f"{pv:.4f}"
        cond_a = label != ctrl_key and a.mean() > ctrl.mean()
        cond_b = pv is not None and pv < 0.05
        cond_c = a.mean() > REPORTED[name]
        if label == ctrl_key:
            verdict = "(ตัวเทียบ)"
        elif cond_a and cond_b and cond_c:
            verdict = "*** ดีขึ้นจริง ผ่านครบ 3 ข้อ"
        else:
            miss = [n for n, ok in (("ก", cond_a), ("ข", cond_b), ("ค", cond_c)) if not ok]
            verdict = f"ไม่ผ่านข้อ {','.join(miss)}"
        verdicts[label] = verdict
        print(f"{label:34s} {a.mean():.4f} +/- {a.std():.4f} "
              f"{np.mean(kappas[label]):8.4f} {dtxt:>11s} {ptxt:>11s}  {verdict}")
    return scores


if __name__ == "__main__":
    print(__doc__)
    df = tm.load_survey()
    print(f"ข้อมูล {len(df)} แถว · split เดียวกันทุก arm "
          f"(StratifiedShuffleSplit n={N_SPLITS}, test_size=0.2, seed={SEED})")

    Xb, yb = build_buy(df)
    run_target("BUY", Xb, yb, OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM)

    Xf, yf = build_fuel(df)
    run_target("FUEL", Xf, yf, OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM)

    print("\nหมายเหตุ: ทุก arm fit เฉพาะ train fold และใช้ split ชุดเดียวกัน "
          "จึงเทียบแบบจับคู่ได้ตรง ๆ")
