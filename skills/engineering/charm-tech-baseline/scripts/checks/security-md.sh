#!/usr/bin/env bash
# Check: SECURITY.md exists and references the Ubuntu disclosure policy.
# Tier coverage: all (product, canonical, personal).
#
# Mandate: SEC0025 §General Requirements + SEC0026 (Canonical-internal);
# best practice for personal-tier.
#
# Pass:    SECURITY.md present AND links to ubuntu.com/security/disclosure-policy
#          OR to security@ubuntu.com / security@canonical.com
# Fail:    SECURITY.md missing, OR present but no disclosure-policy link/contact

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="security-md"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ ! -f SECURITY.md ]; then
    emit_check "$CHECK_ID" "fail" \
        "SECURITY.md is missing." \
        '{}' \
        '{"kind":"mechanical","script":"scripts/fixes/add-security-md.sh","human_review":"Customise the disclosure contact and supported-versions table."}'
    exit 1
fi

# Look for any of the canonical disclosure-policy references.
if grep -qiE 'ubuntu\.com/security/disclosure-policy|security@(ubuntu|canonical)\.com|security/advisories' SECURITY.md; then
    lines=$(wc -l < SECURITY.md)
    emit_check "$CHECK_ID" "pass" \
        "SECURITY.md present and references the Ubuntu disclosure policy." \
        "{\"path\":\"SECURITY.md\",\"lines\":$lines}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "SECURITY.md present but does not reference the Ubuntu disclosure policy or a security contact." \
    '{"path":"SECURITY.md"}' \
    '{"kind":"judgement","human_review":"Add a Reporting section linking https://ubuntu.com/security/disclosure-policy and the project security contact."}'
exit 1
