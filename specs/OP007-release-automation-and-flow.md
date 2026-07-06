# OP007 — Release Automation and Flow

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-09-16 |

## Abstract

Implement a formal release, and automate as much of it as possible and/or desirable.

## Rational

In order to reduce the team's "bus factor" and simply reduce non code related work, it would be useful to formalize and automate the flow of approving and cutting a release, then publishing to PyPI.

## Specification

This spec proposes the following flow:

1) At the start of work on a new release, we will create a release branch, with a name that simply matches the version number of the release. For example, the next release at the time of writing would be 1.2.1, so we would create a branch with that name.
2) PRs should target this release.
3) Upon merging the release branch to master, a github action should fire that creates and publishes the release.

### Publish action

Here's a draft of what that action might look like.

### `name: Publish`

### `on:`

### `release:`

### `jobs:`

### `build-n-publish:`

### `name: Build and Publish to PyPI`

### `runs-on: ubuntu-latest`

### `steps:`

### `- uses: actions/checkout@master`

### `- name: Setup Python`

### `uses: actions/setup-python@v1`

### `with:`

### `python-version: 3.9`

### `- name: Build`

### `run: >-`

### `python setup.py bdist`

### `- name: Publish`

### `uses: pypa/gh-action-pypi-publish@master`

### `with:`

### `password: ${{ secrets.PYPI_API_TOKEN }}`

### Additional work and changes

Track any work above and beyond simply finishing and publishing the above action here.
