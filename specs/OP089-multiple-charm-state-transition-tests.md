# OP089 — Multiple-charm state transition tests

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | Jun 8, 2026 |

## Abstract

This spec defines a multi-charm unit (state-transition) test surface added to `ops.testing`. It provides `deploy`, `integrate`, `add-unit`, `remove-unit`, and `config` as test operations, with the corresponding Juju events triggered automatically as the model converges. Each charm can run in its own isolated subprocess, so charms with incompatible dependency sets can be tested together in a single test. This complements [OP093](https://docs.google.com/document/d/1dd_UK-3bIrFn9LhGyHdNNyI8lgg2l6Vbq4iBVtUWwZs/edit?usp=sharing), where a charm library's testing package provides a stand-in for the remote charm, which Juju deploys like any other: with this spec, the remote can also be the real charm.

## Rationale

#### The gap in current tooling

`ops.testing` (Scenario) runs one charm at a time: the developer writes an event and a `State`, calls `Context.run`, and asserts on the output. With integration tests, using `jubilant`, the tests spin up a full Juju controller (often including a full Canonical Kubernetes) and deploys and integrates real charms. These leave some pain points:

- **Scenario is unlike the `juju` commands charmers think in.** Charmers reason about `juju deploy`, `juju integrate`, `juju add-unit` and so on. Translating that mental model into hand-crafted event sequences and `State`s is friction we can absorb. This has been evident in the success of Jubilant (which itself further strengthens the issue, because charmers are now also used to thinking that way in integration tests too).
- **Integration tests are slow.** A real Juju controller bootstrap and deploy round-trip takes minutes; unit tests should be measured in seconds.
- **Bundle (or solution) and topology assertions are unreachable from unit (state transition) tests.** Asserting "if I deploy A and B and integrate them, A's leader ends up with config X" requires a real Juju or fragile mocks today.

The shape charmers have asked Charm Tech for is 'a multi-charm test tool that feels like Juju but has the speed of unit tests'. This is [Catan's](https://github.com/PietroPasotti/catan) abstraction (Apps, `integrate`, convergence / settle).

Why ops.testing rather than a companion package? This is a non-trivial addition to `ops-scenario`, but not so large that it merits a new `ops-{something}` package, with the packaging overhead that comes from that.

#### Relationship to OP093

OP093 and this spec both answer "what does the other charm do?", with different trade-offs. The two specs have been developed in an overlapping period, and the implementation is expected to overlap as well. The intention is that the two complement each other, with this spec providing the overall multiple-charm testing machinery that OP093 requires, while OP093 provides the basis of the mocking mechanism and provides details of how stand-ins can be used in place of a real remote charm.

With OP093, interface libraries will ship stand-ins to use in place of a real remote charm in multiple-charm state-transition tests. This allows tests to run in a single process and have no dependency on other charms' source code. This is a fit for validating that you're using the interface library correctly, and for setting up relations for tests of things downstream of the relation. This spec defines the machinery that drives these stand-ins in state-transition tests, as well as how real charms can be driven by the same machinery, for testing how two real charms behave together, and making assertions across more than two applications.

A charm library's testing package provides a stand-in for the remote charm, and `deploy()` accepts it in the same place as a charm path or class:

```py
ca = juju.deploy(tls_certificates_testing.provider())
juju.integrate(web, ca)
juju.settle()
```

A stand-in is a `CharmSpec`, returned by the testing package's `provider()` or `requirer()`. It holds a small charm class that observes relation events and answers using the library's own implementation of the other side, along with that class's metadata and the library's `mocked()`. `Juju` runs it like any other in-process charm, so secrets, event ordering, and scaling (with `num_units=`) need no new machinery, and there's only one implementation of firing events (and determining which event to fire).

The stand-in runs in the test process, with the test process's copy of the library, so the charm under test and the stand-in are always on the same library version. When testing with a real remote charm, running in a separate process, the remote charm might be on a different version of the library instead, just like real Juju deployments.

OP093's stand-ins need `Juju`, `deploy()`, `integrate`, and `CharmSpec`, so they land after those. OP093's mocking API doesn't depend on this spec and could land first. Library mocking reuses OP093's `mocked()` (see [*Mocking*](#mocking)).

## Specification

#### Scope of this spec

**Committed API**

* the isolation primitives
* the typed `State` (de)serialiser
* persistent-worker mode
* the single-application operations - `deploy`, `integrate`, `remove_relation`, `add_unit`, `remove_unit`, `config`, and `settle`, with peer and cross-application relation convergence
* secrets shared across units and applications, excluding user secrets, and the other model state Juju shares between units (see [*State shared across units and applications*](#state-shared-across-units-and-applications))
* deploying an in-process charm described by a `CharmSpec` (its class, metadata, and mock), including a charm library's stand-in (see [*Relationship to OP093*](#relationship-to-op093))
* charm-provided mocking and a set of default mocks, applied around each charm's dispatches both in-process and in isolated workers (see [*Mocking*](#mocking))
* isolated environments (`isolated=True`), which the system builds and caches from the charm's declared dependencies, for charms using the `uv` or `python` plugin

**Directional only** (the spec describes these so that the intended trajectory is visible; the APIs shown are sketches and the designs are open)

* alternative settle strategies and scheduling hints (see [*Automatic event triggering and convergence*](#automatic-event-triggering-and-convergence))
* isolated environments for charms using the `poetry` plugin, and the full metadata-resolution coverage
* `Juju.run` for actions: running an action on a single unit is covered by `Unit.to_context()` and `Context.run`. `Juju.run` would only add value where the action's effects need to propagate to other units, such as a peer relation-changed, or a stand-in that revokes what it has issued (OP093 lists this as one way to change a stand-in's behaviour partway through a test)
* stepping through convergence one event at a time: Juju does, essentially, step (each charm is woken for each event), but state transition tests already cover single-event tests, and the `settle()` trace provides each intermediate `State` for assertions
* providing an argument for `settle()` similar to Jubilant's arguments to `wait()` to determine whether to stop after an event completes, as an alternative to stepping through events one at a time
* letting a test switch off one of the default mocks for a charm it deploys, as a separate `deploy()` argument (see [*Mocking*](#mocking))
* user secrets (`add_secret`, `grant_secret`, `update_secret`, and `remove_secret` methods on `Juju`)
* passing `mocked=` to an isolated charm, and changing a charm's mocking arguments between `settle()` calls (see [*Mocking*](#mocking))
* `remove_application`, for testing a charm's clean-up and a remote application going away in one call. The application would leave `Juju.apps` once its units' `remove` hooks have run, as a unit leaves `App.units` after `remove_unit()`
* a clock that `Juju` applies around each dispatch and advances between dispatches, shared with isolated charms, so that charms that depend on time settle deterministically. This is only worth adding if determinism that excludes time causes real problems in tests
* moving the `subprocess` and `filesystem` defaults for machine charms onto `State`, as state transition tests gain filesystem and exec mocking for charms, as `Container` already has for Pebble
* an opt-in flapping check, `settle(check_flapping=True)`, that runs each dispatch of an on-disk charm in a new process with its own hash seed, and reports a value that changes only in order as flapping (see [*Automatic event triggering and convergence*](#automatic-event-triggering-and-convergence))

#### Operation surface

The new names sit directly in `ops.testing`, alongside `Context` and `State`. A subpackage (such as `ops.testing.juju`) was considered, but it wouldn't separate anything: `Unit.state` and every `Dispatch` hold `testing.State`s, and `Juju` builds the `testing.Model` in each one, so a test would import from both anyway. It would also be one more place for names to move out of if they're later folded in. The addition is five new classes (`Juju`, `App`, `Unit`, `Dispatch` and `CharmSpec`), and two new classes in `testing.errors` (`IsolationError` and `JujuError`). In total, this is seven new public names added to the existing 43.

The test API uses Juju CLI style operations (`deploy`, `integrate`, `remove-relation`, `add-unit`, `remove-unit`, `config`) that describe **intent, not events**. The system generates the correct Juju-faithful event sequence and runs it on the affected (mock) units.

Names and signatures follow Jubilant's wherever it has a counterpart, so charmers carry patterns from Juju itself through to this and to Jubilant (both 'unit' and integration tests). The main deviation is that operations take **objects rather than app-name strings**: the objects are already in the test and strings are error-prone.

```py
# In ops.testing:

# Frozen including meta, so one CharmSpec can be deployed many times.
@dataclasses.dataclass(frozen=True)
class CharmSpec(Generic[CharmType]):
    charm_type: type[CharmType]
    meta: Mapping[str, Any]  # charmcraft.yaml shaped, including config & actions.
    mocking: Callable[..., contextlib.AbstractContextManager[None]] | None = None

class Juju:
    def __init__(
        self,
        # With model_name, uuid, and cloud_spec, if None, one is generated, and will be
        # the same on every run.
        model_name: str | None = None,
        *,
        uuid: str | None = None,
        cloud_spec: CloudSpec | None = None,  # cloud_spec.type gives lxd/kubernetes
    ): ...
    @property
    def apps(self) -> Mapping[str, App]: ...  # By name.
    def deploy(
        self, charm: str | pathlib.Path | type[CharmBase] | CharmSpec[CharmBase],
        app: str | None = None,
        *,
        config: Mapping[str, Any] | None = None,
        state_template: State | None = None,
        trust: bool = False,
        num_units: int = 1,
        isolated: bool = False,
        requirements: str | pathlib.Path | None = None,
        mocked: Mapping[str, Any] | None = None,
        juju_version: str = _DEFAULT_JUJU_VERSION,
    ) -> App: ...

    def add_unit(self, app: App) -> Unit: ...
    def remove_unit(self, *app_or_unit: App | Unit, num_units: int = 0) -> None: ...
    def config(self, app: App, config: Mapping[str, Any]) -> None: ...
    def integrate(
        self,
        app1: App | tuple[App, str],
        app2: App | tuple[App, str],
    ) -> None: ...
    def remove_relation(
        self,
        app1: App | tuple[App, str],
        app2: App | tuple[App, str],
    ) -> None: ...
    def settle(self) -> Sequence[Dispatch]:...
    def close(self) -> None: ...
    def __enter__(self) -> Juju: ...
    def __exit__(self, *exc: object) -> None: ...

# All the remaining classes are created by Juju rather than explicitly by tests.
# They are public because the tests use them for assertions after events are run.
class App:
    @property
    def name(self) -> str: ...
    @property
    def meta(self) -> Mapping[str, Any]: ...  # But guaranteed to conform to the Juju metadata format.
    @property
    def config(self) -> Mapping[str, Any]: ...
    @property
    def units(self) -> Mapping[int, Unit]: ...
    @property
    def leader(self) -> Unit: ...  # consistency check ensures this is a member of `units`

class Unit:
    @property
    def state(self) -> State: ...
    @property
    def app(self) -> App: ...
    @property
    def name(self) -> str: ...
    @property
    def id(self) -> int: ...
    @property
    def is_leader(self) -> bool: ...
    @property
    def machine(self) -> str | None: ...  # As `juju status` shows it; None on K8s.
    @property
    def filesystem(self) -> pathlib.Path: ...
    def container_filesystem(self, container: str) -> pathlib.Path: ...
    def to_context(self) -> Context: ...

@dataclasses.dataclass(frozen=True)
class Dispatch:
    event: _Event
    app_name: str  # The application's name.
    unit_id: int
    state_in: State
    state_out: State
    error: str | None
    """The charm's traceback, as a string, if the dispatch failed.

    This will be transmitted over the process boundary when required.
    """

    @property
    def unit_name(self) -> str: ...  # For example, 'web/0'
    def to_context(self) -> Context: ...

# In testing.errors:

class IsolationError(RuntimeError): ...
class JujuError(RuntimeError):
    trace: Sequence[Dispatch] | None
    """Set when settle() raises because a unit is in error."""
```

```py
from ops import testing

juju = testing.Juju()

web = juju.deploy(
    charm="./charms/myapp",
    app="myapp",
    num_units=2,
    config={"log_level": "info"},
)
db = juju.deploy("./charms/mydb")

juju.integrate(web, db)
juju.add_unit(web)
juju.config(web, {"log_level": "debug"})
juju.remove_unit(web.units[1])

juju.settle()

assert db.leader.state...
for unit in web.units:
    assert unit.state...
```

`Juju`, `App` and `Unit` are live handles on the simulated model. A test can't change them directly: their attributes are read-only, and only `Juju`'s operations change the model. Each operation changes the model straight away, as the same command does in a real model, and the events it causes run when the test calls `settle()`. So after `config()` every unit's `State` already has the new values, after `integrate()` the relation exists in the model and each unit has it in its `State` from its `relation-created` onwards, after `add_unit()` the new unit is in `App.units`, and a unit passed to `remove_unit()` stays in `App.units` until its `remove` hook has run.

A unit's `State` is an immutable `testing.State`, replaced rather than modified at each dispatch, so a `State` kept from before `settle()` can be compared with one read afterwards. There are no frozen copies of `Juju`, `App` or `Unit`, because almost nothing about them changes apart from what's in the units' `State`s: a model's identity is fixed and only its applications change, and an application's name and metadata are fixed and only its units change (its config and leader are the ones in each unit's `State`). Anything else about the model that a charm can see belongs in `State` too (on `testing.Model`, for example), so it's captured with the rest. Live handles let a test reuse the objects that `deploy()` and `add_unit()` return across operations, and read the settled state from them. The one mutable part of a `Unit` is its filesystem, which the charm writes to.

`Juju` is a new class. Although the commands it offers would typically be executed on a Juju model, [the `Model` name is already in use](https://canonical.com/juju/docs/ops/latest/reference/ops-testing/#ops.testing.Model). Extending `testing.Model` doesn't work either. It's a frozen dataclass inside every unit's `State`, describing the model as that unit sees it, while `Juju` is a mutable handle that owns the applications, their units and their worker processes. Putting those on `Model` would put the whole simulated model, and its processes, inside every `State`. The name matches `jubilant.Juju` and results in code that strongly resembles the Juju CLI commands that testing against a real Juju would require (for example, `juju integrate db app` and `juju.integrate(db, app)`). It does not follow the convention of naming simulations after the real thing (`Container`, `Relation`, and `Secret` for example), and if we later need to model a controller or cloud, the `Juju` name will fit poorly, but on balance it is the best choice.

##### `Juju` attributes

`Juju.deploy(...)` returns an `App` handle. An `App` owns its charm reference, the charm's metadata (read from disk, or taken from a `CharmSpec`), the environment it runs in (see [*Isolation model*](#isolation-model-subprocess--per-charm-virtual-environment)), and its per-unit `State`s; `App.units` indexes them and `App.leader` is the leader.

`Juju.apps` maps each application's name to its App (populating on `deploy`). A test or fixture can reach any application through it without keeping the handle `deploy()` returned, and a `Dispatch`'s app leads back to the live `App` with `juju.apps[d.app]`. It's read-only: applications are added with `deploy()`.

`mocked=` is passed to the charm's own `mocked()`, or to a `CharmSpec`'s `mocking`, as keyword arguments, so a test can change how that charm's mocks behave without patching anything itself. In the initial implementation it's only for charms that run in the test process, and `deploy()` rejects it when used with `isolated=True` (see [*Mocking*](#mocking)). It has to be JSON-serialisable, so that allowing it for isolated charms later is purely an addition.

`state_template=` is the starting point for every unit's `State`, including units added later with `add_unit`. It's how a test supplies what the system can't know: `Exec` mocks and layers on containers, networks, resources, and so on. The system owns the fields that describe a unit's place in the model (`leader`, `planned_units`, `model`, `config`, `relations`, `secrets`, ...). A template that sets any of those is rejected by `deploy()` with a `JujuError` naming the field. It's a `State` rather than a type of its own so that a test builds it from the same objects that single-charm tests use, and so that anything added to `State` later can be used here without a matching change. For example, relations come from peer endpoints and `integrate`, config comes from `config=`, and secrets come from the charms themselves or from `add_secret` (see [*State shared across units and applications*](#state-shared-across-units-and-applications)).

`trust=` matches `jubilant.Juju.deploy` and `juju deploy --trust`, and sets `app_trusted` on the application's `Context`.

For a charm deployed from a path, the `Context`'s `charm_root` is the charm's source directory, so the charm can find files that it ships alongside its code. The other `Context` arguments are either owned by `Juju` or, like `capture_deferred_events`, add nothing that the `settle()` trace doesn't already provide.

##### `Juju` methods

`Juju.config(app, values)` matches `jubilant.Juju.config` and `juju config`. It works on any application in the model, not only the charm under test: a remote charm deployed from a path (in-process or isolated), a bare class, or a `CharmSpec`. The values are checked against the config options in the application's metadata; an unknown option, or a value of the wrong type, raises `JujuError`. The new config goes into the `State` of every unit of the application immediately, and `settle()` runs `config-changed` on each of them, so anything the charm writes in response reaches related applications. Calling `config()` more than once before `settle()` merges the values, and each unit still gets one `config-changed`, which sees all of them, as in (real) Juju. A `secret` option takes a secret URI, typically from `add_secret`, and the application needs to have been granted that secret (see [*Secrets*](#secrets)).

`Juju.integrate(app1, app2)` matches `jubilant.Juju.integrate` and `juju integrate`. Where only one pair of endpoints can match, the applications are enough. Otherwise either side can be given as an `(App, endpoint)` tuple, which is the object form of Jubilant's `'app:endpoint'` string. `via` is omitted, because there are no cross-model relations. Integrating adds the relation to the model. `settle()` runs `relation-created` on each unit before anything else that's waiting for that unit (straight after `install`, for a unit that hasn't been installed yet), and the relation is in a unit's `State` from then on. A unit enters the relation's scope once its `relation-created` has run, and sees a remote unit join, with `relation-joined` then `relation-changed`, only once both are in scope. A unit whose `relation-created` fails never enters scope.

`Juju.remove_relation(app1, app2)` matches `jubilant.Juju.remove_relation` and `juju remove-relation`, and takes endpoints the same way `integrate` does. `settle()` will run `relation-departed` on each unit for each unit on the other side, then `relation-broken` on every unit, and the relation is removed from each unit's `State` once `relation-broken` has been dispatched there. `force` is omitted, for the same reason as on `remove_unit`. If `remove_relation()` comes before the `settle()` that would run `relation-created`, each unit gets `relation-created` then `relation-broken`, with no joins or departs, because Juju doesn't let a unit enter the scope of a relation that's being removed.

`Juju.add_unit(app)` matches `jubilant.Juju.add_unit` and `juju add-unit`, adding one unit and returning it. The new unit is in `App.units` straight away, and `settle()` runs and its `install` and `start`, and `relation-created` for each relation the application has. Peer relations work the same way as `integrate()`: the new unit gets `relation-created` for each peer relation after `install`, has the relation in its `State` from then on, and joins and is joined by each other unit once both are in scope. `num_units`, `to` and `attach_storage` are omitted: call `add_unit()` again for more units. Each unit on a machine model gets a new machine, and there's no storage to attach.

`Juju.remove_unit(*app_or_unit, num_units=0)` takes objects where Jubilant takes strings. `remove_unit(web, num_units=2)` scales down by count; `remove_unit(web.units[1])` removes a named unit (`Juju` checks the type of cloud to make sure the correct form is used). Removing a unit means `settle()` will run `relation-departed` on every unit related to it, both peers and units of integrated apps. The departing unit gets `relation-departed` and `relation-broken` for each of its relations, then `stop` and `remove`. `force` and `destroy_storage` are omitted: there is no stuck agent to override, and storage-on-removal can be added later if that is needed.

`Unit.to_context()` provides a `testing.Context` built from the data in the `Unit` and linked `App` objects. This can be used to simulate running an action at a specific point, or to continue with a single-charm test. Note that this is a new `Context` on every call (meaning collections like the Juju logs will always be empty), it doesn't feed back into the `Juju` object when it is used, and this doesn't come with any mocking not normally present in a new `Context`. It uses the unit's current `State`; for the unit as it was at an earlier point, use `Dispatch.to_context()` (see [*Automatic event triggering and convergence*](#automatic-event-triggering-and-convergence)).

In terms of isolation, the worker builds the context, so `to_context()` (on a `Unit` or a `Dispatch`) has to import the charm into the test process. If this fails, then an `IsolationError` is raised. The expectation is that this would typically be used for the *local* charm rather than the remote ones.

#### State shared across units and applications

Each unit's `State` is that unit's view of the model, but some of what is in it is shared: Juju holds one copy and every unit that can see it sees the same thing. `Juju` keeps the single authoritative copy of everything shared, writes the relevant view of it into a unit's `State` before each dispatch, and folds the unit's changes back in afterwards, calculating the events Juju would fire on other units. A test never has to keep two `State`s in sync by hand.

Relation data is the obvious case, and is covered by `integrate` above. The others are:

* **Juju-written relation data.** Juju itself writes `ingress-address`, `egress-subnets`, and `private-address` into each unit's databag, and the remote units read them. `Juju` fills them in with addresses derived from the unit and model names, consistent with the unit's `networks` and with the hostname default mock (see [*Mocking*](#mocking)), so they're deterministic and agree with each other.
* **Application status.** The leader sets it, and it belongs to the application rather than the unit, so when leadership moves (for example, after `remove_unit` removes the leader), the new leader's `State` has the status the previous leader set.
* **Model identity, config, and [planned units](https://canonical.com/juju/docs/ops/latest/reference/ops/#ops.Application.planned_units).** These are already owned by `Juju` (see `state_template=` above), and are the same in every unit's `State` for an application.
* **Secrets** (see below).

##### Secrets

Secrets are handled across units and applications in the same way as relation data, whether the charm under test or the remote charm owns them:

* **Charm-owned secrets.** A secret the leader creates with `app.add_secret` is owned by the application, and appears in the `State` of every unit of that application. A secret created with `unit.add_secret` appears only in that unit's `State`.
* **Grants.** `secret.grant(relation)` (optionally for one unit) makes the secret visible to the remote application's units, and it appears in their `State`s as a secret they observe rather than own. Revoking the grant, or removing the relation, takes it away again. A secret URI written into relation data by one application resolves in the other, as it does in Juju.
* **Revisions and events.** When the owner adds a revision, `settle()` will run `secret-changed` on every observer unit that is tracking an older revision. When no observer is tracking a revision any more, `settle()` will run `secret-remove` on the owner. `secret-rotate` and `secret-expired` depend on the clock, so `settle()` never fires them; a test that needs them uses `Unit.to_context()`.
* **Deterministic IDs.** `Juju` allocates every secret ID, for charm-owned and user secrets alike, so the same test produces the same IDs on every run, as the determinism requirement on `settle()` needs.
* **User secrets** *(directional only for this spec)***.** `add_secret`, `grant_secret`, `update_secret`, and `remove_secret` match the Jubilant methods of the same names (and `juju add-secret`, and so on). A user secret is visible only to the applications it has been granted to, and is usually passed to a charm through a `secret` config option. After `update_secret`, `settle()` runs `secret-changed` on the units tracking the secret, and `remove_secret` removes it from every unit's `State`.

An isolated charm gets its secrets in the serialised `State`, like the rest of its view of the model. `Juju` writes them in before each dispatch and reads changes back afterwards, so the worker never has to ask the parent process for one partway through a dispatch.

#### Charm source: local paths and charm specs in v1

`charm=` can be a `CharmSpec`, for a charm that runs in the test process: a charm class defined in the test, or a charm library's stand-in (see [*Relationship to OP093*](#relationship-to-op093)). `Juju` takes the charm class from `charm_type`, and the metadata, config options and actions from `meta`, rather than reading them from disk, and opens `mocking` around each of the application's dispatches. If `app=` isn't given, the application name is `meta["name"]`, as it is for a charm on disk. A `CharmSpec` can't be isolated, so `deploy()` rejects `isolated=` and `requirements=` for one.

A bare charm class is shorthand for a `CharmSpec` with no mocking, whose metadata is loaded from the files beside the class's source, as `Context(MyCharm)` does. For a class defined in a test file there's usually nothing to load, so `deploy()` raises a `JujuError` saying to wrap the class in a `CharmSpec` with explicit `meta`.

The recommendation for charms defined outside your repository is that the test infrastructure (typically a `conftest.py` fixture) should source the charm from somewhere (`git clone` is the obvious choice, if it's not within the same repository) and pass the resulting local path to `deploy(charm=...)`. This keeps the surface small and puts the "where does this charm come from" decision in the test author's hands, where it can be tailored to CI, caching, and gitignore rules per project.

**Not in v1, or defined directionally:**

* Deploying from git (with or without patches, as Catan supports) is out of scope for v1 and possibly ever. The complexity is high and the value versus a conftest-managed clone is low.
* Deploy from Charmhub: this is feasible (download, unzip, treat the unpacked source as a local path), but is not part of v1. If added later, the same `charm=` argument would grow a Charmhub-URL form. If the charm needs mocking, this becomes more complicated, as the mocking won't be shipped on Charmhub, so this form may need both a Charmhub source and a pointer to a source tree that defines mocking configuration, in which case it might as well just be deploying from git.

#### Automatic event triggering and convergence

For each operation, `Juju` calculates the appropriate state change on the affected units. When `settle` is called: it picks an event, dispatches it through that unit's `Context.run(...)`, observes any new relation-data writes, status changes, or secret operations, and adjusts the state of peers and related units. Convergence terminates when there are no more events to generate based on the states. This might be implemented as an event queue (without any test code having access to the queue) and a convergence loop, or in other ways. The spec does not prescribe a specific implementation, and the implementation could change over time without user-facing changes (to support more settle algorithms, for example).

```py
juju.settle()   # explicit convergence point
assert web.leader.state.unit_status == ActiveStatus("ready")
```

Catan shows that this can be done with suitable fidelity to Juju without *actually reimplementing Juju*. We are able to take advantage of the non-specific ordering of some Juju events, as well as reading the Juju code to understand its behaviour.

Settling is explicit: reading a unit's `State` does not run any events. Settling implicitly on read would be convenient, but that settles far more often than wanted when a test just wants to check a value. `settle()` takes the place of Jubilant's `wait`, since there is no real controller to wait on. Most tests are a sequence of operations, a `settle()`, and then assertions on `app.leader.state` or `app.units.state`. The `State` exposed on each unit is the same `testing.State` dataclass that single-charm state transition tests use today, so all the existing assertions work unchanged.

If the model hasn't converged within an internal limit, `settle()` raises `JujuError` with the tail of the trace, so a pair of charms that never converge fails the test instead of hanging it. The limit scales with the number of units in the model and isn't a public setting. Because dispatch is deterministic, the same event reaching the same unit with the same input `State` a second time is an infinite loop, and it's reported as soon as it happens rather than when the limit runs out.

If a charm raises during a dispatch, `settle()` handles it as Juju handles a failed hook. The dispatch's changes are discarded, the unit's status becomes `ErrorStatus('hook failed: "<event>"')`, and the unit gets no more events, while the rest of the model carries on. There's no automatic retry. A unit in error doesn't stop the model converging: `settle()` finishes when no other unit has events left to run, and then raises `JujuError`, naming each unit in error and the event it failed in. The error isn't chained to the charm's exception, because an isolated charm's exception is in another process. Instead, the error's trace is the sequence of `Dispatch`es that `settle()` would have returned, and the dispatches that failed have the charm's traceback in `error`. The model is left as it was, so a test that expects the failure catches the error and asserts on the unit's status:

```py
with pytest.raises(testing.errors.JujuError):
    juju.settle()
assert isinstance(app.leader.state.unit_status, testing.ErrorStatus)
```

So if `settle()` returns, no unit is in error, and a test doesn't need to assert that.

For tests that need to assert on an intermediate state, `settle()` returns the deterministic sequence of `Dispatch` objects it dispatched. Each one is a record of one event as it happened: the event, the unit it went to (by application name and unit ID), the `State` the unit was given, and the `State` it produced. `state_in` is the state after `Juju` wrote in the shared changes from other units (see [*State shared across units and applications*](#state-shared-across-units-and-applications)), so it's what the charm actually saw, rather than the previous dispatch's `state_out`. A `Dispatch` holds no live handles, so it still describes the unit as it was at that dispatch after later operations and dispatches have changed things, and `Dispatch`es compare by value. The model's name, UUID and cloud are in the state, as `state_in.model`. The model is available through the state, for example in [`state_in.model`](https://canonical.com/juju/docs/ops/latest/reference/ops-testing/#ops.testing.State.model).

```py
trace = juju.settle()
assert [d.event.name for d in trace] == ['install', 'config-changed', 'start']

waiting = next(
    d for d in trace if isinstance(d.state_out.unit_status, testing.WaitingStatus)
)
ctx = waiting.to_context()
state_out = ctx.run(waiting.event, waiting.state_in)
```

`Dispatch.to_context()` builds a `testing.Context` for the unit as it was at that dispatch: the charm and metadata the test gave `deploy()`, the application's trust and the unit ID, with config and leadership coming from `state_in`. Running `d.event` against `d.state_in` in that context runs the dispatch again from the same starting point, without `Juju`'s mocking, so a test can pick up from any point in the history. It behaves like `Unit.to_context()`: a new `Context` on every call, with no mocking beyond what a new `Context` has, and for an isolated charm it imports the charm into the test process, raising `IsolationError` if that fails. The charm source and metadata never change, so `Dispatch` keeps a private reference to them rather than to the `App`.

The trace has no history of the per-unit filesystem (see [*Mocking*](#mocking)): `Unit.filesystem` is the root as it is now. A per-dispatch filesystem record can be added later if there's a need.

There's no way to act partway through convergence. A test that needs to change something between two specific events is a single-charm test, which `Context` already handles, and `Dispatch.to_context()` gives it the starting point.

Given the same starting `Model`, the same input event sequence, and deterministic charms, `settle()` **must** produce equal final `State`s for every unit, and an equal sequence of `Dispatch`es, on every run and on every machine. Tests assert on these values, and loop detection relies on them. No wall-clock dependence, no PID-derived ordering, and no ordering that comes from a set is permitted in the policy. This relies on the charms being deterministic as well. We guarantee the order of event dispatch, but if a charm behaves differently (for example, it creates different relation data based on the date and time, or reads a host file that the default mocks don't cover), then the final `State` will differ as a result.

Hash-order differences are a special case of this that `settle()` doesn't catch. Each hook in Juju is a new process with its own string-hash seed, so a charm that writes a set of strings to a databag without sorting it writes a different order in each hook, and two charms reacting to each other's writes never settle ("flapping"). Under `settle()`, the test process and each worker keep one seed for the whole test, so the order doesn't change and the charms appear to converge.

Time is the main way this happens. `Juju` doesn't fake the clock in v1, so a charm that puts the current time into what it writes (a certificate's validity period, a timestamp in relation data, ...) gets a different `State` on every run. A test of such a charm compares the parts that don't depend on time. If the charm under test runs in the test process, its own `mocked()` can also fix its clock. That only changes the time that charm sees, because each charm's mocking only applies to its own dispatches.

The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is decided against this requirement, when there is working code to validate it (see [*Further Information*](#settle-policy-considerations)).

Real Juju runs charms concurrently and per-unit event ordering is non-deterministic. Unit tests should be deterministic, so a single ordering policy ships, but the design keeps the door open for exercising alternative orderings against the *same* starting sequence of events. Three mechanisms are anticipated, none of them committed:

* Alternative strategies via `settle(...)` arguments: for example, `juju.settle(strategy='data-flow')` versus `strategy='round-robin'` versus a caller-supplied deterministic function. Running the same test under two strategies is one way to smoke out charms that accidentally depend on one particular ordering.
* Per-app / per-unit scheduling hints. For example, mark an `App` as "running late" so its events are held until no other events are left to run, or bias one unit to run first. This lets charmers reproduce specific ordering bugs seen in production.
* An exhaustive run of all combinations that Juju could emit (as a [hypothesis](https://hypothesis.readthedocs.io/en/latest/) style test), perhaps with a smart search strategy to find "sad" paths.

All of them are optional layers on top of the default deterministic policy; the default remains what `settle()` with no arguments does. An exhaustive search isn't the default because the number of orderings grows quickly with units and operations, so the cost of a test would be hard to predict, and a failure would be one ordering among many rather than a single trace to read. A test can opt in where the extra cost is worth it.

#### Isolation model: subprocess + per-charm virtual environment

Each isolated `App` runs in its own process, using the interpreter from a virtual environment that the system builds for it (see [*Environment provisioning*](#environment-provisioning) below). For each event dispatch `Juju` serialises `(meta, config, actions, event, State)` as JSON, sends it to the charm's worker process, the worker runs `testing.Context(...).run(...)`, and serialises the resulting `State` back. Two `App`s in the same `Model` may use mutually incompatible dependency sets (`cryptography==41` vs `==3`, different `pydantic` majors, conflicting charm-lib versions, ...).

**Required invariant:** every per-charm virtual environment carries the same `ops.testing` (and therefore `ops`) version as the parent process. Only the charm's own runtime dependencies differ between virtual environments.

Versions are required to match rather than negotiated. Negotiating them would make the JSON `State` representation public API and commit us to a cross-version compatibility guarantee. `Juju` builds each environment itself, so it doesn't install `ops` or `ops-scenario` there at all: the worker imports the test process's own copies, ahead of the environment's packages, and the environment gets only their dependencies. The versions match by construction, including for a development install, and the charm's own `ops` requirement is left out.

The encoded payload carries the `ops.testing` version and the decoder asserts it matches, failing with both versions named. Since the system builds the environments, a mismatch means a stale environment or a bug rather than a user mistake, so the check is a guard rather than a user-facing error.

The isolation worker is persistent: one long-lived process per `App`, spawned lazily on first dispatch and torn down when the `Juju` is closed (with `Juju.close()`, or by leaving a `with testing.Juju() as juju:` block). A framed JSON protocol over stdin or stdout carries requests and responses. Worker crashes propagate as a typed `IsolationError` and fail the test cleanly; `Juju` never silently re-spawns mid-test.

Acceptance criteria:

**Workload:** the performance yardstick is a **4-charm bundle with 20 events per `settle()`** (80 dispatches total). Lives in the test suite and is re-run by every later step to catch regressions.

**Bar:** two absolute budgets, regression tested independently rather than blended into one ratio:

- **Worker startup: <= 400ms per worker.** Covers interpreter start + `import ops` + `import scenario.Context`.
- **Steady-state: <= 2ms/event**, measured on a warm worker at the benchmark fixture's payload size (JSON encode/decode + IPC, no spawn).

They are separate because the two costs amortise differently: spawn is paid once per environment, per-dispatch cost scales with the number of events. Where a single number suits a CI gate better, <= 30ms/20-event has the same budget.

**Benchmark shape:** a benchmark suite measuring (a) in-process Scenario baseline, (b) spawn-per-event isolated, and (c) persistent-worker isolated, all on the same 4-charm/20-event workload.

Measured absolute numbers, three independent machines (Python 3.11.15, median of 5 repetitions):

| Machine | Baseline | Persistent worker | vs baseline | Spawn per event |
| :---- | :---- | :---- | :---- | :---- |
| Original dev box | 4.2 ms/event | 20.9 ms/event | 5.0x | 286.8 ms/event (69x) |
| 2026-07-25 refresh | 4.5 ms/event | 21.5 ms/event | 4.8x | 317.2 ms/event (70x) |
| 2026-07-30 cloud container | 5.3 ms/event | 22.9 ms/event | 4.3x | 309.4 ms/event (59x) |

The absolute persistent-worker number (20.9-22.9 ms/event) is far more stable across hardware than the ratio (4.3-5.0x). The ratio moves because baseline speed varies with the machine, not because persistent worker mode does.

Of the gap, \~95-99% is one-time worker spawn: interpreter start and `import ops`, paid once per worker, which is once per isolated application in each `Juju`, and structurally the price of a process boundary; and \~1-5% is per-event JSON/IPC overhead, which scales roughly linearly with `State` size while staying a minority of the cost (measured up to \~334KB).

Persistent worker mode is \~13-15 times faster than spawning per event on all machines measured.

### Environment provisioning

A charm runs in one of two ways:

#### In-process

The default. No isolation, no virtual environment work, and no external tools. Inline charm classes and charms on disk both run in the same interpreter as the test. This covers locally defined test charms and monorepos where the dependencies are known to be compatible. Charms deployed this way share one set of imported modules, so if two of them vendor the same charm library at different versions, whichever is imported first is used by both. That case needs isolation.

#### Isolated

This is the `Juju.deploy(..., isolated=True)` form. Juju detects the charm's build plugin, extracts its dependency list, builds a cached virtual environment from it with a matching `ops.testing` (see [*Isolation model*](#isolation-model-subprocess--per-charm-virtual-environment)), and runs the charm in a worker process using that environment's interpreter.

Plugin detection is from `charmcraft.yaml`. Extraction per plugin:

| Plugin | Extraction method |
| :---- | :---- |
| charm | *Not supported (an error will be raised).* |
| python | reads `python-requirements` / `python-packages` + `PYDEPS` |
| uv | shells to `uv export --locked --no-default-groups --no-emit-project --no-hashes --format requirements-txt` with forwarded `--extra` / `--group` flags |
| poetry (directional only) | shells to `poetry export --without-hashes --format requirements.txt` with forwarded `--with` flags |

All forms normalise to a flat pip specifier list, which is installed with `uv pip install` into the charm's virtual environment. The environment is cached on disk, keyed by a SHA-256 of the plugin, the extracted requirements, the lockfile or `pyproject.toml` content, the interpreter version, and the `ops.testing` version. For the `uv` plugin, the lockfile, `pyproject.toml`, and the forwarded extras and groups decide the requirements, so they're the key in place of the exported list, and a cache hit doesn't run `uv export`. A cold build for a test charm was measured at \~3s, and a warm cache hit at <0.05s. `deploy()` raises a typed error when a requirement can't be resolved, when a lockfile is stale relative to `pyproject.toml`, or when `uv` is missing. When detection or extraction is what failed, the error suggests `requirements=`.

##### When detection fails

`requirements=` takes the path to a requirements file, as a `str` or a `pathlib.Path`, in the format that `uv pip install -r` accepts. That's also what `uv export` and `poetry export` produce. A relative path is relative to the working directory, as it is for `charm=`, and so are any relative paths inside the file. The file replaces detection and extraction completely, so it has to list everything the charm needs, including its mocking's testing packages and dependency groups. An `ops` or `ops-scenario` line in it does no harm, because the worker imports the test process's copies first (see [Isolation model](#isolation-model-subprocess--per-charm-virtual-environment)). This covers charms with an unusual build, plugins that aren't supported yet, and test infrastructure that already exports a lockfile. `deploy()` rejects `requirements=` without `isolated=True`.

##### Tool dependency

Isolation needs `uv` on `PATH`, and the `poetry` plugin also needs `poetry` and `poetry-plugin-export`. In-process charms depend on nothing beyond the Python standard library.

### Mocking

Charms under test often need parts of their environment mocked: a Kubernetes client built in `__init__`, a subprocess call, or a charm library's own internals. Most charms already do this for their own unit tests. With `Juju`, each charm provides its own mocking, and `Juju` applies it around that charm's dispatches, inside a set of defaults (see *Default mocks*).

#### Each charm's own mocking

Charms provide a function, `mocked()`, that returns a context manager, by default in `tests/unit/mocking.py` (see *Configuration* below in this section). It has the same shape as OP093's `mocked()`: re-entrant, with every argument keyword-only and optional. The charms must declare the arguments rather than taking `**kwargs`, so a misspelt or removed keyword is a `TypeError` that explicitly shows the problem.

```py
# tests/unit/mocking.py (in the charm under test)
@contextlib.contextmanager
def mocked(*, sealed: bool = False):
    with unittest.mock.patch("vault.Vault.is_sealed", return_value=sealed):
        yield
```

Most existing unit-test patches set per-test behaviour (a return value, a failure), so the test needs a way to vary it. It does that with plain data:

```py
# in the 'local' charm
vault = juju.deploy(CHARM_ROOT, "vault", mocked={"sealed": True})
```

In v1, `mocked=` is for charms that run in the test process, which is usually the charm under test. An isolated charm's worker still opens the charm's own `mocked()` around each of its dispatches, with no arguments, and `deploy()` rejects `mocked=` if used with `isolated=True`.

Passing arguments to an isolated charm is planned for after v1. Some remote charms publish a decision made outside the charm: Vault refusing a CSR, an ACME server failing, Notary's status for a request, the result of a Keystone API call, and so on. A requirer testing how it handles those against the real charm needs to vary that charm's mocking, and that charm is usually isolated. The intended shape is the same `mocked=` dict, sent to the worker, which calls `mocked()` in the charm's own environment and reports an unknown keyword as an error naming the charm and the keyword. This does make the remote charm's `mocked()` signature something other repositories' tests depend on, at whatever revision they pin. The most useful of these tests also change the condition partway through (the CA recovers, or the request is signed later), which a deploy-time argument can't express, so this is likely to come with a way to change a charm's mocking arguments between `settle()` calls.

A `CharmSpec` brings its mock with it, as `mocking`, so `Juju` doesn't look for a `pyproject.toml` or a mocking file. The charm is already in the test process, so `Juju` calls mocking directly, with `mocked=` as keyword arguments.

The charm's own unit tests can use the same module, so there's one source for both:

```py
# tests/unit/conftest.py
@pytest.fixture(autouse=True)
def mocked():
    with mocking.mocked():
        yield
```

This provides an incentive to write one: a charm that mocks itself for its own tests gets the same behaviour whenever another charm's tests deploy it.

#### Scope

The scopes open only around that charm's dispatches, so one charm's patches don't reach another, even in-process. Each application gets its own copy of the mocking module, imported under a generated per-application name. That means a fake state kept at module level persists across the application's dispatches, but two applications of the same charm don't share it. State that has to last across dispatches belongs at module level, not inside `mocked()`, which is entered again for every dispatch, and it has to be deterministic. A `CharmSpec`'s `mocking` is a function the test already holds, so it can't be copied: two applications deployed from `CharmSpec`s with the same `mocking` share whatever it keeps. So a `CharmSpec`'s `mocking`, like a library's `mocked()`, must behave the same however its scopes are opened, deriving anything it hands out from what it is working on rather than from how often it has been called (see OP093's *Mocking scope and stateful mocks*).

#### Default mocks

`settle()` must be deterministic across machines, and anything a charm reads from the host (snapd, the hostname, the environment, ...) ends up in its `State`. So `Juju` applies a set of defaults to every charm, outside the charm's own mocking. Where the two overlap, the charm's patches are the inner ones and win.

| Name | Default |
| :---- | :---- |
| charmlibs | The `mocked()` of each library's testing package, for every library the charm imports (OP093). The imports are read from the charm's `src/` and `lib/` (or, for a charm class, its module) and matched to the libraries that testing packages register (see [*How testing packages register*](#how-testing-packages-are-discovered)). A library imported only through another library isn't found. Testing packages added later, such as the proposed `charmlibs-snap`, `charmlibs-apt`, and `pathops` ones, are picked up the same way. |
| lightkube | Intercepted where the client is defined, so every import spelling is caught. Construction succeeds without a kubeconfig, `list` returns nothing, `get` raises a 404, and writes succeed. Without `trust=True` every request is refused with a 403, as Kubernetes refuses an untrusted application in Juju. |
| k8s-patch-libs | A fixed list of patch libraries (`KubernetesServicePatch`, `KubernetesComputeResourcesPatch`, the StatefulSet patch, and `ResourcePatcher`, at their `v0` and `v1` locations) become no-ops, with `is_ready` true. They're vendored `charms.*` libraries, so the `charmlibs` default doesn't reach them. |
| subprocess | Every command succeeds, with return code 0 and empty output, including through `Popen` and `os.system`. Nothing is recorded. This covers `systemd`, which only checks return codes. Empty output is wrong for any command whose output the charm uses, and often silently so, so a charm that uses a command's output fakes that command in its own `mocked()`, or relies on a testing package for the library that runs it. The `apt` library, which parses `dpkg` and `apt-cache` output, is one example, until a testing package for it exists. |
| hostname | `getfqdn`, `gethostname`, and `gethostbyname` return what the unit would see in Juju. On Kubernetes, the FQDN is `<app>-<n>.<app>-endpoints.<model>.svc.cluster.local`, the pod's name under the application's headless service. On machines, each unit has its own machine, and the FQDN is `juju-<end of model UUID>-<machine>.lxd`. |
| env | The environment has only what Juju would set. |
| network | Outbound TCP/IP connections, loopback included, raise an error naming the host and port. Unix sockets are left alone. This is the only default that raises. |
| filesystem | See below |

##### Filesystem

A charm that writes to `/etc/nginx/ssl` in a unit test writes to the test machine. The filesystem default translates paths into a per-unit root, at the Python level, over `open`, `os` and `shutil` (which covers `pathlib` and `pathops`). A chroot needs root, and unprivileged user namespaces are restricted by AppArmor. `subprocess` is already faked, so Python file access is what matters. C extensions that do their own I/O aren't covered.

* Writes land under the unit's root (`/etc/nginx/ssl/x` becomes `<root>/etc/nginx/ssl/x`). The exceptions are an allowlist that passes through: the unit's charm directory, the Python installation or virtual environment, and the framework's own temporary directories.
* During dispatches, `tempfile.tempdir` points inside the unit's root. Literal `/tmp/...` paths are redirected like any other write.
* Reads check the unit's root first, then the host. `/etc/os-release` is seeded from the charm's base in `charmcraft.yaml`, but other reads that fall through to the host aren't deterministic.
* Each unit gets its own copy of the charm source as its charm directory, as each unit does in Juju, so a charm can't write into the source tree.

The root persists across the unit's dispatches for the rest of the test, but it isn't part of `State`. `Unit.filesystem` returns it as a `Path`, like `Container.get_filesystem()`, so a test of a machine charm whose only effect is on the host can still assert on what it wrote.

Each workload container of each unit has a filesystem of its own, too, which persists across the unit's dispatches for the rest of the test, as it does in a pod, rather than being emptied before every dispatch as it is for `Context`. Storage that the charm's metadata mounts into a container appears at that location, and so does any `Mount` in `state_template`. `Unit.container_filesystem(name)` returns a container's root as a `Path`, for asserting on what the charm pushed: `unit.container_filesystem('grafana') / 'etc/grafana/grafana.ini'`. This isn't a default that can be switched off: it's how `Juju` runs a Kubernetes charm.

#### Configuration

A charm configures its mocking in `pyproject.toml`. Every key is optional:

```
[tool.ops.testing.mocking]
path = "tests/unit/mocking.py"  # The default.
function = "mocked"             # The default, matching OP093.
dependency-groups = ["unit"]    # Default: none.
disable = ["network", "hostname"]  # Default: none.
```

* `path` is loaded by file path under a generated per-application module name, not imported as `tests.unit.mocking`. That's what gives each application its own copy, and lets two in-process charms both have one. So the file can import from the charm's `src/` and from installed packages, but not from elsewhere in the charm's tests (such as `tests.unit.helpers`), and the import error says why. `conftest.py` can't be the target, because it holds fixtures rather than an importable function.
* A charm that ships its mocking in an installed package uses `module = "vault.testing.mocks"` instead of `path`, and it's imported by name.
* `dependency-groups` names what the mocking needs beyond the charm's runtime dependencies (see *Where the dependencies come from*). Many existing fixtures use `pytest-mock`.

A charm with no `pyproject.toml`, or no mocking file at the default path, gets the defaults and nothing else. A `CharmSpec` has no `pyproject.toml`, so it gets every default, with its own `mocking` inside them.

##### Opt-outs

A charm switches off defaults by name with `disable`, or uses `disable = "all"` to keep only its own mocking. Most overlaps don't need this, because the charm's patches win. `disable` is for a default that breaks the charm's own fake, such as a fake server on loopback (`network`), or a C extension that the filesystem shim confuses (`filesystem`).

A test switches off part of an in-process charm's own mocking through `mocked=`, if the charm has a keyword for it. For example, a charm whose `mocked()` takes `real_kubectl` can be deployed with `mocked={"real_kubectl": True}`. A test can't switch off a default in v1.

#### Where the dependencies come from

Testing packages and dependency groups aren't runtime dependencies, so a charm's environment doesn't have them automatically. For an isolated charm, `Juju` installs the charm's `dependency-groups` into the environment it builds, which is where a charm lists the testing packages for the `charmlibs` libraries it uses. With `requirements=`, the file has to include them, since extraction is skipped. For an in-process charm they're whatever the test's environment has, so the mocking module's imports have to resolve there. Missing pieces are errors:

* A mocking file missing from the default path isn't an error, because most charms don't have one. One that's configured explicitly but missing, or that fails to import, is an error from `deploy()` naming the charm and the file.
* A `charmlibs` testing package that's installed but not at its library's exact version is an error naming the package and the version. A library with no testing package installed runs without its mocking, since most libraries don't publish one yet.
* A missing `dependency-groups entry` is treated the same way.

#### Load order

Before importing the charm, the worker (or `Juju`, in-process) loads the charm's mocking module and applies the defaults. It then opens the charm's `mocked()` around each dispatch. That's what makes patches to things the charm builds in `__init__` (a lightkube client, a `SnapCache`), and import-time replacements (`sys.modules[...] = MagicMock()`), work from the first dispatch. For a `CharmSpec`, the test has already imported the charm class, so only the first of those holds: patches to what the charm builds in `__init__` work, but import-time replacements made by mocking come too late.

#### Assertions

A multi-charm test asserts on `State`, and on what `Juju` exposes (such as `Unit.filesystem`), not on mocks. How a remote charm uses its own mocks is that charm's implementation, and its own `Context` tests cover that. No mock or call records come back from a worker, and `Dispatch` doesn't carry any.

#### Unit-test patterns that don't carry over

* `ctx(...)` manager access and `harness.charm.x = Mock()` aren't available, because `Juju` has no handle on the charm object. Single-charm tests use `Context`.
* Patches made in the test still reach an in-process charm, but they're unsupported: a test that relies on one breaks when the charm is deployed with `isolated=True`. Behaviour goes through `mocked=` instead. The framework can't detect this, so it's a documentation rule.
* Error injection through ops internals (`Model.get_secret` raising, `Container.restart` failing, a missing binary) goes in the charm's own `mocked()`. That runs in the charm's process, so the injection works in every layer, but in v1 a test can only turn it on for an in-process charm: `mocked={"secret_unreadable": True}`. First-class failure injection in `State` is out of scope.
* Import-time tricks work, because of the load order above.

#### How testing packages are discovered

Each testing package registers its library's `mocked` in the `ops.testing.mocking` entry-point group, named for the library's import package, and OP093 requires it. For example, in the testing package's `pyproject.toml`:

```
[project.entry-points."ops.testing.mocking"]
"charmlibs.interfaces.tls_certificates" = "charmlibs.interfaces.tls_certificates_testing:mocked"
```

The entry point is how a testing package says that it is one, which library it mocks (the name), and where that library's `mocked()` is (the value). The charm must list the testing package in its testing dependencies for the testing package to be installed; nothing is installed on the charm's behalf, for an in-process or an isolated charm. `Juju` reads the entry points installed in the charm's environment (the test's environment for an in-process charm, the worker's for an isolated one) and matches their names against the libraries the charm imports. The imports are the `import` and `from ... import` statements in the charm's source, read without running it, including those inside functions. Nothing is followed from there: a library the charm imports only through another library, or with `importlib`, isn't found. Imports are used rather than the installed distributions because an environment usually has libraries the charm doesn't use, such as the test's own dependencies, and a library the charm doesn't use should be neither mocked nor version-checked. A testing package is only applied for a library the charm imports. If two installed packages register the same library, `Juju` raises `JujuError` naming both, rather than picking one.

This works for any library, not only those in `charmlibs`, and lets a library outside it opt in to the default. For an isolated charm, the lookup happens in the charm's own environment, so it finds the testing packages installed there.

#### Known limit

Each application has its own copy of its mocking, whether it runs in-process or isolated, so two charms that both fake the same external service get two independent fakes. One charm creating a Kubernetes resource that the other then reads won't work. A fake shared between charms would have to live in the parent process and be reached over the IPC channel, which is a much bigger piece of work, and isn't planned.

### Metadata resolution

The `metadata.yaml` / `charmcraft.yaml` files are read from the charm source path without importing the charm in the test process. Less common cases are left as future work:

- Resolve unified-vs-legacy metadata variants and the merged `charmcraft.yaml` + `metadata.yaml` form charms commonly produce
- Resolve charm libraries the charm declares but that live elsewhere on disk
- Inline charm classes (charm classes defined in the test): kept as in-process, same-environment only, with their metadata given in a `CharmSpec`; isolation requires charms on disk, passed as a path to `deploy()` with `isolated=True`. See *Further Information*.

At least one passing test for each of these charm shapes will be included in the implementation:

1. Unified `charmcraft.yaml` only (no `metadata.yaml`): the current default-modern shape.
2. Legacy split: `metadata.yaml` + `actions.yaml` + `config.yaml`: older charms still in production.
3. Mixed / transitional: `charmcraft.yaml` + `metadata.yaml` (the form charmcraft merges): charms mid-migration.
4. Multi-bases (`bases:` / `platforms:` variants per supported platform).
5. Charm with libs outside `src/` (e.g. installed via `pip` from PyPI for testing): this exercises the "where did this lib come from" resolution.
6. Inline `from_type` (no metadata file; class declares everything): documented as `inline: ok` per the docstring convention in *Further Information*.
7. Bare charm class: one with metadata files beside its source, which loads them, and one without, which fails with the error suggesting `CharmSpec`.

## Further Information

### State (de)serialisation

A typed schema-aware encoder/decoder pair (not `json.dumps(dataclasses.asdict(state))`) covers all `ops.testing.State` leaf types:

| Type | Encoding |
| :---- | :---- |
| `frozenset` (on `relations`, `containers`, `secrets`, etc.) | list on encode; re-frozen on decode (dataclass `__post_init__`s re-freeze) |
| `datetime` / `timedelta` | ISO-8601 string / fractional seconds |
| `pathlib.Path` / `PurePosixPath` | string with type tag |
| Pebble enums (`ServiceStatus`, `NoticeType`, `SecretRotate`, ...) | enum name |
| `pebble.Layer` (`Container.layers`) | `to_dict()` / `Layer(dict)` round-trip (not a dataclass; `asdict` won't descend) |
| Int-keyed dicts (`Secret.remote_grants: Mapping[int, set[str]]`) | keys stringified on encode; restored to `int`, inner `set` restored on decode |

`StoredState.content` and `Container._base_plan` are `Mapping[str, Any]` of marshallable types, a superset of JSON: `bytes`, `tuple`-vs-`list` distinction, and arbitrary `set`s. The spec commits to:

1. **A typed escape hatch, always applied**: tag-and-encode `bytes` as base64 and `tuple` as a `["__tuple__", ...]` envelope so they round-trip losslessly. An opt-in mode would create a "passed locally because today's stored-state had no `bytes`, failed in CI when it did" failure mode; a few extra bytes per typed value doesn't justify it.
2. **Loud error on unrecognised types**: the encoder raises `TypeError` with the type name and the path through `State`. The decoder mirrors: unknown `__type__` tags raise `TypeError`. There is never silent lossy coercion.

The JSON `State` representation is not public API. Both sides of the process boundary run the same `ops.testing` version (see [*Isolation model*](#isolation-model-subprocess--per-charm-virtual-environment)), so the encoded form is internal and may change between releases. The payload embeds the producing version and the decoder asserts it matches its own.

#### Serialisation examples

##### Container with a Pebble layer, notices, check infos, service statuses, and mounts

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

##### Secrets with `int`-keyed `remote_grants`, rotation policy, and Relations with `int`-keyed `remote_units_data`

This example shows the "idict" envelope (for `dict[int, ...]` which JSON can't represent natively), the "set" envelope inside an `idict`, and `SecretRotate` enum.

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

##### `StoredState` escape hatch (`bytes`, `tuple`, `set`) + statuses, resources, ports, and deferred events

This example shows the escape-hatch types that `StoredState.content` can contain: `bytes` (base64-encoded), `tuple` (`list`-based envelope), and `set`. It also shows the "status" envelope for non-trivial status values, "Path" in a Resource, and `DeferredEvent`.

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

#### Settle policy considerations

The determinism requirement for settling is set out in [Automatic event triggering and convergence](#automatic-event-triggering-and-convergence): equal States and Dispatches on every run and every machine, with no wall-clock, PID, or set-iteration-order leakage.

The *implementation* of the convergence policy (round-robin, data-flow order, deterministic seed, user-overridable hook) is picked against that requirement, with the following acceptance:

- At least one deterministic policy ships and passes a **"run 100×, all final `State`s equal"** soak test.

#### Subinterpreters are explicitly ruled out

PEP 734 subinterpreters are **not** the mechanism, even assuming a Python 3.14+ requirement would be acceptable:

- **Binary-dependency conflicts remain unsolved.** Many C extensions (`cryptography`, `pydantic-core`, `cffi`-based packages) are not multi-interpreter-safe; two different versions of the same extension cannot coexist in one process at any Python version. These are the exact libraries motivating the work.
- **State boundary still costs a serialisation roundtrip**. The same JSON encode/decode as a subprocess, taken without the isolation benefit.
- **Maintenance cost is high** on a bleeding-edge API for no payoff over the subprocess design.

This will be revisited only if the C-extension multi-interpreter story matures enough to load conflicting binary versions in one process, not merely because the Python version floor moves.

### Inline charm classes vs. on-disk charms

Charm classes defined inline in a test cannot be trivially transferred to a fresh subprocess (the class object is not serialisable). Isolation realistically requires charms on disk. The API keeps both paths: inline classes, given as a `CharmSpec` or a bare class, run in-process with no isolation (like state transition tests today), and `deploy()` rejects `isolated=` for them;

The matrix of 'works inline but not isolated' surprises is closed by a **documentation convention** rather than a runtime check. Every `Juju` operation (`deploy`, `integrate`, `remove_relation`, `add_unit`, `remove_unit`, `config`, `settle`), and every `deploy()` argument that only applies in one mode (such as `isolated=` and `requirements=`) declares in its docstring two explicit fields:

- inline: ok | error | n/a
- isolated: ok | error | n/a

Where `ok` means works as documented, `error` means raises a clear typed error explaining why it's not supported in this mode, and `n/a` means doesn't make sense in this mode.

This is enforced by API-doc review at PR time. It's trivial to grep for. The matrix becomes readable in the docs rather than discoverable only by trial. There is no separate validation layer.

#### Migration from Catan / ops-scenario\~=6.0

The existing `PietroPasotti/catan` package pins `ops-scenario~=6.0` (superseded by `ops.testing`). There is **no compatibility shim**: tests written against Catan must be rewritten against the new API surface. The `ops-scenario~=6.0` form is throwaway regardless of whether this spec is adopted.

What the spec carries forward from Catan:

- The model: Apps + integration graph + convergence/settle
- The Juju-like operation vocabulary: `deploy` / `integrate` / `add-unit` / ...

#### Out of scope

- Changes to Scenario's existing single-charm API or behaviour
- charmcraft `reactive` plugin support

#### Prior art and references

- [Catan](https://github.com/PietroPasotti/catan): the abstraction this spec draws from.
- [operator#1929](https://github.com/canonical/operator/issues/1929): origin of the `ops.testing`-integrated direction.
- [Example tests](https://docs.google.com/document/d/155jcnVmf5w7YLZqVey3sUIzNVvzb8KHgJZuMVB5KKPk/edit?usp=sharing) and some comments on (an agent) writing them.
- [OP093 - charmlibs testing packages API](https://docs.google.com/document/d/1dd_UK-3bIrFn9LhGyHdNNyI8lgg2l6Vbq4iBVtUWwZs/edit?usp=sharing): single-charm testing against a stand-in for the remote charm, provided by the charm library's testing package. The stand-ins deploy through this spec's `Juju`, and library mocking reuses OP093's `mocked()` (see [*Relationship to OP093*](#relationship-to-op093)).
- Proof-of-concept PRs (note that these are vibe coded - I've tested them by using them but there has been no code review at this point):
  - [Isolation](https://github.com/tonyandrewmeyer/operator/pull/18)
  - [State serialisation and deserialisation](https://github.com/tonyandrewmeyer/operator/pull/20)
  - [Persistent workers](https://github.com/tonyandrewmeyer/operator/pull/22)
  - [Multiple charms](https://github.com/tonyandrewmeyer/operator/pull/35)
