# OP???: snapd test double for charmlibs.snap

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 30 Jul 2026 |

## Abstract

`charmlibs.snap` 2.0 talks to snapd over a unix socket. There's no snapd on a test runner, so the first call a machine charm makes raises `snap.ConnectionError`, and the charm errors out before it does anything the test wanted to look at. Today the only way around that is monkeypatching.

This spec proposes a stateful test double, `Snapd`, that replaces the library's client layer and leaves the rest of the library running for real. A charm test can then assert on what the charm asked snapd to do, and on the machine state that resulted, in the same test that runs the charm's event handlers under `ops.testing`.

There's a working proof of concept (see [Further Information](#further-information)).

## Rationale

The library's public surface is a flat set of module-level functions (`ensure_installed`, `install`, `refresh`, `remove`, `list_one`, `hold`, `start`, `stop`, `get`, `set`, `connect`, `alias`, `logs`, and so on). They all go through a small client module that speaks JSON over `/run/snapd.socket`.

The obvious workaround is to monkeypatch the public functions in each test:

```python
def test_install(monkeypatch):
    monkeypatch.setattr(snap, 'ensure_installed', lambda *a, **kw: True)
    ctx.run(ctx.on.install(), ops.testing.State())
```

That works, but it has three problems:

* It asserts nothing about whether the charm's call was well formed. A charm that calls `snap.ensure_installed('prometheus', '2/stable', 7)` passes this test, but the real library raises `TypeError`, because `revision` is keyword-only. The same goes for a snap name the library rejects with `ValueError`.
* It has no state, so we can't test a charm that reads back what it installed.
* Every charm writes it again from scratch, differently, and probably less completely each time.

The code paths that are most worth testing are also the ones an ad-hoc stub can't express at all: snapd being unreachable, a snap missing from the store, or a `post-refresh` hook failing part way through a change.

## Specification

### Packaging

The double is a separate distribution, `charmlibs-snap-testing`, imported as `from charmlibs import snap_testing`. It lives in the `charmlibs` monorepo at `snap/testing/`, and follows the layout and version lock that OP077 sets out for testing packages. It would be the first `*-testing` package to ship, so it's also the first real exercise of that part of the repo machinery.

It depends on `charmlibs-snap` (at the identical version) and nothing else. In particular, it doesn't depend on `ops[testing]`. The template includes that because interface-testing packages return `ops.testing.Relation` objects, but a snapd double doesn't return anything ops-shaped. Keeping ops out of the dependencies means the double works under `ops.testing`, under `Harness`, or with neither.

A `snapd` pytest fixture is registered with a `pytest11` entry point, so installing the package is enough to make it available.

OP077 has charms depend on `charmlibs-<libname>[testing]`. The branch doesn't add that extra to `charmlibs-snap` yet, so for now a charm depends on `charmlibs-snap-testing` directly. Adding the extra is a one-line change, and belongs in the `charmlibs` PR.

The double reaches into the library's private `_client` module from another distribution, which is a trade-off we've made on purpose (see [Alternatives](#alternatives)). I think `charmlibs.snap` should document the client functions as the supported (still underscored) seam for `charmlibs-snap-testing`.

### Where the double intercepts

`Snapd` is a context manager. Entering it replaces the four functions in `charmlibs.snap`'s private client module (`get`, `get_logs`, `post`, and `put`) with a stateful implementation of the snapd REST endpoints the library calls. Exiting restores them.

Everything above the socket still runs for real:

* `ensure_installed`'s decision tree
* snap name validation
* channel normalisation and resolution
* `InstalledInfo` parsing
* the mapping from snapd's error kinds to the library's typed exceptions
* the library narrowing a "not found" into `NotInstalledError` or `NotInStoreError`

Only the I/O is replaced.

This isn't a new seam. The library's own unit tests already patched the same four functions, but with canned responses for each test. The double patches in a model that changes as the charm acts.

A `Snapd` can only be used once, like `ops.testing.Context`. Entering one a second time raises an error, so a test can't accidentally carry state from one run into the next.

### Setting up a test

A test that doesn't care about the starting state can use the fixture, which gives it a fresh, empty `Snapd` for the whole test:

```python
def test_install_handler(snapd):
    ctx = ops.testing.Context(PrometheusCharm)
    state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert snapd.installed['prometheus'].channel == '2/stable'
    assert state_out.unit_status == ops.ActiveStatus()
```

A test that starts from an installed snap describes it using the same frozen `Snap` type that comes back out, so the input and output match:

```python
def test_config_changed_refreshes_channel():
    snapd = snap_testing.Snapd([
        snap_testing.Snap('prometheus', channel='2/stable', revision=100,
                          services={'prometheus': 'active'}),
    ])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        ctx.run(ctx.on.config_changed(), ops.testing.State(config={'channel': '2/edge'}))

    assert snapd.installed == {
        'prometheus': snap_testing.Snap('prometheus', channel='2/edge', revision=100,
                                        services={'prometheus': 'active'}),
    }
```

`installed` is the equivalent of Scenario's `state_out`. A test can assert on it as a whole, because every value the double fills in for a field the test didn't name is fixed and documented. With no store described, an install gets revision `'1'` and version `'1.0'`, and a refresh keeps the snap's revision unless the charm named one. Whether a refresh happened at all is a question for `history` (below), so `installed` only has to describe where the charm ended up.

An install with no store described also gets no services. That's deliberately strict. `start`, `stop`, or `restart` on a service the snap doesn't ship raises `AppNotFoundError`, and that's exactly the case ad-hoc stubs get wrong. A lenient default would quietly opt every test out of it. A test about services says which ones exist, either by giving a `Snap` some `services=`, or by describing the store:

```python
def test_install_starts_prometheus():
    snapd = snap_testing.Snapd(store=[
        snap_testing.StoreSnap('prometheus', channels={'2/stable': 100}, version='2.53.0',
                               services=['prometheus'], daemon_services=['prometheus']),
    ])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        ctx.run(ctx.on.install(), ops.testing.State())

    assert snapd.installed == {
        'prometheus': snap_testing.Snap('prometheus', channel='2/stable', revision=100,
                                        version='2.53.0', services={'prometheus': 'active'}),
    }
```

### Asserting on the path, not only the destination

Some charm behaviour is about ordering, and that's invisible in the final state. The double records every operation the charm performed, as the charm asked for it (before the double resolved it):

```python
def test_refresh_stops_service_first():
    snapd = snap_testing.Snapd([
        snap_testing.Snap('prometheus', channel='2/stable', services={'prometheus': 'active'}),
    ])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        ctx.run(ctx.on.config_changed(), ops.testing.State(config={'channel': '2/edge'}))

    assert snapd.history == [
        snap_testing.Stop('prometheus', services=('prometheus',), disable=False),
        snap_testing.Refresh('prometheus', channel='2/edge', revision=None),
        snap_testing.Start('prometheus', services=('prometheus',), enable=False),
    ]
```

`Refresh(channel='2/edge')` here is what the charm passed. There's one operation type for each library entry point that changes or reads snap state: `Install`, `Refresh`, `Remove`, `Hold`, `Unhold`, `Start`, `Stop`, `Restart`, `ConfigGet`, `ConfigSet`, `ConfigUnset`, `Connect`, `Disconnect`, `Alias`, `Unalias`, and `Logs`. We don't record `list_one`, because `ensure_installed` calls it on every run, and it would be noise in every assertion. Only operations that succeeded are recorded. A failure that the test injected shows up in the charm's behaviour, not in `history`.

A reconcile-style charm will probably ignore `history` and assert on `installed`, and a charm with ordering constraints will do the reverse. Neither is required.

### Store failures

By default, any snap installs and any refresh finds an update. A test that cares about the store describes one, and then the store only has what the test put in it:

* A snap that isn't in it raises `NotInStoreError`.
* A channel that it doesn't have raises `ChannelNotAvailableError`.
* A revision that isn't on any channel raises `RevisionNotAvailableError`.
* A snap marked classic that the charm installs without `classic=True` raises `NeedsClassicError`.
* A refresh to the revision that's already installed finds no update.

There's no separate flag to turn this on. Describing a store is what turns it on.

```python
def test_unknown_snap_blocks():
    snapd = snap_testing.Snapd(store=[snap_testing.StoreSnap('grafana')])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert state_out.unit_status == ops.BlockedStatus('snap prometheus not found in store')
```

### Injected failures

Failures that the store model can't express are described directly. They can be limited to one snap and to a number of occurrences, so that a charm's retry can be tested. The error is any `charmlibs.snap.Error`, raised as given. `'*'` fails every operation, which is what snapd being unreachable looks like to a charm:

```python
def test_snapd_unavailable_defers():
    snapd = snap_testing.Snapd(
        failures=[snap_testing.Failure('*', error=snap.ConnectionError('Could not connect to snapd'))],
    )
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert state_out.unit_status == ops.MaintenanceStatus('waiting for snapd')
    assert len(state_out.deferred) == 1
```

```python
def test_post_refresh_hook_failure_is_retried():
    snapd = snap_testing.Snapd(
        [snap_testing.Snap('prometheus', channel='2/stable')],
        failures=[
            snap_testing.Failure(
                'refresh',
                snap='prometheus',
                error=snap.ChangeError('run hook "post-refresh": exit status 1',
                                       kind='charmlibs-snap-change-error',
                                       value='42', status='Error'),
                times=1,  # succeeds when the charm retries
            ),
        ],
    )
    ...
```

### Behaviour the double reproduces

The point of running the real library over a fake socket is that the awkward cases behave the way they do in production. These are the ones that ad-hoc stubs usually get wrong. Each is covered by a test in the double's own suite, or in `snap`'s converted unit tests (see [Avoiding drift](#avoiding-drift)).

* `install` on a snap that's already installed returns a falsy value and doesn't raise. The same goes for `remove` of a snap that isn't installed, and for `refresh` with nothing to update (when a store is described).
* `connect` of a plug and slot that are already connected succeeds silently. `disconnect` of a named plug and slot that aren't connected raises an `APIError`, but a one-sided `disconnect` that matches nothing doesn't.
* `hold`, `refresh`, `start`, `get`, and the other per-snap operations on a snap that isn't installed raise `NotInstalledError`. snapd's own responses for most of these are ambiguous, so the library probes to tell them apart, and the double answers those probes the way snapd does.
* `get_one` for a key the snap hasn't set raises `OptionNotFoundError`.
* `start`, `stop`, or `restart` naming a service the snap doesn't ship, or a snap that has no services at all, raises `AppNotFoundError`.
* `alias` for an app the snap doesn't have, or an alias that another snap already has, raises `ChangeError`. It fails as an asynchronous change, not up front.
* `system` and `core` are two names for one configuration, whether or not a `core` snap is installed, and removing `core` drops what was stored there.

The double validates its inputs when it's constructed, in the same spirit as Scenario's consistency checker. A test that describes a state that real snapd couldn't be in fails straight away with `SnapStateValidationError`, rather than producing nonsense several layers down. That covers malformed channels and snap names, aliases naming services the snap doesn't have, connections referring to snaps that aren't installed, two snaps with the same name, and failures naming an operation that doesn't exist.

### Charm code outside a handler

Nothing here depends on ops, so charm logic that's been moved out of the event handlers can be tested directly, for example in unit tests for a workload module:

```python
def test_workload_manager(snapd):
    workload.reconcile(channel='2/edge')
    assert snapd.installed['prometheus'].channel == '2/edge'
```

### Scope for a first release

`ensure_installed`, `install`, `refresh`, `remove`, `list_one`, `hold`, `unhold`, `start`, `stop`, `restart`, `get`, `get_one`, `set`, `unset`, `connect`, `disconnect`, `alias`, and `unalias` are all modelled. `logs` returns canned entries: whatever the test described on each `Snap`, without filtering by `limit`. A charm that reads snap logs is usually forwarding them somewhere, so the test wants to control exactly what it gets.

Endpoints the double doesn't model raise `NotImplementedError` naming the path, rather than returning an empty success. If a charm uses something the double doesn't cover, its test should fail with a clear message rather than pass when it shouldn't.

We've deliberately not modelled two pieces of snapd behaviour, because both are machine state that a test has no correct value for.

Real snapd rejects an unknown system option (`snap.set('system', {'totally.bogus.key': 'x'})`) as a failed change. Modelling that would mean carrying snapd's option schema, which is large, changes between snapd versions, and isn't something charm tests assert against. The double stores any key.

A bare `snap.get('system')` on real snapd always includes values that snapd works out from the machine (the hostname, the timezone, and so on). Any value the double made up would just be a different divergence from every real machine, and a charm assertion that relied on a made-up hostname wouldn't be testing anything. The double returns only what was set.

The library's own socket handling (connection retries, the request timeout, and polling asynchronous changes) is also out of scope. That's a library concern rather than a charm one, and the library's functional tests cover it.

### Avoiding drift

The ongoing risk with any test double is drift: the double's snapd moves away from the real one, and charm tests pass against behaviour that real snapd doesn't have. We have two mitigations in place.

The first is that `snap`'s own unit tests run through the double. Every outcome-based test in `snap/tests/unit/` was converted from a mocked client with canned responses to a `Snapd`. That means every `charmlibs.snap` change is tested against the double in the same CI run, and if a library change isn't matched in the double, it fails there rather than in some charm's test suite. By file:

* `test_not_found.py` is fully converted. An empty `Snapd` answers "not found" for every public function, through the same probing code that a charm test exercises.
* `test_snapd_snaps.py`, `test_snapd_apps.py`, `test_snapd_conf.py`, and `test_snapd_logs.py` have every outcome-based test converted.
* `test_snapd_interfaces.py` has its probing and error tests converted. The rest assert on the shape of the request.
* `test_client.py`, `test_utils.py`, `test_functions.py`, `test_empty_or_blank.py`, `test_errors.py`, and `test_snapd_aliases.py` are unchanged.

The tests that weren't converted assert on the exact request the library sends, or on argument validation that fails before any request is made. A double answers questions about outcomes (what's installed, what was raised), so it has nothing to say about the shape of a request body, and those tests keep their mocks. Converting the rest found two places where the double disagreed with the library. Both are fixed.

The second is that the functional suite is the reference. `snap/tests/functional/` runs against real snapd, and where the double and a functional test disagree, the functional test wins and the double has a bug. The results of doing this for the proof of concept are under [Further Information](#further-information).

### Relationship to `ops.testing`

The double works with `ops.testing`, but doesn't depend on it or register into it. `ops.testing.State` models state that Juju owns. Snaps are machine state that Juju knows nothing about, so a `State(snaps=...)` field would be in the wrong place (and would raise the question of why apt packages and systemd units aren't there too). `ops.testing` also has no extension point for a library to add state or mocks to a `Context` run. So the double wraps `Context.run()` rather than living inside it. That has a useful side effect: the same object works under `Harness` and in plain pytest.

The fixture already wraps the whole test, which covers everything that wrapping `Context.run()` would. The one gap is a test that calls `Context.run()` more than once with the same `Snapd`, where `history` builds up across the runs. If that turns out to matter, we can solve it in `charmlibs-snap-testing` without touching ops. For example, there could be a way to mark a point in `history` and ask for what came after it.

## Further Information

### Proof-of-concept implementation

The double is built, as a new `charmlibs-snap-testing` distribution, on the [`feat/snap-testing-double`](https://github.com/tonyandrewmeyer/charmlibs/tree/feat/snap-testing-double/snap/testing) branch of a `charmlibs` fork. There's no `charmlibs` PR open yet.

On the branch, `just unit snap` passes (857 passed, 14 skipped) with `snap`'s unit tests converted to the double, and the double's own suite passes (137).

We ran `snap`'s full functional suite against snapd 2.76 in a VM (501 passed), and then probed the known disagreements directly on the snapd socket to get snapd's exact responses. There were five candidate disagreements. Four were real bugs in the double, and they're fixed:

* With a store described, a refresh with no channel followed `latest/stable` instead of the channel the snap tracks.
* A service action on a snap that isn't installed raised the wrong error kind and message.
* `connect` didn't reject an empty plug snap or plug name.
* `system` and `core` configuration diverged once a `core` snap was in the starting state, and survived removing it. (The second part needed its own check, in a throwaway container, since `core` can't be removed from under a running snapd.)

The fifth turned out to be the double behaving correctly. The two unmodelled behaviours in [Scope for a first release](#scope-for-a-first-release) came out of the same pass. They're real differences from snapd, and we've left them that way on purpose.

The first three bugs aren't visible through the public functions, which turn all of them into `NotInstalledError`. The double's own tests for them assert on the raw endpoint responses, which is the level the functional probe measured at.

### Alternatives

Monkeypatching the library's public functions in each charm's tests is the status quo, and its problems are covered in [Rationale](#rationale).

We considered a submodule, `charmlibs.snap.testing`, instead. That would avoid the double reaching into the library's private `_client` module from another distribution. However, it would ship a fake snapd in every charm that uses `charmlibs.snap`, and it wouldn't get the CI check that keeps a `-testing` distribution's version identical to its library's. The cross-distribution access is private across packages, not private across teams: it's the same repo and the same owners, and the version lock means the two can't drift apart without anyone noticing.

### Related specs

* OP077 (charm library testing) sets out the layout, the `[testing]` extra, and the version lock that `charmlibs-snap-testing` follows.

### Future work

* An extension point in `ops.testing`, so that libraries can register test doubles with a `Context` (for example, `Context(charm, extensions=[snapd])`), is a separate conversation, and this spec doesn't settle it. The double doesn't need one as it stands. I think it's worth having that conversation now that there's a prototype to look at. Anything like that would build on the context manager protocol that `Snapd` already implements, so adopting one later wouldn't change the double's public API.
* `apt`, `systemd`, `sysctl`, and `passwd` don't share `snap`'s seam. Each wraps `subprocess` rather than a client object, and `sysctl` and `passwd` also read and write files. So this double is specific to snaps for now. The parts that would generalise (the operation history, failure injection, and entering several doubles at once) are small, and moving them into a shared package later would only add to it. The fixtures also make it easy to combine doubles: `def test_x(snapd, apt):`.
