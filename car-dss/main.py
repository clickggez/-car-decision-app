"""
CarDSS — Firebase Functions (2nd gen, Cloud Run) entry point
ห่อ Flask app เดิม (app.py) ให้รันบน Cloud Functions/Cloud Run ผ่าน Firebase CLI
โดยไม่ต้องแก้ app.py — ใช้สำหรับ `firebase deploy --only functions` เท่านั้น
รันเว็บแบบปกติเพื่อ dev ในเครื่องให้ใช้ `python app.py` เหมือนเดิม
"""

from firebase_functions import https_fn, options
from app import app as flask_app

options.set_global_options(max_instances=10, region="asia-southeast1")


@https_fn.on_request()
def cardss(req: https_fn.Request) -> https_fn.Response:
    with flask_app.request_context(req.environ):
        return flask_app.full_dispatch_request()
