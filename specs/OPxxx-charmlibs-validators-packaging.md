| Index | OPxxx (number not yet claimed) |  |  |
| :---- | :---- | :---- | :---- |
| Title | charmlibs.validators packaging |  |  |
| **[Type](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?usp=sharing)** | **Author(s)** | **[Status](https://docs.google.com/document/d/1lStJjBGW7lyojgBhxGLUNnliUocYWjAZ1VEbbVduX54/edit?tab=t.0)** | **Created** |
| Implementation | [Tony Meyer](mailto:tony.meyer@canonical.com) | Draft | 6 Jun 2026 |
|  | **Reviewer(s)** | **Status** | **Date** |
|  | Person | Pending Review | Date |

# Abstract

[SQ096 - Library-Driven Interface Validation](https://docs.google.com/document/d/1NtPMO-BoKtgfHOB4N6ytpfvL1h-sfpASIzbYn3IECes/edit)
defines a contract (`BaseValidator.validate(level) -> ValidationResult`) for
objective, runtime "Day-2" interface validation, independent of which charm
library a charm happens to use for the interface itself. A POC implementation
already exists in
[`canonical/charm-integration-testing/validators`](https://github.com/canonical/charm-integration-testing/tree/main/validators)
(`base`, `runner`, and three reference validators: `postgresql_client`,
`mongodb_client`, `tracing`). This spec proposes how to **package** those
validators in the [`charmlibs`](https://github.com/canonical/charmlibs)
monorepo so that any charm can opt in to validation by adding a one-line PyPI
dependency, and the existing Phase-1 injector can consume the packaged versions
without behavioural regression.

26.10 scope is SQ096-only: package `-base` plus the three reference validators.
SQ103 persistence (`BasePersistenceValidator`) and Phase 2
(`charmlibs-validators-action`, the native `juju run app/0 validate` wiring) are
deferred to a later cycle.

# Rationale

[OP070](https://docs.google.com/document/d/1fLUNPiSCn0ecDnc-cNIdonwf8vSXDWyI6VNtvU_mcnU/edit)
established the `charmlibs.*` namespace as the publishing home for shared charm
code, and [OP074](https://docs.google.com/document/d/1YbfwYGSqSCByPHBZaSVJPdN4UP_vjdZEH-Ms6531_fE/edit)
extended that to interface specifications and libraries under
`charmlibs.interfaces`. Interface *validators* sit alongside interface
*libraries* and interface *schemas* but are categorically different from
either:

- An **interface schema** (under `interfaces/<interface>/`) defines the wire shape;
  it has no runtime dependencies beyond the schema-validation library.
- An **interface library** (under `interfaces/<interface>/src/`) implements the
  Juju-side relation logic; its dependencies are framework-shaped (`ops`,
  `pydantic`, light helpers).
- An **interface validator** verifies that what the relation *claims* to
  provide actually works at a functional level: not just that the databag is
  well-formed, but that the credentials authenticate, the endpoint is
  reachable, and a real client operation succeeds. Doing that requires a real
  client of the workload protocol: `psycopg` to open a PostgreSQL connection,
  `pymongo` to round-trip a MongoDB query, an OTLP exporter to push a span at
  a tracing backend. These are heavyweight, category-distinct dependencies
  that have no business in the dep graph of the schema or the relation lib.

Packaging validators under a sibling `charmlibs.validators.*` namespace (rather
than co-locating them under `interfaces/<interface>/validator/`) keeps each
distribution's dependency graph minimal: a charm that wants typed relation data does
not transitively pull in `psycopg`, and a charm that wants validation can opt
in to exactly the validator (and driver) it needs.

This also matches the package naming SQ096 itself proposes
(`charmlibs-validators-<interface>`) and gives the Phase-1 injector a stable
PyPI surface to install from, replacing the current `scp`-the-source approach
without changing the injector's external contract.

## Goals

- Publish `charmlibs-validators-base` and three reference validators
  (`-postgresql-client`, `-mongodb-client`, `-tracing`) to PyPI as part of the
  26.10 cycle.
- A charm consumes a validator by adding **one PyPI dependency** with an
  optional driver extra, no `charmcraft fetch-lib` step.
- The existing Phase-1 injector switches from source `scp` to
  `pip install charmlibs-validators-<iface>[<driver>]` into a unit-side venv,
  with `ValidationResult` JSON output unchanged.
- Validator distributions are independent of the schema package's dependency
  graph, so driver libs never leak into a charm that only uses the schema.

## Non-goals

- Defining `BasePersistenceValidator` / SQ103 persistence semantics
  (`prepare()`/`checkpoint()`/`cleanup()`).
- Building `charmlibs-validators-action` or any Phase-2 native-action wiring.
- `charmlibs-validators-autoupdate` (auto-validation on `update-status`),
  flagged in SQ096 as questionable practice for a library, deferred until the
  Phase-2 conversation.
- Charmcraft/Juju "blessing" for auto-registering the `validate` action in
  `actions.yaml`.
- Reworking the Phase-1 injector beyond swapping the install mechanism.

# Specification

## Repository layout

A new top-level `validators/` subtree in `canonical/charmlibs`, parallel to the
existing `interfaces/` subtree and the `pathops/` and other general library packages:

```
validators/
  base/
    pyproject.toml          # charmlibs-validators-base
    src/charmlibs/validators/base/
      __init__.py           # BaseValidator, ValidationResult, level enum
      runner.py             # the in-unit runner
    tests/
    CHANGELOG.md
    README.md

  postgresql_client/
    v0/
      pyproject.toml        # charmlibs-validators-postgresql-client
      src/charmlibs/validators/postgresql_client/
        __init__.py         # PostgresqlClientValidator(BaseValidator)
      tests/
      CHANGELOG.md
      README.md

  mongodb_client/v0/...     # same shape
  tracing/v0/...            # same shape
```

`base/` is **not** versioned with a `v0/` subdirectory because it is a single
ABI boundary that every validator depends on; versioning happens via the
package version (semver), matching how `pathops` (and others) is structured.
Per-interface validators **do** get a `v0/` subdir, matching the
`interfaces/<iface>/v0/` convention from OP074: the validation contract for a
given interface is part of the interface's stability surface, and a
wire-contract break would land in a sibling `v1/` directory.

## Package naming and imports

| PyPI distribution                         | Import path                                | Source path                          |
|-------------------------------------------|--------------------------------------------|--------------------------------------|
| `charmlibs-validators-base`               | `charmlibs.validators.base`                | `validators/base/`                   |
| `charmlibs-validators-postgresql-client`  | `charmlibs.validators.postgresql_client`   | `validators/postgresql_client/v0/`   |
| `charmlibs-validators-mongodb-client`     | `charmlibs.validators.mongodb_client`      | `validators/mongodb_client/v0/`      |
| `charmlibs-validators-tracing`            | `charmlibs.validators.tracing`             | `validators/tracing/v0/`             |

Kebab-case for PyPI (the `charmlibs` repo convention), snake_case for the
Python import path.

## Driver dependencies: opt-in `extras`

Per SQ096's "Risks → driver conflicts" mitigation, validator drivers ship as
**opt-in extras**, never as required dependencies. A charm that only wants the
base contract classes does not get `psycopg` transitively installed.

```toml
# validators/postgresql_client/v0/pyproject.toml
[project]
name = "charmlibs-validators-postgresql-client"
dependencies = [
  "charmlibs-validators-base",
  "charmlibs-interfaces-postgresql-client",  # see "Relationship to interfaces/"
]

[project.optional-dependencies]
psycopg = ["psycopg[binary]>=3.1"]
```

Consumers depend on `charmlibs-validators-postgresql-client[psycopg]`.
Validator code does a lazy `import psycopg` guarded with a clear error
message if the extra is missing.

## Relationship to `interfaces/<interface>/`

A validator for interface `X` **may** depend on `charmlibs-interfaces-X` for
typed unmarshalling of the relation databag, instead of re-parsing raw bag
fields. This is a per-validator design choice, not a hard rule:

- If the interface schema package exposes a stable typed accessor -> the
  validator depends on it. Single source of truth for the wire shape.
- If the schema package is heavy, unstable, or not yet published -> the
  validator parses raw and documents the wire fields it relies on, with a
  follow-up to migrate later.

Each validator's README declares which mode it is in.

## Phase-1 injector consumption

The existing Phase-1 injector
(`canonical/charm-integration-testing/validators`) currently `scp`s validator
source into units at test time. Migration path:

1. Publish `-base` and the three reference validators to PyPI (or to a Juju
   resource / private index during early phases).
2. Update the injector to
   `pip install charmlibs-validators-<interface>[<driver>]` into a unit-side venv
   instead of copying source.
3. Keep the injector's entry-point invocation and `ValidationResult` JSON
   output identical, so existing integration tests need no changes.

This is the SQ096 acceptance bar for 26.10: the packaged versions are
consumed without regression.

## Versioning policy

- `charmlibs-validators-base` follows standard semver. Breaking changes to
  `BaseValidator` or `ValidationResult` bump the major version. The intent for
  26.10 is to never bump major. The surface is small and well-scoped.
- Per-interface validators: the `v0/` subdir means **wire contract v0**. The
  PyPI package version moves with semver inside that contract. A
  wire-contract break would land as a sibling `v1/` package, parallel to how
  `charmlibs.interfaces` versions schema breaks.

## CI and repo touchpoints

- Add `validators/` to the top-level `justfile` and the `pyproject.toml`
  workspace, mirroring how `pathops/` and `interfaces/` are wired in.
- `CODEOWNERS` entries per validator. SQ096 names interface schema maintainers
  as the validator owners; the same group that owns
  `interfaces/<iface>/` should own `validators/<iface>/`.
- The existing `interface-test-requirements.txt` infrastructure is for schema
  interface tests; validators need their own test rig. Propose
  `validator-test-requirements.txt` and a `validator.just` lane.

# Acceptance criteria

- `charmlibs-validators-base` (including the runner) is published on PyPI.
- At least `charmlibs-validators-postgresql-client[psycopg]` is published on
  PyPI and consumable from a charm with a one-line dependency add.
- The Phase-1 injector consumes the packaged versions via `pip install`, with
  no change to its external contract or to integration-test behaviour.
- `charmlibs-validators-mongodb-client` and `charmlibs-validators-tracing`
  follow the same pattern within the cycle.

# Open questions

1. **Top-level layout.** Is `validators/` the right home, or should validator
   code be co-located under `interfaces/<interface>/validator/v0/`? The
   dependency-graph and naming arguments above favour a sibling subtree, but
   maintainer preference wins.
2. **CI surface.** Workspace setup, lint config inheritance, doc-build path:
   what should be copied from `pathops/` versus `interfaces/<interface>/`?
3. **Doc publishing.** `pathops` is published at
   `documentation.ubuntu.com/charmlibs/reference/charmlibs/pathops/`. Adopt
   the same pattern for `charmlibs/validators/<interface>/`?
4. **PyPI release cadence.** Tied to the `charmlibs` release process, or
   released independently per package?

For the originating team (Ryan Britton et al.):

1. **`-base` boundary.** Is anything currently in
   `charm-integration-testing/validators/base/` injector-specific and better
   kept in the test harness rather than shipped to charms?
2. **`-runner` separation.** SQ096 names a `runner`; the proposed layout
   bundles it inside `-base`. Acceptable, or does it want its own
   distribution?
3. **Test fixtures.** Are the existing fixtures under
   `charm-integration-testing/validators/` portable, or do they assume the
   injector environment?
