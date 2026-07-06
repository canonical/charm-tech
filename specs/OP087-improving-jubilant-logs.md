# OP087 — Improving Jubilant logs

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 26 May 2026 |

## Abstract

This document specifies how Jubilant logs can be improved for Charmers. The proposal introduces a model for log handling in Jubilant and downstream users. It also reduces the amount of clutter in `juju.wait()` logs by introducing a new default log mode, a new message format for logging `app` status changes, the ability to redirect verbose logs into a file, and minor changes in `pytest-jubilant` to integrate well with the proposed Jubilant changes.

## Rationale

It was reported that Jubilant logs were too verbose and hard to read. Charmers wanted Jubilant to surface data that can help with investigating failure causes.

This feedback aligned with Charm Tech's view that Jubilant logs can be difficult to work through when debugging failed integration test cases. For example, Jubilant's `juju.wait()` method emits all changes in the Juju model under test, which contain information unrelated to the charm under test. See [Examples for current Jubilant logs verbosity](#examples-for-current-jubilant-logs-verbosity) for more information.

Therefore, this document proposes changes to Jubilant's default logs, aiming for a better developer experience, and allows granular controls for downstream users.

## Specification

### Goals

We'd strongly prefer not to change the API of `juju.wait()`. Our solution relies on the Python `logging` module, and doesn't update the API of any Jubilant components.

We also prefer not to make any major changes to `pytest-jubilant` implementation in this Spec. For example, make `pytest-jubilant` hook into pytest's logging mechanism and configure it as-code. We discuss these ideas in [Future works](#future-works).

#### Log handling model

Jubilant is developed as a library. Developers that use Jubilant in their test suites are called "Downstream users".

Following the instructions in the [Logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html#adding-handlers-other-than-nullhandler-to-a-logger-in-a-library), Jubilant is responsible for providing public loggers to be consumed by downstream users. Jubilant can decide on the log message, the level of each log message, and the [hierarchy](https://docs.python.org/3/library/logging.html#logger-objects) of its loggers. Downstream users can configure logging to their needs (for example: filtering out logs, redirecting logs to a file).

#### Improving `juju.wait()` logs

Charmers raise concerns mostly on the verbosity of `juju.wait()`, where it logs all status changes of the model. Therefore, we reduce the information `juju.wait()` logs by default. We call this new setup *"Brief mode"*, and the original setup *"Verbose mode"*.  Brief mode reduces clutter in the `juju.wait()` logs, and improves human readability. We aim to include information that is most relevant and would solve most investigations. The Brief mode should only include information available in the Verbose mode.

Downstream users can still access the logs in `juju.wait()` verbose mode. This is useful for long running tests (for example: integration tests in CI) which can be inconvenient to reproduce. They can redirect the verbose log to a file, which can be uploaded as an CI artifact.

### Jubilant public loggers

Jubilant will provide these public loggers:

```py
logger = logging.getLogger('jubilant')
logger_wait = logging.getLogger('jubilant.wait')
```

Where:

* `jubilant` is the root logger object
* `jubilant.wait` is the logger containing logs from `juju.wait()`

#### CLI commands and Bootstrap output

The following log messages still belong to the main `jubilant` logger object.

* Juju CLI commands invoked by Jubilant. For example:

```
cli: juju add-unit --model jubilant-54c64634 snappass-test
```

* The output of bootstrapping a controller with `juju.bootstrap()`:

```
bootstrap output: ...
```

#### `juju.wait()` log messages

All `juju.wait()` log messages belong to the `jubilant.wait` logger. There are two types of logs emitted by `juju.wait()`: the periodical model status changes as [gron style](http://github.com/tomnomnom/gron) diff lines, and the application + unit status changes introduced in this Spec.

##### Model status changes as gron diff

`juju.wait()` continues to log all model status changes periodically to the `jubilant.wait` logger. These logs are at `DEBUG` level.  These status changes will still be in gron style diff lines. For example:

```
... DEBUG ... status changed diff:
- .apps['testdb'].app_status.current = 'unknown'
+ .apps['testdb'].app_status.current = 'active'
+ .apps['testdb'].app_status.message = 'relation created'
- .apps['foo'].app_status.current = 'unknown'
+ .apps['foo'].app_status.current = 'error'
+ .apps['foo'].app_status.message = 'something bad happened'
```

##### Application and unit status changes

An application/`app` status change happens when there is a change to any deployed charm in the model. A `unit` change happens when there is a change to any unit in the model.  To keep it short, we will call  those changes app/unit changes.

Each `app/unit` status change is logged in one individual [LogRecord](https://docs.python.org/3/library/logging.html#logging.LogRecord) object.  We log these changes at `ERROR` level if an application or unit has transitioned into error, otherwise `INFO`.

We intend to show `app/unit` status changes to CLI by default, with human readability in mind. Therefore, we decided to move away from using [gron style](http://github.com/tomnomnom/gron). Gron style is great for capturing the JSON content in a grep-able format and generating diff lines. However, this can be too verbose for Charmers to read in a terminal or in the Github Actions UI.

We propose the following format for logging `app/unit` status changes:

```
[<name>] <previous_status> (<message>) -> <new_status> (<new_message>)
```

Where:

* `[<name>]` is the name of the `app/unit` whose status changed. The square brackets here are literal square brackets.
* `<previous_status>` is the previous status
* `<new_status>` is the status the `app/unit` changed into
* `<message>` is the optional message from the status change. If this is empty, we show the empty brackets.

In the case where previous status is not available (for example, when an application starts), we only show the new status:

```
[<name>] <new_status> (<new_message>)
```

Let's see an example in action. These application changes are captured from `juju status -format json`. For example, given these status changes as gron diff lines:

```
# First juju status --format json
- .apps['testdb'].app_status.current = 'unknown'
+ .apps['testdb'].app_status.current = 'active'
+ .apps['testdb'].app_status.message = 'relation created'
- .apps['foo'].app_status.current = 'unknown'
+ .apps['foo'].app_status.current = 'error'
+ .apps['foo'].app_status.message = 'something bad happened'

# Second juju status --format json
- .apps['foo'].app_status.current = 'error'
+ .apps['foo'].app_status.message = 'something bad happened'
+ .apps['foo'].app_status.current = 'active'
+ .apps['foo'].app_status.message = ''
```

Then the following messages are logged in `juju.wait()` , using either `logger_wait.info(...)` or `logger_wait.error(...)`:

```
[testdb] unknown () -> active (relation created) (1)
[foo] unknown () -> error (something bad happened) (2)
[foo] error (something bad happened) -> active () (3)
```

(1) is logged at `INFO` level. (2) is logged at `ERROR`. (3) is logged at `INFO`, with an empty message.

### Downstream configuration

We recommend downstream users write their integration tests with `pytest-jubilant`. This pytest plugin provides useful fixtures that wrap Jubilant's functionality. However, we shouldn't put any logging configuration in `pytest-jubilant`. In pytest, there is a builtin plugin called `logging-plugin`  ([source](https://github.com/pytest-dev/pytest/blob/main/src/_pytest/logging.py)), which handles logs. This plugin accepts familiar logging arguments such as `--log-cli-level` or `--log-format`, and mechanisms to prevent logging configuration from leaking in-between tests. This is enough to support the logging modes that we suggest.

We ship the default logging configuration in Charmcraft profiles. This configuration will be applied automatically, while allowing users to override it. Quoting from [Configuration file formats](https://docs.pytest.org/en/stable/reference/customize.html#configuration-file-formats): "Many pytest settings can be set in a configuration file, which by convention resides in the root directory of your repository". Charmcraft profiles for k8s and machine charm (at commit [4ef9d3](https://github.com/canonical/charmcraft/commit/4ef9d3899a251701e4773f13df37b279a7207842)) ship 2 pytest-compatible configuration files: `tox.ini` and `pyproject.toml`.  We recommend putting the configuration in `pyproject.toml` because we'll soon be recommending that charmers stop using tox.ini.

This Spec also discusses alternative configurations, if users prefer a more or less verbose logging setup.

#### Brief mode (the default)

The brief mode is shipped by default in Charmcraft profiles. For more information on these configurations, see [pytest's live-logs](https://docs.pytest.org/en/stable/how-to/logging.html#live-logs).

```
[tool.pytest.ini_options]
...
log_cli = true
log_cli_level = "INFO"
log_cli_format = "%(levelname)s %(name)s %(message)s"
```

Behavior:

* While the test is running, logs with level `INFO` and above are emitted live to the console
* Ignore logs with level lower than `INFO` (for example, the model status changes in gron style)
* We don't include timestamps because it is redundant when viewing in Github Actions web UI.

Log format:

* `%(levelname)s` is the log level
* `%(name)s` is the logger name
* `%(message)s` is the log message

Example:

```
ERROR jubilant.wait status changed: myapp active -> error: something bad happened
INFO jubilant.wait status changed: app2 error -> active: everything okay
INFO jubilant.wait status changed: app6 error -> active
```

#### Verbose mode

This mode shows whatever is in `Brief` and the model status changes in gron style. We simply lower the log level to `DEBUG`, and add the timestamps. Lowering the log level is all it needs to switch from `Brief` to `Verbose` mode. You can remove the timestamps without changing the mode, but we recommend leaving it in.

```
[tool.pytest.ini_options]
...
log_cli = true
log_cli_level = "DEBUG"
log_cli_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
log_cli_date_format = "%Y-%m-%dT%H:%M:%SZ"
```

Log format:

* `%(asctime)s` is the timestamps, which follows ISO 8601. This format is defined by `log_cli_date_format`
* `%(levelname)s` is the log level
* `%(name)s` is the logger name
* `%(message)s` is the log message

Example:

```shell
2024-06-29T03:24:20Z ERROR jubilant.wait status changed: myapp active -> error: something bad happened
2024-06-29T03:24:21Z DEBUG jubilant.wait.verbose status changed diff:
- <...>
- <...>
+ <...>
+ <...>
2024-06-29T03:24:22Z INFO jubilant.wait status changed: app2 error -> active: everything okay
2024-06-29T03:24:21Z DEBUG jubilant.wait.verbose status changed diff:
- <...>
- <...>
+ <...>
+ <...>
```

#### Error mode

This mode only shows logs with `ERROR` level to the console. This is useful if you only care if any charm turns into error status.

```
[tool.pytest.ini_options]
...
log_cli = true
log_cli_level = "ERROR"
log_cli_format = "%(levelname)s %(name)s %(message)s"
```

Where:

* `%(levelname)s` is the log level
* `%(name)s` is the logger name
* `%(message)s` is the log message

Example

```shell
2024-06-29T03:24:20Z ERROR jubilant.wait status changed: myapp active -> error: something bad happened
```

#### Log to a file

This is an ideal configuration for long-running integration tests (for example, in CI). It uses `Brief` mode for logging to the console, and `Verbose` mode for logging to a local file.

```
[tool.pytest.ini_options]
...

log_level = "INFO"

log_cli = true
log_cli_level = "INFO"
log_cli_format = "%(levelname)s %(name)s %(message)s"

log_file = "logs/verbose.log"
log_file_level = "DEBUG"
log_file_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
log_file_date_format = "%Y-%m-%dT%H:%M:%SZ"
```

`log_level = "INFO"` is intentional**.** When a test item fails, pytest prints all logs captured during the test to the terminal.

```
--------- Captured log call ---------
...
```

These logs were captured using a separated handler called "Report Handler" (see [here](https://github.com/pytest-dev/pytest/blob/addf8838687c0a4caa20b1bd528a419eb99ddf56/src/_pytest/logging.py#L838)). The Report handler's effective level depends on `log_level`, `log_cli_level`, and `log_file_level`.

* If `log_level` is not set, Report Handler level will be `min(log_cli_level, log_file_level)` . In our configuration above, it will be `DEBUG`
* If `log_level` is set to `INFO`, Report Handler level will be `INFO`

Therefore, we suggest an explicit `log_level = "INFO"` in the configuration to keep the `Captured log call` consistent with `Brief` mode.

`logs/verbose.log` contains logs from one `pytest` session. This is fine because Charmcraft profiles suggest running integration tests as follow:

```
tox -e integration

// tox.ini
[testenv:integration]
commands =
    pytest \
        ...
```

Users might run multiple test suites individually, and store verbose logs in separated files. They can override `log_file` for each pytest invocation:

```
pytest --log-file "run1.log" ...
pytest --log-file "run2.log" ...
```

Alternatively, users can set the log file mode to "append". Pytest then put verbose logs from all invocations into one file:

```
[tool.pytest.ini_options]
log-file-mode = "a"
...
```

#### Behavior when no pytest's logging config is set

The above modes are set using pytest's `ini_options`. This section covers the behavior when **no** logging `ini_options` is set, either via config files, or from CLI arguments.

In this case, pytest captures all log messages at `WARNING` level or above (see [pytest/how-to-manage-logging](https://docs.pytest.org/en/stable/how-to/logging.html#how-to-manage-logging)), and there is no logging to a file. This means all logs from Jubilant will not be captured and shown to the terminal, because they are either at  `DEBUG` or `INFO` level.

You can still see messages from:

* Pytest

```
...
collected 1 item

tests/integration/test_charm.py::test_deploy FAILED
...
```



* Logs from other modules if they are at `WARNING` or above.
* Information from a pytest plugin if it uses [Terminal Reporter](https://docs.pytest.org/en/stable/reference/reference.html#terminalreporter). For example, usage hints from `pytest-jubilant`.

```
---- jubilant --------
Models were torn down. To keep models available for subsequent test runs or manual debugging, pass the following:
--no-juju-teardown
```

### Interaction with pytest-jubilant _dump_all_logs

`pytest-jubilant` produces two types of logs.

#### pytest-jubilant logs to stderr

In a pytest session, if one item fails,  `pytest-jubilant` prints the last 1000 lines of `juju debug-log` for each model to stderr before teardown:

```
------------------------------------------------------------------------------------ Captured log teardown ------------------------------------------------------------------------------------
...
pytest-jubilant:_main.py:263 Logging last 1000 lines of `juju debug-log` for model jubilant-aef316ba-test-charm:
...
```


We would like to keep this behavior. At the same time, we want to modify its logic slightly, with our design goals in mind:

* Follow the same logging model of Jubilant: define logger objects in `pytest-jubilant` and let `pytest` handle the log records
* Maintain `Brief` mode in CLI by putting `Captured log teardown` contents into a file

We propose adding a logger in `pytest-jubilant`, and log to it with `DEBUG` level, instead of printing out to stderr ([original implementation](https://github.com/canonical/pytest-jubilant/blob/66c7cb8afaaa18f9b2dfbd1853bd130f19dc9099/pytest_jubilant/_main.py#L256-L262)):

```py
+ logger = logging.getLogger("pytest-jubilant")

...
- print(f"{msg}\n{last_n_lines}\n{end_msg}", file=sys.stderr, flush=True)
+ logger.debug("%s\n%s\n%s", msg, last_n_lines, end_msg)
```

Log messages to this `pytest-jubilant` logger be handled depending on how you configure pytest:

* For [Brief mode](#brief-mode-(the-default)) and [Error mode](#error-mode): They don't appear anywhere.
* For [Verbose mode](#verbose-mode): They appear in the terminal.
* For [Log to a file](#log-to-a-file): They only land in `logs/verbose.log` , and don't appear in the terminal.

#### pytest-jubilant -juju-dump-logs files

If users set `--juju-dump-logs=<directory>`,  `pytest-jubilant` dumps the `juju debug-log` for all models managed by `JujuFactory` ([source](https://github.com/canonical/pytest-jubilant/blob/66c7cb8afaaa18f9b2dfbd1853bd130f19dc9099/pytest_jubilant/_main.py#L252)) to that directory when the test session finishes.

We want to keep the `.logs/verbose.log` file mentioned in [Log to a file](#log-to-a-file) and the `--juju-dump-logs` generated files in the same location. Users would find it easier to upload them as one CI artifact if they are kept together. This behavior doesn't need any changes to `pytest-jubilant` implementation.

In the next section, we discuss a sample configuration for running the integration tests in Github Actions, and upload all log files as one CI artifact.

### An end-to-end configuration for an example charm

I have made changes to `jubilant` and `pytest-jubilant` following this Spec. You can check them out here:

* [https://github.com/canonical/jubilant/pull/351](https://github.com/canonical/jubilant/pull/351)
* [https://github.com/canonical/pytest-jubilant/pull/97](https://github.com/canonical/pytest-jubilant/pull/97)
* Doc updates [https://github.com/canonical/operator/pull/2619](https://github.com/canonical/operator/pull/2619)

I then created an example charm identical to [k8s-2-configurable](https://github.com/canonical/operator/tree/main/examples/k8s-2-configurable), with additional adjustments.

**Patch `jubilant` and `pytest-jubilant` in `pyproject.toml` to use my `jubilant` and `pytest-jubilant` forks.**

```
# Dependencies of integration tests
integration = [
    "jubilant @ git+https://github.com/<my_jubilant_fork>",
    "pytest",
    "pytest-jubilant @ git+https://github.com/<my_pytest_jubilant_fork>,
    "PyYAML",
]
```

**Store all CI log files in the `logs` directory for uploading as one CI artifact.**

This change includes**:**

* Enabling `pytest-jubilant` 's `--juju-dump-logs` flag to `pytest`. We achieve this by adding that flag to the pytest command in the Github Actions workflow.
* Adding [Log to a file](#log-to-a-file) configuration to `pyproject.toml`.

The pytest configuration in `pyproject.toml`:

```
[tool.pytest.ini_options]
...<others>...

log_level = "INFO"

log_cli = true
log_cli_level = "INFO"
log_cli_format = "%(levelname)s %(name)s %(message)s"

log_file = "logs/verbose.log"
log_file_level = "DEBUG"
log_file_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
log_file_date_format = "%Y-%m-%dT%H:%M:%SZ"
```

The Github Actions workflow can be defined as follow:

```
...

jobs:
  ...
  pack:
    ...
    steps:
      # checkout source and prepare environment

      - name: Pack charm
        ...

      - name: Upload charm artifact
        uses: actions/upload-artifact@v4
        with:
          name: charm
          path: "*.charm"

  integration:
    ...
    needs: pack
    steps:
      - name: Checkout source
        ...

      - name: Download charm artifact (from the pack job)
        ...

      - name: Prepare the environment
        ...

      - name: Run integration tests
        env:
          CHARM_PATH: ${{ needs.pack.outputs.charm-path }}
        run: uvx --with tox-uv tox -e integration -- --juju-dump-logs=.ogs

      - name: Upload test logs
        uses: actions/upload-artifact@v7
        with:
          name: integration-test-logs
          path: logs
```

The integration tests are run in the `integration` job. It requires a packed charm, which was uploaded from the `pack` job. [actions/upload-artifact](https://github.com/actions/upload-artifact) uploads the log files in `logs` in one zipped file.

I ran this workflow twice:

* In one branch, I run the workflow as is, and the pipeline passed. [https://github.com/tromai/api-demo-server/pull/2](https://github.com/tromai/api-demo-server/pull/2)
* In one branch, I introduce a bug in the integration test, to observe our logging behaviors in a failure scenario. [https://github.com/tromai/api-demo-server/pull/3](https://github.com/tromai/api-demo-server/pull/3)

You can inspect the latest run for both repos, and download  the logs zip file from Github Actions UI.

## Further Information

### Future works

#### Use log formatters and filter

Jubilant can provide users with the "tools":

* The loggers (similar to this Spec).
* A couple of `WaitFormatter` s that takes in the `LogRecord` with the raw Status objects and format them following our logging modes:
  * All model status changes
  * Application only status changes
* For the `Error` mode, Jubilant can ship a  filter object. This filter allows `LogRecord` where an `app` goes into error status.

Downstream users have the responsibility to wire those tools to log handlers according to their needs. `pytest-jubilant` will then be shipped with the necessary "wirings" which provides downstream users with the default logging mode. `pytest-jubilant` can achieve this by hooking into the existing pytest logging mechanism:

* [An example of hooking into pytest's logging plugin](https://github.com/pytest-dev/pytest/blob/680f9f3ed3faaaa9a4fd1d8120618cd17cdee2d0/src/_pytest/subtests.py#L317-L331)
* We must be careful to not break pytest's logging mechanism.
* The plugin needs to handle cases such as: working with an older jubilant version (that doesn't have the formatter, filter.
* `Pytest-jubilant` then provides a CLI option to configure the wirings. For example, to select which formatter to use, whether to use the `Error` filter.

#### Tighter integration between jubilant and pytest-jubilant

* `pytest-jubilant` applies pytest logging config conditionally (in code) based on whether `--juju-dump-logs` is set. This remains configurable this way by users who want more manual control, but we don't need to document it as a separate recommendation.
* `pytest-jubilant` can even read from the pytest config file and decide on where to log the juju-debug logs.

#### Show status changes of all charms deployed locally in the integration test

Normally, the locally deployed charms are more interesting because they are likely to be developed locally, and aren't from the store. It would be interesting to know: how often do Charmers deploy charms locally / from store in their integration tests.

#### A way to categorize what information should be in `Brief` mode.

In this Spec, we go with application status as a start. However, with hyrum, and feedback from Charmers, we can come up with a guideline to select which information to show in `Brief` mode.

#### Use GitHub Actions group tags

To avoid clobbering the 'polished' jubilant.wait messages with the deluge of juju debug-logs, we could always choose to wrap them in group tags (at the cost of making this github CI-specific).

Then we'd have:

* collapsible block of juju debug-logs that were captured between the previous status change and this one
* status changed: blob of polished jubilant.wait logs
* collapsible block of juju debug-logs that were captured between the this status change and the next one
* ...

Our team is very interested in this improvement. However, it's much more involved in the implementation. We cannot simply log `::group::{title}` to our loggers. GitHub parses this syntax if it's by itself in stdout. To do this, `pytest-jubilant` needs to hook into pytest' logging internals with a Formatter for this syntax to print it as is.

#### Consider more debug files as CI build artifacts

Your test fails, and you see:

* A one-line explanation of what failed (e.g. I was waiting for active/idle but this charm got to Blocked instead)
* A jhack tail-style-recap of what happened from the POV of the charms.
* A jubilant log of which juju commands were issued and when.
* A juju status changelog of all charms that shows which status (with message) they went to and when.
* All warning/error juju debug-logs
* If you really need it, a full juju debug-log dump that you can analyse as you please if the rest is not enough info.

### Examples for current Jubilant logs verbosity

This is a live log call for `tests/integration/test_relations.py::test_integrate_and_remove_relation` integration test ([source](https://github.com/canonical/jubilant/blob/377673d3df962273274bddcdce718bb52c50718a/tests/integration/test_relations.py#L7-L23)). It deployed 2 charms, integrated them, and waited until two apps eventually became `active`. The section below shows the live log emitted by Jubilant.

We consider some information unrelated to the test itself and it can clutter the terminal:

* Information about the Juju model (which was created by Jubilant for the test) can be omitted
* `INFO wait: status changed:` happens multiple times throughout the test. With complicated tests, it can grow pretty quickly.
* It is hard for users to reason about how deployed apps transition, or whether their status becomes `error` at any time in the test.

<details>
<summary>Click to expand the full log output</summary>

```
-------------------------------- live log call ---------------------------------
07:28:24 INFO cli: juju deploy --model jubilant-d6112216 <redacted>/_temp.charm
07:28:24 INFO cli: juju deploy --model jubilant-d6112216 <redacted>/_temp.charm --resource test-file=<redacted>/test-file.tar
07:28:24 INFO cli: juju integrate --model jubilant-d6112216 testdb testapp
07:28:25 INFO wait: status changed:
+ .model.name = 'jubilant-d6112216'
+ .model.type = 'caas'
+ .model.controller = 'concierge-k8s'
+ .model.cloud = 'k8s'
+ .model.version = '4.1-beta1'
+ .model.model_status.current = 'available'
+ .apps['testapp'].charm = 'local:testapp-0'
+ .apps['testapp'].charm_origin = 'local'
+ .apps['testapp'].charm_name = 'testapp'
+ .apps['testapp'].charm_rev = 0
+ .apps['testapp'].exposed = False
+ .apps['testapp'].base.name = 'ubuntu'
+ .apps['testapp'].base.channel = '24.04'
+ .apps['testapp'].scale = 1
+ .apps['testapp'].life = 'alive'
+ .apps['testapp'].app_status.current = 'waiting'
+ .apps['testapp'].app_status.message = 'installing agent'
+ .apps['testapp'].relations['db'][0].related_app = 'testdb'
+ .apps['testapp'].relations['db'][0].interface = 'dbi'
+ .apps['testapp'].relations['db'][0].scope = 'global'
+ .apps['testapp'].units['testapp/0'].workload_status.current = 'waiting'
+ .apps['testapp'].units['testapp/0'].workload_status.message = 'installing agent'
+ .apps['testapp'].units['testapp/0'].juju_status.current = 'allocating'
+ .apps['testapp'].endpoint_bindings[''] = 'alpha'
+ .apps['testapp'].endpoint_bindings['db'] = 'alpha'
+ .apps['testapp'].endpoint_bindings['juju-info'] = 'alpha'
+ .apps['testdb'].charm = 'local:testdb-0'
+ .apps['testdb'].charm_origin = 'local'
+ .apps['testdb'].charm_name = 'testdb'
+ .apps['testdb'].charm_rev = 0
+ .apps['testdb'].exposed = False
+ .apps['testdb'].base.name = 'ubuntu'
+ .apps['testdb'].base.channel = '24.04'
+ .apps['testdb'].scale = 1
+ .apps['testdb'].life = 'alive'
+ .apps['testdb'].app_status.current = 'waiting'
+ .apps['testdb'].app_status.message = 'installing agent'
+ .apps['testdb'].relations['db'][0].related_app = 'testapp'
+ .apps['testdb'].relations['db'][0].interface = 'dbi'
+ .apps['testdb'].relations['db'][0].scope = 'global'
+ .apps['testdb'].units['testdb/0'].workload_status.current = 'waiting'
+ .apps['testdb'].units['testdb/0'].workload_status.message = 'installing agent'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'allocating'
+ .apps['testdb'].endpoint_bindings[''] = 'alpha'
+ .apps['testdb'].endpoint_bindings['db'] = 'alpha'
+ .apps['testdb'].endpoint_bindings['juju-info'] = 'alpha'
07:28:30 INFO wait: status changed:
+ .apps['testdb'].provider_id = '<redacted>'
07:28:31 INFO wait: status changed:
- .apps['testdb'].app_status.message = 'installing agent'
+ .apps['testdb'].app_status.message = 'agent initialising'
- .apps['testdb'].units['testdb/0'].workload_status.message = 'installing agent'
+ .apps['testdb'].units['testdb/0'].workload_status.message = 'agent initialising'
+ .apps['testdb'].units['testdb/0'].juju_status.version = '4.1-beta1'
+ .apps['testdb'].units['testdb/0'].leader = True
+ .apps['testdb'].units['testdb/0'].provider_id = 'testdb-0'
07:28:33 INFO wait: status changed:
+ .apps['testdb'].units['testdb/0'].address = '<redacted>'
07:28:34 INFO wait: status changed:
- .apps['testdb'].app_status.current = 'waiting'
- .apps['testdb'].app_status.message = 'agent initialising'
+ .apps['testdb'].app_status.current = 'unknown'
- .apps['testdb'].units['testdb/0'].workload_status.current = 'waiting'
- .apps['testdb'].units['testdb/0'].workload_status.message = 'agent initialising'
- .apps['testdb'].units['testdb/0'].juju_status.current = 'allocating'
+ .apps['testdb'].units['testdb/0'].workload_status.current = 'running'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
07:28:36 INFO wait: status changed:
+ .apps['testapp'].provider_id = '<redacted>'
07:28:37 INFO wait: status changed:
- .apps['testdb'].app_status.current = 'unknown'
+ .apps['testdb'].app_status.current = 'active'
+ .apps['testdb'].app_status.message = 'relation created'
- .apps['testdb'].units['testdb/0'].workload_status.current = 'running'
- .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
+ .apps['testdb'].units['testdb/0'].workload_status.current = 'active'
+ .apps['testdb'].units['testdb/0'].workload_status.message = 'relation created'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
+ .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-created hook'
07:28:39 INFO wait: status changed:
- .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
- .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-created hook'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
07:28:40 INFO wait: status changed:
+ .apps['testapp'].units['testapp/0'].provider_id = 'testapp-0'
07:28:41 INFO wait: status changed:
- .apps['testapp'].app_status.current = 'waiting'
- .apps['testapp'].app_status.message = 'installing agent'
+ .apps['testapp'].app_status.current = 'maintenance'
+ .apps['testapp'].app_status.message = 'installing charm software'
- .apps['testapp'].units['testapp/0'].workload_status.current = 'waiting'
- .apps['testapp'].units['testapp/0'].workload_status.message = 'installing agent'
- .apps['testapp'].units['testapp/0'].juju_status.current = 'allocating'
+ .apps['testapp'].units['testapp/0'].workload_status.current = 'maintenance'
+ .apps['testapp'].units['testapp/0'].workload_status.message = 'installing charm software'
+ .apps['testapp'].units['testapp/0'].juju_status.current = 'executing'
+ .apps['testapp'].units['testapp/0'].juju_status.message = 'running db-relation-created hook'
+ .apps['testapp'].units['testapp/0'].juju_status.version = '4.1-beta1'
+ .apps['testapp'].units['testapp/0'].leader = True
+ .apps['testapp'].units['testapp/0'].address = '<redacted>'
- .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
+ .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-joined hook for testapp/0'
07:28:43 INFO wait: status changed:
- .apps['testapp'].app_status.current = 'maintenance'
- .apps['testapp'].app_status.message = 'installing charm software'
+ .apps['testapp'].app_status.current = 'unknown'
- .apps['testapp'].units['testapp/0'].workload_status.current = 'maintenance'
- .apps['testapp'].units['testapp/0'].workload_status.message = 'installing charm software'
+ .apps['testapp'].units['testapp/0'].workload_status.current = 'unknown'
- .apps['testapp'].units['testapp/0'].juju_status.message = 'running db-relation-created hook'
+ .apps['testapp'].units['testapp/0'].juju_status.message = 'running db-relation-changed hook'
- .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
- .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-joined hook for testapp/0'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
07:28:44 INFO wait: status changed:
- .apps['testapp'].app_status.current = 'unknown'
+ .apps['testapp'].app_status.current = 'active'
+ .apps['testapp'].app_status.message = 'relation changed: dbkey=dbvalue'
- .apps['testapp'].units['testapp/0'].workload_status.current = 'unknown'
- .apps['testapp'].units['testapp/0'].juju_status.current = 'executing'
- .apps['testapp'].units['testapp/0'].juju_status.message = 'running db-relation-changed hook'
+ .apps['testapp'].units['testapp/0'].workload_status.current = 'active'
+ .apps['testapp'].units['testapp/0'].workload_status.message = 'relation changed: dbkey=dbvalue'
+ .apps['testapp'].units['testapp/0'].juju_status.current = 'idle'
07:28:46 INFO cli: juju remove-relation --model jubilant-d6112216 testdb testapp
07:28:47 INFO wait: status changed:
+ .model.name = 'jubilant-d6112216'
+ .model.type = 'caas'
+ .model.controller = 'concierge-k8s'
+ .model.cloud = 'k8s'
+ .model.version = '4.1-beta1'
+ .model.model_status.current = 'available'
+ .apps['testapp'].charm = 'local:testapp-0'
+ .apps['testapp'].charm_origin = 'local'
+ .apps['testapp'].charm_name = 'testapp'
+ .apps['testapp'].charm_rev = 0
+ .apps['testapp'].exposed = False
+ .apps['testapp'].base.name = 'ubuntu'
+ .apps['testapp'].base.channel = '24.04'
+ .apps['testapp'].scale = 1
+ .apps['testapp'].provider_id = '<redacted>'
+ .apps['testapp'].life = 'alive'
+ .apps['testapp'].app_status.current = 'active'
+ .apps['testapp'].app_status.message = 'relation changed: dbkey=dbvalue'
+ .apps['testapp'].relations['db'][0].related_app = 'testdb'
+ .apps['testapp'].relations['db'][0].interface = 'dbi'
+ .apps['testapp'].relations['db'][0].scope = 'global'
+ .apps['testapp'].units['testapp/0'].workload_status.current = 'active'
+ .apps['testapp'].units['testapp/0'].workload_status.message = 'relation changed: dbkey=dbvalue'
+ .apps['testapp'].units['testapp/0'].juju_status.current = 'idle'
+ .apps['testapp'].units['testapp/0'].juju_status.version = '4.1-beta1'
+ .apps['testapp'].units['testapp/0'].leader = True
+ .apps['testapp'].units['testapp/0'].address = '<redacted>'
+ .apps['testapp'].units['testapp/0'].provider_id = 'testapp-0'
+ .apps['testapp'].endpoint_bindings[''] = 'alpha'
+ .apps['testapp'].endpoint_bindings['db'] = 'alpha'
+ .apps['testapp'].endpoint_bindings['juju-info'] = 'alpha'
+ .apps['testdb'].charm = 'local:testdb-0'
+ .apps['testdb'].charm_origin = 'local'
+ .apps['testdb'].charm_name = 'testdb'
+ .apps['testdb'].charm_rev = 0
+ .apps['testdb'].exposed = False
+ .apps['testdb'].base.name = 'ubuntu'
+ .apps['testdb'].base.channel = '24.04'
+ .apps['testdb'].scale = 1
+ .apps['testdb'].provider_id = '<redacted>'
+ .apps['testdb'].life = 'alive'
+ .apps['testdb'].app_status.current = 'active'
+ .apps['testdb'].app_status.message = 'relation created'
+ .apps['testdb'].relations['db'][0].related_app = 'testapp'
+ .apps['testdb'].relations['db'][0].interface = 'dbi'
+ .apps['testdb'].relations['db'][0].scope = 'global'
+ .apps['testdb'].units['testdb/0'].workload_status.current = 'active'
+ .apps['testdb'].units['testdb/0'].workload_status.message = 'relation created'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
+ .apps['testdb'].units['testdb/0'].juju_status.version = '4.1-beta1'
+ .apps['testdb'].units['testdb/0'].leader = True
+ .apps['testdb'].units['testdb/0'].address = '<redacted>'
+ .apps['testdb'].units['testdb/0'].provider_id = 'testdb-0'
+ .apps['testdb'].endpoint_bindings[''] = 'alpha'
+ .apps['testdb'].endpoint_bindings['db'] = 'alpha'
+ .apps['testdb'].endpoint_bindings['juju-info'] = 'alpha'
07:28:48 INFO wait: status changed:
- .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
+ .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-broken hook'
07:28:49 INFO wait: status changed:
- .apps['testdb'].units['testdb/0'].juju_status.current = 'executing'
- .apps['testdb'].units['testdb/0'].juju_status.message = 'running db-relation-broken hook'
+ .apps['testdb'].units['testdb/0'].juju_status.current = 'idle'
07:28:58 INFO wait: status changed:
- .apps['testapp'].relations['db'][0].related_app = 'testdb'
- .apps['testapp'].relations['db'][0].interface = 'dbi'
- .apps['testapp'].relations['db'][0].scope = 'global'
- .apps['testdb'].relations['db'][0].related_app = 'testapp'
- .apps['testdb'].relations['db'][0].interface = 'dbi'
- .apps['testdb'].relations['db'][0].scope = 'global'
PASSED [ 88%]
------------------------------ live log teardown -------------------------------
07:29:00 INFO cli: juju debug-log --model jubilant-d6112216 --limit 1000
07:29:01 INFO cli: juju destroy-model jubilant-d6112216 --no-prompt --destroy-storage --force
tests/integration/test_secrets.py::test_add_secret
-------------------------------- live log setup --------------------------------
07:29:13 INFO cli: juju add-model --no-switch jubilant-97c35328
-------------------------------- live log call ---------------------------------
07:29:14 INFO cli: juju add-secret --model jubilant-97c35328 sec1 --info 'A description.' --file <redacted>
07:29:14 INFO cli: juju show-secret --model jubilant-97c35328 secret:<redacted> --format json --reveal
PASSED [ 91%]
tests/integration/test_secrets.py::test_update_secret
-------------------------------- live log call ---------------------------------
07:29:14 INFO cli: juju add-secret --model jubilant-97c35328 sec2 --info 'A description.' --file <redacted>
07:29:15 INFO cli: juju update-secret --model jubilant-97c35328 sec2 --info 'A new description.' --file <redacted>
07:29:15 INFO cli: juju show-secret --model jubilant-97c35328 sec2 --reveal --format json
PASSED [ 94%]
tests/integration/test_secrets.py::test_get_all_secrets
-------------------------------- live log call ---------------------------------
07:29:15 INFO cli: juju secrets --model jubilant-97c35328 --format json
PASSED [ 97%]
tests/integration/test_secrets.py::test_show_secret
-------------------------------- live log call ---------------------------------
07:29:15 INFO cli: juju show-secret --model jubilant-97c35328 sec1 --format json
07:29:15 INFO cli: juju show-secret --model jubilant-97c35328 sec1 --format json --reveal
07:29:16 INFO cli: juju show-secret --model jubilant-97c35328 sec2 --format json --reveal --revision 1
07:29:16 INFO cli: juju show-secret --model jubilant-97c35328 sec2 --format json --reveal --revision 2
07:29:16 INFO cli: juju show-secret --model jubilant-97c35328 sec2 --format json --revisions
07:29:16 INFO cli: juju show-secret --model jubilant-97c35328 secret:<redacted> --format json
PASSED [100%]
------------------------------ live log teardown -------------------------------
07:29:17 INFO cli: juju debug-log --model jubilant-97c35328 --limit 1000
07:29:17 INFO cli: juju destroy-model jubilant-97c35328 --no-prompt --destroy-storage --force
07:39:17 ERROR timeout destroying model: Command '['juju', 'destroy-model', 'jubilant-97c35328', '--no-prompt', '--destroy-storage', '--force']' timed out after 600 seconds
Stdout:
None
Stderr:
b'Destroying model\n\nWaiting for model to be removed.................................................\n................................................................................\n................................................................................\n................................................................................\n..................'
```

</details>
