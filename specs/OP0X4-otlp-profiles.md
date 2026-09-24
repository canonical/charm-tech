# OP0X4 — OpenTelemetry Profiles via OTLP

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 25 May 2026 |

## Abstract

This spec describes adding support for Pebble to:

1. **Receive** OpenTelemetry profiles from services via a local OTLP/HTTP
   endpoint, enrich them with Pebble resource attributes, and forward
   them to a remote profile backend.

Pebble does **not** emit its own profiles. Unlike traces and metrics,
`profile-targets` only handles profile data received from services.

Transport is OTLP/HTTP with JSON and binary Protobuf encodings. No
new binary dependencies (e.g. protobuf codegen or gRPC) are required.

## Experimental Status

The OTel profiling signal is **alpha** as of 2025. The endpoint path
`/v1development/profiles` (not `/v1/profiles`) reflects this alpha
status. Pebble's profile support is also considered experimental and
may change as the OTel spec matures.

## Rationale

Pebble manages the lifecycle of one or more services and is often
deployed in container or embedded environments that integrate with an
observability stack. Two problems motivate this feature:

**Service profiles**: Services instrumented with profiling agents need
a local collector endpoint to send profiles to. Rather than requiring
operators to run a separate OTel Collector sidecar, Pebble can act as
that local agent, receiving and forwarding profiles on behalf of each
service.

**Unified observability**: Operators want to correlate profiles with
traces and metrics using the same backend infrastructure. Supporting
profiles alongside traces and metrics provides a complete observability
stack from a single local agent.


## Plan Configuration

A new top-level section `profile-targets` is added to the Pebble plan.
It follows the same map-based, multi-layer merge pattern used by
`log-targets` and `trace-targets`.

```yaml
profile-targets:
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

- **`override`**: How this target definition is combined with any
  existing definition of the same name in a lower layer. Supported
  values are `merge` and `replace`.

- **`type`**: The target type. Currently the only supported value is
  `opentelemetry`.

- **`location`**: Base URL of the remote OTLP/HTTP endpoint, for
  example `http://otel-collector:4318` or
  `https://ingest.example.com:4318`. Pebble forwards profiles according
  to the OTel profiles API specification.

### Optional Fields

- **`services`**: A list of service names to collect profiles from. For
  each named service, Pebble injects the OTLP endpoint environment
  variables at service start (see [Service Endpoint Injection]) and
  forwards profiles for that service. Use the special keyword `all` to
  include every service in the plan.

  If `services` is omitted, no service-specific profiles are collected,
  but Pebble still accepts profiles at the receiver (and silently
  discards them to avoid SDK error noise).

  When merging, `services` lists are appended. Prefix a service name
  with `-` (e.g. `-svc1`) to remove a previously added entry. `-all`
  removes all entries.

- **`labels`**: Key/value pairs added as resource attributes on every
  outgoing profile, both Pebble-emitted and service-received. Values
  may reference `$ENV_VARS`, which are interpolated from the Pebble
  daemon environment at startup.

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

When any `profile-targets` entry has one or more `services` configured,
Pebble automatically starts a local OTLP/HTTP receiver. This listener
accepts profiles from services running on the same host and forwards
them to the configured targets.

The OTLP profile routes are deregistered when no `profile-targets`
entries have services configured. The underlying listener (shared
across signal types) may remain active for other signals.

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
unambiguously attribute incoming profiles to the correct service
without parsing the profile payload:

```
http://<receiver-address>/v1/services/<service-name>/otlp
```

Pebble handles `POST` requests at:

```
/v1/services/{service}/otlp/v1development/profiles
```

The `development` path segment reflects the alpha status of the OTel
profiling signal.

Both `application/json` and `application/x-protobuf` (binary Protobuf)
request bodies are accepted. Pebble enriches the payload and forwards it
to backends using the same encoding. Any other `Content-Type` returns
`415 Unsupported Media Type`. The implementation relies solely on
`google.golang.org/protobuf`; no gRPC or OTel SDK library dependency
is required.

Note: most current profiling agents emit binary Protobuf rather than
JSON; Protobuf acceptance is particularly important for this signal.


### Service Endpoint Injection

When a service is started and its name appears in any `profile-targets`
entry's `services` list, Pebble injects the following environment
variables before the process is launched:

| Variable | Value |
|---|---|
| `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` | `http://<receiver-address>/v1/services/<name>/otlp/v1development/profiles` |
| `OTEL_EXPORTER_OTLP_PROFILES_PROTOCOL` | `http/json` |
| `OTEL_SERVICE_NAME` | `<name>` |

Each variable is only injected if it is not already present in the
service's resolved environment. An operator can override any of these
in the service's `environment:` block; Pebble will not overwrite an
explicitly set value.

The per-signal endpoint variable is used as-is by the SDK (no path is
appended). `OTEL_SERVICE_NAME` is the only variable shared across signal
types; if it was already injected by another target type for this service
it is not re-injected.

Note: `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` is not yet part of the
OpenTelemetry specification as of this writing. Pebble injects it in
anticipation of standardisation; profiling agents that respect OTel env
var conventions should honour it once standardised.

The OTel profiling signal does not yet define a standardised
`OTEL_PROFILES_EXPORTER` environment variable. Pebble does not inject
one. When the OTel profiling auto-configuration spec stabilises, Pebble
will add injection of `OTEL_EXPORTER_OTLP_PROFILES=otlp`.


### Profile Enrichment

On receiving a valid profile payload for service `<name>`, Pebble
merges the following resource attributes into each `ResourceProfiles`
entry before forwarding:

| Attribute | Value | Notes |
|---|---|---|
| `service.name` | `<name>` | Overrides any value set by the SDK |
| `pebble.service` | `<name>` | Always added |
| `service.instance.id` | UUID generated each time the service starts or restarts | Added if not already present |

Custom `labels` configured on the matching `profile-targets` entry are
also added as resource attributes. If a label key conflicts with an
attribute already present in the payload, the label value wins.


### Forwarding

Enriched profiles are forwarded to every `profile-targets` entry whose
`services` list includes the originating service. If a service appears
in multiple targets, the enriched payload is sent to each independently.

Pebble responds to the service's HTTP request with `200 OK` once it has
accepted the payload into its outbound buffer, not once it has
confirmed delivery to the backend. Delivery errors to the remote backend
are logged but do not cause the receiver to return an error to the
service.


## Profile Types

Pebble supports all profile types that conform to the OTel profiling
signal specification:

- **On-CPU profiling**: CPU execution time samples, typically generated
  by signal handlers (SIGPROF) or JIT sampling.
- **Off-CPU profiling**: Blocked/waiting time samples (e.g. lock
  contention, I/O wait).
- **Heap / memory allocation profiles**: Live and dead object sizes,
  allocation stacks.
- **Language-runtime profiles**: Go pprof, Java JFR, and similar
  native formats via SDK instrumentation.
- **eBPF-based zero-instrumentation profiling**: Linux kernel-level
  profiling with minimal runtime overhead.

Note: Pebble is not a profiling agent. It only acts as the OTLP
endpoint. Deployment and configuration of the actual profiling agent
(eBPF programs, language SDKs, standalone profilers) is outside the
scope of this spec.


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

- Unknown service names (not present in any `profile-targets` `services`
  list) receive `200 OK` with an empty `ExportProfilesServiceResponse`
  body; the payload is silently discarded.
- Malformed content returns `400 Bad Request`.
- Pebble always returns `200 OK` with an empty `ExportProfilesServiceResponse`
  body on success; partial success semantics (`rejected_profiles`) are
  not used in this implementation.

Error responses (`4xx`, `5xx`) include a `Status` message body. When
the request used `application/json`, the body is JSON-encoded; when
`application/x-protobuf`, it is binary-Protobuf-encoded.


## Examples

### Collect service profiles and send to a local collector

```yaml
profile-targets:
    local-collector:
        override: replace
        type: opentelemetry
        location: http://otel-collector:4318
        services: [all]
```

All services in the plan have `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` and
`OTEL_EXPORTER_OTLP_PROFILES_PROTOCOL` injected automatically.

### Cloud backend with authentication, selected services only

```yaml
profile-targets:
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
profile-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://localhost:4318
        services: [all]
```

Override layer (`002-override.yaml`):
```yaml
profile-targets:
    collector:
        override: merge
        type: opentelemetry
        services: [-debug-svc]
        labels:
            deployment: staging
```

The merged result excludes `debug-svc` from profile collection.

### Service overriding the injected endpoint

```yaml
services:
    my-service:
        override: replace
        command: ./my-service
        environment:
            OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT: http://custom-collector:4318/v1/services/my-service/otlp/v1development/profiles
            OTEL_EXPORTER_OTLP_PROFILES_PROTOCOL: http/json
```

Pebble does not overwrite environment variables that are already set in
the service definition. `my-service` sends profiles directly to
`custom-collector` rather than through Pebble's receiver.


## Agent-Specific Configuration

Many profiling agents (eBPF-based, language runtimes) use their own
endpoint configuration rather than the standard `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT`
environment variable. Pebble's automatic injection only applies to agents
that respect the standard OTel env vars.

For agents with their own config (e.g. Elastic eBPF, async-profiler,
third-party collectors), the operator must manually configure the endpoint
`http://<receiver-address>/v1/services/<service-name>/otlp` in the agent.

| Agent Type | Configuration Approach |
|---|---|
| OTel SDK-based | Automatic via `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` injection |
| eBPF-based (e.g. Elastic) | Manual endpoint config required |
| Language runtime (e.g. Go pprof) | Agent-specific config or env vars |
| Standalone profilers | Manual endpoint config required |


## Relation to Other Targets

- **`trace-targets`**: Handles OpenTelemetry traces via `/v1/traces`.
  Both sections may point to the same remote endpoint and Pebble's
  endpoint logic is identical. A service can appear in both `trace-targets`
  and `profile-targets`.

- **`metric-targets`**: Handles OpenTelemetry metrics via `/v1/metrics`.
  Similar endpoint injection and forwarding logic applies.

- **`log-targets`**: Handles logs via the OTLP Logs API (`/v1/logs`).
  Independent from profile targets; uses `type: opentelemetry` in
  `log-targets` entries.

See [OP0X3-otlp-traces.md](OP0X3-otlp-traces.md), [OP0X2-otlp-metrics.md](OP0X2-otlp-metrics.md),
and [OP0X1-otlp-logs.md](OP0X1-otlp-logs.md) for the respective specs.

Pebble emits its own traces and metrics (see the traces spec), but does
not emit its own profiles. Profile targets are receive-only.


## Out of Scope

- **gRPC receiver**: The local receiver only supports OTLP/HTTP JSON.
  gRPC support (port 4317) may be added in a future spec.

- **Pebble self-profiling**: Unlike traces and metrics, Pebble does not
  emit its own profiles. The `profile-targets` section is receive-only.

- **eBPF profiler deployment/management**: Pebble only acts as the OTLP
  endpoint. Deployment, permissions, and rule configuration for eBPF
  profilers are outside scope.

- **Profile aggregation**: Pebble does not perform aggregation or
  summarisation of profiles. Each forwarded payload is a complete
  profile snapshot.

- **Per-service profile rate limiting**: Rate limiting of profile
  collection is the responsibility of the profiling agent, not Pebble.

- **Profiles signal stabilisation**: The OTel profiling signal is currently
  in alpha/development status. When it stabilises, the endpoint path will
  change from `/v1development/profiles` to `/v1/profiles`. Pebble will
  update the receiver route and the injected `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT`
  value accordingly; this will be a breaking change for agents using the
  current development path.

- **`OTEL_PROFILES_EXPORTER` env var**: Not injected in this implementation.
  Pebble will add `OTEL_EXPORTER_OTLP_PROFILES=otlp` injection once the OTel
  profiles auto-configuration spec standardises this variable.
