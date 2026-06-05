# OP0X5 — Running otel-collector as a Pebble Service

| Field | Value |
| --- | --- |
| Type | Guide |
| Created | 25 May 2026 |

## Abstract

This spec describes a pattern for running an
[OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
as a service under Pebble and configuring Pebble's existing
per-signal targets to forward telemetry through it.

No new Pebble features are required. The otel-collector is an
ordinary Pebble service. The `trace-targets`, `metric-targets`,
`log-targets`, and `profile-targets` sections use their existing
`location` field to point at the collector's local endpoint.

```
Services
  │ OTLP (127.0.0.1:12345/v1/services/{svc}/otlp)
  ▼
Pebble  ──  enrichment  ──►  otel-collector  ──►  Backends
             (per-signal targets point here)
```


## Rationale

Pebble forwards enriched telemetry directly to configured backends.
This works well when the backend accepts OTLP natively, but leaves
no room for:

- **Tail sampling** — deciding whether to keep a trace only after all
  its spans have arrived.
- **Attribute manipulation** — adding, removing, or transforming
  resource or span attributes uniformly across all services.
- **Fan-out** — sending the same telemetry to multiple backends
  simultaneously (e.g. Tempo for traces and an archive store).
- **Protocol translation** — converting OTLP/JSON to a backend's
  native format (Jaeger, Zipkin, Prometheus remote write, etc.).

Running otel-collector under Pebble places a standard, composable
processing pipeline between Pebble's enrichment step and the final
backends, without requiring any changes to how Pebble works.


## Port Allocation

OTel's reserved ports are `4317` (OTLP/gRPC) and `4318` (OTLP/HTTP).
Using either of those for the collector's local receiver risks confusion
with the collector's own default listener configuration. A clearly
non-default port such as `12345` makes the intent unambiguous.

Pebble's OTLP receiver binds to either its TCP HTTP API listener (when
configured) or a randomly chosen loopback port. In both cases, only
connections from loopback addresses are accepted. See the individual
signal specs for details.


## Plan Configuration

### The otel-collector service

```yaml
services:
    otel-collector:
        override: replace
        command: /usr/bin/otelcol --config /etc/otel/config.yaml
        startup: enabled
```

The collector is started and managed by Pebble like any other
service. Pebble's retry and restart policies apply if the collector
exits unexpectedly.

### Pointing targets at the collector

Set each per-signal target's `location` to the collector's local
receiver address. Pebble appends the appropriate signal path when
forwarding, so only the base URL is needed:

```yaml
trace-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

metric-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

log-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

profile-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]
```

The `-otel-collector` entry in each `services` list prevents Pebble
from injecting `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`, `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`
(and `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` if enrolled in
profile-targets) into the collector process itself (see [Collector
Self-Telemetry]).


### TLS

The loopback hop between Pebble and the local collector
(`location: http://127.0.0.1:12345`) does not require TLS. Configure
TLS on the collector's outbound exporters for connections to upstream
backends.


## Collector Self-Telemetry

If `otel-collector` appears in a target's `services` list (or via
`all`), Pebble injects `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`, `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`
(and `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` if enrolled in profile-targets)
into the collector process. The collector's own SDK telemetry would then
flow:

```
otel-collector SDK → Pebble → otel-collector → backends
```

This is not a hard loop — data is not returned to Pebble — but it
means the collector's own spans and metrics are processed by itself
before reaching the backend. This may be desirable (uniform
processing for all telemetry including the collector's own) or
undesirable (unexpected self-telemetry in the backend).

Note also that `-otel-collector` in the `services` list only suppresses
Pebble's env-var injection into the collector process. If the collector
binary is itself instrumented and its own telemetry is configured (via
the collector config file) to export to Pebble's receiver, that traffic
will still flow. Operators who do not want the collector's own telemetry
processed through itself should configure the collector's internal
telemetry exporter to point directly at the upstream backend rather than
through Pebble.

Use `-otel-collector` in each `services` list to opt out:

```yaml
trace-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]
```

Or opt in deliberately by omitting the exclusion, in which case the
collector's own instrumentation data flows through the same pipeline
as service data.


## otel-collector Configuration

The collector configuration is independent of Pebble. The following
example receives OTLP/HTTP from Pebble, applies tail sampling and
attribute enrichment, and exports to a remote Tempo and Prometheus
instance.

```yaml
# /etc/otel/config.yaml

receivers:
  otlp:
    protocols:
      http:
        endpoint: 127.0.0.1:12345

processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: keep-errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: sample-rest
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
  resource:
    attributes:
      - key: deployment.environment
        value: production
        action: insert
  batch:

exporters:
  otlphttp/tempo:
    endpoint: https://tempo.example.com:4318
    headers:
      Authorization: "Bearer ${env:TEMPO_TOKEN}"
  prometheusremotewrite:
    endpoint: https://mimir.example.com/api/v1/push
  otlphttp/loki:
    endpoint: https://loki.example.com:4318

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [tail_sampling, resource]
      exporters: [otlphttp/tempo]
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheusremotewrite]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/loki]
    profiles:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/tempo]
```

The collector configuration is managed entirely outside Pebble. Any
change to the collector config requires restarting the
`otel-collector` service, which Pebble can do with
`pebble restart otel-collector`.


## Complete Plan Example

```yaml
services:
    otel-collector:
        override: replace
        command: /usr/bin/otelcol --config /etc/otel/config.yaml
        startup: enabled

    web-server:
        override: replace
        command: ./web-server
        startup: enabled

    worker:
        override: replace
        command: ./worker
        startup: enabled

trace-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

metric-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

log-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]

profile-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]
```

`web-server` and `worker` each receive `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`,
`OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`, `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`,
`OTEL_TRACES_EXPORTER`, `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER`,
and `OTEL_SERVICE_NAME` at startup. Their SDK telemetry flows to
Pebble's local receiver, is enriched, and is forwarded to the
collector at `127.0.0.1:12345`. The collector samples, enriches
further, and exports to the configured remote backends.

Pebble's own emitted spans (service lifecycle, health checks, plan
updates) and metrics also flow to the collector, receiving the same
processing as service telemetry.


## Multi-Layer Configuration

The collector `location` can be set in a base layer and targets
extended in overlay layers without touching the collector service
definition:

Base layer (`001-base.yaml`):
```yaml
services:
    otel-collector:
        override: replace
        command: /usr/bin/otelcol --config /etc/otel/config.yaml
        startup: enabled

trace-targets:
    collector:
        override: replace
        type: opentelemetry
        location: http://127.0.0.1:12345
        services: [all, -otel-collector]
```

Overlay layer (`002-app.yaml`):
```yaml
trace-targets:
    collector:
        override: merge
        labels:
            app.version: "2.4.1"
```

The overlay adds a resource attribute to all forwarded traces without
touching the collector service or its address.


## Relation to Other Specs

This pattern composes the features described in the following specs
without modifying any of them:

- [OpenTelemetry Traces](OP0X3-otlp-traces.md)
- [OpenTelemetry Metrics](OP0X2-otlp-metrics.md)
- [OpenTelemetry Logs via OTLP](OP0X1-otlp-logs.md)
- [OpenTelemetry Profiles](OP0X4-otlp-profiles.md)

The collector sits at the `location` of each per-signal target. From
Pebble's perspective, it is indistinguishable from any other
OTLP/HTTP backend.
