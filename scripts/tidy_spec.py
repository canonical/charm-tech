#!/usr/bin/env python3
"""Deterministic tidying for Google-Docs-exported OP spec markdown.

Reads a source `.md` file (the raw Google-Docs export) and writes a
tidied version. By default the output is placed under `../specs/` relative
to this script; the source path is given on the command line so the script
has no hardcoded knowledge of any individual contributor's local layout.

Handles the high-confidence mechanical transformations:
  - Parse the leading markdown-table metadata block (both row-oriented and
    column-oriented layouts) and re-render it as a clean table.
  - Drop the `Authors` row (per team decision).
  - Strip the leading section-anchor ToC, stray leading backticks, etc.
  - Strip `________________` page-break lines.
  - Strip `[a]`, `[b]`, ... `[zz]` footnote markers from prose (but
    not from real `[text](url)` markdown links).
  - Strip the trailing footnote-definition block.
  - Strip the template boilerplate sections "Is it Done?",
    "How to use a spec / is it ready?" and "Spec History". Each is removed
    from its heading up to the next heading at the same or higher level, so
    real content placed after boilerplate in the export (e.g. an "Extended
    Rationale" tab following the Spec History table) is preserved.
  - Collapse consecutive headings with identical text (a Google-Docs tab
    title followed by the section's own heading).
  - Strip `**bold**` wrapping from heading lines and shift heading levels
    down by 1 so the script's own `# OPxxx — Title` is the sole h1.
  - Normalise curly quotes / dashes / ellipses.
  - Collapse runs of blank lines.
  - Redact private codenames using mappings loaded from
    `scripts/redactions.local.json` (gitignored). Matches are case-
    insensitive. If the file is missing, the redaction pass is a no-op.

Usage:
  ./tidy_spec.py <source.md> [<output.md>]
  ./tidy_spec.py --all --src-dir <path-to-exported-OP-folder>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "specs"

FOOTNOTE_MARKER_RE = re.compile(r"\[[a-z]{1,2}\](?!\()")
FOOTNOTE_DEF_RE = re.compile(r"^\[[a-z]{1,2}\]")

BOILERPLATE_HEADINGS = (
    "is it done?",
    "how to use a spec / is it ready?",
    "how to use a spec",
    "spec history",
    "spec history and changelog",
    "spec history and change log",
)

CURLY = {
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "–": "-", "—": "--",
    "…": "...",
    " ": " ",  # nbsp
}

KNOWN_FIELDS = {
    "title", "status", "authors", "author(s)", "author", "type", "created",
    "reviewer(s)", "reviewer", "date",
}

# Fields we keep in the rendered metadata table, in this order.
KEEP_FIELDS = ("Status", "Type", "Created")

SPEC_ID_RE = re.compile(r"OP\d{3,}")

# Several spec IDs have multiple source files because the title was changed
# over the spec's life and Google Docs kept the old copy. We skip the
# superseded copies by filename.
SKIP_FILENAMES = {
    "OP077_-_Charm_library_test_helpers.md",
    "OP077_-_Charm_library_test_mocks.md",
    "OP083_-_Interface_Design_Recommendation.md",
    "OP085_-_Propagate_required_Juju_version_in_charms.md",
    "OP085_-_TBD_Specification_Template.md",
    "OP086_-_Bridge_pytest_and_craft_testing_in_charms.md",
}

# Manual title overrides where the source title reads awkwardly after the
# redaction pass. Keyed by source filename stem.
TITLE_OVERRIDES = {
    "OP075_-_charm_monorepos": "Charm Monorepos",
}

REDACTIONS_PATH = Path(__file__).resolve().parent / "redactions.local.json"


def load_redactions() -> tuple[list[tuple[re.Pattern[str], str]], list[re.Pattern[str]]]:
    """Load (compiled-pattern, replacement) pairs and link-unwrap patterns.

    Returns ([], []) if the local redactions file is absent. All matches
    are case-insensitive.
    """
    if not REDACTIONS_PATH.exists():
        return [], []
    data = json.loads(REDACTIONS_PATH.read_text(encoding="utf-8"))
    repls = []
    for needle, replacement in data.get("replacements", {}).items():
        repls.append(
            (re.compile(rf"\b{re.escape(needle)}\b", re.IGNORECASE), replacement)
        )
    unwraps = []
    for fragment in data.get("unwrap_link_url_contains", []):
        unwraps.append(
            re.compile(
                rf"\[([^\]]+)\]\((?:[^)]*{re.escape(fragment)}[^)]*)\)",
                re.IGNORECASE,
            )
        )
    return repls, unwraps


_REDACTIONS, _LINK_UNWRAPS = load_redactions()


def normalise_chars(text: str) -> str:
    for k, v in CURLY.items():
        text = text.replace(k, v)
    return text


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def unwrap_inline(text: str) -> str:
    """Strip `[text](url)` and `**text**` wrappers, leaving just text."""
    prev = None
    while prev != text:
        prev = text
        text = _LINK_RE.sub(r"\1", text)
        text = _BOLD_RE.sub(r"\1", text)
    return text.strip()


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def parse_metadata_table(lines: list[str]) -> tuple[dict[str, str], int]:
    """Parse the leading markdown table. Returns (meta, lines-consumed).

    Handles both row-oriented (`| **Key** | Value |`) and column-oriented
    (a row of keys followed by a row of values) layouts.
    """
    # Scan forward up to the first markdown table, skipping anything before
    # it (blank lines, stray backticks, leading "rejected"-notice headings,
    # etc.). Cap the search at line 30 so we don't accidentally pick up a
    # table in the body if there's no metadata table at all.
    i = 0
    while i < min(len(lines), 30) and not _TABLE_ROW_RE.match(lines[i]):
        i += 1
    if i >= len(lines) or not _TABLE_ROW_RE.match(lines[i]):
        return {}, 0

    table_start = i
    rows: list[list[str]] = []
    while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
        # Split on `|`, drop leading/trailing empties from the bounding pipes.
        parts = [c.strip() for c in lines[i].split("|")]
        if parts and parts[0] == "":
            parts = parts[1:]
        if parts and parts[-1] == "":
            parts = parts[:-1]
        # Skip the markdown separator row (cells like `---`, `:---:`).
        if parts and all(_SEPARATOR_CELL_RE.match(c) for c in parts if c):
            i += 1
            continue
        rows.append(parts)
        i += 1

    # Unwrap link/bold on every cell, preserving row/column shape.
    plain_rows: list[list[str]] = [
        [unwrap_inline(c) for c in row] for row in rows
    ]

    def canon(name: str) -> str:
        n = name.lower()
        if n in {"author(s)", "author"}:
            return "Authors"
        if n in {"reviewer(s)", "reviewer"}:
            return "Reviewers"
        return name.title()

    def is_known(cell: str) -> bool:
        return cell.lower() in KNOWN_FIELDS

    meta: dict[str, str] = {}
    r = 0
    while r < len(plain_rows):
        row = plain_rows[r]
        non_empty = [c for c in row if c]
        if not non_empty:
            r += 1
            continue
        # Skip rows that only contain the spec ID / "Index" marker.
        if all(SPEC_ID_RE.fullmatch(c) or c.lower() == "index" for c in non_empty):
            r += 1
            continue
        # Row-oriented: first non-empty cell is a known key, remaining cell
        # (if any) is the value.
        known_positions = [i for i, c in enumerate(row) if is_known(c)]
        non_empty_positions = [i for i, c in enumerate(row) if c]
        if (
            len(known_positions) == 1
            and known_positions[0] == non_empty_positions[0]
            and len(non_empty_positions) >= 1
        ):
            key_idx = known_positions[0]
            # Value = the next non-empty cell after the key (if present),
            # otherwise empty.
            val = ""
            for c in row[key_idx + 1:]:
                if c:
                    val = c
                    break
            meta.setdefault(canon(row[key_idx]), val)
            r += 1
            continue
        # Column-oriented header row: ALL non-empty cells are known keys.
        if all(is_known(c) for c in non_empty):
            keys_with_pos = [(i, c) for i, c in enumerate(row) if c]
            # Pair with the next row's values at matching positions.
            if r + 1 < len(plain_rows):
                value_row = plain_rows[r + 1]
                for pos, key in keys_with_pos:
                    val = value_row[pos] if pos < len(value_row) else ""
                    meta.setdefault(canon(key), val)
                r += 2
                continue
        r += 1

    return meta, i


def skip_after_metadata(lines: list[str], start: int) -> int:
    """Skip blank lines, TOC anchor links, and page-break rules after metadata."""
    toc_re = re.compile(r"^[*\-]?\s*\[[^\]]+\]\(#[^)]+\)\s*$")
    page_break_re = re.compile(r"^_{5,}\s*$")
    j = start
    while j < len(lines):
        s = lines[j].strip()
        if s == "" or toc_re.match(s) or page_break_re.match(s):
            j += 1
            continue
        break
    return j


_HEADING_LEVEL_RE = re.compile(r"^(#{1,6})\s+\S")


def heading_level(line: str) -> int | None:
    """Return the heading level (1-6) for a markdown heading line, else None."""
    m = _HEADING_LEVEL_RE.match(line)
    return len(m.group(1)) if m else None


def _heading_text(line: str) -> str:
    """Normalise a heading line to bare lowercase text for matching."""
    s = re.sub(r"^#+\s*", "", line.strip())
    s = unwrap_inline(s)
    s = re.sub(r"\s*\{#[^}]+\}\s*$", "", s)
    return s.lower().rstrip(":")


def strip_boilerplate_sections(text: str) -> str:
    """Remove template boilerplate sections in place.

    A boilerplate section runs from its heading up to the next heading at the
    same or higher level (or end of file). Removing the section rather than
    truncating to EOF preserves real content that the export places after
    boilerplate, such as an "Extended Rationale" tab following the Spec
    History table.
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        level = heading_level(lines[i])
        if level is not None and _heading_text(lines[i]) in BOILERPLATE_HEADINGS:
            i += 1
            while i < len(lines):
                inner = heading_level(lines[i])
                if inner is not None and inner <= level:
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def strip_trailing_footnotes(text: str) -> str:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if FOOTNOTE_DEF_RE.match(line):
            prev_blank = idx == 0 or lines[idx - 1].strip() == ""
            if prev_blank:
                return "\n".join(lines[:idx]).rstrip() + "\n"
    return text


def strip_page_breaks(text: str) -> str:
    return re.sub(r"(?m)^_{5,}\s*$\n?", "", text)


def strip_footnote_markers(text: str) -> str:
    return FOOTNOTE_MARKER_RE.sub("", text)


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_trailing_whitespace(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines())


_ESCAPE_RE = re.compile(r"\\([!\-_=<>*`#.+|()\[\]])")


def unescape_markdown(text: str) -> str:
    """Strip Google-Docs' over-aggressive backslash escapes.

    The export escapes ordinary punctuation that has no special meaning in
    most contexts: `\\!`, `\\-`, `\\=`, `\\_`, `\\>`, etc. Strip them, but
    leave content inside fenced code blocks alone.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
        else:
            out.append(_ESCAPE_RE.sub(r"\1", line))
    return "\n".join(out)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def normalise_headings(text: str) -> str:
    """Strip bold wrapping from heading text and shift levels down by 1.

    `# **Abstract**` -> `## Abstract`; `## Foo` -> `### Foo`.
    The script's own rendered title is the sole `#`.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m = _HEADING_RE.match(line)
        if not m:
            out.append(line)
            continue
        hashes, body = m.group(1), m.group(2)
        body = unwrap_inline(body)
        # Strip Pandoc-style heading attribute `{#anchor}`.
        body = re.sub(r"\s*\{#[^}]+\}\s*$", "", body).strip()
        if not body:
            continue  # drop empty heading lines
        new_level = min(len(hashes) + 1, 6)
        out.append("#" * new_level + " " + body)
    return "\n".join(out)


def collapse_duplicate_headings(text: str) -> str:
    """Drop a heading immediately followed by another heading with identical
    text (only blank lines between). Google-Docs tab titles produce these:
    a tab named "Extended Rationale" precedes the section heading
    "Extended rationale".
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        if heading_level(lines[i]) is not None:
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if (
                j < len(lines)
                and heading_level(lines[j]) is not None
                and _heading_text(lines[i]) == _heading_text(lines[j])
            ):
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def redact(text: str) -> str:
    """Apply redaction mappings loaded from the local config file.

    Unwraps any link whose URL matches a configured fragment (keeping just
    the visible text), then replaces each configured needle with its
    replacement. Case-insensitive. No-op if no config is present.
    """
    for unwrap_re in _LINK_UNWRAPS:
        text = unwrap_re.sub(r"\1", text)
    for pat, repl in _REDACTIONS:
        text = pat.sub(repl, text)
    return text


def metadata_table(spec_id: str, meta: dict[str, str]) -> str:
    rows: list[tuple[str, str]] = []
    for k in KEEP_FIELDS:
        v = meta.get(k, "").strip()
        if v and v.lower() not in {"pending review", "date", "person", "tbd"}:
            rows.append((k, v))
    out = ["| Field | Value |", "| --- | --- |"]
    for k, v in rows:
        out.append(f"| {k} | {v} |")
    return "\n".join(out)


def derive_title_and_id(src_path: Path, meta: dict[str, str]) -> tuple[str, str]:
    name = src_path.stem
    m = SPEC_ID_RE.search(name)
    spec_id = m.group(0) if m else "OP???"
    if name in TITLE_OVERRIDES:
        return spec_id, TITLE_OVERRIDES[name]
    title = meta.get("Title", "").strip()
    placeholder_titles = {
        "title", spec_id.lower(), "specification template", "tbd",
        "tbd specification template",
    }
    if not title or title.lower() in placeholder_titles:
        bare = re.sub(r"^OP\d+_-_", "", name).replace("_", " ").strip()
        title = bare
    title = unwrap_inline(normalise_chars(title))
    title = redact(title)
    return spec_id, title


def tidy(src_text: str, src_path: Path) -> tuple[str, str]:
    text = src_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.lstrip("﻿")  # BOM
    text = normalise_chars(text)

    lines = text.split("\n")
    meta, consumed = parse_metadata_table(lines)
    body_start = skip_after_metadata(lines, consumed)
    body = "\n".join(lines[body_start:])

    spec_id, title = derive_title_and_id(src_path, meta)

    body = strip_page_breaks(body)
    body = strip_trailing_footnotes(body)
    body = strip_boilerplate_sections(body)
    body = strip_footnote_markers(body)
    body = normalise_headings(body)
    body = collapse_duplicate_headings(body)
    body = unescape_markdown(body)
    body = redact(body)
    body = strip_trailing_whitespace(collapse_blank_lines(body)).strip() + "\n"

    meta = {k: redact(strip_footnote_markers(v)).strip() for k, v in meta.items()}
    header = f"# {spec_id} — {title}\n\n{metadata_table(spec_id, meta)}\n\n"
    out = header + body
    fname = f"{spec_id}-{slugify(title)}.md"
    return out, fname


def process_one(src: Path, out_dir: Path) -> Path:
    text = src.read_text(encoding="utf-8")
    tidied, fname = tidy(text, src)
    out_path = out_dir / fname
    out_path.write_text(tidied, encoding="utf-8")
    return out_path


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("source", nargs="?", help="Source .md file")
    p.add_argument("output", nargs="?", help="Output .md file")
    p.add_argument("--all", action="store_true", help="Process every OP*.md in --src-dir")
    p.add_argument("--src-dir", help="Directory of exported OP*.md files (required with --all)")
    p.add_argument("--out-dir", default=str(OUT_DIR))
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        if not args.src_dir:
            p.error("--all requires --src-dir")
        srcs = sorted(Path(args.src_dir).glob("OP*.md"))
        for s in srcs:
            if s.name in SKIP_FILENAMES:
                print(f"SKIP (superseded) {s.name}")
                continue
            try:
                out = process_one(s, out_dir)
                print(f"{s.name} -> {out.name}")
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {s.name}: {e}", file=sys.stderr)
        return 0

    if not args.source:
        p.error("source or --all required")
    src = Path(args.source)
    if args.output:
        text = src.read_text(encoding="utf-8")
        tidied, _ = tidy(text, src)
        Path(args.output).write_text(tidied, encoding="utf-8")
        print(args.output)
    else:
        out = process_one(src, out_dir)
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
