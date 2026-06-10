"""
Utility helpers — date formatting, Arabic text utilities, response builders.
"""
from __future__ import annotations

import re
from datetime import date, datetime


def format_arabic_date(d: date | datetime) -> str:
    """Return a human-readable Arabic date string."""
    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
    ]
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.day} {months_ar[d.month - 1]} {d.year}"


def arabic_numerals(text: str) -> str:
    """Convert Western digits to Arabic-Indic digits."""
    mapping = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    return text.translate(mapping)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def truncate(text: str, max_len: int = 200, suffix: str = "...") -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix
