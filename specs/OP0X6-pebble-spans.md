# OP0X6 — OpenTelemetry Pebble Spans

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

## Abstract

This spec describes the spans Pebble emits for its own internal
operations: service lifecycle events, health checks, plan updates,
changes and tasks, and exec commands. These spans are forwarded to all
configured `trace-targets` and complement the service spans described
in [OpenTelemetry Traces](OP0X3-otlp-traces.md).

## Resource Attributes

All Pebble-emitted spans carry the following resource attributes:

| Attribute | Value |
|---|---|
| `service.name` | `pebble` |
| `service.version` | Pebble version string |
| `service.instance.id` | UUID generated once at Pebble daemon startup |

## Service Lifecycle

A root span is emitted for each service management operation, named
`service <operation>: <service-name>`.

| Operation | Span Name |
|---|---|
| Start | `service start: <name>` |
| Stop | `service stop: <name>` |
| Restart | `service restart: <name>` |
| Force stop | `service force-stop: <name>` |

Span attributes:

| Attribute | Type | Description |
|---|---|---|
| `pebble.service` | string | Service name |
| `pebble.operation` | string | Operation type |
| `pebble.exit_code` | int | Process exit code (stop/force-stop only; omitted on clean shutdown before exit) |

Service-specific spans are only forwarded to `trace-targets` entries
whose `services` list includes the service (or `all`).

## Health Checks

A span is emitted for each health check execution, named
`check: <check-name>`. The span status is set to `Error` when the
check fails.

| Attribute | Type | Description |
|---|---|---|
| `pebble.check` | string | Check name |
| `pebble.check.type` | string | `http`, `tcp`, or `exec` |
| `pebble.check.threshold` | int | Configured failure threshold |
| `pebble.check.failures` | int | Current consecutive failure count |

## Plan Updates

A span is emitted when a layer is added or updated. The span name is
`plan update`.

| Attribute | Type | Description |
|---|---|---|
| `pebble.layer` | string | Layer label |
| `pebble.layer.order` | int | Layer order number |

## Changes and Tasks

Each Pebble change generates a root span named `change: <kind>`, with
one child span per task named `task: <kind>`.

| Attribute | Type | Description |
|---|---|---|
| `pebble.change.id` | string | Change ID |
| `pebble.change.kind` | string | Change kind |
| `pebble.task.id` | string | Task ID (task spans only) |
| `pebble.task.kind` | string | Task kind (task spans only) |

## Exec Commands

A span is emitted for each `pebble exec` invocation, named
`exec: <command>` where `<command>` is the executable (first element
of the command vector).

| Attribute | Type | Description |
|---|---|---|
| `pebble.exec.argv` | string[] | Full command vector including arguments |
| `pebble.exec.service_context` | string | Service context name, if `--context` was specified |

If the `/v1/exec` API request carries a W3C `traceparent` header,
Pebble extracts that context and creates the exec span as a child.
This lets calling processes — deployment scripts, test harnesses,
CI pipelines — stitch `pebble exec` invocations into their own
distributed trace.

Pebble injects the following environment variables into the executed
command before it launches, if they are not already set:

| Variable | Value |
|---|---|
| `TRACEPARENT` | W3C Trace Context of the exec span |
| `TRACESTATE` | Vendor trace state forwarded from the incoming request, or empty |

Note: `TRACEPARENT` and `TRACESTATE` are an emerging community
convention recognised by some tools (such as the Jenkins OTel plugin
and OTel CLI) rather than a formal OTel SDK specification. Most
language SDKs do not automatically read these variables. The executed
binary must explicitly support them to propagate the exec span as a
parent.

These variables are only injected when at least one `trace-targets`
entry is configured. If no trace-targets exist, no exec span is created
and no context is propagated.

When the exec command runs with `--context=<service>` and that service
appears in a `trace-targets` `services` list, the command also inherits
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`
from the service's resolved environment, giving it a complete OTel
traces configuration to emit and forward its own child spans through
Pebble's receiver.

## Relation to trace-targets

Pebble-emitted spans are forwarded to every `trace-targets` entry
regardless of its `services` filter, with one exception: spans that
carry a `pebble.service` attribute are only forwarded to targets whose
`services` list includes that service (or `all`). Plan update and
change/task spans are forwarded unconditionally.

## Out of Scope

- **Sampling**: Pebble forwards all self-emitted spans without
  sampling. Tail or head sampling must be performed by a downstream
  collector such as otel-collector (see
  [Running otel-collector as a Pebble Service](OP0X5-otlp-delegate.md)
- **Configurable span attributes**: The set of resource and span
  attributes emitted by Pebble is fixed by this spec.
- **Log–trace correlation**: Automatic injection of trace IDs into
  forwarded log records is a future consideration.
- **Trace context propagation for long-running services**: Pebble does
  not inject W3C `traceparent` into long-running service environments.
  Services manage their own trace context through the OTel SDK.
  `pebble exec` is the exception — see [Exec Commands].
