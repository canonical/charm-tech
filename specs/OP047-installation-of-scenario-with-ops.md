# OP047 — Installation of Scenario with ops

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2024-07-01 |

## Abstract

The Scenario framework is to be promoted as the recommended framework for writing charm unit tests. To facilitate this, the Scenario functionality should be optionally installed with ops.

## Rationale

The Scenario framework provides a superior mechanism for charm unit tests to the Harness framework currently bundled with ops. In particular, there is a clear arrange/act/assert pattern, immutable Juju 'state' that doesn't trigger code during setup, and deferred event handling is handled in a cleaner way than possible with Harness (as are multiple events). In general, the test author is pushed towards thinking about the charm at the right level of abstraction (handling an event).

The Scenario functionality should be "first level" in the same way that Harness is - rather than a separate, optional-feeling tool that is separately maintained and installed.

Two minor goals are also covered in this spec:

* Retiring the name "Scenario" publicly - Canonical wants to reserve the name for different future use in Juju.
* The charm testing framework(s) should not be bundled into the packed charm.

## Specification

### Installation

Charmers will install Scenario using the "optional dependencies" (or "extra provides") packaging functionality that allows installing optional extra features of a package via pip (or other standards compliant package managers), and their dependencies.

```
# Both of these get ops and Harness
pip install ops
pip install ops[harness]

# These both get ops, the legacy Harness, and Scenario
pip install ops[testing]
pip install ops[testing,harness]

# Later (likely ops 3.0):
pip install ops  # only ops
pip install ops[harness]  # ops and Harness
pip install ops[testing]  # ops and Scenario
pip install ops[testing,harness]  # ops, Scenario, and Harness
```

This is trivially implemented in the ops `pyproject.toml`:

```
[project.optional-dependencies]
harness = []
testing = ["ops-scenario==7.0.0"]
```

### Usage

The package will be available in the ops.testing namespace, as Harness is now. This means that tests that use Harness remain unchanged, and tests that use Scenario will resemble this:

```py
from ops import testing

def test_case():
    context = testing.Context(MyCharm)
    state_in = testing.State(...)
    state_out = context.run(context.on.install(), state=state_in)
    assert state_out...
```

*Note the absence of the name "Scenario" in the above code (it is still visible under the hood, for example in class repr, but not in user-facing code).*

This will be implemented with a simple import (see the alternatives section below for information about why this isn't using a package namespace or other such mechanism).

```py
# In ops/testing.py

try:
    from scenario import *
except ImportError:
    # ops[testing] is not installed
    pass
```

### Repository

The Scenario code will be added to the canonical/operator GitHub repository (copying all of the history), in a new top-level "testing" folder, using the ["src layout"](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) style.

```
# Previously in canonical/ops-scenario
README.md
scenario/
  __init__.py
  capture_events.py
  consistency_checker.py
  context.py
  logger.py
  mocking.py
  ops_main_mock.py
  runtime.py
  state.py
tests/
  helpers.py
  ...
  test_e2e/
    ...
tox.ini

# In canonical/operator (bold is new)
CHANGES.md
CODE_OF_CONDUCT.md
docs/
  ...
HACKING.md
LICENSE.txt
MANIFEST.in
ops/
  _private/
    __init__.py
    _harness.py
    timeconv.py
    yaml.py
  __init__.py
  charm.py
  framework.py
  jujuversion.py
  log.py
  main.py
  model.py
  pebble.py
  storage.py
  testing.py  # Exposes ops._private.harness and (optionally) ops-scenario
  version.py
testing/
  src/scenario/
    __init__.py
    capture_events.py
    consistency_checker.py
    context.py
    logger.py
    mocking.py
    ops_main_mock.py
    runtime.py
    state.py
  tests/
    helpers.py
    ...
    test_e2e/
      ...
  tox.ini  # Tests only Scenario
pyproject.toml
README.md
SECURITY.md
test/
  ...
tox.ini  # Tests all of ops, Harness, Scenario
```

At some point (likely ops 3.0), ops/testing.py will be moved to a new top-level "harness" folder, similar to the "testing" one.

The canonical/ops-scenario repository will be archived.

This 'mono-repo' approach provides small administration benefits, and encourages contributors to consider the impact on the testing framework when proposing changes to the main ops code. It's also possible to contribute smaller pull requests that have both core ops and testing framework changes in the same request.

### Releases & Documentation

The main ops package will have a compatibility matrix defined for the ops-scenario package, which will be tested with each PR and released in the same way as compatibility with critical charms. As an optional feature of the "ops" package, "ops[testing]" will have a specific range of ops-scenario versions that can be installed, and the package manager (e.g. pip) will select the most appropriate one (almost always the most recent). Charms are expected to specify "ops[testing"]<3" (or similar variants) in their testing dependencies, and have tooling that automatically pins that to specific versions.

The "ops" package on PyPI will include the core ops code, and also (for backwards compatibility) the Harness code, but will not include Scenario code (that will be in the "ops-scenario" package, like now). In the future, most likely as part of an ops 3.x release, the "ops" package will only have the core ops code, and Harness will be installed from a new "ops-harness" package.

Installing the old "ops-scenario" package with ops will work, but no guarantee is made that this will continue to be the case. Releases of the ops-scenario package are not tied to the cadence of releases of the ops package.

Documentation for ops[testing] will be found in the same places as for ops:

* Tutorials: [https://juju.is/docs/sdk/tutorials](https://juju.is/docs/sdk/tutorials)
* How-tos: [https://juju.is/docs/sdk/how-to](https://juju.is/docs/sdk/how-to) - in the "Develop" section, as part of each guide where writing tests is included (the Harness sections of the guides will be phased out over time)
* Reference: [https://ops.readthedocs.io/en/latest/](https://ops.readthedocs.io/en/latest/) - in the existing "ops.testing module" section (we may wish to split "ops", "ops.pebble", and "ops.testing" into separate pages at some point, but that can be done separately)
* Explanation: [https://juju.is/docs/sdk/explanation](https://juju.is/docs/sdk/explanation)

## Further Information

### Alternatives

#### Namespace package, local Harness

A [namespace package](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/) allows installation of multiple packages into a common namespace without explicit cooperation. If backwards compatibility was not an option, this would likely be the cleanest option - we could specify `ops.testing` as a namespace package, and allow installing Scenario into that namespace. However, the namespace package cannot have an `__init__.py` file.

```py
# directory layout
ops/
  __init__.py  # <- ops needs this, so "ops" can't be the namespace package
  main.py  # and all the others except testing.py
  testing/  # new folder
    # no __init__ makes this a namespace package
    harness.py  # optionally installed from a separate distribution package
    scenario/  # installed from a separate distribution package
      __init__.py  # and all the others
```

However, we cannot cleanly achieve the goal of having the Scenario classes available from the top-level ops.testing namespace - and, more significantly, the Harness class moves from the top-level ops.testing namespace as well.

The only way around this would be for the `ops/__init__.py` file to import the various classes and insert them into `ops.testing` - and at this point, there's minimal benefit over simply doing that with a regular installation. In particular, we manage both ops and Scenario, and are not intending to open up the `ops.testing` namespace to third-party packages, so do not need to support adding to the namespace without cooperation.

### Namespace package, separate Harness

A similar method as above would be already moving the Harness functionality into a separate ops-harness package (which could initially be a required dependency for ops). It has the same drawbacks as the above.

### Legacy namespace package

[pkgutil allows extending a logical package over multiple directories](https://docs.python.org/3/library/pkgutil.html#pkgutil.extend_path). This provides similar functionality to a namespace package, but is considered deprecated and so best avoided ([PEP420](https://peps.python.org/pep-0402/#the-problem) goes into detail about the limitations of the approach - these are not generally an issue in our case, but we also don't gain anything by using this feature).

### Legacy setuptools package

[setuptools also has support for declaring namespaces](https://setuptools.pypa.io/en/latest/pkg_resources.html#namespace-package-support). Similar to the above, this is no longer recommended, does not bring any benefits in our case, and would additionally tie us to using setuptools as the build backend.
