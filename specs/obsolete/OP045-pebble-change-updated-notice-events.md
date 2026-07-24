# OP045 — Pebble Change Updated Notice Events

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2024-06-05 |

*We believe that there is value to Pebble consumers in having notices that are based on changes, when the consumer is read-only - for example, a "Pebble dashboard" that shows information about the current Pebble state, or providing status messages to a user, or the way that [snapd uses change notices for AppArmour prompting](https://docs.google.com/document/d/1tBnefdukP69EUJOlH8bgD2hrvZCYoE8-1ZlqRRYlOqc/edit?pli=1#heading=h.hy2udk42yl9e). The critical aspect here is that these consumers are not themselves making changes to the Pebble state.*

*However, within the Juju/charm context, a Kubernetes charm's main purpose is to manage the workload container state, generally through Pebble. The risk of charms inadvertently causing an infinite loop when handling events based on these notices is high, and the value of receiving all the events is low.*

*Our preference is to extend the current list of notice types that generate events to include new events when clear use cases exist, in future specs, and to not implement generic change-updated-notice events. change-updated-notices have value, but not as a source of generic Juju events, although we leave open the possibility that use-cases might arise in the future, and this could be reconsidered in that new light. **As such, this spec is rejected.***

## Abstract

In order to react to changes that Pebble makes in a container, Juju will add a new **{container-name}-pebble-change-updated-notice** event.

## Rationale

Unlike changes to the Juju state, changes in the Pebble state are currently not visible to charms, unless explicitly provided by **pebble notify**. When Pebble executes changes (such as service actions, check failure or recovery, and exec), Pebble creates a **change-updated** notice. We will expose this to Juju/charms through a new **{container-name}-pebble-change-updated-notice** event.

Charms can use this event to:

* React to a check reaching the failure threshold, or recovering.
* Provide additional diagnostic information in the Juju log.
* Debug issues while developing.

## Specification

#### Generate change-updated notices in Juju

Juju already polls Pebble for new notices, to support custom notices. This will be extended so that notices of type **change-updated** also generate events.

The Juju hook context will be the same as for other notice events: **NOTICE_KEY** and **NOTICE_TYPE**. Note that for change-update events, the notice key is always the Pebble Change ID, and the notice type will always be "change-updated". Charms are expected to query Pebble at the time the event is handled in order to get information about the current Pebble state.

Although Pebble is able to consolidate repeated notices (adjusting the **occurrences** and **last_occured** fields for repeats where no **repeat-after** is set or the repeat-after period has elapsed), change-updated notices do not set repeat-after, so a Juju event will be emitted every time the Change's status changes. This avoids the charm missing an update to a Change.

Juju could skip emitting events for a unit when a notice event with an identical (key, type) value is already pending. Since no additional context is included in the event, handling two events with identical context has no value.

The core change is adding a new notice type:

```
// worker/uniter/pebblenotices.go
switch notice.Type {
case client.CustomNotice:  // already exists
    eventType = container.CustomNoticeEvent
case client.ChangeUpdateNotice:
    eventType = container.ChangeUpdatedEvent
default: // already exists
    n.logger.Debugf("container %q: ignoring %s notice", containerName,
                    notice.Type)
    return nil
}
```

In ops, a new subclass of WorkloadEvent will be added. In addition, the testing Harness will gain support for getting changes.

```py
class Change:  # already exists
    id: ChangeID
    kind: str
    summary: str
    status: str
    tasks: List[Task]
    ready: bool
    err: Optional[str]
    spawn_time: datetime.datetime
    ready_time: Optional[datetime.datetime]
    data: Optional[Dict[str, Any]] = None

class PebbleChangeUpdatedEvent(WorkloadEvent):
    # Lazily fetched when more than `id` is required
    @property
    def change(self) -> Change: ...
```

Charms can now observe **pebble-change-updated-notice** events and act appropriately.

```py
# src/charm.py

class MyCharm(ops.CharmBase):
    def __init__(self, framework):
        super().__init__(framework)
        framework.observe(
            self.on.foo_pebble_change_updated_notice,
            self._on_change_notice,
        )

def _on_change_notice(self, event: ops.PebbleChangeUpdatedNoticeEvent):
    if event.notice.last_data['kind'] == 'replan':
        ...

# tests/unit/test_charm.py

def test_check_failed(harness: testing.Harness):
    harness.begin()
    harness.notify(
        NoticeType.CHANGE_UPDATED,
        'change',
        data={'kind': ChangeKind.PERFORM_CHECK, 'status': ChangeStatus.ERROR},
    )
    # assert that the expected action has been taken

```

### Remove the empty-task change notice

Pebble currently generates a change notice when the `Change` object is created. This has an [implicit status of `hold`](https://github.com/canonical/pebble/blob/22cdf7a75e97d506bc45fdf199d721f15b90d1e6/internals/overlord/state/change.go#L398), since there are no tasks yet, but is not the same as when the status is explicitly set to hold (and does not precisely match the documentation for `hold`: "HoldStatus means the task should not run for the moment").

This notice generation will be removed. Changes will first generate a notice when a task is processed (starting a service, executing a command, etc).

This is a breaking change in terms of notices. For example, previously a Pebble `exec` would generate three notices (with statuses `hold`, `do`, `done`) and will now only generate two.

## This does not decrease the risk of fan-out behaviour, but does reduce the overall volume of change-updated notices and change-updated notice events. All changes still result in at least one notice, and 'Pebble created a `Change` object' is an implementation detail that consumers do not need to know about - there are still notices before action is taken (via the change to `do` status).

## Further Information

Support for generating events based on Pebble change-update notices is outlined in [JU048](https://docs.google.com/document/d/16PJ85fefalQd7JbWSxkRWn0Ye-Hs8S1yE99eW7pk8fA/edit), and was previously implemented in Juju [#17118](https://github.com/juju/juju/pull/17118) (and exposed to ops in [#1170](https://github.com/canonical/operator/pull/1170)) and was reverted prior to appearing in any released version in Juju [#17191](https://github.com/juju/juju/pull/17191) and ops [#1189](https://github.com/canonical/operator/pull/1189). The revision was in response to fan-out behaviour observed in a charm that called Pebble exec on every event.

* [Diagram showing how the change-update statuses change over time](https://github.com/tonyandrewmeyer/notices-sim-poc/wiki/change%E2%80%90update-notices).
* [<100 lines of Go (with some supporting tools) that mimic how Juju polls Pebble for notices, for debugging purposes](https://github.com/tonyandrewmeyer/notices-sim-poc)
