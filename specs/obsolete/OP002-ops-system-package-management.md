# OP002 — 'ops.system' Package Management

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2021-07-11 |

## Abstract

In order for the Operator Framework to better support the development of machine charms (and other use cases where management and observability of packages and their repositories is needed), ops.system should provide abstractions and plumbing around common package management utilities.

## Rationale

A charm author must be able to install, remove, replace, and pin packages which are needed to support the charmed application. Though Juju is not a configuration management system as-such,  ops.system shall follow more or less the same semantics as existing configuration management and orchestration systems (Ansible, Puppet, etc). The API is designed around keywords such as ensure so it feels familiar.

One of the difficulties faced is configuration drift. In the case of orchestration systems such as Ansible, an administrator can freely log into a system immediately after a playbook is applied and add/remove/upgrade packages to their heart's content, and Ansible will not automatically remediate this. In contrast to this, configuration management systems with agents continuously monitor drift and ensure that the system is in the "correct" state. Juju machine charms sit in a "middle ground". If we are able to effectively monitor package changes and send events, ensure can remediate at least some of the drift.

Repository management carries the additional complexity of key management for signed package repositories. For flexibility, this is not necessary with (most) non-system repositories on RPM-based systems, but ops.system will abstract this, raising a meaningful exception if a configured repository requires a key which is not configured.

**Specification**

We propose adding new classes and events  to the Operator Framework which can support this workflow..

The ops.system namespace would have several new classes as follows:

class SystemStateBase(IntEnum):
    Present = 1
    Absent = 2

class PackageStateBase(IntEnum):
    Latest = 3

class RepositoryState(SystemStateBase)

# iterate over the above enums to generate PackageState
# since you cannot subclass Enums the 'normal' way

class SnapStateBase(IntEnum):
    Latest = 3

class RepositoryState(SystemStateBase)

class PackageMapping:
    def __init__(self, backend, cache) -> None:
    def __contains__(self, key) -> bool:
    def __len__(self) -> int:
    def __iter__(self) -> Iterable[Package]:
    def __getitem__(self, key) -> Package:

class Package:
    def __init__(self, name, version=None) -> None:
    def _add(self) -> None:
    def _remove(self) -> None:
    @property
    def name(self) -> str
    def ensure(self, state=PackageState, version=) -> raises PackageError
    def hold(self, version=)
    @property
    def present(self) -> bool
    @property
    def epoch(self) -> str
    @property
    def from_repository(self) -> Repository

class AptPackage(Package)
    @property
    def full_version(self) -> str
    @property
    def upstream_version(self) -> str
    @property
    def debian_revision(self) -> str

class RPMPackage(Package):
    @property
    def name(self) -> str
    @property
    def version(self) -> str
    @property
    def release(self) -> str
    @property
    def nvr(self) -> str

class Snaps:
    def __init__(self, model, backend) -> None:
    @property
    def installed(self, model) -> SnapMapping:

class SnapMapping(Mapping):
    def __init__(self, backend, cache) -> None:
    def __contains__(self, key) -> bool:
    def __len__(self) -> int:
    def __iter__(self) -> Iterable[Snap]:
    def __getitem__(self, key) -> Snap:

class Snap:
    def __init__(self, name, channel=None) -> None:
    def _add(self) -> None:
    def _remove(self) -> None:
    def ensure(self,state=PackageState,channel=, version=)
    @property
    def present(self) -> bool

class Repositories:
    def __init__(self, model, backend) -> None:
    @property
    def all(self) -> RepositoryMapping
    @property
    def enabled(self) -> RepositoryMapping
    @property
    def disabled(self) -> RepositoryMapping

class RepositoryMapping(Mapping):
    def __init__(self, backend, cache) -> None:
    def __contains__(self, key) -> bool
    def __len__(self) -> int
    def __iter__(self) -> Iterable[Repository]
    def __getitem__(self, key) -> Repository

class Repository:
    def __init__(self, name) -> None
    def ensure(self, state=RepositoryState, enabled=True)
    def pin(self, version=)
    @property
    def present(self) -> bool
    @property
    def enabled(self) -> bool

class DebianRepository(Repository):
    def __init__(self, name, baseurl="", release="", gpgkey="") -> None:
    def dearmor(self, gpg_key=None) -> None
    @property
    def armored(self) -> bool

class RPMRepository(Repository):
    def __init__(self, name, baseurl="", gpgkey="", gpgcheck=) -> None
    def enable_sources(self, bool) -> None
    def enable_debuginfo(self, bool) -> None

## Further Discussion

In investigations, PackageKit requires too much plumbing to add to sidecar charms, but if the Operator Framework is executing in the context of a machine charm, monitoring is possible. Whether PackageKit is suitable for a partial workflow, or whether watching system logs to detect package changes is a better solution will be evaluated.
