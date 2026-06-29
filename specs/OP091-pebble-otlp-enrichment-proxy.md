# OP091 — Pebble as an OTLP Enrichment Proxy

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

<!-- mdtog begin hs=-1 -->

## Abstract

This spec describes adding support for Pebble to act as a local OTLP
enrichment proxy: services running under Pebble send OpenTelemetry
logs, metrics, and traces to a Pebble-hosted OTLP/HTTP endpoint;
Pebble enriches the payloads with consistent resource attributes and
forwards them to one or more remote backends.

A single local receiver and a single forwarding pipeline serve all
three signal types. Plan configuration, environment-variable
injection, enrichment, and error handling follow a common pattern,
with signal-specific differences captured in tables.

Transport is OTLP/HTTP with JSON or binary-Protobuf encoding.


## Rationale

Pebble is a layered service manager primarily used to run the
workloads of Juju Charms inside Kubernetes containers. In this
deployment model, observability is typically configured by the charm
on behalf of the workload: the charm decides which signals to collect,
where to send them, and what identifying labels to attach. Different
services within the same container may need to be wired to different
observability stacks, and that wiring frequently changes at runtime as
relations come and go or charm configuration is updated.

Without a local agent, every charm has to teach its workloads how to
discover collector endpoints, re-launch processes when those endpoints
change, and stamp consistent identity attributes onto outgoing
signals. That logic ends up duplicated across charms and is awkward to
update without restarting workloads.

By embedding an OTLP enrichment proxy in Pebble itself, the charm only
has to update Pebble's plan. Pebble exposes a stable local OTLP
endpoint to each service, injects the right environment variables at
service start, and re-routes traffic to whichever backends the current
plan specifies. Bundling logs, metrics, and traces into one feature
avoids duplicating the receiver, listener, env-var injection, and
forwarder for each signal type.


## Plan Configuration

This spec uses three top-level plan sections that share an identical
schema:

- `log-targets` — pre-existing; gains a new behaviour for entries with
  `type: opentelemetry`. Other `log-targets` types are unaffected by
  this spec.
- `metric-targets` — new in this spec.
- `trace-targets` — new in this spec.

```yaml
log-targets:
    <target-name>:
        override: merge | replace
        type: opentelemetry
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        headers:
            <header-name>: <value>

metric-targets:
    <target-name>:
        override: merge | replace
        type: opentelemetry
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        headers:
            <header-name>: <value>

trace-targets:
    <target-name>:
        override: merge | replace
        type: opentelemetry
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        headers:
            <header-name>: <value>
```

### Required Fields

- **`override`**: `merge` or `replace`, controlling how this entry
  combines with same-named entries in lower layers.
- **`type`**: The only value covered by this spec is `opentelemetry`.
- **`location`**: Base URL of the remote OTLP/HTTP endpoint, e.g.
  `http://otel-collector:4318`. Pebble appends the standard per-signal
  path when forwarding (`/v1/logs`, `/v1/metrics`, `/v1/traces`).

### Optional Fields

- **`services`**: Service names to enrol. For each enrolled service,
  Pebble injects OTLP environment variables at service start (see
  [Service Endpoint Injection]) and forwards that service's signals to
  this target. The keyword `all` enrols every service in the plan.
  When merging, lists are appended; prefix `-svc` to remove a
  previously added service, or `-all` to clear. If `services` is
  omitted, no signals are forwarded through this target.

- **`labels`**: Key/value pairs added as resource attributes on every
  outgoing signal. Values may reference `$ENV_VARS`, interpolated from
  the daemon environment at startup. Keys beginning with `pebble.` or
  `pebble_` are reserved and rejected at plan validation.

- **`headers`**: Arbitrary HTTP headers added to every outbound
  request, commonly used for `Authorization`.


## Local OTLP Receiver

When any opentelemetry target across the three sections has at least
one enrolled service, Pebble activates a local OTLP/HTTP receiver and
registers the corresponding signal route(s).

### Receiver Address

Pebble exposes OTLP receiver routes on:

- **Pebble's HTTP API listener**, when configured with a TCP address.
  Requests are accepted only from loopback addresses (`127.0.0.1` /
  `::1`); other remotes receive `403 Forbidden`.
- **A dedicated loopback listener** on a randomly chosen port, started
  at daemon startup when no TCP HTTP API listener is configured.

The actual address is determined at startup and substituted into the
environment variables injected when services start.

### Per-Service Endpoint Paths

Each service has a distinct path so Pebble can attribute incoming
payloads without parsing them:

```
POST /v1/services/{service}/otlp/v1/logs
POST /v1/services/{service}/otlp/v1/metrics
POST /v1/services/{service}/otlp/v1/traces
```

The full URL is injected into the SDK via the per-signal endpoint
variable and used as-is — the SDK does not append a path.

Both `application/json` and `application/x-protobuf` request bodies
are accepted. Pebble enriches the payload and forwards it using the
same encoding it received. Other content types return
`415 Unsupported Media Type`.


## Service Endpoint Injection

When a service starts and its name appears in the `services` list of
any matching target, Pebble injects per-signal environment variables
into the process — but only if not already set in the resolved
environment. Operators can override any injected value via the
service's `environment:` block.

| Variable | Value | Set when service is enrolled in… |
|---|---|---|
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | `http://<recv>/v1/services/<name>/otlp/v1/logs` | a `log-targets` opentelemetry target |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | `http/json` | ″ |
| `OTEL_LOGS_EXPORTER` | `otlp` | ″ |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | `http://<recv>/v1/services/<name>/otlp/v1/metrics` | a `metric-targets` target |
| `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` | `http/json` | ″ |
| `OTEL_METRICS_EXPORTER` | `otlp` | ″ |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | `http://<recv>/v1/services/<name>/otlp/v1/traces` | a `trace-targets` target |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | `http/json` | ″ |
| `OTEL_TRACES_EXPORTER` | `otlp` | ″ |
| `OTEL_SERVICE_NAME` | `<name>` | any of the above |

`OTEL_SERVICE_NAME` is the only variable shared across signal types;
it is set once even if the service is enrolled in multiple sections.
The `*_EXPORTER` variables steer the SDK to the OTLP exporter rather
than a console / Prometheus / no-op exporter.


## Pebble Exec Context Propagation

`pebble exec` is a deliberate exception to Pebble's general policy of
not injecting trace context into managed processes. Each `/v1/exec`
request is typically issued by an external caller — a deployment
script, test harness, CI pipeline, or charm hook — that already owns
a distributed trace. To let the executed command stitch its own spans
into that trace, Pebble forwards W3C trace context from the inbound
request into the command's environment.

If the inbound `/v1/exec` request carries a `traceparent` header,
Pebble injects the following into the executed command's environment
before launch, but only if not already set:

| Variable | Value |
|---|---|
| `TRACEPARENT` | The `traceparent` from the inbound request |
| `TRACESTATE` | The `tracestate` from the inbound request, or empty |

When `pebble exec --context=<service>` is used and that service is
enrolled in a `trace-targets` entry, the exec command additionally
inherits `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`, and `OTEL_SERVICE_NAME` from the
service's resolved environment. Combined with the propagated
`TRACEPARENT`, this gives the command everything it needs to emit
child spans through Pebble's local receiver.

`TRACEPARENT` / `TRACESTATE` are an emerging community convention
(recognised by tools such as the Jenkins OTel plugin and `otel-cli`)
rather than a formal OTel SDK specification. Most language SDKs do
not read these variables automatically; the executed binary must
explicitly opt in to use them as a parent context.


## Signal Enrichment

On receiving a valid payload for service `<name>`, Pebble merges the
following resource attributes into every `Resource{Logs,Metrics,Spans}`
entry before forwarding:

| Attribute | Value | Notes |
|---|---|---|
| `service.name` | `<name>` | Overrides any value set by the SDK |
| `pebble.service` | `<name>` | Always added |
| `service.instance.id` | UUID generated at each (re)start of the service | Added if not already present |

Custom `labels` from the matching target are also added as resource
attributes. If a label key conflicts with an existing payload
attribute, the configured label wins.


## Forwarding

Enriched payloads are forwarded to every matching target whose
`services` list includes the originating service. A service that
appears in multiple targets has the payload sent to each
independently.

Pebble responds `200 OK` once the payload is accepted into its
outbound buffer, not once delivery to the remote backend is confirmed.
Backend delivery failures are logged but never propagate back to the
service or affect service management.


## Retry and Error Handling

### Outbound (Pebble → backend)

Pebble retries on `429`, `502`, `503`, and `504`, honouring
`Retry-After` when present and otherwise using exponential backoff with
jitter. All other non-2xx responses are non-retryable; the batch is
dropped with a logged warning. Batches that exceed the in-memory
buffer are dropped with a logged warning. Backend failures never affect
service management or the receiver's response.

### Inbound (service → Pebble receiver)

- **Unknown service** (not enrolled in any target's `services` list):
  `200 OK` with an empty `Export*ServiceResponse` body; payload
  silently discarded.
- **Malformed body**: `400 Bad Request`.
- **Unsupported `Content-Type`**: `415 Unsupported Media Type`.
- **Success**: `200 OK` with an empty `Export*ServiceResponse` body.
  Partial-success semantics (`rejected_*`) are not used.
- **Error responses** carry a `Status` body, encoded matching the
  request's `Content-Type` (JSON or binary Protobuf).


## Examples

### All signals to a local collector

```yaml
log-targets:
    otel-logs:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]

metric-targets:
    otel-metrics:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]

trace-targets:
    otel-traces:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]
```

Every service receives the full set of OTLP env vars and a single
`OTEL_SERVICE_NAME`.

### Cloud backend with auth, selected services

```yaml
trace-targets:
    cloud:
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

Only `web-server` and `worker` are enrolled and receive injected vars.

### Multi-layer override

Base layer:
```yaml
metric-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://localhost:4318
        services: [all]
```

Override layer:
```yaml
metric-targets:
    collector:
        override: merge
        type: opentelemetry
        services: [-debug-svc]
        labels:
            deployment: staging
```

The merged result excludes `debug-svc` and adds the `deployment` label.

### Operator override of an injected endpoint

```yaml
services:
    my-service:
        override: replace
        command: ./my-service
        environment:
            OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: http://custom-collector:4318/v1/traces
            OTEL_EXPORTER_OTLP_TRACES_PROTOCOL: http/json
```

Pebble does not overwrite explicitly set environment variables;
`my-service` bypasses the local receiver for traces.


## Out of Scope

- **Pebble-emitted signals**: Pebble does not, under this spec, emit
  its own metrics (e.g. service-state gauges, check counts), spans
  (e.g. service-lifecycle events, plan-update timing, exec
  invocations), or log records. Producing such signals — and any
  associated trace-context propagation, e.g. `TRACEPARENT` injection
  for `pebble exec` — is left to a future spec. The receiver and
  forwarder defined here are the substrate those features would build
  on.
- **TLS for outbound connections**: Configuring CA verification,
  client certificates, or mTLS to the remote backend is out of scope
  here and will be handled by a separate spec. Until then, secure
  transport relies on whatever defaults the underlying HTTP client
  provides for `https://` URLs.
- **gRPC receiver (port 4317)**: HTTP only. May be added in a future
  spec.
- **Cross-signal correlation**: Automatic injection of trace IDs into
  forwarded log records, or metric exemplars referencing spans, is a
  future consideration.
- **Trace context propagation for long-running services**: Pebble
  does not inject `TRACEPARENT` into the environment of services
  defined in the plan — services manage their own context. `pebble
  exec` is the deliberate exception, covered above.
- **Pebble-emitted exec spans**: This spec only forwards an existing
  inbound `traceparent` into the executed command. Pebble does not
  itself create an `exec: <command>` span as a child of that context;
  emitting such a span is part of the future Pebble-emitted-signals
  work.
- **OTel SDK side-effects of `*_EXPORTER` injection**: Setting
  `OTEL_LOGS_EXPORTER=otlp` activates the OTel log bridge; setting
  `OTEL_METRICS_EXPORTER=otlp` routes metrics through OTLP rather than
  a Prometheus scrape endpoint. Services that intentionally use a
  different exporter must set the variable explicitly in their
  `environment:` block.

<!-- mdtog end -->
