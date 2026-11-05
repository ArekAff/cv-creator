---
name: import-resume
description: Import the person's current CV/résumé (PDF, Word .docx, LaTeX .tex or an Overleaf .zip, text, or a photo/screenshot) into their career knowledge base, and run a sense-making interview about everything in it that the knowledge base doesn't know yet. Use whenever the person uploads, attaches, pastes or mentions their existing CV or a LinkedIn profile PDF, and whenever `uv run cv status` shows CVs waiting in the inbox or imports with open items.
argument-hint: "[path to the CV | pasted CV text]"
---

# Import an existing CV, then interview about what's new

CV: $ARGUMENTS

A CV is the person's own summary of their career. It holds **facts** (titles, dates, schools) and
**claims** (bullets, numbers). Nothing from it enters the knowledge base unconfirmed: facts get
confirmed, and claims get explored with the sense-making method until they rest on what actually
happened (`method/sense-making-interview.md`, section 7). Paths like `profile/` mean the active
person's folder, `people/<id>/profile/`. `uv run cv doctor` prints it.

## 0. Whose CV is it?
Run `uv run cv profile current`. It must be the CV owner's profile. If the CV belongs to someone
else who uses this installation, switch with `uv run cv profile use <id>`, or create their profile
with `uv run cv profile add "<Name>"`. Never import one person's CV into another person's profile.

## 1. Bring the file in
- A path or an attachment: `uv run cv resume import "<path>"`. The original stays where it was.
- Files the person dropped into their inbox (`uv run cv resume list` shows them): `uv run cv resume
  import` takes them all and moves them into the import folder.
- Pasted text: save it as `inbox/<YYYY-MM-DD>-pasted-cv.md` in their folder first, then import it.
- LinkedIn: "More → Save to PDF" on their profile page gives a PDF that imports like a CV.

Supported: PDF with a text layer, .docx, .tex (`\input` files are followed) or an Overleaf .zip,
.txt/.md, and images (.png/.jpg/.webp). For .doc, .odt or .pages, ask for a PDF or .docx export.

The command creates `profile/imports/<id>/` with `original.*`, `text.md` and `import.yaml`. If the
text quality is `low` or `none` (a photo or a scanned PDF), read the original yourself (images can
be read directly) and overwrite `text.md` with a faithful transcription. If a scanned PDF is
unreadable, ask for a text PDF, a .docx, or screenshots.

## 2. Read it out into extracted.yaml
Read `text.md`, and for LaTeX also `original/*.tex`. Text from two-column PDFs can come out in a
scrambled order, so follow the original's structure. Write `extracted.yaml` in the import folder.
The format is in `method/knowledge-base.md` ("CV imports"); there's an example in
`examples/demo/profile/imports/2026-10-30-cv-2023/`.
- Copy facts and bullets **verbatim**. Don't improve, merge, translate or guess. Dates are `YYYY` or
  `YYYY-MM`, and `present` for ongoing roles.
- Split skills into single names. Volunteering goes into `positions` with `type: volunteer`.
  Anything that fits nowhere goes into `other`.
- If the CV shows when it was written, record it in `source.dated`. That explains old end dates.

## 3. Compare with the knowledge base
Run `uv run cv resume diff <import>`. Every entry comes out known, new, changed or partly known. Every
bullet is checked against the stories and roles already recorded, numbers included. Give the person
a short summary: what's already known, and what's new, grouped into roles, claims, certificates,
skills and other.

- **Nothing open:** say so. The CV stays in `profile/imports/` as evidence, and you're done.
- **Anything open:** interview about it. That's the rule here: new information from a CV always gets
  a sense-making interview before it counts. Start right away with the first agenda item. They can
  stop at any time; open items stay listed in `uv run cv status` for next time.
- **Empty knowledge base** (`uv run cv status` says `empty`): this *is* the first career interview.
  Run the `career-interview` skill, use `extracted.yaml` to pre-fill the scaffold (confirm, don't
  re-ask), and treat the CV's bullets as candidate trails.

## 4. Interview, agenda item by item (HIGH, then MEDIUM, then LOW)
Use the protocol in `method/sense-making-interview.md`: their nouns, present tense inside a gap,
situation first, never "why". Save as you go: trails, timeline, skills, and
`profile/sessions/<date>-cv-import-<id>.md`.

- **New position, project or education:** confirm the facts plainly and add the entry to
  `timeline.yaml` (`uv run cv next-id position|project|education`). Go through its responsibilities
  item by item with priorities, then take the high-value ones as trails.
- **Claims (new or partly known):** a CV bullet is the *end* of a story, so walk back from it:
  "Your CV says '<bullet>'. Take me back to when that started. What's happening?" Then do the action
  outline, probe the pivotal gaps, and run a fact pass on every number in the claim ("2 days to 3
  hours: how did you know that? What's the lowest figure you'd defend in an interview?"). Finish with
  a sponsor check. If the story continues an existing trail (shown as `under P0x`/`T00x`), extend
  that trail; otherwise run `uv run cv trail new "<their title>" --link <id>`. The confirmed
  statement goes into `accomplishments` in **their** words, which may differ from the CV's.
- **Changed facts** (dates, titles, language levels, certificate status): ask which is right *now*.
  Old CVs are often simply older (`source.dated`). Fix the knowledge base, or resolve the item.
- **New certifications:** issuer, date, and status (`completed` or `in-progress`), as `C0x` in the
  timeline.
- **New skills:** ask where they used it, so it links to a trail or role as evidence, plus the level
  and when they last used it. A skill with nothing behind it gets a note ("course only") or is
  dismissed.
- **Low items** (contact details, languages, interests, summary wording): confirm quickly and update
  `profile.yaml`. If they like the summary, add it to `insights.summary_drafts`.

If the person says something is outdated, wrong, or not to be kept:
`uv run cv resume resolve <import> <key> --as dismissed --note "<reason>"`.
If it was captured in different words that the diff can't see:
`uv run cv resume resolve <import> <key> --as covered --ref T00x`.

## 5. Close
1. Run `uv run cv validate`, then `uv run cv resume diff <import>` again, until nothing is open. If the
   person stops earlier, tell them what's left.
2. Run `uv run cv master` to refresh the master resume.
3. If it was a LaTeX CV, offer to keep its design as their own layout (`my-layouts/<name>/`,
   `method/template-selection.md` §4). Their next tailored CV can then look like the one they
   already use.
4. Report in a few lines: what was added (ids), corrected, dismissed, and what's still open.
