# OP0X1 — OpenTelemetry Logs via OTLP

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

## Abstract

This spec describes extending Pebble's existing log forwarding
infrastructure to accept structured log records from services via the
same local OTLP/HTTP receiver used by `trace-targets`, `metric-targets`,
and `profile-targets`.

No new plan section is introduced. The existing `log-targets`
configuration is reused as-is. The only behavioural change is that
log-targets with `type: opentelemetry` now also act as receivers for
OTLP-sourced log records, alongside the existing stdout/stderr capture
path.

## Rationale

Pebble currently forwards service logs by capturing stdout and stderr
from each service process, parsing lines into `servicelog.Entry`
records, and shipping them to configured `log-targets`. This works well
for services that write plain text to stdout, but has two limitations:

**Loss of structure**: A log line read from stdout is forwarded as a
plain string body. Severity, span context, key-value attributes, and
other fields provided by a structured logging framework are discarded.

**No OTel SDK integration**: Services using an OTel log bridge (e.g.
connecting zap or logrus to the OTel SDK) emit log records via the OTLP
protocol rather than — or in addition to — stdout. Without a local OTLP
endpoint, those records have nowhere to go inside the same container.

Accepting OTLP logs at the local receiver lets services opt into
structured, high-fidelity log forwarding while Pebble's existing
stdout/stderr capture continues to work unchanged for services that
don't use the OTel SDK.

## Specification

## Plan Configuration

No new top-level plan section is added. The existing `log-targets`
section is unchanged:

```yaml
log-targets:
    <target-name>:
        override: merge | replace
        type: loki | opentelemetry | syslog
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
```

The OTLP log receiver is activated only for log-target entries with
`type: opentelemetry`. Entries with `type: loki` and `type: syslog` are
unaffected by this spec; they continue to receive only stdout/stderr
logs, as today.

For a `type: opentelemetry` entry, the `services` list now controls
three things, rather than two:

1. Which services' stdout/stderr output is forwarded (existing).
2. Which services receive OTLP endpoint environment variable injection
   at start (new — see [Service Endpoint Injection]).
3. Which services' OTLP-sourced log records are forwarded (new).

All other fields (`override`, `location`, `labels`) retain their
existing meaning. `location` refers to the remote OTLP/HTTP backend;
the local receiver address is internal to Pebble.

Labels whose key begins with `pebble.` or `pebble_` are reserved and
are rejected at plan validation.

Values may reference `$ENV_VARS`, which are interpolated from the Pebble
daemon environment at startup.


## Local OTLP Receiver

When any `log-targets` entry with `type: opentelemetry` has one or more
`services` configured, Pebble registers the OTLP log routes on the
active receiver.

### Receiver Address

Pebble exposes OTLP receiver routes on:

- **Pebble's HTTP API listener**, when it is configured with a TCP
  address. Requests to OTLP routes are accepted only from loopback
  addresses (`127.0.0.1` or `::1`); any other remote address receives
  `403 Forbidden`.
- **A dedicated loopback listener** on a randomly chosen port, started
  at daemon startup when no TCP HTTP API listener is configured.

The actual address is determined at startup and substituted into
injected environment variables at service-start time.

The log route registered is:

```
POST /v1/services/{service}/otlp/v1/logs
```


## Service Endpoint Injection

When a service is started and its name appears in any `type: opentelemetry`
log-target's `services` list, Pebble injects the following environment
variables before the process is launched, if they are not already set:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | `http://<receiver-address>/v1/services/<name>/otlp/v1/logs` |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | `http/json` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_SERVICE_NAME` | `<name>` |

The per-signal endpoint variable is used as-is by the SDK (no path is
appended). `OTEL_SERVICE_NAME` is the only variable shared across signal
types; if it was already injected by another target type for this service
it is not re-injected.

Each variable is only injected if it is not already present in the
service's resolved environment. An operator can override any of these
in the service's `environment:` block; Pebble will not overwrite an
explicitly set value.

`OTEL_LOGS_EXPORTER=otlp` activates the SDK's OTLP log exporter,
enabling the OTel log bridge to route structured log records to Pebble's
receiver. `OTEL_SERVICE_NAME` sets the `service.name` resource
attribute in the SDK itself, consistent with the name Pebble uses
during enrichment.


## Log Enrichment

On receiving a valid JSON log payload for service `<name>`, Pebble
merges the following resource attributes into each `ResourceLogs` entry
before forwarding, using the same logic as the other OTLP signal types:

| Attribute | Value | Notes |
|---|---|---|
| `service.name` | `<name>` | Overrides any value set by the SDK |
| `pebble.service` | `<name>` | Always added |
| `service.instance.id` | UUID generated each time the service starts or restarts | Added if not already present |

Custom `labels` configured on the matching log-target are also added as
resource attributes. If a label key conflicts with an attribute already
present in the payload, the label value wins.

This is a meaningful improvement over the existing stdout/stderr path:
the existing `type: opentelemetry` forwarding creates minimal log
records containing only a timestamp and a plain-text body. OTLP-sourced
records preserve the full structure supplied by the SDK, including
`severityNumber`, `severityText`, `attributes`, `spanId`, `traceId`,
and structured body values.


## Forwarding

### OTLP-sourced log records

Enriched log payloads are forwarded to every `log-targets` entry with
`type: opentelemetry` whose `services` list includes the originating
service. Entries with `type: loki` or `type: syslog` do not receive
OTLP-sourced records.

Pebble responds to the service's HTTP request with `200 OK` once the
payload is accepted into the outbound buffer, not once delivery to the
remote backend is confirmed. Backend delivery failures are logged but
do not propagate back to the service.

### Stdout/stderr logs

Pebble continues to read stdout and stderr from each service process
and forward entries via all log-target types (`loki`, `opentelemetry`,
`syslog`) as before. However, for `type: opentelemetry` targets,
stdout/stderr forwarding is subject to automatic muting once the
service's OTel SDK becomes active (see [Auto-Muting]).

`type: loki` and `type: syslog` targets always receive stdout/stderr
entries regardless of OTLP activity.

### Auto-Muting

When Pebble receives the first OTLP log record from a service after
that service has started or restarted, it mutes stdout/stderr
forwarding for that service to all `type: opentelemetry` log-targets.
The mute remains in effect until the service next starts or restarts,
at which point stdout/stderr forwarding resumes and the cycle repeats.

This handles the typical lifecycle of a service using an OTel log
bridge:

1. Service starts; OTel SDK has not yet initialised.
2. Early startup logs written to stdout are forwarded via the
   stdout/stderr path — these are captured and not lost.
3. OTel SDK initialises; the first OTLP log record arrives at
   `/v1/services/{service}/otlp/v1/logs`.
4. Pebble mutes stdout/stderr forwarding to `type: opentelemetry`
   targets for this service. Subsequent stdout lines are no longer
   forwarded to opentelemetry backends (though they continue flowing
   to any `type: loki` or `type: syslog` targets).
5. On restart, the mute is cleared and the cycle begins again.

The mute flag is tracked in memory and is not persisted across Pebble
restarts. Pebble continues to drain the stdout/stderr pipe regardless
of the mute state; the pipe is never left unread.

### Crash Flush

When a service exits with a non-zero exit code while its stdout/stderr
mute is active, Pebble immediately forwards the stdout/stderr entries
accumulated in the service's ring buffer since the mute was activated
to all `type: opentelemetry` log-targets for that service. This
provides crash context — stack traces, panic messages, final error
lines — that the OTel SDK had no opportunity to forward before the
process terminated.

The flush only occurs when all of the following are true:

- The service exits with a non-zero exit code.
- The stdout/stderr mute was active at exit time, meaning at least
  one OTLP log record was received from the service since its last
  start or restart.

The trigger is the OS process exit code, not Pebble's configured restart
policy. A service that Pebble considers successful under its
`on-success: restart` policy still triggers the flush if the process
exit code was non-zero.

On a clean exit (exit code 0), no flush is performed. The OTel SDK
had the opportunity to flush its own log buffer before exiting, so
the structured records are expected to have arrived via the OTLP path.

If the mute was not active at exit time (the service never sent an
OTLP log record in its current run), no flush is performed either.
In that case stdout/stderr was already being forwarded continuously
throughout the service's lifetime and nothing is outstanding.

The flushed entries are plain text log records, identical in format
to normal stdout/stderr forwarding. They are forwarded to
`type: opentelemetry` targets only; `type: loki` and `type: syslog`
targets received this output in real time and are unaffected.

The ring buffer holds a finite amount of recent output. If the service
produced more stdout/stderr since the mute was activated than the
buffer can hold, only the most recent entries are available. Earlier
suppressed output is lost.


## Coexistence and Duplication

Auto-muting handles the typical duplication scenario automatically.
A service that uses an OTel log bridge will have its early startup
logs forwarded via stdout/stderr, then have stdout/stderr suppressed
for `type: opentelemetry` targets once the SDK sends its first OTLP
record. Under normal circumstances no duplicate records reach an
opentelemetry backend.

Two situations can still produce duplicates:

**Startup window**: Logs written to stdout before the OTel SDK
initialises are forwarded as plain text records. If the same message
is later replayed through the SDK (e.g. a buffered logger flushing at
startup), it may appear twice. This window is typically short and
acceptable.

**Concurrent stdout and SDK logging**: If a service writes to stdout
independently of the OTel log bridge (e.g. a legacy logger and a new
SDK logger operating side by side), stdout lines will be forwarded
until the first OTLP record mutes the path. After that, only OTLP
records are forwarded to opentelemetry backends. Lines written to
stdout after the mute are silently dropped for opentelemetry targets
but continue to flow to any `type: loki` or `type: syslog` targets.

Operators who need stdout/stderr suppressed for `type: loki` or
`type: syslog` targets must still do so manually by removing the
service from those targets' `services` lists.


## Retry and Error Handling

### Outbound (Pebble → remote backend)

Pebble retries on `429 Too Many Requests`, `502 Bad Gateway`,
`503 Service Unavailable`, and `504 Gateway Timeout`, honouring the
`Retry-After` header when present and using exponential backoff with
jitter otherwise. All other non-2xx responses are non-retryable; the
batch is dropped and a warning is logged.

### Inbound (service → Pebble receiver)

- Only `application/json` and `application/x-protobuf` (binary Protobuf)
  request bodies are accepted. Pebble enriches the payload and forwards
  it to backends using the same encoding. Any other `Content-Type`
  returns `415 Unsupported Media Type`.
- The implementation relies solely on `google.golang.org/protobuf`;
  no gRPC or OTel SDK library dependency is required.
- Unknown service name: `200 OK` with an empty `ExportLogsServiceResponse`
  body; the payload is silently discarded.
- Malformed JSON or Protobuf: `400 Bad Request`.
- Success: `200 OK` with an empty `ExportLogsServiceResponse` body.
  Partial success (`rejected_log_records`) is not used in this
  implementation.
- Error responses (`4xx`, `5xx`) include a `Status` message body. When
  the request used `application/json`, the body is JSON-encoded; when
  `application/x-protobuf`, it is binary-Protobuf-encoded.


## Examples

### Structured log forwarding with an OTel SDK

```yaml
log-targets:
    otel-backend:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]
        labels:
            environment: production
```

All services receive `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`,
`OTEL_EXPORTER_OTLP_LOGS_PROTOCOL`, `OTEL_LOGS_EXPORTER=otlp`, and
`OTEL_SERVICE_NAME` at start. Services using an OTel log bridge will
have their structured SDK logs received and forwarded automatically.
All services continue to have their stdout/stderr captured and
forwarded on the same target.

### Mixed targets: Loki for stdout, OpenTelemetry for SDK logs

```yaml
log-targets:
    loki:
        override: replace
        type: loki
        location: http://loki:3100/loki/api/v1/push
        services: [all]

    otel-structured:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [api-server]
        labels:
            component: api
```

`loki` receives stdout/stderr from every service. `otel-structured`
receives both stdout/stderr and OTLP SDK logs from `api-server` only.
`api-server` has the OTLP endpoint injected; other services do not.

### Suppressing stdout forwarding for a fully SDK-instrumented service

```yaml
log-targets:
    # Loki still receives stdout from most services
    loki:
        override: replace
        type: loki
        location: http://loki:3100/loki/api/v1/push
        services: [all, -sdk-service]

    # OTLP receives only structured SDK logs from sdk-service
    otel-backend:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [sdk-service]

services:
    sdk-service:
        override: replace
        command: ./sdk-service
```

`sdk-service` is excluded from Loki (via `-sdk-service`). Pebble
injects `OTEL_LOGS_EXPORTER=otlp` at start, activating the OTel log
bridge automatically. Early startup stdout/stderr is forwarded to the
OTLP backend until the first OTLP record arrives, at which point
stdout/stderr forwarding to the opentelemetry target is muted
automatically. No logs reach Loki at any point.


## Relation to Existing Log Forwarding

This spec does not replace or modify the existing log forwarding
infrastructure. The stdout/stderr capture pipeline, the logGatherer,
the logPuller, and all three log client implementations (Loki, OpenTelemetry,
syslog) are unchanged. The OTLP receiver adds a parallel inbound path
whose output feeds into the same `type: opentelemetry` forwarding
client.

The existing OTLP log forwarding (stdout/stderr → OTLP log records)
remains the default for services that do not use an OTel SDK. The new
path is opt-in via the SDK and does not require any plan changes beyond
what is already needed to configure `type: opentelemetry` log-targets.

**Migration note**: operators with existing `type: opentelemetry`
log-targets should be aware that after this change those targets will
also: expose the OTLP receiver routes for enrolled services, inject
`OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` and related variables into service
environments, and activate auto-muting when the first OTLP log record
is received. If any of this is undesirable, set the relevant environment
variables explicitly in the service's `environment:` block to prevent
injection.


## Relation to trace-targets, metric-targets, profile-targets

The local OTLP receiver is shared across all four signal types. The
route `/v1/services/{service}/otlp/v1/logs` is handled by this spec;
the other routes (`/v1/traces`, `/v1/metrics`, `/v1development/profiles`)
are handled by their respective specs.

Only `OTEL_SERVICE_NAME` is shared across signal types; the other
injected variables are signal-specific.


## Out of Scope

- **`type: loki` and `type: syslog` OTLP reception**: These target
  types continue to receive stdout/stderr logs only. Forwarding
  OTLP-structured records to Loki or syslog (via body extraction or
  label mapping) is a future consideration.
- **gRPC receiver and protobuf encoding**: Same constraints as the
  other OTLP specs. HTTP/JSON only in this implementation.
- **Muting across target types**: Auto-muting only silences
  stdout/stderr forwarding to `type: opentelemetry` targets.
  Suppressing stdout/stderr on `type: loki` or `type: syslog` targets
  requires explicit `services` list management.
- **`OTEL_LOGS_EXPORTER` side effects**: Injecting `otlp` activates
  the OTel log bridge in the service SDK. Services that intentionally
  use a non-OTLP log exporter must set `OTEL_LOGS_EXPORTER` explicitly
  in their `environment:` block to override Pebble's injected value.
