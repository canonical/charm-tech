# OP036 — Use Real File System Backend in ops.testing

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Process |
| Created | 2023-06-14 |

## Rationale

The ops library's [testing](https://ops.readthedocs.io/en/latest/#module-ops.testing) module currently uses an in-memory virtual filesystem to back the filesystem operations conducted through the `_TestingPebbleClient`. This virtual testing filesystem is concealed by the testing harness and hence cannot be directly accessed during test cases.

Several charm unit tests require manipulating and inspecting this virtual filesystem to test filesystem-associated functions within the charms. This need has given rise to workarounds such as employing `Harness.model.unit.get_container` to use the container API for controlling the virtual filesystem.

However, this workaround has shortcomings such as the requirement of setting the `can_connect` attribute of the testing container, which may introduce unforeseen effects in the test. Therefore, we aim to offer a new, user-friendly API that will expose the filesystem backend of the testing containers.

## Specification

We propose to use the real filesystem on a developer's machine as the backend for container filesystems in the ops testing harness. The filesystem will be managed by Python's `tempfile` module to simplify creation and cleanup.

Furthermore, a new API, `Harness.get_filesystem_root(container: str | ops.model.Container) -> pathlib.Path`, will be added to the testing Harness to expose the testing container filesystem to the user. The user can then use the path returned by the testing Harness to conduct various operations in the container filesystem, like this:

```py
container_root: pathlib.Path = harness.get_filesystem_root("flask")
flask_dir = container_root / "srv" / "flask"
flask_dir.mkdir(exist_ok=True, parents=True)

# Run some tests

assert (flask_dir / "gunicorn.conf.py").read_text() == "..."
```

## Design Details

The filesystem backend in the ops.testing module must provide two functionalities: container root drive and storage mount.

### Root Drive Design

The root drive is currently provided by the `_TestingFilesystem` class, with one instance included in each `_TestingPebbleClient`. We propose to replace `_TestingFilesystem` inside the `_TestingPebbleClient` with a simple `tempfile.TemporaryDirectory` instance.

In the filesystem-related methods of `_TestingPebbleClient`, such as `pull`, `push`, `list_files`, we will employ Python filesystem APIs in the temporary directory instead of calling corresponding methods from `_TestingFilesystem`. This change will lead to the removal of the `_TestingFilesystem` class and its companion classes, simplifying the implementation of the testing module.

All temporary directories in the testing pebble client will be wiped clean inside the `_cleanup` method of `_TestingModelBackend` to ensure we have a clean state at the start of each test case.

### Storage Mount Design

The current testing modules use a temporary directory to simulate a storage device, with the `_TestingStorageMount` instance inside each `_TestingFilesystem` handling file path translation and redirecting IO to the temporary directory.

In the new design, we propose to use the symbolic link feature of the real filesystem to simulate storage mounts. The temporary directory for each storage will remain the same, but during storage attach and detach, the testing backend will create and remove symbolic links in the container root drive temporary directory, pointing to the temporary directory representing the storage device. These symbolic links are located inside the root drive's temporary directory, so cleanup will be automatic during the cleanup of the root drive temporary directory.

## Limitations and Mitigation

This approach's primary limitation is that under normal conditions, a standard user cannot create a file not owned by them. By default, the Container API creates files with Pebble's uid and gid (which is root under Juju), which we plan to alter in the testing harness to have files created by the current user if user and group options are left at their defaults.

The current in-memory filesystem does not support permission handling, so this would not be any worse than what we have today.

For testing charms that require creating files with specific owners and permissions, there are two potential solutions:

1. Running the charm tests as root. Running tests as root is not usually a good idea, though it may be okay in a containerized/CI context.
2. Refactoring the charm to make user or group names easily patchable, for example:

```py
class FlaskCharm(CharmBase):
    _FLASK_USER = "flask"
    ...
```

This way, we can patch user constants in the unit test, with the test setup setting it to the current username:

```py
class TestCharm(unittest.TestCase):
    def setUp(self) -> None:
        self.user_patch = unittest.mock.patch.object(
            FlaskCharm, "_FLASK_USER", getpass.getuser()
        )
        self.user_patch.start()
        ...

    def tearDown(self) -> None:
        ...
        self.user_patch.stop()
```

Additionally, to ensure we're not painting ourselves into a corner for future extension, there are at least two ways we could improve on permission handling in future:

* Layer permission-handling on top of the real filesystem calls. For example, record what user/group arguments were passed to create_file, and return them in list_files.
* Add support for an optional `ops[memfs]` dependency, which pulled in a more full-fledged in-memory filesystem implementation if the charm tests needed it. We wouldn't want all charms to have to pay the cost of a large 3rd party dependency, and an optional dependency would avoid that.
