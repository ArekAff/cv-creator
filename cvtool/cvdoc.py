"""cv.yaml: the tailored, template-agnostic content of one CV, normalised for the LaTeX templates.

Every string handed to a template is already LaTeX-escaped (with **bold**, *italic* and
[label](url) converted), and URLs are escaped separately for \\href. Templates must not escape
again. Schema and an example: method/knowledge-base.md and examples/demo/applications/.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import dates, texutil, yamlio

SECTION_KEYS = (
    "summary", "experience", "projects", "education", "skills", "certifications", "languages", "awards",
    "publications", "volunteering", "competencies", "achievements", "interests", "references", "custom",
)

HEADINGS = {
    "en": {
        "summary": "Summary", "experience": "Experience", "projects": "Projects", "education": "Education",
        "skills": "Skills", "certifications": "Certifications", "languages": "Languages", "awards": "Awards",
        "publications": "Publications", "volunteering": "Volunteering", "competencies": "Core Competencies",
        "achievements": "Key Achievements", "interests": "Interests", "references": "References",
        "contact": "Contact", "about": "About Me",
    },
    "pl": {
        "summary": "Podsumowanie zawodowe", "experience": "Doświadczenie zawodowe", "projects": "Projekty",
        "education": "Wykształcenie", "skills": "Umiejętności", "certifications": "Certyfikaty",
        "languages": "Języki obce", "awards": "Nagrody i wyróżnienia", "publications": "Publikacje",
        "volunteering": "Wolontariat", "competencies": "Kluczowe kompetencje",
        "achievements": "Najważniejsze osiągnięcia", "interests": "Zainteresowania", "references": "Referencje",
        "contact": "Kontakt", "about": "O mnie",
    },
    "de": {
        "summary": "Profil", "experience": "Berufserfahrung", "projects": "Projekte", "education": "Ausbildung",
        "skills": "Kenntnisse", "certifications": "Zertifikate", "languages": "Sprachen",
        "awards": "Auszeichnungen", "publications": "Publikationen", "volunteering": "Ehrenamt",
        "competencies": "Kernkompetenzen", "achievements": "Erfolge", "interests": "Interessen",
        "references": "Referenzen", "contact": "Kontakt", "about": "Über mich",
    },
}
WORDS = {
    "en": {"thesis": "Thesis", "grade": "Grade", "in_progress": "in progress", "expected": "expected",
           "page": "Page", "cv": "CV", "phone": "Telephone", "email": "E-mail", "residence": "Residence"},
    "pl": {"thesis": "Praca dyplomowa", "grade": "Ocena", "in_progress": "w trakcie", "expected": "planowo",
           "page": "Strona", "cv": "CV", "phone": "Telefon", "email": "E-mail", "residence": "Miejsce zamieszkania"},
    "de": {"thesis": "Abschlussarbeit", "grade": "Note", "in_progress": "laufend", "expected": "voraussichtlich",
           "page": "Seite", "cv": "Lebenslauf", "phone": "Telefon", "email": "E-Mail", "residence": "Wohnort"},
}
BABEL = {
    "en": "english", "en-us": "american", "en-gb": "british", "pl": "polish", "de": "ngerman",
    "fr": "french", "es": "spanish", "it": "italian", "nl": "dutch", "pt": "portuguese",
    "cs": "czech", "sk": "slovak", "sv": "swedish", "da": "danish", "fi": "finnish",
}
GDPR_TEXT = {
    "pl": ("Wyrażam zgodę na przetwarzanie moich danych osobowych dla potrzeb niezbędnych do realizacji "
           "procesu rekrutacji zgodnie z Rozporządzeniem Parlamentu Europejskiego i Rady (UE) 2016/679 "
           "z dnia 27 kwietnia 2016 r. w sprawie ochrony osób fizycznych w związku z przetwarzaniem danych "
           "osobowych i w sprawie swobodnego przepływu takich danych oraz uchylenia dyrektywy 95/46/WE (RODO)."),
    "en": ("I hereby consent to the processing of my personal data included in this document for the purposes "
           "of the recruitment process, in accordance with Regulation (EU) 2016/679 of the European Parliament "
           "and of the Council of 27 April 2016 (GDPR)."),
}
CEFR_RATING = {"a1": 1, "a2": 1.5, "b1": 2.5, "b2": 3.5, "c1": 4.5, "c2": 5}
WORD_RATING = {
    "native": 5, "mother tongue": 5, "ojczysty": 5, "bilingual": 5, "fluent": 4.5, "biegły": 4.5,
    "professional": 4, "advanced": 4, "zaawansowany": 4, "upper-intermediate": 3.5, "intermediate": 3,
    "średniozaawansowany": 3, "conversational": 3, "basic": 2, "podstawowy": 2, "elementary": 1.5,
}
SKILL_RATIO = {"basic": 0.35, "intermediate": 0.55, "advanced": 0.75, "expert": 0.95}
LINK_ICONS = {
    "phone": r"\faPhone", "email": r"\faEnvelope", "location": r"\faMapMarker", "linkedin": r"\faLinkedin",
    "github": r"\faGithub", "gitlab": r"\faGitlab", "website": r"\faGlobe", "twitter": r"\faTwitter",
    "orcid": r"\faOrcid", "stackoverflow": r"\faStackOverflow", "other": r"\faLink",
}
LINK_HOSTS = {
    "linkedin.com": "linkedin", "github.com": "github", "gitlab.com": "gitlab", "twitter.com": "twitter",
    "x.com": "twitter", "orcid.org": "orcid", "stackoverflow.com": "stackoverflow",
}


class Obj(dict):
    """A dict whose keys win over dict methods for attribute access, so templates can say s.items."""

    __slots__ = ()

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("__") and dict.__contains__(self, name):
            return dict.__getitem__(self, name)
        return super().__getattribute__(name)


def load(path: Path) -> dict:
    raw = yamlio.load(path, None)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} is missing or is not a YAML mapping")
    return raw


def language(raw: dict) -> str:
    return str((raw.get("meta") or {}).get("language") or "en").lower()


def structural_errors(raw: dict) -> list[str]:
    """Problems that make rendering impossible or meaningless."""
    errors = []
    header = raw.get("header")
    if not isinstance(header, dict) or not header.get("name"):
        errors.append("header.name is required")
    for key in SECTION_KEYS:
        value = raw.get(key)
        if value in (None, "", []):
            continue
        if key in ("summary", "references"):
            if not isinstance(value, str):
                errors.append(f"{key} must be a text")
        elif key == "interests":
            if not isinstance(value, (list, str)):
                errors.append("interests must be a list or a text")
        elif not isinstance(value, list):
            errors.append(f"{key} must be a list")
    for key in ("experience", "volunteering", "projects", "education"):
        for i, item in enumerate(raw.get(key) or []):
            if not isinstance(item, dict):
                errors.append(f"{key}[{i}] must be a mapping")
                continue
            for field in ("start", "end", "date"):
                try:
                    dates.parse(item.get(field))
                except ValueError as exc:
                    errors.append(f"{key}[{i}].{field}: {exc}")
    unknown = set(raw) - set(SECTION_KEYS) - {"meta", "header", "gdpr_clause"}
    if unknown:
        errors.append("unknown top-level keys: " + ", ".join(sorted(unknown)))
    return errors


def build(raw: dict, template_meta: dict | None = None, photo_file: str | None = None) -> Obj:
    """Template context: {cv, meta, labels, words}."""
    tmeta = template_meta or {}
    m = raw.get("meta") or {}
    lang = language(raw)
    base = lang.split("-")[0]
    style = str(m.get("date_format") or dates.default_style(base))
    options = {**(tmeta.get("options") or {}), **(m.get("options") or {})}

    def E(value: object) -> str:
        return "" if value in (None, "") else texutil.markup(value)

    def when(item: dict) -> str:
        text = dates.fmt_range(item.get("start"), item.get("end"), base, style)
        if not text and item.get("date") not in (None, ""):
            text = dates.fmt(dates.parse(item["date"]), base, style)
        return E(text)

    words = Obj({k: E(v) for k, v in {**WORDS["en"], **WORDS.get(base, {})}.items()})
    cv = Obj()
    cv.update(header=_header(raw.get("header") or {}, E), summary=E(raw.get("summary")))
    cv["experience"] = [_job(x, E, when) for x in raw.get("experience") or [] if isinstance(x, dict)]
    cv["volunteering"] = [_job(x, E, when) for x in raw.get("volunteering") or [] if isinstance(x, dict)]
    cv["experience_groups"] = _groups(raw.get("experience") or [], cv["experience"], base, style, E)
    cv["projects"] = [Obj(name=E(p.get("name")), role=E(p.get("role")), dates=when(p),
                          tech=[E(t) for t in _list(p.get("tech") or p.get("tools"))],
                          url=texutil.url(p["link"]) if p.get("link") else "",
                          link_text=E(_display_url(p["link"])) if p.get("link") else "",
                          description=E(p.get("description")), bullets=_bullets(p.get("bullets"), E))
                      for p in raw.get("projects") or [] if isinstance(p, dict)]
    cv["education"] = [_school(e, E, when, words) for e in raw.get("education") or [] if isinstance(e, dict)]
    cv["skills"] = _skills(raw.get("skills") or [], E)
    cv["certifications"] = [_cert(c, E, base, style, words) for c in raw.get("certifications") or []]
    cv["languages"] = [_spoken(x, E) for x in raw.get("languages") or []]
    cv["awards"] = [Obj(name=E(_get(a, "name", "title")), issuer=E(a.get("issuer")), dates=when(a),
                        description=E(a.get("description")))
                    for a in raw.get("awards") or [] if isinstance(a, dict)]
    cv["publications"] = [Obj(title=E(p.get("title")), authors=E(p.get("authors")), venue=E(p.get("venue")),
                              year=E(p.get("year")), url=texutil.url(p["link"]) if p.get("link") else "")
                          for p in raw.get("publications") or [] if isinstance(p, dict)]
    cv["competencies"] = [Obj(name=E(_get(c, "name", "title")), text=E(c.get("text") or c.get("evidence")))
                          for c in raw.get("competencies") or [] if isinstance(c, dict)]
    cv["achievements"] = [Obj(title=E(a.get("title")), text=E(a.get("text")),
                              icon=str(a.get("icon") or "faTrophy").lstrip("\\"))
                          for a in raw.get("achievements") or [] if isinstance(a, dict)]
    interests = raw.get("interests") or []
    cv["interests"] = [E(i) for i in (interests if isinstance(interests, list) else [interests])]
    cv["references"] = E(raw.get("references"))
    cv["custom"] = [Obj(title=E(c.get("title")), text=E(c.get("text")), items=[E(i) for i in _list(c.get("items"))])
                    for c in raw.get("custom") or [] if isinstance(c, dict)]
    clause = raw.get("gdpr_clause")
    cv["gdpr_clause"] = E(GDPR_TEXT.get(base, GDPR_TEXT["en"]) if clause is True else clause)

    order = list(m.get("sections_order") or tmeta.get("default_order") or SECTION_KEYS)
    hidden = set(m.get("hide") or [])
    present = [k for k in SECTION_KEYS if cv.get(k) and k not in hidden]
    sections = [k for k in order if k in present] + [k for k in present if k not in order]
    side_keys = list(options.get("side_sections") or [])

    headings = {**HEADINGS["en"], **HEADINGS.get(base, {}), **(m.get("headings") or {})}
    accent = str(m.get("accent") or "").lstrip("#").upper()
    font_size = str(m.get("font_size") or tmeta.get("default_font_size") or "11pt")
    meta = Obj(
        language=lang,
        babel=str(m.get("babel") or BABEL.get(lang) or BABEL.get(base) or "english"),
        paper=str(m.get("paper") or tmeta.get("default_paper") or "a4").lower().replace("paper", ""),
        font_size=font_size if font_size.endswith("pt") else f"{font_size}pt",
        accent=accent if re.fullmatch(r"[0-9A-F]{6}", accent) else "",
        date_format=style,
        sections=sections,
        main=[k for k in sections if k not in side_keys],
        side=[k for k in sections if k in side_keys],
        photo=photo_file or "",
        options=options,
        pdf_title=E(f"{(raw.get('header') or {}).get('name', '')} – {WORDS.get(base, WORDS['en'])['cv']}"),
    )
    return Obj(cv=cv, meta=meta, labels=Obj({k: E(v) for k, v in headings.items()}), words=words)


# ----------------------------------------------------------------- sections
def _header(h: dict, E) -> Obj:
    name = str(h.get("name") or "")
    first, _, last = name.rpartition(" ")
    links = []
    raw_links = h.get("links") or []
    if isinstance(raw_links, dict):
        raw_links = [{"kind": k, "url": v} for k, v in raw_links.items()]
    for link in raw_links:
        link = link if isinstance(link, dict) else {"url": link}
        url = str(link.get("url") or "").strip()
        if not url:
            continue
        if not re.match(r"[a-z]+:", url):
            url = "https://" + url
        kind = str(link.get("kind") or _kind_from_url(url))
        links.append(Obj(kind=kind, url=texutil.url(url), label=E(link.get("label") or _display_url(url)),
                         handle=E(link.get("handle") or _handle(kind, url)), icon=LINK_ICONS.get(kind, LINK_ICONS["other"])))
    email = str(h.get("email") or "").strip()
    phone = str(h.get("phone") or "").strip()
    contacts = []
    if phone:
        contacts.append(Obj(kind="phone", text=E(phone), url=texutil.url("tel:" + re.sub(r"[^\d+]", "", phone)),
                            icon=LINK_ICONS["phone"]))
    if email:
        contacts.append(Obj(kind="email", text=E(email), url=texutil.url("mailto:" + email), icon=LINK_ICONS["email"]))
    contacts += [Obj(kind=l.kind, text=l.label, url=l.url, icon=l.icon) for l in links]
    by_kind = {l.kind: l for l in reversed(links)}
    return Obj(
        name=E(name), first_name=E(h.get("first_name") or first or name), last_name=E(h.get("last_name") or last),
        headline=E(h.get("headline")), location=E(h.get("location")), email=E(email),
        email_url=texutil.url("mailto:" + email) if email else "", phone=E(phone),
        phone_url=texutil.url("tel:" + re.sub(r"[^\d+]", "", phone)) if phone else "",
        links=links, contacts=contacts,
        linkedin=by_kind.get("linkedin"), github=by_kind.get("github"), website=by_kind.get("website"),
        quote=E(h.get("quote")), photo=bool(h.get("photo")),
    )


def _job(x: dict, E, when) -> Obj:
    return Obj(
        title=E(_get(x, "title", "position", "role")), organization=E(_get(x, "organization", "company", "employer")),
        location=E(x.get("location")), dates=when(x), description=E(x.get("description")),
        subtitle=E(x.get("subtitle")), tech=[E(t) for t in _list(x.get("tech") or x.get("tools"))],
        bullets=_bullets(x.get("bullets"), E),
    )


def _groups(raw_jobs: list, jobs: list[Obj], lang: str, style: str, E) -> list[Obj]:
    """Consecutive roles at the same organisation (promotions) grouped under one heading."""
    groups: list[Obj] = []
    raw_jobs = [x for x in raw_jobs if isinstance(x, dict)]
    for raw, job in zip(raw_jobs, jobs):
        org_key = str(_get(raw, "organization", "company", "employer")).strip().lower()
        if groups and org_key and groups[-1]["_key"] == org_key:
            groups[-1].roles.append(job)
            groups[-1]["_raw"].append(raw)
        else:
            groups.append(Obj(_key=org_key, _raw=[raw], organization=job.organization, location=job.location,
                              roles=[job]))
    for g in groups:
        starts = [d for r in g["_raw"] if (d := dates.parse(r.get("start")))]
        ends = [d for r in g["_raw"] if (d := dates.parse(r.get("end")))]
        first = min(starts, key=lambda d: d.sort_key()) if starts else None
        last = max(ends, key=lambda d: d.sort_key()) if ends else None
        g["dates"] = E(" – ".join(dates.fmt(d, lang, style) for d in (first, last) if d))
        del g["_key"], g["_raw"]
    return groups


def _school(e: dict, E, when, words: Obj) -> Obj:
    degree, field = _get(e, "degree"), _get(e, "field", "major")
    details = []
    if e.get("thesis"):
        details.append(f"{words.thesis}: {E(e['thesis'])}")
    if e.get("grade"):
        details.append(f"{words.grade}: {E(e['grade'])}")
    details += [E(d) for d in _list(e.get("details"))]
    return Obj(
        degree=E(degree), field=E(field), degree_line=E(", ".join(str(x) for x in (degree, field) if x)),
        institution=E(_get(e, "institution", "school", "university")), location=E(e.get("location")),
        dates=when(e), details=details, grade=E(e.get("grade")), thesis=E(e.get("thesis")),
    )


def _skills(raw: list, E) -> list[Obj]:
    groups = []
    loose = []
    for entry in raw:
        if isinstance(entry, dict) and "items" in entry:
            rated = [_skill_item(i, E) for i in _list(entry.get("items"))]
            groups.append(Obj(category=E(entry.get("category")), items=[r.name for r in rated], rated=rated))
        else:
            loose.append(_skill_item(entry, E))
    if loose:
        groups.append(Obj(category="", items=[r.name for r in loose], rated=loose))
    return [g for g in groups if g["items"]]


def _skill_item(item: object, E) -> Obj:
    if isinstance(item, dict):
        level = item.get("level")
        if isinstance(level, (int, float)):
            ratio = level / 5 if level > 1 else float(level)
        else:
            ratio = SKILL_RATIO.get(str(level or "").lower())
        return Obj(name=E(item.get("name")), ratio=ratio)
    return Obj(name=E(item), ratio=None)


def _cert(c: object, E, lang: str, style: str, words: Obj) -> Obj:
    c = c if isinstance(c, dict) else {"name": c}
    in_progress = str(c.get("status") or "").lower() in ("in-progress", "in progress", "ongoing", "w trakcie")
    when = dates.fmt(dates.parse(c["date"]), lang, style) if c.get("date") else ""
    if in_progress:
        when = f"{words.in_progress}" + (f", {words.expected} {E(when)}" if when else "")
    else:
        when = E(when)
    return Obj(name=E(c.get("name")), issuer=E(c.get("issuer")), when=when, in_progress=in_progress,
               url=texutil.url(c["url"]) if c.get("url") else "")


def _spoken(x: object, E) -> Obj:
    x = x if isinstance(x, dict) else {"language": x}
    level = str(x.get("level") or "")
    rating = x.get("rating")
    if rating is None:
        key = level.lower()
        cefr = re.search(r"\b([abc][12])\b", key)
        rating = CEFR_RATING[cefr.group(1)] if cefr else next(
            (v for w, v in WORD_RATING.items() if w in key), 3)
    return Obj(language=E(x.get("language")), level=E(level), rating=rating)


def _bullets(raw: object, E) -> list[Obj]:
    out = []
    for b in _list(raw):
        if isinstance(b, dict):
            out.append(Obj(text=E(b.get("text")), source=[str(s) for s in _list(b.get("source"))]))
        elif b not in (None, ""):
            out.append(Obj(text=E(b), source=[]))
    return out


def _get(d: dict, *keys: str) -> str:
    for key in keys:
        if d.get(key) not in (None, ""):
            return str(d[key])
    return ""


def _list(value: object) -> list:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _kind_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if url.startswith("mailto:"):
        return "email"
    return next((kind for h, kind in LINK_HOSTS.items() if host == h or host.endswith("." + h)), "website")


def _display_url(url: str) -> str:
    url = re.sub(r"^[a-z]+://", "", str(url).strip())
    return url.removeprefix("www.").rstrip("/")


def _handle(kind: str, url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if kind == "linkedin" and len(parts) >= 2 and parts[0] in ("in", "pub"):
        return parts[1]
    if kind in ("github", "gitlab", "twitter", "orcid") and parts:
        return parts[0]
    return _display_url(url)
