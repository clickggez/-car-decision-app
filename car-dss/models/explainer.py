# -*- coding: utf-8 -*-
"""
CarDSS — Explainer Module (2026-08-28)
อธิบายว่า "ทำไมโมเดลถึงตอบแบบนี้" สำหรับ predict_buy

วิธีที่ใช้: Counterfactual / What-if (occlusion แบบทีละฟิลด์)
-------------------------------------------------------------
สำหรับแต่ละช่องในฟอร์ม ลองเปลี่ยนค่าเป็นทุกตัวเลือกที่เหลือ แล้วดูว่า
ความน่าจะเป็นของ "ซื้อ" ขยับไปเท่าไหร่ — ช่องที่ขยับมากที่สุดคือเหตุผลหลัก

ทำไมเลือกวิธีนี้แทน SHAP:
  - โมเดลคือ BAGGING x25 ห่อ RandomForest 400 ต้น = ~10,000 ต้นไม้
    SHAP บนโมเดลขนาดนี้ใช้เวลาระดับนาที ใช้บนเว็บไม่ได้
  - วัดจริงบนเครื่องนี้: predict_proba 1 แถว = 343 ms, 30 แถว = 356 ms
    -> ยัดทุก variant เข้า batch เดียวแล้วเรียกครั้งเดียว ต้นทุนเกือบเท่าเดิม
  - ค่าที่ได้ตีความง่ายและตรงกับสิ่งที่ผู้ใช้ทำได้จริง ("ถ้าเปลี่ยน X เป็น Y")

⚠️ ข้อจำกัดที่ต้องบอกผู้ใช้เสมอ
  - นี่คือ "โมเดลคิดยังไง" ไม่ใช่ "ความจริงเชิงสาเหตุ" — โมเดล BUY แม่น 69.25% ± 3.91
  - อธิบายเฉพาะ BUY เท่านั้น **ห้ามทำกับ FUEL** เพราะ calibration ของ FUEL ชี้ผิดทาง
    (ดู 00-READ-FIRST.md §3.3) การอธิบายจากความน่าจะเป็นที่เชื่อไม่ได้ = หลอกผู้ใช้
"""

import config
from models import feature_encoding as fe

# ค่าที่เลือกได้ของแต่ละช่อง — คัดลอกโครงจาก validators._BUY_WHITELISTS
# ใช้ list (ไม่ใช่ set) เพราะต้องการลำดับคงที่ ผลลัพธ์จะได้ทำซ้ำได้
CHOICES = {
    'budget':              ['lt500000', '500001-800000', '800001-1200000',
                            '1200001-1500000', '1500000+'],
    'parking':             ['private', 'common', 'none'],
    'housing_status':      ['own', 'rent', 'family'],
    'concern':             ['fuel_price', 'electricity_cost', 'charging_station',
                            'gas_station', 'service_center', 'battery_life',
                            'maintenance', 'resale_value'],
    'purpose':             ['commute', 'trade', 'travel', 'convenience', 'avoid_public'],
    'charging_access':     ['has', 'installable', 'cannot', 'unsure'],
    'tco_awareness':       ['much_cheaper', 'slightly_cheaper', 'similar', 'unknown'],
    'incentive_awareness': ['aware_considered', 'aware_only', 'unknown'],
    'intention':           ['1', '2', '3', '4', '5', '6', '7'],
    'attitude':            ['1', '2', '3', '4', '5', '6', '7'],
    'subjective_norm':     ['1', '2', '3', '4', '5', '6', '7'],
    'pbc_financial':       ['1', '2', '3', '4', '5', '6', '7'],
    'income':              ['lt15000', '15001-25000', '25001-35000', '35001-50000',
                            '50001-75000', '75000+'],
    'housing_type':        ['house', 'townhome', 'condo', 'dormitory'],
    'family_size':         ['1-2', '3-4', '5+'],
    'children':            ['0', '1', '2', '3', '3+'],
}

# ช่องที่ผู้ใช้ "เปลี่ยนได้จริง" — ใช้ตอนเสนอข้อแนะนำ
# (เพศ/อายุ/การศึกษา/อาชีพ ไม่ใส่ เพราะเสนอให้เปลี่ยนไม่ได้และไม่สุภาพ)
ACTIONABLE = {'budget', 'parking', 'housing_status', 'concern', 'purpose',
              'charging_access', 'tco_awareness', 'incentive_awareness',
              'intention', 'attitude', 'subjective_norm', 'pbc_financial'}

FIELD_TH = {
    'budget': 'งบประมาณ', 'parking': 'ที่จอดรถ', 'housing_status': 'สถานะที่พัก',
    'concern': 'สิ่งที่กังวลมากที่สุด', 'purpose': 'วัตถุประสงค์ในการใช้รถ',
    'charging_access': 'จุดชาร์จไฟฟ้า', 'tco_awareness': 'ความรู้เรื่องค่าใช้จ่ายรวม',
    'incentive_awareness': 'ความรู้เรื่องสิทธิประโยชน์ภาษี',
    'intention': 'ความตั้งใจซื้อภายใน 6 เดือน', 'attitude': 'ความจำเป็นต้องมีรถ',
    'subjective_norm': 'การสนับสนุนจากคนใกล้ชิด', 'pbc_financial': 'ความพร้อมทางการเงิน',
    'income': 'รายได้ต่อเดือน', 'housing_type': 'ลักษณะที่พัก',
    'family_size': 'จำนวนสมาชิกในครอบครัว', 'children': 'จำนวนบุตร',
}

VALUE_TH = {
    'lt500000': 'ต่ำกว่า 5 แสน', '500001-800000': '5-8 แสน',
    '800001-1200000': '8 แสน-1.2 ล้าน', '1200001-1500000': '1.2-1.5 ล้าน',
    '1500000+': 'มากกว่า 1.5 ล้าน',
    'private': 'มีที่จอดส่วนตัว', 'common': 'ที่จอดส่วนกลาง/เช่า', 'none': 'ไม่มีที่จอด',
    'own': 'เป็นเจ้าของ', 'rent': 'เช่า', 'family': 'อยู่กับครอบครัว',
    'fuel_price': 'ราคาน้ำมัน', 'electricity_cost': 'ค่าไฟ',
    'charging_station': 'สถานีชาร์จ', 'gas_station': 'ปั๊มน้ำมัน',
    'service_center': 'ศูนย์บริการ', 'battery_life': 'อายุแบตเตอรี่',
    'maintenance': 'ค่าบำรุงรักษา', 'resale_value': 'ราคาขายต่อ',
    'commute': 'เดินทางไปทำงาน', 'trade': 'ค้าขาย', 'travel': 'ท่องเที่ยว',
    'convenience': 'ความสะดวก', 'avoid_public': 'เลี่ยงขนส่งสาธารณะ',
    'has': 'มีอยู่แล้ว', 'installable': 'ติดตั้งเพิ่มได้', 'cannot': 'ติดตั้งไม่ได้',
    'unsure': 'ไม่แน่ใจ',
    'much_cheaper': 'รู้ว่าถูกกว่ามาก', 'slightly_cheaper': 'รู้ว่าถูกกว่าเล็กน้อย',
    'similar': 'คิดว่าพอๆ กัน', 'unknown': 'ไม่ทราบ',
    'aware_considered': 'ทราบและเคยพิจารณา', 'aware_only': 'ทราบแต่ไม่ได้พิจารณา',
    'lt15000': 'ต่ำกว่า 15,000', '15001-25000': '15,001-25,000',
    '25001-35000': '25,001-35,000', '35001-50000': '35,001-50,000',
    '50001-75000': '50,001-75,000', '75000+': 'มากกว่า 75,000',
    'house': 'บ้านเดี่ยว', 'townhome': 'ทาวน์โฮม', 'condo': 'คอนโด', 'dormitory': 'หอพัก',
    '1-2': '1-2 คน', '3-4': '3-4 คน', '5+': '5 คนขึ้นไป',
}


def _th(field, value):
    """แปลงค่าดิบเป็นข้อความไทย — ช่อง Likert 1-7 แสดงเป็นระดับ"""
    if field in ('intention', 'attitude', 'subjective_norm', 'pbc_financial'):
        return 'ระดับ %s จาก 7' % value
    if field == 'children':
        return '%s คน' % value
    return VALUE_TH.get(value, str(value))


def explain_buy(input_data, top_n=3):
    """
    อธิบายผลของ predict_buy

    Returns dict:
        available     : bool — False เมื่ออยู่โหมด mock (ยังไม่มีโมเดลจริง)
        base_result   : 'ซื้อ' | 'ไม่ซื้อ'
        base_percent  : int  — % ที่โมเดลให้กับ "ซื้อ"
        reasons       : [{field, field_th, current_th, better_th, gain,
                          new_percent, flips}] เรียงจากปัจจัยที่ฉุดผลมากที่สุด
        suggestions   : เหมือน reasons แต่กรองเฉพาะช่องที่เปลี่ยนได้จริง
        can_flip      : bool — มีการเปลี่ยนช่องเดียวที่พลิกผลได้ไหม
    """
    if config.USE_MOCK:
        return {'available': False, 'reasons': [], 'suggestions': [],
                'can_flip': False, 'base_result': None, 'base_percent': None}

    import pandas as pd
    from models import predictor as pr

    bundle = pr._buy_bundle
    pipe = bundle['pipeline']
    cols = bundle['feature_cols']
    buy_idx = list(pipe.classes_).index('ซื้อ')

    rows, tags = [fe.buy_features_from_web(input_data)], [None]
    for field, options in CHOICES.items():
        cur = str(input_data.get(field, ''))
        for opt in options:
            if opt == cur:
                continue
            variant = dict(input_data)
            variant[field] = opt
            rows.append(fe.buy_features_from_web(variant))
            tags.append((field, cur, opt))

    # เรียก predict_proba รอบเดียวสำหรับทุก variant — ต้นทุนเกือบเท่าทำนายแถวเดียว
    proba = pipe.predict_proba(pd.DataFrame(rows, columns=cols))[:, buy_idx]

    base_p = float(proba[0])
    base_result = 'ซื้อ' if base_p >= 0.5 else 'ไม่ซื้อ'
    # ทิศทางที่ "ดีขึ้น" = เข้าใกล้ผลตรงข้ามกับที่ได้ตอนนี้
    sign = -1.0 if base_result == 'ซื้อ' else 1.0

    best = {}
    for i, tag in enumerate(tags):
        if tag is None:
            continue
        field, cur, opt = tag
        gain = sign * (float(proba[i]) - base_p)
        if gain > best.get(field, (0.0,))[0]:
            best[field] = (gain, cur, opt, float(proba[i]))

    reasons = []
    for field, (gain, cur, opt, p_new) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        if gain <= 0.005:                 # ต่ำกว่า 0.5 จุด = noise ไม่ต้องแสดง
            continue
        reasons.append({
            'field': field,
            'field_th': FIELD_TH.get(field, field),
            'current_th': _th(field, cur),
            'better_th': _th(field, opt),
            'gain': round(gain * 100, 1),
            'new_percent': int(round(p_new * 100)),
            'flips': (p_new >= 0.5) != (base_p >= 0.5),
        })

    return {
        'available': True,
        'base_result': base_result,
        'base_percent': int(round(base_p * 100)),
        'reasons': reasons[:top_n],
        'suggestions': [r for r in reasons if r['field'] in ACTIONABLE][:top_n],
        'can_flip': any(r['flips'] for r in reasons),
    }
