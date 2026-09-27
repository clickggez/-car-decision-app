# -*- coding: utf-8 -*-
"""คำถามข้อไหนมีผลต่อการทำนายมากที่สุด — ชุดเดิม 500, 40 คำถามร่วม (ไม่มี EV) — 2026-09-27
ใช้ encode/โปรโตคอลเดียวกับ diagnose_newdata_2026-09-26.py · Bagging(DT)×25
permutation importance แบบรวมทุกคอลัมน์ที่มาจากคำถามเดียวกัน · 20 splits (seed 42) × สลับ 5 รอบต่อ split
ค่า = ความแม่นยำที่ลดลงบน test เมื่อสลับคำตอบข้อนั้น (ยิ่งมาก = ยิ่งสำคัญ) · เป็นการวิเคราะห์ ไม่ใช่เลขของระบบที่ deploy
"""
import sys, runpy, builtins
import numpy as np, pandas as pd
from sklearn.ensemble import BaggingClassifier
from sklearn.model_selection import train_test_split
sys.stdout.reconfigure(encoding='utf-8')
_p = builtins.print; builtins.print = lambda *a, **k: None
g = runpy.run_path('diagnose_newdata_2026-09-26.py'); builtins.print = _p
old, feats, encode = g['old'], g['feats'], g['encode']
owner = old[old[g['OWN']].astype(str).str.strip() == 'มี']

def importance(df, target, title):
    E = encode(df); X = E.values; y = df[target].astype(str).values
    groups = {q: [i for i, c in enumerate(E.columns) if c == q or c.startswith(q[:20] + '|') or c.startswith(q[:20] + '_')] for q in feats}
    rng = np.random.default_rng(0); drops = {q: [] for q in feats}
    for s in range(20):
        tr, te = train_test_split(np.arange(len(y)), test_size=0.2, random_state=42 + s, stratify=y)
        m = BaggingClassifier(n_estimators=25, random_state=42).fit(X[tr], y[tr])
        base = (m.predict(X[te]) == y[te]).mean()
        for q, cols in groups.items():
            for _ in range(5):
                Xp = X[te].copy(); perm = rng.permutation(len(te)); Xp[:, cols] = Xp[perm][:, cols]
                drops[q].append(base - (m.predict(Xp) == y[te]).mean())
    r = pd.DataFrame({'q': list(drops), 'drop': [np.mean(v) for v in drops.values()], 'sd': [np.std(v) for v in drops.values()]}).sort_values('drop', ascending=False)
    print(f'\n— {title} (n={len(y)}) — 10 อันดับแรก')
    for i, row in enumerate(r.head(10).itertuples(), 1):
        print(f'{i:>2}. {row.drop*100:+.2f} จุด ± {row.sd*100:.2f}  {row.q[:70]}')
    print(f'   ข้อที่สลับแล้วแทบไม่มีผล (< 0.5 จุด): {(r["drop"] < 0.005).sum()} จาก {len(r)} ข้อ')

importance(old, g['T_BUY'], 'BUY จะซื้อหรือไม่')
importance(owner, g['T_FUEL'], 'FUEL ซื้อประเภทไหน (ผู้มีรถ)')
