#!/usr/bin/env bash
# Check: GitHub repo settings are either declared in canonical-repo-automation
# (CRA) — the Terraform/Terragrunt control plane that owns repo settings for
# Charm Tech — or, for repos not enrolled in CRA, set manually to the baseline.
#
# Tier coverage: product, canonical, personal.
#   - product / canonical: prefer CRA enrolment; otherwise live settings must
#     match the baseline.
#   - personal: live settings only (CRA does not manage personal repos).
#
# Mandate: cycle baseline — canonical-repo-automation (CRA) is the real
# control plane for Charm Tech repo settings. CRA already declares:
#   - allowed_actions = "selected"
#   - private vulnerability reporting on (group-wide)
#   - Dependabot security updates on (group-wide)
#   - squash-only merges, delete-branch-on-merge
#   - secret scanning + push protection (PR #812 group-wide)
# Without CRA the same posture must be set per-repo via Settings or `gh api`.
#
# Baseline settings checked (live):
#   - allow_squash_merge=true, allow_merge_commit=false, allow_rebase_merge=false
#   - delete_branch_on_merge=true
#   - security_and_analysis.secret_scanning.status=enabled
#   - security_and_analysis.secret_scanning_push_protection.status=enabled
#   - security_and_analysis.dependabot_security_updates.status=enabled
#   - private vulnerability reporting enabled
#   - allowed actions != "all" (selected / local_only) — canonical/product only
#
# CRA enrolment is detected via `gh api` against
# canonical/canonical-repo-automation. If gh is unavailable or the query fails,
# the check emits `unknown` and falls back to checking live settings.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="repo-settings"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

url=$(origin_url)
slug=${url#https://github.com/}
owner=${slug%%/*}
name=${slug##*/}

if [ -z "$slug" ] || [ "$slug" = "$url" ]; then
    emit_check "$CHECK_ID" "unknown" "Could not parse owner/repo from origin URL."
    exit 3
fi

if ! command -v gh >/dev/null 2>&1; then
    emit_check "$CHECK_ID" "unknown" \
        "gh CLI not installed; cannot inspect live repo settings or CRA enrolment."
    exit 3
fi

# --- 1. CRA enrolment (product, canonical only) ---
# CRA stores per-repo declarations as
#   groups/<group>/[<subgroup>/]repos/<name>/terragrunt.hcl
# The per-repo file is always literally `terragrunt.hcl` — there is no
# `<name>.hcl`. We pull the recursive tree of CRA's default branch and
# look for any path matching `/repos/<name>/`. Trees API is one call,
# private-repo-friendly (no code search), and not subject to the search
# API's eventual-consistency surprises.
managed_by_cra="false"
cra_path=""
if [ "$tier" != "personal" ] && [ "$owner" = "canonical" ]; then
    cra_branch=$(gh api repos/canonical/canonical-repo-automation \
                    --jq '.default_branch' 2>/dev/null || printf 'main')
    [ -z "$cra_branch" ] && cra_branch=main
    # Anchored on '/repos/' so we don't match a same-named subdirectory
    # elsewhere; anchored on the trailing slash so 'operator' doesn't
    # spuriously match 'operator-foo'.
    if hit=$(gh api "repos/canonical/canonical-repo-automation/git/trees/${cra_branch}?recursive=1" \
                --jq ".tree[].path | select(test(\"(^|/)repos/${name}/\"))" \
                2>/dev/null | head -1); then
        if [ -n "$hit" ]; then
            managed_by_cra="true"
            cra_path="$hit"
        fi
    fi
fi

# --- 2. Live settings ---
# Single API call carries merge / branch-deletion flags and the
# security_and_analysis block (needs `security_and_analysis` accept header
# enabled by default on recent gh).
if ! repo_json=$(gh api "repos/$slug" 2>/dev/null); then
    emit_check "$CHECK_ID" "unknown" \
        "Could not fetch repos/$slug via gh api (auth scope or network)." \
        "{\"slug\":\"$slug\"}"
    exit 3
fi

if ! command -v jq >/dev/null 2>&1; then
    emit_check "$CHECK_ID" "unknown" \
        "jq not installed; cannot parse repo settings JSON." \
        "{\"slug\":\"$slug\"}"
    exit 3
fi
get() { printf '%s' "$repo_json" | jq -r "$1" 2>/dev/null || true; }

squash=$(get '.allow_squash_merge')
merge_commit=$(get '.allow_merge_commit')
rebase=$(get '.allow_rebase_merge')
delete_on_merge=$(get '.delete_branch_on_merge')
ss_secret=$(get '.security_and_analysis.secret_scanning.status // "unknown"')
ss_push=$(get '.security_and_analysis.secret_scanning_push_protection.status // "unknown"')
ss_dep=$(get '.security_and_analysis.dependabot_security_updates.status // "unknown"')

# Private vulnerability reporting + allowed actions are separate endpoints.
pvr="unknown"
if pvr_json=$(gh api "repos/$slug/private-vulnerability-reporting" 2>/dev/null); then
    pvr=$(printf '%s' "$pvr_json" | jq -r '.enabled' 2>/dev/null || printf 'unknown')
fi

allowed_actions="unknown"
if [ "$tier" != "personal" ]; then
    if perms_json=$(gh api "repos/$slug/actions/permissions" 2>/dev/null); then
        allowed_actions=$(printf '%s' "$perms_json" | jq -r '.allowed_actions // "unknown"' 2>/dev/null || printf 'unknown')
    fi
fi

# Split drift (genuine baseline violations) from unverifiable (the gh
# token lacks admin scope on this repo, so security_and_analysis /
# actions/permissions / PVR come back missing or 403). The merge flags
# are world-readable and always trustworthy; the security/PVR/actions
# fields are not.
problems=()
unverifiable=()

# Always-readable: merge / branch deletion.
[ "$squash" = "true" ]          || problems+=("allow_squash_merge != true")
[ "$merge_commit" = "false" ]   || problems+=("allow_merge_commit != false")
[ "$rebase" = "false" ]         || problems+=("allow_rebase_merge != false")
[ "$delete_on_merge" = "true" ] || problems+=("delete_branch_on_merge != true")

# Admin-scope fields: 'unknown' / 'null' means the token couldn't see them.
verify_admin_field() {
    name=$1; value=$2; want=$3
    case "$value" in
        unknown|null|"")
            unverifiable+=("$name (token lacks admin scope)")
            ;;
        "$want") ;;
        *) problems+=("$name != $want ($value)") ;;
    esac
}

verify_admin_field "secret_scanning"                "$ss_secret" "enabled"
verify_admin_field "secret_scanning_push_protection" "$ss_push"   "enabled"
verify_admin_field "dependabot_security_updates"     "$ss_dep"    "enabled"
verify_admin_field "private_vulnerability_reporting" "$pvr"       "true"

if [ "$tier" != "personal" ]; then
    case "$allowed_actions" in
        selected|local_only) ;;
        unknown|null|"")
            unverifiable+=("allowed_actions (token lacks admin scope)")
            ;;
        *) problems+=("allowed_actions=$allowed_actions (expected 'selected' or 'local_only')") ;;
    esac
fi

unverifiable_note=""
if [ ${#unverifiable[@]} -gt 0 ]; then
    j=$(IFS='; '; printf '%s' "${unverifiable[*]}")
    unverifiable_note=" (unverifiable from this token: $j)"
fi

evidence="{\"slug\":\"$slug\",\"managed_by_cra\":$managed_by_cra,\"cra_path\":\"$cra_path\",\"allow_squash_merge\":\"$squash\",\"allow_merge_commit\":\"$merge_commit\",\"allow_rebase_merge\":\"$rebase\",\"delete_branch_on_merge\":\"$delete_on_merge\",\"secret_scanning\":\"$ss_secret\",\"push_protection\":\"$ss_push\",\"dependabot_security_updates\":\"$ss_dep\",\"private_vulnerability_reporting\":\"$pvr\",\"allowed_actions\":\"$allowed_actions\"}"

if [ "$managed_by_cra" = "true" ] && [ ${#problems[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "pass" \
        "Settings declared in CRA ($cra_path); merge/branch-deletion posture matches the baseline$unverifiable_note." \
        "$evidence"
    exit 0
fi

if [ "$managed_by_cra" = "true" ] && [ ${#problems[@]} -gt 0 ]; then
    # Live drift from CRA-declared settings — Phase 4 "apply" territory.
    joined=$(IFS='; '; printf '%s' "${problems[*]}")
    emit_check "$CHECK_ID" "fail" \
        "Repo is declared in CRA ($cra_path) but live settings drift from the baseline: $joined. Run a CRA apply to reconcile; do not patch live settings directly." \
        "$evidence" \
        '{"kind":"judgement","human_review":"Drift between CRA-declared and live settings. Re-apply CRA for the relevant group rather than mutating GitHub directly — direct patches will be overwritten on the next apply."}'
    exit 1
fi

if [ ${#problems[@]} -eq 0 ]; then
    # Not in CRA but live posture is fine — only acceptable for personal tier or
    # for non-charm-tech canonical/* repos that legitimately sit outside CRA.
    if [ "$tier" = "personal" ]; then
        emit_check "$CHECK_ID" "pass" \
            "Live settings match the baseline (personal tier — CRA enrolment not expected)$unverifiable_note." \
            "$evidence"
        exit 0
    fi
    emit_check "$CHECK_ID" "pass" \
        "Live settings match the baseline. Not declared in CRA — confirm whether this repo should be enrolled in canonical-repo-automation$unverifiable_note." \
        "$evidence"
    exit 0
fi

# Not in CRA and live posture is wrong.
joined=$(IFS='; '; printf '%s' "${problems[*]}")
if [ "$tier" = "personal" ]; then
    emit_check "$CHECK_ID" "fail" \
        "Live settings drift from baseline: $joined." \
        "$evidence" \
        '{"kind":"mechanical","script":"scripts/fixes/apply-repo-settings.sh","human_review":"Review each setting before applying; the fix script patches the repo via gh api."}'
    exit 1
fi

emit_check "$CHECK_ID" "fail" \
    "Repo is NOT declared in canonical-repo-automation and live settings drift from baseline: $joined. Either enrol the repo in CRA (preferred for canonical-owned repos) or apply the settings manually." \
    "$evidence" \
    '{"kind":"judgement","human_review":"Preferred: open a CRA PR declaring this repo under the appropriate groups/<group>/repos/ tree so settings are managed centrally. Fallback (if CRA enrolment is intentionally out of scope): run scripts/fixes/apply-repo-settings.sh to patch the live settings via gh api."}'
exit 1
