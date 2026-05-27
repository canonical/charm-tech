# OP055 — Run a Pebble health check

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 2025-01-15 |

## Abstract

Each Pebble health check is configured with a `period` that defaults to 10 seconds and a `threshold` that defaults to 3. Health check status is only updated after `period * threshold` seconds, making debugging health checks inconvenient. This spec adds a way to run a check immediately and get the result synchronously.

## Rationale

This feature request comes from end users where charmers want "a new feature to 'develop' checks as in: SSH into a unit, ask pebble 'would this check pass?' and have immediate feedback." See [Charming survey 24.10](https://docs.google.com/forms/d/1eJU1-KfCnpwG57BfJ3Tblkokh-Yz0EAF2aYPTiVfMH4/edit#responses).

In addition to debugging and diagnostics, it may be useful for a charm to pre-emptively run a health check on demand to check if something is back up (for example, after a charm has updated a workload).

At the moment, after starting the Pebble daemon, users must wait for at least `period` seconds and check Pebble logs to find out if a check passes or not. Depending on the use case, the `period` might be configured to a much longer interval, like 30 seconds, or even longer. If the users prefer not to check Pebble logs but use `pebble checks` to find out if a check passes or not, the situation is even more inconvenient, because in this case, the users need to wait for `period * threshold` to get the check result from `pebble checks`.

## Specification

### CLI

Add a new `pebble check <check>` command, then give it a `--refresh` option indicating the user wants to refresh this check immediately and synchronously see the result (ignoring the configured period).

`pebble help check` will print:

```
Usage:
  pebble check <check>

The check command shows details for a single check in YAML format.

[check command options]
      --refresh   Refresh check immediately and show result
```

Sample result:

```
name: chk1
level: alive      # omitted if empty
startup: enabled
status: up
failures: 0       # included if 0
threshold: 3
change-id: "42    # omitted if empty
```

With the `--refresh` option, Pebble runs a check and returns the result. If running a check is successful, `pebble check chk1 --refresh` will print the YAML output in the format shown above and return a 0 exit code.

If the check is not found, it should display a not found error and return a nonzero exit code:

```
error: cannot find check with name "chk1"
```

If there is an error running the check, the same YAML output will be displayed, with the addition of the "error" and "log" fields showing the task log from the associated change (as `pebble checks` does in compressed form). It will return a zero exit code because fetching the check was successful (even though the last run of the check failed):

```
name: chk1
...
error: Get "http://localhost:8000" error ...
logs: |
    2024-04-18T12:16:57+12:00 ERROR Get "http://localhost:8000": dial tcp 127.0.0.1 ...
    2024-04-18T12:16:58+12:00 ERROR ... any other logs ...
```

As with `pebble checks`, `pebble check <check>` will fetch the error logs using `Client.Change` using the associated change ID.

### Client

The CLI can already call `Client.Checks` and filter with a single check name when `--refresh` is not specified.

For when `--refresh` is specified, in `client/checks.go`, add another function with the following signature:

```
// Check fetches information about a specific health check.
func (client *Client) RefreshCheck(opts *RefreshCheckOptions) (*RefreshCheckResult, error) { ... }

type RefreshCheckOptions struct {
    Name string // name of check to run (required)
}

type RefreshCheckResult struct {
    Info  *CheckInfo
    Error string      // if "", success, if != "", this is the error message
}
```

### API

#### Endpoint

We will reuse existing `/v1/checks?names=chk1` API endpoint for `pebble check <check>`.

For command `pebble check <check> -refresh`, we will add a new API endpoint `/v1/checks/refresh` with a `POST` method and `AdminAccess`. The payload will be like: `{"check": "chk1"}`.

#### Response

For `pebble check <check> -refresh`, if successful, the API shall return a synchronous response in the following structure (check info in the `info` field of the result, with an empty `err` field in the result):

```
{
    "type": "sync",
    "status-code": 200,
    "status": "OK",
    "result": {
        "info": {
            "name": "check1",
            "startup": "enabled",
            "status": "up",
            "threshold": 3,
            "change-id": "1"
        },
        "err": ""
    }
}
```

If the check runs successfully but the check fails, The API shall return a synchronous response with status code 200 because the check does refresh successfully. The check info is also returned in the result, but the `err` field is non-empty with the error message:

```
# check runs but fails
{
    "type": "sync",
    "status-code": 200,
    "status": "OK",
    "result": {
        "info": {
            "name": "check2",
            "startup": "enabled",
            "status": "up",
            "failures": 1,
            "threshold": 3,
            "change-id": "2"
        },
        "err": "non-2xx status code 500"
    }
}
```

In case of other failures, the API returns a non-200 response. For example:

```
# not found
{
    "type": "error",
    "status-code": 404,
    "status": "Not Found",
    "result": {
        "message": "cannot find check with name \"check\""
    }
}
```

#### Access Level

Normal users with `UserAccess` can get a specific check (`pebble check <check>`, without `--refresh`).

The `pebble check <check> --refresh` command requires `AdminAccess`: This feature is aimed at developers to develop/test/debug checks, and the use case is: Get into the container (for example using `kubectl exec`) and run the command as the same user that started the Pebble daemon, in which case, the user has `AdminAccess`. So, making it an AdminAccess level is reasonable and doesn't block anything.

#### Functional Requirements and Design

For `--refresh`:

- If the check is waiting for the next period, act immediately.
- If there is already a running check due to periodic ticking, do not start a new check, wait for the running check to finish and report the result to the user.
- If the refresh check fails, the failure count should also be increased, just like a normal periodic ticking check.
- If the check is disabled, still run it, but don't enable it, and don't send any notifications.

See a proof of concept in the [Further Information](#further-information) section.

## Further Information

- Proof of concept: [https://github.com/canonical/pebble/pull/557](https://github.com/canonical/pebble/pull/557).
- Related spec for disabling health checks: [OP052 - Disabling Pebble checks](https://docs.google.com/document/d/1KpgFR0eaxkrwt_Vd0rTZzb0D57dQVtAv7t1b9iuMUQw/edit?tab=t.0)
