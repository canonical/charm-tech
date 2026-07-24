#!/usr/bin/env python3
"""Check: GitHub repo settings are either declared in canonical-repo-automation
(CRA) — the Terraform/Terragrunt control plane that owns repo settings for
Charm Tech — or, for repos not enrolled in CRA, set manually to the baseline.

Tier coverage: product, canonical, personal.
  - product / canonical: prefer CRA enrolment; otherwise live settings must
    match the baseline.
  - personal: live settings only (CRA does not manage personal repos).

Mandate: cycle baseline — canonical-repo-automation (CRA) is the real
control plane for Charm Tech repo settings. CRA already declares:
  - allowed_actions = "selected"
  - private vulnerability reporting on (group-wide)
  - Dependabot security updates on (group-wide)
  - squash-only merges, delete-branch-on-merge
  - secret scanning + push protection (PR #812 group-wide)
Without CRA the same posture must be set per-repo via Settings or `gh api`.

Baseline settings checked (live):
  - allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false
  - delete_branch_on_merge=true
  - security_and_analysis.secret_scanning.status=enabled
  - security_and_analysis.secret_scanning_push_protection.status=enabled
  - security_and_analysis.dependabot_security_updates.status=enabled
  - private vulnerability reporting enabled
  - allowed actions != "all" (selected / local_only) — canonical/product only

CRA enrolment is detected via `gh api` against
canonical/canonical-repo-automation. If gh is unavailable or the query fails,
the check emits `unknown` and falls back to checking live settings.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    emit_check, origin_url, parse_tier, run, tier_applies,
)

CHECK_ID = "repo-settings"
APPLIES = "product,canonical,personal"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    url = origin_url()
    slug = url[len("https://github.com/"):] if url.startswith("https://github.com/") else url

    if not slug or slug == url:
        emit_check(CHECK_ID, "unknown", "Could not parse owner/repo from origin URL.")
        return EXIT_UNKNOWN

    owner = slug.split("/", 1)[0]
    name = slug.rsplit("/", 1)[-1]

    if not shutil.which("gh"):
        emit_check(CHECK_ID, "unknown", "gh CLI not installed; cannot inspect live repo settings or CRA enrolment.")
        return EXIT_UNKNOWN

    # --- 1. CRA enrolment ---
    managed_by_cra = False
    cra_path = ""
    if tier != "personal" and owner == "canonical":
        r = run(["gh", "api", "repos/canonical/canonical-repo-automation", "--jq", ".default_branch"])
        cra_branch = r.stdout.strip() if r.returncode == 0 else "main"
        if not cra_branch:
            cra_branch = "main"
        r2 = run([
            "gh", "api",
            f"repos/canonical/canonical-repo-automation/git/trees/{cra_branch}?recursive=1",
            "--jq", f'.tree[].path | select(test("(^|/)repos/{name}/"))',
        ])
        if r2.returncode == 0:
            first = ""
            for ln in r2.stdout.splitlines():
                if ln.strip():
                    first = ln.strip()
                    break
            if first:
                managed_by_cra = True
                cra_path = first

    # --- 2. Live settings ---
    r = run(["gh", "api", f"repos/{slug}"])
    if r.returncode != 0:
        emit_check(
            CHECK_ID, "unknown",
            f"Could not fetch repos/{slug} via gh api (auth scope or network).",
            {"slug": slug},
        )
        return EXIT_UNKNOWN

    try:
        repo_json = json.loads(r.stdout)
    except json.JSONDecodeError:
        emit_check(
            CHECK_ID, "unknown",
            f"Could not fetch repos/{slug} via gh api (auth scope or network).",
            {"slug": slug},
        )
        return EXIT_UNKNOWN

    def get(obj, *keys, default="unknown"):
        cur = obj
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
            if cur is None:
                return default
        return cur

    def bool_or_str(v):
        if v is True:
            return "true"
        if v is False:
            return "false"
        if v is None:
            return "null"
        return str(v)

    squash = bool_or_str(repo_json.get("allow_squash_merge"))
    merge_commit = bool_or_str(repo_json.get("allow_merge_commit"))
    rebase = bool_or_str(repo_json.get("allow_rebase_merge"))
    delete_on_merge = bool_or_str(repo_json.get("delete_branch_on_merge"))

    sa = repo_json.get("security_and_analysis") or {}
    ss_secret = (sa.get("secret_scanning") or {}).get("status") or "unknown"
    ss_push = (sa.get("secret_scanning_push_protection") or {}).get("status") or "unknown"
    ss_dep = (sa.get("dependabot_security_updates") or {}).get("status") or "unknown"

    pvr = "unknown"
    r = run(["gh", "api", f"repos/{slug}/private-vulnerability-reporting"])
    if r.returncode == 0:
        try:
            pvr_json = json.loads(r.stdout)
            pvr = bool_or_str(pvr_json.get("enabled"))
        except json.JSONDecodeError:
            pvr = "unknown"

    allowed_actions = "unknown"
    if tier != "personal":
        r = run(["gh", "api", f"repos/{slug}/actions/permissions"])
        if r.returncode == 0:
            try:
                perms_json = json.loads(r.stdout)
                allowed_actions = perms_json.get("allowed_actions") or "unknown"
            except json.JSONDecodeError:
                allowed_actions = "unknown"

    problems: list[str] = []
    unverifiable: list[str] = []

    if squash != "true":
        problems.append("allow_squash_merge != true")
    if merge_commit != "false":
        problems.append("allow_merge_commit != false")
    if rebase != "false":
        problems.append("allow_rebase_merge != false")
    if delete_on_merge != "true":
        problems.append("delete_branch_on_merge != true")

    def verify_admin_field(name: str, value: str, want: str) -> None:
        if value in ("unknown", "null", ""):
            unverifiable.append(f"{name} (token lacks admin scope)")
        elif value == want:
            return
        else:
            problems.append(f"{name} != {want} ({value})")

    verify_admin_field("secret_scanning", ss_secret, "enabled")
    verify_admin_field("secret_scanning_push_protection", ss_push, "enabled")
    verify_admin_field("dependabot_security_updates", ss_dep, "enabled")
    verify_admin_field("private_vulnerability_reporting", pvr, "true")

    if tier != "personal":
        if allowed_actions in ("selected", "local_only"):
            pass
        elif allowed_actions in ("unknown", "null", ""):
            unverifiable.append("allowed_actions (token lacks admin scope)")
        else:
            problems.append(f"allowed_actions={allowed_actions} (expected 'selected' or 'local_only')")

    unverifiable_note = ""
    if unverifiable:
        unverifiable_note = f" (unverifiable from this token: {'; '.join(unverifiable)})"

    evidence = {
        "slug": slug,
        "managed_by_cra": managed_by_cra,
        "cra_path": cra_path,
        "allow_squash_merge": squash,
        "allow_merge_commit": merge_commit,
        "allow_rebase_merge": rebase,
        "delete_branch_on_merge": delete_on_merge,
        "secret_scanning": ss_secret,
        "push_protection": ss_push,
        "dependabot_security_updates": ss_dep,
        "private_vulnerability_reporting": pvr,
        "allowed_actions": allowed_actions,
    }

    if managed_by_cra and not problems:
        emit_check(
            CHECK_ID, "pass",
            f"Settings declared in CRA ({cra_path}); merge/branch-deletion posture matches the baseline{unverifiable_note}.",
            evidence,
        )
        return EXIT_PASS

    if managed_by_cra and problems:
        joined = "; ".join(problems)
        emit_check(
            CHECK_ID, "fail",
            f"Repo is declared in CRA ({cra_path}) but live settings drift from the baseline: {joined}. Run a CRA apply to reconcile; do not patch live settings directly.",
            evidence,
            {"kind": "judgement", "human_review": "Drift between CRA-declared and live settings. Re-apply CRA for the relevant group rather than mutating GitHub directly — direct patches will be overwritten on the next apply."},
        )
        return EXIT_FAIL

    if not problems:
        if tier == "personal":
            emit_check(
                CHECK_ID, "pass",
                f"Live settings match the baseline (personal tier — CRA enrolment not expected){unverifiable_note}.",
                evidence,
            )
            return EXIT_PASS
        emit_check(
            CHECK_ID, "pass",
            f"Live settings match the baseline. Not declared in CRA — confirm whether this repo should be enrolled in canonical-repo-automation{unverifiable_note}.",
            evidence,
        )
        return EXIT_PASS

    joined = "; ".join(problems)
    if tier == "personal":
        emit_check(
            CHECK_ID, "fail",
            f"Live settings drift from baseline: {joined}.",
            evidence,
            {"kind": "mechanical", "script": "scripts/fixes/apply-repo-settings.py", "human_review": "Review each setting before applying; the fix script patches the repo via gh api."},
        )
        return EXIT_FAIL

    emit_check(
        CHECK_ID, "fail",
        f"Repo is NOT declared in canonical-repo-automation and live settings drift from baseline: {joined}. Either enrol the repo in CRA (preferred for canonical-owned repos) or apply the settings manually.",
        evidence,
        {"kind": "judgement", "human_review": "Preferred: open a CRA PR declaring this repo under the appropriate groups/<group>/repos/ tree so settings are managed centrally. Fallback (if CRA enrolment is intentionally out of scope): run scripts/fixes/apply-repo-settings.py to patch the live settings via gh api."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
