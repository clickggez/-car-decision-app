"""
QA Edge-case tests for predict_fuel (Task Board: 🔴 High Priority)

ครอบคลุม 3 หมวด:
  1. input ว่าง      — empty values / missing keys / empty priority list
  2. ค่าติดลบ         — negative numeric strings (tech_env_concern, resale_maintenance_concern)
  3. ค่าเกินช่วง       — out-of-range / invalid select values / multiple priority values

รันด้วย:
    cd car-dss
    python -m unittest tests.test_predict_fuel_edge_cases -v
"""

import os
import sys
import unittest

# เพิ่ม car-dss/ เข้า sys.path เพื่อ import โมดูล
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from models.predictor import predict_fuel  # noqa: E402
import app as flask_app_module  # noqa: E402


VALID_INPUT_FUEL = {
    'usage_type': 'city',
    'frequency': 'everyday',
    'distance': '31-50',
    'prev_car': 'ice',
    'priority': ['price', 'fuel_cost', 'performance'],
    'tech_env_concern': '5',
    'resale_maintenance_concern': '3',
}


# ============================================================
# GROUP 1 — Direct predictor tests (unit level)
# ============================================================
class PredictFuelUnitTests(unittest.TestCase):
    """ทดสอบ predict_fuel() โดยตรง — ไม่ผ่าน Flask"""

    def test_empty_dict_returns_valid_shape(self):
        result = predict_fuel({})
        self._assert_shape(result)

    def test_all_fields_empty_string(self):
        empty = {k: '' for k in VALID_INPUT_FUEL}
        result = predict_fuel(empty)
        self._assert_shape(result)

    def test_empty_priority_list(self):
        data = dict(VALID_INPUT_FUEL)
        data['priority'] = []
        result = predict_fuel(data)
        self._assert_shape(result)

    def test_negative_numeric_strings(self):
        neg = dict(VALID_INPUT_FUEL)
        neg['tech_env_concern'] = '-1'
        neg['resale_maintenance_concern'] = '-5'
        result = predict_fuel(neg)
        self._assert_shape(result)

    def test_out_of_whitelist_values(self):
        bad = dict(VALID_INPUT_FUEL)
        bad['usage_type'] = 'space_travel'
        bad['tech_env_concern'] = '999'
        bad['priority'] = ['unknown_factor', 'price']
        result = predict_fuel(bad)
        self._assert_shape(result)

    # --- helpers ---
    def _assert_shape(self, result):
        self.assertIsInstance(result, dict)
        self.assertIn('result', result)
        self.assertIn('scores', result)
        self.assertIn('confidence', result)
        self.assertIn('model_used', result)
        self.assertIn(result['result'], ('ไฟฟ้า (EV)', 'ไฮบริด', 'สันดาป (ICE)'))
        self.assertIsInstance(result['scores'], dict)
        self.assertIn('EV', result['scores'])
        self.assertIn('Hybrid', result['scores'])
        self.assertIn('ICE', result['scores'])
        self.assertIsInstance(result['confidence'], float)


# ============================================================
# GROUP 2 — Flask endpoint tests (integration level)
# ============================================================
class ApiPredictFuelTests(unittest.TestCase):
    """ทดสอบ POST /api/predict/fuel ผ่าน Flask test client"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()
        # จำลอง login session + buy_result='ซื้อ' (ผ่าน buy_result_required decorator)
        with self.client.session_transaction() as sess:
            sess['user_uid'] = 'test_user_uid'
            sess['username'] = 'tester'
            sess['buy_result'] = 'ซื้อ'

    # --- 2.1 input ว่าง ---
    def test_all_fields_empty_redirects_with_flash(self):
        resp = self.client.post('/api/predict/fuel', data={}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/fuel', resp.headers.get('Location', ''))

    def test_missing_priority_rejected(self):
        data = dict(VALID_INPUT_FUEL)
        del data['priority']
        resp = self.client.post('/api/predict/fuel', data=data, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/fuel', resp.headers.get('Location', ''))

    def test_empty_priority_list_rejected(self):
        # multipart/form-data encoding ของ list ว่าง คือไม่ส่ง field เลย
        # หรือส่ง key แต่ไม่มี value
        resp = self.client.post('/api/predict/fuel', data={'priority': []}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

    def test_whitespace_only_selects_rejected(self):
        data = dict(VALID_INPUT_FUEL)
        data['usage_type'] = '   '
        resp = self.client.post('/api/predict/fuel', data=data, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/fuel', resp.headers.get('Location', ''))

    # --- 2.2 ค่าติดลบ ---
    def test_negative_concerns_rejected(self):
        bad = dict(VALID_INPUT_FUEL)
        bad['tech_env_concern'] = '-5'
        resp = self.client.post('/api/predict/fuel', data=bad, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/fuel', resp.headers.get('Location', ''))

    # --- 2.3 ค่าเกินช่วง ---
    def test_out_of_whitelist_rejected(self):
        bad = dict(VALID_INPUT_FUEL)
        bad['usage_type'] = 'underwater'
        bad['tech_env_concern'] = '99'
        resp = self.client.post('/api/predict/fuel', data=bad, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/fuel', resp.headers.get('Location', ''))

    # --- 2.4 Security Decorators ---
    def test_unauthenticated_blocked(self):
        client = flask_app_module.app.test_client()
        resp = client.post('/api/predict/fuel', data=VALID_INPUT_FUEL, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers.get('Location', ''))

    def test_buy_result_not_buy_blocked(self):
        with self.client.session_transaction() as sess:
            sess['buy_result'] = 'ไม่ซื้อ'
        resp = self.client.post('/api/predict/fuel', data=VALID_INPUT_FUEL, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))


if __name__ == '__main__':
    unittest.main(verbosity=2)
