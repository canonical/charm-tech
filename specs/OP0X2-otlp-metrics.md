# OP0X2 — OpenTelemetry Metrics via OTLP

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

## Abstract

This spec describes adding support for Pebble to:

1. **Receive** OpenTelemetry metrics from services via a local OTLP/HTTP
   endpoint, enrich them with Pebble resource attributes, and forward
   them to a remote metrics backend.
2. **Emit** its own metrics covering service states and health checks,
   and forward those to the same backend.

Transport is OTLP/HTTP with JSON encoding throughout. No new binary
dependencies (e.g. protobuf codegen or gRPC) are required.


## Rationale

Pebble manages the lifecycle of one or more services and is often deployed
in container or embedded environments that integrate with an observability
stack. Two problems motivate this feature:

**Service metrics**: Services instrumented with an OTel SDK need a local
collector endpoint to send metrics to. Rather than requiring operators
to run a separate OTel Collector sidecar, Pebble can act as that local
agent, receiving and forwarding metrics on behalf of each service.

**Pebble metrics**: Operators need visibility into Pebble's own metrics —
service status (active/inactive), start counts, and health check
outcomes — so they can correlate infrastructure health with application
behaviour.


## Plan Configuration

A new top-level section `metric-targets` is added to the Pebble plan. It
follows the same map-based, multi-layer merge pattern used by
`log-targets`, and is structurally identical to `trace-targets`.

```yaml
metric-targets:
    <target-name>:
        override: merge | replace
        type: opentelemetry
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        push-interval: <duration>
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
  Pebble appends `/v1/metrics` when forwarding metrics.

### Optional Fields

- **`services`**: A list of service names to collect metrics from. For
  each named service, Pebble injects the OTLP endpoint environment
  variables at service start (see [Service Endpoint Injection]) and
  forwards Pebble-internal metrics for that service. Use the special
  keyword `all` to include every service in the plan.

  If `services` is omitted, no service-specific metrics are collected or
  forwarded, but Pebble-internal metrics (service states, checks) are
  still forwarded.

  When merging, `services` lists are appended. Prefix a service name
  with `-` (e.g. `-svc1`) to remove a previously added entry. `-all`
  removes all entries.

- **`labels`**: Key/value pairs added as resource attributes on every
  outgoing metric, both Pebble-emitted and service-received. Values may
  reference `$ENV_VARS`, which are interpolated from the Pebble daemon
  environment at startup.

  Labels whose key begins with `pebble.` or `pebble_` are reserved and
  are rejected at plan validation.

- **`push-interval`**: How often Pebble emits its internal metrics to
  configured backends. Accepts a Go duration string (e.g. `30s`, `1m`,
  `2m30s`). Default: `60s`.

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

When any `metric-targets` entry has one or more `services` configured,
Pebble automatically starts a local OTLP/HTTP receiver. The receiver
accepts metric data points from services running on the same host and
forwards them to the configured targets.

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
unambiguously attribute incoming metrics to the correct service without
parsing the payload:

```
http://<receiver-address>/v1/services/<service-name>/otlp
```

Pebble handles `POST` requests at:

```
/v1/services/{service}/otlp/v1/metrics
```

The full URL injected via `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` (see
[Service Endpoint Injection]) is used as-is by the SDK; no path is
appended.

Both `application/json` and `application/x-protobuf` (binary Protobuf)
request bodies are accepted. Pebble enriches the payload and forwards it
to backends using the same encoding. Any other `Content-Type` returns
`415 Unsupported Media Type`. The implementation relies solely on
`google.golang.org/protobuf`; no gRPC or OTel SDK library dependency
is required.

### Service Endpoint Injection

When a service is started and its name appears in any `metric-targets`
entry's `services` list, Pebble injects the following environment
variables before the process is launched:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | `http://<receiver-address>/v1/services/<name>/otlp/v1/metrics` |
| `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` | `http/json` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_SERVICE_NAME` | `<name>` |

The per-signal endpoint variable is used as-is by the SDK (no path is
appended). `OTEL_SERVICE_NAME` is the only variable shared across signal
types; if it was already injected by another target type for this service
it is not re-injected.

Each variable is only injected if it is not already present in the
service's resolved environment. An operator can override any of these
in the service's `environment:` block; Pebble will not overwrite an
explicitly set value.

`OTEL_METRICS_EXPORTER=otlp` ensures the SDK routes metrics through
the OTLP exporter rather than a Prometheus scrape endpoint or no-op
exporter. `OTEL_SERVICE_NAME` sets the `service.name` resource
attribute in the SDK itself, consistent with the name Pebble uses
during enrichment.


### Metric Enrichment

On receiving a valid metrics payload for service `<name>`, Pebble
merges the following resource attributes into each `ResourceMetrics`
entry before forwarding:

| Attribute | Value | Notes |
|---|---|---|
| `service.name` | `<name>` | Overrides any value set by the SDK |
| `pebble.service` | `<name>` | Always added |
| `service.instance.id` | UUID generated each time the service starts or restarts | Added if not already present |

Custom `labels` configured on the matching `metric-targets` entry are
also added as resource attributes. If a label key conflicts with an
attribute already present in the payload, the label value wins.


## Forwarding

Enriched metrics are forwarded to every `metric-targets` entry whose
`services` list includes the originating service. If a service appears
in multiple targets, the enriched payload is sent to each independently.

Pebble responds to the service's HTTP request with `200 OK` once it has
accepted the payload into its outbound buffer, not once it has
confirmed delivery to the backend. Delivery errors to the remote backend
are logged but do not cause the receiver to return an error to the
service.


## Pebble-Emitted Metrics

In addition to forwarding service metrics, Pebble generates its own
metrics for internal operations. These are forwarded to all configured
`metric-targets` regardless of the `services` filter.

Service-labelled Pebble metrics (those with a `service` attribute) are
only forwarded to targets whose `services` list includes that service
(or `all`). Check-labelled Pebble metrics are always forwarded when
check execution occurs.

All Pebble-emitted metrics carry the following resource attributes:

| Attribute | Value |
|---|---|
| `service.name` | `pebble` |
| `service.version` | Pebble version string |
| `service.instance.id` | UUID generated once at Pebble daemon startup |

### Emission Interval

Pebble emits its internal metrics at a configurable interval, defaulting
to 60 seconds. Set via the `push-interval` field on each `metric-targets`
entry.

### Metric Definitions

| Metric name | OTLP type | Description | Attributes |
|---|---|---|---|
| `pebble_service_active` | Gauge (int) | 1 if the service is active, 0 otherwise | `service=<name>` |
| `pebble_service_start_count` | Sum, monotonic, cumulative | Total number of times the service has started | `service=<name>` |
| `pebble_check_up` | Gauge (int) | 1 if the health check is passing, 0 otherwise | `check=<name>` |
| `pebble_check_success_count` | Sum, monotonic, cumulative | Total number of successful check executions | `check=<name>` |
| `pebble_check_failure_count` | Sum, monotonic, cumulative | Total number of failed check executions | `check=<name>` |

The gauge metrics (`pebble_service_active` and `pebble_check_up`) are
reported as single data points with the current value. The count metrics
(`_start_count`, `_success_count`, `_failure_count`) are monotonic sums
that accumulate over the lifetime of the Pebble daemon.

Monotonic cumulative counters (`_start_count`, `_success_count`,
`_failure_count`) reset when Pebble restarts. Backends should detect
resets using the `startTimeUnixNano` field on each sum data point,
which Pebble sets to the daemon's start time.


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

- Unknown service names (not present in any `metric-targets` `services`
  list) receive `200 OK` with an empty `ExportMetricsServiceResponse`
  body; the payload is silently discarded.
- Malformed JSON returns `400 Bad Request`.
- Pebble always returns `200 OK` with an empty
  `ExportMetricsServiceResponse` body on success; partial success
  semantics (`rejected_data_points`) are not used in this implementation.

Error responses (`4xx`, `5xx`) include a `Status` message body. When
the request used `application/json`, the body is JSON-encoded; when
`application/x-protobuf`, it is binary-Protobuf-encoded.


## Examples

### Collect service metrics and send to a local collector

```yaml
metric-targets:
    local-collector:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]
```

All services in the plan have `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` and
`OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` injected automatically.

### Cloud backend with authentication, selected services only

```yaml
metric-targets:
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
metric-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://localhost:4318
        services: [all]
```

Override layer (`002-override.yaml`):
```yaml
metric-targets:
    collector:
        override: merge
        type: opentelemetry
        services: [-debug-svc]
        labels:
            deployment: staging
```

The merged result excludes `debug-svc` from metric collection.

### Service overriding the injected endpoint

```yaml
services:
    my-service:
        override: replace
        command: ./my-service
        environment:
            OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: http://custom-collector:4318
            OTEL_EXPORTER_OTLP_METRICS_PROTOCOL: http/json
```

Pebble does not overwrite environment variables that are already set in
the service definition. `my-service` sends metrics directly to
`custom-collector` rather than through Pebble's receiver.


## Relation to Other Observability Features

`metric-targets` is independent of `trace-targets` and `log-targets`.
The `type: opentelemetry` entry in `log-targets` forwards service *logs*
to the OTLP Logs API (`/v1/logs`); `metric-targets` handles *metrics*
via `/v1/metrics`; and `trace-targets` handles *traces* via `/v1/traces`.
They may point to the same remote endpoint.

The existing pull-based `/v1/metrics` API remains unchanged and serves
prometheus-format metrics directly from Pebble. This spec adds push-based
forwarding to remote backends, not replacement of the existing endpoint.


## Out of Scope

- **gRPC receiver**: The local receiver only supports OTLP/HTTP JSON.
  gRPC support (port 4317) may be added in a future spec.
- **Metrics export via the existing pull API**: The `/v1/metrics` endpoint
  continues to serve prometheus-format metrics and is not modified by
  this feature.
- **Metrics–trace correlation**: Automatic injection of metric metadata
  into spans or vice versa is a future consideration.
