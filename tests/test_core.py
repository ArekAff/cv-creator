"""Fast tests (no LaTeX needed). Full compile checks: uv run cv selftest"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cvtool import apps, checks, cvdoc, dates, lint, paths, render, texutil, yamlio
from cvtool.kb import KnowledgeBase, token_match

DEMO = paths.EXAMPLES_DIR / "demo"
DEMO_APP = next((DEMO / "applications").glob("*/cv.yaml")).parent


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(DEMO))
    return KnowledgeBase.load()


# ----------------------------------------------------------------- texutil
@pytest.mark.parametrize("raw, expected", [
    ("R&D 100%", r"R\&D 100\%"),
    ("snake_case #1 $5", r"snake\_case \#1 \$5"),
    ("{x}", r"\{x\}"),
    ('say "hi"', "say ``hi''"),
    ("a - b", "a -- b"),
    ("6 h → 0.5 h", r"6 h $\rightarrow$ 0.5 h"),
    ("Zażółć gęślą jaźń", "Zażółć gęślą jaźń"),
])
def test_escape(raw, expected):
    assert texutil.escape(raw) == expected


def test_markup_and_url():
    out = texutil.markup("**Power BI** and *dbt*, see [repo](https://x.org/a_b?q=1&r=2#top)")
    assert r"\textbf{Power BI}" in out and r"\textit{dbt}" in out
    assert r"\href{https://x.org/a_b?q=1\&r=2\#top}{repo}" in out
    assert texutil.strip_markup("**a** [b](http://c)") == "a b"


def test_unsupported_chars():
    assert texutil.unsupported_chars("ok ąę – “x” €") == set()
    assert texutil.unsupported_chars("rocket 🚀") == {"🚀"}


# ----------------------------------------------------------------- dates
def test_dates():
    assert dates.parse("2021-03") == dates.CvDate(2021, 3)
    assert dates.parse(2021) == dates.CvDate(2021)
    assert dates.parse("03.2021") == dates.CvDate(2021, 3)
    assert dates.parse("present").present
    assert dates.fmt_range("2021-03", "present", "en") == "Mar 2021 – Present"
    assert dates.fmt_range("2021-03", "present", "pl") == "03.2021 – obecnie"
    assert dates.fmt_range("2021-03", "2022-01", "en", "long") == "March 2021 – January 2022"
    with pytest.raises(ValueError):
        dates.parse("March of 2021")


# ----------------------------------------------------------------- knowledge base
def test_demo_profile_is_valid(demo):
    assert [i for i in demo.validate() if i.level == "error"] == []
    status = demo.status()
    assert status["readiness"] == "ready"
    assert status["counts"]["trails"] == 3


def test_search_finds_evidence(demo):
    hits = demo.search(["demand forecasting"])
    assert hits and hits[0].doc.id == "T002"
    alias_hits = demo.search(["PostgreSQL"])  # alias of the SQL skill
    assert any(h.doc.id.startswith("skill:SQL") or h.doc.id == "T001" for h in alias_hits)


def test_token_match_handles_inflection():
    assert token_match("forecasting", "forecasts")
    assert token_match("zarządzanie", "zarządzałam")
    assert not token_match("data", "database")


def test_next_id_and_master(demo):
    assert demo.next_id("trail") == "T004"
    assert demo.next_id("position") == "P05"
    md = demo.master_markdown()
    assert "Aleksandra Nowak" in md and "T002" in md


# ----------------------------------------------------------------- cv.yaml and rendering
def test_build_context_escapes_and_groups(demo):
    raw = cvdoc.load(DEMO_APP / "cv.yaml")
    raw["summary"] = "Data analyst: **demand forecasting** that cut error from 31% to 19% MAPE"
    ctx = cvdoc.build(raw)
    assert ctx.cv.experience_groups[0].organization == "Lumina Retail"
    assert len(ctx.cv.experience_groups[0].roles) == 2
    assert r"\textbf{demand forecasting}" in ctx.cv.summary and r"31\% to 19\%" in ctx.cv.summary
    assert ctx.cv.skills[0]["items"]  # .items must reach the list, not dict.items
    assert ctx.meta.sections[0] == "summary"
    assert "languages" not in ctx.meta.sections  # hidden in the demo


@pytest.mark.parametrize("template_id", [t for t in render.templates() if not t.startswith("my:")])
def test_every_template_renders(tmp_path, monkeypatch, template_id):
    monkeypatch.setenv("CV_DATA_DIR", str(DEMO))
    app = tmp_path / "app"
    app.mkdir()
    raw = cvdoc.load(DEMO_APP / "cv.yaml")
    raw["meta"]["template"] = template_id
    raw["meta"].pop("hide", None)
    yamlio.dump(raw, app / "cv.yaml")
    result = render.render(app)
    main = (result.out_dir / "main.tex").read_text(encoding="utf-8")
    assert "Aleksandra" in main and "\\begin{document}" in main and "<<" not in main
    assert main.count(render.REAL_SPACES) == 1  # real spaces in the PDF text, for ATS parsers


def test_real_spaces_go_right_after_documentclass():
    tex = "% \\documentclass{old}\n\\documentclass[a4paper,\n  11pt]{article} % note\n\\begin{document}\n"
    out = render.with_real_spaces(tex)
    assert out.splitlines()[3] == render.REAL_SPACES and out.splitlines()[4] == "\\begin{document}"
    assert render.with_real_spaces(out) == out  # never twice
    assert render.with_real_spaces("no class here") == "no class here"


def test_glued_words_in_the_pdf_text_are_flagged():
    raw = {"header": {"name": "Aleksandra Nowak"},
           "experience": [{"title": "Data Analyst", "organization": "Lumina Retail"}]}
    assert checks.glued_words(raw, "Aleksandra Nowak\nData Analyst Jul 2023 – Present\nLumina Retail Kraków") == []
    glued = checks.glued_words(raw, "AleksandraNowak\nData AnalystJul 2023 – Present\n"
                                    "•Builtagradient-boostingdemandforecastforthesummergardenrange in Python")
    assert glued[0] == "Data AnalystJul 2023" and "AleksandraNowak" in glued
    assert any(g.startswith("•Builtagradient") for g in glued)


def test_hand_edits_are_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(DEMO))
    app = tmp_path / "app"
    shutil.copytree(DEMO_APP, app, ignore=shutil.ignore_patterns("cv", "*.pdf"))
    render.render(app)
    main = app / "cv" / "main.tex"
    main.write_text(main.read_text(encoding="utf-8") + "% my edit\n", encoding="utf-8")
    with pytest.raises(render.RenderError, match="edited by hand"):
        render.render(app)
    render.render(app, force=True)


# ----------------------------------------------------------------- lint, coverage, apps
def test_demo_cv_lints_clean(demo):
    findings = lint.lint(DEMO_APP, kb=demo)
    assert [f for f in findings if f.level == "error"] == []


def test_lint_catches_untraceable_and_split_items(tmp_path, demo):
    raw = cvdoc.load(DEMO_APP / "cv.yaml")
    raw["experience"][0]["bullets"].append({"text": "Responsible for everything", "source": ["T999"]})
    raw["skills"].append({"category": "Oops", "items": ["SQL (window functions", "modelling)"]})
    yamlio.dump(raw, tmp_path / "cv.yaml")
    messages = [f.message for f in lint.lint(tmp_path, kb=demo)]
    assert any("T999 does not exist" in m for m in messages)
    assert any("weak opener" in m for m in messages)
    assert any("unbalanced parentheses" in m for m in messages)


def test_coverage_report(demo):
    report = checks.coverage(DEMO_APP, kb=demo)
    forecasting = next(r for r in report["requirements"] if r["id"] == "R03")
    assert any(e.startswith("T002") for e in forecasting["kb_evidence"])
    assert forecasting["in_cv"]


def test_slugify_and_app_folders(tmp_path, monkeypatch):
    assert apps.slugify("Łódź Zakłady Sp. z o.o.") == "lodz-zaklady-sp-z-o-o"
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path))
    folder = apps.create("Ąćme Polska", "Analityk Danych", "2026-11-02")
    assert folder.name == "2026-11-02_acme-polska_analityk-danych"
    assert (folder / "posting.md").exists()
    assert apps.resolve("acme") == folder
    apps.set_status(folder.name, "sent")
    assert apps.load_tracker()[0]["status"] == "sent"
