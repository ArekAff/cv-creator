# Round 1: first draft (cv-writer)

Track **technical** (T-rules), plus the borrowed **N-1** and **N-5**. Layout **jakes**, A4, 11pt, one
page, "Technical Skills" heading, and spoken languages in the skills block, as the person asked in
notes.md. There are no judge findings yet, so this file lists the main tailoring choices.

## Classification
- `career_change` stays **false**. The titles are Junior Business Analyst, then Junior Data Analyst,
  then Data Analyst. The field matches the target family (data & analytics), so C-14 does not apply.

## Structure (T-6, C-5, C-6)
- **Order:** Summary, Experience, Volunteering, Technical Skills, Certifications, Education.
  - I used the **senior** order. She has 6 years in data analytics (Jul 2020 to now), which is past
    T-5's mid-level band of 3–5 years. The ad's priorities (forecasting, dashboards, work with
    operations teams) are proven in experience, not in a list.
  - Volunteering comes right after Experience because it is the evidence for the mentoring duty.
  - Certifications come before Education because they back two must-have tools (Power BI, dbt).
- **Expanded:** Data Analyst at Lumina (P01), 3 bullets. **Condensed:** Junior Data Analyst (P02) and
  Vistula (P03), 2 bullets each. Volunteering (P04), 1 bullet.
- **Promotion shown (T-9):** P01 and P02 are grouped under one Lumina Retail heading.
- **Context lines (T-8)** come from `org_context` for both unknown employers. They add the domain
  ("third-party logistics operator, 2 warehouses") and the scale.

## Top of the CV (C-3, C-4, T-5, C-15)
- **Headline:** "Data Analyst · Forecasting, Power BI and dbt · Retail and Logistics". This is a
  bridging headline with her real title. It doesn't claim "Senior".
- **Target title:** "Senior Data Analyst" goes in the summary as her stated direction, taken from
  `preferences.target_roles`, `preferences.notes` ("close to operations teams") and
  `insights.career_direction`.
  - The clause is short and the rest of the summary is substance.
  - C-3 needs the target title in the summary when she hasn't held it, and C-15 needs the career
    direction to be visible.
- **Summary:**
  - 6 years, retail and logistics;
  - two must-haves: Python demand forecasting, and Power BI on tested dbt models;
  - R06 stakeholder management, in her working style ("starts on the floor or in the meeting room",
    from `insights.working_style`);
  - one proof: MAPE 31% → 19% in back-tests (documented) and Lumina's 2024 Analytics Impact Award
    (AW01, documented).

## Bullets (T-4, T-2, C-7, N-1, N-5, T-12)
The confirmed `accomplishments` and `outcomes` are reframed to the ad's duties. All bullets have no
final period.

| Bullet | Ad's priority | Source |
|---|---|---|
| P01-1 gradient-boosting forecast in Python (pandas, scikit-learn), MAPE 31% → 19% **in back-tests** (wording follows the outcome, not stronger) | duty 1 "build forecasts", R03 | T002 |
| P01-2 explained the forecast to buyers as ranges with a one-page explainer; markdown stock about 12% lower than 2023 (business effect, T-4) | duty 1 "explain them", R06 | T002 |
| P01-3 own the weekly commercial reporting suite: SQL window functions and data modelling in tested dbt models (present tense, current duty) | R02 in the ad's words, R05, the ad's value "ownership" | P01, T001, plus the gap interview (window functions weekly) |
| P02-1 sat in on three Monday meetings, then replaced the 40-tab Excel pack with a one-page Power BI dashboard; prep about 6 h → 30 min a week | duty 2 dashboards, duty 4 "how decisions are really made", R04 | T001 |
| P02-2 SQL extracts moved into tested dbt models on PostgreSQL, copy-paste errors eliminated, old pack switched off once all 6 regional managers used the new report weekly (N-1: decisions managers trust, as adoption) | duty 3 "reliable and tested", R05 | T001 |
| P03-1 two night shifts on the warehouse floor, then an hourly Power BI picking-accuracy dashboard from scanner data for shift leaders | duty 4, duty 2 "shift leaders", R01 logistics | T003 |
| P03-2 trained all 8 shift leaders to use it at handover; picking errors −18% in three months (N-5: training proven with scope) | R10, R06 | T003 |
| P04 monthly beginner SQL and Power BI workshops (N-5: mentoring) | duty 5, R10 | P04 |

- **Wording:** "dashboard" stands in for her "report" where the trail's `keywords` already map it
  (T001, T003). This follows cv-writing-rules B.
- **Tools per bullet (T-2):** at most 3, and those 3 are one stack (Python with pandas and
  scikit-learn; SQL, dbt and PostgreSQL).

## Skills and credentials (T-3, C-9, C-10, T-13, T-14)
- **Groups**, with the ad's stack first:
  - Data: SQL (window functions), dbt, PostgreSQL, Google Cloud / BigQuery (certification in
    progress);
  - Analysis and BI: Python (pandas, scikit-learn), Power BI (DAX, Power Query), demand forecasting;
  - Spoken languages: English (C1), Polish (native). R07 is a must, and notes.md asked for languages
    here.
- **Left out of skills:**
  - soft skills (shown in bullets instead, T-12);
  - Excel, Git and Streamlit (not in the ad);
  - German A2 (not asked for);
  - Tableau and VBA. These come only from the 2023 CV import, are unconfirmed, and so aren't
    evidence.
- **Certifications:** Power BI (PL-300), then dbt, then the GCP Professional Data Engineer marked
  "in progress, expected Dec 2026".

## Cut for the one-page limit (C-6)
- **Tram Delay Explorer (PR01):** Python is already proven at work (T002), and projects shrink for
  experienced candidates (T-6, T-7).
- **GitHub link:** it only showcases PR01, which isn't on this CV (T-13). The two-line contact row
  now fits on one line.
- **Smaller cuts:**
  - the MSc grade;
  - the P01 duties "data-quality checks on the order pipeline" and "ad-hoc marketing/pricing";
  - the P03 process maps.
- **Kept:** the MSc thesis "Short-term demand forecasting for perishable goods" (relevant to duty 1)
  and the RODO/GDPR clause (the job is in Poland).

## Honest gaps (left visible or left out by agreement)
- **R08 BigQuery:** appears only in skills, marked "certification in progress".
  - The knowledge base says there is no production use yet, so no bullet can back it.
  - The lint note "Google Cloud / BigQuery listed but not shown in any bullet" is expected and
    deliberate.
- **R09 Airflow:** none. Left out, as agreed in the gap interview.

## Facts the knowledge base lacks (candidates for a sense-making fact pass; nothing was guessed)
1. **T002 open question:** did the garden-range model run again in 2025, and who owns it now? A yes
   would back "build **and own** forecasts" (duty 1) in the current role.
2. **Mentoring analysts at work** (duty 5, "mentor two junior analysts"): only volunteer workshops and
   shift-leader training are on record. Has she shown a newer analyst at Lumina how to do something?
3. **P04 scale:** how many people come to a workshop, and how many workshops she has run.
4. **P01 reporting suite today:** who uses it and how often. The 6/6 regional-manager figure dates
   from January 2023, so the ownership bullet has no current result.
5. **Unconfirmed claims from the 2023 CV import** that would be strong if confirmed in an interview:
   - "Automated the finance month-end SQL extracts, cutting the close from 2 days to 3 hours" (P02);
   - "Mapped the picking and packing process with the operations team and removed 3 redundant scans"
     (P03, operations work);
   - Tableau Desktop Specialist (2021).
6. **The ad's values:** no record of peak-season or "calm under pressure" work, or of capacity or
   staffing planning (people, trucks, sort lines per hub).

## Build
- 1 page.
- Lint: 0 errors, 0 warnings, 1 info (the deliberate BigQuery note).
- ATS: 13/13 keywords, name, email and phone all extracted.
