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
from sklearn.preprocessing import OneHotEncoder, MinMaxScaler, OrdinalEncoder
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import (
    RandomForestClassifier, HistGradientBoostingClassifier, VotingClassifier,
    StackingClassifier, ExtraTreesClassifier, BaggingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier
from sklearn.model_selection import StratifiedKFold, train_test_split, GridSearchCV, cross_val_score, StratifiedShuffleSplit
from sklearn.base import clone
from sklearn.metrics import accuracy_score, classification_report
from sklearn.feature_selection import f_classif, mutual_info_classif

from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE, BorderlineSMOTE

from models import feature_encoding as fe

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
# ค่าเริ่มต้นคือ models/ ซึ่งเป็นโฟลเดอร์ที่เว็บโหลดใช้จริง
# ตั้ง env var CARDSS_MODEL_DIR เพื่อเทรนลงโฟลเดอร์อื่นได้ โดยไม่ทับ .pkl ที่ deploy อยู่
# (จำเป็นเพราะ 00-READ-FIRST.md §3.3 ห้าม deploy โมเดลใหม่ก่อนแก้ฟอร์มเว็บ)
MODEL_DIR = os.environ.get("CARDSS_MODEL_DIR") or os.path.join(HERE, "models")
RANDOM_STATE = 42

# จำนวน bootstrap ของ BaggingClassifier — ตรงกับที่ใช้วัดใน
# analysis/meta_voting_bagging.py (N_BAGS=25) เพื่อให้ตัวเลขเทียบกันได้
BAGGING_N_ESTIMATORS = 25

# อาจารย์ที่ปรึกษากำหนดให้ใช้ meta-classifier (2026-08-09)
# ตั้งเป็น False เพื่อกลับไปเลือกโมเดลที่คะแนน CV สูงสุดโดยไม่สนชนิด
PREFER_META_CLASSIFIER = True
META_MODEL_NAMES = ("BAGGING", "ENSEMBLE", "STACK")


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


# ============================================================
# คำถามใหม่ที่เพิ่มต่อท้ายแบบสอบถาม (2026-08-01) — คอลัมน์ 44-58
# แบบสอบถามเดิม (คอลัมน์ 0-43) ไม่ถูกแก้ ตามเงื่อนไขที่อาจารย์ให้ไว้
# ไฟล์เก่าที่ไม่มีคอลัมน์เหล่านี้ถูกย้ายไป files/user_from_archive/ แล้ว
# ============================================================

COL_INTENTION = 44        # เจตนาซื้อภายใน 6 เดือน (1-7)
COL_ATTITUDE = 45         # การมีรถสำคัญเพียงใด (1-7)
COL_SUBJ_NORM = 46        # คนใกล้ชิดคิดว่าควรมีรถ (1-7)
COL_PBC = 47              # ความพร้อมทางการเงิน (1-7)
COL_LIFE_EVENTS = 48      # เหตุการณ์ 6 เดือนที่ผ่านมา (multi-select)
COL_CHARGING = 49         # จุดชาร์จที่บ้าน/ที่ทำงาน
COL_EV_EXPOSURE = 50      # เคยลองขับ EV/Hybrid
COL_RANGE_ANXIETY = 51    # กังวลแบตหมดระหว่างทาง (1-7)
COL_TCO = 52              # ความรู้เรื่องต้นทุนรวม
COL_INCENTIVE = 53        # ความรู้เรื่องสิทธิประโยชน์ภาครัฐ
COL_NEP_START = 54        # NEP 5 ข้อ (54-58) ข้อสุดท้าย (58) เป็น reverse-worded
COL_NEP_END = 58

CHARGING_ACCESS = {
    "มีอยู่แล้ว": "has",
    "ไม่มีแต่สามารถติดตั้งเพิ่มได้": "installable",
    "ไม่มีและไม่สามารถติดตั้งได้ (เช่น คอนโด/หอพักที่ไม่อนุญาต)": "cannot",
    "ไม่แน่ใจ": "unsure",
}
EV_EXPOSURE = {
    "เคยทั้ง EV และ Hybrid": "both",
    "เคยเฉพาะ EV": "ev_only",
    "เคยเฉพาะ Hybrid": "hybrid_only",
    "ไม่เคยเลย": "none",
}
TCO_AWARENESS = {
    "ทราบ และคิดว่าถูกกว่ามาก": "much_cheaper",
    "ทราบ แต่คิดว่าถูกกว่าเล็กน้อย": "slightly_cheaper",
    "ทราบ แต่คิดว่าไม่ต่างกันมาก": "similar",
    "ไม่ทราบเลย": "unknown",
}
INCENTIVE_AWARENESS = {
    "ทราบและเคยพิจารณาใช้สิทธิ์": "aware_considered",
    "ทราบแต่ไม่เคยพิจารณา": "aware_only",
    "ไม่ทราบเลย": "unknown",
}
# life event (multi-select) -> multi-hot token; "ไม่มีเหตุการณ์ข้างต้น" = ไม่ติดธงใดเลย
LIFE_EVENTS = {
    "เปลี่ยนงาน/ที่ทำงานใหม่": "job",
    "ย้ายที่อยู่อาศัย": "move",
    "มีบุตร/สมาชิกครอบครัวเพิ่ม": "child",
    "รายได้เปลี่ยนแปลงอย่างมีนัยสำคัญ (เพิ่มขึ้นหรือลดลง)": "income",
}

NEP_REVERSE_OFFSET = 4    # ข้อที่ 5 (index 58) เป็น reverse-worded -> กลับคะแนน


def _likert(cell, default=4):
    """ดึงตัวเลขนำหน้าจากค่า Likert เช่น '5 (เห็นด้วยอย่างยิ่ง)' -> 5"""
    if pd.isna(cell):
        return default
    s = str(cell).strip()
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        else:
            break
    try:
        return int(num)
    except ValueError:
        return default


def _all_mapped(cell, mapping):
    """multi-select: คืน web token ทุกตัวที่ map ได้ (ต่างจาก _first_mapped ที่คืนตัวแรก)"""
    if pd.isna(cell):
        return []
    out = []
    for t in str(cell).split(","):
        t = t.strip()
        if t in mapping and mapping[t] not in out:
            out.append(mapping[t])
    return out


def _nep_score(row):
    """คะแนนเฉลี่ย New Ecological Paradigm 5 ข้อ (1-5) — ข้อสุดท้าย reverse-worded"""
    vals = []
    for i in range(COL_NEP_START, COL_NEP_END + 1):
        v = _likert(row.iloc[i], default=3)
        if i == COL_NEP_START + NEP_REVERSE_OFFSET:
            v = 6 - v          # กลับคะแนน (1<->5) ตามหลัก reverse-worded item
        vals.append(v)
    return float(np.mean(vals)) if vals else 3.0


# ============================================================
# ฟีเจอร์เชิงลำดับ (ordinal) — ใช้ OrdinalEncoder ตามลำดับจริงแทน One-Hot
# (2026-07-29) ต่างจาก housing_type/gender/occupation ฯลฯ ที่เป็นข้อมูลเชิงกลุ่ม
# (nominal, ไม่มีลำดับ) ตัวแปรเหล่านี้มีลำดับตามธรรมชาติชัดเจน (อายุ/รายได้/งบ
# ประมาณ/ระยะทาง ฯลฯ เรียงจากน้อยไปมาก) การเข้ารหัสแบบ ordinal (แทนที่ One-Hot)
# ช่วยให้โมเดลเห็นความสัมพันธ์แบบต่อเนื่อง/เอกโทน (monotonic) ได้ตรงกว่า ไม่ใช่การ
# สร้าง "false ordinality" แบบที่หลีกเลี่ยงไว้กับ housing_type (เพราะที่นั่นไม่มีลำดับจริง)
ORDINAL_ORDERS = {
    "age": list(AGE.values()),
    "children": list(CHILDREN.values()),
    "education": list(EDUCATION.values()),
    "family_size": list(FAMILY_SIZE.values()),
    "income": list(INCOME.values()),
    "budget": list(BUDGET.values()),
    "distance": list(DISTANCE.values()),
    "frequency": list(FREQUENCY.values()),
}


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
        # ข้ามการตรวจ outlier สำหรับตัวแปรทวิภาค (0/1) — IQR ของคอลัมน์ที่ค่าส่วนใหญ่
        # เป็น 0 จะได้ Q1=Q3=0 ทำให้ค่า 1 ทุกตัวถูกตัดสินเป็น "ค่าผิดปกติ" แล้วแทนด้วย
        # มัธยฐาน (0) = ลบข้อมูลของฟีเจอร์ทิ้งทั้งคอลัมน์ (2026-08-01, ฟีเจอร์ evt_*)
        if col.dropna().isin([0, 1]).all():
            X[c] = col
            continue
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

def select_features(X, y, cat_cols, num_cols, alpha=0.10, force_keep=None):
    # force_keep: field ที่มีเหตุผลทางทฤษฎี/สามัญสำนึกชัดเจน ให้เก็บไว้เสมอแม้ p-value
    # ไม่ผ่านเกณฑ์ — เล่มโปรเจกต์ไม่ได้กำหนด alpha ตายตัว (ยืนยันผ่าน NotebookLM) และแนะนำ
    # แนวทางนี้เมื่อการทดสอบสถิติเชิงเดี่ยว (univariate) คัดทิ้งฟีเจอร์ที่มีนัยในทางปฏิบัติ
    force_keep = set(force_keep or [])
    print(f"    การคัดเลือกคุณลักษณะ (feature selection, alpha={alpha}):")
    selected_cat, selected_num = [], []

    for c in cat_cols:
        table = pd.crosstab(X[c], y)
        try:
            _, p, _, expected = chi2_contingency(table)
            sparse_frac = float((expected < 5).mean())
        except ValueError:
            p, sparse_frac = 1.0, 0.0  # ตารางเสีย (เช่นมีแถวเดียว) -> ถือว่าไม่มีนัยสำคัญ
        # เตือนเมื่อ >20% ของ cell มี expected count < 5 (Cochran's rule) — chi-square
        # ไม่valid ในกรณีนี้ ค่า p ที่ได้ไม่น่าเชื่อถือ โดยเฉพาะฟีเจอร์ผสม (interaction)
        # ที่ cardinality สูงบน n ตัวอย่างจำกัด (2026-07-30)
        if sparse_frac > 0.20:
            print(f"      [เตือน] {c:20s} {sparse_frac*100:.0f}% ของ cell มี expected count < 5"
                  f" — chi-square ไม่ valid, p={p:.4f} ไม่น่าเชื่อถือ")
        keep = p < alpha or c in force_keep
        selected_cat.append((c, keep))
        tag = "-> เก็บ (บังคับ)" if (c in force_keep and p >= alpha) else ("-> เก็บ" if keep else "-> ตัดทิ้ง")
        print(f"      [Chi-square] {c:20s} p={p:.4f} {tag}")

    if num_cols:
        X_num = X[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
        f_vals, p_vals = f_classif(X_num, y)
        for c, p in zip(num_cols, p_vals):
            keep = p < alpha or c in force_keep
            selected_num.append((c, keep))
            tag = "-> เก็บ (บังคับ)" if (c in force_keep and p >= alpha) else ("-> เก็บ" if keep else "-> ตัดทิ้ง")
            print(f"      [ANOVA F]   {c:20s} p={p:.4f} {tag}")

    cat_keep = [c for c, keep in selected_cat if keep] or cat_cols  # กันเหลือ 0 ฟีเจอร์
    num_keep = [c for c, keep in selected_num if keep] or num_cols

    if cat_keep == cat_cols and not any(keep for _, keep in selected_cat):
        print("      (ไม่มีฟีเจอร์ผ่านเกณฑ์นัยสำคัญเลย — เก็บทั้งหมดไว้กันโมเดลไม่มีข้อมูลเข้าเลย"
              " เหมาะสมกับ n ตัวอย่างน้อยของชุดข้อมูลทดสอบนี้)")

    return cat_keep, num_keep


# ============================================================
# เทคนิคคัดเลือกคุณลักษณะแบบอื่น — Mutual Information (2026-07-30)
# ต่างจาก Chi-square/ANOVA (univariate, สมมติความสัมพันธ์แบบง่าย) ตรงที่ MI จับ
# ความสัมพันธ์แบบ non-linear/ไม่เป็นเอกภาพ (non-monotonic) ได้กว้างกว่า — ใช้
# permutation test (สลับ label สุ่ม n_perm ครั้ง) หา threshold นัยสำคัญเอง แทนการ
# เดา top-K ตายตัว (MI ไม่มี p-value ในตัวเหมือน chi-square/ANOVA)
# ============================================================

def _mi_scores(X, cols, cat_set, y, random_state):
    Xenc = pd.DataFrame(index=X.index)
    discrete_mask = []
    for c in cols:
        if c in cat_set:
            Xenc[c] = LabelEncoder().fit_transform(X[c].astype(str))
            discrete_mask.append(True)
        else:
            Xenc[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)
            discrete_mask.append(False)
    return mutual_info_classif(Xenc.values, y, discrete_features=discrete_mask, random_state=random_state)


def select_features_mi(X, cat_cols, num_cols, y, n_perm=20, random_state=RANDOM_STATE):
    cols = list(cat_cols) + list(num_cols)
    cat_set = set(cat_cols)
    if not cols:
        return list(cat_cols), list(num_cols)

    real_scores = _mi_scores(X, cols, cat_set, y, random_state)

    rng = np.random.RandomState(random_state)
    y_arr = y.values if hasattr(y, "values") else np.asarray(y)
    perm_max = []
    for i in range(n_perm):
        y_perm = pd.Series(rng.permutation(y_arr))
        perm_scores = _mi_scores(X, cols, cat_set, y_perm, random_state + i + 1)
        perm_max.append(perm_scores.max())
    threshold = float(np.percentile(perm_max, 95))

    print(f"    Mutual Information selection (permutation threshold @95th pct = {threshold:.4f}, n_perm={n_perm}):")
    keep_cat, keep_num = [], []
    for c, score in zip(cols, real_scores):
        keep = score > threshold
        tag = "-> เก็บ" if keep else "-> ตัดทิ้ง"
        print(f"      [MI] {c:20s} score={score:.4f} {tag}")
        if keep:
            (keep_cat if c in cat_set else keep_num).append(c)

    if not keep_cat and not keep_num:
        print("      (ไม่มีฟีเจอร์ผ่าน threshold เลย — เก็บทั้งหมดไว้กันโมเดลไม่มีข้อมูลเข้าเลย)")
        keep_cat, keep_num = list(cat_cols), list(num_cols)
    return keep_cat, keep_num


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
    print(f"      [SMOTE] เปิดใช้งาน BorderlineSMOTE k_neighbors={k} (class น้อยสุด={min_count} ตัวอย่าง)")
    try:
        return BorderlineSMOTE(k_neighbors=k, random_state=random_state)
    except Exception:
        return SMOTE(k_neighbors=k, random_state=random_state)


# ============================================================
# เทรนและเลือกโมเดลที่ดีที่สุด (SVM vs ANN vs ET vs RF vs GB vs XGB)
# ============================================================


# 3.3.3.1 / 3.3.3.2 กำหนด/จูนพารามิเตอร์ต่อโมเดล (C, Gamma สำหรับ SVM;
# hidden layer, learning rate สำหรับ ANN) — จูนแยกกันต่อโมเดล (buy vs fuel)
# เพราะความซับซ้อนของ target ไม่เท่ากัน (2 class vs 3 class)
#
# ขยายเพิ่ม (2026-07-29/2026-08-02): เพิ่ม ExtraTrees + Random Forest + HistGradientBoosting เป็น
# candidate นอกเหนือจาก SVM/ANN ที่เล่มระบุ (ผู้ใช้อนุมัติให้เปลี่ยนวิธีการในบทที่ 3
# ได้ทุกอย่าง ยกเว้นแบบสอบถาม) — โมเดลแบบ tree-ensemble ทนทานต่อฟีเจอร์ที่มี
# ความสัมพันธ์แบบ non-linear/interaction กับ target ได้ดีกว่า SVM/ANN บนข้อมูลที่
# สัญญาณอ่อนแบบนี้ และไม่ต้องพึ่ง one-hot + scaling ให้สมบูรณ์แบบเท่า
# XGBoost's sklearn wrapper only accepts integer-encoded labels (0..n-1) — เรา
# ใช้ label ไทยเป็น string ('ซื้อ'/'ไม่ซื้อ', 'EV'/'Hybrid'/'ICE') จึงห่อด้วย
# LabelEncoder ภายในเพื่อให้ทำงานกับ pipeline/GridSearchCV/VotingClassifier เดิม
# ได้เหมือน classifier ตัวอื่นทุกประการ (มี classes_/predict/predict_proba)
class XGBClassifierStr(ClassifierMixin, BaseEstimator):
    def __init__(self, n_estimators=100, max_depth=3, learning_rate=0.1,
                 subsample=1.0, colsample_bytree=1.0, random_state=RANDOM_STATE):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state

    def fit(self, X, y):
        self._le = LabelEncoder()
        y_enc = self._le.fit_transform(y)
        self._clf = XGBClassifier(
            n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, subsample=self.subsample,
            colsample_bytree=self.colsample_bytree, random_state=self.random_state,
            eval_metric="mlogloss", verbosity=0,
        )
        self._clf.fit(X, y_enc)
        self.classes_ = self._le.classes_
        return self

    def predict(self, X):
        return self._le.inverse_transform(self._clf.predict(X))

    def predict_proba(self, X):
        return self._clf.predict_proba(X)


def _model_specs():
    return {
        "SVM": (
            SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=RANDOM_STATE),
            {
                "clf__C": [0.5, 1, 3, 5, 10],
                "clf__gamma": ["scale", "auto", 0.01, 0.1, 0.5, 1],
            },
        ),
        "ET": (
            ExtraTreesClassifier(class_weight="balanced", random_state=RANDOM_STATE),
            {
                "clf__n_estimators": [100, 200, 300],
                "clf__max_depth": [None, 5, 10],
                "clf__min_samples_leaf": [1, 2, 4],
                "clf__max_features": ["sqrt", "log2"],
            },
        ),
        "ANN": (
            MLPClassifier(activation="relu", max_iter=2000, early_stopping=False, random_state=RANDOM_STATE),
            {
                "clf__hidden_layer_sizes": [(32,), (64, 32), (64, 32, 16)],
                "clf__learning_rate_init": [0.001, 0.01],
            },
        ),
        "RF": (
            RandomForestClassifier(class_weight="balanced", random_state=RANDOM_STATE),
            {
                "clf__n_estimators": [200, 400],
                "clf__max_depth": [None, 6, 12],
                "clf__min_samples_leaf": [1, 2, 4],
                "clf__max_features": ["sqrt"],
            },
        ),
        "GB": (
            HistGradientBoostingClassifier(class_weight="balanced", random_state=RANDOM_STATE),
            {
                "clf__max_iter": [100, 200],
                "clf__max_depth": [3, 6, None],
                "clf__learning_rate": [0.03, 0.1, 0.2],
                "clf__min_samples_leaf": [10, 20],
            },
        ),
        "XGB": (
            XGBClassifierStr(random_state=RANDOM_STATE),
            {
                "clf__n_estimators": [100, 200],
                "clf__max_depth": [3, 5],
                "clf__learning_rate": [0.05, 0.1],
                "clf__subsample": [0.8, 1.0],
                "clf__colsample_bytree": [0.8, 1.0],
            },
        ),
    }


def _tune(name, base_clf, param_grid, pre, smote, X, y, cv):
    steps = [("pre", pre)]
    if smote is not None:
        steps.append(("smote", smote))
    steps.append(("clf", base_clf))
    pipe = Pipeline(steps)
    try:
        grid = GridSearchCV(pipe, param_grid, cv=cv, scoring="balanced_accuracy", n_jobs=-1)
        grid.fit(X, y)
        tuned_params = {k.replace("clf__", ""): v for k, v in grid.best_params_.items()}
        print(f"    {name:4s} CV balanced_accuracy = {grid.best_score_:.3f} (grid search, best params: {tuned_params})")
        return grid.best_estimator_.named_steps["clf"], float(grid.best_score_), tuned_params
    except ValueError as e:
        print(f"    {name:4s} grid search ข้าม — {e}")
        return None, None, None


def _make_pre(cat_cols, num_cols):
    ord_cols = [c for c in cat_cols if c in ORDINAL_ORDERS]
    nom_cols = [c for c in cat_cols if c not in ORDINAL_ORDERS]
    transformers = []
    if nom_cols:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), nom_cols))
    if ord_cols:
        ord_pipe = SkPipeline([
            ("enc", OrdinalEncoder(categories=[ORDINAL_ORDERS[c] for c in ord_cols],
                                    handle_unknown="use_encoded_value", unknown_value=-1)),
            ("scale", MinMaxScaler()),
        ])
        transformers.append(("ord", ord_pipe, ord_cols))
    if num_cols:
        transformers.append(("num", MinMaxScaler(), num_cols))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_and_select(X, y, cat_cols, num_cols, alpha=0.10, force_keep=None):
    # ขยายเพิ่ม (2026-07-29): นอกจาก univariate feature selection (Chi-square/ANOVA)
    # ยังลองชุดฟีเจอร์แบบ "ไม่คัดกรอง" (all) คู่ขนานไปด้วย เพราะโมเดล tree-ensemble
    # (RF/GB) ทนทานต่อฟีเจอร์ที่ไม่เกี่ยวข้องได้ดีกว่า SVM/ANN และอาจจับ interaction
    # ระหว่างฟีเจอร์ที่ univariate test มองไม่เห็นได้ — เลือกชุดที่ดีที่สุดจาก CV จริง
    # ไม่ใช่เดา
    sel_cat, sel_num = select_features(X, y, cat_cols, num_cols, alpha=alpha, force_keep=force_keep)
    feature_sets = {"selected": (sel_cat, sel_num)}
    if (sel_cat, sel_num) != (cat_cols, num_cols):
        feature_sets["all"] = (cat_cols, num_cols)

    mi_cat, mi_num = select_features_mi(X, cat_cols, num_cols, y)
    if force_keep:
        for c in force_keep:
            if c in cat_cols and c not in mi_cat:
                mi_cat.append(c)
    mi_pair = (mi_cat, mi_num)
    if mi_pair not in feature_sets.values():
        feature_sets["mi"] = mi_pair

    smote = make_smote(y)
    min_class_count = int(y.value_counts().min())
    n_splits = min(5, min_class_count)

    results = {}          # (feature_mode, model_name) -> cv score
    candidates = {}       # (feature_mode, model_name) -> tuned (unfitted-params) clf
    tuned_params_all = {}
    pre_cache = {}

    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
        for fmode, (fcat, fnum) in feature_sets.items():
            pre = _make_pre(fcat, fnum)
            pre_cache[fmode] = pre
            print(f"    == ชุดฟีเจอร์ '{fmode}' (cat={len(fcat)}, num={len(fnum)}) ==")
            for name, (base_clf, grid_params) in _model_specs().items():
                clf, score, tuned = _tune(name, base_clf, grid_params, pre, smote, X, y, cv)
                if clf is not None:
                    key = (fmode, name)
                    candidates[key] = clf
                    results[key] = score
                    tuned_params_all[key] = tuned

        # ลอง soft-voting ensemble ของทุกโมเดลที่จูนแล้วบนชุดฟีเจอร์ที่ดีที่สุด
        if results:
            top_fmode = max(results, key=results.get)[0]
            ens_estimators = [(name, candidates[(fmode, name)])
                              for (fmode, name) in candidates if fmode == top_fmode]
            if len(ens_estimators) >= 2:
                pre = pre_cache[top_fmode]
                voting = VotingClassifier(estimators=ens_estimators, voting="soft")
                steps = [("pre", pre)]
                if smote is not None:
                    steps.append(("smote", smote))
                steps.append(("clf", voting))
                vote_pipe = Pipeline(steps)
                try:
                    scores = cross_val_score(vote_pipe, X, y, cv=cv, scoring="balanced_accuracy", n_jobs=-1)
                    vote_score = float(scores.mean())
                    print(f"    ENSEMBLE(soft-vote: {[n for n, _ in ens_estimators]}) "
                          f"CV balanced_accuracy = {vote_score:.3f} (ชุดฟีเจอร์ '{top_fmode}')")
                    key = (top_fmode, "ENSEMBLE")
                    candidates[key] = voting
                    results[key] = vote_score
                    tuned_params_all[key] = {"estimators": [n for n, _ in ens_estimators]}
                except ValueError as e:
                    print(f"    ENSEMBLE(soft-vote) ข้าม — {e}")

                # เพิ่ม stacking (meta-learner เรียนรู้วิธีผสมโมเดลจากข้อมูลจริง แทนการ
                # เฉลี่ยแบบเท่ากันแบบ soft-vote) — ตามที่อาจารย์ที่ปรึกษาอนุญาตให้ "ผสม
                # โมเดลกันได้" (2026-07-30)
                stacking = StackingClassifier(
                    estimators=ens_estimators,
                    final_estimator=LogisticRegression(max_iter=1000, class_weight="balanced"),
                    cv=3,
                )
                stack_steps = [("pre", pre)]
                if smote is not None:
                    stack_steps.append(("smote", smote))
                stack_steps.append(("clf", stacking))
                stack_pipe = Pipeline(stack_steps)
                try:
                    scores = cross_val_score(stack_pipe, X, y, cv=cv, scoring="balanced_accuracy", n_jobs=-1)
                    stack_score = float(scores.mean())
                    print(f"    ENSEMBLE(stacking: {[n for n, _ in ens_estimators]}) "
                          f"CV balanced_accuracy = {stack_score:.3f} (ชุดฟีเจอร์ '{top_fmode}')")
                    key = (top_fmode, "STACK")
                    candidates[key] = stacking
                    results[key] = stack_score
                    tuned_params_all[key] = {"estimators": [n for n, _ in ens_estimators]}
                except ValueError as e:
                    print(f"    ENSEMBLE(stacking) ข้าม — {e}")

                # เพิ่ม bagging — อาจารย์ที่ปรึกษาสั่งให้ใช้ meta-classifier โดยเลือก
                # voting หรือ bagging ก็ได้ (2026-08-09) เลือก bagging เพราะวัดแล้ว
                # ชนะทุกตัวชี้วัดบน BUY และ voting ทำให้ kappa ของ FUEL ติดลบ
                # (ตัวเลขเต็มใน analysis/meta_voting_bagging_results_2026-08-09.txt)
                # ⚠️ ส่วนต่างเล็กกว่า std — ไม่มีนัยสำคัญทางสถิติ ต้องระบุข้อนี้ในเล่ม
                # ⚠️ ตัด ANN ออกจากตัวเลือกฐานของ bagging (พบ 2026-08-09)
                # sklearn 1.8 ให้ BaggingClassifier ส่ง sample_weight เข้า MLPClassifier
                # แทนการสุ่ม index เมื่อฐานรองรับ sample_weight — พอ bootstrap ทำให้
                # ทั้ง mini-batch มีน้ำหนักเป็น 0 จะได้ ZeroDivisionError
                # ("Weights sum to zero, can't be normalized") ใน log_loss
                # จึงห่อโมเดลฐานที่ดีที่สุด "ที่ไม่ใช่ ANN" แทน
                base_keys = [k for k in candidates
                             if k[0] == top_fmode and k[1] not in ("ENSEMBLE", "STACK", "BAGGING", "ANN")]
                if base_keys:
                    best_base_key = max(base_keys, key=lambda k: results[k])
                    bagging = BaggingClassifier(
                        estimator=clone(candidates[best_base_key]),
                        n_estimators=BAGGING_N_ESTIMATORS,
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    )
                    bag_steps = [("pre", pre)]
                    if smote is not None:
                        bag_steps.append(("smote", smote))
                    bag_steps.append(("clf", bagging))
                    bag_pipe = Pipeline(bag_steps)
                    try:
                        scores = cross_val_score(bag_pipe, X, y, cv=cv,
                                                 scoring="balanced_accuracy", n_jobs=-1)
                        bag_score = float(scores.mean())
                        print(f"    ENSEMBLE(bagging x{BAGGING_N_ESTIMATORS} ของ {best_base_key[1]}) "
                              f"CV balanced_accuracy = {bag_score:.3f} (ชุดฟีเจอร์ '{top_fmode}')")
                        key = (top_fmode, "BAGGING")
                        candidates[key] = bagging
                        results[key] = bag_score
                        tuned_params_all[key] = {"base": best_base_key[1],
                                                 "n_estimators": BAGGING_N_ESTIMATORS}
                    except Exception as e:
                        # จับกว้างเพราะ base ต่างชนิดโยน exception ต่างกัน — แต่ต้อง
                        # พิมพ์ชนิดกับข้อความบรรทัดเดียว ไม่ให้ traceback กลบ log
                        print(f"    ENSEMBLE(bagging) ข้าม — {type(e).__name__}: "
                              f"{str(e).splitlines()[-1][:160]}")
    else:
        print(f"    ข้าม CV ทั้งหมด — class น้อยที่สุดมีแค่ {min_class_count} ตัวอย่าง"
              f" (ต้องการอย่างน้อย 2 เพื่อ stratify)")

    if results:
        best_key = max(results, key=results.get)
        # อาจารย์ที่ปรึกษากำหนดให้ใช้ meta-classifier (2026-08-09) จึงจำกัดผู้ชนะ
        # ให้อยู่ในกลุ่ม meta เท่านั้นเมื่อ PREFER_META_CLASSIFIER = True
        #
        # ⚠️ นี่ไม่ใช่การเลือกตามผล (§3.5) เพราะข้อจำกัด "ต้องเป็น meta" ถูกกำหนด
        #    จากภายนอก *ก่อน* เห็นตัวเลข — ในกลุ่ม meta ทั้ง 3 ตัว bagging ชนะทั้ง
        #    BUY (0.695 > 0.682 > 0.675) และ FUEL (0.437 > 0.417 > 0.388)
        #
        # ⚠️ ต้องรายงานในเล่มว่าโมเดลเดี่ยวที่ดีที่สุดได้คะแนนสูงกว่าเล็กน้อย
        #    (BUY: RF 0.701 vs 0.695 = 0.006 | FUEL: ANN 0.440 vs 0.437 = 0.003)
        #    ซึ่งเล็กกว่าค่าความผันผวนหลายเท่า = ไม่มีนัยสำคัญทางสถิติ
        if PREFER_META_CLASSIFIER:
            meta_keys = [k for k in results if k[1] in META_MODEL_NAMES]
            if meta_keys:
                meta_key = max(meta_keys, key=results.get)
                if meta_key != best_key:
                    print(f"    [meta] โมเดลที่คะแนนสูงสุดคือ {best_key[1]} ({results[best_key]:.3f})"
                          f" แต่ไม่ใช่ meta-classifier")
                    print(f"    [meta] เลือก {meta_key[1]} ({results[meta_key]:.3f}) ตามข้อกำหนดของอาจารย์"
                          f" — ส่วนต่าง {results[best_key]-results[meta_key]:+.3f}")
                best_key = meta_key
            else:
                print("    [meta] ไม่มี meta-classifier ที่ใช้ได้เลย — ใช้โมเดลที่คะแนนสูงสุดแทน")
        best_fmode, best_name = best_key
        best_clf = candidates[best_key]
        cat_cols, num_cols = feature_sets[best_fmode]
        pre = pre_cache[best_fmode]
    else:
        # ไม่มี CV ให้เทียบ -> ใช้ SVM ค่าเริ่มต้นเป็น default (rbf จัดการ non-linear ได้ดีกับ n น้อย)
        best_fmode, best_name = "selected", "SVM"
        cat_cols, num_cols = feature_sets["selected"]
        best_clf = SVC(kernel="rbf", C=3.0, gamma="scale", probability=True,
                        class_weight="balanced", random_state=RANDOM_STATE)
        pre = _make_pre(cat_cols, num_cols)
    print(f"    -> เลือก {best_name} (ชุดฟีเจอร์ '{best_fmode}')")

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
    print(f"    held-out test accuracy (1 split, random_state={RANDOM_STATE}) = {test_acc:.3f}")
    print(classification_report(y_te, y_pred, zero_division=0))

    # ประเมินซ้ำด้วย 20 random split (StratifiedShuffleSplit) เพื่อรายงานค่าเฉลี่ย+
    # ส่วนเบี่ยงเบนที่น่าเชื่อถือกว่าตัวเลขจาก split เดียว (2026-07-30 ตามคำถาม
    # "ลองทุกทางแล้วหรอ" — split เดียวมีความผันผวนสูงเมื่อสัญญาณอ่อนและ n น้อย)
    sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=RANDOM_STATE)
    repeat_accs = []
    for tr_idx, te_idx in sss.split(X, y):
        rep_pipe = clone(best_pipe)
        rep_pipe.fit(X.iloc[tr_idx], y.iloc[tr_idx])
        repeat_accs.append(accuracy_score(y.iloc[te_idx], rep_pipe.predict(X.iloc[te_idx])))
    repeat_mean = float(np.mean(repeat_accs))
    repeat_std = float(np.std(repeat_accs))
    print(f"    held-out test accuracy (20 random splits) = {repeat_mean:.3f} +/- {repeat_std:.3f} "
          f"(min={min(repeat_accs):.3f}, max={max(repeat_accs):.3f})")

    final_smote = make_smote(y)
    final_steps = [("pre", pre)]
    if final_smote is not None:
        final_steps.append(("smote", final_smote))
    final_steps.append(("clf", best_clf))
    final_pipe = Pipeline(final_steps)
    final_pipe.fit(X, y)

    metrics = {
        "cv_accuracy": round(float(results[best_key]), 4) if results else None,
        "test_accuracy": round(float(test_acc), 4),
        "test_accuracy_repeated_mean": round(repeat_mean, 4),
        "test_accuracy_repeated_std": round(repeat_std, 4),
        "n_samples": int(len(y)),
        "cv_all": {f"{fmode}/{name}": round(float(v), 4) for (fmode, name), v in results.items()},
        "used_smote": smote is not None,
        "selected_cat_cols": cat_cols,
        "selected_num_cols": num_cols,
        "feature_mode": best_fmode,
        "best_params": tuned_params_all.get(best_key),
        "tuned_params_all": {f"{fmode}/{name}": v for (fmode, name), v in tuned_params_all.items()},
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
            # คำถามใหม่ (2026-08-01) — TPB constructs + life event + EV-domain
            "intention": _likert(r.iloc[COL_INTENTION]),
            "attitude": _likert(r.iloc[COL_ATTITUDE]),
            "subjective_norm": _likert(r.iloc[COL_SUBJ_NORM]),
            "pbc_financial": _likert(r.iloc[COL_PBC]),
            "life_events": _all_mapped(r.iloc[COL_LIFE_EVENTS], LIFE_EVENTS),
            "charging_access": CHARGING_ACCESS.get(str(r.iloc[COL_CHARGING]).strip(), ""),
            "tco_awareness": TCO_AWARENESS.get(str(r.iloc[COL_TCO]).strip(), ""),
            "incentive_awareness": INCENTIVE_AWARENESS.get(str(r.iloc[COL_INCENTIVE]).strip(), ""),
        }
        rows.append(fe.buy_features_from_web(web))
        labels.append(lab)

    cols = fe.buy_feature_columns()
    X = pd.DataFrame(rows, columns=cols)
    for c in fe.BUY_CAT_COLS:
        X[c] = X[c].replace("", np.nan)
        X[c] = X[c].fillna(_mode(X[c]))
    if fe.BUY_NUM_COLS:
        print("    การจัดการค่าขาดหาย/ผิดปกติ (เชิงปริมาณ):")
        X = handle_missing_and_outliers(X, fe.BUY_NUM_COLS)
    y = pd.Series(labels)
    print(f"    ตัวอย่าง: {len(y)} | label: {dict(y.value_counts())}")

    pipe, name, metrics, sel_cat, sel_num = build_and_select(X, y, fe.BUY_CAT_COLS, fe.BUY_NUM_COLS)

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
    out = os.path.join(MODEL_DIR, "buy_model.pkl")
    # compress=3 บังคับไว้ตั้งแต่ 2026-08-28 — ห้ามเอาออก
    # โมเดล BAGGING x25 ไม่บีบอัดจะได้ 137 MB เกินลิมิต 100 MB ของ GitHub
    # ซึ่งทำให้ git push ไม่ผ่าน และเว็บบน PythonAnywhere (deploy ด้วย git pull)
    # จะไม่ได้โมเดลใหม่เลย · บีบแล้วเหลือ 25.7 MB ผลทำนายเท่ากันทุกทศนิยม (ตรวจแล้ว)
    joblib.dump(bundle, out, compress=3)
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
            # คำถามใหม่ (2026-08-01) — กรอบงานวิจัย EV adoption
            "charging_access": CHARGING_ACCESS.get(str(r.iloc[COL_CHARGING]).strip(), ""),
            "ev_exposure": EV_EXPOSURE.get(str(r.iloc[COL_EV_EXPOSURE]).strip(), ""),
            "tco_awareness": TCO_AWARENESS.get(str(r.iloc[COL_TCO]).strip(), ""),
            "incentive_awareness": INCENTIVE_AWARENESS.get(str(r.iloc[COL_INCENTIVE]).strip(), ""),
            "range_anxiety": _likert(r.iloc[COL_RANGE_ANXIETY]),
            "nep_score": _nep_score(r),
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
    # alpha ผ่อนปรนกว่า buy (0.10->0.15) + บังคับเก็บ prev_car: เล่มไม่ได้ล็อก alpha ตายตัว
    # (ยืนยันผ่าน NotebookLM) fuel มีฟีเจอร์ผู้สมัครน้อย (16 ตัว, ล็อกจาก predict_fuel()
    # signature) การกรองแบบ univariate ที่ alpha=0.10 เดิมทิ้ง prev_car ซึ่งมีเหตุผล
    # ทางทฤษฎีชัดเจน (รถเดิมมักทำนายชนิดเชื้อเพลิงที่เลือกครั้งถัดไป)
    pipe, name, metrics, sel_cat, sel_num = build_and_select(
        X, y, fe.FUEL_CAT_COLS, num_cols, alpha=0.15, force_keep=["prev_car"])

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
    # compress=3 บังคับไว้ตั้งแต่ 2026-08-28 — ห้ามเอาออก
    # โมเดล BAGGING x25 ไม่บีบอัดจะได้ 137 MB เกินลิมิต 100 MB ของ GitHub
    # ซึ่งทำให้ git push ไม่ผ่าน และเว็บบน PythonAnywhere (deploy ด้วย git pull)
    # จะไม่ได้โมเดลใหม่เลย · บีบแล้วเหลือ 25.7 MB ผลทำนายเท่ากันทุกทศนิยม (ตรวจแล้ว)
    joblib.dump(bundle, out, compress=3)
    print(f"    บันทึก {out}")


if __name__ == "__main__":
    df = load_survey()
    print(f"โหลดข้อมูล: {len(df)} แถว")
    train_buy(df)
    train_fuel(df)
    print("\nเสร็จสิ้น — ตั้ง config.USE_MOCK = False เพื่อใช้โมเดลจริง")
