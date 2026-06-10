# OP0X7 — TLS Trust Contexts

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 09 Jun 2026 |

## Abstract

This spec describes adding a `trust` section to the Pebble plan that
allows operators to define named TLS trust contexts. Each trust context
holds a CA certificate bundle and an optional inheritance reference that
Pebble resolves into a cert pool for outbound TLS verification.

Trust contexts are consumed by four features:

- **Services**: inject the CA bundle into the process environment via
  well-known environment variables before the process starts.
- **Exec checks**: inject the CA bundle into the exec command environment
  before the command runs.
- **HTTPS health checks**: verify the server certificate when a check
  targets an `https://` URL.
- **Log forwarding**: verify the remote server certificate when a
  `log-targets` entry connects to an `https://` endpoint.


## Rationale

Pebble currently uses the OS system certificate pool for all outbound TLS
connections. This works well for publicly trusted endpoints but fails in
several common deployment scenarios.

**Private CA infrastructure**: Many enterprises and Kubernetes clusters use
an internal certificate authority. Service processes, health check
endpoints, and log backends may present certificates signed by this private
CA, which is absent from the OS system pool. Without custom CA
configuration, all such connections fail with certificate verification
errors.

**Operator-controlled trust**: In Juju and Charmed Operator deployments the
operator supplies CA bundles to both Pebble's own outbound connections and
the service processes it manages. Today this requires either patching the OS
system pool (requiring root privileges and affecting the whole host) or
configuring each service individually outside of Pebble, making the
configuration harder to audit and compose.

**Layer-based composition**: Pebble's layer system lets operators build
configuration incrementally. Trust configuration should follow the same
pattern — a base layer can establish a site-wide CA bundle, and an overlay
layer can extend it without duplicating certificate material across every
check and log-target definition.

Named trust contexts introduce CA bundles as a first-class plan concept. A
bundle is defined once and referenced by name from checks, log targets, and
service definitions, without duplication. The `inherit` field allows
contexts to chain, so a team-specific context can extend a corporate context
which itself extends the OS system pool. The design also provides a clean
extension point for future additions such as client certificates for mutual
TLS.


## The `default` Trust Context

Pebble always has exactly one built-in trust context named `default`. It
represents the OS system certificate pool. It has no `ca-cert`, no
`inherit`, and no other fields. It cannot be defined, replaced, or modified
in any layer; attempting to declare a trust context named `default` causes
plan validation to fail.

`default` can be referenced by name anywhere a trust context name is
accepted: in `tls-context` fields on services, checks, and log targets, and
in the `inherit` field of other trust contexts.

When no explicit `tls-context` is set on a consumer (service, check, log
target), Pebble behaves as if `tls-context: default` were set: the OS system
pool is used for verification, and no environment variables are injected into
services or exec checks.


## Plan Configuration

A new top-level section `trust` is added to the Pebble plan. It follows
the same map-based, multi-layer merge pattern used by `log-targets`.

```yaml
trust:
    <context-name>:
        override: merge | replace
        type: x509
        inherit: <context-name> | default
        ca-cert: |
            <PEM-encoded certificate(s)>
```

### Required Fields

- **`override`**: How this trust context is combined with any existing
  definition of the same name in a lower layer. Supported values are
  `merge` and `replace`. See [Layer Merge Semantics] for how `merge`
  behaves specifically for `ca-cert`.

- **`type`**: The trust context type. Currently the only supported value is
  `x509`. Future extension types (including SSH and x509 client
  certificates) are described in the appendix. `x509` is the type for
  PEM-encoded X.509 certificates.

  `type` is immutable: once a context name is introduced with a given type,
  all subsequent layers defining that same name must either omit `type` or
  specify the same value. Specifying a different value causes plan validation
  to fail. Under `override: merge`, `type` may be omitted because the type
  is already established by the existing definition.

### Optional Fields

- **`ca-cert`**: One or more PEM-encoded X.509 CA certificates, concatenated
  in a single string. When the trust context is used for an outbound TLS
  connection or service injection, Pebble builds a cert pool by first
  resolving the `inherit` chain (if any), then appending these certificates.
  A context with no `ca-cert` and no `inherit` is valid; it resolves to an
  empty cert pool, which trusts nothing.

- **`inherit`**: The name of another trust context (including `default`) whose
  resolved cert pool forms the base of this context. When absent, this
  context's cert pool contains only the certificates in `ca-cert`. When set,
  the referenced context is resolved first and its pool is extended with the
  certificates in this context's `ca-cert`.

  The `inherit` field creates a directed chain. Circular references (e.g.
  context A inherits B and B inherits A) are rejected at plan validation.

  `inherit: default` is the most common value, producing a cert pool of the
  OS system pool plus this context's `ca-cert`. Omitting `inherit` produces
  an isolated pool containing only this context's `ca-cert`, which is useful
  when the intent is to trust nothing except an explicitly listed set of CAs.


## Referencing a Trust Context

### From a service

A `tls-context` field is added to service definitions. It accepts either a
plain context name (simple form) or an object (complex form).

**Simple form** — context name as a string:

```yaml
services:
    <service-name>:
        override: merge | replace
        tls-context: <context-name>
```

Pebble injects the standard set of environment variables (see
[Service and Exec Injection]) before starting the process.

**Complex form** — object with a `name` and an `environment` token map:

```yaml
services:
    <service-name>:
        override: merge | replace
        tls-context:
            name: <context-name>
            environment:
                <ENV_VAR_NAME>: <token>
```

The `environment` map adds extra environment variables to those that the
simple form would inject. Each key is the environment variable name to set;
each value is a well-known token that Pebble resolves at service-start time.
The currently supported token is:

| Token | Resolves to |
|---|---|
| `ca-pem-bundle-file` | Absolute path of the PEM bundle file Pebble wrote for this service |

Additional tokens may be defined in future specs. An unrecognised token
value causes plan validation to fail.

If `tls-context` references a name that does not exist in the combined plan,
plan validation fails.

In `override: merge` context, the entire `tls-context` field (whether string
or object) follows standard field-level merge semantics: the later layer's
value replaces the earlier one if set.

### From an exec check

A `tls-context` field is added to the `exec` check sub-block. It accepts the
same simple and complex forms as on services:

```yaml
checks:
    <check-name>:
        override: merge | replace
        exec:
            command: <command>
            tls-context: <context-name>
```

Or with the complex form:

```yaml
checks:
    <check-name>:
        override: merge | replace
        exec:
            command: <command>
            tls-context:
                name: <context-name>
                environment:
                    <ENV_VAR_NAME>: <token>
```

Pebble injects the standard variables and any extra variables from
`environment` into the exec command's environment before running the command,
following the same rules as [Service and Exec Injection].

If `tls-context` references a name that does not exist in the combined plan,
plan validation fails.

### From pebble exec

`pebble exec` accepts a `--tls-context <name>` flag that names a trust
context from the combined plan. When set, Pebble injects the standard
environment variables (see [Service and Exec Injection]) into the command's
environment before it starts. The named context must exist in the combined
plan; otherwise the command fails before the remote process is started.

There is no complex form for `pebble exec`. Additional runtime-specific
environment variables can be set with the existing `--env KEY=VALUE` flag,
using the bundle file path published via `SSL_CERT_FILE` as the value.

**Interaction with `--context`**: If `--tls-context` is omitted and
`--context <service>` is set and the referenced service has a `tls-context`,
that context is inherited automatically. An explicit `--tls-context` always
takes precedence. To opt out of an inherited context, pass
`--tls-context default`.

### From an HTTP check

A `tls-context` field is added to the `http` check sub-block. Only the
simple form (plain context name) is accepted; there is no environment
injection for HTTP checks.

```yaml
checks:
    <check-name>:
        override: merge | replace
        http:
            url: https://...
            headers:
                <name>: <value>
            tls-context: <context-name>
```

When set, Pebble uses the context's resolved cert pool to verify the server
certificate on the HTTPS connection. When absent, `default` is used (OS
system pool).

`tls-context` has no effect when the check URL uses the `http://` scheme.
Pebble does not require `https://` to be present when `tls-context` is set;
this allows a check URL to be overridden between layers from `http://` to
`https://` independently of the trust context.

If `tls-context` references a name that does not exist in the combined plan,
plan validation fails.

### From a log target

A `tls-context` field is added to `log-targets` entries. Only the simple form
is accepted.

```yaml
log-targets:
    <target-name>:
        override: merge | replace
        type: loki | opentelemetry | syslog
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        tls-context: <context-name>
```

When set, Pebble uses the context's resolved cert pool for all outbound
connections to `location`. When absent, `default` is used (OS system pool).

`tls-context` applies to all three log target types:

- **`loki`**: used for the HTTPS connection to the Loki push endpoint.
- **`opentelemetry`**: used for the HTTPS connection to the OTLP/HTTP
  endpoint.
- **`syslog`**: setting `tls-context` on a syslog log target causes plan
  validation to fail. A future spec will define TLS syslog transport.

`tls-context` is accepted but has no effect when `location` uses the
`http://` scheme. Pebble does not require `https://` to be present when
`tls-context` is set; this allows a location URL to be changed between
layers from `http://` to `https://` independently of the trust context.

If `tls-context` references a name that does not exist in the combined plan,
plan validation fails.


## Service and Exec Injection

When a service or exec check is associated with a trust context, Pebble
writes a PEM bundle file and injects environment variables before the process
or command starts.

### Bundle file

Pebble resolves the context's cert pool (following the `inherit` chain) and
writes the resulting set of CA certificates to a PEM file at
`<PebbleDir>/trust/<context-name>.pem`. The file is created with permissions
`0644`.

Bundle files are per-context and long-lived: a file is written the first time
a context is needed and updated in place whenever the plan changes the
context's resolved content. The same file is shared by all consumers of a
given context (services, exec checks, `pebble exec` invocations). Files are
not removed while their context remains defined in the plan.

### Standard environment variable

Regardless of whether the simple or complex form is used, Pebble always
injects the following environment variable pointing at the bundle file path:

| Variable | Consumers |
|---|---|
| `SSL_CERT_FILE` | OpenSSL, Python (stdlib `ssl`), Ruby, Rust (`openssl` crate) |

Other well-known CA-bundle environment variables (`REQUESTS_CA_BUNDLE`,
`CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`, `SSL_CERT_DIR`) were considered
but are out of scope for this spec. They can still be configured via the
complex form's `environment` token map (e.g. `NODE_EXTRA_CA_CERTS:
ca-pem-bundle-file`). A future spec may revisit auto-injecting a wider
set — for example, via a `presets:` field — once there is operational
evidence about which combinations are needed.

### Additional variables from the complex form

When the complex form is used, the `environment` token map adds further
variables on top of the standard variable. Each token is resolved to its
concrete value (see [Referencing a Trust Context — From a service]) and
the resulting variable is injected.

### Non-overwrite rule

Each variable is only injected if it is not already present in the service's
or exec check's resolved environment. An operator can suppress the injected
variable by explicitly setting it in the service `environment:` block or the
exec check `environment:` block; Pebble will not overwrite an explicitly set
value.

### `default` context and injection

When `tls-context` is `default` (explicitly or by omission), no bundle file
is written and no environment variables are injected. The OS system pool is
used for Pebble's own outbound TLS connections; services and exec commands
receive no extra environment variables and use whatever certificate trust
their runtime provides.

### When does a trust change take effect?

When a plan change alters a trust context or a consumer's `tls-context`
reference, the change takes effect at different times depending on the
consumer type:

- **Services**: issuing a Replan API call restarts affected services with the
  updated context. Without a Replan, the change takes effect the next time
  the service is started.
- **Exec checks**: the updated context is used the next time the check runs.
- **HTTP checks**: the updated context is used the next time the check runs.
- **Log targets**: the change takes effect automatically after the plan
  change, without requiring a restart.


## Layer Merge Semantics

Trust context entries follow the same `override: merge | replace` rules used
by `log-targets` and `checks`, with one field-level difference for `ca-cert`.

### `override: replace`

The later layer's entry entirely replaces any existing definition with the
same name. The resulting context has exactly the fields specified in the
later layer.

### `override: merge`

Fields are merged as follows:

| Field | Merge behaviour |
|---|---|
| `type` | Immutable; may be omitted (the established type is kept). Specifying a different value than the existing definition causes plan validation to fail. |
| `inherit` | Later layer's value wins if set; otherwise the existing value is kept. |
| `ca-cert` | **Concatenated.** The later layer's PEM blocks are appended after the earlier layer's PEM blocks, forming a single multi-certificate bundle. |

The concatenation behaviour for `ca-cert` is intentional: the purpose of
merging a trust context is to extend a bundle, not to replace it. An overlay
layer that needs to replace a bundle entirely should use `override: replace`.

### Plan validation

After all layers are combined, Pebble validates the complete plan:

- Context names must not be reserved. Reserved names are: `default`,
  `system`, `pebble`. Any layer that defines a context with a reserved name
  causes validation to fail.
- Every combined trust context must have a `type`. The only supported value
  is `x509`. All layers defining the same context name must agree on `type`.
- `ca-cert`, if present, must contain one or more valid PEM-encoded X.509
  certificates.
- `inherit`, if present, must name a context present in the combined `trust`
  map or `default`. The `inherit` chain must be acyclic.
- Every `tls-context` value on a service, check, or log target must name a
  context present in the combined `trust` map or `default`.
- `override` must be `merge` or `replace`.
- Token values in a complex `tls-context` `environment` map must be
  recognised tokens (`ca-pem-bundle-file`).


## Examples

### HTTPS health check with a private CA

```yaml
trust:
    internal-ca:
        override: replace
        type: x509
        inherit: default
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIIBvTCCAWOgAwIBAgIUTrustExample...
            -----END CERTIFICATE-----

checks:
    api-ready:
        override: replace
        level: ready
        http:
            url: https://localhost:8443/ready
            tls-context: internal-ca
```

`internal-ca` inherits the OS system pool and appends the private root CA.
The check verifies the server certificate against both pools, so publicly
signed and privately signed endpoints both work.

### Service and log target sharing one trust context

```yaml
trust:
    corp-ca:
        override: replace
        type: x509
        inherit: default
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIICorporateRootCA...
            -----END CERTIFICATE-----

services:
    backend:
        override: replace
        command: ./backend
        tls-context: corp-ca

log-targets:
    loki-private:
        override: replace
        type: loki
        location: https://loki.corp.internal:3100/loki/api/v1/push
        services: [all]
        tls-context: corp-ca
```

`backend` receives `SSL_CERT_FILE` pointing at the bundle file. Log
forwarding to the private Loki instance uses the same cert pool for its
HTTPS connection.

### Custom environment variable name for a non-standard runtime

```yaml
trust:
    internal-ca:
        override: replace
        type: x509
        inherit: default
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIIBvTCCAWOgAwIBAgIUTrustExample...
            -----END CERTIFICATE-----

services:
    go-service:
        override: replace
        command: ./go-service
        tls-context:
            name: internal-ca
            environment:
                MY_APP_CA_FILE: ca-pem-bundle-file

checks:
    go-service-exec-check:
        override: replace
        exec:
            command: /usr/bin/my-healthcheck
            tls-context:
                name: internal-ca
                environment:
                    MY_APP_CA_FILE: ca-pem-bundle-file
```

`go-service` receives the four standard variables plus `MY_APP_CA_FILE`,
all pointing at the same bundle file. The same context and custom variable
are applied to the exec check that accompanies it. If `MY_APP_CA_FILE` is
already set in the service `environment:` block, Pebble does not overwrite
it.

### Isolated trust (no system pool) with an inheritance chain

```yaml
trust:
    corp-root:
        override: replace
        type: x509
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIICorporateRoot...
            -----END CERTIFICATE-----

    team-intermediate:
        override: replace
        type: x509
        inherit: corp-root
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIITeamIntermediate...
            -----END CERTIFICATE-----

checks:
    internal-api:
        override: replace
        http:
            url: https://api.internal.corp/health
            tls-context: team-intermediate
```

`corp-root` has no `inherit`, so its pool contains only the corporate root
certificate — the OS system pool is excluded. `team-intermediate` inherits
`corp-root` and appends the team intermediate, forming a two-certificate
pool. The check trusts only those two certificates and no public CAs.

### Multi-layer composition: adding a CA in an overlay

Base layer (`001-base.yaml`):
```yaml
trust:
    site-ca:
        override: replace
        type: x509
        inherit: default
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIIBSiteRoot...
            -----END CERTIFICATE-----

services:
    web-server:
        override: replace
        command: ./web-server
        tls-context: site-ca
```

Override layer (`002-extra-ca.yaml`):
```yaml
trust:
    site-ca:
        override: merge
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            MIIBSiteIntermediate...
            -----END CERTIFICATE-----
```

The combined `site-ca` context holds the OS system pool, the site root, and
the site intermediate. `web-server` receives all three in a single bundle
file. Neither layer needs to know the full set of certificates ahead of time.

If the override layer had used `override: replace`, the site root from the
base layer would be lost.


## Relation to Existing Features

### Relation to the Pebble TLS daemon (`tlsstate`)

The `trust` section is entirely separate from Pebble's existing TLS
infrastructure. `tlsstate` manages the daemon's own HTTPS server certificate
and client identity for the Pebble API (pairing). Trust contexts manage
outbound TLS verification for checks, log forwarding, and service injection.
The two systems do not interact.

### Relation to log-targets

`tls-context` is a new optional field on existing `log-targets` entries. No
other log-target fields are changed. Existing layer files with no
`tls-context` continue to work without modification, using the OS system pool
as before.

### Relation to checks

`tls-context` is a new optional field on `http` check sub-blocks and `exec`
check sub-blocks. TCP check sub-blocks are unaffected.


## Out of Scope

- **Client certificates (mTLS)**: The `x509` trust context type covers only
  server verification (CA bundles). Supplying `client-cert` and `client-key`
  for mutual TLS on log targets or checks is a natural extension but is
  deferred to a separate spec.
- **Syslog TLS transport**: Adding a TLS syslog transport scheme is deferred
  to a future spec. Setting `tls-context` on a syslog log target is a
  validation error until such a scheme is defined.
- **Dynamic trust context reload**: If a layer change alters a trust context
  while a service is running, the injected bundle file is not updated until
  the service is stopped and restarted. Live reload without a process restart
  is not implemented.
- **Multiple inheritance**: The `inherit` field accepts a single context name.
  A context that needs to combine certificates from two independent parents
  should concatenate them into a single `ca-cert` value or restructure as a
  chain.
- **Certificate validation policy**: There is no `skip-verify` option. Trust
  contexts are purely additive (appending to the inherited pool). Disabling
  certificate verification is not supported.


## Appendix: Future Extensions

This appendix sketches two directions the `trust` section could grow in
future specs. Neither is a commitment. The intent is to show that the
design leaves room for both without requiring breaking changes to the YAML
schema or the consumer reference model.


### A.1 — x509 Client Certificates (Mutual TLS)

The `x509` type currently covers only the server-verification side of TLS:
it tells Pebble which CA certificates to trust when a remote peer presents
its certificate. The natural counterpart is authentication: presenting a
client certificate so that the remote peer can verify *us*.

A minimal extension would add two new optional fields to an `x509` trust
context:

```yaml
trust:
    my-mtls-context:
        override: replace
        type: x509
        inherit: default
        ca-cert: |
            -----BEGIN CERTIFICATE-----
            ...
            -----END CERTIFICATE-----
        client-cert: |
            -----BEGIN CERTIFICATE-----
            ...
            -----END CERTIFICATE-----
        client-key: |
            -----BEGIN EC PRIVATE KEY-----
            ...
            -----END EC PRIVATE KEY-----
```

`client-cert` and `client-key` always appear together; specifying one
without the other would be rejected at plan validation. A context that
carries only a CA bundle (no client cert) would remain valid for consumers
that only need server verification.

**Pebble's own outbound connections** (HTTP checks, log targets) would
automatically use the client keypair when establishing the TLS handshake,
enabling mTLS to Loki, OpenTelemetry, or custom HTTPS check endpoints that
require it.

**Service and exec injection** would gain two new tokens for the complex
`tls-context` form:

| Token | Resolves to |
|---|---|
| `client-cert-file` | Absolute path of the PEM client certificate file |
| `client-key-file` | Absolute path of the PEM client private key file |

The key file would be written with permissions `0600` and removed on service
exit, mirroring the lifecycle of the CA bundle file. Standard env vars for
client certs are not as universally adopted as those for CA bundles, so the
token map would be the primary injection mechanism rather than a fixed set of
defaults.

**Inheritance** would be straightforward for CA certs (concatenation, as
today), but `client-cert` and `client-key` present a design question: should
inheritance allow a child context to override only the client keypair while
inheriting a parent's CA bundle? That would make `inherit` essentially a
projection — "take everything from parent except the client cert" — which is
useful when a base layer defines the trust anchor and an overlay layer
supplies the per-service identity. The alternative is that `client-cert` and
`client-key` are always defined locally on the referenced context and never
come from the inheritance chain. Either position is defensible and would need
to be settled in the implementing spec.

**Key sensitivity** is worth noting: unlike CA certificates, private keys are
secrets. Inline PEM in a layer file means the key is stored wherever layers
are stored. A future spec might accept a file path reference or a secrets
injection hook rather than inline PEM, to avoid key material appearing in
layer YAML on disk.


### A.2 — SSH Trust Contexts

SSH uses a fundamentally different trust model from TLS, but the conceptual
shape is similar enough to fit the `trust` section naturally. The protocol
has three distinct credential concerns that map cleanly onto what the `x509`
type already provides:

| SSH concept | TLS analogue |
|---|---|
| `known_hosts` entries | CA bundle — which servers to trust |
| Client private key | Client certificate + key — how we authenticate |
| `authorized_keys` entries | (Server-side) which clients to admit |

A new `type: ssh` might look like this:

```yaml
trust:
    deploy-host:
        override: replace
        type: ssh
        known-hosts: |
            deploy.internal ecdsa-sha2-nistp256 AAAAE2VjZHNh...
            10.0.0.5 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5...
        client-key: |
            -----BEGIN OPENSSH PRIVATE KEY-----
            ...
            -----END OPENSSH PRIVATE KEY-----
        authorized-keys: |
            ssh-ed25519 AAAAC3NzaC1lZDI1NTE5... operator@workstation
```

**`known-hosts`** is the server-trust anchor: it lists the public key
fingerprints of remote hosts that should be considered trustworthy. Under
`override: merge` this would concatenate entries, exactly as `ca-cert` does
for x509, allowing a base layer to establish organisation-wide known hosts
and an overlay to add deployment-specific ones.

**`client-key`** is the private key used to authenticate to a remote SSH
server. Unlike `known-hosts`, it doesn't make sense to concatenate multiple
client keys from different layers — a single identity is presented per
connection. `override: merge` semantics for `client-key` would likely be
"later layer wins", matching the existing `inherit` field behaviour.

**`authorized-keys`** is the inverse: a list of client public keys that are
permitted to authenticate *to* a service managed by Pebble. This is only
relevant if Pebble or a service acts as an SSH server, or if an exec check
starts an SSH daemon that needs an authorized_keys file. Under `override:
merge` it would concatenate entries, analogously to `known-hosts`.

**`inherit`** between SSH contexts would follow the same directed-chain
model as x509: a child context's `known-hosts` entries are appended to the
parent's, and its `client-key` overrides the parent's (if set). Cross-type
inheritance — an SSH context inheriting from an x509 context or vice versa —
would be rejected at plan validation, since the cert pools are incompatible.

**Service and exec injection** would introduce tokens alongside the existing
`ca-pem-bundle-file`:

| Token | Resolves to |
|---|---|
| `known-hosts-file` | Absolute path of the written `known_hosts` file |
| `client-key-file` | Absolute path of the written SSH private key file |
| `authorized-keys-file` | Absolute path of the written `authorized_keys` file |

Because SSH clients configure trust through a mix of command-line flags
(`-i`, `-o UserKnownHostsFile`), environment variables (`SSH_AUTH_SOCK`),
and config files (`~/.ssh/config`), the complex `tls-context` form with its
custom `environment` token map would be more important for SSH than it is
for x509, where four standard env vars cover the majority of runtimes.

**Open questions** a future spec would need to address:

- SSH certificates (issued by an SSH CA via `ssh-keygen -s`) blur the line
  between `client-key` and `known-hosts`. A `ca-public-key` field analogous
  to `ca-cert` may be needed to represent the SSH CA public key used to
  validate host or user certificates.
- Passphrase-protected private keys cannot be written to a file and used by
  an automated process without the passphrase. The spec would need to decide
  whether to reject passphrase-protected keys at plan validation or to
  provide a passphrase injection mechanism.
- `authorized-keys` is primarily useful when Pebble or a service acts as an
  SSH server. Whether that use case is in scope depends on how Pebble's role
  evolves; it may be better handled as a dedicated `authorized-keys` section
  rather than folded into `trust`.
