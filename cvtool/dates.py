"""CV dates: parse YYYY / YYYY-MM / 'present' and format them the same way everywhere in a CV."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

PRESENT_WORDS = {
    "present", "now", "current", "ongoing", "today",
    "obecnie", "teraz", "nadal", "heute", "aktuell", "actualidad", "aujourd'hui", "oggi",
}

MONTHS = {
    "en": {
        "short": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "long": ["January", "February", "March", "April", "May", "June", "July", "August",
                 "September", "October", "November", "December"],
    },
    "pl": {
        "short": ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"],
        "long": ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień",
                 "wrzesień", "październik", "listopad", "grudzień"],
    },
    "de": {
        "short": ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
        "long": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
                 "Oktober", "November", "Dezember"],
    },
}
PRESENT = {"en": "Present", "pl": "obecnie", "de": "heute", "fr": "aujourd'hui", "es": "actualidad", "it": "oggi"}
NUMERIC_SEPARATOR = {"en": "/", "de": "/"}
STYLES = ("short", "long", "numeric", "year")


@dataclass(frozen=True)
class CvDate:
    year: int
    month: int = 0  # 0 = month not known
    present: bool = False

    def sort_key(self) -> tuple[int, int]:
        return (9999, 12) if self.present else (self.year, self.month)


def parse(value: object) -> CvDate | None:
    """Accepts 2021, '2021', '2021-03', '2021-03-15', '03.2021', date objects and 'present'."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.date):
        return CvDate(value.year, value.month)
    if isinstance(value, int) and not isinstance(value, bool):
        return CvDate(value)
    text = str(value).strip().lower()
    if text in PRESENT_WORDS:
        return CvDate(9999, 12, present=True)
    m = re.fullmatch(r"(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.]\d{1,2})?", text)
    if m:
        year, month = int(m.group(1)), int(m.group(2) or 0)
    else:
        m = re.fullmatch(r"(\d{1,2})[-/.](\d{4})", text)
        if not m:
            raise ValueError(f"unrecognised date {value!r}: use YYYY, YYYY-MM or 'present'")
        month, year = int(m.group(1)), int(m.group(2))
    if not 0 <= month <= 12:
        raise ValueError(f"month out of range in {value!r}")
    return CvDate(year, month)


def default_style(lang: str) -> str:
    return "short" if lang.startswith("en") else "numeric"


def fmt(d: CvDate, lang: str = "en", style: str | None = None) -> str:
    lang = lang.split("-")[0]
    style = style or default_style(lang)
    if d.present:
        return PRESENT.get(lang, PRESENT["en"])
    if style == "year" or d.month == 0:
        return str(d.year)
    if style == "numeric":
        return f"{d.month:02d}{NUMERIC_SEPARATOR.get(lang, '.')}{d.year}"
    names = MONTHS.get(lang, MONTHS["en"])["long" if style == "long" else "short"]
    return f"{names[d.month - 1]} {d.year}"


def fmt_range(start: object, end: object, lang: str = "en", style: str | None = None) -> str:
    """'Mar 2021 – Present', or a single date when only one end is known."""
    s, e = parse(start), parse(end)
    if s and e:
        if s == e:
            return fmt(s, lang, style)
        return f"{fmt(s, lang, style)} – {fmt(e, lang, style)}"
    one = s or e
    return fmt(one, lang, style) if one else ""
