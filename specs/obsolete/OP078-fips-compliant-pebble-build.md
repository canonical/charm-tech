# OP078 — FIPS-compliant Pebble build

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 14 Nov 2025 |

## Abstract

This document specifies the code, compilation, build, packaging and publication changes required to build a version of Pebble that is compliant with FIPS-140v3.

## Rejected

This approach was rejected because the pull request has grown too large.

Ultimately the conditional builds are at odds with Go best practice.

For example, Go advocates for the use of concrete types where possible, and thus e.g. `*x509.Certificate` has spread throughout the Pebble code base, from the arguments parsing in the entry point to config to daemon to the ultimate use site. A clean FIPS build would not import `crypto` or `x509` which would necessitate a significant refactoring just to hide this type behind an interface, or to propagate the PEM content as a `string` instead.

Likewise, Go advocates to inline helper code or write helper functions in the same module, while a clean FIPS build needs to hoist those blocks of code into a function placed in a separate file for the mainline build with a dummy function of the same signature that always returns errors in the FIPS build.

## Rationale

Pebble is embedded into Rocks by Rockcraft. Some customers want to run these Rocks in a FIPS-compliant environment. Pebble relies on cryptography in a few places, which means that changes are necessary to make such Rocks compliant.

The first step, agreed at the Gothenburg sprint, is to open a new snap channel, where a cut-down version of Pebble is published: without using any cryptography.

## Specification

### Current state

- go 1.24.6
- Usage of the third-party library GehirnInc/crypt:
  - To hash the passwords for validation (and setting the password?)
- Usage of std crypto via:
  - Client certificate validation in the mTLS use case
  - HTTPS server via the -https port listening option
  - HTTPS client potentially used to run health checks

### Go runtime

Google has applied for validation of the go language and the standard libraries, including the bundled cryptographic primitives. However, the validation is pending, and may take a year or two.

We should aim to use the correct Go toolchain and runtime versions, but we can't wait for the validation.

### Build tag

A new Go build tag is used: `fips`. In Go, build tags act on source file granularity.
Most of the source code remains agnostic to the new build tag.
Where needed, small portions are refactored out into two helper source code files:

- `feature_impl.go` which is marked with `//go:build !fips`
- `feature_fips.go` which is marked with `//go:build fips`

The same strategy is applied to unit test files.

### Code changes

- Basic auth login: blocked (user creation/updates are allowed)
- Certificate authentication: blocked
- mTLS pairing: blocked
- HTTPS server: blocked
- HTTPS address in CLI: blocked
- HTTPS redirects to HTTP address in CLI: blocked
- WSS use in CLI: blocked
- WS redirects: not possible
- HTTPS health checks: blocked
- HTTPS redirects in HTTP health checks: blocked
- HTTPS Loki logs exporter
- HTTPS redirects in Loki logs exporter
- HTTPS OTEL logs exporter
- HTTPS redirects in OTEL logs exporter

#### Basic auth

A user with basic authentication credentials is created and updated in the Pebble API with a complete password hash, not a raw password. This functionality doesn't use cryptography and therefore remains.

Password validation is blocked, because the third-party library is not FIPS-certified and in any case cryptography would have to be used, while Go runtime is not FIPS-certified.

#### Certificate auth

tbd

#### mTLS pairing

tbd

#### HTTPS server

Blocked at daemon initialisation. Attempting to start with `--https` argument returns an error and Pebble exits.

#### HTTPS clients

Scope: CLI, health checks, log exporters

Go standard HTTP client library is used. In FIPS builds, the `validateBaseURL` helper function returns an error. This function is called before any outbound HTTP client is configured.

#### HTTPS redirects in HTTP clients

Scope: CLI, health checks, log exporters

All HTTP clients are configured with a `CheckRedirect` that restrict redirect targets to HTTP addresses. Any other address scheme, including HTTPS, returns an error.

#### WebSocket clients

Pebble uses the `gorilla/websocket` library. The FIPS build ensure that this library is only ever called with the `ws://` scheme, and never with `wss://`.

The library does not support redirects.

### Build process

The FIPS-compliant Pebble is built using the same build process as regular Pebble.
Same GitHub action runners are used.
The `-tags fips` flags are added.
FIPS-compliant Pebble Snap is published in the `fips/` track.

### Publication

A new track will be created at [https://snapcraft.io/pebble](https://snapcraft.io/pebble): fips/stable, candidate, edge

## Rejected ideas

### Separate branch

Another possibility would have been to maintain a FIPS-compliant source "fork" of Pebble, in a separate branch in the Pebble repository, or in a separate repository.

This didn't seem worthwhile as we expect the Go runtime to pass FIPS validation, perhaps in a year or two.

### Validation

We've attempted to validate that cryptographic primitives are not used in FIPS mode:

- `go-callvis` static analyzer to trace cryptography usage to call sites in Pebble source code

While the headline features could be validated, the Go native cryptographic primitives are necessarily built into the binary, because we use `net/http` package, which may or may not be used HTTPS at runtime.

| go install github.com/ofabry/go-callvis@latest
go-callvis -focus crypto -group pkg,type -ignore vendor ./... |
| :---- |
