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
    # ---- ฟีเจอร์จากคำถามใหม่ (2026-08-01) ----
    # เพิ่มคำถามต่อท้ายแบบสอบถามเดิม (ไม่แก้ของเดิม) ตามที่อาจารย์อนุญาต
    # กลุ่ม EV-domain 3 ตัวนี้ถามไว้เพื่อ predict_fuel แต่ chi-square พบว่ามีนัยสำคัญ
    # กับ label ของ predict_buy แทน (ดู agent-docs/01-architecture.md) จึงใส่เป็น
    # ผู้สมัครของทั้งสองโมเดล ปล่อยให้ feature selection ตัดสินตามข้อมูลจริง
    "charging_access",       # จุดชาร์จที่บ้าน/ที่ทำงาน
    "tco_awareness",         # ความรู้เรื่องต้นทุนรวม (ค่าไฟ vs ค่าน้ำมัน)
    "incentive_awareness",   # ความรู้เรื่องสิทธิประโยชน์ภาครัฐ
]

# ฟีเจอร์เชิงประกอบ (composite/interaction) — คำนวณจากฟิลด์ฟอร์มเดิมทั้งหมด
# ไม่ใช่ข้อมูลใหม่จากแบบสอบถาม (2026-07-29, ดู agent-docs/01-architecture.md)
BUY_NUM_COLS = [
    "income_budget_gap",   # งบซื้อรถเทียบกับรายได้ (ยิ่งสูง = งบเกินตัวมากกว่ารายได้บ่งชี้)
    "financial_readiness_gap", # ช่องว่างความพร้อมทางการเงินจริงเทียบงบซื้อ
    # ---- ฟีเจอร์จากคำถามใหม่ (2026-08-01) — กรอบ Theory of Planned Behavior ----
    # วัดเจตนา/ทัศนคติตรงๆ แทนการอนุมานจาก demographic (Likert 1-7)
    "intention",         # เจตนาซื้อภายใน 6 เดือน (TPB: intention)
    "attitude",          # การมีรถสำคัญกับชีวิตเพียงใด (TPB: attitude)
    "subjective_norm",   # คนใกล้ชิดคิดว่าควรมีรถหรือไม่ (TPB: subjective norm)
    "pbc_financial",     # ความพร้อมทางการเงินตอนนี้ (TPB: perceived behavioral control)
    # เหตุการณ์กระตุ้นเชิงสถานการณ์ (life event) — multi-select แตกเป็น multi-hot
    # เพราะถ้าเก็บเป็นหมวดหมู่รวม จะได้ 25 combo บน n=500 ทำให้ chi-square ไม่ valid
    # (70% ของ cell มี expected count < 5)
    "evt_job",           # เปลี่ยนงาน/ที่ทำงานใหม่
    "evt_move",          # ย้ายที่อยู่อาศัย
    "evt_child",         # มีบุตร/สมาชิกครอบครัวเพิ่ม
    "evt_income",        # รายได้เปลี่ยนแปลงอย่างมีนัยสำคัญ
]

# ค่าที่ใช้เมื่อฟอร์มเว็บยังไม่มีคำถามใหม่ (เว็บ deploy อยู่บนฟอร์มเดิม 13 ฟิลด์)
# 4 = กลางของสเกล 1-7, "" = ให้ไปเข้า mode-fill เหมือนฟิลด์หมวดหมู่ที่ขาดหาย
NEW_BUY_DEFAULTS = {
    "intention": 4, "attitude": 4, "subjective_norm": 4, "pbc_financial": 4,
    "evt_job": 0, "evt_move": 0, "evt_child": 0, "evt_income": 0,
    "charging_access": "", "tco_awareness": "", "incentive_awareness": "",
}

LIFE_EVENT_TOKENS = ["job", "move", "child", "income"]

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

    # คำถามใหม่ (2026-08-01) — ฟอร์มเว็บปัจจุบันยังไม่มีคำถามเหล่านี้ จึงใช้ค่ากลาง
    # เป็น default เพื่อไม่ให้ inference พัง (train/serve skew guard เดิมยังทำงานปกติ)
    for key in ("intention", "attitude", "subjective_norm", "pbc_financial"):
        feat[key] = _num(form.get(key), default=NEW_BUY_DEFAULTS[key])
    feat["financial_readiness_gap"] = feat["income_budget_gap"] + (4.0 - feat["pbc_financial"]) / 3.0
    events = _as_list(form.get("life_events"))
    for tok in LIFE_EVENT_TOKENS:
        feat["evt_" + tok] = 1 if tok in events else 0
    for key in ("charging_access", "tco_awareness", "incentive_awareness"):
        feat[key] = _s(form.get(key))
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
    # ---- ฟีเจอร์จากคำถามใหม่ (2026-08-01) — กรอบงานวิจัย EV adoption ----
    "charging_access",       # จุดชาร์จที่บ้าน/ที่ทำงาน (งานวิจัยระบุเป็นปัจจัยอันดับ 1 ของการเลือก EV)
    "ev_exposure",           # เคยทดลองขับ/นั่ง EV หรือ Hybrid มาก่อนหรือไม่
    "tco_awareness",         # ความรู้เรื่องต้นทุนรวม (ค่าไฟเทียบค่าน้ำมัน)
    "incentive_awareness",   # ความรู้เรื่องสิทธิประโยชน์ภาครัฐ
]

FUEL_NUM_COLS = [
    "tech_env_concern",
    "resale_maintenance_concern",
    "priority_count",  # จำนวน priority ที่เลือก (0-10) — feature เสริมจากฟอร์มเดิม ไม่ใช่ข้อมูลใหม่
    # ฟีเจอร์เชิงประกอบ (composite/interaction, 2026-07-29) — คำนวณจากฟิลด์เดิมทั้งหมด
    "mileage_intensity",   # frequency x distance (norm 0-1) — ความเข้มของการใช้งานรวม
    "tech_cost_balance",   # tech_env_concern - resale_maintenance_concern — เอียงไปทางสนใจเทคโนโลยี(+) หรือค่าใช้จ่าย(-)
    # ---- ฟีเจอร์จากคำถามใหม่ (2026-08-01) ----
    "range_anxiety",       # กังวลแบตหมดระหว่างทาง (Likert 1-7) — วัดทัศนคติตรง แทนการอนุมานจากระยะทาง
    "nep_score",           # New Ecological Paradigm 5 ข้อ เฉลี่ย (1-5) ข้อสุดท้าย reverse-worded แล้ว
    "ev_readiness_index",  # ดัชนีความพร้อมในการเปลี่ยนเป็น EV (ประมวลผลจากจุดชาร์จ, ประสบการณ์, ทัศนคติ)
]

# ค่า default เมื่อฟอร์มเว็บยังไม่มีคำถามใหม่ (เว็บ deploy อยู่บนฟอร์มเดิม)
NEW_FUEL_DEFAULTS = {
    "range_anxiety": 4,   # กลางของสเกล 1-7
    "nep_score": 3.0,     # กลางของสเกล 1-5
    "charging_access": "", "ev_exposure": "", "tco_awareness": "", "incentive_awareness": "",
}

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

    # คำถามใหม่ (2026-08-01) — ฟอร์มเว็บปัจจุบันยังไม่มี จึงใช้ค่ากลางเป็น default
    for key in ("charging_access", "ev_exposure", "tco_awareness", "incentive_awareness"):
        feat[key] = _s(form.get(key))
    feat["range_anxiety"] = _num(form.get("range_anxiety"), default=NEW_FUEL_DEFAULTS["range_anxiety"])
    nep = form.get("nep_score")
    try:
        feat["nep_score"] = float(nep)
    except (TypeError, ValueError):
        feat["nep_score"] = NEW_FUEL_DEFAULTS["nep_score"]

    ch_score = 1.0 if feat["charging_access"] == "has" else (0.5 if feat["charging_access"] == "installable" else 0.0)
    exp_score = 1.0 if feat["ev_exposure"] in ("both", "ev_only") else (0.5 if feat["ev_exposure"] == "hybrid_only" else 0.0)
    tco_score = 1.0 if feat["tco_awareness"] == "much_cheaper" else (0.5 if feat["tco_awareness"] == "slightly_cheaper" else 0.0)
    feat["ev_readiness_index"] = ch_score + exp_score + tco_score + (feat["nep_score"] / 5.0) - (feat["range_anxiety"] / 7.0)
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
