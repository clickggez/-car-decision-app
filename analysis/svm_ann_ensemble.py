"""
ทดสอบ SVM + ANN แบบผสมสองตัวล้วน (2026-08-02)

ที่มา: การทดลอง ensemble ก่อนหน้าใช้ทั้ง 5 อัลกอริทึมรวมกัน (SVM/ANN/RF/GB/XGB)
ยังไม่เคยทดสอบการผสมเฉพาะ SVM กับ ANN ซึ่งเป็นสองอัลกอริทึมที่เอกสารโครงการ
หัวข้อ 3.3 ระบุไว้โดยตรง — จึงอยู่ในขอบเขตของระเบียบวิธีที่กำหนดไว้เดิม

ทดสอบ 3 รูปแบบ:
  1. soft voting  — เฉลี่ยความน่าจะเป็นจากทั้งสองโมเดลเท่า ๆ กัน
  2. weighted     — ถ่วงน้ำหนักตามคะแนน CV ของแต่ละตัว (ไม่ใช่ปรับจนตัวเลขสวย)
  3. stacking     — ใช้ LogisticRegression เรียนรู้วิธีผสมจากข้อมูล

เทียบกับ SVM เดี่ยวและ ANN เดี่ยว วัดด้วย 20 random splits เหมือนกันทุกตัว
รายงานผลทุกแบบไม่ว่าดีขึ้นหรือแย่ลง
"""
import sys, os, io, contextlib, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.ensemble import VotingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedShuffleSplit, StratifiedKFold, GridSearchCV
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.base import clone
from imblearn.pipeline import Pipeline

import train_models as tm
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      NEW_BUY_CAT, NEW_BUY_NUM, OLD_FUEL_CAT, OLD_FUEL_NUM,
                      NEW_FUEL_CAT, NEW_FUEL_NUM)

RS = tm.RANDOM_STATE
BUY_CAT, BUY_NUM = OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM
FUEL_CAT, FUEL_NUM = OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def tune(name, X, y, pre, smote, cv):
    base, grid = tm._model_specs()[name]
    steps = [("pre", pre)] + ([("smote", smote)] if smote else []) + [("clf", base)]
    g = GridSearchCV(Pipeline(steps), grid, cv=cv, scoring="balanced_accuracy", n_jobs=-1)
    g.fit(X, y)
    return g.best_estimator_.named_steps["clf"], float(g.best_score_)


def make_pipe(pre, smote, clf):
    steps = [("pre", pre)] + ([("smote", smote)] if smote else []) + [("clf", clf)]
    return Pipeline(steps)


def repeated(pipe, X, y, n=20):
    sss = StratifiedShuffleSplit(n_splits=n, test_size=0.2, random_state=RS)
    a, b, f = [], [], []
    for tr, te in sss.split(X, y):
        p = clone(pipe); p.fit(X.iloc[tr], y.iloc[tr])
        pred = p.predict(X.iloc[te]); yt = y.iloc[te]
        a.append(accuracy_score(yt, pred))
        b.append(balanced_accuracy_score(yt, pred))
        f.append(f1_score(yt, pred, average="macro", zero_division=0))
    return np.mean(a), np.std(a), np.mean(b), np.mean(f)


def run(tag, X, y, cat, num, alpha, fk):
    print("\n" + "=" * 80)
    print(f"### {tag}   n={len(y)}")
    print("=" * 80)
    sel_cat, sel_num = quiet(tm.select_features, X, y, cat, num, alpha=alpha, force_keep=fk)
    pre = tm._make_pre(sel_cat, sel_num)
    smote = quiet(tm.make_smote, y)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RS)

    svm, cv_svm = tune("SVM", X, y, pre, smote, cv)
    ann, cv_ann = tune("ANN", X, y, pre, smote, cv)
    print(f"  จูนแล้ว — SVM CV={cv_svm:.4f} | ANN CV={cv_ann:.4f}\n")

    w = [cv_svm, cv_ann]
    cands = {
        "SVM เดี่ยว":            svm,
        "ANN เดี่ยว":            ann,
        "SVM+ANN soft voting":  VotingClassifier([("svm", svm), ("ann", ann)], voting="soft"),
        "SVM+ANN ถ่วงน้ำหนัก CV": VotingClassifier([("svm", svm), ("ann", ann)],
                                                  voting="soft", weights=w),
        "SVM+ANN stacking":     StackingClassifier(
                                    [("svm", svm), ("ann", ann)],
                                    final_estimator=LogisticRegression(
                                        max_iter=1000, class_weight="balanced"), cv=3),
    }
    base = y.value_counts(normalize=True).max()
    print(f"  {'วิธี':26}{'accuracy':>18}{'balanced':>11}{'macro F1':>11}{'lift':>10}")
    best = None
    for name, clf in cands.items():
        try:
            m, s, ba, f1 = repeated(make_pipe(pre, smote, clf), X, y)
        except Exception as e:
            print(f"  {name:26}  ข้าม — {type(e).__name__}")
            continue
        mark = ""
        if best is None or m > best[1]:
            best = (name, m)
        print(f"  {name:26}{m:>11.4f} ±{s:.3f}{ba:>11.4f}{f1:>11.4f}{m-base:>+10.4f}{mark}")
    print(f"\n  baseline (ทายคลาสใหญ่สุด) = {base:.4f}")
    print(f"  -> ดีที่สุด: {best[0]} ({best[1]:.4f})")
    return best, base


if __name__ == "__main__":
    df = tm.load_survey()
    Xb, yb = quiet(build_buy, df)
    Xf, yf = quiet(build_fuel, df)
    print("ทดสอบการผสม SVM + ANN (สองอัลกอริทึมตามที่เอกสารโครงการหัวข้อ 3.3 ระบุ)")
    print("วัดด้วย 20 random splits ทุกตัว — รายงานผลทุกแบบไม่ว่าดีขึ้นหรือแย่ลง")

    run("BUY — ซื้อ / ไม่ซื้อ", Xb, yb, BUY_CAT, BUY_NUM, 0.10, None)
    run("FUEL — EV / Hybrid / ICE", Xf, yf, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
