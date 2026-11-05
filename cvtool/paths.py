"""Where things live.

Personal data is kept per person in people/<id>/ (profile/, applications/, inbox/), so several people
can use the same installation. The person the commands work on is, in this order:
  CV_DATA_DIR       a person's folder used directly (tests, examples/demo); `--person <folder path>`
                    and an application folder given as a path set it too
  --person / CV_PERSON
  people/.active    set by `uv run cv profile use <id>`
  the only person, if there is exactly one.
Where people/ itself lives: CV_PEOPLE_DIR, else `people_dir` in cv.local.yaml (machine-specific,
not in git), else the project folder. Use it to keep personal data out of a cloud-synced folder.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import yamlio

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
LAYOUTS_DIR = ROOT / "my-layouts"
ORIGINALS_DIR = ROOT / "cv-templates"
EXAMPLES_DIR = ROOT / "examples"
LOCAL_SETTINGS = ROOT / "cv.local.yaml"


class NoProfileError(LookupError):
    """No person is selected (none exists yet, or several exist and none is active)."""


def local_settings() -> dict:
    data = yamlio.load(LOCAL_SETTINGS, {})
    return data if isinstance(data, dict) else {}


def people_dir_source() -> str:
    if os.environ.get("CV_PEOPLE_DIR"):
        return "CV_PEOPLE_DIR"
    return LOCAL_SETTINGS.name if local_settings().get("people_dir") else "default"


def people_dir() -> Path:
    configured = os.environ.get("CV_PEOPLE_DIR") or local_settings().get("people_dir")
    if not configured:
        return ROOT / "people"
    path = Path(os.path.expandvars(os.path.expanduser(str(configured))))
    return (path if path.is_absolute() else ROOT / path).resolve()


def in_cloud_folder(path: Path) -> str | None:
    """The OneDrive/Dropbox-style folder that would sync `path`, if any."""
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.environ.get(var)
        if root and path.resolve().is_relative_to(Path(root).resolve()):
            return root
    return None


def person_ids() -> list[str]:
    root = people_dir()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def active_person() -> str | None:
    """The person whose data the commands use; None when CV_DATA_DIR points at a folder directly."""
    if os.environ.get("CV_DATA_DIR"):
        return None
    ids = person_ids()
    chosen = os.environ.get("CV_PERSON")
    marker = people_dir() / ".active"
    if not chosen and marker.exists():
        chosen = marker.read_text(encoding="utf-8").strip()
    if chosen:
        if chosen not in ids:
            raise NoProfileError(f"there is no profile '{chosen}' (existing: {', '.join(ids) or 'none'}); "
                                 "create it with  uv run cv profile add \"<name>\"")
        return chosen
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise NoProfileError("no profile yet: create one with  uv run cv profile add \"<your name>\"")
    raise NoProfileError(f"several profiles exist ({', '.join(ids)}): choose with  uv run cv profile use <id>")


def set_active(person_id: str) -> None:
    people_dir().mkdir(parents=True, exist_ok=True)
    (people_dir() / ".active").write_text(person_id + "\n", encoding="utf-8")


def data_dir() -> Path:
    override = os.environ.get("CV_DATA_DIR")
    if override:
        return Path(override).resolve()
    return people_dir() / active_person()


def profile_dir() -> Path:
    return data_dir() / "profile"


def applications_dir() -> Path:
    return data_dir() / "applications"


def inbox_dir() -> Path:
    return data_dir() / "inbox"


def imports_dir() -> Path:
    return profile_dir() / "imports"


def rel(path: Path) -> str:
    """Path relative to the person's folder or the project, with forward slashes, for friendly output."""
    bases = [ROOT]
    try:
        bases.insert(0, data_dir())
    except NoProfileError:
        pass
    for base in bases:
        try:
            return path.resolve().relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()
