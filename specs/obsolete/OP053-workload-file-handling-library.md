# OP053 — Workload File Handling Library

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2024-11-28 |

## Abstract

Pebble provides a number of methods for interacting with files, which are exposed on the `ops.Container` class, but Pebble can't be used for file operations outside of Kubernetes (K8s) charms. This specification defines the API for a library that provides an `ops.Container` style interface for interacting with files in both K8s and machine charms. This will allow greater unification of code for machine and K8s charms, as charmers will be able to use the same API for file operations in both contexts. This unified API can be extended with richer file handling methods if needed, and complements an existing pattern used by charmers to unify machine and K8s charm code, a `WorkloadBase` class.

## Rationale

`ops`  provides an API for interacting with files in the workload container via the `ops.Container` object, providing a wrapper over the `pebble`  API, exposing `pebble` methods like pushing and pulling data or files to and from the workload container, listing and removing files, and making directories, as well as the ability to check if a file or directory exists. This maps well to the API that `pebble` provides, but, this is a very different API to using the Python standard library to do file operations (using for example `pathlib`, `shutil`, and `os`) meaning that totally different code is needed to manage files in a workload container than you would use to manage files in the charm's container, in a machine charm, and in other Python scripts you might write outside of a charm. An explicit goal of this library is to allow charms to use the same API in all of these contexts.

An `ops.Container`-like API for interacting with files outside of a k8s charm's workload container would allow greater code re-use between k8s and machine charms. Additionally, some charms already use a similar pattern to abstract away these differences, a `WorkloadBase` abstract base class, which provides an `ops.Container`-like interface, and allows the differences between the machine and K8s workload operations to be encapsulated in a workload class rather than distributed across the charm code. See [Further Information](#further-information) for more on this.

The possibility that machine charms might also come with Pebble some time in the future has been mentioned a few times. This would go a long way towards resolving these differences, as file operations could be performed using a pebble running on the virtual machine, or in the charm container. This is the primary reason why this library proposes unifying on an `ops.Container`-like API for interacting with files - to ease the transition to actually using Pebble to interact with files in these contexts.

Two additional reasons make unifying on a `pathlib`-like API a less attractive option. Firstly, the elegant  `pathlib.Path` API does not cover all of the operations needed, in particular, `chown`, so the API would need to be extended. Secondly, attempting to provide, for remote files, the file opening semantics that `pathlib.Path` does for local files seems to be impossible. We could use temporary files, but handling cases such as the charm exiting mid-write adds complexity, and it would probably be prudent not to provide `pathlib.Path.open`. These considerations make this option less attractive, though there are certainly reasonable solutions here - there's no reason we couldn't provide a unified Path-like API sans open, with file creation operations extended with owner arguments. However, this would still require both machine and kubernetes charms using the existing ways (stdlib and ops.Container respectively) to modify their code at many call sites to use this unified API - as would machine charms switching to an ops.Container-like api. In the case where machine charms want to go beyond the common API to perform additional file operations (like opening files in read+write mode), the code would be more harmonious in the Path-like case, but it's not clear that this is an advantage - perhaps it would be better to have it appear extremely obvious when machine-only operations are being used.  Ultimately it is the future possibility of pebble in machine charms that is the deciding factor here, as unifying on the ops.Container API will ease migration to performing file operations via Pebble if that is desirable.

## Specification

The high level idea is that the library will provide an object implementing the `ops.Container` file methods, but acting on files in the local machine/container. A `Protocol` would be provided to describe the operations that this object has in common with `ops.Container`. Some rich file methods/helpers will also be provided, which will accept an object of that `Protocol`, allowing them to be used for both local and container file operations. with an `ops.Container`.

#### Outline

```py
"""This code block outlines the signatures of the methods provided."""
from __future__ import annotations

import typing
from pathlib import Path, PurePath
from typing import BinaryIO, Iterable, Protocol, TextIO

import ops

class Protocol(typing.Protocol):
    ## ops.Container methods
    # signatures are exactly the same
    # local implementation will raise the same pebble exception types

    # exec won't be provided in the initial release of this library
    # but may be provided in a future release

    def exists(self, path: str | PurePath) -> bool:
        if self._container:
            return ...
        ...
        return ...

    def isdir(self, path: str | PurePath) -> bool:
        ...

    def list_files(
        self,
        path: str | PurePath,
        *,
        pattern: str | None = None,
        itself: bool = False,
    ) -> list[ops.pebble.FileInfo]:
        ...

    def make_dir(
        self,
        path: str | PurePath,
        *,
        make_parents: bool = False,
        permissions: int | None = None,
        user_id: int | None = None,
        user: str | None = None,
        group_id: int | None = None,
        group: str | None = None,
    ) -> None:
        ...

    def push_path(
        self,
        source_path: str | Path | Iterable[str | Path],
        dest_dir: str | PurePath,
    ) -> None:
        ...

    def pull_path(
        self,
        source_path: str | PurePath | Iterable[str | PurePath],
        dest_dir: str | Path,
    ) -> None:
        ...

    def remove_path(self, path: str | PurePath, *, recursive: bool = False) -> None:
        ...

    def push(
        self,
        path: str | PurePath,
        source: bytes | str | BinaryIO | TextIO,
        *,
        encoding: str = 'utf-8',
        make_dirs: bool = False,
        permissions: int | None = None,
        user_id: int | None = None,
        user: str | None = None,
        group_id: int | None = None,
        group: str | None = None,
    ) -> None:
        ...

    @typing.overload
    def pull(self, path: str | PurePath, *, encoding: None) -> BinaryIO:
        ...
    @typing.overload
    def pull(self, path: str | PurePath, *, encoding: str = 'utf-8') -> TextIO:
        ...
    def pull(
        self,
        path: str | PurePath,
        *,
        encoding: str | None = 'utf-8',
    ) -> BinaryIO | TextIO:
        ...

class Local:
    # implements Protocol for local file operations
    ...

# helpers / rich methods

def ensure_contents(
    context: FileOperationsProtocol,
    path: str | PurePath,
    source: bytes | str | BinaryIO | TextIO,
    *,
    encoding: str = 'utf-8',
    make_dirs: bool = False,  # remove this arg and have it behave as if True?
    permissions: int | None = None,
    user_id: int | None = None,
    user: str | None = None,
    group_id: int | None = None,
    group: str | None = None,
) -> bool:
    """Ensure source can be read from path. Return True if any changes were made.

    Ensure that path exists, and contain source, and has the correct permissions,
    and has the correct file ownership.
    Return True if any changes were made, including chown or chmod, otherwise
    return False.
    """
    ...

```

A proof of concept implementation can be found [here](https://github.com/james-garner-canonical/file-ops).

#### Exceptions

Due to providing a Pebble-like API, and to ease migration if the internal implementation of local file operations ever directly used Pebble itself (for example, if machine charms eventually come with Pebble), this library raises Pebble errors for file operations.

For instance, when calling a method like `make_dir` when the target already exists  `os` or `pathlib` would raise a `FileExistsError` error, while  `ops.Container` would raise a `pebble.PathError`. This library will raise a `pebble.PathError`  in this case, whether operating via an `ops.Container` or in the current machine/container.

Additionally, different `pebble` methods may raise different error types for similar logical errors. For example, while `make_dir` raises a `pebble.PathError` if the parent directory of the target doesn't exist (unless `make_parents` is `True`), `list_files` raises a `pebble.APIError` if the target doesn't exist. Again, this library will raise the corresponding Pebble exception types, regardless of whether the error is encountered via `ops.Container`, or via its own implementation of local filesystem operations.

If extending the Pebble exception hierarchy to allow more specific error types to be caught (e.g. `FileExistsError` and `PermissionError` vs `pebble.PathError`), or to unify logical errors across Pebble errors (e.g. `FileNotFoundError` vs `pebble.PathError` and `pebble.APIError`) is desirable when working on this library, such features should first be added to the `ops.pebble` client, to keep this library's implementation of operations using `ops.Container` simple. The initial release of this library may therefore be delayed until the corresponding `ops` version is released.

#### Distribution

This library will be distributed as a PyPI package (rather than a traditional charm-lib). This is because it provides functionality intended to make it easier to write machine/k8s agnostic code, which may be useful for libraries. Using a PyPI packing makes it possible for a charm-lib to depend on it (via `PYDEPS` - discouraged at the moment, but probably better than duplicating a lot of code or adding a note for users to manually install a `FileOperations` charm-lib). It also makes it easy for future charm libraries that are also distributed as packages to depend on `FileOperations` using standard Python dependency management, rather than needing to essentially vendor a charm-lib.

Distributing this functionality as part of `ops` itself would also address these concerns, and with even less friction for users, but the strong guarantee of backwards compatibility that `ops` provides makes it less well suited as a place to experiment with new features like this. If this library proves to be useful for charmers, it may eventually migrate into `ops`.

## Example usage

This mostly just highlights that using `FileOperations` looks very much like existing k8s charm code, but supports machine charms as well.

```py
"""loki_k8s.v{0,1}.loki_push_api"""

# original
def _is_promtail_installed(self, promtail_info: dict, container: Container) -> bool:
    workload_binary_path = f"{WORKLOAD_BINARY_DIR}/{promtail_info['filename']}"
    try:
        container.list_files(workload_binary_path)
    except (APIError, FileNotFoundError):
        return False
    return True

# with FileOperations -- machine charm compatible code
def _is_promtail_installed(
    self, promtail_info: dict, container: Container | None = None
) -> bool:
    workload_binary_path = f"{WORKLOAD_BINARY_DIR}/{promtail_info['filename']}"
    try:
        FileOperations(container).list_files(workload_binary_path)
    except FileNotFoundError:
        return False
    return True
```

```py
# mysql-k8s/src/mysql_k8s_helpers.py
def write_content_to_file(
    self,
    path: str,
    content: str,
    owner: str = MYSQL_SYSTEM_USER,
    group: str = MYSQL_SYSTEM_USER,
    permission: int = 0o640,
) -> None:
    self.container.push(path, content, permissions=permission, user=owner, group=group)

# mysql/src/mysql_vm_helpers.py
@staticmethod
def write_content_to_file(
    path: str,
    content: str,
    owner: str = MYSQL_SYSTEM_USER,
    group: str = "root",
    permission: int = 0o640,
) -> None:
    with open(path, "w", encoding="utf-8") as fd:
        fd.write(content)
    shutil.chown(path, owner, group)
    os.chmod(path, mode=permission)

# FileOperations
def write_content_to_file(
    self,
    path: str,
    content: str,
    owner: str = MYSQL_SYSTEM_USER,
    group: str = MYSQL_SYSTEM_USER,
    permission: int = 0o640,
) -> None:
    files = FileOperations(getattr(self, 'container', None))
    files.push(path, content, permissions=permission, user=owner, group=group)

```

## Further Information

Some existing charms use a `WorkloadBase` class to abstract away some of the differences between machine charms and k8s charms. The individual charms then create a `Workload` class that inherits from `WorkloadBase` and provide the differing implementations that are required.

For example, the vault-operator charm defines a [Machine](https://github.com/canonical/vault-operator/blob/36034712223c878bcdacddd78be09f464e5e0f13/src/machine.py#L21) class, while vault-k8s-operator defines a [Container](https://github.com/canonical/vault-k8s-operator/blob/f504357aced877820e10614012b4991897749414/src/container.py#L13) class, both of which inherit from the `WorkloadBase` class defined in a shared [charm-lib](https://github.com/canonical/vault-k8s-operator/blob/f504357aced877820e10614012b4991897749414/lib/charms/vault_k8s/v0/vault_managers.py#L148). Apparently this pattern may have originated with the Data team. A `WorkloadBase` class is defined under src/core/workload.py in [kafka-k8s-operator](https://github.com/canonical/kafka-k8s-operator/blob/main/src/core/workload.py#L116) and [kafka-operator](https://github.com/canonical/kafka-operator/blob/main/src/core/workload.py#L116), and in [zookeeper-k8s-operator](https://github.com/canonical/zookeeper-k8s-operator/blob/main/src/core/workload.py#L107) and [zookeeper-operator](https://github.com/canonical/zookeeper-operator/blob/main/src/core/workload.py#L107). In [spark-history-server-k8s-operator](https://github.com/canonical/spark-history-server-k8s-operator) there is an [AbstractWorkload](https://github.com/canonical/spark-history-server-k8s-operator/blob/ac4836cd7686b7ef082aa46f2c03d2b4ec388f04/src/common/workload.py#L10) class, which is inherited by a [K8sWorkload](https://github.com/canonical/spark-history-server-k8s-operator/blob/ac4836cd7686b7ef082aa46f2c03d2b4ec388f04/src/common/k8s.py#L19) class and a [SparkHistoryWorkloadBase](https://github.com/canonical/spark-history-server-k8s-operator/blob/ac4836cd7686b7ef082aa46f2c03d2b4ec388f04/src/core/workload.py#L53) class, with a [SparkHistoryServer](http://SparkHistoryServer) class inheriting from both..

These `WorkloadBase` classes have an `ops.Container`-like API. `FileOps` is a subset of the `ops.Container`-like API. Currently these `WorkloadBase` classes only implement the methods they need, so they don't implement, for example, all the file operations. The work of providing file operations for both implementations could be entirely taken care of by having `WorkloadBase` inherit from `FileOps`. This would help avoid diverging implementations in different `WorkloadBase` classes, and would eliminate the temptation to do file operations outside the `WorkloadBase` class when you only need them in one of the machine or k8s cases. A demo PR showing what this would look like is available for the kafka [k8s](https://github.com/james-garner-canonical/kafka-k8s-operator/pull/2) and [machine](https://github.com/james-garner-canonical/kafka-operator/pull/1) charms, and for the vault [k8s](https://github.com/james-garner-canonical/vault-k8s-operator/pull/1) and [machine](https://github.com/james-garner-canonical/vault-operator/pull/1) charms.

`ops[testing]` aka Scenario uses a fake Pebble implementation for testing, writing files to a local temporary directory. When writing this library, with an eye to making it easy to possibly include in `ops` eventually, we should keep in mind this potential use case.
