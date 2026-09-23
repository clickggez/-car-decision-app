"""
Centralized input validation for predict_buy and predict_fuel endpoints.
แก้ Known Issues: no whitelist, no negative-value check, whitespace bypass, XSS pass-through
"""

_BUY_WHITELISTS = {
    'gender':         {'male', 'female'},
    'age':            {'20-23', '24-26', '27-30', '31-40', '41-50', '51-60', '60+'},
    'children':       {'0', '1', '2', '3', '3+'},
    'education':      {'below_m3', 'm3', 'm6', 'vocational', 'bachelor', 'master', 'phd'},
    'occupation':     {'student', 'freelance', 'soe', 'private', 'government',
                       'business_owner', 'trader', 'farmer_fisher', 'other'},
    'family_size':    {'1-2', '3-4', '5+'},
    'housing_type':   {'house', 'townhome', 'condo', 'dormitory'},
    'housing_status': {'own', 'rent', 'family'},
    'parking':        {'private', 'common', 'none'},
    'income':         {'lt15000', '15001-25000', '25001-35000', '35001-50000',
                       '50001-75000', '75000+'},
    'budget':         {'lt500000', '500001-800000', '800001-1200000',
                       '1200001-1500000', '1500000+'},
    'concern':        {'fuel_price', 'electricity_cost', 'charging_station', 'gas_station',
                       'service_center', 'battery_life', 'maintenance', 'resale_value'},
    'purpose':        {'commute', 'trade', 'travel', 'convenience', 'avoid_public'},
    # ---- คำถามใหม่ 2026-08-01 (เพิ่มลงฟอร์มเว็บ 2026-08-09) ----
    # token ต้องตรงกับ dict ใน train_models.py เป๊ะ ไม่งั้น feature_encoding
    # จะมองเป็นค่าว่างแล้วไปเข้า mode-fill ทำให้ผลทำนายเพี้ยนแบบเงียบ ๆ
    'charging_access':     {'has', 'installable', 'cannot', 'unsure'},
    'tco_awareness':       {'much_cheaper', 'slightly_cheaper', 'similar', 'unknown'},
    'incentive_awareness': {'aware_considered', 'aware_only', 'unknown'},
    'intention':       {'1', '2', '3', '4', '5', '6', '7'},
    'attitude':        {'1', '2', '3', '4', '5', '6', '7'},
    'subjective_norm': {'1', '2', '3', '4', '5', '6', '7'},
    'pbc_financial':   {'1', '2', '3', '4', '5', '6', '7'},
}

# life_events เป็น multi-select ที่ "ไม่เลือกเลย" ถือว่าถูกต้อง (= ไม่มีเหตุการณ์)
# จึงตรวจแยกจาก _BUY_WHITELISTS ซึ่งบังคับว่าต้องมีค่า
_LIFE_EVENT_ALLOWED = {'job', 'move', 'child', 'income'}

# ฟิลด์ที่ฟอร์มเว็บยังถามอยู่ = ฟิลด์ที่โมเดล fuel ใช้จริง (ดู analysis/fuel_feature_usage_2026-09-23.txt)
# 23 ก.ย. 2569: ตัด usage_type / frequency / distance / tech_env_concern /
# resale_maintenance_concern / ev_exposure / range_anxiety ออกจากฟอร์ม เพราะ pipeline
# ของ fuel_model.pkl ตั้ง remainder='drop' ทิ้งคอลัมน์เหล่านี้ทั้งหมด — สลับค่ามั่ว 10 รอบ
# คำตอบไม่เปลี่ยนสักเคส (0.0%) จึงไม่บังคับให้ผู้ใช้กรอกอีกต่อไป
# feature_encoding.fuel_features_from_web ใส่ค่า default ให้ครบอยู่แล้ว โมเดลจึงรับ input ครบ 26 คอลัมน์เท่าเดิม
_FUEL_WHITELISTS = {
    'prev_car': {'ice', 'hybrid', 'ev', 'none'},
}

# ฟิลด์ที่เลิกถามแล้ว — ถ้ายังถูกส่งมา (เช่น ทดสอบเก่า หรือ client เดิม) ต้องยังผ่าน validate ได้
_FUEL_OPTIONAL_WHITELISTS = {
    'usage_type':                 {'city', 'highway', 'both'},
    'frequency':                  {'occasional', '1-2days', '3-4days', '5-6days', 'everyday'},
    'distance':                   {'lt10', '10-30', '31-50', '51-70', '71-90', '90+'},
    'tech_env_concern':           {'1', '2', '3', '4', '5'},
    'resale_maintenance_concern': {'1', '2', '3', '4', '5'},
    'ev_exposure':                {'both', 'ev_only', 'hybrid_only', 'none'},
    'range_anxiety':              {'1', '2', '3', '4', '5', '6', '7'},
}

# NEP 5 ข้อ (สเกล 1-5) — ข้อที่ 5 เป็น reverse-worded, app.py เป็นผู้กลับคะแนน
# แล้วเฉลี่ยเป็น nep_score ก่อนส่งเข้าโมเดล (ตรรกะเดียวกับ train_models._nep_score)
_NEP_FIELDS = ('nep_1', 'nep_2', 'nep_3', 'nep_4', 'nep_5')
_NEP_ALLOWED = {'1', '2', '3', '4', '5'}

_PRIORITY_ALLOWED = {
    'price', 'installment', 'fuel_cost', 'electricity_cost', 'maintenance_cost',
    'performance', 'design', 'technology', 'value', 'warranty',
}


def validate_buy(input_data):
    """Validate predict_buy input. Returns (is_valid, error_message)."""
    for field, allowed in _BUY_WHITELISTS.items():
        val = input_data.get(field, '')
        if not isinstance(val, str) or not val.strip():
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
        if val not in allowed:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    # life_events: ไม่เลือกเลยได้ (= ไม่มีเหตุการณ์ในรอบ 6 เดือน) แต่ถ้าเลือกต้องอยู่ใน whitelist
    events = input_data.get('life_events', [])
    if not isinstance(events, (list, tuple)):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if any(e not in _LIFE_EVENT_ALLOWED for e in events):
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

    # ฟิลด์ที่เลิกถามแล้ว: ไม่ส่งมาก็ได้ แต่ถ้าส่งมาต้องเป็นค่าที่ถูกต้อง
    for field, allowed in _FUEL_OPTIONAL_WHITELISTS.items():
        val = input_data.get(field, '')
        if isinstance(val, str) and val.strip() and val not in allowed:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    priority = input_data.get('priority', [])
    if not priority:
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if any(p not in _PRIORITY_ALLOWED for p in priority):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    for f in _NEP_FIELDS:
        val = input_data.get(f, '')
        if not isinstance(val, str) or val not in _NEP_ALLOWED:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    return True, None
