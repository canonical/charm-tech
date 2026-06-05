# OP052 — Disabling Pebble checks

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Implementation |
| Created | 2024-11-12 |

*Implemented in [Pebble #560](https://github.com/canonical/pebble/pull/560) and [Ops #1560](https://github.com/canonical/operator/pull/1560).*

## Abstract

Once configured, Pebble checks cannot be disabled, other than by replacing the method of the check with one that efficiently always returns success. This spec proposes adding a simple mechanism to keep a check, but make it inactive.

## Rationale

The Pebble plan is composed of one or more layers that progressively build the entire plan. Once added to a plan, it is not possible to remove or disable a layer - a service can effectively be disabled by stopping it, and a log target can be effectively disabled by removing all the services for which it is forwarding logs, but a check cannot be removed or disabled. In some situations, it is useful to disable a check, either permanently or temporarily.

One such use-case, identified in the 24.10 Charming Survey, is upgrading. Charmers would like to pause checks throughout an upgrade, during which time the workload (and therefore checks) and then enable the checks again once the upgrade was complete, and the workload is expected to be completely operational again.

Another use-case is beginning with Pebble layers that are provided by the rock as files, rather than from an initial dynamic layer added with the API. In this situation, the charm can alter the base layers by adding additional layers on top, but cannot currently remove any elements of the base layers without building a new rock image. This feature would allow using the base rock layers, while still permitting disabling checks that are not required in the charmed workload case.

## Specification

### API

Our aim is to be consistent with existing Pebble functionality where possible.

* Log targets are disabled through adding new layers with a `services: [-all]` field for the log target. However, checks are not explicitly connected to services in this way (and may not be connected in the layer to a service at all). The ability to disable using a layer could be added instead (see alternatives, below), but would be inconsistent with log targets in terms of the syntax.
* Services are stopped using the `/v1/services` API at runtime. A service can be "stopped" or "started", if admin access has been granted. This spec proposes using the same approach for checks.

The existing `/v1/checks` API method will gain a POST action to start or stop a check, modelled on the `/v1/services` POST API.

```
// internals/daemon/api.go
{
	Path:       "/v1/checks",
	ReadAccess: UserAccess{},
	WriteAccess: AdminAccess{},
	GET:        v1GetChecks,
      	POST:       v1PostChecks,
}

// internals/daemon/api_checks.go, modelled on internals/daemon/api_service.go
func v1PostChecks(c *Command, r *http.Request, _ *UserState) Response {
	var payload struct {
		Action   string   `json:"action"`
		Checks   []string `json:"checks"`
	}

	...

	switch payload.Action {
	case "start": ...
	case "stop": ...

...
}
```

Several verb pairs for the API and CLI command were considered:

* disable/enable
* pause/resume
* pause/unpause
* suspend/resume

We will use start/stop. This is most consistent with services, and reflects that the check is either effectively removed, or is actively doing work, rather than waiting in some sort of "disabled" state.

### Layer

A new `startup` field will be added to the check specification, mirroring the service field, but defaulting to `enabled` for backwards compatibility. This provides full control to the user of which checks are running.

```
# (Optional) A list of health checks managed by this configuration layer.
checks:
    <check name>:
        override: merge | replace
        level: alive | ready
        # (Optional) Control whether the check is started automatically when
        # Pebble starts or performs a 'replan' operation. Default is "enabled".
        startup: enabled | disabled
        ...
```

When Pebble starts or a replan is executed, all checks with `startup` set to `enabled` will be started (this is a no-op for already active checks), and checks with `startup` set to `disabled` will be left in their current started/stopped state.

When a Pebble layer containing new checks is added or merged, checks with `startup` set to `enabled` will be started, and the other checks will be added in a stopped state.

Checks that have `startup` set to `disabled` will only be started by an explicit start call to the `/v1/checks` API.

The `/v1/checks` API call will include the new `startup` field and use `inactive` as the value for the Status field for all stopped checks, consistent with the "current" value for services.

Stopping a running check will complete the tasks in the active change for the check, moving the change to an `abort` state (a recover-check change moving to `done` would trigger a pebble-check-recovered event in Juju, which is not appropriate in this situation). Starting a stopped check will create a new perform-check change, regardless of whether the check was previously passing or failing (essentially, we move back to an 'unknown' state, exactly as when the check was first added). Note that this means starting a check will move its status to 'up' (see also: [Reconsider checks reporting "up" status before being executed](https://github.com/canonical/pebble/issues/164)). Appropriate `change-updated` notices will be generated as usual.

When executing a `health` command and the `/v1/health` API call, all stopped checks will be excluded from the healthy/unhealthy decision.

Note that stopping all failing checks will result in the health response moving from unhealthy to healthy - even after the checks are restarted, the health response will remain healthy until a check has failed enough time to reach the failure threshold. This mirrors the behaviour when checks are first added, or Pebble is first started.

### CLI

The `pebble checks` command output will be adjusted to include a new "Startup" column, which contains the value of the startup field for that check. In addition, any checks that have been stopped (or have never started) will show "inactive" for the "Status" column, and "-" for the "Failures" column. A new "Active" column could be added instead, with "yes"/"no" values for active and inactive checks, but these values are directly tied to the status: an inactive check will always have no status, and a check with a status will always be active, so it's simpler to combine into a single column. The downside is that if people read the "Status" column as "status of a service" then "inactive" reads as "the service is inactive", but it is better to counter this by making it clearer that the "Status" column is the status of the check (perhaps by clearer check names).

```
$ pebble checks
Check              Level  Startup   Status     Failures  Change
http-service       -      enabled   down       3/3       4
rpc-service        -      enabled   inactive   -         3
background-worker  -      enabled   up         0/3       2
external-network   -      disabled  inactive   -         7
```

New CLI commands `stop-checks` and `start-checks` will be added; these take 1-*n* check names as arguments (providing no arguments will give an error response). The plural form indicates to the user that multiple arguments are possible (as opposed to a theoretical `run-check` command, which would take exactly one argument, and consistent with the *`*`*`-identities` commands being plural and the `notice` command being singular). As "replan" will now impact both services and checks, the "replan" command will be moved in the CLI help from "Services" to "Plan".

```
$ pebble --help
Pebble lets you control services and perform management actions on
the system that is running them.

...

         Run: run
        Info: help, version
        Plan: add, plan, replan
    Services: services, logs, start, restart, signal, stop, replan
      Checks: checks, start-checks, stop-checks, health
       Files: push, pull, ls, mkdir, rm, exec
     Changes: changes, tasks
     Notices: warnings, okay, notices, notice, notify
  Identities: identities --help

...

$ pebble help stop-checks
Usage:
  pebble stop-checks <check> [<check>...]

The stop-checks command stops the configured health checks provided as
positional arguments. For any checks that are inactive, the command has
no effect.

$ pebble help start-checks
Usage:
  pebble start-checks <check> [<check>...]

The start-checks command starts the configured health checks provided as
positional arguments. For any checks that are already active, the command
has no effect.
```

It may be that a "stop all checks" command would be useful. We will not implement that within this spec (waiting until there is clear demand and use cases), but suggest that `pebble stop-checks --all` would likely be an appropriate syntax for this command, rather than `pebble stop-checks` (with no arguments). However, either is backwards compatible (the latter transforming an error to a valid command) so the current choice leaves options available.

## Further Information

### Alternatives

#### Disabling a check via a layer

A new field, `disabled` (defaulting to `false`), will be added to the check definition. If the final value of this field in the resolved plan is `false`, then the check will be active. If the final value is `true`, no perform-check change will be created, meaning no checks will be executed.

This requires a small change to the [`Check` definition](https://github.com/canonical/pebble/blob/ce116b9ff67adb9ec3a981861ab6e8ef2ed438f9/internals/plan/plan.go#L420C1-L436C2), as well minor adjustments to the check management:

```
// Check specifies configuration for a single health check.
type Check struct {
	// Basic details
	Name     string     `yaml:"-"`
	Override Override   `yaml:"override,omitempty"`
	Level    CheckLevel `yaml:"level,omitempty"`
      	Disabled bool       `yaml:"disabled,omitempty"`

       // ... other fields ...
}
```

The check will still exist, so can be modified by subsequent layers, even if it is disabled. This provides simpler disabling/enabling when multiple layers are involved in the check definition, compared with providing the ability to remove the check.

The `checks` command will output "`disabled`" in the status column for any checks that are not enabled. Similarly, the status in a `/v1/checks` call will have a new possible value: `disabled`. Checks and plans returned from the API will include the new field, and the corresponding changes will also be made to the ops Pebble classes.

```
// Example base layer, with an active check
base-layer:
  services:
    http-server:
      override: replace
      command: ...
  checks:
    http-server:
      override: replace
      http:
        url: http://localhost:8000/health

// Subsequent layer that disables the check
// Disabling with `override: replace` is also possible, but would require
// repeating all of the definition of the check.
disable-check-layer:
  checks:
    http-server:
      override: merge
      disabled: true

// `pebble checks` output:
$ pebble checks
Check        Status     Failures
http-server  disabled   0/3

// Subsequent layer that adjusts the (still disabled) check
timeout-adjustment-layer:
  checks:
    http-server:
      override: merge
      timeout: 5s

// Subsequent layer that enables the check again.
enable-check-layer:
  checks:
    http-server:
      override: merge
      disabled: false
```

#### Removing a check via a layer

We could provide a method to remove a check, such as:

```
// Base layer
layer1:
  services:
    http-server:
      override: replace
      command: ...
  checks:
    http-server:
      override: replace
      http:
        url: http://localhost:8000/health

// Remove the http-server check.
layer2:
  http-server: null
```

To add the check back, the layer would need to be replaced (or merged with a later layer) with one that included the entire original definition. With this approach, the `checks` command would not show the check at all, and the check would not be included in the `/v1/checks` response.

### Workaround

A layer can remove a check by replacing it with an empty check, but this is complicated to do while still providing a valid layer, and results in Pebble 'checking' unnecessarily.

```
// Base layer
layer1:
  services:
    http-server:
      override: replace
      command: ...
  checks:
    http-server:
      override: replace
      http:
        url: http://localhost:8000/health

// Replace the `http-server` check with one that does nothing.
layer2:
  checks:
    http-server:
      override: replace
      period: 8760h
      exec:
        command: /bin/true
```
