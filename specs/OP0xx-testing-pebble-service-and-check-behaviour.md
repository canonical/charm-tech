# OP???: Testing Pebble service and check behaviour

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 31 Jul 2026 |

Proof-of-concept implementation across [#26](https://github.com/tonyandrewmeyer/operator/pull/26), [#27](https://github.com/tonyandrewmeyer/operator/pull/27), [#29](https://github.com/tonyandrewmeyer/operator/pull/29), [#30](https://github.com/tonyandrewmeyer/operator/pull/30), [#32](https://github.com/tonyandrewmeyer/operator/pull/32), [#33](https://github.com/tonyandrewmeyer/operator/pull/33) and [#34](https://github.com/tonyandrewmeyer/operator/pull/34).

## Abstract

`ops.testing` models a container's Pebble as a store of state that the charm reads and writes, but not as something that does anything of its own. A service the charm starts always starts; a check's status is whatever the test seeded and never moves; only the charm can produce a notice; and the output state records where each service ended up but not how it got there. As a result, the parts of a charm that deal with a workload misbehaving — the parts most worth testing — are the parts that cannot be unit tested at all.

This spec proposes that a test be able to declare what the workload does (a service that fails to start, a check that comes up on the third poll, a service that notifies Pebble when it is ready), inspect what the charm asked Pebble to do, and see the one thing Pebble does on its own accord (`on-check-failure`). It also brings the shape of a check's change into line with real Pebble, so that a charm reporting *why* a check failed can be tested against what it will actually receive.

## Rationale

### Distinguishing a restart from a start

A charm that reconfigures its workload writes the new layer and then restarts the service. If it calls `start()` instead of `restart()`, the service is already running, Pebble does nothing, and the workload keeps running the old configuration. Whether that mistake was made is not visible in the output state: the only evidence available afterwards is `container.service_statuses['myapp'] == ServiceStatus.ACTIVE`, which is equally true either way. A refactor that swaps one call for the other leaves every existing test passing.

Charms that want to assert on this monkeypatch `ops.model.Container.restart`. In [airflow-core-operators](https://github.com/canonical/airflow-core-operators), each of the four charms has Scenario tests that patch it and then assert `restart_mock.assert_called_once()` or `assert_not_called()` — the assertion the output state cannot support. [postgresql-k8s-operator](https://github.com/canonical/postgresql-k8s-operator), [kafka-operator](https://github.com/canonical/kafka-operator), [zookeeper-operator](https://github.com/canonical/zookeeper-operator) and their K8s counterparts patch the same method. That couples the test to an ops implementation detail, and asserts that the charm called a particular method rather than that the workload ended up in the right state.

### Testing what the charm does when the workload doesn't come up

Charms do handle `ops.pebble.ChangeError` and set a blocked or error status in response: of the 641 charm repositories surveyed (see [Survey basis](#survey-basis)), 128 catch it somewhere outside their tests. There is no way to provoke that path, because in `ops.testing` a service that is asked to start always starts. Eleven of those 128 mention `ChangeError` anywhere in their test suites at all, so for the great majority the handler that matters when a deployment is broken is the handler with no test coverage.

Where it is tested, it is tested by patching. [cos-coordinated-workers](https://github.com/canonical/cos-coordinated-workers) replaces `ops.model.Container.restart` with a function that raises, under the comment `# WHEN service restart fails`, and the test that follows notes that "technically an `ops.pebble.ChangeError` [is raised] but the context manager doesn't catch it for some reason" — the test cannot rely on the error being shaped the way Pebble shapes it, because nothing in `ops.testing` produced it.

### Testing a charm that waits for a check

A charm that polls a health check until the workload is ready, and branches on what it finds, can only ever be tested against one outcome, because a seeded `CheckInfo`'s status is fixed for the whole run. Both branches — "still coming up, defer" and "up, carry on" — need a check whose status can move.

Related: a charm that names a check in a service's `on-check-failure` is delegating recovery to Pebble. Nineteen of the surveyed repositories set `on-check-failure`, including [datahub-k8s-operator](https://github.com/canonical/datahub-k8s-operator) (`{'up': 'restart'}`) and [mediawiki-k8s-operator](https://github.com/canonical/mediawiki-k8s-operator) (`{'git-sync-alive': 'restart'}`). Nothing in `ops.testing` models what Pebble then does, so the furthest a test can go is to assert that the plan says so — which is what datahub's test does, checking `on_check_failure.get('up') == 'restart'` under the docstring "Healthcheck services wire `up` to on-check-failure: restart." Whether the recovery actually happens is not something a unit test can reach.

### Testing a charm that responds to its workload

A workload can notify Pebble once it is up, and the charm then handles a `pebble-custom-notice` event on a later run. This is a minority pattern rather than a common one — seven of the surveyed repositories observe the event, among them [k6-k8s-operator](https://github.com/canonical/k6-k8s-operator), [notary-k8s-operator](https://github.com/canonical/notary-k8s-operator), [github-profiles-automator](https://github.com/canonical/github-profiles-automator) and [charm-rabbitmq-k8s](https://github.com/canonical/charm-rabbitmq-k8s) — but where it is used it is load-bearing.

`ops.testing` can seed such a notice in the input state, but nothing during a run can produce one, so a test has to hand-seed the notice that the previous run *should* have produced. k6's `test_done_notice_sets_unit_idle` builds `testing.Notice(key='k6.com/done')`, rebuilds its container to attach it, and runs the notice event against that — a reasonable test of the handler, but one that cannot check that starting the service is what produces the notice.

### What charms do instead today

Mostly, they don't test any of this — or they push it to integration tests, where a workload failure is slow and awkward to arrange. The counts above are the evidence: 128 repositories handle a Pebble `ChangeError`, and 11 of them mention `ChangeError` in a test.

Where charms do test in this area, it is by asserting on the plan — 44 of the surveyed repositories compare a plan or a layer against an expected dictionary in their tests. [temporal-k8s-operator](https://github.com/canonical/temporal-k8s-operator) is representative: its Scenario test asserts the whole service dictionary, `on-check-failure` entry included. That covers the charm's intent, and says nothing about what happens when the workload does not cooperate.

That plan-shaped assertion is a good fit for a reconciler charm, which generates a plan and lets Pebble decide whether anything needs restarting. The proposal here does not push charms away from that style: recording the operations the charm performed is an observation, not an instruction to write imperative charms. It happens to be the only way to observe a Pebble-initiated restart, which a reconciler charm relies on more heavily than an imperative one.

This is issue [#1427](https://github.com/canonical/operator/issues/1427), though that issue asks only for a `restarted` flag on the output state. A flag answers "was it restarted at all", which is the smallest of the questions above, and answers it in a form that cannot be extended to ordering, to arguments, or to the reason.

## Specification

The behaviour modelled below was taken from the Pebble source — `internals/overlord/servstate/handlers.go` and `manager.go` — and confirmed by driving `ops.pebble.Client` against a running Pebble (v1.32.1). Where this proposal leaves something unmodelled, that is a scope decision with a reason, given in [Limitations](#limitations); those cases raise `NotImplementedError` so that a test asking for them fails loudly rather than silently getting a fabricated answer.

### Declaring what a service does when it starts

`ServiceBehaviour` follows the precedent set by `Exec`: the test says what happens, and `ops.testing` does not try to derive it from the plan.

```python
def test_workload_fails_to_start():
    ctx = Context(MyCharm)
    container = Container(
        'workload',
        can_connect=True,
        layers={'base': layer},
        service_behaviours={
            ServiceBehaviour('myapp', start=ServiceStart.FAILS),
        },
    )
    state_out = ctx.run(ctx.on.config_changed(), State(containers={container}))
    assert isinstance(state_out.unit_status, BlockedStatus)
```

`ServiceStart` has three members:

* `RUNS` — the service comes up and stays up. This is the default, so no existing test changes.
* `FAILS` — the service never comes up, and `start()`, `restart()`, `replan()` and `autostart()` raise `ops.pebble.ChangeError`, as real Pebble does.
* `EXITS` — the service comes up, and exits some time later. The call that started it *succeeds*; the crash shows up in the status afterwards.

The `FAILS`/`EXITS` split is not a matter of degree. Pebble marks a start task `Done` once the service has stayed up for one second (`okayDelay`), so an exit inside that window fails the call that started it and an exit after it does not. A charm's error handling for the two is completely different — one is an exception to catch, the other is a status to notice on a later hook — so a test needs to be able to ask for either.

Two further fields refine each case. `ServiceFailureMode` says how a `FAILS` service fails: `CRASH` (the command runs and exits immediately) or `EXEC_ERROR` (the command could not be run at all, for example a missing binary). The resulting status differs — `EXEC_ERROR` always leaves the service `INACTIVE`, since the process never started, whereas `CRASH` depends on the service's `on-failure` policy. `ServiceExitCode` says whether an `EXITS` service's exit was clean, which decides whether `on-success` or `on-failure` governs the result.

In both cases the resulting status is derived from the plan the way Pebble derives it, including the awkward parts: with the default `on-failure: restart`, a crashed service reports the raw string `'backoff'`, which is not a member of `ops.pebble.ServiceStatus`, so `ServiceInfo.current` is a plain `str` — exactly as it is with real Pebble.

### Declaring what a check does over a run

`CheckBehaviour` lets a test give a check a sequence of statuses instead of a single frozen one:

```python
Container(
    'workload',
    check_infos={CheckInfo('up-check', status=pebble.CheckStatus.DOWN)},
    check_behaviours={
        CheckBehaviour('up-check', statuses=[DOWN, DOWN, UP]),
    },
)
```

The sequence advances one entry each time the charm reads *that* check; reads of other checks do not advance it. Once the sequence is exhausted its last entry repeats, so a charm that polls until the check comes up settles on the final status rather than running off the end, and the test does not have to count reads exactly.

Advancing on reads rather than on service operations is deliberate. In real Pebble a check's status moves when its own period elapses; starting, stopping or replanning a service does not move it. `ops.testing` has no clock, so a read is the closest observable stand-in for time passing. Tying the sequence to service operations would model a causal link that does not exist, and would leave a polling handler seeing one frozen value. The cost is that reads are no longer side-effect free: a handler that logs the status and then branches on it consumes two entries.

Everything else the charm can see about the check follows from the declared statuses, derived as Pebble derives it, rather than being seeded separately and going stale: the failure count reaches the threshold when the check goes down and keeps climbing while it stays down; the success count freezes while the check is down and restarts from one on recovery; the change ID moves to a fresh `recover-check` on failure and a fresh `perform-check` on recovery, with the abandoned change settling at `Error` or `Done`; and each transition emits the `change-update` notice Pebble emits.

`CheckBehaviour` also takes an optional `failure_message` — what Pebble puts in the failed change's `err` and task log, such as `'exit status 1'` for an exec check or `'received non-20x status code 500'` for an HTTP one. A charm that wants to report why a check failed has to read that text, and cannot do so today. Without a `failure_message` the change carries no error text: `ops.testing` cannot know why a declared check failed and should not invent a reason.

Unlike `Exec`, this is deliberately not strict. A check with no declared behaviour keeps reporting its seeded status, because a check that simply sits there is a normal thing for a test to want, where an unmocked exec is usually a test bug.

### Declaring the notices a service sends

A `ServiceBehaviour` can say what the workload notifies Pebble about when it starts:

```python
ServiceBehaviour('myapp', emits=[Notice('example.com/started')])
```

The notices are recorded when the service starts — through `start()`, `restart()`, `replan()` or `autostart()` — and are visible both to the charm during that run and in the output state. That second part is the point: the output state can be fed straight into the run that handles the notice, so the whole sequence is one test rather than two disconnected ones.

```python
state_out = ctx.run(ctx.on.config_changed(), state)
container_out = state_out.get_container('workload')
(notice,) = container_out.notices

ctx.run(
    ctx.on.pebble_custom_notice(container=container_out, notice=notice),
    state_out,
)
```

A `FAILS` service never starts, so it emits nothing; an `EXITS` service does start, so it emits. A service starting alongside a failing one still emits, because Pebble tracks each service's start attempt independently. Only the type, key and data are taken from the declared `Notice` — the ID, timestamps and occurrence count are assigned the way Pebble assigns them, so starting a service twice in one run gives one notice with two occurrences rather than two notices.

Relatedly, notices the charm records itself with `pebble.notify()` currently vanish from the output state, even though the charm can see them via `get_notices()` during the run. They should survive the run, as Pebble keeps them.

### Inspecting what the charm asked Pebble to do

The service statuses in the output state say where the workload ended up. A per-container operation history on `Context` says how it got there, following the `exec_history` precedent:

```python
state_out = ctx.run(ctx.on.config_changed(), state)
assert ctx.service_ops_history['workload'] == [ServiceOp('restart', ('myapp',))]
```

This is what distinguishes a `start()` from a `restart()`, and what makes ordering assertions possible. `Context.get_service_ops(container, service=None)` filters to the operations involving a single service, for the common case.

For `replan` and `autostart`, the recorded service list is the services with `startup: enabled` in the plan at the time of the call — the charm's intent, captured before the underlying client filters out services that are already running. Calls that raise `ConnectionError` because the container cannot be reached are not recorded.

`add_layer_history` records `Container.add_layer()` calls in the same shape, so a test can assert on layer ordering as well.

The history lives on `Context` rather than on the output `Container` because a `service_ops` field on an *input* `Container` would have no meaning, and because accumulating into a frozen dataclass during a run needs a parallel mutable accumulator anyway.

### Modelling what Pebble does on its own

A service can name a check in its `on-check-failure`, and Pebble restarts that service when the check goes down. A charm that relies on this is relying on Pebble to recover its workload, and today there is no way to test that the wiring is right.

With a check that can be made to go down and somewhere to record the consequence, this becomes expressible:

```python
assert ctx.service_ops_history['workload'] == [
    ServiceOp('restart', ('myapp',), caused_by='up-check'),
]
```

`ServiceOp.caused_by` is the name of the check whose failure made Pebble act, or `None` when the charm invoked the operation itself — so every existing `ServiceOp(...)` comparison keeps working.

The recorded operation is the *only* evidence available. Verified against a running Pebble, the service passes through `backoff` and lands back on the `ACTIVE` it already had, and Pebble records no change for the restart it performs. A status-and-changes view of the output state is therefore identical whether or not the restart happened.

The action fires once per transition *into* `DOWN`, not on every read of a check that is already down.

Pebble's `checkFailed` acts on a service in three states — running, in backoff, and exited — and ignores the failure in any other state, including stopped. A running service is terminated and then restarted through backoff; a service already in backoff waits out the backoff it is in, and nothing further happens; an exited service goes straight into backoff. This proposal models the running case, which is the one a charm sets `on-check-failure` for. The backoff and exited cases need a service that is already mid-backoff or crashed at the point the check goes down, which means composing `ServiceBehaviour` with `CheckBehaviour` across a run; that is worth doing, and is left for after both are in.

### Making a check's change look like Pebble's

The reason a check failed is carried on the check's change — its `err`, or its task log — so that is what a charm reporting the reason has to read. What `ops.testing` and `Harness` produce there does not match real Pebble, so a test that exercises such a charm would be asserting against a shape the charm will never see in production. Both should produce:

* A change summary in Pebble's shape: `Perform exec check "up"` — the action, the check's type and the quoted name — rather than the bare check name.
* Exactly one task on the change, sharing the change's kind and summary, rather than no tasks at all.
* A change registered under the check's own change ID, so that `get_change(info.change_id).id` round-trips; with no ready time while the change is still `Doing`; and with no change at all for an inactive check, which is what real Pebble has.
* A stopped check's change settled at `Done`, whether the check was up or down, and no change ID reported — rather than an aborted change and an empty-string change ID.
* A freshly started check reporting neither a failure count nor a success count, rather than resetting only the failure count.

The check type in the summary comes from the plan, so a check that exists only in seeded test state — a state real Pebble cannot be in — gets `Perform check "up"`, with the type omitted.

These are corrections rather than new features, and they apply to `Harness` as well as to `ops.testing`. The declared behaviours above are `ops.testing` only.

## Limitations

`ops.testing` has no clock, and this proposal does not add one. Check statuses advance on reads, and nothing expresses "after thirty seconds". A test that wants a specific number of transitions still has to reason about how many times its charm reads the check.

The workload itself is not simulated. A check's status is declared by the test, not derived from an `Exec` handler, from an HTTP endpoint, or from the plan. Expressing "given this environment variable in the plan, the health check passes" would need a workload mock with its own API, which is a substantially larger design and is not proposed here.

The shutdown policies are not modelled, and this is a deliberate limit rather than an open question. Pebble does two things with them: it calls `HandleRestart` to bring the daemon down, and it moves the service to its exited state, which surfaces as `ServiceStatus.ERROR`. (`on-success` also accepts `failure-shutdown`, and `on-failure` and `on-check-failure` accept `success-shutdown`, so that a service can be made to bring the daemon down the *other* way round; the plain `shutdown` action picks the matching one from the exit code.) The status half is easy to model, but modelling it alone would be worse than not modelling it: the charm-visible consequence of a shutdown is the daemon going down and, under Juju, the container being recycled, and an `ops.testing` run has no daemon and no container lifecycle to express that with. A test that saw `ERROR` and nothing else would be reading a half-truth. So these raise `NotImplementedError`, and modelling them properly waits for `ops.testing` to have some notion of the container going away.

`on-check-failure` deliberately leaves stopped services alone, and this is Pebble's behaviour rather than a gap: `checkFailed` acts only on a service that is running, in backoff, or exited, and logs and ignores the failure in every other state. The states this proposal does not yet cover — backoff and exited — are described in [Modelling what Pebble does on its own](#modelling-what-pebble-does-on-its-own).

Service log output is not modelled, because there is nothing yet for a test to assert against: Pebble keeps a per-service ring buffer and serves it from `/v1/logs`, but `ops.pebble.Client` does not expose it, so a charm cannot read service logs through ops at all. If that API is added, declaring a service's output belongs with it.

## Alternatives considered

**A `restarted` flag on the output container**, as suggested in the original issue. This answers only "did a restart happen at all". It cannot express ordering, which services were named, or that Pebble rather than the charm was responsible, and there is no clean way to grow it into something that can.

**Deriving check status from the plan or from `Exec` handlers.** This would tie a check's outcome to exec mocking, would not work for HTTP or TCP checks, and still could not express the case that matters most — a check that is down and then comes up.

**Advancing check status on service operations** rather than on reads. This reads naturally ("restart the service and the check recovers") but models a causal link that real Pebble does not have, and leaves a polling handler seeing a single frozen value.

**Recording operations on the output `Container`.** Rejected to keep `Container` symmetric in and out: the field would be meaningless on input, and `Context` already carries `exec_history` for exactly this kind of during-the-run record.

## Survey basis

The counts above come from a local mirror of 641 public charm repositories, grepped for the relevant patterns. They are rough by construction: a repository is counted once however many times it uses something, monorepos holding several charms count as one, the mirror is a snapshot rather than a live view, and "catches `ChangeError` outside its tests" is a proxy for "handles a failed Pebble operation" that will over- and under-count in different places. They are meant to show which of these situations charms actually get into, not to be precise.

The comparison that carries the most weight — 128 repositories handling `ChangeError` against 11 mentioning it in a test — is a lower bound on the gap either way, since mentioning the name in a test file is a generous reading of "tests this".

## Further information

* [Add support for testing pebble services interaction](https://github.com/canonical/operator/issues/1427)
* [OP039 — Process Execution Simulation in Ops Framework Testing](./OP039-process-execution-simulation-in-ops-framework-testing.md), which established the "the test declares the outcome" precedent this follows.
