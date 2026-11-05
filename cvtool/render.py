"""Render cv.yaml into a self-contained LaTeX project (cv/ folder) using a built-in or user layout.

Layouts are folders with main.tex.j2 (plus optional extra *.j2 files and a files/ folder copied
verbatim). Built-ins are listed in templates/registry.yaml; user layouts live in
my-layouts/<id>/ with a layout.yaml. Jinja delimiters are LaTeX-friendly:
  << value >>   <% statement %>   <# comment #>
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from . import cvdoc, paths, yamlio
from .kb import KnowledgeBase

HASH_FILE = ".render-hash.json"


@dataclass
class Template:
    id: str
    dir: Path
    meta: dict = field(default_factory=dict)
    custom: bool = False

    @property
    def engine(self) -> str:
        return str(self.meta.get("engine") or "pdflatex")

    @property
    def name(self) -> str:
        return str(self.meta.get("name") or self.id)


@dataclass
class RenderResult:
    out_dir: Path
    files: list[Path]
    template: Template


class RenderError(Exception):
    pass


def templates() -> dict[str, Template]:
    found: dict[str, Template] = {}
    registry = yamlio.load(paths.TEMPLATES_DIR / "registry.yaml", {}) or {}
    for tid, meta in registry.items():
        found[tid] = Template(tid, paths.TEMPLATES_DIR / tid, meta or {})
    if paths.LAYOUTS_DIR.exists():
        for layout in sorted(paths.LAYOUTS_DIR.iterdir()):
            if (layout / "layout.yaml").exists() and (layout / "main.tex.j2").exists():
                meta = yamlio.load(layout / "layout.yaml", {}) or {}
                found[f"my:{layout.name}"] = Template(f"my:{layout.name}", layout, meta, custom=True)
    return found


def get_template(template_id: str) -> Template:
    available = templates()
    if template_id in available:
        return available[template_id]
    if f"my:{template_id}" in available:
        return available[f"my:{template_id}"]
    raise RenderError(f"unknown template {template_id!r}; available: {', '.join(available)}")


def _environment(template: Template) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader([str(template.dir), str(paths.TEMPLATES_DIR / "_shared")]),
        block_start_string="<%", block_end_string="%>",
        variable_start_string="<<", variable_end_string=">>",
        comment_start_string="<#", comment_end_string="#>",
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined, autoescape=False,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hand_edited(out_dir: Path) -> list[str]:
    """Generated files that were changed by hand since the last render."""
    record = out_dir / HASH_FILE
    if not record.exists():
        return []
    hashes = json.loads(record.read_text(encoding="utf-8"))
    return [name for name, digest in hashes.items()
            if (out_dir / name).exists() and _digest(out_dir / name) != digest]


def render(app_dir: Path, template_id: str | None = None, force: bool = False) -> RenderResult:
    cv_path = app_dir / "cv.yaml"
    raw = cvdoc.load(cv_path)
    errors = cvdoc.structural_errors(raw)
    if errors:
        raise RenderError(f"{paths.rel(cv_path)} has problems:\n  - " + "\n  - ".join(errors))
    template = get_template(template_id or str((raw.get("meta") or {}).get("template") or "jakes"))
    out_dir = app_dir / "cv"
    edited = hand_edited(out_dir)
    if edited and not force:
        raise RenderError(
            "these files were edited by hand since the last render and would be overwritten: "
            + ", ".join(edited) + ". Move the change into cv.yaml / the layout, or re-run with --force.")
    out_dir.mkdir(parents=True, exist_ok=True)

    photo_file = _copy_photo(raw, app_dir, out_dir)
    context = cvdoc.build(raw, template.meta, photo_file)
    env = _environment(template)
    written: list[Path] = []
    for j2 in sorted(template.dir.glob("*.j2")):
        target = out_dir / j2.name[:-3]
        try:
            text = env.get_template(j2.name).render(**context)
        except jinja2.TemplateError as exc:
            where = f"{getattr(exc, 'filename', None) or j2.name}:{getattr(exc, 'lineno', '?')}"
            raise RenderError(f"template {template.id} failed at {where}: {exc}") from exc
        if target.name == "main.tex":
            text = with_real_spaces(text)
        target.write_text(text, encoding="utf-8", newline="\n")
        written.append(target)
    files_dir = template.dir / "files"
    if files_dir.exists():
        for src in files_dir.rglob("*"):
            if src.is_file():
                dst = out_dir / src.relative_to(files_dir)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                written.append(dst)
    hashes = {p.relative_to(out_dir).as_posix(): _digest(p) for p in written if p.suffix == ".tex"}
    (out_dir / HASH_FILE).write_text(json.dumps(hashes, indent=1), encoding="utf-8")
    return RenderResult(out_dir, written, template)


# pdfTeX then writes a real space character into the PDF wherever TeX puts space between words. Without
# it, text extraction (and so an ATS) glues words together, e.g. "Data AnalystJul 2023" where a title
# and its dates sit in one row. Invisible on the page; does nothing under XeLaTeX or LuaLaTeX.
REAL_SPACES = r"\ifdefined\pdfinterwordspaceon\pdfinterwordspaceon\fi % CV Creator: real spaces in the PDF text"
_DOCUMENTCLASS = re.compile(r"^[ \t]*\\documentclass(?:\[[^\]]*\])?\{[^}]*\}[^\n]*\n", re.M)


def with_real_spaces(tex: str) -> str:
    """Add REAL_SPACES after \\documentclass, for built-in and user layouts alike (unless already there)."""
    match = _DOCUMENTCLASS.search(tex)
    if "pdfinterwordspace" in tex or not match:
        return tex
    return tex[:match.end()] + REAL_SPACES + "\n" + tex[match.end():]


def _copy_photo(raw: dict, app_dir: Path, out_dir: Path) -> str | None:
    """Copy the photo next to main.tex when the CV asks for one (header.photo: true or a path)."""
    wanted = (raw.get("header") or {}).get("photo")
    if not wanted:
        return None
    if isinstance(wanted, str) and wanted.strip():
        candidates = [Path(wanted), app_dir / wanted, paths.data_dir() / wanted]
    else:
        person = (KnowledgeBase.load().profile.get("person") or {})
        photo = str(person.get("photo") or "")
        candidates = [Path(photo), paths.data_dir() / photo, paths.profile_dir() / photo] if photo else []
    for candidate in candidates:
        if candidate.is_file():
            target = out_dir / f"photo{candidate.suffix.lower()}"
            shutil.copy2(candidate, target)
            return target.stem  # LaTeX finds the extension itself
    raise RenderError("the CV asks for a photo but none was found: set header.photo to a file path "
                      "or person.photo in profile/profile.yaml")
