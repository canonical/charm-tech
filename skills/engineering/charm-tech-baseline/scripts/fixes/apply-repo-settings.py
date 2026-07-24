#!/usr/bin/env python3
"""Fix: patch live GitHub repo settings to match the baseline.

Use this ONLY when the repo is not (and will not be) enrolled in
canonical-repo-automation (CRA). For CRA-enrolled repos, drift must be
fixed by re-applying CRA — direct API patches will be overwritten on the
next apply. The repo-settings check refuses to recommend this fix for
CRA-enrolled repos for that reason.

What it sets:
  - allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false
  - delete_branch_on_merge=true
  - secret_scanning + push protection + dependabot security updates enabled
  - private vulnerability reporting enabled
  - actions allowed_actions=selected (canonical-owned repos only)

What it does NOT set: rulesets / branch protection (a separate fix —
different shape per-repo, needs the protected branch name, required checks,
and bypass policy decided per repo).

Usage: scripts/fixes/apply-repo-settings.py [--dry-run]
The script prints each gh call before running; pass --dry-run to print only.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import origin_url


HELP_TEXT = """Fix: patch live GitHub repo settings to match the baseline.

Use this ONLY when the repo is not (and will not be) enrolled in
canonical-repo-automation (CRA). For CRA-enrolled repos, drift must be
fixed by re-applying CRA — direct API patches will be overwritten on the
next apply. The repo-settings check refuses to recommend this fix for
CRA-enrolled repos for that reason.

What it sets:
  - allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false
  - delete_branch_on_merge=true
  - secret_scanning + push protection + dependabot security updates enabled
  - private vulnerability reporting enabled
  - actions allowed_actions=selected (canonical-owned repos only)

What it does NOT set: rulesets / branch protection (a separate fix —
different shape per-repo, needs the protected branch name, required checks,
and bypass policy decided per repo).

Usage: scripts/fixes/apply-repo-settings.py [--dry-run]
The script prints each gh call before running; pass --dry-run to print only.
"""


def main() -> int:
    dry_run = False
    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg in ("-h", "--help"):
            sys.stdout.write(HELP_TEXT)
            return 0
        else:
            sys.stderr.write(f"Unknown argument: {arg}\n")
            return 2

    if shutil.which("gh") is None:
        sys.stderr.write("gh CLI not installed.\n")
        return 3

    url = origin_url()
    prefix = "https://github.com/"
    if not (url.startswith(prefix) and len(url) > len(prefix)):
        sys.stderr.write(f"Could not parse owner/repo from origin URL: {url}\n")
        return 3
    slug = url[len(prefix):]
    owner = slug.split("/", 1)[0]

    def run_cmd(cmd: list[str]) -> None:
        sys.stdout.write("+ " + " ".join(cmd) + "\n")
        sys.stdout.flush()
        if not dry_run:
            subprocess.run(cmd)

    # Merge + branch hygiene + security-and-analysis (one PATCH call).
    run_cmd([
        "gh", "api", "-X", "PATCH", f"repos/{slug}",
        "-F", "allow_squash_merge=true",
        "-F", "allow_merge_commit=false",
        "-F", "allow_rebase_merge=false",
        "-F", "delete_branch_on_merge=true",
        "-f", "security_and_analysis[secret_scanning][status]=enabled",
        "-f", "security_and_analysis[secret_scanning_push_protection][status]=enabled",
        "-f", "security_and_analysis[dependabot_security_updates][status]=enabled",
    ])

    # Private vulnerability reporting (separate endpoint, PUT, no body).
    run_cmd(["gh", "api", "-X", "PUT", f"repos/{slug}/private-vulnerability-reporting"])

    # Actions allowlist — canonical-owned only. Personal repos legitimately run
    # `allowed_actions=all`; only flip when the repo belongs to canonical.
    if owner == "canonical":
        run_cmd([
            "gh", "api", "-X", "PUT", f"repos/{slug}/actions/permissions",
            "-F", "enabled=true",
            "-f", "allowed_actions=selected",
        ])
        sys.stdout.write(
            "\nNote: allowed_actions set to \"selected\". The selected-actions allowlist itself is org-scoped and lives in canonical-repo-automation; this repo will inherit whatever the org allows. If the repo needs additional vetted actions, declare them in CRA rather than per-repo.\n"
        )

    sys.stdout.write("\nDone. Re-run scripts/check.py --only=repo-settings to confirm.\n")
    if owner == "canonical":
        sys.stdout.write(
            "Reminder: this patches live settings only. For a canonical/* repo, the durable fix is enrolment in canonical-repo-automation — these patches will drift back over time without a CRA declaration.\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
