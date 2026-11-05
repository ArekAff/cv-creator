# Is this listing technical or non-technical?

Every job ad gets classified before anything is written, because the two tracks are tailored
differently. The sources are in `expert-knowledge/how-to-tailor-resume/`: `technical/` and
`non-technical/`, plus `hybrid/`, which applies to both. The **listing-classifier** agent writes
`classification.yaml` into the application folder. The decision is always one of the two tracks.

## The decision

**technical**: the core output of the job is built, engineered, analysed or operated with
specialised tools or disciplines, and the screen is a handful of hard technical keywords (languages,
frameworks, platforms, methods, engineering software, licences). Families: software engineering,
data & analytics (SQL/Python/BI/modelling), data science & ML, IT & infrastructure, cloud & DevOps,
security, QA & test automation, engineering disciplines (mechanical, electrical, civil,
manufacturing, construction engineering, architecture), and technical research.

**non-technical**: the core output is results with people, customers, money or organisation. The
screen looks for proof of results in the posting's own terms: metrics, vocabulary, and evidence for
each soft skill. Families: sales, marketing, HR & recruiting, admin & customer service, finance &
accounting, operations & business roles (including product, operations and customer success at tech
companies), education, care, hospitality, and creative & communication roles.

The deciding question: in the first review, will this person be judged on **"do they have our
stack or discipline?"** (technical) or on **"have they delivered these results with these
people/processes?"** (non-technical)?

## Signals

| Signal | Points to technical | Points to non-technical |
|---|---|---|
| Title | engineer, developer, data/BI analyst, data scientist, architect, DevOps, SRE, IT administrator, technician | sales, account executive, marketing, recruiter, HR, assistant, coordinator, accountant, customer success, non-engineering manager |
| Requirements | 3+ hard technical must-haves (languages, frameworks, cloud, CAD, statistics/ML, engineering codes or licences) | experience, KPIs, client/people/process skills, business tools (CRM, office suites) |
| Duties | build, design, model, code, deploy, analyse data, test | sell, recruit, coordinate, support, manage accounts, run campaigns |
| A "tech stack" paragraph | common | rare |
| Hiring process hints | technical, coding or case interview | competency interviews |

`uv run cv classify <app>` counts these signals in the ad and suggests a track. It is a hint for the
agent, which weighs it but makes the decision itself; word counts don't understand the job.

## Mixed listings

Decide by the core output and the screening criteria. Then list, in `borrow`, the rule ids from the
other playbook that are still worth applying. Examples:

- **Technical product manager, sales engineer, solutions consultant:** non-technical if judged on
  customers, revenue or roadmap outcomes. Borrow T-3 (skills section) and T-2 (naming the stack).
- **Data-heavy business analyst, BI analyst:** technical when SQL/BI/modelling requirements dominate.
  Borrow N-1 (results in the ad's terms) and N-5 (proof for soft skills such as stakeholder work).
- **Engineering manager:** technical. Borrow N-4-style people results: team size, hires, retention.

## Career change is about the person

The ad can't say whether this is a career change. The **cv-writer** sets `career_change: true` when
the person's recent titles or field differ from the target family, in which case rule C-14
(`tailoring-common.md`) applies on top of the track.

## classification.yaml

```yaml
track: technical            # technical | non-technical, always one of the two
family: data & analytics
seniority: senior           # entry | mid | senior | lead
ats_likely: true
confidence: high            # high | medium | low (low = say so to the person)
signals:                    # 3-6 short pieces of evidence from the ad
  - "title: Senior Data Analyst"
  - "must-haves: advanced SQL, Python forecasting, Power BI, dbt (4 of 7 requirements are tools)"
  - "duties: build forecasts, model data in BigQuery + dbt"
borrow: [N-1, N-5]          # rules from the other playbook that still apply
career_change: false        # set by the cv-writer from the knowledge base
playbook: method/tailoring-technical.md
decided_by: listing-classifier
```
