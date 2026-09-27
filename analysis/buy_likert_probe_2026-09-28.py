"""
ทดลองเร็ว (exploratory ไม่ใช่ผลสำหรับเล่ม): ถ้าให้ BUY ใช้ Likert 7P 21 ข้อ จะดีขึ้นไหม — 2026-09-28
โปรโตคอลล็อกก่อนรัน: ข้อมูล n514 (ชุดที่ BUY บนเว็บใช้) · Bagging(DecisionTree)x25 ไม่จูน ·
StratifiedShuffleSplit 20 splits test 20% seed 42 · เหมือนกันทุกแขน · ไม่แตะ .pkl
แขน A = 3 คำถามที่ BUY ใช้อยู่ (education, family_size, purpose multi-hot)
แขน B = A + Likert 21 ข้อ   แขน C = Likert 21 ข้ออย่างเดียว
"""
import sys, os
import numpy as np, pandas as pd
from sklearn.ensemble import BaggingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, cohen_kappa_score
sys.stdout.reconfigure(encoding="utf-8")
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "files", "archive_2026-09-28", "survey_2026-09-27_n514.csv")
d = pd.read_csv(F); d.columns = [" ".join(str(c).split()) for c in d.columns]
col = lambda pre: [c for c in d.columns if c.startswith(pre)][0]
y = (d[col("4. ท่านมีแนวโน้ม")] == "มีแนวโน้มที่จะซื้อ").astype(int).values
lik = [c for c in d.columns if c.startswith("ปัจจัยด้าน")]
A = pd.concat([pd.get_dummies(d[col("3. ระดับการศึกษา")], prefix="edu"),
               pd.get_dummies(d[col("5. จำนวนสมาชิก")], prefix="fam"),
               d[col("3. วัตถุประสงค์")].fillna("").str.get_dummies(sep=", ").add_prefix("pur_")], axis=1).astype(float)
L = d[lik].astype(float)
arms = {"A ฟีเจอร์ปัจจุบัน": A, "B ปัจจุบัน+Likert": pd.concat([A, L], axis=1), "C Likert อย่างเดียว": L}
print(__doc__); print(f"n={len(y)} Likert={len(lik)} ข้อ baseline={max(y.mean(),1-y.mean()):.4f}")
sss = StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=42)
for name, X in arms.items():
    a, k = [], []
    for tr, te in sss.split(X, y):
        m = BaggingClassifier(DecisionTreeClassifier(random_state=42), n_estimators=25, random_state=42).fit(X.iloc[tr], y[tr])
        p = m.predict(X.iloc[te]); a.append(accuracy_score(y[te], p)); k.append(cohen_kappa_score(y[te], p))
    print(f"  {name:22s} acc {np.mean(a):.4f} ± {np.std(a):.4f}   kappa {np.mean(k):+.4f}   ({X.shape[1]} คอลัมน์)")
