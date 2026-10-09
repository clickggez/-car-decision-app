"""
สร้างไฟล์ตัวเลขนับรวมสำหรับ "แดชบอร์ดกรองได้" บนหน้าภาพรวมข้อมูล (2026-10-09)

ดีไซน์ที่ผู้ใช้เลือก: ช่องกรอง + การ์ดตัวเลข + กราฟข้ามตัวแปร (ประเภทเชื้อเพลิงที่สนใจ × รายได้/อายุ/งบประมาณ/แนวโน้มซื้อ)

⭐ ความเป็นส่วนตัว: เก็บเฉพาะ "ตัวเลขนับรวมต่อกลุ่ม" ไม่มีข้อมูลรายบุคคล (เหมือน dataset_overview.json)
   ช่องกรองมี 3 ช่องที่ซ้อนกันได้ = เพศ × การมีรถ × ประเภทที่สนใจ (12 กลุ่ม เล็กสุด 16 คน)
   ไม่ทำช่องกรองอายุ/รายได้/อาชีพ เพราะซ้อนกันแล้วกลุ่มเหลือไม่กี่คน = เดาตัวผู้ตอบได้
   อายุ/รายได้/งบ/แนวโน้มซื้อ ใช้เป็น "แกนกราฟ" ภายในแต่ละกลุ่มแทน

รัน: python analysis/dashboard_groups.py   ->  car-dss/data/dashboard_groups.json
ตัวเลขรวมทุกกลุ่มต้องเท่ากับ dataset_overview.json (มีเทสต์ตรวจ)
"""
import os, sys, json, hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import train_models as tm  # noqa: E402

OUT = os.path.join(_HERE, "..", "car-dss", "data", "dashboard_groups.json")
GENDERS = ["ชาย", "หญิง"]
CARS = ["มี", "ไม่มี"]
FUELS = ["ICE", "Hybrid", "EV"]
BUDGETS = ["ต่ำกว่า 500,000 บาท", "500,001-800,000 บาท", "800,001-1,200,000 บาท",
           "1,200,000-1,500,000 บาท", "มากกว่า 1,500,000 บาท"]
BUYS = ["ซื้อ", "ไม่ซื้อ"]


def col(df, prefix):
    hits = [c for c in df.columns if c.strip().startswith(prefix)]
    if len(hits) != 1:
        raise ValueError(f"หาคอลัมน์ '{prefix}' ได้ {len(hits)} คอลัมน์")
    return hits[0]


def fuel_of(text):
    t = str(text)
    if "สันดาป" in t: return "ICE"
    if "ไฮบริด" in t: return "Hybrid"
    if "ไฟฟ้า" in t: return "EV"
    raise ValueError(f"ประเภทรถไม่รู้จัก: {t}")


def build():
    # files/user_from/ ตอนนี้มี CSV 2 ไฟล์ (n630 + ชุดเดิม 500) ตัวโหลดกลางของ train_models จึงหยุด → ระบุไฟล์ n630 ตรง ๆ
    import glob, pandas as pd
    matches = sorted(glob.glob(os.path.join(_HERE, "..", "files", "user_from", "survey_*_n630.csv")))
    if len(matches) != 1:
        raise RuntimeError(f"ต้องมีไฟล์ survey_*_n630.csv ไฟล์เดียว แต่พบ {len(matches)}")
    path = matches[0]
    df = pd.read_csv(path, encoding="utf-8")
    df = df.drop(columns=[c for c in df.columns if str(c).strip().startswith("คอลัมน์") and df[c].isna().all()])
    cols = tm.resolve_columns(df)
    g = df[col(df, "1. เพศ")].astype(str).str.strip()
    car = df[cols["has_car"]].astype(str).str.strip().map(lambda s: "มี" if s == "มี" else "ไม่มี")
    fuel = df[col(df, "5. หากต้องเลือกซื้อรถยนต์")].map(fuel_of)
    age = df[cols["age"]].astype(str).str.strip()
    inc = df[cols["income"]].astype(str).str.strip()
    bud = df[col(df, "2. งบประมาณที่มี")].astype(str).str.strip()
    buy = df[col(df, "4. ท่านมีแนวโน้มจะซื้อ")].astype(str).str.strip().map(
        lambda s: "ไม่ซื้อ" if s.startswith("ยังไม่") else "ซื้อ")
    age_l, inc_l = list(tm.AGE.keys()), list(tm.INCOME.keys())
    for name, ser, order in (("เพศ", g, GENDERS), ("อายุ", age, age_l), ("รายได้", inc, inc_l), ("งบ", bud, BUDGETS)):
        bad = sorted(set(ser) - set(order))
        if bad:
            raise ValueError(f"{name}: พบค่าที่ไม่รู้จัก {bad}")
    groups = []
    for gg in GENDERS:
        for cc in CARS:
            for ff in FUELS:
                m = (g == gg) & (car == cc) & (fuel == ff)
                groups.append({
                    "gender": gg, "car": cc, "fuel": ff, "n": int(m.sum()),
                    "age": [int(((age == k) & m).sum()) for k in age_l],
                    "income": [int(((inc == k) & m).sum()) for k in inc_l],
                    "budget": [int(((bud == k) & m).sum()) for k in BUDGETS],
                    "buy": [int(((buy == k) & m).sum()) for k in BUYS],
                })
    for grp in groups:
        for k in ("age", "income", "budget", "buy"):
            if sum(grp[k]) != grp["n"]:
                raise ValueError(f"กลุ่ม {grp['gender']}/{grp['car']}/{grp['fuel']} แกน {k} รวมไม่เท่า n")
    if sum(x["n"] for x in groups) != len(df):
        raise ValueError("ผลรวมทุกกลุ่มไม่เท่าจำนวนผู้ตอบ")
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return {
        "_note": "ไฟล์นี้สร้างอัตโนมัติโดย analysis/dashboard_groups.py ห้ามแก้ตัวเลขด้วยมือ · เก็บเฉพาะตัวเลขนับรวมต่อกลุ่ม",
        "source": {"file": "files/user_from/" + os.path.basename(path), "sha256": h, "rows": int(len(df))},
        "dims": {"gender": GENDERS, "car": CARS, "fuel": FUELS},
        "labels": {"age": age_l, "income": inc_l, "budget": BUDGETS, "buy": BUYS},
        "groups": groups,
    }


if __name__ == "__main__":
    out = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1); f.write("\n")
    print("rows", out["source"]["rows"], "groups", len(out["groups"]), "min n", min(x["n"] for x in out["groups"]))
    print("saved ->", os.path.normpath(OUT))
