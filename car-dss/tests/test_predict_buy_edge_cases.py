"""
QA Edge-case tests for predict_buy (Task Board: 🔴 High Priority)

ครอบคลุม 3 หมวด:
  1. input ว่าง      — empty values / missing keys
  2. ค่าติดลบ         — negative numeric values
  3. ค่าเกินช่วง       — out-of-range / invalid select values

รันด้วย:
    cd car-dss
    python -m unittest tests.test_predict_buy_edge_cases -v
"""

import os
import sys
import unittest
from urllib.parse import urlsplit

# เพิ่ม car-dss/ เข้า sys.path เพื่อ import โมดูล
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from models.predictor import predict_buy  # noqa: E402
import app as flask_app_module  # noqa: E402


# 27 ก.ย. 2569: ฟอร์มถามเฉพาะ 3 ช่องที่ buy_model.pkl ชุดข้อมูล n=514 ใช้จริง
# (purpose เลือกได้หลายข้อ) ช่องอื่นของแบบสอบถามยังส่งมาได้ (validators ตรวจแบบไม่บังคับ)
VALID_INPUT = {
    # 29 ก.ย. 2569: buy_model.pkl จากชุดเดิม n=500 ใช้ 10 ช่องนี้ (concern ว่างได้)
    'age': '27-30', 'children': '0', 'education': 'bachelor', 'occupation': 'private',
    'family_size': '1-2', 'housing_type': 'condo', 'parking': 'private',
    'budget': '500001-800000', 'purpose': ['commute', 'travel'], 'concern': ['maintenance'],
}

VALID_INPUT_WITH_UNUSED_FIELDS = dict(VALID_INPUT, **{
    'gender': 'male', 'housing_status': 'rent', 'income': '25001-35000',
})


# ============================================================
# GROUP 1 — Direct predictor tests (unit level)
# ============================================================
class PredictBuyUnitTests(unittest.TestCase):
    """ทดสอบ predict_buy() โดยตรง — ไม่ผ่าน Flask"""

    # --- 1.1 input ว่าง ---
    def test_empty_dict_returns_valid_shape(self):
        result = predict_buy({})
        self._assert_shape(result)

    def test_all_fields_empty_string(self):
        empty = {k: '' for k in VALID_INPUT}
        result = predict_buy(empty)
        self._assert_shape(result)

    def test_missing_required_keys(self):
        partial = {'gender': 'male'}
        result = predict_buy(partial)
        self._assert_shape(result)

    def test_none_values(self):
        none_input = {k: None for k in VALID_INPUT}
        result = predict_buy(none_input)
        self._assert_shape(result)

    # --- 1.2 ค่าติดลบ ---
    def test_negative_numeric_strings(self):
        neg = dict(VALID_INPUT)
        neg['children'] = '-1'
        neg['income'] = '-50000'
        neg['budget'] = '-1000000'
        result = predict_buy(neg)
        self._assert_shape(result)

    def test_negative_as_int(self):
        neg = dict(VALID_INPUT)
        neg['children'] = -3
        result = predict_buy(neg)
        self._assert_shape(result)

    # --- 1.3 ค่าเกินช่วง / ค่าไม่อยู่ใน whitelist ---
    def test_out_of_whitelist_values(self):
        bad = dict(VALID_INPUT)
        bad['gender'] = 'alien'
        bad['age'] = '999'
        bad['education'] = 'postdoc_unknown'
        bad['budget'] = '999999999999'
        result = predict_buy(bad)
        self._assert_shape(result)

    def test_sql_injection_like_strings(self):
        bad = dict(VALID_INPUT)
        bad['gender'] = "'; DROP TABLE users; --"
        bad['occupation'] = '<script>alert(1)</script>'
        result = predict_buy(bad)
        self._assert_shape(result)

    def test_extremely_long_string(self):
        bad = dict(VALID_INPUT)
        bad['occupation'] = 'x' * 100_000
        result = predict_buy(bad)
        self._assert_shape(result)

    # --- helpers ---
    def _assert_shape(self, result):
        self.assertIsInstance(result, dict)
        self.assertIn('result', result)
        self.assertIn('confidence', result)
        self.assertIn('model_used', result)
        self.assertIn(result['result'], ('ซื้อ', 'ไม่ซื้อ'))
        self.assertIsInstance(result['confidence'], float)
        self.assertGreaterEqual(result['confidence'], 0.0)
        self.assertLessEqual(result['confidence'], 1.0)


# ============================================================
# GROUP 2 — Flask endpoint tests (integration level)
# ============================================================
class ApiPredictBuyTests(unittest.TestCase):
    """ทดสอบ POST /api/predict/buy ผ่าน Flask test client"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()
        # จำลอง login session
        with self.client.session_transaction() as sess:
            sess['user_uid'] = 'test_user_uid'
            sess['username'] = 'tester'

    # --- 2.1 input ว่าง ---
    def test_all_fields_empty_redirects_with_flash(self):
        resp = self.client.post('/api/predict/buy', data={}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    def test_partial_fields_rejected(self):
        partial = {'gender': 'male', 'age': '27-30'}
        resp = self.client.post('/api/predict/buy', data=partial, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    def test_whitespace_only_fields_rejected(self):
        data = {k: '   ' for k in VALID_INPUT}
        resp = self.client.post('/api/predict/buy', data=data, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    # --- 2.2 ค่าติดลบ ---
    def test_negative_values_rejected(self):
        # 27 ก.ย. 2569: children/income เลิกถามแล้ว (แอปไม่อ่านค่า) -> ทดสอบกับช่องที่ยังใช้
        bad = dict(VALID_INPUT)
        bad['family_size'] = '-1'
        resp = self.client.post('/api/predict/buy', data=bad, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    # --- 2.3 ค่าเกินช่วง / ค่าไม่อยู่ใน select whitelist ---
    def test_out_of_whitelist_rejected(self):
        bad = dict(VALID_INPUT)
        bad['gender'] = 'alien'
        bad['budget'] = '999999999999'
        bad['education'] = 'postdoc_unknown'
        resp = self.client.post('/api/predict/buy', data=bad, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    def test_only_used_fields_is_enough(self):
        """กรอกแค่ช่องที่โมเดลใช้ก็ต้องผ่านไปหน้าผลได้ (29 ก.ย. 2569: 10 ช่องของโมเดลชุดเดิม n=500)"""
        resp = self.client.post('/api/predict/buy', data=VALID_INPUT, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/result/buy', resp.headers.get('Location', ''))

    def test_unused_fields_still_validated_if_sent(self):
        """ช่องที่เลิกถามแล้ว ถ้ายังถูกส่งมาต้องเป็นค่าที่ถูกต้อง (กัน XSS/ค่ามั่วเข้า Firebase)"""
        from validators import validate_buy
        self.assertEqual(validate_buy(dict(VALID_INPUT_WITH_UNUSED_FIELDS)), (True, None))
        bad = dict(VALID_INPUT_WITH_UNUSED_FIELDS, gender='<script>alert(1)</script>')
        self.assertFalse(validate_buy(bad)[0])

    def test_concern_optional_but_whitelisted(self):
        """29 ก.ย. 2569: concern ข้ามได้ (คนไม่มีรถไม่ได้ตอบในแบบสอบถาม) แต่ถ้าตอบต้องอยู่ใน whitelist"""
        from validators import validate_buy
        self.assertEqual(validate_buy(dict(VALID_INPUT, concern=[])), (True, None))
        self.assertFalse(validate_buy(dict(VALID_INPUT, concern=['<script>']))[0])

    def test_budget_required(self):
        """29 ก.ย. 2569: โมเดลใช้งบประมาณ — ต้องตอบ"""
        from validators import validate_buy
        self.assertFalse(validate_buy(dict(VALID_INPUT, budget=''))[0])

    def test_purpose_must_pick_at_least_one_valid(self):
        """27 ก.ย. 2569: purpose เป็น checkbox — ต้องเลือกอย่างน้อย 1 และทุกค่าต้องอยู่ใน whitelist"""
        from validators import validate_buy
        self.assertFalse(validate_buy(dict(VALID_INPUT, purpose=[]))[0])
        self.assertFalse(validate_buy(dict(VALID_INPUT, purpose=['commute', '<x>']))[0])

    def test_xss_payload_rejected(self):
        # 27 ก.ย. 2569: occupation เลิกถามแล้ว -> ทดสอบ XSS กับช่องที่ยังใช้ (select + checkbox)
        bad = dict(VALID_INPUT)
        bad['education'] = '<script>alert(1)</script>'
        bad['purpose'] = ['<script>alert(1)</script>']
        resp = self.client.post('/api/predict/buy', data=bad, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    # --- 2.4 ต้องล็อกอินก่อน (25 ก.ย. 2569: อาจารย์เคาะให้กลับมาบังคับล็อกอิน) ---
    # เดิม (23 ก.ย.) เทสต์สองตัวนี้ยืนยันว่า guest เข้าได้และได้ uid `guest_...`
    # ตอนนี้พฤติกรรมกลับด้าน: ไม่ล็อกอิน = เด้งไป /login และต้องไม่มี guest uid ถูกสร้าง
    def test_not_logged_in_redirected_to_login(self):
        """ไม่ล็อกอิน -> ทั้งหน้าฟอร์มและ API ต้องเด้งไป /login"""
        client = flask_app_module.app.test_client()  # ไม่ set session
        resp = client.get('/predict/buy', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(urlsplit(resp.headers.get('Location', '')).path, '/login')

        resp = client.post('/api/predict/buy', data=VALID_INPUT, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(urlsplit(resp.headers.get('Location', '')).path, '/login')

    def test_no_guest_uid_created_and_no_admin_rights(self):
        """ไม่ล็อกอินแล้วยิง API -> session ต้องไม่มี uid ใด ๆ (ไม่ออก guest uid ให้อีก)"""
        client = flask_app_module.app.test_client()
        client.post('/api/predict/buy', data=VALID_INPUT, follow_redirects=False)
        with client.session_transaction() as sess:
            self.assertNotIn('user_uid', sess)
            self.assertFalse(sess.get('is_guest'))
            self.assertFalse(sess.get('is_admin'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
