# OP080 — Interface docs and metadata

| Field | Value |
| --- | --- |
| Status | Braindump |
| Type | Implementation |
| Created | 26 Nov 2025 |

## Abstract

In [OP074](https://docs.google.com/document/d/1YbfwYGSqSCByPHBZaSVJPdN4UP_vjdZEH-Ms6531_fE/edit?tab=t.0), we planned out colocating interface libraries and interface definitions in the [charmlibs monorepo](https://github.com/canonical/charmlibs). This spec details what this should look like, as we diverge and evolve from the features used in `charm-relation-interfaces`. The key changes are adding some fields to `interface.yaml` for use by Charmhub, and dropping mandatory dependencies of `schema.py` to facilitate runtime use of the schemas.

## Rationale

While `charm-relation-interfaces` provided a standardised template for interface definitions, this was out of date when we began migrating to the `charmlibs` monorepo ([#203](https://github.com/canonical/charm-relation-interfaces/issues/203)), and does not directly meet the requirements we now have.

## Specification

This specification outlines the requirements for the three interface definition files: `interface.yaml`, `README.md`, and `schema.py`. Note that these files are duplicated for each major version of the interface (reflecting breaking changes to the interface), a design inherited from `charm-relation-interfaces`.

### interface.yaml

**Summary:** add `summary`, `description` and `lib` fields for consumption by Charmhub and our docs. Don't recommend the use of `test_setup`

The `interface.yaml` file provides machine readable metadata about an interface. Currently the following fields are defined:

```
name:  # interface name that will be used in charmcraft.yaml
version:  # current major version, matching vN directory
status:  # draft if this should be considered unstable, otherwise published
maintainer:  # team name on Github
providers:  # list of charms
  - name:  # charm name on charmhub
    url:  # https://github.com/canonical/...
    test_setup:  # additional fields are nested here to facilitate interface testing
requirers:  # as providers
```

Currently we don't recommend investing efforts in the current unit-test-like interface tests, so we won't ask new interfaces to include `test_setup`.

There is existing code on Charmhub to display the charms listed in `providers` and `requirers` more prominently on the interface page. In future, when charm interface test data is exposed to Charmhub, likely via [Solutions QA's integration tests](http://test-observer.canonical.com) (link via VPN only), Charmhub will be able to show users which charms that implement interfaces correctly. At that time, the `providers` and `requirers` fields may serve no use, and be dropped entirely. For now, the current manual solution seems valuable enough to keep supporting as an interim solution, so `providers` and `requirers` should be populated by each interface's `CODEOWNERS` with this in mind.

The primary consumer of the information in `interface.yaml` will be Charmhub, via an `interfaces.json` value that `charmlibs` computes for them. The `charmlibs` docs may also pull information from `interface.yaml`. To support this use case, we should add the following fields to `interface.yaml`:

* `summary` & `description`: following the `charmcraft.yaml` convention.
  * The short one sentence `summary` can be displayed in places like indexes (both in charmlibs docs and on Charmhub).
  * The longer `description` can be included on the interface page on Charmhub, and prepended to the readme in our docs.
* `lib`: The interface library, in the following format:
  * For PyPI packages, the fully qualified import package name.
    * e.g.  `charmlibs.interfaces.tls_interfaces`
  * For Charmhub-hosted libraries, `charms.<charm name>.<lib name>`
    * e.g. `charms.certificate_transfer_interface.certificate_transfer`

### schema.py

**Summary:** drop dependency on `pytest-interface-tester` and `pydantic` to facilitate using schemas in the libraries directly.

The `schema.py` file encodes the expected contents of the relation data in a machine readable format, alongside examples and documentation for humans.

In `charm-relation-interfaces`, this file was primarily consumed by [pytest-interface-tester](https://github.com/canonical/pytest-interface-tester) for relation data validation when running interface tests. This assumed that the module exposed two classes,  `ProviderSchema` and `RequirerSchema`, which inherited from `interface_tester`'s `schema_base.DataBagSchema` class. These two classes had `app` and `unit` attributes. These referred to the schemas for the respective application and unit relation data, which were required to be Pydantic models.

In `charmlibs`, we currently aren't planning to develop and advocate for interface tests, as they weren't widely adopted, and seem like they'll require more from charmers than the value they add.

However, we do want to support a long-requested use case, namely that interface libraries can use these schemas directly, or expose them to charms directly, instead of re-implementing or copy-pasting the code to the interface library. This is possible since the library and schemas now live side-by-side in the same repository. Libraries can add a symlink alongside their `__init__.py` file like this:

```shell
ln -s ../../../../interface/<vN>/schema.py _schema_<vN>.py
```

The symlink is resolved when building the wheel (as wheels don't support including symlinks themselves), and the `interface` directory is included in the `sdist`, so this 'just works'.

To facilitate this use case, we should make the following changes to the `schema.py` requirements:

1. Don't require inheritance from `DataBagSchema`, so that `schema.py` does not require `pytest-interface-tester`
2. Don't require the schema classes to be Pydantic models, so that charm libraries are not required to depend on `pydantic` to import their schemas at runtime - instead we can just require that schema classes work correctly with [ops.Relation.load](https://documentation.ubuntu.com/ops/latest/reference/ops/#ops.Relation.load) instead. See 'Further Information' for more on exporting JSON schemas and validating relation data without requiring Pydantic as a runtime dependency.

The requirements then would be: the module defines four attributes: `ProviderAppData`, `ProviderUnitData`, `RequirerAppData`, and `RequirerUnitData`. These should either be a class that can be used with `ops.Relation.load`, or `None`.

Requiring `None` explicitly helps protect against typos - if not providing one of the attributes indicated that the databag would be empty, then a typo like `class ProvideAppData: ...` would silently be interpreted like `ProviderAppData = None`.  We could add CI to validate that all four are correctly provided at schema PR time.

Note that these changes will break existing interface tests. If/when we look into running them in future, we'd need to either update our CI to include the information `pytest-interface-tester` expects (e.g. appending the expected classes and attributes to the `schema.py` files), or update the library itself.

### README.md

The `README.md` file provides human readable documentation about an interface, including its use case and the recommended library to use, as well as lower level details of the contract that implementations of the interface need to fulfill.

This is pretty much unchanged from the [charm-relation-interfaces template](https://github.com/canonical/charm-relation-interfaces/blob/main/interfaces/__template__/v0/README.md). In future we may be able to eliminate redundancy (and drift) between the human-readable docs and the other two files by automatically including information from them in the rendered docs.

## Further Information

### JSON Schemas

We don't have a use case for JSON schemas now, but knowing that we can still generate them from our Python schemas is useful for language agnostic future applications.

Interface schemas not being Pydantic models does not prevent us from generating JSON schemas, but it does mean that custom validation logic in (e.g.) `__post_init__` wouldn't be captured by such a schema. Certainly not everything a Pydantic model can express is captured by a JSON schema generated from the model (e.g. custom validation functions), but more can be captured for free (e.g. minimum and maximum values) ([Pydantic docs](https://docs.pydantic.dev/latest/concepts/json_schema/#generating-json-schema)).

Here's an example of generating a JSON schema from a standard library `dataclass` ... using Pydantic:

```py
import dataclasses
import json

import pydantic

@dataclasses.dataclass
class Schema:
    a: int


schema = pydantic.TypeAdapter(Schema).json_schema()
print(json.dumps(schema, indent=2))
```

```
{
  "properties": {
    "a": {
      "title": "A",
      "type": "integer"
    }
  },
  "required": [
    "a"
  ],
  "title": "Schema",
  "type": "object"
}
```

### Relation data validation

`pytest-interface-tester` assumes that schemas are Pydantic models, and calls their validation methods. However, at runtime `ops` can handle loading relation data into Pydantic models, `dataclasses`, and even regular classes. We can leave validating whether relation data matches a schema to `ops` rather than requiring schemas to be a Pydantic model.

The use case for this would be interface tests and charm library tests.

This is possible today, with a little `ops.testing` wrangling. We could always expose the relevant functionality publicly to make this simpler, or perhaps wrap it up in a little library for interface libraries to use in their tests.

```py
import json
from typing import Any, Mapping

import ops
from ops import testing

def validate[T](cls: type[T], data: Mapping[str, Any]) -> T:
    """Raise errors determined by cls if the data isn't valid."""

    class TestCharm(ops.CharmBase):
        def __init__(self, framework: ops.Framework):
            super().__init__(framework)
            framework.observe(self.on.update_status, self._on_update_status)

        def _on_update_status(self, event: ops.EventBase):
            rel = self.model.get_relation('rel')
            nonlocal result
            # self.unit to match testing.Relation(..., local_unit_data=...)
            # It doesn't matter whether cls is ProviderAppData, etc.
            result = rel.load(cls, self.unit)

    meta = {'name': 'test', 'provides': {'rel': {'interface': 'doesnt-matter'}}}
    ctx = testing.Context(TestCharm, meta=meta)
    rel_data = {k: json.dumps(v) for k, v in data.items()}
    relation = testing.Relation(endpoint='rel', local_unit_data=rel_data)
    state = testing.State(relations={relation})

    result: T | None = None
    try:
        ctx.run(ctx.on.update_status(), state)
    except testing.errors.UncaughtCharmError as e:
        raise e.__cause__ from None
    assert result is not None
    return result
```
