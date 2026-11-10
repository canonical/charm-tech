# OPxxx - ops-tools: generate charmcraft YAML from Python classes

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | Jun 20, 2026 |

## Abstract

Charms can define their config options and action parameters as Python classes, and load them with `CharmBase.load_config()` and `ActionEvent.load_params()`. However, Juju and Charmcraft still need the same schema as YAML in `charmcraft.yaml`, so a charm that uses classes has two copies of the schema to keep in sync, and in practice they drift.

This spec adds `ops-tools`, a small command-line package on PyPI that generates the `config` and `actions` YAML from those classes. The Python code becomes the single source of truth, and the YAML is a build artefact that CI can check.

## Rationale

We would like the source of truth to be in the charm code. Python is more expressive than the Juju config schema language or the JSON Schema subset used for action parameters, so the classes can carry more complex types and validation than the YAML can. The charm already needs the classes to load config and parameters at runtime, so the YAML is the copy that should be derived.

`ops-tools` is a separate package rather than part of `ops`, for the same reasons that `ops-scenario` and `ops-tracing` are. It's only needed while developing and building the charm, not at runtime, so putting it in `ops` would add to every charm's dependencies for no benefit. A separate package can also be versioned independently (although we'll probably release it at the same time as `ops`, as we do the others).

We've prototyped this before, in [canonical/operator#1975](https://github.com/canonical/operator/pull/1975). The prototype worked, but it was too large to review well, and the discussion of several unrelated design questions got tangled together. This spec settles those questions up front, so that the implementation can land as a few smaller PRs that only need to be reviewed on their own merits.

## Specification

### Example

This config class:

```python
@dataclasses.dataclass(frozen=True, kw_only=True)
class Config:
    log_level: str = 'info'
    """The level to log at."""
    api_token: ops.Secret | None = None
    """A secret holding the workload's API token."""
```

generates:

```yaml
config:
  options:
    log-level:
      type: string
      default: info
      description: The level to log at.
    api-token:
      type: secret
      description: A secret holding the workload's API token.
```

And this action class:

```python
class Compression(enum.Enum):
    GZ = 'gzip'
    BZ = 'bzip2'

@dataclasses.dataclass(frozen=True, kw_only=True)
class RunBackupAction:
    """Back up the database."""

    filename: str
    """The name of the backup file."""
    compression: Compression = Compression.GZ
    """The type of compression to use."""
```

generates:

```yaml
actions:
  run-backup:
    description: Back up the database.
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
```

Underscores in config option and parameter names become hyphens, which is the reverse of what `load_config()` and `load_params()` do. The action name comes from the class name, converted to kebab case, without the `Action` suffix.

### Command line

There's a single `ops-tools` command with a subcommand for each operation:

```bash
uvx ops-tools generate-metadata --config Config
uvx ops-tools generate-actions --action '.+Action'
```

A single entry point is easier to discover (`ops-tools --help` lists everything) and works neatly with `uvx`. It also leaves room for more subcommands later without adding more console scripts.

The flags are short: `--config` and `--action` take a class, and `--path` is the charm's root directory (the current directory by default). The subcommand already says what's being generated, so the flags don't need to repeat it (`--config-file`, `--charm-path`, and so on). `--config` and `--action` can be given more than once. A class is either a bare name (looked up in `src/charm.py`), a `module:Class` reference for classes elsewhere in the charm, or a regular expression matching class names.

The generated YAML goes to stdout.

### Generate, don't edit

`ops-tools` generates YAML. It doesn't edit `charmcraft.yaml` in place.

Editing in place is only useful if it preserves the comments and layout of the rest of the file, and that needs a round-trip YAML library such as `ruamel.yaml`. Charm Tech uses PyYAML everywhere else, and we don't want to maintain two YAML libraries for one feature. Generating fresh output and comparing it with `git diff` is simpler, and makes it obvious what changed. If we ever move off PyYAML more broadly, in-place editing can be added as another subcommand.

### Types

Config options map Python types to Juju config types:

| Python | Juju |
| --- | --- |
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `boolean` |
| `ops.Secret` | `secret` |

Action parameters map to JSON Schema types: `str` to `string`, `int` to `integer`, `float` to `number`, `bool` to `boolean`, and lists and tuples to `array` (with `items` set from the element type). An `enum.Enum` becomes a `string` with an `enum` list of the member values. Fields without a default are listed in `required`, and `additionalProperties` is always `false`.

Optional types (`X | None`) generate the type of `X`. A union of two types that Juju can't express (such as `int | str`) falls back to `string`.

Annotations can use either `a | b` or `Union[a, b]` / `Optional[a]`. We resolve them with `typing.get_type_hints()`, which normalises both forms, so supporting both costs nothing, and requiring only the modern form would reject charm code that is perfectly valid. The documentation uses `a | b`, which is always available because `ops` requires Python 3.10 or later.

### Descriptions

If a field has an explicit description, we use it: `field(metadata={'description': ...})` for a dataclass, or `Field(description=...)` for a Pydantic model. Otherwise, we fall back to the attribute docstring (the string literal immediately after the attribute, as in the examples above), which we find by parsing the class source. An action's description is the class docstring.

The docstring form is much nicer to write, which is why we support it, but it's also the more fragile of the two: it relies on the source being available and on walking the AST correctly. We'll test it explicitly against inherited fields (a parent class's docstring mustn't overwrite the child's), Pydantic models, and conditional imports. The documentation will recommend explicit descriptions for new code.

### Pydantic

Pydantic isn't a dependency of `ops-tools`. The default install handles dataclasses (and any other class that `load_config()` and `load_params()` support), and `pip install ops-tools[pydantic]` adds support for reading Pydantic field metadata directly. The import is lazy, so both code paths are always present and the extra only controls what's installed. For the same class, both paths must generate exactly the same YAML, and the tests check this.

### Packaging

The package is `ops-tools` on PyPI, and the import name is `ops_tools`. It can't be `ops.tools`, because `ops` isn't a namespace package.

We aren't going to set a convention for naming `ops-*` packages here. The two that exist already differ (`ops-scenario` is `import scenario` and `ops-tracing` is `import ops_tracing`), so a convention now would either bless that or force a rename. When there's a third package we'll have a better idea of which pattern to settle on.

### Implementation

The code lives in a new `tools/` directory in `canonical/operator`, alongside `testing/` and `tracing/`, and lands in three PRs:

1. Config generation, including description extraction and its tests, and tests that check the exact YAML output for a set of example classes.
2. Action generation, reusing the description extraction from the first PR.
3. Packaging: `pyproject.toml`, the `ops-tools` command and its subcommands, the Pydantic extra, a documentation page, and adding the package to the release process.

Nothing is installable until the third PR, so the first two can be reviewed purely as code.

## Out of scope

- Editing `charmcraft.yaml` in place (see above).
- Using the classes in `ops.testing`, for example to validate config in a state-transition test. That's worth doing, but it can be designed separately once the generator exists.
- Generating any part of `charmcraft.yaml` other than `config` and `actions`.

## Open questions

How should CI compare the generated YAML with what's committed? This is straightforward for a charm that keeps its config in `config.yaml` and its actions in `actions.yaml`, because the generated output is the whole file. However, most charms now have everything in `charmcraft.yaml`, and the generated `config` and `actions` sections are only part of that file. We could document a recipe that extracts the sections first (with `yq`, perhaps), or add a check mode to `ops-tools` that does the comparison itself. I think the check mode is probably nicer, but it isn't needed for the first release.
