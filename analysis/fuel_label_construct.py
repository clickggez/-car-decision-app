# -*- coding: utf-8 -*-
"""
ตรวจสอบ construct ของ label FUEL (คอลัมน์ 21)
=================================================
ประกาศล่วงหน้าก่อนรัน (ตาม 00-READ-FIRST.md §3.5) — รายงานผลไม่ว่าออกมาทางไหน

สมมติฐาน (จาก 04-handoff.md 2026-08-09):
  label FUEL = "หากต้องเลือกซื้อรถยนต์ ท่านสนใจรถประเภทใดมากที่สุด"
  เป็นคำถาม *ความชอบล้วน ๆ ไม่มีข้อจำกัดใด ๆ* ขณะที่ฟีเจอร์ทุกตัวคือ *สภาพชีวิตจริง*
  → ถ้าจริง ตัวเลือกประเภทรถต้อง **ไม่สัมพันธ์** กับข้อจำกัดจริงของผู้ตอบ

เกณฑ์ตัดสิน (ตั้งก่อนเห็นผล):
  H1 ยืนยัน  ถ้า chi-square ของ FUEL กับตัวแปรข้อจำกัดจริง (จุดชาร์จ/ที่จอด/งบ/ที่พัก) ไม่มีนัยสำคัญ
             ขณะที่ BUY สัมพันธ์กับจุดชาร์จอย่างมีนัยสำคัญ
  H1 ตกไป    ถ้า FUEL สัมพันธ์กับข้อจำกัดจริงอย่างน้อย 2 ตัวที่ p<0.05
  เสริม      วัด "ช่องว่างความอยาก-ความเป็นไปได้": คนเลือก EV ที่ติดตั้งจุดชาร์จไม่ได้เลย

ไม่แตะ .pkl ไม่แก้ train_models.py — อ่านข้อมูลดิบอย่างเดียว
"""
import glob
import pandas as pd
from scipy.stats import chi2_contingency

f = glob.glob('../files/user_from/*')[0]
df = pd.read_csv(f, encoding='utf-8')
C = list(df.columns)

FUEL, BUY, REASON = C[21], C[20], C[22]
COND = {'จุดชาร์จ': C[49], 'ที่จอดรถ': C[9], 'งบประมาณ': C[18],
        'ลักษณะที่พัก': C[7], 'เคยลอง EV/Hybrid': C[50],
        'ระยะทางต่อวัน': C[14], 'รายได้': C[10]}

def chi(a, b):
    t = pd.crosstab(df[a], df[b])
    c2, p, dof, _ = chi2_contingency(t)
    n = t.values.sum()
    v = (c2 / (n * (min(t.shape) - 1))) ** .5      # Cramer's V
    return c2, p, v, n

out = []
def w(s=''):
    print(s); out.append(s)

w('=' * 78)
w('ผลตรวจ construct ของ label FUEL   (n=%d)' % len(df))
w('=' * 78)
w()
w('[1] ตัวเลือกประเภทรถ (label FUEL) สัมพันธ์กับ "ข้อจำกัดจริง" หรือไม่')
w()
w('%-20s | %-28s | %-28s' % ('ตัวแปรสภาพจริง', 'FUEL (ชอบแบบไหน)', 'BUY (จะซื้อจริงไหม)'))
w('-' * 82)
for name, col in COND.items():
    _, pf, vf, _ = chi(FUEL, col)
    _, pb, vb, _ = chi(BUY, col)
    sf = '***' if pf < .001 else '**' if pf < .01 else '*' if pf < .05 else 'ns '
    sb = '***' if pb < .001 else '**' if pb < .01 else '*' if pb < .05 else 'ns '
    w('%-20s | p=%.4f V=%.3f %-4s | p=%.4f V=%.3f %-4s' % (name, pf, vf, sf, pb, vb, sb))
w()
w('*** p<.001   ** p<.01   * p<.05   ns = ไม่มีนัยสำคัญ   V = ขนาดอิทธิพล (Cramer V)')
w()

w('[2] ช่องว่าง "ความอยาก vs ความเป็นไปได้" — เฉพาะคนที่เลือก EV')
w()
ev = df[df[FUEL].str.contains('EV', na=False)]
ice = df[df[FUEL].str.contains('น้ำมัน|เบนซิน', na=False)]
w('คนเลือก EV ทั้งหมด %d คน — สภาพจุดชาร์จจริงของเขา:' % len(ev))
vc = ev[C[49]].value_counts()
for k, v in vc.items():
    w('   %-58s %3d คน (%.1f%%)' % (k, v, 100 * v / len(ev)))
w()
blocked = ev[C[49]].str.contains('ไม่สามารถติดตั้ง', na=False).sum()
w('   → เลือก EV ทั้งที่ "ติดตั้งจุดชาร์จไม่ได้เลย" = %d/%d = %.1f%%' % (blocked, len(ev), 100 * blocked / len(ev)))
blocked_ice = ice[C[49]].str.contains('ไม่สามารถติดตั้ง', na=False).sum()
w('   → เทียบคนเลือกน้ำมัน ที่ติดตั้งไม่ได้        = %d/%d = %.1f%%' % (blocked_ice, len(ice), 100 * blocked_ice / len(ice)))
w()

w('[3] เหตุผลที่ผู้ตอบให้ไว้เอง (คอลัมน์ 22) เป็นเหตุผลแบบไหน')
w()
TOK = ['ค่าบำรุงรักษา', 'ความสะดวกในการใช้งาน', 'ประหยัดค่าเชื้อเพลิง',
       'ราคาซื้อเริ่มต้น', 'เทคโนโลยีและความทันสมัย', 'เป็นมิตรต่อสิ่งแวดล้อม']
hyb = df[df[FUEL].str.contains('Hybrid', na=False)]
w('(ตัวเลข = % ของคนในกลุ่มนั้นที่เลือกเหตุผลข้อนี้ ตอบได้หลายข้อ)')
w('%-26s %8s %8s %8s' % ('เหตุผล', 'EV', 'Hybrid', 'น้ำมัน'))
w('-' * 54)
for t in TOK:
    m = lambda d: 100 * d[REASON].fillna('').str.contains(t).sum() / len(d)
    w('%-26s %7.1f%% %7.1f%% %7.1f%%' % (t, m(ev), m(hyb), m(ice)))
w()
w('n:  EV=%d  Hybrid=%d  น้ำมัน=%d' % (len(ev), len(hyb), len(ice)))
w()

open('fuel_label_construct_2026-08-28.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('\nเขียนผลลง fuel_label_construct_2026-08-28.txt')
