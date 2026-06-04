# Charm Tech PSIRT Engagement Playbook

Operational guide for the person on-point when PSIRT contacts Charm Tech or when a vulnerability surfaces from one of our repos. For policy rationale see SEC0026, SEC0037, SEC0038, and SEC0061; for the Canonical disclosure timeline see the [Ubuntu Security disclosure and embargo policy](https://ubuntu.com/security/disclosure-policy).

## Engagement entry points

PSIRT and external reporters reach us through three channels:

| Channel | Typical source | Triage |
|---|---|---|
| `security@ubuntu.com` | PSIRT-coordinated disclosures; reporters following our SECURITY.md | On-point engineer |
| Launchpad private security bug | PSIRT-initiated or reporter-initiated; private by default | On-point engineer |
| GitHub Security Advisory | Reporter uses the **Report a vulnerability** button in a repo's Security tab | On-point engineer |

**On-point engineer** — the Charm Tech team member carrying the security-contact role for the current pulse. Until a rotation is formalised, treat the engineering lead as the fallback contact.

On receiving a report via any channel:

1. Acknowledge to the reporter within **3 working days** (per the commitment in each repo's `SECURITY.md`).
2. Score the issue (CVSS v3) and check the CISA KEV list.
3. **High/Critical (CVSS ≥ 7.0) or KEV listed** → notify the embargo subteam and engage PSIRT at `security@ubuntu.com`. Follow the embargo process below.
4. **Medium or below, no active exploit** → standard fix-and-release. No embargo required. Still give PSIRT 24-hour notice before the release (see below).

## Embargo handling (SEC0061 / Vulnerability Embargo Policy)

Four hard rules govern embargoed issues:

- **Need-to-know only.** Embargo details — the vulnerability, the fix, the timeline — are shared only with named embargo subteam members and PSIRT. Do not share with the broader team, upstream maintainers, or vendor partners without PSIRT's explicit authorisation.
- **≤ 90-day cap.** Canonical will not hold an embargo beyond 90 days from the initial report. If a fix cannot ship within 90 days, contact GRC/OCISO (`security@canonical.com`) for a Risk Acceptance Form before the deadline.
- **No silent patching.** A security fix cannot be committed to a public branch or shipped without a corresponding public advisory, unless GRC has approved a silent patch via the RAF process. A "quiet" commit to `main` counts as silent patching.
- **4-hour accidental-disclosure notification.** If embargoed information is accidentally disclosed — a premature public commit, a message outside the embargoed group, a public advisory filed before the fix ships — notify PSIRT at `security@ubuntu.com` within **4 hours** of discovery.

**During an embargo:**

- Coordinate via Launchpad private security bug or encrypted email. Not Mattermost, not a public GitHub issue.
- Classify all content at the **Strictly Confidential** level (see Information classification below).
- Develop the fix on a private fork branch; do not open a public PR or push to `main` until the advisory is ready to go.
- Track the 90-day clock from the date of first report. Alert PSIRT if the fix is at risk of missing the window.

## The standing Charm Tech embargo subteam

The embargo subteam is the minimal standing group authorised to hold Strictly Confidential embargoed information on behalf of Charm Tech. Its purpose is to limit need-to-know to a defined roster rather than spreading it across the full team.

**Subteam members: TBD — to be named before publication.**  
*(Target: 2–3 members. This placeholder must be replaced with named individuals before this document is considered active. Until named, the on-point engineer and the Charm Tech engineering lead are the provisional contacts.)*

**Subteam charter:**

- **Scope.** The subteam handles embargoed vulnerability information for all Charm Tech repos: operator, pebble, jubilant, pytest-jubilant, charmlibs, concierge, charm-ubuntu, api_demo_server, and any successors.
- **Need-to-know discipline.** Only subteam members receive embargoed details. If implementing a fix requires involving someone outside the subteam, brief them on exactly what they need to develop the fix — no wider context.
- **Embargo clock.** The subteam tracks the 90-day embargo deadline. If a fix is unlikely to ship before day 85, the subteam escalates to the Charm Tech engineering lead and PSIRT.
- **Accidental-disclosure response.** Any subteam member who discovers an accidental disclosure is responsible for sending the 4-hour notification to PSIRT — regardless of time zone or who caused the disclosure.
- **Availability handoff.** If a subteam member will be unavailable during an active embargo (holiday, sick leave), they must hand off explicitly to another subteam member or the engineering lead. Embargoes must not go unmonitored.

## 24-hour notice to PSIRT before a security release

Before publishing any security fix or advisory, give PSIRT **at least 24 hours' notice**, regardless of severity.

1. Email `security@ubuntu.com` with subject: `[24h notice] <product> <version> security release`.
2. Include: CVE or advisory ID (if already assigned), planned release time in UTC, affected version range, and a one-sentence description of the issue class.
3. Wait for PSIRT acknowledgement before publishing. If no acknowledgement after 12 hours, follow up directly.

PSIRT uses this window to:
- Assign a CVE if none exists (Canonical is a CNA).
- Coordinate with downstream distributors and other affected vendors.
- Prepare an Ubuntu Security Notice (USN) if needed.

## SECURITY.md routing

Every Charm Tech repo's `SECURITY.md` points reporters to the repo's GitHub Security Advisory and to `security@ubuntu.com`. When a report arrives through either route it lands with the on-point engineer.

**Routing flow:**

```
Reporter → repo Security Advisory  or  security@ubuntu.com  or  Launchpad private bug
  ↓
On-point engineer (triage; 3-working-day acknowledgement SLA)
  ↓
High/Critical (CVSS ≥ 7.0) or KEV listed?
  Yes → notify embargo subteam + engage PSIRT → embargo process above
  No  → standard fix + advisory; 24h PSIRT notice before release
```

**Per-repo advisory links** (reporters are directed here from each `SECURITY.md`):

| Repo | GitHub Security Advisory |
|---|---|
| canonical/operator | https://github.com/canonical/operator/security/advisories/new |
| canonical/pebble | https://github.com/canonical/pebble/security/advisories/new |
| canonical/jubilant | https://github.com/canonical/jubilant/security/advisories/new |
| canonical/pytest-jubilant | https://github.com/canonical/pytest-jubilant/security/advisories/new |
| canonical/charmlibs | https://github.com/canonical/charmlibs/security/advisories/new |
| canonical/concierge | https://github.com/canonical/concierge/security/advisories/new |
| canonical/charm-ubuntu | https://github.com/canonical/charm-ubuntu/security/advisories/new |
| canonical/api_demo_server | https://github.com/canonical/api_demo_server/security/advisories/new |
| canonical/charm-tech | https://github.com/canonical/charm-tech/security/advisories/new |

## Information classification (SEC0061)

During and after an embargo, classify all materials per these three levels:

| Level | Meaning | Applies to |
|---|---|---|
| **Strictly Confidential** | Need-to-know only; may not be shared outside named recipients without explicit PSIRT or GRC authorisation | Embargoed vuln details, exploit PoC, fix code before disclosure, embargo timeline |
| **Internal** | Canonical staff; not for external parties | Post-disclosure retrospectives, internal advisory drafts, internal status updates |
| **Public** | No restriction | Published CVEs, merged GitHub Security Advisories, Ubuntu Security Notices, the shipped fix |

Default during an embargo: **Strictly Confidential** until the advisory is public. Downgrade to Internal for internal-only retrospectives; to Public once advisory and fix are live.

## When this playbook applies

**Mandatory** (SEC0037/SEC0038 requirements triggered):

A product has a mandatory PSIRT engagement obligation when it carries an LTS or customer security commitment **and** a High/Critical (CVSS ≥ 7.0) or KEV-listed issue arises. In the current Charm Tech estate this means **pebble** (classified Component & Platform; ships inside customer-facing products). When pebble has a qualifying issue, every step in this playbook is required.

**Best-of-class (recommended, not mandated by the SEC0023 matrix) for:**

- **operator, jubilant, pytest-jubilant, charmlibs, concierge** — Tools & frameworks. The SSDLC matrix does not mandate PSIRT coordination for this class, but the contacts and routing are already wired and the overhead is low. Use this playbook for any High/Critical finding.
- **charm-ubuntu, api_demo_server** — same guidance as tools & frameworks.
- **charm-tech** (this repo) — internal tooling; best-of-class.

**Out of scope for this playbook:**

- Penetration testing (SEC0029) — centrally prioritised by the CISO Office.
- Threat modeling (SEC0028) — per-product process documented separately.
- Risk Acceptance Form submissions — contact GRC/OCISO at `security@canonical.com`.
- TIOBE TQI security-score gaps — tracked in the cycle's SSDLC Jira epic.

## Quick reference

| Contact | Purpose |
|---|---|
| `security@ubuntu.com` | Incoming reports, 24h release notice, PSIRT engagement, accidental-disclosure notification |
| `security@canonical.com` | GRC/OCISO: Risk Acceptance Forms, exception requests, policy questions |
| `~SSDLC` Mattermost + SSDLC Office Hours | SSDLC compliance questions, tool support (TIOBE TICS, secscan, SBOM) |
| Launchpad private security bug | Embargo-period coordination channel (private by default) |
