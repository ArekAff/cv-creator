"""The classify → write → judge loop: classification hint, rounds, verdicts, loop advice, track-aware lint."""
from __future__ import annotations

import os
import shutil

import pytest

from cvtool import checks, cli, cvdoc, lint, paths, tailoring, yamlio
from cvtool.kb import KnowledgeBase

DEMO = paths.EXAMPLES_DIR / "demo"
DEMO_APP = next((DEMO / "applications").glob("*/cv.yaml")).parent


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(DEMO))
    return KnowledgeBase.load()


@pytest.fixture
def no_profile(tmp_path, monkeypatch):
    """No profile selected and an empty people folder. Commands given a folder path set CV_DATA_DIR
    themselves; registering it with monkeypatch first makes sure that is undone after the test."""
    for var in ("CV_DATA_DIR", "CV_PERSON"):
        monkeypatch.setenv(var, "")
        monkeypatch.delenv(var)
    monkeypatch.setenv("CV_PEOPLE_DIR", str(tmp_path / "people"))


@pytest.fixture
def app(tmp_path, demo):
    """A copy of the demo application, freshly built (its PDF is newer than cv.yaml), with no rounds."""
    folder = tmp_path / DEMO_APP.name
    shutil.copytree(DEMO_APP, folder)
    shutil.rmtree(folder / "judging", ignore_errors=True)
    stamp = (folder / "cv.yaml").stat().st_mtime + 5
    os.utime(folder / "cv" / "main.pdf", (stamp, stamp))
    return folder


def judge(verdict: str = "revise", findings: tuple = (), blockers: tuple = (), **scores: int) -> dict:
    """A judge.yaml; the default scores add up to 90 with every criterion above 60%."""
    values = {"relevance": 18, "keywords": 18, "evidence": 18, "summary": 9, "skills": 9, "format": 9,
              "language": 9, **scores}
    return {"verdict": verdict, "total": sum(values.values()),
            "scores": {k: {"score": v, "max": tailoring.CRITERIA[k]} for k, v in values.items()},
            "blockers": list(blockers), "findings": list(findings)}


def finding(severity: str = "should", needs_input: bool = False) -> dict:
    return {"id": "F1", "severity": severity, "rule": "C-7", "where": "experience[0].bullets[0]",
            "problem": "no outcome", "fix": "add the outcome from T002", "needs_input": needs_input}


def rounds_of(*judges: dict | None) -> list[dict]:
    return [{"round": n, "folder": None, "build": {}, "judge": j, "rules": tailoring.evaluate(j) if j else None}
            for n, j in enumerate(judges, start=1)]


# ----------------------------------------------------------------- classification hint
def test_classify_hint_on_the_demo_listing():
    hint = tailoring.classify_signals(DEMO_APP)
    assert (hint["suggested"], hint["confidence"], hint["title_signal"]) == ("technical", "high", "technical")
    assert {"sql", "dbt", "power bi"} <= set(hint["technical_terms"])


def test_classify_hint_on_a_sales_listing(tmp_path):
    (tmp_path / "posting.md").write_text(
        "# Account Executive — Northwind\n\n## Original posting\n\n"
        "Own a territory of mid-market clients and bring in new logos. You run the full sales cycle, from "
        "prospecting and cold calling to negotiation and closing, and you exceed a quarterly quota.\n"
        "Requirements: 3+ years in B2B sales, revenue targets met, account management, Salesforce.\n",
        encoding="utf-8")
    hint = tailoring.classify_signals(tmp_path)
    assert (hint["suggested"], hint["title"], hint["title_signal"]) == (
        "non-technical", "Account Executive", "non-technical")
    assert {"quota", "prospecting", "territory"} <= set(hint["non_technical_terms"])
    assert hint["technical_score"] < hint["non_technical_score"]


def test_a_folder_path_pins_its_owner(tmp_path, no_profile, capsys):
    person = tmp_path / "copy-of-demo"
    shutil.copytree(DEMO, person)
    app = person / "applications" / DEMO_APP.name
    with pytest.raises(paths.NoProfileError):
        paths.data_dir()  # nobody is selected...
    assert cli.main(["classify", str(app)]) == 0
    assert "suggests TECHNICAL" in capsys.readouterr().out
    assert paths.data_dir() == person.resolve()  # ...but the application's owner is used
    assert cli.main(["--person", str(person), "profile", "current"]) == 0
    assert "Aleksandra Nowak" in capsys.readouterr().out
    assert cli.main(["--person", str(tmp_path / "nowhere"), "profile", "current"]) == 1
    assert "not a person's folder" in capsys.readouterr().err


# ----------------------------------------------------------------- rounds
def test_round_save_numbers_and_refreshes(app, capsys):
    assert tailoring.advice(tailoring.load_rounds(app))["action"] == "write"
    number, folder = tailoring.save_round(app)
    assert (number, folder.name) == (1, "round-1")
    assert {"cv.yaml", "cv.pdf", "build.yaml"} <= {p.name for p in folder.iterdir()}
    build = yamlio.load(folder / "build.yaml")
    assert build["track"] == "technical" and build["pages"] == 1 and build["lint"]["error"] == 0
    assert cli.main(["round", "list", str(app)]) == 0
    out = capsys.readouterr().out
    assert "(not judged yet)" in out and "next: cv-judge round 1" in out
    assert tailoring.save_round(app)[0] == 1  # not judged yet: the same round is refreshed
    yamlio.dump(judge(evidence=10, findings=(finding("must"),)), folder / "judge.yaml")
    assert tailoring.save_round(app)[0] == 2
    later = (app / "cv" / "main.pdf").stat().st_mtime + 5
    os.utime(app / "cv.yaml", (later, later))  # cv.yaml edited after the last build
    with pytest.raises(LookupError, match="uv run cv build"):
        tailoring.save_round(app)


# ----------------------------------------------------------------- verdicts and loop policy
@pytest.mark.parametrize("data, verdict", [
    (judge("pass"), "pass"),
    (judge("pass", findings=(finding("should"),)), "pass"),  # a should costs points, it doesn't block
    (judge(findings=(finding("must"),)), "revise"),  # a fixable must blocks the pass
    (judge(skills=5), "revise"),  # 86 in total, but skills is under 60%
    (judge(blockers=("'led' where the trail says 'helped'",)), "revise"),
    (judge("needs-input", evidence=12, findings=(finding(needs_input=True),)), "needs-input"),
    (judge(evidence=12, findings=(finding(needs_input=True), finding())), "revise"),
])
def test_verdict_follows_the_rubric(data, verdict):
    assert tailoring.evaluate(data)["verdict"] == verdict


def test_invalid_or_disagreeing_judge_files_are_caught():
    data = judge("pass")
    data["total"] = 95
    result = tailoring.evaluate(data)
    assert result["verdict"] == "invalid" and "the scores add up to 90" in result["problems"][0]
    del data["scores"]["format"]
    assert "no score for format" in tailoring.evaluate(data)["problems"]
    assert not tailoring.evaluate(judge("revise"))["agrees"]  # the judge said revise, the rubric says pass
    table = tailoring.format_rounds(rounds_of(judge("pass", evidence=10), None))
    assert "pass/revise !" in table and "(not judged yet)" in table


def test_loop_advice():
    low = judge(evidence=10, findings=(finding("must"),))  # 80
    better = judge(evidence=14, findings=(finding("must"),))  # 84
    assert tailoring.advice([], classified=False)["action"] == "classify"
    assert tailoring.advice([])["action"] == "write"
    assert tailoring.advice(rounds_of(None))["action"] == "judge"
    assert tailoring.advice(rounds_of(low))["action"] == "revise"
    assert tailoring.advice(rounds_of(low, better))["round"] == 3  # +4: keep going
    done = tailoring.advice(rounds_of(low, judge("pass")))
    assert (done["action"], done["reason"]) == ("stop", "pass")
    flat = tailoring.advice(rounds_of(better, judge(evidence=13, findings=(finding("must"),))))  # 84 -> 83
    assert (flat["action"], flat["reason"]) == ("stop", "plateau")
    assert "restore judging/round-1/cv.yaml" in flat["text"]
    # a pass with fixable should findings left gets another round while the score keeps rising
    passing = judge("pass", relevance=15, findings=(finding(),))  # 87
    assert tailoring.advice(rounds_of(passing))["action"] == "revise"
    assert tailoring.advice(rounds_of(low, passing))["action"] == "revise"  # +7
    polished = tailoring.advice(rounds_of(passing, judge("pass", relevance=16, findings=(finding(),))))  # +1
    assert (polished["action"], polished["reason"]) == ("stop", "pass") and "restore" not in polished["text"]
    # a polish round that breaks something: keep the passing round, even though the broken one scores higher
    broken = tailoring.advice(rounds_of(passing, judge(relevance=16, blockers=("'led' for 'helped'",))))
    assert broken["reason"] == "plateau" and "keep round 1 (pass, 87/100)" in broken["text"]
    climbing = [judge(evidence=e, findings=(finding("must"),)) for e in (2, 6, 10, 14)]
    assert tailoring.advice(rounds_of(*climbing))["reason"] == "max-rounds"
    ask = tailoring.advice(rounds_of(judge("needs-input", evidence=12, findings=(finding(needs_input=True),))))
    assert ask["action"] == "ask"


def test_keywords_count_only_when_their_words_are_together():
    assert checks.contains("Advanced SQL (window functions) every week", "SQL window functions")
    assert checks.contains("demand forecasting in Python for the buyers", "Python forecasting")
    assert checks.contains("Built a demand forecast", "forecasting")  # one word: inflected forms count
    scattered = ("Senior management asked for a new report. We rebuilt it in two weeks with the regional "
                 "teams and the data warehouse owners, and the analyst on call")
    assert not checks.contains(scattered, "Senior Data Analyst")


# ----------------------------------------------------------------- track-aware lint
def test_lint_applies_the_technical_playbook(app, demo):
    raw = cvdoc.load(app / "cv.yaml")
    raw["header"]["headline"] = "Data Analyst"
    raw["summary"] = "Data analyst who builds demand forecasts and Power BI reports for operations teams."
    raw["skills"].append({"category": "Other", "items": ["Stakeholder management", "Team player"]})
    yamlio.dump(raw, app / "cv.yaml")
    found = {(f.where, f.message.split(":")[0]) for f in lint.lint(app, kb=demo)}
    assert ("header", "C-3") in found  # 'Senior Data Analyst' is in neither headline nor summary
    assert ("skills: Stakeholder management", "T-3/T-12") in found
    assert ("skills: Team player", "C-9/N-11") in found
    raw["header"]["headline"] = "Senior Data Analyst · Forecasting, Power BI and dbt"
    yamlio.dump(raw, app / "cv.yaml")
    assert not any(f.message.startswith("C-3") for f in lint.lint(app, kb=demo))


def test_lint_applies_the_non_technical_playbook(app, demo):
    classification = yamlio.load(app / "classification.yaml")
    yamlio.dump({**classification, "track": "non-technical", "family": "sales"}, app / "classification.yaml")
    raw = cvdoc.load(app / "cv.yaml")
    raw["meta"]["template"] = "altacv"
    raw["skills"] = [{"category": "Skills", "items": ["Negotiation", "SQL"]}]
    for section in ("experience", "volunteering", "projects"):
        for entry in raw.get(section) or []:
            entry["bullets"] = [{"text": "Ran the weekly regional report for six managers", "source": ["T001"]}]
    yamlio.dump(raw, app / "cv.yaml")
    found = {(f.where, f.message.split(":")[0]) for f in lint.lint(app, kb=demo)}
    assert ("skills: Negotiation", "N-5") in found  # no bullet shows any negotiating
    assert ("layout", "N-13/C-12") in found  # two columns, but an ATS reads it first
    assert ("bullets", "N-2") in found  # sales without quota, rank or pipeline
    assert not any(rule.startswith("T-") for _, rule in found)
