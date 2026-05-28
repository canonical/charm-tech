# OP057 — Pebble verbose mode using an environment variable

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2025-02-03 |

## Abstract

We want to allow rocks to enable Pebble's verbose mode where appropriate, so that when running the container, service logs go to the container's stdout as well as just Pebble log buffers. The user of a rock can specify `--verbose` manually when running the rocker, but we want the ability to build a rock that has this behaviour by default.

## Rationale

When running an image, especially in the context of services run on Kubernetes or other orchestration engines, it is rather common to stream the service logs to the stdout, such that those logs can also be picked up and fetched by the orchestration platform. For instance, in Kubernetes, this can be done via

`kubectl logs <pod-name> -n <namespace>`

In a rock, this means that logs need to bubble up from the Pebble service into the Pebble stdout logs. This can be achieved when the pebble daemon is run with the `--verbose` flag, however this flag is not set by rockcraft in the entrypoint (originally it was, but that caused issues, and we turned it off, see the [Pebble issue](https://github.com/canonical/pebble/issues/339) and the [Rockcraft issue](https://github.com/canonical/rockcraft/pull/495)).

Enabling the verbose behaviour using an environment variable would allow the Rock configuration to enable service logs to be sent to Pebble stdout, either at build time by setting the environment variable in rockcraft.yaml, or at deploy time by setting the environment variable in the Kubernetes manifest.

## Specification

For `pebble run`, allow verbose logging mode (log all output from services to stdout) to be enabled when starting the daemon by setting the environment variable `PEBBLE_VERBOSE=1`.  This is in addition to the existing way of enabling verbose mode with a command line argument: `pebble run --verbose`.

For `pebble enter exec`, the `--verbose` flag is currently disabled. However, `pebble enter` (including `pebble enter exec`) would still respect `PEBBLE_VERBOSE=1`: the author or user of the rock would be saying, "I know how this application behaves, and it's okay to use with verbose logging turned on."

### Overriding

If the rock specified `PEBBLE_VERBOSE=1` and the person running the Docker container wanted to then *disable* verbose mode, they would specify a `PEBBLE_VERBOSE=0` environment variable on the `docker run` command line. (Note that there's not currently a `--no-verbose` option.)

If `PEBBLE_VERBOSE=0` is specified in the environment, passing `--verbose` as a command-line argument would override that (and enable verbose mode), as is usual for CLIs.
