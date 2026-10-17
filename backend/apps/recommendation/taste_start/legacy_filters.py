"""
legacy_filters.py -- Best-effort conversion of OLD Gemini-era board filters to tags.

Anything without a clean mapping (location_city, image_focus, unknown values,
junk types) is dropped. Never raises.
"""
from . import vocab
from .normalization import COUNTRY_ALIASES, MATERIAL_GROUP_MAP
from .recognizer import make_tag

_MIN_YEAR, _MAX_YEAR = 1800, 2100


def _ci_lookup(table, raw):
    """Case-insensitive exact vocab key lookup; None if no match."""
    if not isinstance(raw, str):
        return None
    low = raw.strip().lower()
    for key in table:
        if key.lower() == low:
            return key
    return None


def _as_list(raw):
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [raw] if raw is not None else []


def _is_year(v):
    return isinstance(v, int) and not isinstance(v, bool) and _MIN_YEAR <= v <= _MAX_YEAR


def _country(raw):
    if not isinstance(raw, str):
        return None
    hit = _ci_lookup(vocab.COUNTRY, raw)
    if hit:
        return hit
    low = raw.strip().lower()
    for canonical, aliases in COUNTRY_ALIASES.items():
        if any(a.lower() == low for a in aliases):
            return canonical
    return None


def _use_tag(filters):
    typ = _ci_lookup(vocab.TYPOLOGY, filters.get('typology_primary'))
    if typ:
        return make_tag('use', typ, kind='typology')
    prog = filters.get('program')
    hit = _ci_lookup(vocab.PROGRAM, prog)
    if hit:
        return make_tag('use', hit, kind='program')
    hit = _ci_lookup(vocab.TYPOLOGY, prog)
    if hit:
        return make_tag('use', hit, kind='typology')
    return None


def filters_to_tags(filters):
    """Old filters dict -> list[Tag] (all polarity 'want'); unmappable parts dropped."""
    if not isinstance(filters, dict):
        return []
    pairs = []   # (axis, value) in a stable order

    def add(axis, value):
        if value is not None and (axis, value) not in pairs:
            pairs.append((axis, value))

    try:
        use = _use_tag(filters)
        if use is not None:
            kind = 'typology' if 'typology_primary' in use.match else 'program'
            add_use = (use, kind)
        else:
            add_use = None

        for raw in _as_list(filters.get('style')):
            v = _ci_lookup(vocab.STYLE, raw)
            add('style', v)
        for raw in _as_list(filters.get('atmosphere')):
            v = _ci_lookup(vocab.ATMOSPHERE, raw)
            add('atmosphere', v)
        for raw in _as_list(filters.get('color_tone')):
            v = _ci_lookup(vocab.COLOR, raw)
            # Warm colour merges into the atmosphere Warm tag (step-1 rule).
            add('atmosphere' if v == 'Warm' else 'color', v)
        for raw in _as_list(filters.get('architectural_elements')):
            add('element', _ci_lookup(vocab.ELEMENT, raw))
        for raw in _as_list(filters.get('material')):
            group = MATERIAL_GROUP_MAP.get(raw.strip().lower()) if isinstance(raw, str) else None
            add('material', group if group in vocab.MATERIAL else None)
        add('country', _country(filters.get('location_country')))

        lo, hi = filters.get('year_min'), filters.get('year_max')
        if (lo is not None or hi is not None) and all(v is None or _is_year(v) for v in (lo, hi)):
            if lo is None or hi is None or lo <= hi:
                add('year', (lo, hi))

        # Industrial style/atmosphere -> one style Industrial tag.
        if ('atmosphere', 'Industrial') in pairs:
            pairs.remove(('atmosphere', 'Industrial'))
            if ('style', 'Industrial') not in pairs:
                pairs.append(('style', 'Industrial'))

        tags = [make_tag(axis, value) for axis, value in pairs]
        if add_use is not None:
            tags.insert(0, add_use[0])
        # Single-value axes keep only the first want tag.
        seen, out = set(), []
        for t in tags:
            if t.axis in ('style', 'atmosphere', 'color', 'country', 'year', 'use'):
                if t.axis in seen:
                    continue
                seen.add(t.axis)
            out.append(t)
        return out
    except Exception:   # noqa: BLE001 -- junk input must never break board loading
        return []
