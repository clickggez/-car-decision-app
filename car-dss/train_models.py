"""
CarDSS — Training Script
เทรนโมเดลจริง predict_buy / predict_fuel จากข้อมูลแบบสอบถามใน files/user_from/*.csv

⚠️ หมายเหตุสำคัญ (2026-07-19): ชุดข้อมูลปัจจุบัน (100 แถว) เป็น "ข้อมูลทดสอบ"
ที่ผู้ใช้กรอกเองเพื่อจำลองการทำงานของเว็บ ไม่ใช่ข้อมูลแบบสอบถามจริงจากกลุ่มตัวอย่าง
(ตอบทั้ง 100 แถวภายใน ~2 นาที) — ใช้เพื่อทดสอบ pipeline/UX เท่านั้น
ไม่ควรอ้างอิงความแม่นยำเป็นผลงานวิจัยจริง ดู agent-docs/01-architecture.md

การใช้งาน:
    python train_models.py
ผลลัพธ์:
    models/buy_model.pkl   (bundle: pipeline + metadata)
    models/fuel_model.pkl
แล้วตั้ง config.USE_MOCK = False เพื่อให้ระบบใช้โมเดลจริง

หมายเหตุการ map ข้อมูล (train/serve skew guard):
    แปลงค่าไทยจากแบบสอบถาม -> "web value space" ให้ตรงกับที่ฟอร์มเว็บส่ง
    แล้วส่งต่อให้ feature_encoding.buy_features_from_web / fuel_features_from_web
    (ฟังก์ชันเดียวกับที่ predictor.py ใช้ตอน inference)

หมายเหตุ proxy: แบบสอบถามไม่มีคำถาม "tech_env_concern" / "resale_maintenance_concern"
ตรงตัว (เป็น field เฉพาะของฟอร์มเว็บ predict_fuel.html) — ใช้คะแนน 7P Likert ที่ใกล้เคียง
ที่สุดเป็น proxy แทน (ดู comment ในโค้ด) เป็นการประมาณ ไม่ใช่ค่าที่ถามตรงในแบบสอบถาม
"""

import os
import glob
import warnings

import numpy as np
import pandas as pd
import joblib
from scipy.stats import chi2_contingency

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, MinMaxScaler
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import StratifiedKFold, train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.feature_selection import f_classif

from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE

from models import feature_encoding as fe

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "models")
RANDOM_STATE = 42


# ============================================================
# โหลดข้อมูล
# ============================================================

def load_survey():
    matches = glob.glob(os.path.join(HERE, "..", "files", "user_from", "*.csv"))
    if not matches:
        raise FileNotFoundError("ไม่พบไฟล์ CSV แบบสอบถามใน files/user_from/")
    df = pd.read_csv(matches[0], encoding="utf-8")
    return df


# ============================================================
# ตาราง map ไทย -> web value space
# column layout ปัจจุบัน (หลังเพิ่ม children / housing_status ในฟอร์ม):
# 0=timestamp 1=gender 2=age 3=children 4=education 5=occupation
# 6=family_size 7=housing_type 8=housing_status 9=parking(3lvl) 10=income
# 11=has_car 12=usage_type 13=frequency 14=distance 15=concern 16=prev_car
# 17=priority 18=budget 19=purpose 20=buy_label 21=fuel_label 22=reason
# 23..43 = 7P Likert (1-5)
# ============================================================

GENDER = {"ชาย": "male", "หญิง": "female"}
AGE = {
    "20-23 ปี": "20-23", "24-26 ปี": "24-26", "27-30 ปี": "27-30",
    "31-40 ปี": "31-40", "41-50 ปี": "41-50", "51-60 ปี": "51-60",
    "มากกว่า 60 ปี": "60+",
}
CHILDREN = {
    "ไม่มีบุตร": "0", "1 คน": "1", "2 คน": "2", "3 คน": "3",
    "มากกว่า 3 คน": "3+",
}
EDUCATION = {
    "ต่ำกว่า ม.3": "below_m3", "ม.3": "m3", "ม.6": "m6",
    "ปวช. / ปวส.": "vocational", "ปริญญาตรี": "bachelor",
    "ปริญญาโท": "master", "ปริญญาเอก": "phd",
}
OCCUPATION = {
    "นักเรียน / นักศึกษา": "student", "อาชีพอิสระ": "freelance",
    "รัฐวิสาหกิจ": "soe", "พนักงานเอกชน": "private",
    "ข้าราชการ": "government", "เจ้าของกิจการ": "business_owner",
    "ค้าขาย": "trader",
}
FAMILY_SIZE = {"1-2 คน": "1-2", "3-4 คน": "3-4", "5 คนขึ้นไป": "5+"}
HOUSING_TYPE = {
    "บ้านเดี่ยว": "house", "บ้านเดี่ยว / บ้านแฝด": "house",
    "ทาวน์โฮม / ทาวเฮาท์": "townhome",
    "คอนโด / อพาร์ตเมนต์ / หอพัก": "condo",
}
HOUSING_STATUS = {
    "เป็นเจ้าของ": "own", "เช่า": "rent",
    "พักอาศัยกับครอบครัว / ผู้อื่น": "family",
}
PARKING = {
    "มีที่จอดรถส่วนตัว": "private",
    "มีที่จอดรถส่วนกลาง / เช่า": "common",
    "ไม่มีที่จอดรถ": "none",
}
INCOME = {
    "ต่ำกว่า 15,000 บาท": "lt15000", "15,001-25,000 บาท": "15001-25000",
    "25,001-35,000 บาท": "25001-35000", "35,001-50,000 บาท": "35001-50000",
    "50,001-75,000 บาท": "50001-75000", "มากกว่า 75,000": "75000+",
}
BUDGET = {
    "ต่ำกว่า 500,000 บาท": "lt500000", "500,001-800,000 บาท": "500001-800000",
    "800,001-1,200,000 บาท": "800001-1200000",
    "1,200,000-1,500,000 บาท": "1200001-1500000",
    "มากกว่า 1,500,000 บาท": "1500000+",
}
PURPOSE = {
    "เพื่อใช้ในการเดินทางไปทำงาน": "commute",
    "เพื่อใช้ในการค้าขาย": "trade",
    "เพื่อใช้ในการเดินทางท่องเที่ยว": "travel",
    "เพื่อความสะดวกในการเดินทาง": "convenience",
    "เพื่อหลีกเลี่ยงปัญหาจากระบบการขนส่งมวลชน": "avoid_public",
}
CONCERN = {
    "ราคาน้ำมัน": "fuel_price",
    "ค่าไฟฟ้า": "electricity_cost",
    "ปั๊มน้ำมัน / สถานีชาร์จ": "charging_station",
    "ปั้มน้ำมัน / สถานีชาร์จ": "charging_station",  # survey typo variant
    "ศูนย์บริการและอะไหล่": "service_center",
    "อายุการใช้งาน": "battery_life",
    "ค่าใช้จ่ายในการซ่อมบำรุง": "maintenance",
    "มูลค่าการขายต่อ": "resale_value",
}
BUY_LABEL = {"มีแนวโน้มที่จะซื้อ": "ซื้อ", "ยังไม่มีแนวโน้มที่จะซื้อ": "ไม่ซื้อ"}

USAGE_TYPE = {
    "ขับในเมือง": "city", "ขับนอกเมือง": "highway",
    "ขับทั้งในเมืองและนอกเมือง": "both",
}
FREQUENCY = {
    "ใช้เป็นครั้งคราว": "occasional", "1-2 วัน / สัปดาห์": "1-2days",
    "3-4 วัน / สัปดาห์": "3-4days", "5-6 วัน / สัปดาห์": "5-6days",
    "ใช้งานทุกวัน": "everyday",
}
DISTANCE = {
    "น้อยกว่า 10 กิโลเมตร": "lt10", "10-30 กิโลเมตร": "10-30",
    "31-50 กิโลเมตร": "31-50", "51-70 กิโลเมตร": "51-70",
    "71-90 กิโลเมตร": "71-90", "มากกว่า 90 กิโลเมตร": "90+",
}
PREV_CAR = {
    "รถยนต์สันดาป (ดีเซล / เบนซิน)": "ice",
    "รถยนต์ไฮบริด (Hybrid)": "hybrid",
    "รถยนต์ไฟฟ้า (EV)": "ev",
}
PRIORITY = {
    "ราคา": "price", "ความสามารถในการผ่อนชำระ": "installment",
    "ค่าน้ำมัน": "fuel_cost", "ค่าไฟฟ้า": "electricity_cost",
    "ค่าซ่อมบำรุง": "maintenance_cost", "สมรรถนะในการขับขี่": "performance",
    "รูปลักษณ์ / ดีไซน์": "design", "เทคโนโลยีและฟังก์ชันภายในรถ": "technology",
    "ความคุ้มค่าโดยรวม": "value", "การรับประกันและบริการหลังการขาย": "warranty",
    # "แบรนด์" ไม่มีใน priority ของฟอร์มเว็บ -> ตัดทิ้ง
}
FUEL_LABEL = {
    "รถยนต์ไฟฟ้า (EV)": "EV",
    "รถยนต์ไฮบริด (Hybrid)": "Hybrid",
    "รถยนต์สันดาป (ดีเซล / เบนซิน)": "ICE",
}

# 7P Likert column index สำหรับ proxy tech_env_concern / resale_maintenance_concern
# (แบบสอบถามไม่มีคำถามตรงตัว ใช้รายการที่ใกล้เคียงที่สุดเป็นตัวแทน)
COL_LIKERT_ENERGY_FIT = 23    # "ประเภทพลังงานของรถยนต์มีความเหมาะสมกับการใช้งาน" -> proxy tech_env_concern
COL_LIKERT_MAINTENANCE = 28   # "ค่าใช้จ่ายในการบำรุงรักษาซ่อมแซม...เหมาะสม" -> proxy resale_maintenance_concern


def _mode(series):
    m = series.dropna()
    return m.mode().iloc[0] if not m.empty else ""


# ============================================================
# 3.3.2.1 จัดการค่าที่ขาดหาย (เชิงปริมาณ: ค่าเฉลี่ยเลขคณิต) +
# 3.3.2.2 การจัดการข้อมูลผิดปกติ (ตรวจสอบด้วย IQR, แทนที่ด้วยค่ามัธยฐาน)
# ============================================================

def handle_missing_and_outliers(X, num_cols):
    for c in num_cols:
        col = pd.to_numeric(X[c], errors="coerce")
        mean_val = col.mean()
        col = col.fillna(mean_val)
        q1, q3 = col.quantile(0.25), col.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        median_val = col.median()
        n_outliers = int(((col < lower) | (col > upper)).sum())
        if n_outliers:
            col = col.where((col >= lower) & (col <= upper), median_val)
            print(f"      [Outlier] {c:20s} แทนที่ {n_outliers} ค่าผิดปกติด้วยค่ามัธยฐาน ({median_val})")
        X[c] = col
    return X


def _first_mapped(cell, mapping):
    """multi-select: คืน web token ตัวแรกที่ map ได้"""
    if pd.isna(cell):
        return ""
    for t in str(cell).split(","):
        t = t.strip()
        if t in mapping:
            return mapping[t]
    return ""


# ============================================================
# 3.3.2.3 คัดเลือกคุณลักษณะ — Chi-square (เชิงคุณภาพ) + ANOVA F-test (เชิงปริมาณ)
# หมายเหตุ: เล่มใช้ "ค่าสัมประสิทธิ์สหสัมพันธ์" สำหรับตัวแปรเชิงปริมาณ ซึ่งเหมาะกับ
# target ต่อเนื่อง — ในที่นี้ target เป็นหมวดหมู่ (ซื้อ/ไม่ซื้อ, EV/Hybrid/ICE) จึงใช้
# ANOVA F-test (sklearn.feature_selection.f_classif) แทน เป็นเทคนิคมาตรฐานสำหรับ
# วัดความสัมพันธ์ตัวแปรเชิงปริมาณ-เป้าหมายเชิงหมวดหมู่ (ทำหน้าที่เทียบเท่ากัน)
# ============================================================

def select_features(X, y, cat_cols, num_cols, alpha=0.10):
    print("    การคัดเลือกคุณลักษณะ (feature selection):")
    selected_cat, selected_num = [], []

    for c in cat_cols:
        table = pd.crosstab(X[c], y)
        try:
            _, p, _, _ = chi2_contingency(table)
        except ValueError:
            p = 1.0  # ตารางเสีย (เช่นมีแถวเดียว) -> ถือว่าไม่มีนัยสำคัญ
        keep = p < alpha
        selected_cat.append((c, keep))
        print(f"      [Chi-square] {c:20s} p={p:.4f} {'-> เก็บ' if keep else '-> ตัดทิ้ง'}")

    if num_cols:
        X_num = X[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        f_vals, p_vals = f_classif(X_num, y)
        for c, p in zip(num_cols, p_vals):
            keep = p < alpha
            selected_num.append((c, keep))
            print(f"      [ANOVA F]   {c:20s} p={p:.4f} {'-> เก็บ' if keep else '-> ตัดทิ้ง'}")

    cat_keep = [c for c, keep in selected_cat if keep] or cat_cols  # กันเหลือ 0 ฟีเจอร์
    num_keep = [c for c, keep in selected_num if keep] or num_cols

    if cat_keep == cat_cols and not any(keep for _, keep in selected_cat):
        print("      (ไม่มีฟีเจอร์ผ่านเกณฑ์นัยสำคัญเลย — เก็บทั้งหมดไว้กันโมเดลไม่มีข้อมูลเข้าเลย"
              " เหมาะสมกับ n ตัวอย่างน้อยของชุดข้อมูลทดสอบนี้)")

    return cat_keep, num_keep


# ============================================================
# 3.3.2.4 SMOTE — จัดการความไม่สมดุลของ class
# หมายเหตุ: ต้องมีอย่างน้อย 2 ตัวอย่างต่อ class จึงจะ interpolate ได้ (k_neighbors>=1)
# ถ้า class ใดมีตัวอย่างน้อยกว่านั้น (เช่นข้อมูลทดสอบชุดเล็กที่ ICE มีแค่ 1-2 แถว)
# จะ fallback เป็น class_weight="balanced" แทน แล้วแจ้งเหตุผลไว้ให้ชัดเจน
# ============================================================

def make_smote(y, random_state=RANDOM_STATE):
    min_count = y.value_counts().min()
    if min_count < 2:
        print(f"      [SMOTE] ข้าม — class ที่น้อยที่สุดมีแค่ {min_count} ตัวอย่าง"
              f" (ต้องการอย่างน้อย 2) ใช้ class_weight='balanced' แทน")
        return None
    k = min(5, int(min_count) - 1)
    print(f"      [SMOTE] เปิดใช้งาน k_neighbors={k} (class น้อยสุด={min_count} ตัวอย่าง)")
    return SMOTE(k_neighbors=k, random_state=random_state)


# ============================================================
# เทรนและเลือกโมเดลที่ดีที่สุด (SVM vs ANN)
# ============================================================


# 3.3.3.1 / 3.3.3.2 กำหนด/จูนพารามิเตอร์ต่อโมเดล (C, Gamma สำหรับ SVM;
# hidden layer, learning rate สำหรับ ANN) — จูนแยกกันต่อโมเดล (buy vs fuel)
# เพราะความซับซ้อนของ target ไม่เท่ากัน (2 class vs 3 class)
SVM_PARAM_GRID = {
    "clf__C": [0.5, 1, 3, 5, 10],
    "clf__gamma": ["scale", "auto", 0.01, 0.1, 0.5, 1],
}
ANN_PARAM_GRID = {
    "clf__hidden_layer_sizes": [(32,), (64, 32), (64, 32, 16)],
    "clf__learning_rate_init": [0.001, 0.01],
}


def _tune(name, base_clf, param_grid, pre, smote, X, y, cv):
    steps = [("pre", pre)]
    if smote is not None:
        steps.append(("smote", smote))
    steps.append(("clf", base_clf))
    pipe = Pipeline(steps)
    try:
        grid = GridSearchCV(pipe, param_grid, cv=cv, scoring="accuracy")
        grid.fit(X, y)
        tuned_params = {k.replace("clf__", ""): v for k, v in grid.best_params_.items()}
        print(f"    {name:4s} CV accuracy = {grid.best_score_:.3f} (grid search, best params: {tuned_params})")
        return grid.best_estimator_.named_steps["clf"], float(grid.best_score_), tuned_params
    except ValueError as e:
        print(f"    {name:4s} grid search ข้าม — {e}")
        return None, None, None


def build_and_select(X, y, cat_cols, num_cols):
    cat_cols, num_cols = select_features(X, y, cat_cols, num_cols)

    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ] + ([("num", MinMaxScaler(), num_cols)] if num_cols else []),
        remainder="drop",
    )

    base_svm = SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=RANDOM_STATE)
    base_ann = MLPClassifier(activation="relu", max_iter=2000, early_stopping=False, random_state=RANDOM_STATE)

    smote = make_smote(y)
    min_class_count = int(y.value_counts().min())
    n_splits = min(5, min_class_count)

    results = {}
    candidates = {}
    tuned_params_all = {}
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
        for name, base_clf, grid_params in [("SVM", base_svm, SVM_PARAM_GRID), ("ANN", base_ann, ANN_PARAM_GRID)]:
            clf, score, tuned = _tune(name, base_clf, grid_params, pre, smote, X, y, cv)
            if clf is not None:
                candidates[name] = clf
                results[name] = score
                tuned_params_all[name] = tuned
    else:
        print(f"    ข้าม CV ทั้งหมด — class น้อยที่สุดมีแค่ {min_class_count} ตัวอย่าง"
              f" (ต้องการอย่างน้อย 2 เพื่อ stratify)")

    if results:
        best_name = max(results, key=results.get)
        best_clf = candidates[best_name]
    else:
        # ไม่มี CV ให้เทียบ -> ใช้ SVM ค่าเริ่มต้นเป็น default (rbf จัดการ non-linear ได้ดีกับ n น้อย)
        best_name = "SVM"
        best_clf = SVC(kernel="rbf", C=3.0, gamma="scale", probability=True,
                        class_weight="balanced", random_state=RANDOM_STATE)
    print(f"    -> เลือก {best_name}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    train_smote = make_smote(y_tr)
    steps = [("pre", pre)]
    if train_smote is not None:
        steps.append(("smote", train_smote))
    steps.append(("clf", best_clf))
    best_pipe = Pipeline(steps)
    best_pipe.fit(X_tr, y_tr)
    y_pred = best_pipe.predict(X_te)
    test_acc = accuracy_score(y_te, y_pred)
    print(f"    held-out test accuracy = {test_acc:.3f}")
    print(classification_report(y_te, y_pred, zero_division=0))

    final_smote = make_smote(y)
    final_steps = [("pre", pre)]
    if final_smote is not None:
        final_steps.append(("smote", final_smote))
    final_steps.append(("clf", best_clf))
    final_pipe = Pipeline(final_steps)
    final_pipe.fit(X, y)

    metrics = {
        "cv_accuracy": round(float(results[best_name]), 4) if results else None,
        "test_accuracy": round(float(test_acc), 4),
        "n_samples": int(len(y)),
        "cv_all": {k: round(float(v), 4) for k, v in results.items()},
        "used_smote": smote is not None,
        "selected_cat_cols": cat_cols,
        "selected_num_cols": num_cols,
        "best_params": tuned_params_all.get(best_name),
        "tuned_params_all": tuned_params_all,
    }
    return final_pipe, best_name, metrics, cat_cols, num_cols


# ============================================================
# predict_buy
# ============================================================

def train_buy(df):
    print("\n[predict_buy] เตรียมข้อมูล...")
    rows, labels = [], []
    for _, r in df.iterrows():
        lab = BUY_LABEL.get(str(r.iloc[20]).strip())
        if lab is None:
            continue
        web = {
            "gender": GENDER.get(str(r.iloc[1]).strip(), ""),
            "age": AGE.get(str(r.iloc[2]).strip(), ""),
            "children": CHILDREN.get(str(r.iloc[3]).strip(), ""),
            "education": EDUCATION.get(str(r.iloc[4]).strip(), ""),
            "occupation": OCCUPATION.get(str(r.iloc[5]).strip(), ""),
            "family_size": FAMILY_SIZE.get(str(r.iloc[6]).strip(), ""),
            "housing_type": HOUSING_TYPE.get(str(r.iloc[7]).strip(), ""),
            "housing_status": HOUSING_STATUS.get(str(r.iloc[8]).strip(), ""),
            "parking": PARKING.get(str(r.iloc[9]).strip(), ""),
            "income": INCOME.get(str(r.iloc[10]).strip(), ""),
            "budget": BUDGET.get(str(r.iloc[18]).strip(), ""),
            "concern": _first_mapped(r.iloc[15], CONCERN),
            "purpose": _first_mapped(r.iloc[19], PURPOSE),
        }
        rows.append(fe.buy_features_from_web(web))
        labels.append(lab)

    X = pd.DataFrame(rows, columns=fe.BUY_CAT_COLS)
    for c in fe.BUY_CAT_COLS:
        X[c] = X[c].replace("", np.nan)
        X[c] = X[c].fillna(_mode(X[c]))
    y = pd.Series(labels)
    print(f"    ตัวอย่าง: {len(y)} | label: {dict(y.value_counts())}")

    pipe, name, metrics, sel_cat, sel_num = build_and_select(X, y, fe.BUY_CAT_COLS, [])

    bundle = {
        "pipeline": pipe,
        "cat_cols": sel_cat,
        "num_cols": sel_num,
        "feature_cols": fe.BUY_CAT_COLS,
        "classes_": list(pipe.classes_),
        "model_name": name,
        "metrics": metrics,
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "buy_model.pkl")
    joblib.dump(bundle, out)
    print(f"    บันทึก {out}")


# ============================================================
# predict_fuel  (ใช้เฉพาะผู้ที่มีรถ = มีข้อมูล usage/frequency/distance)
# ============================================================

def train_fuel(df):
    print("\n[predict_fuel] เตรียมข้อมูล...")
    rows, labels = [], []
    for _, r in df.iterrows():
        lab = FUEL_LABEL.get(str(r.iloc[21]).strip())
        usage = USAGE_TYPE.get(str(r.iloc[12]).strip(), "")
        if lab is None or usage == "":
            continue  # ข้ามผู้ไม่มีรถ (usage/frequency/distance ว่าง)
        priority_tokens = []
        if not pd.isna(r.iloc[17]):
            for t in str(r.iloc[17]).split(","):
                t = t.strip()
                if t in PRIORITY:
                    priority_tokens.append(PRIORITY[t])
        web = {
            "usage_type": usage,
            "frequency": FREQUENCY.get(str(r.iloc[13]).strip(), ""),
            "distance": DISTANCE.get(str(r.iloc[14]).strip(), ""),
            "prev_car": _first_mapped(r.iloc[16], PREV_CAR) or "none",
            "priority": priority_tokens,
            # proxy: แบบสอบถามไม่มีคำถามตรงตัว ใช้ 7P Likert ที่ใกล้เคียงที่สุดแทน
            "tech_env_concern": r.iloc[COL_LIKERT_ENERGY_FIT],
            "resale_maintenance_concern": r.iloc[COL_LIKERT_MAINTENANCE],
        }
        rows.append(fe.fuel_features_from_web(web))
        labels.append(lab)

    cols = fe.fuel_feature_columns()
    X = pd.DataFrame(rows, columns=cols)
    for c in fe.FUEL_CAT_COLS:
        X[c] = X[c].replace("", np.nan)
        X[c] = X[c].fillna(_mode(X[c]))
    print("    การจัดการค่าขาดหาย/ผิดปกติ (เชิงปริมาณ):")
    X = handle_missing_and_outliers(X, fe.FUEL_NUM_COLS)
    y = pd.Series(labels)
    print(f"    ตัวอย่าง: {len(y)} | label: {dict(y.value_counts())}")

    num_cols = fe.FUEL_NUM_COLS + ["prio_" + t for t in fe.PRIORITY_TOKENS]
    pipe, name, metrics, sel_cat, sel_num = build_and_select(X, y, fe.FUEL_CAT_COLS, num_cols)

    bundle = {
        "pipeline": pipe,
        "cat_cols": sel_cat,
        "num_cols": sel_num,
        "feature_cols": cols,
        "classes_": list(pipe.classes_),
        "model_name": name,
        "metrics": metrics,
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "fuel_model.pkl")
    joblib.dump(bundle, out)
    print(f"    บันทึก {out}")


if __name__ == "__main__":
    df = load_survey()
    print(f"โหลดข้อมูล: {len(df)} แถว")
    train_buy(df)
    train_fuel(df)
    print("\nเสร็จสิ้น — ตั้ง config.USE_MOCK = False เพื่อใช้โมเดลจริง")
