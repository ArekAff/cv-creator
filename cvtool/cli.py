"""Command line interface: uv run cv <command> (see uv run cv --help)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import webbrowser
import zipfile
from pathlib import Path

from . import (apps, checks, compile as latex, cvdoc, kb as kbmod, lint as lintmod, paths, render as rendermod,
               resume, tailoring, yamlio)
from .kb import KnowledgeBase


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _app(ref: str | None) -> Path:
    """The application folder; it also pins whose knowledge base the command uses (see _pin_owner)."""
    folder = apps.resolve(ref)
    _pin_owner(folder)
    return folder


def _pin_owner(app_dir: Path) -> None:
    """An application belongs to the person two levels up (<person>/applications/<app>): use that person's
    profile, whatever profile is active. Agents that pass a folder path can't mix people up."""
    owner = app_dir.parent.parent
    if app_dir.parent.name == "applications" and (owner / "profile").is_dir():
        os.environ["CV_DATA_DIR"] = str(owner)


def _select_person(value: str) -> None:
    """--person: a profile id, or a person's folder (the one holding profile/), e.g. examples/demo."""
    if "/" not in value and "\\" not in value:
        os.environ["CV_PERSON"] = value
        return
    folder = Path(value)
    if not (folder / "profile").is_dir():
        raise paths.NoProfileError(f"{value} is not a person's folder (there is no profile/ inside)")
    os.environ["CV_DATA_DIR"] = str(folder.resolve())


def _who() -> str:
    """'ola (Ola Kowalska)' for the active person, or the data folder when CV_DATA_DIR is set."""
    person = paths.active_person()
    name = (KnowledgeBase.load().profile.get("person") or {}).get("name") or ""
    label = person or paths.data_dir().name
    return f"{label} ({name})" if name and name.lower() != label else label


# ----------------------------------------------------------------- profiles (people)
def cmd_profile(args: argparse.Namespace) -> int:
    if args.profile_cmd == "add":
        person_id = args.id or apps.slugify(args.name, 30)
        folder = paths.people_dir() / person_id
        if folder.exists():
            print(f"profile '{person_id}' already exists: switch to it with  uv run cv profile use {person_id}")
            return 1
        kbmod.init_profile(folder / "profile", person_name=args.name)
        for sub in ("applications", "inbox"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        paths.set_active(person_id)
        print(f"created people/{person_id}/ for {args.name} (now active)")
        return 0
    if args.profile_cmd == "use":
        ids = paths.person_ids()
        wanted = args.id.lower()
        matches = [i for i in ids if i == wanted] or [i for i in ids if i.startswith(apps.slugify(wanted, 30))]
        if len(matches) != 1:
            print(f"no single profile matches '{args.id}' (existing: {', '.join(ids) or 'none'})")
            return 1
        paths.set_active(matches[0])
        os.environ["CV_PERSON"] = matches[0]
        print(f"active profile: {_who()}")
        return 0
    if args.profile_cmd == "current":
        print(_who())
        return 0
    # list
    ids = paths.person_ids()
    if not ids:
        print("no profiles yet: uv run cv profile add \"<your name>\"")
    try:
        active = paths.active_person()
    except paths.NoProfileError:
        active = None
    for person_id in ids:
        kb = KnowledgeBase.load(paths.people_dir() / person_id / "profile")
        status = kb.status()
        name = status["name"] or "-"
        marker = "*" if person_id == active else " "
        print(f"{marker} {person_id:<14} {name:<26} {status['readiness']:<9} "
              f"{status['counts']['positions']} positions, {status['counts']['trails']} trails")
    if (paths.ROOT / "profile").exists():
        print("note: profile/ in the project root is from the single-person layout; "
              "move it into people/<id>/profile to use it")
    return 0


# ----------------------------------------------------------------- classify → write → judge loop
def cmd_classify(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    hint = tailoring.classify_signals(app_dir)
    if args.json:
        _print_json(hint)
        return 0
    print(f"Signals in {app_dir.name}: suggests {hint['suggested'].upper()} ({hint['confidence']} confidence)")
    print(f"  title: {hint['title'] or '?'}" + (f"  -> {hint['title_signal']}" if hint["title_signal"] else ""))
    print(f"  technical {hint['technical_score']}: {', '.join(hint['technical_terms']) or '-'}")
    print(f"  non-technical {hint['non_technical_score']}: {', '.join(hint['non_technical_terms']) or '-'}")
    decided = tailoring.load_classification(app_dir)
    if decided:
        print(f"classification.yaml: {decided.get('track')} / {decided.get('family')} "
              f"(confidence {decided.get('confidence')}, by {decided.get('decided_by', '?')})")
    else:
        print("A hint only: the listing-classifier agent decides and writes classification.yaml "
              "(method/listing-classification.md).")
    return 0


def cmd_round(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    if args.round_cmd == "save":
        number, folder = tailoring.save_round(app_dir)
        build = yamlio.load(folder / "build.yaml", {}) or {}
        lint_counts = build.get("lint") or {}
        print(f"saved round {number} -> {paths.rel(folder)}  ({build.get('pages')} page(s), lint "
              f"{lint_counts.get('error', 0)} error(s) / {lint_counts.get('warning', 0)} warning(s), "
              f"keywords {(build.get('ats') or {}).get('keywords_found', '?')})")
        print(f"next: write {paths.rel(folder / 'changes.md')}, then cv-judge round {number}")
        return 0
    rounds = tailoring.load_rounds(app_dir)
    track = tailoring.load_classification(app_dir).get("track")
    advice = tailoring.advice(rounds, classified=track in ("technical", "non-technical"))
    if args.json:
        _print_json({"rounds": [{k: v for k, v in r.items() if k != "folder"} for r in rounds], "advice": advice})
        return 0
    print(f"{app_dir.name}  (track: {track or 'not classified yet'})")
    if rounds:
        print(tailoring.format_rounds(rounds))
        for r in rounds:
            if r["rules"] and not r["rules"]["agrees"]:
                print(f"  ! round {r['round']}: the judge wrote '{r['judge'].get('verdict')}', "
                      f"the rubric gives '{r['rules']['verdict']}' — the rubric wins")
            if r["rules"] and r["rules"]["problems"]:
                print(f"  ! round {r['round']}: " + "; ".join(r["rules"]["problems"]))
    print(advice["text"])
    return 0


# ----------------------------------------------------------------- existing CVs
def cmd_resume(args: argparse.Namespace) -> int:
    if args.resume_cmd == "import":
        sources = [Path(f) for f in args.files] or resume.inbox_files()
        if not sources:
            print(f"nothing to import: give a file, or put the CV into {paths.inbox_dir()}")
            return 1
        for source in sources:
            folder = resume.import_file(source)
            meta = yamlio.load(folder / "import.yaml", {}) or {}
            print(f"imported {source.name} -> {paths.rel(folder)}  "
                  f"[{meta.get('kind')}, text {meta.get('text_quality')}, {meta.get('text_chars')} characters]")
            for note in meta.get("notes") or []:
                print(f"  note: {note}")
        print("next: read text.md (and the original), write extracted.yaml (method/knowledge-base.md, "
              "'CV imports'), then  uv run cv resume diff <import>")
        return 0
    if args.resume_cmd == "list":
        for name in (p.name for p in resume.inbox_files()):
            print(f"inbox     {name}")
        for folder in resume.imports():
            if not (folder / "extracted.yaml").exists():
                state = "extracted.yaml missing"
            else:
                report = resume.diff(folder, write=False)
                state = f"{report['open']} open item(s)" if report["interview_needed"] else "done (nothing new)"
            print(f"import    {folder.name:<40} {state}")
        if not resume.inbox_files() and not resume.imports():
            print(f"no CVs imported yet (inbox: {paths.inbox_dir()})")
        return 0
    folder = resume.resolve(args.import_id)
    if args.resume_cmd == "resolve":
        resume.record_resolution(folder, args.key, args.how, args.kb_ref or "", args.note or "")
        print(f"{args.key}: {args.how}" + (f" ({args.kb_ref})" if args.kb_ref else ""))
    report = resume.diff(folder)
    if getattr(args, "json", False):
        _print_json(report)
    else:
        print(resume.format_diff(report))
    return 0


# ----------------------------------------------------------------- knowledge base
def cmd_doctor(args: argparse.Namespace) -> int:
    print(f"Project:   {paths.ROOT}")
    print(f"Python:    {sys.version.split()[0]} ({sys.executable})")
    engines = latex.available_engines()
    if engines:
        for name, path in engines.items():
            print(f"LaTeX:     {name} -> {path}")
    else:
        print("LaTeX:     none found. Install MiKTeX (scoop install miktex) or TeX Live, or compile on Overleaf.")
    print(f"People:    {', '.join(paths.person_ids()) or 'none yet'}  "
          f"({paths.people_dir()}, from {paths.people_dir_source()})")
    synced_by = paths.in_cloud_folder(paths.people_dir())
    if synced_by:
        print(f"           note: inside {synced_by}, so personal data syncs to the cloud; set people_dir "
              f"in {paths.LOCAL_SETTINGS.name} to keep it on this computer")
    try:
        status = KnowledgeBase.load().status()
    except paths.NoProfileError as exc:
        print(f"Profile:   {exc}")
        return 0
    print(f"Profile:   {_who()} — {status['readiness']} ({status['counts']['positions']} positions, "
          f"{status['counts']['trails']} trails)")
    print(f"Data:      {paths.data_dir()}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Create whatever is missing in the active person's folder (never overwrites)."""
    created = kbmod.init_profile()
    for folder in (paths.applications_dir(), paths.inbox_dir()):
        folder.mkdir(parents=True, exist_ok=True)
    print("\n".join(f"created {paths.rel(p)}" for p in created) or "profile already complete (nothing overwritten)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    kb = KnowledgeBase.load()
    status = kb.status()
    imports = resume.pending(kb)
    tracked = apps.summary()
    if args.json:
        _print_json({"person": paths.active_person(), **status, "cv_imports": imports, "applications": tracked})
        return 0
    print(f"Profile: {_who()}")
    if imports["inbox"] or imports["imports"]:
        print("CV imports — new information here means a sense-making interview (/import-resume):")
        for name in imports["inbox"]:
            print(f"  - inbox/{name}: waiting to be imported")
        for imp in imports["imports"]:
            print(f"  - {imp['id']}: {imp['state']}")
    meaning = {
        "empty": "no career knowledge yet -> run the career interview (/career-interview)",
        "scaffold": "career facts exist but no explored stories -> continue the career interview",
        "partial": "some recent roles have no explored story yet",
        "ready": "every recent role has at least one explored story",
    }
    print(f"Knowledge base: {status['readiness']} — {meaning[status['readiness']]}")
    print("Counts: " + ", ".join(f"{k} {v}" for k, v in status["counts"].items()))
    if status["trails_by_status"]:
        print("Trails: " + ", ".join(f"{k} {v}" for k, v in status["trails_by_status"].items()))
    for key, title in (("contact_missing", "Missing contact details"),
                       ("recent_positions_without_trails", "Recent positions without a story"),
                       ("trails_without_outcomes", "Trails without outcomes"),
                       ("trails_without_numbers", "Trails whose outcomes have no numbers"),
                       ("skills_without_evidence", "Skills without evidence")):
        if status[key]:
            print(f"{title}:")
            print("\n".join(f"  - {x}" for x in status[key]))
    if status["open_questions"]:
        print("Open questions:")
        print("\n".join(f"  - {tid}: {q}" for tid, q in status["open_questions"]))
    if status["last_session"]:
        print(f"Last session: {status['last_session']}")
    if tracked["tracked"]:
        print(f"Applications: {tracked['tracked']} tracked, {tracked['open']} open, "
              f"{tracked['waiting']} waiting for a reply, {tracked['replied']} replied (uv run cv app list)")
        if tracked["follow_up_due"]:
            print("Follow-up date reached: " + ", ".join(tracked["follow_up_due"]))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    issues = KnowledgeBase.load().validate()
    for issue in issues:
        print(issue)
    errors = sum(1 for i in issues if i.level == "error")
    print(f"{errors} error(s), {len(issues) - errors} warning(s)")
    return 1 if errors else 0


def cmd_search(args: argparse.Namespace) -> int:
    hits = KnowledgeBase.load().search(args.terms, limit=args.limit)
    if args.json:
        _print_json([{"id": h.doc.id, "kind": h.doc.kind, "title": h.doc.title, "score": h.score,
                      "matched": h.matched, "snippet": h.snippet, "file": paths.rel(h.doc.path)} for h in hits])
        return 0
    if not hits:
        print("no matches")
    for h in hits:
        print(f"{h.score:>5}  {h.doc.id:<12} {h.doc.kind:<14} {h.doc.title}")
        print(f"       matched: {', '.join(h.matched)} | {h.snippet}")
    return 0


def cmd_trail(args: argparse.Namespace) -> int:
    path = kbmod.new_trail(args.title, args.link or [])
    print(paths.rel(path))
    return 0


def cmd_next_id(args: argparse.Namespace) -> int:
    print(KnowledgeBase.load().next_id(args.kind))
    return 0


def cmd_master(args: argparse.Namespace) -> int:
    kb = KnowledgeBase.load()
    out = Path(args.out) if args.out else kb.root / "master-resume.md"
    out.write_text(kb.master_markdown(), encoding="utf-8")
    print(paths.rel(out))
    return 0


# ----------------------------------------------------------------- applications
_FIELD_HELP = {
    "link": "the listing's web address", "source": "where the ad was found (LinkedIn, a job board, a referral ...)",
    "salary": "as stated in the ad", "expected_salary": "the salary you asked for, if a form asked",
    "work_mode": "remote | hybrid | on-site", "deadline": "YYYY-MM-DD",
    "contact": "recruiter or hiring manager", "sent_via": "how it was sent",
    "next_step": "e.g. \"phone screen Thu 10:00\"", "follow_up": "YYYY-MM-DD to chase them or check",
}


def cmd_app(args: argparse.Namespace) -> int:
    if args.app_cmd == "new":
        details = {k: getattr(args, k) for k in ("link", "salary", "location", "work_mode", "deadline")}
        folder = apps.create(args.company, args.role, args.date, args.source or "", **details)
        print(paths.rel(folder))
    elif args.app_cmd == "path":
        print(paths.rel(_app(args.ref)))
    elif args.app_cmd == "list":
        entries = apps.load_tracker()
        if args.open:
            entries = [e for e in entries if (e.get("status") or "draft") not in apps.CLOSED]
        if args.json:
            _print_json([apps.row(e) for e in apps.newest_first(entries)])
        else:
            print(apps.format_list(entries))
    elif args.app_cmd == "show":
        entry = apps.get(_app(args.ref))
        if args.json:
            _print_json(apps.row(entry))
        else:
            print(apps.format_entry(entry))
    elif args.app_cmd == "set":
        app_dir = _app(args.ref)
        fields = {k: getattr(args, k) for k in apps.EDITABLE if getattr(args, k) is not None}
        if not fields:
            print("nothing to set: give one or more of "
                  + " ".join("--" + k.replace("_", "-") for k in apps.EDITABLE))
            return 1
        apps.edit(app_dir, **fields)
        print(f"{app_dir.name}: " + ", ".join(f"{k} = {v}" if v else f"{k} cleared" for k, v in fields.items()))
    elif args.app_cmd == "status":
        entry = apps.set_status(_app(args.ref), args.status, args.note or "", args.date)
        print(f"{entry['id']}: {entry['status']} ({apps.STATUS_LABELS[entry['status']]})")
        if args.status == "sent":
            _report_sent(entry)
    elif args.app_cmd == "sent":
        entry = apps.record_sent(_app(args.ref), args.date, args.via or "", Path(args.file) if args.file else None,
                                 args.note or "")
        print(f"{entry['id']}: {entry['status']} ({apps.STATUS_LABELS[entry['status']]})")
        _report_sent(entry)
    elif args.app_cmd == "stats":
        print(apps.stats())
    return 0


def _report_sent(entry: dict) -> None:
    last = (entry.get("sent_cvs") or [{}])[-1]
    if last.get("file"):
        print(f"  sent {last['date']}" + (f" via {last['via']}" if last.get("via") else "")
              + f"; the CV that went out is kept in {last['file']}")
    else:
        print("  no CV file recorded: keep the one that went out with  uv run cv app sent <app> --file <cv.pdf>")


def cmd_tracker(args: argparse.Namespace) -> int:
    from . import tracker
    if not tracker.people():
        print("no profiles yet: uv run cv profile add \"<your name>\"")
        return 1
    try:
        server = tracker.TrackerServer(args.port)
    except OSError:
        print(f"port {args.port} is taken: the tracker may be open already at http://127.0.0.1:{args.port}/ "
              f"(or use --port {args.port + 1})")
        return 1
    print(f"Application tracker: {server.url}  (only this computer can open it; Ctrl+C stops it)", flush=True)
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


# ----------------------------------------------------------------- CV
def cmd_templates(args: argparse.Namespace) -> int:
    available = rendermod.templates()
    if args.json:
        _print_json({tid: {**t.meta, "custom": t.custom, "dir": paths.rel(t.dir)} for tid, t in available.items()})
        return 0
    for tid, t in available.items():
        m = t.meta
        print(f"{tid:<14} {t.name}  [{m.get('engine', 'pdflatex')}, {m.get('columns', '?')} col, ATS {m.get('ats', '?')}]")
        if m.get("look"):
            print(f"{'':<14} {m['look']}")
        if m.get("best_for"):
            print(f"{'':<14} best for: {', '.join(m['best_for'])}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    result = rendermod.render(_app(args.ref), args.template, args.force)
    print(f"rendered with {result.template.id} -> {paths.rel(result.out_dir / 'main.tex')}")
    return 0


def _engine_for(app_dir: Path, override: str | None) -> str:
    if override:
        return override
    meta = (cvdoc.load(app_dir / "cv.yaml").get("meta") or {})
    if meta.get("engine"):
        return str(meta["engine"])
    return rendermod.get_template(str(meta.get("template") or "jakes")).engine


def _report_compile(result: latex.CompileResult) -> None:
    state = "OK" if result.ok else "FAILED"
    pages = f", {result.pages} page(s)" if result.pages else ""
    print(f"compile {state} with {result.engine} in {result.seconds}s{pages}")
    for e in dict.fromkeys(result.errors):
        print(f"  error: {e}")
    if result.missing_chars:
        print("  missing characters (font cannot show them): " + " ".join(result.missing_chars))
    for o in result.overfull[:5]:
        print(f"  overfull: {o}")
    for w in result.warnings[:5]:
        print(f"  warning: {w}")


def cmd_compile(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    result = latex.compile_tex(app_dir / "cv" / "main.tex", _engine_for(app_dir, args.engine))
    _report_compile(result)
    return 0 if result.ok else 1


def _publish_pdf(app_dir: Path, pdf: Path, raw: dict) -> Path:
    """Copy the PDF to a clear name: <Name>_CV_<Company>_<date>.pdf (guide: stay organized)."""
    entry = next((e for e in apps.load_tracker(app_dir.parent) if e.get("id") == app_dir.name), {})
    company = (raw.get("meta") or {}).get("target", {}).get("company") or entry.get("company") or app_dir.name
    name = (raw.get("header") or {}).get("name") or "CV"
    target = app_dir / f"{apps.file_safe(name)}_CV_{apps.file_safe(company)}_{dt.date.today().isoformat()}.pdf"
    shutil.copy2(pdf, target)
    return target


def cmd_build(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    result = rendermod.render(app_dir, args.template, args.force)
    print(f"rendered with {result.template.id} -> {paths.rel(result.out_dir / 'main.tex')}")
    raw = cvdoc.load(app_dir / "cv.yaml")
    engine = args.engine or (raw.get("meta") or {}).get("engine") or result.template.engine
    compiled = latex.compile_tex(result.out_dir / "main.tex", engine)
    _report_compile(compiled)
    findings = lintmod.lint(app_dir, pages=compiled.pages)
    _print_findings(findings)
    if not compiled.ok:
        return 1
    published = _publish_pdf(app_dir, compiled.pdf, raw)
    print(f"PDF: {paths.rel(published)}")
    try:
        report = checks.ats_check(app_dir)
        print(f"ATS read: {report['characters']} characters, keywords {report['keywords_found']}")
        for p in report["problems"]:
            print(f"  problem: {p}")
        for n in report["notes"]:
            print(f"  note: {n}")
        if report["missing_keywords"]:
            print("  keywords not found in the PDF text: " + ", ".join(report["missing_keywords"]))
    except Exception as exc:  # the ATS read is advisory
        print(f"ATS read skipped: {exc}")
    apps.update(app_dir, template=result.template.id, cv_pdf=published.name,
                headline=str((raw.get("header") or {}).get("headline") or ""))
    return 0


def _print_findings(findings: list[lintmod.Finding]) -> None:
    order = {"error": 0, "warning": 1, "info": 2}
    for f in sorted(findings, key=lambda f: order[f.level]):
        print(f"  {f}")
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in order}
    print(f"lint: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} note(s)")


def cmd_lint(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    pdf = app_dir / "cv" / "main.pdf"
    pages = None
    if pdf.exists():
        from pypdf import PdfReader
        pages = len(PdfReader(str(pdf)).pages)
    findings = lintmod.lint(app_dir, pages=pages)
    if args.json:
        _print_json(lintmod.as_dicts(findings))
    else:
        _print_findings(findings)
    return 1 if any(f.level == "error" for f in findings) else 0


def cmd_ats(args: argparse.Namespace) -> int:
    report = checks.ats_check(_app(args.ref))
    _print_json(report)
    return 1 if report["problems"] else 0


def cmd_coverage(args: argparse.Namespace) -> int:
    report = checks.coverage(_app(args.ref))
    if args.json:
        _print_json(report)
    else:
        print(checks.format_coverage(report))
    return 0


def cmd_zip(args: argparse.Namespace) -> int:
    app_dir = _app(args.ref)
    out_dir = app_dir / "cv"
    target = app_dir / f"overleaf_{app_dir.name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in out_dir.rglob("*"):
            if path.is_file() and path.suffix not in (".pdf", ".log", ".json", ".txt"):
                zf.write(path, path.relative_to(out_dir).as_posix())
    print(f"{paths.rel(target)}  (Overleaf: New Project -> Upload Project)")
    return 0


def cmd_engines(args: argparse.Namespace) -> int:
    engines = latex.available_engines()
    for name, path in engines.items():
        print(f"{name:<9} {path}")
    if not engines:
        print("none found")
    return 0 if engines else 1


def cmd_selftest(args: argparse.Namespace) -> int:
    """Render (and compile) the demo CV with every layout, in English, Polish and with hostile characters."""
    demo = paths.EXAMPLES_DIR / "demo"
    sample = next((demo / "applications").glob("*/cv.yaml"), None)
    if sample is None:
        print("examples/demo has no sample application")
        return 1
    os.environ["CV_DATA_DIR"] = str(demo)
    base = _full_variant(cvdoc.load(sample))
    wanted = args.templates or [t for t in rendermod.templates() if not t.startswith("my:")]
    variants = {"en": base, "pl": _polish_variant(base), "chars": _hostile_variant(base)}
    work = Path(tempfile.mkdtemp(prefix="cv-selftest-"))
    failures = 0
    print(f"working in {work}")
    for tid in wanted:
        for vname, raw in variants.items():
            if vname != "en" and args.quick:
                continue
            app_dir = work / f"{tid.replace(':', '_')}-{vname}"
            app_dir.mkdir(parents=True)
            data = json.loads(json.dumps(raw, default=str))
            data.setdefault("meta", {})["template"] = tid
            yamlio.dump(data, app_dir / "cv.yaml")
            try:
                result = rendermod.render(app_dir, tid)
            except rendermod.RenderError as exc:
                print(f"FAIL {tid:<12} {vname:<6} render: {exc}")
                failures += 1
                continue
            if args.no_compile:
                print(f"ok   {tid:<12} {vname:<6} rendered")
                continue
            compiled = latex.compile_tex(result.out_dir / "main.tex", result.template.engine)
            flag = "ok  " if compiled.ok and not compiled.missing_chars else "FAIL"
            failures += flag == "FAIL"
            extra = (" missing: " + " ".join(compiled.missing_chars)) if compiled.missing_chars else ""
            print(f"{flag} {tid:<12} {vname:<6} {compiled.pages or '?'} page(s), {compiled.seconds}s{extra}")
            for e in list(dict.fromkeys(compiled.errors))[:3]:
                print(f"       {e}")
    if not args.keep and not failures:
        shutil.rmtree(work, ignore_errors=True)
    print("all passed" if not failures else f"{failures} failure(s); outputs kept in {work}")
    return 1 if failures else 0


def _full_variant(raw: dict) -> dict:
    """The demo CV with every section filled, each template's own section order and no page limit."""
    data = json.loads(json.dumps(raw, default=str))
    meta = data.setdefault("meta", {})
    for key in ("hide", "sections_order", "max_pages", "headings"):
        meta.pop(key, None)
    data.update({
        "competencies": [
            {"name": "Stakeholder discovery", "text": "sits in the meetings where numbers are used before building anything"},
            {"name": "Forecasting", "text": "seasonal demand models explained as ranges to buyers"},
        ],
        "achievements": [
            {"title": "Analytics Impact Award", "text": "Lumina Retail, 2024, for the garden-range forecast", "icon": "faTrophy"},
            {"title": "6/6 regions", "text": "adopted the rebuilt Monday report", "icon": "faChartLine"},
        ],
        "awards": [{"name": "Analytics Impact Award", "issuer": "Lumina Retail", "date": "2024-12",
                    "description": "garden-range forecast"}],
        "publications": [{"title": "Short-term demand forecasting for perishable goods", "authors": "A. Nowak",
                          "venue": "MSc thesis, AGH University of Krakow", "year": 2020}],
        "languages": [{"language": "Polish", "level": "native"}, {"language": "English", "level": "C1"},
                      {"language": "German", "level": "A2"}],
        "interests": ["urban cycling", "open data", "bouldering"],
        "references": "Available on request.",
        "custom": [{"title": "Community", "items": ["Speaker, Kraków Data Meetup (2024)"]}],
    })
    for group in data.get("skills") or []:
        if group.get("category") == "Data":
            group["items"] = [{"name": "SQL", "level": "advanced"}, {"name": "Python", "level": "advanced"},
                              {"name": "dbt", "level": "intermediate"}]
    return data


def _polish_variant(raw: dict) -> dict:
    data = json.loads(json.dumps(raw, default=str))
    data.setdefault("meta", {}).update(language="pl", headings={})
    header = data.setdefault("header", {})
    header["location"] = "Kraków, Łódź — Zażółć gęślą jaźń"
    header["headline"] = "Analityczka danych — ZAŻÓŁĆ GĘŚLĄ JAŹŃ"
    data["summary"] = "Doświadczona analityczka: współpraca z zespołami sprzedaży, ćwiczenia z „cudzysłowem” i 30% oszczędności."
    data["gdpr_clause"] = True
    return data


def _hostile_variant(raw: dict) -> dict:
    data = json.loads(json.dumps(raw, default=str))
    hostile = 'R&D 100% $5 #1 snake_case {braces} ~approx^2 a<b>c | "quotes" ... C++ C# → ≥ ≈ 5 × 3 back\\slash'
    data["summary"] = f"**Bold** and *italic* and [a link](https://example.com/a_b?x=1&y=2#frag) — {hostile}"
    for section in ("experience", "projects"):
        for item in data.get(section) or []:
            if item.get("bullets"):
                first = item["bullets"][0]
                if isinstance(first, dict):
                    first["text"] = f"{first['text']} {hostile}"
                else:
                    item["bullets"][0] = f"{first} {hostile}"
    if data.get("skills"):
        data["skills"][0].setdefault("items", []).append("C++ & C# 100%")
    return data


# ----------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="uv run cv", description="CV Creator toolkit.")
    p.add_argument("--person", help="profile id, or a person's folder path, for this command only "
                                    "(default: the active profile)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("profile", help="people using this installation: add, use, list, current")
    profile_sub = s.add_subparsers(dest="profile_cmd", required=True)
    a = profile_sub.add_parser("add", help="create people/<id>/ for a new person and make it active")
    a.add_argument("name", help="the person's name, e.g. \"Ola\"")
    a.add_argument("--id", help="folder id (default: derived from the name)")
    a = profile_sub.add_parser("use", help="make a profile the active one")
    a.add_argument("id")
    profile_sub.add_parser("list", help="all profiles; * marks the active one")
    profile_sub.add_parser("current", help="print the active profile")
    s.set_defaults(func=cmd_profile)

    s = sub.add_parser("resume", help="import an existing CV and find what is new to the knowledge base")
    resume_sub = s.add_subparsers(dest="resume_cmd", required=True)
    a = resume_sub.add_parser("import", help="import CV files (PDF, DOCX, TEX, ZIP, TXT/MD, images); default: the inbox")
    a.add_argument("files", nargs="*")
    resume_sub.add_parser("list", help="CVs waiting in the inbox and the state of each import")
    a = resume_sub.add_parser("diff", help="compare an import's extracted.yaml with the knowledge base")
    a.add_argument("import_id", nargs="?", help="import folder name or fragment (default: latest)")
    a.add_argument("--json", action="store_true")
    a = resume_sub.add_parser("resolve", help="mark a diff item covered (captured in other words) or dismissed")
    a.add_argument("import_id")
    a.add_argument("key", help="item key from the diff, e.g. pos2.b3 or skill:tableau")
    a.add_argument("--as", dest="how", required=True, choices=["covered", "dismissed"])
    a.add_argument("--ref", dest="kb_ref", help="knowledge-base id that now holds it, e.g. T005")
    a.add_argument("--note")
    s.set_defaults(func=cmd_resume)

    sub.add_parser("doctor", help="check Python, LaTeX and the profile").set_defaults(func=cmd_doctor)
    sub.add_parser("init", help="create what is missing in the active person's folder").set_defaults(func=cmd_init)
    s = sub.add_parser("status", help="what the knowledge base knows and what is missing")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)
    sub.add_parser("validate", help="check profile/ files for format errors and broken references").set_defaults(func=cmd_validate)
    s = sub.add_parser("search", help="find evidence in the knowledge base")
    s.add_argument("terms", nargs="+", help="one or more terms; quote multi-word phrases")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)
    s = sub.add_parser("trail", help="create a new strategic trail file")
    s.add_argument("action", choices=["new"])
    s.add_argument("title")
    s.add_argument("--link", nargs="*", help="timeline ids this story belongs to, e.g. P01")
    s.set_defaults(func=cmd_trail)
    s = sub.add_parser("next-id", help="next free id for a timeline item or trail")
    s.add_argument("kind", choices=["trail", *kbmod.ID_KINDS])
    s.set_defaults(func=cmd_next_id)
    s = sub.add_parser("master", help="export the master resume (everything) to profile/master-resume.md")
    s.add_argument("--out")
    s.set_defaults(func=cmd_master)

    s = sub.add_parser("app", help="application folders and the tracker: what was sent where, and the replies")
    app_sub = s.add_subparsers(dest="app_cmd", required=True)
    a = app_sub.add_parser("new", help="create applications/<date>_<company>_<role>/ and its tracker entry")
    a.add_argument("company")
    a.add_argument("role")
    a.add_argument("--date", help="YYYY-MM-DD (default today)")
    a.add_argument("--link", help=_FIELD_HELP["link"])
    a.add_argument("--source", help=_FIELD_HELP["source"])
    a.add_argument("--salary", help=_FIELD_HELP["salary"])
    a.add_argument("--location")
    a.add_argument("--work-mode", choices=apps.WORK_MODES)
    a.add_argument("--deadline", help="YYYY-MM-DD")
    a = app_sub.add_parser("path", help="print the folder of an application")
    a.add_argument("ref", nargs="?")
    a = app_sub.add_parser("list", help="every listing: status, company, position, salary, sent, reply, link")
    a.add_argument("--open", action="store_true", help="only the ones still in progress")
    a.add_argument("--json", action="store_true")
    a = app_sub.add_parser("show", help="one application: its details, the CVs sent and the history")
    a.add_argument("ref", nargs="?")
    a.add_argument("--json", action="store_true")
    a = app_sub.add_parser("set", help="set tracker details: salary, link, contact, next step ... ('' clears one)")
    a.add_argument("ref")
    for field in apps.EDITABLE:
        a.add_argument("--" + field.replace("_", "-"), dest=field, help=_FIELD_HELP.get(field))
    a = app_sub.add_parser("status", help="record what happened (screening, interview, rejected, offer ...)")
    a.add_argument("ref")
    a.add_argument("status", choices=apps.STATUSES)
    a.add_argument("--note")
    a.add_argument("--date", help="YYYY-MM-DD it happened (default today)")
    a = app_sub.add_parser("sent", help="mark it sent and keep a copy of the CV that went out (sent/<date>/)")
    a.add_argument("ref")
    a.add_argument("--via", help="company site, LinkedIn Easy Apply, email to ..., referral")
    a.add_argument("--file", help="the CV file that was sent, when it isn't this folder's latest build")
    a.add_argument("--date", help="YYYY-MM-DD (default today)")
    a.add_argument("--note")
    app_sub.add_parser("stats", help="reply rates by layout, headline, where found and how sent")
    s.set_defaults(func=cmd_app)
    s = sub.add_parser("tracker", help="the application tracker as a page in your browser (this computer only)")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true", help="only print the address")
    s.set_defaults(func=cmd_tracker)

    s = sub.add_parser("templates", help="list CV layouts")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_templates)
    for name, func, text in (("render", cmd_render, "cv.yaml -> cv/main.tex"),
                             ("build", cmd_build, "render + compile + lint + ATS read + named PDF")):
        s = sub.add_parser(name, help=text)
        s.add_argument("ref", nargs="?", help="application (folder name, prefix or company); default latest")
        s.add_argument("--template", help="layout id (see: uv run cv templates)")
        s.add_argument("--force", action="store_true", help="overwrite hand-edited generated files")
        if name == "build":
            s.add_argument("--engine", choices=latex.ENGINES)
        s.set_defaults(func=func)
    s = sub.add_parser("compile", help="compile cv/main.tex")
    s.add_argument("ref", nargs="?")
    s.add_argument("--engine", choices=latex.ENGINES)
    s.set_defaults(func=cmd_compile)
    for name, func, text in (("lint", cmd_lint, "check the CV against the writing rules"),
                             ("coverage", cmd_coverage, "job-ad keywords vs knowledge base and CV"),
                             ("ats", cmd_ats, "extract the PDF text like an ATS and look for problems"),
                             ("zip", cmd_zip, "zip cv/ for Overleaf")):
        s = sub.add_parser(name, help=text)
        s.add_argument("ref", nargs="?")
        if name in ("lint", "coverage"):
            s.add_argument("--json", action="store_true")
        s.set_defaults(func=func)
    s = sub.add_parser("classify", help="technical vs non-technical signals in a job ad (a hint for the classifier)")
    s.add_argument("ref", nargs="?")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_classify)
    s = sub.add_parser("round", help="the write-judge loop: save a round, list rounds with the next step")
    round_sub = s.add_subparsers(dest="round_cmd", required=True)
    a = round_sub.add_parser("save", help="snapshot cv.yaml, the PDF and build facts into judging/round-N/")
    a.add_argument("ref", nargs="?")
    a = round_sub.add_parser("list", help="scores per round, verdicts checked against the rubric, what's next")
    a.add_argument("ref", nargs="?")
    a.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_round)
    sub.add_parser("engines", help="show the LaTeX engines found").set_defaults(func=cmd_engines)
    s = sub.add_parser("selftest", help="render and compile the demo CV with every layout")
    s.add_argument("--templates", nargs="*")
    s.add_argument("--no-compile", action="store_true")
    s.add_argument("--quick", action="store_true", help="English variant only")
    s.add_argument("--keep", action="store_true", help="keep the output folder")
    s.set_defaults(func=cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass  # not a reconfigurable text stream (e.g. captured in tests)
    args = build_parser().parse_args(argv)
    try:
        if args.person:
            _select_person(args.person)
        return int(args.func(args) or 0)
    except (LookupError, ValueError, yamlio.YamlError, rendermod.RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
