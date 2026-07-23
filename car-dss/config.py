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
# ============================================================
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
