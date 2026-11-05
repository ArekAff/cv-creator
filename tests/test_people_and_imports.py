"""Profiles for several people, and importing an existing CV (extraction + diff against the knowledge base)."""
from __future__ import annotations

import shutil
import zipfile

import pytest

from cvtool import cli, cvdoc, kb as kbmod, paths, resume, yamlio
from cvtool.kb import KnowledgeBase

DEMO = paths.EXAMPLES_DIR / "demo"
DEMO_APP = next((DEMO / "applications").glob("*/cv.yaml")).parent
DEMO_IMPORT = DEMO / "profile" / "imports" / "2026-10-30-cv-2023"


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("CV_DATA_DIR", str(DEMO))
    return KnowledgeBase.load()


@pytest.fixture
def person(tmp_path, monkeypatch):
    """A fresh, empty person folder."""
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path / "person"))
    kbmod.init_profile()
    paths.inbox_dir().mkdir(parents=True)
    return tmp_path / "person"


# ----------------------------------------------------------------- profiles
def test_profiles_keep_people_apart(tmp_path, monkeypatch):
    for var in ("CV_DATA_DIR", "CV_PERSON"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CV_PEOPLE_DIR", str(tmp_path))
    with pytest.raises(paths.NoProfileError, match="no profile yet"):
        paths.data_dir()
    assert cli.main(["profile", "add", "Alex Example"]) == 0
    assert cli.main(["profile", "add", "Sam", "--id", "sam"]) == 0
    assert paths.active_person() == "sam"  # the newest profile becomes active
    sam = tmp_path / "sam"
    assert (sam / "inbox").is_dir() and (sam / "applications").is_dir() and (sam / "profile" / "imports").is_dir()
    assert 'name: "Sam"' in (sam / "profile" / "profile.yaml").read_text(encoding="utf-8")
    assert cli.main(["profile", "use", "alex"]) == 0  # prefix of alex-example
    assert paths.active_person() == "alex-example"
    monkeypatch.setenv("CV_PERSON", "sam")  # what --person sets, for one command
    assert paths.data_dir().resolve() == sam.resolve()
    monkeypatch.delenv("CV_PERSON")
    (tmp_path / ".active").unlink()
    with pytest.raises(paths.NoProfileError, match="several profiles"):
        paths.data_dir()


def test_people_folder_location(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_PEOPLE_DIR", raising=False)
    settings = tmp_path / "cv.local.yaml"
    monkeypatch.setattr(paths, "LOCAL_SETTINGS", settings)
    assert paths.people_dir() == paths.ROOT / "people" and paths.people_dir_source() == "default"
    settings.write_text(f"people_dir: {(tmp_path / 'local-people').as_posix()}\n", encoding="utf-8")
    assert paths.people_dir() == (tmp_path / "local-people").resolve()
    assert paths.people_dir_source() == "cv.local.yaml"
    monkeypatch.setenv("CV_PEOPLE_DIR", str(tmp_path / "env-people"))  # the variable wins
    assert paths.people_dir() == (tmp_path / "env-people").resolve()
    assert paths.people_dir_source() == "CV_PEOPLE_DIR"
    monkeypatch.setenv("OneDrive", str(tmp_path))
    assert paths.in_cloud_folder(paths.people_dir()) == str(tmp_path)
    monkeypatch.setenv("OneDrive", str(tmp_path / "elsewhere"))
    for var in ("OneDriveConsumer", "OneDriveCommercial"):
        monkeypatch.delenv(var, raising=False)
    assert paths.in_cloud_folder(paths.people_dir()) is None


# ----------------------------------------------------------------- text extraction
def test_detex_reads_the_original_templates():
    jakes = resume.detex((paths.ORIGINALS_DIR / "Jakes_Resume.tex").read_text(encoding="utf-8"))
    assert "Jake Ryan" in jakes and "## Education" in jakes and "Texas A&M University" in jakes
    assert "- Developed a REST API using FastAPI and PostgreSQL" in jakes
    assert "\\" not in jakes
    elegant = resume.detex((paths.ORIGINALS_DIR / "Elegant_resume_template.tex").read_text(encoding="utf-8"))
    assert "name: Carl Johnson (CJ)" in elegant and "Dank Memes Inc." in elegant
    receive = resume.detex((paths.ORIGINALS_DIR / "ReCeiVe.tex").read_text(encoding="utf-8"))
    assert "email: gedlex@hotmail.ch" in receive


def test_detex_accents_and_symbols():
    source = r"\begin{document}Za\.z\'o\l{}\'c g\k{e}\'sl\k{a} ja\'z\'n -- R\&D 100\% $\cdot$ \textbf{bold}\end{document}"
    assert "Zażółć gęślą jaźń – R&D 100% · bold" in resume.detex(source)


def test_docx_text_includes_header_and_lists(tmp_path):
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    doc = tmp_path / "cv.docx"
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/header1.xml", f"<w:hdr {ns}><w:p><w:r><w:t>jane@example.com</w:t></w:r></w:p></w:hdr>")
        z.writestr("word/document.xml",
                   f"<w:document {ns}><w:body><w:p><w:r><w:t>Jane Doe</w:t></w:r></w:p>"
                   "<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Led a team of 4</w:t></w:r></w:p></w:body></w:document>")
    assert resume.docx_text(doc).splitlines() == ["jane@example.com", "", "Jane Doe", "- Led a team of 4"]


# ----------------------------------------------------------------- importing
def test_import_latex_follows_inputs(tmp_path, person):
    src = tmp_path / "mycv"
    (src / "sections").mkdir(parents=True)
    (src / "cv.tex").write_text(r"\documentclass{article}\begin{document}\section{Experience}"
                                r"\input{sections/jobs}\end{document}", encoding="utf-8")
    (src / "sections" / "jobs.tex").write_text(r"\textbf{Analyst} at Acme \\ \item Built dashboards", encoding="utf-8")
    folder = resume.import_file(src / "cv.tex")
    assert (folder / "original" / "sections" / "jobs.tex").exists()
    text = (folder / "text.md").read_text(encoding="utf-8")
    assert "## Experience" in text and "Analyst at Acme" in text and "- Built dashboards" in text
    assert (src / "cv.tex").exists()  # a file outside the inbox is copied, not moved


def test_import_from_inbox_moves_the_file(person):
    cv = paths.inbox_dir() / "old-cv.md"
    cv.write_text("# Jane Doe\n" + "Data analyst at Acme, building weekly reports. " * 12, encoding="utf-8")
    assert resume.inbox_files() == [cv]
    folder = resume.import_file(cv)
    meta = yamlio.load(folder / "import.yaml")
    assert not cv.exists() and (folder / "original.md").exists()
    assert meta["kind"] == "text" and meta["text_quality"] == "ok"
    assert resume.inbox_files() == []
    with pytest.raises(ValueError, match="not supported"):
        bad = paths.inbox_dir() / "cv.doc"
        bad.write_bytes(b"\xd0\xcf\x11\xe0")
        resume.import_file(bad)


# ----------------------------------------------------------------- diff
def test_old_cv_brings_new_information(demo):
    report = resume.diff(DEMO_IMPORT, demo, write=False)
    status = {i["key"]: i["status"] for i in report["items"]}
    claims = {c["key"]: c for i in report["items"] for c in i["claims"]}
    assert status["pos3"] == "new"  # the student job is not in the knowledge base
    assert status["pos2"] == "known"
    assert status["cert1"] == "new" and status["skill:tableau"] == "new" and status["skill:sql"] == "known"
    assert status["lang:german"] == "changed" and status["lang:english"] == "known"
    assert claims["pos1.b1"]["status"] == "known"  # the Monday report story, T001
    assert claims["pos1.b2"]["status"] != "known" and "3" in claims["pos1.b2"]["new_numbers"]
    assert claims["pos3.b1"]["status"] == "new"
    assert "resolution" in next(i for i in report["items"] if i["key"] == "pos1")
    assert report["interview_needed"]
    assert any(imp["id"] == DEMO_IMPORT.name for imp in resume.pending(demo)["imports"])


def test_a_cv_built_from_the_knowledge_base_brings_nothing_new(tmp_path, demo):
    raw = cvdoc.load(DEMO_APP / "cv.yaml")
    jobs = raw["experience"] + raw["volunteering"]
    extracted = {
        "person": {k: raw["header"][k] for k in ("name", "email", "phone", "location", "headline")},
        "summary": raw["summary"],
        "positions": [{**{k: j.get(k) for k in ("title", "organization", "location", "start", "end")},
                       "bullets": [b["text"] for b in j["bullets"]]} for j in jobs],
        "education": [{k: e.get(k) for k in ("degree", "field", "institution", "start", "end")} for e in raw["education"]],
        "certifications": raw["certifications"],
        "projects": [{"name": p["name"], "start": p["start"], "end": p["end"],
                      "bullets": [b["text"] for b in p["bullets"]]} for p in raw.get("projects") or []],
        "skills": [item for g in raw["skills"] if "language" not in g["category"].lower() for item in g["items"]],
        "languages": raw["languages"],
    }
    folder = tmp_path / "import"
    folder.mkdir()
    yamlio.dump(extracted, folder / "extracted.yaml")
    yamlio.dump({"resolutions": {}}, folder / "import.yaml")
    report = resume.diff(folder, demo, write=False)
    still_open = [i["key"] for i in report["items"] if i["status"] != "known"]
    still_open += [c["key"] for i in report["items"] for c in i["claims"] if c["status"] != "known"]
    assert still_open == []


def test_resolution_closes_an_item(tmp_path, demo):
    folder = tmp_path / "import"
    shutil.copytree(DEMO_IMPORT, folder)
    before = resume.diff(folder, demo, write=False)["open"]
    resume.record_resolution(folder, "interest:bouldering", "dismissed", note="private, not for CVs")
    after = resume.diff(folder, demo, write=False)
    assert after["open"] == before - 1
    assert next(i for i in after["items"] if i["key"] == "interest:bouldering")["resolution"]["as"] == "dismissed"
