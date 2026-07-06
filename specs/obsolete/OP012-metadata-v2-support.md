# OP012 — Metadata v2 Support

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2021-11-29 |

## Problem statement

The Operator Framework does not fully support Juju's revised metadata format, informally known as "metadata v2".

This spec outlines the work needed to provide support for the missing fields.

## Reference

* [Charm metadata spec](https://juju.is/docs/sdk/metadata-reference)
* The bulk of the code to be edited lives in the [CharmMeta class](https://github.com/canonical/operator/blob/3f20f80f5bea159ab1f3e1d2ba0dc3d97d668520/ops/charm.py#L682).

## Current state of the world

#### Deprecated Fields

The following fields are supported by the OF, but have been deprecated in metadata v2.

| tags |
| :---- |
| series |
| min_juju_version |
| payloads |

#### Supported Fields

The following fields are supported by the OF, and are in the current version of the spec.

| Field | Required/Optional |
| :---- | :---- |
| name | Required |
| summary | Required |
| description | Required |
| maintainers | Optional |
| terms | Optional |
| subordinate | Optional |
| requires | Optional |
| provides | Optional |
| peers | Optional |
| relations | Optional |
| resources | Optional |
| extra-bindings | Optional |

#### Un/Partially Supported Fields

The following fields have not yet been implemented, or are missing some support.

| Field | Required/Optional | Notes |
| :---- | :---- | :---- |
| devices | Optional | Needs to be added |
| containers | Optional | Only container `name` current exposed. We intend to additionally expose resources, storage, etc. |
| assumes | Optional | Available as of Juju 2.9.22. [[Spec](https://docs.google.com/document/d/1D4ECIWFBxe_7IZE0q1nkEGE8O2QqmTinKOpx5EL7ReI/edit?usp=sharing)] |
| storages | Optional | Implemented, but could use more detail. See [github #646](https://www.google.com/url?q=https://github.com/canonical/operator/issues/646&sa=D&source=docs&ust=1638975734977000&usg=AOvVaw3u8Rjhzru3577Sx_dNg-f8)  |

### How the Code Currently Works

The Operator Framework parses a charm's metadata.yaml and models it as a Python object called CharmMeta. This object is accessible everywhere as `framework.meta`. The object comprises a mapping of properties that themselves map to either Python builtin representations of simple metadata, or Object representations of more complex metadata.

For example, CharmMeta.relations is a mapping of RelationMeta objects. Each RelationMeta object contains the data that one would expect, in addition to doing useful things like populating the "scope" of a relation with the default scope, if the charm author did not override it.

The original data from the yaml is referenced internally as "raw", but is not directly accessible via the tooling in the Operator Framework.

## Proposed Solution

The work to do here is relatively straightforward. We want to make the new fields available as Python objects where appropriate. We would also like to pay off some technical debt in the testing framework (see the last step). _

In detail, we propose make the following changes:

1. #### Skip(?) support for `assumes`

   In lieu of writing capability checks in Python, charm authors may specify a set of Juju or Cloud features they assume will be available in the metadata.yaml. Since the purpose of this entry in the metadata is to make it possible to write a feature without implementing anything in Python, it probably doesn't make sense to include the data in the Operator Framework's object model for now.

   Note that if we did want to include assumes support, it might look a little bit like this:
   (**Edit**: it looks like the Juju team did go with a small DSL for assumes. See the new [about assumes](https://discourse.charmhub.io/t/about-assumes/5450) docs! The below code is overly simplistic, and would need to be expanded to take into account any-of, all-of, and version constraints.)

   ```` ``` ````
   `class Assumes:`
       `def __init__(...):`
           `# parse the assumes list into self._assumes`
       `def includes(self, feature):`
           `return feature in self._assumes`
       `def all(self):`
           `return self._assumes`
   ```` ``` ````

   Thus a charm that re-used code across channels, but changed the metadata.yaml, might do something like:

   ```` ``` ````
   `if model.meta.assumes.includes("controller_storage"):`
       `# do a thing`
       `return`
   `# do another thing`
   ```` ``` ````

   (Note: it would be interesting to replace ``all`` above with `` `__call__ ``` So a charm author would either call ``self.meta.assumes.includes``, or ``self.meta.assumes``. This is not consistent stylistically with the other Meta objects, however.)

2. #### Skip(?) support for `devices`

   Like assumes, the devices entry in the metadata v2 exists to ensure that something is always available to the charm, without requiring explicit capability checks in Python. In the case where a device may or may not be present, a charm author should leave the devices entry blank, as metadata.yaml is not modifiable at runtime, and a capability check is really what's required.

   That said, there might be cases where a charm author may wish to handle different channels of a charm using the same core Python code. If we want to provide support for this in the core Operator Framework, we might do something like:

   ```` ``` ````
   `class DevicesMeta:`
       `def __init__(...):`
           `# parse the data`
           `self._gpu_accelerated = # True if gpu entry in the metadata else False`
           `...`
       `...`
       `def gpu_accelerated(self):`
           `return self._gpu_accelerated`
       `...`
   ```` ``` ````

   A charm author could then call helpers like ``model.meta.devices.gpu_accelerated`` to check for the availability of gpu processing, and branch accordingly.

   This is not necessarily less complex than using subprocess to call the gpu equivalent of `kvm_ok` (does `gpu_ok exist`?), and we might just want to leave this data out of the framework. (Or, alternatively, write a library that wraps things like ``kvm_ok``, and presents them as a nice Python object distinct from CharmMeta.)

3. #### Possibly expand support for `containers`

__
In metadata v2, the containers field has been expanded with some information about where the charm is capable of running. For kubernetes charms, the metadata.yaml specificies a "resource" which was used to seed the container. For machine charms, the metadata.yaml includes a list of "bases" (operating systems, channels, and architectures) upon which the charm runs.

This metadata is useful as a reference at deploy time, because it informs an Operator where they might be able to successfully deploy the charm. At runtime, the information is not useful, however, as there is no indication in the metadata.yaml of which "base" was picked.

That said, when writing a charm, charm authors must specify *either* a resource, in the case of kubernetes charms, or one or more bases, in the case of charms running on lxd and "legacy" substrates. This fact does allow us to write the following check:

```
class CharmMeta(..):

    def __init__(...):
        ...
        self._is_k8s = raw.get('containers', {}).get('resource', False)

    def is_k8s(self):
        return self._is_k8s
```

We may not want to encourage the use of this routine, however. There *is* a need for this logic in the testing harness, but that can be hidden away as an implementation detail of the harness, rather than being exposed to charm authors.

4. #### ~~Possibly expand support for `storages`~~

   ~~OF parses storage entries into StorageMeta classes, each with a .location property. This location property is None if it has not been set explicitly in metadata.yaml. At runtime, if the path has not been overridden, the juju will mount the storage at `/container/path/<name>/<number>`. Per [GH#646](https://github.com/canonical/operator/issues/646), charm authors would like location, if it is null, to be populated by this derived storage path, so that they can always inspect StorageMeta.location to get the path to the storage, rather than checking for an override there, then attempting to look it up themselves.~~

   ~~In terms of code, we'd patch StorageMeta as follows:~~



   ~~```~~

   ~~`class StorageMeta(...):`~~

       ~~`- self.location = raw.get('location')`~~

       ~~`+ self._location = raw.get('location')`~~

   ~~`...`~~

   ~~`+ @property`~~

   ~~`+ def location(self):`~~

   ~~`+     if self._location is not None:`~~

   ~~`+         return self._location`~~

   ~~`+     name = # fetch storage name`~~

   ~~`+     number = # fetch storage number`~~

   ~~`+     self._location = '/path/in/container/{}/{}'.format(name, number)`~~

   ~~`+     return self._location`~~

   ~~```~~

   ~~Note that obtaining ``` name` ``, ``` number` `` and the container path would require introspection of information that may not be available when the routine is called, or when the Meta objects are being instantiated. We suggest that this task be timeboxed, and only addressed as part of the scope of this spec if there is a trivial and safe way to get at those values at runtime.~~

5. #### ~~Pay off technical debt in the testing suite.~~

   ~~There is a test ``metadata.yaml`` in our testing harness. It lives at ``test/charms/test_main/metadata.yaml``~~

   ~~The test yaml contains deprecated fields, such as ``series``, ``tags``, and ``min juju version``.~~

   ~~Unfortunately, our testing harness expects (and processes) both deprecated fields, and "new" metadata v2 fields, making it non trivial to refactor tests to rely on either a new "v2" metadata.yaml, or the old yaml (for backwards compatibility checks).~~

   ~~We need to do the following:~~

1) ~~Break the metadata.yaml into metadata.yaml and metadata_v1.yaml~~
2) ~~Refactor tests so that they rely on one or the other, favoring the new yaml where possible.~~
3) ~~Deal with the big caveat below.~~

   **~~Caveat~~**~~: there are parts of the harness that rely on log messages and other similar things happening in a particular order, based on the arbitrary order of items in Python objects. This is the scariest part of the technical debt, because it happens in parts of the framework that run on almost every test. I'd like to take the opportunity to pay it off here if we can. Fixing the issue will involve a certain amount of trial and error that is hard to capture in the spec. The work should be timeboxed, and set aside for a later date if it threatens the scheduling for other in-cycle work.~~
