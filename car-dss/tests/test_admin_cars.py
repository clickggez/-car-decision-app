"""
TC-11 ผู้ดูแลระบบจัดการรายการรถ (เพิ่ม แก้ไข ลบ) — เพิ่ม 11 ต.ค. 2569

ที่มา: ผลตรวจเล่มรอบ 2 พบว่ากรณีทดสอบ 10 กรณีในตารางที่ 3.5 ไม่มีฟังก์ชันผู้ดูแลระบบ (หัวข้อ 3.4.1 ข้อ 5)
ผู้ใช้เลือกให้เพิ่มกรณีทดสอบนี้

ใช้สำเนา cars.json ในโฟลเดอร์ชั่วคราวเสมอ — ไม่แตะไฟล์รถจริงของระบบ

รันด้วย:
    cd car-dss
    python -m pytest tests/test_admin_cars.py -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module  # noqa: E402
import config  # noqa: E402

NEW_CAR = {
    'fuel_type': 'EV', 'brand': 'ทดสอบ', 'model': 'TC11 Model', 'price': '999,000 บาท',
    'range_km': '400', 'monthly_cost': '1,000 บาท', 'best_for': 'ทดสอบ',
    'insurance_class1': '20,000 บาท', 'highlights': 'จุดเด่น 1\nจุดเด่น 2',
}


def admin_client():
    client = flask_app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['is_admin'] = True
    return client


class AdminCarsTests(unittest.TestCase):

    def setUp(self):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, 'cars.json')
        shutil.copy(config.CARS_JSON_PATH, self.path)
        with open(config.CARS_JSON_PATH, encoding='utf-8') as f:
            self.real_before = f.read()
        self.patch = mock.patch.object(config, 'CARS_JSON_PATH', self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        with open(config.CARS_JSON_PATH, encoding='utf-8') as f:
            self.assertEqual(f.read(), self.real_before, 'ไฟล์รถจริงต้องไม่ถูกแก้')

    def cars(self):
        with open(self.path, encoding='utf-8') as f:
            return json.load(f)

    def test_admin_can_add_edit_delete_car(self):
        c = admin_client()
        n0 = len(self.cars()['EV'])

        r = c.post('/admin/cars/add', data=NEW_CAR)
        self.assertEqual(r.status_code, 302)
        ev = self.cars()['EV']
        self.assertEqual(len(ev), n0 + 1)
        self.assertEqual(ev[-1]['model'], 'TC11 Model')
        self.assertEqual(ev[-1]['highlights'], ['จุดเด่น 1', 'จุดเด่น 2'])
        self.assertIn('TC11 Model', c.get('/admin/cars').get_data(as_text=True))

        idx = len(ev) - 1
        r = c.post(f'/admin/cars/edit/EV/{idx}', data=dict(NEW_CAR, price='888,000 บาท'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.cars()['EV'][idx]['price'], '888,000 บาท')

        r = c.post(f'/admin/cars/delete/EV/{idx}')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(self.cars()['EV']), n0)
        self.assertNotIn('TC11 Model', json.dumps(self.cars(), ensure_ascii=False))

    def test_normal_user_cannot_change_cars(self):
        c = flask_app_module.app.test_client()
        with c.session_transaction() as sess:
            sess['user_uid'] = 'local_tester'
            sess['username'] = 'tester'
        before = self.cars()
        r = c.post('/admin/cars/add', data=NEW_CAR)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers['Location'].endswith('/admin/login'))
        self.assertEqual(self.cars(), before)


if __name__ == '__main__':
    unittest.main()
