"""The application tracker: listing details, the CVs that went out, replies, and the local page."""
from __future__ import annotations

import datetime as dt
import http.client
import json
import threading

import pytest

from cvtool import apps, cli, kb as kbmod, paths, tracker, yamlio


@pytest.fixture
def person(tmp_path, monkeypatch):
    """A fresh person folder with an empty profile."""
    monkeypatch.setenv("CV_DATA_DIR", str(tmp_path / "person"))
    kbmod.init_profile(person_name="Test Person")
    paths.applications_dir().mkdir(parents=True)
    return tmp_path / "person"


def _built(folder, content=b"%PDF-1.4 first"):
    """What `uv run cv build` leaves behind: the named PDF, cv.yaml and the tracker's build fields."""
    (folder / "Test_CV_Acme_2026-11-01.pdf").write_bytes(content)
    yamlio.dump({"header": {"name": "Test Person"}}, folder / "cv.yaml")
    apps.update(folder, cv_pdf="Test_CV_Acme_2026-11-01.pdf", template="jakes", headline="Data Analyst")


# ----------------------------------------------------------------- tracker.yaml
def test_a_listing_keeps_its_details(person):
    folder = apps.create("Acme", "Data Analyst", "2026-11-01", source="https://jobs.example.com/acme/123",
                         salary="16 000–21 000 PLN gross/month", location="Kraków", work_mode="Hybrid",
                         deadline="2026-11-20")
    entry = apps.get(folder)
    assert entry["link"] == "https://jobs.example.com/acme/123" and "source" not in entry  # a URL is the link
    assert entry["salary"] == "16 000–21 000 PLN gross/month" and entry["work_mode"] == "hybrid"
    posting = (folder / "posting.md").read_text(encoding="utf-8")
    assert "- Salary: 16 000–21 000 PLN gross/month" in posting and "Kraków · hybrid" in posting
    apps.create("Acme", "Data Analyst", "2026-11-01", source="LinkedIn", salary="something else")
    entry = apps.get(folder)
    assert entry["source"] == "LinkedIn" and entry["salary"] == "16 000–21 000 PLN gross/month"  # fills gaps only
    assert len(apps.load_tracker()) == 1
    text = apps.tracker_path().read_text(encoding="utf-8")
    assert text.index("salary:") < text.index("created:") < text.index("history:")


def test_edits_are_checked(person):
    folder = apps.create("Acme", "Data Analyst", "2026-11-01")
    apps.edit(folder, link="www.example.com/job", expected_salary="20 000 PLN", follow_up="2026-11-15")
    entry = apps.get(folder)
    assert entry["link"] == "https://www.example.com/job" and entry["follow_up"] == "2026-11-15"
    apps.edit(folder, expected_salary="")
    assert "expected_salary" not in apps.get(folder)
    for bad in ({"follow_up": "next week"}, {"link": "see the email"}, {"work_mode": "sometimes"}, {"company": ""},
                {"status": "sent"}):
        with pytest.raises(ValueError):
            apps.edit(folder, **bad)


def test_sending_keeps_the_cv_that_went_out(person):
    folder = apps.create("Acme", "Data Analyst", "2026-11-01")
    _built(folder)
    entry = apps.record_sent(folder, date="2026-11-02", via="company site")
    assert (entry["status"], entry["sent"], entry["sent_via"]) == ("sent", "2026-11-02", "company site")
    first = entry["sent_cvs"][0]
    assert first == {"date": "2026-11-02", "file": "sent/2026-11-02/Test_CV_Acme_2026-11-01.pdf",
                     "cv_yaml": "sent/2026-11-02/cv.yaml", "template": "jakes", "headline": "Data Analyst",
                     "via": "company site"}
    assert apps.record_sent(folder, date="2026-11-02", via="company site")["sent_cvs"] == [first]  # no duplicate
    _built(folder, b"%PDF-1.4 rebuilt")  # a later build replaces the PDF in the folder ...
    assert (folder / first["file"]).read_bytes() == b"%PDF-1.4 first"  # ... not the copy that went out
    second = apps.record_sent(folder, date="2026-11-02", via="email")["sent_cvs"][1]
    assert second["file"] == "sent/2026-11-02/Test_CV_Acme_2026-11-01-2.pdf"
    apps.set_status(folder, "interview", "Thu 10:00", date="2026-11-06")
    entry = apps.record_sent(folder, date="2026-11-07", via="email to the hiring manager")
    assert entry["status"] == "interview" and entry["sent"] == "2026-11-02"  # sending again keeps the stage


def test_a_cv_made_elsewhere_or_none(person, tmp_path):
    folder = apps.create("Beta", "Analyst", "2026-11-01")
    cv = tmp_path / "My CV.pdf"
    cv.write_bytes(b"%PDF other")
    entry = apps.record_sent(folder, file=cv, date="2026-11-03")
    assert entry["sent_cvs"] == [{"date": "2026-11-03", "file": "sent/2026-11-03/My CV.pdf"}]
    with pytest.raises(LookupError):
        apps.record_sent(folder, file=tmp_path / "missing.pdf")
    other = apps.create("Gamma", "Analyst", "2026-11-01")
    entry = apps.set_status(other, "sent", date="2026-11-01")  # no CV built here: the send is still recorded
    assert entry["sent_cvs"] == [{"date": "2026-11-01"}] and "no CV file" in entry["history"][-1]["note"]


def test_reply_states():
    today = dt.date(2026, 11, 10)
    sent = {"sent": "2026-11-01", "history": [{"date": "2026-11-01", "status": "sent"}]}
    assert apps.reply_info({"status": "ready"}, today)["state"] == "not sent"
    assert apps.reply_info({"status": "sent", **sent}, today) == {"state": "waiting", "date": "", "days": 9}
    rejected = {"status": "rejected", "sent": "2026-11-01", "history": [
        {"date": "2026-11-01", "status": "sent"}, {"date": "2026-11-04", "status": "screening"},
        {"date": "2026-11-09", "status": "rejected"}]}
    assert apps.reply_info(rejected, today) == {"state": "replied", "date": "2026-11-04", "days": 3}
    assert apps.reply_info({"status": "no-response", **sent}, today)["state"] == "no reply"
    assert apps.reply_info({"status": "sent", "sent": dt.date(2026, 11, 1)}, today)["days"] == 9  # unquoted date
    assert apps.row({"status": "sent", "follow_up": "2026-11-10", **sent}, today)["follow_up_due"]
    assert not apps.row({"status": "rejected", "follow_up": "2026-11-10", **sent}, today)["follow_up_due"]


def test_list_and_stats(person):
    acme = apps.create("Acme", "Data Analyst", "2026-11-01", salary="16k PLN", link="https://jobs.example.com/1",
                       source="LinkedIn")
    beta = apps.create("Beta", "BI Developer", "2026-11-02", source="referral")
    apps.set_status(acme, "sent", date="2026-11-02")
    apps.set_status(acme, "screening", date="2026-11-05")
    apps.set_status(beta, "sent", date="2026-11-03")
    table = apps.format_list(apps.load_tracker(), dt.date(2026, 11, 10)).splitlines()
    assert table[1].startswith("sent") and "Beta" in table[1]  # newest first
    acme_row = next(line for line in table if "Acme" in line)
    assert "16k PLN" in acme_row and "yes, 2026-11-05" in acme_row and acme_row.endswith("https://jobs.example.com/1")
    assert "waiting 7 d" in table[1]
    report = apps.stats()
    assert "Any reply: 1/2 (50%)" in report and "Days to first reply: median 3" in report
    assert "LinkedIn: 1/1 replied" in report and "referral: 0/1 replied" in report


def test_app_commands(person, tmp_path, capsys):
    assert cli.main(["app", "new", "Acme", "Data Analyst", "--date", "2026-11-01", "--link",
                     "https://jobs.example.com/1", "--salary", "16 000 PLN", "--work-mode", "remote"]) == 0
    assert cli.main(["app", "set", "acme", "--contact", "Anna (recruiter)", "--next-step", "call on Thursday"]) == 0
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(b"%PDF")
    assert cli.main(["app", "sent", "acme", "--file", str(cv), "--via", "email"]) == 0
    capsys.readouterr()
    assert cli.main(["app", "show", "acme", "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["contact"] == "Anna (recruiter)" and shown["reply"]["state"] == "waiting"
    assert shown["sent_cvs"][0]["via"] == "email" and shown["label"] == "sent, waiting"
    assert cli.main(["app", "set", "acme", "--deadline", "soon"]) == 1
    assert cli.main(["app", "list"]) == 0
    assert "16 000 PLN" in capsys.readouterr().out
    assert cli.main(["status"]) == 0
    assert "Applications: 1 tracked, 1 open, 1 waiting for a reply" in capsys.readouterr().out


# ----------------------------------------------------------------- the local page
@pytest.fixture
def server(person):
    srv = tracker.TrackerServer(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _call(srv, method, path, body=None, token=True, host=None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}", "Content-Type": "application/json"}
    if token:
        headers["X-Tracker-Token"] = srv.token
    conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
    res = conn.getresponse()
    raw = res.read()
    conn.close()
    return res.status, json.loads(raw) if res.getheader("Content-Type", "").startswith("application/json") else raw


def test_tracker_page(server, person):
    status, page = _call(server, "GET", "/")
    assert status == 200 and server.token.encode() in page and b"__TOKEN__" not in page
    status, state = _call(server, "GET", "/api/state")
    assert status == 200 and state["applications"] == [] and state["name"] == "Test Person"
    status, state = _call(server, "POST", "/api/app", {"company": "Acme", "role": "Data Analyst", "salary": "16k",
                                                       "link": "https://jobs.example.com/1"})
    assert status == 200 and state["applications"][0]["salary"] == "16k"
    app_id = state["added"]
    assert (person / "applications" / app_id / "posting.md").exists()
    status, state = _call(server, "POST", f"/api/app/{app_id}", {"status": "interview", "note": "Thu 10:00",
                                                                 "next_step": "prepare the case study"})
    entry = state["applications"][0]
    assert status == 200 and entry["status"] == "interview" and entry["next_step"] == "prepare the case study"
    assert entry["history"][-1] == {"date": dt.date.today().isoformat(), "status": "interview", "note": "Thu 10:00"}
    (person / "applications" / app_id / "x.pdf").write_bytes(b"%PDF-1.4")
    assert _call(server, "GET", f"/file?app={app_id}&path=x.pdf") == (200, b"%PDF-1.4")


def test_tracker_page_refuses(server, person):
    app_id = apps.create("Acme", "Data Analyst", "2026-11-01").name
    assert _call(server, "POST", f"/api/app/{app_id}", {"link": "not a link"})[0] == 400
    assert _call(server, "POST", f"/api/app/{app_id}", {"status": "hired"})[0] == 400
    assert _call(server, "POST", f"/api/app/{app_id}", {"history": []})[0] == 400
    assert _call(server, "POST", "/api/app", {"company": "No role"})[0] == 400
    assert _call(server, "POST", "/api/app/..%2F..%2Fprofile", {"notes": "x"})[0] == 404
    assert _call(server, "POST", f"/api/app/{app_id}", {"notes": "x"}, token=False)[0] == 403
    assert _call(server, "GET", "/api/state", host="tracker.example.com")[0] == 400
    assert _call(server, "GET", f"/file?app={app_id}&path=../../profile/profile.yaml")[0] == 404
    assert _call(server, "GET", f"/file?app={app_id}&path=posting.md")[0] == 404
    assert "notes" not in apps.get(person / "applications" / app_id)
