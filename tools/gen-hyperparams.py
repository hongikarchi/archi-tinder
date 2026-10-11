#!/usr/bin/env python
"""tools/gen-hyperparams.py — generate docs/algorithm-hyperparameters.md from code.

The recommendation hyperparameters live in ONE place: the ``RECOMMENDATION`` dict in
``backend/config/settings.py``. This script renders that dict as a Markdown table so
the documentation can never drift from the values the app actually runs with
(Product Constitution principle 6: values = code is the source of truth; design
intent = ``docs/algorithm.md``).

Meaning text comes from the code itself: the inline ``# comment`` on a key's line is
its description, and the nearest preceding comment block (``# ...`` lines directly
above a key, or above the group it belongs to) is its group note. Document a
parameter by commenting it in settings.py — not by editing the generated file.

Usage:
    python tools/gen-hyperparams.py            # rewrite docs/algorithm-hyperparameters.md
    python tools/gen-hyperparams.py --check    # exit 1 if the committed file is stale (CI)
    python tools/gen-hyperparams.py --stdout   # print to stdout

Parsing is static (``ast``), so values that are expressions (e.g. ``os.getenv(...)``)
are shown as their source text with an ``env`` marker instead of a resolved value.
No Django import, no DB, no network — safe in CI.
"""
from __future__ import annotations

import argparse
import ast
import io
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / "backend" / "config" / "settings.py"
OUT = REPO / "docs" / "algorithm-hyperparameters.md"

# Key-prefix -> group label. Order matters (first match wins). Keys that match
# nothing fall into "Core swipe loop".
GROUPS = [
    ("taste_pool_", "Promote-to-taste pool (Discovery → Taste)"),
    ("discovery_", "Discovery feed (v3.x)"),
    ("llm_search_", "LLM search ranking (LLM-SEARCH-RANK-1)"),
    ("report_", "Persona report grounding (BACK-LLM-5)"),
    ("axis_", "Persona axis scores"),
    ("hyde_", "HyDE V_initial (Topic 03)"),
    ("hybrid_", "Hybrid retrieval RRF (Topic 01)"),
    ("dpp_", "DPP top-K diversity (Topic 04b)"),
    ("mmr_lambda_", "MMR λ ramp (Topic 04a)"),
    ("adaptive_k_", "Adaptive clustering (Topic 06)"),
    ("soft_relevance", "Adaptive clustering (Topic 06)"),
    ("gemini_rerank", "Gemini rerank (Topic 02)"),
    ("pool_", "Embedding cache (IMP-7)"),
    ("async_prefetch", "Async prefetch (IMP-8)"),
    ("card_cache", "Card cache"),
    ("corpus_df_", "LLM search ranking (LLM-SEARCH-RANK-1)"),
    ("context_caching", "Gemini context caching (IMP-5)"),
    ("stage_decouple", "Parse 2-stage decouple (IMP-6)"),
]
DEFAULT_GROUP = "Core swipe loop (Phases 0–3)"


def group_for(key: str) -> str:
    for prefix, label in GROUPS:
        if key.startswith(prefix):
            return label
    return DEFAULT_GROUP


def find_dict(tree: ast.Module) -> ast.Dict:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "RECOMMENDATION" and isinstance(node.value, ast.Dict):
                    return node.value
    raise SystemExit("RECOMMENDATION dict not found in settings.py")


def inline_comments(source: str) -> dict[int, str]:
    """line number -> trailing comment text (without the leading #)."""
    out: dict[int, str] = {}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            line = tok.start[0]
            # a comment that starts a line is a block comment, not an inline one
            prefix = source.splitlines()[line - 1][: tok.start[1]]
            if prefix.strip():
                out[line] = tok.string.lstrip("#").strip()
    return out


def block_comment_above(lines: list[str], lineno: int) -> str:
    """Comment-only lines directly above `lineno` (1-based), joined."""
    buf: list[str] = []
    i = lineno - 2
    while i >= 0 and lines[i].strip().startswith("#"):
        buf.insert(0, lines[i].strip().lstrip("#").strip())
        i -= 1
    return " ".join(buf)


def render_value(node: ast.AST, source: str) -> tuple[str, str]:
    """-> (value text, type label)."""
    try:
        val = ast.literal_eval(node)
    except Exception:
        src = ast.get_source_segment(source, node) or "<expr>"
        env = "env" if "getenv" in src else "expr"
        return f"`{src}`", env
    if isinstance(val, bool):
        return str(val), "bool"
    if isinstance(val, int):
        return str(val), "int"
    if isinstance(val, float):
        return repr(val), "float"
    if isinstance(val, str):
        return f"`{val}`", "str"
    if isinstance(val, dict):
        parts = ", ".join(f"{k}: {v}" for k, v in val.items())
        return f"`{{{parts}}}`", "dict"
    if isinstance(val, (list, tuple)):
        return f"`{list(val)!r}`", "list"
    return repr(val), type(val).__name__


def build() -> str:
    source = SETTINGS.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    d = find_dict(tree)
    comments = inline_comments(source)

    rows: list[dict] = []
    last_block = ""
    for k, v in zip(d.keys, d.values):
        if not isinstance(k, ast.Constant):
            continue
        key = str(k.value)
        block = block_comment_above(lines, k.lineno)
        if block:
            last_block = block
        meaning = comments.get(k.lineno) or comments.get(v.end_lineno or k.lineno, "")
        if not meaning and block:
            meaning = block
        value, typ = render_value(v, source)
        rows.append({
            "key": key, "value": value, "type": typ,
            "group": group_for(key), "meaning": meaning.replace("|", "\\|"),
            "block": last_block,
        })

    by_group: dict[str, list[dict]] = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    # keep groups in first-appearance order
    order = []
    for r in rows:
        if r["group"] not in order:
            order.append(r["group"])

    out: list[str] = []
    out.append("# Recommendation hyperparameters — production values")
    out.append("")
    out.append("<!-- GENERATED FILE — DO NOT EDIT. Source: backend/config/settings.py RECOMMENDATION dict. -->")
    out.append("<!-- Regenerate: python tools/gen-hyperparams.py   (CI fails if this file is stale) -->")
    out.append("")
    out.append(f"Generated from `backend/config/settings.py` `RECOMMENDATION` — **{len(rows)} parameters**.")
    out.append("Values here are what production runs with (environment overrides are marked `env`).")
    out.append("The *meaning* column is the inline comment on each key in `settings.py`; to document a")
    out.append("parameter, comment it there. Design intent and phase semantics: `docs/algorithm.md`.")
    out.append("")
    for g in order:
        out.append(f"## {g}")
        out.append("")
        out.append("| Key | Value | Type | Meaning (from code comment) |")
        out.append("|---|---|---|---|")
        for r in by_group[g]:
            out.append(f"| `{r['key']}` | {r['value']} | {r['type']} | {r['meaning']} |")
        out.append("")
    undocumented = [r["key"] for r in rows if not r["meaning"]]
    out.append("## Undocumented keys")
    out.append("")
    if undocumented:
        out.append("These keys have no comment in `settings.py` — add one next to the key:")
        out.append("")
        for k in undocumented:
            out.append(f"- `{k}`")
    else:
        out.append("None — every key carries a comment in `settings.py`.")
    out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if docs/algorithm-hyperparameters.md is stale")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args()
    text = build()
    if args.stdout:
        sys.stdout.write(text)
        return 0
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.stderr.write(
                f"{OUT.relative_to(REPO)} is stale relative to settings.py RECOMMENDATION. "
                "Run: python tools/gen-hyperparams.py\n"
            )
            return 1
        print(f"{OUT.relative_to(REPO)} up to date ({text.count(chr(10))} lines)")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
