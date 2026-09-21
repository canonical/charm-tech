# OP092 — Pebble `start-at` for scheduled service starts

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | 2026-06-29 |

<!-- mdtog begin hs=-1 -->

## Abstract

Pebble currently has no way to start a service on a recurring schedule. This
spec proposes a new optional `start-at` field on a service in the Pebble plan
that takes a [snapd timer
string](https://snapcraft.io/docs/timer-string-format) and causes Pebble to
start the service every time the timer fires.

## Rationale

Workloads frequently need to run a command, script, or short-lived service on
a recurring schedule — for example, a nightly backup, a periodic data import,
or a maintenance task. Today, charm authors who want this behaviour have to
work around Pebble by either:

- Embedding their own scheduling logic into the service's command (a wrapper
  process that sleeps and re-execs the real workload), or
- Running an external scheduler (cron, systemd timers, etc.) inside the
  workload container, which conflicts with Pebble being the single supervisor
  for charmed workloads, or
- Repurposing unrelated existing features as a scheduling side-effect — for
  example, using a Pebble check's `period` to trigger work via its `exec`
  command, or relying on Juju secret expiry/rotation events in the charm to
  drive periodic workload actions.

These options push complexity elsewhere, and bypass Pebble's service model.
Letting Pebble itself schedule a service start keeps everything inside the
plan and the existing service lifecycle.

## Specification

### Plan change

A new optional `start-at` field is added to each entry under `services` in a
Pebble layer:

```yaml
services:
    <service name>:
        override: merge | replace
        command: ...
        # (Optional) A snapd timer string describing when Pebble should
        # automatically start this service. Each time the timer fires,
        # Pebble starts the service as if `pebble start <service>` had
        # been invoked. If the service is already running when the
        # timer fires, the start is a no-op.
        start-at: <snapd timer string>
        ...
```

The value of `start-at` is a snapd timer string as defined in the [snapd timer
string format reference](https://snapcraft.io/docs/timer-string-format).

If `start-at` is unset (the default), the service's startup behaviour is
unchanged from today and is governed entirely by the existing `startup`
field.

### Semantics

- When the Pebble daemon starts, or when a `replan` resolves a plan in which
  a service has `start-at` set, Pebble computes the next firing time of the
  timer and schedules an internal start at that time.
- When the timer fires, Pebble starts the service exactly as `pebble start
  <service>` would: a `start` change is created, the usual notices are
  emitted, and the service goes through the normal `starting` → `running`
  state transitions. Failure handling (`on-failure`, backoff, etc.) is
  unchanged.
- If the service is already running when the timer fires, the start is a
  no-op (matching the behaviour of `pebble start` on an already-running
  service). The next firing is then scheduled as normal.
- Stopping the service manually (`pebble stop`) does not disable the timer:
  the service will be started again at the next firing. To stop a scheduled
  service permanently, the `start-at` field must be removed (or replaced)
  via a new layer.
- `start-at` is independent of `startup`. The two interact in the obvious
  way:
    - `startup: enabled` + `start-at: ...` — the service is started once when
      Pebble starts (or on replan), and additionally on every timer firing.
    - `startup: disabled` + `start-at: ...` — the service is *not* started
      when Pebble starts, but is started on every timer firing.
- An invalid `start-at` value (one that fails to parse as a snapd timer
  string) is a plan validation error, surfaced the same way as other plan
  errors (e.g. via `pebble add`, `pebble replan`, and on daemon startup).

### Layer merging

`start-at` follows the same merge rules as the other simple scalar fields on
a service:

- With `override: replace`, the new layer's `start-at` (or its absence)
  fully replaces the previous value.
- With `override: merge`, a non-empty `start-at` in the new layer replaces
  the previous value; an absent `start-at` leaves the previous value
  untouched. An explicit empty string clears the value, matching how other
  optional string fields on services behave.

### CLI / API

No new CLI commands are introduced by this spec. The existing
`pebble plan`, `pebble services`, and the `/v1/plan` and `/v1/services` API
responses gain the `start-at` field where the service schema is exposed,
mirroring how other optional service fields are surfaced today.

A future spec may add commands or API affordances for inspecting upcoming
firing times, manually triggering the next firing, or temporarily suspending
a timer without editing the plan; those are explicitly out of scope here.

## Examples

Run a backup service every day at 02:30:

```yaml
services:
    nightly-backup:
        override: replace
        startup: disabled
        command: /usr/local/bin/run-backup
        start-at: "02:30"
```

Run a metrics-flush service every 15 minutes:

```yaml
services:
    metrics-flush:
        override: replace
        startup: disabled
        command: /usr/local/bin/flush-metrics
        start-at: "00:00-24:00/96"
```

Run a weekly report on Mondays at a randomised time between 09:00 and 11:00:

```yaml
services:
    weekly-report:
        override: replace
        startup: disabled
        command: /usr/local/bin/weekly-report
        start-at: "mon,09:00~11:00"
```

## Alternative configuration

- `start-at`
- `schedule`
- `start-schedule`
- extend `startup` with timer string

## Full service layer specification

```yaml
# (Optional) A list of services managed by this configuration layer
services:
    <service name>:
        override: merge | replace
        command: <commmand>
        summary: <summary>
        description: |
            <description>
        startup: enabled | disabled

        # start-at
        start-at: <timer-string>
        # alternative
        startup: enabled | disabled | <timer-string>
        # future possible extension
        stop-at: <timer-string>

        after:
            - <other service name>
        before:
            - <other service name>
        requires:
            - <other service name>
        environment:
            <env var name>: <env var value>
        user: <username>
        user-id: <uid>
        group: <group name>
        group-id: <gid>
        working-dir: <directory>
        on-success: restart | shutdown | failure-shutdown | ignore
        on-failure: restart | shutdown | success-shutdown | ignore
        on-check-failure:
            <check name>: restart | shutdown | success-shutdown | ignore
        backoff-delay: <duration>
        backoff-factor: <factor>
        backoff-limit: <duration>
        kill-delay: <duration>
```

<!-- mdtog end -->
