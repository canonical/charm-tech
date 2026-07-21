# OP056 — Pathlike File Handling Library

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2023-03-09 |

## Abstract

This specification outlines a pathlib-style API for interacting with files in a Kubernetes charm's workload container via a `ContainerPath` object. To allow the same code to be used for interacting with the local filesystem as with a `ContainerPath`, this library will either provide helper functions compatible with `pathlib.Path | ContainerPath`, or provide a protocol specifying a modified subset of pathlib operations, and a `LocalPath` adaptor class provides these modifications for `pathlib.Path`. Special care is taken to support Python 3.8+, and to avoid a `ContainerPath` object mistakenly being used with functions that expect a pathlike object denoting a local path.

## Rationale

Ops provides an API via the ops.Container class for performing file operations in the Kubernetes workload container via Pebble. File operations performed in the charm container or in machine charms cannot use this API, and instead perform file operations using the Python standard library. If the same API could be used in both contexts, this could lead to decreased duplication of code, and ease the implementation of unified codebases for machine and Kubernetes charms.

A unified API could be provided by either providing an `ops.Container` style API for interacting with the local system, or by providing a modified API for working with workload containers via Pebble. Spec [OP053](https://docs.google.com/document/u/0/d/1yQ7RoIBty6CDnKTzCbCzubq-PKLdRPkHGuT7_Zu4124/edit) proposed unifying on the `ops.Container` interface for file operations. However, several concerns were raised by charmers.

The first is that using an API that most programmers are familiar with will make charm code easier for new charmers to read, understand, and contribute to. It will be helpful for charm code to resemble, as much as possible, straightforward Python programs whose semantics and control flow are easy to follow for non-charmers. Python's pathlib is a widely used  interface - one which will be familiar to many Python programmers. Of the 422 charms I know of, 386 contain the string 'os.path', and 352 contain the string 'pathlib'.

Secondly, there is the concern that machine charms may need more functionality than the `ops.Container` API provides. A pathlib-like API for the common subset of local and container file operations will provide a graceful  pathway to using local file system operations outside that subset, while additional rich methods can always be provided by this library as module-level helper functions without clashing with this API.

Finally, it's worth noting that there is no strong reason why ops.Container did not use a pathlib style API in the first place - its API follows the underlying commands exposed by pebble over its API, which is both a reasonable and natural choice, but not one that we are bound by here.

## Specification

This specification describes the methods and attributes that this file operations library will expose for common local and container file operations. It also outlines the concrete implementations provided in the form of the `ContainerPath` class and module level functions.

This library will support Python 3.8+, because ops currently supports Python 3.8+. In addition to the usual constraints on the Python code written, this also implies that a Python 3.8 pathlib.PosixPath object must be compatible with this library. Therefore, methods and arguments added to pathlib after Python 3.8 will not be part of the common file operations protocol. To ease compatibility between `ContainerPath` and `pathlib.Path`, `ContainerPath` may be further extended in future to support these additional methods and arguments without changing the protocol - charms using a higher minimum Python version could use `pathlib.Path | ContainerPath` or `LocalPath | ContainerPath` typing to express this.

Note also that the `ContainerPath` class provided by this library will not implement the `os.PathLike` protocol expected by many Python builtin and stdlib functions, such as `open`. Specifically, this means that there will be no `ContainerPath.__fspath__` method, and functions like `open` will raise a `TypeError` when called with a `ContainerPath`. This is because if you have a `ContainerPath` instance, `container_path`, which refers to a path `/foo/bar`, then `open(container_path)` has no way to operate on the file in the container, and operating on a local file named `/foo/bar` would be surprising, and most likely not the user's intent. For the same reason, there will be no `ContainerPath.__bytes__` method.

#### Exceptions

In general, since this API follows pathlib, it should convert pebble errors like `PathError` or `APIError` to the relevant builtin filesystem errors, like `FileNotFound`, `PermissionError`, etc.

However, we also need to consider the case where we can't connect to the workload's Pebble, which will result in a `pebble.ConnectionError`. Code written using this library to handle being called from a machine or K8s charm will need to be aware of this possibility, and should either catch this error itself, or document the need for K8s users to do so. To avoid the need for machine / K8s agnostic code to import `ops.pebble` just for exception handling, `pebble.ConnectionError` will be re-exported by this library. K8s specific code that uses this library, and probably already imports `pebble`, should feel free to use `pebble.ConnectionError` directly.

#### Protocol

The public protocol has been broken down into several private protocols that specify clear subsets of the methods provided. Only a single protocol will be public. Explanations are given for methods that will not be supported.

```py
from __future__ import annotations
import typing
from typing import Generator

if typing.TYPE_CHECKING:
    from typing_extensions import Self, TypeAlias

# based on typeshed.stdlib.StrPath
# https://github.com/python/typeshed/blob/main/stdlib/_typeshed/__init__.pyi#L173
_StrPath: TypeAlias = 'str | StrPathLike'

# based on typeshed.stdlib.os.PathLike
# https://github.com/python/typeshed/blob/main/stdlib/os/__init__.pyi#L877
class StrPathLike(typing.Protocol):
    def __fspath__(self) -> str: ...

# based on typeshed.stdlib.pathlib.PurePath
# https://github.com/python/typeshed/blob/main/stdlib/pathlib.pyi#L29
class _PurePathSubset(typing.Protocol):
    """Defines the subset of pathlib.PurePath methods required."""

    # constructors
    # ContainerPath constructor will differ from pathlib.Path constructor
    # not part of the protocol
    # def __new__(cls, *args: _StrPath, **kwargs: object) -> Self: ...
    # NOTE: __new__ signature is version dependent
    # def __init__(self, *args): ...

    def __hash__(self) -> int: ...
    # ContainerPath will hash on (self._container.name, self._path)

    # def __reduce__(self): ...
    # ops.Container isn't pickleable itself, but we can provide a custom constructor
    # for ContainerPath that works with the unpickling protocol, and will attempt to
    # make a Container object connected to the appropriate pebble socket
    # for simplicity this will be omitted from v1 unless requested

    # comparison methods
    # ContainerPath comparison methods will return NotImplemented if other is not a
    # ContainerPath with the same container; otherwise the paths are compared
    def __lt__(self, other: Self) -> bool: ...
    def __le__(self, other: Self) -> bool: ...
    def __gt__(self, other: Self) -> bool: ...
    def __ge__(self, other: Self) -> bool: ...
    def __eq__(self, other: object, /) -> bool: ...

    # / operator

    def __truediv__(self, key: _StrPath) -> Self: ...
    # def __rtruediv__(self, key: StrPathLike) -> Self: ...
    # ommitted from v1 protocol
    # doesn't seem worth supporting until (if) ContainerPath gets relative paths
    # when we have relative paths, it will be meaningfull to support the following:
    # def __truediv__(self, key: _StrPath | Self) -> Self: ...
    # def __rtruediv__(self, key: _StrPath | Self) -> Self: ...
    # `ContainerPath / (str or pathlib.Path)`, or `(str or pathlib.Path) / containerPath`
    # will result in a new ContainerPath with the same container.
    # `ContainerPath / ContainerPath` is an error if the containers are not the same,
    # otherwise it too results in a new ContainerPath with the same container.

    # def __fspath__(self) -> str: ...
    # we don't want ContainerPath to be os.PathLike

    # def __bytes__(self) -> bytes: ...
    # we don't want ContainerPath to be mistakenly used like a pathlib.Path

    def __str__(self) -> str: ...
    # all Python objects provide this, via the base object.__str__ method if not directly
    #
    # str(pathlib.Path('/foo/bar')) -> '/foo/bar', but what should
    # str(ContainerPath('/foo/bar', container=...)) return?
    #
    # PROPOSAL: '/charm/containers/container-name/pebble.socket/foo'
    #
    # Please see the Discussion section for an overview of options here and to keep
    # discussion of this issue in one place

    # def as_posix(self) -> str: ...
    # related to the __str__ discussion
    #
    # PROPOSAL: not part of the protocol

    # URIs
    # this doesn't seem useful and is potentially confusing,so it won't be implemented
    # likewise, the constructor (added in 3.13) won't be implemented
    # def as_uri(self) -> str: ...
    # @classmethod
    # def from_uri(uri: str) -> Self: ...

    def is_absolute(self) -> bool: ...

    # def is_reserved(self) -> bool: ...
    # this will always return False with a PosixPath. Since we assume a Linux container
    # so let's just drop it from the protocol for now

    def match(self, path_pattern: str) -> bool: ...
    # signature extended further in 3.12+
    # def match(self, pattern: str, * case_sensitive: bool = False) -> bool: ...
    # extended signature is not part of the protocol but may eventually be provided on
    # ContainerPath to ease compatibility with pathlib.Path on 3.12+

    # def full_match(self, pattern: str, * case_sensitive: bool = False) -> bool: ...
    # 3.13+
    # not part of the protocol but may eventually be provided on ContainerPath
    # to ease compatibility with pathlib.Path on 3.13+

    # def relative_to(self, other: _StrPath, /) -> Self: ...
    # this produces relative paths, which we shouldn't be using in any code designed to
    # be compatible with both machines and containers, since pebble will error on any
    # relative paths at runtime -- if users want to work with relative paths, I think
    # they should explicitly work with a PurePath rather than a ContainerPath, and then
    # construct the ContainerPath when they have the absolute path they need
    #
    # Python 3.12 deprecates the below signature, to be dropped in 3.14
    # def relative_to(self, *other: _StrPath) -> Self: ...
    # to ease future compatibility, we'd just drop support for the old signature
    # from the protocol now if it was included
    #
    # Python 3.12 further modifies the signature with an additional keyword argument
    # def relative_to(self, other: _StrPath, walk_up: bool = False) -> Self: ...
    # this would not part of the protocol but could eventually be provided on
    # ContainerPath to ease compatibility with pathlib.Path on 3.12+ if we someday
    # support relative paths

    # def is_relative_to(self, other: _StrPath) -> Self: ...  # 3.9+
    # not part of protocol but can be provided on ContainerPath implementation
    # to ease compatibility with pathlib.Path on 3.9+

    def with_name(self, name: str) -> Self: ...

    def with_suffix(self, suffix: str) -> Self: ...

    # def with_stem(self, stem: str) -> Self: ...  # 3.9+
    # not part of protocol but can be provided on ContainerPath implementation
    # to ease compatibility with pathlib.Path on 3.9+
    # could be added to the protocol if we're happy for LocalPath to double as backports

    # def with_segments(self, *pathsegments: _StrPath) -> Self: ...
    # required for 3.12+ subclassing machinery
    # not part of the protocol (otherwise LocalPath would have to backport it)
    # but it is a useful method -- given a ContainerPath with some container,
    # you can make another path with the same container cleanly, so it'll be implemented
    # on ContainerPath

    def joinpath(self, *other: _StrPath) -> Self: ...
    # *other cannot be a ContainerPath

    @property
    def parents(self) -> Sequence[Self]: ...

    @property
    def parent(self) -> Self: ...

    @property
    def parts(self) -> tuple[str, ...]: ...

    # @property
    # def drive(self) -> str: ...
    # will always be '' for Posix -- maybe drop it from the protocol
    # so users get more useful autocompletions?

    # @property
    # def root(self) -> str: ...
    # potentially error prone -- ContainerPath.root / Path('foo') is not a ContainerPath

    # @property
    # def anchor(self) -> str: ...
    # this is drive + root

    @property
    def name(self) -> str: ...

    @property
    def suffix(self) -> str: ...

    @property
    def suffixes(self) -> list[str]: ...

    @property
    def stem(self) -> str: ...

class _ConcretePathSubset(typing.Protocol):
    """Defines the subset of pathlib.Path methods required.

    Note that the current idea is to extend the signatures of the file creation methods,
    to support setting ownership and permissions at file creation time, as that's when
    Pebble sets them. See _ConcretePathSubsetExtendedSignatures for details.

    The idea of extending the signatures is still up for debate. The alternative would be
    module level helper functions taking the extended arguments instead. This would
    eliminate the need for the LocalPath class.
    """

    # pull
    def read_text(
        self,
        encoding: str | None = None,
        errors: typing.Literal['strict', 'ignore'] | None = None,
        # newline: typing.Literal['', '\n', '\r', '\r\n'] | None = None,  # 3.13+
    ) -> str: ...

    def read_bytes(self) -> bytes: ...

    # push -- note that (e.g.) additional arguments are required to support setting
    # ownership and permission via pebble -- see _ConcretePathSubsetExtendedSignatures
    def write_bytes(
        self,
        data: bytes,
    ) -> int: ...  # NOTE: supposed to return the number of bytes written

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: typing.Literal['strict', 'ignore'] | None = None,
        # TODO: errors -- do we just suppress pebble errors here?
        # 'strict' -> raise ValueError for encoding error
        # 'ignore' -> just write stuff anyway, ignoring errors
        # None -> 'strict'
        # newline: typing.Literal['', '\n', '\r', '\r\n'] | None = None,  # 3.10+
    ) -> int: ...  # NOTE: supposed to return the number of bytes written

    # make_dir -- note that (e.g.) additional arguments are required to support setting
    # ownership and permission via pebble -- see _ConcretePathSubsetExtendedSignatures
    def mkdir(
        self,
        mode: int = 0o777,  # TODO: check default value with pebble
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None: ...

    # remove
    def rmdir(self) -> None: ...

    def unlink(self, missing_ok: bool = False) -> None: ...

    # list_files
    def iterdir(self) -> typing.Iterable[Self]: ...

    def glob(
        self,
        pattern: str,  # support for _StrPath added in 3.13
        # *,
        # case_sensitive: bool = False,  # added in 3.12
        # recurse_symlinks: bool = False,  # added in 3.13
    ) -> Generator[Self]: ...

    def rglob(
        self,
        pattern: str,  # support for _StrPath added in 3.13
        # *,
        # case_sensitive: bool = False,  # added in 3.12
        # recurse_symlinks: bool = False,  # added in 3.13
    ) -> Generator[Self]: ...
        # NOTE: to ease implementation, this could be dropped from the v1 release

    # walk was only added in 3.12 -- let's not support this for now, as we'd need to
    # implement the walk logic for LocalPath as well as whatever we do for ContainerPath
    # (which will also be a bit trickier being unable to distinguish symlinks as dirs)
    # While Path.walk wraps os.walk, there are still ~30 lines of pathlib code we'd need
    # to vendor for LocalPath.walk
    # def walk(
    #     self,
    #     top_down: bool = True,
    #     on_error: typing.Callable[[OSError], None] | None = None,
    #     follow_symlinks: bool = False,  # NOTE: ContainerPath runtime error if True
    # ) -> typing.Iterator[tuple[Self, list[str], list[str]]]:
    #     # TODO: if we add a follow_symlinks option to Pebble's list_files API, we can
    #     #       then support follow_symlinks=True on supported Pebble (Juju) versions
    #     ...

    # def stat(self) -> os.stat_result: ...
    # stat follows symlinks to return information about the target
    # Pebble's list_files tells you if a file is a symlink, but not what the target is
    # TODO: support if we add follow_symlinks to Pebble's list_files API

    # def lstat(self) -> os.stat_result: ...
    # this may not be in v1, because we can only provide best effort completion on the
    # pebble side. Maybe we can provide a top-level fileinfo helper

    def owner(self) -> str: ...

    def group(self) -> str: ...

    # exists, is_dir and is_file are problematic, because they follow symlinks by default
    # and Pebble will only tell us if the file is a symlink - nothing about its target.
    #
    # as written currently, the behaviour for ContainerPath will be to raise a
    # NotImplementedError if the target is a symlink
    #
    # Python 3.12 and 3.13 add keyword arguments to control this (defaulting to True)
    # The ContainerPath implementation should accept the follow_symlinks argument.
    # Maybe the LocalPath implementation should too, so that the protocol can as well?
    #
    # In this case, for ContainerPath, if follow_symlinks==True and the result type
    # is pebble.FileTypes.SYMLINK, then we'll raise a NotImplementedError at runtime.
    #
    # TODO: add to Pebble an optional eval/follow_symlinks arg for the list_files api,
    #       and then only raise NotImplementedError if follow_symlinks=True AND the
    #       result type is pebble.FileTypes.SYMLINK, AND the pebble version is too old

    def exists(self) -> bool:  # follow_symlinks=True added in 3.12
        """Whether this path exists.

        WARNING: ContainerPath will raise a NotImplementedError if the path is a symlink.
        """
        ...

    def is_dir(self) -> bool:  # follow_symlinks=True added in 3.13
        """Whether this path is a directory.

        WARNING: ContainerPath will raise a NotImplementedError if the path is a symlink.
        """
        ...

    def is_file(self) -> bool:  # follow_symlinks=True added in 3.13
        """Whether path is a regular file.

        WARNING: ContainerPath will raise a NotImplementedError if the path is a symlink.
        """
        ...

    # def is_mount(self) -> bool: ...
    # pebble doesn't support this

    def is_symlink(self) -> bool: ...

    # def is_junction(self) -> bool: ...
    # 3.12
    # this will always be False in ContainerPath since we assume a Linux container
    # so let's just drop it from the protocol for now

    def is_fifo(self) -> bool: ...

    def is_socket(self) -> bool: ...

    # is_block_device and is_char_device are problematic because pebble only tells us if
    # it's a device at all. We can provide an is_device module level helper if needed.
    # def is_block_device(self) -> bool: ...
    # def is_char_device(self) -> bool: ...

    ################################################################################
    # these concrete methods are currently ruled out due to lack of Pebble support #
    ################################################################################

    # def chmod
        # pebble sets mode on creation
        # can't provide a separate method
        # needs to be argument for other functions
        # (same treatment needed for chown)

    # link creation, modification, target retrieval
    # pebble doesn't support link manipulation
    # def hardlink_to
    # def symlink_to
    # def lchmod
    # def readlink
    # def resolve

    # def samefile
        # pebble doesn't return device and i-node number
        # can't provide the same semantics

    # def open
        # the semantics would be different due to needing to make a local copy

    # def touch
        # would have to pull down the existing file and push it back up just to set mtime

    ##################
    # relative paths #
    ##################

    # OPINION: we shouldn't support relative paths in v1 (if ever)
    #
    # if we support relative paths, we'd need to implicitly call absolute before every
    # call that goes to pebble, and it's not clear whether it's a good idea to implement
    # cwd, which absolute would depend on -- we'd have to pebble exec cwd, which wouldn't
    # work in certain images (bare rocks)
    #
    # I think it would be fine for v1 to only support absolute paths, raising an error
    # on file operations with relative paths

    # the following methods would require us to either hardcode cwd or use a pebble.exec
    # def cwd
        # typically /root in container
        # do we need to query this each time? can we hardcode it?
    # def absolute
        # interpret relative to cwd

    # the following methods would require us to either hardcode home or use a pebble.exec
    # def home
        # typically /root in container
        # do we need to query this each time? can we hardcode it?
    # def expanduser
        # '~' in parts becomes self.home

class _ConcretePathSubsetExtendedSignatures(_ConcretePathSubset, typing.Protocol):
    # push
    def write_bytes(
        self,
        data: bytes,
        # extended with chmod + chown args:
        *,
        mode: int | None = None,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> int: ...

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: typing.Literal['strict', 'ignore'] | None = None,
        # extended with chmod + chown args:
        *,
        mode: int | None = None,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> int: ...

    # make_dir
    def mkdir(
        self,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
        # extended with chown args:
        *,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> None: ...

class _CommonProtocol(_ConcretePathSubset, _PurePathSubset, typing.Protocol):
    """Using this protocol does not allow setting permissions and ownership on files.

    pathlib.Path is compatible with this protocol out of the box.

    This is just in the spec to make the differences between pathlib.Path and the
    library's protocol hopefully clearer for readers. It should be pretty much equivalent
    to ContainerPath | pathlib.Path, I think (though note that this depends on the
    installed pathlib version).

    I think we might prefer the encouraged workflow to be type annotating with
    ContainerPath | pathlib.Path and using module level helper functions to do write_...
    etc instead of using a Protocol + LocalPath. If we took that approach we could drop
    LocalPath and the Protocol altogether. See Discussion for more.
    """

class Protocol(_ConcretePathSubsetExtendedSignatures, _PurePathSubset, typing.Protocol):
    """Using this protocol allows setting permissions and ownership on file creation.

    pathlib.Path is not compatible with this protocol due to the extended signatures,
    and will require wrapping with LocalPath.

    This is the only top-level public bit of all this protocol stuff.
    """
```

#### Implementation

The concrete classes and module-level functions this library will provide.

```py
class ContainerPath:  # implements Protocol
    def __init__(*parts: _StrPath, *, container: ops.Container) -> None:
        self._path = pathlib.PurePath(*parts)  # used for path operations
        self._container = container  # used for file operations

    # + Implementation of all the protocol methods

    # extra non-protocol method to facilitate subclassing/etc on 3.12+
    def with_segments(self, *pathsegments: _StrPath) -> Self: ...

    # extended 3.12 and 3.13+ signatures
    def exists(self, follow_symlinks: bool = True) -> bool: ...
    def is_dir(self, follow_symlinks: bool = True) -> bool: ...
    def is_file(self, follow_symlinks: bool = True) -> bool: ...

class LocalPath(pathlib.PosixPath):  # implements Protocol
    """Implementation of the 3 methods from _ConcretePathSubsetExtendedSignatures.

    The idea of extending the signatures is still up for debate. The alternative would be
    module level helper functions taking the extended arguments instead. This would
    eliminate the need for the LocalPath class. See the Discussion section for more.

    Oh and if we want to handle follow_symlinks for exists/is_dir/is_file in the protocol
    they'd need to go in LocalPath too for compatibility with Python versions that don't
    have those arguments. I would only provide these if we go with LocalPath for the file
    creation methods' extended signatures. (They can go in ContainerPath either way).
    """

    # should we provide these extended signatures, or use module level helper functions?
    def write_bytes(
        self,
        data: bytes,
        # extended with chmod + chown args:
        *,
        mode: int | None = None,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> int: ...

    def write_text(
        self,
        data: str,
        encoding: str | None = None,
        errors: typing.Literal['strict', 'ignore'] | None = None,
        # extended with chmod + chown args:
        *,
        mode: int | None = None,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> int: ...

    def mkdir(
        self,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
        # extended with chown args:
        *,
        user: str | int | None = None,
        group: str | int | None = None,
    ) -> None: ...

    # should we backport these extended 3.12 and 3.13+ signatures?
    # def exists(self, follow_symlinks: bool = True) -> bool: ...
    # def is_dir(self, follow_symlinks: bool = True) -> bool: ...
    # def is_file(self, follow_symlinks: bool = True) -> bool: ...

########################
# module level helpers #
########################

# def write_text / write_bytes / mkdir
#
# DECISION: we won't provide these, we'll do it via LocalPath
#
# file creation function(s) taking StrPathLike | ContainerPath as target
# as well as owner and permission arguments for chown and chmod
#
# these are a potential alternative way we could provide the ability to set file
# permissions on creation without needing to switch all your Paths to LocalPaths
# they won't be provided if we provide the extended LocalPath.write_{etc} methods
#
# if we provide these, then we don't really need the LocalPath class at all, do we?
# if we don't need the LocalPath class, then would we need the Protocol?
# users would be able to just use `pathlib.Path | fileops.Container` instead
#
# would it be good to provide these? See the Discussion section for more.

# def write_bytes(
#     path: StrPathLike | ContainerPath,
#     data: bytes,
#     *,
#     # extended with chmod + chown args:
#     mode: int | None = None,
#     user: str | int | None = None,
#     group: str | int | None = None,
# ) -> int:
#     if isinstance(path, ContainerPath):
        ...

# def write_text(
#     path: StrPathLike | ContainerPath,
#     data: str,
#     *,
#     encoding: str | None = None,
#     errors: typing.Literal['strict', 'ignore'] | None = None,
#     # extended with chmod + chown args:
#     mode: int | None = None,
#     user: str | int | None = None,
#     group: str | int | None = None,
# ) -> int: ...

# def mkdir(
#     path: StrPathLike | ContainerPath,
#     *,
#     mode: int = 0o777,
#     parents: bool = False,
#     exist_ok: bool = False,
#     # extended with chown args:
#     user: str | int | None = None,
#     group: str | int | None = None,
# ) -> None: ...

# related to the ContainerPath.__str__ discussion. Please see the Discussion section
def to_posix(path: StrPathLike | ContainerPath) -> str:
    if isinstance(path, ContainerPath):
        return str(ContainerPath._path)
    return str(path)

# ops.Container provides push_path and pull_path for recursively copying files
# the pathlib API doesn't support this, but we could provide this capability in a unified
# way following the stdlib's shutil.copytree
#
# would explicit push_path and pull_path methods be better, or should we try to follow
# shutil.copytree at least in part?
_T = TypeVar("_T", bound=Union[StrPathLike, ContainerPath])
def copytree(
    src: StrPathLike | ContainerPath,
    dest: _T,
    # NOTE: could drop all the kwargs to use ops.Container.{push,pull}_path for k8s
    #       otherwise we'd need to roll our own to handle the kwargs we can support
    *,
    # symlinks: bool = False,  # can't support customising this with ContainerPath
    # alternatively we could accept the argument and ignore it with ContainerPath
    # or raise if it's True with ContainerPath
    ignore: Callable[[str, list[str]], list[str]] | None = None,
    # copy_function = shutil.copy2,  # can't support customising this with ContainerPath
    # alternatively we could accept the argument and ignore it with ContainerPath
    ignore_dangling_symlinks: bool = False,  # idk if we can properly support this
    dirs_exist_ok: bool = False,
) -> _T:
    """What about errors? Presumably convert ops.MultiPushPullError into a shutil.Error
    """
    # implementation assuming no kwargs, with no error handling
    if isinstance(src, ContainerPath):
        if isinstance(dest, ContainerPath):
            temp = ...
            src._container.pull_path(src.as_posix(), temp)
            dest._container.push_path(temp, dest.as_posix())
        else:
            src._container.pull_path(src.as_posix(), dest)
    else:
        if isinstance(dest, ContainerPath):
            dest._container.push_path(src, dest.as_posix())
        else:
            shutil.copytree(src, dest, dirs_exist_ok = True)
    return dest

# we proposed this helper in the previous spec
def ensure_contents(
    path: StrPathLike | ContainerPath,
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

    Ensure that path exists, and contains source, and has the correct permissions,
    and has the correct file ownership.
    Return True if any changes were made, including chown or chmod, otherwise
    return False.
    """

# pebble doesn't distinguish between block and char devices, so we can't include pathlib
# is_block_device and is_char_device in the protocol, but we could provide this helper
# we won't provide it in v1 since charms probably won't use it
# def is_device(path: StrPathLike | ContainerPath) -> bool:
#     if isinstance(path, ContainerPath):
#         try:
#             [info] = path._container.list_files(path.as_posix(), itself=True)
#         except pebble.Error as e:
#             raise ...
#         return info.type is pebble.FileType.BLOCK_DEVICE
#     path = Path(path)
#     return path.is_block_device() or path.is_char_device()
```

#### Example usage

##### discourse-k8s-operator

```py

############
# original #
############

SETUP_COMPLETED_FLAG_FILE = "/run/discourse-k8s-operator/setup_completed"

class DiscourseCharm(CharmBase):
    def __init__(self, *args):
        ...

    def _is_setup_completed(self) -> bool:
        """Check if the _set_up_discourse process has finished.

        Returns:
            True if the _set_up_discourse process has finished.
        """
        container = self.unit.get_container(CONTAINER_NAME)
        return container.can_connect() and container.exists(SETUP_COMPLETED_FLAG_FILE)

    def _set_setup_completed(self) -> None:
        """Mark the _set_up_discourse process as completed."""
        container = self.unit.get_container(CONTAINER_NAME)
        container.push(SETUP_COMPLETED_FLAG_FILE, "", make_dirs=True)

############
# refactor #
############

SETUP_COMPLETED_FLAG_FILE = "/run/discourse-k8s-operator/setup_completed"

class DiscourseCharm(CharmBase):
    def __init__(self, *args):
        ...
        self._flag_file = ContainerPath(
            SETUP_COMPLETED_FLAG_FILE,
            container=self.unit.get_container(CONTAINER_NAME),
        )
        # or someday ...
        container = self.unit.get_container(CONTAINER_NAME)
        self._flag_file = container.path(SETUP_COMPLETED_FLAG_FILE)

    def _is_setup_completed(self) -> bool:
        """Check if the _set_up_discourse process has finished.

        Returns:
            True if the _set_up_discourse process has finished.
        """
        try:
            return self._flag_file.exists(follow_symlinks=False)
        except fileops.ConnectionError:  # a re-exported pebble.ConnectionError
            return False

    def _set_setup_completed(self) -> None:
        """Mark the _set_up_discourse process as completed."""
        self._flag_file.parent.mkdir(parents=True, exist_ok=True)
        self._flag_file.write_bytes(b"")
```

##### kubernetes-dashboard-operator

```py
############
# original #
############

class KubernetesDashboardCharm(CharmBase):
    def __init__(self, *args):
        ...

    def _configure_tls_certs(self, self_signed: bool) -> bool:
        """Load certificates for the Dashboard service."""
        # Make the directory we'll use for certs if it doesn't exist
        container = self.unit.get_container("dashboard")
        container.make_dir("/certs", make_parents=True)
        refresh = self_signed != self._stored.self_signed_cert
        # If there is already a 'tls.crt', then check its validity/suitability.
        if (
            self_signed
            and not refresh
            and "tls.crt" in [x.name for x in container.list_files("/certs")]
            # NOTE: could be simplified -- container.exists("/certs/tls.cert")
        ):
            # Pull the tls.crt file from the workload container
            cert_bytes = container.pull("/certs/tls.crt")
            # NOTE: could be simplified  -- container.pull(..., encoding=None).read()
            # Create an x509 Certificate object with the contents of the file
            if self._validate_certificate(bytes(cert_bytes.read(), encoding="utf-8")):
                return True

        certificate = ...

        container.push("/certs/tls.crt", certificate.cert, make_dirs=True)
        container.push("/certs/tls.key", certificate.key, make_dirs=True)
        return True

############
# refactor #
############

class KubernetesDashboardCharm(CharmBase):
    def __init__(self, *args):
        ...
        self.certs_dir = ContainerPath(
            "/certs", container=self.unit.get_container("dashboard")
        )

    def _configure_tls_certs(self, self_signed: bool) -> bool:
        """Load certificates for the Dashboard service."""
        # Make the directory we'll use for certs if it doesn't exist
        self.certs_dir.mkdir(exist_ok=True)
        refresh = self_signed != self._stored.self_signed_cert
        cert_file = self.certs_dir / 'tls.cert'
        # If there is already a 'tls.crt', then check its validity/suitability.
        if (
            self_signed
            and not refresh
            and cert_file.exists(follow_symlinks=False)
        ):
            # Pull the tls.crt file from the workload container
            # Create an x509 Certificate object with the contents of the file
            if self._validate_certificate(cert_file.read_bytes()):
                return True

        certificate = ...

        cert_file.write_bytes(certificate.cert)
        (self.certs_dir / 'tls.key').write_bytes(certificate.key)
        return True
```

##### openstack-exporter-operator

This is a machine charm, which already uses `pathlib.Path`. In this example I'm imagining a Kubernetes charm that "just works" if we implement the config file writing - of course there are no doubt a lot more changes required.

```py
#######################################
# original -- this is a machine charm #
#######################################

from pathlib import Path
from service import SNAP_NAME, ...

OS_CLIENT_CONFIG = Path(f"/var/snap/{SNAP_NAME}/common/clouds.yaml")
OS_CLIENT_CONFIG_CACERT = Path(f"/var/snap/{SNAP_NAME}/common/cacert.pem")

class OpenstackExporterOperatorCharm(ops.CharmBase):
    ...

    def _write_cloud_config(self, data: dict[str, str]) -> None:
        OS_CLIENT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        OS_CLIENT_CONFIG_CACERT.write_text(self.config["ssl_ca"])

        auth_url = ...
        contents = {
            "clouds": {
                CLOUD_NAME: {
                    ...,
                    "cacert": str(OS_CLIENT_CONFIG_CACERT),
                }
            }
        }

        OS_CLIENT_CONFIG.write_text(yaml.dump(contents))

######################################
# "refactor" -- adding a k8s version #
######################################

import fileops
import pathlib
from service import SNAP_NAME, ...

_OS_CLIENT_CONFIG = f"/var/snap/{SNAP_NAME}/common/clouds.yaml"
_OS_CLIENT_CONFIG_CACERT = f"/var/snap/{SNAP_NAME}/common/cacert.pem"

class OpenstackExporterOperatorCharmBase(ops.CharmBase):
    os_client_config: fileops.Protocol  # machine/k8s must provide
    os_client_config_cacert: fileops.Protocol  # machine/k8s must provide

    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)
        ...

    def _write_cloud_config(self, data: dict[str, str]) -> None:
        self.os_client_config.parent.mkdir(parents=True, exist_ok=True)
        self.os_client_config_cacert.write_text(self.config["ssl_ca"])

        auth_url = ...
        contents = {
            "clouds": {
                CLOUD_NAME: {
                    ...,
                    "cacert": str(self.os_client_config_cacert),
                    # or whatever we decide on for getting the path string
                }
            }
        }

        self.os_client_config.write_text(yaml.dump(contents))

class OpenstackExporterOperatorCharmMachine(OpenstackExporterOperatorCharmBase):
    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)
        self.os_client_config = pathlib.Path(_OS_CLIENT_CONFIG)
        self.os_client_config_cacert = pathlib.Path(_OS_CLIENT_CONFIG_CACERT)
        # we don't need to use fileops.LocalPath because we're not using chown/chmod
        # but we could if we wanted to


class OpenstackExporterOperatorCharmK8s(OpenstackExporterOperatorCharmBase):
    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)
        container = self.unit.get_container(...)
        self.os_client_config = fileops.ContainerPath(
            _OS_CLIENT_CONFIG, container=container
        )
        self.os_client_config_cacert = fileops.ContainerPath(
            _OS_CLIENT_CONFIG_CACERT, container=container
        )
```

## Discussion

### LocalPath + Protocol vs helper functions

**Decision**: We'll go with LocalPath.

We only need `LocalPath` to extend the signatures of the file creation methods to handle chown and chmod, because Pebble can only set ownership and permissions at file creation time.

This isn't the only way to handle this - we could instead have top-level helper functions, `fileops.write_bytes`, `fileops.write_text`, and `fileops.mkdir`, which would accept `_StrPathLike | ContainerPath`. This approach would also eliminate the need for the `Protocol` entirely - users can just write `pathlib.Path | ContainerPath`.

I think the main benefit of the `LocalPath` approach is that if you write `my_path.write_text(...`, then if you later need to set permissions or ownership then you just add some arguments to this call. But since you have to modify the call site, I'm not sure I see the benefit over changing the call site to `fileops.write_text(my_path, ...`. Another potential benefit of `LocalPath` is as a place to provide backports of `pathlib.Path` methods from higher Python versions, however I don't see this as a compelling benefit, and we'd want to keep backporting to a minimum anyway.

The benefit of the helper functions approach is that we wouldn't need the Protocol or LocalPath. Instead users would use pathlib.Path | fileops.ContainerPath in their type annotations. The downside of this approach is that `fileops.write_text(my_path, user=...` will look less familiar to users than `my_path.write_text(user=...`.

### How to allow conversion to a local path string

We need a way to get a path string out of a `ContainerPath`, but we'd like to avoid accidentally operating on local files when working with a `ContainerPath`. We'd also like to be able to get the path string the same way for a `ContainerPath` and for a `pathlib.Path`.

**Decision**: We'll go with `ContainerPath.__str__` because it's already expected behaviour for `pathlib`, we'll always have to return some string, and it's very difficult to return one that will complain about being treated like a path string, so we're likely to cause errors if we don't return the path string.

#### `ContainerPath.__str__`

Is it safe enough for `ContainerPath.__str__` to return just the path string?

The biggest point against this imo is the pattern of accepting `str | Path` and unifying the types by calling `str`. While I suspect this is less common than unifying the types by calling `Path`, it seems unfortunate that we go to all the effort of making sure we're not `os.PathLike` to avoid accidentally operating on local files, only for a thoughtless `str` call to result in silently doing exactly that.

There will always be the `object.__str__` method lurking in the inheritance tree, so we have to provide some implementation. Here are some options for what `ContainerPath('/foo', container=...)` could return, where the container name is `container-name`.

* `'/foo'`
  * pros: convenient way to get path string
  * cons: could inadvertently operate on local files without meaning to
* `'/foo on container-name'`
  * pros: looks nice, displays container information
  * cons: could inadvertently operate on local files without meaning to (a file name of `/foo on container-name` is perfectly valid)
* `'container-name:/foo'`
  * pros: looks nice, displays container information
  * cons: could inadvertently operate on local files without meaning to (a directory name of `container-name:` is perfectly valid)
* `'file://container-name/foo'`
  * pros: looks ok too
  * cons: not really an accurate file path, could inadvertently operate on local files without meaning to (a directory name of `file:` is perfectly valid, and multiple consecutive slashes are just equivalent to a single slash for file separation - both `pathlib.Path` and `os.path` collapse multiple slashes)
* `'/charm/containers/container-name/pebble.socket/foo'`
  * pros: can't accidentally operate on local files easily, because `/charm/containers/container-name/pebble.socket` will exist in the charm container, and will be a socket file
  * cons: ugly, exposes low level implementation details, not really an accurate file path

#### `ContainerPath.as_posix`

What should the  `as_posix` method do?

* It could return the same thing as `__str__`, whatever that is.
* It could not be provided at all, since while `pathlib.Path.as_posix` gives us the posix representation of the object, `ContainerPath.as_posix` can only give us the posix representation of *part of the object*, which makes the `as_` name misleading.
*  `__str__` could try to avoid providing a valid local path to avoid accidentally operating on local files, but perhaps  `as_posix` is explicit enough to return just the path bit. For example:
  *  `__str__`  -> `'/charm/containers/container-name/pebble.socket/foo'`
  * `as_posix` -> `'/foo'`.

#### `fileops.to_{posix,path}`

How about an explicit module level function like `to_posix` or `to_path`?

If neither `__str__` nor `as_posix` will return the string representation of the underlying filesystem path, we still need some way to get this out of a `ContainerPath` object, ideally without the caller needing to know whether the object is a `ContainerPath` or a `LocalPath` or a `pathlib.Path`.

One way to do this would be with a module level helper function that accepts all those types, returning:

* The posix string version of the path, if we go with a `to_posix` function.
* A `pathlib.Path`, if we go with a `to_path` function.

## Further Information

The `ops.pebble` module defines the following exceptions, but we only need to worry about one:

* The base class `pebble.Error` is not raised directly.
* `pebble.ChangeError` is raised by code interacting with services, and doesn't affect this library.
* `pebble.ExecError` is raised by `pebble.Client.exec` and doesn't affect this library.
* `pebble.ProtocolError` will only be raised if something is very broken in the workload's Pebble, and shouldn't be caught by charms - they should just allow the exception to be raised and go to error state.
* `pebble.TimeoutError` is only raised by operations that can time out, like `pebble.Client.exec` and `pebble.Client.wait_changes` so it doesn't affect this library.
* `pebble.APIError` and `pebble.PathError` can be raised by various file operations and will be converted into the appropriate builtin file related errors by this library.
* `pebble.ConnectionError` can potentially be raised by file operations code, and will be re-exported by this library.
