# OP083 — Relation Interface Design

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Standard |
| Created | 29 Jan 2026 |

## Abstract

This document specifies details of the controlled process for introducing breaking changes to Juju relation interfaces: databag schema expectations, requirements to the charm library and supporting practices, charm library testing, and an end-to-end example of an interface upgrade path. The audience is charming engineers, specifically authors of charm libraries.

## Rationale

Historically, different charming teams and different charmed products provided different interoperability guarantees, both in terms of calendar time period and technical implementation. As a company we need a consistent, repeatable approach to manage interface evolution. From a customer perspective, a set of charms available today should just work together, just like packages in an Ubuntu LTS release, while breaking changes must be deliberate, introduced at defined points in time and communicated clearly, so that the experience upgrading a deployed Juju model is similar to an upgrading a live system to the next Ubuntu LTS release.

**Designing for forward compatibility and interface evolution**
When an interface is designed, the design must include provisions for the interface to eventually be extended, in other words, spend time now not to get into a corner later.

**Implementing backwards compatibility and rolling upgrades**
The charm library and the charm must be explicit when data is understood in the legacy format or published in both current and next format. Without that, it's unclear which party to the relation can be upgraded first without breakage, if any. This information ought to propagate to products and get documented, with the end result of Juju users being able to plan the sequence of application upgrades.

**Complicating factors**
Applications in a large deployment may form a densely-connected relation network. Thus, a single broken interface contract may have a significant impact on a running system.

Today, some products provide very long LTS guarantees, while others are developed quickly. Additionally, Juju users outside Canonical don't have a direct line to our engineers to find out the nuance of individual charms and their interfaces. This means that complex deployment upgrades are hard: a Juju user won't know which application would be the safest to upgrade first.

### Goals

* upgrade without downtime, where possible
* defined backwards and forwards compatibility for developers
* no order requirement for most upgrades for Juju users
* support degraded operation: avoid all-or-nothing upgrades

### Non-goals

* extending upgrade gatekeeping functionality in Juju
* simple numeric compatibility checks
* exposing the compatible charm versions in Charmhub

## Specification

We'll treat interface design and charm library API design as a combined exercise, as that's the standard practice in the charming community today.

Using newer Pydantic, prefer the `MISSING` sentinel value over the more traditional `None`.
The former marks the field as "not required" while the latter, "optional":

| *# missing field is read as <MISSING>; deleted when written out*
foo: str | MISSING = MISSING

*# missing field is read as None; written out as JSON null*
foo: str | None = None |
| :---- |

Note that these are not interchangeable after the interface has been published.

### Databag schema

When designing a new interface, adopt the following practices for forwards compatibility, in summary:

- [field type can never be changed](#fixed-field-types)
- [no mandatory field are allowed](#no-mandatory-fields)
- [removed fields cannot be reused](#no-field-reuse)
- [collections should be expressed as arrays of objects](#collections)
- [URLs must be parsed and validated](#urls-and-uris)
- [fields should be grouped semantically](#semantic-grouping)
- [interface schema covers content of granted secrets](#secret-content-schema)

#### Fixed field types

Once a field has been declared, the type of the field must not be changed.

If a field type were widened, the older charm would not understand the newer.
If a field type were narrowed, the newer charm would not understand the older.
The semantics of a field should not be changed significantly.
Likewise the encoding of the top-level field cannot be changed.

The charm author is not in control of application versions Juju users ultimately deploy, therefore both type narrowing and widening of individual fields is forbidden.

Instead, for primitive types, add new fields on minor version bumps of the charm library and remove old fields in new major versions of charm libraries which are only used on a new track of a charm (strictly speaking before charm is promoted to stable in the new track); while structured fields allow addition (and eventual removal) of subfields.

Most charms use JSON, however some have experimented with e.g. compression (in sub-fields). If a charm or charm library wants to use a different encoding for a top-level field, that has to be a new field.

##### Value validation

The value of the field can be validated at the interface level. For example, a port number cannot exceed 65535 or an enumeration value can only be one if "a", "b" or "c".

A drastic change to the validator for a given field is almost the same as a field type being widened, narrowed or replaced. At the same time, small changes (bug fixed) must be and are allowed.

Pragmatically, validators should support the notion of "some other value" which can be coerced to the same result as a missing field. This allows the interface to evolve over time: a newer version of the interface should be foreseen, and the charm library prepared to receive unexpected values (within the specified type).

Notably the interface definition must specify a clear expectation how the out-of-bounds error will be treated for each field.

For example, an integer port outside of supported range should most likely be treated the same as if it were not sent.

An enumeration value outside the declared set of possibilities should be coerced either to `MISSING` or, optionally, to a predefined `UNKNOWN` (catch-all) value:

| foo: Enum(A, B) | MISSING = MISSING
bar: Enum(UNKNOWN, A, B) = UNKNOWN |
| :---- |

##### No Error state on garbage

If a charm library encounters remote data with an incompatible value type it should still be possible to initialise the charm object and query `.is_ready` on it. See [below](#handle-bad-remote-data).

Note that extra care is needed when updating an existing charm library to practice described in this specification, as there could have been incompatible changes in the history of the interface schema.

Note that adopting or dropping custom `encoder=` and `decoder=` in `ops.Reladion.save/.load` is probably a breaking change. Either defer to the next major version, or provide a legacy code path.

[Full rationale](#fixed-field-types-1)

#### No mandatory fields

Top-level fields must not be required.

If the charm does not provide the value, the charm library should either not emit the field into the databag (preferred, following not-required semantics) or emit a null value (following optional semantics).

The recipient should not crash on any missing field, instead it is the charm code that decides if the unit will go into a Waiting or Blocked state when data is missing on some relation, which is expressed by respective charm library's `.is_ready` reporting `False`.

| foo: str | MISSING = MISSING |
| :---- |

Likewise most sub-fields (that is leaf fields in structured data) must not be required.

| role: Role | MISSING = MISSING
  subject: str | MISSING = MISSING
  session: str | MISSING = MISSING |
| :---- |

The case for a required sub-field is as follows: a charm library may choose to discard an incomplete `Role` object using a custom field validator when it's missing a `subject`. Note that this could result in the very same data on the wire to be considered "complete" by one library version and "incomplete" after an interface upgrade, so tread carefully.

See [Semantic Grouping](#semantic-grouping).

A default value may be used instead of marking a sub-field not required:

| protocol: Literal["http", "https"] = "https"
temperature: float = 0.0
priority: int = 100
sans_dns: frozenset[str] = frozenset() |
| :---- |

Analysis of existing libraries suggests that default values are rare, and that they typically correspond to empty collections, enumerations or numeric quantities.

Please avoid "zero-valued" defaults like `username: str = ""`, as these tend to lead to bugs later on when the charm developer is not the developer who specified the default value. A rule of thumb: if you don't want a relation counterpart to send you an explicit empty string, don't use it as the default value.

Note that changing the default value has different meaning for the sender and the recipient (consider the initial handshake, empty databag → recipient's default; sender fills out the databag with defaults → sender's default; sender fills out real values → non-default) which means that it's hard to change the default value after the interface has been published.

[Full rationale](#no-mandatory-fields-1)

#### No field reuse

If a field has been removed from the interface, another field with the very same name must not be added.

The exception is reverting removal of a field, where the field is brought back with the exact same type and semantics.

The fields ought to be removed only in the new major version of the interface and therefore the charm library that processes it.

The charm library unit tests must contain test vectors for the older

**Practical note**
The deprecated annotation `foo: Annotated[str, Field(deprecated="...")]` is not enough:

- only affects reading the attribute and on the object `print(obj.foo) ⚠️`
- and not setting the attribute `obj.foo = "a" 🆗`
- or constructing the object `Class(foo="a") 🆗`.

 The annotation can be useful in the Python API, but is not recommended to deprecate fields on the wire.

[Full rationale](#no-field-reuse-1)

#### Collections

Collections must be represented as arrays of objects on the wire, with few exceptions.
The same rules apply to elements of the collection as to any other nested object.
The recipient must treat a collection as a set, and must not rely on the order of the elements in the collection.
The sender must emit collections in some stable order.

**Collections of primitive types** are strongly discouraged, because the collection elements cannot be extended. If the interface definition includes one, e.g. `foo: list[int]`, then the rules for the elements are fixed, and change to the semantics requires a new field `foo_new: list[...]`. See [the rationale and the alternative](#real-world-example).

The charm library must not rely on the **order in the collection** it receives. See [the rationale](#collections-1).

If the data needs to be keyed or ordered, consider adding a property into the individual objects in the collection:

| [{id: 42, name: "foo", ...}, {id: 1, name: "bar", ...}]
[{priority: 1, some_url: "..."}, {priority: 3, some_url: "..."}] |
| :---- |

The default expectation for the receiver is to filter the collection: discard the elements that fail validation, and present only elements that pass validation, deduplicated, to the charm. If everything is filtered out, the charm library author has a choice whether to effectively present an empty set or `MISSING` to the charm. For example:

| *# Given the schema:*
class Endpoint(pydantic.BaseModel, frozen=True):
    id: str | MISSING = MISSING
    some_url: str | MISSING = MISSING

class Databag(pydantic.BaseModel):
    endpoints: frozenset[Endpoint] | MISSING = MISSING

*# And the databag:*
endpoints = [{"id": 3, "some_url": "http://1.1.1.1/foo", "bar": 42},
             {"id": 1, "some_url": "http://1.1.1.1/foo", "qux": 99}]
*# And the API:*
.get_some_urls() -> set[URL]

*# Expected output is:*
{"http://1.1.1.1/foo"} |
| :---- |

The charm library must emit collections in **a stable order**, to avoid bounce in the relation data.
Note that a stable order always exists in JSON, because each object has a string representation, which could be used to sort the array.

Charm library authors are encouraged to use "frozen" Pydantic dataclasses for the collection elements, as this allows parsing the databag ergonomically (without custom validators, natively removing semantic duplicates):

| class Endpoint(BaseModel, frozen=True):
    id: str | MISSING = MISSING
    url: str | MISSING = MISSING

class Bag(BaseModel):
    endpoints: set(Endpoint) | MISSING = MISSING |
| :---- |

**Data maps** are discouraged. If some unique identifier naturally maps to a string, the interface designer may be tempted to represent a collection as a JSON object:

| {
    "Jane": {address: "foo", ...},
    "John": {address: "bar", ...},
} |
| :---- |

The semantics and type of the key can never be changed. Instead, represent such data as an array of objects: `[{name, address}, {name, address}]`. See [the rationale](#collections-1).

An exception to this rule is when the data map key is a Juju entity with a well-known string key. For example `<unit-name>: <object>` or `<machine-id>: <object>` are acceptable.

**Exceptions** generally fall into the category of existing workload-specific schema, which can be passed verbatim, but is still validated by the charm library.

#### URLs and URIs

URLs are encouraged. Even though a URL is an opaque format, and opaque formats are often problematic, it makes sense to use them when they map well to the workload and developer mental model. For example, [The Twelve-Factor App](https://12factor.net/backing-services) recommends expressing attached resources via URLs or locator strings.

Thus, document and test URLs comprehensively: both in terms of consistency and precision. The schema and the charm library must make it clear:

* what the **purpose** of the URL is
* what **kind** of URL it is: base URL, endpoint, full URL, an opaque value, or a workload-specific URI
* what **components** of the URL are allowed: scheme, userinfo, host, port, path, query, fragment
* what **values** are allowed: for example scheme must be HTTPS, host must be a hostname

`model_config = ConfigDict(arbitrary_types_allowed=True)`
`endpoint: yarl.URL | MISSING = MISSING`

`@field_validator("endpoint", mode="before")`
`@classmethod`
`def _validate(cls, v: typing.Any) -> yarl.URL | MISSING:`
    `if v is MISSING: return MISSING`
    `url = yarl.URL(v)`
    `if url.scheme not in {"http", "https"}: raise ValueError("...")`
    `...`
    `if url.fragment: raise ...`
    `return url`

The restrictions must be both documented and validated in the unit tests that accompany the charm library. Specifically, a developer using a future version of the interface must have a clear understanding how the current version of the charm library (currently released charms) will parse the given URL.

Changes to the validation rules must be explicit, documented in release notes and/or change log of the charm library and bump the major/minor/micro versions of the charm library accordingly.

[Rationale](#urls-and-uris-1)

#### Semantic grouping

The databag content should be structured to reflect the meaning of data. This allows validating the components of the databag separately, which in turn allows one side of the relation to degrade gracefully, if only a part of the databag is required.

For example,  instead of:

| {"host": ..., "port": ..., "base_url": ..., "path": ...} |
| :---- |

consider:

| {
  "direct": {"host": ..., "port": ...},
  "upstream": {"base_url": ..., "path": ...}
} |
| :---- |

The charm library API can then provide methods `.get_direct()` and `.get_upstream()` which raise exceptions only on the errors within their respective blocks.

For example, the semantics of the `direct` block could be that the `host` field doesn't make sense without the `port` field. When a remote application follows a different version of the interface `{host: "a.io", ports: [1,2,3]}`, the charm library can wipe out the entire `host` block, as if the content of the databag were `{"direct": MISSING, "upstream": ...}`.

Full [rationale](#semantic-grouping-1)

#### Secret content schema

When the secret is shared over a relation, the secret content schema must be contained in the same charm library as the relation interface schema.

Same rules apply to the secret content:

* no mandatory fields
* no field reuse
* allowed URL or URI components

The following rules would only apply if the secret content is sufficiently complex for individual secret field values to be encoded as e.g. JSON. However, an argument can be made that this should be rare, because at that point multiple secrets should be used instead.

* fixed field types
* collections
* semantic grouping

**Delta libraries** would typically compare the current secret revision against the latest and emit a custom event when the content is different.

**Holistic libraries** would typically refresh the secret to the latest revision and rely on the charm to compare the revealed values against the workload.

The Ops library doesn't provide the native API to validate the secret content against a schema. Additionally, the charm library may not be in a position to determine whether it is allowed to "refresh" the secret, that is to pivot the newest revision. At this point the recommendation is for the charm library to provide a wrapper around `ops.Secret` that validates the content against the schema at the use time.

A wrapper would be a natural place to decouple the charm-facing API from the content schema. The API should expose semantic access, similar to [Semantic grouping](#semantic-grouping). For example:

| class ContentSchema(BaseModel):
    username: str | MISSING = MISSING
    password: str | MISSING = MISSING  *# deprecated*
    password_hash: str | MISSING = MISSING

def get_verifier(...) -> str:
    data = ContentSchema.model_validate(
        model.get_secret(self.secret_id).get_content(refresh=True))
    if data.password_hash is not MISSING:
        return ...
    if data.password is not MISSING:
        return ...
    raise CustomError("...")

@deprecated
def get_raw_password(...) -> str:
    ... |
| :---- |

Full [rationale](#secret-content-schema-1)

### Charm library

To allow interface evolution, the charm-facing API should be decoupled from the interface parsing code. The Python code in the charm library typically deals with:

* logic: combining fields, filtering values
* stable Python API: both new and legacy interface fields are processed
* run-time: wrapping and suppressing errors in further dependencies and secrets
* arguments: charm context, for example the arguments that charm passes to the library
* third-party dependencies, for example loading PEM content in `cryptography.x509` primitives

Adopt the following conventions in charm libraries that wrap interfaces.

#### Handle bad remote data

Initialising the charm library object, and superficial API access (`.is_ready`, detailed status: see below) must not raise exceptions due to relation databag contents. Most importantly parsing the remote databag content must not lead to a charm-level exception / unit going into the error state.

* charm object initialisation must not raise
* charm object `.is_ready` must not raise

The rule exists because charm's `__init__()` has to succeed in order for the charm to respond to Juju events. The charm library author is not a position to decide which of the charm libraries are important for the charm and which are secondary.

Relation databags should not be loaded at charm library initialisation time, but if they are, the library should catch exceptions arising from `ops.Relation.load()`. Likewise, `.is_ready` should catch exceptions arising from loading and parsing the databags.

Exceptions can and should be used to report incorrect initialization (e.g. wrong relation name), or transient errors (hook command unexpectedly erroring out).

[Rationale](#handle-bad-remote-data-1)

#### Provide `.is_ready`

The charm library must provide an API that quickly determines if the endpoint is "ready" for a particular purpose. Accessing `is_ready` must be free from side effects, must not raise exceptions and the return value must be `False` in these cases:

* the relevant databag is empty, when appropriate
* the relevant databag could not be parsed
* the library evaluated the databag and determines that it's logically "not ready"

The specific shape of the API varies, here are some common examples:

* simple requirer: the `.is_ready` property on the charm library object
* app provider: a method with one argument `.is_ready(relation: ops.Relation)`
* per-unit provider: a method with two arguments `.is_ready(relation, remote_unit)`
* an attribute per function: `.is_upstream_ready` and `.is_direct_ready`
* an attribute per state: `.is_request_ready` and `.is_acknowledgement_ready`

Note that this method/property doesn't provide additional information about what's wrong with the relation. See [Advances status](#advanced-status) below.

[Rationale](#provide-.is_ready)

#### Advanced status

Charm libraries authors are advised to provide some API that reports advanced status of the wrapped endpoint. It's reasonable for the unit to go into a waiting, blocked or degraded state on "bad" relation data. Given that `.is_ready` only returns `True` or `False` during normal operation and doesn't raise extensions, some API is needed to report the details of the current error state.

This specification doesn't set out the shape of the advanced status API, because the charming community has put forward competing proposals. Some charms use hardcoded constants, others callbacks, and yet others `.validate_foo()` methods that raise exceptions.

Here's an example unit status showing the message elements decided by the charm and by the charm library:

`Waiting(ingress not ready: FDQN is missing)`

`charm --^^^^^^^^^^^^^^^^^`
`charm library -------------^^^^^^^^^^^^^^^`

Recall that if the databag is completely "against the rules" (e.g. wrong data type under the existing key), there should still be a way for the charm to decide what status to report. Missing fields should always be accepted, and charm object initialisation should not crash on bad (yet legal) data. This leaves a well-defined area for the advanced status: logical validation failures:

- relation is "not ready" until data is received
- failed to parse the dartabag (e.g. not JSON)
- a field is missing, and that's "bad"
- the value of a necessary field is out of range
- the value of the URL field contains "bad" element

At the same time, the charming community doesn't currently have a single standard for such API, or a standard to expose the detailed errors.

Following attempts deserve mention here:

- Rich Status API and data available via `status-detail` action
- Relation data via `show-config` action

There are also other, related efforts:

- `jhack sitrep`
- Juju Doctor

[Rationale](#advanced-status-1)

### Testing

Charm library authors must include the tests that validate the charm library conformance to the requirements in this specification. Documentation and code comments are great, but may get out of sync. Therefore a small but comprehensive set of tests is required. Consider writing these tests in a way that reduces churn, as that would both allow the test to survive interface evolution and be clear enough to the future developer who runs `git blame`.

The ultimate goal is to prevent accidental introduction of breaking changes.

**Unit tests capture must interface evolution**

One of the core requirements is for each interface version to be accompanied by a set of test vectors, that is databag snapshots representing all meaningful states of the relation and covering all defined fields and value ranges.

When the interface is developed, the new version is unit-tested against both **new and old test vectors**, going all the way back to the first version of the interface.

Thus, if a unit test fails and needs to be changed, the developer is alerted, and it's their explicit decision that a certain old data is now interpreted in this new way.

**Unit tests that capture charm-facing API evolution**

The unit tests also capture the evolution of the charm library API, following the general best practice for Python API contracts. This specification doesn't mandate anything specific, but suggests following Python conventions around deprecation, argument validation, value and type coercion, defaults and error reporting. The unit tests should cover these.

#### Fixed field types

Given a hypothetical field definition like:

| number: float | int | MISSING = MISSING |
| :---- |

A set of test vectors and tests could look like:

| V1_FLOAT = {"number": 42.1}
V1_INT = {"number": 42}
V1_MISSING = {}

def test_field_types():
    Data.model_validate(V1_FLOAT)
    Data.model_validate(V1_INT)
    Data.model_validate(V1_MISSING)
*# Note that Pydantic coerces False to 0 and "42" to 42*
@pytest.mark.parametrize("bad_value", ["str", [], {}, None])
def test_invalid_field_types(bad_value: Any):
    with pytest.raises(ValueError):
        Data.model_validate({"number": bad_value}) |
| :---- |

#### No mandatory fields

| V1_DATABAG = {"name": "aa", "surname": "bb"}
@pytest.mark.parametrize("field_to_remove", ["name", "surname"])
def test_missing_fields(field_to_remove):
    data = {**V1_DATABAG}
    del data[field_to_remove]
    assert DataV2.model_validate(data) |
| :---- |

#### No field reuse

Charm library unit tests must contain test vectors from the old versions of the interface. For example, suppose that the field `surname` was removed in v2, then a good unit test could be:

| V1_DATABAG = {"name": "a name", "surname": "bb"}

def test_removed_fields():
    assert DataV2.model_validate(V1_DATABAG).name == "a name"
    assert "surname" not in DataV2.model_fields  *# Removed in V2*

    *# alternatively*
    assert DataV2.model_validate(V1_DATABAG).model_dump == {"name": "a name"} |
| :---- |

Or a state transition test:

| *# dummy charm*
def _on_relation_changed(self, event: ops.RelationChangedEvent):
    data = event.relation.load(lib.DataV2, event.app)
    assert data.name == "aa"

*# test*
data = {"name": '"aa"', "surname": '"bb"'}
rel = testing.Relation('db', remote_app_data=data)
state_in = testing.State(leader=True, relations={rel})
ctx.run(ctx.on.relation_changed(rel), state_in) |
| :---- |

#### Collections

If the charm library filters collections, a test should be added that codifies the expectations on the Python (charm) side.

| DATABAG = {"foos": [
    {"foo": "a"},
    {"strange-data": "bar"},
    {"foo": "b", "new-field": "d"}
]}
def test_foos():
    foos_seen_by_charm = charm_lib.parse(DATABAG).foos
    assert charm_sees = {"a", "b"} |
| :---- |

#### URLs and URIs

| @pytest.mark.parametrize("bad_url", [
    "ftp://an.example",        *# unsupported scheme*
    "https://1.1.1.1",         *# hostnames only*
    "http://user@an.example",  *# credentials not allowed*
    "http://an.example/#bar",  *# fragment not allowed*
])
def test_bad_url_field_values(bad_url: str):
    with pytest.raises(ValueError):
        SomeData(url_field=bad_url)

@pytest.mark.parametrize("good_url", [
    "http://an.example",
    "https://an.example",
    "http://an.example/some/path",
    "http://an.example/some/path?some=query",
])
def test_good_url_field_values(good_url: str)
    SomeData(url_field=good_url) |
| :---- |

#### Secret content schema

The `ops` library doesn't provide helpers for typed secret content (as of version 3.5.2). It is envisioned that the charm libraries will resolve the secret content to a typed object on demand, taking into account relation specifics: secret id specified in the databag or possibly a local label; and which revision should be fetched, current or latest.

A good test coverage would include:

* obsolete and deprecated fields
* current fields with simple values
* fields with structured values, if any
* secret revisions

Ideally, the charm library comes with a set of state transition tests that utilise a dummy charm that shows how the charm library should be used and validate charm library API behaviour against a fixed set of secret content.

The state transition tests could follow this shape:

| @pytest.mark.parametrize("secret_content, status", [
    (GOOD_SECRET_CONTENT, ops.ActiveStatus()),
    (BAD_SECRET_CONTENT, ops.WaitingStatus("...")),
])
def test_secret_content(secret_content: dict[str, Any], status):
    ...
    state_out = ctx.run(
        ctx.on.relation_changed(relation=rel, remote_unit=1), state_in)

    assert state_out.unit_status == status |
| :---- |

[Full test code](https://github.com/dimaqq/op083-samples/blob/main/test_secret_content.py)

Alternatively, the same could be achieved with a set of pure unit tests:

| GOOD_SECRET_CONTENT = {"secret_thing": "foo", "some_future_field": "42"}
BAD_SECRET_CONTENT = {"unknown_field": "42"}
DATABAG = {"server_uri": '"secret://42"'}

def test_good_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("charm_lib._load_secret", GOOD_SECRET_CONTENT)
    charm_lib.parse(DATABAG)
    assert charm_lib.get_secret_thing() == "foo"

def test_bad_secret():
    monkeypatch.setattr("charm_lib._load_secret", BAD_SECRET_CONTENT)
    charm_lib.parse(DATABAG)
    with pytest.raises(SomeCharmLibError):
        charm_lib.get_secret_thing() |
| :---- |

#### Handle bad remote data

| *# dummy charm*
def __init__(self, framework):
    foo = FooRequirer(self, relation="foo")
    assert not foo.is_ready

*# test*
data = {"bad": '"data"', "weird": "[{}, {}]"}
rel = testing.Relation("foo", remote_app_data=data)
state_in = testing.State(relations={rel})
ctx.run(ctx.on.relation_changed(rel), state_in) |
| :---- |

#### Provide .is_ready

| *# dummy charm*
def __init__(self, framework):
    foo = FooRequirer(self, relation="foo")
    assert foo.is_ready

*# test*
data = {"good": '"value"', "some-future-thing": '"sss"'}
rel = testing.Relation("foo", remote_app_data=data)
state_in = testing.State(relations={rel})
ctx.run(ctx.on.relation_changed(rel), state_in) |
| :---- |

#### Advanced status

Suppose that the requirer expects a domain name in the databag under the `host` key. The requirement to provide advanced status API is ultimately for the deployed application to be able to express why the unit shows the waiting (or blocked) status. A comprehensive test may look like this:

| *# dummy charm*
def __init__(self, framework):
    self.foo = FooRequirer(self, relation="foo")
    ...

def _on_relation_changed(self, event: ops.RelationChangedEvent):
    if not self.foo.is_ready:
        self.unit.status = ops.WaitingStatus(self.foo.rich_status)
    try:
        host = self.foo.get_hostname()
        use(host)
    except SomeException as e:
        self.unit.status = ops.BlockedStatus(str(e))

*# test*
data = {"host": '"fe80::1"'}
rel = testing.Relation("foo", remote_app_data=data)
state_in = testing.State(relations={rel})
state_out = ctx.run(ctx.on.relation_changed(rel), state_in)
assert state_out.unit_status == ops.testing.BlockedStatus(
    "foo not ready: host must be a domain name"
) |
| :---- |

### Interface upgrades

**Each product** must define the following rules:

- what can and cannot be upgraded
- what track to upgrade to (one just vs many steps)
- which side of the relation needs to go first

**Field additions** can be done in the charm library minor version bumps, which can be included in the current product track.

**Field removals** should be done in the charm library major version bumps, being effecting in the next product track.

Concretely this means that version N sends and/or parses:

| foo_url: str | MISSING |
| :---- |

Intermediate release sends and/or parses:

| foo_url: str | MISSING
foo_url_set: set[str] | MISSING |
| :---- |

Version N+1 sends and/or parses:

| foo_url_set: set[str] | MISSING |
| :---- |

Charmers are encouraged to upgrade interfaces with some overlap.

One option could be to require the Juju user to first upgrade each application to the latest on their respective track, and only then switch tracks. Then the published charm versions would look like:

* Year 2024 LTS track on version N
* Year 2024 LTS track, "last" release supports versions N and N+1
* Year 2026 LTS track on version N+1

Another option is to introduce a deliberate transition track. Then charm versions would look like:

* Year 2024 LTS track on version N
* Year 2026 LTS track supports versions N and N+1
* Year 2028 LTS track on version N+1

This specification does not prescribe the cadence for major version bumps as such.

The expectation is for product teams to establish and publish the support windows for their products and upgrade rules for the interfaces they use. Pragmatically, with very few exceptions, breaking changes must not land into an existing track on Charm Hub.

## Further Information

### Previous work and references

[Analysis of versions of popular interfaces](https://docs.google.com/document/d/1YwriXR3eO_7PbdDJmLhCc8mERNKah46pQSj4jDe_Zqo/edit?tab=t.0)
[OB068 - Charm interface versioning](https://docs.google.com/document/d/1cUj0_-6CR_L_9R2zrm5gBW0Wqpnuhobr5phTcSAaPos/edit?tab=t.0) (rejected earlier effort)
[DA147 - UX of Statuses](https://docs.google.com/document/d/1SV11ct-flQkc5BOYOeXgmPeglL8bVs-mDVkGjG20K48/edit?tab=t.0) and [DA161- Implementation of Advanced Statuses](https://docs.google.com/document/d/1Yg7w7N-S1STbluk3SttZCQx1waZW_e_yOuKWeyahy20/edit?tab=t.0)
[DA174 - Error Propagation on Data Interfaces](https://docs.google.com/document/d/1YIRE2XP_xILoec6hOPOPdsiIJPcFqzI7JA-mEw1XEw4/edit?tab=t.0)
[Should charms implement a `show-config` action?](https://discourse.charmhub.io/t/should-charms-implement-a-show-config-action/19609)
[Compound status tree representation: a deep dive into a little `jhack` utility - charm - Charmhub](https://discourse.charmhub.io/t/compound-status-tree-representation-a-deep-dive-into-a-little-jhack-utility/14332)
[jhack/utils/sitrep.py](https://github.com/canonical/jhack/blob/main/jhack/utils/sitrep.py) (advanced status via `jhack`)
[Juju Doctor - why does Juju need it? - juju - Charmhub](https://discourse.charmhub.io/t/juju-doctor-why-does-juju-need-it/17748)
[Introducing `jhack list-endpoints` - charm - Charmhub](https://discourse.charmhub.io/t/introducing-jhack-list-endpoints/11763)
[OpenStack upgrade -- charm-guide 0.0.1.dev818 documentation](https://docs.openstack.org/charm-guide/latest/admin/upgrades/openstack.html)

## Rejected alternatives

### Version specification

[TE175 - Charm interface data bag versioning](https://docs.google.com/document/d/1Zt87OQYsmDzutX9qc5vma7uaVRYmiGzA6xdw4CzUQrc/edit?tab=t.0) specifies sender indicating a single, integer version number in the databags they populate (and possibly to blank databags too).

While useful, this falls apart in this scenario:

- Application A was built in 2022, when versions `1` and `2` existed
- Application B was built in 2026, when versions `6` and `7` were used
- When related, App A can't do anything meaningful with a value like `6` or `7`.

Additionally, a singular version doesn't help if the interface is complex, where the charm is ultimately interested in the subset of the fields. One example is `data_interfaces` where the databag may contain half a dozen fields.

This specification doesn't invalidate TE175 though. The version stamp can still be used for debug or analysis of a live deployment. This specification advises that the unit (charm or charm library code) should most likely not act on the stamped version.

### Version negotiation

[OB068 - Charm interface versioning](https://docs.google.com/document/d/1cUj0_-6CR_L_9R2zrm5gBW0Wqpnuhobr5phTcSAaPos/edit?tab=t.0) was essentially rejected at the Göteborg sprint.

Primary reasons were: ping-pong overhead, unclear support window and complexity.

### Separate interfaces

Some charms have transitions from one to another named interface, see for example [PostgreSQL K8s charm modern and legacy interfaces](https://canonical-charmed-postgresql-k8s.readthedocs-hosted.com/14/explanation/interfaces-and-endpoints/index.html?channel=14/stable). While that remains an option and in a sense rather understandable, such approach suffers from several downsides:

- unclear upgrade path for the Juju user when both ends of the relation are upgraded
- all the functionality the interface represents is broken at once, while the desire behind this spec was to isolate individual functions.

### Interface versions in charm metadata

There was a discussion about exposing the contract each side of the relation promises to fulfill to Juju and having Juju decide whether any given relation blocks the application upgrade.

Doing so would require charm libraries to be annotated with the interface version the data is published on and a set or a range of interface versions understood. This information would then percolate into charm metadata, for each relation. Something outside of the charm (Juju itself, or a scriptlet-based mechanism) would then example the proposed application upgrade (declared version info from the metadata of the currently deployed application, declared version info from the metadata of the proposed application version from charmhub, current active relations, and current version info from the metadata of the relation counterparts) and decide whether the application upgrade is allowed to proceed.

The solution has not been defined yet, and work on this is too far ahead to consider in this spec.
