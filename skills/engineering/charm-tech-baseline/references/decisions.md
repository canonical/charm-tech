# Settled decisions and carve-outs

These are the **settled** decisions from the 26.10 cycle. Do not
reopen without new evidence; do not flag them as "gaps" in an audit
report.

## Admin bypass — `pull_request`, with an emergency escape hatch

Charm Tech ruleset `bypass_actors` = **`Admins` / `pull_request`** (not
`Admins` / `always`, not full no-bypass). Admins still go through a PR
— so reviews and required checks remain visible — rather than pushing
straight to a protected branch. The bypass is deliberately retained as
an emergency escape hatch (broken CI blocking an urgent fix, incident
response).

A repo configured with full no-bypass is **not** a gap — it is a
stricter policy. A repo configured with `Admins` / `always` **is** a
gap — flag it.

## SHA-pinning — every third-party action, no exceptions

Every Charm Tech repo SHA-pins **every** third-party GitHub Action.
`actions/*`, `github/*`, `pypa/*`, `canonical/*` — all pin to a commit
SHA, same as any other third-party action. The prior ref-pin carve-out
for GitHub-owned and PyPA-owned actions has been retired: the `pypa/*`
open investigation surfaced `release/v1` as a moving *branch* (not a
tag), and rather than special-case one org and leave the others on a
weaker rationale, the whole allowlist is dropped. Uniform SHA-pinning is
the policy.

The standard form is `actions/checkout@<40-char-sha>. # v4.x.y` — SHA
first, human-readable tag in a trailing comment so Dependabot can bump
both together.

A `.github/zizmor.yaml` config file is **no longer required**. zizmor's
default `unpinned-uses` rule already enforces SHA-pinning across the
board; the previous config existed only to carry the now-retired
allowlist. Existing `.github/zizmor.yaml` files that only encode the old
allowlist should be deleted (the check no longer looks for a config
file, only for a workflow that invokes zizmor).

A repo with `actions/checkout@v4`, `pypa/gh-action-pypi-publish@release/v1`,
or `canonical/foo@v2` **is** a gap. A repo with all `uses:` refs pinned
to 40-char SHAs is not.

## Tool pinning — `pyproject.toml` is the source of truth

All tool version pins belong in `[dependency-groups]` in
`pyproject.toml`, locked via `uv.lock`. This applies across every
invocation surface — pre-commit hooks (`language: system` calling the
tool from the lockfile), CI, local dev. **No tool versions in
`.pre-commit-config.yaml` `rev:` fields, no version pins in CI
workflows.**

## pip-audit (non-product tier only) + Dependabot everywhere

Two-tier:

- **Product tier** (operator, jubilant, pytest-jubilant, charmlibs):
  Dependabot only. Per-release secscan with `--ssdlc-*` covers the
  SSDLC requirement.
- **Non-product tier** (hyrum, charmhub-listing-review,
  api_demo_server): pip-audit in CI alongside Dependabot.

Forward note: planned replacement of `pip-audit` with `uv audit` once
stable — see [`open-investigations.md`](open-investigations.md).

## Linear history

Required across Charm Tech repos via CRA. Squash + linear merge
strategy.

## Required status checks pinned to the GitHub Actions app

`integration_id = 15368` on every CRA ruleset for Charm Tech repos.
Without this, any app or PAT can satisfy a rule by posting a status of
the same name. Done for Charm Tech in
[canonical/canonical-repo-automation#873](https://github.com/canonical/canonical-repo-automation/pull/873)
(merged 2026-06-09).

This applies to **Canonical-managed rulesets only**, which are
configured centrally in `canonical-repo-automation`, not per-repo. A
personal-tier audit must not flag this.

## Immutable releases — on by default; blocked on tooling for some

ON for: operator, jubilant, pytest-jubilant, charmhub-listing-review,
hyrum.

OFF (legitimate blocker) for: concierge (goreleaser incompat —
[canonical/concierge#172](https://github.com/canonical/concierge/issues/172)),
pebble (snap build —
[canonical/pebble#856](https://github.com/canonical/pebble/issues/856)).

OFF (action needed) for: api_demo_server (no releases yet; toggle when
first release approaches), charmlibs.

A check for immutable releases must distinguish "blocked on known
tooling" from "needs toggling".

## SEC0045 applicability — per-product

Resolved 2026-06-09:

- **Done**: ops (operator#1905), pebble (pebble#666)
- **In scope this cycle**: concierge (concierge#208).
- **Deferred**: charmlibs (future cycle).
- **Out of scope**: jubilant, pytest-jubilant (no user/admin/auth
  surface), charm-ubuntu.

A check should not flag "no SEC0045 events" on jubilant or
pytest-jubilant.

## CODEOWNERS — only required when membership exceeds the Charm Tech team

Resolved 2026-07-02. The Canonical Security "Repository security" and
"How-To: Secure a repo" pages recommend a `CODEOWNERS` file with
code-owner review required, at minimum for `.github/workflows/`.

For a repo whose maintainer set is exactly the Charm Tech team, a
`CODEOWNERS` file adds no filtering signal over the existing
required-review rule (every PR would need review from the same people
who already review every PR). Overhead without benefit.

**A `CODEOWNERS` file is only required for a charm-tech repo when its
maintainer/contributor set is broader than the Charm Tech team** —
external contributors, cross-team ownership, or per-directory owners
mapping to different sub-teams. In this cycle, that's **charmlibs only**
(has a substantive `CODEOWNERS` mapping to `@canonical/charmlibs-maintainers`).

A repo without `CODEOWNERS` whose maintainer set is the Charm Tech team
is **not** a gap. A check should not flag it. A check *should* flag a
CODEOWNERS file that references only the Charm Tech team wholesale (no
benefit; adds review friction) — i.e. the anti-pattern is a file that
does nothing.

## PR-review ergonomics — conversation resolution and dismiss-stale-on-push not required

Resolved 2026-07-02. The Canonical Security "How-To: Secure a repo"
page recommends both `Require conversation resolution` and `dismiss
stale reviews on new commits` on protected branches. The team has
decided **against** requiring either at this time.

**Conversation resolution required.** Rationale: the team already
treats unresolved threads as a review-blocker socially; making it a
merge gate adds friction (author must chase every threaded "nit" the
reviewer intended as advisory), and every pushed follow-up commit
would need a fresh comment-resolution round. Net-negative for
Charm-Tech-sized PRs where the reviewer set is small and consistent.

**Dismiss stale reviews on new commits.** Rationale: most Charm Tech
PRs iterate quickly under reviewer feedback; auto-dismissing on every
push makes even trivial rebases / typo fixes re-trigger the full
review round. The `Require last push approval` flag (already
recommended in the CRA baseline) covers the substantive risk
(unreviewed content sneaking in after approval) without the churn of
full dismissal.

Both to be re-evaluated in a future cycle (26.10+1), especially if the
team scales or if we see a real incident tied to their absence.

A repo without `require_conversation_resolution` or without dismiss-
stale-on-push on its default-branch ruleset is **not** a gap in this
cycle. A check should not flag either.

## Signed commits — not required this cycle

Resolved 2026-07-02, after the Canonical Security "Repository security"
and "How-To: Secure a repo" pages (published Jul 01, 2026) recommended
`Require signed commits` on protected branches.

The team has decided **against** requiring signed commits at this time.
Rationale: the onboarding cost across current + occasional contributors
outweighs the marginal supply-chain benefit while the org allowlist,
SHA-pinned actions, branch protection, PR review, and required checks
are already in place. To be re-evaluated in a future cycle (26.10+1),
particularly if Security makes it an org-level baseline.

A repo without `require_signed_commits` on its default-branch ruleset
is **not** a gap in this cycle. A check should not flag it.
