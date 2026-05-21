# Charm Tech decisions

Lightweight decision records for the Charm Tech team — like ADRs, but kept in
this one file. Each entry is short: what we decided, when, and (briefly) why.

## Adding a decision

1. Copy the template below to the **end** of the Decisions list.
2. Give it the next sequential number, zero-padded to four digits, and today's
   date.
3. Keep the explicit `<a id="NNNN"></a>` anchor: it gives the decision a stable
   link, so you can point people at `DECISIONS.md#NNNN` (or click the 🔗 that
   GitHub shows when you hover the heading). The anchor stays valid even if the
   title is later reworded.
4. Decisions are append-only — don't edit or delete past ones. To change a
   decision, add a new one and note that it supersedes the old (e.g. "Supersedes
   [0001](#0001)"); set the old one's status to `Superseded by [NNNN](#NNNN)`.

### Template

```markdown
<a id="NNNN"></a>
### NNNN — Short title

- **Date:** YYYY-MM-DD
- **Status:** Accepted

What we decided, and briefly why.
```

## Decisions

<a id="0001"></a>
### 0001 — Use govulncheck instead of Trivy in CI

- **Date:** 2026-05-20
- **Status:** Accepted

We'll stop using Trivy in CI for Pebble and Concierge, and rely on `govulncheck`
instead. Trivy is still run as part of the `secscan` checks in the release
process. We don't entirely trust Trivy after their issues earlier this year, and
they are also notorious for false positives because they don't check whether
impacted code (like the Go standard library) is actually used by the project.
