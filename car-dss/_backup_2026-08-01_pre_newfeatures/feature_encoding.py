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
    # ฟีเจอร์ผสมเชิงหมวดหมู่ (categorical interaction, 2026-07-30) — เก็บเข้า BUY_CAT_COLS
    # เพื่อให้แข่ง Chi-square เหมือนฟีเจอร์ดิบทุกตัว ไม่ใช่ข้อมูลใหม่จากแบบสอบถาม
    # หมายเหตุ: ลอง concern x budget ด้วย (40 combo) แต่ 44% ของ cell มี expected count < 5
    # (ผิดเงื่อนไข Chi-square — ค่า p ที่ได้ไม่น่าเชื่อถือ) จึงตัดออก เก็บเฉพาะตัวที่
    # ผ่านเงื่อนไขสถิติจริง (purpose_housing: 0% cell < 5)
    "purpose_housing",  # purpose x housing_status — วัตถุประสงค์ใช้รถอาจสัมพันธ์กับสถานะที่พัก
]

# ฟีเจอร์เชิงประกอบ (composite/interaction) — คำนวณจากฟิลด์ฟอร์มเดิมทั้งหมด
# ไม่ใช่ข้อมูลใหม่จากแบบสอบถาม (2026-07-29, ดู agent-docs/01-architecture.md)
BUY_NUM_COLS = [
    "income_budget_gap",   # งบซื้อรถเทียบกับรายได้ (ยิ่งสูง = งบเกินตัวมากกว่ารายได้บ่งชี้)
]

INCOME_ORDER = ["lt15000", "15001-25000", "25001-35000", "35001-50000", "50001-75000", "75000+"]
BUDGET_ORDER = ["lt500000", "500001-800000", "800001-1200000", "1200001-1500000", "1500000+"]


def _rank01(value, order):
    """แปลงค่าหมวดหมู่เชิงลำดับ -> 0..1 ตามตำแหน่งใน order; ไม่รู้จัก -> 0.5 (กลาง)"""
    try:
        n = len(order) - 1
        return order.index(value) / n if n > 0 else 0.5
    except ValueError:
        return 0.5


def buy_features_from_web(form):
    """
    สร้าง feature dict สำหรับ predict_buy จากข้อมูลฟอร์มเว็บ (web value space)

    Args:
        form (dict): ค่าจากฟอร์ม predict_buy.html (13 fields)
    Returns:
        dict: {col: value} — BUY_CAT_COLS + BUY_NUM_COLS
    """
    income = _s(form.get("income"))
    budget = _s(form.get("budget"))
    concern = _s(form.get("concern"))
    purpose = _s(form.get("purpose"))
    housing_status = _s(form.get("housing_status"))
    feat = {
        "gender": _s(form.get("gender")),
        "age": _s(form.get("age")),
        "children": _s(form.get("children")),
        "education": _s(form.get("education")),
        "occupation": _s(form.get("occupation")),
        "family_size": _s(form.get("family_size")),
        "housing_type": _s(form.get("housing_type")),
        "housing_status": housing_status,
        "parking": _s(form.get("parking")),
        "income": income,
        "budget": budget,
        "concern": concern,
        "purpose": purpose,
    }
    feat["purpose_housing"] = f"{purpose}|{housing_status}"
    feat["income_budget_gap"] = _rank01(budget, BUDGET_ORDER) - _rank01(income, INCOME_ORDER)
    return feat


def buy_feature_columns():
    """คืนลำดับคอลัมน์ฟีเจอร์ทั้งหมดของ predict_buy (cat + num)"""
    return BUY_CAT_COLS + BUY_NUM_COLS


# ============================================================
# predict_fuel  (6 fields + priority list ตาม docstring ใน predictor.py)
# ============================================================

FUEL_CAT_COLS = [
    "usage_type",
    "frequency",
    "distance",
    "prev_car",
    # หมายเหตุ: ลอง prev_car x usage_type (2026-07-30) แต่ 48% ของ cell มี expected
    # count < 5 (ผิดเงื่อนไข Chi-square) และ p=0.585 ไม่มีนัยสำคัญอยู่แล้ว — ตัดออก
]

FUEL_NUM_COLS = [
    "tech_env_concern",
    "resale_maintenance_concern",
    "priority_count",  # จำนวน priority ที่เลือก (0-10) — feature เสริมจากฟอร์มเดิม ไม่ใช่ข้อมูลใหม่
    # ฟีเจอร์เชิงประกอบ (composite/interaction, 2026-07-29) — คำนวณจากฟิลด์เดิมทั้งหมด
    "mileage_intensity",   # frequency x distance (norm 0-1) — ความเข้มของการใช้งานรวม
    "tech_cost_balance",   # tech_env_concern - resale_maintenance_concern — เอียงไปทางสนใจเทคโนโลยี(+) หรือค่าใช้จ่าย(-)
]

FREQUENCY_ORDER = ["occasional", "1-2days", "3-4days", "5-6days", "everyday"]
DISTANCE_ORDER = ["lt10", "10-30", "31-50", "51-70", "71-90", "90+"]

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
    frequency = _s(form.get("frequency"))
    distance = _s(form.get("distance"))
    tech_env_concern = _num(form.get("tech_env_concern"), default=3)
    resale_maintenance_concern = _num(form.get("resale_maintenance_concern"), default=3)
    usage_type = _s(form.get("usage_type"))
    prev_car = _s(form.get("prev_car")) or "none"
    feat = {
        "usage_type": usage_type,
        "frequency": frequency,
        "distance": distance,
        "prev_car": prev_car,
        "tech_env_concern": tech_env_concern,
        "resale_maintenance_concern": resale_maintenance_concern,
    }
    selected = _as_list(form.get("priority"))
    for tok in PRIORITY_TOKENS:
        feat["prio_" + tok] = 1 if tok in selected else 0
    feat["priority_count"] = len(selected)
    feat["mileage_intensity"] = _rank01(frequency, FREQUENCY_ORDER) * _rank01(distance, DISTANCE_ORDER)
    feat["tech_cost_balance"] = tech_env_concern - resale_maintenance_concern
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
