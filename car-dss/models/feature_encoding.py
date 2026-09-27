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
# 2026-09-26: เทรนจากแบบสอบถามชุดใหม่ (n=511) — ไม่มีคำถาม TPB / กลุ่ม EV / NEP แล้ว
# ⚠️ .pkl ที่เทรนก่อนวันนี้ (feature_cols มีคอลัมน์ที่ถูกตัด) ใช้กับไฟล์นี้ไม่ได้
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
    # 2026-09-27: concern / purpose ย้ายไปเป็น multi-hot (concern_* / purpose_*) ใน BUY_NUM_COLS
    # เพราะเป็นคำถามเลือกได้หลายข้อ — เดิมเก็บแค่ตัวเลือกแรก ทำให้คำตอบผสมถูกยุบหายไป
    # ฟีเจอร์ผสมเชิงหมวดหมู่ (categorical interaction, 2026-07-30) — เก็บเข้า BUY_CAT_COLS
    # เพื่อให้แข่ง Chi-square เหมือนฟีเจอร์ดิบทุกตัว ไม่ใช่ข้อมูลใหม่จากแบบสอบถาม
    # หมายเหตุ: ลอง concern x budget ด้วย (40 combo) แต่ 44% ของ cell มี expected count < 5
    # (ผิดเงื่อนไข Chi-square — ค่า p ที่ได้ไม่น่าเชื่อถือ) จึงตัดออก เก็บเฉพาะตัวที่
    # ผ่านเงื่อนไขสถิติจริง (purpose_housing: 0% cell < 5)
    # 2026-09-27: ตัด purpose_housing (purpose x housing_status) — ต้องใช้ purpose ค่าเดียว
    # นิยามไม่ได้แล้วเมื่อ purpose เป็น multi-hot
    # 2026-09-26: ตัด charging_access / tco_awareness / incentive_awareness ออก
    # แบบสอบถามชุดใหม่ (n=511) ไม่มีคำถามกลุ่ม EV และอาจารย์ไม่ต้องการคำถามกลุ่มนี้แล้ว
]

# ฟีเจอร์เชิงประกอบ (composite/interaction) — คำนวณจากฟิลด์ฟอร์มเดิมทั้งหมด
# ไม่ใช่ข้อมูลใหม่จากแบบสอบถาม (2026-07-29, ดู agent-docs/01-architecture.md)
# multi-select -> multi-hot (2026-09-27) token ตรงกับตาราง map ใน train_models.py
# concern ถามเฉพาะผู้มีรถ ผู้ไม่มีรถ = 0 ทุกตัว (เลิก mode-fill ที่เคยเติม charging_station ให้ 276 คน)
CONCERN_TOKENS = ["fuel_price", "electricity_cost", "charging_station", "service_center",
                  "battery_life", "maintenance", "resale_value"]
PURPOSE_TOKENS = ["commute", "trade", "travel", "convenience", "avoid_public"]

BUY_NUM_COLS = [
    "income_budget_gap",   # งบซื้อรถเทียบกับรายได้ (ยิ่งสูง = งบเกินตัวมากกว่ารายได้บ่งชี้)
] + ["concern_" + t for t in CONCERN_TOKENS] + ["purpose_" + t for t in PURPOSE_TOKENS] + [
    # 2026-09-26: ตัด TPB 4 ข้อ (intention/attitude/subjective_norm/pbc_financial),
    # evt_* 4 ตัว และ financial_readiness_gap (คำนวณจาก pbc_financial) ออก
    # เพราะแบบสอบถามชุดใหม่ไม่มีคำถามเหล่านี้
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
    }
    # concern / purpose รับได้ทั้ง list (checkbox) และ string คั่นด้วย ','
    concern = _as_list(form.get("concern"))
    purpose = _as_list(form.get("purpose"))
    for tok in CONCERN_TOKENS:
        feat["concern_" + tok] = 1 if tok in concern else 0
    for tok in PURPOSE_TOKENS:
        feat["purpose_" + tok] = 1 if tok in purpose else 0
    feat["income_budget_gap"] = _rank01(budget, BUDGET_ORDER) - _rank01(income, INCOME_ORDER)
    return feat


def buy_feature_columns():
    """คืนลำดับคอลัมน์ฟีเจอร์ทั้งหมดของ predict_buy (cat + num)"""
    return BUY_CAT_COLS + BUY_NUM_COLS


# ============================================================
# predict_fuel  (6 fields + priority list ตาม docstring ใน predictor.py)
# ============================================================

# 2026-09-27: prev_car ("ประสบการณ์ประเภทรถยนต์ที่เคยใช้") เลือกได้หลายข้อ -> multi-hot 3 คอลัมน์
# เดิมเก็บตัวเลือกแรกค่าเดียว คนที่เคยใช้ทั้งสันดาปและไฮบริดจึงกลายเป็น "ice" เฉย ๆ
# ไม่ได้เลือกเลย / 'none' = 0 ทั้งสามตัว
PREV_CAR_TOKENS = ["ice", "hybrid", "ev"]

FUEL_CAT_COLS = [
    "usage_type",
    "frequency",
    "distance",
    # หมายเหตุ: ลอง prev_car x usage_type (2026-07-30) แต่ 48% ของ cell มี expected
    # count < 5 (ผิดเงื่อนไข Chi-square) และ p=0.585 ไม่มีนัยสำคัญอยู่แล้ว — ตัดออก
    # 2026-09-26: ตัด charging_access / ev_exposure / tco_awareness / incentive_awareness
    # ออก — แบบสอบถามชุดใหม่ไม่มีคำถามกลุ่ม EV
]

FUEL_NUM_COLS = [
    "tech_env_concern",
    "resale_maintenance_concern",
    "priority_count",  # จำนวน priority ที่เลือก (0-10) — feature เสริมจากฟอร์มเดิม ไม่ใช่ข้อมูลใหม่
    # ฟีเจอร์เชิงประกอบ (composite/interaction, 2026-07-29) — คำนวณจากฟิลด์เดิมทั้งหมด
    "mileage_intensity",   # frequency x distance (norm 0-1) — ความเข้มของการใช้งานรวม
    "tech_cost_balance",   # tech_env_concern - resale_maintenance_concern — เอียงไปทางสนใจเทคโนโลยี(+) หรือค่าใช้จ่าย(-)
    "prev_ice", "prev_hybrid", "prev_ev",   # multi-hot ของ prev_car (2026-09-27)
    # 2026-09-26: ตัด range_anxiety / nep_score / ev_readiness_index ออก
    # — แบบสอบถามชุดใหม่ไม่มีคำถาม range anxiety และ NEP
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
    prev_car = _as_list(form.get("prev_car"))
    feat = {
        "usage_type": usage_type,
        "frequency": frequency,
        "distance": distance,
        "tech_env_concern": tech_env_concern,
        "resale_maintenance_concern": resale_maintenance_concern,
    }
    for tok in PREV_CAR_TOKENS:
        feat["prev_" + tok] = 1 if tok in prev_car else 0
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
# ฟีเจอร์ -> ช่องในฟอร์มเว็บที่ต้องถาม (2026-09-26)
# ใช้ตรวจว่า "ฟอร์มถามเฉพาะคำถามที่โมเดลใช้จริง" จาก cat_cols/num_cols ใน .pkl
# (ColumnTransformer ตั้ง remainder='drop' — คอลัมน์ที่ไม่อยู่ในสองรายการนั้นถูกทิ้งก่อนเข้าโมเดล)
# ฟีเจอร์ที่ไม่อยู่ใน dict นี้ = ช่องในฟอร์มชื่อเดียวกันตรง ๆ
# ============================================================

DERIVED_FROM = {
    "income_budget_gap": ("income", "budget"),
    "priority_count": ("priority",),
    "mileage_intensity": ("frequency", "distance"),
    "tech_cost_balance": ("tech_env_concern", "resale_maintenance_concern"),
}
DERIVED_FROM.update({"prio_" + t: ("priority",) for t in PRIORITY_TOKENS})
DERIVED_FROM.update({"prev_" + t: ("prev_car",) for t in PREV_CAR_TOKENS})
DERIVED_FROM.update({"concern_" + t: ("concern",) for t in CONCERN_TOKENS})
DERIVED_FROM.update({"purpose_" + t: ("purpose",) for t in PURPOSE_TOKENS})


def form_fields_used(cat_cols, num_cols):
    """คืนชุดชื่อช่องในฟอร์มเว็บที่โมเดลต้องใช้ จากรายการฟีเจอร์ที่ pipeline ใช้จริง"""
    out = set()
    for c in list(cat_cols) + list(num_cols):
        out.update(DERIVED_FROM.get(c, (c,)))
    return out


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
