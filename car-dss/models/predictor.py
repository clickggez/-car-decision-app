"""
CarDSS — Predictor Module
Mock predictions ใช้ชั่วคราวจนกว่าจะมีโมเดลจริง (.pkl)

การใช้งาน:
    from models.predictor import predict_buy, predict_fuel

เมื่อโมเดลจริงพร้อม:
    1. วาง buy_model.pkl / fuel_model.pkl ใน models/
    2. เปลี่ยน USE_MOCK = False ใน config.py
    3. ระบบจะสลับไปใช้โมเดลจริงอัตโนมัติ
"""

import random
import config
from models import feature_encoding as fe

# จะ import เมื่อ USE_MOCK = False เท่านั้น
if not config.USE_MOCK:
    try:
        import joblib
        _buy_bundle = joblib.load(config.BUY_MODEL_PATH)
        _fuel_bundle = joblib.load(config.FUEL_MODEL_PATH)
    except FileNotFoundError:
        print("[WARNING] Model files not found, falling back to mock predictions")
        config.USE_MOCK = True


# ============================================================
# MOCK PREDICTIONS
# ============================================================

def _mock_predict_buy(input_data):
    """ผลจำลอง: ซื้อ/ไม่ซื้อ — ใช้ชั่วคราวจนกว่าจะมีโมเดลจริง"""
    # สุ่มผลลัพธ์โดยมีน้ำหนักให้ "ซื้อ" มากกว่า (70/30)
    result = random.choices(["ซื้อ", "ไม่ซื้อ"], weights=[70, 30], k=1)[0]
    confidence = round(random.uniform(0.72, 0.95), 3) if result == "ซื้อ" else round(random.uniform(0.60, 0.85), 3)
    model_name = random.choice(["SVM", "ANN"])

    return {
        "result": result,
        "confidence": confidence,
        "model_used": f"{model_name} (mock)"
    }


def _mock_predict_fuel(input_data):
    """ผลจำลอง: ประเภทเชื้อเพลิง — ใช้ชั่วคราว"""
    # สุ่มคะแนนแต่ให้ EV สูงกว่า (mock bias)
    ev_score = random.randint(65, 92)
    hybrid_score = random.randint(45, 75)
    ice_score = random.randint(30, 60)

    scores = {"EV": ev_score, "Hybrid": hybrid_score, "ICE": ice_score}
    top = max(scores, key=scores.get)

    result_map = {"EV": "ไฟฟ้า (EV)", "Hybrid": "ไฮบริด", "ICE": "สันดาป (ICE)"}
    top_score = scores[top]
    confidence = round(top_score / 100, 3)
    model_name = random.choice(["SVM", "ANN"])

    return {
        "result": result_map[top],
        "scores": scores,
        "confidence": confidence,
        "model_used": f"{model_name} (mock)"
    }


# ============================================================
# REAL MODEL PREDICTIONS (Phase 3)
# ============================================================

def _real_predict_buy(input_data):
    """โมเดลจริง: ซื้อ/ไม่ซื้อ — ใช้เมื่อ USE_MOCK = False"""
    import pandas as pd

    feat = fe.buy_features_from_web(input_data)
    X = pd.DataFrame([feat], columns=_buy_bundle["feature_cols"])
    pipe = _buy_bundle["pipeline"]
    result = pipe.predict(X)[0]
    proba = pipe.predict_proba(X)[0]
    confidence = round(float(max(proba)), 3)

    return {
        "result": result,
        "confidence": confidence,
        "model_used": f"{_buy_bundle['model_name']} (real)",
    }


def _real_predict_fuel(input_data):
    """โมเดลจริง: ประเภทเชื้อเพลิง — ใช้เมื่อ USE_MOCK = False"""
    import pandas as pd

    feat = fe.fuel_features_from_web(input_data)
    X = pd.DataFrame([feat], columns=_fuel_bundle["feature_cols"])
    pipe = _fuel_bundle["pipeline"]
    proba = pipe.predict_proba(X)[0]
    classes = pipe.classes_
    scores = {cls: int(round(p * 100)) for cls, p in zip(classes, proba)}
    top = max(scores, key=scores.get)

    result_map = {"EV": "ไฟฟ้า (EV)", "Hybrid": "ไฮบริด", "ICE": "สันดาป (ICE)"}
    confidence = round(scores[top] / 100, 3)

    return {
        "result": result_map.get(top, top),
        "scores": {k: scores.get(k, 0) for k in ("EV", "Hybrid", "ICE")},
        "confidence": confidence,
        "model_used": f"{_fuel_bundle['model_name']} (real)",
    }


# ============================================================
# PUBLIC API — เรียกใช้จาก app.py
# ============================================================

def predict_buy(input_data):
    """
    พยากรณ์ซื้อ/ไม่ซื้อ

    Args:
        input_data (dict): ข้อมูลจากฟอร์ม predict_buy มี 13 fields:
            gender           : 'male' | 'female'
            age              : '20-23' | '24-26' | '27-30' | '31-40' | '41-50' | '51-60' | '60+'
            children         : '0' | '1' | '2' | '3' | '3+'
            education        : 'below_m3' | 'm3' | 'm6' | 'vocational' | 'bachelor' | 'master' | 'phd'
            occupation       : 'student' | 'freelance' | 'soe' | 'private' | 'government' |
                               'business_owner' | 'trader' | 'farmer_fisher' | 'other'
            family_size      : '1-2' | '3-4' | '5+'
            housing_type     : 'house' | 'townhome' | 'condo' | 'dormitory'
            housing_status   : 'own' | 'rent' | 'family'
            parking          : 'private' | 'common' | 'none'
            income           : 'lt15000' | '15001-25000' | '25001-35000' | '35001-50000' |
                               '50001-75000' | '75000+'
            budget           : 'lt500000' | '500001-800000' | '800001-1200000' |
                               '1200001-1500000' | '1500000+'
            concern          : 'fuel_price' | 'electricity_cost' | 'charging_station' |
                               'gas_station' | 'service_center' | 'battery_life' |
                               'maintenance' | 'resale_value'
            purpose          : 'commute' | 'trade' | 'travel' | 'convenience' | 'avoid_public'

    Returns:
        dict: {
            'result'     : 'ซื้อ' | 'ไม่ซื้อ',
            'confidence' : float (0.0–1.0),
            'model_used' : str  เช่น 'SVM (mock)'
        }

    Example:
        >>> predict_buy({
        ...     'gender': 'male', 'age': '27-30', 'children': '0',
        ...     'education': 'bachelor', 'occupation': 'private',
        ...     'family_size': '1-2', 'housing_type': 'condo',
        ...     'housing_status': 'rent', 'parking': 'common',
        ...     'income': '25001-35000', 'budget': '500001-800000',
        ...     'concern': 'fuel_price', 'purpose': 'commute'
        ... })
        {'result': 'ซื้อ', 'confidence': 0.883, 'model_used': 'SVM (mock)'}
    """
    if config.USE_MOCK:
        return _mock_predict_buy(input_data)
    return _real_predict_buy(input_data)


def predict_fuel(input_data):
    """
    พยากรณ์ประเภทเชื้อเพลิงที่เหมาะสม

    Args:
        input_data (dict): ข้อมูลจากฟอร์ม predict_fuel มี 6 fields + 1 list:
            usage_type                 : 'city' | 'highway' | 'both'
            frequency                  : 'occasional' | '1-2days' | '3-4days' | '5-6days' | 'everyday'
            distance                   : 'lt10' | '10-30' | '31-50' | '51-70' | '71-90' | '90+'
            prev_car                   : 'ice' | 'hybrid' | 'ev' | 'none'
            tech_env_concern           : '1'–'5'  (1=ไม่สนใจ, 5=สนใจมาก)
            resale_maintenance_concern : '1'–'5'  (1=ไม่สนใจ, 5=สนใจมาก)
            priority (list)            : subset ของ {'price', 'installment', 'fuel_cost',
                                         'electricity_cost', 'maintenance_cost', 'performance',
                                         'design', 'technology', 'value', 'warranty'}

    Returns:
        dict: {
            'result'     : 'ไฟฟ้า (EV)' | 'ไฮบริด' | 'สันดาป (ICE)',
            'scores'     : {'EV': int, 'Hybrid': int, 'ICE': int},
            'confidence' : float (0.0–1.0),
            'model_used' : str  เช่น 'ANN (mock)'
        }

    Example:
        >>> predict_fuel({
        ...     'usage_type': 'city', 'frequency': 'everyday',
        ...     'distance': '10-30', 'prev_car': 'ice',
        ...     'tech_env_concern': '4', 'resale_maintenance_concern': '3',
        ...     'priority': ['fuel_cost', 'technology', 'design']
        ... })
        {'result': 'ไฟฟ้า (EV)', 'scores': {'EV': 88, 'Hybrid': 61, 'ICE': 42},
         'confidence': 0.88, 'model_used': 'ANN (mock)'}
    """
    if config.USE_MOCK:
        return _mock_predict_fuel(input_data)
    return _real_predict_fuel(input_data)
