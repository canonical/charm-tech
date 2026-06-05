# OP084 — Standardised Charm Dev Workflows

| Field | Value |
| --- | --- |
| Status | Braindump |
| Type | Implementation |
| Created | 27 Feb 2026 |

## Abstract

This spec defines standardised dev workflows for charm repository CI. We recommend a top-level `CI` job defined in `ci.yaml` which has `lint`, `unit`, and `integration` jobs, all of which should be required checks. Publication workflows are out of scope for this spec, as they will likely be determined by future build tooling and processes.

## Rationale

[OP061 - Linting and Testing Command Standardisation in Charms](https://docs.google.com/document/d/1GfOTT1Ir-pLAbILUrI4GS9T8AAI8Ni8gpF1Mh67Wx3E/edit?tab=t.0)settled on a number of standardised task runner commands that charms should provide: `format`, `lint`, `unit`, `integration`, `docs`. This makes it easier for developers from other teams to make contributions to (and debug) any charm, and has been helpful for Charm Tech to be able to run charm testing commands from the `ops` repo to avoid regressions. This should also make it simpler for AI agents to have a common understanding of any charm repo's linting and testing commands.

There is currently no equivalent standard for the workflows that run in CI, though there are several efforts within teams to standardise by using shared workflows or actions (see [below](#prior-art)). This leads to duplicated work, and can be a friction point for cross-team contributions. This spec addresses this by recommending a set of standardised workflows that charms should run. This will make cross-team contributions easier, and should make it simpler to inform AI agents how to work on PRs to charm repos.

This specification is scoped to developer workflows. Charm publication infrastructure is out of scope, as this will change as future build tooling develops.

## Specification

Charm repositories should have a workflow named `CI` defined in `ci.yaml` that runs automatically on pull requests and on push to `main` (and any other release branches, e.g. for different channels). The workflow should also have a `workflow_dispatch` trigger.

The `CI` workflow should have `lint`, and `unit` jobs running the corresponding command as defined in [OP061](https://docs.google.com/document/d/1GfOTT1Ir-pLAbILUrI4GS9T8AAI8Ni8gpF1Mh67Wx3E/edit?tab=t.0#heading=h.kavgppauvkj5) e.g. `tox -e lint`, `just unit`.

If the charm provides a `docs` command, the `CI` workflow should also define a `docs` job that runs the command to validate that documentation builds correctly on every PR - this need not be the command that actually publishes the documentation (for example, that might be performed by Read the Docs).

These must all be required checks for pull requests to be merged.

There should also be an `integration` job that uses `charmcraft test`. This will be discussed later. This job may be gated based on any/all of `lint`, `unit`, and/or `docs` completing successfully.

Here's an example of what `ci.yaml` might look like.

```
# ci.yaml

name: CI
on:
  push:
    branches:
  pull_request:
  workflow_dispatch:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v7
      - run: uvx --with tox-uv tox -e lint
  # unit: ...
```

Charm repos may have other CI jobs, and those may be required checks. Ideally, they would also run from the `CI` job, but if this is impractical, that's OK. However, charms should make a best effort to cover all their required testing and linting under the recommended `lint`, `unit`, and `integration` jobs.

Note: unless your integration tests also pack your charm(s), the `integration` job should include a step that packs your charm(s) with `charmcraft pack`. Alternatively, you may pack in a separate job and make the results available via `actions/upload-artifact` if this is more performant in your case.

### What if my jobs need some extra complicated steps?

If some simple extra checks are required, first consider having extra steps in the job.

If it's not practical or desirable for the extra checks to be steps, and they should be jobs instead:

* Define a reusable workflow named `<check>.yaml` (e.g. `unit.yaml`)
* The workflow should have a job named `<check>` (e.g. `unit`) that runs the (e.g.) `tox -e unit`.
* The workflow may have as many other jobs as needed.
* The workflow must be called from `ci.yaml` in a job named `run-<check>` (e.g. `run-unit`). This may be a matrix job.
* The `<check>` job in `ci.yaml` (e.g. `unit`) should be defined with `needs: run-<check>`, and must fail if the expected jobs from `<check>.yaml` fail.

This allows the complicated checks to be executed in parallel, while the required checks always remain `lint`, `unit`, and `integration`.

This example factors the `integration` job into a reusable workflow and runs it as a matrix job.

```
# ci.yaml

jobs:
  run-integration:
    strategy:
      fail-fast: false
      matrix:
        foo: [bar, baz]
    uses: ./.github/workflows/integration.yaml
    with:
      foo: ${{ matrix.foo }}

  integration:
    needs: [run-integration]
    if: ${{ !cancelled() }}  # run even if tests are skipped or failed
    runs-on: ubuntu-latest
    steps:
      - name: Fail if any tests failed
        if: ${{ needs.run-integration.result != 'success' }}
        run: |
          echo '${{ toJSON(needs) }}' | jq  # logging
          exit 1

---

# integration.yaml

name: Integration
on:
  workflow_call:
    inputs:
      foo:
        required: true

jobs:
  pack:
  integration:
    runs-on: ubuntu-latest
    needs: [pack-a, pack-b]
    steps:
      - uses: actions/checkout@v6
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@v7
      - run: uvx --from rust-just just integration "$FOO"
        env:
          FOO: ${{ inputs.foo }}

  # some-other-check: ...
```

### Charm monorepos

Charm monorepos should have the same top-level `CI` workflow with the required jobs. These jobs may run separate steps for the separate charms. Alternatively, if reusing workflows via matrix jobs (e.g. calling once per charm), follow the convention for extra complicated steps above.

### Updating existing workflows

This spec does not require that charms update existing workflows in any specific timeframe. Rather, we recommend that this approach be adopted for new charm repositories, and old repositories migrate their workflows when feasible. Additionally, all branches in a repository need not migrate at once - for example, it may be desirable to leave CI for older LTS release branches untouched.

## Further Information

### Why not common reusable workflows or actions?

We don't think it's worth mandating the use of common reusable workflows given the relative simplicity of the workflow recommendations - complexity in testing comes from the specific needs of individual charm repos, and should be pushed to the task runner command definitions where possible, or locally defined reusable workflows otherwise.

This spec does not deprecate existing common reusable workflow projects. Teams are free to use such projects while implementing the core recommendations of this spec.

### Out of scope

Publishing infra (will be shaped by future build tooling).

Non-charm repositories (e.g. library and tool repositories).

Charmhub-hosted libraries are on their way out, so this spec avoids making any recommendations about them, though as noted in OP061, commands like `lint` should also cover any locally developed libraries. Teams should continue to use existing approaches to publishing and updating Charmhub-hosted libraries in the meantime.

### Prior art

Ad-hoc workflow organisation: (not a charm, but ops!), ...

Common reusable workflows: WIP/TODO write/think about these

* [https://github.com/canonical/identity-team/](https://github.com/canonical/identity-team/)
* [https://github.com/canonical/observability](https://github.com/canonical/observability)
* [https://github.com/canonical/data-platform-workflows](https://github.com/canonical/data-platform-workflows)
* [https://github.com/canonical/identity-credentials-workflows/tree/v0/.github/workflows](https://github.com/canonical/identity-credentials-workflows/tree/v0/.github/workflows)

[https://github.com/canonical/charming-actions](https://github.com/canonical/charming-actions)

* [canonical/charming-actions/check-libraries](https://github.com/canonical/charming-actions/blob/main/check-libraries/README.md)
* [canonical/charming-actions/release-libraries](https://github.com/canonical/charming-actions/blob/main/release-libraries/README.md)
  * These two actions are concerned with updating and publishing legacy Charmhub-hosted libraries. This spec doesn't recommend anything for these libraries, because they're not the way of the future™
* [canonical/charming-actions/channel](https://github.com/canonical/charming-actions/blob/main/channel/README.md)ca
* [canonical/charming-actions/upload-charm](https://github.com/canonical/charming-actions/blob/main/upload-charm/README.md)
* [canonical/charming-actions/upload-bundle](https://github.com/canonical/charming-actions/blob/main/upload-bundle/README.md)
  * These three actions are all to do with publishing charms (or bundles). This falls under the scope of publishing related infra.
* [canonical/charming-actions/dump-logs](https://github.com/canonical/charming-actions/blob/main/dump-logs/README.md)
  * This is a testing related action designed to be run after your integration tests. Its job overlaps with `pytest-jubilant`'s `--dump-logs` argument, followed by an `actions/upload-artifact` step.

[https://github.com/canonical/operator-workflows](https://github.com/canonical/operator-workflows)

* Test Workflow (canonical/operator-workflows/.github/workflows/test.yaml@main)
  * Run tests. We believe that having the standardised testing boilerplate in your own repo makes tests easier to follow and run from outside the repo.
* Comment Workflow (canonical/operator-workflows/.github/workflows/comment.yaml@main)
  * Makes a comment on a PR with contents from an artifact (from tests). Not needed if you have your own test workflows.
* Integration Test Workflow (canonical/operator-workflows/.github/workflows/integration_test.yaml@main)
* Publish Charm Workflow (canonical/operator-workflows/.github/workflows/publish_charm.yaml@main)
  * Publishing. Out of scope.
* Promote Charm Workflow (canonical/operator-workflows/.github/workflows/promote_charm.yaml@main)
  * Promotion. Out of scope.
* Update Charm Libs Workflow (canonical/operator-workflows/.github/workflows/auto_update_charm_libs.yaml@main)
  * Charmhub libs. Deprecated.
* Bot PR Approval Workflow (canonical/operator-workflows/.github/workflows/bot_pr_approval.yaml@main)
  * Auto-approve PRs from bots. Out of scope. Probably not desirable.
* RTD-specific Workflow (canonical/operator-workflows/.github/workflows/docs_rtd.yaml@main)
  * Use the workflow from the docs starter pack instead.
* Automated Documentation Testing Workflow (canonical/operator-workflows/.github/workflows/docs_spread.yaml@main)
  * Extracts `SPREAD` markers from docs and runs tests based on them. Interesting. Probably not suitable for standardisation here though.
* Terraform modules tests (`canonical/operator-workflows/.github/workflows/terraform_modules_test.yaml@main)
  * Seems like it would be simpler as a recipe - "add a `terraform`  job to `ci.yaml` with these steps, and customize ..."
