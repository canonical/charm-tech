#!/usr/bin/env bash
# Check: SEC0045 Security Event Logging — heuristic.
# Tier coverage: product only.
#
# Applicability is per-product (see references/decisions.md). Where the
# per-product disposition is settled we short-circuit. For other products we
# look for evidence the OWASP Application Logging Vocabulary has been
# adopted — either by name reference (OWASP / owasp-logger / securitylog) or
# by emitted event-name tokens (authn_*, authz_*, sys_*, user_created/updated,
# excessive_use, malicious_*, input_validation_*).
#
# Output is informational: a pass means evidence exists, NOT that the events
# match the doc's required set. A fail means the agent should confirm whether
# the product genuinely has no auth/admin/user surface, or whether logging is
# missing.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="sec0045-events"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

url=$(origin_url)
slug=${url#https://github.com/}

# Per-product disposition from references/decisions.md.
case "$slug" in
    canonical/operator)
        emit_check "$CHECK_ID" "pass" \
            "SEC0045 done long ago via canonical/operator#1905."
        exit 0 ;;
    canonical/jubilant|canonical/pytest-jubilant)
        emit_check "$CHECK_ID" "na" \
            "Out of scope: no user/admin/auth surface."
        exit 2 ;;
    canonical/charmlibs)
        emit_check "$CHECK_ID" "na" \
            "Applicable but deferred to a future cycle."
        exit 2 ;;
esac

# Broad-name signal first (cheap).
named_evidence=$(grep -rEl --include='*.go' --include='*.py' \
    'OWASP|owasp-logger|securitylog|security_event|security-event' \
    . 2>/dev/null | head -5 || true)

# OWASP Application Logging Vocabulary event tokens. These are the
# canonical strings the spec defines; any of them in code is strong evidence.
# Grouped roughly by category for readability — the regex matches any of them.
owasp_pattern='authn_(login|password|token|impersonation|create|sso|2fa)_(succ|fail|change|created|revoked|expired|lock|use|unlock)|authz_(fail|change|admin|impersonation)|excessive_use|input_validation_(fail)|malicious_(direct_reference|attack_tool|cors|excess_use)|sys_(startup|shutdown|restart|crash|monitor_disabled|monitor_enabled|config_change)|user_(created|updated|deleted|archived|suspended)|session_(created|expired|use_after_expire|hijacked|renewed)'

token_evidence=$(grep -rEl --include='*.go' --include='*.py' "$owasp_pattern" . 2>/dev/null | head -5 || true)

if [ -n "$token_evidence" ]; then
    found=$(printf '%s' "$token_evidence" | tr '\n' ',' | sed 's/,$//')
    emit_check "$CHECK_ID" "pass" \
        "Code emits OWASP Application Logging Vocabulary event tokens." \
        "{\"evidence_files\":\"$found\",\"signal\":\"event-name-tokens\"}"
    exit 0
fi

if [ -n "$named_evidence" ]; then
    found=$(printf '%s' "$named_evidence" | tr '\n' ',' | sed 's/,$//')
    emit_check "$CHECK_ID" "pass" \
        "Code references SEC0045 / OWASP security event logging by name (but no specific event-name tokens detected — confirm the 17 OWASP events are covered)." \
        "{\"evidence_files\":\"$found\",\"signal\":\"name-reference-only\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "No SEC0045 security-event logging detected: neither OWASP-named files nor any event-name tokens (authn_/authz_/sys_/user_/session_/excessive_use/malicious_/input_validation_). Confirm applicability per the per-product disposition in references/decisions.md." \
    '{}' \
    '{"kind":"judgement","human_review":"If the product emits user/admin/auth events, implement the OWASP Application Logging Vocabulary events in JSON (or logfmt) per canonical/operator#1905 / canonical/concierge#208. The 17 events span authn_*, authz_*, sys_*, user_*, session_*, plus excessive_use, malicious_*, input_validation_*."}'
exit 1
