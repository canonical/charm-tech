# OP???: Dependabot config conventions for Charm Tech repos

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Process |
| Created | 16 Jun 2026 |

## Abstract

This spec proposes a canonical `.github/dependabot.yml` shape for
Charm Tech repositories, plus the per-repo deltas needed to apply it. The aim
is **fewer, larger, better-batched PRs at a steady cadence** without
lengthening security-patch latency. Adoption should materially reduce the
~58 Dependabot PRs/month the team currently fields across ten repos. CVE
patches stay fast because they are raised by the repo-level "Dependabot
security updates" toggle (managed group-wide via canonical-repo-automation),
which is event-driven and independent of `dependabot.yml`'s schedule.

## Rationale

The Charm Tech repos emit a steady stream of Dependabot PRs. The cost is
**reviewer time and context-switching**, not the updates themselves:

* Even a clean patch-bump needs eyes on the diff and on CI.
* Five PRs in a morning, each ~5 min, is closer to an hour once the
  reviewer has re-loaded the repo's context.

When something *does* need to land urgently (typically a CVE patch),
being two minors behind is fine; being a major behind is not, and
shipping a major as a security fix is the worst time to do it.

The strategy is not to *update less*. It is to (a) batch routine bumps along
sensible seams, (b) rely on the repo-level "Dependabot security updates"
toggle for the CVE path (it is event-driven, so batching the routine lane
does not delay CVE response), and (c) give majors a longer cooldown window
and their own PR so they cannot silently ride a patch bundle.

### Goals

* Reduce reviewer load per repo without losing coverage of patch + minor bumps.
* Keep CVE-patch latency at "next day" or better on every repo.
* Make majors visible: they get their own PR with a longer cooldown.
* Normalise the shape of `dependabot.yml` across repos so drift is one-glance
  visible. (Also, we should normalise the `.yml`/`.yaml`.)

### Non-goals

* Switching from Dependabot to Renovate.
* Auto-merge rules. Humans still merge; this spec is config-tuning only.
* **Suppressing transitive bumps** is *not* a non-goal: it is open work,
  blocked on upstream Dependabot. See [§Transitive dependencies](#transitive-dependencies)
  and the corresponding open question.

## Specification

### Baseline (snapshot, 2026-06-08)

The shape proposed below is grounded in 90 days of actual Dependabot PR
history. Window: `created:>=2026-03-08`, captured 2026-06-06. 90 days
provides a good window size, but this is slightly complicated by
including two different dependabot config shapes during the window.

| Repo | Lang | Ecosystems | Schedule | Cooldown | Grouping | Security lane |
|---|---|---|---|---|---|---|
| `operator` | Python | github-actions, uv ×4 (root + 3 examples) | monthly | 7d | none | no |
| `charmlibs` | Python | github-actions, pip (root + `/[a-z]*`) | monthly + daily security-only | 7d on routine; none on sec | `test-deps: ["*"]` | yes |
| `jubilant` | Python | github-actions, uv | monthly | 7d | none | no |
| `pytest-jubilant` | Python | github-actions, uv | monthly | 7d | none | no |
| `pebble` | Go | github-actions, gomod | monthly / daily security-only (gomod) | 7d on gh-actions; none on sec | none | yes |
| `concierge` | Go | github-actions, gomod | monthly | 7d | none | none | no |
| `api_demo_server` | Python | github-actions, pip, docker | monthly | 7d | none | no |
| `charmhub-listing-review` | Python | github-actions, uv | monthly | 7d | none | no |
| `charm-ubuntu` | Python | github-actions, pip | monthly | 7d | none | no |
| `hyrum` | Python | github-actions, uv | monthly | 7d | none | no |

Aggregate noise across the ten in-scope repos in the 90-day window:

| Metric | Value |
|---|---|
| Total Dependabot PRs | **174** |
| Per-month average across the ten repos | **~58** |
| Open at snapshot | 14 |
| Merged in window | 122 |
| Closed-without-merge | 38 (22 %) |

Per-repo volume (sorted high to low):

| Repo | Total | Merged | Open | Closed-unmerged | TTM median |
|---|---|---|---|---|---|
| `operator` | 42 | 20 | 1 | 21 | 3.9 d |
| `charmhub-listing-review` | 26 | 25 | 0 | 1 | 26 min |
| `charmlibs` | 22 | 10 | 10 | 2 | 3.2 d |
| `api_demo_server` | 21 | 15 | 1 | 5 | 6.0 d |
| `jubilant` | 17 | 15 | 1 | 1 | 1.3 h |
| `pytest-jubilant` | 15 | 11 | 0 | 4 | 4.0 d |
| `concierge` | 11 | 11 | 0 | 0 | 4.9 d |
| `charm-ubuntu` | 10 | 8 | 0 | 2 | 17 min |
| `pebble` | 6 | 4 | 1 | 1 | 40.3 h |
| `hyrum` | 4 | 3 | 0 | 1 | 5.0 h |

Two observations from this data drive the design:

1. **Grouping is essentially absent** outside `charmlibs`. Five small bumps
   become five PRs in every other repo. This is the single biggest noise
   source.
2. **`charmlibs`' grouped lane is not delivering**: 10 open PRs (45 % of
   its window) despite a wildcard `test-deps: ["*"]` group, because the
   group only targeted `directory: "/"` while the bumps were in
   `/interfaces/*`. The fix is sharper seams plus the right directory reach
   (see [§charmlibs delta](#charmlibs)).

**On CVE latency and the repo-level setting.** The `schedule:` field in
`dependabot.yml` governs *version-update* sweeps only. Security-update PRs
are driven by the **repo-level "Dependabot security updates" toggle**
(canonical-repo-automation sets `features.dependabot_security_updates = true`
group-wide for Charm Tech, see `groups/charm-engineering/charm-tech/repos/repos-settings.hcl`),
and open as soon as a matching GHSA advisory publishes, independent of any
YAML schedule. A monthly routine lane therefore does not delay CVE patches.
The two repos that currently ship a separate daily "security lane" in YAML
(`pebble` gomod, `charmlibs` pip) get nothing measurable from it that the
repo toggle does not already provide; this spec drops the pattern (see
[§no security lane in YAML](#no-security-lane-in-yaml)).

### The canonical template

Designed against `canonical/operator` (highest PR volume in the set, the
flagship). Root block only; per-ecosystem deltas in
[§Per-repo deltas](#per-repo-deltas).

```yaml
# Routine version-update sweeps only. CVE patches are raised by the
# repo-level "Dependabot security updates" toggle (managed in
# canonical-repo-automation: features.dependabot_security_updates = true),
# which is event-driven and does not honour the schedule below.
version: 2

updates:
  # ===================================================================
  # GitHub Actions: routine lane (monthly, single grouped PR)
  # ===================================================================
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
    open-pull-requests-limit: 5
    cooldown:
      default-days: 7
      semver-major-days: 14
    groups:
      actions:
        patterns:
          - "*"

  # ===================================================================
  # Python (uv): routine lane (monthly, grouped along three seams)
  # ===================================================================
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "monthly"
    labels:
      - "dependencies"
    open-pull-requests-limit: 5
    cooldown:
      default-days: 7
      semver-major-days: 14
    groups:
      # Linters / type-checkers / formatters. Majors ride along; we do not
      # pin these and a major ruff/pyright is low-risk to review in a batch.
      dev-tooling:
        patterns:
          - "ruff"
          - "pyright"
          - "ty"
          - "codespell"
          - "coverage"
          - "pre-commit"
          - "types-*"
      # Test runner + the jubilant/scenario test stack.
      test-deps:
        patterns:
          - "pytest"
          - "pytest-*"
          - "jubilant"
          - "ops-scenario"
      # Everything else, minor + patch only. A runtime MAJOR falls through
      # to its own ungrouped PR so it never silently rides a patch bundle.
      runtime:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"
```

### Design rationale: one lane per ecosystem

Per ecosystem, **one `updates:` entry**: the routine lane, `monthly`,
grouped, `open-pull-requests-limit: 5`. Batches the steady patch/minor
stream into a handful of grouped PRs per month.

<a id="no-security-lane-in-yaml"></a>

**No separate security lane in YAML.** GHSA-driven security PRs come from the
repo-level "Dependabot security updates" toggle, which is event-driven
(advisory publishes, alert raised, PR opened within minutes) and ignores
`dependabot.yml` schedules entirely. The toggle is set group-wide for
Charm Tech in canonical-repo-automation
(`features.dependabot_security_updates = true` in
`groups/charm-engineering/charm-tech/repos/repos-settings.hcl`).

A second `updates:` entry with `schedule: daily` and
`open-pull-requests-limit: 0`, as `pebble` and `charmlibs` currently ship,
adds no measurable benefit on top of the repo toggle: the daily schedule
only governs *version-update* sweeps (suppressed here by `limit: 0`
anyway), and security PRs are event-driven, not scan-driven. The pattern
is dropped from the canonical template; the comment at the top of
`dependabot.yml` points a reader at the repo setting instead.

If for any reason the repo toggle gets turned off, the recovery is to turn it
back on in canonical-repo-automation, not to paper over it in YAML.

### Group patterns

Validated against `operator`'s actual 90-day bump stream. Three Python seams
plus one actions group:

| Group | Patterns | Why these |
|---|---|---|
| `dev-tooling` | `ruff`, `pyright`, `ty`, `codespell`, `coverage`, `pre-commit`, `types-*` | Linters/checkers we do not pin; safe to batch including majors. `ruff` is a top-5 bump in `operator`/`jubilant`/`pytest-jubilant`/`charmhub-listing-review`. |
| `test-deps` | `pytest`, `pytest-*`, `jubilant`, `ops-scenario` | `pytest` is the single noisiest package in `charmlibs` (7×) and recurs everywhere. |
| `runtime` | `*` (catch-all), `update-types: [minor, patch]` | Everything else. The update-type filter means a runtime **major** matches no group and so gets its own ungrouped PR, so a major never silently rides a patch bundle. |
| `actions` | `*` | The github-actions surface is small and homogeneous; one group is plenty. |

**Docs-toolchain bumps are out of scope.** Version bumps for `sphinx`,
`furo`, `myst-parser`, and the rest of the docs stack are managed upstream
by the **Sphinx Stack** project rather than per-repo Dependabot, since the
docs stack is coupled and best updated together. The routine lane
structurally never sees these packages: docs deps are not present in the
tracked `uv.lock`/`requirements.txt` files, and no `dependabot.yml` entry
in this spec targets a `docs/` directory, so no `ignore:` block is needed.
Security PRs for docs packages still flow via the repo-level "Dependabot
security updates" toggle.

**Group precedence.** Dependabot assigns a dependency to the *first* matching
group in file order. `dev-tooling` / `test-deps` are listed before `runtime`,
so for example `ruff` lands in `dev-tooling` (all update-types), never in
`runtime`. The `runtime` catch-all is last and only claims minor + patch.

**Why not copy `charmlibs`' `test-deps: ["*"]`?** The baseline shows
`charmlibs` sitting on 10 open PRs (45 % of its window) *despite* that
group, because the grouped lane only targeted `directory: "/"` while the
bumps were in `/interfaces/*`. The lesson is the opposite of "one wildcard
group": sharper seams **plus** the right directory reach (see
[§charmlibs delta](#charmlibs)).

### Cooldowns and majors

* **`cooldown.default-days: 7`** everywhere (unchanged from baseline): gives
  a week for a bad release to be yanked before we look.
* **`cooldown.semver-major-days: 14`** is new: majors get a longer settle
  window to flush regressions. Cheap, and pairs with majors arriving as their
  own PR.
* **Majors as their own PR** is enforced *structurally*, not by `ignore:`:
  the `runtime` group's `update-types: [minor, patch]` lets a runtime major
  fall through to an individual PR. This deliberately avoids the
  hand-maintained per-directory `ignore:` lists that the baseline caught
  drifting (`PyYAML` present in one of `operator`'s example lists, missing
  from the other).

### Transitive dependencies

`uv.lock` and `pip` lockfile bumps for **transitive** (indirect) deps,
meaning things we did not pick that get pulled in through someone else's
range, show up as Dependabot PRs and account for a non-trivial chunk of the
noise. The canonical template does **not** filter them; they match the
`runtime` group's `"*"` pattern (by name) with `update-types: [minor,
patch]`, so they ride the monthly `runtime` PR alongside direct deps. This
is honest about the volume but does not reduce it.

The clean fix is "raise PRs only for *direct* deps; let transitives move
when something direct pulls them, and rely on the repo-level security
toggle to catch CVEs in transitives in between". The supported way to
express that in `dependabot.yml` is `allow: [{ dependency-type: "direct" }]`
on the relevant entries.

**We are not doing that yet** because the Dependabot integration for uv
(the dominant ecosystem here, and where most repos are headed) is not
ready:

* [dependabot-core#13202](https://github.com/dependabot/dependabot-core/issues/13202):
  uv classifies every dep as `production`, so `dependency-type`-based
  filtering is incomplete in practice. Until that lands, an `allow:` filter
  on a uv entry would silently filter the wrong set.

`pip` entries *could* take the `allow:` filter today (the bugs above are
uv-specific), and `pip` is documented to support `dependency-type: direct`
cleanly. We are deliberately not splitting the spec by ecosystem for this:
`charm-ubuntu` is migrating to uv soon and `charmlibs` is a likely uv
migration after that, so the pip-only window is short-lived. Cleaner to
revisit transitives once everything is on uv and the upstream classifier
issues are fixed.

See the [corresponding open question](#open-questions).

### Resolved scoring rules

1. **Routine lane stays monthly.** Status quo. Weekly + groups produces
   tighter feedback but more context-switches; the job of grouping is to
   right-size the *PR*, not the cadence. Revisit only if data shows the
   monthly grouped PR is so large that group-PR review itself is the
   bottleneck.
2. **`charmlibs` uses per-charmlib groups.** One group config per charmlib,
   not a single shared group across the monorepo. Mirrors the
   per-`pyproject.toml` reality and lets reviewer routing fan out along
   `CODEOWNERS` lines.
3. **Reviewer auto-routing is off, except in `charmlibs`.** Most repos are
   small enough that auto-assignment is noise. `charmlibs` follows
   `CODEOWNERS` so Dependabot PRs land on the right reviewer automatically.

### Per-repo deltas

All repos use the canonical shape above; only the deltas below differ.

| Repo | Ecosystem(s) | Delta from canonical |
|---|---|---|
| `operator` (root) | github-actions, uv | None at the root: self-check. `+ examples/httpbin-demo` as a second `uv` entry on the canonical routine-lane shape; drop the existing `k8s-5-observe` and `machine-tinyproxy` blocks (their `uv.lock` files are being removed from the repo, see below). |
| `charmhub-listing-review` | github-actions, uv | `+ zizmor` in `dev-tooling` (repo runs the zizmor GH-Actions linter). |
| `pytest-jubilant` | github-actions, uv | None of substance (actions-heavy; the `actions` group is the win). |
| `jubilant` | github-actions, uv | None of substance (`ops` is a dev dep, caught by `runtime`). |
| `charm-ubuntu` | github-actions, **pip** | `pip` not `uv`; `+ versioning-strategy: increase` (constraint-style requirements). Tiny surface; mostly a grouping win. |
| `api_demo_server` | github-actions, uv | None of substance once [api_demo_server#45](https://github.com/canonical/api_demo_server/pull/45) lands (that PR converts pip→uv, drops the `Dockerfile` for a rock, and switches flit→`uv_build`). |
| <a id="charmlibs"></a>`charmlibs` | github-actions, **pip** (monorepo) | **Biggest delta:** routine lane uses `directories: ["/", "/*", "/interfaces/*"]` instead of a lone `directory: "/"`, so the grouped lane actually reaches the nested lib dirs where the 10-PR backlog lives. Preserves and widens the existing glob. Drop the existing daily security-only `pip` entry; superseded by the repo-level toggle. |
| `concierge` | github-actions, **gomod** | None of substance; matches the template. |
| `pebble` | github-actions, **gomod** | Drop the existing daily security-only `gomod` entry; superseded by the repo-level toggle. Normalise at replication time (`.yaml` to `.yml`, `master` to `main` lookup path). |
| `hyrum` | github-actions, uv | Same shape as `jubilant` / `pytest-jubilant`; lowest volume in the set, fine as-is. |

**`operator/examples/*` blocks.** The current `dependabot.yml` carries three
`examples/*` entries (`httpbin-demo`, `k8s-5-observe`, `machine-tinyproxy`),
each with a hand-rolled `ignore:` list.

Two of those, the k8s tutorial (`k8s-5-observe`) and the machine tutorial
(`machine-tinyproxy`), are dropping their committed `uv.lock` and will
generate the lockfile in their test runs instead. With no `uv.lock` in the
tree, Dependabot has nothing to track in those directories: **drop their
`examples/*` entries entirely** as part of this rollout.

That leaves `httpbin-demo` as the only surviving `examples/*` block. Convert
it to the canonical routine-lane shape (groups, cooldown, no per-directory
`ignore:` list). The hand-rolled `ignore:` lists then go away in all three
places.

**Replication hygiene.** Normalise the filename to `.github/dependabot.yml`
(`charmlibs` and `pebble` currently use `.yaml`). Normalise indentation to
two spaces.

### Rollout

Smallest-blast-radius first, one PR per repo so a regression in one does not
block the others:

1. `charmhub-listing-review`
2. `pytest-jubilant`
3. `jubilant`
4. `charm-ubuntu`
5. `api_demo_server` (after [#45](https://github.com/canonical/api_demo_server/pull/45) lands; spec baseline assumes that PR's state)
6. `charmlibs`
7. `operator`
8. `concierge`
9. `pebble` (normalisation + drop the existing security lane)
10. `hyrum`

### Acceptance criteria

* Each in-scope repo has a `dependabot.yml` matching the canonical template,
  or with deltas documented in this spec.
* Each in-scope repo has the repo-level **"Dependabot security updates"**
  setting enabled (`features.dependabot_security_updates = true`, applied via
  canonical-repo-automation). This is the **only** CVE path under the new
  template; verify on the GitHub Settings then Code security page for every
  in-scope repo, not only in the HCL.
* Indentation is 2-space throughout. Filename is `.github/dependabot.yml`.
* Volume of Dependabot PRs over a 4-week window after rollout is materially
  lower than the 4-week pre-window baseline. (Concrete target deferred to
  step-1 data check after rollout.)

### Open questions

1. <a id="open-questions"></a>**Filter transitive deps once upstream is
   ready.** Goal: stop raising PRs for indirect deps in the routine lane;
   let them move when something direct pulls them, and rely on the
   repo-level security toggle for CVEs in between. Blocked on
   [dependabot-core#13202](https://github.com/dependabot/dependabot-core/issues/13202)
   (uv classifies every dep as `production`, so `dependency-type`-based
   filtering is incomplete). Revisit once that lands and `charm-ubuntu` /
   `charmlibs` have migrated to uv, then add `allow: [{ dependency-type:
   "direct" }]` to the canonical template.
