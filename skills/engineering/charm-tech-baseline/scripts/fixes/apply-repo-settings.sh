#!/usr/bin/env bash
# Fix: patch live GitHub repo settings to match the baseline.
#
# Use this ONLY when the repo is not (and will not be) enrolled in
# canonical-repo-automation (CRA). For CRA-enrolled repos, drift must be
# fixed by re-applying CRA — direct API patches will be overwritten on the
# next apply. The repo-settings check refuses to recommend this fix for
# CRA-enrolled repos for that reason.
#
# What it sets:
#   - allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false
#   - delete_branch_on_merge=true
#   - secret_scanning + push protection + dependabot security updates enabled
#   - private vulnerability reporting enabled
#   - actions allowed_actions=selected (canonical-owned repos only)
#
# What it does NOT set: rulesets / branch protection (a separate fix —
# different shape per-repo, needs the protected branch name, required checks,
# and bypass policy decided per repo).
#
# Usage: scripts/fixes/apply-repo-settings.sh [--dry-run]
# The script prints each gh call before running; pass --dry-run to print only.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

dry_run=false
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry_run=true ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

if ! command -v gh >/dev/null 2>&1; then
    printf 'gh CLI not installed.\n' >&2
    exit 3
fi

url=$(origin_url)
slug=${url#https://github.com/}
owner=${slug%%/*}
if [ -z "$slug" ] || [ "$slug" = "$url" ]; then
    printf 'Could not parse owner/repo from origin URL: %s\n' "$url" >&2
    exit 3
fi

run() {
    printf '+ %s\n' "$*"
    if [ "$dry_run" = "false" ]; then
        "$@"
    fi
}

# Merge + branch hygiene + security-and-analysis (one PATCH call).
run gh api -X PATCH "repos/$slug" \
    -F allow_squash_merge=true \
    -F allow_merge_commit=false \
    -F allow_rebase_merge=false \
    -F delete_branch_on_merge=true \
    -f security_and_analysis[secret_scanning][status]=enabled \
    -f security_and_analysis[secret_scanning_push_protection][status]=enabled \
    -f security_and_analysis[dependabot_security_updates][status]=enabled

# Private vulnerability reporting (separate endpoint, PUT, no body).
run gh api -X PUT "repos/$slug/private-vulnerability-reporting"

# Actions allowlist — canonical-owned only. Personal repos legitimately run
# `allowed_actions=all`; only flip when the repo belongs to canonical.
if [ "$owner" = "canonical" ]; then
    run gh api -X PUT "repos/$slug/actions/permissions" \
        -F enabled=true \
        -f allowed_actions=selected
    printf '\nNote: allowed_actions set to "selected". The selected-actions allowlist itself is org-scoped and lives in canonical-repo-automation; this repo will inherit whatever the org allows. If the repo needs additional vetted actions, declare them in CRA rather than per-repo.\n'
fi

printf '\nDone. Re-run scripts/check.sh --only=repo-settings to confirm.\n'
if [ "$owner" = "canonical" ]; then
    printf 'Reminder: this patches live settings only. For a canonical/* repo, the durable fix is enrolment in canonical-repo-automation — these patches will drift back over time without a CRA declaration.\n'
fi
