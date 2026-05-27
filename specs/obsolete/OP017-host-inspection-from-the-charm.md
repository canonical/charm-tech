# OP017 — Host Inspection from the Charm

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-04-28 |

## Abstract

This covers adding some ability to inspect several host parameters from within the charm.

## Rationale

It is sometimes useful for a charm to know what "base" it is running on, or know what cloud features the charm author "assumes" that it has access to.

For example, a charm author might want to detect whether they are running on an apt or yum based distro, and install packages accordingly. Or a charm author might want to check for the existence of snapd, or the availability of a specific type of storage.

## Specification

A charm's metadata.yaml provides some fields that outline possible properties a host might have. The `bases` lists all the OS/arch combinations where a charm might be deployed, for example, and "assumes" lists the cloud features that a charm can rely on.

We can expose the information from the metadata.yaml, but this possibility list is of limited use to a charm that is running on a specific host, in a specific environment.

This specification will be complete when it outlines how we might inspect and expose host information, possibly starting from the metadata, and possibly simply relying on tooling in the host machine, or in Pebble.

It is unclear, as of the time of this writing, how much cross team effort will be required.

### List of Useful Host Features to Detect

(Please feel free to expand on this. This is very much a collaborative spec!)

- The presence or absence of a GPU. (HPC charmers and ML/kubeflow charmers might benefit from this feature, and can help define the requirements.)
- The presence or absence of a specific package manager or similar service (apt, yum, snapd, etc.)
- The presence or absence of "fast" storage.
- Whether we are running in a Docker style container, or a full featured lxd container, vm, or bare metal host.
  - Caution should be used here: we don't want to encourage tangles for branching paths, based on substrate, in our charms.
  - The type of shell/environment you get on the other end? Is cat present, is it bash, is it sh, is initd running, is it pebble?
- Support for a specific Juju feature, such as events from Pebble.

## Further Information

This spec is essentially a reframing of some of the ideas and comments in the [Metadata v2 Support](https://docs.google.com/document/d/1NHmcQ__Qz7AhtuZYazfUChOLQ83i-CDUmGBkoh3f0Bc/edit?usp=sharing) spec.

## History

* 27 Oct 2023: Rejected by [Ben Hoyt](mailto:ben.hoyt@canonical.com) as not touched / too old / never implemented.
