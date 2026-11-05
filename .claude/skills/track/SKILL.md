---
name: track
description: Keep the person's list of job applications and show it - which CV went to which company and listing, the salary and link, how it was sent, and whether they replied (screening, interview, rejection, offer, no reply). Use whenever the person says they sent an application, heard back from a company, has an interview, got an offer or a rejection, wants to save a listing for later, asks what they sent where, or asks to see their applications.
argument-hint: "[what happened, e.g. \"sent the Acme CV today\" or \"Vantaro called me\"]"
---

# Track: what was sent where, and what came back

Update: $ARGUMENTS

Each person's applications are listed in `applications/tracker.yaml`, one entry per application
folder. Each entry holds the listing (company, position, link, salary as written in the ad,
location, work mode, deadline), how it was sent, the exact CV that went out (`sent/<date>/` keeps
the PDF and its `cv.yaml`), and every reply in `history`. This is the guide's "track which versions
get responses" (guide-to-great-cv.txt [59]). Format: `method/knowledge-base.md`
("applications/tracker.yaml").

1. **Right person.** `uv run cv profile current` (see "Who's there" in CLAUDE.md). Work only with
   their applications.
2. **Find the application.** `uv run cv app list` (`--json` gives the ids). A company fragment
   works as `<app>`. If it isn't tracked yet:
   - a listing they want to keep for later: `uv run cv app new "<Company>" "<Role>" --link <url>
     --salary "<as written in the ad>" --location <city> --work-mode remote|hybrid|on-site
     --deadline YYYY-MM-DD`, giving only what the ad says. If they share the ad, paste it into
     `posting.md`. A tailored CV for it later is `/apply`, which reuses that folder.
   - an application they sent without this tool: the same, then
     `uv run cv app sent <app> --file "<the CV they sent>"` so a copy of it is kept.
3. **Record what happened**, one command per event. The date is today unless they say otherwise
   (`--date YYYY-MM-DD`). Put what they told you into `--note`, in their words.

   | They say | Command |
   |---|---|
   | they sent it | `uv run cv app sent <app> --via "<company site / LinkedIn Easy Apply / email to … / referral>"` |
   | a reply, a recruiter call | `uv run cv app status <app> screening --note "…"` |
   | an interview | `uv run cv app status <app> interview --note "…"`, then `uv run cv app set <app> --next-step "…"` |
   | a rejection | `uv run cv app status <app> rejected` |
   | an offer, or they accepted one | `uv run cv app status <app> offer` (or `accepted`) |
   | still nothing after a long wait | ask whether to mark it `no-response`; don't decide for them |
   | they withdrew | `uv run cv app status <app> withdrawn` |
   | the salary they asked for, a contact, a date to chase them | `uv run cv app set <app> --expected-salary "…" --contact "…" --follow-up YYYY-MM-DD` |

   Salaries come from the ad or from the person, never from you. `--<field> ""` clears a field.
4. **Show the list.** In chat: `uv run cv app list` as a compact table (company, position, salary,
   sent, reply). As a page they can sort, search and edit (status menus, the PDF that was sent): in
   the Claude desktop app, open it in the Browser pane (`preview_start` with the `tracker` entry of
   `.claude/launch.json`); otherwise they run `uv run cv tracker`. It runs on this computer only and
   opens on the active profile. Never publish tracker data as an Artifact or send it to a web service.
5. **Before an interview**, `uv run cv app show <app>` tells you which CV the company has. Send them
   that exact PDF from `sent/<date>/` (SendUserFile) so they prepare from what the interviewer read,
   and offer to go through the posting and their evidence for it (`coverage.yaml`).
6. **Now and then**, `uv run cv app stats`: reply rates by layout, headline, where the ad was found
   and how it was sent. Tell them what stands out in a line or two. With only a few applications,
   say it's too early to read much into it.
