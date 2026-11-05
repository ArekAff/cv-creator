# Round 2: revision from judging/round-1/judge.yaml (cv-writer)

Round 1 passed at 85/100. This round applies both `should` findings (F1, F2) and both `could`
findings that need no new facts (F5, F6). The four `needs_input` findings (F3, F4, F7, F8) are
skipped and left open: nobody has answered them yet, and nothing was guessed.

**Outside cv.yaml:** the jakes layout no longer leaves a gap between an employer's context line and its
bullets. The round-1 content, rebuilt under the new layout, has its last body line at y=80pt instead
of y=60pt. That frees about 20pt, which is room for one more line (12–14pt) but not two. This round
spends that room on the one extra line F2 suggested.

## Findings

| id | severity | status |
|---|---|---|
| F1 | should | **done**: summary rebuilt on her own draft, still four lines |
| F2 | should | **done**: one working sentence on one line, plus the optional data-quality line |
| F3 | should | **skipped, needs_input**: no current usage figure in the knowledge base |
| F4 | should | **skipped, needs_input**: no record of helping analysts at work |
| F5 | could | **done**: "self-service" added, bullet still two lines |
| F6 | could | **done**: ad's exact phrase; it causes the one lint warning (a false positive, explained below) |
| F7 | could | **skipped, needs_input**: no workshop size or count in the knowledge base |
| F8 | could | **skipped, needs_input**: T002's open question is still unanswered |

### F1 (N-1, summary): done
New summary, four lines as before:
> Data analyst with 6 years in retail and logistics who builds forecasts and dashboards around the
> decisions operations teams make every week, now aiming for a Senior Data Analyst role. Works in
> Python, Power BI and tested dbt models, with stakeholder management that starts on the warehouse
> floor or in the meeting room. At Lumina Retail, a garden-range forecast cut error from 31% to 19%
> MAPE in back-tests and won the 2024 Analytics Impact Award.

- I used the judge's wording as given.
- **Sentence 1** is her own draft (`insights.summary_drafts`), with "reports" changed to "dashboards".
  That mapping is recorded in the T001 and T003 `keywords`.
  - It now echoes the ad's outcome ("turns operational data into decisions") and its weekly rhythm.
  - "Senior Data Analyst" stays here because it appears nowhere else on the CV (C-3).
- **Sentence 2** replaces the "Combines … on … with …" keyword chain.
  - "stakeholder management" stays, again the only place it appears.
  - "starts on the floor or in the meeting room" comes from `insights.working_style`.
- **Sentence 3** keeps the same proof: the T002 documented outcome, back-test wording unchanged, and
  AW01.
- **Dropped:** "close to operations" (sentence 1 now says it with "the decisions operations teams
  make") and "the company's" (the sentence already opens with "At Lumina Retail").

### F2 (T-4, experience[0].bullets[2]): done
- **Was:** "Own the weekly commercial reporting suite: SQL window functions and data modelling in tested
  dbt models"
- **Now:** "Own the weekly commercial reporting suite and its data modelling in dbt, writing SQL with
  window functions"
  - One sentence on one line.
  - It keeps R02's words (SQL, window functions, data modelling) and R05 (dbt).
  - Sources: P01 for the responsibility, T001 for the dbt models, and the Vantaro gap interview for
    window functions used weekly in those models.
- "tested dbt models" now appears twice (summary, experience[1].bullets[1]) instead of three times.
- **Optional part, done.** The room freed by the layout change goes to a new fourth P01 bullet:
  "Run data-quality checks on the order pipeline".
  - It is P01's responsibility almost word for word, in the present tense, source [P01].
  - It answers the ad's "reporting is reliable and tested" with a current duty.
  - It has no result because the knowledge base records none (see the list at the end).
- The ownership bullet still has no current result. That is F3, which stays open.

### F3 (T-4, experience[0].bullets[2]): skipped, needs_input
Neither T001 nor P01 records who uses the reporting suite today; the 6/6 figure dates from January
2023 and stays in experience[1]. The judge's question still stands: "It's a Monday morning at Lumina
this autumn and the weekly commercial reports have just refreshed. Who opens them, and about how
many people is that?"

### F4 (N-5, experience[0]): skipped, needs_input
There is no record of mentoring analysts at Lumina. R10 is still covered honestly by
experience[2].bullets[1] (8 shift leaders trained) and the volunteering entry. The question stands:
"Has there been a time at Lumina when someone newer in the analytics team was learning something
from you? If so, take me to that moment: what's happening?" If she says yes, the page has only about
6pt left (see the layout check), so that bullet would have to take a line from somewhere else.

### F5 (C-7, experience[1].bullets[0]): done
- "a one-page Power BI dashboard" is now "a one-page self-service Power BI dashboard". T001's keywords
  include "self-service BI", and two managers opened the prototype on their phones.
- The bullet still takes two lines, so "one-page" stays; the judge's fallback wasn't needed.
- **Typography:** the line break fell inside the product name ("…self-service Power" / "BI
  dashboard…"). A non-breaking space between the two words (U+00A0, rendered as LaTeX `~`) keeps
  "Power BI" together. The ATS text still reads "Power BI".

### F6 (C-2, skills[0]): done; the round's one lint warning comes from this change
- "Google Cloud / BigQuery (certification in progress)" is now "Google Cloud Platform / BigQuery
  (certification in progress)", the ad's exact phrase. The row stays on one line.
- **Lint warning:** "Google Cloud Platform / BigQuery: not found in the knowledge base". This is a
  false positive.
  - Lint needs every word of the item to appear in the knowledge base, and "Platform" doesn't.
  - `skills.yaml` holds Google Cloud with the aliases GCP and BigQuery, and Google Cloud Platform is
    GCP's full name.
  - The evidence (C03) is unchanged, and so is the "certification in progress" qualifier. No claim
    is stronger than in round 1.
- **To clear it:** add "Google Cloud Platform" to the Google Cloud aliases in `skills.yaml`. That
  records the same fact under the ad's spelling. The writer doesn't edit the knowledge base, so this
  is for the main agent. The other way out is to go back to "Google Cloud / BigQuery", which loses
  the exact-phrase match.

### F7 (N-5, volunteering[0].bullets[0]): skipped, needs_input
P04 has no participant or workshop count. The question stands: "Picture the most recent Data Girls
Kraków workshop you ran. How many people are in the room?"

### F8 (C-7, experience[0].bullets[0]): skipped, needs_input
T002's open question ("Did the model run again in 2025, and who owns it now?") is unanswered, so the
bullet still claims only the 2024 build, not ongoing ownership. The question stands: "It's spring
2025 and the buyers are planning the garden range again. What's happening with your forecast model
at that point?"

## Layout check (measured from the PDF text positions)
- **Line counts:**
  - one page;
  - summary 4 lines;
  - skills row "Data" 1 line;
  - experience[1].bullets[0] 2 lines;
  - new P01 bullet 1 line.
- **Room at the bottom:** the gap between the last body line and the GDPR clause is 21pt, against
  15pt in the round-1 PDF as judged. About 6pt is left, which is less than half a line, so any new
  content now has to replace something.

## Build
- 1 page (max 1).
- **Lint:** 0 errors, 1 warning, 0 notes.
  - The warning is F6's false positive, explained above.
  - Round 1's info note (BigQuery listed but not shown in any bullet) no longer appears because the
    warning replaces it. The gap is still deliberate: there is no production use.
- **ATS:** 13/13 keywords; name, email and phone extracted. `cv coverage` shows BigQuery only in
  skills, as intended for R08 (partial).

## Facts the knowledge base lacks (for the next fact pass; nothing was guessed)
1. **F3:** who opens the weekly commercial reports today, and how many people that is.
2. **F4:** whether she has helped a newer analyst at Lumina, and the scope.
3. **F7:** people per Data Girls Kraków workshop, or how many workshops she has run since October
   2021.
4. **F8:** whether the garden-range model ran again in 2025, and who owns it now (T002 open
   question).
5. **New:** what the order-pipeline data-quality checks catch or prevent (how often they run, what
   they have found). This would give the new P01 bullet a result.
6. **Still open from round 1:**
   - the unconfirmed claims from the 2023 CV import (finance month-end extracts from 2 days to 3
     hours; 3 redundant scans removed; Tableau Desktop Specialist);
   - any peak-season or capacity-planning work.
