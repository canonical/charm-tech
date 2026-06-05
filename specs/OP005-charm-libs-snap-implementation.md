# OP005 — Charm Libs \`snap\` implementation

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-08-15 |

## Abstract

In order for the Operator Framework to better support the development of machine charms (and other use cases where management and observability of packages and their repositories is needed), the Operator Framework should provide abstractions and plumbing around common operations with snaps. Charmed Kubernetes in particular makes heavy use of snaps, along with other applications. As a modern delivery paradigm, delivery of snaps via charms is an ideal use case, and providing an abstraction around snap will be beneficial.

## Rationale

A charm author must be able to install, remove, list, refresh, and change channels for snaps which are needed to support the charmed application. Though Juju is not a configuration management system as-such, the semantics used shall follow more or less the same patterns as existing configuration management and orchestration systems (Ansible, Puppet, etc). The API is designed around keywords such as ensure so it feels familiar.

Snap management carries the complexity of communicating with the Snap API itself to present an abstraction which is more feature-rich than calling out to subprocess, as well as potentially logging in to the snap store. Like dpkg, the output from snap is not machine-readable as such, but the local snap socket presents JSON which can be consumed by Python.

The Snap API itself does not present a way to list all available packages, which are instead stored in a file containing only a list of keys, but we can list all *installed* snaps and their information, lazily loading additional requested packages from the APi if requested.

An additional complication is that importing Charm libraries does not pull requisite dependencies with may come from PyPi, so the standard library only is used. While there are a few available libraries which can speak to HTTP over traditional UNIX sockets, calling out directly to curl through a wrapper results in zero dependencies and little added complexity for the same functionality.

**Specification**

We propose adding a new Charm library to support this workflow, to be shipped on Charmhub and tagged with linux in to condense system tooling and documentation under a single place

Reference: the [Snapd API](https://snapcraft.io/docs/snapd-api)

The ops.system namespace would have several new classes as follows:

class Error(Exception):
    def __repr__(self) -> str:
    def name(self) -> str:
    # A convenience method with the exception name for logging caught exceptions
    def message(self) -> str:
    # The actual error message

class SnapError(Error):

class StateBase(IntEnum):
    Present = 1
    Absent = 2

class PackageStateBase(IntEnum):
    Latest = 3
    Available = 4

class Snap(object):
    def __init__(self, name: str, state: SnapState, channel: str, revision: str, confinement: str)
    def __eq__(self) -> bool:
    def __hash__(self):
    def __repr__(self) -> str:
    def __str__(self) -> str:
    # A "friendly" string

    def _snap(command: str, optargs: Optional[List[str]]) -> None:
    # A wrapper around raw apt
    # optargs is used to specify the channel and confinement level

    def _install(self, channel: Optional[str] = "") -> None:
    def _refresh(self, channel: Optional[str] = "") -> None:
    def _remove(self) -> None:
    def ensure(self, state: PackageState, classic: Optional[bool] = False, channel: Optional[str] = ""):
    # add/remove/refresh a snap as needed or change the confinement level/channel

    @property
    def name(self) -> str:

    @property
    def present(self) -> bool:
    # whether or not the snap is installed

    @property
    def latest(self) -> bool:
    # whether or not the snap is the latest revision

    @property
    def state(self) -> PackageState:

    @state.setter
    def state(self, state: PackageState) -> None:
    # Manipulate the package state to add/remove/update
    # via enum values

    @property
    def revision(self) -> str:

    @property
    def channel(self) -> str:

    @property
    def confinement(self) -> str:

class SnapCache(Mapping):
    # A dict-like object to represent installed/available snaps
    def __init__(self):
        self._snap_map = {}
        self._load_available_snaps()
        self._load_installed_snaps()

    def __contains__(self, key: str) -> bool:
    def __len__(self) -< int:
    def __iter__(self) -> Iterable['Snap']:

    def __getitem__(self, snap_name: str) -> Snap:
    # if the snap is in the cache by name only after preloading from
    # a list of available snaps, hit the API to load information about it
    # to instantiate an object

    @staticmethod
    def _curl_cmd(endpoint: str) -> Dict:
    # Connect to a given endpoint of the Snap API, load the JSON, and return it
    #
    # check whether the snap daemon is running before we try

    def load_available_snaps(self) -> None:
    # Read /var/cache/snapd/names to get a list of snaps which the
    # daemon knows about. Log a warning if it has not been populated.
    #
    # For each package, assign a key to it in the dict with a value of None, so we
    # can look it up later during lazy loading if needed

    def _load_installed_snaps(self) -> None:
    # Hit the `/snaps` endpoint of the API, which returns information about
    # installed snaps, and populate the cache with objets representing them

    def _load_info(self, name) -> Snap:
    # If a snap must be lazily loaded, hit the endpoint with:
    # `?name=<name>
    # and parse the first result of the list into an object

## Further Discussion

Installation of local snap files is not yet supported. Generation of new snap packages is out of scope.
