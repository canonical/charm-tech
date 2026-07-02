#!/usr/bin/env bash
# Check: CI invocations of `uv run` and `uv sync` pass `--locked` so a
# stale `uv.lock` fails the build rather than silently re-resolving.
#
# Rationale (Canonical Security "How-To: Secure a repo" — Lockfile(s)
# section): commit the lockfile and use the frozen-install command in
# CI, so drift between `pyproject.toml` and `uv.lock` comes back as a
# reviewable commit instead of a silent CI-side re-resolve. Without
# `--locked`, a PR that widens a version range in `pyproject.toml`
# without regenerating `uv.lock` silently re-resolves in the CI runner
# and the transitive-dep delta never appears in the diff.
#
# Preference: `--locked` (fails on stale lockfile) over `--frozen`
# (skips freshness check entirely — masks drift instead of surfacing
# it). This check accepts either but reports how many use each.
#
# Tier coverage: product, canonical, personal (advisory).
#
# Scope: reads `.github/workflows/*.y*ml` and the top-level `Makefile`
# (some repos, e.g. api_demo_server, put `uv run` inside `make lint` /
# `make integration` targets that CI shells out to).
#
# Skipped patterns (don't touch the project lockfile — reporting them
# would be noise):
#   - `uv run --no-project --script ...`
#   - `uv run --no-project --with-requirements ...`
#   - `uvx <tool>` / `uvx <tool>@vX.Y.Z ...`
#   - `uv tool install` / `uv tool run`
#
# Non-uv repos (Go, or Python repos with no `pyproject.toml`) are
# reported as `na`.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="uv-locked-in-ci"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ ! -f pyproject.toml ] && [ ! -f uv.lock ]; then
    emit_check "$CHECK_ID" "na" "No pyproject.toml or uv.lock — not a uv project."
    exit 2
fi

# Gather candidate files: workflows + Makefile at the top level.
mapfile -t files < <(
    { find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null
      [ -f Makefile ] && printf 'Makefile\n'
      [ -f makefile ] && printf 'makefile\n'
      [ -f GNUmakefile ] && printf 'GNUmakefile\n'
    } | sort -u)

if [ ${#files[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "na" "No workflows or Makefile to audit."
    exit 2
fi

# Walk every candidate file, extract each `uv run` / `uv sync` line,
# classify: has-locked / has-frozen / bare / skipped.
report=$(FILES="$(printf '%s\n' "${files[@]}")" python3 - <<'PY' 2>/dev/null
import os, re, sys

# Match `uv run` or `uv sync`, at any indent, in a YAML `run:` block or
# Makefile recipe. Group 1 is the invocation slice (everything from
# `uv` to end-of-line — enough to inspect flags).
INVOKE_RE = re.compile(r'(uv\s+(?:run|sync)\b[^\r\n]*)')

def classify(inv: str) -> str:
    """Return one of: locked, frozen, bare, skipped-<reason>."""
    # Skip patterns first.
    if re.search(r'\buv\s+run\s+--no-project\b.*(?:--script|--with-requirements)\b', inv):
        return "skipped-no-project"
    if re.search(r'\buv\s+tool\s+(?:install|run)\b', inv):
        return "skipped-uv-tool"
    # Note: `uvx` is a separate binary; the regex above only matches
    # `uv run|sync`, so uvx invocations never reach this classifier.
    if '--locked' in inv:
        return "locked"
    if '--frozen' in inv:
        return "frozen"
    return "bare"

by_file = {}
totals = {"locked": 0, "frozen": 0, "bare": 0, "skipped-no-project": 0, "skipped-uv-tool": 0}
bare_hits = []

for path in os.environ["FILES"].splitlines():
    if not path:
        continue
    try:
        with open(path) as f:
            for lineno, line in enumerate(f, 1):
                for m in INVOKE_RE.finditer(line):
                    inv = m.group(1)
                    cat = classify(inv)
                    totals[cat] = totals.get(cat, 0) + 1
                    by_file.setdefault(path, {}).setdefault(cat, []).append((lineno, inv.strip()))
                    if cat == "bare":
                        bare_hits.append(f"{path}:{lineno}: {inv.strip()}")
    except (OSError, UnicodeDecodeError):
        continue

# Report totals as space-separated key=value; per-file bare lines below.
print(f"TOTALS locked={totals['locked']} frozen={totals['frozen']} bare={totals['bare']} skipped_no_project={totals['skipped-no-project']} skipped_uv_tool={totals['skipped-uv-tool']}")
for h in bare_hits:
    print(f"BARE {h}")
PY
)

# Parse the python output.
totals_line=$(printf '%s' "$report" | awk 'NR==1{print}')
n_locked=$(printf '%s' "$totals_line" | sed -n 's/.*locked=\([0-9][0-9]*\).*/\1/p')
n_frozen=$(printf '%s' "$totals_line" | sed -n 's/.*frozen=\([0-9][0-9]*\).*/\1/p')
n_bare=$(printf '%s' "$totals_line" | sed -n 's/.*bare=\([0-9][0-9]*\).*/\1/p')
n_skipped_no_project=$(printf '%s' "$totals_line" | sed -n 's/.*skipped_no_project=\([0-9][0-9]*\).*/\1/p')
n_skipped_uv_tool=$(printf '%s' "$totals_line" | sed -n 's/.*skipped_uv_tool=\([0-9][0-9]*\).*/\1/p')

n_locked=${n_locked:-0}
n_frozen=${n_frozen:-0}
n_bare=${n_bare:-0}
n_skipped_no_project=${n_skipped_no_project:-0}
n_skipped_uv_tool=${n_skipped_uv_tool:-0}

total_project=$(( n_locked + n_frozen + n_bare ))

evidence=$(printf '{"files_scanned":%d,"invocations":{"locked":%d,"frozen":%d,"bare":%d,"skipped_no_project":%d,"skipped_uv_tool":%d}}' \
    "${#files[@]}" "$n_locked" "$n_frozen" "$n_bare" "$n_skipped_no_project" "$n_skipped_uv_tool")

if [ "$total_project" -eq 0 ]; then
    emit_check "$CHECK_ID" "na" \
        "No project-scoped uv run / uv sync invocations found in workflows or Makefile (skipped: $n_skipped_no_project no-project, $n_skipped_uv_tool uv-tool)." \
        "$evidence"
    exit 2
fi

if [ "$n_bare" -eq 0 ]; then
    if [ "$n_frozen" -gt 0 ] && [ "$n_locked" -eq 0 ]; then
        emit_check "$CHECK_ID" "pass" \
            "All $total_project project-scoped uv invocations use --frozen or --locked ($n_frozen frozen, 0 bare). Prefer --locked over --frozen — --locked fails on a stale lockfile, --frozen skips the freshness check entirely." \
            "$evidence"
    else
        emit_check "$CHECK_ID" "pass" \
            "All $total_project project-scoped uv invocations use --locked or --frozen ($n_locked locked, $n_frozen frozen)." \
            "$evidence"
    fi
    exit 0
fi

bare_detail=$(printf '%s' "$report" | awk '/^BARE /{sub(/^BARE /,""); print}')
remediation='{"kind":"judgement","human_review":"Add --locked (preferred) or --frozen to each bare `uv run` / `uv sync` invocation. --locked fails the build if uv.lock is stale vs pyproject.toml, forcing the PR author to commit a fresh lockfile — surfacing the resolution delta as a reviewable diff. --frozen skips the freshness check entirely and masks drift, so prefer --locked."}'

emit_check "$CHECK_ID" "fail" \
    "$n_bare of $total_project project-scoped uv invocation(s) missing --locked/--frozen ($n_locked locked, $n_frozen frozen, $n_bare bare)." \
    "$evidence" \
    "$remediation"
if [ -n "$bare_detail" ]; then
    printf '\n# uv-locked-in-ci detail (bare invocations):\n%s\n' "$bare_detail" >&2
fi
exit 1
