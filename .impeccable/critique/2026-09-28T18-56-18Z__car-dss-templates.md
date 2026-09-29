---
target: ทุกหน้า (car-dss/templates)
total_score: 17
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
target_identity: "file:C:\\Users\\click\\Desktop\\car-decision-app\\car-dss\\templates"
timestamp: 2026-09-28T18-56-18Z
slug: car-dss-templates
---
Method: dual-agent (A: design review · B: detector+browser)

## Design Health Score: 17/40 (Poor)
| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | System status | 2 | stepper step 3 labelled "Dashboard" (predict_buy.html:28, result_*.html:21); no loading state |
| 2 | Real world match | 1 | English/ML jargon: Binary, Multi-class, SVM (real), Dashboard, WLTP, Top 1 |
| 3 | User control | 3 | back/restart present |
| 4 | Consistency | 2 | home "500" (home.html:44-47) vs dashboard 630; "5 รุ่น" vs 8/12/5 |
| 5 | Error prevention | 2 | invalid fields styled in brand blue, not danger |
| 6 | Recognition | 2 | predict_fuel.html:39-42 banner hard-coded "แนะนำให้ซื้อ" |
| 7 | Flexibility | 2 | whole flow behind login, no preview |
| 8 | Minimalist | 2 | filler stat cards/badges on results |
| 9 | Error recovery | 2 | generic "กรอกข้อมูลให้ครบ" |
| 10 | Help/trust | 1 | model accuracy shown nowhere |

## Design specificity
Generic AI template on Tesla tokens: fade-in stagger everywhere (style.css:611, no prefers-reduced-motion), icon before every h1/CTA, bi-cpu on submit, two 3-card feature grids (home.html:81-190), 100vh hero + vanity stats, badge overload (recommend/result_fuel), English fuel badges.
Detector: 14 warnings (4 low-contrast mostly false positives from unloaded Jinja CSS; 4 tiny-text + 2 undersized in recommend.html 10-11px real; overused Inter real; layout-transition register.html:52 minor). Browser: .mock-tag contrast 3.4:1 on every page.

## Priority issues
- [P0] Trust story missing/false: no accuracy shown; result_buy.html:81/88 cites finance/housing the model does not use; result_fuel.html:130 invented EV reason; home "500". Fix: plain-Thai trust block, real-input explanations, stats from dataset_overview.json.
- [P0] Dev residue shown to users: "Skeleton Mode" base.html:169, "Mock" recommend.html:40, model_used chip, "เขตบางขุนเทียน" recommend.html:281. Fix: delete.
- [P1] FUEL % ความเหมาะสม + animated bars = false precision (result_fuel.html:199-211). Owner decision.
- [P1] Jargon + AI chrome: stat cards, English badges, bi-cpu, icon-h1, stagger fade.
- [P2] Flow/label bugs: stepper, fuel banner, error colour, "5 รุ่น", recommend CTA to dashboard.

## Persona red flags
Jordan: no reason for login wall; stepper lies. Casey: home ~4,490px at 390px; 10-checkbox grid. Riley: 500 vs 630, banner after no-buy. Thai non-English reader: Binary/Multi-class/Top 1/Skeleton/Mock; username a-z only.

## Minor
Thai line-height tight (1.43/1.2); login title mid-word break (overflow-wrap); Google Fonts loaded twice; 10-11px text on phones; recommend tabs lack role=tab.

## Questions
BUY as headline verdict at 56%? Tesla showroom vs data-first dashboard voice? End journey at dashboard instead of next steps?
