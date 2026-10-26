"""
year_rule.py -- Rule-based numeric year extraction for the taste-start tag layer.

JEV answers era WORDS ("최근", "옛날"); explicit numbers ("90년대", "2000년 이후")
are parsed here with regexes because they are exact and free. The recognizer
lets a numeric range win over any JEV era answer.
"""
import re

from django.utils import timezone

_DECADE_4 = re.compile(r'(\d{4})\s*년?\s*대')
_DECADE_2 = re.compile(r'(?<!\d)(\d{2})\s*년대')
_AFTER = re.compile(r'(\d{4})\s*년?\s*(이후|부터|after|since|~)')
_BEFORE = re.compile(r'(\d{4})\s*년?\s*(이전|까지|before)')


def parse_years(text):
    """Return (year_min, year_max) parsed from `text`, or None.

    Either bound may be None (open-ended). Examples:
      "2010년대" -> (2010, 2019); "90년대" -> (1990, 1999);
      "2000년 이후" -> (2000, None); "1950년 이전" -> (None, 1950).
    """
    m = _DECADE_4.search(text)
    if m:
        d = int(m.group(1)) // 10 * 10
        return (d, d + 9)
    m = _DECADE_2.search(text)
    if m:
        d = int(m.group(1))
        d = (1900 if d >= 30 else 2000) + d
        return (d, d + 9)
    m = _AFTER.search(text)
    if m:
        return (int(m.group(1)), None)
    m = _BEFORE.search(text)
    if m:
        return (None, int(m.group(1)))
    return None


def current_year():
    """Current calendar year (evaluated per call, never cached at import)."""
    return timezone.now().year
