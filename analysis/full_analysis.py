"""
การวิเคราะห์เพิ่มเติม 8 รายการ (2026-08-02)
#5 Nested CV        — ตรวจว่าตัวเลขปัจจุบันสูงเกินจริงจาก leakage หรือไม่
#1 Selective classification — coverage/accuracy ที่ระดับที่กำหนดไว้ล่วงหน้า
#6 Learning curve   — accuracy เทียบ n
#7 Pairwise FUEL    — confusion + แยกวิเคราะห์ทีละคู่
#2 Hierarchical FUEL— ICE vs xEV แล้วค่อย EV vs Hybrid
#4 Ordinal FUEL     — ICE<Hybrid<EV ตามระดับการใช้ไฟฟ้า (QWK, off-by-one)
#3 Confident Learning — หา label ที่น่าจะผิดพลาดเชิงระบบ (Northcutt et al. 2021)
#8 Clustering       — label FUEL ตรงกับโครงสร้างข้อมูลหรือไม่

⚠️ ระดับ coverage สำหรับ #1 กำหนดไว้ล่วงหน้าที่ 50%, 70%, 90% (ระบุไว้ในรายงาน
   ก่อนรันสคริปต์นี้) เพื่อไม่ให้เป็นการเลือกจุดที่ตัวเลขสวยที่สุดภายหลัง
"""
import sys, os, io, contextlib, warnings
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.model_selection import (StratifiedShuffleSplit, StratifiedKFold,
                                     cross_val_predict, train_test_split)
from sklearn.metrics import (accuracy_score, confusion_matrix, cohen_kappa_score,
                             classification_report)
from sklearn.base import clone
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

import train_models as tm
from models import feature_encoding as fe
from ablation import (build_buy, build_fuel, OLD_BUY_CAT, OLD_BUY_NUM,
                      NEW_BUY_CAT, NEW_BUY_NUM, OLD_FUEL_CAT, OLD_FUEL_NUM,
                      NEW_FUEL_CAT, NEW_FUEL_NUM)

RS = tm.RANDOM_STATE
COVERAGE_LEVELS = [0.50, 0.70, 0.90]     # กำหนดไว้ล่วงหน้า ห้ามแก้หลังเห็นผล

BUY_CAT = OLD_BUY_CAT + NEW_BUY_CAT
BUY_NUM = OLD_BUY_NUM + NEW_BUY_NUM
FUEL_CAT = OLD_FUEL_CAT + NEW_FUEL_CAT
FUEL_NUM = OLD_FUEL_NUM + NEW_FUEL_NUM


def quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*a, **kw)


def header(txt):
    print("\n" + "=" * 74)
    print(txt)
    print("=" * 74)


def get_pipe(X, y, cat, num, alpha, force_keep=None):
    """สร้าง pipeline ที่ผ่านการเลือกโมเดล/ฟีเจอร์ตาม pipeline หลัก"""
    pipe, name, metrics, sc, sn = quiet(
        tm.build_and_select, X, y, cat, num, alpha=alpha, force_keep=force_keep)
    return pipe, name, metrics


# ============================================================
# #5 Nested CV
# ============================================================
def nested_cv(X, y, cat, num, alpha, force_keep, tag):
    header(f"#5 NESTED CV — {tag}")
    print("  เทียบ 2 วิธี:")
    print("   (ก) วิธีปัจจุบัน  = เลือกฟีเจอร์+จูนพารามิเตอร์บนข้อมูลทั้งหมด แล้ววัดบน 20 splits")
    print("   (ข) Nested CV     = เลือกฟีเจอร์+จูนใหม่ 'ภายใน' train fold ทุกครั้ง (ไม่เห็น test เลย)")
    print("  ถ้า (ก) สูงกว่า (ข) มาก แปลว่าตัวเลขที่รายงานสูงเกินจริงจาก selection bias\n")

    pipe, name, metrics = get_pipe(X, y, cat, num, alpha, force_keep)
    cur = metrics["test_accuracy_repeated_mean"]
    print(f"  (ก) วิธีปัจจุบัน  : {cur:.4f} ± {metrics['test_accuracy_repeated_std']:.4f}  (โมเดล {name})")

    outer = StratifiedShuffleSplit(n_splits=5, test_size=0.2, random_state=RS)
    accs = []
    for i, (tr, te) in enumerate(outer.split(X, y), 1):
        Xtr, ytr = X.iloc[tr].reset_index(drop=True), y.iloc[tr].reset_index(drop=True)
        Xte, yte = X.iloc[te], y.iloc[te]
        p, _, _ = get_pipe(Xtr, ytr, cat, num, alpha, force_keep)   # เลือก/จูนจาก train เท่านั้น
        accs.append(accuracy_score(yte, p.predict(Xte)))
        print(f"      outer fold {i}/5: {accs[-1]:.4f}")
    nested = float(np.mean(accs))
    print(f"  (ข) Nested CV    : {nested:.4f} ± {np.std(accs):.4f}")
    print(f"  -> ส่วนต่าง (ก)-(ข) = {cur-nested:+.4f}")
    if abs(cur - nested) < 0.03:
        print("  ✔ ส่วนต่างน้อยกว่า 3 จุด — ตัวเลขที่รายงานเชื่อถือได้ ไม่มี selection bias ที่มีนัยสำคัญ")
    else:
        print("  ⚠ ส่วนต่างเกิน 3 จุด — ควรรายงานค่า nested CV แทน")
    return cur, nested


# ============================================================
# #1 Selective classification
# ============================================================
def selective(X, y, cat, num, alpha, force_keep, tag):
    header(f"#1 SELECTIVE CLASSIFICATION — {tag}")
    print(f"  ระดับ coverage ที่กำหนดไว้ล่วงหน้า: {[int(c*100) for c in COVERAGE_LEVELS]}%")
    print("  (ระบบงดทำนายเคสที่ไม่มั่นใจ แล้วส่งต่อให้ผู้เชี่ยวชาญ — ตรงกับนิยาม Decision Support)\n")

    pipe, name, _ = get_pipe(X, y, cat, num, alpha, force_keep)
    sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=RS)
    rows = {c: [] for c in COVERAGE_LEVELS}
    full = []
    for tr, te in sss.split(X, y):
        p = clone(pipe); p.fit(X.iloc[tr], y.iloc[tr])
        proba = p.predict_proba(X.iloc[te])
        pred = p.classes_[proba.argmax(axis=1)]
        conf = proba.max(axis=1)
        yte = y.iloc[te].values
        full.append((pred == yte).mean())
        order = np.argsort(-conf)                      # มั่นใจมากสุดก่อน
        for c in COVERAGE_LEVELS:
            k = max(1, int(round(c * len(order))))
            idx = order[:k]
            rows[c].append((pred[idx] == yte[idx]).mean())

    print(f"  coverage 100% (ทำนายทุกเคส) : accuracy {np.mean(full):.4f} ± {np.std(full):.4f}")
    out = {}
    for c in COVERAGE_LEVELS:
        m, s = np.mean(rows[c]), np.std(rows[c])
        out[c] = m
        mark = "  ← ถึง 80%" if m >= 0.80 else ""
        print(f"  coverage {int(c*100):3d}%                : accuracy {m:.4f} ± {s:.4f}{mark}")
    return out


# ============================================================
# #6 Learning curve
# ============================================================
def learning_curve(X, y, cat, num, alpha, force_keep, tag):
    header(f"#6 LEARNING CURVE — {tag}")
    print("  ถ้ากราฟแบนเมื่อ n เพิ่ม = ชนเพดานสารสนเทศของข้อมูลแล้ว (เพิ่มข้อมูลอีกก็ไม่ช่วย)\n")
    pipe, _, _ = get_pipe(X, y, cat, num, alpha, force_keep)
    n_total = len(y)
    fracs = [0.2, 0.4, 0.6, 0.8, 1.0]
    print(f"  {'n':>6} | {'accuracy':>18} | กราฟ")
    res = []
    for f in fracs:
        n = int(n_total * f)
        accs = []
        sss = StratifiedShuffleSplit(n_splits=10, test_size=0.2, random_state=RS)
        for tr, te in sss.split(X, y):
            tr_sub = tr[:max(10, int(len(tr) * f))]
            if len(np.unique(y.iloc[tr_sub])) < 2:
                continue
            p = clone(pipe)
            try:
                p.fit(X.iloc[tr_sub], y.iloc[tr_sub])
                accs.append(accuracy_score(y.iloc[te], p.predict(X.iloc[te])))
            except ValueError:
                continue
        if accs:
            m, s = np.mean(accs), np.std(accs)
            bar = "█" * int(m * 50)
            print(f"  {n:>6} | {m:.4f} ± {s:.4f} | {bar}")
            res.append((n, m))
    if len(res) >= 2:
        slope_last = res[-1][1] - res[-2][1]
        print(f"\n  ส่วนต่างช่วงท้าย (จาก n={res[-2][0]} -> {res[-1][0]}): {slope_last:+.4f}")
        print("  ✔ กราฟแบน = เพิ่มข้อมูลไม่ช่วยแล้ว" if abs(slope_last) < 0.02
              else "  ⚠ ยังไม่แบน = เพิ่มข้อมูลอาจยังช่วยได้")
    return res


# ============================================================
# #7 Pairwise FUEL + confusion
# ============================================================
def pairwise_fuel(X, y):
    header("#7 PAIRWISE FUEL — คู่ไหนคือปัญหา")
    pipe, name, _ = get_pipe(X, y, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RS)
    p = clone(pipe); p.fit(Xtr, ytr)
    pred = p.predict(Xte)
    labels = list(p.classes_)
    cm = confusion_matrix(yte, pred, labels=labels)
    print(f"  Confusion matrix (แถว=จริง, คอลัมน์=ทำนาย), โมเดล {name}")
    print(f"        {'':>8}" + "".join(f"{l:>9}" for l in labels))
    for i, l in enumerate(labels):
        print(f"  จริง {l:>8}" + "".join(f"{v:>9}" for v in cm[i]))
    print()
    print("  แยกวิเคราะห์ทีละคู่ (2-class ในกลุ่มย่อย):")
    for a, b in [("EV", "ICE"), ("Hybrid", "ICE"), ("EV", "Hybrid")]:
        mask = y.isin([a, b])
        Xs, ys = X[mask].reset_index(drop=True), y[mask].reset_index(drop=True)
        base = ys.value_counts(normalize=True).max()
        ps, nm, mt = get_pipe(Xs, ys, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
        acc = mt["test_accuracy_repeated_mean"]
        print(f"    {a:>6} vs {b:<6} n={len(ys):3d} | acc {acc:.4f} | baseline {base:.4f} "
              f"| lift {acc-base:+.4f} {'✔ ชนะ' if acc>base else '✘ แพ้'}")


# ============================================================
# #2 Hierarchical FUEL
# ============================================================
def hierarchical_fuel(X, y):
    header("#2 HIERARCHICAL FUEL — ICE vs xEV แล้วค่อย EV vs Hybrid")
    print("  เหตุผลเชิงทฤษฎี: การตัดสินใจจริงเป็น 2 ขั้น — เลือกใช้ไฟฟ้าหรือไม่ ก่อนเลือกระดับ")
    print("  (nested logit, Train 2009) ไม่ใช่การเลือกเพราะตัวเลขสวย\n")

    base_flat = y.value_counts(normalize=True).max()
    _, _, mflat = get_pipe(X, y, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
    flat = mflat["test_accuracy_repeated_mean"]

    y_stage1 = y.map({"ICE": "ICE", "EV": "xEV", "Hybrid": "xEV"})
    sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=RS)
    p1, n1, _ = get_pipe(X, y_stage1, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
    mask_x = y.isin(["EV", "Hybrid"])
    Xx, yx = X[mask_x].reset_index(drop=True), y[mask_x].reset_index(drop=True)
    p2, n2, _ = get_pipe(Xx, yx, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])

    accs = []
    for tr, te in sss.split(X, y):
        a = clone(p1); a.fit(X.iloc[tr], y_stage1.iloc[tr])
        sub_tr = [i for i in tr if y.iloc[i] in ("EV", "Hybrid")]
        if len(set(y.iloc[sub_tr])) < 2:
            continue
        b = clone(p2); b.fit(X.iloc[sub_tr], y.iloc[sub_tr])
        s1 = a.predict(X.iloc[te])
        final = []
        for j, idx in enumerate(te):
            if s1[j] == "ICE":
                final.append("ICE")
            else:
                final.append(b.predict(X.iloc[[idx]])[0])
        accs.append(accuracy_score(y.iloc[te], final))
    hier = float(np.mean(accs))
    print(f"  Flat 3-class (ปัจจุบัน) : {flat:.4f} | baseline {base_flat:.4f}")
    print(f"  Hierarchical 2 ขั้น     : {hier:.4f} ± {np.std(accs):.4f}  (stage1={n1}, stage2={n2})")
    print(f"  -> ส่วนต่าง {hier-flat:+.4f} จุด")
    return flat, hier


# ============================================================
# #4 Ordinal treatment
# ============================================================
def ordinal_fuel(X, y):
    header("#4 ORDINAL TREATMENT — ICE < Hybrid < EV (ตามระดับการใช้พลังงานไฟฟ้า)")
    print("  เหตุผลเชิงทฤษฎี (กำหนดก่อนดูผล): ทั้งสามเรียงตามสัดส่วนการใช้ไฟฟ้าอย่างเป็นธรรมชาติ")
    print("  ทายพลาดจาก EV เป็น Hybrid ควรถือว่า 'ใกล้เคียง' กว่าทายพลาดเป็น ICE\n")
    order = {"ICE": 0, "Hybrid": 1, "EV": 2}
    pipe, name, _ = get_pipe(X, y, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"])
    sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=RS)
    exact, offby1, qwk = [], [], []
    b_exact, b_off, b_qwk = [], [], []
    major = y.value_counts().idxmax()
    for tr, te in sss.split(X, y):
        p = clone(pipe); p.fit(X.iloc[tr], y.iloc[tr])
        pred = p.predict(X.iloc[te])
        yt = y.iloc[te]
        a = np.array([order[v] for v in yt]); b = np.array([order[v] for v in pred])
        exact.append((a == b).mean()); offby1.append((np.abs(a - b) <= 1).mean())
        qwk.append(cohen_kappa_score(a, b, weights="quadratic"))
        bb = np.full_like(a, order[major])
        b_exact.append((a == bb).mean()); b_off.append((np.abs(a - bb) <= 1).mean())
        b_qwk.append(0.0)
    print(f"  {'ตัวชี้วัด':<28}{'โมเดล':>18}{'baseline':>12}{'lift':>10}")
    print(f"  {'Exact accuracy':<28}{np.mean(exact):>18.4f}{np.mean(b_exact):>12.4f}{np.mean(exact)-np.mean(b_exact):>+10.4f}")
    print(f"  {'Off-by-one accuracy':<28}{np.mean(offby1):>18.4f}{np.mean(b_off):>12.4f}{np.mean(offby1)-np.mean(b_off):>+10.4f}")
    print(f"  {'Quadratic Weighted Kappa':<28}{np.mean(qwk):>18.4f}{0.0:>12.4f}{np.mean(qwk):>+10.4f}")
    print("\n  หมายเหตุ: off-by-one baseline สูงมากโดยธรรมชาติ (ทายคลาสกลางก็ได้แล้ว)")
    print("  ตัวชี้วัดที่มีความหมายจริงคือ QWK (>0 = ดีกว่าเดาสุ่ม, 1.0 = สมบูรณ์แบบ)")


# ============================================================
# #3 Confident Learning (Northcutt et al. 2021) — implement เอง ไม่ใช้ cleanlab
# ============================================================
def confident_learning(X, y, cat, num, alpha, force_keep, tag):
    header(f"#3 CONFIDENT LEARNING — {tag}")
    print("  หลักการ (Northcutt et al. 2021, JAIR): ใช้ความน่าจะเป็นแบบ out-of-fold")
    print("  หา threshold ต่อคลาส = ค่าเฉลี่ยความมั่นใจของตัวอย่างที่ถูก label เป็นคลาสนั้น")
    print("  ตัวอย่างที่โมเดล 'มั่นใจว่าเป็นคลาสอื่น' เกิน threshold = ต้องสงสัยว่า label ผิด")
    print("  ⚠ เกณฑ์กำหนดจากอัลกอริทึมต้นฉบับ ไม่ได้ปรับเพื่อให้ accuracy สวย\n")

    pipe, name, m0 = get_pipe(X, y, cat, num, alpha, force_keep)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RS)
    proba = cross_val_predict(clone(pipe), X, y, cv=cv, method="predict_proba")
    classes = np.array(sorted(y.unique()))
    cls_idx = {c: i for i, c in enumerate(classes)}

    thresholds = {c: proba[[i for i in range(len(y)) if y.iloc[i] == c], cls_idx[c]].mean()
                  for c in classes}
    print("  threshold ต่อคลาส: " + ", ".join(f"{c}={thresholds[c]:.3f}" for c in classes))

    suspect = []
    for i in range(len(y)):
        given = y.iloc[i]
        for c in classes:
            if c != given and proba[i, cls_idx[c]] >= thresholds[c] \
               and proba[i, cls_idx[c]] > proba[i, cls_idx[given]]:
                suspect.append(i); break
    print(f"  ตัวอย่างที่ต้องสงสัยว่า label ผิด: {len(suspect)} / {len(y)} ({len(suspect)/len(y)*100:.1f}%)")

    if not suspect or len(suspect) > len(y) * 0.5:
        print("  -> ไม่ดำเนินการต่อ (ไม่พบ หรือพบมากเกินครึ่ง ซึ่งไม่สมเหตุสมผลที่จะคัดออก)")
        return
    keep = [i for i in range(len(y)) if i not in set(suspect)]
    Xc, yc = X.iloc[keep].reset_index(drop=True), y.iloc[keep].reset_index(drop=True)
    _, name2, m1 = get_pipe(Xc, yc, cat, num, alpha, force_keep)
    b0 = y.value_counts(normalize=True).max(); b1 = yc.value_counts(normalize=True).max()
    print(f"  ก่อนคัด : acc {m0['test_accuracy_repeated_mean']:.4f} | baseline {b0:.4f} "
          f"| lift {m0['test_accuracy_repeated_mean']-b0:+.4f}  (n={len(y)})")
    print(f"  หลังคัด : acc {m1['test_accuracy_repeated_mean']:.4f} | baseline {b1:.4f} "
          f"| lift {m1['test_accuracy_repeated_mean']-b1:+.4f}  (n={len(yc)})")
    print("  ⚠ การคัดออกทำให้ baseline เปลี่ยนด้วย ต้องเทียบที่ lift ไม่ใช่ accuracy ดิบ")


# ============================================================
# #8 Exploratory clustering
# ============================================================
def clustering(X, y):
    header("#8 EXPLORATORY CLUSTERING — label FUEL ตรงกับโครงสร้างข้อมูลหรือไม่")
    print("  ถ้า cluster ที่ได้ไม่สัมพันธ์กับ EV/Hybrid/ICE = หลักฐานว่า label ไม่สอดคล้อง")
    print("  กับโครงสร้างธรรมชาติของข้อมูล (สนับสนุนข้อสรุปเรื่องเพดาน)\n")
    pre = tm._make_pre(FUEL_CAT, [c for c in FUEL_NUM if c in X.columns])
    Z = pre.fit_transform(X)
    Z = StandardScaler().fit_transform(Z)
    from scipy.stats import chi2_contingency
    for k in (2, 3, 4):
        km = KMeans(n_clusters=k, random_state=RS, n_init=10).fit(Z)
        ct = pd.crosstab(pd.Series(km.labels_, name="cluster"), y.reset_index(drop=True))
        chi2, p, _, _ = chi2_contingency(ct)
        n = ct.values.sum()
        cramer = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
        print(f"  k={k}: Cramer's V = {cramer:.4f}, p = {p:.4f}  "
              f"{'(สัมพันธ์อ่อนมาก)' if cramer < 0.2 else '(สัมพันธ์พอสมควร)'}")
        print(ct.to_string().replace("\n", "\n      "))
        print()


if __name__ == "__main__":
    df = tm.load_survey()
    Xb, yb = quiet(build_buy, df)
    Xf, yf = quiet(build_fuel, df)
    print(f"ข้อมูล: BUY n={len(yb)} | FUEL n={len(yf)}")
    print(f"ระดับ coverage ที่ pre-register: {COVERAGE_LEVELS}")

    nested_cv(Xb, yb, BUY_CAT, BUY_NUM, 0.10, None, "BUY")
    nested_cv(Xf, yf, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"], "FUEL")

    selective(Xb, yb, BUY_CAT, BUY_NUM, 0.10, None, "BUY")
    selective(Xf, yf, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"], "FUEL")

    learning_curve(Xb, yb, BUY_CAT, BUY_NUM, 0.10, None, "BUY")
    learning_curve(Xf, yf, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"], "FUEL")

    pairwise_fuel(Xf, yf)
    hierarchical_fuel(Xf, yf)
    ordinal_fuel(Xf, yf)

    confident_learning(Xb, yb, BUY_CAT, BUY_NUM, 0.10, None, "BUY")
    confident_learning(Xf, yf, FUEL_CAT, FUEL_NUM, 0.15, ["prev_car"], "FUEL")

    clustering(Xf, yf)
    print("\n" + "=" * 74 + "\nเสร็จสิ้นทั้ง 8 รายการ\n" + "=" * 74)
