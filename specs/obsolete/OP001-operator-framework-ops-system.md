# OP001 — Operator framework 'ops.system'

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2021-06-13 |

## Background and motivation

Pebble charms currently operate under the assumption that workloads will be pre-composed or container-based workloads which contain all necessary application dependencies as part of a single image. In the future, the Operator framework must be extended to support machine charms which may require package additions to the host system. In addition, in the case of specific workloads as containers/VMs, it may be desirable to add explicit mountpoints to the system ([e.g. automatic installation of NVIDIA drivers from inside a pod](https://github.com/GoogleCloudPlatform/container-engine-accelerators/tree/master/nvidia-driver-installer/ubuntu))

In order to support these workloads, a proposed ops.system should be added to the Operator Framework which is capable of adding and managing system repositories and packages for machine charms.

Juju charms want to register for event notifications from the system to be aware of when a package has successfully installed or failed to install, to be able to list enabled repositories, and to add additional repositories to the system.

Machine charms may also need to add/manage users, apparmor profiles, and systemd services (TBD: whether Pebble will manage system services in machine charms)

A charm would be able to subscribe to events from the system which are added over time and without the need for Juju to be upgraded to support new/removed events where possible.

Examples Of Events That a Charm May Want To Receive:

* System:
  * Support initially:
    * Requested package status (installed/removed/failed)
    * Hold package version
    * Snap management
    * Requested repository status (enabled/failed/requires intervention)
    * Repository data (if explicitly requested)
    * Users/group addition
    * Service status
  * Nice to have but could be added in future versions:
    * Hardware functionality is available (SR-IOV, GPU, nested|normal virtualization
    * Apparmor status/failures
    * Running containers
    * Cronjob/Job;

## Proposed solution and implementation

We propose adding new classes and events  to the Operator Framework which can support these events. Initially, the API should be simple

For package management, PackageKit was evaluated and is not suitable unless we wanted to add another sidecar to charms. Even though it's unlikely that sidecar charmers will need or want to manage system properties, negating an entire part of the framework does not feel correct, and PackageKit does not handle snap

### Python Operator Framework API

The ops.system namespace would have several new classes as follows:

class User:
    def groups(self, groups: List) -> None
    def _add(self) -> None: ...
    def _remove(self) -> None: ...
    def home(self, homedir)
    def shell(self, shell)
    def enable(self) -> None: ...
    def disable(self) -> None: ...
class Group:
    def __init__(self, name) -> None: ...
    def _add(self) -> None: ...
    def _remove(self) -> None: ...
    def enable(self) -> None: ...
    def ensure(self, present=True, absent=False)
    @property
    def present(self) -> bool

# with the following additional methods/parameters for:
class Package:
    def ensure(self, present=True, absent=False, version=)
    def hold(self, version=)

class Snap:
    def ensure(self,present=True,absent=False,channel=)

class Repository:
    def ensure(self, present=True, enabled=True, gpg_key=)
    def baseurl(self, url)
    Def release(self, release)
    def pin(self, version=)
\\

These would raise events upon method resolution in the following format:

    (class)_(action)
With additional methods on Repository to enable add-apt-repository

## Out of scope

*

## Open questions

* Intervention for repos which require GPG keys?
