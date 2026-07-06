# OP064 — Action schema in Ops

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Mar 24, 2025 |

Implemented in [https://github.com/canonical/operator/pull/1756](https://github.com/canonical/operator/pull/1756) (with some minor adjustments, and without the schema generation, which has a draft implementation in this branch: [https://github.com/tonyandrewmeyer/operator/tree/action-schema](https://github.com/tonyandrewmeyer/operator/tree/action-schema))

## Abstract

Juju provides type validation of charm action parameters (defined as JSONSchema). However, charms may need to add additional validation (for example, where one action parameter influences the possible values for another), and although `action-get` provides typed data the types are not available to Python tooling (leading to proliferation of `typing.cast(str, x)` type code). A new ActionBase class will be added to Ops that avoids schema duplication by acting as the source of truth, while allowing any validation that can be done in Python code, and providing strong type annotations.

## Rationale

The charm action parameter schema is specified in charmcraft.yaml, where it is strongly typed, for example:

```
actions:
    run-backup:
        description: Backup the database.
        params:
            filename:
                type: string
                description: The name of the backup file.
            compression:
                type: string
                description: The type of compression to use.
                default: gzip
                enum: [gzip, bzip2]
            retries:
                type: integer
        required: [filename]
        additionalProperties: false
```

This data is retrieved using the action-get hook tool, and arrives as typed JSON, for example:

```
{
    'filename': 'backup.tar.gz',
    'compression': 'gzip',
    'retries: 3
}
```

However, since the schema is in YAML and not Python, Python tooling is unable to determine that (using the example above) 'retries' is an integer, so every action parameter is typed as `Any`. This means that charm code needs to copy the type information from the schema (through typing.cast or asserts) for static type-checking tools to work correctly, and for hints to appear in an IDE.

Values for parameters are validated by Juju when an action is run. This validation is significantly more elaborate than with configuration options, since the parameters are not simple types but JSONSchema. In most cases, charms do not currently make use of the extended functionality here. If charms need to add additional validation, this must be done in the charm code.

## Specification

To have a single source of truth, the action parameters schema must be defined once, and that definition used to produce alternative versions. The schema must be located where it can be most expressive - of the charmcraft.yaml, (potential) Starlark, and Python versions, the Python version is (by far) the most expressive.

Using Python action parameter classes is far less common in existing charms than for configuration options or relation data. However, for consistency, the intention is to follow the same pattern. In particular, standard library dataclasses, Pydantic dataclasses, and Pydantic BaseModel subclasses are all supported, but other classes should work with no or minimal changes.

### New class: ops.ActionBase

Using a Python class already solves two of the goals: clearer static type checking, and providing improved assistance (such as autocomplete) in IDEs. To complement these, a new class will be added to Ops that provides a mechanism for converting the schema to YAML suitable for actions.yaml. In the future, conversion to Starlark could also be added.

Note that unlike configuration options, it's expected that a charm may have multiple actions, and therefore multiple action classes. The structure of the new class is:

```py
class ActionBase:
    """Base class for strongly typed charm actions.

    Use :class:`ActionBase` as a base class for your actions, and define the
    attributes as you would in ``charmcraft.yaml``. For example::

        class Compression(enum.Enum):
            GZ = 'gzip'
            BZ = 'bzip2'

        @dataclasses.dataclass(frozen=True)
        class RunBackup(ops.ActionBase):
            '''Backup the database.'''

            filename: str
            '''The name of the backup file.'''

            compression: Compression = Compression.GZ
            '''The type of compression to use.'''

        @dataclasses.dataclass(frozen=True)
        class AddAdminUser(ops.ActionBase):
            '''Add a new admin user and return their credentials.'''

            username: str

    These are dataclasses, but can be any objects that inherit from
    ``ops.ActionBase``, and can be initialised with the raw Juju action
    params passed as keyword arguments. Any errors should be indicated by
    raising ``ValueError`` (or a ``ValueError`` subclass) in initialisation.

    Inheriting from ``ops.ActionBase`` is not strictly necessary, but it
    provides utility methods for translating the class to a YAML schema
    suitable for use with Juju.

    Use this in your charm class like so::

        class MyCharm(ops.CharmBase):
            def __init__(self, framework):
                super().__init__(framework)
                framework.observe(self.on['run-backup'].action, self._on_run_backup)
                framework.observe(self.on['add-admin-user'].action, self._on_add_admin_user)

            def _on_run_backup(self, event: ops.ActionEvent):
                params = event.load_params(RunBackup)
                ...

            def _on_add_admin_user(self, event: ops.ActionEvent):
                params = event.load_params(AddAdminUser)
                ...
    """

    @classmethod
    def to_juju_schema(cls) -> dict[str, Any]:
        """Translate the class to a dictionary suitable for actions.yaml.

        Using :attr:`ActionBase.to_juju_schema` will generate a YAML schema
        suitable for use in ``actions.yaml``. For example, with the class from
        the example above::

            print(yaml.safe_dump(RunBackup.to_juju_schema()))

        Will output::

            run-backup:
                description: Backup the database.
                params:
                    filename:
                        type: string
                        description: The name of the backup file.
                    compression:
                        type: string
                        description: The type of compression to use.
                        default: gzip
                        enum: [gzip, bzip2]
                required: [filename]
                additionalProperties: false

        To customise, override this method in the subclass. For example, to
        allow additional properties::

            @classmethod
            def to_juju_schema(cls) -> dict[str, Any]:
                action = super().to_juju_schema()
                action['additionalProperties'] = True
                return action
        """
```

The intention is not to support producing actions.yaml content for any possible class, but for the majority of the current use-cases. Charms can use third-party libraries (for example, Pydantic) to handle complex cases, or override the provided methods in the class.

Some Juju functionality is explicitly not supported in the default YAML generation: ['parallel'](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/actions-yaml-file/#action-parallel) and ['execution-group`](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/actions-yaml-file/#action-execution-group). Reviewing known charms found no use of these fields in existing metadata. If charms do want to use this, it's simple to add by overriding `to_juju_schema` in the subclass, for example:

```py
class MyAction(ops.ActionBase):
    ...
    @classmethod
    def to_juju_schema(cls) -> dict[str, Any]:
        schema = super().to_juju_schema(cls)
        schema['my-action']['parallel'] = True
        schema['my-action']['execution-group'] = 'my-group'
        return schema
```

When generating the schema as Juju YAML, Ops will select an appropriate set of attributes from the class to include (for example, with a dataclass, this would be `dataclasses.fields()`, and with a Pydantic BaseModel, this would be `model_fields`). Charmers can customise which attributes are included by overriding the `to_juju_schema()` method in the action class. The generated schema will include at least type, default value, and description.

### Future work

Charmcraft's pack command currently creates an appropriate actions.yaml file by extracting the actions from the charmcraft.yaml file, with extensions able to further modify the actions. The functionality in this spec provides a charmer the ability to generate the appropriate YAML to insert into charmcraft.yaml, for example:

```shell
uvx --with=pyyaml --with=ops python -c 'import yaml;from charm import Action1,Action2;schema=Action1.to_juju_schema();schema.update(Action2.to_juju_schema());print(yaml.dump(schema))'
```

### In the future, this may be extended so that Ops provides a method to keep charmcraft.yaml in sync with the Python class, and/or verify that the two formats of the schema match. A charmcraft extension could also be developed that extended the action specification (as the existing extensions do) to include the generated schema from the charm via Ops.

### New ActionEvent.load_params method

To provide a consistent mechanism for instantiating the action classes, and, in particular, for handling errors, the `ActionEvent` class will gain a new method, `load_params`:

```py
def load_params(
    self,
    cls: Type[_ActionType],
    errors: Literal['raise', 'fail'] = 'raise',
    *args: Any,
    **kwargs: Any,
) -> _ActionType:
    """Load the action parameters into an instance of an action class.

    The object will be instantiated with keyword arguments of all the raw
    Juju action parameters, but with dashes in names converted to
    underscores.

    Any additional positional or keyword arguments will be passed through to
    the action class.

    Args:
        cls: A class that inherits from :class:`ops.ActionBase`.
        errors: defines the behaviour if the configuration is invalid. When set
            to 'raise', the original exception will not be caught by this method;
            when set to 'fail', the hook will exit with a zero exit code,
            after setting an appropriate action failure message.
        args: positional arguments to pass through to the action class.
        kwargs: keyword arguments to pass through to the action class.

    Returns:
        An instance of the action class with the provided parameter values.

    Raises:
        ValueError: when 'errors' is 'raise', and the configuration is valid.
            Note that this will be the original exception raised by the schema
            validation, so may be a ``ValueError`` subclass.
    """
```

If there are errors instantiating the class (including the class raising `ValueError` or any `ValueError` subclasses), the method will fail the action (exactly as if the charm code had used `event.fail`) with an appropriate message (based on the error raised). After setting the failure message, the charm will exit with a zero (success) error code, meaning that the charm code does not continue, and the Juju user will be presented with the failure message (but no traceback).

For example ([original source](https://github.com/canonical/discourse-k8s-operator/blob/main/actions.yaml)):

```py
@dataclasses.dataclass
class AnonymizeUser(ops.ActionBase):
    """Anonymize a user."""
    username: str
    """The unique identifier of the user to anonymize."""

@dataclasses.dataclass
class CreateUser(ops.ActionBase):
    """Create a new user."""
    email: str
    """User email."""
    admin: bool = False
    """Whether the user should be an admin."""
    active: bool = True
    """Whether the user should be email-verified and active."""

    def __post_init__(self):
        self.validate_email()

    def validate_email(self):
        # The charm would do more sophisticated validation than this.
        if '@' not in self.email:
            raise ValueError(f'{self.email} does not appear to be an email address')
        local, domain = self.email.rsplit('@', 1)
        if '.' not in domain:
            raise ValueError(f'{self.email} does not appear to be an email address')
        if ' ' in local:
            raise ValueError('email addresses containing spaces are not supported')

class DiscourseCharm(ops.CharmBase):
    def __init__(self, framework: ops.Framework):
        ...
        framework.observe(self.on['anonymize-user'].action, self._on_anonymize_user)
        framework.observe(self.on['create-user'].action, self._on_create_user)

    def _on_anonymize_user(self, event: ops.EventBase):
        params = event.load_params(AnonymizeUser)
        ...

    def _on_create_user(self, event.ops.EventBase):
        params = event.load_params(CreateUser)
        ...
```

Or using Pydantic:

```py
class AnonymizeUser(pydantic.BaseModel, ops.ActionBase):
    """Anonymize a user."""
    username: str
    """The unique identifier of the user to anonymize."""

class CreateUser(pydantic.BaseModel, ops.ActionBase):
    """Create a new user."""
    email: pydantic.EmailStr
    """User email."""
    admin: bool = False
    """Whether the user should be an admin."""
    active: bool = True
    """Whether the user should be email-verified and active."""

    @field_validator('email')
    @classmethod
    def validate_email(cls, value):
        # Extra validation can be added here (but pydantic.EmailStr does most
        # of what's needed).
        return value
```

### Future considerations: Starlark

There is a long-term plan ("scriptlets") that Starlark will be used to provide validation functionality (presumably for all of config, action params, and relation data) in Juju. Charms will provide Starlark code that Juju would execute in the Starlark sandbox, and from the charm's point of view the data would be valid in nearly all situations (or when setting, would be rejected if invalid). Given the restrictions of the Starlark sandbox, it's likely that there will always be edge cases that must be tested in the live charm code, but those should be rare exceptions.

Starlark does not provide a solution for static checking, and does not provide a solution for IDE / language server integration, so by itself is not sufficient to meet our goals. Since Starlark doesn't support type annotations (or exceptions, or classes) sharing the same code for charm code and Starlark would require significant changes (probably considered detrimental, given the decreased expressiveness) to how charms are currently defining schema.

It seems less likely that Starlark validation would provide significant advantages with action parameters compared to configuration options or relation data, since parameters already provide JSONSchema validation. However, if Starlark is added for the others, it would be consistent to add it for actions as well.

However, the `ActionBase` class does provide a natural place for charms to define their Starlark code, which could be exported in 'charmcraft pack' to the appropriate location in the charm.

## Further Information

See also the related specs:

* [Config schema in Ops](https://docs.google.com/document/d/1vj2pTvVRXClCrYM7tUjft3ngISSsFdBQD1B-CzOG1Vs/edit?usp=sharing) (very similar to this spec)
* [Interface schema in Ops](https://docs.google.com/document/d/1G0xfWJXomzzH2VIY1trFq4b5ybMEEjV0w_aReLWyjCs/edit?usp=sharing) (this spec in particular has more information about schema validation specs and implementations that have been attempted in the past)
