# -*- coding: utf-8 -*-
"""
ตั้ง/ถอดสิทธิ์ผู้ดูแลระบบให้บัญชีผู้ใช้ปกติ — CarDSS (2026-08-28)
================================================================
พอตั้งแล้ว ผู้ใช้คนนั้นล็อกอินที่หน้า /login ตามปกติ
ระบบจะพาเข้าหน้าผู้ดูแลระบบให้เอง และมีเมนู "ผู้ดูแลระบบ" ขึ้นบนแถบด้านบน

วิธีใช้
    cd car-dss
    python make_admin.py ชื่อผู้ใช้           # ตั้งเป็น admin
    python make_admin.py ชื่อผู้ใช้ --remove  # ถอดสิทธิ์
    python make_admin.py --list              # ดูว่าใครเป็น admin บ้าง

ทำงานได้ทั้งโหมด Firebase และโหมด local (data/users_local.json)
"""

import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def _firebase():
    """คืน (db, auth) ถ้าเชื่อม Firebase ได้ ไม่งั้นคืน (None, None)"""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore, auth
        if not firebase_admin._apps:
            firebase_admin.initialize_app(
                credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH))
        return firestore.client(), auth
    except Exception as e:
        print('[info] ใช้ Firebase ไม่ได้ (%s) — จะใช้โหมด local แทน' % e)
        return None, None


def _local_users_path():
    return config.USERS_LOCAL_JSON_PATH


def _load_local():
    try:
        with open(_local_users_path(), encoding='utf-8') as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return {}


def _save_local(users):
    os.makedirs(os.path.dirname(_local_users_path()), exist_ok=True)
    with open(_local_users_path(), 'w', encoding='utf-8') as fh:
        json.dump(users, fh, ensure_ascii=False, indent=2)


def list_admins(db):
    found = False
    if db:
        for doc in db.collection('users').stream():
            d = doc.to_dict() or {}
            if d.get('role') == 'admin' or d.get('is_admin') is True:
                print('  [firebase] %s  (uid %s)' % (d.get('username', '?'), doc.id))
                found = True
    for name, rec in _load_local().items():
        if rec.get('is_admin') is True:
            print('  [local]    %s' % name)
            found = True
    if not found:
        print('  (ยังไม่มีใครเป็น admin)')


def set_admin(db, username, make):
    """คืน True ถ้าเปลี่ยนสำเร็จ"""
    if db:
        col = db.collection('users')
        try:    # API ใหม่ของ firestore — เลี่ยง DeprecationWarning
            from google.cloud.firestore_v1.base_query import FieldFilter
            q = col.where(filter=FieldFilter('username', '==', username))
        except ImportError:
            q = col.where('username', '==', username)
        docs = list(q.limit(1).stream())
        if docs:
            doc = docs[0]
            if make:
                doc.reference.update({'role': 'admin'})
            else:
                doc.reference.update({'role': 'user'})
            print('%s สิทธิ์ admin ให้ %s แล้ว (Firebase uid %s)'
                  % ('ตั้ง' if make else 'ถอด', username, doc.id))
            return True
        print('[info] ไม่พบ %s ใน Firebase — ลองหาในโหมด local' % username)

    users = _load_local()
    if username in users:
        users[username]['is_admin'] = bool(make)
        _save_local(users)
        print('%s สิทธิ์ admin ให้ %s แล้ว (local)'
              % ('ตั้ง' if make else 'ถอด', username))
        return True

    print('ไม่พบผู้ใช้ชื่อ "%s" — ต้องสมัครสมาชิกที่หน้าเว็บก่อน' % username)
    return False


def main():
    ap = argparse.ArgumentParser(description='ตั้ง/ถอดสิทธิ์ admin ให้บัญชีผู้ใช้')
    ap.add_argument('username', nargs='?', help='ชื่อผู้ใช้ที่ต้องการตั้ง')
    ap.add_argument('--remove', action='store_true', help='ถอดสิทธิ์แทนการตั้ง')
    ap.add_argument('--list', action='store_true', help='แสดงรายชื่อ admin ทั้งหมด')
    args = ap.parse_args()

    db, _ = _firebase()

    if args.list:
        print('รายชื่อผู้ดูแลระบบ:')
        list_admins(db)
        return 0

    if not args.username:
        ap.print_help()
        return 1

    ok = set_admin(db, args.username, not args.remove)
    if ok and not args.remove:
        print('ให้ %s ออกจากระบบแล้วล็อกอินใหม่ที่ /login สิทธิ์ถึงจะมีผล' % args.username)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
