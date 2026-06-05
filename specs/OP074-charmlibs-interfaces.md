# OP074 — charmlibs.interfaces

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 8 Aug 2025 |

## Abstract

Interface libraries and interface specifications are important parts of the charming ecosystem. Interface specifications define the shape of the data in the charms' relation databags, and document how this data should be processed, while interface libraries implement the majority of this logic, abstracting it away from the charms using the interface. However, interface libraries are currently distributed primarily as (legacy) Charmhub-hosted libs, while the specifications are hosted in the [charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces) repository, which has not seen wide adoption (details below). With the acceptance of the [spec](https://docs.google.com/document/d/1fLUNPiSCn0ecDnc-cNIdonwf8vSXDWyI6VNtvU_mcnU/view?tab=t.0) for the [charmlibs](https://github.com/canonical/charmlibs) monorepo, a timely solution is to move interface specifications to the charmlibs monorepo alongside their interface libs, with the interface libs distributed on PyPI under the `charmlibs.interfaces` namespace.

Additionally, this spec outlines improvements addressing longstanding issues with `charm-relation-interfaces`, such as the lack of reason for charmers to care if their charms are passing [interface tests](https://www.google.com/url?q=https://github.com/canonical/charm-relation-interfaces?tab%3Dreadme-ov-file%23relation-interface-testers&sa=D&source=docs&ust=1754980876775967&usg=AOvVaw1S7ycb9-b85WBXhzqcotBk) and the low adoption of interface tests. This spec also outlines the information that should be made available on Charmhub, or linked to from Charmhub. The issue of interface versioning is also touched on.

## Rationale

One of the biggest pain points with `charm-relation-interfaces` was that charmers had little reason to be invested in whether their charms passed (or continue to pass) interface tests. This is because these tests were typically only run in the `charm-relation-interfaces` repo (despite the ability being there to run them from the charm repo), and failing charms were notified via issues opened in the `charm-relation-interfaces` repo. Additionally, interface test development was not widely adopted (13 of the 58 interfaces defined in the repo have at least one non-empty test definition file). Furthermore, interface libraries were not directly tested against interface specifications, despite being the primary channel through which charms would implement a given interface.

Currently, charm interfaces are defined in the [charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces) repository. With the recent acceptance of [OP070](https://docs.google.com/document/d/1fLUNPiSCn0ecDnc-cNIdonwf8vSXDWyI6VNtvU_mcnU/view?tab=t.0), official charm libraries will be developed as Python namespace packages using the `charmlibs` namespace, and their development will take place in the [charmlibs](https://github.com/canonical/charmlibs) monorepo - distributing libraries on Charmhub will eventually be deprecated, while team-internal Python packages are not considered as charm libraries but implementation details of their charms. This implies that the development of interface libraries will also take place there, as these libraries are necessarily of interest to multiple charms. This presents an opportunity to colocate interface specifications with the libraries that implement them, rather than splitting these efforts across two locations.

Having the specification and the library implementation in the same place will hopefully align well with current interface development practices, where charming engineers typically develop an interface specification, library implementation, and charm implementation (using that library) at the same time. However, this does present a change for interface libraries whose development was previously tightly coupled to the implementation details of the charm that hosted the lib. This move represents a real hit to developer experience for these charmers. However, the shift to more closely aligning development of interface libraries with specifications, while decoupling libraries from specific charms, should be a healthy move for the charming ecosystem. It should make accidental interface breakages more difficult, and encourage greater reusability of interfaces.

This will also solve the issue of official interface library discoverability, as the official interface library is always available under `charmlibs.interfaces.<interface name>`. This makes it trivial to find the correct library after discovering the interface itself. With Charmhub-hosted libraries and interfaces defined on `charm-relation-interfaces`, there could be multiple libraries for an interface (for example if one library deprecates another - see some examples [here](https://canonical-charmlibs.readthedocs-hosted.com/reference/interface-libs/)). Additionally, since libraries were all hosted under a charm, even if there was one interface library named exactly the same as the interface itself (the most common case), you still had to know which charm to get the library from.

## Specification

### Repository machinery

This is the proposed machinery that would live in the repository:

1. An action for running interface tests that can be used from charm repositories. Charms would be required to use this to be eligible for public listing on Charmhub.
2. A workflow for running interface tests on a schedule and tracking failures. Issues may be opened on the charmlibs repo or the charm repos on failure (alternatively, the action used by charm repos may take care of this).
3. Workflows for keeping a top-level interface index file up-to-date for consumption by Charmhub.

### Interface tests

When colocating the interface specifications with the interface library implementations in the `charmlibs` monorepo, the following changes will be made to address current pain points with `charm-relation-interfaces`, specifically the low adoption of interface tests, lack of ownership, and charms not being invested in whether they pass tests for the interfaces they implement:

1. In addition to their regular unit and integration tests, interface libs will also maintain versioned suites of [interface tests](https://www.google.com/url?q=https://github.com/canonical/pytest-interface-tester&sa=D&source=docs&ust=1756248958318469&usg=AOvVaw2PdciJsX4oawUdmWfNcFZy) - interface tests are unit style tests that run against the charms that claim to provide or require the interface ([example](https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/pyroscope_cluster/v0/interface_tests/test_provider.py)). These interface tests will be run automatically in CI for the interface versions supported by the interface library (injecting the current version of the library into the charm), providing a clear point of ownership for the tests, and helping to avoid accidental interface breakages by library authors. This spec does not commit to following the exact design of the tests in `charm-relation-interfaces` - the exact shape of the tests and machinery in `charmlibs.interfaces` will be specified in greater detail in future..
2. A github action will be provided by the monorepo, allowing charms to run the interface tests for the interfaces they provide/require against the charm's latest changes in CI. Charms will be required to run this action in their CI to be eligible for public listing on Charmhub.
3. Scheduled runs of the interface tests in the `charmlibs` monorepo against charms that have registered as providing/requiring the interface will open/bump issues on the *charm repositories* on failure, with repeated failures resulting in a gradual process of dropping the charm from the list of official requirers/providers. The official requirers/provided are currently given greater visibility on Charmhub.

Implementer charms will continue to be able to customize an entrypoint for interface tests where they mock out components as necessary.

### Interface versioning

We all know that interface versioning and backwards compatibility is a problem that will need to be solved eventually, but solving it entirely is out of scope for this spec. However, we attempt to lay a solid foundation for future interface versioning (e.g. [OB068 - Charm interface versioning](https://docs.google.com/document/d/1cUj0_-6CR_L_9R2zrm5gBW0Wqpnuhobr5phTcSAaPos/edit?tab=t.0) draft spec) in the following ways:

* Interfaces are defined in versioned subdirectories (corresponding to a major interface version) alongside the library source code in the repository, creating a permanent snapshot of each version of the interface.
* The library can use the actual versioned schema definitions in their implementation, instead of having to reimplement or copy the schemas from a separate repository.
* Interface tests are likewise versioned, allowing a charm's compliance with different versions of the interface to be tested.

Additionally, the following best practices should be followed until we have clear policies for when support for charms using old versions of interfaces can be dropped:

* Interface specifications should avoid making backwards incompatible changes whenever possible. *Any backwards incompatible change must be a new version of the interface.*
*  Since the library developer does not control the order or timeframe in which provider and requirer charms are upgraded, adding a new version of the interface will require *supporting communication with multiple versions of the interface.* Support for older versions cannot be dropped immediately.
* *When support for old interface versions can be dropped is an open question*, and depends heavily on what versions of charms are deployed in production and what versions of charms on the other end of the interface they may be deployed with. When planning to drop support for an interface version, libraries must consider and document a clear upgrade path for charms, with consideration for how the known provider and requirer charms are used and their upgrade compatibility requirements. When it is considered safe to drop support for an interface version, this must always be a major version bump for the library itself as a clear signal of a backwards incompatible change.

### Interface namespace

Interface libraries will be distributed under the `charmlibs.interfaces` namespace, hosted on PyPI at `charmlibs-interfaces-<interface name>` and importable as `charmlibs.interfaces.<interface name>`.

### Anatomy of an interface

This is the proposed layout for interfaces and interface libs.

```
interfaces/
    <interface name>/
        docs/
            # displayed on documentation.ubuntu.com/charmlibs
            how-to/
            explanation/
            TUTORIAL.md
        interface/
            v0/  # interface version
                tests/  # tests tests are run against provider/requirer charms in CI
                interface.yaml
                schema.py  # JSON schemas generated on the fly if needed
                README.md  # displayed in reference docs for the interface
            v1/
                tests/
                interface.yaml
                schema.py
                README.md
            README.md
        src/charmlibs/interfaces/<interface name>/
            __init__.py
            _some_module.py
            _some_other_module.py
            # real schema files included at build time (symlinks are resolved):
            _schema_v0.py -> ../.../interface/v0/schema.py
            _schema_v1.py -> ../.../interface/v1/schema.py
            # things for charms to use in tests, not imported in __init__.py
            testing.py
            _some_testing_module.py
        tests/
            integration/
            functional/
            unit/
        CHANGELOG.md
        pyproject.toml
        README.md  # displayed on PyPI

```

A demo of this approach for the `tls_certificates` interface can be seen [here](https://github.com/canonical/charmlibs/pull/125).

### Charmhub integration

A `json` file would be generated  in CI and list:

* Interface (name)
  * Library docs link
  * Interface docs link
  * version
    * Version specific docs link
    * Registered provider charms
    * Registered requirer charms

This file would be exposed at [documentation.ubuntu.com/charmlibs/interfaces.json](http://documentation.ubuntu.com/charmlibs/index.json). This would make the file available to Charmhub without having to checkout or work on the repo itself, and without the file needing to be checked into the repo and kept up to date which would add friction to the developer experience.

Charmhub would consume this file to display the following information:

* `charmhub.io/integrations`
  * a top-level overview of the interfaces available - this is currently a paginated list of links to the specific interface pages, but **(new:)** it would be nice if it wasn't paginated
  * **(new:)** we could surface additional information about interfaces here - for example, a tabular format could be used with columns for the docs links and the count of providers and requirers
* `charmhub.io/integrations/<interface name>`
  * list of provider/requirer charms and their status as complying with the interface according to the index file (e.g. the current approach of a  fancy card for registered charms).
  * **(new:)** link to official library docs (for charm developers)
  * **(change:)** instead of embedding interface docs, link to official interface docs (for library developers and other interested parties)
* `charmhub.io/<charm name>`
  * **(new:)** on the interfaces tab: an indicator next to each interface this charm provides/requires based on whether the charm is in the registered list (e.g. a green tick for registered charms)
  * **(new:)** technically unrelated to the other changes proposed in this spec, but it would be great if Charmhub showed whether an interface was optional or not, independent of interface test compliance

#### Future steps

As the dust settles on these changes, and the charmlibs documentation site becomes more established,  we could take the opportunity to adjust the layout of the Charmhub charm page to remove the libraries tab.

Rationale - the libraries tab has always felt like the odd item out on the charm page, being charm developer focused rather than charm user focused. With the recommendation going forward being *not* to use Charmhub-hosted libraries, the prominence of the libraries tab will only steer charm authors in the wrong direction. Additionally, the library tab currently serves three purposes, all of which would now be better addressed elsewhere:

1. Interface library discoverability for charm authors and interested users: this would now be solved for all charms by clicking through to information about the interface itself (rather than only partially solved for charms that happen to host the lib for a particular interface)..
2. A peek into the charm's internal libraries: this is better addressed by following the source link for the charm, particularly as charms move towards using local, git, and PyPI hosted python packages for code sharing rather than Charmhub-hosted libraries.
3. Documentation of libraries: library docs will be hosted on the charmlibs documentation site, listed by library name, rather than needing to know the hosting charm and visiting its page.

However, while Charmhub-hosted libs continue to be used (likely for a very long time), it's important that their documentation continues to be publicly accessible and discoverable.

* I suggest adding a link in the sidebar to expose the content from this tab as a legacy library docs page at a url like `charmhub.io/legacy/libs/<charm name>`.
* The top-level page `charmhub.io/legacy/libs` could have an index of legacy Charmhub-hosted libs.
* These legacy pages should open with information pointing readers to `charmhub.io/integrations` for up-to-date information on interfaces and interface libs, and to the `charmlibs` documentation website for all public, non-interface libraries

## Further Information

It's worth addressing the fact that decoupling the interface definitions from their implementation(s) in `charm-relation-interfaces` had the following implications:

* As with Juju's perspective on charms, the perspective of the interface specification on the implementation is essentially language agnostic.
  * Like the modern charming ecosystem, the `charmlibs` monorepo is a Python first project.
  * This does not prevent non-Python libraries from being developed outside the monorepo; and implementations will still be separate from the specifications, allowing the possible expansion to more languages in future.
* There could be multiple competing implementations of an interface.
  * The `charmlibs` monorepo will allow only a single official Python implementation for each interface.
  * Python package versioning provides the mechanism by which breaking changes to the library (not the interface) can take place safely, providing the possibility to radically rewrite libraries, or for a competing, unofficial, implementation of an interface to be adopted into the monorepo and replace the previous implementation.
