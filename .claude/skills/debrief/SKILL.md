---
name: debrief
description: Capture one recent experience (a project just finished, a promotion, a hard problem solved, a new certificate) as a strategic trail in the career knowledge base, using a short sense-making interview. Use when the person mentions something new they did, or for the periodic master-resume update the CV guide recommends.
argument-hint: "[what happened, in a few words]"
---

# Debrief: add one new experience while it is fresh

Topic: $ARGUMENTS

The CV guide warns that people forget the specifics of big projects by the time they need them
(guide-to-great-cv.txt [14]). The sense-making article notes that an in-the-moment debriefing is
the other way to surface what an expert knew (HRDI article p. 354). This is that debriefing.
Protocol: `method/sense-making-interview.md`. Formats: `method/knowledge-base.md`.

1. Check it's the right person's profile (`uv run cv profile current`), then `uv run cv status`.
   If the profile is empty, suggest `/career-interview` first, but still
   capture this experience if they want.
2. Place it: which position or project does it belong to? If it's a new role or a new
   certification, add it to `timeline.yaml` (`uv run cv next-id position|certification|project`).
3. `uv run cv trail new "<their title>" --link <id>`.
4. Action outline: one action per line, with dates.
5. Probe the 2–3 pivotal gaps: present tense, situation first, then questions, emotions, wishes,
   intentions, outcomes. No "why", no interpretation, no looking back.
6. Fact pass: scale, numbers only if real, where the proof is. If they have proof (an email, a
   review, a screenshot), save it to `profile/evidence/`.
7. Sponsor check: read back 1–3 accomplishment statements and let them correct.
8. Save the trail (`status: explored`), update `skills.yaml` with evidence, append
   `profile/sessions/<date>-debrief-<topic>.md`, then `uv run cv validate` and
   `uv run cv master`.
9. Tell them what was captured in two or three lines.
