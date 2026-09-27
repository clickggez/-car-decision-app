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

def _force_single_thread(obj, _depth=0):
    """
    บังคับ n_jobs=1 ทุกชั้นของโมเดลที่โหลดมา (2026-08-09)

    ทำไมต้องทำ: โมเดล BAGGING x25 ห่อ RandomForest 400 ต้น = ~10,000 ต้นไม้
    ถ้าปล่อย n_jobs=-1 ไว้ sklearn จะแตกงานไป 20 คอร์ "ต่อการทำนาย 1 แถว"
    ซึ่ง overhead ของการกระจายงานมากกว่างานจริงหลายเท่า

    วัดจริงบนเครื่องนี้: n_jobs=-1 -> 2156 ms | n_jobs=1 -> 831 ms (เร็วขึ้น 2.6 เท่า)
    และ **predict_proba ออกมาเท่ากันทุกทศนิยม** (ตรวจแล้ว) เพราะ n_jobs
    มีผลแค่การกระจายงาน ไม่ได้เปลี่ยนวิธีคำนวณ

    เว็บทำนายทีละ 1 คน การขนานจึงมีแต่เสีย — ถ้าอนาคตต้องทำนายเป็น batch
    ค่อยพิจารณาเปิดกลับ
    """
    if _depth > 6 or obj is None:
        return
    if hasattr(obj, "n_jobs"):
        try:
            obj.n_jobs = 1
        except (AttributeError, ValueError):
            pass
    for attr in ("named_steps", "estimators_", "estimators", "steps",
                 "final_estimator_", "base_estimator_", "estimator"):
        sub = getattr(obj, attr, None)
        if sub is None:
            continue
        if isinstance(sub, dict):
            for v in sub.values():
                _force_single_thread(v, _depth + 1)
        elif isinstance(sub, (list, tuple)):
            for v in sub:
                _force_single_thread(v[1] if isinstance(v, tuple) and len(v) == 2 else v,
                                     _depth + 1)
        else:
            _force_single_thread(sub, _depth + 1)


# จะ import เมื่อ USE_MOCK = False เท่านั้น
if not config.USE_MOCK:
    try:
        import joblib
        _buy_bundle = joblib.load(config.BUY_MODEL_PATH)
        _fuel_bundle = joblib.load(config.FUEL_MODEL_PATH)
        _force_single_thread(_buy_bundle.get("pipeline"))
        _force_single_thread(_fuel_bundle.get("pipeline"))
    except FileNotFoundError:
        print("[WARNING] Model files not found, falling back to mock predictions")
        config.USE_MOCK = True


def _check_bundle(bundle, expected_cols, name):
    """กันโมเดลกับโค้ดคนละรุ่นกัน (2026-09-26)

    .pkl ที่เทรนจากข้อมูลชุดเดิม (มีคอลัมน์ TPB / กลุ่ม EV / NEP) ใช้กับ feature_encoding
    ปัจจุบันไม่ได้ — ถ้าปล่อยผ่าน pandas จะเติม NaN ให้คอลัมน์ที่หายไปเงียบ ๆ แล้วโมเดล
    ทำนายเพี้ยนโดยไม่มีใครรู้ จึงหยุดพร้อมข้อความชัดเจนแทน
    """
    got = list(bundle.get("feature_cols", []))
    if got != list(expected_cols):
        missing = [c for c in got if c not in expected_cols]
        extra = [c for c in expected_cols if c not in got]
        raise RuntimeError(
            f"{name}: โมเดลกับโค้ดไม่ตรงรุ่นกัน — .pkl ต้องการคอลัมน์ที่โค้ดไม่สร้างแล้ว {missing}"
            f" / โค้ดสร้างคอลัมน์ที่ .pkl ไม่รู้จัก {extra} -> ต้องใช้ .pkl ที่เทรนจากข้อมูลชุด 2026-09-26")


if not config.USE_MOCK:
    for _b, _cols, _n in ((_buy_bundle, fe.buy_feature_columns(), "buy_model.pkl"),
                          (_fuel_bundle, fe.fuel_feature_columns(), "fuel_model.pkl")):
        try:
            _check_bundle(_b, _cols, _n)
        except RuntimeError as _e:
            print(f"[WARNING] {_e}")


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

    _check_bundle(_buy_bundle, fe.buy_feature_columns(), "buy_model.pkl")
    feat = fe.buy_features_from_web(input_data)
    X = pd.DataFrame([feat], columns=_buy_bundle["feature_cols"])
    pipe = _buy_bundle["pipeline"]
    # เรียก predict_proba รอบเดียวแล้วหา label จาก argmax แทนการเรียก predict() ซ้ำ
    # (2026-08-09) โมเดล BAGGING x25 หนักมาก การเดินซ้ำสองรอบทำให้ช้าเป็นเท่าตัว
    # ผลลัพธ์เท่ากันเพราะ predict() ของ sklearn คือ classes_[argmax(predict_proba)]
    proba = pipe.predict_proba(X)[0]
    result = pipe.classes_[int(proba.argmax())]
    confidence = round(float(max(proba)), 3)

    return {
        "result": result,
        "confidence": confidence,
        "model_used": f"{_buy_bundle['model_name']} (real)",
    }


def _real_predict_fuel(input_data):
    """โมเดลจริง: ประเภทเชื้อเพลิง — ใช้เมื่อ USE_MOCK = False"""
    import pandas as pd

    _check_bundle(_fuel_bundle, fe.fuel_feature_columns(), "fuel_model.pkl")
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
        input_data (dict): ข้อมูลจากฟอร์ม predict_buy
            27 ก.ย. 2569 (โมเดลชุดข้อมูล n=514) ฟอร์มถาม 3 ช่องที่โมเดลใช้จริง:
            education        : 'below_m3' | 'm3' | 'm6' | 'vocational' | 'bachelor' | 'master' | 'phd'
            family_size      : '1-2' | '3-4' | '5+'
            purpose (list)   : subset ของ {'commute', 'trade', 'travel', 'convenience', 'avoid_public'}
                               (เลือกได้หลายข้อ -> multi-hot · string คั่น ',' ก็รับ)
            ส่ง field อื่นของแบบสอบถามมาด้วยได้ (gender, age, children, occupation, housing_type,
            housing_status, parking, income, budget, concern) — โมเดลชุดนี้ไม่ได้ใช้

    Returns:
        dict: {
            'result'     : 'ซื้อ' | 'ไม่ซื้อ',
            'confidence' : float (0.0–1.0),
            'model_used' : str  เช่น 'SVM (mock)'
        }

    Example:
        >>> predict_buy({
        ...     'education': 'bachelor', 'family_size': '3-4',
        ...     'purpose': ['commute', 'travel'],
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
        input_data (dict): ข้อมูลจากฟอร์ม predict_fuel
            27 ก.ย. 2569 (FUEL เทรนใหม่ 28 ก.ย. บนชุด n=630 — ช่องฟอร์มเท่าเดิม) ฟอร์มถามช่องที่โมเดลใช้จริง:
            usage_type                 : 'city' | 'highway' | 'both'
            frequency                  : 'occasional' | '1-2days' | '3-4days' | '5-6days' | 'everyday'
            distance                   : 'lt10' | '10-30' | '31-50' | '51-70' | '71-90' | '90+'
            prev_car (list)            : subset ของ {'ice', 'hybrid', 'ev'} (เลือกได้หลายข้อ, ว่างได้)
            tech_env_concern           : '1'–'5'  "ประเภทพลังงานของรถยนต์มีความเหมาะสมกับการใช้งาน"
                                         (5 = เห็นด้วยอย่างยิ่ง ตรงกับข้อ 7P ในแบบสอบถาม)
            priority (list)            : subset ของ {'price', 'installment', 'fuel_cost',
                                         'electricity_cost', 'maintenance_cost', 'performance',
                                         'design', 'technology', 'value', 'warranty'}
            resale_maintenance_concern ส่งมาได้ แต่โมเดลชุดนี้ไม่ได้ใช้

    Returns:
        dict: {
            'result'     : 'ไฟฟ้า (EV)' | 'ไฮบริด' | 'สันดาป (ICE)',
            'scores'     : {'EV': int, 'Hybrid': int, 'ICE': int},
            'confidence' : float (0.0–1.0),
            'model_used' : str  เช่น 'ANN (mock)'
        }

    Example:
        >>> predict_fuel({
        ...     'usage_type': 'city', 'frequency': 'everyday', 'distance': '10-30',
        ...     'prev_car': ['ice', 'hybrid'],
        ...     'tech_env_concern': '4', 'resale_maintenance_concern': '3',
        ...     'priority': ['fuel_cost', 'technology', 'design']
        ... })
        {'result': 'ไฟฟ้า (EV)', 'scores': {'EV': 88, 'Hybrid': 61, 'ICE': 42},
         'confidence': 0.88, 'model_used': 'ANN (mock)'}
    """
    if config.USE_MOCK:
        return _mock_predict_fuel(input_data)
    return _real_predict_fuel(input_data)
