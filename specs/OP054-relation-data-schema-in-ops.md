# OP054 — Relation Data Schema in Ops

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Nov 29, 2024 |

*Branch with draft implementation: [https://github.com/tonyandrewmeyer/operator/tree/interface-schema](https://github.com/tonyandrewmeyer/operator/tree/interface-schema)*

## Abstract

Juju relation data has an implicit string:string schema with arbitrary keys, but charms expect more specific and complex schema. The pattern that has emerged is using Python classes (particularly Pydantic classes) to define relation data schema, providing improved static type validation, IDE support, and validation. Ops currently exposes the data as a plain str:str mapping, requiring charms to implement their own support (for example, for serialising/deserialising, handling errors, and so on), and this has led to a variety of similar but not identical implementations. This spec proposes standardising the current approach and adopting explicit support for these Python classes in ops.

## Rationale

One of the core value propositions of Juju is constructing a service through integrating many charms. The primary mechanism for communication between the integrated charms is the relation data - this is also the recommended mechanism for communication between units within a charm (with a peer relation). Juju provides a basic "databag" that is a key:value mapping, where keys and values are both strings. Juju provides no functionality for validating the data, and keys and values are essentially coerced to strings (as they are provided to `relation-set` as command-line arguments). The limited validation and serialisation/deserialisation functionality provided by Juju does not match well with the importance of this data to charms.

Charms almost always need to provide additional "business logic" validation of either single key:value parts, or combinations of key:value. Charms also commonly need to store data that is not a string (from simple numbers through to complex nested custom types). Charm correctness is improved by allowing static type checking of this data, and the charming experience is improved by providing support to IDEs (language servers) of the expected keys (including documentation and type annotations).

Some validation can be done statically - for example type checking when writing to relation databags. Some validation cannot be done statically, either because it is more complex (e.g. "int but not these specific ones") or because the data only arrives at runtime.

Many charms have adopted a pattern where the relation databag schema is defined in Python (typically using a Pydantic BaseModel subclass). For example, in the [charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces) repository each interface requires a YAML schema, but the majority of interfaces define their schema in a Python module that is used to generate the YAML schema. These are then used both in the charm code and to validate interface compatibility with [pytest-interface-tester](https://github.com/canonical/pytest-interface-tester).

Summary of goals:

* Stronger static type checking for relation data
* Improved autocompletion, help popovers, and so forth in IDEs when working with relation data
* More complex validation than the minimal that Juju provides
* Ease of adoption of the new ops features for charms already using Python relation data schema classes

## Specification

This specification follows on from the ones in [OP063](https://docs.google.com/document/d/1vj2pTvVRXClCrYM7tUjft3ngISSsFdBQD1B-CzOG1Vs/edit?usp=sharing) (config) and [OP064](https://docs.google.com/document/d/1AiNvr1xfh078ieRczCCc9HSx4VW-dDJdF2p9FS2E_do/edit?usp=sharing) (action parameters), with the three specs providing a fairly unified approach. However, there are two key differences with relation data:

* There's no second version of the schema to produce, since a schema cannot be provided to Juju (there is an implicit schema of str:str with arbitrary keys).
* The data gets written as well as read - the functionality added in this spec is mostly around syncing the data back to Juju.

The intention is to, as far as possible, allow charms to continue using the Python schema classes (such as those in [charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces) and the related [pytest-interface-test](https://github.com/canonical/pytest-interface-tester)) that they already have, with minimal changes. In particular, standard library dataclasses, Pydantic dataclasses, and Pydantic BaseModel subclasses are all supported, and other classes should work with no or minimal changes. Essentially, we are adopting the existing charming practice with as few changes as possible, but providing serialisation/deserialisation and error handling within ops.

Functionality deliberately **not included** in this spec includes:

* Version specification and notification. There is not yet any established pattern for specifying interface versions, or for negotiation of which schema to use based on version, and doing so is outside the scope of this specification. Our intention is to work on this after the completion of this specification, and potentially include this functionality in improvements to ops that build on the features added in this spec.
* Similarly, changing schema based on the event (expecting a different schema in joined, then changed, and so forth) is out of scope. For now, charms are able to define multiple Relation`DataBase` classes and use the one that is appropriate based on the current charm / unit state. There are very early-stage plans that Starlark/Starform might provide this functionality in a "config as code" form.
* Defining a class that contains the entire interface (optional app and unit schema for provider and requirer). This is trivially done by combining instances of the `RelationDataBase` classes, and already has established patterns in the charm-relation-interfaces repository.
* Defining schema for secret data. See [future considerations](#future-considerations:-secrets) for intentions.
* Sourcing the schema classes. See [Further Information](#sourcing-schema) for some initial considerations.
* There is a long-term intention to adopt Starlark (specifically the [Canonical version](https://github.com/canonical/starlark)), likely via [Starform](https://github.com/canonical/starform), as a mechanism for extending the validation done when setting relation data (prior to the values being accepted) with arbitrary validation code provided by individual charms.

### New class: ops.RelationDataBase

Using a Python class already solves two of the goals: clearer static type checking, and providing improved assistance (such as autocomplete) in IDEs. To complement these, a new class will be added to Ops that provides a mechanism for serialising data to and from Juju. In the future, conversion to Starlark can also be added.

The structure of the new class is:

```py
class RelationDataBase:
    """Base class for strongly typed relation databags.

    Use :class:`RelationDataBase` as a base class for your databag class. For example::

        @dataclasses.dataclass
        class SMTPProviderData(RelationDataBase):
            host: str
            port: int = 587
            user: str | None = None
            password: ops.Secret | None = None
            auth_type: AuthType = AuthType.NONE
            transport_security: TransportSecurity = TransportSecurity.NONE

    Note: this is a dataclass, but can be any object that inherits from
    ``ops.RelationDataBase``, and can be initialised with the decoded Juju databag
    content passed as keyword arguments, for example a Pydantic model. Any
    errors should be indicated by raising ``ValueError`` (or a
    ``ValueError`` subclass) in initialisation.

    Use this in your charm class like so::

        class MyCharm(CharmBase):
            ...
            def _on_relation_changed(self, event: ops.RelationChangedEvent):
                rel = event.relation
                data = rel.load(SMTPProviderData, self.app)
                ...
                rel.save(data, self.app)

    If the data provided by Juju is not valid, the charm is expected to handle
    any errors raised.

    At the end of the hook, the updated values are automatically sent through to
    Juju. The databag class is responsible for ensuring that the data is valid.

    Note that :meth:`load` will, by default, decode the raw Juju data from
    JSON before passing the values through to the class, and encode to JSON when
    sending any modified data back to Juju.
    """

    # This class does not currently provide any functionality - any class that
    # has an appropriate __init__ could be passed to load() and would work.
    # However, we may want to add some built-in functionality to the base class
    # in the future - for example, to provide some default validation when the
    # class is a dataclass rather than a pydantic model, or to make it easier to
    # select which fields are serialised. Requiring users to inherit from this
    # class makes it easier to add that functionality in the future.

```

### New Relation .load, .save methods

To provide a consistent mechanism for instantiating the databag classes, and, in particular, for binding the class to make appropriate relation-get and relation-set calls, the Relation class will gain two new methods: `load` and `save`. This is similarly structured to `relation.data[app_or_unit]`, but you provide it with the class to use to make the object and it returns it.

```py
def load(
    self,
    cls: Type[_InterfaceType],
    app_or_unit: Unit | Application,
    *args: Any,
    decoder: Optional[Callable[[str], Any]] = None,
    **kwargs: Any,
) -> _InterfaceType:
    """Load the data for this relation into an instance of a databag class.

    The object will be instantiated with the data from the relation databag.

    Any additional positional or keyword arguments will be passed through to
    the databag class.

    Args:
        cls: A class that inherits from :class:`ops.RelationDataBase`.
        app_or_unit: The databag to load. This can be either a :class:`Unit`
            or :class:`Application` instance.
        decoder: An optional callable that will be used to decode each field
            before loading into the class. If not provided, json.loads will
            be used.
        args: positional arguments to pass through to the databag class.
        kwargs: keyword arguments to pass through to the databag class.

    Returns:
        An instance of the databag class with the current relation data values.

    Raises:
        ValueError: if the databag class cannot be instantiated with the
            provided data.
    """

def save(
    self,
    obj: RelationDataBase,
    app_or_unit: Unit | Application,
    encoder: Optional[Callable[[Any], str]] = None,
) -> None:
    """Send the data from this databag object to Juju.

    The object fields will be encoded and then sent to the Juju unit
    agent, which will update the relation data at the successfull completion
    of the hook.

    Args:
        obj: A instance of a class that inherits from :class:`ops.RelationDataBase`.
        app_or_unit: The databag to load. This can be either a :class:`Unit`
            or :class:`Application` instance.
        encoder: An optional callable that will be used to encode each field
            before passing to Juju. If not provided, json.dumps will be
            used.

    Raises:
        ValueError: if the databag fields cannot be encoded to a string.
    """
```

Charms are expected to catch errors that occur when instantiating the class (for example, the data is incompatible with the schema) and handle the situation appropriately. We do *not* automatically set a status as we propose in the related [config schema spec](https://docs.google.com/document/d/1vj2pTvVRXClCrYM7tUjft3ngISSsFdBQD1B-CzOG1Vs/edit?usp=sharing). It is also the charm's responsibility to handle validation errors when setting data (trying to set incompatible data is a charm bug rather than a problem outside of the specific unit), or sending it through to Juju.

Relation data is always read when calling `load`. In some cases, charms do not need access to the existing data, and want to simply use a strongly typed class to construct data to set, and then send that data to Juju. This is particularly the case when a relation is first created, where there is no existing data and the charm needs to set data (that is: where the charm needs to update the schema rather than to avoid the cost of reading the data). In this case, the charm creates an appropriate instance of the class without using `load`, and then calls save on it to send the data to Juju.

Example class ([original source](https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/tempo_cluster/v1/schema.py)) and usage:

```py
# Schema

class TempoClusterProviderAppData(pydantic.BaseModel):
    worker_config: str = Field(
        description="The tempo configuration that the requirer should run with."
    )
    loki_endpoints: dict[str, str] | None = Field(
        default=None,
        description="List of loki-push-api endpoints.",
    )
    ca_cert: str | None = Field(
        default=None, description="CA certificate for tls encryption."
    )
    server_cert: str | None = Field(
        default=None, description="Server certificate for tls encryption."
    )
    s3_tls_ca_cert: str | None = Field(
        default=None, description="CA certificate for the s3 bucket API."
    )
    privkey_secret: ops.Secret | None = Field(
        default=None,
        description="A Juju secret that holds the private key.",
    )
    remote_write_endpoints: list[dict[str, str]] | None = Field(
        default=None,
        description="Endpoints to which the workload can push metrics to.",
    )
    charm_tracing_receivers: dict[str, str] | None = Field(
        default=None,
        description="Endpoints to which the worker node can push its charm traces to."
    )
    workload_tracing_receivers: dict[str, str] | None = Field(
        default=None,
        description="Endpoints to which the worker node can push its workload traces to."
    )
    worker_ports: list[int] | None = Field(
        default=None,
        description="Ports that the worker should open on its pod.",
    )

    _model: pydantic.SkipJsonSchema[ops.Model] = Field(
        default=None,
        description="Not included in the relation data. Used to get secrets.",
    )

    model_config = pydantic.ConfigDict(
        validate_assignment=True,
    )

    @field_serializer('privkey_secret')
    def serialize_privkey_secret(self, secret: ops.Secret, _info):
        return secret.id

    @field_validator('privkey_secret', mode='before')
    @classmethod
    def parse_string(cls, v):
        """Converts Juju secret IDs to ops.Secret instances."""
        if isinstance(v, str):
            try:
                return self._model.get_secret(id=v)
            except ops.SecretNotFoundError:
                # No such such, or missing permissions. Raise a validation error
                # or otherwise handle.
                ...
        # We might want to fail validation here instead.
        return v

# Raw Juju application databag. Note that the field values are all JSON.

{
    'worker_config': '...yaml...',
    'loki_endpoints': 'null',
    'ca_cert':  'null',
    'server_cert': 'null',
    's3_tls_ca_cert': 'null',
    'privkey_secret': 'secret:1234',
    'remote_write_endpoints': 'null',
    'charm_tracing_receivers': 'null'
    'workload_tracing_receivers': 'null',
    'worker_ports': '[8000'],
}

# Example requirer usage

def _on_relation_event(self, event: ops.RelationEvent):
    rel = event.relation
    # We pass in the model so that the class can load secrets.
    data = rel.load(TempoClusterProviderAppData, event.app, _model=self.model)
    # Note that the data has been deserialised from JSON.
    if data.worker_ports:
        logger.info(
            'Open worker ports: %s', ', '.join((str(p) for p in data.worker_ports))
        )

# Example provider usage

def _add_worker_port(self, port: int):
    rel = self.model.get_relation(name)
    # We pass in the model so that the class can load secrets.
    data = rel.load(TempoClusterProviderAppData, self.app, _model=self.model)
    try:
        data.worker_ports.append(port)
    except ValueError:
        # Handle this appropriately...
    data.save(self.app)
```

### Future considerations: Secrets

Juju Secrets are, like relation data, string:string mappings (a string:bytes mapping is also supported, but is not known to be used by any charms) with arbitrary schema, and are also shared between different units and applications. In practice, secret schema is simpler than relation data - nested data is not common, and values typically are strings (such as passwords or encoded certificates).

A `SecretContentBase` class is not proposed in this spec, but is a potential improvement in a future version of Ops, covered by a follow-up spec. This might look like:

```py
# SecretContentBase objects would lazily fill all attributes the first time
# an attribute is accessed, so that the secret content is not loaded into
# memory until required.

# The spec would design how peek/refresh symantics would be included,
# what an owned secret (where metadata is available, content can be updated,
# and so on) would look like, use of labels, and so forth.

class DatabaseCredentials(ops.SecretContentBase):
    username: str
    certificate: str

class GithubToken(ops.SecretContentBase):
    token: str

@dataclasses.dataclass
class MyConfig(ops.ConfigBase):
    ...
    github_token: GithubToken | None = None

@dataclasses.dataclass
class CharmWithSecretUnitData(ops.RelationDataBase):
    ...
    credentials: DatabaseCredentials | None = None

class MyCharm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        super().__init__(framework)
        ...
        self.typed_config = self.load_config(MyConfig)
        # load_config knows that SecretContentBase objects serialise to/from
        # strings (the Juju secret ID).
        self.load_github_data(token=self.typed_config.github_token.token)

    def _on_relation_event(self, event: ops.RelationEvent):
        rel = event.relation
        # load knows that SecretContentBase objects are strings in the
        # relation data (in the form of Juju secret IDs).
        data = rel.load(CharmWithSecretUnitData, self.unit)
        db = self.connect_to_db(
            username=data.credentials.username,
            certification=data.credentials.certificate,
        )
        ...
```

Note that much of this functionality can be done using only what is proposed in this spec (the main exceptions are lazy loading and not having to pass around a `Model` to get secrets). For example, adjusting the example from above:

```py
class TLSCoordinatorSecretKey(pydantic.BaseModel):
    private_key: str
    _secret: ops.Secret

class TempoClusterProviderAppData(pydantic.BaseModel):
    ...
    privkey_secret: TLSCoordinatorSecretKey | None = Field(
        default=None,
        description="A Juju secret that holds the private key.",
    )
    ...

    @field_serializer('privkey_secret')
    def serialize_privkey_secret(self, key: TLSCoordinatorSecretKey, _info):
        return key._secret.id

    @field_validator('privkey_secret', mode='before')
    @classmethod
    def parse_string(cls, v):
        """Converts Juju secret IDs to TLSCoordinatorSecretKey instances."""
        if isinstance(v, str):
            try:
                secret = self._model.get_secret(id=v)
            except ops.SecretNotFoundError:
                # No such secret, or missing permissions. Raise a validation error
                # or otherwise handle.
                ...
            else:
                # Let validation errors bubble up.
                return TLSCoordinatorSecretKey(_secret=secret, **secret.get_content())
        # We might want to fail validation here instead.
        return v
```

### Future considerations: Starlark & Starform

There is a long-term plan ("scriptlets") that Starlark will be used to provide validation functionality (presumably for all of config, action params, and relation data) in Juju (likely using [Starform](https://github.com/canonical/starform)). Charms will provide Starlark code that Juju would execute in the Starlark sandbox, and from the charm's point of view the data would be valid in nearly all situations (or when setting, would be rejected if invalid). Given the restrictions of the Starlark sandbox, it's likely that there will always be edge cases that must be tested in the live charm code, but those should be rare exceptions.

A significant advantage of using Starlark may be that it will allow for relation data schema that adapts during the integration process - for example, starting with empty relation data, then gradually filling the schema as the charms do work and other charms are also integrated (for example, adding in TLS). This is easier to describe in Starlark code than in a static form.

Starlark does not provide a solution for static checking (particularly static type checking), and does not provide a solution for IDE / language server integration, so by itself is not sufficient to meet our goals. Since Starlark doesn't support type annotations (or exceptions, or classes) sharing the same code for charm code and Starlark would require significant changes (probably considered detrimental, given the decreased expressiveness) to how charms are currently defining schema.

A Starlark based validation of relation data provides less certainty to the charm than validation of charm config or charm action parameters. A charm providing config or action Starlark validation can be certain that the validation will always occur (when running on an appropriate version of Juju), and so the incoming data will have been validated. However, a charm providing Starlark validation of relation data may be interacting (sharing databags) with other charms that do not use Starlark validation (or use different validation). Solving this issue is left for future work.

## Further Information

### Pydantic

Many charms are already using Pydantic to define interface schema, and this is required by [charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces). It's also a requirement for the [cosl](https://pypi.org/project/cosl/) package, which is used to add observability to charms. This means that a large number of charms are already using Pydantic, and - assuming that almost all charms end up using COS/COS lite - this will increase to nearly 100%.

A consequence of this is that builds are slower or more complicated than we'd like. Pydantic's core is implemented in Rust, which means that the Rust toolchain is required to create a wheel, and this is slower than pure Python dependencies (or alternatively, charms have to implement/use some sort of wheel building or caching mechanism). Pydantic is also fairly large - the core is currently around 5.1MB when installed, and the main package another 1.9MB.

If ops requires Pydantic, these issues will extend to all (operator framework) charms. An allowance could be made for very simple charms by making this an optional dependency (e.g. ops[validation]), but the expectation would be that nearly all charms would choose to include the dependency. This increases the size of most charms - but perhaps that's going to happen anyway unless the COS dependencies change.

While Pydantic is a popular and heavily used library, for many charm use-cases simple structures can be used. For example, using the standard library dataclasses:

* Static type checking is supported.
* Validation at instantiation time is easily done in `__post_init__` (raising `ValueError` or a subclass).
* Validation of setting attributes is easily done with `__setattr__`.
* The majority of types that charms use are either available in the standard library (for example, IP addresses and enums), or can be trivially defined (for example, URLs) - ops could even include the most common of these in a future update.
* The majority of validation that charms use is straightforward (minimum and maximums for numbers, maximum lengths for strings). For action parameters these can be specified in the JSON schema, but even for config and relation data very little Python code is required to implement this validation.

Another consideration with requiring Pydantic is that the ops versioning approach is to continue with the 2.x version for as long as possible, enabling charms to always quickly migrate to the latest version. A consequence of this is that features are supported for the long term (likely 10+ years, given the Ubuntu LTS cycle). While Pydantic is the most popular package in the Python ecosystem right now, that is not necessarily going to be the case going forward. We would like to avoid tying features to specific dependencies.

The Charm-Tech team encourages charmers to consider avoiding Pydantic as a dependency until the additional costs are clearly justified. However, the team also recognises the existing adoption of Pydantic (including currently as a required dependency for charm-relation-interfaces), and does not want to block use where it is appropriate. This specification does not require a specific schema class type (such as standard library dataclasses or Pydantic). Tests will be added that handle four cases: a plain Python object, standard library dataclasses, Pydantic dataclasses, and Pydantic BaseModel classes. The intention is that these are explicitly supported but that other types of class also work, and there is no promise that every future version of Pydantic will be supported (although while it remains in common use in charms, that is likely).

### Sourcing Schema

For peer relations, and other relations that are intended to only be used within the charm, the schema can be included in a file within the charm source. More commonly, the relation will be designed to be used via a library and using an interface, ideally published at charm-relation-interfaces. We would like these schema to be available without having to copy and paste them into the charm lib code (particularly for charm libs, since only a single file is available).

Sourcing the schema is out of scope for this spec, but one option is to add a pyproject.toml file to charm-relation-interfaces to allow retrieval via pip (or other installation tools). For example:

```
[project]
name = "charm_relation_interfaces.smtp"
version = "0.1.0"
description = "The schema for the Juju relation interface `smtp`"
requires-python = ">=3.8"
dependencies = ['pydantic', 'pytest-interface-tester']

[build-system]
requires = ['setuptools', 'wheel']
build-backend = 'setuptools.build_meta'

[tool.setuptools]
packages = ["smtp.v0"]
package-dir = {"smtp.v0" = "v0"}
```

This allows the package to be installed like this:

`uv pip install git+https://github.com/canonical/charm-relation-interfaces#subdirectory=interfaces/smtp`

And the schema is available in code, for example:

```py
import smtp.v0.schema as s

s.SmtpProviderData(
    host='example.com',
    port=22,
    auth_type=s.AuthType.NONE,
    transport_security=s.TransportSecurity.NONE,
    user=None,
    password=None,
    password_id=None,
    domain=None
)
```

This avoids having to upload a package for each interface (or each interface+version) to PyPI, or to have a single package that includes all interface schemas. It does require `git` to be available during packing, however (but if we are going to encourage charm libraries to be installable from source control, this is perhaps less of an issue).

If Charmhub represented libraries as top-level objects, then it seems feasible that a library could contain an interface schema, and a charmcraft command could retrieve the file. However, implementing this does not seem feasible in the short term, and it could easily be done as future work. Note that this might become a requirement if charm packing in the future cannot rely on any external sources.

However, a limitation here is that packages provided by PyPI cannot include dependencies that are not also available from PyPI. A large number of very small packages within a common namespace on PyPI may be the most practical solution.

See also the prior work in [operator-schemas](https://github.com/canonical/operator-schemas).

### Prior Work

#### charm-json

charm-json is a library that wraps the ops Relation class to provide automatic serialisation to and from JSON when sending data to Juju.

#### ID037 - Charm Uniformity

Spec ID037 (May 2024) is much broader than relation data validation, but recommends using Pydantic to define schema for relation data.

#### ST010 Adopt schemas into charm relations

This Q3 2021 spec proposed adding a standard data interface into Charmcraft & Juju. The spec focused specifically on the schema, leaving validation to Python code. The goal was to to add support for schemas to charmhub as a top-level object. It also included [support to fetch schemas at pack time](https://github.com/canonical/charmcraft/pull/442), and support for versioning of relation data, enforced by Juju. It focused on JSONSchema as the choice for defining schemas. The desire was to have a common solution that works across config, relations, etc.

Example:

```
requires:  # or provides, peer
  object-storage:
    interface: object-storage
    schema: https://raw.githubusercontent.com/canonical/operator-schemas/master/object-storage.yaml
    versions: [v1]
```

```py
try:
	self.interfaces = get_interfaces(self)
except NoVersionsListed as err:
	self.model.unit.status = WaitingStatus(str(err))
	return
except NoCompatibleVersions as err:
	self.model.unit.status = BlockedStatus(str(err))
	return
else:
	self.model.unit.status = ActiveStatus()
```

The spec is has significantly more functionality than this one. We believe it will be better to start with a smaller feature set that is added to ops, and improvements (such as Starlark validation in Juju, version negotiation in ops) can be made in the future.

#### OP016 Provides-requires Relation data interface

This spec (mid-2022 to 2023) - reached a [proof-of-concept](https://github.com/PietroPasotti/relation-wrapper/tree/main) stage, but didn't win approval. It also made it clear which was databag was the provider and which was the requirer. It was agnostic as to whether you're using dataclasses or pydantic etc. It included a template class where you provide the four schema, and an endpoint class that you provide the Template to. Validation was handed with local_valid, remote_valid, and valid properties. It also handled writing. It did not cover config or action parameters.

#### DA101 Pydantic integration in charms

This early 2023 to mid 2024 spec covered config, action parameters, and relation data, and specifically recommended pydantic. It originated from the data_platform_libs library, but parts (with modifications) were also used elsewhere, and it is strongly based on the common practices that were developing (and have continued since) in defining interface schema.

The spec suggests that ops could include this functionality. A [charm-Tech response](https://gist.github.com/tonyandrewmeyer/6127fdff397e35178d38f6da325a1edc) suggested a simpler implementation that was less tied to pydantic and had simpler typing (in particular, fewer generics).

The implementation provides classes that inherit from pydanic.BaseModel that provide charming integration (one for config & action params, and one for relations). The config/action one provides a read method that is basically load_from_juju_config_dict or load_from_juju_action_params_dict, plus some case tweaking (kebab vs snake). For config, provides a Generic class to inherit from instead of CharmBase that provides the typed config data.

For config, validation occurs when the config attribute is accessed and for action params on read().
Setting up writing relation data requires calling "bind" between the data class and the appropriate ops RelationDataContent object.

Serialisation/deserialisation are handled transparently, and the user can choose a method (for example, YAML, or JSON). A wrapped ops.main is provided that handles errors. There is some discussion of having models generated from YAML.

#### Versioning support in alertmanager-k8s

This is an example of an existing charm that has support for handling multiple versions of schemas (it tries the newer schema, and falls back to the older one). This functionality should work essentially unchanged with the implementation this spec describes.

#### Serialised Data Interface

This is a Python package on PyPI. It is used to define relation schema in YAML (which is essentially JSON Schema, similar to action parameters). It can pull the schema from version control or a local file. The documentation indicates that it only supports the application databag, although the code seems to work with units. It provides methods for getting/setting data - validating it with the schema but getting or setting the data through ops. It was apparently dropped because there were many bugs. This included schema versions and version negotiation.

#### data_models lib

The data_models charm lib includes an implementation that is essentially an early version of [DA101](#da101-pydantic-integration-in-charms).
