# CV writing rules

The primary source is `expert-knowledge/guide-to-great-cv.txt` (line numbers in brackets). Where
this file adds general CV practice, it says so. `uv run cv lint` checks the mechanical parts.

## A. The guide, rule by rule

### A1. Start with a master resume [7–16]
- The knowledge base in `profile/` **is** the master resume: the full, unfiltered career that
  every tailored CV is drawn from. It is never sent to anyone. Length does not matter.
- It includes all responsibilities (not only the headline ones), projects with details, numbers and
  outcomes, tools, side projects, volunteering and **partial or in-progress certifications**
  (`status: in-progress`).
- Keep supporting material next to it: performance reviews, project summaries, emails praising the
  work, in `profile/evidence/`. Reference it from `outcomes[].source`.
- Update it every few months, because people forget the specifics. After a big project, run
  `/debrief`. `uv run cv master` writes the readable version to `profile/master-resume.md`.

### A2. Research the company [18–23]
- Read how the company describes itself: its language, the values it repeats, its culture.
  The careers page tells you the most and is the page applicants most often skip.
- Look at people currently in the target role (e.g. LinkedIn). What they highlight is what is
  actually valued, which isn't always what's in the posting.
- Write it down in `research.md`. Use their language in the headline, summary and bullets **only
  where it is true for the candidate**.

### A3. Break down the job description [25–33]
- Separate real requirements from nice-to-haves. Things listed first or mentioned more than once
  matter most (`type: must | nice`, `signal:` in `requirements.yaml`).
- Build the requirement → own experience "cheat sheet": that is `coverage.yaml`.
- Pay attention to specific tools, technical skills and methodologies. Large companies screen on them
  before a human reads anything, so they go into `keywords` exactly as the posting spells them.
- **Don't let the candidate talk themselves out of applying** because a few boxes are unticked. Ads
  are aspirational; focus on the core responsibilities. Nice-to-have gaps are normal.

### A4. Line up your title [35–38]
- If their titles already match the target role, fine.
- If not, add a **professional headline** at the top that connects the two, built from true facts:
  "Client Relations Specialist with Customer Success Experience" for a Customer Success Manager
  ad. Pattern: *current or most recent title* + *with / · * + *the target's focus that they really
  have*. Never claim the target title itself if they haven't held it.

### A5. Keywords [40–45]
- Work the posting's keywords in **naturally**: summary, skills, experience bullets, education.
- Fold them into real bullets rather than piling them into the skills list. If the ad keeps saying
  "cross-functional collaboration", write a bullet where that actually happened.
- Pair keywords with outcomes or numbers wherever possible. That is what clears the screen *and*
  impresses the reader.

### A6. Mistakes to avoid [47–54]
- **Keyword stuffing.** Every keyword must connect to something real in the knowledge base. A skill
  listed in the skills section should, ideally, also appear in a bullet.
  `uv run cv lint` flags skills not found in the knowledge base and skills never shown in action;
  `uv run cv coverage` flags keywords that appear *only* in the skills list.
- **Over-relying on templates.** A template with text dropped in still reads as generic. Tailor the
  layout too: section order, which sections exist, headline, emphasis, accent colour, length. See
  `method/template-selection.md`.
- **Lying or exaggerating.** Every claim must trace to the knowledge base (`source:` on each
  bullet). Numbers come from the person, never from you. "About" and ranges are fine.
- **A generic cover letter.** If you write one, tailor it to this company and this role. Swapping
  only the company name is noticed.
- **Formatting.** Inconsistent dates, random font changes and typos undermine everything else. The
  renderer formats every date in one style. The `cv-judge` agent reads the final text for typos and
  consistency in every round.

### A7. Stay organised [56–59]
- One folder per application: tailored CV, research notes, the original posting
  (`uv run cv app new` creates it).
- Clear file names, company + date: the build writes `<Name>_CV_<Company>_<YYYY-MM-DD>.pdf`.
- Track which versions get responses: `uv run cv app sent <app>` when it goes out (it keeps that
  exact CV in `sent/<date>/`), `uv run cv app status <app> screening|interview|rejected…` when they
  hear back, and `uv run cv app stats` (reply rate per layout, headline, source and channel).
  `uv run cv tracker` shows the whole list as a page on this computer.

## B. Writing the bullets (general practice, consistent with the guide)

- **Formula:** strong verb + what you did + context or scale + result. "Rebuilt the weekly regional
  report around the five KPIs six managers actually used, cutting preparation from ~6 hours to 30
  minutes a week."
- Draw bullets from the trail's confirmed `accomplishments`, `outcomes` and `intentions`. The
  sense-making material is what makes them specific.
- Past tense for past roles, present tense for the current role. No "I", "my" or "responsible
  for".
- 2–5 bullets for recent roles, 1–2 for older ones; the most relevant first. One or two lines each.
- Numbers only where real; a qualitative result beats an invented number.
- Mirror the posting's terms when the meaning is the same ("dashboards" vs "reports"). Keep the
  person's own term where it is more precise, and note the mapping in the trail's `keywords`.

## C. Shape of the document (general practice)

- Reverse-chronological. One page under ~10 years of experience, two at most otherwise (academic CVs
  are the exception). `meta.max_pages` makes the build warn.
- Order sections by what this employer cares about most. Graduates may lead with education.
- Summary: 2–4 lines, tailored, with no generic adjectives. Built from `insights.summary_drafts` and
  the target role.
- Skills: grouped and specific, only what the knowledge base supports, with qualifiers where honest
  ("Google Cloud (certification in progress)").
- Personal data: name, location (city), phone, email, relevant links. **No** date of birth,
  marital status, ID numbers. A photo only where it is the local norm and the person wants it
  (common in Poland, Germany, Austria and Switzerland; avoided in the US, UK, Ireland and Canada).
- Paper: A4 everywhere except the US and Canada (letter).
- **Poland:** CVs end with a consent clause for processing personal data (RODO/GDPR):
  `gdpr_clause: true` inserts the standard text in Polish or English. Use the employer's own
  wording if the ad gives one.
- Language: the language of the ad, unless the person or the ad says otherwise.

## D. Before you show the result

1. `uv run cv build` succeeds: compiles, page count within `max_pages`, no lint errors.
2. ATS read (part of build): name, email and key keywords extractable from the PDF text.
3. The write–judge loop has ended with `uv run cv round list` saying "stop": the `cv-judge` checked
   truthfulness against the knowledge base, the track's tailoring playbook (`tailoring-*.md`), these
   rules and typos (`judge-rubric.md`).
4. Show the PDF and say plainly what was emphasised, what was left out and why, and which
   requirements remain honest gaps.
