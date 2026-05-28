# OP046 — Pebble Check Events

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Implementation |
| Created | 2024-06-20 |

Implemented in [Juju#17655](https://github.com/juju/juju/pull/17655), [Juju/charm#432](https://github.com/juju/charm/pull/432), [ops#1281](https://github.com/canonical/operator/pull/1281), [pebble#444](https://github.com/canonical/pebble/pull/444), [jhack#172](https://github.com/canonical/jhack/pull/172), [Scenario#151](https://github.com/canonical/ops-scenario/pull/151)

## Abstract

When Pebble checks start (or finish) failing, charms may wish to react. To support this, a new pair of Juju events will be added: **{container-name}-pebble-check-failed** and **{container-name}-pebble-check-recovered**.

## Rationale

Charms can add health checks via Pebble plans, and the service plan can indicate that a service should be restarted or Pebble should be shut down on failure of specific checks. However, a charm is not notified when a check has failed (or has recovered), so is unable to take more extensive action. A charm could use Pebble to poll the configured checks, but this is a poor fit for the event-based charm system.

When the number of failed checks exceeds the configured threshold, and a check moves to a failing status ("down"), a charm might want to, for example:

* Set a unit or app status with an appropriate message, such as  `ActiveStatus('Queuing email - destination server unavailable')`
* Surface additional diagnostic information, such as sending `'Sidekiq unreachable - last log message: ... see Loki for more details'` to the Juju debug-log
* Adjust configuration in an attempt to restore functionality, such as increasing throttling in response to high load

## Specification

In Juju, we will add two new workload events. These are triggered by a new addition to the Pebble Notices poller's list of actionable notices, which has a new sub-list of actionable change-updated notices, based on the data field of the notice.

```
// worker/uniter/pebblenotices.go
switch notice.Type {
case client.CustomNotice:  // already exists
    eventType = container.CustomNoticeEvent
case client.ChangeUpdateNotice:
    data := notice.LastData
    if data["kind"] == "perform-check" || data["kind"] == "recover-check" {
        // We always look for the final status (Done, Error), because
        // the status might have changed since the notice was updated
        // and now. We know that the notice for the change will never
        // update from Done/Error to anything else, so cannot miss
        // the change entirely.
        chg, err := pebbleClient.Change(notice.key)
        if err != nil { ... }

        switch {
        case data["kind"] == "perform-check" && chg.Status() == "Error":
            eventType = container.CheckFailedEvent
        case data["kind"] == "recover-check" && chg.Status() == "Done":
            eventType = container.CheckRecoveredEvent
        }
    }
default: // already exists
    n.logger.Debugf("container %q: ignoring %s notice", containerName,
                    notice.Type)
    return nil
}
```

Juju will provide only the check name as the environment context for the event. To simplify this, Pebble will add the check name to the data map for recover-check and perform-check change-updated notices (this value does not change for the lifetime of the notice - it is just another key, not the actual data).

In ops, two new subclasses of WorkloadEvent will be added. In addition, the testing Harness will gain support for getting checks and changes.

```py
class CheckInfo:  # already exists
    name: str
    level: CheckLevel | str | None
    threshold: int
    status: CheckStatus | str
    failures: int
    change_id: ChangeID | None

class PebbleCheckRecoveredEvent(WorkloadEvent):
    # Lazily fetched when more than `name` is required
    @property
    def info(self) -> CheckInfo: ...

class PebbleCheckFailedEvent(WorkloadEvent):
    # Lazily fetched when more than `name` is required
    @property
    def info(self) -> CheckInfo: ...
```

Charms can now observe **pebble-check-recovered** and **pebble-check-failed** events and act appropriately.

```py
# src/charm.py

class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        framework.observe(
            self.on.foo_pebble_check_recovered,
            self._on_check_recovered,
        )
        framework.observe(
            self.on.foo_pebble_check_failed,
            self._on_check_failed,
        )

def _on_check_failed(self, event: ops.PebbleCheckFailedEvent):
    # Note that the check might have recovered by the time we get
    # here, so it's likely that you always want to have a guard
    # like `if event.info.status == CheckStatus.DOWN` in here.
    if event.info.name == 'http-check':
        ...

def _on_check_recovered(self, event: ops.PebbleCheckRecoveredEvent):
    # Similarly, the check might have started failing (again) at
    # this point, so you may need to have a check for the current
    # status, depending on what this does (handlers for failure
    # seem more likely).
    if event.info.name == 'http-check':
        ...

# tests/unit/test_charm.py

def test_check_failed_harness(harness: testing.Harness):
    # Consider higher-level APIs like this:
    harness.fail_check('container', 'check'[, failures=3])
    harness.recover_check('container', 'check')
    # What it would like without adding anything:
    patch_pebble_client_to_add_checks()
    harness.charm.on.foo_pebble_failed.emit('check')
    # Original:
    change_id = harness.add_pebble_change(
        container_name='foo',
        kind=ChangeKind.PERFORM_CHECK,
        status=ChangeStatus.ERROR,
    )
    harness.set_pebble_check_info(
        container_name='foo',
        name='http-check',
        status=CheckStatus.DOWN,
        failures=3,
        change_id=change_id,
    )
    harness.begin()
    harness.notify(
        NoticeType.CHANGE_UPDATED,
        change_id,
        data={'kind': ChangeKind.PERFORM_CHECK, 'check_name': 'http-check'},
    )
    # assert that the expected action has been taken

def test_check_failed_scenario(context: Context):
    check = Check('http-check', status=CheckStatus.DOWN, failures=4)
    container = Container(
        'foo',
        can_connect=True,
        layers={...},
        checks={check},
    )
    state_in = State(containers={container})
    state_out = context.run(
        context.on.pebble_check_failed(
            container=container,
            check=check,
        ),
        state=state_in,
    )
    # assert that the output state is as expected
```

We will add both `pebble-check-failed` and `pebble-check-recovered` events as this is a change of the system state (consistent with `storage-attached`/`storage-detached`, `relation-joined`/`relation-departed`) rather than a single `pebble-check-changed` event (`relation-changed`, `secret-changed`, `config-changed` indicate updated values of objects in the state, not a change of the state).

In addition, a single event would require always checking whether the check had passed the fail threshold or had started passing, which is boilerplate and easily missed by charmers. As long as the charm logic is ok with some 'flip-flopping' (for example, a status blipping to non-active and then back) the case where a `pebble-check-recovered` is received immediately after `pebble-check-failed` because the check had recovered by then still doesn't require getting the current check status. When blipping is undesirable (e.g. involves restarting a service twice), the charm code would need to query the live check status.

## Further Information

* Pebble Notices were added in [JU048](https://docs.google.com/document/d/16PJ85fefalQd7JbWSxkRWn0Ye-Hs8S1yE99eW7pk8fA/edit).
* Pebble checks were added in [JU011](https://docs.google.com/document/d/1d6-h3UAt2VPUSvlkVF30l8iuDW8raRNkHbp5M6NUo1A/edit).
* Pebble checks were changed to use the changes and tasks system in [JU073](https://docs.google.com/document/d/1VbdRtcoU0igd64YBLW5jwDQXmA6B_0kepVtzvdxw7Cw/edit).
* An earlier proposal to generate generic change-updated-notice events was rejected in [OP045](https://docs.google.com/document/d/1EgRwMarsAOB04zWdSpcHbP0VykRApxQlyNFF1oC2Gzw/edit).
