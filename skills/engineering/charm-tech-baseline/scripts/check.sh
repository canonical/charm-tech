#!/usr/bin/env bash
# Umbrella check runner. Dispatches every script in checks/ that
# applies to the resolved tier and emits a single JSON report.
#
# Usage:
#   check.sh [--tier=product|canonical|personal]
#            [--only=<check>[,<check>...]]
#            [--format=json|markdown]

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=lib/common.sh
. "$script_dir/lib/common.sh"

tier_override=""
only_filter=""
format="json"

for arg in "$@"; do
    case "$arg" in
        --tier=*) tier_override=${arg#--tier=} ;;
        --only=*) only_filter=${arg#--only=} ;;
        --format=*) format=${arg#--format=} ;;
        -h|--help)
            sed -n '2,8p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

# Resolve tier.
if [ -n "$tier_override" ]; then
    tier="$tier_override"
    tier_source="override"
else
    tier=$("$script_dir/detect-tier.sh")
    tier_source="detected"
fi

if [ "$tier" = "unknown" ]; then
    printf 'Could not detect tier; pass --tier=product|canonical|personal\n' >&2
    exit 2
fi

repo=$(origin_url)
generated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build list of checks to run.
checks_dir="$script_dir/checks"
if [ -n "$only_filter" ]; then
    IFS=',' read -r -a only_ids <<< "$only_filter"
    selected=()
    for id in "${only_ids[@]}"; do
        path="$checks_dir/$id.sh"
        if [ -x "$path" ]; then
            selected+=("$path")
        else
            printf 'Unknown check: %s\n' "$id" >&2
            exit 2
        fi
    done
else
    selected=()
    if [ -d "$checks_dir" ]; then
        for path in "$checks_dir"/*.sh; do
            [ -e "$path" ] || continue
            selected+=("$path")
        done
    fi
fi

# Run each check. Each emits a single JSON object on stdout.
results=()
notes=()
for path in "${selected[@]}"; do
    if out=$("$path" --tier="$tier" 2>/dev/null); then
        :
    fi
    rc=$?
    if [ -z "$out" ]; then
        notes+=("\"check ${path##*/} produced no output (exit $rc)\"")
        continue
    fi
    results+=("$out")
done

# Assemble report.
joined_results=$(IFS=,; printf '%s' "${results[*]:-}")
joined_notes=$(IFS=,; printf '%s' "${notes[*]:-}")

if [ "$format" = "json" ]; then
    printf '{"schema_version":1,"repo":"%s","tier":"%s","tier_source":"%s","generated_at":"%s","checks":[%s],"notes":[%s]}\n' \
        "$repo" "$tier" "$tier_source" "$generated_at" "$joined_results" "$joined_notes"
    exit 0
fi

# Markdown summary path. Naive transformation — agents should prefer
# the JSON path; this is for human spot-checks.
printf '# Repo-setup audit\n\n'
printf -- '- Repo: `%s`\n' "$repo"
printf -- '- Tier: **%s** (%s)\n' "$tier" "$tier_source"
printf -- '- Generated: %s\n\n' "$generated_at"
printf '## Findings\n\n'
for r in "${results[@]:-}"; do
    # very small JSON-ish parse; works because emit_check uses a fixed shape
    id=$(printf '%s' "$r" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
    status=$(printf '%s' "$r" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
    summary=$(printf '%s' "$r" | sed -n 's/.*"summary":"\([^"]*\)".*/\1/p')
    printf -- '- **%s** (`%s`) — %s\n' "$status" "$id" "$summary"
done
if [ ${#notes[@]} -gt 0 ]; then
    printf '\n## Notes\n\n'
    for n in "${notes[@]}"; do printf -- '- %s\n' "${n//\"/}"; done
fi
