"""
ทางเลือกเชิงระเบียบวิธีที่เหลือ (2026-08-01) — ทดสอบว่าได้ตัวเลขเท่าไหร่
  1. FUEL 2 คลาส: electrified (EV+Hybrid) vs ICE
  2. FUEL top-2 accuracy (DSS แนะนำ 2 ตัวเลือก)
  3. BUY: balanced accuracy / ROC-AUC
ทุกตัววัดด้วย 20 random splits เหมือน pipeline หลัก — ไม่มีการเลือก seed
"""
import sys, os, io, contextlib
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, f1_score
from sklearn.base import clone

import train_models as tm
from models import feature_encoding as fe
from ablation import build_buy, build_fuel, OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM
from ablation import OLD_BUY_CAT, OLD_BUY_NUM, NEW_BUY_CAT, NEW_BUY_NUM


def fit_best(X, y, cat_cols, num_cols, alpha, force_keep):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, metrics, sc, sn = tm.build_and_select(
            X, y, cat_cols, num_cols, alpha=alpha, force_keep=force_keep)
    return pipe, name, metrics


def repeated_eval(pipe, X, y, n_splits=20, topk=False):
    """ประเมินซ้ำ 20 random splits — คืน accuracy / balanced acc / top-2 / auc"""
    sss = StratifiedShuffleSplit(n_splits=n_splits, test_size=0.2, random_state=tm.RANDOM_STATE)
    accs, bals, top2s, aucs, f1s = [], [], [], [], []
    for tr, te in sss.split(X, y):
        p = clone(pipe)
        p.fit(X.iloc[tr], y.iloc[tr])
        yp = p.predict(X.iloc[te])
        yt = y.iloc[te]
        accs.append(accuracy_score(yt, yp))
        bals.append(balanced_accuracy_score(yt, yp))
        f1s.append(f1_score(yt, yp, average="macro", zero_division=0))
        proba = p.predict_proba(X.iloc[te])
        classes = list(p.classes_)
        if topk:
            order = np.argsort(-proba, axis=1)[:, :2]
            hit = [yt.iloc[i] in [classes[j] for j in order[i]] for i in range(len(yt))]
            top2s.append(np.mean(hit))
        if len(classes) == 2:
            pos = classes[1]
            aucs.append(roc_auc_score((yt == pos).astype(int), proba[:, 1]))
        else:
            try:
                aucs.append(roc_auc_score(yt, proba, multi_class="ovr", average="macro"))
            except ValueError:
                pass
    out = {
        "acc": (np.mean(accs), np.std(accs)),
        "bal": (np.mean(bals), np.std(bals)),
        "f1": (np.mean(f1s), np.std(f1s)),
    }
    if aucs:
        out["auc"] = (np.mean(aucs), np.std(aucs))
    if top2s:
        out["top2"] = (np.mean(top2s), np.std(top2s))
    return out


def show(tag, res, baseline=None):
    print(f"\n### {tag}")
    if baseline is not None:
        print(f"  baseline (ทายคลาสใหญ่สุด) = {baseline:.4f}")
    for k, label in (("acc", "accuracy      "), ("bal", "balanced acc  "),
                     ("f1", "macro F1      "), ("auc", "ROC-AUC       "),
                     ("top2", "top-2 accuracy")):
        if k in res:
            m, s = res[k]
            extra = ""
            if k == "acc" and baseline is not None:
                extra = f"   (lift เทียบ baseline: {m-baseline:+.4f})"
            print(f"  {label}: {m:.4f} +/- {s:.4f}{extra}")


if __name__ == "__main__":
    df = tm.load_survey()

    # ---------- FUEL ----------
    Xf, yf = build_fuel(df)
    fcat = OLD_FUEL_CAT + NEW_FUEL_CAT
    fnum = OLD_FUEL_NUM + NEW_FUEL_NUM

    print("=" * 72)
    print("FUEL — ทางเลือกที่ 1: 3 คลาสเดิม (EV/Hybrid/ICE) + top-2 accuracy")
    print("=" * 72)
    base3 = yf.value_counts(normalize=True).max()
    pipe3, name3, _ = fit_best(Xf, yf, fcat, fnum, 0.15, ["prev_car"])
    r3 = repeated_eval(pipe3, Xf, yf, topk=True)
    show(f"FUEL 3 คลาส (โมเดล {name3}) n={len(yf)}", r3, base3)

    # baseline ของ top-2: แนะนำ 2 คลาสใหญ่สุดเสมอโดยไม่ใช้โมเดลเลย
    top2_base = float(yf.value_counts(normalize=True).nlargest(2).sum())
    print(f"\n  [baseline ของ top-2] แนะนำ 2 คลาสใหญ่สุดเสมอ = {top2_base:.4f}")
    print(f"  -> top-2 ของโมเดลต้องชนะค่านี้ถึงจะถือว่ามีประโยชน์จริง")

    # ---------- BUY ----------
    print()
    print("=" * 72)
    print("BUY — ตัวชี้วัดอื่นนอกจาก raw accuracy")
    print("=" * 72)
    Xb, yb = build_buy(df)
    baseb = yb.value_counts(normalize=True).max()
    pipeb, nameb, _ = fit_best(Xb, yb, OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM, 0.10, None)
    rb = repeated_eval(pipeb, Xb, yb)
    show(f"BUY (โมเดล {nameb}) n={len(yb)}", rb, baseb)
