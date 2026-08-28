"""
CarDSS — Configuration
Firebase config, secret keys, model flags
"""

import os

# ============================================================
# Flask
# ============================================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'cardss-dev-secret-change-in-production')

# ============================================================
# ML Model Flag
# เปลี่ยนเป็น False เมื่อมีโมเดลจริงพร้อมใช้งาน (.pkl)
# ============================================================
USE_MOCK = False

# ============================================================
# Auth Flag — False = ใช้ Firebase Auth จริง (ไม่มี local fallback)
# ============================================================
USE_MOCK_AUTH = False

# ============================================================
# Firebase
# ============================================================
# วิธีใช้งาน:
# 1. ไปที่ Firebase Console → Project Settings → Service Accounts
# 2. สร้าง private key (JSON) แล้ววางไว้ใน root ของ project
# 3. ตั้งชื่อไฟล์ว่า firebase-service-account.json
# 4. หรือกำหนด path ผ่าน environment variable

FIREBASE_CREDENTIALS_PATH = os.environ.get(
    'FIREBASE_CREDENTIALS_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firebase-service-account.json')
)

# Firebase Web API Key (สำหรับ REST Auth)
FIREBASE_API_KEY = os.environ.get('FIREBASE_API_KEY', 'AIzaSyBmk-T6RUAnYdYKm12Mw6JG4qo9HqkdStY')

# Firebase project ID
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'cardss-e678f')

# ============================================================
# Model Paths
# ============================================================
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
BUY_MODEL_PATH = os.path.join(MODEL_DIR, 'buy_model.pkl')
FUEL_MODEL_PATH = os.path.join(MODEL_DIR, 'fuel_model.pkl')

# ============================================================
# Data dir (admin-editable JSON)
# ============================================================
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CARS_JSON_PATH = os.path.join(DATA_DIR, 'cars.json')
USERS_LOCAL_JSON_PATH = os.path.join(DATA_DIR, 'users_local.json')

# ============================================================
# Admin credentials (แยกจากผู้ใช้ทั่วไป)
# ------------------------------------------------------------
# ⚠️ แก้ 2026-08-28: เดิมรหัสผ่าน 'admin123' เขียนตรง ๆ อยู่ในไฟล์นี้
#    ซึ่ง git ติดตามและ push ขึ้น GitHub ตั้งแต่ commit แรก
#    เว็บ deploy จริงบนอินเทอร์เน็ตแล้ว (PythonAnywhere) = ใครอ่าน repo ได้ก็เข้า admin ได้
#
# ลำดับการอ่านค่า (ตัวแรกที่เจอชนะ):
#   1. env ADMIN_PASSWORD_HASH  — hash (ปลอดภัยที่สุด ใช้บนเซิร์ฟเวอร์)
#   2. env ADMIN_PASSWORD       — ข้อความธรรมดา (สะดวกตอนตั้งค่าบน PythonAnywhere)
#   3. ไฟล์ admin_credentials.json ข้าง ๆ ไฟล์นี้ (git ไม่ติดตาม — วิธีหลักบนเครื่องตัวเอง)
#   4. ไม่เจออะไรเลย -> ปิดการล็อกอิน admin ทั้งหมด (ไม่มีรหัสเริ่มต้นให้เดาอีกแล้ว)
#
# ตั้ง/เปลี่ยนรหัส:  python set_admin_password.py
# ============================================================
ADMIN_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'admin_credentials.json')


def _load_admin_credentials():
    """คืน (username, password_hash, password_plain) — ค่าที่ไม่ได้ใช้จะเป็น None"""
    user = os.environ.get('ADMIN_USERNAME')
    pw_hash = os.environ.get('ADMIN_PASSWORD_HASH')
    pw_plain = os.environ.get('ADMIN_PASSWORD')
    if pw_hash or pw_plain:
        return (user or 'admin'), pw_hash, pw_plain

    try:
        import json
        with open(ADMIN_CREDENTIALS_PATH, encoding='utf-8') as fh:
            data = json.load(fh)
        return (user or data.get('username') or 'admin'), data.get('password_hash'), None
    except FileNotFoundError:
        print('[WARNING] ไม่พบ admin_credentials.json และไม่ได้ตั้ง env '
              '-> ปิดการล็อกอิน admin (ตั้งรหัสด้วย: python set_admin_password.py)')
    except (ValueError, OSError) as e:
        print(f'[WARNING] อ่าน admin_credentials.json ไม่ได้: {e} -> ปิดการล็อกอิน admin')
    return (user or 'admin'), None, None


ADMIN_USERNAME, ADMIN_PASSWORD_HASH, ADMIN_PASSWORD_PLAIN = _load_admin_credentials()
ADMIN_LOGIN_ENABLED = bool(ADMIN_PASSWORD_HASH or ADMIN_PASSWORD_PLAIN)
