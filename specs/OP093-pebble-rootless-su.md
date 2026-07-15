# OP093 — Pebble rootless service user switching via yuzu

| Field | Value |
| --- | --- |
| Status | Draft |
| Type | Implementation |
| Created | Jun 29, 2026 |

## Abstract

Pebble service layers can specify `user`/`user-id` and `group`/`group-id` to
run a service as a different Linux user. Today, switching user requires Pebble
itself to be running as root (UID 0): the service is started with
`setresuid(2)`/`setresgid(2)` applied between `fork(2)` and `execve(2)`,
and the kernel only honours those calls for privileged callers.

Pebble is often run as a
non-root user inside a container (security best practice; rootless Podman /
Kubernetes `runAsNonRoot`), but the workload still needs to drop further to
a different unprivileged uid (e.g. `nobody`, an app-specific user).

[`yuzu`](https://github.com/canonical/yuzu) is a prototype
privilege-delegation tool built to handle exactly this Pebble use case. It
is a setuid-per-profile helper that lets an unprivileged Pebble process
exec a command as another user, with authorisation governed by a config
file written at image-build time rather than by host-level privilege.

This spec proposes that, when Pebble is not running as root and the `yuzu`
binary is available on `PATH`, Pebble starts services that request a user
or group switch by exec'ing them through `yuzu` instead of calling
`setresuid`/`setresgid` directly.

## Specification

### Trigger

When starting a service (or any service-equivalent process — see
[Scope](#scope)) Pebble currently resolves the desired uid/gid from the
service config (and workload) and, if those differ from the current uid/gid,
arranges for `setresuid`/`setresgid` to run in the child between `fork`
and `execve`. See `internals/overlord/servstate/handlers.go`
(`startInternal`).

This spec replaces that branch with the following decision:

1. Resolve the target `(uid, gid)` and the original `(user, group)` names
   exactly as today via `osutil.NormalizeUidGid`.
2. If the target user/group equals the current user/group, exec the command
   directly (unchanged).
3. Otherwise, if Pebble's effective uid is `0`, switch the child's
   credentials with `setresuid`/`setresgid` before `execve` (unchanged).
4. Otherwise, if a `yuzu` binary is found on `PATH`, exec the command via
   yuzu (see below).
5. Otherwise, fail to start the service with a clear error explaining that
   user switching requires either running Pebble as root or installing
   `yuzu`.

### Invocation

When yuzu is used, the command line becomes:

```
yuzu -u <user> -g <group> <cmd> <args>...
```

`<user>` and `<group>` are the **names** when present in the plan, otherwise
the numeric ids as decimal strings. yuzu accepts both forms (see the
[yuzu README](https://github.com/canonical/yuzu/blob/main/README.md)).

The yuzu CLI looks up `/opt/yuzu/<user>_<group>` (a setuid/setgid copy of
the yuzu binary, installed at image-build time with `yuzu -i -u <user>
-g <group> -au <pebble-uid>` or similar) and execs the target. From
Pebble's point of view the lifecycle, pid, signals, working directory,
environment and stdio are all unchanged: yuzu `execve`s into the target
process and is not an intermediary.

No new fields are added to the plan schema. The choice between native
`setresuid`/`setresgid` switching and yuzu is a property of the runtime
environment, not of the layer.

### Audit / error reporting

yuzu writes **exactly one line to stderr** per invocation, before
`execve`-ing the target. The line describes either the authorisation
decision (allow/deny) or a startup error:

```
yuzu: profile=app_app caller uid=1000 gid=1000 gids=[1000] run=/srv/app -> ALLOW (gid 1000 is in allowed gids)
yuzu: error: /opt/yuzu/app_app is not setuid or setgid
```

Pebble must:

1. Capture the **first line** of the service's stderr when the service was
   started via yuzu, before the stream is forwarded to the normal service
   log buffer.
2. Parse it as a yuzu audit line and:
   - If it begins with `yuzu: error:` (or otherwise does not contain
     `-> ALLOW`), treat the start as failed: surface the line as the start
     error, mark the service in `error` state, and emit a Pebble security
     log event (see [OP073](OP073-security-event-logging-for-pebble.md)).
   - Otherwise, log the line as a Pebble notice (or, preferably, as a
     dedicated audit log entry) at the same level Pebble currently uses for
     "service started as user X". The line is not forwarded to the regular
     service log output, so it does not appear interleaved with the
     workload's own stderr.
3. Strip exactly one line — no more, no less. yuzu guarantees a single
   newline-terminated line; subsequent stderr bytes are produced by the
   exec'd workload and must be passed through unchanged.

This is sufficient to distinguish three cases the user cares about:

| yuzu output | Pebble behaviour |
| --- | --- |
| `… -> ALLOW …` | Start succeeded; record audit line. |
| `… -> DENY …` | Service exits 1; surface the deny reason as the start error. |
| `yuzu: error: …` | Service exits 1; surface the startup error. |

### Auth socket

yuzu can be configured to delegate authorisation to a Unix-domain socket
that speaks a tiny HTTP/1.0 protocol:

```
GET /v1/auth?uid=<uid>&gids=<gid1>:<gid2>:... HTTP/1.0
Host: localhost
Connection: close
```

`200 OK` allows; anything else denies. The response body is ignored.

Pebble will implement this endpoint on its existing API socket as
`GET /v1/auth`. Image authors can then point yuzu at it, e.g.:

```ini
[default]
auth_socket = /var/lib/pebble/default/.pebble.socket
```

For the charm use case, Juju is expected to configure this automatically
as part of how it sets up the workload container: the operator does not
need to author `yuzu.conf` or know the Pebble socket path.

This means a profile installed without any `uids =`/`gids =` entries (or
for a caller that does not match those entries) is allowed iff Pebble
itself agrees the caller is permitted to start a service as the requested
user/group. The expected deployment shape is:

- Image build time: `yuzu -i -u app -g app` with no `-au`/`-ag` flags, plus
  `auth_socket = …` in `yuzu.conf`. The profile is callable only via
  Pebble's auth socket.
- Runtime: Pebble (the only process that knows the socket path and has it
  on its filesystem permissions) is implicitly the only allowed caller.

#### Authorisation policy (initial)

For the first iteration, `/v1/auth` returns `200 OK` iff the request's
`uid` query parameter equals Pebble's own effective uid (or is `0` when
Pebble is running as root). The `gids` query parameter is parsed for
well-formedness but its values are otherwise ignored: only the uid is
relevant for confirming that the requested run-as identity is Pebble's
own.

yuzu's caller-uid check (`SO_PEERCRED` on the socket) ensures that the
caller actually is Pebble; this endpoint then confirms that the
requested run-as uid is the one Pebble itself runs as. Because yuzu
profiles are set up at image-build time to map to specific
`(user, group)` pairs, this is enough to prevent a compromised non-Pebble
process on the same image from abusing the socket to run as arbitrary
users.

Any other request — including a probe of `/v1/auth` from outside Pebble's
trust boundary — receives `403 Forbidden` (or, for malformed queries,
`400 Bad Request`). Authorisation failures are emitted as Pebble security
log events per [OP073](OP073-security-event-logging-for-pebble.md)
(`authz_fail`).

Future iterations may extend the policy (e.g. consult Pebble identities)
without changing the wire protocol. yuzu itself never needs to learn
about those refinements: the endpoint stays a black-box `200`/non-`200`
decision.

#### Endpoint shape

- Method: `GET`.
- Path: `/v1/auth`.
- Query: `uid=<decimal>&gids=<decimal>[:<decimal>]*`.
- Access: open on the regular Pebble API socket; no authentication beyond
  the socket's own filesystem permissions and `SO_PEERCRED`. The endpoint
  does **not** require an admin identity — it is, by design, the one
  endpoint that unprivileged local callers (yuzu profiles) can hit.
- Response: empty body, status code only.

### Discovery

Discovery is a single `PATH` lookup for `yuzu` at service-start time. The
result is not cached: the operator may install yuzu after Pebble has
started, and Pebble should pick it up on the next service start without a
restart. (The lookup is cheap, and service starts are rare.)

Before using the discovered binary, Pebble must validate that it is
sufficiently protected against tampering: owned by `root:root`, not
world- or group-writable, not a symlink, and not setuid/setgid (the
setuid bits live on the per-profile copies under `/opt/yuzu/`, not on the
`yuzu` CLI itself — see the yuzu security model). If those checks fail
Pebble must refuse to use yuzu and surface the reason as the start
error, rather than silently exec'ing through a potentially compromised
binary.


### Scope

The same logic applies anywhere Pebble currently honours
`user`/`user-id`/`group`/`group-id` by calling `setresuid`/`setresgid` in
the child:

- `services` (`servstate`) — primary target.
- `checks` of type `exec` (`checkstate`).
- `pebble exec` requests (`cmdstate`) when the request specifies a user.

Each of these resolves uid/gid via `osutil.NormalizeUidGid` and applies
the credential change before `execve`. They should share a small helper
that, given the resolved `(uid, gid, user, group)`, either configures the
native `setresuid`/`setresgid` path or rewrites the command to go through
yuzu, plus returns a callback wired up to the child's stderr to consume
the yuzu audit line.

### Non-goals

- **No plan change.** The yuzu path is purely a runtime fallback; layers
  remain portable between root and rootless Pebble deployments.
- **No yuzu installation by Pebble.** Profiles are installed at image-build
  time (`yuzu -i …`) by the image author, who is also the only party with
  the privilege to do so. Pebble only consumes profiles.
- **No support for the yuzu `-p` (explicit profile) form.** Pebble always
  invokes `yuzu -u <user> -g <group>`; the image author is expected to have
  installed a matching `<user>_<group>` profile. If they have not, yuzu
  will emit a `yuzu: error:` line that Pebble surfaces unchanged.
- **No capability propagation logic in Pebble.** `keep-caps` is configured
  at profile install time; Pebble does not need to know about it.
- **No richer auth policy in this spec.** `/v1/auth` only confirms that
  the requested uid matches Pebble's own. Validating the requested
  identity against Pebble's configured identities (`/v1/identities`) is
  out of scope.

## Further information

- yuzu README:
  <https://github.com/canonical/yuzu/blob/main/README.md>
- Pebble service start, current user-switching code:
  `internals/overlord/servstate/handlers.go` (`startInternal`,
  `setCmdCredential`).
- Related security logging spec:
  [OP073 — Security event logging for Pebble](OP073-security-event-logging-for-pebble.md).
