---
name: apply
description: Tailor a LaTeX CV to a job ad. Saves the ad, classifies it as technical or non-technical (listing-classifier), breaks it down, maps every requirement to evidence in the career knowledge base, runs a sense-making gap interview for what's missing, picks a layout with the person, then runs the write–judge loop (cv-writer drafts, cv-judge grades against the track's tailoring playbook, the writer revises) until the CV passes. Use whenever the person shares a job listing (text, file or URL) or asks for a CV for a specific job.
argument-hint: "<job ad text | path to a file | URL>"
---

# Apply: from job ad to tailored CV

Job ad: $ARGUMENTS (if empty, ask for it: pasted text, a file, or a link).

Read as you need them: `method/listing-classification.md`, `method/judge-rubric.md`,
`method/sense-making-interview.md`, `method/template-selection.md`, `method/knowledge-base.md`. The
writing rules (`tailoring-*.md`, `cv-writing-rules.md`) are applied by the agents. Talk to the person
in their language. Always give agents the application folder as a **path**; the toolkit then uses
that folder owner's profile automatically.

## 1. Is there career knowledge to work from?

Make sure the active profile belongs to the person applying (`uv run cv profile current`; see
"Who's there" in CLAUDE.md), then run `uv run cv status`.
- **They brought their current CV** (attached, a path, pasted, or waiting in their inbox): save the ad
  first (step 2), then run the `import-resume` skill. Whatever in the CV is new gets its interview
  before you tailor anything. Come back here afterwards.
- **empty**: first save the ad (step 2) so it's not lost. Explain that you'll start with a career
  interview **not** tied to this ad, to capture as much of their experience as possible, and run the
  `career-interview` skill fully (importing their CV first if they have one). Come back afterwards.
- **scaffold / partial**: continue. The gap interview below fills what this ad needs. Mention that a
  full career interview would make future applications faster.
- **ready**: continue.

## 2. Save the ad and open the application folder

- If it's a URL, fetch it (WebFetch). If that fails or needs a login, ask them to paste the text.
- If the listing is already in their tracker (`uv run cv app list`, e.g. saved earlier from the
  tracker page), use that folder (`uv run cv app path <ref>`) instead of opening a second one.
- Otherwise `uv run cv app new "<Company>" "<Role>" --link "<url>" --source "<where they found it>"
  --salary "<as written in the ad>" --location "<city>" --work-mode remote|hybrid|on-site
  --deadline YYYY-MM-DD` prints the folder. Give only what the ad or the person says. Details found
  later go in with `uv run cv app set <app> --salary "…"` (etc.).
- Paste the **complete ad verbatim** into `posting.md` under "Original posting".

## 3. Research the company (guide A2)

Keep it to a few minutes. Look at the company website, especially the careers and about pages, for
how they describe themselves, the values they repeat, and their culture and language. If possible,
see what people in this role highlight. Search only for the company and the role, never for the
person. Write `research.md`. Without web access, ask what the person knows and note it.

## 4. Classify the listing, then break it down

1. Launch the **listing-classifier** agent with the folder path. It writes `classification.yaml`
   (technical or non-technical, family, seniority, rules to borrow); that choice selects the tailoring
   playbook for everything after. Tell the person the track in one line, and ask them to confirm if
   the confidence is low.
2. Launch the **job-analyst** agent with the folder path. It writes `requirements.yaml` and uses the
   track (a technical ad's 5–8 screening signals first; a non-technical ad's results vocabulary).
   Show the person a compact view: title and seniority, must-haves (most important first),
   nice-to-haves, key tools and keywords.

## 5. Map requirements to evidence

Launch the **evidence-mapper** agent with the folder path. It writes `coverage.yaml` with
`strong | partial | gap` per requirement, evidence ids, and a neutral opener for each gap. Run
`uv run cv coverage <app>` for the keyword view. Show the person the "cheat sheet":

| Requirement | Must/nice | Status | Evidence |
|---|---|---|---|

Remind them, briefly and kindly, that ads are aspirational: a few gaps are normal, and the core
responsibilities matter most (guide [33]).

## 6. Gap interview (sense-making, focused)

Goal: for every requirement, establish the **current, true state** of their qualification. Order:
must-haves with `gap`, then must-haves with `partial`, then nice-to-haves if they want. Open today's
session file `profile/sessions/<date>-gap-interview-<company>.md`.

For each requirement:
1. **Opener**, neutral and in plain words: "Has there been a time, at work, in your studies, in a
   side project or volunteering, when you <did what the requirement describes>?" Then switch to
   their nouns.
2. **If yes:** it's a trail. If it extends an existing trail, add actions and gaps there. Otherwise
   `uv run cv trail new "<their title>" --link <id>` with `why_chosen: "evidence for <R0x> of <app
   folder>"`. Run the protocol at quick or standard depth: action outline → probe the pivotal gaps
   (situation first, then questions, emotions, wishes, intentions, outcomes) → fact pass (scale,
   numbers only if real, proof) → sponsor check of 1–2 accomplishment statements. Save the trail,
   update `skills.yaml` with evidence, and set `coverage.yaml` to `strong` or `partial`.
3. **A detail confirmed with a plain question** (a technique, a tool, a figure) goes into the trail
   it belongs to (`skills_used`, `outcomes`) or `skills.yaml` `notes`, not only into the session
   file: CV bullets can cite trails and timeline entries, not session notes.
4. **If no:** don't push and don't stretch. Record it honestly in `coverage.yaml`: `status: gap` with
   a note such as "no experience", "currently learning X since <date>", or "adjacent: <what>".
5. Write the exchange to the session file as you go.

Finish with `uv run cv validate`, then a short summary: strong / partial / gap counts, what
surfaced, and what stays a gap. Ask whether they still want to apply. (They usually should.)

## 7. Choose the layout with them

Follow `method/template-selection.md`, including what the track means for the layout (technical and
non-technical online applications both default to a single column). Recommend one layout with a
one-line reason tied to this job, plus 1–2 real alternatives and "my own layout / modify one". Ask
with AskUserQuestion. Record the choice, the reason and any requests in `notes.md`. The cv-writer
reads it from there.

## 8. The write–judge loop

`method/judge-rubric.md` has the full policy; `uv run cv round list <app>` applies it and prints the
next step. Repeat until it says **stop**:
1. **cv-writer**, round 1: launch it with the folder path and "round 1". It drafts `cv.yaml` from the
   knowledge base by the playbook, builds, runs `uv run cv round save <app>`, and writes
   `judging/round-1/changes.md`.
2. **cv-judge**, round N: launch it with the folder path and the round number. It grades the round
   and writes `judging/round-N/judge.yaml`.
3. Run `uv run cv round list <app>` and follow it:
   - `next: cv-writer round N+1`: launch the writer with that round number; it revises from the
     findings. This also happens after a pass that left fixable `should` findings.
   - `next: ask the person …`: the remaining improvements need facts the knowledge base doesn't have.
     Ask the judge's `question`s one at a time in the sense-making style (a short fact pass), record
     the answers in the knowledge base (trail outcomes, skills), then run one more writer round.
   - `stop: pass | plateau | 4 rounds`: go on to step 9. If the line says `keep round K`, an earlier
     round is the better CV: copy `judging/round-K/cv.yaml` over `cv.yaml` and rebuild.
4. After each round, tell the person in one line: the total, and what improved.

Log every round's verdict and total in `notes.md`. If the person wants to stop early, stop.

## 9. Present

- Send the final PDF (SendUserFile, display render) and the folder path.
- In a few lines: the track and why; the layout; what the CV emphasises for this job; the score trend
  across rounds and what still holds the score back; which requirements are honest gaps and how the
  CV handles them; page count and the ATS-read result.
- If the last `judge.yaml` still has `needs_input` questions, they're facts that would make the CV
  stronger. Offer them as an optional short fact pass, one question at a time. If the person answers,
  record the answers in the knowledge base and run one more writer and judge round.
- Remind them that applying in the first days after a posting matters (C-17).

## 10. Their changes

Apply requested changes through the **cv-writer** (a new round with the request as its instructions)
or via `cv.yaml` `meta` options (`method/template-selection.md` §3), then run one **cv-judge** round
so changes don't undo the tailoring. Rebuild, re-send, and log each request in `notes.md`.

## 11. Close the loop

- `uv run cv app status <app> ready`. When they send it: `uv run cv app sent <app> --via "<how>"`.
  This keeps the exact PDF and `cv.yaml` that went out in `sent/<date>/`, so a later rebuild can't
  change what the company has. If a form asked for their expected salary, record what they gave
  (`uv run cv app set <app> --expected-salary "…"`).
- Ask them to tell you when they hear back (the `track` skill records it), so `uv run cv app stats`
  can show what works (guide A7). The whole list is on the tracker page (`uv run cv tracker`).
- Offer a tailored cover letter. If they want one, write `cover-letter.md` in the folder from the same
  evidence, specific to this company and role, never a template with the name swapped.
- New material from the interviews is already in `profile/`, so the next application starts from a
  richer base.
