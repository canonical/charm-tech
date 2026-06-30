# Charm Tech change log style guide

This is the change log style we inherit from [canonical/operator](https://github.com/canonical/operator). 

We will use this style going forward in all repos that we own.

## File format

The change log is written in Markdown. The file is located in the root directory of a repo, with the name `CHANGES.md`. See [operator's change log](https://github.com/canonical/operator/blob/main/CHANGES.md) and [jubilant's change log](https://github.com/canonical/jubilant/blob/main/CHANGES.md).

## Specification

Each `CHANGES.md` contains one or many sections.

Each section in the change log represents a release version, and the included commits.

The section title has the version number and its released date (in Github Release), separated by a dash `-`.

```
# {{ version_number }} - {{ date }}
```

For example, Jubilant [v1.9.0](https://github.com/canonical/jubilant/releases/tag/v1.9.0) has the following section title:

```
# 1.9.0 - 29 April 2026
```

We use [conventional commits](https://www.conventionalcommits.org). Only these types of commit are recorded in `CHANGES.md`: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`. Commit types not in these types are ignored.

Each commit type has its own Sub-section. The table below maps each commit type to a Sub-section. **All** breaking change commits belongs to their own Sub-section `Breaking changes`:

| Commit type | Sub-section |
| :--- | :--- |
| `<type>!:` | `## Breaking changes` |
| `feat:` | `## Features` |
| `fix:` | `## Fixes` |
| `docs:` | `## Documentation` |
| `test:` | `## Tests` |
| `refactor:` | `## Refactoring` |
| `ci:` | `## CI` |

The order of Sub-sections follow the table from top to bottom. For example:

```
# 1.9.0 - 29 April 2026

## Breaking Changes

* Commit message (#1)
* Commit message (#2)

## Features

* Commit message (#1)
* Commit message (#2)

## Fixes

* Commit message (#1)
* Commit message (#2)

## Documentation

* Commit message (#1)
* Commit message (#2)

## Tests

* Commit message (#1)
* Commit message (#2)

## Refactoring

* Commit message (#1)
* Commit message (#2)

## CI

* Commit message (#1)
* Commit message (#2)
```

If a Sub-section doesn't have a commit, it is not included.

Spacing: There is exactly one empty lines before and after each Section and Sub-section. There is no empty line between commits.

Each commit follows this format:

```
* {{ capitalized_first_letter_message }} #{{ Pull request number }}
```

If a commit doesn't follow conventional commit, discuss with the commit author or the team to decide. You must put all code symbols (for example: method names) in backticks.

## Toolings

You can use [cliff](https://git-cliff.org/) to generate the change log. See [cliff.toml](./cliff.toml) for an example configuration.

Remember to double check the tool's result before checking it into the repo.
