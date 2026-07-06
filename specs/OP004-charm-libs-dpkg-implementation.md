# OP004 — Charm Libs \`dpkg\` implementation

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-08-15 |

## Abstract

In order for the Operator Framework to better support the development of machine charms (and other use cases where management and observability of packages and their repositories is needed), the Operator Framework should provide abstractions and plumbing around common package management utilities available as libraries to replace the existing usage of charmhelpers

## Rationale

A charm author must be able to install, remove, replace, and pin packages which are needed to support the charmed application. Though Juju is not a configuration management system as-such, the semantics used shall follow more or less the same patterns as existing configuration management and orchestration systems (Ansible, Puppet, etc). The API is designed around keywords such as ensure so it feels familiar.

One of the difficulties faced is configuration drift. In the case of orchestration systems such as Ansible, an administrator can freely log into a system immediately after a playbook is applied and add/remove/upgrade packages to their heart's content, and Ansible will not automatically remediate this. In contrast to this, configuration management systems with agents continuously monitor drift and ensure that the system is in the "correct" state. Juju machine charms sit in a "middle ground". If we are able to effectively monitor package changes and send events, ensure can remediate at least some of the drift.

Repository management carries the additional complexity of key management for signed package repositories. For flexibility, this is not necessary with (most) non-system repositories on RPM-based systems, but the library will abstract this, raising a meaningful exception if a configured repository requires a key which is not configured or a key cannot be imported.

Since the deprecation of apt-key is current best practice, the library for dpkg management follows [upstream Debian Guidance](https://wiki.debian.org/DebianRepository/UseThirdParty) about using armored 3rd party repositories, importing new keys, de-armoring the key, and per-repository keyrings. As a default, repositories added through the library will create per-repository configuration files in /etc/apt/sources.list.d/{baseuri}-{release}.list with keyrings following the same semantics.

An additional complication is that importing Charm libraries does not pull requisite dependencies with may come from PyPi, so the standard library only is used. Since the tooling around dpkg and apt-cache do not have machine-readable formats, and apt_pkg relies on a compiler toolchain to build against the running version of dpkg (and additionally is not available in PyPi), it has not been used.

**Specification**

We propose adding a new Charm library to support this workflow, to be shipped on Charmhub and tagged with linuux in to condense system tooling and documentation under a single place

The ops.system namespace would have several new classes as follows:

class StateBase(IntEnum):
    Present = 1
    Absent = 2

class PackageStateBase(IntEnum):
    Latest = 3
    Available = 4

class Error(Exception):
    def __repr__(self) -> str:
    def name(self) -> str:
    # A convenience method with the exception name for logging caught exceptions
    def message(self) -> str:
    # The actual error message

class PackageError(Error):

class DebianPackage(object):
    def __init__(self, name: str, version: str, epoch: str, arch: str, state: PackageState):
    def __eq__(self) -> bool:
    def __hash__(self):
    def __repr__(self) -> str:
    def __str__(self) -> str:
    # A "friendly" string

    @staticmethod
    def _apt(command: str, pacakge_names: Union[str, List]) -> None:
    # A wrapper around raw apt

    def _add(self) -> None:
    def _remove(self) -> None:
    def ensure(self, state: PackageState):
    # add/remove/update a package as needed

    @property
    def name(self) -> str:

    @property
    def present(self) -> bool:
    # whether or not the package is installed

    @property
    def latest(self) -> bool:
    # whether or not the package is the latest version

    @property
    def state(self) -> PackageState:

    @state.setter
    def state(self, state: PackageState) -> None:
    # Manipulate the package state to add/remove/update
    # via enum values

    @property
    def version(self) -> Version:

    @property
    def epoch(self) -> str:

    @property
    def arch(self) -> str:

    @property
    def fullversion(self) -> str:
    # Returns a completely qualified string which can be used by apt

class Version(object):
    # A representation of the version of a Debian package
    # separated out so comparison operations are nicer
    def __init__(self, version: str, epoch: str)
    def __repr__(self)
    def __str__(self):

    @property
    def epoch(self) -> str
    @property
    def number(self) -> str

    def _compare_version(self, other: Version, op: str) -> int:
    # A wrapper around `dpkg --compare-versions` to handle
    # equality checking

    def __eq__(self, other) -> bool:
    def __lt__(self, other) -> bool:
    def __gt__(self, other) -> bool:
    def __le__(self, other) -> bool:
    def __qe__(self, other) -> bool:
    def __ne__(self, other) -> bool:

class PackageCache(Mapping):
    # A dict-like object to represent installed/available packages
    def __init__(self):
        Self._pacakge_map = {}

    def __contains__(self, key: str) -> bool:
    def __len__(self) -< int:
    def __iter__(self) -> Iterable['DebianPackage']:
    # Iterate over the known packages

    def __getitem__(self, package_name: str) -> DebianPackage:
    # return either the installed version of the specified package
    # or the most highest version number if none is installed

    def get_all(self, package_name: str) -> List['DebianPackage']:
    # returns all DebianPackages for a given package name

    def _merge_with_cache(self, packages: Dict) -> None:
    # Update the cache with a package list from apt-pkg or dpkg

    def _generate_packages_from_apt_cache(self) -> Dict:
    # Parse out "apt-cache dumpavail" into DebianPackages

    @staticmethod
    def _get_epoch_from_version(version: str) -> Tuple[str, str]:
    # Suss out the epoch, if any, from a version string

    def _generate_packages_from_dpkg(self) -> Dict:
    # Parse out `dpkg -l` to get a list of installed packages

class InvalidSourceError(Error):
class GPGKeyError(Error):

class DebianRepository(object):
    # An abstraction for a repository

    def __init__(self, enabled: bool, repotype: str, uri: str, release: str, groups: List[str], filename: str, gpg_key_filename: str)

    @property
    def enabled(self):
    @property
    def repotype(self):
    @property
    def uri(self):
    @property
    def release(self):
    @property
    def groups(self):
    @property
    def filename(self):
    @property
    def gpg_key(self):

    def import_key(self, key:str):
    # Import a GPG key into a keyring

    def _get_keyid_by_kgpg_key(key_material: bytes) -> str:
    # Helper for de-armoring

    def _get_key_by_keyid(keyid: str) -> str:
    # helper for de-armoring

    def _dearmor_gpg_key(key_esc: bytes) -> str:
    # perform the actual dearmor operation

    def _write_apt_gpg_keyfile(key_name: str, key_material: str):

Class RepositoryList(Mapping):
    # A dict-like class to parse and hold repositories
    def __init__(self):
        self.repository_map = {}
        self.default_file = "/etc/apt/sources.list"

    def __contains__(self, key: str) -> bool
    def __len__(self) -> int:
    def __iter__(self) -> Iterable[DebianRepository]:
    def __getitem__(self, repository_uri: str) -> DebianRepository
    def __setitem__(self, repository_uri: str, repository: DebianRepository) -> None:

    def load(self, file: str):
    # parse a file into the map

    @staticmethod
    def _parse(line: str, filename: str) -> DebianRepository:
    # A haleper method to parse out the lines in a sources.list file

    def add(self, repo: DebianRepository, default_filename: Optional[bool] = True):
    # A helper for adding repos which lets the filename be customized

    def disable(self, repo: DebianRepository) -> None:
    # Disable a repository by commenting out the entries in its
    # sources.list file. Do not remove it from the system

## Further Discussion

At the moment, package holding/marking/pinning is not implemented, nor are repository priorities. OpenStack determines which release to install based on the Ubuntu release, Kubernetes is Snaps. These are easy enough to add if desired, but not currently present
