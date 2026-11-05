"""LaTeX escaping and the small inline markup allowed in cv.yaml: **bold**, *italic*, [label](url)."""
from __future__ import annotations

import re

_CHAR_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"$\sim$", "^": r"\^{}", "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}",
    "→": r"$\rightarrow$", "←": r"$\leftarrow$", "↑": r"$\uparrow$", "↓": r"$\downarrow$",
    "≈": r"$\approx$", "≥": r"$\geq$", "≤": r"$\leq$", "×": r"$\times$", "±": r"$\pm$",
    "•": r"\textbullet{}", "…": r"\ldots{}", " ": "~", " ": r"\,", " ": r"\,",
}
_MARKUP = re.compile(
    r"\[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|\*(?P<ital>[^*\s][^*]*?)\*"
)
_QUOTED = re.compile(r'"([^"]*)"')


def escape(text: object) -> str:
    """Escape plain text for LaTeX (no markup handling)."""
    s = "".join(_CHAR_MAP.get(ch, ch) for ch in str(text))
    s = s.replace("...", r"\ldots{}")
    s = re.sub(r"(?<=\s)-(?=\s)", "--", s)  # spaced hyphen -> en dash
    s = _QUOTED.sub(r"``\1''", s)
    return s.replace('"', "''")


def markup(text: object) -> str:
    """Escape text and convert **bold**, *italic* and [label](url)."""
    text = str(text)
    out: list[str] = []
    pos = 0
    for m in _MARKUP.finditer(text):
        out.append(escape(text[pos:m.start()]))
        if m.group("label") is not None:
            out.append(rf"\href{{{url(m.group('url'))}}}{{{markup(m.group('label'))}}}")
        elif m.group("bold") is not None:
            out.append(rf"\textbf{{{markup(m.group('bold'))}}}")
        else:
            out.append(rf"\textit{{{markup(m.group('ital'))}}}")
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out)


def url(value: object) -> str:
    """Escape a URL for use as the first argument of \\href (safe inside other macro arguments)."""
    u = str(value).strip().replace("\\", "/").replace("{", "%7B").replace("}", "%7D")
    # hyperref turns \% \# \& back into the plain characters in the link target; unescaped they
    # break macro arguments (%, #) and table cells (&)
    return u.replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


def strip_markup(text: object) -> str:
    """Plain text with the inline markup removed (for checks and plain-text exports)."""
    s = re.sub(r"\[([^\]]+)\]\([^)\s]+\)", r"\1", str(text))
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    return re.sub(r"\*([^*\s][^*]*?)\*", r"\1", s)


def _supported(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x20 <= cp <= 0x7E
        or 0xA0 <= cp <= 0x17F  # Latin-1 + Latin Extended-A (Polish, Czech, German, ...)
        or 0x218 <= cp <= 0x21B  # Romanian comma-below letters
        or 0x2010 <= cp <= 0x2027  # dashes, quotes, bullet, ellipsis
        or cp in (0x20AC, 0x2122, 0x2030, 0x2032, 0x2033)  # euro, trade mark, per mille, primes
        or ch in _CHAR_MAP
        or ch in "\n\t"
    )


def unsupported_chars(text: object) -> set[str]:
    """Characters likely to fail or vanish under pdfLaTeX with T1 fonts (emoji, CJK, Cyrillic...)."""
    return {ch for ch in str(text) if not _supported(ch)}
