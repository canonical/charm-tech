# OP068 — Ops Tracing How-to

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Informational |
| Created | 12 Jun 2025 |

## Abstract

This document outlines the How-to guide for ops[tracing], the tracing feature in Ops.

## Rationale

Ultimately, we envision a world where every charm is traced by default.

The road towards that requires many hops, including integrating the tracing functionality into ops, having the charmer community adopt tracing, and work on native telemetry support in Juju.

Today, deployed applications must be related to COS to collect the trace data.

## Specification

### Introduction

#### Why trace your charms

In the how-to doc itself, I'd probably try to compact these into key points in the intro and put the full details in [https://ops.readthedocs.io/en/latest/explanation/tracing.html](https://ops.readthedocs.io/en/latest/explanation/tracing.html)
A section with motivation, form the viewpoints of: charm developers, field engineering (initial deployment), managed solutions (SRE), and solutions QA (testing).

What it's not, including that charm tracing is not useful for business analytics, while workload tracing is.

#### What is traced

##### What ops and charm libs provide

Ops already provides the key ingredients, list them, explain them.

Charm library authors are responsible for instrumenting their charm libs.

Examples.

#### What your charm needs to do

The ops.tracing.Tracing() object setup.
Explain that for simple cases that's it, as ops and charm libs cover quite a lot.
Highlight unique workload features that do require manual instrumentation.

- Subprocess calls
- HTTP or RPC calls to workload
- Important function calls if workload-specific Python module is installed

### Add tracing to an existing charm

Updating an Existing Charm
Charm age and versions of library dependencies:

- New enough Ops
- Scenario tests
- A word about integration tests

### Replace the charm_tracing library

Migration guide from `charm_tracing` charm lib to `ops[tracing]`.

### Trace a charm library

### Include tracing in a new charm

### View the trace data

How to install COS (link), relate your app to COS, where to point browser, screenshot of a trace in Grafana, some pointer about what's on the screenshot and how manual instrumentation (above) connects to that.

### Test the feature

#### Write unit tests

Scenario, not Harness

#### Write integration tests

Against the tracing-integration-tester charm (example)
Against grafana-agent
Against Tempo
Links to COS documentation

### Best practices

Depending on the amount of content, this can be its own section or content can be distributed across other sections.

- How to name spans
- What attributes to include
- Ideal level of detail
