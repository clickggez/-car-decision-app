# -*- coding: utf-8 -*-
"""ตารางไขว้ งบประมาณ x แนวโน้มการซื้อ ของข้อมูลสองชุด (อ่านอย่างเดียว) — ใช้อ้างในเล่มบทที่ 4 หัวข้อ 4.3
รัน: python analysis/budget_vs_buy_2026-10-10.py"""
import glob
import pandas as pd
from scipy.stats import chi2_contingency

B = "2. งบประมาณที่มีในการซื้อรถยนต์"
Y = "4. ท่านมีแนวโน้มจะซื้อรถยนต์ตามประเภทเชื้อเพลิงที่ท่านสนใจหรือไม่"
BUY = "มีแนวโน้มที่จะซื้อ"
HIGH = ["1,200,000-1,500,000 บาท", "มากกว่า 1,500,000 บาท"]
SETS = [("ชุดเดิม 500 คน", glob.glob("files/archive_2026-09-26/*500*")[0]),
        ("ชุดใหม่ 514 คน", "files/archive_2026-09-28/survey_2026-09-27_n514.csv")]
for name, f in SETS:
    d = pd.read_csv(f, encoding="utf-8-sig")
    print("=" * 70, "\n", name, "n =", len(d))
    ct = pd.crosstab(d[B], d[Y])
    ct["ซื้อ%"] = (ct[BUY] / ct.sum(axis=1) * 100).round(1)
    print(ct.to_string())
    p = chi2_contingency(pd.crosstab(d[B], d[Y]))[1]
    hi = d[B].isin(HIGH)
    print(f"งบ 1.2 ล้านขึ้นไป: ซื้อ {(d[hi][Y]==BUY).sum()} จาก {hi.sum()} ({(d[hi][Y]==BUY).mean()*100:.1f}%)")
    print(f"งบต่ำกว่า        : ซื้อ {(d[~hi][Y]==BUY).sum()} จาก {(~hi).sum()} ({(d[~hi][Y]==BUY).mean()*100:.1f}%)")
    print(f"ไคสแควร์ (งบ 5 ช่วง x คำตอบ) p = {p:.4f}")
