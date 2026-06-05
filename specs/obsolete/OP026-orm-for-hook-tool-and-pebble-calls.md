# OP026 — ORM for hook-tool and pebble calls

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-08-08 |

## Abstract

This spec proposes to add an ORM layer between the Operator Framework and 1) the hook tools provided by juju and 2) the API endpoints exposed by Pebble.

## Rationale

#### Early warning system

Providing an ORM layer between hook tools and Ops can help to catch early on mismatches between what `ops` expects to receive from juju and what `ops` actually receives.

- Bugs such as [this one](https://github.com/canonical/operator/issues/818) are difficult to trace back and reproduce. The issue was: `network-get` sometimes returns an unexpected object type in its `ingress-addresses` field.

##### Considerations:

- Should it be an optional dependency? `pip install ops[pydantic]`? Should we _vendor it?
- Which library to use?
  - **Jsonschema**: lightweight, should be usable from go and python
  - **Pydantic**: better, but heavyweight and python-only.
  - **?**
- Should it be a dev-only feature? Or runtime checks?
  - Runtime: warnings only, no hard-blocking errors, to give charms a chance to recover or ignore a possibly harmless error.
- secret-get -relation <rel_id> <secret_id> <key>
  - returns a string
  - schema for inputs and schema for outputs
- Testing against actual juju, compare juju returns to harness testing backend returns
- Validating schemas and against expected input/output

#### Typing system foundation

Secondly, it would provide a single foundation layer for Ops' typing system. That means less casts, and a better guarantee that if the foundation is solid, then so is what is built on it.

#### Testability

Having a clear specification of what the expected inputs (hook-tool, pebble return values) and outputs (hook-tool, pebble arguments) of Ops are means we can cover more edge cases when testing the OF itself. We can leverage existing frameworks (e.g. **hypothesis**) to generate test cases based on the ORM layer blueprints.

## Further Information

Where do the models live?
Ideally, for each juju/pebble version, we'd automatically generate the models (or rip off the facades from python-libjuju) and put them in `ops/models`.  If an older ops version attempts to interact with a newer juju/pebble version, for which it does not have models installed, there will be no runtime validation, ops will behave as it does now.

#### How will this look like?

- At runtime, Ops will lookup the juju version in an envvar and fetch the pebble version from an endpoint. These will be used to select the relevant models from the available library. If no
- The harness will have to be extended with a `juju_version: str` argument and a `pebble_version: str` argument, which it will use to set the envvars mentioned above.
  - Harness._backend calls will be validated using the models.
  - If we do our ops testing straight, no such validation error should be hit in user code, it's more of a sanity check for our own testing. User code should only raise more specific type errors (or warnings) before we reach the ORM layer.

#### Juju Facades
