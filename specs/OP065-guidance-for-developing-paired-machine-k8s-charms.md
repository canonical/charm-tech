# OP065 — Guidance for developing paired Machine/K8s charms

| Field | Value |
| --- | --- |
| Type | Informational |
| Created | Apr 2, 2025 |

## Abstract

It's common to have pairs of charms, one for deployment on "machines", and for one deployment to Kubernetes (K8s) - the expected functionality of the charms is the same, but the implementation of the charm has differences to handle the different substrates. There are currently several approaches to maintaining these charm pairs - this spec provides guidance for best practices (but is not prescriptive). In the long term, we expect that it will be easily possible to produce charms that can be deployed to either machines or K8s from a single code-base.

## Rationale

Maintaining two separate code bases to provide machine and Kubernetes charms is not ideal. As a step towards universal charms, we recommend unifying the charm code (multiple charmcraft.yaml files will still be required, and multiple packed charms). In the longer term, we expect that a single charm code base will be possible much more simply (for example, if a machine charm uses an OCI image and has Pebble, then significantly more of the code is common). A goal of this specification is to support moving towards a true single set of code incrementally as these changes arise.

## Specification

### Sharing code

#### Not recommended

A charm lib for common code is not recommended: charm libs have significant issues with dependencies, are restricted to a single file, and there are no mechanisms (other than documentation) to indicate that a charm lib is intended only for internal use and not for use by other charms. A package on PyPI is also generally intended for wider use (and will be found via search), and includes additional overhead for managing publishing. A package via source control link makes packing the charm more complex, and still requires managing two to three repositories and keeping them in sync.

#### Recommendation

Use a single repository that contains three top-level folders, one for common code, one for building a machine charm, and one for building a Kubernetes charm. A single repository allows updating both charms in a single PR, and avoids having to manage an internal-only dependency.

Add a symlink in the charm `src` folder to the `common` folder, so that the tooling can locate the code. charmcraft does not support resolving symlinked folders when packing ([and are blocked adding this support](https://github.com/canonical/charmcraft/issues/1079)). In your `charmcraft pack` command (for example, in a Makefile or tox environment), remove the symlink, copy the folder of common code where the symlink was, and then after pack completes (including if it fails) remove the copy and add the symlink back. An example of this is below, or see the [vault-k8s charm Makefile](https://github.com/canonical/vault-k8s-operator/blob/main/Makefile) for a slightly simpler approach in use.

```shell
#!/bin/bash

SYMLINK="src/common"
TARGET="../common"

if [ -L "$SYMLINK" ]; then
    rm "$SYMLINK"
fi
cp -r "$TARGET" "$SYMLINK"

charmcraft pack

rm -rf "$SYMLINK"
ln -s "$TARGET" "$SYMLINK"
```

Note that in the future when charms are built via the upcoming build machinery mechanism, any change to the repository will result in rebuilding all artefacts from the repository. For example, if code specific to the machine charm changed, that would trigger a new revision of both the machine and Kubernetes charms. We do not consider this an issue at this time, and by the time upcoming build machinery charm building is common, other solutions for common charms may exist.

### Structuring code

#### Abstract out the pieces that differ significantly

This typically involves the install and remove hooks where a Kubernetes charm has packages provided through the OCI image and needs to define services in pebble-ready, but a machine charm needs to install and later remove snaps or other packages and management is provided by the package. This code that differs significantly should live in the charm classes in the machine charm and Kubernetes charm folders.

#### Common charm base class

Create a base charm class (inheriting from `ops.CharmBase`) for the charms in the common folder, and have each of the charms inherit from this rather than from `ops.CharmBase`. The majority of the logic for handling events from Juju is able to be located in the base charm, with any specifics (such as package installation) located in the substrate-specific charm.

#### Common workload module

Each charm should continue to have its own workload module in src, as for single-substrate charms. However, the majority of the logic for interacting with the workload should be able to be located in the common code. For example, if the charm communicates with the workload via HTTPS, the majority of this interaction will be identical across machine and Kubernetes charms, and if the charm communicates via process calls, each charm can provide a method that calls a process (for example, `subprocess.call` on machines, and `container.exec` on Kubernetes) and handles errors, while the specifics of which commands are run in response to which events is kept common.

### Tools

Use libraries that provide a common interface over machine and Kubernetes charms:

* [pathops](https://pypi.org/project/charmlibs-pathops/) provides a pathlib-like interface that uses native file operations on machine charms and Pebble file operations on Kubernetes charms.

Consider building other such libraries, for example:

* A common interface for service management, using Pebble for Kubernetes charms and [systemd via operator-libs-linux](https://charmhub.io/operator-libs-linux/libraries/systemd) for machine charms.
* A common interface for custom notices, using Pebble for Kubernetes charms and [systemd via operator-libs-linux](https://charmhub.io/operator-libs-linux/libraries/juju_systemd_notices) for machine charms.

Note that in the future, Juju expects to provide a style of machine charms that run an OCI image including Pebble, which would provide a common API for machine and Kubernetes charms for services, file operations, and Pebble events, although a Kubernetes charm has 1 to n containers, and a machine charm would have a single container. When designing common interfaces, it is therefore typically best to provide a Pebble-like API (translating the machine side) than the other way around.

It is currently recommended to *not* implement common code by installing Pebble on a machine, other than for experimental exploration.

## Further Information

### Existing Machine/K8s Charm Pairs

The pairs of Machine/K8s charms that were reviewed during the development of this spec are:

#### Data Platform

* [kafka](https://github.com/canonical/kafka-operator), [kafka-k8s](https://github.com/canonical/kafka-k8s-operator) (both charms have charm, workload, and common support modules, and the charm modules are very similar; there's also heavy use of the common charming systems that are used across the data platform charms. There's no obvious explicit code sharing of the charm module)
* [mongodb](https://github.com/canonical/mongodb-operator), [mongodb-k8s](https://github.com/canonical/mongodb-k8s-operator) (see [below](#mongodb:-declarative-charms))
* [mongos](https://github.com/canonical/mongos-operator), [mongos-k8s](https://github.com/canonical/mongos-k8s-operator) (see [below](#mongodb:-declarative-charms))
* [mysql](https://github.com/canonical/mysql-operator), [mysql-k8s](https://github.com/canonical/mysql-k8s-operator) (see [below](#mysql-&-postgressql:-common-code-in-a-charm-lib))
* [mysql-router](https://github.com/canonical/mysql-router-operator), [mysql-router-k8s](https://github.com/canonical/mysql-router-k8s-operator) (see [below](#mysql-router:-common-code-in-a-synced-module))
* [pgbouncer](https://github.com/canonical/pgbouncer-operator), [pgbouncer-k8s](https://github.com/canonical/pgbouncer-k8s-operator) (some overlapping code, some use of the data platform charming systems, no obvious code sharing)
* [postgresql](https://github.com/canonical/postgresql-operator), [postgresql-k8s](https://github.com/canonical/postgresql-k8s-operator) ([see below](#mysql-&-postgressql:-common-code-in-a-charm-lib))
* [zookeeper](https://github.com/canonical/zookeeper-operator), [zookeeper-k8s](https://github.com/canonical/zookeeper-k8s-operator) (separate charm and workload modules, some use of the data platform charming systems, very similar charm structures, some code overlap, no obvious code sharing)

#### Identity

* [glauth](https://github.com/canonical/glauth-operator), [glauth-k8s](https://github.com/canonical/glauth-k8s-operator) (glauth has workload and charm module separation; the K8s charm has significantly more integration support; there's no obvious code sharing)

#### Telco

* [vault](https://github.com/canonical/vault-operator), [vault-k8s](https://github.com/canonical/vault-k8s-operator/) (the -k8s repository has both charms and the common code; there's a custom build script that handles copying across the common code. The suggestions above are strongly based on the approach used here)

#### Observability

* [grafana-agent](https://github.com/canonical/grafana-agent-operator), [grafana-agent-k8s](https://github.com/canonical/grafana-agent-k8s-operator) (common code is located in a module found in both charm repositories, these are not identical in main@HEAD, and it seems like they are manually kept in sync, similar to the MySQL Router approach outlined [below](#mysql-router:-common-code-in-a-synced-module))

#### IS

* [content-cache](https://github.com/canonical/content-cache-operator), [content-cache-k8s](https://github.com/canonical/content-cache-k8s-operator) (charms seem quite different - the K8s one has significantly more code and functionality - and no obvious code sharing)

#### Platform Engineering

* [jenkins-agent](https://github.com/canonical/jenkins-agent-operator), [jenkins-agent-k8s](https://github.com/canonical/jenkins-agent-k8s-operator) (charms are written in a very similar style, but other than both using the IS state system, don't have any obvious code sharing)

### Existing methods for code sharing

#### MongoDB: declarative charms

The four MongoDB charms (Machine/K8s, sharded/non-sharded) use a [common base package](https://github.com/canonical/mongo-single-kernel-library). This includes almost all of the code required for the four charms, so that each charm ends up being essentially declarative. For example, the [MongoDBK8s charm](https://github.com/canonical/mongodb-k8s-operator/blob/6/edge/src/charm.py) is only these eight lines (25 lines including imports and the main call):

```py
class MongoDBK8sCharm(AbstractMongoCharm[MongoDBCharmConfig, MongoDBOperator]):
    """Charm the service."""

    config_type = MongoDBCharmConfig
    operator_type = MongoDBOperator
    substrate = Substrates.K8S
    peer_rel_name = PeerRelationNames.PEERS
    name = "mongodb-k8s"
```

Some of the common code here is not specific to MongoDB, but helper classes and methods for charming more generally. At least some of this is expected to be available in Ops in the future, and in general our recommendation would be to propose improvements to Ops before including generic common code across variants of charms - that might result in Ops providing the common functionality, or recommendations for using existing functionality without needing the additions, or a conclusion that it's not suitable for Ops and including it in the charms-specific code is best.

The data platform charms are the most complex of the current Canonical charms, and this approach suits their needs (as can be seen in the other methods outlined here, the team has tried many other approaches before developing this one). For less complex charms, a less complex method of sharing code is desirable. The data platform charms are also, such as in this case, sharing code across more than a pair of charms - in this case four charms.

#### Vault: monorepo with shared common code

The Vault charms have a [single repository](https://github.com/canonical/vault-k8s-operator/tree/main) that contains [Machine](https://github.com/canonical/vault-k8s-operator/tree/main/machine) and [K8s](https://github.com/canonical/vault-k8s-operator/tree/main/k8s) charms. The K8s charm owns the common code and it is fetched this code into the Machine charm using ``make vendor-libs``, which copies the code from the K8s charm's `lib/vault` directory to the Machine charm's `lib/vault` directory. (Note that this is not `lib/charms` - a charm lib - it's a separate directory under lib). Both copies exist in the repository, which is probably not ideal. The common code doesn't include a charm base model, but has managers, helpers, errors, and so forth.

#### MySQL Router: common code in a synced module

There is a common charm base class in a module in both repositories, which appears to be manually synced (and is currently in sync). There is other common code, and the code is separated out into charm and workload modules as per the latest recommendations.

#### MySQL & PostgresSQL: common code in a charm lib

These charms have a common charm base class that is located in a charm lib (charms.mysql.v0.mysql and charms.postgresql.v0.postgresql) that one of the charms owns.

#### Charm code sharing for other purposes

There are also other charms that share common code, but for purposes other than building Machine & K8s pairs:

* The 12-factor charm templates have a common base that is used for all charms based on the templates: [paas-charm](https://github.com/canonical/paas-charm)
* The Sunbeam charms use a monorepo with shared code using a custom build system (all in the monorepo): [Sunbeam charms monorepo](https://opendev.org/openstack/sunbeam-charms)
* The filesystem charms use a monorepo with shared code in a charm lib (code for the lib is also in the monorepo): [filesystem charms monorepo](https://github.com/charmed-hpc/filesystem-charms)
* The COS charms share some functionality via a common library (although this doesn't provide base classes for charms): [cos-lib](https://github.com/canonical/cos-lib)
