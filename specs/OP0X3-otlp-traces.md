# OP0X3 — OpenTelemetry Traces via OTLP

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

## Abstract

This spec describes adding support for Pebble to:

1. **Receive** OpenTelemetry traces from services via a local OTLP/HTTP
   endpoint, enrich them with Pebble resource attributes, and forward
   them to a remote trace backend.
2. **Emit** its own traces covering service lifecycle events, health
   checks, and plan changes, and forward those to the same backend.

Transport is OTLP/HTTP with JSON encoding throughout. No new binary
dependencies (e.g. protobuf codegen or gRPC) are required.


## Rationale

Pebble manages the lifecycle of one or more services and is often deployed
in container or embedded environments that integrate with an observability
stack. Two problems motivate this feature:

**Service traces**: Services instrumented with an OTel SDK need a local
collector endpoint to send spans to. Rather than requiring operators to
run a separate OTel Collector sidecar, Pebble can act as that local agent,
receiving and forwarding spans on behalf of each service.

**Pebble traces**: Operators need visibility into Pebble's own operations —
service start and stop latencies, health check failures, and the timing of
configuration changes — so they can correlate infrastructure events with
application behaviour.


## Plan Configuration

A new top-level section `trace-targets` is added to the Pebble plan. It
follows the same map-based, multi-layer merge pattern used by `log-targets`.

```yaml
trace-targets:
    <target-name>:
        override: merge | replace
        type: opentelemetry
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        tls:
            ca-cert: <path-or-pem>
            client-cert: <path-or-pem>
            client-key: <path-or-pem>
        headers:
            <header-name>: <value>
```

### Required Fields

- **`override`**: How this target definition is combined with any existing
  definition of the same name in a lower layer. Supported values are
  `merge` and `replace`.

- **`type`**: The target type. Currently the only supported value is
  `opentelemetry`.

- **`location`**: Base URL of the remote OTLP/HTTP endpoint, for example
  `http://otel-collector:4318` or `https://ingest.example.com:4318`.
  Pebble appends `/v1/traces` when forwarding spans.

### Optional Fields

- **`services`**: A list of service names to collect traces from. For
  each named service, Pebble injects the OTLP endpoint environment
  variables at service start (see [Service Endpoint Injection]) and
  emits Pebble-side lifecycle spans for that service. Use the special
  keyword `all` to include every service in the plan.

  If `services` is omitted, no service-specific spans are collected or
  emitted, but Pebble-internal spans (plan updates, changes) are still
  forwarded.

  When merging, `services` lists are appended. Prefix a service name
  with `-` (e.g. `-svc1`) to remove a previously added entry. `-all`
  removes all entries.

- **`labels`**: Key/value pairs added as resource attributes on every
  outgoing span, both Pebble-emitted and service-received. Values may
  reference `$ENV_VARS`, which are interpolated from the Pebble daemon
  environment at startup.

  Labels whose key begins with `pebble.` or `pebble_` are reserved and
  are rejected at plan validation.

- **`tls`**: TLS configuration for the outbound connection to `location`.
  Each field accepts either a file path or a PEM-encoded string inline.
  - `ca-cert`: CA certificate used to verify the server. When absent,
    the system certificate pool is used.
  - `client-cert` and `client-key`: Client certificate and key for
    mutual TLS. Both must be set together.

- **`headers`**: Arbitrary HTTP headers sent on every outbound request
  to `location`. Commonly used for authentication, for example:
  ```yaml
  headers:
      Authorization: "Bearer <token>"
  ```


## Local OTLP Receiver

When any `trace-targets` entry has one or more `services` configured,
Pebble registers OTLP receiver routes for traces. Services running on
the same host send spans to these routes, and Pebble forwards them to
the configured targets.

The OTLP trace routes are deregistered when no `trace-targets` entries have
services configured. The underlying listener (shared across signal types)
may remain active for other signals.

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

### Per-Service Endpoint Paths

Each service gets its own distinct endpoint path so Pebble can
unambiguously attribute incoming spans to the correct service without
parsing the span payload. Pebble handles `POST` requests at:

```
/v1/services/{service}/otlp/v1/traces
```

The full URL injected via `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` (see
[Service Endpoint Injection]) is used as-is by the SDK; no path is
appended.

Both `application/json` and `application/x-protobuf` (binary Protobuf)
request bodies are accepted. Pebble enriches the payload and forwards it
to backends using the same encoding. Any other `Content-Type` returns
`415 Unsupported Media Type`. The implementation relies solely on
`google.golang.org/protobuf`; no gRPC or OTel SDK library dependency
is required.

### Service Endpoint Injection

When a service is started and its name appears in any `trace-targets`
entry's `services` list, Pebble injects the following environment
variables before the process is launched:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://<receiver-address>/v1/services/<name>/otlp/v1/traces` |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | `http/json` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_SERVICE_NAME` | `<name>` |

The per-signal endpoint variable is used as-is by the SDK
(no path is appended). `OTEL_SERVICE_NAME` is the only variable shared
across signal types; if it was already injected by another target type
for this service it is not re-injected.

`OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/json` steers the OTel SDK to
use the HTTP/JSON transport. `OTEL_TRACES_EXPORTER=otlp` ensures the SDK
routes traces through the OTLP exporter rather than a console or no-op
exporter. `OTEL_SERVICE_NAME` sets the `service.name` resource attribute
in the SDK itself, consistent with the name Pebble uses during enrichment.

### Span Enrichment

On receiving a valid JSON span payload for service `<name>`, Pebble
merges the following resource attributes into each `ResourceSpans`
entry before forwarding:

| Attribute | Value | Notes |
|---|---|---|
| `service.name` | `<name>` | Overrides any value set by the SDK |
| `pebble.service` | `<name>` | Always added |
| `service.instance.id` | UUID generated each time the service starts or restarts | Added if not already present |

Custom `labels` configured on the matching `trace-targets` entry are
also added as resource attributes. If a label key conflicts with an
attribute already present in the payload, the label value wins.

### Forwarding

Enriched spans are forwarded to every `trace-targets` entry whose
`services` list includes the originating service. If a service appears
in multiple targets, the enriched payload is sent to each independently.

Pebble responds to the service's HTTP request with `200 OK` once it has
accepted the payload into its outbound buffer, not once it has
confirmed delivery to the backend. Delivery errors to the remote backend
are logged but do not cause the receiver to return an error to the
service.


## Pebble-Emitted Spans

Pebble-emitted spans for service lifecycle events, health checks, plan
updates, and exec commands are specified in
[OpenTelemetry Pebble Spans](OP0X6-pebble-spans.md).


## Retry and Error Handling

### Outbound (Pebble → backend)

Pebble retries on `429 Too Many Requests`, `502 Bad Gateway`,
`503 Service Unavailable`, and `504 Gateway Timeout`, honouring the
`Retry-After` header when present and using exponential backoff with
jitter otherwise. All other non-2xx responses are non-retryable; the
batch is dropped and a warning is logged.

Batches that cannot be delivered within the in-memory buffer limit are
dropped with a log warning. Backend delivery failures never affect
service management or the receiver's response to services.

### Inbound (service → Pebble receiver)

- Unknown service names (not present in any `trace-targets` `services`
  list) receive `200 OK` with an empty `ExportTraceServiceResponse`
  body; the payload is silently discarded.
- Malformed JSON returns `400 Bad Request`.
- Pebble always returns `200 OK` with an empty
  `ExportTraceServiceResponse` body on success; partial success
  semantics (`rejected_spans`) are not used in this implementation.

Error responses (`4xx`, `5xx`) include a `Status` message body. When
the request used `application/json`, the body is JSON-encoded; when
`application/x-protobuf`, it is binary-Protobuf-encoded.


## Examples

### Collect service traces and send to a local collector

```yaml
trace-targets:
    local-collector:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]
```

All services in the plan have `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and
`OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` injected automatically.

### Cloud backend with authentication, selected services only

```yaml
trace-targets:
    cloud-backend:
        override: replace
        type: opentelemetry
        location: https://ingest.example.com:4318
        services: [web-server, worker]
        headers:
            Authorization: "Bearer eyJhbGci..."
        labels:
            environment: production
            region: us-east-1
```

Only `web-server` and `worker` receive injected OTLP environment
variables. Other services are unaffected.

### Multi-layer configuration

Base layer (`001-base.yaml`):
```yaml
trace-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://localhost:4318
        services: [all]
```

Override layer (`002-override.yaml`):
```yaml
trace-targets:
    collector:
        override: merge
        type: opentelemetry
        services: [-debug-svc]
        labels:
            deployment: staging
```

The merged result excludes `debug-svc` from trace collection.

### Service overriding the injected endpoint

```yaml
services:
    my-service:
        override: replace
        command: ./my-service
        environment:
            OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: http://custom-collector:4318/v1/services/my-service/otlp/v1/traces
            OTEL_EXPORTER_OTLP_TRACES_PROTOCOL: http/json
```

Pebble does not overwrite environment variables that are already set in
the service definition. `my-service` sends traces directly to
`custom-collector` rather than through Pebble's receiver.


## Relation to Log Forwarding

`trace-targets` and `log-targets` are independent sections. The
`type: opentelemetry` entry in `log-targets` forwards service *logs* to
the OTLP Logs API (`/v1/logs`); `trace-targets` handles *traces* via
`/v1/traces`. They may point to the same remote endpoint.


## Out of Scope

- **gRPC receiver**: The local receiver only supports OTLP/HTTP JSON.
  gRPC support (port 4317) may be added in a future spec.
- **Metrics export**: Covered separately by Pebble's existing metrics
  abstraction.
- **Log–trace correlation**: Automatic injection of trace IDs into
  forwarded log records is a future consideration.
- **Trace context propagation for services**: Pebble does not inject
  W3C `traceparent` into long-running service environments. Services
  manage their own trace context through the OTel SDK. `pebble exec`
  is the exception — see [Exec Commands].


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
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://<receiver-address>/v1/services/<name>/otlp/v1/traces` |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | `http/json` |
| `OTEL_SERVICE_NAME` | `<name>` |

Note: `TRACEPARENT` and `TRACESTATE` are an emerging community
convention recognised by some tools (such as the Jenkins OTel plugin
and OTel CLI) rather than a formal OTel SDK specification. Most language
SDKs do not automatically read these variables. The executed binary must
explicitly support them to propagate the exec span as a parent.

When the exec command runs with `--context=<service>` and that service
appears in a `trace-targets` `services` list, the command also inherits
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`,
and `OTEL_SERVICE_NAME` from the service's resolved environment, giving it
a complete OTel configuration to emit and forward its own child spans
through Pebble's local receiver.
