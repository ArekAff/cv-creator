"""The career knowledge base in profile/: create, load, validate, report status, search, export.

The knowledge base is the "master resume" of guide-to-great-cv.txt, enriched with the
sense-making material (strategic trails, action lists, probed gaps) from the interviews.
Formats are documented in method/knowledge-base.md.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import dates, paths, yamlio

TRAIL_STATUSES = ("outlined", "partial", "explored")
SKILL_LEVELS = ("basic", "intermediate", "advanced", "expert")
POSITION_TYPES = ("employment", "internship", "freelance", "volunteer", "other")
GAP_FIELDS = ("situation", "questions", "emotions", "wishes", "intentions")
# timeline list -> (id prefix, required keys)
TIMELINE_LISTS = {
    "positions": ("P", ("title", "organization")),
    "education": ("E", ("institution",)),
    "certifications": ("C", ("name",)),
    "projects": ("PR", ("name",)),
    "awards": ("AW", ("name",)),
    "publications": ("PUB", ("title",)),
}
ID_KINDS = {
    "position": "positions", "education": "education", "certification": "certifications",
    "project": "projects", "award": "awards", "publication": "publications",
}

PROFILE_SKELETON = """\
# Who you are and how you like your CVs. Filled in during the career interview.
schema_version: 1
person:
  name: ""
  headline: ""          # how the person describes themselves, in their own words
  location: ""
  email: ""
  phone: ""
  links: []             # - {kind: linkedin, url: "https://www.linkedin.com/in/..."}
  photo: ""             # path to a photo file (used only when a CV should have one)
languages: []           # - {language: English, level: C1}
interests: []
preferences:
  target_roles: []
  industries: []
  locations: []
  work_mode: ""         # remote / hybrid / on-site
  cv_language: ""       # default CV language, e.g. en or pl
  paper: ""             # a4 or letter
  photo_on_cv: false
  avoid: []             # things never to put on a CV
  notes: ""
"""

TIMELINE_SKELETON = """\
# Career scaffold: the who / what / where / when facts. The stories live in trails/.
# Format and examples: method/knowledge-base.md
positions: []
education: []
certifications: []
projects: []
awards: []
publications: []
"""

SKILLS_SKELETON = """\
# Skills inventory. Every skill points to evidence: trail ids (T001) or timeline ids (P01, PR01...).
skills: []
"""

INSIGHTS_SKELETON = """\
# Cross-trail synthesis (Sagis step 2): what shows up again and again across the stories.
patterns: []          # - {pattern: "...", seen_in: [T001, T003], cv_use: "summary"}
strengths: []
values: []
working_style: ""
career_direction: ""
recurring_themes: []
summary_drafts: []    # candidate profile summaries, in the person's own voice
"""

TRAIL_SKELETON = """\
id: {id}
title: {title}
linked_to: [{links}]
responsibility: ""      # the high-value responsibility this story exemplifies
why_chosen: ""          # e.g. "most valuable part of the role" or "evidence for R03 of <application>"
timeframe: {{start: "", end: ""}}
goal: ""                # the result they were working towards
status: outlined        # outlined -> partial -> explored
context: ""             # the situation at the start: organisation, team, stakes, constraints
actions: []             # - {{id: A1, when: "2022-01", actor: self, action: "one action per line"}}
gaps: []                # - {{after: A1, situation: "", questions: "", emotions: "", wishes: "", intentions: "", quotes: []}}
outcomes: []            # - {{text: "", metric: "", evidence: user_stated, source: ""}}
competencies: []        # - {{name: "", evidence: ""}}
skills_used: []
keywords: []            # their own nouns plus the standard terms a recruiter would search for
accomplishments: []     # CV-ready statements drafted from this trail and confirmed by the person
open_questions: []
sessions: []
"""


@dataclass
class Issue:
    level: str  # "error" | "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


@dataclass
class Doc:
    """One searchable unit of the knowledge base."""
    id: str
    kind: str
    title: str
    path: Path
    fields: list[tuple[str, str]]


@dataclass
class Hit:
    doc: Doc
    score: float
    matched: list[str]
    snippet: str


@dataclass
class KnowledgeBase:
    root: Path
    profile: dict = field(default_factory=dict)
    timeline: dict = field(default_factory=dict)
    skills: list = field(default_factory=list)
    insights: dict = field(default_factory=dict)
    trails: list = field(default_factory=list)
    sessions: list = field(default_factory=list)

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, root: Path | None = None) -> "KnowledgeBase":
        root = root or paths.profile_dir()
        kb = cls(root=root)
        kb.profile = _mapping(yamlio.load(root / "profile.yaml", {}))
        kb.timeline = _mapping(yamlio.load(root / "timeline.yaml", {}))
        kb.skills = [s for s in (_mapping(yamlio.load(root / "skills.yaml", {})).get("skills") or [])
                     if isinstance(s, dict)]
        kb.insights = _mapping(yamlio.load(root / "insights.yaml", {}))
        for path in sorted((root / "trails").glob("*.yaml")):
            data = _mapping(yamlio.load(path, {}))
            data["_path"] = path
            kb.trails.append(data)
        kb.sessions = sorted((root / "sessions").glob("*.md"))
        return kb

    @property
    def exists(self) -> bool:
        return (self.root / "profile.yaml").exists()

    def items(self, list_name: str) -> list[dict]:
        return [x for x in (self.timeline.get(list_name) or []) if isinstance(x, dict)]

    def index(self) -> dict[str, tuple[str, str]]:
        """id -> (kind, label) for every item that evidence can point to."""
        idx: dict[str, tuple[str, str]] = {}
        for list_name in TIMELINE_LISTS:
            for item in self.items(list_name):
                if item.get("id"):
                    idx[str(item["id"])] = (list_name, label_for(list_name, item))
        for t in self.trails:
            if t.get("id"):
                idx[str(t["id"])] = ("trails", str(t.get("title") or ""))
        return idx

    def trail(self, trail_id: str) -> dict | None:
        return next((t for t in self.trails if str(t.get("id")) == trail_id), None)

    def next_id(self, kind: str) -> str:
        if kind == "trail":
            nums = [int(m.group(1)) for t in self.trails if (m := re.fullmatch(r"T(\d+)", str(t.get("id") or "")))]
            nums += [int(m.group(1)) for p in (self.root / "trails").glob("T*.yaml")
                     if (m := re.match(r"T(\d+)", p.name))]
            return f"T{max(nums, default=0) + 1:03d}"
        list_name = ID_KINDS[kind]
        prefix = TIMELINE_LISTS[list_name][0]
        nums = [int(m.group(1)) for it in self.items(list_name)
                if (m := re.fullmatch(rf"{prefix}(\d+)", str(it.get("id") or "")))]
        return f"{prefix}{max(nums, default=0) + 1:02d}"

    # ------------------------------------------------------------- validation
    def validate(self) -> list[Issue]:
        issues: list[Issue] = []
        seen: dict[str, str] = {}

        def add(level: str, where: str, message: str) -> None:
            issues.append(Issue(level, where, message))

        def check_date(where: str, value: object, required: bool = False) -> dates.CvDate | None:
            if value in (None, ""):
                if required:
                    add("warning", where, "missing date")
                return None
            try:
                return dates.parse(value)
            except ValueError as exc:
                add("error", where, str(exc))
                return None

        def register(item_id: str, where: str) -> None:
            if item_id in seen:
                add("error", where, f"duplicate id {item_id} (also {seen[item_id]})")
            seen[item_id] = where

        person = _mapping(self.profile.get("person"))
        if not person.get("name"):
            add("warning", "profile.yaml", "person.name is empty")
        email = person.get("email")
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(email)):
            add("warning", "profile.yaml", f"email looks malformed: {email}")

        for list_name, (prefix, required) in TIMELINE_LISTS.items():
            for i, item in enumerate(self.items(list_name)):
                item_id = str(item.get("id") or "")
                where = f"timeline.yaml {list_name}[{i}]" + (f" ({item_id})" if item_id else "")
                if not item_id:
                    add("error", where, "missing id")
                else:
                    if not re.fullmatch(rf"{prefix}\d+", item_id):
                        add("warning", where, f"id should look like {prefix}01")
                    register(item_id, where)
                for key in required:
                    if not item.get(key):
                        add("error", where, f"missing {key}")
                start = check_date(f"{where} start", item.get("start"), required=list_name == "positions")
                end = check_date(f"{where} end", item.get("end"))
                if start and end and end.sort_key() < start.sort_key():
                    add("error", where, "end is before start")
                check_date(f"{where} date", item.get("date"))
                if list_name == "positions":
                    if item.get("type") and item["type"] not in POSITION_TYPES:
                        add("warning", where, f"type should be one of {', '.join(POSITION_TYPES)}")
                    for j, resp in enumerate(item.get("responsibilities") or []):
                        if isinstance(resp, dict) and not resp.get("text"):
                            add("error", f"{where} responsibilities[{j}]", "missing text")

        for t in self.trails:
            where = f"trails/{t['_path'].name}"
            trail_id = str(t.get("id") or "")
            if not trail_id:
                add("error", where, "missing id")
                continue
            if not re.fullmatch(r"T\d{3,}", trail_id):
                add("warning", where, "id should look like T001")
            if not t["_path"].name.startswith(trail_id):
                add("warning", where, f"file name should start with {trail_id}")
            register(trail_id, where)
            if not t.get("title"):
                add("error", where, "missing title")
            if t.get("status") and t["status"] not in TRAIL_STATUSES:
                add("warning", where, f"status should be one of {', '.join(TRAIL_STATUSES)}")
            timeframe = _mapping(t.get("timeframe"))
            check_date(f"{where} timeframe.start", timeframe.get("start"))
            check_date(f"{where} timeframe.end", timeframe.get("end"))
            action_ids = set()
            for k, action in enumerate(t.get("actions") or []):
                if not isinstance(action, dict) or not action.get("action"):
                    add("error", f"{where} actions[{k}]", "each action needs an 'action' text")
                    continue
                if action.get("id"):
                    action_ids.add(str(action["id"]))
            for k, gap in enumerate(t.get("gaps") or []):
                if not isinstance(gap, dict):
                    add("error", f"{where} gaps[{k}]", "a gap must be a mapping")
                    continue
                if gap.get("after") and str(gap["after"]) not in action_ids:
                    add("warning", f"{where} gaps[{k}]", f"after: {gap['after']} does not match an action id")
                if not any(gap.get(f) for f in GAP_FIELDS):
                    add("warning", f"{where} gaps[{k}]", "no probe answers recorded yet")
            for k, outcome in enumerate(t.get("outcomes") or []):
                if not _text(outcome):
                    add("error", f"{where} outcomes[{k}]", "outcome without text")

        known = set(seen)

        def check_refs(where: str, refs: object) -> None:
            for ref in _as_list(refs):
                if str(ref) not in known:
                    add("warning", where, f"unknown reference {ref}")

        for t in self.trails:
            check_refs(f"trails/{t['_path'].name} linked_to", t.get("linked_to"))
        for list_name in TIMELINE_LISTS:
            for item in self.items(list_name):
                check_refs(f"timeline.yaml {item.get('id')} trails", item.get("trails"))
                for resp in item.get("responsibilities") or []:
                    if isinstance(resp, dict):
                        check_refs(f"timeline.yaml {item.get('id')} responsibilities", resp.get("trails"))
        for skill in self.skills:
            name = skill.get("name")
            if not name:
                add("error", "skills.yaml", "skill without a name")
                continue
            if skill.get("level") and skill["level"] not in SKILL_LEVELS:
                add("warning", f"skills.yaml {name}", f"level should be one of {', '.join(SKILL_LEVELS)}")
            if not skill.get("evidence"):
                add("warning", f"skills.yaml {name}", "no evidence (trail or timeline id)")
            check_refs(f"skills.yaml {name} evidence", skill.get("evidence"))
        for pattern in self.insights.get("patterns") or []:
            if isinstance(pattern, dict):
                check_refs("insights.yaml patterns", pattern.get("seen_in"))
        return issues

    # ----------------------------------------------------------------- status
    def status(self) -> dict:
        positions = self.items("positions")
        linked = {str(x) for t in self.trails for x in _as_list(t.get("linked_to"))}
        for p in positions:
            for resp in p.get("responsibilities") or []:
                if isinstance(resp, dict) and resp.get("trails"):
                    linked.add(str(p.get("id")))
        recent_cutoff = dt.date.today().year - 6
        # readiness is judged on recent paid roles; volunteering without a story is listed but not blocking
        recent = [p for p in positions if _end_year(p) >= recent_cutoff and p.get("type") not in ("volunteer", "other")]
        uncovered = [p for p in positions if str(p.get("id")) not in linked]
        recent_uncovered = [p for p in uncovered if p in recent]
        explored = [t for t in self.trails if t.get("status") in ("partial", "explored")]
        no_outcomes = [t for t in self.trails if not t.get("outcomes")]
        no_numbers = [t for t in self.trails
                      if t.get("outcomes") and not any(re.search(r"\d", _text(o)) for o in t["outcomes"])]
        open_questions = [(str(t.get("id")), str(q)) for t in self.trails for q in (t.get("open_questions") or [])]
        if not self.exists or (not positions and not self.items("education")):
            readiness = "empty"
        elif not explored:
            readiness = "scaffold"
        elif recent_uncovered:
            readiness = "partial"
        else:
            readiness = "ready"
        person = _mapping(self.profile.get("person"))
        return {
            "readiness": readiness,
            "profile_exists": self.exists,
            "name": person.get("name") or "",
            "contact_missing": [k for k in ("name", "email", "phone", "location") if not person.get(k)],
            "counts": {
                "positions": len(positions),
                "education": len(self.items("education")),
                "certifications": len(self.items("certifications")),
                "projects": len(self.items("projects")),
                "trails": len(self.trails),
                "skills": len(self.skills),
                "sessions": len(self.sessions),
            },
            "trails_by_status": dict(Counter(str(t.get("status") or "outlined") for t in self.trails)),
            "positions_without_trails": [f"{p.get('id')} {label_for('positions', p)}" for p in uncovered],
            "recent_positions_without_trails": [f"{p.get('id')} {label_for('positions', p)}" for p in recent_uncovered],
            "trails_without_outcomes": [f"{t.get('id')} {t.get('title')}" for t in no_outcomes],
            "trails_without_numbers": [f"{t.get('id')} {t.get('title')}" for t in no_numbers],
            "skills_without_evidence": [s.get("name") for s in self.skills if not s.get("evidence")],
            "open_questions": open_questions,
            "last_session": self.sessions[-1].stem if self.sessions else None,
        }

    # ----------------------------------------------------------------- search
    def documents(self) -> list[Doc]:
        docs: list[Doc] = []
        timeline_path = self.root / "timeline.yaml"
        for list_name in TIMELINE_LISTS:
            for item in self.items(list_name):
                fields = []
                for key, value in item.items():
                    if key in ("id", "trails"):
                        continue
                    if key == "responsibilities":
                        fields += [("responsibility", _text(r)) for r in value or []]
                    else:
                        fields.append((key, _flatten(value)))
                docs.append(Doc(str(item.get("id") or "?"), list_name, label_for(list_name, item),
                                timeline_path, fields))
        for t in self.trails:
            fields = [(k, _flatten(t.get(k))) for k in ("title", "responsibility", "goal", "context", "why_chosen")]
            fields += [("action", _text(a)) for a in t.get("actions") or []]
            for gap in t.get("gaps") or []:
                if isinstance(gap, dict):
                    fields += [(f"gap {gap.get('after', '')} {f}", _flatten(gap.get(f))) for f in (*GAP_FIELDS, "quotes")]
            fields += [("outcome", _text(o)) for o in t.get("outcomes") or []]
            fields += [("competency", _flatten(c)) for c in t.get("competencies") or []]
            fields += [("accomplishment", _text(a)) for a in t.get("accomplishments") or []]
            fields += [("skills_used", _flatten(t.get("skills_used"))), ("keywords", _flatten(t.get("keywords")))]
            docs.append(Doc(str(t.get("id")), "trail", str(t.get("title") or ""), t["_path"], fields))
        for skill in self.skills:
            fields = [("skill", _flatten([skill.get("name"), skill.get("aliases")])),
                      ("notes", _flatten(skill.get("notes")))]
            evidence = ", ".join(map(str, _as_list(skill.get("evidence"))))
            docs.append(Doc(f"skill:{skill.get('name')}", "skill", f"{skill.get('name')} (evidence: {evidence or 'none'})",
                            self.root / "skills.yaml", fields))
        person = _mapping(self.profile.get("person"))
        profile_fields = [("headline", _flatten(person.get("headline")))]
        profile_fields += [("language", f"{_mapping(l).get('language')} {_mapping(l).get('level')}")
                           for l in _as_list(self.profile.get("languages"))]
        docs.append(Doc("profile", "profile", "Profile (headline, spoken languages)", self.root / "profile.yaml",
                        profile_fields))
        insight_fields = [(k, _flatten(v)) for k, v in self.insights.items()]
        if insight_fields:
            docs.append(Doc("insights", "insights", "Cross-trail insights", self.root / "insights.yaml", insight_fields))
        for session in self.sessions:
            paragraphs = [p.strip() for p in session.read_text(encoding="utf-8").split("\n\n") if p.strip()]
            docs.append(Doc(f"session:{session.stem}", "session", session.stem, session,
                            [("transcript", p) for p in paragraphs]))
        return [d for d in docs if any(text for _, text in d.fields)]

    def search(self, terms: list[str], limit: int = 10) -> list[Hit]:
        variants = {term: self._variants(term) for term in terms if term.strip()}
        hits: list[Hit] = []
        for doc in self.documents():
            total, matched, snippets = 0.0, [], []
            for term, forms in variants.items():
                best, best_snip = 0.0, ""
                for form in forms:
                    score, snip = _score(doc, form)
                    if score > best:
                        best, best_snip = score, snip
                if best >= 0.5:
                    total += best
                    matched.append(term)
                    snippets.append(best_snip)
            if matched:
                weight = 1.15 if doc.kind == "trail" else 1.0
                hits.append(Hit(doc, round(total * weight, 2), matched, snippets[0]))
        hits.sort(key=lambda h: (-h.score, h.doc.id))
        return hits[:limit]

    def _variants(self, term: str) -> list[str]:
        """The term plus the skill name and aliases it matches in skills.yaml."""
        forms = [term]
        term_tokens = tokens(term)
        for skill in self.skills:
            names = [str(skill.get("name") or "")] + [str(a) for a in _as_list(skill.get("aliases"))]
            for name in names:
                name_tokens = tokens(name)
                if name_tokens and len(name_tokens) == len(term_tokens) and all(
                        any(token_match(a, b) for b in name_tokens) for a in term_tokens):
                    forms += [n for n in names if n and n not in forms]
                    break
        return forms

    # ----------------------------------------------------------------- master
    def master_markdown(self) -> str:
        """Everything in one readable document: the master resume (guide, 'Start with a master resume')."""
        person = _mapping(self.profile.get("person"))
        lines = [f"# {person.get('name') or 'Master resume'}", ""]
        contact = [str(person.get(k)) for k in ("location", "email", "phone") if person.get(k)]
        contact += [str(_mapping(l).get("url")) for l in _as_list(person.get("links")) if _mapping(l).get("url")]
        if contact:
            lines += [" · ".join(contact), ""]
        if person.get("headline"):
            lines += [f"*{person['headline']}*", ""]
        lines += ["> Master resume generated from profile/ — everything known, untailored. Never send this as is.", ""]
        trails_by_link: dict[str, list[dict]] = {}
        for t in self.trails:
            for ref in _as_list(t.get("linked_to")):
                trails_by_link.setdefault(str(ref), []).append(t)

        drafts = self.insights.get("summary_drafts") or []
        if drafts:
            lines += ["## Summary drafts", ""] + [f"- {d}" for d in drafts] + [""]

        def section(title: str, list_name: str) -> None:
            entries = sorted(self.items(list_name), key=_sort_key, reverse=True)
            if not entries:
                return
            lines.extend([f"## {title}", ""])
            for item in entries:
                when = dates.fmt_range(item.get("start"), item.get("end")) or (
                    dates.fmt(dates.parse(item["date"])) if item.get("date") else "")
                lines.append(f"### {label_for(list_name, item)}" + (f" ({when})" if when else "") + f" [{item.get('id')}]")
                for key in ("org_context", "team", "location", "description", "role", "grade", "thesis", "status"):
                    if item.get(key):
                        lines.append(f"- {key.replace('_', ' ')}: {item[key]}")
                for resp in item.get("responsibilities") or []:
                    resp = _mapping(resp) or {"text": resp}
                    tag = f" ({resp.get('priority')})" if resp.get("priority") else ""
                    lines.append(f"- responsibility{tag}: {resp.get('text')}")
                for key in ("tools", "highlights"):
                    if item.get(key):
                        lines.append(f"- {key}: {_flatten(item[key])}")
                for t in trails_by_link.get(str(item.get("id")), []):
                    lines.append(f"- story {t.get('id')}: {t.get('title')} [{t.get('status', 'outlined')}]")
                    for acc in t.get("accomplishments") or []:
                        lines.append(f"  - {_text(acc)}")
                    if not t.get("accomplishments"):
                        for outcome in t.get("outcomes") or []:
                            lines.append(f"  - outcome: {_text(outcome)}")
                lines.append("")

        section("Experience", "positions")
        section("Projects", "projects")
        section("Education", "education")
        section("Certifications", "certifications")
        section("Awards", "awards")
        section("Publications", "publications")
        if self.skills:
            lines += ["## Skills", ""]
            by_category: dict[str, list[str]] = {}
            for skill in self.skills:
                label = str(skill.get("name"))
                if skill.get("level"):
                    label += f" ({skill['level']})"
                by_category.setdefault(str(skill.get("category") or "other"), []).append(label)
            lines += [f"- **{cat}**: {', '.join(names)}" for cat, names in by_category.items()] + [""]
        languages = _as_list(self.profile.get("languages"))
        if languages:
            lines += ["## Languages", ""] + [
                f"- {_mapping(l).get('language')}: {_mapping(l).get('level')}" for l in languages] + [""]
        if self.insights.get("patterns") or self.insights.get("strengths"):
            lines += ["## Patterns and strengths (from the interviews)", ""]
            for p in self.insights.get("patterns") or []:
                p = _mapping(p) or {"pattern": p}
                lines.append(f"- {p.get('pattern')} (seen in {', '.join(map(str, _as_list(p.get('seen_in'))))})")
            lines += [f"- strength: {s}" for s in self.insights.get("strengths") or []] + [""]
        orphan_trails = [t for t in self.trails if not _as_list(t.get("linked_to"))]
        if orphan_trails:
            lines += ["## Other stories", ""]
            for t in orphan_trails:
                lines.append(f"- {t.get('id')}: {t.get('title')}")
                lines += [f"  - {_text(a)}" for a in t.get("accomplishments") or []]
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------- helpers
def init_profile(root: Path | None = None, person_name: str = "") -> list[Path]:
    """Create the empty knowledge base. Never overwrites existing files."""
    root = root or paths.profile_dir()
    profile_text = PROFILE_SKELETON
    if person_name:
        profile_text = profile_text.replace('  name: ""', f'  name: "{person_name.replace(chr(34), "")}"', 1)
    created = []
    for name, text in (("profile.yaml", profile_text), ("timeline.yaml", TIMELINE_SKELETON),
                       ("skills.yaml", SKILLS_SKELETON), ("insights.yaml", INSIGHTS_SKELETON)):
        path = root / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            created.append(path)
    for sub in ("trails", "sessions", "evidence", "imports"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return created


def new_trail(title: str, links: list[str], kb: KnowledgeBase | None = None) -> Path:
    kb = kb or KnowledgeBase.load()
    trail_id = kb.next_id("trail")
    from .apps import slugify  # local import: apps imports kb
    path = kb.root / "trails" / f"{trail_id}-{slugify(title, 40)}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    quoted_title = '"' + title.replace('"', "'") + '"'
    path.write_text(TRAIL_SKELETON.format(id=trail_id, title=quoted_title, links=", ".join(links)), encoding="utf-8")
    return path


def label_for(list_name: str, item: dict) -> str:
    if list_name == "positions":
        return f"{item.get('title', '?')} @ {item.get('organization', '?')}"
    if list_name == "education":
        degree = ", ".join(str(x) for x in (item.get("degree"), item.get("field")) if x)
        return f"{degree} — {item.get('institution', '?')}" if degree else str(item.get("institution", "?"))
    if list_name == "publications":
        return str(item.get("title", "?"))
    return str(item.get("name", "?"))


_TOKEN = re.compile(r"\w[\w+#./-]*[\w+#]|\w", re.UNICODE)
_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ers", "er", "ed", "es", "s")


def tokens(text: str) -> list[str]:
    out = []
    for tok in _TOKEN.findall(str(text).lower()):
        out.append(tok)
        if re.search(r"[./-]", tok):
            out += [part for part in re.split(r"[./-]+", tok) if part]
    return out


def _stem(tok: str) -> str:
    for suffix in _SUFFIXES:
        if len(tok) > len(suffix) + 3 and tok.endswith(suffix):
            return tok[: -len(suffix)]
    return tok


def token_match(a: str, b: str) -> bool:
    """Equal, same crude stem, or a long shared prefix (handles inflected languages such as Polish)."""
    if a == b or _stem(a) == _stem(b):
        return True
    shortest = min(len(a), len(b))
    if shortest >= 6:
        return len(os.path.commonprefix([a, b])) >= max(5, int(0.75 * shortest))
    return False


def _score(doc: Doc, term: str) -> tuple[float, str]:
    term_tokens = tokens(term)
    if not term_tokens:
        return 0.0, ""
    phrase = term.lower().strip()
    best, snippet = 0.0, ""
    for label, text in doc.fields:
        if not text:
            continue
        text_tokens = tokens(text)
        matched = sum(1 for q in term_tokens if any(token_match(q, t) for t in text_tokens))
        score = matched / len(term_tokens) + (0.5 if len(phrase) > 2 and phrase in text.lower() else 0.0)
        if score > best:
            best, snippet = score, f"{label}: {_snip(text, term_tokens)}"
    return best, snippet


def _snip(text: str, term_tokens: list[str], width: int = 150) -> str:
    text = " ".join(text.split())
    lower = text.lower()
    pos = min((lower.find(t) for t in term_tokens if lower.find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    piece = text[start:start + width]
    return ("…" if start else "") + piece + ("…" if start + width < len(text) else "")


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def _text(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("action") or value.get("name") or "")
    return "" if value is None else str(value)


def _flatten(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten(v) for k, v in value.items() if not str(k).startswith("_"))
    if isinstance(value, list):
        return ", ".join(_flatten(v) for v in value)
    return str(value)


def _end_year(item: dict) -> int:
    try:
        end = dates.parse(item.get("end"))
    except ValueError:
        return 0
    if end is None:
        return 9999 if item.get("start") else 0
    return dt.date.today().year if end.present else end.year


def _sort_key(item: dict) -> tuple[int, int]:
    for key in ("end", "date", "start", "year"):
        try:
            parsed = dates.parse(item.get(key))
        except ValueError:
            parsed = None
        if parsed:
            return parsed.sort_key()
    return (0, 0)
