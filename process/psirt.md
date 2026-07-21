# Charm Tech PSIRT Engagement Playbook

Operational guide for the person on-point when PSIRT contacts Charm Tech or when a vulnerability surfaces from one of our repos. For policy rationale see [SEC0026](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---vulnerability-response), [SEC0037](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---psirt/ssdlc---psirt-coordination-team%27s-vulnerability-response-guidelines), and [SEC0061](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---additional-documents/ssdlc---vulnerability-response-standard); for the Canonical disclosure timeline see the [Ubuntu Security disclosure and embargo policy](https://ubuntu.com/security/disclosure-policy).

## Engagement entry points

Reports reach us three ways:

| Channel | Typical source |
|---|---|
| `security@ubuntu.com` | PSIRT-coordinated disclosures; reporters following our SECURITY.md |
| Launchpad private security bug | PSIRT-initiated or reporter-initiated; private by default |
| GitHub Security Advisory | Reporter uses the **Report a vulnerability** button in a repo's Security tab |

Every repo's advisory form is at `https://github.com/canonical/<repo>/security/advisories/new`, and every repo's `SECURITY.md` points reporters there and to `security@ubuntu.com`.

**On-point engineer**: the team member holding the security-contact role this pulse. There's no formal rotation yet; the manager (Ben Hoyt) is the fallback.

When a report arrives:

1. Acknowledge to the reporter within **3 working days** (per the commitment in each repo's `SECURITY.md`).
2. Score the issue (CVSS 3.1/4.0, or Ubuntu Priority) and check the CISA KEV list.
3. If it's High/Critical (CVSS ≥ 7.0) or KEV-listed, notify the embargo subteam and engage PSIRT at `security@ubuntu.com` — the embargo rules below apply.
4. Anything lower, with no active exploit, is a standard fix and release: no embargo, but PSIRT still gets the 24-hour notice.

## Embargo handling (SEC0061 / Vulnerability Embargo Policy)

Hard rules for embargoed issues:

- **Need-to-know only.** Embargo details (the vulnerability, the fix, the timeline) are shared only with the embargo subteam and PSIRT. Do not share with the broader team, upstream maintainers, or vendor partners without PSIRT's approval.
- **90-day cap.** An embargo must not extend beyond 90 days from the initial report without GRC/OCISO approval (`security@canonical.com`) — ask before the deadline, not after.
- **7-day floor.** When PSIRT is coordinating, don't set an embargo shorter than 7 days without PSIRT's approval, even if the fix is ready sooner.
- **No silent patching.** Don't commit a fix to a public branch or ship it without a public advisory unless GRC has approved a silent patch (RAF). A quiet commit to `main` counts.
- **Accidental disclosure.** If embargoed information leaks (a premature public commit, a message outside the embargo group, a public advisory filed before the fix ships), notify PSIRT and GRC **immediately** (`security@ubuntu.com`, `security@canonical.com`) and the other embargo parties (reporter, upstream) within **4 hours** of discovery. Make the leaked material unavailable, then follow the [Vulnerability Embargo Policy](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---embargo-policy) for the investigation and retrospective.

**During an embargo:**

- Coordinate via the Launchpad private bug, the GitHub private advisory, or email; Mattermost only in DMs or a private channel limited to the embargo group. Never a public issue, PR, or public channel.
- All content is **Strictly Confidential** until the advisory is public; after disclosure, classify materials per the [Vulnerability Response Standard](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---additional-documents/ssdlc---vulnerability-response-standard) (retrospectives and draft comms stay Internal).
- Develop the fix on a private fork branch ([GitHub's temporary private fork](https://docs.github.com/en/code-security/tutorials/fix-reported-vulnerabilities/collaborate-in-a-fork)); do not open a public PR or push to `main` until the advisory is ready to go.
- Track the 90-day clock from the first report. Alert PSIRT if the fix is at risk of missing the window.

## The standing Charm Tech embargo subteam

The subteam is the minimal standing group authorised to hold embargoed information on behalf of Charm Tech (the embargo policy requires each product team to define one):

- Harry Pidcock (Juju, Pebble, Go)
- Tony Meyer (Ops, Python)
- Ben Hoyt (manager; the policy requires the management chain in the embargo)

**Charter:**

- **Scope.** Embargoed vulnerability information for all Charm Tech repositories.
- **Need-to-know.** Only the subteam and PSIRT hold embargoed details. If developing a fix needs someone else, tell them only what they need to build the fix. Membership changes are agreed with the manager and recorded here.
- **Embargo clock.** Track the 90-day deadline; if the fix looks unlikely to ship by day 85, escalate to the manager and PSIRT.
- **Accidental-disclosure response.** Any member who discovers an accidental disclosure is responsible for the immediate PSIRT and GRC notification (see Embargo handling above), regardless of who caused it.
- **Availability handoff.** Before going on leave during an active embargo, hand it to another member or the manager — an embargo is never unmonitored.

## 24-hour notice to PSIRT before a security release

Before publishing any security fix or advisory, whatever the severity, email PSIRT (`security@ubuntu.com`) at least 24 hours ahead with the planned release time (UTC), the affected versions, and the CVE or advisory ID if one exists. PSIRT uses the window to assign a CVE if none exists (Canonical is a CNA), coordinate downstreams, and prepare an Ubuntu Security Notice if needed.

## When this playbook applies

- **Mandatory:** PSIRT coordination is required (SEC0026) when a product with an LTS or customer security commitment has a High/Critical or KEV-listed issue. For Charm Tech that means **Pebble** — our only Component & Platform product, shipped inside customer-facing products.
- **Best-of-class:** every other Charm Tech repo is Tools & frameworks or internal tooling, where PSIRT coordination isn't mandated — but the contacts and routing are already wired and the overhead is low, so use this playbook for any High/Critical finding regardless.
