# OP059 — Pebble in-memory state using an environment variable

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2025-02-20 |

## Abstract

This spec for Pebble proposes an environment variable that allows whoever runs the Pebble daemon to opt-in to a non-persistant mode.

## Rationale

In certain container contexts, Pebble needs to be run with a read-only filesystem, for example, with `docker run --read-only`. Or, for a larger example, the Knative Operator charm uses upstream K8s manifests that hardcode `readOnlyRootFilesystem: true` ([description of issue](https://github.com/canonical/knative-operators/issues/291)), which means they don't work as rocks (which use Pebble). Their current workaround is to [patch those lines with a sed script](https://github.com/canonical/knative-rocks/pull/24/files) when building the rocks, but it's quite hacky. This solution would allow them to keep the read-only filesystem (though see the note about the Pebble socket below).

In the context of K8s containers where Pebble is PID 1, it's okay to have the state store be in-memory. When Pebble gets killed, the container is recycled, so any disk-based storage in the container would be recycled anyway.

However, we still want the Pebble state to be durable by default. So it's not okay for in-memory state to be the default, or for Pebble to silently fall back to in-memory state if it can't write to the disk. For that reason, this spec proposes an explicitly opt-in approach using an environment variable.

## Specification

This spec proposes a new environment variable for the Pebble daemon (`pebble run`), as follows:

`PEBBLE_PERSIST=always    # the default`
`PEBBLE_PERSIST=never     # new feature`

* `always`: always persist state to disk, and fail loudly if we can't (the current behaviour). This would be the default if the environment variable is unset.
* `never`:  never persist state to disk, use in-memory state only.

If the new "never" in-memory mode was specified, the Pebble daemon would use a different [`Backend`](https://github.com/canonical/pebble/blob/e3b81e139fc188e8ef01311e9fb13fe26402f816/internals/overlord/state/state.go#L34) implementation which did nothing in its `Checkpoint` method; the default writes the state JSON to a file on disk.

For efficiency, we should try to entirely avoid serialising the state to JSON in this case, perhaps by adding a new `NeedsCheckpoint() bool` method on the interface.

### Notes on Pebble socket

The previous version of this spec proposed adding a way to entirely disable the Pebble API socket with `PEBBLE_SOCKET=:disabled:` or similar, for when the entire file system is read-only. However, disabling the socket makes Pebble impossible to interact with and diagnose issues with.

Instead, we believe users that require this should mount a temporary filesystem (e.g. *tmpfs*) and point PEBBLE_SOCKET to that for use by API clients.

## Further Information

* [Original Matrix thread discussing this](https://matrix.to/#/!NPPCseDHKRvSBMUEXN:ubuntu.com/$HhUg26RQBUw-vDdMvw8IKER2SlJgSCANsPXz_AEW2q0?via=ubuntu.com&via=matrix.org)
