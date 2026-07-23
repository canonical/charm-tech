# Charm Tech decisions

Lightweight decision records for the Charm Tech team, kept in this one file.
Each entry is short: what we decided, when, and (briefly) why.

Only accepted decisions are recorded (an accepted decision may be to say no to
something). Each gets a dated heading you can link to; when a day has more than
one decision, add a short descriptor suffix like `-govulncheck`.

## 2026-07-23-ops-pebble-for-charming

**ops.pebble is a Pebble client specifically for charming**. New features or other improvements should have a clear use-case *in charms*. At some point, ops.pebble will probably move to a dedicated Pebble client PyPI package (and development should keep that in mind) but that will only happen once there's a significant need for a package separate from charming.

## 2026-07-02-sha-everything

**All GitHub workflow actions will be hash-pinned.** We'll remove the exceptions for `github/*`, `action/*`, and `pypa/*`, and pin all actions to a git hash.

## 2026-06-30-soften-logo-requirement

**Including a logo for the charm will be changed to a soft requirement** for public listing on Charmhub. We'll organise a discussion with design/web/store before or at the next sprint to figure out what the best path forward is here. In particular, it doesn't seem useful for all Canonical charms to use the Ubuntu (or Juju, and so on) logo, but using the upstream logo, even in part, is not necessarily permitted and the reviewer can't really check that. A logo is important for making a good impression. Perhaps there can be some standard process for getting approval to use the workload logo (if there is one) and combine with a standard charm/Canonical/Juju form. Maybe design would like to make logos for tools that don't have one. Until this is resolved, we'll suggest that a charm has a logo, but not require it for public listing. 

## 2026-05-20-govulncheck

**Use govulncheck instead of Trivy in CI.** We'll stop using Trivy in CI for
Pebble and Concierge, and rely on `govulncheck` instead. Trivy is still run as
part of the `secscan` checks in the release process. We don't entirely trust
Trivy after their issues earlier this year, and they are also notorious for false
positives because they don't check whether impacted code (like the Go standard
library) is actually used by the project.
