"""The application tracker as a page in the browser: uv run cv tracker.

A small server on 127.0.0.1 only, so nothing leaves this computer: one page (tracker.html) and a
JSON API over the same applications/tracker.yaml that `uv run cv app ...` uses. Every change goes
through apps.py, so the page, the commands and Claude always agree. Changes need the token that
only the page carries, and every request must name this server as its host, so other websites
open in the same browser can't read or change the tracker.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import apps, paths, yamlio

PAGE = Path(__file__).with_name("tracker.html")
MAX_BODY = 100_000
_LOCK = threading.Lock()  # one change at a time: each is load → modify → save of tracker.yaml
_PAGE_POLICY = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; form-action 'none'; frame-ancestors 'none'; base-uri 'none'")


def people() -> list[dict]:
    """Whose trackers the page can show, the active person first: [{id, name, dir}]."""
    if os.environ.get("CV_DATA_DIR"):
        folders, first = [paths.data_dir()], None
    else:
        folders = [paths.people_dir() / i for i in paths.person_ids()]
        try:
            first = paths.active_person()
        except paths.NoProfileError:
            first = None
    found = [{"id": folder.name, "name": _name(folder), "dir": folder} for folder in folders]
    return sorted(found, key=lambda p: p["id"] != first)


def _name(folder: Path) -> str:
    try:
        data = yamlio.load(folder / "profile" / "profile.yaml", {})
    except yamlio.YamlError:
        data = {}
    person = data.get("person") if isinstance(data, dict) else None
    return str((person.get("name") if isinstance(person, dict) else None) or folder.name)


def _person(everyone: list[dict], wanted: str) -> dict:
    if not everyone:
        raise LookupError("no profiles yet: uv run cv profile add \"<your name>\"")
    for person in everyone:
        if person["id"] == wanted:
            return person
    if wanted:
        raise LookupError(f"there is no profile {wanted!r}")
    return everyone[0]


def _app_dir(person: dict, app_id: str) -> Path:
    """The folder of one of this person's tracked applications (never anything outside applications/)."""
    root = person["dir"] / "applications"
    if Path(app_id).name != app_id or app_id not in {str(e.get("id")) for e in apps.load_tracker(root)}:
        raise LookupError(f"no application {app_id!r}")
    return root / app_id


def state(person: dict, everyone: list[dict]) -> dict:
    root = person["dir"] / "applications"
    today = dt.date.today()
    return {
        "person": person["id"], "name": person["name"],
        "people": [{"id": p["id"], "name": p["name"]} for p in everyone],
        "file": str(apps.tracker_path(root)), "today": today.isoformat(),
        "statuses": [{"id": s, "label": apps.STATUS_LABELS[s]} for s in apps.STATUSES],
        "work_modes": list(apps.WORK_MODES),
        "applications": [apps.row(e, today) for e in apps.newest_first(apps.load_tracker(root))],
    }


def add(person: dict, data: dict) -> str:
    """A listing from the page's form gets its folder and tracker entry, like `uv run cv app new`."""
    unknown = set(data) - set(apps.EDITABLE)
    if unknown:
        raise ValueError("unknown field(s): " + ", ".join(sorted(unknown)))
    fields = apps.clean_fields({k: v for k, v in data.items() if v})
    company, role = fields.pop("company", ""), fields.pop("role", "")
    if not company or not role:
        raise ValueError("a listing needs the company and the position")
    source = fields.pop("source", "")
    return apps.create(company, role, source=source, root=person["dir"] / "applications", **fields).name


def change(person: dict, app_id: str, data: dict) -> None:
    """Edit fields and/or set the status (with an optional note for the history)."""
    app_dir = _app_dir(person, app_id)
    unknown = set(data) - set(apps.EDITABLE) - {"status", "note"}
    if unknown:
        raise ValueError("unknown field(s): " + ", ".join(sorted(unknown)))
    status, note = str(data.get("status") or ""), str(data.get("note") or "").strip()
    if status and status not in apps.STATUSES:
        raise ValueError(f"status must be one of: {', '.join(apps.STATUSES)}")
    fields = {k: v for k, v in data.items() if k in apps.EDITABLE}
    if fields:
        apps.edit(app_dir, **fields)
    if status and (status != apps.get(app_dir).get("status") or note):
        apps.set_status(app_dir, status, note)


def pdf_file(person: dict, query: dict) -> Path:
    """A PDF inside one of the person's application folders (a CV that was built or sent)."""
    app_dir = _app_dir(person, _one(query, "app"))
    target = (app_dir / _one(query, "path")).resolve()
    if not target.is_relative_to(app_dir.resolve()) or target.suffix.lower() != ".pdf" or not target.is_file():
        raise LookupError("no such PDF in that application")
    return target


def _one(query: dict, key: str) -> str:
    return (query.get(key) or [""])[0]


class Handler(BaseHTTPRequestHandler):
    server: TrackerServer

    def log_message(self, format: str, *args: object) -> None:  # keep the terminal quiet
        pass

    def do_GET(self) -> None:
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def _route(self, method: str) -> None:
        if (self.headers.get("Host") or "").lower() not in self.server.hosts:
            return self._json(400, {"error": "unexpected Host header"})  # e.g. DNS rebinding
        url = urlparse(self.path)
        query = parse_qs(url.query)
        try:
            if method == "GET" and url.path == "/":
                page = PAGE.read_text(encoding="utf-8").replace("__TOKEN__", self.server.token)
                return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": _PAGE_POLICY})
            if method == "POST" and self.headers.get("X-Tracker-Token") != self.server.token:
                return self._json(403, {"error": "this page is out of date: reload it"})
            body = self._body() if method == "POST" else {}
            with _LOCK:
                everyone = people()
                person = _person(everyone, _one(query, "person"))
                if method == "GET" and url.path == "/api/state":
                    return self._json(200, state(person, everyone))
                if method == "GET" and url.path == "/file":
                    pdf = pdf_file(person, query)
                    return self._send(200, pdf.read_bytes(), "application/pdf",
                                      {"Content-Disposition": f"inline; filename*=UTF-8''{quote(pdf.name)}"})
                if method == "POST" and url.path == "/api/app":
                    added = add(person, body)
                    return self._json(200, {**state(person, everyone), "added": added})
                if method == "POST" and url.path.startswith("/api/app/"):
                    change(person, unquote(url.path[len("/api/app/"):]), body)
                    return self._json(200, state(person, everyone))
            self._json(404, {"error": "not found"})
        except LookupError as exc:
            self._json(404, {"error": str(exc)})
        except (ValueError, yamlio.YamlError) as exc:
            self._json(400, {"error": str(exc)})

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("request too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def _json(self, code: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _send(self, code: int, body: bytes, kind: str, headers: dict | None = None) -> None:
        self.send_response(code)
        for key, value in {"Content-Type": kind, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                           **(headers or {})}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


class TrackerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = sys.platform != "win32"  # on Windows it would let a second server take a busy port

    def __init__(self, port: int = 8765):
        super().__init__(("127.0.0.1", port), Handler)
        self.token = secrets.token_urlsafe(24)
        bound = self.server_address[1]
        self.hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/"
