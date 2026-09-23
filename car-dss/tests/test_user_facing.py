"""
QA Tests: สิ่งที่ผู้ใช้เห็นจริงบนหน้าเว็บ (ไม่ใช่แค่ route ทำงานถูก)

ที่มา: 23 ก.ย. 2569 — pytest ผ่าน 42/42 แต่ผู้ใช้ยังเจอหน้าล็อกอิน
เพราะเทสต์เดิมเช็คแค่ว่า route ไม่บังคับล็อกอินแล้ว
แต่ **ปุ่มในหน้า HTML ยังลิงก์ไป /login อยู่** (`home.html:33,247`)
เทสต์ชุดนี้จึงเช็คสิ่งที่ผู้ใช้กดจริง ไม่ใช่แค่สิ่งที่เซิร์ฟเวอร์ตอบ

Scenarios:
  1. ผู้ใช้ทั่วไปเข้าทุกหน้าได้โดยไม่ต้องล็อกอิน (ได้ 200 ไม่ใช่เด้งไป login)
  2. ไม่มีปุ่ม/ลิงก์ในหน้าเว็บที่พาผู้ใช้ไปหน้าล็อกอินโดยไม่จำเป็น
  3. หน้าแอดมินยังต้องล็อกอินเหมือนเดิม (ห้ามหลุดไปด้วย)
  4. dashboard ต้องไม่มีตัวเลขจำลองฝังอยู่ในหน้า
  5. ฟอร์มเชื้อเพลิงถามเฉพาะคำถามที่โมเดลใช้จริง
  6. ข้อความที่ผู้ใช้สั่งให้ตัดออก ต้องไม่กลับมาโผล่อีก

รันด้วย:
    cd car-dss
    python -m pytest tests/test_user_facing.py -v
"""

import os
import re
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module  # noqa: E402

TEMPLATES = os.path.join(BASE_DIR, 'templates')

# หน้าที่ผู้ใช้ทั่วไปต้องเข้าได้โดยไม่ต้องล็อกอิน
GUEST_PAGES = ['/', '/predict/buy', '/dashboard']

# หน้าที่ต้องล็อกอินแอดมินเสมอ — ถ้าหลุดคือช่องโหว่
ADMIN_PAGES = ['/admin', '/admin/users', '/admin/explain', '/admin/cars']

# ข้อความที่ผู้ใช้สั่งตัดออกจากหน้าที่ผู้ใช้ทั่วไปเห็น (23 ก.ย. 2569)
BANNED_TEXT = ['Data Mining', 'SVM & ANN', 'Data Mining · SVM · ANN']

# คำถามที่ fuel_model.pkl ไม่ได้ใช้ (ดู analysis/fuel_feature_usage_2026-09-23.txt)
DROPPED_FUEL_FIELDS = [
    'usage_type', 'frequency', 'distance',
    'tech_env_concern', 'resale_maintenance_concern',
    'ev_exposure', 'range_anxiety',
]

# คำถามที่โมเดลใช้จริง — ห้ามหายไปจากฟอร์ม
REQUIRED_FUEL_FIELDS = ['prev_car', 'priority', 'nep_1', 'nep_2', 'nep_3', 'nep_4', 'nep_5']


def read_template(name):
    with open(os.path.join(TEMPLATES, name), encoding='utf-8') as f:
        return f.read()


class GuestAccessTests(unittest.TestCase):
    """ผู้ใช้ทั่วไปต้องใช้ระบบได้โดยไม่ต้องสมัครสมาชิก"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def setUp(self):
        self.client = flask_app_module.app.test_client()  # ไม่ล็อกอิน

    def test_guest_can_open_every_user_page(self):
        for url in GUEST_PAGES:
            with self.subTest(url=url):
                resp = self.client.get(url, follow_redirects=False)
                self.assertEqual(
                    resp.status_code, 200,
                    f'{url} ควรเปิดได้เลยโดยไม่ล็อกอิน แต่ได้ {resp.status_code} '
                    f'-> {resp.headers.get("Location", "")}'
                )

    def test_admin_pages_still_locked(self):
        for url in ADMIN_PAGES:
            with self.subTest(url=url):
                resp = self.client.get(url, follow_redirects=False)
                # 404 ไม่นับว่า "ล็อกอยู่" — แปลว่า route หายไปต่างหาก (codex ค้านไว้ board #31)
                self.assertIn(
                    resp.status_code, (301, 302, 403),
                    f'{url} ต้องเด้งไปหน้าล็อกอินแอดมินหรือ 403 แต่ได้ {resp.status_code}'
                )
                if resp.status_code in (301, 302):
                    self.assertIn('/admin/login', resp.headers.get('Location', ''),
                                  f'{url} เด้งไปที่อื่นที่ไม่ใช่ /admin/login')


class NoDeadEndToLoginTests(unittest.TestCase):
    """ไม่มีปุ่มที่พาผู้ใช้ไปหน้าล็อกอินทั้งที่ระบบเปิดให้ใช้ฟรีแล้ว

    นี่คือบั๊กที่หลุดออกไปจริงเมื่อ 23 ก.ย. 2569 — route เปิดแล้วแต่ปุ่มยังชี้ /login
    """

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def test_home_cta_goes_to_form_not_login(self):
        """ปุ่ม "เริ่มวิเคราะห์" ต้องพาไปแบบประเมิน ไม่ใช่หน้าล็อกอิน

        ไม่นับจำนวนลิงก์เฉย ๆ (codex ค้านไว้ใน board #31 ว่าหลวมเกิน)
        แต่ดูที่ตัวปุ่มจริง: ลิงก์ที่มีข้อความ "เริ่มวิเคราะห์" ต้องไม่ชี้ไป /login
        และลิงก์ไป /login ที่เหลือได้ ต้องเป็นปุ่ม "เข้าสู่ระบบ" บนเมนูเท่านั้น
        """
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)

        # <a ...>...</a> ทุกตัว พร้อมข้อความข้างใน
        anchors = re.findall(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
        self.assertTrue(anchors, 'หน้าแรกไม่มีลิงก์เลย — เทสต์นี้อ่านหน้าผิดหรือเปล่า')

        cta = [href for href, text in anchors if 'เริ่มวิเคราะห์' in text]
        self.assertTrue(cta, 'หาปุ่ม "เริ่มวิเคราะห์" บนหน้าแรกไม่เจอ')
        for href in cta:
            self.assertIn('/predict/buy', href,
                          f'ปุ่มเริ่มวิเคราะห์ชี้ไป {href} ควรชี้ไปหน้าแบบประเมิน')

        for href, text in anchors:
            if href.rstrip('/').endswith('/login'):
                self.assertIn(
                    'เข้าสู่ระบบ', text,
                    f'มีลิงก์ไป /login ที่ไม่ใช่ปุ่มเข้าสู่ระบบ (ข้อความ: {text.strip()[:40]})'
                )

    def test_home_template_has_no_auth_conditional_on_cta(self):
        """กันการกลับไปใช้เงื่อนไข is_authenticated กับปุ่ม CTA อีก"""
        html = read_template('home.html')
        self.assertNotIn(
            "url_for('login')", html,
            'home.html ไม่ควรมีลิงก์ไปหน้าล็อกอินแล้ว (ระบบเปิดให้ guest ใช้)'
        )


class DashboardHasNoFakeNumbersTests(unittest.TestCase):
    """dashboard ต้องไม่โชว์ตัวเลขที่ไม่ใช่ผลของผู้ใช้

    บั๊กเดิม: ฝัง "EV 78% ANN (mock)" ไว้ใน HTML ผู้ใช้จึงเห็นผลของคนอื่น
    """

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def test_no_hardcoded_result_in_template(self):
        html = read_template('dashboard.html')
        for fake in ('78.0%', 'EV: 78', 'mockScores'):
            self.assertNotIn(
                fake, html,
                f'dashboard.html ยังมีค่าจำลอง "{fake}" ฝังอยู่'
            )

    def test_empty_state_when_no_prediction(self):
        html = flask_app_module.app.test_client().get('/dashboard').get_data(as_text=True)
        self.assertIn('ยังไม่มีผลวิเคราะห์', html)
        self.assertNotIn('78.0%', html)

    def test_shows_real_result_after_prediction(self):
        client = flask_app_module.app.test_client()
        with client.session_transaction() as sess:
            sess['fuel_prediction'] = {
                'result': 'สันดาป (ICE)',
                'scores': {'EV': 26, 'Hybrid': 36, 'ICE': 38},
                'confidence': 0.38,
                'model_used': 'BAGGING (real)',
            }
        html = client.get('/dashboard').get_data(as_text=True)
        self.assertIn('สันดาป (ICE)', html)
        self.assertIn('38.0%', html)
        self.assertNotIn('ยังไม่มีผลวิเคราะห์', html)


class FuelFormAsksOnlyUsedQuestionsTests(unittest.TestCase):
    """ฟอร์มเชื้อเพลิงถามเฉพาะคำถามที่โมเดลใช้จริง

    หลักฐาน: analysis/fuel_feature_usage_2026-09-23.txt
    (fuel_model.pkl ตั้ง remainder='drop' ทิ้ง 21 จาก 26 คอลัมน์)
    """

    def test_dropped_questions_not_in_form(self):
        html = read_template('predict_fuel.html')
        for field in DROPPED_FUEL_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(
                    f'name="{field}"', html,
                    f'ฟอร์มยังถาม "{field}" ทั้งที่โมเดลไม่ได้ใช้ค่านี้เลย'
                )

    def test_used_questions_still_in_form(self):
        """เช็คจาก HTML ที่เรนเดอร์จริง เพราะ NEP 5 ข้อสร้างด้วย Jinja loop
        (grep ในไฟล์ template ดิบจะไม่เจอ name="nep_1")
        """
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'
        client = flask_app_module.app.test_client()
        with client.session_transaction() as sess:
            sess['buy_result'] = 'ซื้อ'  # ผ่านด่าน buy_result_required
        html = client.get('/predict/fuel').get_data(as_text=True)
        self.assertEqual(html.count('<form'), 1, 'ไม่ได้อยู่ที่หน้าฟอร์มเชื้อเพลิง')
        for field in REQUIRED_FUEL_FIELDS:
            with self.subTest(field=field):
                self.assertIn(
                    f'name="{field}"', html,
                    f'ฟอร์มขาด "{field}" ซึ่งเป็นคำถามที่โมเดลใช้จริง — ผลทำนายจะเพี้ยน'
                )

    def test_buy_form_untouched(self):
        """ฟอร์ม BUY ใช้ฟีเจอร์ครบ 27 ตัว ห้ามตัดคำถามออก"""
        html = read_template('predict_buy.html')
        for field in ('charging_access', 'tco_awareness', 'incentive_awareness',
                      'intention', 'attitude', 'subjective_norm', 'pbc_financial'):
            with self.subTest(field=field):
                self.assertIn(f'name="{field}"', html,
                              f'ฟอร์ม BUY ขาด "{field}" — buy_model.pkl ใช้ทุกฟีเจอร์')


class RemovedTextStaysRemovedTests(unittest.TestCase):
    """ข้อความที่ผู้ใช้สั่งตัดออก ต้องไม่กลับมาโผล่อีก"""

    @classmethod
    def setUpClass(cls):
        flask_app_module.app.config['TESTING'] = True
        flask_app_module.app.config['SECRET_KEY'] = 'test-secret'

    def test_home_and_login_free_of_jargon(self):
        client = flask_app_module.app.test_client()
        for url in ('/', '/login'):
            html = client.get(url).get_data(as_text=True)
            for banned in BANNED_TEXT:
                with self.subTest(url=url, text=banned):
                    self.assertNotIn(banned, html,
                                     f'{url} ยังมีข้อความ "{banned}" ที่ผู้ใช้สั่งตัดออก')

    def test_footer_free_of_jargon(self):
        html = read_template('base.html')
        for banned in BANNED_TEXT + ['เขตบางขุนเทียน']:
            with self.subTest(text=banned):
                self.assertNotIn(banned, html, f'footer ยังมี "{banned}"')

    def test_system_name_updated(self):
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        self.assertIn('ตามประเภทเชื้อเพลิง', html,
                      'หน้าแรกควรใช้ชื่อระบบใหม่ที่ผู้ใช้กำหนด')


if __name__ == '__main__':
    unittest.main(verbosity=2)
