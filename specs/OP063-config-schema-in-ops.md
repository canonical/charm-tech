# OP063 — Config schema in Ops

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Implementation |
| Created | Mar 24, 2025 |

Loading implemented in [https://github.com/canonical/operator/pull/1741](https://github.com/canonical/operator/pull/1741) (with some small changes), with schema generation available in a branch with draft implementation: [https://github.com/tonyandrewmeyer/operator/tree/config-schema](https://github.com/tonyandrewmeyer/operator/tree/config-schema)

## Abstract

Juju provides type validation of charm configuration options (for five possible types). However, charms may need to add additional validation (for example, "positive integer" or "integer except these values" rather than "integer"), and although `config-get` provides typed data the types are not available to Python tooling (leading to proliferation of `typing.cast(str, x)` type code). A new ConfigBase class will be added to Ops that avoids schema duplication by acting as the source of truth, while allowing any validation that can be done in Python code, and providing strong type annotations.

## Rationale

The charm configuration schema is specified in charmcraft.yaml, where it is strongly typed, for example:

```
options:
  hostname:
    type: string
    description: Hostname to serve on.
  port:
    type: int
    default: 8000
```

This data is retrieved using the config-get hook tool, and arrives as typed JSON, for example:

```
{
    'hostname': 'example.com',
    'port': 8080
}
```

However, since the schema is in YAML and not Python, Python tooling is unable to determine that (using the example above) 'port' is an integer, so every config value is typed as `bool | int | float | str`. This means that charm code needs to copy the type information from the schema (through typing.cast or asserts) for static type-checking tools to work correctly, and for hints to appear in an IDE.

Values for configuration are validated by Juju when config is passed (for example, with `juju config` or when deploying). However, the only validation is that the value is of the appropriate type (and, for secrets, that the secret exists). If charms need to add additional validation, this must be done in the charm code.

Many charms have adopted a pattern where the configuration schema is defined in Python (typically using a dataclass or Pydantic BaseModel subclass). For [example](https://github.com/canonical/haproxy-operator/blob/main/src/state/ha.py):

```py
@pydantic.dataclasses.dataclass(frozen=True)
class HAInformation:
    """A component of charm state containing information about TLS.

    Attributes:ready
        ha_integration_ready: Whether the ha relation is ready.
        vip: The configured virtual IP address.
        haproxy_peer_integration_ready: Whether the haproxy peer integration is ready.
        configured_vip: Previously configured Virtual IP address. None if no vip was configured.
    """

    ha_integration_ready: bool
    vip: typing.Optional[IPvAnyAddress]
    haproxy_peer_integration_ready: bool
    configured_vip: typing.Optional[IPvAnyAddress]

    @model_validator(mode="after")
    def validate_vip_not_none_when_ha_integration_active(self) -> Self:
        """Validate that vip is configured when ha integration is active.

        Raises:
            ValueError: When ha integration is active but vip is not configured.

        Returns:
            Self: Validated model.
        """

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "HAInformation":
        """Get ha information from a charm instance.

        Args:
            charm: The haproxy charm.

        Raises:
            HAInformationValidationError: When validation of the state component failed.

        Returns:
            HAInformation: Information needed to configure ha.
        """
```

The main disadvantages here are that the schema is now specified in two locations that must be kept in sync - charmcraft.yaml and the Python code - and that this pattern is not entirely standardised so is reimplemented in slightly different ways across charms.

There is a long-term intention to adopt Starlark (specifically [the Canonical version](https://github.com/canonical/starlark)) as a mechanism for extending the validation done when providing configuration values (prior to the values being accepted, so well prior to any charm activation) with arbitrary validation code provided by individual charms. Implementing Starlark checks in Juju is outside the scope of this spec, but this goal is taken into account in the design.

Summary of goals:

* Stronger static type checking for config
* Improved autocompletion, help popovers, and so forth in IDEs when working with config
* Avoid duplication of schemas and schema validation
* Move schema validation as early as possible
* More complex validation than Juju provides

## Specification

To have a single source of truth, the configuration schema must be defined once, and that definition used to produce alternative versions. The schema must be located where it can be most expressive - of the charmcraft.yaml, (potential) Starlark, and Python versions, the Python version is (by far) the most expressive.

The intention is to, as far as possible, allow charms to continue using the Python config schema classes that they already have, with minimal changes. In particular, standard library dataclasses, Pydantic dataclasses, and Pydantic BaseModel subclasses are all supported, but other classes should work with no or minimal changes. Essentially, we are adopting the existing charming practice with as few changes as possible, but providing schema-deduplication and error handling within ops.

### New class: ops.ConfigBase

Using a Python class already solves two of the goals: clearer static type checking, and providing improved assistance (such as autocomplete) in IDEs. To complement these, a new class will be added to Ops that provides a mechanism for converting the schema to YAML suitable for config.yaml. In the future, conversion to Starlark can also be added.

The structure of the new class is:

```py
class ConfigBase:
    """Base class for strongly typed charm config.

    Use :class:`ConfigBase` as a base class for your config class, and define
    the attributes as you would in ``charmcraft.yaml``. For example::

        @dataclasses.dataclass(frozen=True)
        class MyConfig(ops.ConfigBase):
            my_float: float
            '''A floating point value.'''
            my_bool: bool = False
            '''A boolean value.'''
            my_int: int = 42
            '''An integer value.'''
            my_str: str = "foo"
            '''A string value.'''
            my_secret: ops.Secret | None = None
            '''A user secret.'''

    Note: this is a dataclass, but can be any object that inherits from
    ``ops.ConfigBase``, and can be initialised with the raw Juju config
    passed as keyword arguments. Any errors should be indicated by raising
    ``ValueError`` (or a ``ValueError`` subclass) in initialisation.

    Inheriting from ``ops.ConfigBase`` is not strictly necessary, but it
    provides utility methods for translating the class to a YAML schema suitable
    for use with Juju.

    Use this in your charm class like so::

        class MyCharm(ops.CharmBase):
            def __init__(self, framework):
                super().__init__(framework)
                self.typed_config = self.load_config(MyConfig)
    """

    @classmethod
    def to_juju_schema(cls) -> dict[str, Any]:
        """Translate the class to YAML suitable for config.yaml.

        Using :attr:`ConfigBase.to_juju_schema` will generate a YAML schema
        suitable for use in ``config.yaml``. For example, with the class from
        the example above::

            print(yaml.safe_dump(MyConfig.to_juju_schema()))

        Will output::

            options:
                my-float:
                    type: float
                    description: A floating point value.
                my-bool:
                    type: boolean
                    default: False
                    description: A boolean value.
                my-int:
                    type: int
                    default: 42
                    description: An integer value.
                my-str:
                    type: string
                    default: foo
                    description: A string value.
                my-secret:
                    type: secret
                    description: A user secret.
        """
```

When generating the schema as Juju YAML, Ops will select an appropriate set of attributes from the class to include (for example, with a dataclass, this would be `dataclasses.fields()`, and with a Pydantic BaseModel, this would be `model_fields`). Charmers can customise which attributes are included by overriding the `to_juju_schema()` method in the config class.

### Future work

Charmcraft's pack command currently creates an appropriate config.yaml file by extracting the configuration schema from the charmcraft.yaml file, with extensions able to further modify config. The functionality in this spec provides a charmer the ability to generate the appropriate YAML to insert into charmcraft.yaml, for example:

```shell
uvx --with=pyyaml --with=ops python -c 'import yaml;from charm import Config;print(yaml.dump(Config.to_juju_schema()))'
```

In the future, this may be extended so that Ops provides a method to keep charmcraft.yaml in sync with the Python class, and/or verify that the two formats of the schema match. A charmcraft extension could also be developed that extended the config (as the existing extensions do) to include the generated schema from the charm via Ops.

### New CharmBase.load_config method

To provide a consistent mechanism for instantiating the config classes, and, in particular, for handling errors, the `CharmBase` class will gain a new method, `load_config`:

```py
def load_config(
    self,
    cls: type[ops.ConfigBase],
    errors: Literal['raise', 'blocked'] = 'raise',
    *args: Any,
    **kwargs: Any,
) -> _ConfigType:
    """Load the config into an instance of a config class.

    The object will be instantiated with keyword arguments of the raw Juju config
    for all the options that are found in the class, but with:

    * ``secret`` type options having a :class:`model.Secret` value rather
        than the secret ID.
    * dashes in names converted to underscores.

    Any additional positional or keyword arguments will be passed through to
    the config class.

    Args:
        cls: A class that inherits from :class:`ops.ConfigBase`.
        errors: defines the behaviour if the configuration is invalid. When set to
            'raise', the original exception will not be caught by this method;
            when set to 'blocked', the hook will exit with a zero exit code,
            after setting an appropriate blocked status.
        args: positional arguments to pass through to the config class.
        kwargs: keyword arguments to pass through to the config class.

    Returns:
        An instance of the config class with the current config values.

    Raises:
        ValueError: when 'errors' is 'raise', and the configuration is valid.
            Note that this will be the original exception raised by the schema
            validation, so may be a ``ValueError`` subclass.
    """
```

If there are errors instantiating the class (including the class raising `ValueError` or any `ValueError` subclasses), the charm has two options.

For charms that can exit when loading the configuration fails, and only need to inform the charm of the error, `load_config` can be passed `errors='blocked'`. In that case, the hook will immediately exit, with a non-zero status (note that this indicates to Juju that the hook was 'successful' and does not need to be retried), after setting the unit status to "blocked", with a message based on the original exception.

When a charm needs to handle the event even if the configuration is not valid, or wants to handle the issue in a different way, the default `errors="raise"` is used. In this case the `load_config` method doesn't handle the exception raised by the validation and lets it 'bubble up' instead. The charm can either leave the exception uncaught (to exit the hook in an error state), or catch the exception and handle it appropriately.

Note that fewer errors will occur at charm loading time once there is additional validation using Starlark, but it's likely that there will always be some validation that cannot be done within the restricted Starlark context.

In addition to error handling, `load_config` will convert any `secret` options from the secret ID to an `ops.Secret` object. This avoids every charm needing to do a `` `secret = self.model.get_secret(id=secret_id)` `` call whenever the configuration includes user secrets. This is a 'lazy' `Secret` object, like the one provided to `SecretEvent` objects, that contains the secret ID but has *not* fetched any secret data or metadata from Juju (which is done on demand).

The typical use-case ([original schema](https://github.com/canonical/openstack-exporter-operator/blob/0f027fd372e0882ba4b47c8d8d1e2cfe327a97f3/charmcraft.yaml#L36), [original validation](https://github.com/canonical/openstack-exporter-operator/blob/main/src/validate_config.py)) looks like:

```py
MAX_PORT = 65535

# Allowable duration units for cache_ttl from https://pkg.go.dev/time#ParseDuration
VALID_UNITS = {"ns", "us", "\u00b5s", "\u03bcs", "ms", "s", "m", "h"}

# Regex patterns for cache_ttl
NUMBER_PATTERN = r"(\d+\.?\d*|\d*\.\d+)"
DURATION_PATTERN = (
    rf"^\+?{NUMBER_PATTERN}[a-zµ\u03bc\u05bc]+({NUMBER_PATTERN}[a-zµ\u03bc\u05bc]+)*$"
)

@dataclasses.dataclass(frozen=True)
class ExporterConfig(ops.ConfigBase):
    """Configuration for the OpenStack Exporter charm."""
    port: int = 9180
    """The service will listen at this port."""
    ssl_ca: str = ""
    """Custom TLS CA for keystone if required."""
    cache_ttl: str = "300s"
    """Cache expiry TTL, e.g. 10s, 11m, 12h."""
    cache: bool = True
    """Enable or disable the exporter cache globally."""
    snap_channel: str = "latest/stable"
    """The channel from which to install the charmed-openstack-exporter snap."""

    def __post_init__(self):
        self.validate_port()
        self.validate_cache_ttl()

    def validate_port(self):
        if self.port <= 0 or self.port > MAX_PORT:
            raise ValuError(f"port must be between 1 and {MAX_PORT}, got {self.port}")

    def validate_cache_ttl():
        if not self.cache_ttl:
            raise ValueError(f"cache_ttl must be non-empty. Got {self.cache_ttl}")

        if self.cache_ttl[0] == "-":
            raise ValueError(f"cache_ttl must be non-negative. Got {self.cache_ttl}")

        if not re.fullmatch(DURATION_PATTERN, self.cache_ttl):
            raise ValueError(
                "cache_ttl is not in a valid format. It must be a valid format for "
                "https://pkg.go.dev/time#ParseDuration; for example '20m' or '2h30m'"
            )

        # Get each number-unit pair
        matches = re.findall(
            r"(\d+\.?\d*|\d*\.\d+)([a-zµ\u03bc\u05bc]+)",
            self.cache_ttl,
        )

        if not any((float(number) < 0) for number, _ in matches):
            raise ValueError(f"cache_ttl must be non-zero. Got {self.cache_ttl}")

        # Validate units
        for _, unit in matches:
            if unit not in VALID_UNITS:
                raise ValueError(
                    f"cache_ttl has invalid time unit: {unit}. "
                    f"Valid units are 'ns', 'us' (or 'µs'), 'ms', 's', 'm', 'h'."
                )

class Charm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        ...
        self.typed_config = self.load_config(ExporterConfig)
```

A Pydantic version of this could look like:

```py
MAX_PORT = 65535
# Regex patterns for cache_ttl
DURATION_PATTERN = r"^(?:\d+(\.\d+)?[a-zµ\u03bc\u05bc]+)+$"
# Allowable duration units for cache_ttl from https://pkg.go.dev/time#ParseDuration
VALID_UNITS = {'ns', 'us', 'µs', 'ms', 's', 'm', 'h'}

class ExporterConfig(pydantic.BaseModel, ops.ConfigBase):
    """Configuration for the OpenStack Exporter charm."""
    port: int = pydantic.Field(9180, ge=1, le=MAX_PORT)
    """The service will listen at this port."""
    ssl_ca: str = ""
    """Custom TLS CA for keystone if required."""
    cache_ttl: str = "300s"
    """Cache expiry TTL, e.g. 10s, 11m, 12h."""
    cache: bool = True
    """Enable or disable the exporter cache globally."""
    snap_channel: str = "latest/stable"
    """The channel from which to install the charmed-openstack-exporter snap."""

    @pydantic.validator('cache_ttl')
    def validate_cache_ttl(cls, v):
        if not v:
            raise ValueError(f"cache_ttl must be non-empty. Got {v}")
        if v[0] == "-":
            raise ValueError(f"cache_ttl must be non-negative. Got {v}")

        if not re.fullmatch(DURATION_PATTERN, v):
            raise ValueError(
                "cache_ttl is not in a valid format. It must be a valid format for "
                "https://pkg.go.dev/time#ParseDuration; for example '20m' or '2h30m'"
            )

        # Get each number-unit pair
        matches = re.findall(r"(\d+\.?\d*|\d*\.\d+)([a-zµ\u03bc\u05bc]+)", v)
        if not any(float(number) < 0 for number, _ in matches):
            raise ValueError(f"cache_ttl must be non-zero. Got {v}")

        # Validate units
        for _, unit in matches:
            if unit not in VALID_UNITS:
                raise ValueError(
                    f"cache_ttl has invalid time unit: {unit}. "
                    f"Valid units are 'ns', 'us' (or 'µs'), 'ms', 's', 'm', 'h'."
                )
        return v

    class Config:
        allow_mutation = False
```

A more complicated example class ([original](https://github.com/canonical/haproxy-operator/blob/main/src/state/ha.py)) and usage that mixes attributes from config and ones that are determined in the Python code:

```py
HACLUSTER_INTEGRATION = "ha"
HAPROXY_PEER_INTEGRATION = "haproxy-peers"

# This class brings in one value from the config, "vip", which in the Juju
# config.yaml is typed as a string. It also uses the charm's relations to set other
# configuration values.

@dataclass.dataclass(frozen=True)
class HAInformation(ops.ConfigBase):
    """A component of charm state containing information about TLS."""

    ha_integration_ready: bool = False
    """Whether the ha relation is ready."""
    vip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    """The configured virtual IP address."""
    haproxy_peer_integration_ready: bool = False
    """Whether the haproxy peer integration is ready."""
    configured_vip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    """Previously configured virtual IP address. None if no vip was configured."""

    def __init__(self, charm, vip: str):
        ha_integration = charm.model.get_relation(HACLUSTER_INTEGRATION)
        self.ha_integration_ready = bool(ha_integration and ha_integration.units)

        self.vip = ipaddress.ip_address(vip) if vip else None

        haproxy_peer_integration = charm.model.get_relation(HAPROXY_PEER_INTEGRATION)
        self.haproxy_peer_integration_ready = bool(haproxy_peer_integration),

        self.configured_vip = (
            haproxy_peer_integration.data[charm.unit].get("vip")
            if haproxy_peer_integration
            else None
        )

        if self.ha_integration_ready and not self.vip:
            raise ValueError("vip needs to be configured in ha mode.")

    @classmethod
    def to_juju_schema(cls) -> dict[str, str]:
        schema = super().to_juju_schema(cls)
        # Convert the ipaddress.IPv{4,6}Address to a string.
        schema["options"]["vip"]["type"] = "str"
        # Three of the fields aren't in the config, they're constructed afterwards.
        del schema["options"]["ha_integration_ready"]
        del schema["options"]["haproxy_peer_relation_ready"]
        del schema["options"]["configured_vip"]
        return schema

class Charm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        ...
        self.typed_config = self.load_config(HAInformation, charm=self)
```

A Pydantic version of this could look like:

```py
HACLUSTER_INTEGRATION = "ha"
HAPROXY_PEER_INTEGRATION = "haproxy-peers"

class HAInformation(pydantic.BaseModel, ops.ConfigBase):
    ha_integration_ready: bool
    vip: pydantic.IPvAnyAddress | None
    haproxy_peer_integration_ready: bool
    configured_vip: pydantic.IPvAnyAddress | None

    def __init__(self, charm, vip: str):
        ha_integration = charm.model.get_relation(HACLUSTER_INTEGRATION)
        self.ha_integration_ready = bool(ha_integration and ha_integration.units)

        haproxy_peer_integration = charm.model.get_relation(HAPROXY_PEER_INTEGRATION)
        self.haproxy_peer_integration_ready = bool(haproxy_peer_integration),

        self.configured_vip = (
            haproxy_peer_integration.data[charm.unit].get("vip")
            if haproxy_peer_integration
            else None
        )

        super().__init__(
            ha_integration_ready=bool(ha_integration and ha_integration.units),
            vip=vip if vip else None,  # type: ignore
            haproxy_peer_integration_ready=bool(haproxy_peer_integration),
            configured_vip=configured_vip,  # type: ignore
        )

    @pydantic.model_validator(mode="after")
    def validate_vip_not_none_when_ha_integration_active(self) -> Self:
        if self.ha_integration_ready and not self.vip:
            raise ValueError("vip needs to be configured in ha mode.")
        return self

    @classmethod
    def to_juju_schema(cls) -> dict[str, str]:
        schema = super().to_juju_schema(cls)
        schema["options"]["vip"]["type"] = "str"
        del schema["options"]["ha_integration_ready"]
        del schema["options"]["haproxy_peer_relation_ready"]
        del schema["options"]["configured_vip"]
        return schema

class Charm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        ...
        self.typed_config = self.load_config(HAInformation, charm=self)
```

### Future considerations: Starlark

There is a long-term plan ("scriptlets") that Starlark will be used to provide validation functionality (presumably for all of config, action params, and relation data) in Juju. Charms will provide Starlark code that Juju would execute in the Starlark sandbox, and from the charm's point of view the data would be valid in nearly all situations (or when setting, would be rejected if invalid). Given the restrictions of the Starlark sandbox, it's likely that there will always be edge cases that must be tested in the live charm code, but those should be rare exceptions.

Starlark does not provide a solution for static checking, and does not provide a solution for IDE / language server integration, so by itself is not sufficient to meet our goals. Since Starlark doesn't support type annotations (or exceptions, or classes) sharing the same code for charm code and Starlark would require significant changes (probably considered detrimental, given the decreased expressiveness) to how charms are currently defining schema.

However, the `ConfigBase` class does provide a natural place for charms to define their Starlark code, which could then be delivered during 'charmcraft pack' to the appropriate destination.

## Further Information

See also the related specs:

* [Action parameter schema in Ops](https://docs.google.com/document/d/1AiNvr1xfh078ieRczCCc9HSx4VW-dDJdF2p9FS2E_do/edit?usp=sharing)
* [Interface schema in Ops](https://docs.google.com/document/d/1G0xfWJXomzzH2VIY1trFq4b5ybMEEjV0w_aReLWyjCs/edit?usp=sharing) (this spec in particular has more information about schema validation specs and implementations that have been attempted in the past)
