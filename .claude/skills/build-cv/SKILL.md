---
name: build-cv
description: Render, compile and adjust a CV for an existing application - switch the layout, apply the person's requested modifications (colours, order, sections, length, wording), use or adapt a layout they uploaded, or re-check a CV. Use after /apply has created the application folder, or whenever the person asks to change how their CV looks.
argument-hint: "[application] [what to change]"
---

# Build and adjust a CV

Request: $ARGUMENTS

Read `method/template-selection.md` (layouts, options, user layouts) and keep
`method/cv-writing-rules.md` in mind. Content must keep tracing to `profile/`.

## Find the application
Applications belong to a person: check `uv run cv profile current` first (switch with
`uv run cv profile use <id>`). Then `uv run cv app list` and `uv run cv app path <ref>`. The latest
one is the default. If there is no `cv.yaml` yet, this is `/apply` territory: go through it.
If the CV was already sent (`uv run cv app show <ref>`), a rebuild makes a new version. The one the
company has stays in `sent/<date>/`. When the new version goes out, record it with
`uv run cv app sent <ref> --via "…"`.

## Changing the layout
- List them: `uv run cv templates`. Recommend per `method/template-selection.md` §1 and ask the
  person when the choice is open.
- Set `meta.template` in `cv.yaml` (or pass `--template`). Layouts differ in which sections they
  emphasise and in page budget, so check the page count again after switching.

## Modifications the person asks for
In order of preference:
1. **`cv.yaml` meta options**: `sections_order`, `hide`, `headings`, `accent`, `paper`,
   `font_size`, `date_format`, `max_pages`, `options` (column ratio, sidebar position, side
   sections). These survive re-rendering.
2. **Content edits** in `cv.yaml`: wording, order of bullets, which roles appear. New claims need
   evidence in `profile/`; if it's missing, ask and record it there first (sense-making fact pass).
3. **Layout edits for good**: copy the layout into `my-layouts/<name>/` (from
   `templates/<id>/`), change it, add `layout.yaml`, and set `meta.template: my:<name>`.
4. **One-off edits** in `cv/main.tex`: allowed. Re-rendering refuses to overwrite them unless
   `--force` is given. Say so, and note the edit in `notes.md`.

## Their own layout
They can drop a `.tex` (plus `.cls`/`.sty`/images), an unzipped Overleaf project, or a PDF/image of a
CV they like into `my-layouts/<name>/`. Turn it into a reusable renderer as described in
`method/template-selection.md` §4: `main.tex.j2` plus `files/` plus `layout.yaml`. Compile, compare
with the original, and iterate until it matches. Report any visible differences honestly.

## Build and check
```
uv run cv build <app> [--template <id>] [--force]
```
This renders, compiles, lints, reads the PDF the way an ATS would, and writes
`<Name>_CV_<Company>_<date>.pdf`. Fix errors; take warnings seriously (page count, untraceable
bullets, missing keywords, characters the font can't show, sidebar overflow, and rule-tagged ones
like `T-3` from the tailoring playbook).

After a change to content or layout, keep the tailoring intact with one more loop round: run
`uv run cv round save <app>`, launch the **cv-judge** agent for that round, then check
`uv run cv round list <app>`. If the judge asks for a revision, run the **cv-writer** agent for the
next round (`method/judge-rubric.md`). A purely visual change (colour, font size) needs no judge
round.

`uv run cv zip <app>` produces an Overleaf-ready zip if they prefer to edit there.

## Report
Send the PDF (SendUserFile), say what changed, and log the change in `notes.md`. Keep earlier PDFs
unless they ask you to remove them.
