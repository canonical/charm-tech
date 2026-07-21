# OP061 — Linting and Testing Command Standardisation in Charms

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Mar 5, 2025 |

## Abstract

To simplify development, charms provide named commands to format or lint code, do static type checking, and run unit and integration tests. The names and meaning of these commands vary between charms. To make it easier to work with and test a broad range of charms, we will standardise on a common minimum set of commands.

## Rationale

Almost all charms have a "`lint`" command and "`unit`" command, but there is a mixture (roughly 4 to 1) of "`fmt`" and "`format`" for formatting, and around a fifth of charms have a "`scenario`" command that separates out tests using the Scenario framework. Although many charms have a "`static`" command, there is no consensus on what that means, and similarly, while many charms have a command for static type checking, there is no consensus on what command executes that (see this [summary](https://docs.google.com/spreadsheets/d/1t7AS_QLxe6IfbehEqSlYrXxOY5L50Y5rw8M4UZX4Tvo/edit)).

Charms tend to use `tox` to run the commands at present. However, there is growing interest in using other command runners, such as `make`.

A consistent set of tools and commands, both in terms of command names and also what each command does, makes it easier to work across and move between charming teams. It also provides a clearer picture of what a charm repository should look like to charmers outside of Canonical.

In addition, the Charm-Tech team uses tooling to verify compatibility of changes made to ops and other tools, such as [regular CI running charm static checking and unit tests against large numbers of published charms](https://github.com/canonical/operator/blob/main/.github/workflows/published-charms-tests.yaml), and [manually validating changes against a large number of locally cloned charms](https://github.com/tonyandrewmeyer/charm-analysis?tab=readme-ov-file#super-tox). A known set of tools and commands ensures that changes are validated against the largest set of charms possible.

## Specification

Charms must include the following commands, with the given meaning:

| Command | Definition |
| :---- | :---- |
| *(no command, running the tool with no args)* | Running the command tool in the top level of the charm repository must execute the `lint`, and `unit` commands. |
| format | Automatically format the code (including tests) according to the project's style. |
| lint | Report any linting errors, for example from tools such as ruff, pylint, flake8, isort, pydocstyle, or bandit. This must include code of any libs the charm provides, and should include the charm test code. In addition, report any static type checking issues, for example from tools such as pyright, ty, or mypy. This must include code of any libs the charm provides, and should include the charm test code. |
| unit | Run unit tests for the charm and its libs (if any). Note that this includes unit tests using the deprecated Harness framework as well as unit tests using the state-transition framework (Scenario). |
| integration | Run integration tests (against a real Juju controller) for the charm and its libs (if any). Note that this includes tests using pytest-operator and python-libjuju as well as tests using [Jubilant](https://canonical-jubilant.readthedocs-hosted.com/). Running `charmcraft test` should also run these tests, via spread, but this is only recommended, not required, while the `test` command is experimental. |
| docs | Build the documentation for the charm. If the documentation is not in the repository (for example, it is on Discourse), then this command is not required. This should run the ``make run`` command in the docs directory, provided by [the starter pack](https://canonical-starter-pack.readthedocs-hosted.com/latest/). |

The [charmcraft profiles](https://github.com/canonical/charmcraft/tree/main/charmcraft/templates) will hold the ongoing source-of-truth of the spelling and meaning of each of the commands.

We are standardising on "format" rather than the Go-style "fmt", even though the latter is more common at the moment, because this has been the charmcraft profile standard for [some time](https://github.com/canonical/charmcraft/commit/8b6620350b7e453cd4a77a927742ebd2308c39f0), and it aligns with all of the other commands that are the full word.

Charms may also include any other commands that make sense for the specific project. For example:

* Charms that include libs may have commands that are specifically limited to the lib.
* Charmers may choose to have commands that are combinations of other individual commands (for example, "static" might be a combination of "static-charm" and "static-lib"), or that provide aliases (for example, "fmt" as an alias for "format").
* Charms, particularly for machines, might want to have a "functional" set of tests that validate interactions with the workload, but without Juju.

All commands will be executable from the top level of the charm repository. Any requirements for running the commands (such as installing `uv` or `tox`) must be clearly documented in a CONTRIBUTING or HACKING file found in the top level of the charm repository.

In a repository that contains more than one charm (for example, a pair of machine and Kubernetes charms, or a pair of coordinator and worker charms):

* The "format", "link", "unit", and "integration" commands must be available in each charm folder. The expectation is that running the command in the folder limits the action to that charm.
* The "format" command should be available at the top level, suitably formatting code across all charms in the repository.
* The "lint" command is ideally available at the top level, linting all charms in the repository with the same rules. Note that with static type checking, running the checker at the top level may not be feasible (if the charms have conflicting dependencies, for example), and the command may need to change to each charm directory, run the checker, then change to the next charm directory, and so on.
* The "unit" and "integration" commands are ideally available at the top level, running all tests across the charms.
* If one set of documentation is produced for all the charms in the repository, the "docs" command must be available at the top level; if each charm has separate documentation, the "docs" command must be available in each charm folder (with an optional top-level command that builds docs for all the charms).

Commands must be run with one of the following tools:

| Tool | Examples |
| :---- | :---- |
| [tox](https://tox.wiki/en/latest/index.html) | `tox tox -e lint tox -e unit -- -k test_foo` |
| make | `make make lint make unit ARGS='-k test_too'` |
| [just](https://github.com/casey/just) | `just just lint just unit` |

New command runner tools may be added to this list in the future. The most highly recommended tool is the one used in the charmcraft profiles - `tox`, at the time of writing this spec.

The tool must execute the appropriate action without any additional arguments (for example: "tox -e unit", "make unit", "just unit"). Charms may also support providing arguments (for example, to adjust formatting or limit to specific files) and should do this using the style common to the tool.

Other tools in the charming ecosystem (such as ops, Scenario, or Jubilant) should also follow this specification.
