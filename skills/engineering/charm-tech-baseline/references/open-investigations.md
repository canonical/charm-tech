# Open investigations

Items the 26.10 cycle could not close because they're waiting on
external triggers. When auditing, treat these as "watch but don't
flag as a gap" — the audit can note the status but should not push
the repo to adopt yet.

## `uv audit` — wait for stable release

**Status:** Preview as of 2026-06-27. uv 0.11.21 ships the subcommand
by default with an `--preview-features audit-command` opt-in flag to
silence the experimental warning. The roadmap tracker
[astral-sh/uv#18506](https://github.com/astral-sh/uv/issues/18506)
shows 1 / 61 sub-items complete; meaningful MVP work (SARIF output,
config-based ignores, fix mode, PEP 792 yanked-distribution flagging)
is still in flight.

**Plan when stable:**

- Replace `pip-audit` on the non-product tier (charmhub-listing-review,
  api_demo_server, hyrum).
- Add `uv audit` to the product tier (operator, jubilant,
  pytest-jubilant, charmlibs) as a belt-and-braces CI gate alongside
  Dependabot. Does not change SSDLC compliance — Dependabot continuous
  monitoring + per-release secscan still covers the requirement.
- Configuration: per-advisory ignores in `[tool.uv.audit] ignore =
  [...]` in `pyproject.toml`. Job-level `UV_MALWARE_CHECK: "1"` for
  install-time malware checks.

**Baseline scan (2026-06-27, advisory only):**

- jubilant — `cryptography 46.0.7` (GHSA-537c-gmf6-5ccf, bundled
  OpenSSL, fixed 48.0.1) + `pytest 8.3.5` (GHSA-6w46-j5rx-g56g,
  tmpdir, fixed 9.0.3).
- pytest-jubilant — `pytest 8.3.5`.
- charmlibs/nginx_k8s — `pytest 8.3.5`.
- charmlibs/rollingops — `cryptography 46.0.5` with 3 CVEs (bundled
  OpenSSL, buffer overflow, DNS name constraint). Highest-priority of
  the lot since `cryptography` is a runtime dep there. Single bump to
  `>=48.0.1` clears all three.
- operator, charmhub-listing-review, api_demo_server, hyrum, other
  charmlibs packages — clean.

## OpenSSF Scorecard — operator in progress, rest gated

**Status:** Adopt — operator in progress, current score **8.1/10**.
Other 9 repos gated behind operator's adoption so they can pick up
whatever score-improvement conventions land there first.

**Decision basis:** OpenSSF Scorecard is an Astral best-of-class extra,
*not* a GRC/OCISO ask.

**Plan:** wait for operator's adoption to settle (improvements on
branch-protection wiring, allowlisted-checks shape, badge rendering),
then sweep the workflow + consider a badge across the other 9 repos.

## Go-module minimum-release-age — no native equivalent

**Status:** Gap identified 2026-07-02 while rolling out
`exclude-newer = "7 days"` across the fleet's uv repos (see
[`decisions.md`](decisions.md) and the `uv-exclude-newer` check).

The Python side is covered: `[tool.uv].exclude-newer = "7 days"`
gives every uv resolution path (manual `uv add`, `uv lock` regens,
uvx bootstraps, CI re-resolves) a rolling 7-day quarantine on fresh
releases, complementing the existing Dependabot cooldown.

**Go has no native equivalent.** Go's module resolver offers:

- `go.sum` + `-mod=readonly` (default) — analogous to `uv.lock` +
  `--locked`. Prevents silent modification of go.mod/go.sum during
  `go build`/`go test`. Already in place on pebble and concierge.
- Dependabot / Renovate `minimumReleaseAge` — works for the `gomod`
  ecosystem, so the Dependabot-authored path is covered.

But there is no `go.mod` directive, `GOFLAGS` value, or `go` env var
that says "refuse to consider modules published in the last N days"
during resolution. So the residual vector — a developer running
`go get -u <mod>@latest` or `go mod tidy` locally, pulling a fresh
release straight into go.sum before Dependabot could have cooled it
down — is unaddressed on pebble and concierge.

**Options considered:**

1. **Custom CI check** — script that reads go.sum, queries
   `proxy.golang.org` for each module's `.info` (which has a `Time`
   field), fails if any version is younger than 7 days. Bespoke;
   ~30 lines of Bash/Go. Would sit alongside `govulncheck`.
2. **Private module proxy with a cooldown policy** — Athens (open
   source) or JFrog Artifactory. Whole team would need to point
   `GOPROXY` at it. Overkill for two Go repos.
3. **PR-diff inspection** — only cross-check go.sum entries added by
   the PR. Cheaper variant of (1).
4. **Accept the residual risk** — pebble and concierge have small
   dependency graphs, tight review cadence, and are already covered
   by `govulncheck` + `dependency-review-action` (`fail-on-severity:
   high`, fleet-wide).

**Plan:** deferred. Watch `golang/go` issues for a native
`min-release-age` proposal. If the fleet's Go footprint grows or a
concrete incident traces to this vector, revisit and default to
option 3 (PR-diff inspection — smallest surface area, no proxy
infra). Not a `fail` in the audit report on Go repos today.

A check should not flag pebble or concierge for missing a Go-side
release-age control in the 26.10 cycle.

## `pypa/*` ref-pin posture — resolved

**Resolved:** the team took option (a) — tighten to SHA-pin — and
extended it to the whole allowlist (`actions/*`, `github/*`, `pypa/*`,
`canonical/*`). Every third-party action pins to a SHA, no exceptions.
See [`decisions.md`](decisions.md). `.github/zizmor.yaml` config files
are no longer needed; the check ([`scripts/checks/gha-sha-pinning.sh`](../scripts/checks/gha-sha-pinning.sh))
flags any non-SHA `uses:` ref.
