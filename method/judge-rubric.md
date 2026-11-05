# The judge's rubric and the editor–judge loop

The **cv-judge** scores each round of a CV against the playbook chosen by `classification.yaml`
(`tailoring-common.md` + `tailoring-technical.md` or `tailoring-non-technical.md`) and the house rules
(`cv-writing-rules.md`). The **cv-writer** then edits from the findings. The judge never edits the CV;
the writer never grades its own work.

## Gate: blockers (no pass while any exists)
- A claim the knowledge base doesn't support: a number, scale, tool, title, outcome or skill. Also a
  claim made stronger than the source ("led" for "helped", "12%" for "about 12%").
- A changed fact: job title, employer, dates or degree.
- A broken build: compile errors, lint errors, an ATS read that can't extract name or email, or more
  pages than `max_pages`.

## Criteria

| key | max | judged on | rules |
|---|---|---|---|
| relevance | 20 | most relevant evidence first; the relevant role expanded and the rest condensed; distractors cut; the "why you" and 10-second tests | C-5, C-6, C-8, C-15 · T-9 / N-15 |
| keywords | 20 | must-have keywords present, in context, with the ad's spelling; title near the top; acronyms; no stuffing | C-2, C-3, C-11 · T-1, T-2, T-11 / N-1, N-12 |
| evidence | 20 | results in the track's terms (technical: performance, scale, business effect; non-technical: KPIs, quota, volume, speed, satisfaction); bullet formula | C-7 · T-4, T-12 / N-2…N-9 |
| summary | 10 | target title + two best requirements + one proof; length; voice | C-4 · T-5 / N-12, C-14 |
| skills | 10 | the track's skills-section rules | C-9, C-10 · T-3, T-13 / N-11 |
| format | 10 | layout for the application route, length, section order, consistency, extras, a clean ATS text read (`uv run cv ats`: no words run together) | C-12, C-16 · T-6, T-7, T-8, T-14, T-15 / N-10, N-13, N-14 |
| language | 10 | the person's voice, no generic AI phrasing, no inflated words, typos, tense | C-13 · T-10 |

**Pass:** no blockers, no fixable `must` finding, a total of 85 or more, and every criterion at 60%
of its maximum or above. `uv run cv round list` recomputes the verdict from the scores; when it
disagrees with the judge, the rubric wins.
Otherwise the verdict is **revise**, or **needs-input** when the only fixes left need information the
knowledge base doesn't have. Rules listed in `classification.yaml` `borrow` are judged too.

Finding severities: **must** (blocks a pass), **should** (costs points), **could** (polish).

## Loop policy (`uv run cv round list <app>` applies it and prints the next step)
1. Round 1: the writer drafts `cv.yaml`, builds, and saves the round (`uv run cv round save <app>`
   snapshots `cv.yaml`, `cv.pdf` and `build.yaml` into `judging/round-N/`; the writer adds
   `changes.md`).
2. The judge scores the round and writes `judging/round-N/judge.yaml`.
3. The loop stops at **pass** once no fixable `must` or `should` finding is left. A pass that still
   lists fixable `should` findings gets another round, because the aim is the best CV, not the
   threshold. The loop also stops after **4 rounds**; on a **plateau** (the total rose less than
   3 points over the previous round), which also ends the extra rounds after a pass; or when only
   **needs-input** findings remain. In the last case the main agent asks the person (a sense-making
   fact pass), records the answers in the knowledge base, and then runs one more round.
4. Otherwise the writer edits from the findings, builds, saves round N+1, and the judge scores it.
5. When the loop stops, the best round is kept: a passing round over a failing one, then the higher
   total. If that isn't the last round, the stop line says `keep round K`; restore
   `judging/round-K/cv.yaml` and rebuild.

## judge.yaml (judging/round-N/judge.yaml)

```yaml
round: 2
track: technical
verdict: revise             # pass | revise | needs-input
total: 81
scores:
  relevance: {score: 17, max: 20}
  keywords: {score: 16, max: 20}
  evidence: {score: 17, max: 20}
  summary: {score: 7, max: 10}
  skills: {score: 7, max: 10}
  format: {score: 9, max: 10}
  language: {score: 8, max: 10}
blockers: []                # truthfulness or build problems, one line each
findings:
  - id: F1
    severity: must          # must | should | could
    rule: T-3
    where: skills[2]
    problem: "Soft skills (Stakeholder management, Workshop facilitation) sit in the technical skills list."
    fix: "Remove them from skills; stakeholder work is already proven in experience[2].bullets[0]."
    needs_input: false
  - id: F2
    severity: should
    rule: N-1
    where: experience[0].bullets[1]
    problem: "No figure for how many buyers used the forecast ranges."
    fix: "Add the number of buyers if the person knows it."
    needs_input: true
    question: "When the buyers started using the forecast ranges, how many of them were working with them?"
summary: "What improved since the last round and what still holds the score back, in one or two sentences."
```

Every `fix` uses only facts from the knowledge base. Anything that needs a new fact becomes
`needs_input: true` with a neutral, sense-making `question`: no "why", and it goes back to the
moment (`sense-making-interview.md`).
