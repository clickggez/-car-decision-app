"""
CarDSS — Flask Main Application
ระบบสนับสนุนการตัดสินใจซื้อรถยนต์
"""

import os
import re
import json
import uuid
import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)

import config
from models.predictor import predict_buy, predict_fuel, model_reliability
from validators import validate_buy, validate_fuel


# ============================================================
# JSON persistence helpers (local mode)
# ============================================================
def _load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cars():
    return _load_json(config.CARS_JSON_PATH, {"EV": [], "Hybrid": [], "ICE": []})


def save_cars(data):
    _save_json(config.CARS_JSON_PATH, data)


def load_local_users():
    return _load_json(config.USERS_LOCAL_JSON_PATH, {})


def save_local_users(users):
    _save_json(config.USERS_LOCAL_JSON_PATH, users)

# ============================================================
# Flask App Setup
# ============================================================
app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ============================================================
# Firebase Setup (graceful fallback ถ้ายังไม่มี credentials)
# ============================================================
db = None  # Firestore client
firebase_auth_available = False

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth as firebase_auth

    if os.path.exists(config.FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_auth_available = True
        print("[OK] Firebase connected successfully (service account file)")
    elif os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
        # Render/host อื่นที่ไม่มีไฟล์ .json — วางเนื้อหา JSON ทั้งก้อนไว้ใน env var แทน
        cred = credentials.Certificate(json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_JSON']))
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_auth_available = True
        print("[OK] Firebase connected successfully (env var credentials)")
    else:
        print(f"[WARNING] Firebase credentials not found at {config.FIREBASE_CREDENTIALS_PATH}")
        print("[WARNING] Running without Firebase — auth uses local session, data not persisted")
except ImportError:
    print("[WARNING] firebase-admin not installed — running without Firebase")


# ============================================================
# Simple User Object for session-based auth
# ============================================================
class SimpleUser:
    """Lightweight user object compatible with templates."""
    def __init__(self, uid, username):
        self.uid = uid
        self.username = username
        self.is_authenticated = True


# ============================================================
# Auth Helpers
# ============================================================

def get_current_user():
    """ดึง current user จาก session"""
    if 'user_uid' in session:
        return SimpleUser(session['user_uid'], session.get('username', ''))
    return None


def login_required(f):
    """Decorator: ต้อง login ก่อนเข้าหน้านี้

    25 ก.ย. 2569 — อาจารย์ที่ปรึกษาเคาะ: ระบบล็อกอินอยู่ในขอบเขตปริญญานิพนธ์
    การพยากรณ์ (BUY → FUEL) ต้องล็อกอินก่อน เพื่อให้ผลผูกกับบัญชีผู้ใช้จริง
    จึงเลิกใช้ guest session (`session_required` ที่เพิ่มเมื่อ 23 ก.ย.) แล้วกลับมาใช้ตัวนี้
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_uid' not in session:
            flash('กรุณาเข้าสู่ระบบก่อน', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.before_request
def _drop_legacy_guest_session():
    """ล้างตัวตน guest ที่ค้างอยู่ในคุกกี้ของผู้ใช้ตั้งแต่ช่วง 23–25 ก.ย. 2569

    ถ้าไม่ล้าง `guest_<random>` จะผ่าน login_required ได้ทั้งที่ไม่ได้ล็อกอินจริง
    และหน้า /login จะเด้งกลับไป /predict/buy วนไม่จบ
    """
    uid = str(session.get('user_uid', ''))
    if session.get('is_guest') or uid.startswith('guest_'):
        session.clear()


def buy_result_required(f):
    """Decorator: ต้องผ่านผลลัพธ์ ซื้อ ก่อนเข้าหน้า predict_fuel (<<extend>>)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('buy_result') != 'ซื้อ':
                # 4 ต.ค. 2569 เขียนใหม่ให้ไม่ตำหนิผู้ใช้ และบอกทางไปต่อ (ทดสอบแบบผู้ใช้จริง ข้อ 2)
            flash('ขั้นเลือกประเภทเชื้อเพลิงจะเปิดเมื่อผลขั้นที่ 1 คือ "มีแนวโน้มจะซื้อ" · ดูรุ่นรถทั้งหมดได้ที่หน้าแรก', 'info')
            return redirect(url_for('predict_buy_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: ต้อง login admin"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('กรุณาเข้าสู่ระบบผู้ดูแล', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_user():
    """ส่ง current_user ให้ทุก template"""
    return {
        'current_user': get_current_user(),
        'is_admin': session.get('is_admin', False),
    }


def _user_is_admin(user_uid, username):
    """
    บัญชีผู้ใช้ปกตินี้เป็น admin หรือไม่ (2026-08-28)

    ตั้งค่าที่ตัวข้อมูลผู้ใช้ ไม่ใช่ในโค้ด — ทำได้ 2 ทาง
      - Firebase: เอกสาร users/<uid> มีฟิลด์ role = "admin"  (หรือ is_admin = true)
      - โหมด local: data/users_local.json ของ user นั้นมี "is_admin": true
    ตั้งง่าย ๆ ด้วย:  python make_admin.py <ชื่อผู้ใช้>
    """
    if db and user_uid and not str(user_uid).startswith('local_'):
        try:
            doc = db.collection('users').document(user_uid).get()
            if doc.exists:
                data = doc.to_dict() or {}
                return data.get('role') == 'admin' or data.get('is_admin') is True
        except Exception as e:
            print(f"[ERROR] _user_is_admin: {e}")
        return False

    record = load_local_users().get(username) or {}
    return record.get('is_admin') is True


# ============================================================
# Firebase Helpers
# ============================================================

def save_prediction_to_firebase(user_uid, pred_type, input_data, result_data):
    """บันทึกผลพยากรณ์ลง Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection('predictions').document()
        doc_ref.set({
            'user_id': user_uid,
            'type': pred_type,
            'input_data': input_data,
            'result': result_data.get('result', ''),
            'confidence': result_data.get('confidence', 0),
            'model_used': result_data.get('model_used', ''),
            'scores': result_data.get('scores', {}),
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return doc_ref.id
    except Exception as e:
        print(f"[ERROR] Firebase save failed: {e}")
        return None


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    """หน้าแรก Home — ตัวเลขข้อมูลอ่านจาก dataset_overview.json (29 ก.ย. 2569 เลิกพิมพ์ "500" ตายตัว)
    30 ก.ย. 2569 ดีไซน์ใหม่ "พระราม 2 คืนฝนตก": car_counts ใช้กับป้ายประเภทรถ (EV/Hybrid/ICE)"""
    cars = summarize_cars()
    car_total = sum(item['count'] for item in cars)
    car_counts = {item['fuel']: item['count'] for item in cars}
    return render_template('home.html', overview=load_dataset_overview(),
                           car_total=car_total, car_counts=car_counts)


@app.route('/version')
def version():
    """บอกว่าเซิร์ฟเวอร์กำลังรันโค้ด commit ไหนอยู่ (23 ก.ย. 2569)

    ที่มา: เคยเสียเวลาเป็นชั่วโมงเพราะ git pull สำเร็จแล้วแต่ลืมกด Reload
    เว็บจึงเสิร์ฟโค้ดเก่าต่อไปโดยไม่มีอะไรบอก
    อ่านจาก .git โดยตรง ไม่ต้องติดตั้ง git module และไม่เปิดเผยอะไรนอกจากเลข commit
    ใช้คู่กับ tools/check_deploy.py
    """
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commit = 'unknown'
    try:
        with open(os.path.join(repo, '.git', 'HEAD'), encoding='utf-8') as f:
            head = f.read().strip()
        if head.startswith('ref:'):
            ref = head.split(' ', 1)[1].strip()
            with open(os.path.join(repo, '.git', ref), encoding='utf-8') as f:
                commit = f.read().strip()
        else:
            commit = head
    except OSError:
        pass
    return jsonify({'commit': commit[:7], 'commit_full': commit})


@app.route('/login', methods=['GET', 'POST'])
def login():
    """หน้าเข้าสู่ระบบ"""
    if 'user_uid' in session:
        return redirect(url_for('predict_buy_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html', error='กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')

        # --- Firebase Auth (production) ---
        if not config.USE_MOCK_AUTH:
            if not firebase_auth_available:
                return render_template('login.html',
                    error='Firebase ยังไม่เชื่อมต่อ — ตรวจสอบ firebase-service-account.json')
            if not config.FIREBASE_API_KEY:
                return render_template('login.html',
                    error='ยังไม่ได้ตั้งค่า FIREBASE_API_KEY (Web API Key)')

            import requests as http_requests
            try:
                resp = http_requests.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
                    f"?key={config.FIREBASE_API_KEY}",
                    json={
                        'email': f"{username}@cardss.local",
                        'password': password,
                        'returnSecureToken': True
                    },
                    timeout=10
                )
                data = resp.json()
                if 'localId' in data:
                    session['user_uid'] = data['localId']
                    session['username'] = username
                    session['id_token'] = data.get('idToken', '')
                    session['is_admin'] = _user_is_admin(data['localId'], username)
                    flash(f'ยินดีต้อนรับ {username}!', 'success')
                    if session['is_admin']:
                        return redirect(url_for('admin_dashboard'))
                    return redirect(url_for('predict_buy_page'))
                error_msg = data.get('error', {}).get('message', '')
                if 'EMAIL_NOT_FOUND' in error_msg or 'INVALID_PASSWORD' in error_msg or 'INVALID_LOGIN_CREDENTIALS' in error_msg:
                    return render_template('login.html', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
                return render_template('login.html', error=f'เกิดข้อผิดพลาด: {error_msg}')
            except Exception as e:
                print(f"[ERROR] Firebase Auth: {e}")
                return render_template('login.html', error='ไม่สามารถเชื่อมต่อ Firebase ได้')

        # --- Local mock (dev only) ---
        users = load_local_users()
        record = users.get(username)
        if record and record.get('password') == password:
            session['user_uid'] = f"local_{username}"
            session['username'] = username
            session['is_admin'] = _user_is_admin(session['user_uid'], username)
            flash(f'ยินดีต้อนรับ {username}!', 'success')
            if session['is_admin']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('predict_buy_page'))
        elif not record:
            return render_template('login.html', error='ไม่พบชื่อผู้ใช้นี้ กรุณาสมัครสมาชิกก่อน')
        else:
            return render_template('login.html', error='รหัสผ่านไม่ถูกต้อง')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """หน้าสมัครสมาชิก"""
    if 'user_uid' in session:
        return redirect(url_for('predict_buy_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validate
        if not username or not password:
            return render_template('register.html', error='กรุณากรอกข้อมูลให้ครบ')
        if len(username) < 3 or len(username) > 30:
            return render_template('register.html', error='ชื่อผู้ใช้ต้องมี 3–30 ตัวอักษร')
        if len(password) < 8:
            return render_template('register.html', error='รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร')
        if password != confirm:
            return render_template('register.html', error='รหัสผ่านไม่ตรงกัน')

        # --- Firebase Auth (production) ---
        if not config.USE_MOCK_AUTH:
            if not firebase_auth_available:
                return render_template('register.html',
                    error='Firebase ยังไม่เชื่อมต่อ — ตรวจสอบ firebase-service-account.json')
            try:
                user_record = firebase_auth.create_user(
                    email=f"{username}@cardss.local",
                    password=password,
                )
                if db:
                    db.collection('users').document(user_record.uid).set({
                        'username': username,
                        'email': user_record.email,
                        'created_at': firestore.SERVER_TIMESTAMP
                    })
                flash('สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
                return redirect(url_for('login'))
            except firebase_auth.EmailAlreadyExistsError:
                return render_template('register.html', error='ชื่อผู้ใช้นี้ถูกใช้แล้ว')
            except Exception as e:
                print(f"[ERROR] Firebase create_user: {e}")
                return render_template('register.html', error=f'เกิดข้อผิดพลาด: {e}')

        # --- Local mock (dev only) ---
        users = load_local_users()
        if username in users:
            return render_template('register.html', error='ชื่อผู้ใช้นี้ถูกใช้แล้ว')
        users[username] = {
            'password': password,
            'created_at': datetime.datetime.utcnow().isoformat() + 'Z'
        }
        save_local_users(users)
        flash('สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    """ออกจากระบบ"""
    session.clear()
    flash('ออกจากระบบสำเร็จ', 'success')
    return redirect(url_for('login'))


# ============================================================
# PAGE ROUTES (render template)
# ============================================================

@app.route('/predict/buy')
@login_required
def predict_buy_page():
    """แสดงฟอร์มพยากรณ์ซื้อ/ไม่ซื้อ"""
    return render_template('predict_buy.html', use_mock=config.USE_MOCK)


@app.route('/predict/fuel')
@login_required
@buy_result_required
def predict_fuel_page():
    """แสดงฟอร์มพยากรณ์ประเภทเชื้อเพลิง"""
    return render_template('predict_fuel.html')


@app.route('/result/buy')
@login_required
def result_buy():
    """แสดงผลพยากรณ์ซื้อ/ไม่ซื้อ"""
    result = session.get('buy_prediction')
    if not result:
        flash('กรุณาทำแบบประเมินก่อน', 'danger')
        return redirect(url_for('predict_buy_page'))
    return render_template('result_buy.html', result=result, reliability=model_reliability('buy'))


@app.route('/result/fuel')
@login_required
def result_fuel():
    """แสดงผลพยากรณ์ประเภทเชื้อเพลิง"""
    result = session.get('fuel_prediction')
    if not result:
        flash('กรุณาทำแบบประเมินประเภทเชื้อเพลิงก่อน', 'danger')
        return redirect(url_for('predict_fuel_page'))
    return render_template('result_fuel.html', result=result, reliability=model_reliability('fuel'))


def load_dataset_overview():
    """อ่านสรุปข้อมูลงานวิจัยที่คำนวณไว้แล้ว (data/dataset_overview.json)

    ไฟล์นี้สร้างโดย `analysis/dashboard_overview.py` จากแบบสอบถามทั้งชุดใน files/user_from/
    (28 ก.ย. 2569: ชุด n=630 — ภาพรวมข้อมูล ไม่ใช่ชุดเทรน BUY ซึ่งเป็น n=514) เก็บเฉพาะตัวเลขนับรวม ไม่มีข้อมูลรายบุคคล
    ที่ต้องคำนวณล่วงหน้าเพราะ CSV ต้นฉบับชื่อไฟล์ยาวเกินจนไม่มีบน PythonAnywhere
    ไม่มีไฟล์หรืออ่านไม่ได้ = คืน None ให้หน้าเว็บบอกว่าไม่มีข้อมูล (ห้ามเติมตัวเลขแทน)
    """
    data = _load_json(config.DATASET_OVERVIEW_PATH, None)
    if not isinstance(data, dict):
        return None
    for key in ('buy', 'fuel', 'age', 'income'):
        block = data.get(key)
        if not isinstance(block, dict) or sum(block.get('counts', [])) != block.get('n'):
            return None
    return data


def load_dashboard_groups():
    """ตัวเลขนับรวมต่อกลุ่ม (เพศ × การมีรถ × ประเภทที่สนใจ) สำหรับแดชบอร์ดกรองได้ — data/dashboard_groups.json

    สร้างโดย analysis/dashboard_groups.py · ไม่มีข้อมูลรายบุคคล · ตรวจว่าทุกกลุ่มรวมกันได้ n พอดี
    ไม่มีไฟล์/ไม่ผ่านการตรวจ = None (หน้าเว็บซ่อนส่วนกรอง ห้ามเติมตัวเลขแทน)
    """
    data = _load_json(config.DASHBOARD_GROUPS_PATH, None)
    if not isinstance(data, dict) or not isinstance(data.get('groups'), list) or not data['groups']:
        return None
    labels = data.get('labels') or {}
    dims = data.get('dims') or {}
    for g in data['groups']:
        if (g.get('gender') not in dims.get('gender', []) or g.get('car') not in dims.get('car', [])
                or g.get('fuel') not in dims.get('fuel', []) or not isinstance(g.get('n'), int)):
            return None
        for axis in ('age', 'income', 'budget', 'buy'):
            counts = g.get(axis)
            if (not isinstance(counts, list) or len(counts) != len(labels.get(axis, []))
                    or not all(isinstance(c, int) and c >= 0 for c in counts) or sum(counts) != g['n']):
                return None
    # ต้องตรงกับสรุปหลัก (dataset_overview.json) ไม่งั้นไม่แสดง ดีกว่าแสดงตัวเลขสองชุดที่ขัดกัน
    ov = load_dataset_overview()
    if ov:
        if sum(g['n'] for g in data['groups']) != ov['source']['rows']:
            return None
        for axis in ('age', 'income'):
            total = [sum(g[axis][i] for g in data['groups']) for i in range(len(ov[axis]['counts']))]
            if total != ov[axis]['counts']:
                return None
    return data


def _price_to_int(text):
    digits = ''.join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else None


def summarize_cars():
    """สรุปรถที่ระบบใช้แนะนำจาก data/cars.json (อ่านอย่างเดียว) — นับสด ณ ตอนเปิดหน้า"""
    cars = load_cars()
    summary = []
    for fuel_key in ('EV', 'Hybrid', 'ICE'):
        bucket = cars.get(fuel_key, []) or []
        prices = [p for p in (_price_to_int(c.get('price')) for c in bucket) if p]
        summary.append({
            'fuel': fuel_key,
            'count': len(bucket),
            'price_min': min(prices) if prices else None,
            'price_max': max(prices) if prices else None,
        })
    return summary


@app.route('/dashboard')
def dashboard():
    """ภาพรวมข้อมูลงานวิจัย — หน้าสาธารณะ ทุกคนเห็นเหมือนกัน ไม่ต้องล็อกอิน (25 ก.ย. 2569)

    อาจารย์ที่ปรึกษาเคาะให้ dashboard ไม่บังคับล็อกอิน และผู้ใช้เคาะให้เป็นหน้าสถิติทั่วไป
    แทนหน้าผลส่วนตัว (ผลส่วนตัวดูได้ที่ /result/buy, /result/fuel หลังล็อกอิน)
    ตัวเลขทุกตัวมาจาก dataset_overview.json + cars.json เท่านั้น ห้ามฝังตัวเลขใน template
    """
    return render_template(
        'dashboard.html',
        overview=load_dataset_overview(),
        car_summary=summarize_cars(),
        buy_reliability=model_reliability('buy'),   # จำนวนคนที่ใช้ฝึก BUY (ไม่พิมพ์ตายตัว) — 9 ต.ค. 2569
        groups=load_dashboard_groups(),            # แดชบอร์ดกรองได้ — 9 ต.ค. 2569
    )


# ============================================================
# API ROUTES (รับ-ส่งข้อมูล)
# ============================================================

def _current_uid():
    return session.get('user_uid', '')


def _form_fields(keys):
    return {k: request.form.get(k, '') for k in keys}


@app.route('/api/predict/buy', methods=['POST'])
@login_required
def api_predict_buy():
    """รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → redirect ไปหน้าผลลัพธ์"""
    # 29 ก.ย. 2569: buy_model.pkl เทรนจากชุดเดิม n=500 เฉพาะคำถามทั่วไป — ถามเฉพาะช่องที่โมเดลใช้จริง
    # purpose / concern เลือกได้หลายข้อ (multi-hot) · concern ว่างได้ (คนไม่มีรถไม่ได้ตอบในแบบสอบถาม)
    input_data = _form_fields(['age', 'children', 'education', 'occupation', 'family_size',
                               'housing_type', 'parking', 'budget'])
    input_data['purpose'] = request.form.getlist('purpose')
    input_data['concern'] = request.form.getlist('concern')

    valid, err = validate_buy(input_data)
    if not valid:
        flash(err, 'danger')
        return redirect(url_for('predict_buy_page'))

    result = predict_buy(input_data)
    session['buy_prediction'] = result
    session['buy_result'] = result['result']
    session['buy_input_data'] = input_data
    save_prediction_to_firebase(_current_uid(), 'buy', input_data, result)
    return redirect(url_for('result_buy'))


@app.route('/api/predict/fuel', methods=['POST'])
@login_required
@buy_result_required
def api_predict_fuel():
    """รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → redirect ไปหน้าผลลัพธ์"""
    # 27 ก.ย. 2569: ถามเฉพาะช่องที่ fuel_model.pkl (ข้อมูลชุด n=630 ตั้งแต่ 28 ก.ย.) ใช้จริง
    # prev_car / priority เลือกได้หลายข้อ (multi-hot) · ไม่คำนวณ nep_score และไม่ดึงคำตอบกลุ่ม EV
    # จากหน้า buy อีกแล้ว (แบบสอบถามไม่มีคำถาม NEP / จุดชาร์จ / ต้นทุนรวม / สิทธิประโยชน์)
    input_data = _form_fields(['usage_type', 'frequency', 'distance', 'tech_env_concern'])
    input_data['prev_car'] = request.form.getlist('prev_car')
    input_data['priority'] = request.form.getlist('priority')

    valid, err = validate_fuel(input_data)
    if not valid:
        flash(err, 'danger')
        return redirect(url_for('predict_fuel_page'))

    result = predict_fuel(input_data)
    session['fuel_prediction'] = result
    session['fuel_input_data'] = input_data
    save_prediction_to_firebase(_current_uid(), 'fuel', input_data, result)
    return redirect(url_for('result_fuel'))


@app.route('/api/dashboard')
def api_dashboard():
    """ข้อมูลภาพรวมงานวิจัยแบบ JSON — ชุดเดียวกับหน้า /dashboard (สาธารณะ)

    25 ก.ย. 2569: เลิกคืนผลส่วนตัวของผู้ใช้ และตัด `cost_comparison` ที่เป็นตัวเลขฝังตายตัว
    (800/2200/3800 ฯลฯ) ออก เพราะไม่มีแหล่งที่มาในโปรเจกต์
    """
    overview = load_dataset_overview()
    return jsonify({
        'source': 'dataset_overview' if overview else 'unavailable',
        'overview': overview,
        'cars': summarize_cars(),
    })


# ============================================================
# CAR DATABASE — โหลดจาก data/cars.json (admin แก้ได้)
# ============================================================


def _numbers(text):
    """ดึงตัวเลขทุกตัวจากข้อความ เช่น '~800 ฿/เดือน' → [800] · '51,000–58,500' → [51000, 58500]"""
    return [int(n.replace(',', '')) for n in re.findall(r'\d[\d,]*', str(text or ''))]


def build_cost_table(car_db):
    """ตารางค่าใช้จ่ายต่อเดือนในหน้ารถแนะนำ — คำนวณจาก cars.json ล้วน (4 ต.ค. 2569 ผู้ใช้เลือกแบบ ก)
    เดิม template พิมพ์ตัวเลขตายตัว (ขัดกฎห้ามแต่งตัวเลข) · ใช้เฉพาะแถวที่มีข้อมูลรายรุ่นจริง:
    monthly_cost (ค่าน้ำมัน/ค่าไฟ) และ insurance_class1 (เบี้ยต่อปี ÷ 12) · แสดงช่วงต่ำสุด–สูงสุดของรุ่นในประเภท
    ค่าบำรุงรักษาไม่มีในข้อมูลรถ จึงไม่แสดง"""
    def rng(lo, hi):
        return f'~{lo:,}' if lo == hi else f'~{lo:,}–{hi:,}'

    rows = {'energy': {}, 'insurance': {}}
    total = {}
    for key in ('EV', 'Hybrid', 'ICE'):
        energy = [n for c in car_db.get(key, []) for n in _numbers(c.get('monthly_cost'))[:1]]
        ins = [n for c in car_db.get(key, []) for n in _numbers(c.get('insurance_class1'))]
        if not energy or not ins:
            return None
        e_lo, e_hi = min(energy), max(energy)
        i_lo, i_hi = round(min(ins) / 12), round(max(ins) / 12)
        rows['energy'][key] = rng(e_lo, e_hi)
        rows['insurance'][key] = rng(i_lo, i_hi)
        total[key] = rng(e_lo + i_lo, e_hi + i_hi)
    return {
        'rows': [('ค่าน้ำมัน / ค่าไฟ', rows['energy']),
                 ('เบี้ยประกันชั้น 1 (เบี้ยต่อปี ÷ 12)', rows['insurance'])],
        'total': total,
        'note': 'คำนวณจากข้อมูลรถแต่ละรุ่นในระบบ แสดงเป็นช่วงต่ำสุด–สูงสุดของรุ่นในประเภทนั้น · ยังไม่รวมค่าบำรุงรักษา',
    }


# งบที่ตอบในฟอร์ม BUY → ราคาสูงสุดที่ยังอยู่ในงบ (None = ไม่จำกัด) · ค่าต้องตรง validators.ALLOWED['budget']
BUDGET_MAX = {'lt500000': 500000, '500001-800000': 800000, '800001-1200000': 1200000,
              '1200001-1500000': 1500000, '1500000+': None}
BUDGET_TH = {'lt500000': 'ต่ำกว่า 500,000 บาท', '500001-800000': '500,001–800,000 บาท',
             '800001-1200000': '800,001–1,200,000 บาท', '1200001-1500000': '1,200,001–1,500,000 บาท',
             '1500000+': 'มากกว่า 1,500,000 บาท'}


def sort_cars_by_budget(car_db, budget):
    """รุ่นที่ราคาอยู่ในงบขึ้นก่อน (คงลำดับเดิมใน cars.json) แล้วตามด้วยรุ่นที่เกินงบ ติด over_budget=True
    4 ต.ค. 2569 ผู้ใช้สั่ง (ทดสอบแบบผู้ใช้จริง ข้อ 1): ตอบงบไว้แล้วแต่หน้ารถแนะนำไม่สนงบ
    ไม่ใช่ส่วนของโมเดล — โมเดลเลือก "ประเภท" · งบใช้แค่จัดลำดับรุ่นในประเภท · ไม่รู้งบ = คืนลำดับเดิม"""
    if budget not in BUDGET_MAX:
        return car_db
    cap = BUDGET_MAX[budget]
    out = {}
    for key, cars in car_db.items():
        within, over, unknown = [], [], []
        for car in cars or []:
            price = _price_to_int(car.get('price'))
            if not price:
                unknown.append(car)            # ไม่รู้ราคา = ไม่อ้างว่าอยู่ในงบ ไว้ท้ายสุด ไม่ติดป้าย (Codex #55)
            elif cap is not None and price > cap:
                over.append(dict(car, over_budget=True))
            else:
                within.append(car)
        out[key] = within + over + unknown
    return out


@app.route('/recommend')
@login_required
def recommend():
    """หน้าแนะนำรถยนต์ตามประเภทเชื้อเพลิงที่โมเดลพยากรณ์"""
    fuel_pred = session.get('fuel_prediction')
    if not fuel_pred:
        flash('กรุณาทำแบบประเมินประเภทเชื้อเพลิงก่อน', 'danger')
        return redirect(url_for('predict_fuel_page'))

    # แปลงผลพยากรณ์เป็น key ของ CAR_DATABASE
    result_text = fuel_pred.get('result', '')
    if 'EV' in result_text or 'ไฟฟ้า' in result_text:
        fuel_key = 'EV'
    elif 'ไฮบริด' in result_text or 'Hybrid' in result_text:
        fuel_key = 'Hybrid'
    else:
        fuel_key = 'ICE'

    car_db = load_cars()
    budget = (session.get('buy_input_data') or {}).get('budget')
    all_cars = sort_cars_by_budget(car_db, budget)
    recommended_cars = all_cars.get(fuel_key, [])[:5]

    return render_template('recommend.html',
                           fuel_key=fuel_key,
                           fuel_pred=fuel_pred,
                           recommended_cars=recommended_cars,
                           all_cars=all_cars,
                           cost_table=build_cost_table(car_db),
                           budget_th=BUDGET_TH.get(budget))


# ============================================================
# ADMIN ROUTES
# ============================================================

def _admin_credentials_ok(username, password):
    """
    ตรวจรหัสผ่าน admin (2026-08-28)

    รองรับทั้งแบบ hash และข้อความธรรมดา ตามที่ config โหลดมาได้
    ถ้าไม่ได้ตั้งรหัสไว้เลย จะคืน False เสมอ — ไม่มีรหัสเริ่มต้นให้เดา
    """
    if not config.ADMIN_LOGIN_ENABLED:
        return False
    if username != config.ADMIN_USERNAME:
        return False
    if config.ADMIN_PASSWORD_HASH:
        from werkzeug.security import check_password_hash
        return check_password_hash(config.ADMIN_PASSWORD_HASH, password)
    # เทียบแบบ constant-time กันการเดาจากเวลาที่ใช้ตอบ
    import hmac
    return hmac.compare_digest(config.ADMIN_PASSWORD_PLAIN or '', password)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        if _admin_credentials_ok(u, p):
            session['is_admin'] = True
            session['admin_username'] = u
            flash('เข้าสู่ระบบผู้ดูแลสำเร็จ', 'success')
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
    warn = None if config.ADMIN_LOGIN_ENABLED else (
        'ยังไม่ได้ตั้งรหัสผ่านผู้ดูแลระบบ — เปิด terminal แล้วรัน  python set_admin_password.py')
    return render_template('admin/login.html', warn=warn)


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_username', None)
    flash('ออกจากระบบผู้ดูแลแล้ว', 'success')
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    users = load_local_users()
    cars = load_cars()
    stats = {
        'user_count': len(users),
        'car_count': sum(len(v) for v in cars.values()),
        'car_by_type': {k: len(v) for k, v in cars.items()},
    }
    return render_template('admin/dashboard.html', stats=stats)


# ---------- Users ----------
def _list_firebase_users(query=''):
    """List users from Firebase Auth, merge with Firestore user docs"""
    if not firebase_auth_available:
        return []
    rows = []
    try:
        firestore_users = {}
        if db:
            for doc in db.collection('users').stream():
                firestore_users[doc.id] = doc.to_dict()
        for u in firebase_auth.list_users().iterate_all():
            email = u.email or ''
            username = email.split('@')[0] if email else u.uid
            if query and query not in username.lower() and query not in email.lower():
                continue
            fs = firestore_users.get(u.uid, {})
            created_ms = u.user_metadata.creation_timestamp if u.user_metadata else None
            created = datetime.datetime.fromtimestamp(created_ms / 1000).isoformat(timespec='seconds') if created_ms else '-'
            rows.append({
                'uid': u.uid,
                'username': fs.get('username', username),
                'email': email,
                'created_at': created,
                'disabled': u.disabled,
            })
    except Exception as e:
        print(f"[ERROR] list_firebase_users: {e}")
    rows.sort(key=lambda r: r['username'])
    return rows


@app.route('/admin/users')
@admin_required
def admin_users():
    q = request.args.get('q', '').strip().lower()
    if not config.USE_MOCK_AUTH:
        rows = _list_firebase_users(q)
    else:
        users = load_local_users()
        rows = []
        for username, rec in users.items():
            if q and q not in username.lower():
                continue
            rows.append({
                'uid': f'local_{username}',
                'username': username,
                'email': '-',
                'created_at': rec.get('created_at', '-'),
                'disabled': False,
            })
        rows.sort(key=lambda r: r['username'])
    return render_template('admin/users.html', users=rows, q=q,
                           source='firebase' if not config.USE_MOCK_AUTH else 'local')


@app.route('/admin/users/delete/<uid>', methods=['POST'])
@admin_required
def admin_users_delete(uid):
    if not config.USE_MOCK_AUTH and firebase_auth_available:
        try:
            firebase_auth.delete_user(uid)
            if db:
                db.collection('users').document(uid).delete()
            flash(f'ลบผู้ใช้ {uid} แล้ว', 'success')
        except Exception as e:
            print(f"[ERROR] delete_user: {e}")
            flash(f'ลบไม่สำเร็จ: {e}', 'danger')
    else:
        username = uid.replace('local_', '', 1)
        users = load_local_users()
        if username in users:
            users.pop(username)
            save_local_users(users)
            flash(f'ลบผู้ใช้ {username} แล้ว', 'success')
        else:
            flash('ไม่พบผู้ใช้นี้', 'danger')
    return redirect(url_for('admin_users'))


# ---------- Cars ----------
@app.route('/admin/explain')
@admin_required
def admin_explain():
    """
    หน้า admin: อธิบายว่าโมเดล BUY ตัดสินแบบนั้นเพราะอะไร (2026-08-28)

    เลือกผลพยากรณ์ที่บันทึกไว้ใน Firestore มาวิเคราะห์ได้ ถ้าไม่มี Firestore
    จะถอยไปใช้ผลล่าสุดใน session ของเบราว์เซอร์นี้แทน

    ⚠️ อธิบายเฉพาะ BUY เท่านั้น — ห้ามทำให้ FUEL (ดู models/explainer.py)
    """
    from models.explainer import explain_buy

    records, source = [], 'session'
    if db:
        try:
            docs = (db.collection('predictions')
                    .order_by('created_at', direction=firestore.Query.DESCENDING)
                    .limit(50)
                    .stream())
            # กรอง type ใน Python ไม่ใช่ใน query — เลี่ยงการต้องสร้าง composite index เพิ่ม
            for d in docs:
                item = d.to_dict()
                if item.get('type') != 'buy':
                    continue
                records.append({
                    'id': d.id,
                    'user_id': item.get('user_id', ''),
                    'result': item.get('result', ''),
                    'created_at': item.get('created_at'),
                    'input_data': item.get('input_data') or {},
                })
            source = 'firestore'
        except Exception as e:
            print(f"[ERROR] admin_explain read failed: {e}")

    selected_id = request.args.get('id') or (records[0]['id'] if records else None)
    chosen = next((r for r in records if r['id'] == selected_id), None)

    input_data = chosen['input_data'] if chosen else session.get('buy_input_data')
    exp = explain_buy(input_data) if input_data else None

    return render_template('admin/explain.html', exp=exp, records=records,
                           selected_id=selected_id, chosen=chosen,
                           source=source, has_input=bool(input_data))


@app.route('/admin/cars')
@admin_required
def admin_cars():
    cars = load_cars()
    return render_template('admin/cars.html', cars=cars)


@app.route('/admin/cars/add', methods=['GET', 'POST'])
@admin_required
def admin_cars_add():
    if request.method == 'POST':
        fuel_type = request.form.get('fuel_type')
        if fuel_type not in ('EV', 'Hybrid', 'ICE'):
            flash('ประเภทเชื้อเพลิงไม่ถูกต้อง', 'danger')
            return redirect(url_for('admin_cars_add'))
        car = _car_from_form(request.form)
        car['id'] = uuid.uuid4().hex[:12]
        cars = load_cars()
        cars.setdefault(fuel_type, []).append(car)
        save_cars(cars)
        flash(f'เพิ่ม {car["brand"]} {car["model"]} แล้ว', 'success')
        return redirect(url_for('admin_cars'))
    return render_template('admin/car_form.html', mode='add', car=None, fuel_type='EV')


@app.route('/admin/cars/edit/<fuel_type>/<int:index>', methods=['GET', 'POST'])
@admin_required
def admin_cars_edit(fuel_type, index):
    cars = load_cars()
    bucket = cars.get(fuel_type, [])
    if index < 0 or index >= len(bucket):
        flash('ไม่พบรถที่ต้องการแก้ไข', 'danger')
        return redirect(url_for('admin_cars'))
    if request.method == 'POST':
        updated = _car_from_form(request.form)
        updated['id'] = bucket[index].get('id') or uuid.uuid4().hex[:12]
        new_type = request.form.get('fuel_type', fuel_type)
        if new_type != fuel_type and new_type in ('EV', 'Hybrid', 'ICE'):
            bucket.pop(index)
            cars.setdefault(new_type, []).append(updated)
        else:
            bucket[index] = updated
        save_cars(cars)
        flash('บันทึกการแก้ไขแล้ว', 'success')
        return redirect(url_for('admin_cars'))
    return render_template('admin/car_form.html', mode='edit',
                           car=bucket[index], fuel_type=fuel_type, index=index)


@app.route('/admin/cars/delete/<fuel_type>/<int:index>', methods=['POST'])
@admin_required
def admin_cars_delete(fuel_type, index):
    cars = load_cars()
    bucket = cars.get(fuel_type, [])
    if 0 <= index < len(bucket):
        removed = bucket.pop(index)
        save_cars(cars)
        flash(f'ลบ {removed.get("brand","")} {removed.get("model","")} แล้ว', 'success')
    else:
        flash('ไม่พบรถที่ต้องการลบ', 'danger')
    return redirect(url_for('admin_cars'))


def _car_from_form(form):
    """แปลงฟอร์มเป็น dict รถ"""
    highlights = [h.strip() for h in form.get('highlights', '').split('\n') if h.strip()]
    car = {
        'brand': form.get('brand', '').strip(),
        'model': form.get('model', '').strip(),
        'price': form.get('price', '').strip(),
        'range_km': form.get('range_km', '').strip(),
        'image': form.get('image', '').strip(),
        'image_icon': form.get('image_icon', 'bi-car-front-fill').strip(),
        'color': form.get('color', '#1A1A1A').strip(),
        'highlights': highlights,
        'monthly_cost': form.get('monthly_cost', '').strip(),
        'best_for': form.get('best_for', '').strip(),
        'insurance_class1': form.get('insurance_class1', '').strip(),
    }
    # fuel_consumption (flexible)
    fc = {}
    for k in ('km_per_liter', 'km_per_kwh', 'baht_per_km', 'wltp_kwh_100km'):
        v = form.get(f'fc_{k}', '').strip()
        if v:
            fc[k] = v
    if fc:
        car['fuel_consumption'] = fc
    return car


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(e):
    """7 ต.ค. 2569: หน้าแจ้งข้อผิดพลาดแบบดีไซน์ใหม่ + สถานะ 404 จริง (เดิม flash แล้วเด้งกลับหน้าแรก)
    ไฟล์ /static/ ที่หาย (รูป/CSS/JS) ได้ข้อความสั้นแทนหน้า HTML ทั้งหน้า (Codex #57)"""
    if request.path.startswith('/static/'):
        return 'Not Found', 404, {'Content-Type': 'text/plain; charset=utf-8'}
    return render_template('error.html', code=404, title='ไม่พบหน้าที่คุณหา',
                           message='ลิงก์อาจพิมพ์ผิด หรือหน้านี้ถูกย้ายไปแล้ว ลองกลับไปเริ่มที่หน้าแรก'), 404


@app.errorhandler(500)
def internal_error(e):
    """หน้าแจ้งข้อผิดพลาดภายในระบบ · ถ้าวาดหน้าแบบใหม่ไม่ได้ (เช่น template เสีย) ใช้ข้อความธรรมดาแทน ไม่ให้พังซ้ำ"""
    try:
        return render_template('error.html', code=500, title='ระบบขัดข้องชั่วคราว',
                               message='ขออภัย เกิดข้อผิดพลาดภายในระบบ คำตอบที่กรอกไว้ยังจำอยู่ในเครื่องของคุณ ลองใหม่อีกครั้งในอีกสักครู่'), 500
    except Exception:
        return 'ระบบขัดข้องชั่วคราว กรุณาลองใหม่อีกครั้ง', 500


# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    print("=" * 50)
    print(" CarDSS — Car Purchase Decision Support System")
    print(f" Mock Mode: {'ON' if config.USE_MOCK else 'OFF'}")
    print(f" Firebase:  {'Connected' if db else 'Not connected (local mode)'}")
    print(f" Auth:      {'MOCK (local file)' if config.USE_MOCK_AUTH else 'Firebase Auth'}")
    if not config.USE_MOCK_AUTH and not config.FIREBASE_API_KEY:
        print(" [!] FIREBASE_API_KEY not set - login/register will not work")
        print("     Firebase Console -> Project Settings -> General -> Web API Key")
        print("     Then set env: FIREBASE_API_KEY=AIza...")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
