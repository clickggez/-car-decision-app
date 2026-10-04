"""
check_deploy.py — เช็คว่าโค้ดขึ้นเว็บออนไลน์จริงหรือยัง

ที่มา: 23 ก.ย. 2569 — แก้โค้ด push แล้ว pull แล้ว แต่เว็บยังเป็นของเก่า
เสียเวลาไล่หาเป็นชั่วโมงกว่าจะรู้ว่าลืมกด Reload
สคริปต์นี้ยิงเข้าเว็บจริงจากนอกเครื่อง แล้วบอกตรง ๆ ว่าผ่านหรือไม่ผ่านตรงไหน

รัน:
    python tools/check_deploy.py                    # เช็คเว็บออนไลน์
    python tools/check_deploy.py --local            # เช็คเซิร์ฟเวอร์บนเครื่อง
    python tools/check_deploy.py --url http://...   # เช็ค URL ที่ระบุเอง

ไม่ต้องติดตั้งอะไรเพิ่ม ใช้ urllib ของ Python เอง
สคริปต์นี้ **อ่านอย่างเดียว** ไม่ส่งฟอร์ม จึงไม่มีข้อมูลทดสอบตกค้างใน Firebase
"""

import argparse
import json
import re
import os
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ONLINE = 'https://r4tt4.pythonanywhere.com'
LOCAL = 'http://127.0.0.1:5000'

TIMEOUT = 20
OK, FAIL, WARN = '[ ผ่าน ]', '[ ตก  ]', '[เตือน]'


def fetch(url):
    """คืน (status, html, redirect_to) — ไม่ตาม redirect เพื่อดูว่ามันเด้งไปไหน"""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={'User-Agent': 'CarDSS-deploy-check'})
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode('utf-8', 'replace'), None
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.code, '', e.headers.get('Location', '')
        return e.code, '', None
    except Exception as e:
        return None, f'!! เชื่อมต่อไม่ได้: {e}', None


class Report:
    def __init__(self):
        self.failed = []

    def check(self, name, passed, detail=''):
        mark = OK if passed else FAIL
        print(f'  {mark} {name}' + (f'  — {detail}' if detail else ''))
        if not passed:
            self.failed.append(name)
        return passed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--local', action='store_true', help='เช็คเซิร์ฟเวอร์บนเครื่องแทนเว็บออนไลน์')
    ap.add_argument('--url', help='เช็ค URL ที่ระบุเอง')
    args = ap.parse_args()

    base = args.url or (LOCAL if args.local else ONLINE)
    base = base.rstrip('/')

    print(f'\nเช็คเว็บ: {base}\n' + '=' * 60)

    r = Report()

    # --- 1. เว็บยังมีชีวิตอยู่ไหม ---
    status, html, _ = fetch(base + '/')
    if status is None:
        print(f'  {FAIL} เปิดหน้าแรกไม่ได้ — {html}')
        print('\nสรุป: เชื่อมต่อเว็บไม่ได้เลย ตรวจว่าเซิร์ฟเวอร์เปิดอยู่ไหม')
        return 2
    r.check('หน้าแรกเปิดได้', status == 200, f'status {status}')

    # --- 2. ชื่อระบบใหม่ขึ้นแล้วไหม (ดูว่าโค้ดรอบ 23 ก.ย. ขึ้นหรือยัง) ---
    r.check('ใช้ชื่อระบบใหม่ (ตามประเภทเชื้อเพลิง)',
            'ตามประเภทเชื้อเพลิง' in html)

    # --- 3. ข้อความที่สั่งตัดออก ต้องไม่กลับมา ---
    for banned in ('เขตบางขุนเทียน', 'Data Mining', 'SVM & ANN', 'Skeleton Mode'):
        r.check(f'ไม่มีข้อความ "{banned}" บนหน้าแรก', banned not in html)
    # 29 ก.ย. 2569: commit ตรงแต่หน้าเว็บยังเก่า (touch wsgi ไม่ติด ต้องกด Reload ในแท็บ Web)
    # เช็คว่า template ที่เสิร์ฟอยู่เป็นรุ่นใหม่จริง ไม่ใช่แค่ไฟล์บนดิสก์
    # 4 ต.ค. 2569 หน้าแรกดีไซน์ใหม่: ตัวเลขอยู่บนหินกิโล + ปุ่มระดับน้ำ · ส่วน "สายไหน" ถูกตัดออก
    r.check('หน้าแรกเป็น template รุ่นใหม่ (ตัวเลขข้อมูลอ่านสด)',
            'ข้อมูลตัวอย่าง</span><b>' in html and 'id="wl"' in html and 'สายไหน' not in html,
            'ถ้าตกแต่ commit ตรง = ยังไม่ได้ Reload ให้กดปุ่มในแท็บ Web')

    # --- 4. ปุ่มบนหน้าแรกต้องพาไปแบบประเมิน (ถ้ายังไม่ล็อกอิน route นั้นจะพาไป /login เอง) ---
    # ไม่นับจำนวนลิงก์เฉย ๆ (codex ค้านไว้ board #31 ว่าหลวมเกิน) ดูที่ตัวปุ่มจริง
    # รับ href ทั้ง "..." และ '...'
    anchors = [(m.group(2), t) for attrs, t in re.findall(r'<a\s([^>]*)>(.*?)</a>', html, re.S)
               for m in [re.search(r"""href\s*=\s*(["'])(.*?)\1""", attrs)] if m]
    cta = [href for href, text in anchors if 'เริ่มเลือกรถ' in text]
    r.check('ปุ่ม "เริ่มเลือกรถ" ชี้ไปหน้าแบบประเมิน',
            bool(cta) and all(urlsplit(h).path == '/predict/buy' for h in cta),
            f'ปุ่มชี้ไป {cta}' if cta else 'หาปุ่มเริ่มเลือกรถไม่เจอ')

    # --- 5. การพยากรณ์ต้องล็อกอิน (อาจารย์เคาะ 25 ก.ย. 2569) / dashboard เปิดได้ทุกคน ---
    for path in ('/predict/buy', '/result/buy', '/recommend'):
        st, _, loc = fetch(base + path)
        r.check(f'{path} ไม่ล็อกอิน = เด้งไป /login', st == 302 and urlsplit(loc or '').path == '/login',
                f'status {st}' + (f' -> {loc}' if loc else ''))
    st, dash, loc = fetch(base + '/dashboard')
    r.check('เข้า /dashboard ได้โดยไม่ล็อกอิน', st == 200,
            f'status {st}' + (f' -> {loc}' if loc else ''))

    # --- 6. dashboard ต้องเป็นภาพรวมข้อมูลจริง ไม่มีผลปลอม ---
    if st == 200:
        r.check('dashboard ไม่มีค่าจำลอง 78% / ค่าใช้จ่ายฝังตายตัว',
                '78.0%' not in dash and 'mockCosts' not in dash)
        r.check('dashboard แสดงภาพรวมข้อมูลงานวิจัย (มีไฟล์ dataset_overview.json บนเซิร์ฟเวอร์)',
                'id="statRespondents"' in dash and 'ยังไม่มีข้อมูลสรุป' not in dash)

    # --- 7. หน้าแอดมินต้องยังล็อกอยู่ ---
    st, _, loc = fetch(base + '/admin')
    r.check('หน้าแอดมินยังต้องล็อกอิน', st in (301, 302) and 'admin/login' in (loc or ''),
            f'status {st} -> {loc}')

    # --- 8. เว็บรันโค้ด commit เดียวกับที่เราเพิ่ง push หรือเปล่า ---
    # ด่านนี้แหละที่จะจับ "ลืมกด Reload" ได้ตรง ๆ แทนการเดาจากข้อความในหน้า
    st, body, _ = fetch(base + '/version')
    if st != 200:
        print(f'  {WARN} /version ยังไม่มีบนเซิร์ฟเวอร์ (status {st}) '
              f'— เวอร์ชันบนเว็บอาจเก่ากว่าที่คิด ข้ามการเทียบ commit')
    else:
        try:
            deployed = json.loads(body).get('commit', '?')
        except ValueError:
            deployed = '?'
        local = ''
        try:
            local = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
        except Exception:
            pass
        if not local:
            print(f'  {WARN} อ่าน commit ของเครื่องไม่ได้ — เว็บรันอยู่ที่ {deployed}')
        else:
            r.check('เว็บรัน commit เดียวกับเครื่องเรา', deployed == local,
                    f'เว็บ={deployed} เครื่อง={local}'
                    + ('' if deployed == local else '  <-- ยังไม่ได้ pull หรือยังไม่ได้ Reload'))

    print('=' * 60)
    if r.failed:
        print(f'\nไม่ผ่าน {len(r.failed)} ข้อ:')
        for name in r.failed:
            print(f'  - {name}')
        print('\nถ้าเพิ่ง push โค้ดใหม่แล้วยังไม่ผ่าน มักเป็นเพราะ "ยังไม่ได้กด Reload"')
        print('ดูวิธีแก้ทีละขั้นใน  วิธีเอาโค้ดขึ้นเว็บ.txt')
        return 1

    print('\nผ่านทุกข้อ — โค้ดขึ้นเว็บเรียบร้อยแล้ว')
    return 0


if __name__ == '__main__':
    sys.exit(main())
