# OP075 — Charm Monorepos

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Informational |
| Created | 11 Aug 2025 |

## Abstract

Charming teams manage many charms, and often need to update multiple charms at the same time, for example machine and Kubernetes versions of the same charm. Monorepos are a natural solution here, but upcoming build machinery does not currently support producing multiple artifacts of the same `craft` from a single repo (besides `sourcecraft`), which presents an obstacle to charm monorepos.

This spec describes how charms might be able to use a monorepo-like approach with what we currently know about upcoming build machinery: by having a core repo where all the charm code is worked on, and then a separate repo for each charm with just a `charmcraft.yaml` file.

This spec is intended as a starting point for further discussion about *what's feasible*, *what's recommended*, and *what might change* in future. While this spec focuses on charms, rocks face the exact same technical challenge.

## Rationale

Some charms are closely related, making it useful to update them together. These include machine and Kubernetes versions of the same charmed application ([list](https://www.google.com/url?q=https://docs.google.com/document/d/1wCySfdM7nQQfqzwzUcI-NPQxzCPFzBk2Uern3RWlQoc/edit?tab%3Dt.0%23heading%3Dh.38tl5vagfwvd&sa=D&source=docs&ust=1756165796301563&usg=AOvVaw3Eax9MS9vuylsnbwu3Jlb7)), pairs of coordinator and worker charms, and grouped efforts like HPC and Sunbeam. Keeping these in sync is harder when each charm lives in a separate repo, and the need to update multiple repos makes testing these changes against each other more difficult.

The HPC and Sunbeam teams have used charm monorepos successfully for some time. However, their approach will not be compatible with upcoming build machinery onboarding. An alternative approach tried by other teams to be compatible with upcoming build machinery is hosting as much charm logic as possible in a shared Python package. For example, [`mongo-single-kernel`](https://github.com/canonical/mongo-single-kernel-library) - though even these developers have expressed a desire not to have to manage the common code and the charms in separate repos.

True charm monorepos are not compatible with upcoming build machinery right now, since a single top-level `charmcraft.yaml` file provides the `charmcraft` entrypoint for upcoming build machinery. However, we may be able to get many of the benefits of a charm monorepo while retaining a separate repository for each charm, by pushing as much as possible into a monorepo, and having satellite repos that just provide the top-level `charmcraft.yaml` entrypoint for upcoming build machinery. This is not quite as smooth a developer experience as a true monorepo, but will still be a nice improvement over otherwise trying to manage multiple charm repositories.

## Specification

*All the charm code (for multiple charms) and any common code would live in a core sourcecrafted repository, while the `charmcraft.yaml` files for the charms would live in their own repos, one per charm, and pull in the core repo during packing via parts.*

For example, the 'monorepo' might look like this (based on the `vault` charm monorepo, which contains a machine and kubernetes charm pair with lots of common code):

```
# repo: canonical/vault-operator-core

common-code/
  src/__init__.py
  pyproject.toml

kubernetes-charm/
  src/
    charm.py
    helper.py
  tests/
  pyproject.toml

machine-charm/
  src/
    charm.py
    helper.py
  tests/
  pyproject.toml

pyproject.toml  # common tool config, yay for monorepos
sourcecraft.yaml
```

The charms themselves would be onboarded into upcoming build machinery from separate repositories containing only the `charmcraft.yaml` files, for example:

```
# repo: canonical/vault-k8s-operator
charmcraft.yaml

# repo: canonical/vault-operator
charmcraft.yaml
```

These `charmcraft.yaml` files would refer to `canonical/vault-operator-core` as the `source` for their `parts`. In the simplest case, imagine we use the `dump` plugin to get all the files from the monorepo. Then we could massage them into a structure like this, and use a standard charm plugin (e.g. `uv`, `charm`) to proceed from there:

```
# from canonical/vault-operator-core top-level
common-code/
  src/__init__.py
  pyproject.toml

# from (e.g.) canonical/vault-operator-core kubernetes-charm dir
src/
  charm.py
  helper.py
pyproject.toml
```

Here we imagine that `pyproject.toml` specifies `common-code` as a dependency both in the 'monorepo' (for testing) and during packing (e.g. by running `uv add ./common-code` at this point).

## Implications

The `charmcraft.yaml` repositories would be logically separate and updated independently from the core repo. This introduces complications when wanting to make atomic updates to charm code and charm metadata.

The following strategies can mitigate this:

* Updates can be ordered to avoid the need for atomic updates, e.g. drop config option in `charmcraft.yaml`, then drop the code for it. Add code for a new action, then add the action to `charmcraft.yaml`.
* Changes to `charmcraft.yaml` could be prototyped in the monorepo and then transferred to the `charmcraft.yaml` repos either manually or via some automation, allowing charm code to be tested with new metadata during development.
* The `charmcraft.yaml` files could contain only the `charmcraft` specific information, with the Juju metadata defined in the core repo under `k8s/metadata.yaml`, `machine/config.yaml`, etc. This would cut down on the need to update `charmcraft.yaml` a lot.

Atomic updates (from the perspective of charm releases) would be possible by massaging the release channel/branch of the core repo, and the target of the `charmcraft.yaml:parts:source` appropriately. In this example,  we assume that `charmcraft.yaml` normally depends on the common code's `A` release channel,  and `B` is otherwise unused.

1. Push an update to `B`.
2. Update `charmcraft.yaml` as needed and change its dependency to `B`.
3. Update `A` to match `B`.
4. Point `charmcraft.yaml` back to `A`.

Steps 1 and 3 would trigger `sourcecraft` rebuilds of the common code, while steps 2 and 4 would trigger `charmcraft` rebuilds of the charm. Step 3 would also trigger a `charmcraft` rebuild for any other charms depending on `A` - but presumably, all dependent charms would be updated in steps 2 and 4, triggering their own rebuilds there.

## Alternatives

### Wouldn't it be nice if upcoming build machinery had first-class monorepo support?

The need for the additional `charmcraft.yaml` repositories could be eliminated entirely by allowing multiple artifacts of the same `craft` to be built from the same repository. This would greatly simplify the monorepo experience for our developers. Here are a couple of ideas:

1. Specify an alternative `*craft.yaml` path when onboarding, to be stored as additional metadata alongside the repository.
2. Onboard multiple artifacts at once by parsing a new config file format. This could be implemented on a craft by craft basis, following a common convention, e.g.:
   1. A `charmcrafts.yaml` (or `charms.yaml`, etc) file which lists multiple project directories and/or `charmcraft.yaml` files.
   2. A new `type` for `charmcraft.yaml` that lists multiple project directories and/or `charmcraft.yaml` files.

### 'Mirror' release repositories

An alternative to having repositories with just `charmcraft.yaml` would be for `canonical/vault-k8s-operator`  and `canonical/vault-operator` to both be exact copies of `canonical/vault-operator-core`, but with a single, top-level `charmcraft.yaml` symlink added to point to an appropriate `charmcraft-*.yaml` file stored in `vault-operator-core` (e.g. `charmcraft-k8s.yaml` and `charmcraft-machine.yaml`).

* With this approach, `vault-operator-core` doesn't need to be onboarded into upcoming build machinery in order to release the charms, though it could still be onboarded to facilitate making (security) updates from inside the system.
* Atomic modifications of all parts of the monorepo are possible. Changes would be automatically propagated to the `charmcraft.yaml` repos (requiring some CI setup).
* Security updates would ideally be made to the monorepo, but could be pulled into the monorepo from the `charmcraft.yaml` repos if need be (requiring some more CI setup).

A variant on this alternative would be to have the 'mirror' repositories apply other mechanical changes to the structure (e.g. moving files to different locations to look more like an individual charm repo, making the `charmcraft.yaml` files more similar to those in individual charm repos).
