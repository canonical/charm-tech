# Charm Tech decisions

Lightweight decision records for the Charm Tech team, kept in this one file.
Each entry is short: what we decided, when, and (briefly) why.

Only accepted decisions are recorded (an accepted decision may be to say no to
something). Each gets a dated heading you can link to; when a day has more than
one decision, add a short descriptor suffix like `-govulncheck`.

## 2026-07-02-sha-everything

**All GitHub workflow actions will be hash-pinned.** We'll remove the exceptions for `github/*`, `action/*`, and `pypa/*`, and pin all actions to a git hash.

## 2026-05-20-govulncheck

**Use govulncheck instead of Trivy in CI.** We'll stop using Trivy in CI for
Pebble and Concierge, and rely on `govulncheck` instead. Trivy is still run as
part of the `secscan` checks in the release process. We don't entirely trust
Trivy after their issues earlier this year, and they are also notorious for false
positives because they don't check whether impacted code (like the Go standard
library) is actually used by the project.
