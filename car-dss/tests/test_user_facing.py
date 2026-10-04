"""
QA Tests: สิ่งที่ผู้ใช้เห็นจริงบนหน้าเว็บ (ไม่ใช่แค่ route ทำงานถูก)

ที่มา: 23 ก.ย. 2569 — pytest ผ่าน 42/42 แต่ผู้ใช้ยังเจอหน้าล็อกอิน
เพราะเทสต์เดิมเช็คแค่ route แต่ไม่ได้เช็คปุ่มที่ผู้ใช้กดจริง
เทสต์ชุดนี้จึงเช็คสิ่งที่ผู้ใช้กดจริง ไม่ใช่แค่สิ่งที่เซิร์ฟเวอร์ตอบ

⚠️ 25 ก.ย. 2569 พฤติกรรมเปลี่ยนตามที่อาจารย์ที่ปรึกษาเคาะ:
  - การพยากรณ์ (BUY → FUEL) และหน้าผลลัพธ์ **ต้องล็อกอิน** อีกครั้ง (เลิก guest session)
  - /dashboard เป็น **หน้าภาพรวมข้อมูลงานวิจัยสาธารณะ** ไม่ต้องล็อกอิน ทุกคนเห็นเหมือนกัน
  เทสต์ที่เคยยืนยันพฤติกรรม guest ถูกเขียนใหม่ให้ยืนยันพฤติกรรมใหม่ (ไม่ได้ลบทิ้งเงียบ ๆ)

Scenarios:
  1. หน้าพยากรณ์/ผลลัพธ์ทั้ง 7 route ไม่ล็อกอิน = เด้งไป /login พอดี และไม่มี guest uid ถูกสร้าง
  2. หน้าสาธารณะ (/, /dashboard, /login, /register) เปิดได้โดยไม่ล็อกอิน
  3. หน้าแอดมินยังล็อก — ยอมเฉพาะ redirect ไป /admin/login หรือ 403 (404 ไม่นับ, board #31)
  4. ปุ่ม CTA ชี้ไปที่ที่ถูก — เช็คตัวปุ่มจริง ไม่ใช่นับจำนวนลิงก์ (board #31)
  5. dashboard ไม่มีผลส่วนตัว ไม่มีตัวเลขปลอม และตัวเลขตรงกับ dataset_overview.json
  6. ฟอร์ม BUY และเชื้อเพลิงถามเฉพาะคำถามที่โมเดลใช้จริง (26 ก.ย. 2569 เทียบกับ .pkl ที่โหลดอยู่ด้วย)
  7. ข้อความที่ผู้ใช้สั่งให้ตัดออก ต้องไม่กลับมาโผล่อีก

รันด้วย:
    cd car-dss
    python -m pytest tests/test_user_facing.py -v
"""

import json
import os
import re
import sys
import unittest
from urllib.parse import urlsplit

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as flask_app_module  # noqa: E402
import config  # noqa: E402

TEMPLATES = os.path.join(BASE_DIR, 'templates')

# หน้าที่ต้องล็อกอินก่อน (อาจารย์เคาะ 25 ก.ย. 2569) — (method, url)
LOGIN_REQUIRED_ROUTES = [
    ('GET', '/predict/buy'),
    ('GET', '/predict/fuel'),
    ('GET', '/result/buy'),
    ('GET', '/result/fuel'),
    ('POST', '/api/predict/buy'),
    ('POST', '/api/predict/fuel'),
    ('GET', '/recommend'),
]

# หน้าที่ทุกคนเข้าได้โดยไม่ต้องล็อกอิน
PUBLIC_PAGES = ['/', '/dashboard', '/login', '/register']

# หน้าที่ต้องล็อกอินแอดมินเสมอ — ถ้าหลุดคือช่องโหว่
ADMIN_PAGES = ['/admin', '/admin/users', '/admin/explain', '/admin/cars']

# ข้อความที่ผู้ใช้สั่งตัดออกจากหน้าที่ผู้ใช้ทั่วไปเห็น (23 ก.ย. 2569)
BANNED_TEXT = ['Data Mining', 'SVM & ANN', 'Data Mining · SVM · ANN']

# ตัวเลขปลอมที่เคยฝังอยู่ใน dashboard (ห้ามกลับมา)
FAKE_DASHBOARD_MARKERS = [
    '78.0%', 'EV: 78', 'mockScores', 'mockCosts', 'cost_comparison',
    '32500', '19600', '11300',            # เบี้ยประกันที่ฝังตายตัว
    '[800,', '[2200,', '[3800,',          # ค่าใช้จ่ายรายเดือนที่ฝังตายตัว
    'Loss Ratio', 'ข้อมูลจำลอง',
]

# 27 ก.ย. 2569: โมเดลเทรนใหม่จากแบบสอบถามชุด n=514 (ผู้ใช้อนุมัติ) — ดู analysis/verify_newdata_2026-09-27.txt
# (ชุด n=511 ของ 26 ก.ย. ถูกถอด) คำถามที่ fuel_model.pkl ชุดนี้ไม่ได้ใช้ + คำถามกลุ่ม EV/NEP ที่ไม่มีแล้ว
DROPPED_FUEL_FIELDS = [
    'resale_maintenance_concern',
    'ev_exposure', 'range_anxiety',
    'nep_1', 'nep_2', 'nep_3', 'nep_4', 'nep_5',
]

# คำถามที่โมเดลใช้จริง — ห้ามหายไปจากฟอร์ม
REQUIRED_FUEL_FIELDS = ['usage_type', 'frequency', 'distance', 'prev_car', 'priority', 'tech_env_concern']

# ฟอร์ม BUY: buy_model.pkl ชุด n=514 ใช้ education + family_size + purpose_avoid_public (จาก purpose)
# 29 ก.ย. 2569: buy_model.pkl จากชุดเดิม n=500 (คำถามทั่วไป)
REQUIRED_BUY_FIELDS = ['age', 'children', 'education', 'occupation', 'family_size',
                       'housing_type', 'parking', 'budget', 'concern', 'purpose']

# คำถามกลุ่ม TPB / EV / เหตุการณ์ชีวิต — แบบสอบถามชุดใหม่ไม่มี อาจารย์ไม่ต้องการแล้ว ห้ามกลับมา
DROPPED_BUY_FIELDS = [
    'charging_access', 'tco_awareness', 'incentive_awareness',
    'intention', 'attitude', 'subjective_norm', 'pbc_financial', 'life_events',
    # ยังอยู่ในแบบสอบถามแต่ buy_model.pkl (ชุดเดิม n=500) ไม่ได้ใช้
    'gender', 'income', 'housing_status',
]

NAME_RE = re.compile(r'''\bname\s*=\s*(["'])(.*?)\1''')

# <a ...>ข้อความ</a> — รับทั้ง href="..." และ href='...' (codex ค้าน board #31 ว่ารับแค่ double quote)
ANCHOR_RE = re.compile(r'<a\s([^>]*)>(.*?)</a>', re.S)
HREF_RE = re.compile(r'''href\s*=\s*(["'])(.*?)\1''', re.S)
ID_RE = re.compile(r'''\bid\s*=\s*(["'])(.*?)\1''', re.S)


def read_template(name):
    with open(os.path.join(TEMPLATES, name), encoding='utf-8') as f:
        return f.read()


def anchors(html):
    """คืน [(href, id, ข้อความ)] ของทุกลิงก์ในหน้า"""
    out = []
    for attrs, text in ANCHOR_RE.findall(html):
        href = HREF_RE.search(attrs)
        aid = ID_RE.search(attrs)
        out.append((href.group(2) if href else '', aid.group(2) if aid else '', text))
    return out


def path_of(location):
    return urlsplit(location or '').path


def _setup_app():
    flask_app_module.app.config['TESTING'] = True
    flask_app_module.app.config['SECRET_KEY'] = 'test-secret'


def logged_in_client(uid='local_tester', username='tester'):
    client = flask_app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['user_uid'] = uid
        sess['username'] = username
    return client


class LoginRequiredTests(unittest.TestCase):
    """การพยากรณ์และผลลัพธ์ต้องล็อกอินก่อน (อาจารย์เคาะ 25 ก.ย. 2569)"""

    @classmethod
    def setUpClass(cls):
        _setup_app()

    def test_each_route_redirects_exactly_to_login(self):
        for method, url in LOGIN_REQUIRED_ROUTES:
            with self.subTest(method=method, url=url):
                client = flask_app_module.app.test_client()  # ไม่ล็อกอิน
                resp = client.open(url, method=method, follow_redirects=False)
                self.assertEqual(resp.status_code, 302,
                                 f'{method} {url} ไม่ล็อกอินควรได้ 302 แต่ได้ {resp.status_code}')
                self.assertEqual(path_of(resp.headers.get('Location')), '/login',
                                 f'{method} {url} ต้องเด้งไป /login พอดี แต่ไป {resp.headers.get("Location")}')

    def test_no_guest_uid_created(self):
        """เลิก guest session แล้ว — ไม่ล็อกอินเข้าหน้าไหนก็ต้องไม่มี uid ถูกสร้าง"""
        client = flask_app_module.app.test_client()
        for method, url in LOGIN_REQUIRED_ROUTES:
            client.open(url, method=method)
        for url in PUBLIC_PAGES:
            client.get(url)
        with client.session_transaction() as sess:
            self.assertNotIn('user_uid', sess)
            self.assertNotIn('is_guest', sess)

    def test_legacy_guest_cookie_is_not_treated_as_login(self):
        """คุกกี้ guest ที่ค้างมาจากช่วง 23–25 ก.ย. ต้องไม่ผ่าน login_required
        และต้องไม่ทำให้ /login เด้งวนไป /predict/buy"""
        client = flask_app_module.app.test_client()
        with client.session_transaction() as sess:
            sess['user_uid'] = 'guest_abc123def456'
            sess['username'] = 'ผู้ใช้ทั่วไป'
            sess['is_guest'] = True
        resp = client.get('/predict/buy', follow_redirects=False)
        self.assertEqual(path_of(resp.headers.get('Location')), '/login')
        self.assertEqual(client.get('/login').status_code, 200)
        with client.session_transaction() as sess:
            self.assertNotIn('user_uid', sess)

    def test_logged_in_user_can_open_form(self):
        resp = logged_in_client().get('/predict/buy', follow_redirects=False)
        self.assertEqual(resp.status_code, 200)


class PublicAndAdminAccessTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _setup_app()

    def test_public_pages_open_without_login(self):
        for url in PUBLIC_PAGES:
            with self.subTest(url=url):
                resp = flask_app_module.app.test_client().get(url, follow_redirects=False)
                self.assertEqual(
                    resp.status_code, 200,
                    f'{url} ควรเปิดได้โดยไม่ล็อกอิน แต่ได้ {resp.status_code} '
                    f'-> {resp.headers.get("Location", "")}'
                )

    def test_admin_pages_still_locked(self):
        """ยอมเฉพาะ redirect ไป /admin/login หรือ 403 — 404 แปลว่า route หาย ไม่ใช่ล็อก (board #31)"""
        for url in ADMIN_PAGES:
            with self.subTest(url=url):
                resp = flask_app_module.app.test_client().get(url, follow_redirects=False)
                self.assertIn(resp.status_code, (302, 403),
                              f'{url} ต้องเด้งไป /admin/login หรือ 403 แต่ได้ {resp.status_code}')
                if resp.status_code == 302:
                    self.assertEqual(path_of(resp.headers.get('Location')), '/admin/login',
                                     f'{url} เด้งไป {resp.headers.get("Location")} ไม่ใช่ /admin/login')

    def test_normal_user_cannot_open_admin(self):
        resp = logged_in_client().get('/admin', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(path_of(resp.headers.get('Location')), '/admin/login')


class CtaLinksTests(unittest.TestCase):
    """ปุ่ม CTA ต้องชี้ไปที่ที่ถูก — เช็คตัวปุ่มจริง ไม่ใช่นับจำนวนลิงก์ /login (board #31)"""

    @classmethod
    def setUpClass(cls):
        _setup_app()

    def test_home_cta_goes_to_prediction_form(self):
        """ปุ่ม "เริ่มเลือกรถ" บนหน้าแรก (ดีไซน์ 30 ก.ย. 2569 มี 2 ปุ่ม: หัวเรื่อง + ปิดท้าย) ต้องชี้ /predict/buy
        (ถ้ายังไม่ล็อกอิน route นั้นจะพาไป /login เองพร้อมข้อความแจ้ง)"""
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        links = anchors(html)
        cta = [href for href, _, text in links if 'เริ่มเลือกรถ' in text]
        self.assertEqual(len(cta), 2, 'หน้าแรกควรมีปุ่ม "เริ่มเลือกรถ" 2 ปุ่ม')
        for href in cta:
            self.assertEqual(path_of(href), '/predict/buy',
                             f'ปุ่มเริ่มเลือกรถชี้ไป {href} ควรชี้ /predict/buy')

    def test_home_links_point_to_real_routes(self):
        """ดีไซน์ต้นฉบับลิงก์ไปเว็บจริงแบบเต็ม URL — หลังย้ายเข้า Flask ทุกลิงก์ต้องเป็น route ในระบบ"""
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        self.assertNotIn('pythonanywhere.com', html)
        allowed = {'/', '/predict/buy', '/predict/fuel', '/dashboard', '/login', '/logout', ''}
        for href, _, _ in anchors(html):
            with self.subTest(href=href):
                self.assertIn(path_of(href), allowed)

    def test_home_cta_redirect_lands_on_login(self):
        """กดปุ่มหน้าแรกตอนยังไม่ล็อกอิน -> ต้องจบที่หน้าล็อกอินพร้อมข้อความ ไม่ใช่หน้า error"""
        resp = flask_app_module.app.test_client().get('/predict/buy', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.request.path, '/login')
        self.assertIn('กรุณาเข้าสู่ระบบก่อน', resp.get_data(as_text=True))

    def test_dashboard_cta_logged_out_points_to_login(self):
        html = flask_app_module.app.test_client().get('/dashboard').get_data(as_text=True)
        by_id = {aid: href for href, aid, _ in anchors(html) if aid}
        self.assertIn('ctaLogin', by_id, 'dashboard ไม่มีปุ่มชวนเข้าสู่ระบบสำหรับคนที่ยังไม่ล็อกอิน')
        self.assertEqual(path_of(by_id['ctaLogin']), '/login')
        self.assertEqual(path_of(by_id.get('ctaRegister')), '/register')
        self.assertNotIn('ctaStart', by_id)

    def test_dashboard_cta_logged_in_points_to_form(self):
        html = logged_in_client().get('/dashboard').get_data(as_text=True)
        by_id = {aid: href for href, aid, _ in anchors(html) if aid}
        self.assertEqual(path_of(by_id.get('ctaStart')), '/predict/buy')
        self.assertNotIn('ctaLogin', by_id)

    def test_navbar_shows_overview_link_when_logged_out(self):
        # 4 ต.ค. 2569 หน้าในใช้ base_cardss.html (ดีไซน์ผู้ใช้) เมนูแบบเดียวกับหน้าแรก:
        # แสดงลิงก์พยากรณ์ทุกคน (กดแล้วเด้งไปล็อกอินเอง) · ซ่อนเฉพาะ "รถแนะนำ" ที่ต้องล็อกอิน
        html = flask_app_module.app.test_client().get('/dashboard').get_data(as_text=True)
        nav = html[html.index('id="menu"'):html.index('</nav>', html.index('id="menu"'))]
        hrefs = [path_of(h) for h, _, _ in anchors(nav)]
        self.assertIn('/dashboard', hrefs, 'เมนูบนต้องมีลิงก์ภาพรวมข้อมูลแม้ยังไม่ล็อกอิน')
        self.assertIn('/login', hrefs)
        self.assertNotIn('/recommend', hrefs, 'ยังไม่ล็อกอินไม่ควรเห็นเมนูรถแนะนำ')


class DashboardPublicOverviewTests(unittest.TestCase):
    """dashboard = ภาพรวมข้อมูลงานวิจัยสาธารณะ

    บั๊กเดิม: ฝัง "EV 78% ANN (mock)" / score card 92/75/88/60 / ค่าใช้จ่ายที่ไม่มีที่มา
    ตอนนี้ตัวเลขทุกตัวต้องมาจาก data/dataset_overview.json (analysis/dashboard_overview.py)
    และ data/cars.json เท่านั้น
    """

    @classmethod
    def setUpClass(cls):
        _setup_app()
        with open(config.DATASET_OVERVIEW_PATH, encoding='utf-8') as f:
            cls.ov = json.load(f)

    def _html(self, client=None):
        client = client or flask_app_module.app.test_client()
        resp = client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        return resp.get_data(as_text=True)

    def test_no_hardcoded_numbers_in_template(self):
        html = read_template('dashboard.html')
        for fake in FAKE_DASHBOARD_MARKERS:
            with self.subTest(fake=fake):
                self.assertNotIn(fake, html, f'dashboard.html ยังมีค่าที่ไม่มีที่มา "{fake}"')
        # ตัวเลข 3 หลักขึ้นไปใน template = สงสัยว่าฝังข้อมูล (ยกเว้นค่าขนาด/สี CSS)
        body = re.sub(r'<style>.*?</style>', '', html, flags=re.S)
        body = re.sub(r'\{#.*?#\}', '', body, flags=re.S)         # คอมเมนต์ Jinja
        body = re.sub(r'<!--.*?-->', '', body, flags=re.S)        # คอมเมนต์ HTML
        body = re.sub(r'^\s*//.*$', '', body, flags=re.M)         # คอมเมนต์ JS
        body = re.sub(r'#[0-9A-Fa-f]{3,6}\b', '', body)          # รหัสสี fallback
        body = re.sub(r'rgba?\([^)]*\)', '', body)               # สี rgba() ของกราฟ (4 ต.ค. 2569)
        body = re.sub(r'font-weight:\s*\d+', '', body)            # น้ำหนักฟอนต์
        body = re.sub(r'\*\s*100\b', '', body)                    # แปลงเป็นเปอร์เซ็นต์
        body = re.sub(r'\d+(px|ms|%)', '', body)                  # ขนาด
        body = re.sub(r'chart\.js@[\d.]+', '', body)              # เวอร์ชัน CDN
        suspicious = re.findall(r'(?<![\w.])\d{3,}(?![\w.])', body)
        self.assertEqual(suspicious, [], f'dashboard.html มีตัวเลขฝังอยู่: {suspicious}')

    def test_logged_out_shows_real_overview_numbers(self):
        html = self._html()
        self.assertIn(f'id="statRespondents">{self.ov["source"]["rows"]}<', html)
        self.assertIn(f'id="statFuelN">{self.ov["fuel"]["n"]}<', html)
        for key in ('buy', 'fuel'):
            block = self.ov[key]
            for lab, c in zip(block['labels'], block['counts']):
                with self.subTest(key=key, label=lab):
                    pct = '%.1f%%' % (c * 100.0 / block['n'])
                    self.assertRegex(html, rf'<(t[dh])[^>]*>{re.escape(lab)}</\1><td class="num">{c} คน</td>'
                                           rf'<td class="num">{re.escape(pct)}</td>')

    def test_overview_matches_research_dataset(self):
        """ตัวเลขชุดนี้ต้องตรงกับชุดข้อมูลใน files/user_from/ — 28 ก.ย. 2569 เปลี่ยนเป็นชุด n=630
        (n514 + ไฟล์ EV 73 + ไฟล์ไฮบริด 43 · BUY ซื้อ 325 · FUEL ผู้มีรถ 457 ICE 160 baseline 0.3501
        ตาม analysis/dashboard_overview_2026-09-28.txt / verify_web_accuracy_2026-09-28.txt)
        หมายเหตุ: buy_model.pkl ยังเป็นของชุด n=514 (ผู้ใช้เลือก) แต่ dashboard แสดงภาพรวมข้อมูลทั้งหมด"""
        self.assertEqual(self.ov['source']['rows'], 630)
        self.assertEqual(self.ov['buy']['n'], 630)
        self.assertEqual(self.ov['fuel']['n'], 457)
        self.assertEqual(max(self.ov['buy']['counts']), 325)
        self.assertEqual(max(self.ov['fuel']['counts']), 160)
        self.assertEqual(self.ov['fuel']['respondents_with_car'], 457)
        for key in ('buy', 'fuel', 'age', 'income'):
            self.assertEqual(sum(self.ov[key]['counts']), self.ov[key]['n'])

    def test_car_counts_are_live_from_cars_json(self):
        cars = flask_app_module.load_cars()
        html = self._html()
        total = sum(len(cars.get(k, [])) for k in ('EV', 'Hybrid', 'ICE'))
        self.assertIn(f'id="statCars">{total}<', html)

    def test_no_personal_result_even_with_session_prediction(self):
        client = logged_in_client()
        with client.session_transaction() as sess:
            sess['fuel_prediction'] = {
                'result': 'สันดาป (ICE)', 'scores': {'EV': 26, 'Hybrid': 36, 'ICE': 38},
                'confidence': 0.38, 'model_used': 'BAGGING (real)',
            }
            sess['buy_prediction'] = {'result': 'ซื้อ', 'confidence': 0.71, 'model_used': 'BAGGING (real)'}
        html = self._html(client)
        # 'สันดาป (ICE)' อยู่ในตารางรถสาธารณะ ("รถยนต์สันดาป (ICE)") จึงไม่ใช้เป็นตัวชี้ผลส่วนตัวแล้ว (4 ต.ค. 2569)
        for personal in ('38.0%', '71.0%', 'BAGGING (real)', 'ผลลัพธ์: คุณเหมาะสมกับ', 'ประเภทที่เข้ากับคุณ'):
            self.assertNotIn(personal, html, f'dashboard สาธารณะแสดงผลส่วนตัว "{personal}"')

    def test_same_numbers_for_everyone(self):
        """คนล็อกอินกับไม่ล็อกอินต้องเห็นตัวเลขชุดเดียวกัน (ต่างกันได้แค่ปุ่ม CTA/เมนู)"""
        def data_section(html):
            start = html.index('id="statRespondents"')
            end = html.index('id="carTable"')
            return html[start:end]
        self.assertEqual(data_section(self._html()), data_section(self._html(logged_in_client())))

    def test_no_model_accuracy_shown(self):
        """ไม่แสดง accuracy บน dashboard (เลี่ยงการหยิบเลขผิดชุด — 00-READ-FIRST §1)"""
        html = self._html()
        for word in ('Accuracy', 'accuracy', 'ความแม่นยำ', '0.6900', '0.4180', '0.4336', '0.6925',
                     '0.4995', '0.3543', '49.9', '35.4',
                     '0.5583', '0.6804', '55.8', '68.0'):
            self.assertNotIn(word, html)


def rendered_form_fields(url, session_extra=None):
    """ชื่อช่องทั้งหมดในฟอร์มที่เรนเดอร์จริง (ไม่ใช่ template ดิบ — บางช่องสร้างด้วย Jinja loop)"""
    _setup_app()
    client = logged_in_client()
    if session_extra:
        with client.session_transaction() as sess:
            sess.update(session_extra)
    html = client.get(url).get_data(as_text=True)
    form = html[html.index('<form'):html.index('</form>')]
    return {m.group(2) for m in NAME_RE.finditer(form)}


class FormMatchesLoadedModelTests(unittest.TestCase):
    """26 ก.ย. 2569: ช่องในฟอร์ม == ช่องที่ .pkl ที่โหลดอยู่ใช้จริง (อ่านจาก cat_cols/num_cols ใน bundle)

    ถ้าเทรนใหม่แล้วชุดฟีเจอร์เปลี่ยน เทสต์นี้จะฟ้องทันที ไม่ต้องพึ่งคนจำไปแก้ฟอร์ม
    (ColumnTransformer ตั้ง remainder='drop' — ช่องที่ไม่อยู่ในรายการ ถามไปก็ไม่มีผล)
    """

    @classmethod
    def setUpClass(cls):
        from models import predictor as pr
        from models import feature_encoding as fe
        if config.USE_MOCK:
            raise unittest.SkipTest('โหมด mock ไม่มี .pkl ให้เทียบ')
        cls.pr, cls.fe = pr, fe

    def _used(self, bundle):
        return self.fe.form_fields_used(bundle['cat_cols'], bundle['num_cols'])

    def test_bundles_match_feature_encoding(self):
        """โมเดลกับโค้ดต้องรุ่นเดียวกัน (.pkl ข้อมูลชุดเดิมจะไม่ผ่านข้อนี้ — ตั้งใจ)"""
        self.assertEqual(list(self.pr._buy_bundle['feature_cols']), self.fe.buy_feature_columns())
        self.assertEqual(list(self.pr._fuel_bundle['feature_cols']), self.fe.fuel_feature_columns())

    def test_buy_form_fields_equal_model_fields(self):
        self.assertEqual(rendered_form_fields('/predict/buy'), self._used(self.pr._buy_bundle))

    def test_fuel_form_fields_equal_model_fields(self):
        self.assertEqual(rendered_form_fields('/predict/fuel', {'buy_result': 'ซื้อ'}),
                         self._used(self.pr._fuel_bundle))


class FuelFormAsksOnlyUsedQuestionsTests(unittest.TestCase):
    """ฟอร์มถามเฉพาะคำถามที่โมเดลใช้จริง (ชื่อคลาสเดิม — ตอนนี้ครอบทั้งฟอร์ม BUY และ FUEL)

    หลักฐาน: analysis/verify_newdata_2026-09-26.txt (โมเดลชุดข้อมูล n=511)
    เทสต์ชุดนี้เช็คจากรายชื่อตายตัว ส่วน FormMatchesLoadedModelTests เช็คจาก .pkl ที่โหลดอยู่
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
        _setup_app()
        client = logged_in_client()
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

    def test_buy_form_asks_only_used_questions(self):
        """26 ก.ย. 2569: เดิมเทสต์นี้ชื่อ test_buy_form_untouched (ยืนยันว่าฟอร์ม BUY ถามครบ 27 ฟีเจอร์
        รวมคำถาม TPB/EV) — พฤติกรรมกลับด้านตามคำสั่งผู้ใช้: แบบสอบถามชุดใหม่ไม่มีคำถามเหล่านั้น
        29 ก.ย. 2569: buy_model.pkl เปลี่ยนเป็นโมเดลจากชุดเดิม n=500 (คำถามทั่วไป 10 ช่อง)"""
        fields = rendered_form_fields('/predict/buy')
        for field in REQUIRED_BUY_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, fields, f'ฟอร์ม BUY ขาด "{field}" ซึ่งเป็นคำถามที่โมเดลใช้จริง')
        for field in DROPPED_BUY_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, fields, f'ฟอร์ม BUY ยังถาม "{field}" ทั้งที่โมเดลไม่ได้ใช้/ไม่มีในแบบสอบถาม')

    def test_fuel_likert_wording_matches_survey(self):
        """ข้อ Likert ต้องใช้ถ้อยคำเดียวกับแบบสอบถามที่ใช้เทรน (เดิมถามเป็น "ความใส่ใจ/ความกังวล" ซึ่งกลับทิศ)"""
        html = read_template('predict_fuel.html')
        self.assertIn('ประเภทพลังงานของรถยนต์มีความเหมาะสมกับการใช้งาน', html)
        self.assertNotIn('ความกังวลเรื่องราคาขายต่อ', html)

    def test_multi_select_questions_are_checkboxes(self):
        """27 ก.ย. 2569: คำถามที่แบบสอบถามให้เลือกได้หลายข้อ ต้องเป็น checkbox ไม่ใช่ select ค่าเดียว
        (เดิม prev_car เป็น select ทำให้คำตอบผสมถูกยุบเหลือแบบเดียว)"""
        # 4 ต.ค. 2569 ช่องสร้างผ่าน _cardss_macros.html → ตรวจจากหน้าที่เรนเดอร์จริง
        _setup_app()
        client = logged_in_client()
        buy = client.get('/predict/buy').get_data(as_text=True)
        with client.session_transaction() as sess:
            sess['buy_result'] = 'ซื้อ'
        fuel = client.get('/predict/fuel').get_data(as_text=True)
        for v in ('ice', 'hybrid', 'ev'):
            self.assertRegex(fuel, rf'type="checkbox"[^>]*name="prev_car"[^>]*value="{v}"')
        self.assertNotIn('<select id="prev_car"', fuel)
        self.assertRegex(buy, r'type="checkbox"[^>]*name="purpose"[^>]*value="avoid_public"')
        self.assertNotIn('<select id="purpose"', buy)


class RemovedTextStaysRemovedTests(unittest.TestCase):
    """ข้อความที่ผู้ใช้สั่งตัดออก ต้องไม่กลับมาโผล่อีก"""

    @classmethod
    def setUpClass(cls):
        _setup_app()

    def test_public_pages_free_of_jargon(self):
        client = flask_app_module.app.test_client()
        for url in ('/', '/login', '/dashboard'):
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


class HonestResultTests(unittest.TestCase):
    """29 ก.ย. 2569 (impeccable critique P0): หน้าผลต้องบอกว่าเชื่อได้แค่ไหน และห้ามอ้างสิ่งที่โมเดลไม่ได้ใช้
    — ตัวเลขความแม่นยำต้องมาจาก metrics ใน .pkl (model_reliability) ไม่ใช่พิมพ์ตายตัว
    — ของที่ใช้ตอนพัฒนา (Skeleton Mode / Mock / ชื่อโมเดล) ห้ามโผล่ให้ผู้ใช้เห็น"""

    DEV_RESIDUE = ('mock-tag', 'Skeleton Mode', '(real)', '(mock)', 'Multi-class', 'Binary', 'จำนวน Class')

    @classmethod
    def setUpClass(cls):
        _setup_app()
        from models import predictor
        from models import feature_encoding
        cls.pr, cls.fe = predictor, feature_encoding

    def _page(self, url, key, value):
        client = logged_in_client()
        with client.session_transaction() as sess:
            sess[key] = value
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.get_data(as_text=True)

    def _check(self, html, kind):
        rel = self.pr.model_reliability(kind)
        if rel is None:
            self.skipTest('โหมด mock ไม่มีตัวเลขความแม่นยำ')
        self.assertIn('ผลนี้เชื่อได้แค่ไหน', html)
        self.assertIn(f"{rel['correct_per_100']} จาก 100 คน", html)
        used = html[html.index('class="fields-used"'):html.index('</div>', html.index('class="fields-used"'))]
        self.assertEqual(re.findall(r'<span>([^<]+)</span>', used), list(rel['fields_th']))
        # เทียบกับ baseline (ทายคำตอบที่พบบ่อยที่สุด) ไม่ใช่เดาสุ่ม — Codex ห้องประชุม #44
        self.assertNotIn('เดาสุ่ม', html)
        if rel['baseline_per_100'] is not None:
            # 4 ต.ค. 2569 ดีไซน์ใหม่แยกประโยค/ตัวเลขเป็นแถบเทียบ → ตรวจจากตัวหนังสือล้วน
            text = ' '.join(re.sub(r'<[^>]+>', ' ', html).split())
            self.assertRegex(text, rf"ทายคำตอบที่พบบ่อยที่สุดทุกครั้ง\s+{rel['baseline_per_100']} จาก 100 คน")
        self.assertIn(f"{rel['n_samples']:,}", html)
        for text in self.DEV_RESIDUE:
            with self.subTest(kind=kind, text=text):
                self.assertNotIn(text, html)

    def test_buy_result_shows_real_reliability(self):
        html = self._page('/result/buy', 'buy_prediction',
                          {'result': 'ซื้อ', 'confidence': 0.6, 'model_used': 'BAGGING (real)'})
        self._check(html, 'buy')

    def test_fuel_result_shows_real_reliability(self):
        html = self._page('/result/fuel', 'fuel_prediction',
                          {'result': 'ไฮบริด', 'scores': {'EV': 20, 'Hybrid': 50, 'ICE': 30},
                           'confidence': 0.5, 'model_used': 'BAGGING (real)'})
        self._check(html, 'fuel')

    def test_trust_block_lists_exactly_what_model_uses(self):
        """กล่อง "ผลนี้เชื่อได้แค่ไหน" บอกว่าระบบดูอะไร — ต้องตรงกับช่องที่ .pkl ใช้จริงทุกช่อง ไม่ขาดไม่เกิน"""
        if config.USE_MOCK:
            self.skipTest('โหมด mock')
        for kind, bundle in (('buy', self.pr._buy_bundle), ('fuel', self.pr._fuel_bundle)):
            rel = self.pr.model_reliability(kind)
            used = self.fe.form_fields_used(bundle['cat_cols'], bundle['num_cols'])
            with self.subTest(kind=kind):
                self.assertEqual(set(rel['fields']), used)
                self.assertEqual(len(rel['fields_th']), len(used))
                for label in rel['fields_th']:
                    self.assertRegex(label, '[ก-๙]', f'ชื่อช่อง "{label}" ยังไม่มีคำแปลไทยใน explainer.FIELD_TH')

    def test_baseline_file_matches_deployed_models(self):
        """data/model_reliability.json ต้องเป็นของ .pkl ชุดปัจจุบัน (SHA ตรง) — ลืมรัน verify_web_accuracy.py หลังเปลี่ยนโมเดล = ตก"""
        if config.USE_MOCK:
            self.skipTest('โหมด mock')
        for kind in ('buy', 'fuel'):
            with self.subTest(kind=kind):
                self.assertIsNotNone(self.pr.model_reliability(kind)['baseline_per_100'],
                                     'model_reliability.json ไม่ตรงกับ .pkl — รัน python analysis/verify_web_accuracy.py ใหม่')

    def test_stale_baseline_is_hidden(self):
        """SHA ไม่ตรง (เปลี่ยนโมเดลแต่ไม่ได้วัดใหม่) ต้องคืน None ไม่ใช่ตัวเลขของโมเดลเก่า"""
        import json, tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'model_reliability.json'), 'w', encoding='utf-8') as f:
                json.dump({'buy': {'sha256': '0' * 64, 'baseline': 0.9}}, f)
            with mock.patch.object(config, 'DATA_DIR', d), mock.patch.dict(self.pr._baseline_cache, clear=True):
                self.assertIsNone(self.pr._verified_baseline('buy'))

    def test_home_numbers_are_live(self):
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        ov = flask_app_module.load_dataset_overview()
        total = sum(item['count'] for item in flask_app_module.summarize_cars())
        # ดีไซน์ 30 ก.ย. 2569: ตัวเลขอยู่บนหินกิโล + หัวข้อส่วนรถ + ป้ายประเภท (เคยพิมพ์ 500/25/12/8/5 ตายตัว)
        self.assertIn(f'<span>รุ่นรถในระบบ</span><b>{total}</b>', html)
        self.assertIn(f'<h2>{total} รุ่น<br>', html)
        for item in flask_app_module.summarize_cars():
            with self.subTest(fuel=item['fuel']):
                self.assertIn(f"<small>{item['count']} รุ่น · ", html)
        if ov:
            self.assertIn(f"<span>ข้อมูลตัวอย่าง</span><b>{ov['source']['rows']:,}</b>", html)

    def test_recommend_cost_table_from_cars_json(self):
        """4 ต.ค. 2569 ผู้ใช้เลือกแบบ ก: ตารางค่าใช้จ่ายหน้ารถแนะนำคำนวณจาก cars.json (monthly_cost + insurance_class1)
        เดิม template พิมพ์ตายตัว (~32,500 / ~19,600 / ~11,300 / ค่าบำรุงรักษา) ซึ่งไม่มีที่มา"""
        cars = flask_app_module.load_cars()
        table = flask_app_module.build_cost_table(cars)
        self.assertIsNotNone(table)
        ev = [flask_app_module._numbers(c['monthly_cost'])[0] for c in cars['EV']]
        self.assertEqual(dict(table['rows'])['ค่าน้ำมัน / ค่าไฟ']['EV'], f'~{min(ev):,}–{max(ev):,}')
        client = logged_in_client()
        with client.session_transaction() as sess:
            sess['fuel_prediction'] = {'result': 'ไฮบริด (Hybrid)', 'scores': {'EV': 30, 'Hybrid': 40, 'ICE': 30}}
        html = client.get('/recommend').get_data(as_text=True)
        self.assertIn(dict(table['rows'])['ค่าน้ำมัน / ค่าไฟ']['Hybrid'], html)
        for fake in ('~32,500', '~19,600', '~11,300', 'ค่าบำรุงรักษา</th>'):
            self.assertNotIn(fake, html)
        self.assertNotIn('ค่าเดิมจาก template เก่า', read_template('recommend.html'))
        # Codex #52: ยืนยันทุกช่องของทุกประเภทเทียบกับ cars.json โดยตรง
        num = flask_app_module._numbers
        for key in ('EV', 'Hybrid', 'ICE'):
            e = [num(c['monthly_cost'])[0] for c in cars[key]]
            i = [n for c in cars[key] for n in num(c['insurance_class1'])]
            with self.subTest(fuel=key):
                self.assertEqual(table['rows'][1][1][key], f'~{round(min(i) / 12):,}–{round(max(i) / 12):,}')
                self.assertEqual(table['total'][key],
                                 f'~{min(e) + round(min(i) / 12):,}–{max(e) + round(max(i) / 12):,}')
                self.assertIn(table['total'][key], html)
        # ข้อมูลประเภทใดขาด = ไม่แสดงตาราง (ห้ามเติมตัวเลขแทน)
        self.assertIsNone(flask_app_module.build_cost_table({'EV': [], 'Hybrid': cars['Hybrid'], 'ICE': cars['ICE']}))

    def test_inner_pages_accessibility(self):
        """Antigravity #53: ข้อความเตือนผูกกับช่อง · ปุ่มรหัสผ่าน 44px · กราฟอายุ/รายได้มีตารางคู่"""
        client = logged_in_client()
        buy = client.get('/predict/buy').get_data(as_text=True)
        for fid in re.findall(r'<fieldset class="field" id="([^"]+)"', buy):
            with self.subTest(field=fid):
                self.assertIn(f'aria-describedby="{fid}-err"', buy)
                self.assertIn(f'id="{fid}-err"', buy)
        css = open(os.path.join(BASE_DIR, 'static', 'css', 'cardss-app.css'), encoding='utf-8').read()
        self.assertNotIn('min-height:40px', css[css.index('.peek{'):css.index('}', css.index('.peek{'))])
        ov = flask_app_module.load_dataset_overview()
        if ov:
            dash = flask_app_module.app.test_client().get('/dashboard').get_data(as_text=True)
            for tid, key in (('ageTable', 'age'), ('incomeTable', 'income')):
                table = dash[dash.index(f'id="{tid}"'):dash.index('</table>', dash.index(f'id="{tid}"'))]
                for lab, c in zip(ov[key]['labels'], ov[key]['counts']):
                    with self.subTest(table=tid, label=lab):
                        self.assertIn(f'<th scope="row">{lab}</th><td>{c} คน</td>', table)

    def test_register_explains_username_and_password_rules(self):
        """ผู้ใช้สั่ง 4 ต.ค. 2569: บอกวิธีตั้งชื่อผู้ใช้/รหัสผ่านให้ตรงกติกาจริงของระบบ"""
        html = flask_app_module.app.test_client().get('/register').get_data(as_text=True)
        self.assertIn('ใช้ตัวอังกฤษ a–z ตัวเลข 0–9 หรือขีดล่าง _ ยาว 3–30 ตัว', html)
        self.assertIn('อย่างน้อย 8 ตัว', html)
        self.assertIn('ไม่บังคับตัวพิมพ์ใหญ่', html)
        self.assertIn('aria-describedby="username-help"', html)

    def test_recommend_sorts_by_answered_budget(self):
        """ทดสอบแบบผู้ใช้จริง ข้อ 1 (4 ต.ค. 2569): รุ่นในงบที่ตอบขึ้นก่อน รุ่นเกินงบติดป้าย"""
        cars = flask_app_module.load_cars()
        out = flask_app_module.sort_cars_by_budget(cars, 'lt500000')
        for key in ('EV', 'Hybrid', 'ICE'):
            prices = [flask_app_module._price_to_int(c['price']) for c in out[key]]
            flags = [bool(c.get('over_budget')) for c in out[key]]
            with self.subTest(fuel=key):
                self.assertEqual(len(out[key]), len(cars[key]))            # ไม่ตัดรุ่นทิ้ง
                self.assertEqual(flags, sorted(flags))                     # ในงบก่อน เกินงบทีหลัง
                self.assertEqual(flags, [p > 500000 for p in prices])
        self.assertIs(flask_app_module.sort_cars_by_budget(cars, None), cars)   # ไม่รู้งบ = ลำดับเดิม
        # รุ่นที่ไม่มีราคา ต้องไม่ถูกจัดเป็น "อยู่ในงบ" (Codex #55)
        odd = flask_app_module.sort_cars_by_budget({'EV': [{'model': 'x', 'price': ''}, {'model': 'y', 'price': '400,000'}]}, 'lt500000')
        self.assertEqual([c['model'] for c in odd['EV']], ['y', 'x'])
        client = logged_in_client()
        with client.session_transaction() as sess:
            sess['fuel_prediction'] = {'result': 'ไฮบริด (Hybrid)', 'scores': {'EV': 30, 'Hybrid': 40, 'ICE': 30}}
            sess['buy_input_data'] = {'budget': 'lt500000'}
        html = client.get('/recommend').get_data(as_text=True)
        # ทุกรุ่นในระบบราคาเกิน 5 แสน → บอกตรง ๆ ว่าไม่มีรุ่นในงบ ไม่ติดป้ายซ้ำทุกคัน
        if not any(c for c in out['Hybrid'] if not c.get('over_budget')):
            self.assertIn('ยังไม่มีรุ่นประเภทนี้ในระบบที่ราคาอยู่ในงบที่คุณตอบ', html)
        with client.session_transaction() as sess:
            sess['buy_input_data'] = {'budget': '800001-1200000'}
        html = client.get('/recommend').get_data(as_text=True)
        mixed = flask_app_module.sort_cars_by_budget(cars, '800001-1200000')['Hybrid']
        self.assertEqual(html.count('class="over-budget"') >= sum(1 for c in mixed if c.get('over_budget')), True)
        self.assertIn('เกินงบที่คุณตอบ (800,001–1,200,000 บาท)', html)
        self.assertIn('ขึ้นก่อน', html)

    def test_not_buy_result_is_not_a_dead_end(self):
        """ทดสอบแบบผู้ใช้จริง ข้อ 2: ผล "ไม่ซื้อ" มีทางไปดูรถ · ข้อความเด้งกลับไม่ตำหนิ"""
        client = logged_in_client()
        with client.session_transaction() as sess:
            sess['buy_prediction'] = {'result': 'ไม่ซื้อ', 'confidence': 0.6}
            sess['buy_result'] = 'ไม่ซื้อ'
        html = client.get('/result/buy').get_data(as_text=True)
        self.assertIn('href="/#models"', html)
        bounced = client.get('/predict/fuel', follow_redirects=True).get_data(as_text=True)
        self.assertNotIn('ผลลัพธ์ต้องเป็น', bounced)
        self.assertIn('ดูรุ่นรถทั้งหมดได้ที่หน้าแรก', bounced)

    def test_home_route_section_removed(self):
        """ผู้ใช้สั่ง 4 ต.ค. 2569: ตัดส่วน "คุณเป็นคนบางขุนเทียนสายไหน?" + คำถาม 3 ข้อ"""
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        for gone in ('id="route"', 'สายไหน', 'ลองตอบ 3 ข้อ'):
            self.assertNotIn(gone, html)

    def test_draft_cleared_only_on_result_page(self):
        # Codex #52: คำตอบที่จำไว้ต้องไม่ถูกลบตอนกดส่ง (เซิร์ฟเวอร์อาจตีกลับ) → ลบเมื่อหน้าผลโหลดเท่านั้น
        js = open(os.path.join(BASE_DIR, 'static', 'js', 'cardss-app.js'), encoding='utf-8').read()
        self.assertNotIn('store.del(key)', js)
        self.assertIn('data-clear-draft="predictBuyForm"', read_template('result_buy.html'))
        self.assertIn('data-clear-draft="predictFuelForm"', read_template('result_fuel.html'))

    def test_login_does_not_promise_history_page(self):
        # ยังไม่มีหน้าดูประวัติผล → ห้ามบอกว่า "กลับมาดูย้อนหลังได้" (ผู้ใช้ตกลง 4 ต.ค. 2569)
        self.assertNotIn('ย้อนหลัง', flask_app_module.app.test_client().get('/login').get_data(as_text=True))

    def test_home_water_levels(self):
        """30 ก.ย. 2569 ผู้ใช้สั่ง: ปุ่มระดับน้ำ 4 ระดับในส่วนรถหล่น (ปลอดภัย→ห้ามขับ) + คำแนะนำทั่วไป ไม่บอกรายคัน
        ต้องบอกว่าไม่ใช่ผลจากโมเดล และเริ่มที่ระดับปลอดภัย"""
        html = flask_app_module.app.test_client().get('/').get_data(as_text=True)
        block = html[html.index('id="wl"'):html.index('id="wlNote"')]
        buttons = re.findall(r'data-cm="(\d+)" aria-pressed="(true|false)" data-note="([^"]+)"><b>([^<]+)</b>', block)
        self.assertEqual([(cm, name) for cm, _, _, name in buttons],
                         [('10', 'ปลอดภัย'), ('20', 'ระวัง'), ('30', 'อันตราย'), ('50', 'ห้ามขับ')])
        self.assertEqual([p for _, p, _, _ in buttons], ['true', 'false', 'false', 'false'])
        self.assertIn('ไม่ใช่ผลจากโมเดลพยากรณ์', html[html.index('id="wlNote"'):])

    def test_templates_free_of_dev_residue(self):
        for name in ('base.html', 'recommend.html', 'result_buy.html', 'result_fuel.html', 'home.html'):
            html = read_template(name)
            for text in ('mock-tag', 'Skeleton Mode', 'model_used', '>Mock<'):
                with self.subTest(template=name, text=text):
                    self.assertNotIn(text, html)

    def test_survey_area_stated_as_data_source(self):
        # 29 ก.ย. 2569 ผู้ใช้ยืนยันว่าแจกแบบสอบถามในเขตบางขุนเทียนจริง
        # บอกพื้นที่ได้เฉพาะในฐานะ "ที่มาของข้อมูล" (หน้าแรก + ภาพรวม) ไม่ใช่ป้ายหรือคำอธิบายผล
        client = flask_app_module.app.test_client()
        # 30 ก.ย. 2569 ผู้ใช้ออกแบบหน้าแรกใหม่ธีมบางขุนเทียน/พระราม 2 และสั่งให้กฎตามดีไซน์ → หน้าแรกพูดถึงพื้นที่ได้
        self.assertIn('บางขุนเทียน', client.get('/').get_data(as_text=True))
        self.assertIn('ข้อมูลเก็บในเขตบางขุนเทียน จึงอาจไม่ตรงกับคนพื้นที่อื่น',
                      client.get('/dashboard').get_data(as_text=True))
        for name in ('base.html', 'recommend.html', 'result_buy.html', 'result_fuel.html'):
            with self.subTest(template=name):
                self.assertNotIn('บางขุนเทียน', read_template(name))


if __name__ == '__main__':
    unittest.main(verbosity=2)
