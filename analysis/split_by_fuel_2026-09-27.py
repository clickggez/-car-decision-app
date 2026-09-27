# -*- coding: utf-8 -*-
"""ถ้าแยกเป็นไฟล์ละประเภท (EV / Hybrid / ICE) โมเดลจะดีขึ้นไหม — 2026-09-27
ทำ 3 โมเดลย่อยแบบ "ประเภทนี้ vs ไม่ใช่" · ชุดเดิม ผู้มีรถ n=316 · 40 คำถามร่วม (ไม่มี EV)
Bagging(DT)×25 · 20 splits seed 42 · รายงาน balanced accuracy (0.5 = เดาสุ่ม) และ kappa
"""
import sys, runpy, builtins
import numpy as np
from sklearn.ensemble import BaggingClassifier
from sklearn.metrics import balanced_accuracy_score, cohen_kappa_score
from sklearn.model_selection import train_test_split
sys.stdout.reconfigure(encoding='utf-8')
_p = builtins.print; builtins.print = lambda *a, **k: None
g = runpy.run_path('diagnose_newdata_2026-09-26.py'); builtins.print = _p
old = g['old']; df = old[old[g['OWN']].astype(str).str.strip() == 'มี']
X = g['encode'](df).values; y = df[g['T_FUEL']].astype(str).values
for cls in sorted(set(y)):
    yb = (y == cls).astype(int); ba, ka = [], []
    for s in range(20):
        tr, te = train_test_split(np.arange(len(yb)), test_size=0.2, random_state=42 + s, stratify=yb)
        p = BaggingClassifier(n_estimators=25, random_state=42).fit(X[tr], yb[tr]).predict(X[te])
        ba.append(balanced_accuracy_score(yb[te], p)); ka.append(cohen_kappa_score(yb[te], p))
    print(f'{cls[:32]:<34} มี {yb.sum():>3} คน · balanced acc {np.mean(ba):.4f} ± {np.std(ba):.4f} · κ {np.mean(ka):+.4f}')
