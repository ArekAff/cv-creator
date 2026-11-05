"""Import a person's existing CV and find what in it is new to their knowledge base.

  uv run cv resume import [file]   copy into profile/imports/<id>/ and extract text.md (PDF, Word .docx,
                                   LaTeX .tex or Overleaf .zip, .txt/.md; images are kept for Claude to
                                   read). Without a file: everything waiting in the person's inbox/.
  (Claude)                         reads text.md / the original and writes extracted.yaml
  uv run cv resume diff <id>       compares extracted.yaml with the knowledge base. Anything new, changed
                                   or only partly known is an open item, and open items are the agenda
                                   of a sense-making interview (skill: import-resume).
  uv run cv resume resolve ...     marks an item covered (captured in other words) or dismissed

Formats: method/knowledge-base.md ("CV imports").
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import subprocess
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import dates, paths, yamlio
from .apps import slugify
from .kb import KnowledgeBase, label_for, token_match, tokens

KINDS = {".pdf": "pdf", ".docx": "docx", ".tex": "latex", ".zip": "latex-zip", ".txt": "text", ".md": "text"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
UNSUPPORTED_HINT = {".doc": "old Word format", ".odt": "OpenDocument", ".pages": "Pages", ".rtf": "RTF"}
MAX_ZIP_BYTES = 60 * 1024 * 1024
STATUS_ORDER = {"new": 0, "changed": 1, "partly-known": 2, "known": 3}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# =============================================================== import
def import_file(source: Path) -> Path:
    """Copy one CV into profile/imports/<id>/ and extract its text. Inbox files are moved, others copied."""
    source = source.resolve()
    if not source.is_file():
        raise LookupError(f"{source} not found")
    ext = source.suffix.lower()
    kind = KINDS.get(ext) or ("image" if ext in IMAGES else None)
    if kind is None:
        what = UNSUPPORTED_HINT.get(ext, ext or "files without an extension")
        raise ValueError(f"{source.name}: {what} is not supported; save it as PDF or Word (.docx), or paste the text")
    folder = _new_folder(source.stem)
    notes: list[str] = []
    if kind == "latex-zip":
        main = _unzip(source, folder / "original")
        if main is None:
            raise ValueError(f"{source.name}: no .tex file with \\documentclass inside the zip")
        original = main.relative_to(folder).as_posix()
        text = detex(_inline_tex(main))
        kind = "latex"
    elif kind == "latex":
        main = _copy_latex(source, folder / "original")
        original = main.relative_to(folder).as_posix()
        text = detex(_inline_tex(main))
    else:
        target = folder / f"original{ext}"
        shutil.copy2(source, target)
        original = target.name
        text = extract_text(target, kind)
    chars = len((text or "").strip())
    quality = "none" if text is None else ("ok" if chars >= 400 else "low")
    if kind == "image":
        notes.append("image: read it and write text.md (transcription) yourself")
    elif quality == "low":
        notes.append("little text extracted (scanned or image-based?): ask for a text PDF/DOCX or screenshots")
    header = f"<!-- text of {original}, extracted by `uv run cv resume import`; corrections welcome -->\n\n"
    (folder / "text.md").write_text(header + (text or "(no text layer: transcribe from the original)\n"),
                                    encoding="utf-8")
    yamlio.dump({
        "id": folder.name, "imported": dt.date.today().isoformat(), "source_name": source.name,
        "original": original, "kind": kind, "text_chars": chars, "text_quality": quality, "notes": notes,
        "resolutions": {},
    }, folder / "import.yaml")
    try:
        if source.parent.resolve() == paths.inbox_dir().resolve():
            source.unlink()  # moved: the copy now lives in the import folder
    except OSError:
        pass
    return folder


def inbox_files() -> list[Path]:
    inbox = paths.inbox_dir()
    if not inbox.exists():
        return []
    return sorted(p for p in inbox.iterdir()
                  if p.is_file() and not p.name.startswith(".") and not p.name.lower().startswith("readme"))


def imports() -> list[Path]:
    root = paths.imports_dir()
    if not root.exists():
        return []
    return sorted((p for p in root.iterdir() if (p / "import.yaml").exists()), key=lambda p: p.name)


def resolve(ref: str | None) -> Path:
    found = imports()
    if not found:
        raise LookupError("no CV imports yet: uv run cv resume import <file>")
    if not ref or ref == "latest":
        return found[-1]
    matches = [p for p in found if p.name == ref] or [p for p in found if ref.lower() in p.name.lower()]
    if len(matches) != 1:
        raise LookupError(f"'{ref}' matches {len(matches)} imports: {', '.join(p.name for p in found)}")
    return matches[0]


def _new_folder(stem: str) -> Path:
    base = f"{dt.date.today().isoformat()}-{slugify(stem, 40)}"
    folder, n = paths.imports_dir() / base, 2
    while folder.exists():
        folder, n = paths.imports_dir() / f"{base}-{n}", n + 1
    folder.mkdir(parents=True)
    return folder


# =============================================================== text extraction
def extract_text(path: Path, kind: str) -> str | None:
    if kind == "pdf":
        return _pdf_text(path)
    if kind == "docx":
        return docx_text(path)
    if kind == "text":
        return path.read_text(encoding="utf-8", errors="replace")
    return None


def _pdf_text(path: Path) -> str:
    """poppler's pdftotext when installed (keeps the spaces pdfLaTeX encodes as gaps), else pypdf."""
    exe = shutil.which("pdftotext")
    if exe:
        try:
            done = subprocess.run([exe, "-enc", "UTF-8", str(path), "-"], capture_output=True, timeout=60)
            text = done.stdout.decode("utf-8", errors="replace")
            if done.returncode == 0 and text.strip():
                return unicodedata.normalize("NFKC", text.replace("\f", "\n\n"))
        except (OSError, subprocess.TimeoutExpired):
            pass
    from pypdf import PdfReader
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    return unicodedata.normalize("NFKC", "\n\n".join(pages))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    """Paragraph text of a .docx (headers first, then the body, then footers); list items get '- '."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        parts = sorted(n for n in names if re.fullmatch(r"word/header\d*\.xml", n))
        parts += ["word/document.xml"] + sorted(n for n in names if re.fullmatch(r"word/footer\d*\.xml", n))
        chunks = [_wordml_text(z.read(n)) for n in parts if n in names]
    return "\n\n".join(c for c in chunks if c.strip())


def _wordml_text(xml: bytes) -> str:
    root = ET.fromstring(xml)
    parent = {child: node for node in root.iter() for child in node}

    def owner(node: ET.Element) -> ET.Element | None:
        up = parent.get(node)
        while up is not None and up.tag != _W + "p":
            up = parent.get(up)
        return up

    lines = []
    for para in root.iter(_W + "p"):
        bits = []
        for node in para.iter():
            if node is para or owner(node) is not para:
                continue  # text boxes hold their own paragraphs
            if node.tag == _W + "t":
                bits.append(node.text or "")
            elif node.tag == _W + "tab":
                bits.append("\t")
            elif node.tag in (_W + "br", _W + "cr"):
                bits.append("\n")
        text = "".join(bits).strip()
        if text:
            props = para.find(_W + "pPr")
            listed = props is not None and props.find(_W + "numPr") is not None
            lines.append(("- " if listed else "") + text)
    return "\n".join(lines)


# --------------------------------------------------------------- LaTeX
_INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")


def _tex_file(base: Path, name: str) -> Path | None:
    for candidate in (base / name, base / f"{name}.tex"):
        if candidate.is_file():
            return candidate
    return None


def _inline_tex(main: Path, depth: int = 0) -> str:
    """The .tex source with \\input/\\include files pasted in (relative to the main file's folder)."""
    text = main.read_text(encoding="utf-8", errors="replace")
    if depth > 5:
        return text

    def paste(m: re.Match) -> str:
        found = _tex_file(main.parent, m.group(1).strip())
        return _inline_tex(found, depth + 1) if found else m.group(0)
    return _INPUT.sub(paste, text)


def _copy_latex(main: Path, dest: Path) -> Path:
    """Copy the .tex plus the local files it uses (\\input files, own .cls/.sty, images)."""
    dest.mkdir(parents=True, exist_ok=True)
    base = main.parent
    wanted, seen, queue = {main}, set(), [main]
    while queue:
        tex = queue.pop()
        if tex in seen:
            continue
        seen.add(tex)
        source = tex.read_text(encoding="utf-8", errors="replace")
        for m in _INPUT.finditer(source):
            found = _tex_file(base, m.group(1).strip())
            if found:
                wanted.add(found)
                queue.append(found)
        for m in re.finditer(r"\\(?:documentclass|usepackage|RequirePackage)(?:\[[^\]]*\])?\{([^}]+)\}", source):
            for name in m.group(1).split(","):
                for ext in (".cls", ".sty"):
                    if (base / f"{name.strip()}{ext}").is_file():
                        wanted.add(base / f"{name.strip()}{ext}")
        for m in re.finditer(r"\\(?:includegraphics|photo[RL]?|background)(?:\[[^\]]*\])*(?:\{[^}]*\})?\{([^}]+)\}", source):
            for ext in ("", ".png", ".jpg", ".jpeg", ".pdf"):
                if (base / f"{m.group(1).strip()}{ext}").is_file():
                    wanted.add(base / f"{m.group(1).strip()}{ext}")
    for path in wanted:
        if not path.resolve().is_relative_to(base.resolve()):
            continue  # only files inside the CV's own folder
        target = dest / path.relative_to(base)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return dest / main.name


def _unzip(archive: Path, dest: Path) -> Path | None:
    """Extract an Overleaf zip safely (no absolute paths, no '..', size-limited); return the main .tex."""
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = Path(info.filename)
            if info.is_dir() or name.is_absolute() or ".." in name.parts or info.filename.startswith(("/", "\\")):
                continue
            total += info.file_size
            if total > MAX_ZIP_BYTES:
                raise ValueError(f"{archive.name} is larger than {MAX_ZIP_BYTES // 2**20} MB unpacked")
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
    mains = [p for p in dest.rglob("*.tex") if "\\documentclass" in p.read_text(encoding="utf-8", errors="replace")]
    mains.sort(key=lambda p: (p.name != "main.tex", len(p.parts)))
    return mains[0] if mains else None


# LaTeX source -> readable text. Commands are handled by rule; unknown macros show their arguments
# separated by " | " (e.g. \resumeSubheading{Org}{City}{Title}{Dates}), which keeps CV data readable.
_DROP = {
    "vspace": 1, "hspace": 1, "includegraphics": 1, "label": 1, "setlength": 2, "addtolength": 2, "definecolor": 3,
    "colorlet": 2, "color": 1, "usepackage": 1, "RequirePackage": 1, "documentclass": 1, "geometry": 1,
    "hypersetup": 1, "pagestyle": 1, "thispagestyle": 1, "input": 1, "include": 1, "addbibresource": 1,
    "fontsize": 2, "rule": 2, "linespread": 1, "setmainfont": 1, "setsansfont": 1, "columnratio": 1,
    "background": 1, "photoscale": 1, "headerscale": 1, "mynames": 1, "nocite": 1, "printbibliography": 0,
    "wheelchart": 3, "photo": None, "photoR": 2, "photoL": 2, "newcommand": None, "renewcommand": None,
    "providecommand": None, "newenvironment": None, "renewenvironment": None, "titleformat": None,
    "titlespacing": None, "setlist": None, "fancyhf": 1, "fancyfoot": 1, "fancyhead": 1, "makecvfooter": 3,
    "urlstyle": 1, "addvspace": 1, "newsavebox": 1, "sbox": 2, "simpleicon": 1, "faicon": 1, "title": 1,
    "AtBeginEnvironment": 2, "AddToHook": 2, "excludecomment": 1, "includecomment": 1, "prefix": 1,
    "keyfont": 1, "rubricfont": 1, "makeheaders": 0, "makerubric": 1, "pdfgentounicode": 0, "selectfont": 0,
    "phantomsection": 0, "hrule": 0, "today": 0, "makecvsidebar": 0, "BeginAccSupp": 1, "EndAccSupp": 1,
}
_KEEP_LAST = {"textcolor": 2, "colorbox": 2, "fcolorbox": 3, "raisebox": 2, "resizebox": 3, "scalebox": 2,
              "parbox": 2, "makebox": 1, "framebox": 1, "multicolumn": 3, "multirow": 3, "hyperlink": 2}
_FORMAT = {"textbf", "textit", "emph", "underline", "textsc", "texttt", "textsf", "textrm", "textup", "textsl",
           "textmd", "textnormal", "mbox", "hbox", "text", "uline", "MakeUppercase", "MakeLowercase", "textBF"}
_HEADINGS = {"section", "subsection", "subsubsection", "cvsection", "cvsubsection", "sectitle", "subrubric"}
_HEADING_ENVS = {"rSection", "rubric"}
_PLAIN_ENVS = {"document", "itemize", "enumerate", "description", "center", "flushleft", "flushright", "tabular",
               "tabular*", "tabularx", "longtable", "minipage", "adjustwidth", "multicols", "paracol", "list",
               "quote", "quotation", "tikzpicture", "figure", "table", "filecontents", "filecontents*",
               "spacing", "comment", "fullonly"}
_NEWLINE = {"par", "newline", "linebreak", "smallskip", "medskip", "bigskip", "vfill", "divider", "switchcolumn",
            "newpage", "clearpage", "pagebreak", "cr", "makecvheader", "maketitle"}
_SPACE = {"hfill", "hfil", "quad", "qquad", "enspace", "enskip", "thinspace", "noindent", "centering",
          "raggedright", "raggedleft", "indent", "space", "dotfill", "hrulefill", "infoSeparator"}
_WORDS = {"textbullet": "•", "textendash": "–", "textemdash": "—", "textasciitilde": "~", "textbar": "|",
          "textless": "<", "textgreater": ">", "ldots": "…", "dots": "…", "LaTeX": "LaTeX", "TeX": "TeX",
          "textquotedblleft": "“", "textquotedblright": "”", "quotedblbase": "„", "euro": "€", "texteuro": "€"}
_LETTERS = {"l": "ł", "L": "Ł", "o": "ø", "O": "Ø", "ss": "ß", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ",
            "aa": "å", "AA": "Å", "i": "ı"}
_ACCENT_SYMBOLS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304",
                   ".": "\u0307"}
_ACCENT_WORDS = {"u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a",
                 "d": "\u0323", "b": "\u0331"}
_ESCAPES = {"&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}", ",": " ", " ": " ", ";": " ",
            ":": " ", "!": "", "-": "", "/": "", "@": "", "|": "|"}
_MATH = {"cdot": "·", "bullet": "•", "sim": "~", "times": "×", "rightarrow": "→", "to": "→", "leftarrow": "←",
         "geq": "≥", "ge": "≥", "leq": "≤", "le": "≤", "approx": "≈", "pm": "±", "diamond": "◇", "circ": "°",
         "mid": "|", "vert": "|", "ldots": "…", "dots": "…"}
_DATA_COMMANDS = ("name", "tagline", "address", "mobile", "phone", "email", "position", "headwords", "quote",
                  "aboutMe", "skillset", "languages", "hobbies", "nonProfit", "leftheader", "personalinfo",
                  "homepage", "linkedin", "github", "gitlab", "twitter", "xtwitter", "orcid", "location",
                  "mailaddress", "extrainfo", "author", "subtitle")
_CMD = re.compile(r"\\([A-Za-z@]+)\*?")


def detex(source: str) -> str:
    """Readable text from a LaTeX CV: the document body plus personal data set in the preamble."""
    source = _strip_comments(source)
    start, end = source.find("\\begin{document}"), source.find("\\end{document}")
    preamble = source[:start] if start >= 0 else ""
    body = source[start + len("\\begin{document}"):end if end > start else None] if start >= 0 else source
    return _tidy(_preamble_data(preamble) + "\n\n" + _render(body))


def _strip_comments(source: str) -> str:
    lines = []
    for line in source.splitlines():
        i, cut = 0, len(line)
        while i < len(line):
            if line[i] == "\\":
                i += 2
                continue
            if line[i] == "%":
                cut = i
                break
            i += 1
        lines.append(line[:cut])
    return "\n".join(lines)


def _match_close(s: str, i: int, open_ch: str = "{", close_ch: str = "}") -> int:
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s) - 1


def _read_groups(s: str, i: int, arity: int | None) -> tuple[list[tuple[str, str]], int]:
    """[(kind, content)] of the [..] and {..} groups after a command; arity None = all following {..}."""
    groups: list[tuple[str, str]] = []
    mandatory = 0
    while i < len(s):
        if s[i] == "[" and (mandatory == 0 or arity is None):
            j = _match_close(s, i, "[", "]")
            groups.append(("[", s[i + 1:j]))
            i = j + 1
            continue
        k = i
        while k < len(s) and s[k] in " \t\n" and s[i:k + 1].count("\n") < 2:
            k += 1
        if k < len(s) and s[k] == "{" and (arity is None or mandatory < arity):
            j = _match_close(s, k)
            groups.append(("{", s[k + 1:j]))
            mandatory += 1
            i = j + 1
            continue
        break
    return groups, i


def _render(s: str, math: bool = False) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "\\":
                out.append("\n")
                groups, i = _read_groups(s, i + 2, 0)
                continue
            if nxt in _ACCENT_SYMBOLS and not math:
                j = i + 2
                if j < n and s[j] == "{":
                    k = _match_close(s, j)
                    base, i = _render(s[j + 1:k]), k + 1
                else:
                    base, i = (s[j] if j < n else ""), j + 1
                out.append(unicodedata.normalize("NFC", base[:1] + _ACCENT_SYMBOLS[nxt] + base[1:]))
                continue
            if not nxt.isalpha():
                out.append(_ESCAPES.get(nxt, ""))
                i += 2
                continue
            m = _CMD.match(s, i)
            name, i = m.group(1), m.end()
            if name in _ACCENT_WORDS:
                groups, i = _read_groups(s, i, 1)
                base = _render(groups[-1][1]) if groups else ""
                out.append(unicodedata.normalize("NFC", base[:1] + _ACCENT_WORDS[name] + base[1:]))
                continue
            if name in _LETTERS:
                if s.startswith("{}", i):
                    i += 2
                out.append(_LETTERS[name])
                continue
            text, i = _command(s, name, math, i)
            out.append(text)
            continue
        if c == "{":
            j = _match_close(s, i)
            out.append(_render(s[i + 1:j], math))
            i = j + 1
        elif c == "}":
            i += 1
        elif c == "$" and not math:
            j = s.find("$", i + 1)
            if j < 0:
                i += 1
                continue
            out.append(_render(s[i + 1:j], math=True))
            i = j + 1
        elif c == "~":
            out.append(" ")
            i += 1
        elif c == "&":
            out.append(" | ")
            i += 1
        elif math and c in "^_":
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


_SWITCHES = {"tiny", "scriptsize", "footnotesize", "small", "normalsize", "large", "Large", "LARGE", "huge", "Huge",
             "bfseries", "itshape", "scshape", "sffamily", "rmfamily", "ttfamily", "upshape", "mdseries", "em",
             "bf", "it", "sc", "sf", "rm", "tt", "normalfont"}


def _command(s: str, name: str, math: bool, i: int) -> tuple[str, int]:
    """Render the command whose name ends at s[i]; returns the text and the position after its arguments."""
    if math:
        if name in _MATH:
            return _MATH[name], i
        groups, end = _read_groups(s, i, 1 if name in ("text", "mathrm", "textrm", "mathbf") else 0)
        return "".join(_render(c) for _, c in groups), end
    if name in _WORDS or name in _NEWLINE or name in _SPACE or name in _SWITCHES or name == "item" or _is_icon(name):
        groups, end = _read_groups(s, i, 0)
        if name == "item":
            label = groups[0][1].strip() if groups else ""
            return "\n- " + (_render(label).strip() + " " if label else ""), end
        if name in _WORDS:
            return _WORDS[name], end
        if name in _NEWLINE:
            return "\n", end
        return (" " if name in _SPACE else ""), end
    if name == "href":
        arity = 2
    elif name in _DROP:
        arity = _DROP[name]
    elif name in _KEEP_LAST:
        arity = _KEEP_LAST[name]
    else:
        arity = 1 if name in _FORMAT | _HEADINGS | {"url", "end"} else None
    groups, end = _read_groups(s, i, arity)
    args = [c for kind, c in groups if kind == "{"]
    if name in _DROP:
        return "", end
    if name == "begin":
        env, rest = (args[0] if args else ""), args[1:]
        if env in _HEADING_ENVS and rest:
            return f"\n\n## {_render(rest[0]).strip()}\n", end
        if env in _PLAIN_ENVS:
            return "\n", end
        return "\n" + " | ".join(r for r in (_render(a).strip() for a in rest) if r) + "\n", end
    if name == "end":
        return "\n", end
    if name in _HEADINGS:
        return (f"\n\n## {_render(args[-1]).strip()}\n" if args else ""), end
    if name == "href":
        return (f"{_render(args[1]).strip()} <{args[0].strip()}>" if len(args) == 2 else ""), end
    if name == "url":
        return (args[0].strip() if args else ""), end
    if name in _KEEP_LAST:
        return (_render(args[-1]) if args else ""), end
    if name in _FORMAT:
        return "".join(_render(a) for a in args), end
    shown = " | ".join(x for x in (_render(c).strip() for _, c in groups) if x)  # unknown macro: show its data
    if name.lower().endswith("item") and shown:  # \resumeItem, \cvItem, \italicitem ... are bullets
        return f"\n- {shown}", end
    return (f" {shown} " if shown else ""), end


def _is_icon(name: str) -> bool:
    return len(name) > 2 and name.startswith("fa") and name[2].isupper()


def _preamble_data(preamble: str) -> str:
    """Personal data some templates set before \\begin{document} (\\name, \\email, \\address, ...)."""
    out = []
    for m in re.finditer(r"\\(" + "|".join(_DATA_COMMANDS) + r")(?![A-Za-z@])", preamble):
        if re.search(r"(?:newcommand|renewcommand|providecommand|def)\s*\{?\s*$", preamble[max(0, m.start() - 16):m.start()]):
            continue
        groups, _ = _read_groups(preamble, m.end(), None)
        values = [v for v in (_render(c).strip() for kind, c in groups if kind == "{") if v]
        if values:
            out.append(f"{m.group(1)}: {' '.join(values)}")
    return "\n".join(out)


def _tidy(text: str) -> str:
    text = text.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        line = re.sub(r"(?:\|\s*){2,}", "| ", line)
        line = re.sub(r"^\|\s*|\s*\|$", "", line).strip()
        lines.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).replace("\n\n- ", "\n- ")
    return unicodedata.normalize("NFC", text).strip() + "\n"


# =============================================================== diff against the knowledge base
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from", "at", "as", "into", "over",
    "under", "via", "per", "across", "within", "using", "about", "around", "than", "more", "less", "their", "our",
    "my", "his", "her", "its", "this", "that", "these", "those", "was", "were", "is", "are", "be", "been", "has",
    "have", "had", "will", "would", "it", "they", "we", "you", "all", "each", "also", "while", "during", "after",
    "before", "up", "out", "through", "both", "such", "which", "who", "where", "when", "what", "how", "not", "new",
    "i", "oraz", "w", "we", "z", "ze", "na", "do", "dla", "od", "po", "przy", "o", "ale", "lub", "czy", "jest",
    "są", "był", "była", "było", "się", "jak", "że", "który", "która", "które", "ich", "jego", "jej", "przez",
    "pod", "nad", "za", "bez", "ten", "ta", "te", "tym", "tego", "co", "jako", "także", "również",
}
ORG_NOISE = {"sp", "oo", "o.o", "inc", "ltd", "llc", "gmbh", "sa", "s.a", "corp", "co", "company", "group",
             "plc", "ag", "bv", "nv", "spółka", "spolka", "limited"}
_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")  # not ids such as A3, T001, P02 or levels like B1


def _content(text: object) -> set[str]:
    return {t for t in tokens(str(text or "")) if len(t) > 1 and t not in STOPWORDS and not _NUMBER.fullmatch(t)}


_DATE = re.compile(r"\b(?:19|20)\d\d[-/.]\d{1,2}(?:[-/.]\d{1,2})?\b|\b\d{1,2}[./](?:19|20)\d\d\b")


def _numbers(text: object) -> set[str]:
    """Figures a claim rests on: dates (2022-09, 03.2021) and bare years are not figures."""
    found = set()
    for m in _NUMBER.finditer(_DATE.sub(" ", str(text or ""))):
        value = m.group(0).replace(",", ".")
        if re.fullmatch(r"(19|20)\d\d", value):
            continue  # a year is a date, not a claim
        found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return found


def _coverage(claim: set[str], corpus: set[str]) -> float:
    if not claim:
        return 1.0
    hits = sum(1 for t in claim if t in corpus or any(token_match(t, c) for c in corpus))
    return hits / len(claim)


def _sim(a: object, b: object) -> float:
    """Symmetric name similarity (organisations, titles, schools, certificates)."""
    ta = {t for t in _content(a) if t not in ORG_NOISE}
    tb = {t for t in _content(b) if t not in ORG_NOISE}
    if not ta or not tb:
        return 0.0
    a_in_b = sum(1 for x in ta if any(token_match(x, y) for y in tb)) / len(ta)
    b_in_a = sum(1 for y in tb if any(token_match(y, x) for x in ta)) / len(tb)
    return (a_in_b + b_in_a) / 2


def _span(item: dict, open_ended: bool) -> tuple[tuple[int, int], tuple[int, int]] | None:
    try:
        start, end = dates.parse(item.get("start")), dates.parse(item.get("end"))
    except ValueError:
        return None
    today = dt.date.today()
    if start is None and end is None:
        return None
    first = start or end
    begin = (first.year, first.month or 1) if not first.present else (today.year, today.month)
    if end is None:
        finish = (today.year, today.month) if open_ended else (begin[0], 12)
    elif end.present:
        finish = (today.year, today.month)
    else:
        finish = (end.year, end.month or 12)
    return begin, finish


def _overlap(a: dict, b: dict) -> float:
    sa, sb = _span(a, True), _span(b, True)
    if not sa or not sb:
        return 0.5
    return 1.0 if sa[0] <= sb[1] and sb[0] <= sa[1] else 0.0


def _date_changes(kb_item: dict, cv_item: dict, fields: tuple[str, ...]) -> list[str]:
    changes = []
    for field in fields:
        kb_value, cv_value = kb_item.get(field), cv_item.get(field)
        try:
            a, b = dates.parse(kb_value), dates.parse(cv_value)
        except ValueError:
            continue
        if not a and not b:
            continue
        differs = (not a or not b) or a.present != b.present or (
            not a.present and (a.year != b.year or (a.month and b.month and a.month != b.month)))
        if differs:
            changes.append(f"{field}: knowledge base {kb_value or '—'}, CV {cv_value or '—'}")
    return changes


class _Corpus:
    """Token and number sets of every knowledge-base unit, for 'is this CV claim already known?'."""

    def __init__(self, kb: KnowledgeBase):
        self.docs: dict[str, tuple[set[str], set[str]]] = {}
        for doc in kb.documents():
            text = " ".join(t for _, t in doc.fields)
            self.docs[doc.id] = (_content(text), _numbers(text))
        self.trails_of: dict[str, list[str]] = {}
        for t in kb.trails:
            for ref in t.get("linked_to") or []:
                self.trails_of.setdefault(str(ref), []).append(str(t.get("id")))
        for list_name in ("positions", "projects", "education"):
            for item in kb.items(list_name):
                for resp in item.get("responsibilities") or []:
                    for ref in (resp.get("trails") if isinstance(resp, dict) else None) or []:
                        self.trails_of.setdefault(str(item.get("id")), []).append(str(ref))
                for ref in item.get("trails") or []:
                    self.trails_of.setdefault(str(item.get("id")), []).append(str(ref))
        self.everything = set().union(*(toks for toks, _ in self.docs.values())) if self.docs else set()

    def claim(self, text: str, scope: str | None) -> dict:
        claim_tokens, claim_numbers = _content(text), _numbers(text)
        local = [scope, *self.trails_of.get(scope, [])] if scope else []
        candidates = [d for d in dict.fromkeys(local) if d in self.docs] + [d for d in self.docs if d not in local]
        best_ref, best = None, 0.0
        for ref in candidates:
            cov = _coverage(claim_tokens, self.docs[ref][0])
            if cov > best + 1e-9:
                best_ref, best = ref, cov
        known_numbers = set()
        for ref in [*local, best_ref if best >= 0.6 else None]:  # a weak match's figures prove nothing
            if ref in self.docs:
                known_numbers |= self.docs[ref][1]
        missing = sorted(claim_numbers - known_numbers, key=lambda x: (len(x), x))
        return _verdict(best, best_ref, missing)

    def overall(self, text: str) -> dict:
        """For summaries and headlines, which draw on the whole knowledge base at once."""
        all_numbers = set().union(*(nums for _, nums in self.docs.values())) if self.docs else set()
        missing = sorted(_numbers(text) - all_numbers, key=lambda x: (len(x), x))
        return _verdict(_coverage(_content(text), self.everything), None, missing)


def _verdict(coverage: float, closest: str | None, missing_numbers: list[str]) -> dict:
    if coverage >= 0.6 and not missing_numbers:
        status = "known"
    else:
        status = "new" if coverage < 0.35 else "partly-known"
    return {"status": status, "coverage": round(coverage, 2), "closest": closest, "new_numbers": missing_numbers}


def load_extracted(folder: Path) -> dict:
    data = yamlio.load(folder / "extracted.yaml", None)
    if data is None:
        raise LookupError(f"{folder.name}/extracted.yaml is missing: read text.md and write it first "
                          "(format: method/knowledge-base.md, 'CV imports')")
    if not isinstance(data, dict):
        raise ValueError(f"{folder.name}/extracted.yaml must be a mapping")
    return data


def diff(folder: Path, kb: KnowledgeBase | None = None, write: bool = True) -> dict:
    """Compare extracted.yaml with the knowledge base; writes diff.yaml unless write=False."""
    kb = kb or KnowledgeBase.load()
    cv = load_extracted(folder)
    meta = yamlio.load(folder / "import.yaml", {}) or {}
    resolutions = meta.get("resolutions") or {}
    corpus = _Corpus(kb)
    items: list[dict] = []

    def add(item: dict) -> dict:
        item.setdefault("changes", [])
        item.setdefault("claims", [])
        items.append(item)
        return item

    # --- positions, with each bullet checked against what the knowledge base knows
    for n, pos in enumerate(_dicts(cv.get("positions")), 1):
        label = f"{pos.get('title', '?')} @ {pos.get('organization', '?')} ({_when(pos)})"
        best, score = None, 0.0
        for cand in kb.items("positions"):
            org = _sim(pos.get("organization"), cand.get("organization"))
            if org < 0.6:
                continue
            s = 0.55 * org + 0.25 * _sim(pos.get("title"), cand.get("title")) + 0.2 * _overlap(pos, cand)
            if s > score:
                best, score = cand, s
        if best is not None and score < 0.6:
            best = None
        item = add({"key": f"pos{n}", "kind": "position", "label": label,
                    "match": str(best.get("id")) if best else None, "score": round(score, 2)})
        if best is None:
            item.update(status="new", priority="high")
        else:
            changes = _date_changes(best, pos, ("start", "end"))
            if _sim(pos.get("title"), best.get("title")) < 0.8:
                changes.append(f"title: knowledge base '{best.get('title')}', CV '{pos.get('title')}'")
            item.update(status="changed" if changes else "known", priority="medium", changes=changes)
        scope = item["match"]
        for b, bullet in enumerate(_texts(pos.get("bullets")), 1):
            item["claims"].append({"key": f"pos{n}.b{b}", "text": bullet, **corpus.claim(bullet, scope)})

    # --- other timeline lists
    specs = (
        ("education", "edu", lambda e: f"{', '.join(str(x) for x in (e.get('degree'), e.get('field')) if x)} — {e.get('institution', '?')}",
         lambda e, k: 0.6 * _sim(e.get("institution"), k.get("institution"))
         + 0.4 * _sim(f"{e.get('degree', '')} {e.get('field', '')}", f"{k.get('degree', '')} {k.get('field', '')}"),
         ("start", "end")),
        ("certifications", "cert", lambda c: str(c.get("name", "?")),
         lambda c, k: _sim(c.get("name"), k.get("name")), ("date",)),
        ("projects", "proj", lambda p: str(p.get("name", "?")), lambda p, k: _sim(p.get("name"), k.get("name")),
         ("start", "end")),
        ("awards", "award", lambda a: str(a.get("name", "?")), lambda a, k: _sim(a.get("name"), k.get("name")),
         ("date",)),
        ("publications", "pub", lambda p: str(p.get("title", "?")),
         lambda p, k: _sim(p.get("title"), k.get("title")), ()),
    )
    for list_name, prefix, describe, similarity, date_fields in specs:
        for n, entry in enumerate(_dicts(cv.get(list_name)), 1):
            scored = sorted(((similarity(entry, cand), cand) for cand in kb.items(list_name)),
                            key=lambda pair: -pair[0])
            best, score = (scored[0][1], scored[0][0]) if scored and scored[0][0] >= 0.55 else (None, 0.0)
            when = _when(entry)
            item = add({"key": f"{prefix}{n}", "kind": list_name.rstrip("s") if list_name != "education" else "education",
                        "label": describe(entry) + (f" ({when})" if when else ""),
                        "match": str(best.get("id")) if best else None, "score": round(score, 2)})
            if best is None:
                item.update(status="new", priority="medium")
            else:
                changes = _date_changes(best, entry, date_fields)
                if list_name == "certifications" and entry.get("status") and best.get("status") \
                        and str(entry["status"]).lower() != str(best["status"]).lower():
                    changes.append(f"status: knowledge base {best['status']}, CV {entry['status']}")
                item.update(status="changed" if changes else "known", priority="medium", changes=changes)
            for b, bullet in enumerate(_texts(entry.get("bullets")), 1):
                item["claims"].append({"key": f"{prefix}{n}.b{b}", "text": bullet,
                                       **corpus.claim(bullet, item["match"])})

    # --- skills, spoken languages, interests
    skill_text = " ".join(
        [str(s.get("name")) for s in kb.skills] + [str(a) for s in kb.skills for a in s.get("aliases") or []]
        + [str(x) for t in kb.trails for x in t.get("skills_used") or []]
        + [str(x) for lst in ("positions", "projects") for p in kb.items(lst) for x in p.get("tools") or []]
        + [str(c.get("name")) for c in kb.items("certifications")])
    skill_tokens = set(tokens(skill_text))
    for raw in _texts(cv.get("skills")):
        name = re.sub(r"\s*\([^)]*\)", "", raw).strip() or raw
        name_tokens = tokens(name)
        known = bool(name_tokens) and all(t in skill_tokens or any(token_match(t, k) for k in skill_tokens)
                                          for t in name_tokens)
        add({"key": f"skill:{slugify(name, 40)}", "kind": "skill", "label": raw,
             "status": "known" if known else "new", "priority": "medium", "match": None})
    kb_languages = {str(l.get("language", "")).lower(): l for l in _dicts(kb.profile.get("languages"))}
    for entry in _dicts(cv.get("languages")):
        language = str(entry.get("language") or "")
        known = next((v for k, v in kb_languages.items() if k and token_match(k, language.lower())), None)
        item = add({"key": f"lang:{slugify(language, 30)}", "kind": "language",
                    "label": f"{language} {entry.get('level') or ''}".strip(), "priority": "low", "match": None})
        if known is None:
            item["status"] = "new"
        elif str(known.get("level") or "").lower() != str(entry.get("level") or "").lower() and entry.get("level"):
            item.update(status="changed", changes=[f"level: knowledge base {known.get('level') or '—'}, "
                                                   f"CV {entry.get('level')}"])
        else:
            item["status"] = "known"
    kb_interests = " ".join(str(x) for x in kb.profile.get("interests") or [])
    for raw in _texts(cv.get("interests")):
        known = _coverage(_content(raw), _content(kb_interests)) >= 0.6
        add({"key": f"interest:{slugify(raw, 30)}", "kind": "interest", "label": raw,
             "status": "known" if known else "new", "priority": "low", "match": None})

    # --- contact details and self-description
    person = cv.get("person") or {}
    kb_person = kb.profile.get("person") or {}
    for field in ("name", "email", "phone", "location"):
        cv_value, kb_value = str(person.get(field) or "").strip(), str(kb_person.get(field) or "").strip()
        if not cv_value:
            continue
        same = _squash(cv_value) == _squash(kb_value) or (field in ("name", "location") and _sim(cv_value, kb_value) >= 0.8)
        status = "known" if same else ("new" if not kb_value else "changed")
        add({"key": f"contact:{field}", "kind": "contact", "label": f"{field}: {cv_value}", "status": status,
             "priority": "low", "match": None,
             "changes": [f"{field}: knowledge base {kb_value}, CV {cv_value}"] if status == "changed" else []})
    kb_links = {_squash_url(l.get("url") if isinstance(l, dict) else l) for l in kb_person.get("links") or []}
    for n, link in enumerate(_texts(person.get("links")), 1):
        add({"key": f"contact:link{n}", "kind": "contact", "label": link, "priority": "low", "match": None,
             "status": "known" if _squash_url(link) in kb_links else "new"})
    for field in ("headline", "summary"):
        text = person.get(field) if field == "headline" else cv.get("summary")
        if text:
            add({"key": field, "kind": field, "label": str(text), "priority": "low", "match": None,
                 "status": corpus.overall(str(text))["status"]})
    for n, raw in enumerate(_texts(cv.get("other")), 1):
        add({"key": f"other{n}", "kind": "other", "label": raw, "status": "new", "priority": "low", "match": None})

    # --- resolutions recorded earlier, and the agenda
    for item in items:
        for claim in item["claims"]:
            if item["status"] == "new" and claim["status"] == "partly-known":
                claim["status"] = "new"  # word overlap with an unrelated story is no evidence
            if claim["key"] in resolutions:
                claim["resolution"] = resolutions[claim["key"]]
            if claim["status"] != "known":
                claim["priority"] = "high"
        if item["key"] in resolutions:
            item["resolution"] = resolutions[item["key"]]
    open_items = [i for i in items if i["status"] != "known" and "resolution" not in i]
    open_claims = [c for i in items for c in i["claims"] if c["status"] != "known" and "resolution" not in c]
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUS_ORDER}
    counts["claims_open"] = len(open_claims)
    report = {
        "import": folder.name,
        "person": paths.active_person(),
        "compared": dt.date.today().isoformat(),
        "counts": counts,
        "open": len(open_items) + len(open_claims),
        "interview_needed": bool(open_items or open_claims),
        "items": items,
    }
    if write:
        yamlio.dump(report, folder / "diff.yaml")
    return report


def format_diff(report: dict) -> str:
    who = f" (profile: {report['person']})" if report.get("person") else ""
    c = report["counts"]
    lines = [f"CV import {report['import']}{who}",
             f"known {c['known']} · new {c['new']} · changed {c['changed']} · claims not yet known "
             f"{c['claims_open']} -> {report['open']} open", ""]
    agenda: list[tuple[str, str, str]] = []
    for item in report["items"]:
        if item["status"] != "known" and "resolution" not in item:
            what = f"{item['status'].upper()} {item['kind']}"
            detail = item["label"] + (f" [{item['match']}]" if item.get("match") else "")
            if item["changes"]:
                detail += " — " + "; ".join(item["changes"])
            agenda.append((item["priority"], item["key"], f"{what:<22} {detail}"))
        for claim in item["claims"]:
            if claim["status"] != "known" and "resolution" not in claim:
                where = f"under {item['match']}" if item.get("match") else f"in {item['key']}"
                numbers = f" (numbers: {', '.join(claim['new_numbers'])})" if claim["new_numbers"] else ""
                agenda.append(("high", claim["key"], f"{claim['status'].upper() + ' claim':<22} {where}: "
                                                     f"\"{claim['text']}\"{numbers}"))
    for level in ("high", "medium", "low"):
        rows = [row for row in agenda if row[0] == level]
        if rows:
            lines.append(level.upper())
            lines += [f"  {key:<20} {text}" for _, key, text in rows]
    if report["interview_needed"]:
        lines += ["", f"-> {report['open']} open item(s): run the sense-making interview on them (skill: import-resume)"]
    else:
        lines += ["-> nothing new: everything in this CV is already in the knowledge base"]
    return "\n".join(lines)


def record_resolution(folder: Path, key: str, how: str, ref: str = "", note: str = "") -> None:
    if how not in ("covered", "dismissed"):
        raise ValueError("resolution must be 'covered' or 'dismissed'")
    meta = yamlio.load(folder / "import.yaml", {}) or {}
    meta.setdefault("resolutions", {})[key] = {"as": how, "ref": ref, "note": note, "date": dt.date.today().isoformat()}
    yamlio.dump(meta, folder / "import.yaml")


def pending(kb: KnowledgeBase | None = None) -> dict:
    """What `status` should nag about: files in the inbox and imports with open items."""
    kb = kb or KnowledgeBase.load()
    result = {"inbox": [p.name for p in inbox_files()], "imports": []}
    for folder in imports():
        if not (folder / "extracted.yaml").exists():
            result["imports"].append({"id": folder.name, "state": "extracted.yaml missing"})
            continue
        try:
            report = diff(folder, kb, write=False)
        except (ValueError, LookupError) as exc:
            result["imports"].append({"id": folder.name, "state": f"error: {exc}"})
            continue
        if report["interview_needed"]:
            result["imports"].append({"id": folder.name, "state": f"{report['open']} open item(s)"})
    return result


# --------------------------------------------------------------- helpers
def _dicts(value: object) -> list[dict]:
    return [v for v in (value or []) if isinstance(v, dict)] if isinstance(value, list) else []


def _texts(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v).strip() for v in value or [] if str(v).strip()] if isinstance(value, list) else []


def _when(item: dict) -> str:
    try:
        return dates.fmt_range(item.get("start"), item.get("end"), "en", "numeric") or (
            dates.fmt(dates.parse(item["date"]), "en", "numeric") if item.get("date") else "")
    except (ValueError, TypeError):
        return ""


def _squash(value: str) -> str:
    return re.sub(r"[\s().\-+/]", "", value.lower())


def _squash_url(value: object) -> str:
    return re.sub(r"^[a-z]+://(www\.)?", "", str(value or "").strip().lower()).rstrip("/")
