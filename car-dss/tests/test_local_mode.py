"""
QA Tests: Local Mode (JSON) ทำงานแทน Firebase ได้จริง
simulate Firebase down โดย patch app.db = None และ app.firebase_auth_available = False

Scenarios:
  1. save_prediction_to_firebase คืน None โดยไม่ crash เมื่อ db=None
  2. /api/dashboard คืนภาพรวมข้อมูลงานวิจัย (สาธารณะ) ไม่ใช่ผลส่วนตัว ไม่มีตัวเลขฝังตายตัว
  3. Login ด้วย local users (USE_MOCK_AUTH=True) ทำงานได้
  4. Full flow: login → predict_buy → predict_fuel ด้วยบัญชีจริง บันทึกด้วย uid ของบัญชีนั้น

แก้ 25 ก.ย. 2569: ตัด get_dashboard_data_from_firebase ออกจาก app.py แล้ว
(dashboard เป็นหน้าสาธารณะ ไม่ดึงผลรายคนอีก) จึงตัดเทสต์ของ helper ตัวนั้นด้วย

รันด้วย:
    cd car-dss
    python -m unittest tests.test_local_mode -v
"""

import os
import sys
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module
import config

# 27 ก.ย. 2569: ฟอร์มถามเฉพาะช่องที่โมเดลชุดข้อมูล n=514 ใช้จริง
# ไม่มีคำถาม TPB / กลุ่ม EV / NEP · purpose / prev_car / priority เลือกได้หลายข้อ
VALID_BUY = {
    'age': '27-30', 'children': '0', 'education': 'bachelor', 'occupation': 'private',
    'family_size': '3-4', 'housing_type': 'house', 'parking': 'private',
    'budget': '800001-1200000', 'purpose': ['commute', 'travel'], 'concern': [],
}

VALID_FUEL = {
    'usage_type': 'city', 'frequency': 'everyday', 'distance': '31-50',
    'prev_car': ['ice'], 'priority': ['price', 'fuel_cost'],
    'tech_env_concern': '4',
}


class LocalModeHelperTests(unittest.TestCase):
    """ทดสอบ helper functions โดยตรงเมื่อ db=None"""

    def test_save_prediction_returns_none_when_no_db(self):
        with patch.object(flask_app_module, 'db', None):
            result = flask_app_module.save_prediction_to_firebase(
                'uid_test', 'buy', VALID_BUY, {'result': 'ซื้อ', 'confidence': 0.9, 'model_used': 'mock'}
            )
        self.assertIsNone(result)


class LocalModeDashboardTests(unittest.TestCase):
    """/api/dashboard = ภาพรวมข้อมูลงานวิจัย (สาธารณะ) ตั้งแต่ 25 ก.ย. 2569

    เดิมคืนผลส่วนตัวจาก Firebase/session + cost_comparison ที่เป็นตัวเลขฝังตายตัว
    ตอนนี้ต้องคืนข้อมูลชุดเดียวกันให้ทุกคน และตัวเลขต้องมาจาก dataset_overview.json เท่านั้น
    """

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'
        with open(config.DATASET_OVERVIEW_PATH, encoding='utf-8') as f:
            cls.overview = json.load(f)

    def test_dashboard_api_public_and_from_overview_file(self):
        resp = flask_app_module.app.test_client().get('/api/dashboard')  # ไม่ล็อกอิน
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['source'], 'dataset_overview')
        self.assertEqual(data['overview'], self.overview)

    def test_dashboard_api_has_no_personal_or_hardcoded_fields(self):
        """ผลส่วนตัวใน session ต้องไม่รั่วออกมา และ cost_comparison (800/2200/3800) ต้องหายไป"""
        client = flask_app_module.app.test_client()
        with client.session_transaction() as sess:
            sess['user_uid'] = 'local_tester'
            sess['fuel_prediction'] = {'result': 'สันดาป (ICE)', 'scores': {'EV': 21, 'Hybrid': 35, 'ICE': 44},
                                       'confidence': 0.44, 'model_used': 'BAGGING'}
        data = json.loads(client.get('/api/dashboard').data)
        for key in ('cost_comparison', 'fuel_result', 'fuel_scores', 'buy_result', 'has_result'):
            self.assertNotIn(key, data)
        self.assertNotIn('สันดาป (ICE)', json.dumps(data, ensure_ascii=False))

    def test_dashboard_api_same_for_everyone(self):
        anon = json.loads(flask_app_module.app.test_client().get('/api/dashboard').data)
        client = flask_app_module.app.test_client()
        with client.session_transaction() as sess:
            sess['user_uid'] = 'local_tester'
            sess['username'] = 'tester'
        logged_in = json.loads(client.get('/api/dashboard').data)
        self.assertEqual(anon, logged_in)

    def test_cars_summary_counts_match_cars_json(self):
        """จำนวนรุ่นรถต้องนับสดจาก cars.json (อ่านอย่างเดียว)"""
        cars = flask_app_module.load_cars()
        data = json.loads(flask_app_module.app.test_client().get('/api/dashboard').data)
        got = {row['fuel']: row['count'] for row in data['cars']}
        self.assertEqual(got, {k: len(cars.get(k, [])) for k in ('EV', 'Hybrid', 'ICE')})

    def test_missing_overview_file_gives_unavailable_not_numbers(self):
        """ไม่มีไฟล์สรุป = บอกว่าไม่มีข้อมูล ห้ามเติมตัวเลขแทน"""
        missing = os.path.join(BASE_DIR, 'data', '__missing__.json')
        with patch.object(config, 'DATASET_OVERVIEW_PATH', missing):
            client = flask_app_module.app.test_client()
            data = json.loads(client.get('/api/dashboard').data)
            html = client.get('/dashboard').get_data(as_text=True)
        self.assertEqual(data['source'], 'unavailable')
        self.assertIsNone(data['overview'])
        self.assertIn('ยังไม่มีข้อมูลสรุป', html)
        self.assertNotIn('statRespondents', html)


class LocalModeAuthTests(unittest.TestCase):
    """ทดสอบ login ด้วย local users (USE_MOCK_AUTH=True)"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()

    def _with_test_user(self, username='test_local_user', password='testpass123'):
        """สร้าง local user ชั่วคราวสำหรับทดสอบ แล้วลบออกเมื่อเสร็จ"""
        from contextlib import contextmanager
        @contextmanager
        def ctx():
            users = flask_app_module.load_local_users()
            users[username] = {'password': password, 'created_at': '2026-01-01T00:00:00Z'}
            flask_app_module.save_local_users(users)
            try:
                yield
            finally:
                users = flask_app_module.load_local_users()
                users.pop(username, None)
                flask_app_module.save_local_users(users)
        return ctx()

    def test_local_login_success(self):
        with self._with_test_user(), patch.object(config, 'USE_MOCK_AUTH', True):
            resp = self.client.post('/login',
                data={'username': 'test_local_user', 'password': 'testpass123'},
                follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/predict/buy', resp.headers.get('Location', ''))

    def test_local_login_wrong_password(self):
        with self._with_test_user(), patch.object(config, 'USE_MOCK_AUTH', True):
            resp = self.client.post('/login',
                data={'username': 'test_local_user', 'password': 'wrongpass'},
                follow_redirects=False)
        self.assertEqual(resp.status_code, 200)

    def test_local_login_unknown_user(self):
        with patch.object(config, 'USE_MOCK_AUTH', True):
            resp = self.client.post('/login',
                data={'username': 'ghost_user_xyz', 'password': 'any'},
                follow_redirects=False)
        self.assertEqual(resp.status_code, 200)


class LocalModeFullFlowTests(unittest.TestCase):
    """full flow ด้วยบัญชีจริงในโหมด local: login → buy → fuel (db=None ไม่แตะ Firebase จริง)

    25 ก.ย. 2569: การพยากรณ์ต้องล็อกอิน และผลต้องบันทึกด้วย uid ของบัญชีนั้น ไม่ใช่ guest
    """

    USERNAME = 'test_flow_user'
    PASSWORD = 'testpass123'

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        users = flask_app_module.load_local_users()
        users[self.USERNAME] = {'password': self.PASSWORD, 'created_at': '2026-01-01T00:00:00Z'}
        flask_app_module.save_local_users(users)
        self.client = flask_app_module.app.test_client()

    def tearDown(self):
        users = flask_app_module.load_local_users()
        users.pop(self.USERNAME, None)
        flask_app_module.save_local_users(users)

    def _login(self):
        with patch.object(config, 'USE_MOCK_AUTH', True):
            resp = self.client.post('/login', data={'username': self.USERNAME, 'password': self.PASSWORD})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(urlsplit(resp.headers['Location']).path, '/predict/buy')

    def test_logged_in_user_completes_buy_then_fuel_with_real_uid(self):
        saved = []

        def fake_save(uid, pred_type, input_data, result):
            saved.append((uid, pred_type))
            return None

        with patch.object(flask_app_module, 'db', None), \
                patch.object(flask_app_module, 'save_prediction_to_firebase', side_effect=fake_save):
            self._login()
            self.assertEqual(self.client.get('/predict/buy').status_code, 200)

            resp = self.client.post('/api/predict/buy', data=VALID_BUY)
            self.assertEqual(urlsplit(resp.headers['Location']).path, '/result/buy')
            self.assertEqual(self.client.get('/result/buy').status_code, 200)

            # โมเดลอาจทาย "ไม่ซื้อ" ได้ — บังคับผ่านด่าน buy_result_required เพื่อทดสอบขั้น fuel ต่อ
            with self.client.session_transaction() as sess:
                sess['buy_result'] = 'ซื้อ'
            self.assertEqual(self.client.get('/predict/fuel').status_code, 200)

            resp = self.client.post('/api/predict/fuel', data=VALID_FUEL)
            self.assertEqual(urlsplit(resp.headers['Location']).path, '/result/fuel')
            self.assertEqual(self.client.get('/result/fuel').status_code, 200)
            self.assertEqual(self.client.get('/recommend').status_code, 200)

        expected_uid = f'local_{self.USERNAME}'
        self.assertEqual(saved, [(expected_uid, 'buy'), (expected_uid, 'fuel')])
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['user_uid'], expected_uid)
            self.assertFalse(sess.get('is_guest'))

    def test_predict_buy_works_without_firebase(self):
        with self.client.session_transaction() as sess:
            sess['user_uid'] = 'local_test'
            sess['username'] = 'tester'
        with patch.object(flask_app_module, 'db', None):
            resp = self.client.post('/api/predict/buy', data=VALID_BUY, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(urlsplit(resp.headers['Location']).path, '/result/buy')


if __name__ == '__main__':
    unittest.main(verbosity=2)
