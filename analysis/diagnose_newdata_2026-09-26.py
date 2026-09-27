# -*- coding: utf-8 -*-
"""
วินิจฉัยว่าความแม่นยำที่ตกลงกับข้อมูลชุดใหม่ (n=511) มาจากอะไร — 2026-09-26
===========================================================================
คำถาม: ผลตกเพราะ (1) ตัดคำถาม EV/TPB/NEP ออก หรือ (2) ตัวข้อมูลชุดใหม่เอง

โปรโตคอล (ล็อกไว้ก่อนรัน ใช้เหมือนกันทุกเงื่อนไข เพื่อให้เทียบกันได้):
- ฟีเจอร์ = เฉพาะคำถามที่มีทั้งสองชุด (หัวคอลัมน์ตรงกัน) ไม่ใช้คำถาม EV/TPB/NEP เลย
  ตัดเป้าหมาย (ข้อ 4 แนวโน้มซื้อ, ข้อ 5 ประเภทที่สนใจ) และข้อ 6 "เหตุผลในการเลือกประเภท" (รั่วคำตอบ FUEL)
  ข้อเลือกได้หลายคำตอบ (มี ", ") แตกเป็น multi-hot · Likert เป็นตัวเลข · ที่เหลือ one-hot
- BUY = ทุกแถว · FUEL = เฉพาะผู้มีรถ (ตามการออกแบบเดิม)
- โมเดล = BaggingClassifier(DecisionTree) ×25 ค่าเริ่มต้นทั้งหมด ไม่จูน
- 20 random splits (seed 42, test 20%, stratify) รายงาน accuracy ± sd, kappa, baseline, lift
- เงื่อนไข: ก = ชุดเดิม 500 · ใหม่ = ชุดใหม่ 511 · ข = รวม 1,011
  ข แยกรายงานความแม่นยำบน test ที่มาจากแต่ละชุดด้วย เพื่อไม่ให้ชุดหนึ่งกลบอีกชุด
เลขชุดนี้เป็นการวินิจฉัย ไม่ใช่เลขของระบบที่ deploy
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import BaggingClassifier
from sklearn.metrics import accuracy_score, cohen_kappa_score
from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')

T_BUY = '4. ท่านมีแนวโน้มจะซื้อรถยนต์ตามประเภทเชื้อเพลิงที่ท่านสนใจหรือไม่'
T_FUEL = '5. หากต้องเลือกซื้อรถยนต์ ท่านสนใจรถประเภทใดมากที่สุด'
LEAK = '6. เหตุผลในการเลือกประเภทรถยนต์ดังกล่าว'
OWN = '1. ปัจจุบันท่านมีรถยนต์หรือไม่'


def load(path):
    d = pd.read_csv(path, encoding='utf-8')
    d.columns = [c.strip() for c in d.columns]
    return d


old = load(glob.glob(os.path.join(ROOT, 'files', 'archive_2026-09-26', '*.csv'))[0])
new = load(os.path.join(ROOT, 'files', 'user_from', 'survey_2026-09-26_n511.csv'))
old['_src'], new['_src'] = 'old', 'new'

common = [c for c in new.columns if c in old.columns and c not in ('คอลัมน์ 1', 'ประทับเวลา', '_src')]
feats = [c for c in common if c not in (T_BUY, T_FUEL, LEAK)]


def encode(df):
    parts = []
    for c in feats:
        s = df[c]
        num = pd.to_numeric(s, errors='coerce')
        if num.notna().mean() > 0.95:
            parts.append(num.fillna(num.median()).rename(c).to_frame())
        elif s.astype(str).str.contains(', ').any():
            parts.append(s.fillna('').astype(str).str.get_dummies(sep=', ').add_prefix(c[:20] + '|'))
        else:
            parts.append(pd.get_dummies(s.fillna('NA').astype(str), prefix=c[:20]).astype(int))
    return pd.concat(parts, axis=1)


def evaluate(df, target, label):
    X = encode(df).values
    y = df[target].astype(str).values
    src = df['_src'].values
    accs, kaps, by_src = [], [], {'old': [], 'new': []}
    for i in range(20):
        idx = np.arange(len(y))
        tr, te = train_test_split(idx, test_size=0.2, random_state=42 + i, stratify=y)
        m = BaggingClassifier(n_estimators=25, random_state=42).fit(X[tr], y[tr])
        p = m.predict(X[te])
        accs.append(accuracy_score(y[te], p))
        kaps.append(cohen_kappa_score(y[te], p))
        for s in by_src:
            mask = src[te] == s
            if mask.sum():
                by_src[s].append(accuracy_score(y[te][mask], p[mask]))
    base = pd.Series(y).value_counts(normalize=True).iloc[0]
    a = np.mean(accs)
    line = (f"{label:<22} n={len(y):<5} acc {a:.4f} ± {np.std(accs):.4f}  "
            f"κ {np.mean(kaps):+.4f} ± {np.std(kaps):.4f}  baseline {base:.4f}  lift {a - base:+.4f}")
    if len(set(src)) > 1:
        line += f"\n{'':<22} test จากชุดเดิม {np.mean(by_src['old']):.4f} · จากชุดใหม่ {np.mean(by_src['new']):.4f}"
    print(line)


both = pd.concat([old[common + ['_src']], new[common + ['_src']]], ignore_index=True)
owner = lambda d: d[d[OWN].astype(str).str.strip() == 'มี']

print(f"ฟีเจอร์ร่วม {len(feats)} คำถาม (ไม่มี EV/TPB/NEP)\n")
print('— BUY —')
evaluate(old, T_BUY, 'ก ชุดเดิม 500')
evaluate(new, T_BUY, 'ชุดใหม่ 511')
evaluate(both, T_BUY, 'ข รวม 1,011')
print('\n— FUEL (ผู้มีรถ) —')
evaluate(owner(old), T_FUEL, 'ก ชุดเดิม')
evaluate(owner(new), T_FUEL, 'ชุดใหม่')
evaluate(owner(both), T_FUEL, 'ข รวม')
