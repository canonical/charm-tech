# Charm Tech Python style guide

This is the Python code style we're converging on across the projects maintained
by the Charm Tech team. For documentation and docstring style (which applies to
all languages), see [docs.md](./docs.md).

We use Ruff for formatting, and run our code through the Pyright type checker. We
try to follow [PEP 8](https://peps.python.org/pep-0008/), the official Python
style guide. However, PEP 8 is fairly low-level, so in addition we've come up
with the following style guidelines. See [Tooling configuration](#tooling-configuration)
below for the standardised lint/format/type-check config that enforces much of this.

New code should follow these guidelines, unless there's a good reason not to.
Sometimes existing code doesn't follow these, but we're happy for it to be
updated to do so (either all at once, or as you change nearby code).

Of course, this is just a start! We add to this list as things come up in code
review; this list reflects our team decisions.

## Import modules, not objects

"Namespaces are one honking great idea -- let's do more of those!"

When reading code, it's significantly easier to tell where a name came from if it
is prefixed with the package name.

An exception is names from `typing` -- type annotations get too verbose if these
all have to be prefixed with `typing.`.

**Don't:**

```python
from ops import CharmBase, PebbleReadyEvent
from subprocess import run

class MyCharm(CharmBase):
    def _pebble_ready(self, event: PebbleReadyEvent):
        run(['echo', 'foo'])
```

**Do:**

```python
import ops
import subprocess

class MyCharm(ops.CharmBase):
    def _pebble_ready(self, event: ops.PebbleReadyEvent):
        subprocess.run(['echo', 'foo'])

# However, "from typing import Foo" is okay to avoid verbosity
from typing import Optional, Tuple
counts: Optional[Tuple[str, int]]
```

## Use relative imports inside a package

When writing code inside a package (a directory containing an `__init__.py`
file), use relative imports with a `.` instead of absolute imports. For example,
within the `ops` package:

**Don't:**

```python
from ops import charm
```

**Do:**

```python
from . import charm

# Or, if you need to avoid adding the public name "charm" to the namespace:

from . import charm as _charm
```

## Avoid nested comprehensions and generator expressions

"Flat is better than nested."

**Don't:**

```python
units = [unit for app in model.apps for unit in app.units]

for current in (
    current for current in pebble.ServiceStatus if current is not pebble.ServiceStatus.ACTIVE
):
    ...
```

**Do:**

```python
units = []
for app in model.apps:
    for unit in app.units:
        units.append(unit)

for status in pebble.ServiceStatus:
    if status is pebble.ServiceStatus.ACTIVE:
        continue
    ...
```

## Compare enum values by identity

The [Enum HOWTO](https://docs.python.org/3/howto/enum.html#comparisons) says that
"enum values are compared by identity", so we've decided to follow that. Note
that this decision applies to regular `enum.Enum` values, not to `enum.IntEnum`
or `enum.StrEnum` (the latter is only available from Python 3.11).

**Don't:**

```python
if status == pebble.ServiceStatus.ACTIVE:
    print('Running')

if status != pebble.ServiceStatus.ACTIVE:
    print('Stopped')
```

**Do:**

```python
if status is pebble.ServiceStatus.ACTIVE:
    print('Running')

if status is not pebble.ServiceStatus.ACTIVE:
    print('Stopped')
```

## Tooling configuration

Our repos (operator, jubilant, pytest-jubilant, charmhub-listing-review,
charmlibs) have converged on a common lint/format/type-check configuration. The
aim is consistency, not lock-step: a project can deviate where it has a good
reason, but this is the default.

The decisions:

- **Line length is 99.**
- **Single quotes** for strings (`ruff format` `quote-style = "single"`).
- **Type-checking is `strict`** (pyright), with `reportPrivateUsage = false`
  (things that are effectively public still need to be private to users) and
  `reportUnnecessaryTypeIgnoreComment = "error"`.
- **Set `target-version` / `pythonVersion` to the project's actual minimum
  supported Python** — don't leave it stale (several repos disagreed with their
  own `requires-python`).
- **Coverage runs with `branch = true`.**
- The agreed **ruff rule set** is: `F`, `E`, `W`, `I001`, `N`, `A`, `CPY`, `UP`,
  `YTT`, `S`, `B`, `SIM`, `RUF`, `PERF`, `D`, `FA`, `TC` — ignoring `TC001`–`TC003`
  (don't force imports into type-checking blocks), `S101` (`assert` is fine), and
  `D105`/`D107` (no docstrings required for magic/`__init__` methods). Tests
  additionally drop `D` and the hard-coded-secret checks (`S101`/`S105`/`S106`).

The ready-to-copy `pyproject.toml` config itself will be distributed via the
shared-template mechanism (see canonical/charm-tech#6); this section records
*what* we standardised on.
