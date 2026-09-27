# -*- coding: utf-8 -*-
"""ประเมินข้อมูลชุด 27 ก.ย. 2569 (n=514) — โปรโตคอลเดียวกับ diagnose_newdata_2026-09-26.py ทุกอย่าง
(40 คำถามร่วม ไม่มี EV · Bagging(DT)×25 ไม่จูน · 20 splits seed 42 · FUEL = ผู้มีรถ)
ตั้งไว้ก่อนรัน: เทียบกับชุดเดิม 500 และชุด 511 ที่ lift/kappa · ชุดรวม (เดิม+514) รายงานแยกตามแหล่งด้วย
"""
import glob, os, sys, runpy, builtins
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
_p = builtins.print; builtins.print = lambda *a, **k: None
g = runpy.run_path('diagnose_newdata_2026-09-26.py'); builtins.print = _p
new = g['load'](glob.glob(os.path.join('..', 'files', 'user_from_archive', '*27_9_2569*.csv'))[0])
new['_src'] = 'new'
extra = [c for c in new.columns if c not in g['old'].columns and c != '_src']
print('คอลัมน์ที่ไม่มีในชุดเดิม:', extra or 'ไม่มี')
old = g['old']; common = g['common']
both = pd.concat([old[common + ['_src']], new[common + ['_src']]], ignore_index=True)
owner = lambda d: d[d[g['OWN']].astype(str).str.strip() == 'มี']
ev = g['evaluate']
print('— BUY —'); ev(new, g['T_BUY'], 'ชุด 27 ก.ย. 514'); ev(both, g['T_BUY'], 'รวม เดิม500+514')
print('— FUEL (ผู้มีรถ) —'); ev(owner(new), g['T_FUEL'], 'ชุด 27 ก.ย.'); ev(owner(both), g['T_FUEL'], 'รวม เดิม+514')
