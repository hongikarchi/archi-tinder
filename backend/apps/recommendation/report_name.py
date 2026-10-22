"""Board-name-follows-persona rule (FULL-REPORT-UI-1). Pure, no DB.

A board's default name is a copy of the LLM persona name made at save time.
When the report is regenerated the board name follows the new persona name
UNLESS the user renamed it. "Not renamed" == the current name still equals the
OLD report's persona name in any form (flat / i18n.ko / i18n.en).
"""

NAME_MAX_LENGTH = 200  # Project.name max_length


def _persona_names(report):
    """All persona_type strings (stripped, non-empty) found in a report dict."""
    if not isinstance(report, dict):
        return set()
    candidates = [report.get('persona_type')]
    i18n = report.get('i18n')
    if isinstance(i18n, dict):
        for lang in ('ko', 'en'):
            block = i18n.get(lang)
            if isinstance(block, dict):
                candidates.append(block.get('persona_type'))
    return {c.strip() for c in candidates if isinstance(c, str) and c.strip()}


def _new_persona_name(report, language):
    if not isinstance(report, dict):
        return ''
    i18n = report.get('i18n')
    block = i18n.get(language) if isinstance(i18n, dict) else None
    if isinstance(block, dict) and isinstance(block.get('persona_type'), str) \
            and block['persona_type'].strip():
        return block['persona_type'].strip()
    flat = report.get('persona_type')
    return flat.strip() if isinstance(flat, str) else ''


def followed_board_name(current_name, old_report, new_report, language='ko'):
    """Return the new board name, or None when the name must stay untouched."""
    current = (current_name or '').strip()
    if not current:
        return None
    if current not in _persona_names(old_report):
        return None
    new_name = _new_persona_name(new_report, language or 'ko')[:NAME_MAX_LENGTH]
    if not new_name or new_name == current_name:
        return None
    return new_name
