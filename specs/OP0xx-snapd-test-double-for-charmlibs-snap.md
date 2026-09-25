# OP???: snapd test double for charmlibs.snap

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 30 Jul 2026 |

## Abstract

`charmlibs.snap` 2.0 talks to snapd over a unix socket, and there is no snapd on a test runner, so a machine charm that installs a snap needs monkeypatching, otherwise the first call raises `snap.ConnectionError` and the charm errors out before it does anything a test wanted to look at. This spec proposes a stateful test double, `Snapd`, that replaces the library's client layer, leaving every other part of the library running for real. Charmers get to assert on what their charm asked snapd to do, and on the machine state that resulted, in the same test that runs their event handlers under `ops.testing`.

The double is built, as a new `charmlibs-snap-testing` distribution, on the [`feat/snap-testing-double`](https://github.com/tonyandrewmeyer/charmlibs/tree/feat/snap-testing-double/snap/testing) branch of a `charmlibs` fork. `snap`'s own unit tests already drive through it, and its behaviour has been checked against real snapd. No `charmlibs` PR is open yet.

## Rationale

The library's public surface is a flat set of module-level functions (`ensure_installed`, `install`, `refresh`, `remove`, `list_one`, `hold`, `start`, `stop`, `get`, `set`, `connect`, `alias`, `logs`, and so on) that all funnel through a small client module speaking JSON over `/run/snapd.socket`.

The obvious workaround is to monkeypatch the library's public functions, per test:

```python
def test_install(monkeypatch):
    monkeypatch.setattr(snap, 'ensure_installed', lambda *a, **kw: True)
    ctx.run(ctx.on.install(), ops.testing.State())
```

There are three problems with this. It asserts nothing about whether the charm's call was well formed - a charm that calls `snap.ensure_installed('prometheus', '2/stable', 7)`, which is a `TypeError` in the real library (`revision` is keyword-only), passes this test and fails in production, and so does a snap name the library rejects with `ValueError`. It carries no state, so a charm that reads back what it installed cannot be tested for correctness. And it is written again from scratch in every charm, differently and probably less completely each time.

In practice, the code paths most valuable to test are the ones an ad-hoc stub cannot express at all: snapd unreachable, a snap missing from the store, a `post-refresh` hook failing mid-change.

## Specification

### Packaging

The double is a separate distribution, `charmlibs-snap-testing`, importable as `from charmlibs import snap_testing`. It lives in the `charmlibs` monorepo at `snap/testing/`, following the layout and version lock that OP077 sets out for testing packages. It would be the first `*-testing` package to ship, so it is also the first real exercise of that repo machinery.

It depends on `charmlibs-snap` (at the identical version) and on nothing else. In particular, it does not depend on `ops[testing]`, which the template includes because interface-testing packages return `ops.testing.Relation` objects. A snapd double returns nothing ops-shaped, and keeping ops out of the dependency tree means it works under `ops.testing`, under `Harness`, or with neither.

A `snapd` pytest fixture is registered through a `pytest11` entry point, so installing the package is enough to make it available.

OP077 has charms depend on `charmlibs-<libname>[testing]`. The branch doesn't add that extra to `charmlibs-snap` yet, so for now a charm depends on `charmlibs-snap-testing` directly. Adding the extra is a one-line change, and belongs in the `charmlibs` PR.

A submodule, `charmlibs.snap.testing`, was considered and rejected. It would avoid the double reaching into the library's private `_client` module across a distribution boundary, but it would ship a fake snapd in every charm that uses `charmlibs.snap`, and it would get nothing from the CI check that keeps a `-testing` distribution's version identical to its library's. The cross-distribution access is private-across-packages rather than private-across-teams: same repo, same owners, and the version lock means the two cannot drift apart silently. `charmlibs.snap` should document the client functions as the sanctioned (still underscored) seam for `charmlibs-snap-testing`.

### Where the double intercepts

`Snapd` is a context manager. Entering it replaces the four functions in `charmlibs.snap`'s private client module (`get`, `get_logs`, `post`, `put`) with a stateful implementation of the snapd REST endpoints the library actually calls; exiting restores them. Everything above the socket still runs for real: `ensure_installed`'s decision tree, snap name validation, channel normalisation and resolution, `InstalledInfo` parsing, the mapping from snapd's error kinds onto the library's typed exceptions, and the library's narrowing of a "not found" into `NotInstalledError` or `NotInStoreError`. Only the I/O is fake.

This is not a new seam: the library's own unit tests already patched those same four functions. The difference is that they patched in per-test canned responses, where the double patches in a world that changes as the charm acts.

A `Snapd` is single-use, like `ops.testing.Context`: entering one a second time raises, so a test can't accidentally carry state from one run into the next.

### Setting up a test

The fixture gives a test that doesn't care about the starting state a fresh, empty `Snapd`, entered for the whole test:

```python
def test_install_handler(snapd):
    ctx = ops.testing.Context(PrometheusCharm)
    state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert snapd.installed['prometheus'].channel == '2/stable'
    assert state_out.unit_status == ops.ActiveStatus()
```

A test that starts from an already-installed snap describes it, in the same frozen `Snap` type that comes back out, so input and output are symmetric:

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

`installed` is the analogue of Scenario's `state_out`, and is assertable as a whole because every value the double synthesises for a field the test didn't name is fixed and documented, rather than incidental. With no store described, an install gets revision `'1'` and version `'1.0'`, and a refresh keeps the snap's revision unless the charm named one. Whether a refresh happened at all is a question for `history` (below), so `installed` only has to describe where the charm ended up.

An install with no store described also gets no services. This is strict on purpose: `start`, `stop` or `restart` on a service the snap doesn't ship raises `AppNotFoundError`, which is exactly the case ad-hoc stubs get wrong, and a lenient default would quietly opt every test out of it. A test about services says which ones exist, by seeding a `Snap` with `services=` or by describing the store:

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

Some charm behaviour is about ordering, and is invisible in the final state. The double records every operation the charm performed, as the charm asked for it, before the double resolved it:

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

`Refresh(channel='2/edge')` here is what the charm passed. There is one operation type per library entry point that changes or reads snap state (`Install`, `Refresh`, `Remove`, `Hold`, `Unhold`, `Start`, `Stop`, `Restart`, `ConfigGet`, `ConfigSet`, `ConfigUnset`, `Connect`, `Disconnect`, `Alias`, `Unalias`, `Logs`). `list_one` isn't recorded, since `ensure_installed` calls it on every run and it would be noise in every assertion. Only operations that succeeded are recorded; a failure the test injected shows up in the charm's behaviour, not in `history`.

A reconcile-style charm will ignore `history` and assert on `installed`; a charm with ordering constraints will do the reverse. Neither is required.

### Store failures

By default any snap installs and any refresh finds an update. A test that cares about the store describes one, and then the catalogue is the world: a snap that isn't in it raises `NotInStoreError`, a channel that isn't on it raises `ChannelNotAvailableError`, a revision that isn't on any channel raises `RevisionNotAvailableError`, a snap marked classic that the charm installs without `classic=True` raises `NeedsClassicError`, and a refresh to the revision already installed finds no update. There is no mode flag - the presence of the argument is the mode.

```python
def test_unknown_snap_blocks():
    snapd = snap_testing.Snapd(store=[snap_testing.StoreSnap('grafana')])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert state_out.unit_status == ops.BlockedStatus('snap prometheus not found in store')
```

### Injected failures

Failures the store model cannot express are described directly, optionally scoped to one snap and to a number of occurrences, so that a charm's retry can be exercised. The error is any `charmlibs.snap.Error`, raised as given. `'*'` fails every operation, which is what snapd being unreachable looks like to a charm:

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

The value of running the real library over a fake socket is that the awkward cases behave as they do in production. These are the ones ad-hoc stubs habitually get wrong, and each is pinned by a test in the double's own suite or in `snap`'s converted unit tests (see [Keeping it honest](#keeping-it-honest)):

* `install` on an already-installed snap returns falsy and does not raise; likewise `remove` of a snap that isn't installed, and `refresh` with nothing to update (when a store is described).
* `connect` of an already-connected plug and slot succeeds silently. `disconnect` of a named plug and slot that aren't connected raises an `APIError`, but a one-sided `disconnect` that matches nothing does not.
* `hold`, `refresh`, `start`, `get` and the other per-snap operations on a snap that isn't installed raise `NotInstalledError`. snapd's own responses for most of these are ambiguous; the library probes to disambiguate them, and the double answers those probes the way snapd does.
* `get_one` for a key the snap hasn't set raises `OptionNotFoundError`.
* `start`, `stop` or `restart` naming a service the snap doesn't ship, or naming a snap that has no services at all, raises `AppNotFoundError`.
* `alias` for an app the snap doesn't have, or an alias another snap already has, raises `ChangeError` (it fails as an asynchronous change, not up front).
* `system` and `core` are two names for one configuration, whether or not a `core` snap is installed, and removing `core` drops what was stored there.

Inputs are validated on construction, in the spirit of Scenario's consistency checker, so a test that describes a state real snapd could not be in fails immediately with `SnapStateValidationError`, rather than producing nonsense several layers down: malformed channels and snap names, aliases naming services the snap doesn't have, connections referring to snaps that aren't installed, two snaps with the same name, and failures naming an operation that doesn't exist.

### Charm code outside a handler

Nothing here depends on ops, so charm logic that has been factored out of event handlers is testable directly, for example in unit tests for the workload module:

```python
def test_workload_manager(snapd):
    workload.reconcile(channel='2/edge')
    assert snapd.installed['prometheus'].channel == '2/edge'
```

### Scope for a first release

`ensure_installed`, `install`, `refresh`, `remove`, `list_one`, `hold`, `unhold`, `start`, `stop`, `restart`, `get`, `get_one`, `set`, `unset`, `connect`, `disconnect`, `alias` and `unalias` are all modelled. `logs` is canned: it returns the entries the test described on each `Snap`, without filtering by `limit`, because a charm reading snap logs is usually forwarding them somewhere and the test wants to control exactly what it sees.

Endpoints the double does not model raise `NotImplementedError` naming the path, rather than returning a silent empty success. A charm using something outside the double's coverage should fail its test with a clear message, not pass on a lie.

Two pieces of snapd behaviour are deliberately not modelled, because both are machine state that a test has no correct value for:

* **System option validation.** Real snapd rejects an unknown system option (`snap.set('system', {'totally.bogus.key': 'x'})`) as a failed change. Modelling that means carrying snapd's option schema, which is large, changes between snapd versions, and isn't something a charm test asserts against. The double stores any key.
* **Computed system configuration.** A bare `snap.get('system')` on real snapd always includes values snapd computes from the machine (the hostname, the timezone, and so on). Any value the double invented would just be a different divergence from every real machine, and a charm assertion resting on an invented hostname would be asserting nothing. The double returns only what was set.

The library's own socket handling (connection retries, the request timeout, polling asynchronous changes) is also out of scope: it's a library concern rather than a charm one, and the library's functional tests cover it.

### Keeping it honest

The standing risk with any test double is drift: the double's snapd diverges from the real one, and charm tests go green on fiction. There are two mitigations, and both are in place.

**`snap`'s own unit tests run through the double.** Every outcome-shaped test in `snap/tests/unit/` was converted from a mocked client with canned responses to a `Snapd`, so every `charmlibs.snap` change is tested against the double in the same CI run, and a library change that the double doesn't keep up with fails there rather than in a charm's test suite. Per file:

* `test_not_found.py` is fully converted: an empty `Snapd` answers "not found" for every public function, through the same probing code paths a charm test exercises.
* `test_snapd_snaps.py`, `test_snapd_apps.py`, `test_snapd_conf.py` and `test_snapd_logs.py` have every outcome-shaped test converted.
* `test_snapd_interfaces.py` has its probing and error tests converted; the rest asserts on request shape.
* `test_client.py`, `test_utils.py`, `test_functions.py`, `test_empty_or_blank.py`, `test_errors.py` and `test_snapd_aliases.py` are unchanged.

The unconverted tests assert on the exact request the library sends, or on argument validation that fails before any request. A double answers questions about outcomes (what is installed, what was raised), so it has nothing to say about the shape of a request body, and those tests keep their mocks. The conversion found two places where the double disagreed with the library, both fixed.

**The functional suite is the oracle.** `snap/tests/functional/` runs against real snapd. The rule is that where the double and a functional test disagree, the functional test wins and the double has a bug. The full suite was run against snapd 2.76 in a VM (501 passed), and the known disagreements were then probed directly on the snapd socket to get snapd's exact responses.

Of the five candidate disagreements, four were real bugs in the double, and are fixed:

* With a store described, a refresh with no channel followed `latest/stable` instead of the channel the snap tracks.
* A service action on a snap that isn't installed raised the wrong error kind and message.
* An empty plug snap or plug name in `connect` wasn't rejected.
* `system` and `core` configuration diverged once a `core` snap was seeded, and survived removing it. (The second part needed its own measurement, in a throwaway container, since `core` can't be removed from under a running snapd.)

The fifth closed in the double's favour. The two unmodelled behaviours above came out of the same pass; they are real differences from snapd, left as they are on purpose.

The first three are invisible through the public functions, which narrow all of them to `NotInstalledError`. The double's own tests for them assert on the raw endpoint responses, which is the level the functional probe measured at.

### Relationship to `ops.testing`

The double composes with `ops.testing` but does not depend on it or register into it. `ops.testing.State` models Juju-owned state, and snaps are machine state that Juju knows nothing about, so a `State(snaps=...)` field would be a category error (and would raise the question of why apt packages and systemd units aren't there too). `ops.testing` also has no extension point for a library to contribute state or mocks to a `Context` run. So the double wraps `Context.run()` rather than living inside it, which turns out to be useful: the same object works under `Harness` and in plain pytest.

The fixture already brackets the whole test, which covers everything that bracketing `Context.run()` would. The one gap is a test that calls `Context.run()` more than once against the same `Snapd`, where `history` accumulates across the runs. If that turns out to matter, it can be solved in `charmlibs-snap-testing` without touching ops (for example, a way to mark a point in `history` and ask for what came after it).

### Future work

* **An extension point in `ops.testing`.** A way for libraries to register test doubles with a `Context` (for example, `Context(charm, extensions=[snapd])`) is a separate conversation, and this spec doesn't settle it. The double's current position is that it doesn't need one. It is worth having the conversation with this prototype in hand, and anything like that would build on the context manager protocol `Snapd` already implements, so adopting one later wouldn't change the double's public API.
* **Doubles for the other machine libraries.** `apt`, `systemd`, `sysctl` and `passwd` don't share `snap`'s seam: each wraps `subprocess` rather than a client object, and `sysctl` and `passwd` also read and write files. So this double is snap-specific for now. The parts that would generalise (the operation history, failure injection, and entering several doubles at once) are small, and extracting them into a shared package later is additive. The fixtures also make composing doubles simple: `def test_x(snapd, apt):`.
