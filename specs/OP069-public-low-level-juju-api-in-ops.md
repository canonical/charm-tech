# OP069 — Public low-level Juju API in ops

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Jun 30, 2025 |

## Abstract

To make it easier to experiment with alternate styles of charming, and to simplify charm code that requires access to ops framework objects but is outside of event handlers, the ops interface to Juju (hook commands and environment variables) will be exposed as a type-annotated, Pythonic, 1:1 public API.

## Rationale

Ops provides charmers with an interface to Juju (wrappers around the Juju hook commands, environment variables set by Juju, and a Pebble client) and an ostensibly observer-pattern framework (which models not only Juju events, but Ops 'lifecycle' events, charm library 'custom' events, and a [problematic](https://documentation.ubuntu.com/ops/latest/explanation/defer-guidance/) event deferral mechanism). Many charmers struggle to learn the Ops framework approach while learning Juju because of the disconnect between the two, and many charmers would prefer to implement charms in Python but without using the Ops framework. This spec proposes more clearly separating in Ops the communication with Juju and the framework, so that charmers are able to build tools that use the Juju interface without needing to use the framework.

Exposing a 1:1, type-annotated, Pythonic, wrapper of the Juju hook commands also aligns with the approach we have used with [Jubilant](https://canonical-jubilant.readthedocs-hosted.com/), which - although new - shows early signs of success. Juju users, including charmers, are familiar with the Juju CLI and want their tests to behave in the same way as running CLI tools. In the same way, experienced charmers are familiar with the Juju hook commands and expect their charm code to behave in the same way as calling the hook commands (without additional functionality like caching, as Ops currently does for relation data, or alternative APIs, as Ops currently does for secret data).

We want to provide one obvious, best, way to build charms, and that remains Ops. However, we also want to support experimentation in the ecosystem (for example, [goops](https://github.com/gruyaume/goops), [rusty-charm-framework](https://github.com/samuelallan72/rusty-charm-framework), [charm-api](https://github.com/canonical/charm-api), [jinx](https://github.com/PietroPasotti/jinx)). Feedback from charmers who are exploring this space is that experimentation would be simpler if tooling could build on top of a Charm Tech maintained API for the Juju hook commands and environment.

## Specification

### Hook commands

To provide access to the Juju hook commands, the functionality in the existing `_ModelBackend` class will be made public, in a new `ops.hookcmds` module (accessed in a namespace of the same name, not in the top-level ops namespace). `ops.hookcmds` will:

* be automatically traced, just as `_ModelBackend` is;
* not include support (including raising specific errors) for any versions of Juju below 2.9;
* not include support for `add-metric`, `leader-get`, `leader-set`, `payload-register`, `payload-status-set`, `payload-unregister`, or `pod-spec-set` (as these are both not recommended for use, and have none-to-minimal use in Ops charms - where there is existing support in `_ModelBackend`, the `_ModelBackend` class will continue to support it);
* not do run-time type checking (`_ModelBackend` will continue to layer this on top), and in general will rely on static type checking and Juju for validation;
* not cache or buffer any input or output to/from the hook commands;
* prefer returning simple built-in Python objects (specifically: `bool`, `int`, `str`, `list`, and `dict`); where the structure of a dictionary is constant, a dataclass will be returned (for example, the result of `status-get`, but not the result of `relation-get`); and
* be stateless, so that any code can safely use the module, including in multiple threads (for example, multi-threaded test code).

As part of the work in this spec, the `_ModelBackend` class will be changed to a small wrapper on top of `ops.hookcmds`. In the future, some `_ModelBackend` usage within ops, such as in `Relation` and `Secret`, might change to directly use `ops.hookcmds` instead (to avoid needing access to the framework or model to create objects of those types), but to keep the initial implementation at a reasonable size, no `_ModelBackend` usage within ops will change at this time.

The public API of `ops.hookcmds` will be:

```py
# All of the names listed here are available in the ops.hookcmds namespace, and are
# *not* available in the top-level ops namespace.
#
# Example usage (although expected usage is actually in a higher-level wrapper):
#
# from ops import hookcmds
# if hookcmds.is_leader():
#     hookcmds.status_set('active', app=True)

class HookCommandError(Exception):
    """Raised when a hook command exits with a non-zero code."""

    returncode: int
    """Exit status of the child process."""

    cmd: list[str]
    """The full command that was run."""

    stdout: str = ''
    """Stdout output of the child process."""

    stderr: str = ''
    """Stderr output of the child process."""

@dataclasses.dataclass(frozen=True, kw_only=True)
class CloudSpec:
    ...

@dataclasses.dataclass(frozen=True, kw_only=True)
class GoalState:
    units: dict[str, Goal]
    # The top key is the endpoint/relation name, the second key is the app/unit name.
    relations: dict[str, dict[str, Goal]]

@dataclasses.dataclass(frozen=True, kw_only=True)
class Goal:
    status: str
    since: datetime.datetime

@dataclasses.dataclass(frozen=True, kw_only=True)
class Network:
    bind_addresses: BindAddress
    egress_subnets: Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]
    ingress_addresses: Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]

@dataclasses.dataclass(frozen=True, kw_only=True)
class Port:
    protocol: Literal['tcp', 'udp', 'icmp']
    port: int | None
    to_port: int | None

@dataclasses.dataclass(frozen=True, kw_only=True)
class RelationModel:
    uuid: uuid.UUID

@dataclasses.dataclass(frozen=True, kw_only=True)
class SecretInfo:
    type: str
    name: str
    ...

@dataclasses.dataclass(frozen=True, kw_only=True)
class UnitStatus:
    name: StatusName
    message: str = ""
    status_data: dict[str, str | int]

# TODO: Verify that this is the correct structure.
@dataclasses.dataclass(frozen=True, kw_only=True)
class AppStatus:
    name: StatusName
    message: str = ""
    status_data: dict[str, str | int]
    units: dict[str: UnitStatus]

@dataclasses.dataclass(frozen=True, kw_only=True)
class Storage:
    kind: str
    location: pathlib.Path

# All methods are 1:1 mapping to Juju hook commands. This is a *low-level* API,
# available for charm use, but expected to be used via higher-level wrappers.

def relation_ids(name: str) -> list[int]: ...

# Note that an `id` of None will only work in a relation event, where Juju will
# provide the ID of the relation that triggered the event. In other cases, an
# error will be raised to the caller.
def relation_list(id: int | None = None, *, app: bool = False) -> list[str]: ...

# Note that an `id` of None will only work in a relation event, where Juju will
# provide the ID of the relation that triggered the event. In other cases, an
# error will be raised to the caller.
@overload
def relation_get(
    id: int | None = None, *, unit: str | None = None, app: bool = False,
) -> dict[str, str]: ...
@overload
def relation_get(
    id: int | None = None,
    *,
    key: str,
    unit: str | None = None,
    app: bool = False,
) -> str: ...
def relation_get(
    id: int | None = None,
    *,
    key: str | None = None,
    unit: str | None = None,
    app: bool = False,
) -> dict[str, str] | str: ...

def relation_set(
    id: int,
    data: Mapping[str, str],
    *,
    app: bool = False,
    file: pathlib.Path | None,
) -> None: ...

# Note that an `id` of None will only work in a relation event, where Juju will
# provide the ID of the relation that triggered the event. In other cases, an
# error will be raised to the caller.
def relation_model_get(id: int | None = None) -> RelationModel: ...

# Note that 'secret' type options are returned as strings.
@overload
def config_get(key: str, all: Literal[False]) -> bool | int | float | str: ...
@overload
def config_get(all: bool = False) -> Mapping[str, bool | int | float | str]: ...
def config_get(
    key: str | None, all: bool = False,
) -> Mapping[str, bool | int | float | str] | str: ...

# Note that this does not do any caching (_ModelBackend will still do that).
def is_leader() -> bool: ...

def resource_get(name: str) -> pathlib.Path: ...

# TODO: In docs, make it clear this is the workload status not the agent status,
# (`juju status` will show the agent status) and they may differ.
@overload
def status_get(*, include_data: Literal[True], app: bool = False) -> Status: ...
@overload
def status_get(*, app: bool = False) -> str: ...
def status_get(*, include_data: bool = False, app: bool = False) -> Status | str: ...

# SettableStatusName would be moved from ops.model._SettableStatusName, and ops.model
# could use ops.hookcmds.SettableStatusName (which is also a doc improvement).
def status_set(
    status: ops.SettableStatusName, message: str = '', *, app: bool = False
) -> None: ...

def storage_list(name: str) -> list[int]: ...

# Note that an `identifier` of None will only work in a storage event, where Juju will
# provide the ID of the storage that triggered the event. In other cases, an error will
# be raised to the caller.
@overload
def storage_get(identifier: str | None = None, *, attribute: str) -> str: ...
@overload
def storage_get(identifier: str | None = None) -> Storage: ...
def storage_get(
    identifier: str | None = None, attribute: str | None = None
) -> Storage | str: ...

def storage_add(name: str, count: int = 1) -> None: ...

def application_version_set(version: str) -> None: ...

# This does not split lines (_ModelBackend.juju_log will continue to do so).
def juju_log(message: str, level: str = 'INFO') -> None: ...

# We could have bind_address: bool=True, egress_subnets: bool=True,
# --ingress-address: bool=True, and could even return just that data if only one
# is specified. However, it seems like it's unlikely there would be a lot of data
# here, and that it's unlikely to be much faster to only get one, so the API is
# a lot simpler if we only support getting all at once (which is the behaviour
# when none of those arguments are specified).
def network_get(binding_name: str, relation_id: int | None = None) -> Network: ...

def goal_state() -> GoalState: ...

@overload
def state_get(key: str) -> str: ...
@overload
def state_get() -> State: ...
def state_get(key: str | None) -> State | str: ...

def state_set(data: Mapping[str, str]) -> None: ...

@overload
def secret_get(
    *,
    id: str,
    refresh: bool = False,
    peek: bool = False,
) -> dict[str, str]: ...
@overload
def secret_get(
    *,
    label: str,
    refresh: bool = False,
    peek: bool = False,
) -> dict[str, str]: ...
def secret_get(
    *,
    id: str | None = None,
    label: str | None = None,
    refresh: bool = False,
    peek: bool = False,
) -> dict[str, str]: ...

def secret_ids() -> list[str]: ...

@overload
def secret_info_get(
    *, id: str,
) -> SecretInfo: ...
@overload
def secret_info_get(
    *, label: str,
) -> SecretInfo: ...
def secret_info_get(
    *, id: str | None = None, label: str | None = None
) -> SecretInfo: ...

# This will always use the --file argument to provide the content.
def secret_set(
    id: str,
    *,
    content: dict[str, str] | None = None,
    label: str | None = None,
    description: str | None = None,
    expire: datetime.datetime | None = None,
    rotate: SecretRotate | None = None,
) -> None: ...

def secret_add(
    content: dict[str, str],
    *,
    label: str | None = None,
    description: str | None = None,
    expire: datetime.datetime | None = None,
    rotate: SecretRotate | None = None,
    owner: str | None = None,
) -> str: ...

def secret_grant(id: str, relation_id: int, *, unit: str | None = None) -> None: ...

def secret_revoke(
    id: str, *, relation_id: int | None, app: str | None, unit: str | None = None,
) -> None: ...

def secret_remove(id: str, *, revision: int | None = None) -> None: ...

# port can be a single port, or a range of ports, or (for ICMP) None
def open_port(
    protocol: str,
    port: int | None = None,
    *
    to_port: int | None,
    endpoints: str | list[str],
) -> None: ...
def close_port(
    protocol: str,
    port: int | None = None,
    *
    to_port: int | None,
    endpoints: str | list[str],
) -> None: ...

def opened_ports(endpoints: bool = False) -> list[Port]: ...

def credential_get() -> CloudSpec: ...

@overload
def action_get() -> dict[str, Any]: ...
@overload
def action_get(key: str) -> str: ...
def action_get(key: str | None = None) -> dict[str, Any] | str: ...

# This does the same flattening as _ModelBackend.action_set.
def action_set(results: Mapping[str, Any]) -> None: ...

def action_log(message: str) -> None: ...

def action_fail(message: str | None = None) -> None: ...

def reboot(now: bool = False) -> None:
```

In the initial implementation, Scenario and Harness will not mock any `ops.hookcmds` methods, but they both continue to use a mocked model backed (that does not actually call any hook commands). Charms are not expected to use the low-level API directly, and code that builds on top of this API is expected to provide appropriate testing solutions. In charms or charm libraries that do use the commands directly, they can explicitly mock (with unittest or pytest's monkeypatch) the commands in the tests. We do expect to add a solution for automatically mocking the low-level functions (in Scenario, but likely not Harness) in the future, but will not do that immediately to lower the time required for implementation, and to learn more about how these functions are used in practice before developing the testing story.

### Juju environment variables

To provide access to the low-level Juju context provided by environment variables, the existing `_JujuContext` class will be renamed to `JujuContext` and added to the top-level `ops` namespace. Charms can populate an `ops.JujuContext` object with `context = ops.JujuContext.from_environ()`. Scenario updates `os.environ` during event emission, so charms that read the context from there in tests will continue to work as expected.

Minimal changes will be made to the `_JujuContext` API:

`kw_only` will be added to the dataclass. If this feature had been available in Python 3.8, we would likely have used it originally. With the class becoming public, we should take the opportunity to add it, as there is no obvious positional order for the arguments.

The JUJU_MACHINE_ID, JUJU_PRINCIPAL_UNIT, JUJU_HOOK_NAME, and JUJU_AVAILABILITY_ZONE environment variables will be exposed in appropriate attributes. These are not needed by the Ops framework, but are set in every hook, and have use-cases for charming.

The class currently includes a set of default values to create objects with `_JujuContext()`, and also defines default values for all fields when creating objects with `_JujuContext.from_dict()`. [Many of the fields are documented to be set in every hook execution](https://documentation.ubuntu.com/juju/3.6/reference/hook/#hook-execution), but [this is not entirely correct](https://github.com/canonical/operator/issues/1836), and the dict in `from_dict()` might not be `os.environ` in a hook process (it might be a hand-crafted dict in a test, for example).

Some of the fields can have reasonable default values (`charm_dir`, `debug`, `debug_at`), and some of the fields are specific to one or more events so can reasonably default to None. However, there are several that have no sensible default (such as `model_name`, `unit_name`, `version`).

The from_dict method will not change, but the dataclass fields defaults will be adjusted (which changes the __init__ correspondingly), and a new from_environ will be added:

```py
# Docstrings omitted for brevity.
@dataclasses.dataclass(frozen=True, kw_only=True)
class JujuContext:
    # Required:
    dispatch_path: str
    model_name: str
    model_uuid: str
    unit_name: str
    version: JujuVersion

    # Reasonable defaults:
    charm_dir: Path = dataclasses.field(
        default_factory=lambda: pathlib.Path(f'{__file__}/../../..').resolve()
    )
    debug: bool = False
    debug_at: set[str] = dataclasses.field(default_factory=set[str])

    # Event-specific context:
    action_name: str | None = None
    action_uuid: str | None = None
    notice_id: str | None = None
    notice_key: str | None = None
    notice_type: str | None = None
    pebble_check_name: str | None = None
    relation_departing_unit_name: str | None = None
    relation_name: str | None = None
    relation_id: int | None = None
    remote_app_name: str | None = None
    remote_unit_name: str | None = None
    secret_id: str | None = None
    secret_label: str | None = None
    secret_revision: int | None = None
    storage_name: str | None = None
    workload_name: str | None = None

    # This resembles JujuContext.from_dict(os.environ), but validates the presence of the
    # documented Juju environment variables. That means it will raise if an environment
    # variable that is documented to be set in all hooks is missing, or if an environment
    # variable expected for an event is missing when the dispatch path indicates that
    # event.
    @classmethod
    def from_environ(cls, environ: dict[str, str] | None = None) -> JujuContext: ...
        # If environ is None, os.environ will be used.
```

A new event property will be added.

```py
@property
def event(self) -> str:
    """Return the name of the current Juju event.

    The event name can be used to determine which `JujuContext` attributes can be
    expected to have values.

    Events without any supporting attributes:
      * `install`
      * `start`
      * `stop`
      * `remove`
      * `config-changed`
      * `update-status`
      * `upgrade-charm`
      * `leader-elected`

    `secret-changed`, `secret-rotate`, `secret-remove`, and `secret-expired` events all
    have `secret_id` and `secret_label` set (if the secret does not have a label,
    `secret_label` may still be `None). In addition, both `secret-remove` and
    `secret-expired` will have `secret_revision` set.

    `relation-created`, `relation-joined`, `relation-changed`, `relation-departed`, and
    `relation-broken` all have `relation_name`, `relation_id`, and `remote_app_name` set.
    In addition, `relation-joined`, `relation-changed`, and `relation-departed` will have
    `remote_unit_name` set, and `relation-departed` will also have
    `relation_departing_unit_name` set.

    Other events with supporting attributes:
      * `action`: `action_name`, `action_uuid`
      * `pebble-custom-notice: `workload_name`, `notice_id`, `notice_key`, `notice_type`
      * `pebble-check-failed: `workload_name`, `pebble_check_name`
      * `pebble-check-recovered: `workload_name`, `pebble_check_name`
      * `pebble-ready`: `workload_name`
      * `storage-attached`: `storage_name`
      * `storage-detatching`: `storage_name`

# Example usage (although expected usage is actually in a higher-level wrapper):
#
# import ops
# from ops import hookcmds
#
# context = ops.JujuContext.from_environ()
# if context.event == "secret-remove":
#     hookcmds.secret_remove(context.secret_id, context.secret_revision)
```

## Further Information

### Alternatives

A far simple alternative that would make it possible to get access to Ops objects (such as Relation, Secret, or Container) from any charm code, without passing objects around, would be a top-level get_model() method that returned the model from the framework (presumably, the framework would store the model in a global when created, and we expect that there is only ever a single framework and model).

However, while this would make it easier to get existing Ops objects, it does not provide the 1:1 mapping of the Juju API that many charmers are keen to use.

### Additional Reading

* [charm-api](https://github.com/canonical/charm-api)
* [A similar approach in k6-charm](https://github.com/sed-i/k6-k8s-operator/blob/main/src/charm.py)
