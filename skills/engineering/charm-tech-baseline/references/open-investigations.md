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

## `pypa/*` ref-pin posture — team discussion

**Status:** Awaiting team discussion.

**Issue:** the existing `pypa/*` ref-pin exception (see
[`decisions.md`](decisions.md)) was rationalised as "trusted PyPA org,
major tag is fine."

**Options:**

- (a) Tighten to SHA-pin: ~6-line edit across 6 workflow files +
  drop the `pypa/*` exception from 4 `zizmor.yaml` files. Mechanical,
  low-risk.
- (b) Keep the exception but require the team to acknowledge the
  moving-branch posture explicitly.

**Audit behaviour:** treat a `pypa/*@release/v1` ref as a *note* (not a
gap) until the team picks (a) or (b).
