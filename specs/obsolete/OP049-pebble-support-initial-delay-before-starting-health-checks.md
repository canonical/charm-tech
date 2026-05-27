# OP049 — Pebble support initial delay before starting health checks

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2024-08-20 |

## Abstract

Pebble has a feature "[health checks](https://canonical-pebble.readthedocs-hosted.com/en/latest/reference/health-checks/)" where a check is performed within the specified period (the default is 10 seconds apart), and is considered an error if a timeout happens before the check responds.

This spec proposes to add an "initial delay" feature to health checks, similar to Kubernetes' **`initialDelaySeconds`** for liveness/readiness checks,  so that, as the name suggests, health checks are delayed for a certain period of time.

## Rationale

In order to allow the application to fully start up before the health checks are initiated, a K8s style "initial delay" is crucial because:

- Application initialisation: When a container starts up, the application within it might need some time to initialise all its components, establish connections to databases or external services, and reach a stable state where it can handle incoming requests effectively.
- Avoid premature failures: If health checks were to start immediately as the container launches, they might trigger false alarms or failures because the application may not be fully ready to handle requests. This could lead to unnecessary container restarts, impacting availability and performance.
- "Graceful startup": Similar to graceful shutdown, providing an initial delay ensures that the application has had sufficient time to start up gracefully. This is particularly important for complex applications that might have dependencies or initialisation steps that take some time to complete.

This feature is requested by a member from [is-charms](https://github.com/orgs/canonical/teams/is-charms), and it will close [issue 145](https://github.com/canonical/pebble/issues/145). There are a few user-reported issues related to this, like [Synapse restarting before it could fully reconcile](https://github.com/canonical/pebble/issues/145#issuecomment-2289229958) and [a web app needing to do database migrations on startup](https://github.com/canonical/pebble/issues/145#issuecomment-1232889239).

## Specification

Add a new field named **`initial-delay`** to health checks, which tells Pebble it should wait the given period of time before running that check for the first time. Example:

```
checks:
    <check name>:
        override: merge
        level: alive | ready
        period: 10s
        timeout: 3s
        initial-delay: 60s
        ...
```

Before the initial-delay time has passed, the pebble checks command should return a pending status for the check.

## Further Information

* [A simple PoC code from a contributor](https://github.com/canonical/pebble/pull/487)
* [Another PoC from Ben](https://github.com/canonical/pebble/issues/145#issuecomment-1235000796)
* Some issues from users: [here](https://github.com/canonical/pebble/issues/145#issuecomment-1232889239), [here](https://github.com/canonical/pebble/issues/145#issuecomment-2289229958) and [here](https://github.com/canonical/pebble/pull/487)
* Jira issue: [https://warthogs.atlassian.net/browse/CHARMTECH-220](https://warthogs.atlassian.net/browse/CHARMTECH-220)
