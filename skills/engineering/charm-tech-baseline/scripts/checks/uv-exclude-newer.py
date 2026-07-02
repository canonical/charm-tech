#!/usr/bin/env python3
"""Check: pyproject.toml sets `[tool.uv].exclude-newer` to a rolling
quarantine of at least 7 days.

Rationale (Canonical Security "How-To: Secure a repo" — Minimum
release age section): a package-manager-level cooldown protects
every dep-resolution path (manual `uv add`, `uv lock` regens, uvx
bootstraps, CI re-resolves) that Dependabot cooldown alone doesn't
cover — Dependabot cooldown only affects PRs Dependabot itself opens.

uv's `exclude-newer` accepts three formats per the docs:
  - RFC 3339 timestamps (absolute snapshot; e.g. 2026-01-01T00:00:00Z)
  - Friendly durations (rolling window; e.g. "7 days", "1 week")
  - ISO 8601 durations (rolling window; e.g. "P7D", "P30D")

Prefer a rolling window ("7 days" / "P7D"). Absolute timestamps also
accepted but flagged in evidence: they freeze resolution to a moment
and drift silently as they age.

Tier coverage: all tiers.
`na` when there's no `pyproject.toml`, no `[tool.uv]`, or (for tiers
where uv isn't in use) no `uv.lock`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "uv-exclude-newer"
APPLIES = "product,canonical,personal"
MIN_DAYS = 7


def parse_days(v: str):
    """Classify the value:
      RFC3339 timestamp: contains 'T' and ends with 'Z' or timezone offset.
      ISO 8601 duration: matches /^P(?:\\d+[YMWD])+(?:T(?:\\d+[HMS])+)?$/ or PT...
      Friendly duration: matches a number + unit word (hours/days/weeks/etc.)
    """
    v = v.strip()
    # RFC 3339 timestamp
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', v):
        return ("snapshot", None)
    # ISO 8601 duration
    m = re.match(r'^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$', v)
    if m:
        y, mo, w, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
        # Approx: month=30d, year=365d.
        days = y*365 + mo*30 + w*7 + d + h/24 + mi/1440 + s/86400
        return ("iso8601", days)
    # Friendly duration: parse "N unit" tokens; sum in days.
    unit_days = {
        "second": 1/86400, "seconds": 1/86400, "sec": 1/86400, "s": 1/86400,
        "minute": 1/1440, "minutes": 1/1440, "min": 1/1440, "m": 1/1440,
        "hour": 1/24, "hours": 1/24, "hr": 1/24, "hrs": 1/24, "h": 1/24,
        "day": 1, "days": 1, "d": 1,
        "week": 7, "weeks": 7, "w": 7,
        "month": 30, "months": 30, "mon": 30, "mo": 30,
        "year": 365, "years": 365, "yr": 365, "y": 365,
    }
    total = 0.0
    matched = False
    for num, unit in re.findall(r'(\d+(?:\.\d+)?)\s*([A-Za-z]+)', v):
        u = unit.lower().rstrip('.')
        if u not in unit_days:
            return ("unknown", None)
        total += float(num) * unit_days[u]
        matched = True
    if matched:
        return ("friendly", total)
    return ("unknown", None)


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    if not Path("pyproject.toml").is_file():
        emit_check(CHECK_ID, "na", "No pyproject.toml — not a uv project.")
        return EXIT_NA

    # Parse [tool.uv] and inspect exclude-newer. Needs python3+tomllib
    # (stdlib in 3.11+) — fall back to a text-only presence check when the
    # parser isn't available.
    try:
        import tomllib
        have_parser = True
    except ImportError:
        have_parser = False

    if not have_parser:
        # Fallback: presence check on `exclude-newer` inside `[tool.uv]`.
        # This is intentionally cheap; agents on hosts without Python 3.11+
        # can still get a signal.
        text = Path("pyproject.toml").read_text(errors="replace")
        if re.search(r'^\s*exclude-newer\s*=', text, re.MULTILINE) and \
           re.search(r'^\[tool\.uv\]', text, re.MULTILINE):
            emit_check(
                CHECK_ID, "pass",
                "exclude-newer present in pyproject.toml (value not validated — python3+tomllib unavailable).",
                {"parser": False, "exclude_newer_present": True},
            )
            return EXIT_PASS
        emit_check(
            CHECK_ID, "fail",
            "No exclude-newer found under [tool.uv] in pyproject.toml (unvalidated fallback).",
            {"parser": False, "exclude_newer_present": False},
            {"kind": "judgement", "human_review": "Add `exclude-newer = \"7 days\"` under [tool.uv] in pyproject.toml. Prefer a friendly-duration string (rolling window) over an RFC 3339 timestamp (absolute snapshot). See Canonical Security \"How-To: Secure a repo\" — Minimum release age."},
        )
        return EXIT_FAIL

    try:
        with open("pyproject.toml", "rb") as f:
            doc = tomllib.load(f)
    except Exception as e:
        emit_check(
            CHECK_ID, "unknown",
            f"Could not parse pyproject.toml: {e}",
            {"parser": True},
        )
        return EXIT_UNKNOWN

    tool_uv = (doc.get("tool") or {}).get("uv")
    if tool_uv is None:
        # A uv.lock in the working tree means the project uses uv even
        # though pyproject.toml doesn't declare [tool.uv] yet — that's
        # a fail (add the section), not na.
        if Path("uv.lock").is_file():
            emit_check(
                CHECK_ID, "fail",
                f"uv.lock present but pyproject.toml has no [tool.uv] section. Add [tool.uv] with exclude-newer = \"{MIN_DAYS} days\".",
                {"parser": True, "tool_uv": False, "uv_lock_present": True},
                {"kind": "judgement", "human_review": "Add [tool.uv] to pyproject.toml with `exclude-newer = \"7 days\"`. This gives every uv resolution path (manual uv add, uv lock regens, uvx bootstraps, CI re-resolves) a rolling 7-day quarantine on fresh releases — complementing the Dependabot cooldown that only covers Dependabot-authored PRs. See Canonical Security \"How-To: Secure a repo\" — Minimum release age."},
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "na",
            "pyproject.toml has no [tool.uv] section and no uv.lock — not a uv-configured project.",
            {"parser": True, "tool_uv": False, "uv_lock_present": False},
        )
        return EXIT_NA

    if "exclude-newer" not in tool_uv:
        emit_check(
            CHECK_ID, "fail",
            f"[tool.uv] present but exclude-newer not set. Add exclude-newer = \"{MIN_DAYS} days\" to give every uv resolution path (manual uv add, uv lock, uvx, CI re-resolves) a rolling {MIN_DAYS}-day quarantine on fresh releases.",
            {"parser": True, "tool_uv": True, "exclude_newer_present": False},
            {"kind": "judgement", "human_review": "Add `exclude-newer = \"7 days\"` under [tool.uv] in pyproject.toml. Prefer a friendly-duration string (rolling window) over an RFC 3339 timestamp (absolute snapshot). See Canonical Security \"How-To: Secure a repo\" — Minimum release age."},
        )
        return EXIT_FAIL

    value = tool_uv["exclude-newer"]
    if not isinstance(value, str):
        emit_check(
            CHECK_ID, "fail",
            f"[tool.uv].exclude-newer is not a string: {type(value).__name__} {value!r}",
            {"parser": True},
            {"kind": "judgement", "human_review": "Set exclude-newer to a string, e.g. \"7 days\"."},
        )
        return EXIT_FAIL

    kind, days = parse_days(value)

    evidence = {
        "parser": True,
        "exclude_newer_kind": kind,
        "exclude_newer_value": value,
        "exclude_newer_days": days,
    }

    if kind == "snapshot":
        emit_check(
            CHECK_ID, "pass",
            f"exclude-newer set to an RFC 3339 timestamp (absolute snapshot). Accepted but note: this freezes resolution to a moment and drifts silently as time passes; prefer a rolling friendly-duration like \"{MIN_DAYS} days\".",
            evidence,
        )
        return EXIT_PASS

    if kind in ("iso8601", "friendly"):
        days_int = int(days) if days is not None else 0
        if days_int >= MIN_DAYS:
            emit_check(
                CHECK_ID, "pass",
                f"exclude-newer = '{value}' ({kind}, ≈{days} days). Rolling ≥{MIN_DAYS}-day quarantine.",
                evidence,
            )
            return EXIT_PASS
        emit_check(
            CHECK_ID, "fail",
            f"exclude-newer = '{value}' ({kind}, ≈{days} days) is below the {MIN_DAYS}-day baseline.",
            evidence,
            {"kind": "judgement", "human_review": "Widen exclude-newer to at least \"7 days\" to match the Charm Tech baseline and the existing Dependabot cooldown."},
        )
        return EXIT_FAIL

    # unknown
    emit_check(
        CHECK_ID, "fail",
        f"exclude-newer = '{value}' did not parse as an RFC 3339 timestamp, ISO 8601 duration, or friendly duration.",
        evidence,
        {"kind": "judgement", "human_review": "Set exclude-newer to a friendly duration like \"7 days\" per the uv docs."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
