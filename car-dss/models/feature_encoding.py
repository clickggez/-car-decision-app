"""
CarDSS — Feature Encoding (shared)
ใช้ร่วมกันระหว่างสคริปต์ train (train_models.py) และ predictor.py ตอน inference
เพื่อกันปัญหา train/serve skew — ฟีเจอร์ต้องถูกสร้างด้วย logic เดียวกันทั้งสองฝั่ง

หลักการ:
- โมเดลถูก train ใน "value space" เดียวกับที่ฟอร์มเว็บส่งมา (predict_buy.html / predict_fuel.html)
- ตอน train: แปลงค่าภาษาไทยจากแบบสอบถาม → web value space (ดู train_models.py)
  แล้วเรียกฟังก์ชันในไฟล์นี้เพื่อสร้าง feature dict เดียวกับ inference
"""

# ============================================================
# predict_buy  (13 fields ตาม docstring ใน predictor.py)
# ============================================================

BUY_CAT_COLS = [
    "gender",
    "age",
    "children",
    "education",
    "occupation",
    "family_size",
    "housing_type",
    "housing_status",
    "parking",        # 'private' / 'common' / 'none'
    "income",
    "budget",
    "concern",
    "purpose",
]


def buy_features_from_web(form):
    """
    สร้าง feature dict สำหรับ predict_buy จากข้อมูลฟอร์มเว็บ (web value space)

    Args:
        form (dict): ค่าจากฟอร์ม predict_buy.html (13 fields)
    Returns:
        dict: {col: value} เฉพาะฟีเจอร์ใน BUY_CAT_COLS
    """
    return {
        "gender": _s(form.get("gender")),
        "age": _s(form.get("age")),
        "children": _s(form.get("children")),
        "education": _s(form.get("education")),
        "occupation": _s(form.get("occupation")),
        "family_size": _s(form.get("family_size")),
        "housing_type": _s(form.get("housing_type")),
        "housing_status": _s(form.get("housing_status")),
        "parking": _s(form.get("parking")),
        "income": _s(form.get("income")),
        "budget": _s(form.get("budget")),
        "concern": _s(form.get("concern")),
        "purpose": _s(form.get("purpose")),
    }


# ============================================================
# predict_fuel  (6 fields + priority list ตาม docstring ใน predictor.py)
# ============================================================

FUEL_CAT_COLS = [
    "usage_type",
    "frequency",
    "distance",
    "prev_car",
]

FUEL_NUM_COLS = [
    "tech_env_concern",
    "resale_maintenance_concern",
]

# priority (multi-select) → multi-hot columns ตามค่าใน predict_fuel.html
PRIORITY_TOKENS = [
    "price",
    "installment",
    "fuel_cost",
    "electricity_cost",
    "maintenance_cost",
    "performance",
    "design",
    "technology",
    "value",
    "warranty",
]


def fuel_features_from_web(form):
    """
    สร้าง feature dict สำหรับ predict_fuel จากข้อมูลฟอร์มเว็บ (web value space)

    Args:
        form (dict): ค่าจากฟอร์ม predict_fuel.html
            priority อาจเป็น list หรือ string (คั่นด้วย ',') ก็ได้
            tech_env_concern / resale_maintenance_concern เป็น '1'-'5'
    Returns:
        dict: FUEL_CAT_COLS + FUEL_NUM_COLS + prio_<token> (0/1) ทุกตัวใน PRIORITY_TOKENS
    """
    feat = {
        "usage_type": _s(form.get("usage_type")),
        "frequency": _s(form.get("frequency")),
        "distance": _s(form.get("distance")),
        "prev_car": _s(form.get("prev_car")) or "none",
        "tech_env_concern": _num(form.get("tech_env_concern"), default=3),
        "resale_maintenance_concern": _num(form.get("resale_maintenance_concern"), default=3),
    }
    selected = _as_list(form.get("priority"))
    for tok in PRIORITY_TOKENS:
        feat["prio_" + tok] = 1 if tok in selected else 0
    return feat


def fuel_feature_columns():
    """คืนลำดับคอลัมน์ฟีเจอร์ทั้งหมดของ predict_fuel (cat + num + multi-hot)"""
    return FUEL_CAT_COLS + FUEL_NUM_COLS + ["prio_" + t for t in PRIORITY_TOKENS]


# ============================================================
# helpers
# ============================================================

def _s(v):
    return str(v).strip() if v is not None else ""


def _num(v, default=3):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).split(",") if x.strip()]
