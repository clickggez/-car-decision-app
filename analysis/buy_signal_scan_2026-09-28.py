"""
สแกนสัญญาณของป้าย BUY ก่อนเปิดประชุม "ทำให้ BUY ดีขึ้น" (2026-09-28)
อ่านอย่างเดียว ไม่เทรนโมเดล ไม่แตะ .pkl
1. ป้าย BUY สัมพันธ์กับคำถามข้อไหนบ้าง (chi-square) — ทุกคอลัมน์ในแบบสอบถาม ไม่ใช่แค่ที่ train_models ใช้
2. เทียบ n514 / แถวที่เพิ่ม 116 (มีรถทุกคน) / ชุดเดิม n500
3. สัดส่วนซื้อ แยกตามการมีรถ
"""
import sys, os, glob
import pandas as pd
from scipy.stats import chi2_contingency
sys.stdout.reconfigure(encoding="utf-8")
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files")
BUY = "4. ท่านมีแนวโน้มจะซื้อรถยนต์ตามประเภทเชื้อเพลิงที่ท่านสนใจหรือไม่"
HAS = "1. ปัจจุบันท่านมีรถยนต์หรือไม่"
FUEL = "5. หากต้องเลือกซื้อรถยนต์ ท่านสนใจรถประเภทใดมากที่สุด"

def load(p):
    d = pd.read_csv(p); d.columns = [" ".join(str(c).split()) for c in d.columns]
    return d.drop(columns=[c for c in d.columns if c.startswith("คอลัมน์") and d[c].isna().all()])

def scan(name, d):
    buy = [c for c in d.columns if c.startswith("4. ท่านมีแนวโน้ม")][0]
    print(f"\n=== {name}  n={len(d)}  ซื้อ={dict(d[buy].value_counts())}")
    has = [c for c in d.columns if c.startswith("1. ปัจจุบันท่านมีรถ")]
    if has: print("  สัดส่วน 'มีแนวโน้มซื้อ' แยกตามการมีรถ:", d.groupby(d[has[0]].str[:3])[buy].apply(lambda s: round((s=="มีแนวโน้มที่จะซื้อ").mean(),3)).to_dict())
    rows = []
    for c in d.columns:
        if c == buy or c.startswith("5. หากต้องเลือก") or c.startswith("6."): continue
        s = d[c].astype(str)
        if s.nunique() < 2 or s.nunique() > 30: continue
        t = pd.crosstab(s, d[buy]); 
        if t.shape[0] < 2: continue
        rows.append((chi2_contingency(t)[1], c[:60]))
    rows.sort()
    sig = [r for r in rows if r[0] < 0.05]
    print(f"  คำถามที่ p<0.05 : {len(sig)}/{len(rows)}")
    for p, c in rows[:8]: print(f"    p={p:.4f}  {c}")

if __name__ == "__main__":
    n630 = load(glob.glob(os.path.join(R, "user_from", "*.csv"))[0])
    n514 = load(os.path.join(R, "archive_2026-09-28", "survey_2026-09-27_n514.csv"))
    old = glob.glob(os.path.join(R, "user_from_archive", "*(500).csv"))
    scan("n514", n514)
    scan("แถวที่เพิ่ม 116 (EV+ไฮบริด)", n630.iloc[514:])
    scan("n630", n630)
    if old: scan("ชุดเดิม n500 (เว็บปัจจุบัน)", load(old[0]))
