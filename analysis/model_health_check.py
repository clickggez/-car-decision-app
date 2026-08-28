"""
ตรวจสุขภาพโมเดลชุดปัจจุบัน (meta-classifier)  [2026-08-09]

ตอบ 3 คำถาม โดยวัดจริง ไม่ใช่อนุมานจาก accuracy
--------------------------------------------------
1. **เสถียรหรือยัง**      -> std / min / max ของ 20 random splits
2. **ยังเดามั่วอยู่ไหม**   -> Cohen's kappa (0 = ไม่ต่างจากเดาตามสัดส่วนคลาส)
                              + เทียบกับ permutation test (สลับ label สุ่ม)
3. **ยังเดาคลาสใหญ่ไหม**  -> recall รายคลาส + confusion matrix เฉลี่ย
                              + majority-rate (สัดส่วนที่โมเดลทายคลาสใหญ่สุด)

⚠️ ตัวชี้วัดทั้งหมดประกาศไว้ก่อนรัน ไม่มีการเลือกภายหลัง
   วัดด้วย 20 random splits เหมือน pipeline หลักทุกประการ (§4.1)
   **ไม่แตะ .pkl ที่ deploy อยู่** — วิเคราะห์อย่างเดียว

เกณฑ์อ่านผล (เขียนไว้ก่อนเห็นตัวเลข)
------------------------------------
- kappa <= 0        : เดามั่ว ใช้งานไม่ได้
- kappa 0.01-0.20   : อ่อนมาก แต่ไม่ใช่การเดา
- kappa 0.21-0.40   : พอใช้ (fair)
- majority-rate ใกล้ 1.00 = ยุบไปทายคลาสใหญ่
  ถ้าใกล้สัดส่วนจริงของคลาสใหญ่ = กระจายตามธรรมชาติ
"""
import sys, os, io, contextlib, warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score,
                             cohen_kappa_score, recall_score, precision_score,
                             confusion_matrix)
from sklearn.base import clone

import train_models as tm
from ablation import (build_buy, build_fuel,
                      OLD_BUY_CAT, OLD_BUY_NUM, NEW_BUY_CAT, NEW_BUY_NUM,
                      OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM)

N_SPLITS = 20
N_PERM = 20          # จำนวนครั้งที่สลับ label สุ่ม เพื่อหาค่า kappa ของ "การเดาจริง ๆ"


def check(tag, X, y, cat, num, alpha, force_keep):
    print(f"\n{'='*76}\n### {tag}   (n={len(y)})\n{'='*76}")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, _m, _sc, _sn = tm.build_and_select(
            X, y, cat, num, alpha=alpha, force_keep=force_keep)
    classes = sorted(y.unique())
    dist = y.value_counts()
    major = dist.idxmax()
    baseline = float(dist.max() / len(y))
    print(f"  โมเดลที่ใช้ : {name}")
    print(f"  คลาสใหญ่สุด : {major} ({dist.max()}/{len(y)} = {baseline:.4f})")

    accs, bals, f1s, kaps, majrates = [], [], [], [], []
    recs = {c: [] for c in classes}
    precs = {c: [] for c in classes}
    cms = []
    perm_kaps = []

    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2,
                                 random_state=tm.RANDOM_STATE)
    rng = np.random.RandomState(tm.RANDOM_STATE)
    for si, (tr, te) in enumerate(sss.split(X, y), 1):
        Xtr, ytr, Xte, yte = X.iloc[tr], y.iloc[tr], X.iloc[te], y.iloc[te]
        p = clone(pipe)
        p.fit(Xtr, ytr)
        yp = p.predict(Xte)

        accs.append(accuracy_score(yte, yp))
        bals.append(balanced_accuracy_score(yte, yp))
        f1s.append(f1_score(yte, yp, average="macro", zero_division=0))
        kaps.append(cohen_kappa_score(yte, yp))
        majrates.append(float(np.mean(np.asarray(yp) == major)))
        for c, v in zip(classes, recall_score(yte, yp, labels=classes,
                                              average=None, zero_division=0)):
            recs[c].append(v)
        for c, v in zip(classes, precision_score(yte, yp, labels=classes,
                                                average=None, zero_division=0)):
            precs[c].append(v)
        cms.append(confusion_matrix(yte, yp, labels=classes))

        # permutation: สลับ label ของ train แล้วดูว่า kappa ของ "การเดา" อยู่ที่เท่าไหร่
        if si <= N_PERM:
            yperm = ytr.sample(frac=1.0, random_state=rng.randint(1 << 30)).reset_index(drop=True)
            yperm.index = ytr.index
            pp = clone(pipe)
            pp.fit(Xtr, yperm)
            perm_kaps.append(cohen_kappa_score(yte, pp.predict(Xte)))
        print(f"    split {si:2d}/{N_SPLITS} เสร็จ", flush=True)

    a, s = float(np.mean(accs)), float(np.std(accs))
    k = float(np.mean(kaps))
    pk, pks = float(np.mean(perm_kaps)), float(np.std(perm_kaps))

    print(f"\n  ── 1. เสถียรหรือยัง ──")
    print(f"    accuracy      {a:.4f} ± {s:.4f}   (ต่ำสุด {min(accs):.4f} / สูงสุด {max(accs):.4f})")
    print(f"    ช่วงกว้าง      {max(accs)-min(accs):.4f}")
    print(f"    balanced acc  {np.mean(bals):.4f} ± {np.std(bals):.4f}")
    print(f"    macro F1      {np.mean(f1s):.4f} ± {np.std(f1s):.4f}")

    print(f"\n  ── 2. ยังเดามั่วอยู่ไหม ──")
    print(f"    Cohen kappa            {k:+.4f} ± {np.std(kaps):.4f}")
    print(f"    kappa ของการเดาจริง     {pk:+.4f} ± {pks:.4f}  (สลับ label สุ่ม {len(perm_kaps)} ครั้ง)")
    print(f"    ส่วนต่าง                {k-pk:+.4f}  ({(k-pk)/pks:.1f} เท่าของ std การเดา)"
          if pks > 0 else "")
    if k <= 0:
        verdict = "เดามั่ว — ใช้งานไม่ได้"
    elif k <= 0.20:
        verdict = "อ่อนมาก แต่ไม่ใช่การเดา"
    elif k <= 0.40:
        verdict = "พอใช้ (fair)"
    else:
        verdict = "ปานกลางขึ้นไป (moderate)"
    print(f"    -> {verdict}")

    print(f"\n  ── 3. ยังเดาคลาสใหญ่ไหม ──")
    mr = float(np.mean(majrates))
    print(f"    สัดส่วนที่ทายเป็น '{major}'  = {mr:.4f}")
    print(f"    สัดส่วนจริงของ '{major}'     = {baseline:.4f}")
    print(f"    -> {'ยุบไปทายคลาสใหญ่' if mr > 0.90 else 'กระจาย ไม่ยุบ'} "
          f"(ถ้าใกล้ 1.00 คือยุบ)")
    print(f"\n    {'คลาส':<10s} {'n':>5s} {'recall':>10s} {'precision':>11s}")
    print("    " + "-" * 40)
    for c in classes:
        print(f"    {str(c):<10s} {int((y==c).sum()):>5d} "
              f"{np.mean(recs[c]):>10.4f} {np.mean(precs[c]):>11.4f}")

    cm = np.mean(cms, axis=0)
    print(f"\n    confusion matrix เฉลี่ย {N_SPLITS} splits (แถว=จริง, คอลัมน์=ทาย)")
    print("           " + "".join(f"{str(c):>11s}" for c in classes))
    for i, c in enumerate(classes):
        print(f"    {str(c):<9s}" + "".join(f"{cm[i][j]:>11.1f}" for j in range(len(classes))))


if __name__ == "__main__":
    print("=" * 76)
    print("ตรวจสุขภาพโมเดลชุดปัจจุบัน — เสถียร? เดามั่ว? เดาคลาสใหญ่?")
    print(f"{N_SPLITS} random splits | permutation test {N_PERM} ครั้ง")
    print("=" * 76)

    df = tm.load_survey()
    Xb, yb = build_buy(df)
    check("BUY (ซื้อ / ไม่ซื้อ)", Xb, yb,
          OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM, 0.10, None)

    Xf, yf = build_fuel(df)
    check("FUEL (EV / Hybrid / ICE)", Xf, yf,
          OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM, 0.15, ["prev_car"])
