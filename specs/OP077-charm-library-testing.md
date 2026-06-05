# OP077 — Charm library testing

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 13 Nov 2025 |

## Abstract

This spec details how charm libraries should provide mock relation data for use in charm tests. Each charm library will have a parallel testing package, which charms should depend on as `charmlibs-<libname>[testing]`, and import as `from charmlibs import <libname>_testing`. Testing packages must provide two functions, `relation_for_provider` and `relation_for_requirer`, returning `ops.testing.Relation` objects, to  be used in tests for provider and requirer charms respectively.

## Rationale

Charmers have requested a standard way for charm libraries to provide test mocks for a long time, because they shouldn't need to know about charm library internals when writing charm tests.

This is particularly relevant for interface libraries, because the charm's relation data needs to be specified for relevant state-transition tests. Ideally, an interface library would abstract away the charm's need to know about the relation databag format, but currently charms need to know enough about the library's expectations for the relation databag to set up `ops.testing.Relation` objects for their tests. A natural solution to this problem is for interface libraries to distribute mock databags for testing purposes.

The methods for distributing this mock data can be extended to distributing more sophisticated test doubles if necessary.

## Specification

Charm interface library authors should consider the testing needs of charmers and define mock relation data that satisfies these needs. If necessary, they may also distribute test doubles of the library's public API objects to facilitate unit testing.

This specification outlines:

1. How this code and data should be distributed:  in a separate package for each library. e.g. `charmlibs.interfaces.foo` will have a separate `charmlibs.interfaces.foo_testing` distribution and import package.
2. What should be distributed: functions charms can use to populate the remote relation data in their tests, and (if necessary) test doubles to eliminate library side effects while testing. This approach aims to provide a consistent testing UX for most charms and libraries. Where it's not a good fit, libraries may judiciously provide alternative functionality to achieve a good testing UX.

### A. How to distribute testing content

The testing code - mocks, data, etc. should not be distributed with the library itself when it is installed at runtime and packaged into charms. Each library that provides testing content should distribute it in a separate package.

An example of what this might look like for the `tls_certificates` library can be seen in [this draft PR](https://github.com/canonical/charmlibs/pull/331/changes), which also shows the `charmlibs` infrastructure changes required to support this.

#### Charm UX

Charms shouldn't depend on the testing distribution package directly.  Instead, they should depend on the `testing` extra of the charm library. They should depend on the version of the charm library that they require, and the charm library's extra will take care of versioning for the testing package. This is what the dependency UX would look like for a charm (with `ops` included just for illustrative purposes):

```
# Charm's pyproject.toml
[project]
# ...
dependencies = [
    "ops>=3.4.0,<4",
    "charmlibs-foo>=1.0,<2",
]

[dependency-groups]
dev = [
    "ops[testing]",
    "charmlibs-foo[testing]",
]
```

In their tests, the charm would then import any testing packages like this:

```py
from charmlibs import foo_testing
from charmlibs.interfaces import bar_testing
```

#### Package naming

* The package should have the distribution package name `<namespace>-<name>-testing`, e.g.
  * `charmlibs-pathops-testing`
  * `charmlibs-interfaces-tls-certificates-testing`
* The package should install the import package `<namespace>.<name>_testing`, e.g.
  *  `charmlibs.pathops_testing`
  * `charmlibs.interfaces.tls_certificates_testing`

#### Package versioning

The charm library and its testing package should depend on exact versions of each other. Being able to assume an exact version of the charm library makes the testing package's job much easier.

For simplicity, the testing package's version should always be identical to the charm library's version. This means its initial release version should be whatever the current version of the charm library is, and it means that every release of the charm library or testing package implies releasing the other.

#### Charmlibs monorepo

##### Code layout

The testing package will be defined under the top-level directory for the library in the `charmlibs` monorepo, under the `testing` sub-directory.

```
interfaces/foo
  src/charmlibs/interfaces/foo/
    __init__.py
    py.typed
  testing/
    src/charmlibs/interfaces/foo_testing/
      __init__.py
      py.typed
     tests/
       unit/
    pyproject.toml
   tests/
     unit/
     functional/
     integration/
   pyproject.toml
```

The library and its testing package will specify each other's exact versions in their `pyproject.toml` files, and use `uv.sources` to install the local version for development and testing.

```py
# foo/pyproject.toml

[project.optional-dependencies]
testing = ["charmlibs-foo-testing==1.2.3"]

[tool.uv.sources]
charmlibs-foo-testing = { path = "testing" , editable = true }

# to use the same version in foo's unit tests
[dependency-groups]
unit = [
    "charmlibs-foo[testing]",
]
```

```py
# foo/testing/pyproject.toml

[project]
dependencies = [
    "charmlibs-foo==1.2.3",
]

[tool.uv.sources]
charmlibs-foo = { path = ".." , editable = true }
```

##### Publication infrastructure

The `charmlibs` monorepo CI will take care of ensuring that the library and its testing package always match. With this check in place, publishing the `<foo>_testing` package will always be required whenever the `<foo>` library is published (the current CI automatically publishes libraries whenever their version changes).

##### Testing infrastructure

Infra will be tweaked to detect testing packages. If a package has a testing package, tests for it will always be run in CI when the regular package tests would be run too. Additionally, testing packages will be validated to provide the two required functions, that they are callable with just the endpoint name provided positionally, and that they return an `ops.testing.Relation` object.

 For a library to use its testing package in its own (e.g. `unit`) tests, it can add the distribution package name to its `unit` dependency group (e.g. `unit = ['tls-certificates-testing']`).

#### Rejected alternatives for distribution

##### 1. Distributing the test data in a `testing` submodule of the library

* We shouldn't add runtime or packing time overhead to charms.
* Introduces the potential for errors at runtime if the `testing` module is erroneously imported.
* `from charmlibs import foo.testing` is an error, so the import syntax doesn't end up being very nice for users - e.g. `from charmibs.foo import testing as foo_testing`

##### 2. Shimming the `<foo>_testing` package into the `<foo>` namespace

* Per the last bullet point above, this doesn't lead to a very nice import experience.
* This complicates the life of the library code with special modules that shouldn't be imported at runtime, or conditional imports, increasing the surface area for making mistakes, and potentially confusing type checkers

### B. What to distribute

Libraries should provide mock relation data, as `ops.testing.Relation` objects. This section details this API. Libraries may also provide additional helper functions/constants, or test doubles for use in patching, as required to provide a clean testing experience for charmers.

An example of what this might look like for the `tls_certificates` library can be seen in [this draft PR](https://github.com/canonical/charmlibs/pull/331/changes), which also shows the `charmlibs` infrastructure changes required to support this.

#### Testing API

Libraries' testing packages must provide two main entrypoint functions, for provider charms and requirer charms to use in their unit tests. These must be named `relation_for_provider` and `relation_for_requirer` respectively, and their job is to return an `ops.testing.Relation` object with the local and remote data populated based on arguments provided by the charm tests, with sensible defaults. The defaults should represent a typical charm's use, rather than the empty case.

* Their first argument should be `endpoint`, the endpoint name (which may have a default value if the library uses a default endpoint name), which must be able to be passed positionally.
* Any number of additional arguments are permitted, but they should all be optional. These should typically align with arguments to the library objects, but may diverge for testing convenience.
* If the library follows a request-response pattern, the functions should accept a boolean `response` argument to specify whether the response side should be filled in. This should default to `True`.

Additional helper functions or constants may be provided by the testing package as needed. For example, if the interface library transparently handles multiple relations on the same endpoint, it might be useful to provide a helper like `default_relations_for_provider(endpoint)` which returns a collection of relation objects. Testing packages should recommend their intended default approach in the package documentation.

#### Types of relation conversations

Let's look at what relation conversations tend to look like. The counts reflect LLM analysis of the existing relation `README.md` files in the `charmlibs` repo today.

| Conversation type (count) | Charm A | Charm B |
| :---- | :---- | :---- |
| One way (28/65) | **Write** Done | *Wait* Read Done |
| Request-response (34/65) | **Write** *Wait* Read Done | *Wait* Read + **Write** Done |
| Two way (3/65) | **Write** *Wait* Read Done | **Write** *Wait* Read Done |
| Request-response-ack | **Write** *Wait* Read + **Write** Done | *Wait* Read + **Write** *Wait* Read Done |
| Ongoing conversation | **Write** *Wait* Read + **Write** *Wait* Read + **Write** *Wait* ... | *Wait* Read + **Write** *Wait* Read + **Write** *Wait* Read + **Write** ... |

From the three conversation types actually in use, we can see four unique conversational roles that a charm might play.

1. **Write**: (e.g. [certificate_transfer provider](https://github.com/canonical/charmlibs/blob/main/interfaces/certificate_transfer/src/charmlibs/interfaces/certificate_transfer/_certificate_transfer.py#L220))
   1. Haven't written yet: just set up an empty relation.
   2. Already written: call the testing library function like this: `relation_for_<role>(response=False)`.
2. *Wait*, Read: (e.g. [certificate_transfer requirer](https://github.com/canonical/charmlibs/blob/417a1b1b41bcd58ceec3b6b0484a1daa46921129/interfaces/certificate_transfer/src/charmlibs/interfaces/certificate_transfer/_certificate_transfer.py#L456))
   1. Nothing to read yet: just set up an empty relation.
   2. Something to read: call the testing library function: `relation_for_<role>(...)`.
3. **Write**, *Wait*, Read: (e.g. [tls-certificates requirer](https://github.com/canonical/charmlibs/blob/417a1b1b41bcd58ceec3b6b0484a1daa46921129/interfaces/tls-certificates/src/charmlibs/interfaces/tls_certificates/_tls_certificates.py#L1726))
   1. Haven't written yet: just set up an empty relation.
   2. Already written: call the testing library function like this: `relation_for_<role>(response=False)`.
   3. Something to read: call the testing library function: `relation_for_<role>(...)`.
4. *Wait*, Read, **Write**: (e.g. [tls-certificates provider](https://github.com/canonical/charmlibs/blob/417a1b1b41bcd58ceec3b6b0484a1daa46921129/interfaces/tls-certificates/src/charmlibs/interfaces/tls_certificates/_tls_certificates.py#L2874))
   1. Nothing to read yet: just set up an empty relation.
   2. Something to read: call the testing library function: `relation_for_<role>(..., response=False)`.
   3. Already written back: call the testing library function:
   4. `relation_for_<role>(...)`.

These roles in turn show a number of unique states that we might want to model in tests:

1. Initial empty relation, doesn't use the testing library.
2. Populate just the remote side for me: call the testing library method, with `response=False` if it's a request-response relation.
3. Both sides have written (implies request-response or two way): call the testing library with `response=True` (the default).

There's an extra consideration for this last case: the charm code under test likely wants to write to the databag, and will do so if the way it calls the library doesn't match what's in the databag. This often happens before reading the remote side of the databag.

In a request-response relation, the response may need to match what we wrote. For example, the TLS Certificates library expects the certificates in the response to match the private key used to sign the certificate requests. Care must be taken to ensure that the databag contents provided by the testing library match those written by the charm code in the test.

This may involve the testing library providing a mock that should be used to patch out some part of the real library during tests. Or it might involve instructions to patch the charm code that constructs the request. Testing packages should take care to design a UX that makes things easy for charms.

An example of what this might look like for the `tls_certificates` library can be seen in [this PR](https://github.com/canonical/charmlibs/pull/331/changes). Below we'll use examples from charm unit tests to sketch out what the testing UX might look like for the `certificate_transfer`, `ingress`, and `s3` interfaces.

##### Example: certificate_transfer

As a concrete example, consider [this test](https://github.com/canonical/opentelemetry-collector-operator/blob/3d151ab7e0d0baf2a52c08163a66c9d438c0658d/tests/unit/test_receive_ca_cert.py#L20) from `opentelemetry-collector` using the [certificate_transfer](https://charmhub.io/certificate-transfer-interface/libraries/certificate_transfer) library, testing that when certificates are provided to the charm from the library, the charm writes them all correctly to disk.  The issue is that the test needs to know not just the shape of the databag, but something about the format of the certificates in the databag.

```py
def test_ca_forwarded_over_rel_data(ctx, recv_ca_folder_path):
    # Relation 1
    cert1a = "-----BEGIN CERTIFICATE-----\n ... cert1a ... \n-----END CERTIFICATE-----"
    cert1b = "-----BEGIN CERTIFICATE-----\n ... cert1b ... \n-----END CERTIFICATE-----"
    # Relation 2
    cert2a = "-----BEGIN CERTIFICATE-----\n ... cert2a ... \n-----END CERTIFICATE-----"
    cert2b = "-----BEGIN CERTIFICATE-----\n ... cert2b ... \n-----END CERTIFICATE-----"

    # GIVEN the charm is related to a CA
    state = State(
        leader=True,
        relations=[
            Relation(
                "receive-ca-cert",
                remote_app_data={"certificates": json.dumps([cert1a, cert1b])},
            ),
            Relation(
                "receive-ca-cert",
                remote_app_data={"certificates": json.dumps([cert2a, cert2b])},
            ),
        ],
    )

    # WHEN any event is emitted
    with patch("integrations._add_alerts"):
        ctx.run(ctx.on.update_status(), state)

    # THEN recv_ca_cert-associated certs are present
    certs_dir = recv_ca_folder_path
    assert certs_dir.exists()
    certs = {file.read_text() for file in certs_dir.glob("*.crt")}
    assert certs == {cert1a, cert1b, cert2a, cert2b}
```

To achieve the same test coverage, the testing library could provide a way to make some certificates for use in testing (if this is likely to be required by other charm/library code), or just accept a collection of strings for the certificates to return. Using the approach proposed in this spec, the test would look something like this:

```py
from charmlibs.interfaces import certificate_transfer_testing

def test_ca_forwarded_over_rel_data(
    ctx, recv_ca_folder_path
):
    # this imagines that the testing API allows us to translate the test above 'as is'
    certs1 = certificate_transfer_testing.make_certs(..)
    rel1 = certificate_transfer_testing.relation_for_requirer(
        "receive-ca-cert", certs=certs1
    )
    certs2 = certificate_transfer_testing.make_certs(...)
    rel2 = certificate_transfer_testing.rel_for_requirer(
        "receive-ca-cert", certs=certs2
    )
    # make_certs is probably not the right level of abstraction for this testing package
    # instead helpers like this might make more sense:
    # rels = {*certificate_transfer_testing.relations_for_requirer(endpoint)}
    # certs = certificate_transfer_testing.certs_from_rels(*rels)

    # GIVEN the charm is related to a CA
    state = State(leader=True, relations=[rel1, rel2])

    # WHEN any event is emitted
    with patch("integrations._add_alerts"):
        ctx.run(ctx.on.update_status(), state)

    # THEN recv_ca_cert-associated certs are present
    assert recv_ca_folder_path.exists()
    written = sorted(
        file.read_text()
        for file
        in recv_ca_folder_path.glob("*.crt")
    )
    assert written == sorted((*certs1, *certs2))
```

##### Example: s3

 From `spark-history-server-k8s-operator`'s [tests/unit/conftest.py](https://github.com/canonical/spark-history-server-k8s-operator/blob/3/edge/tests/unit/conftest.py):

```py
@pytest.fixture
def s3_relation():
    """Provide fixture for the S3 relation."""
    relation = Relation(
        endpoint=S3,
        interface="s3",
        remote_app_name="s3-integrator",
    )
    relation_id = relation.id
    return replace(
        relation,
        local_app_data={"bucket": f"relation-{relation_id}"},
        remote_app_data={
            "access-key": "access-key",
            "bucket": "my-bucket",
            "data": f'{{"bucket": "relation-{relation_id}"}}',
            "endpoint": "https://s3.endpoint",
            "path": "spark-events",
            "secret-key": "secret-key",
            "tls-ca-chain": '["certificate"]',
        },
    )
```

Translating the example above would look something like:

```py
from charmlibs.interfaces import s3_testing

import charm  # src/charm.py

@pytest.fixture
def s3_relation():
    """Provide fixture for the S3 relation."""
    return s3_testing.relation_for_requirer(
        charm.S3,  # endpoint name from charm defined constant
        # parameters to for our local relation data
        bucket_name=charm.BUCKET_NAME,  # again charm defined
        # probably don't need to use any parameters for
        # what we want back
    )
```

##### Example: ingress

 From `spark-history-server-k8s-operator`'s [tests/unit/conftest.py](https://github.com/canonical/spark-history-server-k8s-operator/blob/3/edge/tests/unit/conftest.py):

```py
@pytest.fixture
def ingress_subdomain_relation():
    """Provide fixture for the ingress relation."""
    return Relation(
        endpoint=INGRESS,
        interface="ingress",
        remote_app_name="traefik-k8s",
        local_app_data={
            "model": '"spark"',
            "name": '"spark-history-server-k8s"',
            "port": "18080",
            "redirect-https": "false",
            "scheme": '"http"',
            "strip-prefix": "true",
        },
        remote_app_data={
            "ingress": '{"url": "http://spark-history-server-k8s.spark.deusebio.com"}'
        },
    )
```

Translating the example above would look something like:

```py
from charmlibs.interfaces import ingress_testing

import charm  # src/charm.py

@pytest.fixture
def ingress_subdomain_relation():
    """Provide fixture for the ingress relation."""
    return ingress_testing.relation_for_requirer(
        charm.INGRESS,  # endpoint name from charm defined constant
        # parameters to for our local relation data
        # could also be pulled from the charm code
        model='spark',
        name='spark-history-server-k8s',
        port=18080,
        # parameters for the remote relation data
        # if these are relevant for testing ...
        # could probably be left out of the API?
        ingress_domain='deusebio.com',
    )
```

#### Rejected alternatives

##### Databag constants

This would be fine for simple cases, but once you want to parametrize the mock remote data based on (e.g.) the local relation data, you need functions, and it would be better to have one convention rather than two. Additionally, functions that return fresh objects eliminate the risk of accidentally mutating state shared between tests.

##### Library provides individual databags (via functions)

This was the pitch before returning `Relation` objects. The problems are: probably you want to bundle getting the remote app and unit data - the `Relation` object bundles this naturally. You either have to make a bunch of separate calls when setting up your `Relation` for testing, or have functions that return both and also have some way of unpacking the bundled data into a `Relation` object. You also need to think about how to provide local data, relation name, etc to the function if that should be used in the mock databags.

##### Library provides tuples of databags

Well, a tuple of `(app databag, [list of unit databags])`. At this point you might want a custom type (e.g. lightweight named tuple) to make accessing app or unit data less ambiguous, which starts to make using a `Relation` object as the container more appealing.

###### Library provides a dict of ops.testing.Relation compatible kwargs

Pretty ok, but at this point we're so close to the `testing` API that we might as well use `testing.Relation` - and if we just want the databags, we can pull them out of the `Relation`.

##### Relation to relation API

We had the idea that the functions in the library would also take a `testing.Relation` as their argument, as this seemed like a natural way to bundle the endpoint name and any local app/unit data that should be taken into account. However, to populate the local relation data, the charm would likely need to be stepped through a series of events by scenario, which adds Harness-like complexity to the setup of the Scenario test. Declaring your state is cleaner if you just need to call a library provided testing function with the appropriate arguments instead.

##### Exposing library objects in a testing context

It would be quite nice to interact with the library's regular public API in a testing context, particularly for ensuring that what you're doing with the library makes sense from the other side. For example as a TLS certificates *provider*, being able to write something like  `assert tls_certificates_requirer.get_all_certificates() == my_certs`. However, this requires a whole new charm context and some under the hood scenario wiring that would probably be a bit too complicated and magical for right now. Charms could do this manually in their tests though, by setting up a dummy charm for the other side and shuffling their test's local databags over to its remote databags.
