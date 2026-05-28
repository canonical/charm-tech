# OP062 — Pebble ability to tail a log file

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2025-03-07 |

## Abstract

This specification proposes a new feature enabling Pebble to follow a file for logging purposes. The goal is to capture file-based logs as though they are stdout/stderr streams, and send them to existing Pebble log targets. By integrating with Pebble's existing logging pipeline, this feature remains lightweight and transparent to operators and charms, while still offering flexible log collection.

## Rejected

The feature request is rejected because the functionality can be implemented using these existing mechanisms:

- Coreutils tail -F <filename>
- One extra services per log file
- Service dependencies in the Pebble plan

Demo charm: [https://github.com/dimaqq/log-tail-demo-charm](https://github.com/dimaqq/log-tail-demo-charm)

## Specification

Two main motivations guide this proposal:

1. **Service-Centric File Monitoring**

- Currently, Pebble only captures logs emitted via stdout/stderr. If an application writes logs to a file (or several files) by default, operators must install and configure separate tools for tailing them. This leads to inconsistent or duplicative patterns for log viewing.
- Integrating log-file following into Pebble provides operators a single, cohesive logging mechanism.

2. **Lightweight Implementation and Integration**

- Adding file/folder tailing should not expand Pebble's footprint dramatically, nor change the way logs are ultimately managed. The logs should appear in `pebble logs` like other process output.
- Operators should be able to configure these file-based logs with minimal overhead--no major new components or specialized knowledge required.

### Configuration

The design introduces a new optional key in the Pebble layer for each service:

| services:
  my-service:
    override: replace
    command: /usr/bin/my-app     log-files:       access-log:
        path: /var/log/my-app/access.log |
| :---- |

- `log-files`: new block
- `<key>`: arbitrary key, included in Loki labels
- `path`: a single file to follow.

Each log entry discovered is treated like standard output from the service and routed to Pebble's existing log pipeline.

#### Service updates

- New service: start reading the files
- Disabled service enabled for the first time: start reading the files
- Service updated: recompute the file set and:
  - Start reading new files,
  - Continue reading remaining files
- Service is disabled: stop reading the files
- Service is re-enabled: start tailing with some defined semantics
  - For example, like "tail", last 20 lines are potentially emitted again
- Files appear and disappear without explicit service update
  - Start reading new files
  - Stop reading files that are gone

A caveat is whether log followers need to store the offsets for the disappearing files in case a file with the same name reappears later. Is it a new file? Or the same file coming back?

### Implementation Outline

#### File Monitoring

Pebble spawns a dedicated routine at service start to read new lines from the configured file(s).

A simple implementation is preferred to detect appended data. An event-driven mechanism like inotify can be used, but it's not a hard requirement. Ultimately, logs need to be shipped within a set time frame, but it's more seconds than milliseconds.

Rotation handling is accounted for by re-initializing after a file rename/truncation event or after noticing the file no longer exists.

#### Log Transport

Each new log line is passed through the same code path as stdout/stderr, ensuring existing CLI (`pebble logs`) and external log-aggregation setups continue to function without change.

#### State

The positions of logs already "consumed" have to be preserved for the following reasons:

- Pebble is restarted: we don't want to re-emit the entire log file content
- A service is reconfigured: for the files that are followed, the set that didn't change should continue following from the same position

The implementation may be file path / offset, or it may track inodes, or in fact last N KB of log data (where the size should be large enough to include at least one timestamp). This specification doesn't take a stance on the specific mechanism to achieve a consistent logical reading position.

#### Performance and Limits

The first implementation will make no special provision for performance. The guiding principle is that the file content is like a stdout that's been dumped to a file. If Pebble doesn't throttle stdout output, it should not throttle the data coming from a file on disk.

There may be a practical limit on the number of the tailed files depending on the implementation coming from e.g. max number of allowed open file descriptors.

#### Security and Permissions

If Pebble does not have permission to read a file or folder, an error is logged to Pebble's own log.

No new authentication mechanism is needed; existing container user privileges apply.

### Implementation Approaches

This section is informational only.

#### New code

Something like [https://github.com/hpcloud/tail](https://github.com/hpcloud/tail) with Reopen: true

#### Reused code

Promtail is written in Go and is hosted under the client/ subdirectory of Loki.

Although Loki is AGPL, it appears that the client/ comes with an Apache license. That implies that Pebble could import or vendor Promtail code.

### User Interaction

#### Command-Line Usage

`pebble logs -n <service>` shows file-followed logs interspersed with stdout/stderr.

#### Troubleshooting

Errors (e.g., permission denied, file not found) are logged internally by Pebble, and can be surfaced like other errors.

### Charm log streaming

An overview of different approaches and implementations across existing charms.

#### Stdout/stderr

[list here]

#### Promtail

Some older workloads are not really built to stream logs to stdout or stderr, forcing charmers to:

- Get a list of Promtail binary URLs from the relation to COS
- Download Promtail in the charm container
- Push Promtail binary into the workload container
- Push Promtail config into workload container
- Start an extra Pebble service

| MYSQL_LOG_FILES = [
    f"{MYSQL_LOG_DIR}/error.log",
    f"{MYSQL_LOG_DIR}/audit.log",
    f"{MYSQL_LOG_DIR}/general.log",
]

class MySQLOperatorCharm(...):
    def __init__(self, *args):
          ...
          self.loki_push = LogProxyConsumer(
              self,
              log_files=MYSQL_LOG_FILES,
              relation_name="logging",
              container_name="mysql")

class LogProxyConsumer(...):  *# deprecated*
    ...
    def _on_pebble_ready(self, event: WorkloadEvent):
        """Event handler for `pebble_ready`."""
        if self.model.relations[self._relation_name]:
            self._setup_promtail(event.workload)

    def _setup_promtail(self, container: Container) -> None:
        ...
        workload_binary_path = os.path.join(
            WORKLOAD_BINARY_DIR, promtail_binaries[self._arch]["filename"]
        )
        self._add_pebble_layer(workload_binary_path, container) |
| :---- |

Arguably, the same end result could be achieved by Pebble services that run tail -f error.log

### Alternatives

Today, Pebble is mostly used in Juju/k8s and project crystal.

Both use cases are solved by:

- An extra service per log file path
- command: tail -F <the-path>
- Adding these to log-targets.foo.services: [...]

I've verified that tail -F handles almost every corner case I could throw at it: file truncated, file replaced, file doesn't exist at start.

Promptail comes with more functionality: log labels, trying to parse common log formats, including JSON and compressed files... but then again we don't include these features in this proposal.

Case in point: the LogProxyConsumer class that injects promtail has been deprecated in the loki_push_api charm lib. The recommended replacement is the LogForwarder class. The container is expected to have a secondary tail -F service (or equivalent) if the workload logs to files (confirmed with a team member).

Another case in point: the Rust uutils coreutils project that is meant to replace GNU coreutils in Ubuntu includes a tiny but fully functional `tail` replacement at 1.5MB for single binary (Linux, release build) or 12MB for the full coreutils suite.

### Rejected and postponed ideas

#### Log targets

Log sources under in the logging block (as opposed to services)

log-targets:
  tgt1:
    services: [...]

#### Log directories

Glob patterns, a.k.a. following log directories.

services:
  my-service:
    override: replace
    command: /usr/bin/my-app
    log-files:
      access-log:
        folder: /var/log/my-app/sub-logs
        include: '*.log'

Cloud-native workloads log to stdout/stderr or integrate log transport. These don't need the new feature in Pebble.

Classical workloads rely on the external logrotate, and if that is needed, why not use an external service like Promtail as well?

This leaves a relatively narrow set of workloads in between: namely those that rotate the log files in process, using e.g.:

- Go's [lumberjack](https://github.com/natefinch/lumberjack)
- Python's [logging.RotatingFileHandler](https://docs.python.org/3/library/logging.handlers.html#logging.handlers.RotatingFileHandler)

We may consider this in the future and the proposed configuration format allows for extensions.

#### Exposing tailed file list

Doesn't bring additional value directly, as Pebble already reports the current plan, where every file that's supposed to be tailed is listed.

#### Monitoring

Each tailed path could be a subject of a monitoring entry: number of log records emitted. That would help in both debugging (e.g. misnamed path, dead/stuck service) as well as overall performance monitoring. I feel that inclusion is premature at this point.
