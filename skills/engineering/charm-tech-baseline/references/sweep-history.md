# Sweep history

What estate-wide sweeps the 26.10 cycle ran, with the per-sweep
status.

## Landed

### attest-build-provenance

Wires `actions/attest-build-provenance` into release / publish
workflows for Sigstore-backed SLSA L3 attestations.

| Repo | Status |
|---|---|
| pebble | Merged (canonical/pebble#885) |
| jubilant | Merged (canonical/jubilant#352) |
| pytest-jubilant | Merged (canonical/pytest-jubilant#82 + #83) |
| operator, charmlibs, charmhub-listing-review | Already attesting (pre-cycle) |
| concierge | Skip — goreleaser-monolithic release; revisit after build/publish split |
| hyrum | Skip — not published |

### Conventional Commits on PR titles

7 of 8 PRs merged: jubilant#341, pytest-jubilant#79, charm-ubuntu#80,
charmhub-listing-review#120, api_demo_server#54, concierge#206,
hyrum#34, pebble#884.

### SECURITY.md (V2.0 cross-cutting mandate)

charmhub-listing-review#105 merged 2026-05-26; charm-ubuntu#73 merged
2026-06-11. operator already had one. Closes the V2.0 SECURITY.md gap
across the estate.

### dependency-review-action

All 4 PRs open 2026-06-27 (charmlibs#561, jubilant#353, pebble#894,
operator#2587). Awaiting review.

### Code of Conduct

7 fork branches pushed. **Only hyrum#50 merged.** 6 remain unopened on
fork (pebble, jubilant, charmlibs, charm-ubuntu, api_demo_server,
concierge).

### CONTRIBUTING.md

charm-ubuntu and api_demo_server received one in the validate-pr-title
sweep. pebble branch pushed but PR not opened. jubilant, charmlibs,
concierge — N/A or already covered.
