"""
เปรียบเทียบผลบนกลุ่มตัวอย่างเต็ม vs กลุ่มตัวอย่างที่ปรับสมดุลคลาส (2026-08-02)

ที่มา: กลุ่มตัวอย่างรอบนี้เก็บ ICE เพิ่มโดยตั้งใจจนเป็น 264/500 = 52.8%
(oversampling by design) ทำให้ majority-class baseline สูงถึง 53.16%
กลุ่มตัวอย่างจึงไม่ได้เป็นตัวแทนสัดส่วนประชากรอยู่แล้ว การรายงานผลบนกลุ่มที่
สมดุลจึงเป็นการประเมินที่ตรงกับความสามารถของโมเดลมากกว่า

⚠️ ข้อควรระวังเชิงระเบียบวิธี: การตัดสินใจนี้เกิดขึ้น "หลัง" เห็นผลของกลุ่มเต็มแล้ว
จึงต้องรายงานผลทั้งสองแบบเสมอ ห้ามเลือกรายงานเฉพาะแบบที่ตัวเลขดีกว่า

วิธี: สุ่มลดจำนวนคลาสที่มากเกินให้เท่ากับคลาสที่น้อยที่สุด (random undersampling)
ทำซ้ำ 10 ครั้งด้วย seed ต่างกัน เพื่อไม่ให้ผลขึ้นกับการสุ่มครั้งเดียว
"""
import sys, os, io, contextlib, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import train_models as tm
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      NEW_BUY_CAT, NEW_BUY_NUM, OLD_FUEL_CAT, OLD_FUEL_NUM,
                      NEW_FUEL_CAT, NEW_FUEL_NUM)

BUY_CAT, BUY_NUM = OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM
FUEL_CAT, FUEL_NUM = OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM
N_REPEATS = 10


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **kw)


def evaluate(X, y, cat, num, alpha, fk):
    _, name, m, _, _ = quiet(tm.build_and_select, X, y, cat, num, alpha=alpha, force_keep=fk)
    base = y.value_counts(normalize=True).max()
    return {
        "model": name,
        "acc": m["test_accuracy_repeated_mean"],
        "std": m["test_accuracy_repeated_std"],
        "base": base,
        "lift": m["test_accuracy_repeated_mean"] - base,
    }


def balance(X, y, seed):
    """สุ่มลดคลาสที่มากเกินให้เท่ากับคลาสที่น้อยที่สุด"""
    rng = np.random.RandomState(seed)
    n_min = y.value_counts().min()
    keep = []
    for cls in y.unique():
        idx = np.where(y.values == cls)[0]
        keep.extend(rng.choice(idx, size=n_min, replace=False))
    keep = sorted(keep)
    return X.iloc[keep].reset_index(drop=True), y.iloc[keep].reset_index(drop=True)


def run(tag, X, y, cat, num, alpha, fk):
    print("\n" + "=" * 78)
    print(f"### {tag}")
    print("=" * 78)

    full = evaluate(X, y, cat, num, alpha, fk)
    dist = dict(y.value_counts())
    print(f"  [กลุ่มเต็ม]  n={len(y)}  {dist}")
    print(f"      โมเดล {full['model']:6s} | accuracy {full['acc']:.4f} ± {full['std']:.4f} "
          f"| baseline {full['base']:.4f} | lift {full['lift']:+.4f}")

    accs, lifts, bases, models = [], [], [], []
    for s in range(N_REPEATS):
        Xb, yb = balance(X, y, seed=tm.RANDOM_STATE + s)
        r = evaluate(Xb, yb, cat, num, alpha, fk)
        accs.append(r["acc"]); lifts.append(r["lift"]); bases.append(r["base"])
        models.append(r["model"])
    n_bal = len(yb)
    from collections import Counter
    print(f"\n  [กลุ่มสมดุล] n={n_bal}  {dict(yb.value_counts())}  "
          f"(สุ่มลด {N_REPEATS} ครั้ง)")
    print(f"      โมเดลที่ถูกเลือก: {dict(Counter(models))}")
    print(f"      accuracy {np.mean(accs):.4f} ± {np.std(accs):.4f} "
          f"(ช่วง {min(accs):.4f}–{max(accs):.4f})")
    print(f"      baseline {np.mean(bases):.4f} | lift {np.mean(lifts):+.4f} ± {np.std(lifts):.4f}")
    print(f"\n  -> accuracy เปลี่ยน {np.mean(accs)-full['acc']:+.4f} | "
          f"lift เปลี่ยน {np.mean(lifts)-full['lift']:+.4f}")
    return full, {"acc": np.mean(accs), "lift": np.mean(lifts), "base": np.mean(bases), "n": n_bal}


if __name__ == "__main__":
    df = tm.load_survey()
    Xb, yb_ = quiet(build_buy, df)
    Xf, yf_ = quiet(build_fuel, df)

    print("เปรียบเทียบผล: กลุ่มตัวอย่างเต็ม vs กลุ่มตัวอย่างที่ปรับสมดุลคลาส")
    print("(รายงานทั้งสองแบบเสมอ ตามที่ระบุไว้ใน docstring)")

    bf, bb = run("BUY — ซื้อ / ไม่ซื้อ", Xb, yb_, BUY_CAT, BUY_NUM, 0.10, None)
    ff, fb = run("FUEL — EV / Hybrid / ICE", Xf, yf_, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])

    print("\n" + "=" * 78)
    print("สรุปเปรียบเทียบ")
    print("=" * 78)
    print(f"  {'':8}{'':>10}{'accuracy':>12}{'baseline':>12}{'lift':>12}")
    for tag, f, b in (("BUY", bf, bb), ("FUEL", ff, fb)):
        print(f"  {tag:8}{'เต็ม':>10}{f['acc']:>12.4f}{f['base']:>12.4f}{f['lift']:>+12.4f}")
        print(f"  {'':8}{'สมดุล':>10}{b['acc']:>12.4f}{b['base']:>12.4f}{b['lift']:>+12.4f}")
