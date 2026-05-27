# OP044 — Pebble Unified Mkdir Function with MkdirOptions Support

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2024-05-23 14:30 GMT+8 |

## Abstract

Create a unified `osutil.Mkdir` function with options such as if need to create parent directory, if need to chown, if need to chmod explicitly to make sure the permission isn't affected by [`umask`](https://man7.org/linux/man-pages/man2/umask.2.html), etc.

## Rationale

Pebble has a command `mkdir` that creates directories. However, the implementation is scattered in multiple functions, such as `osutil.MkdirAllChown`, `osutil.MkdirChown`, etc., which in turn calls internal functions like `mkdirAllChown`, `mkdirChown`, etc. See [`internals/osutil/mkdirallchown.go`](https://github.com/canonical/pebble/blob/master/internals/osutil/mkdirallchown.go) for more detail.

Now there is a need to add support for a new flag so that when creating directories, the permission won't be affected by [`umask`](https://man7.org/linux/man-pages/man2/umask.2.html) settings. See the [issue here](https://github.com/canonical/pebble/issues/372). There was already a similar implementation for writing files ([issue](https://github.com/canonical/pebble/issues/80), [PR](https://github.com/canonical/pebble/pull/111)), but doing similar things to mkdir means adding even more chaos into the existing functions, public or private, see an initial implementation [here](https://github.com/canonical/pebble/pull/405).

So, as suggested by [Ben Hoyt](mailto:ben.hoyt@canonical.com), since the function signatures, as well as the number of functions in the implementation, are getting out of control, there is a need to design a better function to unify all these mkdir functions with options defined in a struct.

This will also close [issue 372](https://github.com/canonical/pebble/issues/372).

## Specification

### Files

Package: `osutil`
File: `mkdir.go`

This will replace the current `mkdirallchown.go` file, and the test file `mkdirallchown_test.go` will be renamed to `mkdir_test.go` accordingly.

### API Design

```
func Mkdir(path string, perm os.FileMode, options *MkdirOptions) error { ... }
```

Two required arguments:

- path: string
- perm: containing other options, type `MkdirOptions`, as explained below.

This function will replace the current `MkdirChown` and `MkdirAllChown`, usages in `internals/daemon/api_files.go` will be updated too.

### Options

```
type MkdirOptions struct {
    // If false (default), a missing parent raises an error.
    // If true, any missing parents of this path are created as needed.
    MakeParents bool

    // If false (default), an error is raised if the target directory already exists. In case MakeParents is true but ExistOK is false, an error won't be raised if the parent directory already exists but the target directory doesn't.
    // If true, an error won't be raised unless the given path already exists in the file system and isn't a directory (same behaviour as the POSIX mkdir -p command).
    ExistOK bool

    // If false (default), no explicit chmod is performed. In this case, the permission of the created directories will be affected by umask settings.
    // If true, perform an explicit chmod on any directories created.
    Chmod bool

    // If false (default), no explicit chmod is performed. In this case, the permission of the created directories will be affected by umask settings.
    // If true, perform an explicit chmod on any directories created.
    Chown bool // NOTE: additional bool is needed because 0 is a valid value for UserID and GroupID (root)

    UserID sys.UserID

    GroupID sys.GroupID
}
```

The above is modelled after [https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir](https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir).

## Further Information

Jira: [https://warthogs.atlassian.net/browse/CHARMTECH-38](https://warthogs.atlassian.net/browse/CHARMTECH-38)
