# Tools we measured and skipped

The 26.10 cycle piloted these tools against the actual Charm Tech
estate and chose not to adopt them. Each entry records the
measurement, the verdict, and what would have to change for the
verdict to flip. **Do not re-recommend any of these in an audit report
unless new evidence appears.**

## `harden-runner` (StepSecurity)

**Verdict:** Skip. **Date:** 2026-06-27.

**Basis:** Charm Tech does not want to take a third-party action
dependency for runtime egress monitoring across every workflow, even
in audit-mode where the data stays on-runner. The action itself is a
supply-chain dependency for every workflow that uses it.

**What would flip the verdict:** GitHub's native L7 egress firewall
hits GA; at that point use the native control instead. Adopting
harden-runner in the interim is not worth the migration.

## `actionlint`

**Verdict:** Skip. **Date:** 2026-06-27.

**Basis:** Measured against the live estate (operator, pebble,
jubilant, pytest-jubilant, charmlibs, concierge,
charmhub-listing-review, api_demo_server, hyrum). 32 total findings
resolved to **zero real bugs**:

- ~25 self-hosted runner-label warnings (silenceable via a one-time
  `.github/actionlint.yaml` config).
- 5 `matrix.disabled` references in operator's
  `observability-charm-tests.yaml` — intentional scaffolding (disable
  hook left in place for future use).
- 1 `schedule.timezone:` on jubilant — GitHub supports it; actionlint's
  schema is stale.

Forward value is "catches future expression typos at PR time" — not
enough to anchor adding a third-party action across 10 repos when
nothing in the corpus is wrong.

**What would flip the verdict:** actionlint releases address the
stale-schema gaps (timezone, others), AND a wave of new GHA syntax is
adopted that materially raises the typo-rate.

## `pydoclint`

**Verdict:** Skip. **Date:** 2026-06-27.

**Basis:** Piloted on jubilant (65 findings) and operator (282
findings) with the right config (`--style=google
--arg-type-hints-in-docstring=False --check-return-types=False`).
After triage of representative samples:

- DOC103 / DOC101 sig-drift cluster: almost entirely varargs naming
  pedantry (`*foo` in signature, `foo` in docstring without `*`) or
  cases where the existing prose already conveys the arg purpose
  clearly (`Framework.observe`, `Status.get_units`, `Container.exec`
  uses a Sphinx cross-reference to `pebble.Client.exec`).
- DOC502 / DOC503 raises mismatches: transitive blindness (pydoclint
  only sees direct `raise` statements; doesn't follow helpers).
- DOC606 inline-attribute findings: PEP 257 inline attribute
  docstrings are intentionally the chosen style.

After filtering, **0 real bugs** across both pilots. Adding pydoclint
as a gate would lock in style preferences (mandatory `Returns:` /
`Raises:` / `Args:` sections) that aren't currently the estate's
convention.

**What would flip the verdict:** the team decides it *does* want
mandatory `Returns:` / `Raises:` / `Args:` sections everywhere as a
style policy — then pydoclint becomes a way to enforce that decision.

## `prek` (Rust pre-commit replacement)

**Verdict:** Skip. **Date:** 2026-06-27.

**Basis:** The "10× faster" claim is on prek's *framework startup
overhead*, not on the hook work itself. Charm Tech pre-commit wall-clock
is dominated by ruff (already Rust), codespell, zizmor, pyright — so the
framework speedup doesn't show up where engineers would notice. The
"no Python install" benefit is hollow for a Python-heavy team where
every developer already has Python. Drop-in compatibility is
almost-but-not-quite — occasional divergence on `language: python`
hook installs.

**Cost to switch:** CI workflow changes per repo, CONTRIBUTING /
dev-setup updates, onboarding ambiguity (two install paths to
document), cross-team friction.

**What would flip the verdict:** pre-commit is somehow removed from
maintenance and prek becomes the de-facto path, OR prek extends past
1.0 with hardened compatibility guarantees AND a meaningfully
different feature set.

## `shellcheck`

**Verdict:** Skip. **Date:** 2026-06-27.

**Basis:** Surveyed the entire estate — only 10 real `.sh` files total
(1 pebble, 7 charmlibs test helpers, 1 charmhub-listing-review, 1
api_demo_server; ~300 lines combined). `shellcheck` reports **zero
findings** against all of them.

**What would flip the verdict:** estate grows a non-trivial shell
codebase (anything more than mechanical test pack helpers).

## `yamllint` / `hadolint` / `dprint`

**Verdict:** Skip (carried over from the original survey — not
re-measured).

**Basis:** No high-value target on this estate; ruff covers most of
the formatting role.

## `hypothesis` property-based testing

**Verdict:** Out of scope for repo-setup. **Date:** 2026-06-27.

**Basis:** Adopting Hypothesis well requires per-test engineering
judgement; not a repo-setup sweep decision.

## `pytest-xdist`

**Verdict:** Skip estate-wide. Adopt only where the suite is already
long enough to dominate xdist's startup cost. **Date:** 2026-06-15.

**Basis:** Measured wall-clock against jubilant (279 tests),
pytest-jubilant (27), hyrum (93), charmhub-listing-review (104). Every
suite went 2× to 13× **slower** under `-n auto` because per-worker
startup dominates. operator is currently the only Charm Tech Python
suite long enough to clear the threshold (already on `-n auto`).

**What would flip the verdict:** a suite grows past ~3s of wall-clock
without xdist; then re-measure.
