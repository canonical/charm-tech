# OP??? — snapd test double for charmlibs.snap

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 30 Jul 2026 |

## Abstract

`charmlibs.snap` 2.0 talks to snapd over a unix socket, and there is no snapd on a test runner, so a machine charm that installs a snap needs monkeypatching, otherwise the first call raises `snap.ConnectionError` and the charm errors out before it does anything a test wanted to look at. This spec proposes a stateful test double, `Snapd`, that replaces the library's client layer, leaving every other part of the library running for real. Charmers get to assert on what their charm asked snapd to do, and on the machine state that resulted, in the same test that runs their event handlers under `ops.testing`.

## Rationale

The library's public surface is a flat set of module-level functions (`ensure`, `install`, `refresh`, `remove`, `info`, `hold`, `start`, `stop`, `get`, `set`, `connect`, `alias`, `logs`, and so on) that all funnel through a small client module speaking JSON over `/run/snapd.socket`.

The obviously workaround is to monkeypatch the library's public functions, per test:

def test_install(monkeypatch):
    monkeypatch.setattr(snap, 'ensure', lambda *a, **kw: True)
    ctx.run(ctx.on.install(), ops.testing.State())
```

There are three problems with this. It asserts nothing about whether the charm's call was well formed - a charm that calls `snap.install('foo', channel='2/stable', revision=7)`, which is a `ValueError` in the real library, passes this test and fails in production. It carries no state, so a charm that reads back what it installed cannot be tested for correctness. And it is written again from scratch in every charm, differently and probably less completely each time.

In theory, code paths they most valuable to test are the ones an ad-hoc stub cannot express at all: snapd unreachable, a snap missing from the store, a `post-refresh` hook failing mid-change.

## Specification

### Where the double intercepts

`Snapd` is a context manager. Entering it replaces the four functions in `charmlibs.snap`'s private client module (`get`, `get_logs`, `post`, `put`) with a stateful implementation of the snapd REST endpoints the library actually calls; exiting restores them. Everything above the socket still runs for real: `ensure`'s decision tree, `install`'s channel/revision mutual exclusion, snap name validation, channel normalisation and resolution, `Info` parsing, and the mapping from snapd's `result.kind` onto the library's typed exceptions. Only the I/O is fake.

This is not a new seam: the library's own unit tests already patch those same four functions. The difference is that they patch in per-test canned responses, where the double patches in a world that changes as the charm acts.

### Setting up a test

A pytest fixture ships with the package, so a test that doesn't care about the starting state needs no setup at all:

def test_install_handler(snapd):
    ctx = ops.testing.Context(PrometheusCharm)
    state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert snapd.installed['prometheus'].channel == '2/stable'
    assert snapd.installed['prometheus'].services['prometheus'] == 'active'
    assert state_out.unit_status == ops.ActiveStatus()
```

A test that starts from an already-installed snap describes it, in the same frozen `Snap` type that comes back out, so input and output are symmetric:

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

`installed` is the analogue of Scenario's `state_out`, and is assertable as a whole because every value the double synthesises for a field the test didn't name is fixed and documented, rather than incidental.

### Asserting on the path, not only the destination

Some charm behaviour is about ordering, and is invisible in the final state. The double records every operation the charm performed, as the charm asked for it, before the double resolved it:

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

`Refresh(channel='2/edge')` here is what the charm passed. A reconcile-style charm will ignore `history` and assert on `installed`; a charm with ordering constraints will do the reverse. Neither is required.

### Store failures

By default any snap installs and any refresh finds an update. A test that cares about the store describes one, and then the catalogue is the world: a snap that isn't in it raises `NotFoundError`, a channel that isn't on it raises `ChannelNotAvailableError`, and a snap marked classic that the charm installs without `classic=True` raises `NeedsClassicError`. There is no mode flag - the presence of the argument is the mode.

def test_unknown_snap_blocks():
    snapd = snap_testing.Snapd(store=[snap_testing.StoreSnap('grafana')])
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert state_out.unit_status == ops.BlockedStatus('snap prometheus not found in store')
```

### Injected failures

Failures the store model cannot express are described directly, optionally scoped to one snap and to a number of occurrences, so that a charm's retry can be exercised. `'*'` fails every operation, which is what snapd being unreachable looks like to a charm:

def test_snapd_unavailable_defers():
    snapd = snap_testing.Snapd(
        failures=[snap_testing.Failure('*', error=snap.ConnectionError(
            'Could not connect to snapd', kind='charmlibs-snap-socket-not-found', value=''))],
    )
    ctx = ops.testing.Context(PrometheusCharm)

    with snapd:
        state_out = ctx.run(ctx.on.install(), ops.testing.State())

    assert state_out.unit_status == ops.MaintenanceStatus('waiting for snapd')
    assert len(state_out.deferred) == 1
```

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

### Behaviour the double is obliged to reproduce

The value of running the real library over a fake socket is that the awkward cases behave as they do in production. These all come from the library's documented behaviour and its error map, and are the ones ad-hoc stubs habitually get wrong:

* `install` on an already-installed snap returns falsy and does not raise; likewise `refresh` with nothing to update, and `remove` of a snap that isn't installed.
* `connect` of an already-connected plug and slot is a no-op.
* `install` or `refresh` with both `channel` and `revision` raises `ValueError` in the library, before any request - so the double never sees it, and a test asserting it is really asserting that the library still validates.
* `hold` on a snap that isn't installed raises `NotFoundError`.
* `ensure` with a bare risk inherits the installed track, so `'edge'` on a snap tracking `3.6/stable` gives `3.6/edge`.
* `get` for a key the snap hasn't set raises `OptionNotFoundError`, and `start`, `stop` or `restart` naming a service the snap doesn't ship raises `AppNotFoundError`.

Inputs are validated on construction, in the spirit of Scenario's consistency checker, so a test that describes a state real snapd could not be in fails immediately rather than producing nonsense several layers down: malformed channels and snap names, aliases naming services the snap doesn't have, connections referring to snaps that aren't installed, and two snaps with the same name.

### Charm code outside a handler

Nothing here depends on ops, so charm logic that has been factored out of event handlers is testable directly, for example in unit tests for the workload module:

def test_workload_manager(snapd):
    workload.reconcile(channel='2/edge')
    assert snapd.installed['prometheus'].channel == '2/edge'
```

### Packaging

Per OP077, the double ships as a separate distribution alongside the library, version locked to it, so charms depend on `charmlibs-snap[testing]` and import `from charmlibs import snap_testing`.

### Scope for a first release

`ensure`, `install`, `refresh`, `remove`, `info`, `hold`, `unhold`, `start`, `stop`, `restart`, `get`, `set`, `unset`, `connect`, `disconnect`, `alias` and `unalias` are all modelled. `logs` is canned: it returns the entries the test described, without filtering, because a charm reading snap logs is usually forwarding them somewhere and the test wants to control exactly what it sees.

Endpoints the double does not model raise `NotImplementedError` naming the path, rather than returning a silent empty success. A charm using something outside the double's coverage should fail its test with a clear message, not pass on a lie.
