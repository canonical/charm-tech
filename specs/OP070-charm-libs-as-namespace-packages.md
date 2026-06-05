# OP070 — Charm Libs as Namespace Packages

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Jul 2, 2025 |

## Abstract

Charm libraries are a means for sharing code between charms. A simple format, charm libraries consist of a single file which has a unique ID (`LIBID`), a major version and a minor version. They are used for distributing shared relation interface code, as well as utility code, but they provide a suboptimal experience when external dependencies are required, and the single file format can be cumbersome when working with larger libraries.

One of the benefits of the current structure is that it forces discipline. The constrained format encourages developers to think carefully before introducing external dependencies or over-engineering the library, but as the ecosystem has evolved this has become cumbersome in many cases.

This spec proposes an alternative technical proposal, but critically a community governance process to prevent charm libs from becoming bloated and unwieldy (think `charmhelpers`).

## Rationale

As charms have become more capable, there has been an inevitable creep in complexity. Charm teams have evolved practices around schemas for relation data using libraries such as `pydantic`, which objectively raise the quality of our charms, but intermediate mechanisms such as `PYDEPS` have proved subpar for managing those external dependencies. Critical libraries such as those provided by the TLS team must depend on external dependencies such as `cryptography`.

Where external dependencies are introduced, charm developers consuming the libraries can be left in a situation where the charm fails to build unless they *manually* look up and add dependencies when using popular package management solutions such as `uv`, even if they fetch those libraries using `charmcraft fetch-lib` or `charmcraft fetch-libs`.

Over the past four years, there have been countless instances where new developers (both internal and external) have expressed confusion as to the purpose of libraries, their difference from Python packages and when they should be used, which further exacerbates an already steep learning curve.

There is an inherent awkwardness that libs must belong to *a charm*, which doesn't always make sense. For example, `operator-libs-linux` is a contrived charm which only exists to serve libraries such as `apt`, `systemd`, etc. Even so, the charm remains "deployable" but useless.

## Specification

#### Technical Solution

The proposed solution to this problem is to use Python's [namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/). The Charm Tech team have already established the [charmlibs](https://github.com/canonical/charmlibs) repository, which houses the `pathops` library. Here, there is a top-level namespace package named `charmlibs`, with a subpackage named `pathops`.

Critically, the `pathops` package is a full-featured package with its own version and its own dependencies, as described in the `pyproject.toml`. This means that one cannot just install `charmlibs` and end up with a large amount of potentially unused code, as was previously the case with `charmhelpers`.

To install the package, developers must first use their preferred package manager, for example:

```shell
uv pip install charmlibs-pathops
```

Then import the package as follows:

```py
from charmlibs import pathops
```

With this construct, one could easily imagine our existing `apt`, `snap`, `systemd` libraries becoming `charmlibs-apt`, `charmlibs-snap`, etc.

Because the subpackages are first-class Python packages of their own, dependency locking (through `uv.lock` or similar) becomes more easily synced with the rest of the charm package, an area where `PYDEPS` previously struggled. One consequence of this is that mismatched versions of transient dependencies are no longer possible.

#### Governance & Process

Part two of this proposal is a community process that can be used to govern quality and practice within charm libraries. If the proposed technical solution is to be adopted, all charm libraries should be contributed as a [`charmlibs`](https://github.com/canonical/charmlibs) namespace package in the `charmlibs` monorepo. The `charmlibs` namespace should only be used by packages in the `charmlibs` monorepo. This will service the following aims:

- Central repository will aid discoverability of charm libraries
- Review required from Charm Tech team or selected reviewers from Charm Teams & community to add new libraries (with `CODEOWNERS` allowing teams to manage their own library updates)
- Central release CI for publishing new versions of individual libraries - we will work with the upcoming build machinery team to ensure this centralised approach works when onboarded to upcoming build machinery, the current word is that monorepos work with sourcecraft
- One place to enforce style/formatting/consistency with tooling such as `ruff`.

This structure will make creating an up-to-date library index significantly easier (and automatable). The charmlibs docsite will maintain the [official listing](https://canonical-charmlibs.readthedocs-hosted.com/reference/general-libs/) of charm libraries. To be included in this listing and considered an official charm library, the library must be contributed to the charmlibs monorepo and follow the appropriate standards. This includes [relation libraries](https://canonical-charmlibs.readthedocs-hosted.com/reference/interface-libs/) as interfaces are included in the repository.

The repository should make use of a `CODEOWNERS` file to ensure that teams can merge changes to their own libraries, but initial contributions should be reviewed by a cross-functional team including the Charm Tech team and leads from across Charm Engineering.

It might be prudent to introduce some automation that detects, for example, new dependencies being added to a lib or a major version change, and triggers a broader review. The full list of criteria for triggering a broader review is to be developed.

This structure also introduces the ability for a ReadTheDocs instance documenting all of the charm libraries to the same (or better) standard than is currently present on Charmhub using parsed docstrings. This will be part of the existing [charmlibs documentation site](https://canonical-charmlibs.readthedocs-hosted.com/), linked to from the Ops [docs](https://ops.readthedocs.io/en/latest/), further enhancing discoverability. Care will be taken not to diminish discoverability, via Charmhub, of library documentation, for interfaces in particular.

#### Existing Implementation

Should this spec be accepted, the existing charm library infrastructure and mechanisms should be deprecated. In a future version of `charmcraft`, the `fetch-lib` and `fetch-libs` commands should display a deprecation warning, and subsequently be removed.

Care will need to be taken in order to maintain the discovery of libraries associated with charms on Charmhub, which will likely need updates to both the Charmhub backend and frontend.

#### Proposed Implementation Plan

To test this theory, some libraries from `operator-libs-linux` will be ported first (`snap` and `apt`), followed by the `tls-certificates` interface library, and tested with a subset of charms. The `operator-libs-linux` libraries belong to the Charm Tech team, and can serve to work out how we might handle releases, documentation and how to migrate users from the last release on Charmhub to the new release on PyPI (likely with a new minor version uploaded to Charmhub which logs a deprecation warning and a link to some docs on migration).

The `tls-certificates` library is used in a large percentage of our charm portfolio, so is a good target for assessing how workflow would be affected across teams.

## Further Information

#### Merging `charm-relation-interfaces`

There is some relation to the work done in [`charm-relation-interfaces`](https://github.com/canonical/charm-relation-interfaces/). As part of this work, the two efforts will be merged, such that formal relation interface definitions are merged with the [`charmtech-charmlibs`](https://github.com/canonical/charmtech-charmlibs) repository alongside their concrete implementations. This should be more feasible than when every library was required to be associated with a charm. There is some ongoing work on the structure of that repo, which may affect how these projects are merged when complete.

#### Charmlibs definition and scope

Charm libraries refers to user-facing Python packages hosted in the `charmlibs` monorepo, and legacy libraries hosted on Charmhub.

The terms `charmlibs` and charm libraries initially referred exclusively to Charmhub-hosted libraries, with the term covering both user-facing libs (whether interface libs or general purpose libs), and team-internal code sharing or encapsulation. This was due to this being the only endorsed mechanism for sharing code in charms, and such libs were never intended to be part of the broader, user-facing charming ecosystem as such.

To avoid ambiguity, we can refer to the former as `charmlibs` *packages* or PyPI charmlibs, and the latter as *Charmhub-hosted* libraries or Charmhub charmlibs.

#### Python packages outside the monorepo

Not all Python packages used by charms are intended to be charm libraries. These libraries are essentially implementation details of one or more charms, and should be managed by charming teams following general best practices.

For example, it was raised in a recent meeting that Data Platform Engineering have previously used Charmhub-hosted libraries for "base charm" implementations - i.e. a `mysql` base charm which is then specialised for K8s and Machines; or the [mongo-single-kernel-library](https://github.com/canonical/mongo-single-kernel-library) which provides code for the mongo charms. Cases such as this should remain outside of the `charmlibs` monorepo, since their appeal is strictly limited to the implementation of specific charms. Libraries contributed to the repo should have utility across products. Teams are free to manage internally used packages like this as best fits their needs.

The same is true of ecosystem-specific libraries. For example, the Openstack charms have a number of libraries which are used extensively within the Openstack product, but not outside it. When maintaining a large number of packages, teams could create their own monorepo that uses a similar structure, but limited to those libraries (e.g. `openstack-charmlibs`). Alternatives include a single package with several modules, or the development of separate packages in their own repos or in a charm monorepo.

#### Integration testing CI

Some charm libs currently live alongside their respective charms, and trigger large integration testing suites when changes are proposed. In this case, it is suggested that unit tests live in the central repository, but there might be external repositories or integration tests triggered elsewhere with `workflow_dispatch` or similar. As such libraries are migrated to the monorepo, we can standardise the machinery used to include the charm's integration tests in the CI for that library. Additionally, there should be a baseline of smoke tests that deploy/integrate charms using the libraries.

#### Existing charm review process

If this spec is approved, then when new `charmlibs` are added, the charm listing review process may be updated if needed to indicate when charms should (or must) use them. For example, "If a charm is installing debs, then recommend `charmlibs.apt`".

If a charm developers use and own a non-charmlibs package that seems like a good fit for the monorepo, this is also a good opportunity to suggest adding it.

This will help to ensure that there is a consistent charming ecosystem.

#### Integration with Charmhub

If the proof of concept involving a few libraries is deemed a success, and the community of charmers agree to move this forward, any move must be coordinated with the Charmhub store team to ensure that we don't (even temporarily) lose discoverability/visibility of libraries on Charmhub.

#### Reference Material

- [https://canonical-charmlibs.readthedocs-hosted.com/explanation/charm-libs/](https://canonical-charmlibs.readthedocs-hosted.com/explanation/charm-libs/)
