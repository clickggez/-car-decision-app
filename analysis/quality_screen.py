"""
Careless responder screening (2026-08-02)
เกณฑ์มาตรฐานของระเบียบวิธีวิจัยเชิงสำรวจ — กำหนดไว้ก่อนดูผลโมเดล

1. NEP reverse-worded inconsistency (attention check ที่ออกแบบใส่ไว้ตั้งแต่ต้น)
   ข้อ 5 ของ NEP (คอลัมน์ 58) เป็น reverse-worded — ถ้าผู้ตอบให้คะแนนไปทางเดียวกับ
   อีก 4 ข้อ แสดงว่าไม่ได้อ่านคำถาม
2. Straight-lining — ตอบเลขเดียวกันรวดทุกข้อใน 7P Likert 21 ข้อ (คอลัมน์ 23-43)
3. Longstring — ตอบเลขเดียวกันติดต่อกันยาวผิดปกติ
"""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "car-dss"))
sys.path.insert(0, _HERE)
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
import train_models as tm

LIKERT_START, LIKERT_END = 23, 43          # 7P Likert 21 ข้อ
NEP_COLS = list(range(tm.COL_NEP_START, tm.COL_NEP_END + 1))
NEP_REVERSE_COL = tm.COL_NEP_START + tm.NEP_REVERSE_OFFSET   # = 58


def longstring(vals):
    """ความยาวสูงสุดของการตอบค่าเดิมติดต่อกัน"""
    best = cur = 1
    for i in range(1, len(vals)):
        cur = cur + 1 if vals[i] == vals[i - 1] else 1
        best = max(best, cur)
    return best


def main():
    df = tm.load_survey()
    n = len(df)
    print(f"ข้อมูลทั้งหมด: {n} แถว\n")

    likert = df.iloc[:, LIKERT_START:LIKERT_END + 1].apply(
        lambda c: pd.to_numeric(c, errors="coerce"))

    # ---------- 1. NEP reverse-worded inconsistency ----------
    nep_raw = pd.DataFrame({c: df.iloc[:, c].map(lambda v: tm._likert(v, default=3))
                            for c in NEP_COLS})
    forward_cols = [c for c in NEP_COLS if c != NEP_REVERSE_COL]
    fwd_mean = nep_raw[forward_cols].mean(axis=1)
    rev_raw = nep_raw[NEP_REVERSE_COL]

    # ถ้าตอบสอดคล้อง: ข้อ reverse ควรได้คะแนน "ดิบ" ต่ำ เมื่ออีก 4 ข้อสูง
    # วัดด้วยผลต่างระหว่างคะแนนดิบของข้อ reverse กับค่าเฉลี่ยของ 4 ข้อแรก
    inconsistency = rev_raw - fwd_mean
    print("=" * 66)
    print("1. NEP reverse-worded attention check")
    print("=" * 66)
    print(f"   ค่าเฉลี่ย 4 ข้อ forward : {fwd_mean.mean():.2f}")
    print(f"   ค่าเฉลี่ยข้อ reverse (ดิบ): {rev_raw.mean():.2f}")
    print(f"   correlation (reverse ดิบ vs forward): {np.corrcoef(rev_raw, fwd_mean)[0,1]:+.3f}")
    print("   (ถ้าผู้ตอบอ่านจริง ควรเป็นลบ — ถ้าเป็นบวกแปลว่าตอบไปทางเดียวกันหมด)\n")

    # เกณฑ์: ตอบ reverse >= 4 ทั้งที่ forward เฉลี่ย >= 4.5 = ขัดแย้งชัดเจน
    flag_nep = (rev_raw >= 4) & (fwd_mean >= 4.5)
    print(f"   ผู้ตอบที่เข้าข่ายไม่สอดคล้อง: {int(flag_nep.sum())} คน "
          f"({flag_nep.mean()*100:.1f}%)\n")

    # ---------- 2. Straight-lining ----------
    print("=" * 66)
    print("2. Straight-lining (7P Likert 21 ข้อ)")
    print("=" * 66)
    nuniq = likert.nunique(axis=1)
    flag_straight = nuniq <= 1
    print(f"   ตอบเลขเดียวรวดทั้ง 21 ข้อ: {int(flag_straight.sum())} คน "
          f"({flag_straight.mean()*100:.1f}%)")
    print(f"   ใช้คำตอบต่างกัน <= 2 ค่า  : {int((nuniq<=2).sum())} คน "
          f"({(nuniq<=2).mean()*100:.1f}%)")
    print(f"   ค่าเฉลี่ยจำนวนค่าที่ใช้    : {nuniq.mean():.2f} จาก 5 ระดับ\n")

    # ---------- 3. Longstring ----------
    print("=" * 66)
    print("3. Longstring (ตอบค่าเดิมติดต่อกัน)")
    print("=" * 66)
    ls = likert.apply(lambda r: longstring(r.fillna(-1).tolist()), axis=1)
    print(f"   ค่าเฉลี่ย: {ls.mean():.1f} | มัธยฐาน: {ls.median():.0f} | สูงสุด: {ls.max()}")
    for thr in (10, 14, 18, 21):
        print(f"   ติดต่อกัน >= {thr:2d} ข้อ: {int((ls>=thr).sum()):3d} คน ({(ls>=thr).mean()*100:.1f}%)")
    flag_ls = ls >= 14
    print()

    # ---------- สรุปรวม ----------
    flagged = flag_nep | flag_straight | flag_ls
    print("=" * 66)
    print("สรุปผู้ตอบที่เข้าข่ายตอบไม่ตั้งใจ (เข้าเกณฑ์ใดเกณฑ์หนึ่ง)")
    print("=" * 66)
    print(f"   NEP ไม่สอดคล้อง : {int(flag_nep.sum()):3d}")
    print(f"   Straight-lining : {int(flag_straight.sum()):3d}")
    print(f"   Longstring >=14 : {int(flag_ls.sum()):3d}")
    print(f"   -> รวม (ไม่ซ้ำ)  : {int(flagged.sum()):3d} คน ({flagged.mean()*100:.1f}% ของ {n})")
    print(f"   -> เหลือหลังคัด  : {int((~flagged).sum()):3d} คน")

    df.loc[~flagged].to_csv(
        os.path.join(_HERE, "cleaned.csv"),
        index=False, encoding="utf-8")
    print("\n   บันทึกชุดข้อมูลที่คัดแล้วไว้ที่ scratchpad/cleaned.csv")


if __name__ == "__main__":
    main()
