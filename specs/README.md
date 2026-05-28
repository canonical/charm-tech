# Operator Engineering specs

This folder holds the Charm Tech team's Operator Engineering (OP) specifications.

These are lightly cleaned and **redacted** Markdown copies, originally exported from
Google Docs. They are kept here for convenient reading and history alongside the code.

> **The authoritative copies live at [specs.canonical.com](https://specs.canonical.com).**
> If anything here is out of date, incomplete, or unclear, the versions at
> specs.canonical.com take precedence.

## Layout

- Top level (`OP*.md`) — specs with status Approved or Completed.
- `obsolete/` — specs that were rejected, superseded, or otherwise no longer apply.

## Adding or updating a spec

The authoritative version of each spec lives at
[specs.canonical.com](https://specs.canonical.com). That is typically where review —
particularly outside the Charm Tech team — takes place, and where the official status
(draft, approved, rejected, and so on) is maintained.

Early-stage specs (braindumps, drafts) can be developed in Google Docs or in a branch
of this repository. Once a spec has been approved or rejected, add an up-to-date copy
here via a pull request: top level for Approved/Completed specs, `obsolete/` for
rejected or superseded ones.

> **As with all public-facing documents, ensure that the copy of the spec in this repo
> does not contain any private information.** Do not mention unreleased or confidential
> Canonical products, services, or plans; do not copy review comments from the Google
> Doc; remove the "Author" field; and generally adjust the public copy so that it is
> suitable for general consumption.

## Notes

- These were produced by exporting from Google Docs using its built-in "Download as
  Markdown" feature, then running them through `scripts/tidy_spec.py` to strip
  template boilerplate, redact private content, and re-emit a clean header.
- Google Docs export cruft (comment threads, revision tables, page-break artifacts,
  template boilerplate) has been removed.
- Confidential material — unreleased project codenames and related details — has been
  redacted or generalised in these copies.
