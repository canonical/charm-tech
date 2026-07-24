| Index | OP089 |  |  |
| :---- | :---- | :---- | :---- |
| Title | Multiple-charm state transition tests |  |  |
| **[Type](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?usp=sharing)** | **Author(s)** | **[Status](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?usp=sharing)** | **Created** |
| Implementation | [Tony Meyer](mailto:tony.meyer@canonical.com) | Drafting | Jun 8, 2026 |
|  | **Reviewer(s)** | **Status** | **Date** |
|  | Person | Pending Review | Date |

# Abstract

This spec defines a multi-charm unit (state-transition) test surface folded into `ops.testing`. It provides `deploy`, `integrate`, `add-unit`, `remove-unit`, and `update-config` as test operations, with the corresponding Juju events triggered automatically as the model converges. Each charm runs in its own isolated subprocess (its own venv), so charms with mutually incompatible dependency sets can be tested together in a single test. This spec targets `ops.testing` in `canonical/operator`; it is not a companion package. It draws the abstraction from [Catan](https://github.com/PietroPasotti/catan) (Apps \+ convergence) but is not a direct port.

# Rationale

### **The gap in current tooling**

`ops.testing` (Scenario) runs one charm at a time: the developer writes an event and a `State`, calls `Context.run`, and asserts on the output. This is efficient for single-charm logic but leaves four pain points unaddressed:

- **Integration tests are slow.** A real Juju controller bootstrap and deploy round-trip takes minutes; unit tests should be measured in seconds.  
- **Scenario is unlike the `juju` commands charmers think in.** Charmers reason about `juju deploy`, `juju integrate`, `juju add-unit`. Translating that mental model into hand-crafted event sequences and `State`s is friction the tool should absorb. This has been evident in the success of Jubilant (which itself further strengthens the issue, because charmers are now also used to thinking that way in integration tests too).  
- **Charm libraries don't yet ship mocks.** Cross-charm relation data is hand-crafted per test. Running the other charm's own code against the relation removes that hand-crafting: the other charm's actual reaction becomes the fixture. This may change with the acceptance of [OP077](https://docs.google.com/document/d/1A50MlUpNz6YPVvIFxFZYTDBgxNboVYlpfZB8uy8o58c/edit?usp=sharing) (Charm library testing).  
- **Bundle (or solution) and topology assertions are unreachable from unit tests.** Asserting "if I deploy A and B and integrate them, A's leader ends up with config X" requires real Juju or fragile mocks today.

The shape charmers ask Charm Tech for is ‘a multi-charm state-transition test tool that feels like Juju’. This is Catan’s abstraction (Apps, `integrate`, convergence / settle).

Why ops.testing rather than a companion package? Catan today pins `ops-scenario~=6.0`, a superseded API that has been merged into `ops.testing` as Scenario 7 (Scenario 8 is identical to 7, other than requiring Python 3.10+). Porting off that API is **net-new work regardless of the destination**; there is no path that productises the companion-package form without a full re-targeting. Since we have to re-target anyway, we target `ops.testing` directly. This is a non-trivial addition to ops-scenario, but not so large that it merits a new ops-{something} package, with the packaging overhead that comes from that.

# Specification

### **Location and scope**

The new surface lives in `ops.testing` (`canonical/operator`), the same module that provides `Context` and `State`. The single-charm primitives are **unchanged and remain the substrate**. The new surface adds a model-level layer above `Context` that owns a set of `App`s, an integration graph, and a convergence loop. Single-charm Scenario (state transition) tests continue to work exactly as today and do not require the new surface.

### **Operation surface**

The test API uses Juju-shaped operations (`deploy`, `integrate`, `add-unit`, `remove-unit`, `update-config`, `run_action`) that describe **intents, not events**. The model generates the correct Juju-faithful event sequence and delivers it to the affected units.

# 

```py
from ops import testing

model = testing.Model()  # Already exists, but *not* the same as ops.Model!

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

model.integrate(db, web)
# Or, when the endpoints need to be disambiguated:
# model.integrate(db.get_endpoint("db"), web.get_endpoint("pg"))
model.add_unit(web)
model.update_config(web, {"log_level": "debug"})
model.remove_unit(web, unit=1)
model.run_action(db.leader, "create-backup", params={})
```

# 

`Model.deploy(...)` returns an `App` handle. An `App` owns its charm reference, the metadata resolved from the charm on disk, the environment it runs in (see Isolation model below), and its per-unit `State`s. Exact type names are illustrative and will be settled in code review.

`Model.integrate(...)` follows Jubilant's shape but takes `App` objects rather than strings — we have the objects here, and there is no live Juju model to look them up in. The default form `integrate(db, web)` works whenever the endpoint pair is unambiguous from the two charms' metadata. When it isn't, endpoints are named explicitly via `App.get_endpoint(name)`: `integrate(db.get_endpoint("db"), web.get_endpoint("pg"))`. This mirrors Jubilant's `integrate("postgresql:db", "myapp:pg")` while keeping the API object-typed.

### **Charm source: local paths only in v1**

`charm=` in v1 is **a path to charm source on the local filesystem**. Type is `pathlib.Path | str`; a `str` must be a relative path, matching `juju deploy` behaviour. This covers test charms and monorepos out of the box.

**Not in v1:**

- **Deploy from git** (with or without patches, as Catan supports) is out of scope for v1 and possibly ever — the complexity is high and the value versus a conftest-managed clone is low.
- **Deploy from Charmhub** — feasible (download → unzip → treat the unpacked source as a local path), but not v1. If added later, the same `charm=` argument would grow a Charmhub-URL form; no prototype yet.

**Recommendation for charms defined outside your repository:** the test infra (typically a `conftest.py` fixture) should source the charm from somewhere — `git clone` is the obvious choice — and pass the resulting local path to `deploy(charm=...)`. This keeps the harness surface small and puts the "where does this charm come from" decision in the test author's hands, where it can be tailored to CI, caching, and gitignore rules per project.

### **Automatic event triggering and convergence**

Each operation enqueues the appropriate events (`relation-created`, `relation-joined`, `relation-changed`, `config-changed`, and so on) on the affected units. A **convergence loop** drains the queue: it picks an event, dispatches it through that unit's `Context.run(...)`, observes any new relation-data writes, status changes, or secret operations, and enqueues the downstream events those produce on peers and related units. Convergence terminates when the queue is empty and no unit's last run produced new observable changes.

```py
model.settle()   # explicit convergence point
assert web.leader.state.unit_status == ActiveStatus("ready")
assert db.leader.state.get_relation("db").local_app_data["database"] == "myapp"
```

Catan shows that this can be done with suitable fidelity to Juju without *actually reimplementing Juju*. We are able to take advantage of the non-specific ordering of some Juju events, and also of the access to the Juju code to understand its behaviour.

`settle()` is also called implicitly before reading any unit’s `State` if there are pending events, so most tests are a sequence of operations followed by assertions on `app.leader.state` or `app.units[i].state`. The `State` exposed on each unit is the same `ops.testing.State` dataclass that single-charm Scenario tests use today; all existing assertions are available unchanged.

For tests that need to assert on **intermediate** state — partway through convergence, or on the exact sequence of events dispatched — two complementary APIs are exposed:

- **Step-at-a-time context** — mirrors Scenario's `with ctx(...) as mgr: mgr.run(...)` shape. Inside the block, the implicit-settle-on-read is suspended so assertions between steps do not drain the queue:

    ```py
    with model.stepping() as stepper:
        stepper.step()      # dispatch exactly one queued event
        assert web.leader.state.unit_status == MaintenanceStatus("configuring")
        stepper.step()
        assert ...
    # outside the block, implicit-settle-on-read is back
    ```

    `stepper.step()` returns the `(event, unit)` it just dispatched so the loop can be predicate-driven (`while stepper.step() != ("relation-changed", web.leader): ...`) without a separate peek API. Exiting the block re-enables implicit settling.

- **Recorded event trace** — `settle()` returns the deterministic sequence of `(event, unit, state_snapshot)` tuples it dispatched, so post-hoc assertions can walk what happened without needing to steer the loop:

    ```py
    trace = model.settle()
    assert [e.name for e, _, _ in trace] == ["relation-created", "relation-joined", "relation-changed", "config-changed"]
    ```

    No behaviour change to the default settle path — the return value is additive.

Mid-flight assertions with `stepping()`, post-hoc assertions with the returned trace; neither leaks into the default settle path a simple test uses.

Given the same starting `Model` and the same input event sequence, `settle()` **must** produce the same final `State` per unit and the same sequence of intermediate events, byte-for-byte, across runs and across machines. **No wall-clock dependence, no PID-derived ordering, no Python-dict-iteration-order leakage** is permitted in the policy. The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is decided against this requirement, when there is working code to validate it. See [Further Information](#settle-policy-considerations).

Real Juju runs charms concurrently and per-unit event ordering is non-deterministic. Unit tests must be deterministic, so v1 ships a single ordering policy — but the design keeps the door open for exercising alternative orderings against the *same* starting sequence of events. Two mechanisms are anticipated (concrete API picked in step 5 alongside the default policy):

- **Alternative strategies via `settle(...)` arguments** — e.g. `model.settle(strategy="data-flow")` vs `strategy="round-robin"` vs a caller-supplied deterministic function. Running the same test under two strategies is one way to smoke out charms that accidentally depend on one particular ordering.
- **Per-app / per-unit scheduling hints** — e.g. mark an `App` as "running late" so its events are held until the queue is otherwise empty, or bias one unit to drain first. This lets charmers reproduce specific ordering bugs seen in production.

Both are optional layers on top of the default deterministic policy; the default remains what `settle()` with no arguments does.

### **Isolation model: subprocess \+ per-charm venv**

Each `App` runs in its own process with its own interpreter (an existing venv's `bin/python`, or one the harness provisioned; see Environment provisioning below). For each event dispatch the harness serialises `(meta, config, actions, event, State)` as JSON, sends it to the charm's worker process, the worker runs `testing.Context(...).run(...)`, and serialises the resulting `State` back. Two `App`s in the same `Model` may use mutually incompatible dependency sets (`cryptography==41` vs `==3`, different `pydantic` majors, conflicting charm-lib versions, …).

**Required invariant:** each per-charm venv contains an `ops` / `ops-scenario` build whose JSON `State` wire format is compatible with the parent process's. Only the charm's own runtime deps differ between venvs. This is realistic, since all charms (that matter here) build on `ops`.

**Cross-`ops`-version compatibility policy.** Running each charm in its own venv means charms may sit on different `ops` versions than the parent process — a real ongoing cost. The policy has three parts:

- **Version negotiation at worker handshake.** On startup, the worker declares the wire-format version it supports. The parent process picks the intersection or raises `StateSchemaVersionError` (already introduced by the typed-`State` serialiser, step 2 of the incremental delivery plan). Mismatches fail fast at handshake, not silently mid-test.
- **Directionality: unidirectional, parent-authoritative.** The parent process (running `ops.testing`) is the authority; it supports schema versions `1..N` where `N` is its own current version. A charm worker on any version in `1..N` is fine — the parent decodes at the worker's declared version. A worker on `>N` (a newer `ops` than the parent) raises at handshake, because the parent cannot invent decoder logic for a future schema. **Practical invariant: the orchestrating test suite's `ops` must be ≥ every charm-under-test's `ops`.** This matches the natural test-suite topology (bump `ops.testing` first, then adopt in charms) and keeps the compat matrix strictly triangular rather than a full N×N grid.
- **Documented compatibility window.** Wire-format changes are treated as `ops` release-note items with an explicit "supported charm-side `ops` versions" range published against each `ops.testing` release — this is the *floor* (how far back a charm can be); the *ceiling* is the parent's own version (directionality, above). Charms outside the window raise at handshake with a message pointing at the range. Bounded surface, small compat matrix, testable.
- **Escape hatch: pin the charm's `ops` to the parent process's.** When `build_env=True`, the provisioner can override the charm's declared `ops` pin with the parent process's exact version via `deploy(..., pin_ops=True)`. Cuts through the compat matrix at the cost of not exercising the charm on its own declared `ops`. Off by default; opt-in per `deploy(...)`.

The isolation worker is persistent: one long-lived process per `App`, spawned lazily on first dispatch and torn down at `Model` teardown or after an idle timeout. A framed JSON protocol over stdin/stdout carries requests and responses. Spawn-per-event remains available as an explicit debug mode (easier to attach a debugger; no shared interpreter state between events). Worker crashes propagate as a typed `IsolationError` and fail the test cleanly; the harness never silently re-spawns mid-test.

Acceptance criteria:

- **Workload:** the performance yardstick is a **4-charm bundle with 20 events per `settle()`** (80 dispatches total). Lives in the test suite and is re-run by every later step to catch regressions.  
- **Bar:** **persistent-worker mode within 2× the in-process Scenario baseline** on that workload. 2× is the threshold where "slow but acceptable for a CI unit-test suite" tips into "too slow, charmers will avoid it and just use integration tests"; subprocess \+ JSON serialisation has a real floor below that.  
- **Benchmark shape:** a benchmark suite measuring (a) in-process Scenario baseline, (b) spawn-per-event isolated, and (c) persistent-worker isolated, all on the same 4-charm/20-event workload.
- **Measured absolute numbers (step 3 draft implementation, Python 3.11.15, median of 5 reps):**

    | mode | total (80 dispatches) | per event | vs baseline |
    | :---- | :---- | :---- | :---- |
    | (a) in-process Scenario baseline | 0.332 s | 4.15 ms | 1.00× |
    | (c) persistent-worker isolated | 1.671 s | 20.89 ms | **5.04×** |
    | (b) spawn-per-event isolated | 22.94 s | 286.77 ms | 69× |

    Persistent-worker mode does **not** currently meet the 2× bar (see step 3 log in [`step3-persistent-worker-log.md`](./step3-persistent-worker-log.md)). Dominant cost is `import ops` per worker (~243 ms), paid once per isolated environment and structurally unshareable across environments; JSON/IPC is sub-millisecond per event. On this 4-worker workload the ~1.1 s of worker spawns alone already exceeds the 2× budget (~0.66 s). Persistent is nonetheless ~13.7× faster than spawn-per-event and is the correct foundation for step 5's convergence loop, where more events per worker amortise the spawn cost further. **The 2× bar itself is up for revision** in light of the numbers — the working assumption is that the threshold is comfortably higher than 2× in practice, and step 5 will re-measure with real bundle-shaped workloads before locking it in.

### **Subinterpreters are explicitly ruled out**

PEP 734 subinterpreters are **not** the mechanism, even assuming a Python 3.14+ requirement would be acceptable:

- **Binary-dependency conflicts remain unsolved.** Many C extensions (`cryptography`, `pydantic-core`, `cffi`\-based packages) are not multi-interpreter-safe; two different versions of the same extension cannot coexist in one process at any Python version. These are the exact libraries motivating the work.  
- **State boundary still costs a serialisation roundtrip**. The same JSON encode/decode as a subprocess, taken without the isolation benefit.  
- **Maintenance cost is high** on a bleeding-edge API for no payoff over the subprocess design.

This will be revisited only if the C-extension multi-interpreter story matures enough to load conflicting binary versions in one process, not merely because the Python version floor moves.

## Environment provisioning

The environment API is deliberately layered so the core primitive has a small surface and no external-tool dependencies, and the ergonomic auto-detection form is a convenience helper on top rather than the load-bearing default.

**Layer 1 — inherit the test process** (default; no `python=` argument). No isolation, no venv work, no external tools. Runs the charm in the same interpreter as the test. Unblocks Scenario-style tests with locally-defined test charms and monorepo cases where dependencies are known compatible.

**Layer 2 — explicit interpreter + resolved requirements** (`Model.deploy(..., python="/path/to/venv/bin/python", requirements=[...])`). The core primitive: a Python interpreter path plus a fully-resolved list of pip specifiers. Zero magic; no charmcraft-plugin knowledge; no dependency on `uv` or `poetry`. The caller has already done whatever resolution they want to do (their own build script, their own lockfile export, whatever). This form unlocks the conflicting-dependency case without pulling any external-tool complexity into the core.

    Passing `python=` without `requirements=` means "use this interpreter as-is" — the caller has already provisioned the venv. Passing `requirements=` without `python=` is an error.

**Layer 3 — auto-provision from declared deps** (opt-in `Model.deploy(..., build_env=True)`). A convenience helper that detects the charm's build plugin, extracts the dependency list, and calls into layer 2 with the extracted values. Charmers who want ergonomics use this; charmers whose plugin detection fails, or who want control, drop to layer 2 without losing anything.

    Plugin detection is `charmcraft.yaml` first; file-based heuristic second (`uv.lock` → `uv`; `poetry.lock` → `poetry`; `pyproject.toml` → `python`; else → `charm`). Extraction per plugin:

    | Plugin | Extraction method |
    | :---- | :---- |
    | charm | reads `charm-requirements` files \+ `charm-python-packages` \+ AST-harvested `PYDEPS` from `lib/**/*.py` |
    | python | reads `python-requirements` / `python-packages` \+ PYDEPS (included even though charmcraft's python plugin does not auto-install them: the isolation worker needs the lib importable) |
    | uv | shells to `uv export --frozen --no-emit-project --no-hashes --format requirements-txt` with forwarded `--extra` / `--group` flags |
    | poetry | shells to `poetry export --without-hashes --format requirements.txt` with forwarded `--with` flags |

    All forms normalise to a flat pip specifier list, then install via `uv pip install` into the per-charm venv. The venv is cached on disk, keyed by SHA-256 of (plugin, extracted requirements, lockfile/pyproject content, interpreter version, parent-process `ops` version): cold build \~3s for a test charm; warm cache hit \<0.05s (measured). Detection-and-extraction was validated against two real charms (loki-k8s-operator via the uv plugin; postgresql-k8s-operator via the poetry plugin). Layer 3 emits a clear, typed error when an extracted requirement cannot be resolved, when a lockfile is stale relative to the pyproject, or when a required external tool (`uv` / `poetry`) is missing — the failure mode is "drop to layer 2", not "fall through silently".

**Tool dependency (layer 3 only):** `uv` on PATH for all install steps; `poetry` \+ `poetry-plugin-export` for the poetry-plugin path. Layers 1 and 2 depend on nothing beyond the Python standard library. This scopes the external-tool concern to the convenience layer where charmers opted in to the ergonomics.

**Future:** a charmcraft-managed flow for charms already packed locally, sitting at layer 3 alongside the plugin-based extraction.

## State (de)serialisation

A typed schema-aware encoder/decoder pair (not `json.dumps(dataclasses.asdict(state))`) covers all `ops.testing.State` leaf types:

| Type | Encoding |
| :---- | :---- |
| `frozenset` (on `relations`, `containers`, `secrets`, etc.) | list on encode; re-frozen on decode (dataclass `__post_init__`s re-freeze) |
| `datetime` / `timedelta` | ISO-8601 string / fractional seconds |
| `pathlib.Path` / `PurePosixPath` | string with type tag |
| Pebble enums (`ServiceStatus`, `NoticeType`, `SecretRotate`, …) | enum name |
| `pebble.Layer` (`Container.layers`) | `to_dict()` / `Layer(dict)` round-trip (not a dataclass; `asdict` won't descend) |
| Int-keyed dicts (`Secret.remote_grants: Mapping[int, set[str]]`) | keys stringified on encode; restored to `int`, inner `set` restored on decode |

`StoredState.content` and `Container._base_plan` are `Mapping[str, Any]` of marshallable types, a superset of JSON: `bytes`, `tuple`\-vs-`list` distinction, and arbitrary `set`s. The spec commits to:

1. **A typed escape hatch, applied always**: tag-and-encode `bytes` as base64 and `tuple` as a `["__tuple__", ...]` envelope so they round-trip losslessly. **No flag.** An opt-in would create a "passed locally because today's stored-state had no `bytes`, failed in CI when it did" failure mode; the cost (a few extra bytes per typed value) doesn't justify it.  
2. **Loud error on unrecognised types**: the encoder raises `TypeError` with the type name and the path through `State`. The decoder mirrors: unknown `__type__` tags raise `TypeError`. Never silent lossy coercion.

A small follow-up survey of in-tree charm `StoredState` usage is left as a separate work item, to confirm no charm relies on round-tripping more exotic marshallable types than `bytes`/`tuple`/`set`. The survey does not gate the implementation; it informs whether the encoder's type set needs to be extended.

The JSON `State` representation is **part of `ops.testing`'s public API**: a per-charm venv may have a different `ops` build from the parent, and both sides must agree on the encoded form.

1. **Explicit `state_schema_version` integer field** is embedded in every encoded `State` payload. Cheaper and more legible than overloading `ops`'s SemVer: we don't have to ship an `ops` major just because we added one field to `State` serialisation.  
2. **Per-version interpretation is locked at the source-code level**: a dispatch table keyed by version. Adding a new version is ordinary work; changing the *meaning* of an existing version is not.  
3. **Decoder rejects unsupported versions with a clear typed error.** A v1 producer and a v1+v2 consumer work fine. A version the decoder doesn't recognise surfaces as an explicit error, not silent corruption.  
4. **`ops.testing` API-stability documentation commits to (2).** "We may add new versions; we don't change the meaning of an existing version."

### **Serialisation examples**

#### Container with a Pebble layer, notices, check infos, service statuses, and mounts

This example shows the most type-envelope diversity in one place: `pebble.Layer` → **t**: "layer", `pebble.ServiceStatus` enum → **t**: "enum", `pebble.NoticeType` enum, `datetime` fields, `timedelta` fields, `PurePosixPath` and `Path` in a `Mount`, and `CheckInfo` containing multiple enum types.

```py
  state = State(
      containers=frozenset([
          Container(
              name='myapp',
              can_connect=True,
              layers={
                  'base': pebble.Layer({
                      'services': {
                          'app': {
                              'command': '/bin/app --port 8080',
                              'startup': 'enabled',
                              'override': 'replace',
                          },
                      },
                  }),
              },
              service_statuses={'app': pebble.ServiceStatus.ACTIVE},
              notices=[
                  Notice(
                      key='example.com/event',
                      type=pebble.NoticeType.CUSTOM,
                      repeat_after=datetime.timedelta(minutes=30),
                      first_occurred=datetime.datetime(
                          2025, 6, 15, 10, 0, 0, tzinfo=datetime.timezone.utc
                      ),                                                 
                      last_occurred=datetime.datetime(
                          2025, 6, 15, 10, 30, 0, tzinfo=datetime.timezone.utc
                      ),
                      last_repeated=datetime.datetime(
                          2025, 6, 15, 10, 30, 0, tzinfo=datetime.timezone.utc
                      ),
                  ),
              ],
              check_infos=frozenset([
                  CheckInfo(
                      name='http',
                      level=pebble.CheckLevel.ALIVE,
                      status=pebble.CheckStatus.UP,
                  ),
              ]),
              mounts={
                  'cfg': Mount(
                      location=pathlib.PurePosixPath('/etc/config'),
                      source=pathlib.Path('/tmp/cfg'),
                  ),
              },
          ),
      ]),
  )
```

```json
  {                                                                            
    "state_schema_version": 1,                                                 
    "state": {                                                                 
      "__t__": "dc",                                                           
      "cls": "State",                                                          
      "f": {                                                                   
        "config": {},                                                          
        "relations": {"__t__": "frozenset", "v": []},                          
        "networks": {"__t__": "frozenset", "v": []},                           
        "containers": {"__t__": "frozenset", "v": [                            
          {                                                                    
            "__t__": "dc",                                                     
            "cls": "Container",                                                
            "f": {                                                             
              "name": "myapp",                                                 
              "can_connect": true,                                             
              "_base_plan": {},                                                
              "layers": {                                                      
                "base": {                                                      
                  "__t__": "layer",                                            
                  "v": {                                                       
                    "services": {                                              
                      "app": {                                                 
                        "startup": "enabled",                                  
                        "override": "replace",                                 
                        "command": "/bin/app --port 8080"                      
                      }                                                        
                    }                                                          
                  }                                                            
                }                                                              
              },                                                               
              "service_statuses": {                                            
                "app": {"__t__": "enum", "cls": "ServiceStatus", "name":       
"ACTIVE"}                                                                      
              },                                                               
              "mounts": {                                                      
                "cfg": {                                                       
                  "__t__": "dc",                                               
                  "cls": "Mount",                                              
                  "f": {                                                       
                    "location": {"__t__": "PurePosixPath", "v":                
"/etc/config"},                                                                
                    "source": {"__t__": "Path", "v": "/tmp/cfg"}               
                  }                                                            
                }                                                              
              },                                                               
              "execs": {"__t__": "frozenset", "v": []},                        
              "notices": [                                                     
                {                                                              
                  "__t__": "dc",                                               
                  "cls": "Notice",                                             
                  "f": {                                                       
                    "key": "example.com/event",                                
                    "id": "1",                                                 
                    "user_id": null,                                           
                    "type": {"__t__": "enum", "cls": "NoticeType", "name":     
"CUSTOM"},                                                                     
                    "first_occurred": {"__t__": "datetime", "v":               
"2025-06-15T10:00:00+00:00"},                                                  
                    "last_occurred": {"__t__": "datetime", "v":                
"2025-06-15T10:30:00+00:00"},                                                  
                    "last_repeated": {"__t__": "datetime", "v":                
"2025-06-15T10:30:00+00:00"},                                                  
                    "occurrences": 1,                                          
                    "last_data": {},                                           
                    "repeat_after": {"__t__": "timedelta", "v": 1800.0},       
                    "expire_after": null                                       
                  }                                                            
                }                                                              
              ],                                                               
              "check_infos": {"__t__": "frozenset", "v": [                     
                {                                                              
                  "__t__": "dc",                                               
                  "cls": "CheckInfo",                                          
                  "f": {                                                       
                    "name": "http",                                            
                    "level": {"__t__": "enum", "cls": "CheckLevel", "name":    
"ALIVE"},                                                                      
                    "startup": {"__t__": "enum", "cls": "CheckStartup",        
"name": "ENABLED"},                                                            
                    "status": {"__t__": "enum", "cls": "CheckStatus", "name":  
"UP"},                                                                         
                    "successes": 0,                                            
                    "failures": 0,                                             
                    "threshold": 3,                                            
                    "change_id": "1"                                           
                  }                                                            
                }                                                              
              ]}                                                               
            }                                                                  
          }                                                                    
        ]},                                                                    
        "storages": {"__t__": "frozenset", "v": []},                           
        "opened_ports": {"__t__": "frozenset", "v": []},                       
        "leader": false,                                                       
        "model": {"__t__": "dc", "cls": "Model", "f": {"name": "...", "uuid":  
"...", "type": "kubernetes", "cloud_spec": null}},                             
        "secrets": {"__t__": "frozenset", "v": []},                            
        "resources": {"__t__": "frozenset", "v": []},                          
        "planned_units": 1,                                                    
        "deferred": [],                                                        
        "stored_states": {"__t__": "frozenset", "v": []},                      
        "app_status": {"__t__": "status", "name": "unknown", "msg": ""},       
        "unit_status": {"__t__": "status", "name": "unknown", "msg": ""},      
        "workload_version": ""                                                 
      }                                                                        
    }                                                                          
  }                                                                            
```

#### Secrets with `int`\-keyed `remote_grants`, rotation policy, and Relations with `int`\-keyed `remote_units_data`

This example shows the "idict" envelope (for `dict[int, ...]` which JSON can’t represent natively), the "set" envelope inside an `idict`, and `SecretRotate` enum.

```py
  state = State(
      secrets=frozenset([
          Secret(
              tracked_content={'password': 'x2', 'cert': '---BEGIN CERT---'},
              latest_content={'password': 'x3', 'cert': '---BEGIN CERT---'},
              owner='app',
              label='db-creds',
              description='Database credentials',
              expire=datetime.datetime(
                  2030, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc
              ),
              rotate=SecretRotate.DAILY,
              remote_grants={0: {'related-app'}, 2: {'other-app/0'}},
          ),
      ]),
      relations=frozenset([
          Relation(
              endpoint='db',
              interface='postgresql_client',
              remote_app_name='postgresql',
              remote_units_data={
                  0: {'host': '10.0.0.1', 'port': '5432'},
                  1: {'host': '10.0.0.2', 'port': '5432'},
              },
              remote_app_data={'version': '14', 'db': 'mydb'},
          ),
          PeerRelation(
              endpoint='peers',
              peers_data={1: {'leader': 'true', 'ready': 'yes'}},
          ),
      ]),
  )
```

```json
  {                                                                            
    "relations": {"__t__": "frozenset", "v": [                                 
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "Relation",                                                     
        "f": {                                                                 
          "endpoint": "db",                                                    
          "interface": "postgresql_client",                                    
          "id": 1,                                                             
          "local_app_data": {},                                                
          "local_unit_data": {                                                 
            "egress-subnets": "192.0.2.0",                                     
            "ingress-address": "192.0.2.0",                                    
            "private-address": "192.0.2.0"                                     
          },                                                                   
          "remote_app_name": "postgresql",                                     
          "limit": 1,                                                          
          "remote_app_data": {"version": "14", "db": "mydb"},                  
          "remote_units_data": {                                               
            "__t__": "idict",                                                  
            "v": {                                                             
              "0": {"host": "10.0.0.1", "port": "5432"},                       
              "1": {"host": "10.0.0.2", "port": "5432"}                        
            }                                                                  
          },                                                                   
          "remote_model_uuid": null                                            
        }                                                                      
      },                                                                       
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "PeerRelation",                                                 
        "f": {                                                                 
          "endpoint": "peers",                                                 
          "interface": null,                                                   
          "id": 2,                                                             
          "local_app_data": {},                                                
          "local_unit_data": {"egress-subnets": "192.0.2.0",                   
"ingress-address": "192.0.2.0", "private-address": "192.0.2.0"},               
          "peers_data": {                                                      
            "__t__": "idict",                                                  
            "v": {"1": {"leader": "true", "ready": "yes"}}                     
          }                                                                    
        }                                                                      
      }                                                                        
    ]},                                                                        
    "secrets": {"__t__": "frozenset", "v": [                                   
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "Secret",                                                       
        "f": {                                                                 
          "tracked_content": {"password": "hunter2", "cert": "---BEGIN         
CERT---"},                                                                     
          "latest_content": {"password": "hunter3", "cert": "---BEGIN          
CERT---"},                                                                     
          "id": "secret:oup6t3bz6wzkkjylya5u",                                 
          "owner": "app",                                                      
          "remote_grants": {                                                   
            "__t__": "idict",                                                  
            "v": {                                                             
              "0": {"__t__": "set", "v": ["related-app"]},                     
              "2": {"__t__": "set", "v": ["other-app/0"]}                      
            }                                                                  
          },                                                                   
          "label": "db-creds",                                                 
          "description": "Database credentials",                               
          "expire": {"__t__": "datetime", "v": "2030-12-31T23:59:59+00:00"},   
          "rotate": {"__t__": "enum", "cls": "SecretRotate", "name": "DAILY"}, 
          "_tracked_revision": 1,                                              
          "_latest_revision": 1                                                
        }                                                                      
      }                                                                        
    ]}                                                                         
  }                                                                            
```

#### `StoredState` escape hatch (`bytes`, `tuple`, `set`) \+ statuses, resources, ports, and deferred events

This example shows the escape-hatch types that `StoredState.content` can contain: `bytes` (base64-encoded), `tuple` (`list`\-based envelope), and `set`. It also shows the "status" envelope for non-trivial status values, "Path" in a Resource, and `DeferredEvent`.

```py
  state = State(
      config={'log_level': 'debug', 'port': 8080, 'enabled': True},
      leader=True,
      unit_status=ActiveStatus('ready'),
      app_status=BlockedStatus('needs database'),
      workload_version='1.2.3',
      planned_units=3,
      stored_states=frozenset([
          StoredState(
              name='_stored',
              owner_path='MyCharm',
              content={
                  'count': 42,
                  'raw': b'\xde\xad\xbe\xef',
                  'coords': (1, 2, 3),
                  'tags': {'alpha', 'beta'},
                  'mapping': {'nested': True},
              },
          ),
      ]),
      resources=frozenset([
          Resource(name='oci-image', path=pathlib.Path('/tmp/image.tar')),
      ]),
      opened_ports=frozenset([TCPPort(8080), UDPPort(53)]),
      deferred=[
          DeferredEvent(
              handle_path='MyCharm/on/config_changed[1]',
              owner='MyCharm',
              observer='_on_config_changed',
          ),
      ],
  )
```

```json
  {                                                                            
    "config": {"log_level": "debug", "port": 8080, "enabled": true},           
    "opened_ports": {"__t__": "frozenset", "v": [                              
      {"__t__": "dc", "cls": "UDPPort", "f": {"port": 53, "protocol": "udp"}}, 
      {"__t__": "dc", "cls": "TCPPort", "f": {"port": 8080, "protocol":        
"tcp"}}                                                                        
    ]},                                                                        
    "leader": true,                                                            
    "resources": {"__t__": "frozenset", "v": [                                 
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "Resource",                                                     
        "f": {                                                                 
          "name": "oci-image",                                                 
          "path": {"__t__": "Path", "v": "/tmp/image.tar"}                     
        }                                                                      
      }                                                                        
    ]},                                                                        
    "planned_units": 3,                                                        
    "deferred": [                                                              
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "DeferredEvent",                                                
        "f": {                                                                 
          "handle_path": "MyCharm/on/config_changed[1]",                       
          "owner": "MyCharm",                                                  
          "observer": "_on_config_changed",                                    
          "snapshot_data": {}                                                  
        }                                                                      
      }                                                                        
    ],                                                                         
    "stored_states": {"__t__": "frozenset", "v": [                             
      {                                                                        
        "__t__": "dc",                                                         
        "cls": "StoredState",                                                  
        "f": {                                                                 
          "name": "_stored",                                                   
          "owner_path": "MyCharm",                                             
          "content": {                                                         
            "count": 42,                                                       
            "raw": {"__t__": "bytes", "v": "3q2+7w=="},                        
            "coords": ["__tuple__", 1, 2, 3],                                  
            "tags": {"__t__": "set", "v": ["alpha", "beta"]},                  
            "mapping": {"nested": true}                                        
          },                                                                   
          "_data_type_name": "StoredStateData"                                 
        }                                                                      
      }                                                                        
    ]},                                                                        
    "app_status": {"__t__": "status", "name": "blocked", "msg": "needs         
database"},                                                                    
    "unit_status": {"__t__": "status", "name": "active", "msg": "ready"},      
    "workload_version": "1.2.3"                                                
  }                                                                            
```

## Metadata resolution

The harness reads `metadata.yaml` / `charmcraft.yaml` from the charm source path without importing the charm in the test process. Less common cases are left as future work:

- Resolve unified-vs-legacy metadata variants and the merged `charmcraft.yaml` \+ `metadata.yaml` form charms commonly produce  
- Resolve charm libraries the charm declares but that live elsewhere on disk  
- Inline charm classes (`from_type` charms defined in the test): kept as in-process, same-environment only; isolation requires charms on disk (`from_isolated_path`). See Further Information.

At least one passing test for each of these charm shapes must be included in the implementation:

1. Unified `charmcraft.yaml` only (no `metadata.yaml`) — the current default-modern shape.  
2. Legacy split: `metadata.yaml` \+ `actions.yaml` \+ `config.yaml` — older charms still in production.  
3. Mixed / transitional: `charmcraft.yaml` \+ `metadata.yaml` (the form charmcraft merges) — charms mid-migration.  
4. Multi-bases (`bases:` / `platforms:` variants per supported platform).  
5. Charm with libs outside `src/` (e.g. installed via `pip` from PyPI for testing) — exercises the "where did this lib come from" resolution.  
6. Inline `from_type` (no metadata file; class declares everything) — documented as `inline: ok` per the docstring convention in Further Information.

## Migration from Catan / ops-scenario\~=6.0

The existing `PietroPasotti/catan` package pins `ops-scenario~=6.0` (superseded by `ops.testing`). There is **no compatibility shim**: tests written against Catan must be rewritten against the new API surface. The `ops-scenario~=6.0` form is throwaway regardless of whether this spec is adopted. Porting off it is net-new work either way.

What the spec carries forward from Catan:

- The model: Apps \+ integration graph \+ convergence/settle  
- The Juju-like operation vocabulary: `deploy` / `integrate` / `add-unit` / …

## Incremental delivery plan

Sequenced so each merge is **independently useful** and the area can pause cleanly after any step. This is the handle on the priority reservation: agentic coding lowers per-step build cost, and the sequencing means a pause never strands a half-built feature.

| Step | Deliverable | Value without later steps |
| :---- | :---- | :---- |
| 1 ([proof of concept PR](https://github.com/tonyandrewmeyer/operator/pull/18)) | Lift isolation into `ops.testing`: `IsolatedEnv`, persistent worker, `from_isolated_path` | Immediately useful: run one charm in an isolated venv from a Scenario test; no `Model`, no convergence |
| 2 ([proof of concept PR](https://github.com/tonyandrewmeyer/operator/pull/20)) | Typed `State` (de)serialiser with full leaf-type coverage and the StoredState escape hatch | Snapshot-style tests and debugging; required by every later step |
| 3 ([proof of concept PR](https://github.com/tonyandrewmeyer/operator/pull/22)) | Persistent-worker mode replacing spawn-per-event (benchmarked in the same PR). **Acceptance:** within 2× of in-process Scenario on the 4-charm/20-event workload. See *Isolation model* | Performance baseline; unblocks realistic convergence-run testing |
| 4 | `Model` \+ `App` \+ non-relating operations: `deploy`, `add-unit`, `remove-unit`, `update-config`, `run_action`, single-app convergence | Drive a single charm through Juju-shaped operations without writing event sequences by hand |
| 5 | `integrate` \+ cross-app event propagation \+ settle policy locked. **Acceptance:** see *Settle policy considerations* (Further Information), at least one deterministic policy passes a 100×-soak; user-override hook exposed | Unlocks the multi-charm pain points; steps 1–4 stand alone if priorities pull us off here |
| 6 | `build_env=True` environment provisioning (all four plugins, caching, lockfile handling) \+ full metadata-resolution coverage. **Acceptance:** the six-shape metadata test set. See *Metadata resolution* | Productisation tail; not on the critical path for any earlier step |

# Further Information

### **Settle policy considerations** {#settle-policy-considerations}

The determinism requirement is locked in *Automatic event triggering and convergence*: byte-for-byte reproducible across runs and machines; no wall-clock, PID, or dict-iteration-order leakage.

The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is picked in step 5 against that requirement, with the following acceptance:

- At least one deterministic policy ships and passes a **"run 100×, all final `State`s identical"** soak test.  
- The API exposes a **user-override hook** for cases the default policy doesn't fit. The hook may ship empty initially.

Picked here rather than locked up front because the choice benefits from being able to play with the convergence loop in working code.

## **Inline charm classes vs. on-disk charms**

`from_type` charms defined inline in a test cannot be trivially transferred to a fresh subprocess (the class object is not serialisable). Isolation realistically requires charms on disk. The API keeps both paths: inline classes run in-process with no isolation (like Scenario today); on-disk charms run isolated by default.

The matrix of ‘works inline but not isolated’ surprises is closed by a **documentation convention** rather than a runtime check. Every operation beyond `IsolatedContext.run()` (`deploy`, `add-unit`, `integrate`, `update-config`, `run_action`, …) declares in its docstring two explicit fields:

- inline: ok | error | n/a  
- isolated: ok | error | n/a

Where `ok` means works as documented, `error` means raises a clear typed error explaining why it's not supported in this mode, and `n/a` means doesn't make sense in this mode.

This is enforced by API-doc review at PR time. It’s trivial to grep for. The matrix becomes readable in the docs rather than discoverable only by trial. There is no separate validation layer.

### **Real-world charm coverage**

The isolation and provisioning proof-of-concept implementations were validated end-to-end on synthetic test charms with intentionally conflicting deps, and the provisioning detection/extraction path was validated against two real charms (loki-k8s-operator, postgresql-k8s-operator) via a read-only `describe` CLI. Full end-to-end "provision venv, run the charm's code" against a real production charm remains unproven at spec writing time. Likely first regression class: Python-version mismatch (charms targeting `requires-python = "~=3.12"` in a 3.11 harness).

### **Out of scope**

- Changes to Scenario's existing single-charm API or behaviour  
- charmcraft `reactive` plugin support

### **Prior art and references**

- [Catan](https://github.com/PietroPasotti/catan) — the abstraction this spec draws from; spike branch `explore/per-charm-dependency-isolation` at commit `1f4c357`  
- [operator\#1929](https://github.com/canonical/operator/issues/1929) — origin of the `ops.testing`\-integrated direction

# Spec History and Changelog

Please be thorough when recording changes and progress with the spec itself and the work resulting from it. Record every meeting, attendees and conclusions from the meeting.

| Author(s) | Status | Date | Comment |
| :---- | :---- | :---- | :---- |
| [Tony Meyer](mailto:tony.meyer@canonical.com) | Drafting | Jun 8, 2026 | Initial draft |
| [Ben Hoyt](mailto:ben.hoyt@canonical.com) | Drafting | Jun 15, 2026 | Initial review, comments |
| [James Garner](mailto:james.garner@canonical.com) | Drafting | Jun 15, 2026 | Initial review, comments |
| [Tony Meyer](mailto:tony.meyer@canonical.com) | Drafting | Jun 24, 2026 | Addressed comments. Added serialisation example section. |
| Person | Braindump | Date |  |
|  |  |  |  |

