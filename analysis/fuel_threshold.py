"""
FUEL — Per-class decision threshold (prior correction)  [2026-08-08]

ปัญหาที่ต้องการแก้
------------------
โมเดล FUEL ยุบไปทายคลาสใหญ่ (ICE) เกือบทั้งหมด ทำให้ recall ของ EV/Hybrid ต่ำมาก
และ Cohen's kappa เข้าใกล้ 0 (Auto-WEKA ที่รันด้วย -metric errorRate ได้ kappa ติดลบ)
สคริปต์นี้ทดสอบว่า "การปรับ decision threshold หลังเทรน" แก้อาการนี้ได้หรือไม่
โดยไม่ต้องเทรนใหม่ ไม่ต้องเพิ่มข้อมูล และไม่ต้องแก้ฟอร์มเว็บ

วิธี
----
แทนที่จะทำนายด้วย argmax(P(c|x)) ตรง ๆ ให้ทำนายด้วย
        argmax_c  P(c|x) / prior(c)^alpha
alpha = 0 คือพฤติกรรมเดิม (ไม่แก้อะไร)  alpha = 1 คือหักล้าง prior เต็มที่
เลือกครอบครัวพารามิเตอร์เดียว (alpha) แทน grid 3 มิติอิสระ เพราะ
  (ก) อธิบายได้ว่ามาจากทฤษฎี prior correction ไม่ใช่จูนมั่ว
  (ข) มีพารามิเตอร์เดียว โอกาส overfit ต่ำกว่ามาก

⚠️ ประกาศล่วงหน้าก่อนรัน (pre-registration) — ห้ามแก้ 5 ข้อนี้หลังเห็นผล
----------------------------------------------------------------------
1. ALPHA_GRID ตรึงไว้ที่ [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
2. เลือก alpha จาก **train เท่านั้น** ด้วย inner 5-fold CV — test ไม่ถูกแตะระหว่างจูน
   (ถ้าเลือก alpha จาก test จะเป็นกับดักเดียวกับ Confident Learning ใน §3.1
    ของ 00-READ-FIRST.md ที่ทำให้ได้ 86.7% ปลอม)
3. เกณฑ์ที่ใช้เลือก alpha = **macro F1** ประกาศไว้ก่อน ไม่ใช่ accuracy
   เพราะเป้าหมายคือให้โมเดลทายคลาสน้อยได้ ไม่ใช่ดัน accuracy รวม
4. วัดด้วย 20 random splits เหมือน pipeline หลักทุกประการ (§4.1)
5. **รายงานทุกตัวชี้วัดไม่ว่าดีขึ้นหรือแย่ลง** — accuracy คาดว่า *จะลดลง*
   เพราะการทายคลาสน้อยเพิ่มขึ้นย่อมแลกมาด้วย accuracy รวมที่ต่ำลง
   เกณฑ์ตัดสินว่างานนี้สำเร็จคือ "ได้ตัวเลขที่ตรวจสอบได้ว่า trade-off เป็นเท่าไหร่"
   ไม่ใช่ "accuracy สูงขึ้น"

หมายเหตุการนำไป deploy
----------------------
รันทั้งชุดฟีเจอร์เดิม (ฟอร์มเว็บปัจจุบันรองรับ) และเดิม+ใหม่
ชุดเดิมคือชุดที่นำไปใช้บนเว็บได้ทันทีโดยไม่ต้องแก้ predict_fuel.html
สคริปต์นี้ **ไม่แตะ .pkl ที่ deploy อยู่** — วิเคราะห์อย่างเดียว
"""
import sys, os, io, contextlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit, StratifiedKFold
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
                             cohen_kappa_score, recall_score, confusion_matrix)
from sklearn.base import clone

import train_models as tm
from ablation import build_fuel, OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM

ALPHA_GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]   # ตรึงก่อนรัน — ห้ามแก้
N_SPLITS = 20
INNER_FOLDS = 5


def apply_alpha(proba, priors, alpha):
    """ปรับ posterior ด้วย prior^alpha แล้วคืน index ของคลาสที่ชนะ"""
    adj = proba / np.power(priors, alpha)
    return np.argmax(adj, axis=1)


def pick_alpha_on_train(pipe, X_tr, y_tr):
    """เลือก alpha ด้วย inner CV บน train เท่านั้น — test ไม่ถูกแตะ"""
    skf = StratifiedKFold(n_splits=INNER_FOLDS, shuffle=True, random_state=tm.RANDOM_STATE)
    scores = {a: [] for a in ALPHA_GRID}
    for itr, iva in skf.split(X_tr, y_tr):
        p = clone(pipe)
        p.fit(X_tr.iloc[itr], y_tr.iloc[itr])
        classes = np.array(p.classes_)
        proba = p.predict_proba(X_tr.iloc[iva])
        y_in = y_tr.iloc[itr]
        priors = np.array([(y_in == c).mean() for c in classes])
        y_va = y_tr.iloc[iva]
        for a in ALPHA_GRID:
            yp = classes[apply_alpha(proba, priors, a)]
            scores[a].append(f1_score(y_va, yp, average="macro", zero_division=0))
    mean_scores = {a: float(np.mean(v)) for a, v in scores.items()}
    best = max(mean_scores, key=lambda a: (mean_scores[a], -a))   # เสมอกัน -> เลือก alpha น้อยกว่า
    return best, mean_scores


def evaluate(X, y, cat_cols, num_cols, tag):
    print(f"\n{'='*74}\n### {tag}   (n={len(y)}, cat={len(cat_cols)}, num={len(num_cols)})\n{'='*74}")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, metrics, _sc, _sn = tm.build_and_select(
            X, y, cat_cols, num_cols, alpha=0.15, force_keep=["prev_car"])
    baseline = float(y.value_counts(normalize=True).max())
    print(f"  โมเดลที่เลือก : {name}")
    print(f"  baseline (ทายคลาสใหญ่สุดเสมอ) = {baseline:.4f}")

    classes_all = sorted(y.unique())
    res = {k: {m: [] for m in ("acc", "bal", "f1", "kappa")} for k in ("base", "tuned")}
    rec = {k: {c: [] for c in classes_all} for k in ("base", "tuned")}
    chosen, cms = [], []

    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2, random_state=tm.RANDOM_STATE)
    for si, (tr, te) in enumerate(sss.split(X, y), 1):
        X_tr, y_tr = X.iloc[tr], y.iloc[tr]
        X_te, y_te = X.iloc[te], y.iloc[te]

        a_best, _ = pick_alpha_on_train(pipe, X_tr, y_tr)
        chosen.append(a_best)

        p = clone(pipe)
        p.fit(X_tr, y_tr)
        classes = np.array(p.classes_)
        priors = np.array([(y_tr == c).mean() for c in classes])
        proba = p.predict_proba(X_te)

        for key, a in (("base", 0.0), ("tuned", a_best)):
            yp = classes[apply_alpha(proba, priors, a)]
            res[key]["acc"].append(accuracy_score(y_te, yp))
            res[key]["bal"].append(balanced_accuracy_score(y_te, yp))
            res[key]["f1"].append(f1_score(y_te, yp, average="macro", zero_division=0))
            res[key]["kappa"].append(cohen_kappa_score(y_te, yp))
            r = recall_score(y_te, yp, labels=classes_all, average=None, zero_division=0)
            for c, v in zip(classes_all, r):
                rec[key][c].append(v)
            if key == "tuned":
                cms.append(confusion_matrix(y_te, yp, labels=classes_all))
        print(f"    split {si:2d}/{N_SPLITS}: alpha ที่เลือกจาก train = {a_best}", flush=True)

    print(f"\n  alpha ที่ถูกเลือก: " +
          ", ".join(f"{a}x{chosen.count(a)}" for a in ALPHA_GRID if chosen.count(a)))

    print(f"\n  {'ตัวชี้วัด':<16s} {'เดิม (alpha=0)':>18s} {'ปรับ threshold':>18s} {'ส่วนต่าง':>12s}")
    print("  " + "-" * 68)
    for m, label in (("acc", "accuracy"), ("bal", "balanced acc"),
                     ("f1", "macro F1"), ("kappa", "Cohen kappa")):
        b, t = np.mean(res["base"][m]), np.mean(res["tuned"][m])
        bs, ts = np.std(res["base"][m]), np.std(res["tuned"][m])
        print(f"  {label:<16s} {b:>8.4f} ± {bs:.4f} {t:>8.4f} ± {ts:.4f} {t-b:>+12.4f}")

    print(f"\n  recall รายคลาส (สัดส่วนที่โมเดลจับได้จริง)")
    print(f"  {'คลาส':<12s} {'n':>5s} {'เดิม':>12s} {'ปรับ':>12s} {'ส่วนต่าง':>12s}")
    print("  " + "-" * 58)
    for c in classes_all:
        b, t = np.mean(rec["base"][c]), np.mean(rec["tuned"][c])
        print(f"  {str(c):<12s} {int((y==c).sum()):>5d} {b:>12.4f} {t:>12.4f} {t-b:>+12.4f}")

    cm = np.mean(cms, axis=0)
    print(f"\n  confusion matrix เฉลี่ย {N_SPLITS} splits หลังปรับ threshold (แถว=จริง, คอลัมน์=ทาย)")
    print("           " + "".join(f"{str(c):>10s}" for c in classes_all))
    for i, c in enumerate(classes_all):
        print(f"  {str(c):<9s}" + "".join(f"{cm[i][j]:>10.1f}" for j in range(len(classes_all))))

    return {"acc_base": np.mean(res["base"]["acc"]), "acc_tuned": np.mean(res["tuned"]["acc"]),
            "kappa_base": np.mean(res["base"]["kappa"]), "kappa_tuned": np.mean(res["tuned"]["kappa"]),
            "baseline": baseline}


if __name__ == "__main__":
    df = tm.load_survey()
    Xf, yf = build_fuel(df)

    print("=" * 74)
    print("FUEL — ทดสอบ per-class decision threshold (prior correction)")
    print(f"ALPHA_GRID ที่ตรึงไว้ก่อนรัน: {ALPHA_GRID}")
    print(f"เลือก alpha ด้วย inner {INNER_FOLDS}-fold CV บน train | วัดผลบน {N_SPLITS} random splits")
    print("=" * 74)

    r_old = evaluate(Xf, yf, OLD_FUEL_CAT, OLD_FUEL_NUM,
                     "FUEL (ก) ฟีเจอร์เดิมเท่านั้น — deploy ได้ทันที ไม่ต้องแก้ฟอร์ม")
    r_new = evaluate(Xf, yf, OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM,
                     "FUEL (ข) เดิม + คำถามใหม่ 10 ข้อ — ต้องแก้ฟอร์มก่อนถึง deploy ได้")

    print(f"\n\n{'='*74}\nสรุป\n{'='*74}")
    print(f"{'ชุดฟีเจอร์':<14s} {'acc เดิม':>10s} {'acc ปรับ':>10s} {'kappa เดิม':>12s} {'kappa ปรับ':>12s}")
    for tag, r in (("เดิม", r_old), ("เดิม+ใหม่", r_new)):
        print(f"{tag:<14s} {r['acc_base']:>10.4f} {r['acc_tuned']:>10.4f} "
              f"{r['kappa_base']:>12.4f} {r['kappa_tuned']:>12.4f}")
    print(f"\nbaseline (ทายคลาสใหญ่สุดเสมอ) = {r_old['baseline']:.4f}")
