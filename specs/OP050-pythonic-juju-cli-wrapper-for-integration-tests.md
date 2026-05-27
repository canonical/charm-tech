# OP050 — Pythonic Juju CLI wrapper for integration tests

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2024-09-16 |

**NOTE ABOUT APPROVAL:** This spec is just a "sketch" of the initial proof of concept, and further review and discussion is happening in PRs at [https://github.com/canonical/jubilant](https://github.com/canonical/jubilant)

## Abstract

This spec presents a sketch for a Python library that wraps the Juju CLI, intended for use in integration tests. It's intended as a very light wrapper, with one function corresponding to one Juju CLI command. For commands that return output, like `juju status`, it uses the stable JSON-formatted output.

The goal is to vastly simplify integration testing, eliminating the need for the complex beasts that are python-libjuju and pytest-operator. Usage is intended to be similar to how you'd manually test using commands at a shell, except that you have the power of Python at your disposal, as well as argument names and type hints for good code completion.

## Specification

The library, named **jubilant**, would use `subprocess.run()` to wrap Juju CLI commands in a 1:1 manner, with typed parameter names for common parameters, and typed return values.

We'd start by defining a `Juju` class with methods for the most common commands (and parameters) used by integration tests, with a `cli()` method that library users could fall back on if they needed to run Juju subcommands not implemented by the wrapper.

Like this:

```py
# jubilant.py

class Juju:
    def deploy(
        self,
        charm_name: str,
        app_name: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        num_units: int = 1,
        resources: dict[str, str] | None = None,
        trust: bool = False,
        ...,  # include all the arguments we think people we use
    ) -> None:
        args = [...]
        subprocess.run(['juju', 'deploy'] + args, check=True)

    def status(
        self,
        *,
    ) -> Status:
        process = subprocess.run(['juju', 'status', '--format', 'json'],
                                 check=True, capture_output=True)
        result = json.load(process.stdout)
        return Status.from_dict(result)

# Other commands we think tests will use and should be implemented:
#
# add-model                  Adds a workload model.
# add-secret                 Add a new secret. ### MAYBE???
# add-unit                   Adds one or more units to a deployed application.
# config                     Gets, sets, or resets configuration for a deployed
# deploy                     Deploys a new application or bundle.
# destroy-model              Terminate all machines/containers and resources for
# exec                       Run the commands on the remote targets specified.
# integrate                  Integrate two applications.
# offer                      Offer application endpoints for use in other models.
# refresh                    Refresh an application's charm.
# remove-application         Remove applications from the model.
# remove-unit                Remove application units from the model.
# run                        Run an action on a specified unit.
# show-operation             Show results of an operation.
# ssh                        Initiates an SSH session on a Juju machine or container.
# status                     Report the status of the model, its machines, applications
# switch                     Selects or identifies the current controller and model.
# trust                      Sets the trust status of a deployed application to true.

    # For commands not defined as functions, users would fall back to calling this:
    def cli(self, *args: str) -> str:
        process = subprocess.run(['juju', *args], check=True, capture_output=True)
        return process.stdout

    def wait_status(
        self,
        ready_func: Callable[[Status], bool],
        *,
        model: str | None = None,
        timeout: float = 10*60,  # same default as python-libjuju's wait_for_idle
        delay: float = 1,
        successes: int = 3,
    ) -> Status:
        start = time.time()
        success_count = 0
        while time.time() - start < timeout:
            status = status()
            logger.info('wait_status: %s', status)  # ensure better debugging
            if ready_func(status):
                success_count += 1
                if success_count >= successes:
                    return status
            else:
                success_count = 0
            time.sleep(delay)
        raise Exception(f'timed out after {timeout}, last status:\n{status}')

@dataclass
class Status:
    # Ideally we can generate the list of fields from the Go source in Juju:
    # cmd/juju/status/formatted.go
    applications: dict[str, ApplicationStatus]
    ...

    # In addition to the "raw" fields, have a number of helper methods that extract
    # commonly-used pieces of information, such as:
    def subordinate_units() -> list[str]:
        ...

# In a jubilant.helpers submodule, have some ready_func helper implementations that
# allow you to do things like this:
#
# juju.wait_status(lambda s: (helpers.raise_on_error(s) and
#                             helpers.applications_active(s, 'a1', 'a2')))
#
# Or perhaps even better, these could be methods on Status:
#
# juju.wait_status(lambda s: s.raise_on_error() and s.applications_active('a1', 'a2'))

# In a jubilant.fixtures submodule, add common pytest fixtures such as:
@pytest.fixture
def model():
    # add a model
    yield model
    # destroy model
```

As an example of usage, here's a [test from prometheus-k8s-operator](https://github.com/canonical/prometheus-k8s-operator/blob/1bd9e7fd96a9f5a91443e5932667c58a92c1ce5e/tests/integration/test_charm.py#L31), reworked using this idea:

```py
import jubilant

def test_prometheus_scrape_relation_with_prometheus_tester():
    juju = jubilant.Juju()

    juju.deploy(
        prometheus_charm,
        "prometheus",
        resources={"prometheus-image":
                   oci_image("./metadata.yaml", "prometheus-image")},
        trust=True,
    )

    juju.deploy(
        prometheus_tester_charm,
        "prometheus-tester",
        resources={"prometheus-tester-image": oci_image(
            "./tests/integration/prometheus-tester/metadata.yaml",
            "prometheus-tester-image",
        )},
    )

    def all_active(status):
        return (
            status.applications["prometheus"].application_status.current == "active" and
            status.applications["prometheus-tester"].application_status.current == "active"
        )
    juju.wait_status(all_active, timeout=10*60)

    # ...

    juju.integrate(f"{prometheus_app_name}:metrics-endpoint",
                   f"{tester_app_name}:metrics-endpoint")
    juju.wait_status(all_active, timeout=10*60)

    # ...
```

### Notes on the design

* **Class API:** We would start with the class-based API described above. If needed, we could have a default `jubilant.juju = Juju()` object at the top level for simple use cases. Users would then write `from jubilant import juju` and `juju.deploy()`.
* **Versions of Juju:** The initial version of the library would support Juju 3 and Juju 4 (whose CLI will likely be 100% compatible with Juju 3's CLI).
  * Before Juju 5 comes out we'd design a way to handle versioning.
  * I (Ben) feel strongly we want to preserve the "API is 1:1 with the Juju command line", so that would mean one version per major Juju version, rather than having lots of if/else smarts in the library to patch over version differences.
  * We could have a new version of the lib, say jubilant5, to handle this.
  * Or we could have a compatibility layer like jubilant.compat that had helpers to do this.
  * We don't want to repeat the mistake of python-libjuju versioning, where they tried to tie it to the version of Juju, which versions such as 3.5.2.1. Most of us see this as a mistake.

### Not in scope

* **No setting up infrastructure** or installing Juju. This should be done by the test runner, for example in a GitHub Action, by `spread`, or by `charmcraft test`. This library assumes the "juju" command is already in the path and a controller has been created.
  * For this, see Jon's [concierge](https://github.com/jnsgruk/concierge/tree/main) tool and an [example](https://github.com/jnsgruk/zinc-k8s-operator/pull/284) using it in zinc-k8s-operator.
* **No packing the charm.** `charmcraft pack` will be executed by the infrastructure or script running the integration tests.

## Further Information

* [Pietro's Guru library](https://github.com/PietroPasotti/guru/blob/main/guru/guru.py)
  * Guru is similar in wrapping the Juju CLI with Pythonic functions (though I hadn't actually looked at Guru before writing this up).
  * It includes tools for deploying from a git repo, status condition classes, and various helper methods to set up a matrix of integrations.
  * I'd like to go back to first principles and simplify a lot of that down.
  * However, the basic concept is roughly the same!
* [Jon's juju.py and integration tests PoC on zinc-k8s-operator](https://github.com/jnsgruk/zinc-k8s-operator/pull/273/files)
* [Pietro's additions to juju.py](https://github.com/canonical/tempo-coordinator-k8s-operator/blob/a487211b1afe6f2370af974089cc1c26ba2b9922/tests/integration/juju.py): this is fairly close to this spec, and has some good inspiration for fixtures and the like (conftest.py).
* [Dylan's jtest library](https://github.com/dstathis/jtest)

### Findings from existing integration tests

After looking over several existing integration tests written by different teams (postgresql-operator, traefik-k8s-operator, prometheus-k8s-operator, sdcore-ausf-operator), we've found that for the most part they do fairly simple interactions with Juju (and more complex interactions with the workloads in some cases).

In addition to building a charm, which is a charmcraft function and not in scope for this library, they fall into three categories:

#### Performing operations

* Deploy charms (juju deploy)
* Integrate charms to form a relation (juju integrate)
* Add and remove units, scale up/down (juju add-unit, juju remove-unit)
* Remove applications (juju remove-application)
* Upgrade/refresh a charm (juju refresh)
* Run charm actions and get results (juju run, juju show-operation)

#### Waiting for application or unit status

* wait_for_idle(), which is most often used to with for one (or sometimes more) applications to reach a certain status, like "active" or "blocked"
* block_until(<lambda>), a slightly more general version of the above; generally the lambda looks at something in a unit status

#### Fetch data from application status

* model.units.get(unit_name).public_address
* find status of the leader (or other) units
* get number of units
* and many more...
