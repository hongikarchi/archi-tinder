"""Report staleness signature (FULL-REPORT-UI-1).

The persona report (`Project.final_report`) is generated from a board's liked
buildings. To know whether it is out of date WITHOUT a schema change (the
runtime DB role has no DDL), the report dict carries a `source_signature`: a
short digest of the liked building ids it was generated from. The board is
"stale" when the current liked ids no longer hash to that value.

Kept dependency-free so both serializers and views can import it.
"""
import hashlib


def liked_ids_of(entries):
    """Building id strings of a liked_ids list; tolerates dict + legacy str entries."""
    ids = []
    for entry in (entries or []):
        if isinstance(entry, str):
            ids.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get('id'), str):
            ids.append(entry['id'])
    return ids


def liked_signature(liked_ids):
    """Stable 16-hex digest of the SORTED set of liked building ids.

    Accepts raw liked_ids entries (dict / legacy str) or plain id strings.
    Order- and duplicate-independent.
    """
    ids = sorted(set(liked_ids_of(liked_ids)))
    return hashlib.sha1('\n'.join(ids).encode('utf-8')).hexdigest()[:16]


def is_report_stale(final_report, liked_ids):
    """True iff the report is a dict carrying a signature that differs from now."""
    if not isinstance(final_report, dict):
        return False
    stored = final_report.get('source_signature')
    if not stored:
        return False
    return stored != liked_signature(liked_ids)
