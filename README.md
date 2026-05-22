# Charm Tech

Shared standards, conventions, and templates for the repositories maintained by
the Charm Tech team.

This repository is the canonical home for the things our repos have in common.
Rather than copy-pasting (and slowly diverging) the same style guides, security
policies, and CI config across every repo, we keep the source of truth here and
either link to it or copy from it.

## Contents

### Decisions

- [DECISIONS.md](./DECISIONS.md) — a running log of team decisions.

### Style guides

Our style guides reflect team decisions, and we add to them as things come up in
code review.

- [STYLE.md](./STYLE.md) — documentation and docstring style (language-agnostic:
  British English, abbreviations, how to write great docs).
- [python-style.md](./python-style.md) — Python code style.
- [go-style.md](./go-style.md) — Go code style.

Other repos should link to these rather than maintaining their own copies. For
example, an `AGENTS.md` or `CONTRIBUTING.md` can point at
`https://github.com/canonical/charm-tech/blob/main/STYLE.md`.

### Reusable CI

Reusable workflows for other repos to call live in
[.github/workflows/](./.github/workflows/). The main one runs the
[zizmor](https://github.com/zizmorcore/zizmor) GitHub Actions security scanner
and uploads SARIF results; call it from another repo with a thin caller
workflow:

```yaml
# .github/workflows/zizmor.yaml in the consuming repo
name: Workflow static checks
on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["**"]
permissions: {}
jobs:
  zizmor:
    uses: canonical/charm-tech/.github/workflows/zizmor.yaml@<commit-sha>
    permissions:
      security-events: write
```

Pin to a commit SHA (not `@main`) so a change here can't silently alter another
repo's CI.

## Licence

This repository is licensed under the Apache License 2.0. See
[LICENSE.txt](./LICENSE.txt).
