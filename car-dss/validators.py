"""
Centralized input validation for predict_buy and predict_fuel endpoints.
แก้ Known Issues: no whitelist, no negative-value check, whitespace bypass, XSS pass-through
"""

# 27 ก.ย. 2569: โมเดลเทรนใหม่จากแบบสอบถามชุด n=514 (ผู้ใช้อนุมัติ) — ฟอร์มถามเฉพาะช่องที่โมเดลใช้จริง
# buy_model.pkl  ใช้ education + family_size + purpose_avoid_public (multi-hot จาก purpose)
# fuel_model.pkl ใช้ usage_type + frequency + distance + tech_env_concern + mileage_intensity
#   (จาก frequency, distance) + prev_ice/prev_hybrid/prev_ev (จาก prev_car) + prio_* 5 ตัว (จาก priority)
# ดู analysis/verify_newdata_2026-09-27.txt · ไม่มีคำถาม TPB / กลุ่ม EV / NEP
# purpose / prev_car / priority เป็นคำถามเลือกได้หลายข้อ -> list ตรวจแยกด้านล่าง
# ⚠️ ถ้าเทรนใหม่แล้วชุดฟีเจอร์เปลี่ยน ต้องแก้ตรงนี้ + ฟอร์ม — tests/test_user_facing.py จะฟ้องเอง

_BUY_WHITELISTS = {
    'education':      {'below_m3', 'm3', 'm6', 'vocational', 'bachelor', 'master', 'phd'},
    'family_size':    {'1-2', '3-4', '5+'},
}

# ฟิลด์ที่ยังอยู่ในแบบสอบถามแต่โมเดลชุดนี้ไม่ได้ใช้ — เลิกถามในฟอร์มแล้ว
# ถ้ายังถูกส่งมา (client เดิม / เทสต์เก่า) ไม่บังคับ แต่ถ้าส่งมาต้องเป็นค่าที่ถูกต้อง
_BUY_OPTIONAL_WHITELISTS = {
    'gender':         {'male', 'female'},
    'age':            {'20-23', '24-26', '27-30', '31-40', '41-50', '51-60', '60+'},
    'children':       {'0', '1', '2', '3', '3+'},
    'occupation':     {'student', 'freelance', 'soe', 'private', 'government',
                       'business_owner', 'trader', 'farmer_fisher', 'other'},
    'housing_type':   {'house', 'townhome', 'condo', 'dormitory'},
    'housing_status': {'own', 'rent', 'family'},
    'parking':        {'private', 'common', 'none'},
    'income':         {'lt15000', '15001-25000', '25001-35000', '35001-50000',
                       '50001-75000', '75000+'},
    'budget':         {'lt500000', '500001-800000', '800001-1200000',
                       '1200001-1500000', '1500000+'},
}

# purpose เลือกได้หลายข้อ ต้องเลือกอย่างน้อย 1 (ทุกคนในแบบสอบถามตอบข้อนี้)
_PURPOSE_ALLOWED = {'commute', 'trade', 'travel', 'convenience', 'avoid_public'}

_FUEL_WHITELISTS = {
    'usage_type':       {'city', 'highway', 'both'},
    'frequency':        {'occasional', '1-2days', '3-4days', '5-6days', 'everyday'},
    'distance':         {'lt10', '10-30', '31-50', '51-70', '71-90', '90+'},
    # ถ้อยคำในฟอร์มตรงกับข้อ 7P ในแบบสอบถามที่ใช้เทรน (5 = เห็นด้วยอย่างยิ่ง)
    'tech_env_concern': {'1', '2', '3', '4', '5'},
}

# ฟิลด์ที่เลิกถามแล้ว — ถ้ายังถูกส่งมา ต้องยังผ่าน validate ได้
_FUEL_OPTIONAL_WHITELISTS = {
    'resale_maintenance_concern': {'1', '2', '3', '4', '5'},
}

# prev_car เลือกได้หลายข้อ — ไม่เลือกเลยได้ (ยังไม่เคยใช้รถ) · 'none' รับไว้เพื่อ client เดิม
_PREV_CAR_ALLOWED = {'ice', 'hybrid', 'ev', 'none'}

_PRIORITY_ALLOWED = {
    'price', 'installment', 'fuel_cost', 'electricity_cost', 'maintenance_cost',
    'performance', 'design', 'technology', 'value', 'warranty',
}


def _as_str_list(v):
    """รับได้ทั้ง list (request.form.getlist) และ string เดี่ยว — คืน None ถ้าชนิดผิด"""
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, (list, tuple)):
        return list(v) if all(isinstance(x, str) for x in v) else None
    return None


def _check_optional(input_data, whitelists):
    """ไม่ส่งมาก็ได้ แต่ถ้าส่งมาต้องเป็นค่าที่ถูกต้อง"""
    for field, allowed in whitelists.items():
        val = input_data.get(field, '')
        if isinstance(val, str) and val.strip() and val not in allowed:
            return False
    return True


def validate_buy(input_data):
    """Validate predict_buy input. Returns (is_valid, error_message)."""
    for field, allowed in _BUY_WHITELISTS.items():
        val = input_data.get(field, '')
        if not isinstance(val, str) or not val.strip():
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
        if val not in allowed:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if not _check_optional(input_data, _BUY_OPTIONAL_WHITELISTS):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    purpose = _as_str_list(input_data.get('purpose', []))
    if not purpose or any(p not in _PURPOSE_ALLOWED for p in purpose):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    return True, None


def validate_fuel(input_data):
    """Validate predict_fuel input. Returns (is_valid, error_message)."""
    for field, allowed in _FUEL_WHITELISTS.items():
        val = input_data.get(field, '')
        if not isinstance(val, str) or not val.strip():
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
        if val not in allowed:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if not _check_optional(input_data, _FUEL_OPTIONAL_WHITELISTS):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    prev = _as_str_list(input_data.get('prev_car', []))
    if prev is None or any(p not in _PREV_CAR_ALLOWED for p in prev):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    priority = input_data.get('priority', [])
    if not priority:
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if any(p not in _PRIORITY_ALLOWED for p in priority):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    return True, None
