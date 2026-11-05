"""Support for the classify → write → judge loop of /apply.

  classification   `classify_signals` counts technical vs non-technical signals in a job ad. It is
                   only a hint for the listing-classifier agent, which writes classification.yaml.
  rounds           every round of the cv-writer is snapshotted in judging/round-N/ (cv.yaml, cv.pdf,
                   build.yaml); the cv-judge adds judge.yaml there.
  loop policy      `evaluate` recomputes the verdict from the scores (method/judge-rubric.md) and
                   `advice` says what happens next: judge, revise, ask the person, or stop.
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path

from . import yamlio

# --- rubric (method/judge-rubric.md)
CRITERIA = {"relevance": 20, "keywords": 20, "evidence": 20, "summary": 10, "skills": 10, "format": 10,
            "language": 10}
PASS_TOTAL = 85
MIN_RATIO = 0.6
MAX_ROUNDS = 4
PLATEAU = 3

# --- classification hint: (pattern, weight); patterns are matched case-insensitively as whole words
_TECH_TERMS = [
    "python", "java", "javascript", "typescript", r"c\+\+", "c#", "golang", "rust", "scala", "kotlin", "swift",
    "ruby", "php", "matlab", "sql", "nosql", "bash", "react", "angular", "vue", "django", "flask", "fastapi",
    "spring", r"node\.js", r"\.net", "pandas", "numpy", "scikit-learn", "pytorch", "tensorflow", "spark", "hadoop",
    "kafka", "airflow", "dbt", "machine learning", "deep learning", "nlp", "statistics", "statistical",
    "data model(?:l)?ing", "data pipelines?", "etl", "data warehouse", "bigquery", "snowflake", "databricks",
    "power bi", "tableau", "looker", "a/b test(?:ing|s)?", "aws", "azure", "gcp", "google cloud", "kubernetes",
    "docker", "terraform", "ci/cd", "devops", "linux", "microservices", "rest apis?", "graphql", "git",
    "autocad", "solidworks", "revit", "bim", "plc", "scada", "embedded", "firmware", "fpga", "hvac",
    "cybersecurity", "networking", "cisco", "siem", "software", "algorithms", "system design", "code review",
    "test automation", "backend", "frontend", "full-stack", "infrastructure", "databases?", "window functions",
    "forecast(?:s|ing)? models?", "scripting", "cloud",
]
_NONTECH_TERMS = [
    "sales", "quota", "prospecting", "cold calling", "account executive", "business development", "closing",
    "territory", "revenue targets?", "client relationships", "account management", "upsell", "new logos",
    "marketing", "campaigns?", "brand(?:ing)?", "social media", "copywriting", "public relations", "events",
    "recruiting", "recruitment", "talent acquisition", "human resources", "hr", "payroll", "employee relations",
    "benefits", "compensation", "hris", "learning and development", "administrative", "scheduling", "calendars?",
    "office management", "reception", "customer service", "customer support", "customer success",
    "call cent(?:er|re)", "front desk", "accounting", "accounts payable", "accounts receivable", "bookkeeping",
    "gaap", "ifrs", "audit", "tax", "financial statements", "budgeting", "invoicing", "teaching", "curriculum",
    "patient care", "nursing", "hospitality", "guests?", "negotiation", "fundraising", "merchandising",
]
_TECH_TITLE = re.compile(r"engineer|developer|programmer|architect|devops|\bsre\b|scientist|technician|\bqa\b|"
                         r"tester|\bdata\b|\bbi\b|machine learning|\bml\b|\bit\b|security|cloud|network|"
                         r"analytics", re.I)
_NONTECH_TITLE = re.compile(r"sales|account (?:executive|manager)|marketing|recruit|talent|\bhr\b|human resources|"
                            r"people partner|assistant|coordinator|receptionist|customer|accountant|bookkeeper|"
                            r"controller|teacher|nurse|copywriter|brand", re.I)


def classify_signals(app_dir: Path) -> dict:
    """Count technical and non-technical signals in posting.md. A hint, not the decision."""
    posting = (app_dir / "posting.md").read_text(encoding="utf-8") if (app_dir / "posting.md").exists() else ""
    marker = posting.find("## Original posting")
    text = posting[marker:] if marker >= 0 else posting
    req = yamlio.load(app_dir / "requirements.yaml", {}) or {}
    title = str((req.get("job") or {}).get("title") or "")
    if not title:
        heading = re.search(r"^#\s+(.+?)(?:\s+[—–-]\s+.*)?$", posting, re.M)
        title = heading.group(1).strip() if heading else ""

    def count(terms: list[str]) -> dict[str, int]:
        found = {}
        for term in terms:
            hits = re.findall(rf"(?<![\w+#.]){term}(?![\w+#])", text, re.I)
            if hits:
                found[hits[0].lower()] = min(len(hits), 3)  # repeated terms count, capped
        return found

    tech, nontech = count(_TECH_TERMS), count(_NONTECH_TERMS)
    tech_score, nontech_score = sum(tech.values()), sum(nontech.values())
    title_signal = ""
    if title and _NONTECH_TITLE.search(title) and not re.search(r"engineer|developer|data", title, re.I):
        nontech_score += 8
        title_signal = "non-technical"
    elif title and _TECH_TITLE.search(title):
        tech_score += 8
        title_signal = "technical"
    suggested = "technical" if tech_score >= nontech_score else "non-technical"
    high, low = max(tech_score, nontech_score), min(tech_score, nontech_score)
    ratio = high / max(low, 1)
    agrees = title_signal in ("", suggested)
    confidence = "high" if ratio >= 2 and agrees else ("medium" if ratio >= 1.3 else "low")
    top = lambda d: [k for k, _ in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
    return {"suggested": suggested, "confidence": confidence, "title": title, "title_signal": title_signal,
            "technical_score": tech_score, "non_technical_score": nontech_score,
            "technical_terms": top(tech), "non_technical_terms": top(nontech)}


def load_classification(app_dir: Path) -> dict:
    data = yamlio.load(app_dir / "classification.yaml", {}) or {}
    return data if isinstance(data, dict) else {}


# ================================================================ rounds
def judging_dir(app_dir: Path) -> Path:
    return app_dir / "judging"


def round_dirs(app_dir: Path) -> list[Path]:
    root = judging_dir(app_dir)
    if not root.exists():
        return []
    found = [p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"round-\d+", p.name)]
    return sorted(found, key=lambda p: int(p.name.split("-")[1]))


def save_round(app_dir: Path) -> tuple[int, Path]:
    """Snapshot the current cv.yaml + PDF + build facts as the next round (or refresh an unjudged one)."""
    from . import checks, lint
    from pypdf import PdfReader

    cv_yaml, pdf = app_dir / "cv.yaml", app_dir / "cv" / "main.pdf"
    if not cv_yaml.exists():
        raise LookupError(f"{app_dir.name}/cv.yaml does not exist yet")
    if not pdf.exists() or pdf.stat().st_mtime < cv_yaml.stat().st_mtime:
        raise LookupError("cv.yaml changed after the last build: run  uv run cv build <app>  first")
    rounds = round_dirs(app_dir)
    if rounds and not (rounds[-1] / "judge.yaml").exists():
        folder = rounds[-1]  # saved but not judged yet: refresh it
    else:
        folder = judging_dir(app_dir) / f"round-{len(rounds) + 1}"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cv_yaml, folder / "cv.yaml")
    shutil.copy2(pdf, folder / "cv.pdf")
    pages = len(PdfReader(str(pdf)).pages)
    findings = lint.lint(app_dir, pages=pages)
    try:
        ats = checks.ats_check(app_dir)
        ats_summary = {"keywords_found": ats["keywords_found"], "missing_keywords": ats["missing_keywords"],
                       "problems": ats["problems"]}
    except (LookupError, ValueError) as exc:
        ats_summary = {"error": str(exc)}
    meta = yamlio.load(cv_yaml, {}).get("meta") or {}
    number = int(folder.name.split("-")[1])
    yamlio.dump({
        "round": number, "saved": dt.datetime.now().isoformat(timespec="seconds"),
        "template": meta.get("template", ""), "track": load_classification(app_dir).get("track", ""),
        "pages": pages,
        "lint": {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("error", "warning", "info")},
        "lint_findings": [str(f) for f in findings if f.level != "info"],
        "ats": ats_summary,
    }, folder / "build.yaml")
    return number, folder


def evaluate(judge: dict) -> dict:
    """The verdict the rubric's rules give for this judge.yaml, independent of what the judge wrote."""
    scores = judge.get("scores") or {}
    problems, low = [], []
    total = 0
    for key, maximum in CRITERIA.items():
        entry = scores.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("score"), (int, float)):
            problems.append(f"no score for {key}")
            continue
        score = entry["score"]
        if not 0 <= score <= maximum:
            problems.append(f"{key} score {score} outside 0..{maximum}")
        total += score
        if score < MIN_RATIO * maximum:
            low.append(f"{key} {score}/{maximum}")
    if isinstance(judge.get("total"), (int, float)) and judge["total"] != total:
        problems.append(f"total says {judge['total']} but the scores add up to {total}")
    blockers = [str(b) for b in judge.get("blockers") or [] if str(b).strip()]
    findings = [f for f in judge.get("findings") or [] if isinstance(f, dict)]
    fixable = [f for f in findings if f.get("severity") in ("must", "should") and not f.get("needs_input")]
    must_fixable = [f for f in fixable if f.get("severity") == "must"]
    needs_input = [f for f in findings if f.get("needs_input")]
    if problems:
        verdict = "invalid"
    elif not blockers and not must_fixable and total >= PASS_TOTAL and not low:
        verdict = "pass"
    elif not blockers and not fixable and needs_input:
        verdict = "needs-input"
    else:
        verdict = "revise"
    return {"verdict": verdict, "total": total, "low": low, "blockers": blockers, "problems": problems,
            "fixable": len(fixable), "needs_input": len(needs_input),
            "agrees": verdict == judge.get("verdict") or verdict == "invalid"}


def load_rounds(app_dir: Path) -> list[dict]:
    rounds = []
    for folder in round_dirs(app_dir):
        judge = yamlio.load(folder / "judge.yaml", None)
        rounds.append({
            "round": int(folder.name.split("-")[1]), "folder": folder,
            "build": yamlio.load(folder / "build.yaml", {}) or {},
            "judge": judge if isinstance(judge, dict) else None,
            "rules": evaluate(judge) if isinstance(judge, dict) else None,
        })
    return rounds


def advice(rounds: list[dict], classified: bool = True) -> dict:
    """What the loop does next, per method/judge-rubric.md."""
    if not classified:
        return {"action": "classify", "round": 0,
                "text": "next: listing-classifier writes classification.yaml (the writer and the judge need the track)"}
    if not rounds:
        return {"action": "write", "round": 1,
                "text": "next: cv-writer round 1 (draft cv.yaml), build, then  uv run cv round save <app>"}
    last = rounds[-1]
    n = last["round"]
    if last["judge"] is None:
        return {"action": "judge", "round": n, "text": f"next: cv-judge round {n}"}
    rules = last["rules"]
    if rules["verdict"] == "invalid":
        return {"action": "fix-judge", "round": n,
                "text": f"next: judge.yaml of round {n} is not valid ({'; '.join(rules['problems'])}); re-run cv-judge"}
    if rules["verdict"] == "needs-input":
        return {"action": "ask", "round": n,
                "text": f"next: ask the person the judge's questions from round {n}, record the answers in the "
                        f"knowledge base, then cv-writer round {n + 1}"}
    judged = [r for r in rounds if r["rules"] and r["rules"]["verdict"] != "invalid"]
    # the round to keep: a passing one over a failing one, then the higher total, then the later one
    best = max(judged, key=lambda r: (r["rules"]["verdict"] == "pass", r["rules"]["total"], r["round"]))
    best_note = "" if best is last else (f"; keep round {best['round']} ({best['rules']['verdict']}, "
                                         f"{best['rules']['total']}/100): restore judging/round-{best['round']}/cv.yaml")
    previous = judged[-2] if len(judged) >= 2 and judged[-1] is last else None
    gain = rules["total"] - previous["rules"]["total"] if previous else None
    plateau = gain is not None and gain < PLATEAU
    if rules["verdict"] == "pass" and (not rules["fixable"] or n >= MAX_ROUNDS or plateau):
        return {"action": "stop", "reason": "pass", "round": n,
                "text": f"stop: pass in round {n} ({rules['total']}/100){best_note}"}
    if n >= MAX_ROUNDS:
        return {"action": "stop", "reason": "max-rounds", "round": n,
                "text": f"stop: {MAX_ROUNDS} rounds reached ({rules['total']}/100){best_note}"}
    if plateau:
        return {"action": "stop", "reason": "plateau", "round": n,
                "text": f"stop: plateau (total {gain:+d} since round {previous['round']}){best_note}"}
    if rules["verdict"] == "pass":  # passes, but fixable findings are left and the score is still rising
        return {"action": "revise", "round": n + 1,
                "text": f"next: cv-writer round {n + 1}: round {n} passes ({rules['total']}/100), but "
                        f"{rules['fixable']} fixable finding(s) in judging/round-{n}/judge.yaml can still improve it"}
    return {"action": "revise", "round": n + 1,
            "text": f"next: cv-writer round {n + 1} with the findings of judging/round-{n}/judge.yaml"}


def format_rounds(rounds: list[dict]) -> str:
    lines = [f"{'round':<6}{'total':<7}{'verdict (judge/rules)':<24}{'pages':<7}{'lint e/w':<10}"
             f"{'keywords':<10}weakest"]
    for r in rounds:
        build = r["build"]
        lint_counts = build.get("lint") or {}
        lint_text = f"{lint_counts.get('error', '?')}/{lint_counts.get('warning', '?')}"
        keywords = (build.get("ats") or {}).get("keywords_found", "?")
        if r["judge"] is None:
            lines.append(f"{r['round']:<6}{'-':<7}{'(not judged yet)':<24}{build.get('pages', '?')!s:<7}"
                         f"{lint_text:<10}{keywords!s:<10}")
            continue
        rules = r["rules"]
        verdict = f"{r['judge'].get('verdict', '?')}/{rules['verdict']}" + ("" if rules["agrees"] else " !")
        weakest = ", ".join(rules["low"]) or _weakest(r["judge"])
        lines.append(f"{r['round']:<6}{rules['total']:<7}{verdict:<24}{build.get('pages', '?')!s:<7}"
                     f"{lint_text:<10}{keywords!s:<10}{weakest}")
    return "\n".join(lines)


def _weakest(judge: dict) -> str:
    scores = judge.get("scores") or {}
    ratios = [(entry.get("score", 0) / CRITERIA[key], key, entry.get("score"))
              for key, entry in scores.items() if key in CRITERIA and isinstance(entry, dict)]
    if not ratios:
        return ""
    _, key, score = min(ratios)
    return f"{key} {score}/{CRITERIA[key]}"
