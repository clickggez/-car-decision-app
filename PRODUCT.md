# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary (confirmed 2026-09-29):** Thai members of the public who are thinking about buying a car and want help deciding. They arrive on phones and computers in roughly equal measure, so every surface must work well on both.

Secondary, confirmed from project context: the thesis committee (อาจารย์/กรรมการ), who judge the system during the defense and check that every number shown is honest and traceable. The site owner is a student. An admin maintains the car list and the user accounts.

Users read Thai. Many cannot read English. Technical terms must be explained in Thai, or not shown at all.

## Product Purpose

CarDSS (ระบบสนับสนุนการตัดสินใจซื้อรถยนต์ตามประเภทเชื้อเพลิง) is a decision support system built as a university thesis project. A visitor answers a short questionnaire and gets two predictions from models trained on real survey data:

1. **BUY**: whether they are likely to buy a car
2. **FUEL**: which fuel type suits them best (EV, Hybrid or ICE)

It then recommends car models from a curated list.

Success means the visitor leaves with both of these (confirmed 2026-09-29):
- a useful recommendation: which fuel type and which models to consider
- an honest sense of how much to trust it: the result comes from real survey data, and the site states plainly how accurate the model is and where its limits are

## Positioning

The recommendations come from machine-learning models trained on the thesis's own Thai car-buyer survey, not from sales copy or dealer incentives. The site is open about accuracy and limits, and it never overstates confidence. A dealer or car-review site could not truthfully make that claim.

## Operating Context

- **Flow:** home → login/register → questionnaire BUY (10 questions, including budget) → result BUY → questionnaire FUEL (6 question groups) → result FUEL → recommended models (`/recommend`)
- **Login:** every prediction page requires login. This is part of the scope the committee approved (2026-09-25) and must not be removed.
- **Dashboard:** `/dashboard` is public. It shows the same research-data overview to everyone and never shows personal results.
- **Admin area** (`/admin/*`): users, car catalogue, model explanation
- **Hosting:** PythonAnywhere at https://r4tt4.pythonanywhere.com. Deploy is git push → pull → Reload.
- **Stack:** Flask + Jinja templates, scikit-learn models, Firebase for accounts and stored results

## Capabilities and Constraints

- The model inputs are fixed by the trained `.pkl` files. Forms may only ask the questions the models actually use, and tests enforce this (`car-dss/tests/test_user_facing.py`). Changing the questions means retraining the models, which is not a UI decision.
- **Accuracy shown to users must match `agent-docs/00-READ-FIRST.md` §1** (currently BUY 65.0% vs 58.4% always-guess-most-common, FUEL 65.7% vs 35.0%). Never invent, round up or hard-code numbers. Result pages read them via `predictor.model_reliability()` (metrics in the .pkl plus `car-dss/data/model_reliability.json`, which is SHA-checked). Always compare against the most-common-answer baseline, never against random guessing. The dashboard reads `car-dss/data/dataset_overview.json` only.
- Project rule: FUEL must not show a per-prediction "% confidence". The current % "ความเหมาะสม" on `result_fuel.html` is an open question for the owner.
- `predict_buy()` / `predict_fuel()` signatures and data schemas are locked.
- Thai text rendering: fonts must support Thai. Stacked vowels and tone marks must never clip.
- Light and dark mode are both supported.

## Brand Commitments

- Product name: CarDSS / "ระบบสนับสนุนการตัดสินใจซื้อรถยนต์ตามประเภทเชื้อเพลิง"
- Voice: plain, calm Thai. Avoid marketing hype, technical jargon (for example "SVM & ANN" or "Data Mining" on public pages) and location-specific phrasing as a heading or pitch. The survey was distributed in เขตบางขุนเทียน (user confirmed 2026-09-29), so the area may appear only as the data source line on the home page and the dashboard caveat.
- The owner has said the current UI "looks too AI-generated" (2026-09-29). Future work should remove generic AI-template tells.
- **The owner retired the Tesla-inspired style on 2026-09-29, and a full redesign is planned.** The old `DESIGN.md` is archived at `agent-docs/archive/DESIGN_tesla_retired_2026-09-29.md` for reference only. Treat the current look as evidence to replace, not a system to extend.

## Evidence on Hand

- Survey data: the current survey has 630 respondents (457 car owners), with a research overview in `car-dss/data/dataset_overview.json`. The BUY model is trained on the earlier survey round (n=500, general questions only). The owner decided on 2026-09-29 that the "เน้น ice" file name does not need to go in the thesis. The owner must confirm with the advisor that this data may be used.
- Model accuracy and verification: `analysis/verify_web_accuracy_2026-09-28.txt`
- Car catalogue: `car-dss/data/cars.json` (EV 8, Hybrid 12, ICE 5 models) with images in `car-dss/static/img/cars/`
- **Absent, do not fabricate:** testimonials, user counts, press, partner logos, prices beyond `cars.json`, and accuracy claims above the verified figures

## Product Principles

1. **Honest over impressive.** Show real accuracy and limits. A modest true number beats an invented confident one.
2. **Short path to an answer.** Ask only what the models use, and get people to their recommendation quickly.
3. **Thai-first clarity.** Every label, result and error must make sense to someone who does not read English.
4. **Advice, not a verdict.** Present results as decision support. The person still decides.
5. **Works equally on phone and desktop.**

## Accessibility & Inclusion

- Users may not read English. All user-facing text must be in Thai, including errors.
- Thai fonts must render correctly, with no clipped marks.
- Use legible sizes and contrast on mobile, and in both light and dark mode.
