# OPxxx — ops-tools: YAML generation from Python dataclasses

| Field | Value |
| --- | --- |
| Index | OPxxx |
| Title | ops-tools: YAML generation from Python dataclasses |
| Type | Implementation |
| Author | Tony Meyer |
| Status | Draft |
| Created | 2026-06-20 |
| Reviewer | Pending Review |

## Abstract

`ops-tools` is a small command-line package, distributed independently on PyPI, that generates `charmcraft.yaml` configuration and action stanzas from Python dataclasses. Charm authors annotate their config and action classes in Python, then run `ops-tools generate-metadata` / `ops-tools generate-actions` to produce the corresponding YAML — replacing hand-maintained files with a single source of truth in code.

This spec captures the architectural decisions reached during review of [canonical/operator#1975](https://github.com/canonical/operator/pull/1975) ("feat: support for generating charmcraft YAML from Python classes"), which is the productisation of `ops-tools`. The PR accumulated 46 review threads and contained too many changes to effectively review. This document resolves questions from the review, so the four-PR implementation series (PR1–PR4) can land without re-opening them.

## Rationale

**Separate PyPI package.** `ops-tools` ships independently from `ops`, following the precedent set by `ops-scenario` (OP028) and `ops-tracing`. Like validators (see OP070, OP074 for packaging context), tools that are useful alongside `ops` but not part of the framework itself belong in their own packages: it keeps `ops`'s dependency surface minimal and lets `ops-tools` version independently (although, for convenience, we will likely release simultaneously). The import name is `ops_tools` (not `ops.tools` — Q9 below explains why a namespace package is not possible).

**Why split PR1975?** At 2465 lines across 27 files, #1975 is not reviewable in its current form. Its 46 review threads contain five distinct technical debates (subcommand shape, ruamel.yaml vs PyYAML, 12-factor compatibility, `_attrdocs.py` AST fragility, packaging convention) that are entangled across comments. Splitting into smaller PRs separates the debates, allowing each to land on its own merits. The spec exists to short-circuit the "we keep discussing this" failure mode.

**What shipping unblocks.** Once `ops-tools` is on PyPI, charm authors can `uvx ops-tools generate-metadata` in their CI, eliminating manual YAML maintenance and the round-trip errors it causes. The tooling also provides a clear upgrade path away from hand-authored `charmcraft.yaml`: generate once, compare with `git diff`, then maintain in Python thereafter.

## Goals

- Ship `ops-tools` 1.0 to PyPI with `generate-metadata` and `generate-actions` subcommands (PR1 + PR2 + PR4).
- Provide a clean upgrade path for charm authors currently writing config and action YAML by hand.
- Settle the nine architectural questions from #1975 so implementation PRs cite this spec rather than re-discussing them.

## Non-goals

- Surgical in-place editing of `charmcraft.yaml` (PR3 dropped — see Q3).
- Scenario integration (PR5 deferred).
- Establishing a Charm Tech wide `ops-*` namespace package convention (Q9 — deferred until three data points exist).
- Resolving the broader 12-factor charm direction for the ecosystem (Q4 deferred as wrongly-formed).

## Specification — decisions

### Q1: Subcommand shape

**Decision:** one `ops-tools` entry point with subcommands (`ops-tools generate-metadata`, `ops-tools generate-actions`).

A single entry point is discoverable via `ops-tools --help`, composes cleanly with `uvx` (`uvx ops-tools generate-metadata`), and matches the "one tool, multiple modes" framing. Separate per-operation console scripts would proliferate the global namespace; a `--mode` flag on one script would be less ergonomic than named subcommands. The subcommand structure is extensible: a future `ops-tools update-yaml` (if PR3 unblocks) fits naturally as a third subcommand. ([Thread 8](https://github.com/canonical/operator/pull/1975#discussion_r2302407622))

### Q2: Pydantic as a dependency

**Decision:** pydantic is an optional extra — `pip install ops-tools[pydantic]` — not a required dependency.

The default install is pydantic-free; docs lead with dataclasses. If a charm already uses pydantic, `ops-tools[pydantic]` enables cleaner field introspection via `Field(description=...)`. Implementation uses a lazy import (`try: import pydantic except ImportError: HAS_PYDANTIC = False`); both code paths exist in the codebase, the extra only gates installation. Output must be byte-identical between paths for the same input — this is a testable invariant enforced in PR1's test suite. ([Thread 19](https://github.com/canonical/operator/pull/1975#discussion_r2308940579))

### Q3: YAML library

**Decision:** PyYAML throughout; ruamel.yaml not adopted. PR3 (`update-charmcraft-yaml` surgical-update script) is **dropped** from this series.

Consistency across Charm Tech repos outweighs ruamel's comment-preservation advantage. The whole rationale for PR3 was comment-preservation on round-trip; PyYAML cannot do this. The gating workflow becomes: generate fresh YAML and compare with `git diff` — a simpler and more transparent alternative. PR3 unblocks only if Charm Tech evaluates moving off PyYAML project-wide; that cross-project decision is tracked separately. ([Thread 27](https://github.com/canonical/operator/pull/1975#discussion_r2324187431), [Thread 29](https://github.com/canonical/operator/pull/1975#discussion_r2268772907))

### Q5: Flag names

**Decision:** shorter forms — `--path`, `--config`, `--action`.

The Q1 subcommand namespacing already disambiguates the verbs: `generate-metadata --config` is unambiguous without needing `--config-file` or `--charm-path`. Future needs for a second `--path`-style argument are deferred until they appear concretely rather than guarded against pre-emptively. ([Thread 30](https://github.com/canonical/operator/pull/1975#discussion_r2286655050), [Thread 31](https://github.com/canonical/operator/pull/1975#discussion_r2286658715))

### Q7: Type-annotation requirement

**Decision:** support both `a | b` (PEP 604) and `Union[a, b]` / `Optional[a]`.

`typing.get_type_hints()` normalises both forms to the same internal representation at near-zero cost. Docs recommend `a | b` as the modern form; both are accepted at runtime. Ops 3.x's minimum is Python 3.10+, so `a | b` is never a syntax error. Mandating only the modern form would silently break valid charm code using `Union`; accepting both is strictly more compatible. ([Thread 6](https://github.com/canonical/operator/pull/1975#discussion_r2302399071))

### Q8: `_attrdocs.py` fragility

**Decision:** hybrid — explicit metadata takes precedence; AST extraction is the documented fallback.

If `field.metadata.get("description")` (stdlib dataclasses) or `Field(description=...)` (pydantic) is present, use it. Otherwise fall back to AST extraction. Explicit tests are added for the known clobber scenarios: pydantic `model_fields`, `dataclasses.fields()`, mro-order (the parent-overwrites-child bug from Thread 12), and conditional imports. The explicit form is recommended in docs for new code; the AST fallback is supported-for-now. The mro-order fix lands in PR1 alongside the new `_attrdocs.py` test suite. ([Thread 12](https://github.com/canonical/operator/pull/1975#discussion_r2268799642))

### Q9: Packaging convention

**Decision:** document `import ops_tools` (not `ops.tools`) in `ops-tools`'s own README; no charm-tech-wide `ops-*` namespace package convention yet.

`ops` cannot be a namespace package, so `ops.tools` is not possible. `ops-scenario` uses `import scenario` and `ops-tracing` uses `import ops_tracing` — two existing packages are already inconsistent, so ratifying a convention now would either bless the inconsistency or force a rename. Defer the convention until a third `ops-*` package provides a third data point. ([Thread 4](https://github.com/canonical/operator/pull/1975#discussion_r2271965470))

## Deferred decisions

**Q4 — 12-factor charm compatibility.** Dimaqq raised this across Threads 29 and 35. The question as posed ("is this for 12-factor charms?") is wrongly-formed: it conflates what layout the *generator output* assumes with what layout the *target repo* uses. Re-open with the cleaner two-part question. Does not block PR1–PR4, which generate YAML sections without touching the top-level file layout.

**Q6 — Script name for the surgical-update command.** Q3's PyYAML decision dropped PR3 from this series, so the command Q6 would name does not exist for now. Re-opens when PR3 unblocks. Likely resolution at that time: a third `ops-tools` subcommand per Q1's structure, not a separate console script.

## Open thread dispositions

These five threads were not clearly resolved in the PR, and need resolution before proceeding.

- **Thread 1** (`charm.py:35`) — **PR1.** Trivial comment-wording nit ("test expected to fail if uncommented"). Tucked into the test-charm lift in PR1. Recorded here so PR2 doesn't undo it.

- **Thread 3** (`test_config.py:127`) — **Split.** Defaults-at-call-site is pre-existing `load_config` API; not in this series' scope. Required/non-required negative tests carried to PR5 (Scenario integration, deferred per PLAN).

- **Thread 7** (`README.md:113`) — **Wontfix.** README moves to a proper docs page in PR4 (per Thread 4). Line-numbered requests against the old README are stale by the time they would land; write any parallel doctest against the new docs page post-PR4.

- **Thread 25** (`_generate_yaml.py:160`) — **Wontfix for this series.** Reusing `ops.charm._juju_fields` would either expose `ops` internals or scope-creep a public-helper PR into this series. Build-time vs runtime traversal shapes overlap but aren't identical. If a future `ops` PR exposes a public traversal helper, `ops-tools` can refactor against it — flagged as a `[needs-design]` follow-up against `ops`.

- **Thread 45** (`test_generate_yaml_config.py:54`) — **Split.** Runtime optional-`Secret` semantics are pre-existing `load_config` behaviour, out of scope. Generator emission for `Optional[Secret]` gets a PR1 verbatim-output stability fixture (folds into Thread 46's fixture set). The spec documentation gap for `Optional[Secret]` in ops docs is a future ops-docs follow-up, not addressed here.

## Carry-forward per implementation PR

### PR1 — config YAML generation

Applies decisions **Q7** (type-annotation handling), **Q8** (`_attrdocs.py` hybrid approach and mro-order fix).

Threads landing in PR1: all config-side HIGH threads (9, 10, 11, 16, 17, 18, 21, 23, 24, 26, 46), MED threads (13, 15, 20, 22), and LOW threads (1, 3, 7, 45 per dispositions above). Scope: `_generate_yaml.py` (config half), `_attrdocs.py` with explicit unit tests, doctest-shaped module examples, verbatim YAML stability fixture, in-thread simplifications listed in PLAN.

### PR2 — action YAML generation

Applies decisions **Q7** (type annotations; `_attrdocs.py` shared with PR1).

Threads landing in PR2: Thread 14 (per-attribute docstring spacing on `ActionDict`), Threads 37–44 (Copilot "statement has no effect" / `N801` naming family). Scope: `_generate_yaml.py` (action half), `test_generate_yaml_action.py` cleanup.

### PR3 — dropped

Dropped as a consequence of the Q3 (YAML library) decision. The surgical `update-charmcraft-yaml` script required comment-preserving YAML round-tripping; PyYAML cannot provide that. Threads 27, 29, 30, 31, 35 are resolved in PR0 but have no implementation PR to land in for this series. PR3 re-opens if charm-tech moves off PyYAML.

### PR4 — `ops-tools` packaging

Applies decisions **Q1** (subcommand shape / entry-point wiring), **Q2** (pydantic extra in `pyproject.toml`), **Q5** (flag names applied in CLI layer), **Q9** (packaging rationale in README/docs).

No thread is dominantly a PR4 item; Threads 4 and 8 land here as secondary carry-forward (README → docs page, `pyproject.toml` name, `uvx` entry-point wiring). Scope: `tools/pyproject.toml`, docs page replacing README, release pipeline integration.

### PR5 — Scenario integration (deferred, not in this series)

`testing/src/scenario/state.py` changes from #1975: "left for future work, rather than baking anything in to Scenario at this time." Thread 2 (Thread 3's secondary) maps to opening a tracking issue on `canonical/operator` referencing #1975's Scenario thread. Reopens in a future cycle.

## References

- Upstream PR: <https://github.com/canonical/operator/pull/1975>
- Reviewer threads cited above (Q1–Q9): all in
  <https://github.com/canonical/operator/pull/1975>
- OP070 (charm libs as namespace packages): `specs/OP070-charm-libs-as-namespace-packages.md`
- OP074 (charmlibs interfaces): `specs/OP074-charmlibs-interfaces.md`
