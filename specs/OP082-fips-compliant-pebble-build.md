# OP082 — FIPS-compliant Pebble build

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 11 Dec 2025 |

## Abstract

This document specifies the code, compilation, build, packaging and publication changes required to build a version of Pebble that is compliant with FIPS 140-3.

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
  - HTTPS client potentially used in the Pebble CLI
  - HTTPS clients potentially used for Loki and OTEL log export

### Go runtime

Google has applied for validation of the go language and the standard libraries, including the bundled cryptographic primitives. However, the validation is pending, and may take a year or two.

We should aim to use the correct Go toolchain and runtime versions, but we can't wait for the validation.

### Dedicated branch

A new branch `fips` has been created in the Pebble repository. The cut point is some commit on the `master` branch after the `v1.26.0` release. A fake release with a tag `v1.26.0-fips` has been applied to the first commit in the new branch.

The FIPS releases will have a suffix, for example `v1.27.0-fips`, both the release/tag name as well as the version of the snap artifact.

The release procedure is updated, so that the Pebble release process ensures that changes from the `master` branch are merged into the `fips` before each release. Each release pushes both regular and FIPS builds into the respective tracks.

### Code changes

The third-party dependency `GehirnInc/crypt` has been removed.

- users with pre-hashed passwords can still be created
- basic authentication always fails

All imports of `crypto` and `x509` have been removed.

- PEM certificate parsing and validation has been removed
- user "certificate" identity has been removed

The `-https` daemon argument has been removed.

- the code that would start and HTTPS server has been removed

The concept of cryptographic identity of this Pebble instance has been removed.
Pairing (mTLS) code and the API endpoint have been removed.
HTTP clients (Pebble CLI, checks, and log exporters) has been restricted to the HTTP protocol:

- the client can only be instantiated with an HTTP URL
- the redirects these clients may encounter are restricted to HTTP URLs

WebSocket client has been restricted to `ws://` URLs.

- the client does not support redirects

### Build process

The FIPS-compliant Pebble is built using the same build process as regular Pebble.
Same GitHub Action runners are used.
The GitHub Action workflows have been updated to use the new snap store track.
For non-release (edge) builds, the version injection has been updated to use `git describe` relative to the nearest `-fips` tag in the branch history.

### Publication

A new track will be created at [https://snapcraft.io/pebble](https://snapcraft.io/pebble): fips/stable, candidate, edge
The version format adopted:

- `v1.27.0-fips` for releases
- `v1.27.0-fips-1234567` for the edge builds

The version is built into the Pebble binaries and snaps.

## Rejected ideas

### Go build tag

This was attempted, but the pull request has gotten way too large, see rejection reason in[OP078 - FIPS-compliant Pebble build](https://docs.google.com/document/d/1ROa_eUUAhAbWY0QBFMvtb9Bb3P-R7m_Y0ec5_KhdwJM/edit?tab=t.0).
Ultimately the build tag would require too much refactoring. Since we hope that the Go runtime will eventually pass FIPS certification, it seemed unwise to commit to build tags for the long haul.
