"""
Confident Learning เวอร์ชันที่ถูกต้องตามระเบียบวิธี (2026-08-02)

ปัญหาของเวอร์ชันแรก: คัดตัวอย่างที่ต้องสงสัยออกจาก "ทั้งชุด" แล้ววัดใหม่
-> test set ไม่มีเคสยากเหลืออยู่ = วัดแบบวนซ้ำ (circular) ตัวเลขสูงขึ้นแบบไม่มีความหมาย

เวอร์ชันนี้: ในแต่ละ split
  1. แบ่ง train / test ก่อน
  2. รัน Confident Learning บน "train เท่านั้น"
  3. เทรนบน train ที่คัดแล้ว
  4. วัดผลบน test ที่ไม่ถูกแตะเลย (ยังมีเคสยากครบ)
= ถ้า accuracy ขึ้นจริง แปลว่าการคัด label ที่ผิดช่วยให้โมเดลเรียนได้ดีขึ้นจริง
"""
import sys, os, io, contextlib, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit, StratifiedKFold, cross_val_predict
from sklearn.metrics import accuracy_score
from sklearn.base import clone

import train_models as tm
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      NEW_BUY_CAT, NEW_BUY_NUM)

RS = tm.RANDOM_STATE
BUY_CAT = OLD_BUY_CAT + NEW_BUY_CAT
BUY_NUM = OLD_BUY_NUM + NEW_BUY_NUM


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def find_label_errors(pipe, X, y):
    """Confident Learning — คืน index ของตัวอย่างที่ต้องสงสัยว่า label ผิด"""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RS)
    proba = cross_val_predict(clone(pipe), X, y, cv=cv, method="predict_proba")
    classes = np.array(sorted(y.unique()))
    ci = {c: i for i, c in enumerate(classes)}
    thr = {c: proba[[i for i in range(len(y)) if y.iloc[i] == c], ci[c]].mean() for c in classes}
    sus = []
    for i in range(len(y)):
        g = y.iloc[i]
        for c in classes:
            if c != g and proba[i, ci[c]] >= thr[c] and proba[i, ci[c]] > proba[i, ci[g]]:
                sus.append(i); break
    return sus


if __name__ == "__main__":
    df = tm.load_survey()
    X, y = quiet(build_buy, df)
    pipe, name, m0, _sc, _sn = quiet(tm.build_and_select, X, y, BUY_CAT, BUY_NUM, alpha=0.10)
    base = y.value_counts(normalize=True).max()

    print("=" * 74)
    print("CONFIDENT LEARNING — เวอร์ชันถูกต้อง (คัดเฉพาะใน train, วัดบน test ที่ไม่ถูกแตะ)")
    print("=" * 74)
    print(f"  โมเดล {name} | n={len(y)} | baseline {base:.4f}")
    print(f"  ค่าอ้างอิงเดิม (ไม่คัดอะไรเลย): {m0['test_accuracy_repeated_mean']:.4f}\n")

    sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=RS)
    acc_raw, acc_clean, n_removed = [], [], []
    for k, (tr, te) in enumerate(sss.split(X, y), 1):
        Xtr = X.iloc[tr].reset_index(drop=True); ytr = y.iloc[tr].reset_index(drop=True)
        Xte, yte = X.iloc[te], y.iloc[te]

        p_raw = clone(pipe); p_raw.fit(Xtr, ytr)
        acc_raw.append(accuracy_score(yte, p_raw.predict(Xte)))

        sus = set(find_label_errors(pipe, Xtr, ytr))       # <-- ใช้เฉพาะ train
        keep = [i for i in range(len(ytr)) if i not in sus]
        n_removed.append(len(sus))
        if len(set(ytr.iloc[keep])) < 2:
            acc_clean.append(acc_raw[-1]); continue
        p_cl = clone(pipe); p_cl.fit(Xtr.iloc[keep], ytr.iloc[keep])
        acc_clean.append(accuracy_score(yte, p_cl.predict(Xte)))   # <-- test เดิมครบทุกเคส

    print(f"  คัดออกเฉลี่ย {np.mean(n_removed):.1f} จาก {len(tr)} แถวของ train "
          f"({np.mean(n_removed)/len(tr)*100:.1f}%)\n")
    print(f"  {'':30}{'accuracy':>18}{'lift เทียบ baseline':>22}")
    print(f"  {'ไม่คัด (train เต็ม)':30}{np.mean(acc_raw):>18.4f}{np.mean(acc_raw)-base:>+22.4f}")
    print(f"  {'คัด label ผิดใน train แล้ว':30}{np.mean(acc_clean):>18.4f}{np.mean(acc_clean)-base:>+22.4f}")
    print(f"\n  ส่วนต่าง: {np.mean(acc_clean)-np.mean(acc_raw):+.4f} "
          f"(sd ของส่วนต่าง = {np.std(np.array(acc_clean)-np.array(acc_raw)):.4f})")

    diff = np.array(acc_clean) - np.array(acc_raw)
    from scipy.stats import ttest_rel
    t, p = ttest_rel(acc_clean, acc_raw)
    print(f"  paired t-test: t={t:.3f}, p={p:.4f} "
          f"{'-> มีนัยสำคัญ' if p < 0.05 else '-> ไม่มีนัยสำคัญ'}")
    print("\n  เทียบกับตัวเลข 86.7% ที่ได้จากวิธีคัดทั้งชุด: ตัวเลขนั้นเกิดจากการ")
    print("  เอาเคสยากออกจาก test ด้วย จึงไม่ใช่ผลที่นำไปรายงานได้")
