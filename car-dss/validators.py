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
}

_FUEL_WHITELISTS = {
    'usage_type':                 {'city', 'highway', 'both'},
    'frequency':                  {'occasional', '1-2days', '3-4days', '5-6days', 'everyday'},
    'distance':                   {'lt10', '10-30', '31-50', '51-70', '71-90', '90+'},
    'prev_car':                   {'ice', 'hybrid', 'ev', 'none'},
    'tech_env_concern':           {'1', '2', '3', '4', '5'},
    'resale_maintenance_concern': {'1', '2', '3', '4', '5'},
}

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
    return True, None


def validate_fuel(input_data):
    """Validate predict_fuel input. Returns (is_valid, error_message)."""
    for field, allowed in _FUEL_WHITELISTS.items():
        val = input_data.get(field, '')
        if not isinstance(val, str) or not val.strip():
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
        if val not in allowed:
            return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    priority = input_data.get('priority', [])
    if not priority:
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'
    if any(p not in _PRIORITY_ALLOWED for p in priority):
        return False, 'กรุณากรอกข้อมูลให้ครบทุกช่อง'

    return True, None
