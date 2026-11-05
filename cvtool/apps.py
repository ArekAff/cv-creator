"""Application folders (one per job ad) and the tracker of what was sent and what came back.

Follows "Try to stay organized" in guide-to-great-cv.txt: a folder per application with the
original posting, research notes and the tailored CV; clear names (company + date); a record
of which versions get responses. The tracker (applications/tracker.yaml) is the list of
listings: company, role, link, salary, how it was sent, which CV went out (a frozen copy in
sent/<date>/) and every reply. `uv run cv app ...` and the local page (`uv run cv tracker`)
both read and write it.
"""
from __future__ import annotations

import datetime as dt
import filecmp
import re
import shutil
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from . import paths, yamlio

STATUSES = ("draft", "ready", "sent", "screening", "interview", "offer", "accepted", "rejected", "no-response",
            "withdrawn")
STATUS_LABELS = {
    "draft": "not sent yet", "ready": "ready to send", "sent": "sent, waiting", "screening": "replied / screening",
    "interview": "interview", "offer": "offer", "accepted": "offer accepted", "rejected": "rejected",
    "no-response": "no reply", "withdrawn": "withdrawn",
}
NOT_SENT = {"draft", "ready"}
POSITIVE = {"screening", "interview", "offer", "accepted"}
REPLIED = POSITIVE | {"rejected"}
CLOSED = {"accepted", "rejected", "no-response", "withdrawn"}
WORK_MODES = ("remote", "hybrid", "on-site")
_WORK_MODE_ALIASES = {"onsite": "on-site", "on site": "on-site", "office": "on-site", "in office": "on-site"}
# Fields the person (or Claude) sets. The toolkit writes the others: status, created, sent, sent_cvs,
# history (through set_status and record_sent) and template, cv_pdf, headline (through build).
EDITABLE = ("company", "role", "link", "source", "salary", "expected_salary", "location", "work_mode", "deadline",
            "contact", "sent_via", "next_step", "follow_up", "notes")
DATE_FIELDS = ("deadline", "follow_up")
FIELD_ORDER = ("id", "company", "role", "status", "link", "source", "salary", "expected_salary", "location",
               "work_mode", "deadline", "contact", "created", "sent", "sent_via", "next_step", "follow_up", "notes",
               "template", "cv_pdf", "headline")

POSTING_TEMPLATE = """\
# {role} — {company}

- Source: {source}
- Link: {link}
- Saved: {date}
- Salary: {salary}
- Location / work mode: {where}
- Deadline: {deadline}

## Original posting (verbatim)

<!-- Paste the complete job ad here, unchanged. It is the reference for everything else. -->
"""

RESEARCH_TEMPLATE = """\
# Company research — {company}

## How they describe themselves
<!-- Wording from their website and careers page: mission, products, customers. -->

## Values and culture they repeat

## What people in this role highlight
<!-- e.g. LinkedIn profiles of people currently in the role. -->

## Language worth mirroring (only where it is true for the candidate)

## Sources
"""

NOTES_TEMPLATE = """\
# Notes — {role} at {company}

## Layout
<!-- Template chosen, alternatives offered, the user's preference, why. -->

## Modifications requested by the user

## Review findings

## Versions sent
<!-- `uv run cv app sent` records each one in tracker.yaml and keeps the copy in sent/<date>/. -->
"""


def slugify(text: str, max_len: int = 40) -> str:
    text = str(text).replace("ł", "l").replace("Ł", "L")
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    return slug[:max_len].rstrip("-") or "x"


def file_safe(text: str) -> str:
    """For human-facing file names: keeps capitals, drops accents and punctuation."""
    text = str(text).replace("ł", "l").replace("Ł", "L")
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_") or "x"


# ----------------------------------------------------------------- tracker.yaml
def tracker_path(root: Path | None = None) -> Path:
    """tracker.yaml in `root` (an applications folder), by default the active person's."""
    return (root or paths.applications_dir()) / "tracker.yaml"


def load_tracker(root: Path | None = None) -> list[dict]:
    data = yamlio.load(tracker_path(root), {}) or {}
    return [a for a in data.get("applications") or [] if isinstance(a, dict)]


def save_tracker(entries: list[dict], root: Path | None = None) -> None:
    yamlio.dump({"applications": [_ordered(e) for e in entries]}, tracker_path(root))


def _ordered(entry: dict) -> dict:
    """Fields in a fixed, readable order, empty ones left out, sent CVs and history last."""
    tail = ("sent_cvs", "history")
    keys = [k for k in FIELD_ORDER if k in entry]
    keys += [k for k in entry if k not in FIELD_ORDER and k not in tail] + [k for k in tail if k in entry]
    return {k: entry[k] for k in keys if entry[k] not in ("", None)}


def _where(app: str | Path) -> tuple[Path, str]:
    """(applications folder, application id) for an application folder, or an id of the active person."""
    if isinstance(app, Path):
        return app.parent, app.name
    return paths.applications_dir(), app


def _find(entries: list[dict], app_id: str) -> dict:
    for entry in entries:
        if entry.get("id") == app_id:
            return entry
    raise LookupError(f"{app_id} is not in the tracker")


def get(app: str | Path) -> dict:
    root, app_id = _where(app)
    return _find(load_tracker(root), app_id)


def _today() -> str:
    return dt.date.today().isoformat()


def _date(value: object) -> dt.date | None:
    """A tracker date (written as text, or a date when someone typed it unquoted), else None."""
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _iso_date(value: str, what: str) -> str:
    parsed = _date(value)
    if parsed is None or len(str(value).strip()) != 10:
        raise ValueError(f"{what} must be a date like 2026-11-20, not {value!r}")
    return parsed.isoformat()


def clean_fields(fields: dict) -> dict:
    """Checked and trimmed values for EDITABLE fields ('' clears one). ValueError for anything else."""
    out = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key not in EDITABLE:
            raise ValueError(f"{key!r} is not a tracker field (fields: {', '.join(EDITABLE)})")
        text = str(value).strip() if key == "notes" else " ".join(str(value).split())
        if text and key in DATE_FIELDS:
            text = _iso_date(text, key)
        elif text and key == "work_mode":
            text = _WORK_MODE_ALIASES.get(text.lower(), text.lower())
            if text not in WORK_MODES:
                raise ValueError(f"work_mode must be one of: {', '.join(WORK_MODES)}")
        elif text and key == "link":
            if text.startswith("www."):
                text = "https://" + text
            if not text.startswith(("http://", "https://")):
                raise ValueError(f"link must be the listing's web address (https://...), not {text!r}")
        elif not text and key in ("company", "role"):
            raise ValueError(f"{key} can't be empty")
        out[key] = text
    return out


# ----------------------------------------------------------------- application folders
def create(company: str, role: str, date: str | None = None, source: str = "", root: Path | None = None,
           **details: str) -> Path:
    """Create <root>/<date>_<company>_<role>/ with starter files and a tracker entry; reuse it if it exists.

    `details` are tracker fields (link, salary, location, work_mode, deadline ...). For an existing
    entry they only fill fields that are still empty. A web address given as the source is the link."""
    day = _iso_date(date, "date") if date else _today()
    details = {k: v for k, v in clean_fields({"source": source, **details}).items() if v}
    if not details.get("link") and details.get("source", "").startswith(("http://", "https://", "www.")):
        details.update(clean_fields({"link": details.pop("source")}))
    root = root or paths.applications_dir()
    folder = root / f"{day}_{slugify(company, 30)}_{slugify(role, 40)}"
    folder.mkdir(parents=True, exist_ok=True)
    blank = {k: details.get(k, "") for k in ("source", "link", "salary", "deadline")}
    where = " · ".join(details[k] for k in ("location", "work_mode") if details.get(k))
    starters = {
        "posting.md": POSTING_TEMPLATE.format(role=role, company=company, date=day, where=where, **blank),
        "research.md": RESEARCH_TEMPLATE.format(company=company),
        "notes.md": NOTES_TEMPLATE.format(role=role, company=company),
    }
    for name, text in starters.items():
        path = folder / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
    entries = load_tracker(root)
    entry = next((e for e in entries if e.get("id") == folder.name), None)
    if entry is None:
        entries.append({"id": folder.name, "company": company, "role": role, "status": "draft", **details,
                        "created": day, "history": [{"date": day, "status": "draft", "note": "created"}]})
    else:
        entry.update({k: v for k, v in details.items() if not entry.get(k)})
    save_tracker(entries, root)
    return folder


def all_folders() -> list[Path]:
    root = paths.applications_dir()
    if not root.exists():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))),
                  key=lambda p: p.name)


def resolve(ref: str | None) -> Path:
    """An application folder from a name, prefix, company fragment or path; latest when omitted."""
    if ref:
        as_path = Path(ref)
        if as_path.is_dir():
            return as_path.resolve()
    folders = all_folders()
    if not folders:
        raise LookupError("no applications yet: create one with  uv run cv app new \"Company\" \"Role\"")
    if not ref or ref == "latest":
        return max(folders, key=lambda p: (p.name[:10], p.stat().st_mtime))
    exact = [p for p in folders if p.name == ref]
    if exact:
        return exact[0]
    needle = slugify(ref, 80)
    matches = [p for p in folders if p.name.startswith(ref) or needle in p.name]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise LookupError(f"no application matches {ref!r}")
    raise LookupError(f"{ref!r} is ambiguous: " + ", ".join(p.name for p in matches))


# ----------------------------------------------------------------- changing an entry
def update(app: str | Path, **fields: str) -> dict | None:
    """Fields the toolkit writes (template, cv_pdf, headline); skips applications that aren't tracked."""
    root, app_id = _where(app)
    entries = load_tracker(root)
    for entry in entries:
        if entry.get("id") == app_id:
            entry.update({k: v for k, v in fields.items() if v is not None})
            save_tracker(entries, root)
            return entry
    return None


def edit(app: str | Path, **fields: str | None) -> dict:
    """Fields the person sets (EDITABLE), checked first; '' clears a field, None leaves it alone."""
    changes = clean_fields(fields)
    root, app_id = _where(app)
    entries = load_tracker(root)
    entry = _find(entries, app_id)
    entry.update(changes)
    save_tracker(entries, root)
    return entry


def set_status(app: str | Path, status: str, note: str = "", date: str | None = None) -> dict:
    """Record what happened. The first `sent` goes through record_sent, which keeps the CV that went out."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of: {', '.join(STATUSES)}")
    root, app_id = _where(app)
    entries = load_tracker(root)
    entry = _find(entries, app_id)
    if status == "sent" and not entry.get("sent_cvs"):
        return record_sent(root / app_id, date=date, note=note)
    day = _iso_date(date, "date") if date else _today()
    entry["status"] = status
    entry.setdefault("history", []).append({"date": day, "status": status, "note": note})
    save_tracker(entries, root)
    return entry


def record_sent(app_dir: Path, date: str | None = None, via: str = "", file: Path | None = None,
                note: str = "") -> dict:
    """Mark an application sent and keep the CV that went out in sent/<date>/: the PDF, plus cv.yaml when
    the PDF is this folder's own build. Sending again (a new version, another contact) adds a record;
    the same file on the same day doesn't."""
    root, app_id = app_dir.parent, app_dir.name
    entries = load_tracker(root)
    entry = _find(entries, app_id)
    day = _iso_date(date, "date") if date else _today()
    via = " ".join(str(via or "").split())
    if file is not None and not Path(file).is_file():
        raise LookupError(f"{file} does not exist")
    pdf = Path(file) if file is not None else (app_dir / entry["cv_pdf"] if entry.get("cv_pdf") else None)
    record: dict = {"date": day}
    if pdf is not None and pdf.is_file():
        kept = _copy_once(pdf, app_dir / "sent" / day)
        record["file"] = kept.relative_to(app_dir).as_posix()
        if file is None:
            if (app_dir / "cv.yaml").exists():
                record["cv_yaml"] = _copy_once(app_dir / "cv.yaml", app_dir / "sent" / day).relative_to(app_dir).as_posix()
            record.update({k: entry[k] for k in ("template", "headline") if entry.get(k)})
    if via:
        record["via"] = via
    sent_cvs = entry.setdefault("sent_cvs", [])
    if record in sent_cvs:
        return entry
    sent_cvs.append(record)
    if not entry.get("sent"):
        entry["sent"] = day
    if via:
        entry["sent_via"] = via
    if (entry.get("status") or "draft") in NOT_SENT:
        entry["status"] = "sent"
    what = f"sent {Path(record['file']).name}" if record.get("file") else "sent (no CV file recorded)"
    entry.setdefault("history", []).append({"date": day, "status": entry["status"],
                                            "note": note or what + (f" via {via}" if via else "")})
    save_tracker(entries, root)
    return entry


def _copy_once(src: Path, folder: Path) -> Path:
    """Copy src into folder under its own name; reuse an identical copy, number a different one (name-2.pdf)."""
    folder.mkdir(parents=True, exist_ok=True)
    target, n = folder / src.name, 2
    while target.exists() and not filecmp.cmp(src, target, shallow=False):
        target, n = folder / f"{src.stem}-{n}{src.suffix}", n + 1
    if not target.exists():
        shutil.copy2(src, target)
    return target


# ----------------------------------------------------------------- reading the tracker
def reply_info(entry: dict, today: dt.date | None = None) -> dict:
    """Did they reply? state: not sent | waiting | replied | no reply, with the reply date and the days
    (days waiting so far, or days from sending to the first reply)."""
    status = entry.get("status") or "draft"
    sent = _date(entry.get("sent"))
    if status in NOT_SENT:
        return {"state": "not sent", "date": "", "days": None}
    first = next((_date(h.get("date")) for h in entry.get("history") or [] if h.get("status") in REPLIED), None)
    if first or status in REPLIED:
        days = (first - sent).days if first and sent else None
        return {"state": "replied", "date": first.isoformat() if first else "", "days": days}
    if status in CLOSED:
        return {"state": "no reply", "date": "", "days": None}
    days = ((today or dt.date.today()) - sent).days if sent else None
    return {"state": "waiting", "date": "", "days": days}


def reply_text(reply: dict) -> str:
    if reply["state"] == "waiting":
        return "waiting" if reply["days"] is None else f"waiting {reply['days']} d"
    if reply["state"] == "replied":
        return f"yes, {reply['date']}" if reply["date"] else "yes"
    return "-" if reply["state"] == "not sent" else reply["state"]


def row(entry: dict, today: dt.date | None = None) -> dict:
    """A tracker entry plus what follows from it (status label, reply, follow-up due), ready for JSON."""
    today = today or dt.date.today()
    status = entry.get("status") or "draft"
    follow_up = _date(entry.get("follow_up"))
    return {**_plain(entry), "status": status, "label": STATUS_LABELS.get(status, status),
            "open": status not in CLOSED, "reply": reply_info(entry, today),
            "follow_up_due": bool(follow_up and follow_up <= today and status not in CLOSED)}


def _plain(value: object) -> object:
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def newest_first(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda e: (str(e.get("created") or ""), str(e.get("id"))), reverse=True)


def summary(root: Path | None = None, today: dt.date | None = None) -> dict:
    """Counts for `uv run cv status`: tracked, still open, waiting for a reply, replied, follow-ups due."""
    rows = [row(e, today) for e in load_tracker(root)]
    states = Counter(r["reply"]["state"] for r in rows)
    return {"tracked": len(rows), "open": sum(1 for r in rows if r["open"]), "waiting": states["waiting"],
            "replied": states["replied"], "follow_up_due": [str(r.get("company")) for r in rows if r["follow_up_due"]]}


def format_list(entries: list[dict], today: dt.date | None = None) -> str:
    """The tracker as a table, newest first. The link goes last so long addresses don't break the columns."""
    if not entries:
        return "no applications yet:  uv run cv app new \"<Company>\" \"<Role>\" --link <url>"
    rows = [row(e, today) for e in newest_first(entries)]
    table = [("status", "company", "position", "salary", "sent", "reply", "link")]
    for r in rows:
        table.append((r["status"], r.get("company") or "", r.get("role") or "", r.get("salary") or "-",
                      r.get("sent") or "-", reply_text(r["reply"]) + (" !" if r["follow_up_due"] else ""),
                      r.get("link") or ""))
    widths = (11, 22, 28, 22, 10, 17)
    lines = ["  ".join(_cell(c, w) for c, w in zip(cells, widths)) + "  " + cells[-1] for cells in table]
    states = Counter(r["reply"]["state"] for r in rows)
    lines.append(f"{len(rows)} application(s): {len(rows) - states['not sent']} sent, {states['waiting']} waiting, "
                 f"{states['replied']} replied, {states['no reply']} no reply")
    due = [r for r in rows if r["follow_up_due"]]
    if due:
        lines.append("! follow-up date reached: " + ", ".join(f"{r.get('company')} ({r.get('follow_up')})" for r in due))
    return "\n".join(lines)


def _cell(text: object, width: int) -> str:
    text = " ".join(str(text).split())
    return (text[:width - 1] + "…" if len(text) > width else text).ljust(width)


def format_entry(entry: dict, today: dt.date | None = None) -> str:
    r = row(entry, today)
    sent = r.get("sent") or "-"
    state = r["status"] if r["label"] == r["status"] else f"{r['status']}: {r['label']}"
    lines = [f"{r.get('company')} — {r.get('role')}   [{state}]",
             f"  folder:          {r.get('id')}"]
    for key, label in (("link", "link"), ("source", "found on"), ("salary", "salary (ad)"),
                       ("expected_salary", "salary asked"), ("location", "location"), ("work_mode", "work mode"),
                       ("deadline", "deadline"), ("contact", "contact"), ("created", "saved")):
        lines.append(f"  {label + ':':<16} {r.get(key) or '-'}")
    lines.append(f"  {'sent:':<16} {sent}" + (f" via {r['sent_via']}" if r.get("sent_via") else ""))
    lines.append(f"  {'reply:':<16} {reply_text(r['reply'])}"
                 + (f" ({r['reply']['days']} d after sending)" if r["reply"]["state"] == "replied"
                    and r["reply"]["days"] is not None else ""))
    for key, label in (("next_step", "next step"), ("follow_up", "follow up"), ("notes", "notes")):
        value = r.get(key) or "-"
        lines.append(f"  {label + ':':<16} {value}" + (" (due)" if key == "follow_up" and r["follow_up_due"] else ""))
    lines.append(f"  {'current CV:':<16} {r.get('cv_pdf') or '-'}" + (f" [{r['template']}]" if r.get("template") else ""))
    if r.get("sent_cvs"):
        lines.append("CVs sent:")
        for s in r["sent_cvs"]:
            extra = "".join(f" {x}" for x in (f"[{s['template']}]" if s.get("template") else "",
                                               f"via {s['via']}" if s.get("via") else "") if x)
            lines.append(f"  {s.get('date')}  {s.get('file') or '(no file kept)'}{extra}")
    if r.get("history"):
        lines.append("History:")
        lines.extend(f"  {h.get('date')}  {h.get('status', ''):<12} {h.get('note') or ''}".rstrip()
                     for h in r["history"])
    return "\n".join(lines)


def stats(root: Path | None = None) -> str:
    """Reply rates overall and per layout, headline, source and channel, to see what works (guide: stay organized)."""
    entries = [e for e in load_tracker(root) if (e.get("status") or "draft") not in NOT_SENT]
    if not entries:
        return "Nothing sent yet. When an application goes out:  uv run cv app sent <app>"
    replies = [reply_info(e) for e in entries]
    states = Counter(r["state"] for r in replies)
    lines = [f"Sent: {len(entries)} (waiting {states['waiting']}, replied {states['replied']}, "
             f"no reply {states['no reply']})"]
    statuses = Counter(e.get("status") for e in entries)
    lines.append("By status: " + ", ".join(f"{k} {v}" for k, v in statuses.most_common()))
    positive = sum(1 for e in entries if _ever(e, POSITIVE))
    lines.append(f"Any reply: {states['replied']}/{len(entries)} ({_pct(states['replied'], len(entries))})   "
                 f"Positive (screening/interview/offer): {positive}/{len(entries)} ({_pct(positive, len(entries))})")
    days = sorted(r["days"] for r in replies if r["state"] == "replied" and r["days"] is not None)
    if days:
        lines.append(f"Days to first reply: median {statistics.median(days):g} "
                     f"(fastest {days[0]}, slowest {days[-1]})")
    for key, title in (("template", "layout"), ("headline", "headline"), ("source", "where found"),
                       ("sent_via", "sent via")):
        groups: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            groups[str(e.get(key) or "-")].append(e)
        if len(groups) > 1 or "-" not in groups:
            lines.append(f"By {title}:")
            for name, group in sorted(groups.items()):
                replied = sum(1 for e in group if reply_info(e)["state"] == "replied")
                pos = sum(1 for e in group if _ever(e, POSITIVE))
                lines.append(f"  {name}: {replied}/{len(group)} replied, {pos}/{len(group)} positive")
    return "\n".join(lines)


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "-"


def _ever(entry: dict, wanted: set[str]) -> bool:
    return entry.get("status") in wanted or any(h.get("status") in wanted for h in entry.get("history") or [])
