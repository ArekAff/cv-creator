"""Checks on a tailored CV (cv.yaml + compiled output) against guide-to-great-cv.txt and traceability rules.

Levels: error (fix before sending), warning (very likely worth fixing), info (consider).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import cvdoc, dates, texutil, yamlio
from .kb import KnowledgeBase, tokens, token_match

WEAK_OPENERS = (
    "responsible for", "helped", "worked on", "assisted", "participated", "involved in", "duties included",
    "tasked with", "in charge of", "was part of", "odpowiedzialny za", "odpowiedzialna za", "pomagałem",
    "pomagałam", "brałem udział", "brałam udział", "uczestniczyłem", "uczestniczyłam", "zajmowałem się",
    "zajmowałam się",
)
FIRST_PERSON = re.compile(r"\b(I|me|my|mine|myself)\b")
PLACEHOLDER = re.compile(r"\b(TODO|TBD|XXX?|lorem ipsum)\b|\?\?\?|\[\s*\]|<[^>]*>", re.IGNORECASE)
DATED_SECTIONS = ("experience", "volunteering", "projects", "education")


@dataclass
class Finding:
    level: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


def lint(app_dir: Path, kb: KnowledgeBase | None = None, pages: int | None = None) -> list[Finding]:
    raw = cvdoc.load(app_dir / "cv.yaml")
    kb = kb or KnowledgeBase.load()
    out: list[Finding] = []

    def add(level: str, where: str, message: str) -> None:
        out.append(Finding(level, where, message))

    for error in cvdoc.structural_errors(raw):
        add("error", "cv.yaml", error)
    meta = raw.get("meta") or {}
    header = raw.get("header") or {}
    if not header.get("email") and not header.get("phone"):
        add("error", "header", "no email or phone: the reader cannot contact you")
    if header.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(header["email"])):
        add("warning", "header", f"email looks malformed: {header['email']}")

    # --- every claim traceable to the knowledge base (guide: no lying or exaggerating)
    known = set(kb.index())
    for where, bullet in _bullets(raw):
        sources = bullet.get("source") if isinstance(bullet, dict) else None
        if not sources:
            add("warning", where, "bullet has no source: link it to a trail/timeline id or confirm it with the user")
            continue
        for ref in sources if isinstance(sources, list) else [sources]:
            if str(ref) not in known:
                add("error", where, f"source {ref} does not exist in the knowledge base")

    # --- bullet quality
    all_bullets = [(w, texutil.strip_markup(_text(b))) for w, b in _bullets(raw)]
    openers: dict[str, int] = {}
    with_number = 0
    endings = set()
    for where, text in all_bullets:
        low = text.lower().strip()
        if not low:
            add("error", where, "empty bullet")
            continue
        if any(low.startswith(w) for w in WEAK_OPENERS):
            add("warning", where, f"weak opener ({text.split()[0]} ...): start with what you did, then the result")
        if FIRST_PERSON.search(text):
            add("info", where, "first person (I/my): CV bullets usually drop the pronoun")
        if len(text) > 230:
            add("warning", where, f"long bullet ({len(text)} chars): keep it to one or two lines")
        elif len(text) < 35:
            add("info", where, "very short bullet: add the context or the result")
        if re.search(r"\d", text):
            with_number += 1
        first = low.split()[0] if low.split() else ""
        openers[first] = openers.get(first, 0) + 1
        endings.add(text.rstrip()[-1:] == ".")
    for verb, count in openers.items():
        if count >= 3 and verb:
            add("info", "bullets", f"{count} bullets start with '{verb}': vary the verbs")
    if len(endings) > 1:
        add("warning", "bullets", "some bullets end with a period and some do not: pick one (formatting consistency)")
    if all_bullets and with_number / len(all_bullets) < 0.3:
        add("info", "bullets", f"only {with_number}/{len(all_bullets)} bullets carry a number: pair claims with "
                               "outcomes or numbers where they are real")
    texts = [t.lower() for _, t in all_bullets]
    for t in {t for t in texts if texts.count(t) > 1}:
        add("warning", "bullets", f"duplicate bullet: {t[:60]}...")

    # --- dates: valid, consistent and reverse-chronological (guide: inconsistent dates undermine everything)
    for section in DATED_SECTIONS:
        items = [x for x in raw.get(section) or [] if isinstance(x, dict)]
        previous = None
        for i, item in enumerate(items):
            where = f"{section}[{i}]"
            try:
                start, end = dates.parse(item.get("start")), dates.parse(item.get("end"))
            except ValueError as exc:
                add("error", where, str(exc))
                continue
            if section in ("experience", "volunteering", "education") and not (start or end):
                add("warning", where, "no dates")
            if start and end and end.sort_key() < start.sort_key():
                add("error", where, "end is before start")
            key = (end or start).sort_key() if (end or start) else None
            if key and previous and key > previous and section != "projects":
                add("warning", where, "not in reverse-chronological order")
            previous = key or previous
    precision = {bool(dates.parse(v).month) for s in DATED_SECTIONS for x in raw.get(s) or [] if isinstance(x, dict)
                 for v in (x.get("start"), x.get("end")) if _is_dated(v)}
    if len(precision) > 1:
        add("info", "dates", "some dates have months and some only years: consider one precision throughout")

    # --- headline / title alignment (guide: line up your title)
    target = str((meta.get("target") or {}).get("role") or "")
    first_job = next((x for x in raw.get("experience") or [] if isinstance(x, dict)), None)
    if target and first_job and not header.get("headline"):
        if not _similar(target, str(first_job.get("title") or "")):
            add("warning", "header", f"latest title '{first_job.get('title')}' differs from the target '{target}': "
                                     "add a professional headline that connects them (only if true)")

    # --- skills must be real and preferably backed by a bullet (guide: keyword stuffing)
    kb_skill_names = [str(s.get("name")) for s in kb.skills] + [str(a) for s in kb.skills for a in s.get("aliases") or []]
    kb_text = " ".join([" ".join(map(str, t.get("skills_used") or [])) for t in kb.trails] +
                       [" ".join(map(str, p.get("tools") or [])) for p in kb.items("positions")] +
                       [str(l.get("language")) for l in kb.profile.get("languages") or [] if isinstance(l, dict)])
    narrative = " ".join(t for _, t in all_bullets) + " " + str(raw.get("summary") or "")
    spoken = " ".join(str(l.get("language")) for l in kb.profile.get("languages") or [] if isinstance(l, dict))
    for group in raw.get("skills") or []:
        items = group.get("items") if isinstance(group, dict) else [group]
        for item in items or []:
            label = str(item.get("name") if isinstance(item, dict) else item)
            if label.count("(") != label.count(")"):
                add("error", f"skills: {label}", "unbalanced parentheses: a YAML list was probably split at a "
                                                 "comma inside (...); put the item in quotes")
                continue
            name = re.sub(r"\s*\([^)]*\)", "", label).strip() or label
            if not _mentioned(name, " ".join(kb_skill_names) + " " + kb_text):
                add("warning", f"skills: {name}", "not found in the knowledge base: confirm the user really has it")
            elif not _mentioned(name, narrative) and not _mentioned(name, spoken):
                add("info", f"skills: {name}", "listed but not shown in any bullet or the summary")

    # --- text hygiene
    summary = str(raw.get("summary") or "")
    if len(summary) > 600:
        add("warning", "summary", f"summary is {len(summary)} characters: aim for 2-4 lines")
    for where, value in _strings(raw):
        if PLACEHOLDER.search(value):
            add("error", where, f"placeholder text: {value[:60]}")
        odd = texutil.unsupported_chars(value)
        if odd:
            add("warning", where, "characters that may not render with pdfLaTeX: " + " ".join(sorted(odd)))
        if re.search(r"\s{2,}", value.strip()) and "\n" not in value:
            add("info", where, "double spaces")

    # --- length
    max_pages = int(meta.get("max_pages") or 0)
    if pages and max_pages and pages > max_pages:
        add("warning", "layout", f"{pages} pages but max_pages is {max_pages}: cut the least relevant content")
    if raw.get("gdpr_clause") is None and cvdoc.language(raw).startswith("pl"):
        add("info", "gdpr_clause", "Polish applications usually end with a RODO consent clause (gdpr_clause: true)")
    _track_checks(app_dir, raw, kb, all_bullets, add)
    return out


# Words that mark a soft skill or a personality trait when they sit in the skills list.
SOFT_SKILLS = ("communication", "teamwork", "team work", "leadership", "stakeholder", "problem-solving",
               "problem solving", "collaboration", "interpersonal", "time management", "adaptability",
               "creativity", "critical thinking", "presentation", "facilitation", "mentoring", "negotiation",
               "organisation", "organization", "multitasking")
TRAITS = ("hardworking", "hard-working", "motivated", "team player", "detail-oriented", "detail oriented",
          "passionate", "results-driven", "results driven", "self-starter", "self starter", "dynamic",
          "go-getter", "proactive", "reliable", "enthusiastic")
SALES_PROOF = re.compile(r"quota|target|% of|percent of|rank|top \d|#\d|president'?s club|attainment|pipeline", re.I)


def _track_checks(app_dir: Path, raw: dict, kb: KnowledgeBase, bullets: list[tuple[str, str]], add) -> None:
    """Rules of the playbook chosen in classification.yaml (method/tailoring-*.md), where a machine can check."""
    from .tailoring import load_classification

    cls = load_classification(app_dir)
    track = cls.get("track")
    if track not in ("technical", "non-technical"):
        return
    header = raw.get("header") or {}
    req = load_requirements(app_dir)
    target = str(((raw.get("meta") or {}).get("target") or {}).get("role") or (req.get("job") or {}).get("title") or "")
    top_text = f"{header.get('headline') or ''} {raw.get('summary') or ''}"
    if target and not _covers(target, top_text):
        add("warning", "header", f"C-3: the target title '{target}' isn't in the headline or summary; "
                                 "name it there honestly (as the role you're aiming for if you haven't held it)")
    items = [(str(g.get("category") or ""), i) for g in raw.get("skills") or [] if isinstance(g, dict)
             for i in g.get("items") or []]
    names = [re.sub(r"\s*\([^)]*\)", "", str(i.get("name") if isinstance(i, dict) else i)).strip() for _, i in items]
    for name in names:
        if any(t in name.lower() for t in TRAITS):
            add("warning", f"skills: {name}", "C-9/N-11: a personality trait is not a skill; show it through a result")
    narrative = " ".join(t for _, t in bullets) + " " + str(raw.get("summary") or "")
    ats_likely = cls.get("ats_likely", (req.get("job") or {}).get("ats_likely"))
    template = str((raw.get("meta") or {}).get("template") or "")
    two_column = template in ("altacv", "receive")
    if two_column and ats_likely:
        rule = "T-15" if track == "technical" else "N-13"
        add("warning", "layout", f"{rule}/C-12: '{template}' is a two-column layout and this application is likely "
                                 "parsed by an ATS; use a single-column layout unless the CV goes straight to a person")
    if track == "technical":
        for (category, item), name in zip(items, names):
            if any(s in name.lower() for s in SOFT_SKILLS):
                add("warning", f"skills: {name}", "T-3/T-12: soft skills don't belong in a technical skills list; "
                                                  "show them in a bullet instead")
            if isinstance(item, dict) and item.get("level") is not None:
                add("info", f"skills: {name}", "T-3: skip proficiency ratings on a technical CV")
        categories = {c for c, _ in items if c}
        if len(names) > 6 and len(categories) < 2:
            add("info", "skills", "T-3: group the skills by category (Languages / Data / Cloud ...), ad's stack first")
        if len(names) > 15:
            add("warning", "skills", f"T-3: {len(names)} skills reads as a laundry list; keep ~6-12 you'd be interviewed on")
        tools = {t.lower() for s in kb.skills for t in [s.get("name"), *(s.get("aliases") or [])] if t}
        for where, text in bullets:
            named = {t for t in tools if re.search(rf"(?<![\w+#]){re.escape(t)}(?![\w+#])", text, re.I)}
            if len(named) > 3:
                add("info", where, f"T-2: {len(named)} tools in one bullet ({', '.join(sorted(named))}); 1-2 per bullet")
    else:
        for name in names:
            if any(s in name.lower() for s in SOFT_SKILLS) and not _mentioned(name, narrative):
                add("warning", f"skills: {name}", "N-5: a soft skill without a bullet that proves it reads as filler")
        if len(names) > 10:
            add("info", "skills", f"N-11: {len(names)} skills; 5-10 in the ad's own phrasing work best")
        with_number = sum(1 for _, t in bullets if re.search(r"\d", t))
        if bullets and with_number / len(bullets) < 0.5:
            add("info", "bullets", f"N-1/N-9: {with_number}/{len(bullets)} bullets carry a number; non-technical "
                                   "screeners look for results (volume, speed, KPIs) where real figures exist")
        if str(cls.get("family") or "").lower().startswith("sales") and not any(SALES_PROOF.search(t) for _, t in bullets):
            add("info", "bullets", "N-2: no bullet shows quota attainment, rank or pipeline: in sales the numbers are the evidence")


def as_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]


# ----------------------------------------------------------------- helpers
def _bullets(raw: dict) -> list[tuple[str, object]]:
    found = []
    for section in ("experience", "volunteering", "projects"):
        for i, item in enumerate(raw.get(section) or []):
            if isinstance(item, dict):
                found += [(f"{section}[{i}].bullets[{j}]", b) for j, b in enumerate(item.get("bullets") or [])]
    return found


def _text(bullet: object) -> str:
    return str(bullet.get("text") or "") if isinstance(bullet, dict) else str(bullet or "")


def _strings(value: object, where: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(where or "cv.yaml", value)]
    if isinstance(value, dict):
        return [s for k, v in value.items() if k not in ("meta", "source", "link", "url", "photo")
                for s in _strings(v, f"{where}.{k}" if where else str(k))]
    if isinstance(value, list):
        return [s for i, v in enumerate(value) for s in _strings(v, f"{where}[{i}]")]
    return []


def _is_dated(value: object) -> bool:
    try:
        parsed = dates.parse(value)
    except ValueError:
        return False
    return bool(parsed and not parsed.present)


def _similar(a: str, b: str) -> bool:
    ta = [t for t in tokens(a) if len(t) > 2]
    tb = [t for t in tokens(b) if len(t) > 2]
    if not ta or not tb:
        return True
    shared = sum(1 for x in ta if any(token_match(x, y) for y in tb))
    return shared / len(ta) >= 0.5


def _covers(phrase: str, text: str) -> bool:
    """Most of the phrase's content words appear in the text (a title 'Senior Data Analyst' in a summary)."""
    words = [t for t in tokens(phrase) if len(t) > 2]
    text_tokens = set(tokens(text))
    hits = sum(1 for w in words if any(token_match(w, t) for t in text_tokens))
    return not words or hits / len(words) >= 0.75


def _mentioned(name: str, text: str) -> bool:
    name_tokens = tokens(name)
    text_tokens = set(tokens(text))
    return bool(name_tokens) and all(any(token_match(n, t) for t in text_tokens) for n in name_tokens)


def load_requirements(app_dir: Path) -> dict:
    return yamlio.load(app_dir / "requirements.yaml", {}) or {}
