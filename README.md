# CV Creator

Tailored LaTeX CVs built from what you actually did, collected by a Claude agent in
**sense-making interviews**.

```
 your current CV ──► import ──► diff vs. knowledge base ──► interview about what's new ─┐
 (PDF/DOCX/LaTeX/photo)                                                                ▼
 career interview ──► profile/ (knowledge base = master resume) ◄── debrief (new experiences)
 (sense-making,                       │
  no job ad)                          ▼
 job ad ──► technical or ──► requirements ──► evidence map ──► gap interview ──► layout choice
            non-technical?   (job-analyst)   (evidence-mapper)  (sense-making)    (with you)
            (listing-classifier)                                                     │
                                                                                     ▼
                         ┌──► cv-writer: drafts / revises cv.yaml, builds the PDF ──┐
                         │                                                           ▼
                         └── revise ◄── cv-judge: scores it against the playbook ──► pass ──► PDF
```

Each person who uses the installation has their own profile (`people/<name>/`), so two people
can share one laptop without their careers getting mixed up.

- **The interview method** comes from Linderman, Baker & Bosacker (2011), *Surfacing and
  transferring expert knowledge: the sense-making interview* (`expert-knowledge/HRDIArticle.pdf`):
  pick real episodes ("strategic trails"), list their actions, then relive the gaps between the
  actions through the probing cycle (situation, questions, emotions, wishes, intentions). No
  "why", no hindsight. The protocol is in `method/sense-making-interview.md`.
- **The CV rules** come from `expert-knowledge/guide-to-great-cv.txt`: master resume, company
  research, ad breakdown, title alignment, natural keywords with outcomes, no stuffing and no
  exaggeration, consistent formatting, one folder per application. The details are in
  `method/cv-writing-rules.md`, and `uv run cv lint` checks them.
- **Tailoring to the job** follows `expert-knowledge/how-to-tailor-resume/`, whose guides
  separate technical from non-technical listings. Every ad is first classified as one or the other.
  Then the matching playbook applies: `method/tailoring-common.md` for every listing, plus
  `tailoring-technical.md` (stack signals, tools named in bullets, a grouped skills list,
  seniority-based structure) or `tailoring-non-technical.md` (results in the ad's own terms: quota,
  KPIs, proof for every soft skill).
- **The editor–judge loop**: a writer agent drafts the CV from your interviews, and a judge agent
  scores it out of 100 against the playbook (`method/judge-rubric.md`). The judge first checks
  that every claim matches what you told it. The writer revises from the judge's findings, round
  after round, until the CV passes (85+) with nothing fixable left, stops improving, or reaches four
  rounds. The best round is the one kept. When an
  improvement needs a fact the knowledge base doesn't have, Claude asks you instead of guessing.
  Every round is kept in `judging/round-N/`.
- **The layouts** are the seven in `cv-templates/`, turned into renderers (`templates/`), plus any
  layout you add to `my-layouts/`.

The reading in `expert-knowledge/` was written by other people, so it isn't published here
([`expert-knowledge/README.md`](expert-knowledge/README.md) lists it). The tool doesn't need it: the
rules it works from are in `method/`.

## Setup (once)

Python and its dependencies are managed with [uv](https://docs.astral.sh/uv/): `pyproject.toml`
declares them, `uv.lock` pins the exact versions, and `.python-version` pins Python 3.12. If uv is
missing, install it with `scoop install uv` or `winget install astral-sh.uv`.

```bash
uv sync
```

```bash
uv run cv profile add "Your Name"
```

`uv sync` creates `.venv` with the pinned Python and the locked packages: PyYAML, Jinja2, pypdf,
and pytest for development. Every `uv run` keeps `.venv` in sync with the lockfile, so there is
nothing to reinstall after an update. `uv run cv profile add` creates your folder
`people/<name>/` and makes it the active profile. You don't have to run it yourself: Claude asks
for your name the first time. `uv run cv doctor` shows which LaTeX engine was found.

Compiling needs a TeX distribution: MiKTeX with automatic package install (on Windows,
`scoop install miktex`) or TeX Live. Without one, `uv run cv zip` gives you an Overleaf-ready upload.

Check that everything works (all 7 layouts × English/Polish/special characters):

```bash
uv run cv selftest
```

## Using it

Open this folder in Claude Code and type:

| You type | What happens |
|---|---|
| `/import-resume <your CV file>` | Reads your current CV (PDF, Word, LaTeX `.tex` or Overleaf zip, text, photo). Everything in it that your profile doesn't know yet becomes a short interview. |
| `/career-interview` | First interview about your whole career (≈20–60 min, can be split). Builds `profile/`. |
| `/apply <paste the ad, a file or a link>` | Tailored CV for that job. Classifies the ad, interviews you briefly about any requirement your profile doesn't cover yet, then runs the editor–judge loop until the CV passes. |
| `/build-cv <what to change>` | Change the layout, colours, section order or length, or use your own layout. |
| `/debrief <what you just did>` | Add a new project or achievement while you still remember the details. |
| `/track <what happened>` | Keep your list of applications: which CV went to which company and listing, the salary and link, and every reply ("sent the Acme CV today", "Vantaro called me"). |

You can also just say "I want a CV for this job: …" or attach your CV, and Claude will follow the
same steps. Another way to hand over a CV is to drop it into your `inbox/` folder
(`people/<name>/inbox/`). The next session notices it, and `uv run cv status` lists it.

### Several people, one laptop

Claude asks who's using it at the start of each session and switches to that person's profile.
Each person's interviews, CVs and applications live only in their own folder. Their knowledge is
never used for someone else's CV. You can also switch yourself:

```bash
uv run cv profile list
```

```bash
uv run cv profile use sam
```

### Tracking applications

Every job ad you apply to gets an entry in your `applications/tracker.yaml`: company, position,
link to the listing, salary as written in the ad, location and work mode, deadline, the salary you
asked for, a contact, the next step and notes. When you tell Claude you've sent it (or run
`uv run cv app sent <app>`), the exact PDF and `cv.yaml` that went out are copied to
`sent/<date>/` in that application's folder. Later rebuilds can't change what the company has, and
before an interview you can open the version they read. Replies ("they called", "rejected",
"interview on Thursday") go into the entry's history with the date. `uv run cv app stats` shows
which layouts, headlines and channels get answers.

To see the whole list, ask Claude, run `uv run cv app list`, or open it as a page:

```bash
uv run cv tracker
```

The page opens in your browser. You can sort, search, change a status from a menu, edit details,
add a listing you want to apply to later, and open the CV each company received. It runs only on
this computer (Ctrl+C stops it), works on the same file as Claude, and shows the active profile
first. If there are several profiles, a menu switches between them.

## What gets created

Personal data goes into a `people/` folder, inside the project by default and ignored by git.
`cv.local.yaml` can move it elsewhere (see Notes).

```
people/
  .active                          which profile is active
  alex/                            one folder per person
    inbox/                         drop CVs here to import them
    profile/                       the knowledge base (never sent anywhere)
      profile.yaml timeline.yaml skills.yaml insights.yaml
      trails/T001-....yaml         one file per story from the interviews
      sessions/                    interview notes in your words
      imports/2026-11-02-cv/       an imported CV: original, text, what it says, the diff
      evidence/                    reviews, emails, certificates you add
      master-resume.md             everything in one document (uv run cv master)
    applications/
      tracker.yaml                 every listing: link, salary, the CV sent, the replies
      2026-11-02_acme_data-analyst/
        posting.md research.md requirements.yaml coverage.yaml cv.yaml notes.md
        cv/main.tex (+ support files, main.pdf)
        Your_Name_CV_Acme_2026-11-02.pdf
        sent/2026-11-03/           the exact CV that went out (PDF + cv.yaml)
  sam/
```

`examples/demo/` is a complete fictional person's folder, including an imported older CV with open
items. Run `CV_DATA_DIR=examples/demo uv run cv status` to see it.

## Commands

```
uv run cv profile add "<Name>" | profile use <id> | profile list | profile current    (--person <id or folder> = one command only)
uv run cv resume import [file] | resume list | resume diff [import] | resume resolve <import> <key> --as covered|dismissed
uv run cv status | validate | search <terms> | master | trail new "<title>" --link P01 | next-id <kind>
uv run cv app new "<Company>" "<Role>" [--link URL --salary …] | app list | app show <app> | app set <app> --salary …
uv run cv app sent <app> [--via …] | app status <app> screening|interview|rejected|offer … | app stats | tracker
uv run cv templates | build [app] [--template id] | lint | coverage | ats | zip | engines | doctor | selftest
uv run cv classify [app] | round save [app] | round list [app]     (the editor–judge loop)
```

## Layouts

| id | look | best for |
|---|---|---|
| `jakes` | classic one column, small caps, dense | tech, data, graduates, ATS-heavy employers |
| `swe` | Jake's with Lato and icons | software engineering, start-ups |
| `minimal` | quiet serif, label — description lines | analysts, research, public sector, career changers |
| `elegant` | formal, navy, labelled details | finance, law, consulting, institutions |
| `altacv` | two columns, colour, tags, achievements | start-ups, product, marketing, design-adjacent |
| `curve` | academic, dates in a key column | academia, research, long CVs |
| `receive` | sidebar with photo and skill bars | creative roles, small companies, photo-expected markets |

Some original templates depended on files that weren't in `cv-templates/`:
- `resume.cls` (Elegant), `settings.sty` (CurVe) and `ReCeiVe.cls` (ReCeiVe) were missing.
- AltaCV's class isn't distributed by CTAN or MiKTeX.

All four are reimplemented in `templates/<id>/files/` to keep the same commands and look. To use an
original class instead, put it in the same folder.

Every layout, including your own, gets real spaces in the PDF's text layer: the renderer adds
pdfTeX's `\pdfinterwordspaceon` after `\documentclass`. Without it, applicant tracking systems can read
"Data AnalystJul 2023" where the page shows a title and its dates. It doesn't change how the page
looks. `uv run cv ats` flags any words that still run together.

### Layout credits

The layouts are other people's designs. `cv-templates/` holds the originals unchanged, and
`templates/` adapts them into renderers filled from `cv.yaml`, with the missing classes reimplemented
as described above.

| Layout | Original | Author | Licence |
|---|---|---|---|
| `jakes` | [Jake's Resume](https://github.com/jakegut/resume), based on [sb2nov/resume](https://github.com/sb2nov/resume) | Jake Gutierrez | MIT |
| `swe` | SWE Resume Template | Audric Serador | MIT |
| `minimal` | [Minimal CV Template](https://www.overleaf.com/latex/templates/minimal-cv-template/hnvkvrchysmg) | Matheus Hostert | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `elegant` | [Elegant resume template](https://www.overleaf.com/latex/templates/elegant-resume-template/gcnbfnxkcwby) | Christian Maria Giannetti | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `altacv` | [AltaCV](https://github.com/liantze/AltaCV) | LianTze Lim | [LPPL 1.3 or later](https://www.latex-project.org/lppl/) |
| `curve` | [A Customised CurVe CV](https://www.overleaf.com/latex/templates/a-customised-curve-cv/mvmbhkwsnmwv) | LianTze Lim | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `receive` | [ReCeiVe](https://www.overleaf.com/latex/templates/receive/dbzynfgjmxqy) | Ged Lex | [LPPL 1.3c](https://www.latex-project.org/lppl/) |

## Notes

- **Where the data lives:** by default `people/` is created inside the project. If the project is in
  a synced folder such as OneDrive, keep profiles, interviews, imported CVs and applications on your
  computer instead: create `cv.local.yaml` in the project folder (machine-specific, not in git) with
  the line `people_dir: C:/path/to/people`. A `CV_PEOPLE_DIR` environment variable overrides both.
  `uv run cv doctor` shows the location in effect and warns if it's inside OneDrive. To move the
  data, copy the `people` folder and change the line.
- **Privacy:** profiles keep people's data apart for Claude, but they aren't password-protected.
  Anyone using this Windows account can open any profile folder.
- Backups: data outside a synced folder is only as safe as your computer's disk. Copy the `people`
  folder somewhere safe now and then.
- `people/`, `cv.local.yaml` and your own layouts in `my-layouts/` are in `.gitignore`, so no personal
  data goes into git.
- Optional: to stop Claude Code asking before each toolkit command, add this to
  `.claude/settings.json` (or `.claude/settings.local.json`):
  ```json
  { "permissions": { "allow": ["Bash(uv run cv:*)"] } }
  ```
- Tests: `uv run pytest` (pytest is in the `dev` dependency group that `uv sync` installs).
- Adding a dependency: `uv add <package>` (updates `pyproject.toml` and `uv.lock`); don't use pip.

## Licence

The project's own code and docs are under the [MIT licence](LICENSE). The layouts in `cv-templates/`,
and the renderers and classes in `templates/` based on them, keep their original licences: see
[Layout credits](#layout-credits).
