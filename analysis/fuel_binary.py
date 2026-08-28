"""
FUEL แบบ 2 คลาส: electrified (EV+Hybrid) vs ICE   [2026-08-09]

ที่มา
-----
เอกสารเคยบันทึกว่าการยุบ EV+Hybrid ถูก "ปัดตก" เพราะขัดวัตถุประสงค์ของระบบ
ที่ต้องแนะนำครบ 3 ประเภท — แต่ **ไม่เคยวัดตัวเลขจริง** สคริปต์นี้วัดให้เห็น
ว่าถ้ายุบแล้วได้เท่าไหร่ เพื่อให้ตัดสินใจโดยมีข้อมูล ไม่ใช่เดา

⚠️ ประกาศล่วงหน้าก่อนรัน
-----------------------
1. วัดด้วย 20 random splits เหมือน pipeline หลัก (§4.1)
2. **ต้องเทียบกับ baseline ของปัญหา 2 คลาสเอง** ไม่ใช่ baseline ของ 3 คลาส
   (ยุบคลาสทำให้ baseline เปลี่ยน — เทียบข้าม framing โดยไม่ดู baseline
    เป็นความผิดพลาดแบบเดียวกับที่ §4.2 เตือนไว้)
3. รายงาน accuracy / balanced acc / macro F1 / kappa / ROC-AUC ครบทุกตัว
   ไม่ว่าดีขึ้นหรือแย่ลง (§3.5)
4. **เกณฑ์ตัดสิน: lift เหนือ baseline ของตัวเอง** ไม่ใช่ accuracy ดิบ
   ถ้า accuracy สูงขึ้นแต่ lift ไม่ขึ้น = ได้มาจากการที่โจทย์ง่ายลง ไม่ใช่โมเดลเก่งขึ้น

ไม่แตะ .pkl — วิเคราะห์อย่างเดียว
"""
import sys, os, io, contextlib, warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
                             cohen_kappa_score, roc_auc_score, recall_score,
                             confusion_matrix)
from sklearn.base import clone

import train_models as tm
from ablation import build_fuel, OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM

N_SPLITS = 20
CAT = OLD_FUEL_CAT + NEW_FUEL_CAT
NUM = OLD_FUEL_NUM + NEW_FUEL_NUM


def evaluate(tag, X, y):
    print(f"\n{'='*74}\n### {tag}   (n={len(y)})\n{'='*74}")
    dist = y.value_counts()
    baseline = float(dist.max() / len(y))
    print(f"  สัดส่วนคลาส : {dict(dist)}")
    print(f"  baseline    : {baseline:.4f}")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, _m, _sc, _sn = tm.build_and_select(
            X, y, CAT, NUM, alpha=0.15, force_keep=["prev_car"])
    print(f"  โมเดลที่ใช้  : {name}")

    classes = sorted(y.unique())
    accs, bals, f1s, kaps, aucs, cms = [], [], [], [], [], []
    recs = {c: [] for c in classes}
    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2,
                                 random_state=tm.RANDOM_STATE)
    for si, (tr, te) in enumerate(sss.split(X, y), 1):
        p = clone(pipe)
        p.fit(X.iloc[tr], y.iloc[tr])
        yt, yp = y.iloc[te], p.predict(X.iloc[te])
        accs.append(accuracy_score(yt, yp))
        bals.append(balanced_accuracy_score(yt, yp))
        f1s.append(f1_score(yt, yp, average="macro", zero_division=0))
        kaps.append(cohen_kappa_score(yt, yp))
        for c, v in zip(classes, recall_score(yt, yp, labels=classes,
                                              average=None, zero_division=0)):
            recs[c].append(v)
        cms.append(confusion_matrix(yt, yp, labels=classes))
        proba = p.predict_proba(X.iloc[te])
        pcls = list(p.classes_)
        if len(pcls) == 2:
            aucs.append(roc_auc_score((yt == pcls[1]).astype(int), proba[:, 1]))
        else:
            aucs.append(roc_auc_score(yt, proba, multi_class="ovr", average="macro"))
        print(f"    split {si:2d}/{N_SPLITS} เสร็จ", flush=True)

    a = float(np.mean(accs))
    print(f"\n  accuracy      {a:.4f} ± {np.std(accs):.4f}")
    print(f"  **lift**      {a-baseline:+.4f}   <-- ตัวตัดสิน")
    print(f"  balanced acc  {np.mean(bals):.4f} ± {np.std(bals):.4f}")
    print(f"  macro F1      {np.mean(f1s):.4f} ± {np.std(f1s):.4f}")
    print(f"  Cohen kappa   {np.mean(kaps):+.4f} ± {np.std(kaps):.4f}")
    print(f"  ROC-AUC       {np.mean(aucs):.4f} ± {np.std(aucs):.4f}")
    print(f"\n  recall รายคลาส:")
    for c in classes:
        print(f"    {str(c):<14s} {np.mean(recs[c]):.4f}")
    cm = np.mean(cms, axis=0)
    print(f"\n  confusion matrix เฉลี่ย (แถว=จริง, คอลัมน์=ทาย)")
    print("           " + "".join(f"{str(c):>14s}" for c in classes))
    for i, c in enumerate(classes):
        print(f"  {str(c):<12s}" + "".join(f"{cm[i][j]:>14.1f}" for j in range(len(classes))))
    return {"acc": a, "base": baseline, "lift": a - baseline,
            "kappa": float(np.mean(kaps)), "auc": float(np.mean(aucs))}


if __name__ == "__main__":
    print("=" * 74)
    print("FUEL: 3 คลาส vs 2 คลาส (electrified vs ICE)")
    print("เกณฑ์ตัดสินคือ lift เหนือ baseline ของตัวเอง ไม่ใช่ accuracy ดิบ")
    print("=" * 74)

    df = tm.load_survey()
    X, y3 = build_fuel(df)

    r3 = evaluate("FUEL 3 คลาส (EV / Hybrid / ICE) — ของเดิม", X, y3)

    y2 = y3.map(lambda v: "ICE" if v == "ICE" else "Electrified")
    r2 = evaluate("FUEL 2 คลาส (Electrified = EV+Hybrid / ICE)", X, y2)

    print(f"\n{'='*74}\nสรุปเปรียบเทียบ\n{'='*74}")
    print(f"  {'':10s} {'accuracy':>10s} {'baseline':>10s} {'lift':>10s} {'kappa':>10s} {'ROC-AUC':>10s}")
    for tag, r in (("3 คลาส", r3), ("2 คลาส", r2)):
        print(f"  {tag:10s} {r['acc']:>10.4f} {r['base']:>10.4f} {r['lift']:>+10.4f} "
              f"{r['kappa']:>+10.4f} {r['auc']:>10.4f}")
    print(f"\n  accuracy เปลี่ยน {r2['acc']-r3['acc']:+.4f}  แต่ lift เปลี่ยน {r2['lift']-r3['lift']:+.4f}")
    print("  -> ถ้า accuracy ขึ้นแต่ lift ไม่ขึ้น แปลว่าได้มาจากโจทย์ง่ายลง ไม่ใช่โมเดลเก่งขึ้น")
