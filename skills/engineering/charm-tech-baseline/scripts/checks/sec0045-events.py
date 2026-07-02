#!/usr/bin/env python3
"""Check: SEC0045 Security Event Logging — heuristic.
Tier coverage: product only.

Applicability is per-product (see references/decisions.md). Where the
per-product disposition is settled we short-circuit. For other products we
look for evidence the OWASP Application Logging Vocabulary has been
adopted — either by name reference (OWASP / owasp-logger / securitylog) or
by emitted event-name tokens (authn_*, authz_*, sys_*, user_created/updated,
excessive_use, malicious_*, input_validation_*).

Output is informational: a pass means evidence exists, NOT that the events
match the doc's required set. A fail means the agent should confirm whether
the product genuinely has no auth/admin/user surface, or whether logging is
missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS,
    cd_repo_root, emit_check, origin_url, parse_tier, tier_applies,
)

CHECK_ID = "sec0045-events"
APPLIES = "product"

NAMED_RE = re.compile(r"OWASP|owasp-logger|securitylog|security_event|security-event")
OWASP_RE = re.compile(
    r"authn_(login|password|token|impersonation|create|sso|2fa)_(succ|fail|change|created|revoked|expired|lock|use|unlock)"
    r"|authz_(fail|change|admin|impersonation)"
    r"|excessive_use"
    r"|input_validation_(fail)"
    r"|malicious_(direct_reference|attack_tool|cors|excess_use)"
    r"|sys_(startup|shutdown|restart|crash|monitor_disabled|monitor_enabled|config_change)"
    r"|user_(created|updated|deleted|archived|suspended)"
    r"|session_(created|expired|use_after_expire|hijacked|renewed)"
)


def find_matches(pattern: re.Pattern[str], max_hits: int = 5) -> list[str]:
    hits: list[str] = []
    for ext in ("*.go", "*.py"):
        for p in Path(".").rglob(ext):
            if not p.is_file():
                continue
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            if pattern.search(text):
                # strip leading ./ to match grep -rEl output shape
                s = str(p)
                if not s.startswith("./") and not s.startswith("/"):
                    s = "./" + s
                hits.append(s)
                if len(hits) >= max_hits:
                    return hits
    return hits


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    url = origin_url()
    slug = url[len("https://github.com/"):] if url.startswith("https://github.com/") else url

    if slug == "canonical/operator":
        emit_check(CHECK_ID, "pass", "SEC0045 done long ago via canonical/operator#1905.")
        return EXIT_PASS
    if slug in ("canonical/jubilant", "canonical/pytest-jubilant"):
        emit_check(CHECK_ID, "na", "Out of scope: no user/admin/auth surface.")
        return EXIT_NA
    if slug == "canonical/charmlibs":
        emit_check(CHECK_ID, "na", "Applicable but deferred to a future cycle.")
        return EXIT_NA

    named_evidence = find_matches(NAMED_RE)
    token_evidence = find_matches(OWASP_RE)

    if token_evidence:
        found = ",".join(token_evidence)
        emit_check(
            CHECK_ID, "pass",
            "Code emits OWASP Application Logging Vocabulary event tokens.",
            {"evidence_files": found, "signal": "event-name-tokens"},
        )
        return EXIT_PASS

    if named_evidence:
        found = ",".join(named_evidence)
        emit_check(
            CHECK_ID, "pass",
            "Code references SEC0045 / OWASP security event logging by name (but no specific event-name tokens detected — confirm the 17 OWASP events are covered).",
            {"evidence_files": found, "signal": "name-reference-only"},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "No SEC0045 security-event logging detected: neither OWASP-named files nor any event-name tokens (authn_/authz_/sys_/user_/session_/excessive_use/malicious_/input_validation_). Confirm applicability per the per-product disposition in references/decisions.md.",
        {},
        {"kind": "judgement", "human_review": "If the product emits user/admin/auth events, implement the OWASP Application Logging Vocabulary events in JSON (or logfmt) per canonical/operator#1905 / canonical/concierge#208. The 17 events span authn_*, authz_*, sys_*, user_*, session_*, plus excessive_use, malicious_*, input_validation_*."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
