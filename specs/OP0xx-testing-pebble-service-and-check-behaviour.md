# OP???: Testing Pebble service and check behaviour

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 31 Jul 2026 |
| Updated | 21 Oct 2026 |

There's a proof-of-concept implementation on the `tonyandrewmeyer/operator` fork. The service half is on [`scenario-notices-reach-state-out`](https://github.com/canonical/operator/compare/main...tonyandrewmeyer:operator:scenario-notices-reach-state-out) and [`scenario-service-behaviour-fails`](https://github.com/canonical/operator/compare/main...tonyandrewmeyer:operator:scenario-service-behaviour-fails) (these are the first two PRs below), with the rest of that line (`EXITS`, emitted notices, and the dependency rules) on [`claude/scenario-workload-mock-rebased-20260926`](https://github.com/canonical/operator/compare/main...tonyandrewmeyer:operator:claude/scenario-workload-mock-rebased-20260926). The check half is on fork PRs [#29](https://github.com/tonyandrewmeyer/operator/pull/29), [#30](https://github.com/tonyandrewmeyer/operator/pull/30), [#33](https://github.com/tonyandrewmeyer/operator/pull/33) and [#34](https://github.com/tonyandrewmeyer/operator/pull/34). Those predate the service work and will need rebasing onto it.

## Abstract

`ops.testing` models a container's Pebble as a store of state that the charm reads and writes, not as something that does anything of its own. A service the charm starts always starts. A check's status is whatever the test seeded, and never changes. Only the charm can produce a notice, and the output state records where each service ended up but not how it got there. So the parts of a charm that deal with the workload misbehaving (which are the parts most worth testing, I think) are the parts that can't be unit tested at all.

This spec proposes that a test can declare what the workload does (a service that fails to start, a service that exits later, a service that notifies Pebble when it's ready, a check that comes up on the third poll), and that `ops.testing` then reproduces what Pebble does in response: the error the charm sees, the status each service ends up in, and the services Pebble starts, stops or holds along the way because of `requires`, `before` and `after`. It also proposes a record of what the charm asked Pebble to do, so that a restart can be told apart from a start, and it brings the shape of a check's change into line with real Pebble.

The work is split into rounds, and the first round is small on purpose: a bug fix for notices, then declaring that a service fails to start, exits, or emits notices. The dependency rules and the check work come after those have landed.

## Rationale

### Distinguishing a restart from a start

A charm that reconfigures its workload writes the new layer and then restarts the service. If it calls `start()` instead of `restart()`, the service is already running, so Pebble does nothing and the workload keeps running with the old configuration. You can't see from the output state whether that mistake was made: the only evidence afterwards is `container.service_statuses['myapp'] == ServiceStatus.ACTIVE`, which is true either way. A refactor that swaps one call for the other leaves every existing test passing.

Charms that want to assert on this monkeypatch `ops.model.Container.restart`. In [airflow-core-operators](https://github.com/canonical/airflow-core-operators), each of the four charms has Scenario tests that patch it and then `restart_mock.assert_called_once()` or `assert_not_called()`, which is the assertion the output state can't support. [postgresql-k8s-operator](https://github.com/canonical/postgresql-k8s-operator), [kafka-operator](https://github.com/canonical/kafka-operator), [zookeeper-operator](https://github.com/canonical/zookeeper-operator) and their Kubernetes counterparts patch the same method. That couples the test to an ops implementation detail, and it asserts that the charm called a particular method rather than that the workload ended up in the right state.

### Testing what the charm does when the workload doesn't come up

Charms do handle `ops.pebble.ChangeError` and set a blocked or error status in response: of the 641 charm repositories surveyed (see [Survey basis](#survey-basis)), 128 catch it somewhere outside their tests. There's no way to provoke that path, because in `ops.testing` a service that's asked to start always starts. Only 11 of those 128 mention `ChangeError` anywhere in their test suites, so for most of them the handler that matters when a deployment is broken is the one with no test coverage.

Where it is tested, it's tested by patching. [cos-coordinated-workers](https://github.com/canonical/cos-coordinated-workers) replaces `ops.model.Container.restart` with a function that raises, under the comment `# WHEN service restart fails`, and the test that follows notes that "technically an `ops.pebble.ChangeError` [is raised] but the context manager doesn't catch it for some reason". The test can't rely on the error being shaped the way Pebble shapes it, because nothing in `ops.testing` produced it.

### Testing a charm whose layer has dependencies

A layer can say that one service `requires` another, or must start `before` or `after` it. Pebble acts on those: starting a service also starts what it requires, stopping a service also stops what requires it, a service whose dependency failed to start is held rather than started, and a layer whose ordering has a loop is rejected. `ops.testing` does none of this today. Only the named service changes status, whatever the layer says - a charm that relies on `requires` to bring up a sidecar can't see in a test that the sidecar came up, and a charm that gets a layer's ordering wrong can't see that Pebble would refuse it.

This matters more once a service can fail, because the interesting question is then not "did `myapp` fail" but "what happened to the services that depend on it", and a charm that handles the failure needs to know which services it's now responsible for.

### Testing a charm that waits for a check

A charm that polls a health check until the workload is ready, and branches on what it finds, can only ever be tested against one outcome, because a seeded `CheckInfo`'s status is fixed for the whole run. Testing both branches ("still coming up, defer" and "up, carry on") needs a check whose status can change.

A charm that names a check in a service's `on-check-failure` has a related problem: it's delegating recovery to Pebble. 19 of the surveyed repositories set `on-check-failure`, including [datahub-k8s-operator](https://github.com/canonical/datahub-k8s-operator) (`{'up': 'restart'}`) and [mediawiki-k8s-operator](https://github.com/canonical/mediawiki-k8s-operator) (`{'git-sync-alive': 'restart'}`). Nothing in `ops.testing` models what Pebble then does, so the furthest a test can go is to assert that the plan says so. That's what datahub's test does, checking `on_check_failure.get('up') == 'restart'` under the docstring "Healthcheck services wire `up` to on-check-failure: restart." Whether the recovery actually happens isn't something a unit test can reach.

### Testing a charm that responds to its workload

A workload can notify Pebble once it's up, and the charm then handles a `pebble-custom-notice` event on a later run. This is a minority pattern (seven of the surveyed repositories observe the event, among them [k6-k8s-operator](https://github.com/canonical/k6-k8s-operator), [notary-k8s-operator](https://github.com/canonical/notary-k8s-operator), [github-profiles-automator](https://github.com/canonical/github-profiles-automator) and [charm-rabbitmq-k8s](https://github.com/canonical/charm-rabbitmq-k8s)), but where it's used, the charm depends on it.

`ops.testing` can seed such a notice in the input state, but nothing during a run can produce one, so a test has to hand-seed the notice that the previous run should have produced. k6's `test_done_notice_sets_unit_idle` builds `testing.Notice(key='k6.com/done')`, rebuilds its container to attach it, and runs the notice event against that. That's a reasonable test of the handler, but it can't check that starting the service is what produces the notice.

### What charms do instead today

Mostly, they don't test any of this, or they push it to integration tests, where a workload failure is slow and awkward to arrange. The counts above are the evidence: 128 repositories handle a Pebble `ChangeError`, and 11 of them mention `ChangeError` in a test.

Where charms do test in this area, it's by asserting on the plan. 44 of the surveyed repositories compare a plan or a layer against an expected dictionary in their tests. [temporal-k8s-operator](https://github.com/canonical/temporal-k8s-operator) is typical: its Scenario test asserts the whole service dictionary, `on-check-failure` entry included. That covers the charm's intent, but says nothing about what happens when the workload doesn't cooperate.

Asserting on the plan is a good fit for a reconciler charm, which generates a plan and lets Pebble decide whether anything needs restarting. This proposal doesn't push charms away from that style: recording the operations the charm performed is an observation, not an instruction to write imperative charms. It happens to be the only way to observe a Pebble-initiated restart, which a reconciler charm relies on more than an imperative one does.

This is issue [#1427](https://github.com/canonical/operator/issues/1427), although that issue only asks for a `restarted` flag on the output state. A flag answers "was it restarted at all", which is the smallest of the questions above, and answers it in a form that can't be extended to ordering, to arguments, or to the reason.

## Specification

The behaviour modelled below was taken from the Pebble source (`internals/overlord/servstate/handlers.go` and `manager.go`) and confirmed by driving `ops.pebble.Client` and the `pebble` CLI against a running Pebble 1.32. Where this proposal leaves something unmodelled, that's a scope decision with a reason, given in [Limitations](#limitations). Those cases raise `NotImplementedError`, so a test that asks for them fails loudly rather than quietly getting a made-up answer.

The design principle throughout is the one `Exec` established: the test declares what the workload does, and `ops.testing` doesn't try to simulate the workload or derive its behaviour from the plan. What `ops.testing` does reproduce is Pebble's own reaction to what was declared, because that's deterministic (it's all in Pebble's source) and is what a charm actually has to handle.

### Notices a charm records survive the run

Notices the charm records with `pebble.notify()` are visible to the charm through `get_notices()` while the run is in progress, but are dropped from the output state. They should survive the run, as they do in Pebble. This is a bug regardless of the rest of this spec, and the fix goes up first and on its own, because the emitted-notices feature below depends on it.

A test that asserted the old empty `notices` on the output container would change. I don't know of any such test.

### Declaring what a service does when it starts

`ServiceBehaviour` says what happens to one named service when the charm starts it:

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

`Container.service_behaviours` is a frozen set, mirroring `Container.execs`, and a behaviour hashes on its service name, so a container holds at most one behaviour per service.

`ServiceStart` has three members:

* `RUNS`: the service comes up and stays up. This is the default, so no existing test changes.
* `FAILS`: the service never comes up, and `start()`, `restart()`, `replan()` and `autostart()` raise `ops.pebble.ChangeError`, as real Pebble does.
* `EXITS`: the service comes up, and exits some time later. The call that started it succeeds, and the crash shows up in the status afterwards.

The `FAILS`/`EXITS` split isn't a matter of degree. Pebble marks a start task `Done` once the service has stayed up for one second (`okayDelay`), so an exit inside that window fails the call that started it and an exit after it doesn't. A charm handles the two completely differently (one is an exception to catch, the other is a status to notice on a later hook), so a test needs to be able to ask for either.

Two further fields refine each case. `ServiceBehaviour.failure_mode` says how a `FAILS` service fails: `ServiceFailureMode.CRASH` (the default, where the command runs and exits immediately) or `ServiceFailureMode.EXEC_ERROR` (the command couldn't be run at all, for example because the binary is missing). The resulting status differs: `EXEC_ERROR` always leaves the service `INACTIVE`, since the process never started, whereas `CRASH` depends on the service's `on-failure` policy. `ServiceBehaviour.exit_code` says whether an `EXITS` service's exit was clean (`ServiceExitCode.SUCCESS`) or not (`ServiceExitCode.FAILURE`, the default), which decides whether `on-success` or `on-failure` governs the result.

In every case the resulting status is derived from the plan the way Pebble derives it, including the odd bits. With `on-failure: ignore` a crashed service is `ERROR`, and with `on-success: ignore` a cleanly exited one is `INACTIVE`. With the default `restart` policy, either reports the raw string `'backoff'`, which isn't a member of `ops.pebble.ServiceStatus`. `ServiceInfo.current` is already typed `ServiceStatus | str` for this reason, and `Container.service_statuses` on the output state is widened to match, from `Mapping[str, ServiceStatus]` to `Mapping[str, ServiceStatus | str]`. Matching the existing type seems better than adding an enum member that Pebble doesn't have, but it's a change to a public type, so it's the first of two decisions I'd like agreement on.

The `ChangeError` a `FAILS` service raises has the error text, change kind, summary and task list that Pebble gives for the same situation. The text is `cannot perform the following tasks:` followed by one line per failed task, and the reason on that line is Pebble's: `service start attempt: exited quickly with code 1, will restart` for a crash under the default policy, or `cannot start service: fork/exec <command>: no such file or directory` for an exec error. Other services started in the same call still come up (Pebble tracks each service's start attempt independently), and they aren't named in the error.

The default is not strict. With `Exec`, a command that nothing matches is an error, because an unmocked exec is usually a test bug. Here a service with no declared behaviour runs, exactly as it does today. That keeps every existing test passing unchanged, although it does mean that a typo in the service name silently does nothing. This is the second decision.

### Declaring the notices a service sends

A `ServiceBehaviour` can say what the workload notifies Pebble about when it starts:

```python
ServiceBehaviour('myapp', emits=[Notice('example.com/started')])
```

The notices are recorded when the service starts (through `start()`, `restart()`, `replan()` or `autostart()`), and are visible both to the charm during that run and in the output state. The output state part is the useful bit: it can be fed straight into the run that handles the notice, so the whole sequence is one test rather than two disconnected ones.

```python
state_out = ctx.run(ctx.on.config_changed(), state)
container_out = state_out.get_container('workload')
(notice,) = container_out.notices

ctx.run(
    ctx.on.pebble_custom_notice(container=container_out, notice=notice),
    state_out,
)
```

A `FAILS` service never starts, so it emits nothing. An `EXITS` service does start, so it emits. A service starting alongside a failing one still emits. Only the type, key and data are taken from the declared `Notice`. The ID, timestamps and occurrence count are assigned the way Pebble assigns them, so starting a service twice in one run gives one notice with two occurrences rather than two notices.

### Following the layer's dependency rules

Once a service can fail, what Pebble does with the services around it matters, and `ops.testing` should do the same. These rules are taken from Pebble's service manager, and each was checked against a running Pebble. They apply whether or not any `ServiceBehaviour` is declared, so they're the one part of this proposal that changes what an existing test can observe. A layer with no `requires`, `before` or `after` is unaffected.

*Ordering.* The tasks in a start change, and the lines in a `ChangeError`, follow `before` and `after`, with Pebble's alphabetical tie-break for any pair the layer leaves unordered. A stop change uses the reverse order. `stop_services` gets a real task list (one `stop` task per service) where today it has none.

*Membership.* Starting a service also starts every service it transitively `requires`. Stopping a service also stops every service that transitively requires it, dependants first. `restart` is a stop pass followed by a start pass, and the two differ: the stop pass covers only the services the charm named, while the start pass covers their full `requires` closure. `replan` and `autostart` behave as `start` does over the services with `startup: enabled`. `before` and `after` play no part in membership, and `requires` plays no part in ordering, because Pebble keeps the two apart.

*Holding.* Pebble runs a change's tasks in lanes, one lane per group of services connected by `requires` edges within the change, and runs the tasks in a lane one after another. When a task in a lane fails, every later task in that lane is held: its task status is `Hold`, the service stays `INACTIVE`, it emits no notices, and it isn't named in the error, which lists only the services that actually failed. Services in other lanes are unaffected. The rule follows the lane rather than the `requires` edges directly, and that has two consequences: a service later in a lane is held even when the service it requires didn't itself fail, and a service declared `FAILS` that sits behind a failure in its lane holds rather than failing. A service related only by `before` or `after` to a failed one isn't held, because Pebble doesn't hold it either.

*Loops.* `add_layer` fails the way Pebble does for a plan whose services form a `before`/`after` loop, raising `400 Bad Request: services in before/after loop: <names>` rather than accepting the plan, where the names are the members of the loop. A service ordered after itself isn't a loop. When a plan has more than one loop, which one Pebble names depends on the order the services and their `after` lists are written in. The proof of concept reproduces that too, but a charm can't branch on the names in that message, so it's the first thing to drop if it complicates review.

A test that asserted a `requires`-dependant stayed `INACTIVE` after its dependency was started, or that an ordering loop was accepted, would change. Neither is something a test should have been asserting, since neither is a state real Pebble can be in.

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

The sequence advances one entry each time the charm reads that check. Reads of other checks don't advance it. Once the sequence is exhausted the last entry repeats, so a charm that polls until the check comes up settles on the final status rather than running off the end, and the test doesn't have to count reads exactly.

Advancing on reads rather than on service operations is a deliberate choice. In real Pebble a check's status changes when its own period elapses. Starting, stopping or replanning a service doesn't change it. `ops.testing` has no clock, so a read is the closest observable stand-in for time passing. Tying the sequence to service operations would model a causal link that doesn't exist, and would leave a polling handler seeing one frozen value. The cost is that reads are no longer side-effect free: a handler that logs the status and then branches on it consumes two entries.

Everything else the charm can see about the check follows from the declared statuses, derived as Pebble derives it, rather than being seeded separately and going stale. The failure count reaches the threshold when the check goes down and keeps climbing while it stays down. The success count freezes while the check is down and restarts from one on recovery. The change ID moves to a fresh `recover-check` on failure and a fresh `perform-check` on recovery, with the abandoned change settling at `Error` or `Done`. Each transition emits the `change-update` notice that Pebble emits.

`CheckBehaviour` also takes an optional `failure_message`, which is what Pebble puts in the failed change's `err` and task log, such as `'exit status 1'` for an exec check or `'received non-20x status code 500'` for an HTTP one. A charm that wants to report why a check failed has to read that text, and can't do so today. Without a `failure_message` the change carries no error text: `ops.testing` can't know why a declared check failed, and shouldn't invent a reason.

As with services, this isn't strict. A check with no declared behaviour keeps reporting its seeded status, because a check that just sits there is a normal thing for a test to want.

### Inspecting what the charm asked Pebble to do

The service statuses in the output state say where the workload ended up. A per-container operation history on `Context` says how it got there, following the `exec_history` precedent:

```python
state_out = ctx.run(ctx.on.config_changed(), state)
assert ctx.service_ops_history['workload'] == [ServiceOp('restart', ('myapp',))]
```

This is what distinguishes a `start()` from a `restart()`, and what makes ordering assertions possible. `Context.get_service_ops(container, service=None)` filters to the operations involving a single service, for the common case.

For `replan` and `autostart`, the recorded service list is the services with `startup: enabled` in the plan at the time of the call. That's the charm's intent, captured before the underlying client filters out the services that are already running. Calls that raise `ConnectionError` because the container can't be reached aren't recorded.

`add_layer_history` records `Container.add_layer()` calls in the same shape, so a test can assert on layer ordering as well.

The history is on `Context` rather than on the output `Container` because a `service_ops` field on an input `Container` would have no meaning, and because accumulating into a frozen dataclass during a run needs a parallel mutable accumulator anyway.

### Modelling what Pebble does on its own

A service can name a check in its `on-check-failure`, and Pebble restarts that service when the check goes down. A charm that relies on this is relying on Pebble to recover its workload, and today there's no way to test that the wiring is right.

With a check that can be made to go down, and somewhere to record the consequence, this becomes expressible:

```python
assert ctx.service_ops_history['workload'] == [
    ServiceOp('restart', ('myapp',), caused_by='up-check'),
]
```

`ServiceOp.caused_by` is the name of the check whose failure made Pebble act, or `None` when the charm invoked the operation itself, so every existing `ServiceOp(...)` comparison keeps working.

The recorded operation is the only evidence available. Checked against a running Pebble, the service passes through `backoff` and lands back on the `ACTIVE` it already had, and Pebble records no change for the restart it performs. So a status-and-changes view of the output state is identical whether or not the restart happened.

The action fires once per transition into `DOWN`, not on every read of a check that's already down.

Pebble's `checkFailed` acts on a service in three states (running, in backoff, and exited) and ignores the failure in any other state, including stopped. A running service is terminated and then restarted through backoff. A service already in backoff waits out the backoff it's in, and nothing further happens. An exited service goes straight into backoff. This proposal models the running case, which is the one a charm sets `on-check-failure` for. The backoff and exited cases need a service that's already mid-backoff or crashed at the point the check goes down, which means composing `ServiceBehaviour` with `CheckBehaviour` across a run. That's worth doing, but can wait until both are in.

### Making a check's change look like Pebble's

The reason a check failed is carried on the check's change (its `err`, or its task log), so that's what a charm reporting the reason has to read. What `ops.testing` and `Harness` produce there doesn't match real Pebble, so a test that exercises such a charm would be asserting against a shape the charm will never see in production. Both should produce:

* A change summary in Pebble's shape, `Perform exec check "up"` (the action, the check's type and the quoted name), rather than the bare check name.
* Exactly one task on the change, sharing the change's kind and summary, rather than no tasks at all.
* A change registered under the check's own change ID, so that `get_change(info.change_id).id` round-trips, with no ready time while the change is still `Doing`, and with no change at all for an inactive check, which is what real Pebble has.
* A stopped check's change settled at `Done`, whether the check was up or down, and no change ID reported, rather than an aborted change and an empty-string change ID.
* A freshly started check reporting neither a failure count nor a success count, rather than resetting only the failure count.

The check type in the summary comes from the plan, so a check that exists only in seeded test state (a state real Pebble can't be in) gets `Perform check "up"`, with the type omitted.

These are corrections rather than new features, and they apply to `Harness` as well as to `ops.testing`. The declared behaviours above are `ops.testing` only.

## Delivery

The proof of concept is one branch per line, and neither is reviewable in one sitting (the service line alone is about 4,500 added lines, most of them tests). It goes upstream as a sequence of small PRs, each useful on its own, in this order:

1. Notices a charm creates during a run reach the output state. A bug fix, about 60 lines, with one test.
2. `ServiceBehaviour` with `FAILS`, plus the `service_statuses` type widening and the `ops.testing` re-exports and reference docs for the new names.
3. `EXITS`.
4. Emitted notices.

Those four answer #1427. The two decisions above (the `service_statuses` widening and the non-strict default) should be agreed before the second PR goes up, since both are visible in its diff. They're set out under [Declaring what a service does when it starts](#declaring-what-a-service-does-when-it-starts).

The dependency rules follow as a second round, once the first has landed: ordering, then `requires` on start (membership and holding together, because membership alone leaves a failed dependency's dependants in a state Pebble never produces), then `requires` on stop and restart, then loop rejection. Each is already separable on the proof-of-concept branch. If reviewers would rather not have them at all, the first four PRs stand without them, and `ops.testing` just keeps starting only the services it's told to.

The check work (`CheckBehaviour`, the check-change corrections, the operation history, and `on-check-failure`) is a third round. It was built against an older `main` and shares no code with the service line, so it needs rebasing onto whatever has merged by then. The check-change corrections go first, because they're independent of everything else and fix `Harness` as well.

## Limitations

`ops.testing` has no clock, and this proposal doesn't add one. Check statuses advance on reads, and nothing expresses "after thirty seconds". A test that wants a specific number of transitions still has to reason about how many times its charm reads the check.

The workload itself isn't simulated. A check's status is declared by the test, not derived from an `Exec` handler, from an HTTP endpoint, or from the plan. Expressing "given this environment variable in the plan, the health check passes" would need a workload mock with its own API, which is a much larger design and isn't proposed here.

The shutdown policies aren't modelled, and that's a decision rather than an open question. Pebble does two things with them: it calls `HandleRestart` to bring the daemon down, and it moves the service to its exited state, which shows up as `ServiceStatus.ERROR`. (`on-success` also accepts `failure-shutdown`, and `on-failure` and `on-check-failure` accept `success-shutdown`, so a service can be made to bring the daemon down the other way round, and the plain `shutdown` action picks the matching one from the exit code.) The status half is easy to model, but modelling it alone would be worse than not modelling it. The consequence the charm sees from a shutdown is the daemon going down and, under Juju, the container being recycled, and an `ops.testing` run has no daemon and no container lifecycle to express that with. A test that saw `ERROR` and nothing else would be getting half the story. So these raise `NotImplementedError`, and modelling them properly waits until `ops.testing` has some notion of the container going away.

`on-check-failure` leaves stopped services alone, and this is Pebble's behaviour rather than a gap: `checkFailed` acts only on a service that's running, in backoff, or exited, and logs and ignores the failure in every other state. The states this proposal doesn't yet cover (backoff and exited) are described in [Modelling what Pebble does on its own](#modelling-what-pebble-does-on-its-own).

Service log output isn't modelled, because there's nothing yet for a test to assert against. Pebble keeps a per-service ring buffer and serves it from `/v1/logs`, but `ops.pebble.Client` doesn't expose it, so a charm can't read service logs through ops at all. If that API is added, declaring a service's output belongs with it.

## Alternatives considered

The original issue suggests a `restarted` flag on the output container. This answers only "did a restart happen at all". It can't express ordering, which services were named, or that Pebble rather than the charm was responsible, and there's no clean way to grow it into something that can.

The dependency rules could be left out entirely, on the grounds that reproducing them starts to look like simulating Pebble rather than declaring outcomes. There's something to this, and it's why they're a second round rather than part of the first. But the line this spec draws is between the workload, which the test declares, and Pebble, which `ops.testing` already stands in for. A service that comes up when started is Pebble's behaviour, and so is a dependant that's held when its dependency fails. Declaring the latter by hand in every test would mean every test author re-deriving Pebble's rules, and getting them wrong in ways the test couldn't detect.

Check status could be derived from the plan or from `Exec` handlers. This would tie a check's outcome to exec mocking, wouldn't work for HTTP or TCP checks, and still couldn't express the case that matters most, a check that's down and then comes up.

Check status could advance on service operations rather than on reads. This reads naturally ("restart the service and the check recovers") but models a causal link that real Pebble doesn't have, and leaves a polling handler seeing a single frozen value.

Operations could be recorded on the output `Container`. I'd rather keep `Container` symmetric in and out: the field would be meaningless on input, and `Context` already carries `exec_history` for exactly this kind of during-the-run record.

`ServiceBehaviour` could have a strict default, matching `Exec`. That would break every existing test that starts a service, for a benefit (catching a mistyped service name) that a test's own assertions on the status already provide.

## Survey basis

The counts above come from a local mirror of 641 public charm repositories, grepped for the relevant patterns. They're rough by construction: a repository is counted once however many times it uses something, monorepos holding several charms count as one, the mirror is a snapshot rather than a live view, and "catches `ChangeError` outside its tests" is a proxy for "handles a failed Pebble operation" that will over- and under-count in different places. They're meant to show which of these situations charms actually get into, not to be precise.

The comparison that carries the most weight (128 repositories handling `ChangeError` against 11 mentioning it in a test) is a lower bound on the gap either way, since mentioning the name in a test file is a generous reading of "tests this".

## Further information

* [Add support for testing pebble services interaction](https://github.com/canonical/operator/issues/1427)
* [OP039: Process Execution Simulation in Ops Framework Testing](./OP039-process-execution-simulation-in-ops-framework-testing.md), which established the "the test declares the outcome" precedent this follows.
