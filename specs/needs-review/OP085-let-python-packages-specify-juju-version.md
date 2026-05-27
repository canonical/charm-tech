# OP085 — Let Python packages specify Juju version

| Field | Value |
| --- | --- |
| Status | Drafting |
| Type | Implementation |
| Created | 7 Apr 2026 |

## Abstract

This document specifies how charm libraries (or arbitrary Python packages) can include a small bit of metadata: the minimum required Juju version. Charmcraft will then combine the information from the metadata files of all installed Python packages into the strictest minimum Juju version requirement.

Juju then allows or rejects the deployment of this charm using the `assumes` field in the rendered `metadata.yaml` file packed into the charm.

## Rationale

Charms often depend on multiple Python packages that use ops, and by extension, rely on specific Juju features.

It is error prone to compute the resulting set of Juju versions manually, and it's impractical to rely on the integration tests at charm level to validate a wide variety of Juju versions, thus we need a way to collate requirements of the charm itself and all the charm libraries in its virtual environment.

## Specification

### Goals

- allow charm libraries to express minimum supported Juju version
- allow charmcraft to stamp the packed charm with assumes computed from the above

### Future goals

- allow charm libraries to require a k8s substrate
- allow charm libraries to require a machine substrate
- provide a carve-out for charms that dynamically import libraries

### Non-goals

- support for Charmhub-based charm libs
- complex version math: `2.9.49<=v<3 or 3.4.3<=v<3.5 or 3.5.1<=v<4` ([charm link](https://github.com/canonical/postgresql-operator/blob/8e26b0b8f7f82ec85390be8e335c0b6e29871de8/metadata.yaml#L82-L93))

### Proposal

The `Keywords` metadata field will be used by Python packages to indicate the lower bound of supported Juju versions.

The `Keywords` field can be specified in `pyproject.toml`, is widely supported by tooling, and ends up in the Python wheels in the `package-X.Y.Z.dist-info/METADATA` file and in the source distributions in the `package-X.Y.Z/PKG-INFO` file. When the package is installed in the virtual environment, the field is available in `package-X.Y.Z.dist-info/METADATA`, regardless of whether the package is installed as a wheel or an sdist.

The annotations are human-readable, are surfaced by PyPI and look reasonable in that context.

Charmcraft will examine the `Keywords` field in all the packages in the virtual environment (`{prime_dir}/**/METADATA`), filter out the entries it does not understand, and collate the remaining assumes to the strictest lower bound.

Note that while the charm code typically comes with a `pyproject.toml`, that's not mandatory, and today `charmcraft` doesn't preserve the metadata from that file.

#### Example

A charm library specifies in `pyproject.toml`:

| license = "Apache-2.0"
keywords = ["assumes:juju>=3.0", "unrelated-keyword"] |
| :---- |

Which gets formatted as wheel and venv `METADATA`:

| License-Expression: Apache-2.0
Keywords: assumes:juju>=3.0,unrelated-keyword |
| :---- |

Which, combined with other libraries becomes an assume in `metadata.yaml` packed into the charm:

| assumes:
  - juju >= 3.0 |
| :---- |

#### Details

* the only allowed version comparison operator is `>=`
* the allowed version string formats: `1`, `1.2`, and `1.2.3`
* keyword case: lower-case only; spacing: optional
* tooling computes the effective assume keyword value for each keyword (here only `juju`).
* charmcraft would only process installed packages, not pointers or editable source trees
* build dependencies should not be processed, although [today they are included in the venv](https://github.com/canonical/charmcraft/issues/2652)

#### Format Debate

Whether to prefix the

- proposed: `keywords: ["assumes:juju>=3.6", "unrelated", "keywords"]`
- alternatively: `keywords: ["juju.assumes>=3.6"]` or `charmcraft.juju>=3.6`

With the proposed option, each keyword is either a prefixed complete and simple assume expression, like `assumes:juju>=3.6` or `assumes:k8s-api` or an unknown keyword, like `http`. Thus, `charmcraft` will filter out keywords that are missing the `assumes:` prefix, or perhaps keywords that fail a pattern match, where the values that are passed through are `foo`, `foo>=1.2.3`, and perhaps `foo>1.2.3`.

The PyPI "Meta" block for a package would look like this:
![][image1]

#### How to handle conflicts between charm's assumes and libraries'?

Or, what if charm's `charmcraft.yaml` or `metadata.yaml` contains a set of explicit assumes?

* option A: allow the charm to override the computed value
  * option A.1: ... and warn if the computed value is stricter than the declared
* option B: merge the declared assumes with the computed value
* **option C: error (proposed - see below)**

Note that a charm may include [a convoluted assumes declaration](https://github.com/canonical/postgresql-operator/blob/c7a4832a2063ba4d660922da95badbbf7c09a239/metadata.yaml#L82-L93).

For example, suppose a charm knows that it needs at least Juju 4.13 for some feature. It uses a library that relies on a feature only present in Juju 4.77. There seem to be two-ish possibilities for what the charm wants:

1. It wants to use the maximum of its own `assumes` and that of its libraries.
2. It wants to ignore the library's `assumes` and just use its own:
   1. Perhaps it knows that it doesn't actually use the library feature requiring 4.77, so it would like to ignore that specific library's `assumes`.
   2. Perhaps it doesn't like this `assumes` propagation feature and wants to opt out entirely.

With a straightforward implementation of option A, any explicit `assumes` from the charm will override those coming from the libraries. This makes providing a charm-level `assumes` equivalent to 2(b) (opting out of this feature entirely). The only other thing the user can do is leave out the charm `assumes` entirely to use the maximum of the library `assumes`.

Option A.1 warns if the library `assumes` are stricter than the charm's. This facilitates 1 (using the maximum), if the user notices the warning. It also facilitates 2(b) (opting out entirely) if the user doesn't notice or chooses to ignore the warning.

A straightforward implementation of Option B only supports 1 (using the maximum of the charm and library `assumes`). In this case, a charm `assumes` sets a floor. Even with the addition of an explicit opt-out system, there's an important limitation here: if this takes place at packing time, this would silently raise the charm's minimum Juju version compared to what was explicitly provided in `charmcraft.yaml`.

Option C is a bit underspecified. One reading is that it is an error to have both a charm-level `assumes` and library-level `assumes`, which doesn't seem viable. Instead, it would be an error only when there's a conflict, that is, if the library `assumes` are stricter than the charm's. This is similar to option A.1 (warn if the library `assumes` are stricter), but only supports 1 (using the maximum). Additional explicit support is required to facilitate 2(a/b).

Given that both 1 and 2 are reasonable wishes, only option A.1 fulfills both. However, using warnings to communicate information to the user, and the user's choice being implicit in ignoring or escalating the warning, doesn't seem very reliable. If we do want to support both 1 and 2(a/b), then we should use a more explicit way of opting in or out.

Instead, we propose option C with the addition of an explicit opt-out mechanism:

If there are library `assumes`, compute the maximum.

* If the charm's `assumes` is lower (or it doesn't have one at all), abort with an error and explain why (whether this is happening at pack time or a separate tool).
* If the charm's `assumes` is greater or equal, or it has an opt-out marker, then proceed with the charm's `assumes`.

This requires an opt-out mechanism somewhere, which could be per-library, or global. Depending on where this feature is implemented, this could look like:

* Arguments to the tool used to generate the `assumes` (e.g. `ops_tools.lib_assumes --ignore='charmlibs.pathops'`)
* Options for the plugin in `charmcraft.yaml`.
* A top-level option in `charmcraft.yaml`.

## Alternatives

### Out-of-band validation

What if we didn't want to modify `charmcraft`?

We could build a tool, available via `pre-commit` and/or GitHub Actions, that:

- creates a `venv`
  - for each Python version, according to bases in `charmcraft.yaml`
  - for each architecture, according to declaration in `charmcraft.yaml`
- installs the dependencies (project file, lock file, or requirements.txt)
- computes the assumes from the install Python package metadata
- reads the declared assumes from `charmcraft.yaml`
- validates that the declaration is stricter than the computed assumes

This tool can be run without `charmcraft`.

- the tool would have to emulate charmcraft plugins, like 12-factor
- the tool may need separate paths for different part plugins: `uv`, `charm`, `poetry`
  - perhaps the tool can be limited to projects with lock files, which implies functional/installable `pyproject.toml` files
- the tool may fail if there are multiple parts in `charmcraft.yaml`, where Python package installation requires the previous part to run

### Fake packages

[David Wilding](mailto:david.wilding@canonical.com) proposes: As another alternative, what if we (or someone) published a no-op Juju package to PyPI with version numbers matching Juju, purely so that other packages could depend on it in their runtime dependencies? I'm not pushing for this solution, but others may wonder about it, so maybe it's good to have a note addressing why it's not our approach

For this to work, we'd have to get charm and charm library authors to:

- depend on the fake package
- resolve dependencies, that is have a lock file
- publish the fake package for every released Juju version
- have charmcraft read the version of the installed fake package

## Further Information

### Charm package

Today, charm source code is typically a script and not a Python package, though the repository almost always includes `pyproject.toml` which contains tooling configuration and often the charm's dependencies. Thus it is not straightforward for the charm to express the Juju version that the charm code itself requires. Which brings a question about the semantics when charm's `charmcraft.yaml` or `metadata.yaml` file includes the `assumes` block.

### Assumes

[Juju](https://github.com/juju/juju/blob/15dfb49b4e0b593f28f44e1250b4b32dd9f92920/core/assumes/features.go#L12-L29) currently supports these assume keywords: `juju` and `k8s-api`.

- the `juju` keyword is used to restrict Juju controller versions the charm can be deployed on
- the `k8s-api` keyword is used to indicate that a Kubernetes substrate is required

In a complete solution, an additional keyword or keywords is needed to indicate that a machine substrate is required.

#### `juju`

The version of Juju used by the model.

Usage in today's charms: [always used with a lower bound and sometimes with an upper bound](https://github.com/search?q=org%3Acanonical+%22assumes%3A%22+%22-+juju%22+language%3AYAML&type=code) to represent several non-overlapping version ranges.

#### `k8s-api`

The Kubernetes API lets charms query and manipulate the state of API objects in a Kubernetes cluster.

Today, k8s charms use this assume to indicate that the charm should only be deployed on a Kubernetes substrate, however it's used as a Boolean, without a required version, both in charms that merely indicate the required substrate, charms that use the k8s API for something simple, and charms that rely on the k8s API to rewrite stateful set declaration.

Usage in today's charms: [always used without a numeric argument](https://github.com/search?q=org%3Acanonical+%22assumes%3A%22+%22-+k8s-api%22+language%3AYAML&type=code).

#### `machine` (hypothetical)

There's currently no way for the charm to indicate that it must be deployed on a machine substrate.

While out of the scope of this specification, there should be a way for a charm to indicate that it can only function on a machine substrate.

The currently discussed options are:

- a single `machine` or `vm` assume, or

- individual, fine-grained features, such as:
  - `ip-address-may-change` for charms that respond to changes in local ip addresses
  - `can-modify-vm-boot-parameters` for charms that configure the linux huge page pool
  - `snapd` for charms that install snaps
  - `systemd` for charms that integrated into systemd, installing services or hooks to respond to service notifications asynchronously
  - `crond` for charms that install periodic jobs
  - `logrotate` for charms that expect workload logs in the same namespace as the charm and install configuration to rotate these logs (while k8s charms would run logrotate as another service in the workload container instead)
  - `rsyslog` for charms that inject custom log forwarding
  - `ca-certificates` for charms that add root CAs in the charm namespace
  - `dns` for charms that alter host bindd configuration
  - `openvpn` for the one charm that installs OpenVPN, write out config to `/etc` but also expects the host network tables to be modified
  - `modprobe` for charms that install additional kernel modules
  - `sysctl` for charms that update the system configuration parameters
  - `sudo` for charms that tweak the sudoers policy
  - `xinetd` for a couple of charms that install daemons and expect them to be started on incoming connections
  - `mounts` for charms that validate storage via `mountpoint` (also possible in k8s) but also remount some volumes (?)
  - `fstab` as a part of snap integration (arguably part of `snapd`)
  - `system-event-log` for the `ipmiseld` (a systemd service) to collect interesting data
  - `?unclear?` for the subordinate charm that expects Kubernetes to be installed on that given machine and integrates with it ([autocert-charm](https://git.launchpad.net/autocert-charm)).
  - `?letsencrypt?` for the subordinate charm that expect LetEncrypt to be installed on the machine and integrates with it, and also includes integration with AWS, GCP and  ([certbot-charm](https://github.com/canonical/certbot-charm))
  - `etc` for charms that own the config files in `/etc` (arguably may work on k8s too)
  - `apt` for charms that install apt packages (though that's also possible on the k8s substrate in the `charm` container)
