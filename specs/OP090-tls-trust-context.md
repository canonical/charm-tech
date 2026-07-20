# OP090 — Pebble TLS Trust Contexts

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 09 Jun 2026 |

<!-- mdtog begin hs=-1 -->

## Abstract

This spec describes adding a `trust` section to the Pebble plan that
allows operators to define named TLS trust contexts. Each trust context
holds a CA certificate bundle that Pebble resolves into a cert pool for
outbound TLS verification.

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

Pebble currently uses the system certificate pool for all outbound TLS
connections. This works well for publicly trusted endpoints but fails in
several common deployment scenarios.

**Private CA infrastructure**: Many enterprises and Kubernetes clusters use
an internal certificate authority. Service processes, health check
endpoints, and log backends may present certificates signed by this private
CA, which is absent from the system pool. Without custom CA configuration,
all such connections fail with certificate verification errors.

**Charm-controlled trust**: In Juju deployments the Charm supplies CA bundles
to both Pebble's own outbound connections and the service processes it manages.
Today this requires either patching the system pool (requiring root privileges
and affecting the whole container) or configuring each service individually
using environment variables with a custom CA pool, making the configuration
harder to compose and audit.

**Layer-based composition**: Pebble's layer system lets operators build
configuration incrementally. Trust configuration could follow the same
pattern — a base layer can establish a CA bundle, and an overlay layer can
extend it without duplicating certificates across every check and log-target
definition.


## Specification

Named trust contexts introduce CA bundles as a first-class plan concept. A
bundle is defined once and referenced by name from checks, log targets, and
service definitions, without duplication. The `include-system` field allows
a context to extend the system certificate pool with additional private CAs,
without requiring operators to patch system files. The design also provides a
clean extension point for future additions such as client certificates for
mutual TLS.


### System Certificate Pool Default

When no `trust-context` is specified on a service, check, or log target,
Pebble uses the system certificate pool for outbound TLS verification.
No environment variables are injected into services or exec checks in this
case. This is the default behaviour, requires no plan configuration and
maintains existing behaviour.


### Plan Configuration

A new top-level section `trust-contexts` is added to the Pebble plan. It follows
the same key-based typing, multi-layer merge pattern used by `log-targets`.

```yaml
trust-contexts:
    <context-name>:
        override: merge | replace
        include-system: true | false
        x509:
            ca-cert: |
                <PEM-encoded certificate(s)>
            ca-cert-files:
                - /path/to/cert/0.crt
                - /path/to/cert/1.crt
```

#### Required Fields

- **`override`**: How this trust context is combined with any existing
  definition of the same name in a lower layer. Supported values are
  `merge` and `replace`. See [Layer Merge Semantics] for how `merge`
  behaves specifically for `x509`.

#### Optional Fields

- **`x509`**: X.509-specific trust configuration. Contains the following
  sub-fields:

  - **`ca-cert`**: One or more PEM-encoded X.509 CA certificates,
    concatenated in a single string. When the trust context is used for an
    outbound TLS connection or service injection, Pebble builds a cert pool
    from these certificates (and the system pool if `include-system` is
    `true`).

  - **`ca-cert-files`**: A list of paths to PEM-encoded X.509 certificate
    files. Pebble reads and appends these certificates to the pool after
    `ca-cert`. Paths are read at cert-pool resolution time. Each file's
    permissions are checked: if any permission bit outside of `0644` is set
    (i.e. the file is more permissive than `rw-r--r--`), the file is skipped
    and a warning is logged. Only files with permissions that are a subset of
    `0644` (for example `0644`, `0640`, `0600`, or `0444`) are included in
    the pool.

  A context with no `x509` (or an `x509` block with neither `ca-cert` nor
  `ca-cert-files`) is valid; when `include-system` is also absent or `false`,
  it resolves to an empty cert pool, which trusts nothing.

- **`include-system`**: Whether to include the system certificate pool as
  part of this context's cert pool. When `true`, the system pool is
  combined with the certificates in `x509`. When `false` or absent, only the
  certificates explicitly listed in `x509` are trusted. Setting
  `include-system: true` is the most common way to extend the system pool with a
  private CA without requiring privileged access to the system certificate
  store.


### Referencing a Trust Context

#### From a service

A `trust-context` field is added to service definitions. It accepts a
plain context name string.

```yaml
services:
    <service-name>:
        override: merge | replace
        trust-context: <context-name>
```

Pebble injects the standard set of environment variables (see
[Service and Exec Injection]) before starting the process.

If `trust-context` references a name that does not exist in the combined plan,
plan validation fails.

In `override: merge` context, `trust-context` follows standard field-level
merge semantics: the later layer's value replaces the earlier one if set.

#### From an exec check

A `trust-context` field is added to the `exec` check sub-block. It accepts a
plain context name string:

```yaml
checks:
    <check-name>:
        override: merge | replace
        exec:
            command: <command>
            trust-context: <context-name>
```

Pebble injects the standard environment variables into the exec command's
environment before running the command, following the same rules as
[Service and Exec Injection].

If `trust-context` references a name that does not exist in the combined plan,
plan validation fails.

#### From `pebble exec`

`pebble exec` accepts a `--trust-context <name>` flag that names a trust
context from the combined plan. When set, Pebble injects the standard
environment variables (see [Service and Exec Injection]) into the command's
environment before it starts. The named context must exist in the combined
plan; otherwise the command fails before the remote process is started.

**Interaction with `--context`**: If `--trust-context` is omitted and
`--context <service>` is set and the referenced service has a `trust-context`,
that context is inherited automatically. An explicit `--trust-context` always
takes precedence.

#### From an HTTP check

A `trust-context` field is added to the `http` check sub-block. It accepts a
plain context name string.

```yaml
checks:
    <check-name>:
        override: merge | replace
        http:
            url: https://...
            headers:
                <name>: <value>
            trust-context: <context-name>
```

When set, Pebble uses the context's resolved cert pool to verify the server
certificate on the HTTPS connection. When absent, the system certificate
pool is used.

`trust-context` has no effect when the check URL uses the `http://` scheme.
Pebble does not require `https://` to be present when `trust-context` is set;
this allows a check URL to be overridden between layers from `http://` to
`https://` independently of the trust context.

If `trust-context` references a name that does not exist in the combined plan,
plan validation fails.

#### From a log target

A `trust-context` field is added to `log-targets` entries. It accepts a
plain context name string.

```yaml
log-targets:
    <target-name>:
        override: merge | replace
        type: loki | opentelemetry | syslog
        location: <url>
        services: [<service-names>]
        labels:
            <key>: <value>
        trust-context: <context-name>
```

When set, Pebble uses the context's resolved cert pool for all outbound
connections to `location`. When absent, the system certificate pool is
used.

`trust-context` applies to all three log target types:

- **`loki`**: used for the HTTPS connection to the Loki push endpoint.
- **`opentelemetry`**: used for the HTTPS connection to the OTLP/HTTP
  endpoint.
- **`syslog`**: setting `trust-context` on a syslog log target causes plan
  validation to fail. A future spec may define TLS syslog transport.

`trust-context` is accepted but has no effect when `location` uses the
`http://` scheme. Pebble does not require `https://` to be present when
`trust-context` is set; this allows a location URL to be changed between
layers from `http://` to `https://` independently of the trust context.

If `trust-context` references a name that does not exist in the combined plan,
plan validation fails.


### Service and Exec Injection

When a service or exec check is associated with a trust context, Pebble
writes a PEM bundle file and injects environment variables before the process
or command starts.

#### Bundle file

Pebble resolves the context's cert pool and writes the resulting set of CA
certificates to a PEM file at
`$PEBBLE/trust/<context-name>.pem`. The file is created with permissions `0644`.

When resolving `x509.ca-cert-files`, Pebble checks each file's permissions
before reading it. If a file's mode has any bit set outside of `0644`
(i.e. `file_mode & ~0644 != 0`), the file is excluded from the cert pool and
Pebble logs a warning identifying the file and its actual permissions. Files
with permissions that are a subset of `0644` — such as `0640`, `0600`, or
`0444` — are accepted normally.

Bundle files are per-context and long-lived: a file is written the first time
a context is needed and updated in place whenever the plan changes the
context's resolved content. The same file is shared by all consumers of a
given context (services, exec checks, `pebble exec` invocations). Files are
not removed while their context remains defined in the plan.

#### Standard environment variable

Pebble always injects the following environment variable pointing at the
bundle file path:

| Variable | Consumers |
|---|---|
| `SSL_CERT_FILE` | OpenSSL, Python (stdlib `ssl`), Ruby, Rust (`openssl` crate) |

Other well-known CA-bundle environment variables (`REQUESTS_CA_BUNDLE`,
`CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`, `SSL_CERT_DIR`) were considered
but are out of scope for this spec. A future spec may revisit auto-injecting
a wider set — once there is operational evidence about which combinations are
needed.

#### Non-overwrite rule

Each variable is only injected if it is not already present in the service's
or exec check's resolved environment. An operator can suppress the injected
variable by explicitly setting it in the service `environment:` block or the
exec check `environment:` block; Pebble will not overwrite an explicitly set
value.

#### When no trust context is set

When no `trust-context` is configured on a service or exec check, no bundle
file is written and no environment variables are injected. Services and exec
commands receive no extra environment variables and use whatever certificate
trust their runtime provides (e.g. the system pool).

#### When does a trust change take effect?

When a plan change alters a trust context or a consumer's `trust-context`
reference, the change takes effect at different times depending on the
consumer type:

- **Services**: issuing a Replan API call restarts affected services with the
  updated context. Without a Replan, the change takes effect the next time
  the service is started.
- **Exec checks**: the updated context is used the next time the check runs.
- **HTTP checks**: the updated context is used the next time the check runs.
- **Log targets**: the change takes effect automatically after the plan
  change, without requiring a restart.


### Layer Merge Semantics

Trust context entries follow the same `override: merge | replace` rules used
by `log-targets` and `checks`, with one field-level difference for `x509.ca-cert`.

#### `override: replace`

The later layer's entry entirely replaces any existing definition with the
same name. The resulting context has exactly the fields specified in the
later layer.

#### `override: merge`

Fields are merged as follows:

| Field | Merge behaviour |
|---|---|
| `include-system` | Later layer's value wins if set; otherwise the existing value is kept. |
| `x509.ca-cert` | **Concatenated.** The later layer's PEM blocks are appended after the earlier layer's PEM blocks, forming a single multi-certificate bundle. |
| `x509.ca-cert-files` | **Concatenated.** The later layer's file paths are appended after the earlier layer's paths. |

The concatenation behaviour for `ca-cert` is intentional: the purpose of
merging a trust context is to extend a bundle, not to replace it. An overlay
layer that needs to replace a bundle entirely should use `override: replace`.

#### Plan validation

After all layers are combined, Pebble validates the complete plan:

- `x509.ca-cert`, if present, must contain one or more valid PEM-encoded
  X.509 certificates.
- `x509.ca-cert-files`, if present, must list paths to PEM-encoded X.509
  certificate files. At cert-pool resolution time, any listed file whose
  permissions exceed `0644` is dropped with a warning and excluded from the
  pool; this is a runtime condition, not a plan validation error.
- `include-system`, if present, must be a boolean (`true` or `false`).
- Every `trust-context` value on a service, check, or log target must name a
  context present in the combined `trust-contexts` map.
- `override` must be `merge` or `replace`.


### Examples

#### HTTPS health check with a private CA

```yaml
trust-contexts:
    internal-ca:
        override: replace
        include-system: true
        x509:
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
            trust-context: internal-ca
```

`internal-ca` sets `include-system: true`, so its pool contains the system
certificates plus the private root CA. The check verifies the server
certificate against both, so publicly signed and privately signed endpoints
both work.

#### Service and log target sharing one trust context

```yaml
trust-contexts:
    corp-ca:
        override: replace
        include-system: true
        x509:
            ca-cert: |
                -----BEGIN CERTIFICATE-----
                MIICorporateRootCA...
                -----END CERTIFICATE-----

services:
    backend:
        override: replace
        command: ./backend
        trust-context: corp-ca

log-targets:
    loki-private:
        override: replace
        type: loki
        location: https://loki.corp.internal:3100/loki/api/v1/push
        services: [all]
        trust-context: corp-ca
```

`backend` receives `SSL_CERT_FILE` pointing at the bundle file. Log
forwarding to the private Loki instance uses the same cert pool for its
HTTPS connection.

#### Isolated trust (no system pool)

```yaml
trust-contexts:
    corp-ca:
        override: replace
        x509:
            ca-cert: |
                -----BEGIN CERTIFICATE-----
                MIICorporateRoot...
                -----END CERTIFICATE-----
                -----BEGIN CERTIFICATE-----
                MIITeamIntermediate...
                -----END CERTIFICATE-----

checks:
    internal-api:
        override: replace
        http:
            url: https://api.internal.corp/health
            trust-context: corp-ca
```

`corp-ca` has no `include-system`, so its pool contains only the listed
certificates — the system pool is excluded. The check trusts only those
two certificates and no public CAs.

#### Multi-layer composition: adding a CA in an overlay

Base layer (`001-base.yaml`):
```yaml
trust-contexts:
    site-ca:
        override: replace
        include-system: true
        x509:
            ca-cert: |
                -----BEGIN CERTIFICATE-----
                MIIBSiteRoot...
                -----END CERTIFICATE-----

services:
    web-server:
        override: replace
        command: ./web-server
        trust-context: site-ca
```

Override layer (`002-extra-ca.yaml`):
```yaml
trust-contexts:
    site-ca:
        override: merge
        x509:
            ca-cert: |
                -----BEGIN CERTIFICATE-----
                MIIBSiteIntermediate...
                -----END CERTIFICATE-----
```

The combined `site-ca` context includes the system pool (from
`include-system: true` in the base layer), the site root, and the site
intermediate. `web-server` receives all three in a single bundle file.
Neither layer needs to know the full set of certificates ahead of time.

If the override layer had used `override: replace`, the site root from the
base layer would be lost.


### Relation to Existing Features

#### Relation to the Pebble TLS daemon (`tlsstate`)

The `trust-contexts` section is entirely separate from Pebble's existing TLS
infrastructure. `tlsstate` manages the daemon's own HTTPS server certificate
and client identity for the Pebble API (pairing). Trust contexts manage
outbound TLS verification for checks, log forwarding, and service injection.
The two systems do not interact.

#### Relation to log-targets

`trust-context` is a new optional field on existing `log-targets` entries. No
other log-target fields are changed. Existing layer files with no
`trust-context` continue to work without modification, using the system pool
as before.

#### Relation to checks

`trust-context` is a new optional field on `http` check sub-blocks and `exec`
check sub-blocks. TCP check sub-blocks are unaffected.


### Out of Scope

- **Client certificates (mTLS)**: The `x509` trust context type covers only
  server verification (CA bundles). Supplying `client-cert` and `client-key`
  for mutual TLS on log targets or checks is a natural extension but is
  deferred to a separate spec.
- **Syslog TLS transport**: Adding a TLS syslog transport scheme is deferred
  to a future spec. Setting `trust-context` on a syslog log target is a
  validation error until such a scheme is defined.
- **Dynamic trust context reload**: If a layer change alters a trust context
  while a service is running, the injected bundle file is not updated until
  the service is stopped and restarted. Live reload without a process restart
  is not implemented.
- **Certificate validation policy**: There is no `skip-verify` option. Trust
  contexts are purely additive (certificates are appended to the pool).
  Disabling certificate verification is not supported.

<!-- mdtog end -->

## Appendix: Future Extensions

This appendix sketches two directions the `trust-contexts` section could grow in
future specs. Neither is a commitment. The intent is to show that the
design leaves room for both without requiring breaking changes to the YAML
schema or the consumer reference model.


### A.1 — x509 Client Certificates (Mutual TLS)

The `x509` type currently covers only the server-verification side of TLS:
it tells Pebble which CA certificates to trust when a remote peer presents
its certificate. The natural counterpart is authentication: presenting a
client certificate so that the remote peer can verify *us*.

A minimal extension would add two new optional sub-fields to the `x509`
block:

```yaml
trust-contexts:
    my-mtls-context:
        override: replace
        include-system: true
        x509:
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

**Service and exec injection** would require new standard environment
variables for the client keypair. The key file would be written with
permissions `0600` and removed on service exit, mirroring the lifecycle of
the CA bundle file. Standard env vars for client certs are not as universally
adopted as those for CA bundles, so the specific variable names would need to
be settled in the implementing spec.

**`include-system`** behaviour for an mTLS context would follow the same
rules as for a CA-only context: when `true`, the OS system pool is combined
with `ca-cert`. `client-cert` and `client-key` are always defined locally on
the context and are not affected by `include-system`.

**Key sensitivity** is worth noting: unlike CA certificates, private keys are
secrets. Inline PEM in a layer file means the key is stored wherever layers
are stored. A future spec might accept a file path reference or a secrets
injection hook rather than inline PEM, to avoid key material appearing in
layer YAML on disk.


### A.2 — SSH Trust Contexts

SSH uses a fundamentally different trust model from TLS, but the conceptual
shape is similar enough to fit the `trust-contexts` section naturally. The protocol
has three distinct credential concerns that map cleanly onto what the `x509`
type already provides:

| SSH concept | TLS analogue |
|---|---|
| `known_hosts` entries | CA bundle — which servers to trust |
| Client private key | Client certificate + key — how we authenticate |
| `authorized_keys` entries | (Server-side) which clients to admit |

An `ssh` trust context might look like this:

```yaml
trust-contexts:
    deploy-host:
        override: replace
        ssh:
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
fingerprints of remote hosts that should be considered trustworthy.
Under `override: merge` this would concatenate entries, exactly as `x509.ca-cert` does
for x509 contexts, allowing a base layer to establish organisation-wide known hosts
and an overlay to add deployment-specific ones.

**`client-key`** is the private key used to authenticate to a remote SSH
server. Unlike `known-hosts`, it doesn't make sense to concatenate multiple
client keys from different layers — a single identity is presented per
connection. `override: merge` semantics for `client-key` would likely be
"later layer wins", matching standard field-level merge behaviour.

**`authorized-keys`** is the inverse: a list of client public keys that are
permitted to authenticate *to* a service managed by Pebble. This is only
relevant if Pebble or a service acts as an SSH server, or if an exec check
starts an SSH daemon that needs an authorized_keys file. Under `override:
merge` it would concatenate entries, analogously to `known-hosts`.

**Service and exec injection** would require new standard environment
variables for the SSH trust paths. Because SSH clients configure trust
through a mix of command-line flags (`-i`, `-o UserKnownHostsFile`),
environment variables (`SSH_AUTH_SOCK`), and config files (`~/.ssh/config`),
there are no widely adopted standard environment variable names for SSH trust
paths. The specific variable names and injection mechanism would need to be
defined in the implementing spec.
