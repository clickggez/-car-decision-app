# -*- coding: utf-8 -*-
"""
ตั้ง / เปลี่ยนรหัสผ่านผู้ดูแลระบบ (admin) — CarDSS
=================================================
เขียนไฟล์ admin_credentials.json ซึ่ง git ไม่ติดตาม (อยู่ใน .gitignore)
เก็บเฉพาะ hash ของรหัสผ่าน ไม่เก็บตัวรหัสจริง

วิธีใช้
    cd car-dss
    python set_admin_password.py                 # พิมพ์รหัสเอง
    python set_admin_password.py --random        # ให้สุ่มรหัสแข็งแรงให้

⚠️ ไฟล์นี้ไม่ขึ้น git ดังนั้นบนเซิร์ฟเวอร์ (PythonAnywhere) ต้องทำอย่างใดอย่างหนึ่ง
   - รันสคริปต์นี้บนเซิร์ฟเวอร์อีกครั้ง (ผ่าน Bash console) หรือ
   - ตั้ง environment variable ADMIN_PASSWORD ไว้แทน
"""

import argparse
import getpass
import json
import os
import secrets
import string
import sys

sys.stdout.reconfigure(encoding='utf-8')

from werkzeug.security import generate_password_hash

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'admin_credentials.json')
MIN_LEN = 8


def random_password(n=16):
    """สุ่มรหัสผ่านที่อ่านออกและพิมพ์ง่าย (ตัดอักขระที่สับสน เช่น l 1 O 0)"""
    pool = ''.join(c for c in string.ascii_letters + string.digits if c not in 'lI1O0')
    return ''.join(secrets.choice(pool) for _ in range(n))


def main():
    ap = argparse.ArgumentParser(description='ตั้งรหัสผ่าน admin ของ CarDSS')
    ap.add_argument('--username', default=None, help='ชื่อผู้ใช้ admin (ค่าเดิม/ค่าเริ่มต้น: admin)')
    ap.add_argument('--random', action='store_true', help='ให้สุ่มรหัสผ่านให้')
    args = ap.parse_args()

    current = {}
    if os.path.exists(DEST):
        try:
            with open(DEST, encoding='utf-8') as fh:
                current = json.load(fh)
        except (ValueError, OSError):
            current = {}

    username = args.username or current.get('username') or 'admin'

    if args.random:
        password = random_password()
        print()
        print('  รหัสผ่านที่สุ่มให้:  %s' % password)
        print('  >>> จดเก็บไว้ให้ดี ระบบไม่เก็บตัวรหัสจริง ดูย้อนหลังไม่ได้ <<<')
        print()
    else:
        password = getpass.getpass('รหัสผ่านใหม่: ')
        if len(password) < MIN_LEN:
            print('รหัสผ่านสั้นเกินไป ต้องอย่างน้อย %d ตัวอักษร' % MIN_LEN)
            return 1
        if password != getpass.getpass('พิมพ์รหัสผ่านอีกครั้ง: '):
            print('รหัสผ่านสองครั้งไม่ตรงกัน')
            return 1

    with open(DEST, 'w', encoding='utf-8') as fh:
        json.dump({'username': username,
                   'password_hash': generate_password_hash(password)},
                  fh, ensure_ascii=False, indent=2)

    print('บันทึกแล้ว: %s' % DEST)
    print('ชื่อผู้ใช้: %s' % username)
    print('ไฟล์นี้ git ไม่ติดตาม จึงไม่ขึ้น GitHub')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
