| Index | OPxxx (number not yet claimed) |  |  |
| :---- | :---- | :---- | :---- |
| Title | Saddle: Multi-Charm Unit Testing in ops.testing |  |  |
| **[Type](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?usp=sharing)** | **Author(s)** | **[Status](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?tab=t.0)** | **Created** |
| Implementation | [Tony Meyer](mailto:tony.meyer@canonical.com) | Draft | 26 May 2026 |
|  | **Reviewer(s)** | **Status** | **Date** |
|  | Person | Pending Review | Date |

# Abstract

This spec defines **Saddle**: a multi-charm unit (state-transition) test surface folded into `ops.testing`. It provides `deploy`, `integrate`, `add-unit`, `remove-unit`, and `update-config` as test operations, with the corresponding Juju events triggered automatically as the model converges. Each charm runs in its own isolated subprocess (its own venv), so charms with mutually incompatible dependency sets can be tested together in a single test. Saddle targets `ops.testing` in `canonical/operator`; it is not a companion package. It draws the abstraction from [Catan](https://github.com/PietroPasotti/catan) (Apps + convergence) but is not a direct port.

# Rationale

## The gap in current tooling

`ops.testing` (Scenario) runs one charm at a time: the developer writes an event and a `State`, calls `Context.run`, and asserts on the output. This is efficient for single-charm logic but leaves four pain points unaddressed:

- **Integration tests are too slow for the inner loop.** A real Juju controller bootstrap and deploy round-trip takes minutes; unit tests must be measured in seconds.
- **Scenario is unlike the `juju` commands charmers think in.** Charmers reason about `juju deploy`, `juju integrate`, `juju add-unit`. Translating that mental model into hand-crafted event sequences and `State`s is friction the tool should absorb.
- **Charm libraries don't yet ship mocks.** Cross-charm relation data is hand-crafted per test. Running the other charm's own code against the relation removes that hand-crafting: the other charm's actual reaction becomes the fixture. This may change with the acceptance of OP077 — Charm library testing.
- **Bundle and topology assertions are unreachable from unit tests.** Asserting "if I deploy A and B and integrate them, A's leader ends up with config X" requires real Juju or fragile mocks today.

## Validated abstraction

The shape charmers ask Charm Tech for is "a multi-charm state-transition test tool that feels like Juju". This is Catan's abstraction (Apps, `integrate`, convergence/settle), validated by demand rather than speculative.

## Why ops.testing rather than a companion package

Catan today pins `ops-scenario~=6.0`, a superseded API that has been merged into `ops.testing` as Scenario 7. Porting off that API is **net-new work regardless of the destination**; there is no path that productises the companion-package form without a full re-targeting. Since we have to re-target anyway, we target `ops.testing` directly.

# Specification

## Location and scope

The new surface lives in `ops.testing` (`canonical/operator`), the same module that provides `Context`, `State`, and `Manager`. The single-charm primitives are **unchanged and remain the substrate**. The new surface adds a model-level layer above `Context` that owns a set of `App`s, an integration graph, and a convergence loop. Single-charm Scenario tests continue to work exactly as today and do not require the new surface.

## Operation surface

The test API uses Juju-shaped operations — `deploy`, `integrate`, `add-unit`, `remove-unit`, `update-config`, `run_action` — that describe **intents, not events**. The model generates the correct Juju-faithful event sequence and delivers it to the affected units.

```python
from ops import testing

model = testing.Model()

db = model.deploy(
    charm="./charms/postgresql",
    app="postgresql",
    config={"profile": "testing"},
    num_units=1,
)
web = model.deploy(
    charm="./charms/myapp",
    app="myapp",
    num_units=2,
)

model.integrate(db["db"], web["pg"])
model.add_unit(web)
model.update_config(web, {"log_level": "debug"})
model.remove_unit(web, unit=1)
model.run_action(db.leader, "create-backup", params={})
```

`Model.deploy(...)` returns an `App` handle. An `App` owns its charm reference, the metadata resolved from the charm on disk, the environment it runs in (see Isolation model below), and its per-unit `State`s. Exact type names are illustrative and will be settled in code review.

## Automatic event triggering and convergence

Each operation enqueues the appropriate events (`relation-created`, `relation-joined`, `relation-changed`, `config-changed`, `leader-elected`, etc.) on the affected units. A **convergence loop** drains the queue: it picks an event, dispatches it through that unit's `Context.run(...)`, observes any new relation-data writes, status changes, or secret operations, and enqueues the downstream events those produce on peers and related units. Convergence terminates when the queue is empty and no unit's last run produced new observable change.

```python
model.settle()   # explicit convergence point
assert web.leader.state.unit_status == ActiveStatus("ready")
assert db.leader.state.get_relation("db").local_app_data["database"] == "myapp"
```

`settle()` is also called implicitly before reading any unit's `State` if there are pending events, so most tests are a sequence of operations followed by assertions on `app.leader.state` or `app.units[i].state`. The `State` exposed on each unit is the same `ops.testing.State` dataclass that single-charm Scenario tests use today; all existing assertions are available unchanged.

**Determinism requirement (resolved 2026-06-03).** Given the same starting `Model` and the same input event sequence, `settle()` MUST produce the same final `State` per unit and the same sequence of intermediate events, byte-for-byte, across runs and across machines. **No wall-clock dependence, no PID-derived ordering, no Python-dict-iteration-order leakage** is permitted in the policy. The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is picked in step 5 against this requirement, when there is working code to validate it. See Further Information.

## Isolation model: subprocess + per-charm venv

Each `App` runs in its own process with its own interpreter (an existing venv's `bin/python`, or one the harness provisioned — see Environment provisioning below). For each event dispatch the harness serialises `(meta, config, actions, event, State)` as JSON, sends it to the charm's worker process, the worker runs `testing.Context(...).run(...)`, and serialises the resulting `State` back. Two `App`s in the same `Model` may use mutually incompatible dependency sets — `cryptography==41` vs `==3`, different `pydantic` majors, conflicting charm-lib versions — demonstrated end-to-end by the isolation spike: two charms with intentionally conflicting `confdep` versions, each in its own venv, both producing correct output in the same test session via both a lightweight `sys.path`-injected dep dir and a full real venv per charm.

**Required invariant:** each per-charm venv contains an `ops` / `ops-scenario` build whose JSON `State` wire format is compatible with the parent harness's. Only the charm's own runtime deps differ between venvs — realistic, since all charms build on `ops`.

The isolation worker is persistent: one long-lived process per `App`, spawned lazily on first dispatch and torn down at `Model` teardown or after an idle timeout. A framed JSON protocol over stdin/stdout carries requests and responses. Spawn-per-event remains available as an explicit debug mode (easier to attach a debugger; no shared interpreter state between events). Worker crashes propagate as a typed `IsolationError` and fail the test cleanly; the harness never silently re-spawns mid-test.

**Acceptance criterion (fixed 2026-06-03):**

- **Workload:** the canonical perf yardstick is a **4-charm bundle with 20 events per `settle()`**. Lives in the test suite from step 3 onward and is re-run by every later step to catch regressions.
- **Bar:** **persistent-worker mode within 2× the in-process Scenario baseline** on that workload. 2× is the threshold where "slow but acceptable for a CI unit-test suite" tips into "too slow, charmers will avoid it"; subprocess + JSON serialisation has a real floor below that.
- **Benchmark shape:** the step 3 PR ships a benchmark suite measuring (a) in-process Scenario baseline, (b) spawn-per-event isolated, and (c) persistent-worker isolated, all on the same 4-charm/20-event workload.
- **If (c) misses the bar:** the PR either records a clear "this is slower than the target; here's why; here's what could close the gap" trade-off note, or the persistent-worker design is reconsidered before step 3 is signed off.

### Subinterpreters are explicitly ruled out

PEP 734 subinterpreters are **not** the mechanism, even granting a 3.14+ floor:

- **Binary-dependency conflicts remain unsolved.** Many C extensions (`cryptography`, `pydantic-core`, `cffi`-based packages) are not multi-interpreter-safe; two different versions of the same extension cannot coexist in one process at any Python version. These are the exact libraries motivating the work.
- **State boundary still costs a serialisation roundtrip** — the same JSON encode/decode as a subprocess, taken without the isolation benefit.
- **Maintenance cost is high** on a bleeding-edge API for no payoff over the subprocess design.

Revisit only if the C-extension multi-interpreter story matures enough to load conflicting binary versions in one process — not merely because the Python version floor moves.

## Environment provisioning

How a charmer declares an `App`'s environment:

| Form | API | When to use |
| --- | --- | --- |
| Auto-provision from declared deps | `Model.deploy(..., build_env=True)` | Canonical recommended UX |
| Point at an existing venv | `Model.deploy(..., python="/path/to/venv/bin/python")` | CI where the venv is already managed |
| Inherit the test process | explicit opt-in flag | Only when deps are known not to conflict |

For auto-provisioning the harness detects the charm's build plugin (from `charmcraft.yaml` first; file-based heuristic second — `uv.lock` → `uv`; `poetry.lock` → `poetry`; `pyproject.toml` → `python`; else → `charm`) and extracts the dependency list:

| Plugin | Extraction method |
| --- | --- |
| `charm` | reads `charm-requirements` files + `charm-python-packages` + AST-harvested `PYDEPS` from `lib/**/*.py` |
| `python` | reads `python-requirements` / `python-packages` + PYDEPS (included even though charmcraft's python plugin does not auto-install them — the test harness needs the lib importable) |
| `uv` | shells to `uv export --frozen --no-emit-project --no-hashes --format requirements-txt` with forwarded `--extra` / `--group` flags |
| `poetry` | shells to `poetry export --without-hashes --format requirements.txt` with forwarded `--with` flags |

All forms normalise to a flat pip specifier list, then install via `uv pip install` into the per-charm venv. The venv is cached on disk, keyed by SHA-256 of (plugin, extracted requirements, lockfile/pyproject content, interpreter version, harness `ops` version): cold build ~3s for a test charm; warm cache hit <0.05s (measured). The detection-and-extraction path was validated against two real Canonical charms (loki-k8s-operator via the uv plugin; postgresql-k8s-operator via the poetry plugin); the harness emits a clear, typed error when an extracted requirement cannot be resolved against an available index, when a lockfile is stale relative to the pyproject, or when a required external tool (`uv` / `poetry`) is missing.

**Tool dependency:** `uv` on PATH for all install steps; `poetry` + `poetry-plugin-export` for the poetry-plugin path. The harness emits a clear error when a required tool is absent.

**Future:** a charmcraft-managed flow for charms already packed locally.

## State (de)serialisation

A typed schema-aware encoder/decoder pair — not `json.dumps(dataclasses.asdict(state))` — covers all `ops.testing.State` leaf types verified against the spike's findings:

| Type | Encoding |
| --- | --- |
| `frozenset` (on `relations`, `containers`, `secrets`, etc.) | list on encode; re-frozen on decode (dataclass `__post_init__`s re-freeze) |
| `datetime` / `timedelta` | ISO-8601 string / fractional seconds |
| `pathlib.Path` / `PurePosixPath` | string with type tag |
| Pebble enums (`ServiceStatus`, `NoticeType`, `SecretRotate`, …) | enum name |
| `pebble.Layer` (`Container.layers`) | `to_dict()` / `Layer(dict)` round-trip (not a dataclass; `asdict` won't descend) |
| Int-keyed dicts (`Secret.remote_grants: Mapping[int, set[str]]`) | keys stringified on encode; restored to `int`, inner `set` restored on decode |

**StoredState fidelity (resolved 2026-06-03).** `StoredState.content` and `Container._base_plan` are `Mapping[str, Any]` of marshallable types — a superset of JSON: `bytes`, `tuple`-vs-`list` distinction, and arbitrary `set`s. The spec commits to:

1. **A typed escape hatch, applied always** — tag-and-encode `bytes` as base64 and `tuple` as a `["__tuple__", ...]` envelope so they round-trip losslessly. **No flag.** An opt-in would create a "passed locally because today's stored-state had no `bytes`, failed in CI when it did" failure mode; the cost (a few extra bytes per typed value) doesn't justify it.
2. **Loud error on unrecognised types** — the encoder raises `TypeError` with the type name and the path through `State`. The decoder mirrors: unknown `__type__` tags raise `TypeError`. Never silent lossy coercion.

A small follow-up survey of in-tree charm `StoredState` usage is left as a separate work item, to confirm no charm relies on round-tripping more exotic marshallable types than `bytes`/`tuple`/`set`. The survey does not gate the implementation; it informs whether the encoder's type set needs to be extended.

**JSON `State` schema stability (resolved 2026-06-03).** The JSON `State` representation is **part of `ops.testing`'s public API** — a per-charm venv may have a different `ops` build from the parent, and both sides must agree on the encoded form.

1. **Explicit `state_schema_version` integer field** is embedded in every encoded `State` payload. Cheaper and more legible than overloading `ops`'s SemVer: we don't have to ship an `ops` major just because we added one field to `State` serialisation.
2. **Per-version interpretation is locked at the source-code level** — a dispatch table keyed by version. Adding a new version is ordinary work; changing the *meaning* of an existing version is not.
3. **Decoder rejects unsupported versions with a clear typed error.** A v1 producer and a v1+v2 consumer work fine. A version the decoder doesn't recognise surfaces as an explicit error, not silent corruption.
4. **`ops.testing` API-stability documentation commits to (2).** "We may add new versions; we don't change the meaning of an existing version."

Implementation honours this from step 2 onward (the encoder writes `state_schema_version`; the decoder dispatches on it).

## Metadata resolution

The harness reads `metadata.yaml` / `charmcraft.yaml` from the charm-source path without importing the charm in the test process. Work required for productisation:

- Resolve unified-vs-legacy metadata variants and the merged `charmcraft.yaml` + `metadata.yaml` form charms commonly produce
- Resolve charm libraries the charm declares but that live elsewhere on disk
- An isolated equivalent of Catan's `App.from_git` (clone, detect build system, provision venv, run)
- Inline charm classes (`from_type` charms defined in the test): kept as in-process, same-environment only; isolation requires charms on disk (`from_isolated_path`). See Further Information.

**Step 6 acceptance set for metadata-resolution coverage (locked 2026-06-03).** At least one passing test for each of these charm shapes:

1. Unified `charmcraft.yaml` only (no `metadata.yaml`) — the current default-modern shape.
2. Legacy split: `metadata.yaml` + `actions.yaml` + `config.yaml` — older charms still in production.
3. Mixed / transitional: `charmcraft.yaml` + `metadata.yaml` (the form charmcraft merges) — charms mid-migration.
4. Multi-bases (`bases:` / `platforms:` variants per supported platform).
5. Charm with libs outside `src/` (e.g. installed via `pip` from PyPI for testing) — exercises the "where did this lib come from" resolution.
6. Inline `from_type` (no metadata file; class declares everything) — documented as `inline: ok` per the docstring convention in Further Information.

## Migration from Catan / ops-scenario~=6.0

The existing `PietroPasotti/catan` package pins `ops-scenario~=6.0` (superseded by `ops.testing`). There is **no compatibility shim**: tests written against Catan must be rewritten against the Saddle surface. The `ops-scenario~=6.0` form is throwaway regardless of whether Saddle is adopted — porting off it is net-new work either way.

What Saddle carries forward from Catan:

- The model: Apps + integration graph + convergence/settle — the abstraction demand validates
- The Juju-like operation vocabulary: `deploy` / `integrate` / `add-unit` / …
- The isolation and provisioning spikes as seed implementations for steps 1 and 6

What is discarded:

- The `ops-scenario~=6.0` companion-package API
- The Catan package as a separate distribution artifact (PyPI release, separate repo, separate release cadence)

## Incremental delivery plan

Sequenced so each merge is **independently useful** and the area can pause cleanly after any step. This is the handle on the priority reservation: agentic coding lowers per-step build cost, and the sequencing means a pause never strands a half-built feature.

| Step | Deliverable | Value without later steps |
| --- | --- | --- |
| 1 | Lift isolation into `ops.testing`: `IsolatedEnv`, persistent worker, `from_isolated_path` | Immediately useful: run one charm in an isolated venv from a Scenario test; no `Model`, no convergence |
| 2 | Typed `State` (de)serialiser with full leaf-type coverage and the StoredState escape hatch | Snapshot-style tests and debugging; required by every later step |
| 3 | Persistent-worker mode replacing spawn-per-event (benchmarked in the same PR). **Acceptance:** within 2× of in-process Scenario on the 4-charm/20-event workload — see *Isolation model* | Performance baseline; unblocks realistic convergence-run testing |
| 4 | `Model` + `App` + non-relating operations: `deploy`, `add-unit`, `remove-unit`, `update-config`, `run_action`, single-app convergence | Drive a single charm through Juju-shaped operations without writing event sequences by hand |
| 5 | `integrate` + cross-app event propagation + settle policy locked. **Acceptance:** see *Settle policy considerations* (Further Information) — at least one deterministic policy passes a 100×-soak; user-override hook exposed | Unlocks the multi-charm pain points; steps 1–4 stand alone if priorities pull us off here |
| 6 | `build_env=True` environment provisioning (all four plugins, caching, lockfile handling) + full metadata-resolution coverage. **Acceptance:** the six-shape metadata test set — see *Metadata resolution* | Productisation tail; not on the critical path for any earlier step |

# Further Information

## Settle policy considerations (resolved 2026-06-03)

The determinism requirement is locked in *Automatic event triggering and convergence*: byte-for-byte reproducible across runs and machines; no wall-clock, PID, or dict-iteration-order leakage.

The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is picked in step 5 against that requirement, with the following acceptance:

- At least one deterministic policy ships and passes a **"run 100×, all final `State`s identical"** soak test.
- The API exposes a **user-override hook** for cases the default policy doesn't fit. The hook may ship empty initially.

Picked here rather than locked up front because the choice benefits from being able to play with the convergence loop in working code.

## Inline charm classes vs on-disk charms (resolved 2026-06-03)

`from_type` charms defined inline in a test cannot be trivially transferred to a fresh subprocess (the class object is not serialisable). Isolation realistically requires charms on disk. The API keeps both paths: inline classes run in-process with no isolation (like Scenario today); on-disk charms run isolated by default.

The matrix of "works inline but not isolated" surprises is closed by a **documentation convention** rather than a runtime check. Every operation introduced from step 4 onward — anything beyond `IsolatedContext.run()` (`deploy`, `add-unit`, `integrate`, `update-config`, `run_action`, …) — declares in its docstring two explicit fields:

- `inline: ok | error | n/a`
- `isolated: ok | error | n/a`

Where `ok` means works as documented, `error` means raises a clear typed error explaining why it's not supported in this mode, and `n/a` means doesn't make sense in this mode.

Enforced by API-doc review at PR time. Trivial to grep for. The matrix becomes readable in the docs rather than discoverable only by trial. No separate validation layer.

## Real-world charm coverage

The isolation and provisioning spikes were demonstrated end-to-end on synthetic test charms with intentionally conflicting deps, and the provisioning detection/extraction path was validated against two real Canonical charms (loki-k8s-operator, postgresql-k8s-operator) via a read-only `describe` CLI. Full end-to-end "provision venv, run the charm's code" against a real production charm remains unproven at spike scope. Likely first regression class: Python-version mismatch (charms targeting `requires-python = "~=3.12"` in a 3.11 harness).

## Out of scope

- Changes to Scenario's existing single-charm API or behaviour
- charmcraft `reactive` plugin support (not in current use; defer)

## Prior art and references

- [Catan](https://github.com/PietroPasotti/catan) — the abstraction this spec draws from; spike branch `explore/per-charm-dependency-isolation` at commit `1f4c357`
- [operator#1929](https://github.com/canonical/operator/issues/1929) — origin of the Saddle name and the `ops.testing`-integrated direction

# Spec History and Changelog

| Author(s) | Status | Date | Comment |
| :---- | :---- | :---- | :---- |
| [Tony Meyer](mailto:tony.meyer@canonical.com) | Draft | 26 May 2026 | Initial draft; seeded from the isolation spike, the environment-provisioning spike, and the decision to target `ops.testing` rather than a companion package |
| [Tony Meyer](mailto:tony.meyer@canonical.com) | Draft | 3 June 2026 | Resolved six open questions: StoredState fidelity (always-on typed escape hatch), JSON `State` schema stability (explicit `state_schema_version` field + dispatch table), settle-policy determinism requirement (byte-for-byte reproducible), inline-vs-on-disk docstring convention, perf 2× acceptance bar (4-charm/20-event workload), metadata-resolution six-shape step-6 acceptance set. Small follow-up survey of in-tree charm `StoredState` usage is queued separately. |
| Person | Pending Review | Date |  |
