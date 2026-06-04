# Charm Tech

Shared standards, conventions, and templates for the repositories maintained by
the Charm Tech team.

This repository is the canonical home for the things our repos have in common.
Rather than copy-pasting (and slowly diverging) the same style guides, security
policies, and CI config across every repo, we keep the source of truth here and
either link to it or copy from it.

## Decisions

- [DECISIONS.md](./DECISIONS.md) — a running log of team decisions.

## Specs

- [specs/](./specs/) — cleaned, redacted copies of the team's Operator
  Engineering (OP) specifications. Authoritative versions live at
  [specs.canonical.com](https://specs.canonical.com).

## Style guides

Our style guides reflect team decisions, and we add to them as things come up in
code review.

- [style/docs.md](./style/docs.md) — documentation and docstring style
  (language-agnostic: English spelling, abbreviations, how to write great docs).
- [style/python.md](./style/python.md) — Python code style.
- [style/go.md](./style/go.md) — Go code style.

Other repos should link to these rather than maintaining their own copies. For
example, an `AGENTS.md` or `CONTRIBUTING.md` can point at
`https://github.com/canonical/charm-tech/blob/main/style/docs.md`.

