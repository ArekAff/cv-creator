# Choosing and adapting the layout

Layouts: `uv run cv templates` (metadata in `templates/registry.yaml`, originals in
`cv-templates/`, user layouts in `my-layouts/`). The person's preference always wins. Your job is
to recommend well and explain why in one line per option.

## 1. Decide what matters for this application

| Signal (from `requirements.yaml` / `research.md`) | Points to |
|---|---|
| Large company, online application portal, "apply via Workday/Greenhouse/SuccessFactors/Taleo…", lots of tools listed (`ats_likely: true`) | single column, ATS high: **jakes**, **swe**, **minimal**, **elegant** |
| Software / data / engineering role | **jakes** (classic) or **swe** (modern sans + icons) |
| Finance, law, consulting, public institutions, research institutes, formal European employers | **elegant** (formal) or **minimal** (quiet) |
| Analyst, research, NGO, generalist, career change leading with competencies | **minimal** (has a natural "Core Competencies" block) |
| Start-up, product, marketing, growth, UX/design-adjacent; referral or direct email to a person | **altacv** (two columns, achievements, tags) |
| Academia, PhD/postdoc, teaching, science; publications matter; long CV is fine | **curve** |
| Creative, communication, hospitality, small company; photo expected by local norm | **receive** (sidebar, photo, skill bars), or **altacv** with a photo |
| Very senior, much to say | **elegant** or **curve** (two pages read well) |
| Graduate / intern | **jakes** with `sections_order: [education, …]` |

Two-column and sidebar layouts (altacv, receive) can confuse ATS parsing. If `ats_likely: true`,
recommend them only if the person insists, and mention the risk. `uv run cv build` runs an ATS
text read either way.

**The track in `classification.yaml` matters too:**
- **Technical** (T-15): single column, no photo, no icons or skill bars for online applications
  (jakes, swe, minimal). Two columns only for a CV handed straight to a person.
- **Non-technical** (N-13): keep it simple, with no graphics, tables or columns for online
  applications (elegant, minimal, jakes). AltaCV or ReCeiVe suit creative or direct applications
  where a person reads the PDF first.

The lint warns about a two-column layout when the application is likely parsed by an ATS.

## 2. Ask the person

Recommend one layout and give 1–2 real alternatives, plus "my own layout". Use the
AskUserQuestion tool with one option per layout, the recommended one first, each with a one-line
reason tied to *this* job. Mention that they can drop their own `.tex` (or an Overleaf zip, or a PDF
of a CV they like) into `my-layouts/`.

## 3. Tailor the layout, not only the words (guide: over-relying on templates)

Everything below lives in `cv.yaml` `meta`, so it survives re-rendering:

| Need | Setting |
|---|---|
| Order of sections | `sections_order: [summary, experience, …]` |
| Hide a section for this CV | `hide: [interests]` |
| Rename a heading | `headings: {skills: Technical Skills}` |
| Accent colour (e.g. a calm nod to the company's brand) | `accent: "1F6E8C"` (hex, no #) |
| Paper / size | `paper: a4 | letter`, `font_size: 10pt | 11pt | 12pt` |
| Date style | `date_format: short | long | numeric | year` |
| Page budget | `max_pages: 1` |
| Language (headings, dates, hyphenation) | `language: en | pl | de | …` |
| Photo | `header.photo: true` (uses `profile.yaml person.photo`) or a path |
| Layout-specific | `options:` e.g. AltaCV `column_ratio: 0.62`, `side_sections: […]`; ReCeiVe `sidebar_position: right`, `side_sections`, `headwords: "…"` |

Requests the options cannot express (a different header, a new element) go into the layout itself:
- **For this one CV only:** edit `applications/<app>/cv/main.tex` directly. Re-rendering then
  refuses to overwrite it unless `--force` is given. Note the change in `notes.md`.
- **For good:** copy the layout to `my-layouts/<name>/` (see below) and change it there.

## 4. The person's own layout (uploaded or modified)

1. Put the files in `my-layouts/<name>/`: their `.tex` plus any `.cls`/`.sty`/fonts/images. For an
   Overleaf project, unzip it there. For a PDF or image of a CV they like, recreate it in LaTeX as
   faithfully as practical and say what differs.
2. Read their `.tex`. Identify the commands it uses for header, sections, entries and bullets.
3. Create `my-layouts/<name>/main.tex.j2` from it by replacing the sample content with loops over
   the cv.yaml context. Copy the patterns from `templates/jakes/main.tex.j2` (simple) or
   `templates/altacv/main.tex.j2` (two columns). Put support files under
   `my-layouts/<name>/files/`. Add `my-layouts/<name>/layout.yaml`:
   ```yaml
   name: "Anna's layout"
   engine: pdflatex          # or xelatex / lualatex, as the layout needs
   columns: 1
   ats: high
   default_paper: a4
   look: "one line on what it looks like"
   best_for: [...]
   ```
4. Use it with `meta.template: my:<name>` (or `--template my:<name>`). Build, look at the PDF, and
   fix it until it matches the original.
5. Apply their modification requests inside the layout and tell them what changed.
6. Check the text an ATS gets: `uv run cv ats`. The renderer adds pdfTeX's real interword spaces
   after `\documentclass` (`render.REAL_SPACES`); keep that line if you edit `main.tex` by hand. It
   does nothing under XeLaTeX or LuaLaTeX, so for those layouts the "words run together" problem
   is the one to watch.

Template context (all strings already LaTeX-escaped; do not escape again):
`cv.header` (name, first_name, last_name, headline, location, email, email_url, phone, phone_url,
links[kind,url,label,handle,icon], contacts[], linkedin/github/website, quote), `cv.summary`,
`cv.experience[]` / `cv.volunteering[]` (title, organization, location, dates, description, tech,
bullets[text, source]), `cv.experience_groups[]` (organization, location, dates, roles[]),
`cv.projects[]` (name, role, dates, tech, url, link_text, description, bullets), `cv.education[]`
(degree, field, degree_line, institution, location, dates, details, grade, thesis), `cv.skills[]`
(category, items, rated[name, ratio]), `cv.certifications[]` (name, issuer, when, in_progress, url),
`cv.languages[]` (language, level, rating 1–5), `cv.awards[]`, `cv.publications[]`,
`cv.competencies[]` (name, text), `cv.achievements[]` (title, text, icon), `cv.interests[]`,
`cv.references`, `cv.custom[]` (title, text, items), `cv.gdpr_clause`; `meta` (language, babel,
paper, font_size, accent, sections, main, side, photo, options, pdf_title); `labels.<section>`;
`words` (thesis, grade, in_progress, phone, email, residence, cv).
Jinja delimiters: `<< value >>`, `<% statement %>`, `<# comment #>`. Use `x['items']` or `x.items`
(both work).
