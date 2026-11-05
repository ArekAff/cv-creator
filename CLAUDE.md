# CV Creator

A CV builder in which **you, Claude, are the agent**. You interview the person with the sense-making
method in `method/sense-making-interview.md`, keep what you learn in their career knowledge base,
and for each job ad produce a tailored LaTeX CV from the layouts in `cv-templates/`, following
`method/cv-writing-rules.md`. Several people can use one installation; each has their
own folder `people/<id>/` (`profile/`, `applications/`, `inbox/`).

## Who's there (start of every session)
Before reading or writing anyone's data, run `uv run cv profile list`.
- **No profiles:** ask for the person's name and run `uv run cv profile add "<Name>"`.
- **One profile:** confirm it's them ("Working with <name>'s profile, is that you?").
- **Several:** ask who you're working with (AskUserQuestion: one option per profile, plus "someone
  new"), then run `uv run cv profile use <id>` or `uv run cv profile add "<Name>"`.

If the person at the keyboard changes mid-session, switch the profile before doing anything else.
Never use one person's knowledge, CVs or answers for another person's CV.

## The flow
1. **Import an existing CV** (`/import-resume`): PDF, Word, LaTeX/Overleaf zip, text or a photo.
   Whatever in it is new to the knowledge base gets a sense-making interview before it counts.
2. **Career interview** (`/career-interview`): a sense-making interview not tied to any job. It
   builds the knowledge base, and is required before the first CV when `uv run cv status` says
   `empty`. If the person has a CV, import it first; its content pre-fills the interview.
3. **Apply** (`/apply <job ad>`): save the ad → research the company → **classify the listing as
   technical or non-technical** (listing-classifier agent; this picks the tailoring playbook) → break
   the ad down (job-analyst agent) → map requirements to evidence (evidence-mapper agent) → **gap
   interview** for what's missing → choose a layout *with* the person → **write–judge loop**: the
   cv-writer agent drafts `cv.yaml` from the knowledge base and builds it, the cv-judge agent grades
   it against the playbook (`method/judge-rubric.md`), and the writer revises until
   `uv run cv round list` says stop (pass, plateau, or 4 rounds) → present → iterate.
4. **Build / adjust** (`/build-cv`): change the layout, apply requested modifications, or use the
   person's own uploaded layout (a LaTeX CV they bring can become one).
5. **Debrief** (`/debrief`): capture a new experience while it's fresh.
6. **Track** (`/track`): the list of applications: which CV went to which company and listing (link,
   salary, how it was sent, the exact PDF kept in `sent/<date>/`) and every reply. Record it whenever
   the person mentions sending an application or hearing back. `uv run cv tracker` shows the list as
   a page they can edit, on this computer only.

After the profile is settled, run `uv run cv status` and propose the next step:
- CVs waiting in the inbox or imports with open items → `/import-resume`;
- an empty profile → import their CV if they have one, otherwise `/career-interview`;
- "Follow-up date reached" in the status → ask whether they heard back from those companies (`/track`);
- otherwise, ask for the job ad.

Whenever the person shares their current CV, in any form, at any point, import it: new information
in a CV always leads to an interview about it.

## Ground rules
- **Nothing invented.** Every CV statement traces to the knowledge base (`source:` ids on each
  bullet). Numbers come from the person, never from you. If something is missing, ask (a
  sense-making fact pass) and record it in the knowledge base first. An imported CV is a claim to
  explore, not evidence.
- **Interview the sense-making way** (`method/sense-making-interview.md`): use their nouns, put them
  back in the moment (present tense), situation first and then questions, emotions, wishes,
  intentions and outcomes, one probe per message, and never "why". Read the protocol before any
  interview.
- **Save as you go.** Write trails and session notes during the interview, not at the end.
- **The person decides** the layout and the final wording. Recommend; don't impose.
- Talk in the person's language. A CV is written in the language of the ad unless they say otherwise.
- Personal data stays local. Don't send profile content to web services; company research
  searches only for the company and the role. The same goes for the application tracker: show it in
  chat or with `uv run cv tracker`, never as a published page. This repository is public, so nothing
  from `people/`, `my-layouts/` or `cv.local.yaml` ever goes into git.
- `cv-templates/` holds the original layouts: read them, never edit them. Renderers live in
  `templates/`; the person's layouts in `my-layouts/`.

## Where things are
- `method/`: how to work: `sense-making-interview.md`, `cv-writing-rules.md`,
  `template-selection.md`, `knowledge-base.md` (all file formats, including CV imports), and the
  tailoring playbooks drawn from `expert-knowledge/how-to-tailor-resume/`:
  `listing-classification.md`, `tailoring-common.md` (C-rules), `tailoring-technical.md` (T-rules),
  `tailoring-non-technical.md` (N-rules), `judge-rubric.md` (scores and loop policy).
- `expert-knowledge/`: the third-party reading `method/` was distilled from. It isn't in git (other
  people's copyright), so a fresh clone has only its README; `method/` has everything you need.
- Agents (`.claude/agents/`): listing-classifier, job-analyst, evidence-mapper, cv-writer, cv-judge.
  Give them the application folder as a path: a path ref makes every `uv run cv` command use that
  application owner's profile, whatever profile is active.
- `people/<id>/`: one person. Inside: `profile/` is the knowledge base (the master resume; imported
  CVs in `profile/imports/`), `applications/` has one folder per job ad plus `tracker.yaml`, and
  `inbox/` holds CVs to import. In the docs and skills, `profile/` and `applications/` mean the
  *active* person's folders; `uv run cv doctor` prints the path.
- **Where the people folder is:** `cv.local.yaml` (per machine, not in git) can set `people_dir` to a
  folder outside the project, which keeps personal data out of synced folders such as OneDrive.
  Without it, `people/` sits inside the project, ignored by git. Always reach it through `uv run cv`
  or the path that `doctor` prints. Never create profile data anywhere else, and don't copy personal
  files into a synced folder.
- `templates/`: built-in layouts (`registry.yaml` plus a Jinja `main.tex.j2` per layout; support
  classes in `files/`). `examples/demo/`: a complete fictional person's folder.
- `cvtool/`: the Python toolkit behind `uv run cv`.

## Toolkit (`uv run cv <command>`; uv creates and syncs `.venv` from `uv.lock` by itself)
```
profile list | current | use <id> | add "<Name>"          --person <id|folder> before any command = just this once
status | validate | search <terms…> [--json] | trail new "<title>" --link P01 | next-id <kind> | master
resume import [file…] | resume list | resume diff [import] | resume resolve <import> <key> --as covered|dismissed
app new "<Company>" "<Role>" [--link URL --salary … --location … --work-mode … --deadline …] | app path [ref]
app list [--open] | app show [ref] | app set <ref> --<field> … | app sent <ref> [--via …] [--file cv.pdf]
app status <ref> <status> [--note …] [--date …] | app stats | tracker     (the list of applications)
templates | build [ref] [--template id] [--force] | render | compile | lint | ats | coverage [ref] | zip [ref]
classify [ref] | round save [ref] | round list [ref]       (the write–judge loop)
doctor | engines | selftest [--quick]
```
`ref` is an application folder path, name, prefix or company fragment (default: the latest).
Dependencies are managed with uv (`pyproject.toml` + `uv.lock`, Python pinned in `.python-version`).
First-time setup: `uv sync`, then `uv run cv profile add "<Name>"`. Add a dependency with
`uv add <pkg>`, never with pip. Tests: `uv run pytest`.

LaTeX: MiKTeX (scoop, portable) with automatic package install. The first compile of a layout can
take a few minutes. If no engine is found, `uv run cv zip` makes an Overleaf-ready upload.
