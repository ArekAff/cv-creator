"""Keyword coverage of a job ad (requirements.yaml) against the knowledge base and the CV, plus an
ATS-style read of the compiled PDF: can a machine extract the text, the contacts and the keywords?
"""
from __future__ import annotations

import re
from pathlib import Path

from . import cvdoc, texutil, yamlio
from .kb import KnowledgeBase, token_match, tokens


def _requirements(app_dir: Path) -> dict:
    data = yamlio.load(app_dir / "requirements.yaml", {}) or {}
    if not data:
        raise LookupError(f"{app_dir.name}/requirements.yaml not found: analyse the job ad first")
    return data


def _cv_sections(raw: dict) -> dict[str, str]:
    """Plain text of each CV area, for 'where does this keyword appear'."""
    areas = {"headline": str((raw.get("header") or {}).get("headline") or ""), "summary": str(raw.get("summary") or "")}
    bullets, skills = [], []
    for section in ("experience", "volunteering", "projects"):
        for item in raw.get(section) or []:
            if isinstance(item, dict):
                bullets.append(" ".join(str(item.get(k) or "") for k in ("title", "name", "description")))
                bullets += [str(b.get("text") if isinstance(b, dict) else b) for b in item.get("bullets") or []]
                bullets += [str(t) for t in item.get("tech") or []]
    for group in raw.get("skills") or []:
        items = group.get("items") if isinstance(group, dict) else [group]
        skills += [str(i.get("name") if isinstance(i, dict) else i) for i in items or []]
    areas["experience"] = " \n".join(bullets)
    areas["skills"] = ", ".join(skills)
    areas["education"] = " ".join(str(v) for e in raw.get("education") or [] if isinstance(e, dict)
                                  for v in e.values() if isinstance(v, (str, list)))
    areas["other"] = " ".join(str(raw.get(k) or "") for k in ("certifications", "competencies", "achievements", "languages"))
    return {k: texutil.strip_markup(v) for k, v in areas.items()}


def contains(text: str, keyword: str) -> bool:
    """The keyword as written, or all its words close together (any order, a few words apart at most).
    Words scattered over the page don't count: a reader or an ATS phrase search wouldn't see the keyword."""
    kw_tokens = tokens(keyword)
    if not kw_tokens:
        return False
    if keyword.lower() in text.lower():
        return True
    text_tokens = tokens(text)
    window = len(kw_tokens) + 3
    for start in range(max(len(text_tokens) - window, 0) + 1):
        span = text_tokens[start:start + window]
        if all(any(token_match(k, t) for t in span) for k in kw_tokens):
            return True
    return False


def coverage(app_dir: Path, kb: KnowledgeBase | None = None) -> dict:
    kb = kb or KnowledgeBase.load()
    req = _requirements(app_dir)
    cv_raw = cvdoc.load(app_dir / "cv.yaml") if (app_dir / "cv.yaml").exists() else None
    areas = _cv_sections(cv_raw) if cv_raw else {}
    rows = []
    for r in req.get("requirements") or []:
        if not isinstance(r, dict):
            continue
        terms = [str(k) for k in r.get("keywords") or []] or [str(r.get("text") or "")]
        hits = kb.search(terms, limit=3)
        row = {
            "id": r.get("id"), "type": r.get("type", "must"), "text": r.get("text"), "keywords": terms,
            "kb_evidence": [f"{h.doc.id} ({h.score})" for h in hits],
        }
        if cv_raw is not None:
            row["in_cv"] = sorted({area for term in terms for area, text in areas.items() if contains(text, term)})
        rows.append(row)
    keywords = []
    for kw in req.get("keywords") or []:
        kw = str(kw)
        entry = {"keyword": kw, "in_kb": bool(kb.search([kw], limit=1))}
        if cv_raw is not None:
            where = [area for area, text in areas.items() if contains(text, kw)]
            entry["in_cv"] = where
            entry["only_in_skills"] = where == ["skills"]
        keywords.append(entry)
    return {"application": app_dir.name, "requirements": rows, "keywords": keywords}


def format_coverage(report: dict) -> str:
    lines = [f"Coverage for {report['application']}", ""]
    has_cv = any("in_cv" in r for r in report["requirements"])
    for r in report["requirements"]:
        evidence = ", ".join(r["kb_evidence"]) or "NO EVIDENCE FOUND"
        line = f"{r['id']} [{r['type']}] {r['text']}\n    knowledge base: {evidence}"
        if has_cv:
            line += f"\n    in CV: {', '.join(r['in_cv']) or 'not mentioned'}"
        lines.append(line)
    if report["keywords"]:
        lines += ["", "Keywords:"]
        for k in report["keywords"]:
            status = "kb:yes" if k["in_kb"] else "kb:NO"
            if "in_cv" in k:
                status += f"  cv:{','.join(k['in_cv']) or 'MISSING'}"
                if k["only_in_skills"]:
                    status += "  <- only in the skills list; back it with a bullet if true"
            lines.append(f"  {k['keyword']:<32} {status}")
    return "\n".join(lines)


def ats_check(app_dir: Path) -> dict:
    """Extract the PDF text the way an applicant tracking system would and look for trouble."""
    from pypdf import PdfReader

    pdf = app_dir / "cv" / "main.pdf"
    if not pdf.exists():
        raise LookupError("no compiled PDF yet: run  uv run cv build")
    raw = cvdoc.load(app_dir / "cv.yaml")
    reader = PdfReader(str(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    (app_dir / "cv" / "ats-text.txt").write_text(text, encoding="utf-8")
    flat = " ".join(text.split())
    header = raw.get("header") or {}
    problems, notes = [], []
    if len(flat) < 300:
        problems.append("very little extractable text: the PDF may be image-based or use unmapped fonts")
    for key in ("name", "email", "phone"):
        value = str(header.get(key) or "")
        if value and not _loose_in(value, flat):
            problems.append(f"{key} '{value}' not found in the extracted text")
    if "\ufffd" in text or "(cid:" in text:
        problems.append("garbled characters in the extracted text (font without a Unicode map)")
    glued = glued_words(raw, text)
    if glued:
        problems.append("words run together in the extracted text, e.g. " + ", ".join(f"'{g}'" for g in glued[:3])
                        + ": an ATS may read them as one word (the PDF needs real spaces between words)")
    spaced = re.findall(r"(?:\b\w ){5,}\w\b", flat)
    if spaced:
        notes.append(f"letter-spaced words extract badly, e.g. '{spaced[0]}'")
    if re.search(r"[\ufb00-\ufb06]", text):
        notes.append("ligatures (fi, fl) extracted as single glyphs; most ATS normalise them")
    labels = cvdoc.build(raw).labels
    for key in cvdoc.build(raw).meta.sections:
        heading = texutil.strip_markup(_untex(labels.get(key, "")))
        if heading and heading.lower() not in flat.lower():
            notes.append(f"section heading '{heading}' not found as text")
    keywords = []
    req = yamlio.load(app_dir / "requirements.yaml", {}) or {}
    for kw in req.get("keywords") or []:
        keywords.append({"keyword": str(kw), "found": contains(flat, str(kw))})
    found = sum(1 for k in keywords if k["found"])
    return {
        "pages": len(reader.pages), "characters": len(flat), "problems": problems, "notes": notes,
        "keywords_found": f"{found}/{len(keywords)}" if keywords else "no requirements.yaml keywords",
        "missing_keywords": [k["keyword"] for k in keywords if not k["found"]],
        "text_file": str(app_dir / "cv" / "ats-text.txt"),
    }


_UPPER_OR_DIGIT = "A-ZĄĆĘŁŃÓŚŹŻÄÖÜ0-9"


def glued_words(raw: dict, text: str) -> list[str]:
    """Where the extracted text runs words together: a name, title or organisation glued to the next word
    ('Data AnalystJul 2023'), the person's name without its space, or a long stretch without any space."""
    flat = " ".join(text.split())
    header = raw.get("header") or {}
    labels = [str(header.get("name") or "")]
    for section in ("experience", "volunteering", "education", "projects", "certifications"):
        for entry in raw.get(section) or []:
            if isinstance(entry, dict):
                labels += [str(entry.get(k) or "") for k in ("title", "organization", "institution", "name")]
    found = []
    for label in sorted({texutil.strip_markup(item).strip() for item in labels if item.strip()}):
        hit = re.search(re.escape(label) + rf"(?=[{_UPPER_OR_DIGIT}])", flat)
        if hit:
            found.append(flat[hit.start():hit.end() + 8])
    name = str(header.get("name") or "").strip()
    if " " in name and name not in flat and name.replace(" ", "") in flat:
        found.append(name.replace(" ", ""))
    for run in re.findall(r"\S{30,}", flat):
        if not re.search(r"https?:|www\.|@|\.(?:com|org|net|io|eu|pl|de|uk)\b", run):
            found.append(run[:30] + "...")
    return found


def _loose_in(value: str, text: str) -> bool:
    squash = lambda s: re.sub(r"[\s()\-.]", "", s.lower())
    return squash(value) in squash(text)


def _untex(value: str) -> str:
    return re.sub(r"\\[a-zA-Z]+\{?|[{}$\\]", "", value)
