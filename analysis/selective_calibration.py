"""
Selective classification + Calibration ของโมเดลชุดปัจจุบัน (meta/Bagging)  [2026-08-09]

ตอบคำถาม "โมเดลแม่นจริงไหม" ด้วย 2 มุมที่ accuracy เดี่ยว ๆ ตอบไม่ได้
---------------------------------------------------------------------
A. **Selective classification** — ถ้าตอบเฉพาะเคสที่มั่นใจที่สุด จะแม่นขึ้นแค่ไหน
   (ระบบ DSS จริงส่งเคสที่ไม่มั่นใจให้พนักงานดูแทนได้)

B. **Calibration** — เวลาโมเดลบอก "มั่นใจ 80%" มันถูกจริง 80% หรือเปล่า
   ถ้าโมเดลโม้ (overconfident) ตัวเลขในข้อ A จะเชื่อไม่ได้ตั้งแต่ต้น
   วัดด้วย ECE (Expected Calibration Error) = ค่าเฉลี่ยส่วนต่าง |ความมั่นใจ − ความแม่นจริง|
   ยิ่งใกล้ 0 ยิ่งซื่อสัตย์

⚠️ ประกาศล่วงหน้าก่อนรัน (pre-registration)
-------------------------------------------
1. **COVERAGE = [0.5, 0.7, 0.9]** ตรึงไว้เท่ากับ `full_analysis.py` เป๊ะ
   เพื่อให้เทียบกับผลรอบ 2026-08-02 (BUY 77.70% ที่ coverage 50%) ได้ตรง ๆ
   **ห้ามเพิ่ม/ลดระดับ coverage หลังเห็นผล** (จะเป็น outcome switching)
2. **N_BINS = 10** สำหรับ calibration ตรึงก่อนรัน
3. วัดด้วย 20 random splits เหมือน pipeline หลัก (§4.1)
4. **รายงานทุกค่าไม่ว่าดีขึ้นหรือแย่ลงกว่ารอบเก่า** (§3.5)
   ถ้าได้ต่ำกว่า 77.70% ให้ใช้ค่าใหม่ ห้ามย้อนไปหยิบค่าเก่ามาใช้
   เพราะค่าเก่ามาจากโมเดลคนละตัว (ก่อนเปลี่ยนเป็น meta-classifier)

หมายเหตุ: **ไม่แตะ .pkl และไม่เทรนโมเดลถาวรใด ๆ** — วิเคราะห์อย่างเดียว
"""
import sys, os, io, contextlib, warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.base import clone

import train_models as tm
from ablation import (build_buy, build_fuel,
                      OLD_BUY_CAT, OLD_BUY_NUM, NEW_BUY_CAT, NEW_BUY_NUM,
                      OLD_FUEL_CAT, OLD_FUEL_NUM, NEW_FUEL_CAT, NEW_FUEL_NUM)

COVERAGE = [0.5, 0.7, 0.9]     # ตรึง — ต้องตรงกับ full_analysis.py
N_BINS = 10                    # ตรึง
N_SPLITS = 20


def run(tag, X, y, cat, num, alpha, force_keep, ref_note):
    print(f"\n{'='*76}\n### {tag}   (n={len(y)})\n{'='*76}")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pipe, name, _m, _sc, _sn = tm.build_and_select(
            X, y, cat, num, alpha=alpha, force_keep=force_keep)
    print(f"  โมเดลที่ใช้ : {name}")
    print(f"  baseline   : {y.value_counts(normalize=True).max():.4f}")

    full_acc = []
    sel = {c: [] for c in COVERAGE}
    # เก็บ (ความมั่นใจ, ถูก/ผิด) ของทุก split ไว้คำนวณ calibration รวม
    conf_all, hit_all = [], []

    sss = StratifiedShuffleSplit(n_splits=N_SPLITS, test_size=0.2,
                                 random_state=tm.RANDOM_STATE)
    for si, (tr, te) in enumerate(sss.split(X, y), 1):
        p = clone(pipe)
        p.fit(X.iloc[tr], y.iloc[tr])
        proba = p.predict_proba(X.iloc[te])
        classes = np.array(p.classes_)
        pred = classes[np.argmax(proba, axis=1)]
        conf = proba.max(axis=1)
        hit = (pred == y.iloc[te].values).astype(float)

        full_acc.append(hit.mean())
        conf_all.append(conf)
        hit_all.append(hit)

        order = np.argsort(-conf)          # มั่นใจมากสุดก่อน
        for c in COVERAGE:
            k = max(1, int(round(c * len(hit))))
            sel[c].append(hit[order[:k]].mean())
        print(f"    split {si:2d}/{N_SPLITS} เสร็จ", flush=True)

    conf_all = np.concatenate(conf_all)
    hit_all = np.concatenate(hit_all)

    print(f"\n  ── A. Selective classification ──")
    print(f"    (ระบบงดทำนายเคสที่ไม่มั่นใจ แล้วส่งต่อให้พนักงานดูแทน)")
    fa, fs = float(np.mean(full_acc)), float(np.std(full_acc))
    print(f"    coverage 100% (ตอบทุกเคส) : accuracy {fa:.4f} ± {fs:.4f}")
    for c in COVERAGE:
        m, s = float(np.mean(sel[c])), float(np.std(sel[c]))
        print(f"    coverage {int(c*100):3d}%              : accuracy {m:.4f} ± {s:.4f}"
              f"   ({m-fa:+.4f} จาก 100%)")
    print(f"    {ref_note}")

    print(f"\n  ── B. Calibration (โมเดลโม้หรือเปล่า) ──")
    print(f"    {'ช่วงความมั่นใจ':<18s} {'n':>6s} {'บอกว่ามั่นใจ':>13s} {'ถูกจริง':>10s} {'ส่วนต่าง':>10s}")
    print("    " + "-" * 62)
    edges = np.linspace(conf_all.min(), conf_all.max() + 1e-9, N_BINS + 1)
    ece, tot = 0.0, len(conf_all)
    for i in range(N_BINS):
        m = (conf_all >= edges[i]) & (conf_all < edges[i + 1])
        if m.sum() == 0:
            continue
        cm, am = conf_all[m].mean(), hit_all[m].mean()
        ece += (m.sum() / tot) * abs(cm - am)
        flag = "  <-- โม้" if cm - am > 0.10 else ("  <-- ถ่อมตัว" if am - cm > 0.10 else "")
        print(f"    {edges[i]:.3f}-{edges[i+1]:.3f}   {m.sum():>6d} "
              f"{cm:>13.4f} {am:>10.4f} {cm-am:>+10.4f}{flag}")
    print(f"\n    ECE (ยิ่งใกล้ 0 ยิ่งซื่อสัตย์) = {ece:.4f}")
    verdict = ("ความมั่นใจเชื่อถือได้ดี" if ece < 0.05 else
               "พอเชื่อได้ มีคลาดเคลื่อนบ้าง" if ece < 0.10 else
               "ความมั่นใจเชื่อไม่ค่อยได้")
    print(f"    -> {verdict}")
    print(f"    ความมั่นใจเฉลี่ยรวม {conf_all.mean():.4f} | ความแม่นจริงรวม {hit_all.mean():.4f}"
          f" | ต่าง {conf_all.mean()-hit_all.mean():+.4f}")


if __name__ == "__main__":
    print("=" * 76)
    print("โมเดลแม่นจริงไหม — Selective classification + Calibration")
    print(f"COVERAGE={COVERAGE} (ตรึงเท่ากับ full_analysis.py) | {N_SPLITS} random splits")
    print("=" * 76)

    df = tm.load_survey()

    Xb, yb = build_buy(df)
    run("BUY (ซื้อ / ไม่ซื้อ)", Xb, yb,
        OLD_BUY_CAT + NEW_BUY_CAT, OLD_BUY_NUM + NEW_BUY_NUM, 0.10, None,
        "อ้างอิงรอบเก่า (โมเดลเดี่ยว 2026-08-02): coverage 50% = 0.7770")

    Xf, yf = build_fuel(df)
    run("FUEL (EV / Hybrid / ICE)", Xf, yf,
        OLD_FUEL_CAT + NEW_FUEL_CAT, OLD_FUEL_NUM + NEW_FUEL_NUM, 0.15, ["prev_car"],
        "อ้างอิงรอบเก่า (โมเดลเดี่ยว 2026-08-02): coverage 50% = 0.4188 (เส้นแบน)")
