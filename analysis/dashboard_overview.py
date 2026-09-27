"""
สร้างไฟล์สรุปข้อมูลงานวิจัยสำหรับหน้า Dashboard สาธารณะ (2026-09-25)

ที่มา: อาจารย์ที่ปรึกษาเคาะ 2026-09-25 ให้หน้า /dashboard เป็น "ภาพรวมข้อมูลงานวิจัย"
ที่ทุกคนเห็นเหมือนกัน ไม่ต้องล็อกอิน และ**ห้ามมีตัวเลขที่ไม่มีที่มา**
(เคยพลาดมาแล้ว: "EV 78%" และ score card 92/75/88/60 ที่ฝังไว้ใน HTML)

ทำไมต้องสร้างเป็นไฟล์แยก แทนที่จะให้เว็บอ่าน CSV เอง
  ไฟล์ CSV แบบสอบถามใน files/user_from/ ชื่อไทยยาวเกิน 255 ไบต์
  สร้างบน Linux ไม่ได้ (00-READ-FIRST §1) = บน PythonAnywhere ไม่มีไฟล์นี้
  จึงคำนวณที่เครื่องนี้ แล้วเก็บผล "เฉพาะตัวเลขนับรวม" ลง car-dss/data/dataset_overview.json
  ซึ่ง git ติดตามและไปถึงเซิร์ฟเวอร์ด้วย git pull (ไม่มีข้อมูลรายบุคคลในไฟล์นั้น)

ตัวเลขทุกตัวนับจากไฟล์เดียวใน files/user_from/
  ⚠️ 2026-09-28: ไฟล์นั้นคือชุด n=630 (n514 + EV 73 + ไฮบริด 43) → BUY n=630 / FUEL n=457
     FUEL บนเว็บเทรนจากชุดนี้ แต่ BUY บนเว็บเทรนจากชุด n=514 (ผู้ใช้เลือก) — dashboard จึงเป็น "ภาพรวมข้อมูล" ไม่ใช่ชุดเทรน BUY
  (ประวัติ) 2026-09-27: เปลี่ยนเป็นแบบสอบถามชุด n=514 (files/user_from/survey_2026-09-27_n514.csv) — เดิม 09-26 ใช้ชุด n=511
  และเลิกพึ่ง analysis/ablation.py (ผูกกับคอลัมน์ของข้อมูลชุดเดิม) — ใช้ตัวสร้างชุดข้อมูล
  ใน train_models.py โดยตรง ซึ่งดึงคอลัมน์ด้วยชื่อหัวคอลัมน์ ไม่ใช่ตำแหน่ง
  - BUY  : train_models.build_buy_xy()  (n=514)  label "4. ท่านมีแนวโน้มจะซื้อรถยนต์..."
  - FUEL : train_models.build_fuel_xy() (n=341)  label "5. หากต้องเลือกซื้อรถยนต์..." เฉพาะผู้ที่มีรถยนต์
  - อายุ / รายได้ : หัวคอลัมน์ "2. อายุ" / "8. รายได้เฉลี่ยต่อเดือน" (ผู้ตอบทุกคน)
ไม่มีการสุ่ม ไม่มีการเทรน ไม่แตะ .pkl — รันซ้ำได้เลขเดิมเสมอ

รัน:
    python analysis/dashboard_overview.py
ผล:
    car-dss/data/dataset_overview.json   (เว็บอ่านไฟล์นี้)
    stdout สรุปตัวเลข (เซฟเป็น analysis/dashboard_overview_2026-09-27.txt ให้ผู้ตรวจอ่าน)
"""
import os
import sys
import json
import hashlib
import contextlib
import io

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import train_models as tm  # noqa: E402  (import เพื่อใช้ตาราง map + ตัวสร้างชุดข้อมูลเท่านั้น ไม่เทรน)

OUT_PATH = os.path.join(_HERE, "..", "car-dss", "data", "dataset_overview.json")

BUY_ORDER = ["ซื้อ", "ไม่ซื้อ"]
FUEL_ORDER = ["EV", "Hybrid", "ICE"]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ordered_counts(series, order):
    vc = series.value_counts()
    extra = sorted(set(vc.index) - set(order))
    if extra:
        raise ValueError(f"พบค่าที่ไม่รู้จัก {extra} — ตรวจตาราง map ก่อน")
    return [int(vc.get(k, 0)) for k in order]


def build():
    csv_path = tm.survey_path()   # ต้องมี CSV ไฟล์เดียวใน files/user_from/ ไม่งั้นหยุด
    df = tm.load_survey()
    cols = tm.resolve_columns(df)

    # build_* พิมพ์ log การแทนค่า outlier ออกมาเยอะ — เก็บเงียบไว้ ไม่เกี่ยวกับการนับ label
    with contextlib.redirect_stdout(io.StringIO()):
        _, y_buy = tm.build_buy_xy(df)
        _, y_fuel = tm.build_fuel_xy(df)

    # ช่วงอายุ / รายได้ ของผู้ตอบทั้งหมด เรียงตามลำดับในตาราง map ของ train_models
    age_raw = df[cols["age"]].astype(str).str.strip()
    inc_raw = df[cols["income"]].astype(str).str.strip()
    age_labels = list(tm.AGE.keys())
    inc_labels = list(tm.INCOME.keys())

    # ตรวจความสอดคล้อง: กลุ่ม FUEL = ผู้ที่มีรถยนต์อยู่แล้ว (ตอบ "มี" ในคำถาม "1. ปัจจุบันท่านมีรถยนต์หรือไม่")
    has_car = int((df[cols["has_car"]].astype(str).str.strip() == "มี").sum())
    if has_car != len(y_fuel):
        raise ValueError(f"ผู้มีรถ {has_car} คน ไม่เท่ากับกลุ่ม FUEL {len(y_fuel)} คน — ตรวจข้อมูลก่อน")

    overview = {
        "_note": "ไฟล์นี้สร้างอัตโนมัติโดย analysis/dashboard_overview.py ห้ามแก้ตัวเลขด้วยมือ",
        "source": {
            "file": "files/user_from/" + os.path.basename(csv_path),
            "sha256": _sha256(csv_path),
            "rows": int(len(df)),
        },
        "buy": {
            "n": int(len(y_buy)),
            "labels": BUY_ORDER,
            "counts": _ordered_counts(y_buy, BUY_ORDER),
        },
        "fuel": {
            "n": int(len(y_fuel)),
            "labels": FUEL_ORDER,
            "counts": _ordered_counts(y_fuel, FUEL_ORDER),
            "respondents_with_car": has_car,
        },
        "age": {
            "n": int(len(df)),
            "labels": age_labels,
            "counts": [int((age_raw == k).sum()) for k in age_labels],
        },
        "income": {
            "n": int(len(df)),
            "labels": inc_labels,
            "counts": [int((inc_raw == k).sum()) for k in inc_labels],
        },
    }

    # กันการนับตกหล่นเงียบ ๆ — ทุกกลุ่มต้องรวมได้ n พอดี
    for key in ("buy", "fuel", "age", "income"):
        block = overview[key]
        if sum(block["counts"]) != block["n"]:
            raise ValueError(f"{key}: ผลรวม {sum(block['counts'])} ไม่เท่ากับ n={block['n']}")
    return overview


def main():
    ov = build()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ov, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("สรุปข้อมูลสำหรับหน้า Dashboard สาธารณะ")
    print(f"ไฟล์ต้นทาง : {ov['source']['file']}")
    print(f"SHA-256    : {ov['source']['sha256']}")
    print(f"จำนวนแถว   : {ov['source']['rows']}\n")
    for key, title in (("buy", "BUY (ซื้อ/ไม่ซื้อ)"), ("fuel", "FUEL (ประเภทเชื้อเพลิง)"),
                       ("age", "ช่วงอายุ"), ("income", "รายได้เฉลี่ยต่อเดือน")):
        b = ov[key]
        print(f"[{title}] n={b['n']}")
        for lab, c in zip(b["labels"], b["counts"]):
            print(f"  {lab:<28} {c:>4}  ({c / b['n'] * 100:5.1f}%)")
        print()
    print(f"ผู้ตอบที่มีรถยนต์อยู่แล้ว (ตอบ 'มี'): {ov['fuel']['respondents_with_car']}")
    print(f"\nบันทึกแล้ว -> {os.path.normpath(OUT_PATH)}")


if __name__ == "__main__":
    main()
