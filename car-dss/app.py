"""
CarDSS — Flask Main Application
ระบบสนับสนุนการตัดสินใจซื้อรถยนต์
"""

import os
import json
import uuid
import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)

import config
from models.predictor import predict_buy, predict_fuel
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
    """Decorator: ต้อง login ก่อนเข้าหน้านี้ (ใช้กับหน้าที่ต้องมีบัญชีจริงเท่านั้น)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_uid' not in session:
            flash('กรุณาเข้าสู่ระบบก่อน', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def session_required(f):
    """Decorator: ให้ผู้ใช้ทั่วไปเข้าใช้ระบบได้ทันทีโดยไม่ต้องล็อกอิน (23 ก.ย. 2569)

    ระบบนี้เป็น DSS แบบใช้ครั้งเดียวจบ การบังคับสมัครสมาชิกสร้าง friction เกินจำเป็น
    - ยังไม่มีตัวตนในเซสชัน → ออก guest uid ให้อัตโนมัติ (`guest_<random>`)
    - ผลวิเคราะห์ยังถูกบันทึกเข้า Firebase ด้วย uid นี้ ตามที่ผู้ใช้เคาะไว้ จึงแยกคนได้
    - guest ไม่มีสิทธิ์แอดมินเด็ดขาด (`is_admin` ไม่ถูกตั้งที่นี่) ฝั่งแอดมินยังใช้ admin_required เหมือนเดิม
    - ถ้าล็อกอินด้วยบัญชีจริงอยู่แล้ว จะใช้ uid ของบัญชีนั้น ไม่ถูกทับ
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_uid' not in session:
            session['user_uid'] = 'guest_' + uuid.uuid4().hex[:12]
            session['username'] = 'ผู้ใช้ทั่วไป'
            session['is_guest'] = True
        return f(*args, **kwargs)
    return decorated


def buy_result_required(f):
    """Decorator: ต้องผ่านผลลัพธ์ ซื้อ ก่อนเข้าหน้า predict_fuel (<<extend>>)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('buy_result') != 'ซื้อ':
            flash('กรุณาทำแบบประเมินซื้อ/ไม่ซื้อก่อน และผลลัพธ์ต้องเป็น "ซื้อ" จึงจะวิเคราะห์ประเภทเชื้อเพลิงได้', 'danger')
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


def get_dashboard_data_from_firebase(user_uid):
    """ดึงข้อมูล prediction ล่าสุดของ user สำหรับ Dashboard"""
    if not db:
        return None
    try:
        docs = (db.collection('predictions')
                .where('user_id', '==', user_uid)
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(10)
                .stream())
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[ERROR] Firebase read failed: {e}")
        return None


# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    """หน้าแรก Home"""
    return render_template('home.html')


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
@session_required
def predict_buy_page():
    """แสดงฟอร์มพยากรณ์ซื้อ/ไม่ซื้อ"""
    return render_template('predict_buy.html', use_mock=config.USE_MOCK)


@app.route('/predict/fuel')
@session_required
@buy_result_required
def predict_fuel_page():
    """แสดงฟอร์มพยากรณ์ประเภทเชื้อเพลิง"""
    return render_template('predict_fuel.html')


@app.route('/result/buy')
@session_required
def result_buy():
    """แสดงผลพยากรณ์ซื้อ/ไม่ซื้อ"""
    result = session.get('buy_prediction')
    if not result:
        flash('กรุณาทำแบบประเมินก่อน', 'danger')
        return redirect(url_for('predict_buy_page'))
    return render_template('result_buy.html', result=result)


@app.route('/result/fuel')
@session_required
def result_fuel():
    """แสดงผลพยากรณ์ประเภทเชื้อเพลิง"""
    result = session.get('fuel_prediction')
    if not result:
        flash('กรุณาทำแบบประเมินประเภทเชื้อเพลิงก่อน', 'danger')
        return redirect(url_for('predict_fuel_page'))
    return render_template('result_fuel.html', result=result)


@app.route('/dashboard')
@session_required
def dashboard():
    """แสดง Dashboard แผนภาพข้อมูล — ใช้ผลวิเคราะห์ล่าสุดของผู้ใช้จาก session

    ถ้ายังไม่เคยวิเคราะห์ ให้หน้าเว็บแสดงสถานะว่าง ห้ามแสดงค่าจำลองเป็นผลลัพธ์
    (บั๊กเดิม: dashboard.html ฝังค่า EV 78% ANN ไว้ตรง ๆ จนผู้ใช้เห็นผลของคนอื่น)
    """
    return render_template(
        'dashboard.html',
        fuel=session.get('fuel_prediction'),
        buy=session.get('buy_prediction'),
    )


# ============================================================
# API ROUTES (รับ-ส่งข้อมูล)
# ============================================================

def _current_uid():
    return session.get('user_uid', '')


def _form_fields(keys):
    return {k: request.form.get(k, '') for k in keys}


@app.route('/api/predict/buy', methods=['POST'])
@session_required
def api_predict_buy():
    """รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → redirect ไปหน้าผลลัพธ์"""
    input_data = _form_fields([
        'gender', 'age', 'children', 'education', 'occupation', 'family_size',
        'housing_type', 'housing_status', 'parking', 'income', 'budget', 'concern', 'purpose',
        # คำถามใหม่ 2026-08-01 (ต่อสายเข้าฟอร์มเว็บ 2026-08-09)
        # 3 ตัวแรกเป็นคำถามกลุ่ม EV ที่ predict_fuel ต้องใช้ด้วย — ถามที่นี่ครั้งเดียว
        # แล้วส่งต่อผ่าน session ไปหน้า fuel (ผู้ใช้ไม่ต้องตอบซ้ำ)
        'charging_access', 'tco_awareness', 'incentive_awareness',
        'intention', 'attitude', 'subjective_norm', 'pbc_financial',
    ])
    input_data['life_events'] = request.form.getlist('life_events')

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
@session_required
@buy_result_required
def api_predict_fuel():
    """รับข้อมูลฟอร์ม → ส่งเข้าโมเดล → redirect ไปหน้าผลลัพธ์"""
    input_data = _form_fields([
        'usage_type', 'frequency', 'distance', 'prev_car',
        'tech_env_concern', 'resale_maintenance_concern',
        # คำถามใหม่ 2026-08-01 (ต่อสายเข้าฟอร์มเว็บ 2026-08-09)
        'ev_exposure', 'range_anxiety',
        'nep_1', 'nep_2', 'nep_3', 'nep_4', 'nep_5',
    ])
    input_data['priority'] = request.form.getlist('priority')

    valid, err = validate_fuel(input_data)
    if not valid:
        flash(err, 'danger')
        return redirect(url_for('predict_fuel_page'))

    # NEP 5 ข้อ -> คะแนนเฉลี่ย (ข้อที่ 5 เป็น reverse-worded ต้องกลับคะแนนก่อน)
    # ตรรกะเดียวกับ train_models._nep_score เป๊ะ — ถ้าแก้ที่ใดที่หนึ่งต้องแก้ทั้งคู่
    nep_vals = [int(input_data['nep_' + str(i)]) for i in range(1, 6)]
    nep_vals[4] = 6 - nep_vals[4]
    input_data['nep_score'] = sum(nep_vals) / 5.0

    # 3 คำถามกลุ่ม EV ถามไปแล้วในหน้า buy — ดึงกลับมาใช้ ไม่ถามผู้ใช้ซ้ำ
    # (ผ่าน validate_buy มาแล้ว จึงไม่ต้อง validate ซ้ำ)
    prev = session.get('buy_input_data') or {}
    for k in ('charging_access', 'tco_awareness', 'incentive_awareness'):
        input_data[k] = prev.get(k, '')

    result = predict_fuel(input_data)
    session['fuel_prediction'] = result
    session['fuel_input_data'] = input_data
    save_prediction_to_firebase(_current_uid(), 'fuel', input_data, result)
    return redirect(url_for('result_fuel'))


@app.route('/api/dashboard')
@session_required
def api_dashboard():
    """ดึงข้อมูลสำหรับ Dashboard (JSON)"""
    user_uid = _current_uid()

    # ลองดึงจาก Firebase ก่อน
    firebase_data = get_dashboard_data_from_firebase(user_uid)

    if firebase_data:
        return jsonify({'source': 'firebase', 'data': firebase_data})

    # Fallback: ใช้ผลจริงใน session
    # 23 ก.ย. 2569: เลิกเติมค่าจำลองแทนผลที่ยังไม่มี — เดิมผู้ใช้ที่ยังไม่ได้วิเคราะห์
    # จะเห็น "EV 78% ANN (mock)" เหมือนเป็นผลของตัวเอง
    buy_pred = session.get('buy_prediction', {})
    fuel_pred = session.get('fuel_prediction', {})

    if not buy_pred and not fuel_pred:
        return jsonify({'source': 'empty', 'has_result': False})

    dashboard_data = {
        'source': 'session',
        'has_result': True,
        'buy_result': buy_pred.get('result'),
        'buy_confidence': buy_pred.get('confidence'),
        'buy_model': buy_pred.get('model_used'),
        'fuel_result': fuel_pred.get('result'),
        'fuel_scores': fuel_pred.get('scores'),
        'fuel_confidence': fuel_pred.get('confidence'),
        'fuel_model': fuel_pred.get('model_used'),
        'cost_comparison': {
            'labels': ['ค่าเชื้อเพลิง', 'ค่าบำรุงรักษา', 'ค่าประกัน'],
            'ev': [800, 500, 8500],
            'hybrid': [2200, 1200, 9000],
            'ice': [3800, 2000, 8000]
        },
    }

    return jsonify(dashboard_data)


# ============================================================
# CAR DATABASE — โหลดจาก data/cars.json (admin แก้ได้)
# ============================================================


@app.route('/recommend')
@session_required
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
    recommended_cars = car_db.get(fuel_key, [])[:5]
    all_cars = car_db

    return render_template('recommend.html',
                           fuel_key=fuel_key,
                           fuel_pred=fuel_pred,
                           recommended_cars=recommended_cars,
                           all_cars=all_cars)


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
    flash('ไม่พบหน้าที่ต้องการ', 'danger')
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_error(e):
    flash('เกิดข้อผิดพลาดภายในระบบ กรุณาลองใหม่อีกครั้ง', 'danger')
    return redirect(url_for('index'))


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
