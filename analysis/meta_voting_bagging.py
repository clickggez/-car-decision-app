"""
Meta-classifier: Voting vs Bagging  [2026-08-09]

ที่มา
-----
อาจารย์ที่ปรึกษาให้ใช้ meta-classifier โดยเลือก **voting หรือ bagging** ก็ได้
สคริปต์นี้วัดทั้งสองแบบด้วยโปรโตคอลเดียวกัน เพื่อให้เลือกโดยมีตัวเลขรองรับ
ไม่ใช่เลือกตามความรู้สึก

สถานะเดิมในโค้ด
---------------
- `train_models.py:665` มี **soft VotingClassifier** อยู่แล้ว และเข้าแข่งเป็น candidate
  ชื่อ `ENSEMBLE` แต่ **ไม่เคยมีบันทึกว่าได้คะแนนเท่าไหร่** ในไฟล์ผลใด ๆ
- `train_models.py:686` มี StackingClassifier (`STACK`)
- **ไม่มี BaggingClassifier** — RandomForest/ExtraTrees เป็นตระกูล bagging ก็จริง
  แต่ไม่ใช่ meta ที่ห่อโมเดลฐานที่จูนแล้ว ซึ่งเป็นสิ่งที่อาจารย์หมายถึง

สิ่งที่เทียบ (3 ตัว บนโปรโตคอลเดียวกันเป๊ะ)
------------------------------------------
  1. BEST   = โมเดลเดี่ยวที่ดีที่สุดจาก CV (ตัวที่ pipeline ใช้อยู่ตอนนี้)
  2. VOTING = soft voting ของโมเดลฐานที่จูนแล้วทุกตัว (เหมือน `ENSEMBLE` ในโค้ดหลัก)
  3. BAGGING= BaggingClassifier ห่อโมเดลเดี่ยวที่ดีที่สุด (n_estimators=25)

⚠️ ประกาศล่วงหน้าก่อนรัน (pre-registration)
-------------------------------------------
1. วัดด้วย **20 random splits** ชุดเดียวกันทั้ง 3 โมเดล (§4.1 ของ 00-READ-FIRST.md)
2. รายงาน accuracy / balanced acc / macro F1 / kappa **ครบทุกตัว ไม่ว่าดีขึ้นหรือแย่ลง** (§3.5)
3. `N_BAGS = 25` ตรึงไว้ก่อนรัน ห้ามไล่ปรับจนตัวเลขสวย
4. เกณฑ์ตัดสิน: **"ได้ตัวเลขที่เทียบ voting กับ bagging ได้อย่างเป็นธรรม"**
   ไม่ใช่ "accuracy สูงขึ้น" — ถ้าทั้งคู่แพ้โมเดลเดี่ยวก็ต้องรายงานตามนั้น
5. ส่วนต่างที่เล็กกว่าค่า std ถือว่า **ไม่มีนัยสำคัญ** ห้ามเคลมว่าดีกว่า

หมายเหตุ
--------
สคริปต์นี้ **ไม่แตะ `.pkl` ที่ deploy อยู่ และไม่แก้ `train_models.py`** — วิเคราะห์อย่างเดียว
โปรโตคอลการจูน (จูนบนข้อมูลทั้งหมด แล้ววัดบน 20 splits) เป็นแบบเดียวกับ pipeline หลัก
ซึ่งตรวจด้วย nested CV แล้วว่าต่างกัน <3 จุด (`full_analysis.py` #5)
"""
import sys, os, io, contextlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit, StratifiedKFold
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             f1_score, cohen_kappa_score)
from sklearn.base import clone
from sklearn.ensemble import VotingClassifier, BaggingClassifier
from imblearn.pipeline import Pipeline   # ต้องเป็นของ imblearn เพราะมี SMOTE เป็น step กลาง

import train_models as tm
from ablation import (build_buy, build_fuel,
                      OLD_BUY_CAT, OLD_BUY_NUM, NEW_BUY_CAT, NEW_BUY_NUM,
                      OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM)

N_SPLITS = 20
N_BAGS = 25          # ตรึงก่อนรัน
CV_FOLDS = 5


def tune_bases(X, y, cat_cols, num_cols):
    """จูนโมเดลฐานทุกตัวด้วยเครื่องมือเดียวกับ train_models.py"""
    pre = tm._make_pre(cat_cols, num_cols)
    smote = tm.make_smote(y)
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=tm.RANDOM_STATE)
    tuned, scores = {}, {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for name, (base_clf, grid) in tm._model_specs().items():
            clf, score, _params = tm._tune(name, base_clf, grid, pre, smote, X, y, cv)
            if clf is not None:
                tuned[name] = clf
                scores[name] = score
    return pre, smote, tuned, scores


def wrap(pre, smote, clf):
    steps = [("pre", pre)]
    if smote is not None:
        steps.append(("smote", smote))
    steps.append(("clf", clf))
    return Pipeline(steps)


def eval_pipes(pipes, X, y):
    """วัดทุก pipeline บน 20 splits ชุดเดียวกัน"""
    out = {k: {m: [] for m in ("acc", "bal", "f1", "kappa")} for k in pipes}
    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2,
                                 random_state=tm.RANDOM_STATE)
    for si, (tr, te) in enumerate(sss.split(X, y), 1):
        Xtr, ytr, Xte, yte = X.iloc[tr], y.iloc[tr], X.iloc[te], y.iloc[te]
        for k, pipe in pipes.items():
            p = clone(pipe)
            p.fit(Xtr, ytr)
            yp = p.predict(Xte)
            out[k]["acc"].append(accuracy_score(yte, yp))
            out[k]["bal"].append(balanced_accuracy_score(yte, yp))
            out[k]["f1"].append(f1_score(yte, yp, average="macro", zero_division=0))
            out[k]["kappa"].append(cohen_kappa_score(yte, yp))
        print(f"    split {si:2d}/{N_SPLITS} เสร็จ", flush=True)
    return out


def run(tag, X, y, cat_cols, num_cols):
    print(f"\n{'='*76}\n### {tag}   (n={len(y)})\n{'='*76}")
    baseline = float(y.value_counts(normalize=True).max())
    print(f"  baseline (ทายคลาสใหญ่สุดเสมอ) = {baseline:.4f}")

    pre, smote, tuned, scores = tune_bases(X, y, cat_cols, num_cols)
    best_name = max(scores, key=scores.get)
    print(f"  โมเดลฐานที่จูนได้ : {', '.join(f'{n}={scores[n]:.3f}' for n in sorted(scores, key=scores.get, reverse=True))}")
    print(f"  โมเดลเดี่ยวที่ดีที่สุด: {best_name}")

    pipes = {
        "BEST (เดี่ยว)": wrap(pre, smote, clone(tuned[best_name])),
        "VOTING (soft)": wrap(pre, smote, VotingClassifier(
            estimators=[(n, clone(c)) for n, c in tuned.items()], voting="soft")),
        f"BAGGING x{N_BAGS}": wrap(pre, smote, BaggingClassifier(
            estimator=clone(tuned[best_name]), n_estimators=N_BAGS,
            random_state=tm.RANDOM_STATE, n_jobs=-1)),
    }
    res = eval_pipes(pipes, X, y)

    print(f"\n  {'โมเดล':<16s} {'accuracy':>17s} {'balanced':>10s} {'macroF1':>10s} {'kappa':>10s} {'lift':>9s}")
    print("  " + "-" * 78)
    for k in pipes:
        a, s = np.mean(res[k]["acc"]), np.std(res[k]["acc"])
        print(f"  {k:<16s} {a:>8.4f} ± {s:.4f} {np.mean(res[k]['bal']):>10.4f} "
              f"{np.mean(res[k]['f1']):>10.4f} {np.mean(res[k]['kappa']):>10.4f} "
              f"{a-baseline:>+9.4f}")

    base_acc = np.mean(res["BEST (เดี่ยว)"]["acc"])
    base_std = np.std(res["BEST (เดี่ยว)"]["acc"])
    print(f"\n  เทียบกับโมเดลเดี่ยว (std = {base_std:.4f} — ส่วนต่างที่เล็กกว่านี้ถือว่าไม่มีนัยสำคัญ)")
    for k in pipes:
        if k == "BEST (เดี่ยว)":
            continue
        d = np.mean(res[k]["acc"]) - base_acc
        verdict = "ไม่มีนัยสำคัญ" if abs(d) < base_std else ("ดีกว่าจริง" if d > 0 else "แย่กว่าจริง")
        print(f"    {k:<16s} {d:>+8.4f}  -> {verdict}")
    return res


if __name__ == "__main__":
    print("=" * 76)
    print("Meta-classifier: VOTING vs BAGGING (ตามที่อาจารย์ที่ปรึกษาให้เลือก)")
    print(f"20 random splits | N_BAGS={N_BAGS} ตรึงก่อนรัน | รายงานทุกผลไม่ว่าดีขึ้นหรือแย่ลง")
    print("=" * 76)

    df = tm.load_survey()

    Xb, yb = build_buy(df)
    run("BUY (ซื้อ/ไม่ซื้อ)", Xb, yb,
        OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM)

    Xf, yf = build_fuel(df)
    run("FUEL (EV/Hybrid/ICE)", Xf, yf,
        OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM)
