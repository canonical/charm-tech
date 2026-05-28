# OP051 — Auto restart services failed within okay delay if startup enabled

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2024-11-07 |

## Abstract

Pebble does not try to restart services if they exit too quickly.

## Background

Pebble has an "okay delay" period internally set to 1 second.

When starting a service, Pebble executes the service's command, sets the state of the service as "starting", then waits for the okay delay period to ensure the command doesn't exit too quickly:

- If the command doesn't exit within the okay delay period, the service state is transferred from "starting" to "running", and the start is considered successful.
- If the service exits within the okayDelay period in the state "starting", the task will end up with an error.

Pebble also has a feature that automatically restarts services that exit unexpectedly. This is enabled by default unless explicitly disabled.

However, the auto restart feature currently only works for services in the "running" state. That is to say, if a service exists after the okay delay period, it will be restarted automatically by Pebble; but if the service exits within the okay delay period (still in the state "starting"), it will not be restarted by Pebble.

## Rationale

The current behaviour described above has caused a few issues, for example, [this one here](https://github.com/canonical/pebble/issues/240) where the service exists quickly because its dependencies are not met yet, and it will never be restarted, which is not what the charmers expected.

In this spec, we are proposing a new feature where if the service is configured as `startup: enabled` in the layer config, it will be automatically restarted even if it exists within the okay delay period. To be precise, this is more of a "bug fix", because previously, if a service is configured as `startup: enabled` and exits too quickly, Pebble won't retry to make sure it's started, although this is what `startup: enabled` implies.

This feature is requested by a charmer of the [kfp-operators](https://github.com/canonical/kfp-operators/issues/220) charm, and it will close [issue 240](https://github.com/canonical/pebble/issues/240).

## Option 1 Specification (Rejected)

No change to the configuration is required.

If a service is configured as `startup: enabled` in the layer config, when the service starts and if it fails within the okay delay period, restart it.

This can be achieved in multiple ways, but after internal discussion, the best way to do so is to skip the "starting" state for services with `startup: enabled` and put it directly into the running state.

This essentially skips the okayDelay check and hand over the backoff/restart part to Pebble. See PoC below. This method has a few advantages, for example:

- A much lower backward compatibility impact, because it only affects services configured with `startup: enabled` and if they fail within the 1s okay delay.
- Doesn't affect other Pebble commands like `pebble start`, because services started by `pebble start` and fail within the 1s okay delay still won't be restarted, same as the current behaviour.
- Doesn't interfere with other configurations like `on-failure`.

See the state transfer diagram below, the red line is what is proposed in this spec:

![][image1]
Sample usage/layer config example:

```
summary: a simple layer
services:
  test:
    override: replace
    command: bash -c "sleep 0.1; exit 0"
    startup: enabled
```

## Option 2 Specification (Approved)

No change to the configuration is required.

Always restart the service if it's configured as `on-failure: restart` (which is the default) if the service fails to start, no matter if it fails within or without the okayDelay, and no matter if the start comes from `pebble start`, daemon start, or replan.

This can be achieved by allowing the state to transfer from "starting" to "backoff" so that Pebble will take over to handle the restart.

See the state transfer diagram below, the red line is what is proposed in this spec:

**![][image2]**

The task for starting the service should return an error message mentioning that Pebble will keep trying to start it.

See "Notes from Nov 14 Review Meeting" for the final decision.

## Further Information

* [PoC](https://github.com/canonical/pebble/pull/514): always restart services if on-failure is "restart", no matter if it's configured as `startup: enabled` or not,  no matter if it's started by `pebble start` or by starting daemon or by replan. (After review, this is preferred.)
* [PoC2:](https://github.com/canonical/pebble/pull/517) only restart services if it's configured as `startup: enabled`.
* [Jira issue](https://warthogs.atlassian.net/browse/CHARMTECH-353).
