# OP??? — Dependabot config conventions for charm-tech repos

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
~58 Dependabot PRs/month the team currently fields across ten repos while
keeping CVE patches on a daily lane.

## Rationale

The Charm Tech repos emit a steady stream of Dependabot PRs. The cost is
**reviewer time and context-switching**, not the updates themselves:

* Even a clean patch-bump needs eyes on the diff and on CI.
* Five PRs in a morning, each ~5 min, is closer to an hour once the
  reviewer has re-loaded the repo's context.
* When something *does* need to land urgently — typically a CVE patch — being
  two minors behind is fine; being a major behind is not, and shipping a major
  as a security fix is the worst time to do it.

The strategy is not to *update less*. It is to (a) batch routine bumps along
sensible seams, (b) keep a fast, ungrouped lane for security advisories so the
batching does not delay CVE response, and (c) give majors a longer cooldown
window and their own PR so they cannot silently ride a patch bundle.

### Goals

* Reduce reviewer load per repo without losing coverage of patch + minor bumps.
* Keep CVE-patch latency at "next day" or better on every repo.
* Make majors visible: they get their own PR with a longer cooldown.
* Normalise the shape of `dependabot.yml` across repos so drift is one-glance
  visible. (Also, we should normalise the `.yml`/`.yaml`.)

### Non-goals

* Switching from Dependabot to Renovate.
* Auto-merge rules. Humans still merge; this spec is config-tuning only.
* Reviewing transitive dependencies, since we do not pick those.
* Standalone vulnerability scanning in CI (e.g. `uv audit`); see
  [§Future work](#future-work).

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

Per-repo volume (sorted high → low):

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

Three observations from this data drive the design:

1. **Grouping is essentially absent** outside `charmlibs`. Five small bumps
   become five PRs in every other repo. This is the single biggest noise
   source.
2. **A security-only daily lane exists only on `pebble` (gomod) and
   `charmlibs` (pip).** Everywhere else, a CVE patch waits for the next
   monthly window.
3. **The two repos that already run two lanes have the lowest PR volume in
   the set** (`pebble` 6/90d, and `charmlibs`'s low *merged* count masks an
   open-PR backlog that the existing wildcard group is failing to consolidate
   — see [§charmlibs delta](#charmlibs)).

`pebble`'s shape is the proof-of-concept: two lanes work, and they work
without inflating CVE latency.

### The canonical template

Designed against `canonical/operator` (highest PR volume in the set, the
flagship). Root block only; per-ecosystem deltas in
[§Per-repo deltas](#per-repo-deltas).

```yaml
version: 2

updates:
  # ===================================================================
  # GitHub Actions — routine lane (monthly, single grouped PR)
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
  # Python (uv) — routine lane (monthly, grouped along four seams)
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
      # Linters / type-checkers / formatters. Majors ride along — we do not
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
      # Docs toolchain. pygments is operator's single noisiest package
      # (7 bumps/90d) and is a docs/highlighting dep — grouping it here is
      # the biggest single noise win.
      docs:
        patterns:
          - "sphinx"
          - "sphinx-*"
          - "furo"
          - "myst-parser"
          - "pygments"
      # Everything else, minor + patch only. A runtime MAJOR falls through
      # to its own ungrouped PR so it never silently rides a patch bundle.
      runtime:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  # ===================================================================
  # Python (uv) — security-only lane (daily, ungrouped)
  #
  # open-pull-requests-limit: 0  ⇒  no version-update PRs from this entry;
  # security-update PRs (which ignore the limit) still flow, daily. NO
  # cooldown here on purpose — a security feed must not be delayed.
  # ===================================================================
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "daily"
    open-pull-requests-limit: 0
    labels:
      - "dependencies"
```

### Design rationale — two lanes

Per ecosystem, **two `updates:` entries**:

* **Routine lane** — `monthly`, grouped, `open-pull-requests-limit: 5`. Batches
  the steady patch/minor stream into a handful of grouped PRs per month.
* **Security-only lane** — `daily`, ungrouped, `open-pull-requests-limit: 0`.

`open-pull-requests-limit: 0` does **not** disable the entry — it suppresses
*version-update* PRs while *security-update* PRs (which ignore the limit) keep
flowing, checked daily. This is the pattern already proven on `pebble`
(gomod, six PRs in 90 days) and `charmlibs` (pip). The two-lane split is what
lets the routine lane go monthly without lengthening CVE-patch latency.

Two deliberate choices:

* **The security lane sets no `cooldown:`.** A cooldown on a security feed
  defeats its purpose; no repo in the baseline does this, and the canonical
  template must not paste a default cooldown there by reflex.
* **The security lane is ungrouped.** A CVE patch should be its own
  reviewable PR, not bundled.

**Multi-config note.** The routine and security lanes are two entries for the
*same* ecosystem + `directory: "/"`. Dependabot's multiple-configurations
support allows this (`charmlibs` already ships overlapping `pip` entries on
`/`). If a future Dependabot validation ever rejects the overlap, the
fallback is to keep the single routine entry and rely on Dependabot's
always-on security updates — but the explicit daily lane matches the
established precedent and makes the intent legible.

### Group patterns

Validated against `operator`'s actual 90-day bump stream. Four Python seams
plus one actions group:

| Group | Patterns | Why these |
|---|---|---|
| `dev-tooling` | `ruff`, `pyright`, `ty`, `codespell`, `coverage`, `pre-commit`, `types-*` | Linters/checkers we do not pin; safe to batch incl. majors. `ruff` is a top-5 bump in `operator`/`jubilant`/`pytest-jubilant`/`charmhub-listing-review`. |
| `test-deps` | `pytest`, `pytest-*`, `jubilant`, `ops-scenario` | `pytest` is the single noisiest package in `charmlibs` (7×) and recurs everywhere. |
| `docs` | `sphinx`, `sphinx-*`, `furo`, `myst-parser`, `pygments` | `pygments` is `operator`'s #1 bump (7×/90d) and `charmlibs`' #2 (4×) — a docs/highlighting dep, pure lockfile churn. Folding it (with sphinx) into one group is the biggest single noise win. |
| `runtime` | `*` (catch-all), `update-types: [minor, patch]` | Everything else. The update-type filter means a runtime **major** matches no group → its own ungrouped PR, so a major never silently rides a patch bundle. |
| `actions` | `*` | The github-actions surface is small and homogeneous; one group is plenty. |

**Group precedence.** Dependabot assigns a dependency to the *first* matching
group in file order. `dev-tooling` / `test-deps` / `docs` are listed before
`runtime`, so e.g. `ruff` lands in `dev-tooling` (all update-types), never in
`runtime`. The `runtime` catch-all is last and only claims minor + patch.

**Why not copy `charmlibs`' `test-deps: ["*"]`?** The baseline shows
`charmlibs` sitting on 10 open PRs (45 % of its window) *despite* that group —
because the grouped lane only targeted `directory: "/"` while the bumps were
in `/interfaces/*`. The lesson is the opposite of "one wildcard group":
sharper seams **plus** the right directory reach (see [§charmlibs delta](#charmlibs)).

### Cooldowns and majors

* **`cooldown.default-days: 7`** everywhere (unchanged from baseline) — gives
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
* Indentation is normalised to 2-space throughout.

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
3. **SHA-pin all third-party GitHub Actions.** Security-posture win pays back
   the review-cost increase; Dependabot still raises tag-tracking PRs against
   the pinned SHA so updates remain visible. First-party / verified-publisher
   actions stay tag-pinned.
4. **Reviewer auto-routing is off, except in `charmlibs`.** Most repos are
   small enough that auto-assignment is noise. `charmlibs` follows
   `CODEOWNERS` so Dependabot PRs land on the right reviewer automatically.
5. **Conventional Commits prefix is `chore: …`, no scope.** Match the repo
   convention of not using scopes; do not introduce `chore(deps): …` as a
   special case.

### Per-repo deltas

All repos use the canonical shape above; only the deltas below differ.

| Repo | Ecosystem(s) | Delta from canonical |
|---|---|---|
| `operator` (root) | github-actions, uv | None — self-check. `examples/*` blocks are deferred (see below). |
| `charmhub-listing-review` | github-actions, uv | `+ zizmor` in `dev-tooling` (repo runs the zizmor GH-Actions linter). |
| `pytest-jubilant` | github-actions, uv | None of substance (actions-heavy; the `actions` group is the win). |
| `jubilant` | github-actions, uv | None of substance (`ops` is a dev dep, caught by `runtime`). |
| `charm-ubuntu` | github-actions, **pip** | `pip` not `uv`; `+ versioning-strategy: increase` (constraint-style requirements). Tiny surface; main win is adding the security lane. |
| `api_demo_server` | github-actions, **pip**, **docker** | `pip` + `versioning-strategy: increase`; `+ docker` ecosystem (base image, monthly grouped); `+ flit` in `dev-tooling`. |
| <a id="charmlibs"></a>`charmlibs` | github-actions, **pip** (monorepo) | **Biggest delta:** routine + security lanes use `directories: ["/", "/*", "/interfaces/*"]` instead of a lone `directory: "/"`, so the grouped lane actually reaches the nested lib dirs where the 10-PR backlog lives. Preserves & widens the existing glob. |
| `concierge` | github-actions, **gomod** | Add the daily security-only `gomod` lane to match `pebble`. The github-actions / gomod shape otherwise matches the template. |
| `pebble` | github-actions, **gomod** | Already two-lane; the proof-of-concept. Only normalisation at replication time (`.yaml`→`.yml`, `master`→`main` lookup path). |
| `hyrum` | github-actions, uv | Same shape as `jubilant` / `pytest-jubilant`; lowest volume in the set, fine as-is. |

**`operator/examples/*` blocks** are out of scope of this spec. `uv.lock`
is being removed from the charmcraft profiles; the count has already dropped
5 → 4 → 3 on its own. When the remaining blocks are revisited, copy the
routine-lane shape into each surviving `examples/*` block and drop the
hand-rolled `ignore:` lists.

**Replication hygiene.** Normalise the filename to `.github/dependabot.yml`
(`charmlibs` and `pebble` currently use `.yaml`). `pebble`'s config lives on
the `master` branch, not `main`.

### Rollout

Smallest-blast-radius first, one PR per repo so a regression in one does not
block the others:

1. `charmhub-listing-review`
2. `pytest-jubilant`
3. `jubilant`
4. `charm-ubuntu`
5. `api_demo_server`
6. `charmlibs`
7. `operator` root
8. `concierge` (independent — adds the daily security `gomod` lane)
9. `pebble` (normalisation only)
10. `hyrum` (optional; lowest priority)

### Acceptance criteria

* Each in-scope repo has a `dependabot.yml` matching the canonical template,
  or with deltas documented in this spec.
* Each in-scope repo has the daily security-only lane for every ecosystem it
  configures.
* Indentation is 2-space throughout. Filename is `.github/dependabot.yml`.
* Volume of Dependabot PRs over a 4-week window after rollout is materially
  lower than the 4-week pre-window baseline. (Concrete target deferred to
  step-1 data check after rollout.)

## Future work

* **`uv audit` as a CI gate.** Once `uv audit`
  ([blog post](https://astral.sh/blog/uv-audit), Astral, 2026) leaves preview,
  adding it as a CI step across the uv-managed repos is a natural complement
  to the security-only Dependabot lane. The Dependabot lane alerts when a
  published advisory matches a dep already locked; `uv audit` blocks a PR
  that *introduces* a newly-vulnerable dep. It also adds deprecation
  detection (signal for the dep-audit work) and an opt-in malware check
  (`UV_MALWARE_CHECK=1`) that Dependabot provides no equivalent for. Requires
  a `uv.lock`; pip-managed repos would continue with `pip-audit` or wait
  for a migration path.
* **Direct-dependency audit.** Per-repo walk of direct deps and GitHub
  Actions asking three questions — "do we use enough of this to justify it?",
  "is there a tighter-focused alternative?", "is the action still the right
  action?" — with verdicts feeding follow-up removal / replacement work.
  Tracked separately from this spec.
* **Conventions note.** Once the template stabilises, fold a short
  "charm-tech repo conventions" reference into this repo's README so new
  repos start from this shape.

## Open questions

These are not blockers for the rollout above but should be settled with repo
owners during or shortly after adoption:

1. **Weekly vs monthly routine cadence.** Defaulted to monthly. `operator`'s
   50 % closed-without-merge ratio hints that monthly batching is letting
   PRs age out before merge — a point *for* weekly. Decide from the
   merge-cadence data once a few months of the new template are in.
2. **Auto-merge-on-green.** Three repos look like they already auto-merge:
   `charm-ubuntu` (17 min median TTM), `charmhub-listing-review` (26 min),
   `jubilant` (1.3 h). Confirm whether this is a convention this spec should
   leave alone or formalise.
3. **SHA-pinning posture for third-party actions.** Two repos currently
   tag-pin third-party actions: `DavidAnson/markdownlint-cli2-action`
   (`charmlibs`) and `aquasecurity/trivy-action` (`pebble`). Scoring rule #3
   says SHA-pin; track those two as the first migration targets.
4. **Canonical Sec org-standard.** Verify there is no org-wide
   `dependabot.yml` standard from Canonical Sec that this spec needs to
   align with. If one emerges later, fold a Sec review in then.
