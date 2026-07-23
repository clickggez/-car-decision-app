"""
QA Tests: Local Mode (JSON) ทำงานแทน Firebase ได้จริง
simulate Firebase down โดย patch app.db = None และ app.firebase_auth_available = False

Scenarios:
  1. save_prediction_to_firebase คืน None โดยไม่ crash เมื่อ db=None
  2. get_dashboard_data_from_firebase คืน None โดยไม่ crash เมื่อ db=None
  3. /api/dashboard fallback ไป mock data เมื่อ Firebase ไม่ตอบ
  4. Login ด้วย local users (USE_MOCK_AUTH=True) ทำงานได้
  5. Full flow: predict_buy → predict_fuel → dashboard ไม่ crash เมื่อ db=None

รันด้วย:
    cd car-dss
    python -m unittest tests.test_local_mode -v
"""

import os
import sys
import json
import unittest
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module
import config

VALID_BUY = {
    'gender': 'male', 'age': '27-30', 'children': '0',
    'education': 'bachelor', 'occupation': 'private', 'family_size': '1-2',
    'housing_type': 'condo', 'housing_status': 'rent', 'parking': 'private',
    'income': '25001-35000', 'budget': '500001-800000',
    'concern': 'fuel_price', 'purpose': 'commute',
}

VALID_FUEL = {
    'usage_type': 'city', 'frequency': 'everyday', 'distance': '31-50',
    'prev_car': 'ice', 'priority': ['price', 'fuel_cost'],
    'tech_env_concern': '4', 'resale_maintenance_concern': '3',
}


class LocalModeHelperTests(unittest.TestCase):
    """ทดสอบ helper functions โดยตรงเมื่อ db=None"""

    def test_save_prediction_returns_none_when_no_db(self):
        with patch.object(flask_app_module, 'db', None):
            result = flask_app_module.save_prediction_to_firebase(
                'uid_test', 'buy', VALID_BUY, {'result': 'ซื้อ', 'confidence': 0.9, 'model_used': 'mock'}
            )
        self.assertIsNone(result)

    def test_get_dashboard_returns_none_when_no_db(self):
        with patch.object(flask_app_module, 'db', None):
            result = flask_app_module.get_dashboard_data_from_firebase('uid_test')
        self.assertIsNone(result)


class LocalModeDashboardTests(unittest.TestCase):
    """ทดสอบ /api/dashboard fallback เมื่อ Firebase ไม่มีข้อมูล"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_uid'] = 'test_uid'
            sess['username'] = 'tester'

    def test_dashboard_api_returns_mock_when_firebase_down(self):
        resp = self.client.get('/api/dashboard')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('source', data)
        self.assertIn(data['source'], ('firebase', 'mock'))

    def test_dashboard_api_returns_mock_source_when_no_db(self):
        with patch.object(flask_app_module, 'db', None):
            resp = self.client.get('/api/dashboard')
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertEqual(data['source'], 'mock')

    def test_dashboard_mock_has_required_keys(self):
        with patch.object(flask_app_module, 'db', None):
            resp = self.client.get('/api/dashboard')
            data = json.loads(resp.data)
            for key in ('buy_result', 'buy_confidence', 'fuel_result',
                        'fuel_scores', 'cost_comparison', 'behavior_scores'):
                self.assertIn(key, data)


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
    """ทดสอบ full flow predict_buy → predict_fuel → dashboard เมื่อ db=None"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_uid'] = 'local_test'
            sess['username'] = 'tester'

    def test_predict_buy_works_without_firebase(self):
        with patch.object(flask_app_module, 'db', None):
            resp = self.client.post('/api/predict/buy',
                data=VALID_BUY, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/result/buy', resp.headers.get('Location', ''))

    def test_predict_fuel_works_without_firebase(self):
        with patch.object(flask_app_module, 'db', None):
            with self.client.session_transaction() as sess:
                sess['buy_result'] = 'ซื้อ'
            resp = self.client.post('/api/predict/fuel',
                data=VALID_FUEL, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/result/fuel', resp.headers.get('Location', ''))

    def test_result_buy_page_works_without_firebase(self):
        with patch.object(flask_app_module, 'db', None):
            # submit buy form ก่อน
            self.client.post('/api/predict/buy', data=VALID_BUY)
            resp = self.client.get('/result/buy')
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_page_works_without_firebase(self):
        with patch.object(flask_app_module, 'db', None):
            resp = self.client.get('/api/dashboard')
        self.assertEqual(resp.status_code, 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
