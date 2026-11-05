"""Find a LaTeX engine (MiKTeX, TeX Live, MacTeX) and compile a CV, reporting problems that matter."""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

ENGINES = ("pdflatex", "xelatex", "lualatex")
AUX_SUFFIXES = (".aux", ".out", ".toc", ".fls", ".fdb_latexmk", ".synctex.gz", ".bcf", ".run.xml", ".xdv", ".nav", ".snm")


@dataclass
class CompileResult:
    ok: bool
    engine: str
    pdf: Path | None = None
    pages: int | None = None
    errors: list[str] = field(default_factory=list)
    missing_chars: list[str] = field(default_factory=list)
    overfull: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log: Path | None = None
    seconds: float = 0.0


def _candidate_dirs() -> list[Path]:
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    patterns = [
        str(home / "scoop" / "apps" / "miktex" / "current" / "texmfs" / "install" / "miktex" / "bin" / "x64"),
        str(local / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64"),
        r"C:\Program Files\MiKTeX\miktex\bin\x64",
        r"C:\texlive\*\bin\windows", r"C:\texlive\*\bin\win64", r"C:\texlive\*\bin\win32",
        "/Library/TeX/texbin", "/usr/local/texlive/*/bin/*", "/usr/bin", "/usr/local/bin",
    ]
    dirs: list[Path] = []
    for pattern in patterns:
        dirs += [Path(p) for p in sorted(glob.glob(pattern), reverse=True)]
    return dirs


def find_engine(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for directory in _candidate_dirs():
        for candidate in (directory / f"{name}.exe", directory / name):
            if candidate.is_file():
                return str(candidate)
    return None


def available_engines() -> dict[str, str]:
    return {name: path for name in ENGINES if (path := find_engine(name))}


def is_miktex(engine_path: str) -> bool:
    return "miktex" in engine_path.lower()


def compile_tex(main_tex: Path, engine: str = "pdflatex", timeout: int = 900) -> CompileResult:
    """Run the engine (twice when LaTeX asks for a rerun) and parse the log."""
    exe = find_engine(engine)
    if exe is None:
        fallback = next(iter(available_engines()), None)
        if fallback is None:
            return CompileResult(False, engine, errors=[
                "No LaTeX engine found. Install MiKTeX (Windows: scoop install miktex) or TeX Live, "
                "or upload the cv/ folder (uv run cv zip) to Overleaf."])
        exe, engine = find_engine(fallback), fallback
    cmd = [exe, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
    if is_miktex(exe):
        cmd.append("--enable-installer")
    cmd.append(main_tex.name)
    started = time.time()
    log_path = main_tex.with_suffix(".log")
    result = CompileResult(False, engine, log=log_path)
    for _ in range(3):
        try:
            proc = subprocess.run(cmd, cwd=main_tex.parent, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            result.errors.append(f"{engine} did not finish within {timeout}s "
                                 "(first runs can be slow while MiKTeX downloads packages; try again)")
            return result
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else proc.stdout
        if proc.returncode != 0 or not re.search(r"Rerun|Label\(s\) may have changed|rerunfilecheck|Please rerun", log):
            break
    _parse_log(log, result)
    pdf = main_tex.with_suffix(".pdf")
    result.ok = proc.returncode == 0 and pdf.exists() and not result.errors
    if proc.returncode != 0 and not result.errors:
        tail = "\n".join((proc.stdout or "").strip().splitlines()[-15:])
        result.errors.append(f"{engine} exited with code {proc.returncode}:\n{tail}")
    result.pdf = pdf if pdf.exists() else None
    result.seconds = round(time.time() - started, 1)
    for suffix in AUX_SUFFIXES:
        aux = main_tex.with_suffix(suffix)
        if aux.exists():
            aux.unlink()
    return result


def _parse_log(log: str, result: CompileResult) -> None:
    lines = log.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("!") or re.match(r"^[^\s:]+\.(tex|cls|sty):\d+: ", line):
            context = " ".join(l.strip() for l in lines[i:i + 3] if l.strip())
            # "ignored error" = TeX recovered by itself (e.g. longtable page breaks under the new mark mechanism)
            (result.warnings if "ignored error" in line else result.errors).append(context[:400])
    result.errors = list(dict.fromkeys(result.errors))
    result.missing_chars = sorted(set(re.findall(r"Missing character: There is no (.+?) in font", log)))
    for m in re.finditer(r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)[^\n]*?lines? (\d+)", log):
        if float(m.group(1)) > 2.0:
            result.overfull.append(f"{m.group(1)}pt too wide near line {m.group(2)}")
    for pattern in (r"LaTeX Warning: (Reference .+? undefined)", r"LaTeX Font Warning: (Font shape .+? undefined)",
                    r"(Package \w+ Warning: .+)", r"(Class \w+ Warning: .+)"):
        result.warnings += sorted(set(re.findall(pattern, log)))[:5]
    pages = re.search(r"Output written on .+?\((\d+) pages?", log)
    result.pages = int(pages.group(1)) if pages else None
