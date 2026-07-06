# OP010 — Harness implementation of Pebble filesystem API

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-09-28 |

## Problem statement

The filesystem APIs in ops.testing._TestingPebbleClient are not implemented.  This causes errors when charm hooks are executed which interact with these APIs unless mocks are applied.

Original issue: [https://github.com/canonical/operator/issues/518](https://github.com/canonical/operator/issues/518)

### Use cases considered

In short: this is needed for tests where tests or charm code exercise the 5 filesystem API functions of the pebble client:

* push (push file to container)
* pull (pull file from container)
* list_files (list files within a directory on the container)
* make_dir (create a directory, optionally recursively, on the container.
* remove_path (remove a file or directory from the container)

Beyond this, a couple other cases we should consider:

* How can we pre-populate the container's filesystem with expected files and directories?
* How can we track calls to these APIs?
* How can we handle code which would create/modify files on the container's filesystem as side effects?

## Currently preferred solution

### Filesystem backend

The current preferred solution is to mock everything in memory.

Compared to other possible solutions, this may require somewhat more code.  Additionally, memory consumption would need to be considered.  However, this solution would likely have faster execution time than other solutions, and compared to the filesystem-based alternative described later in this document, would avoid any unintended consequences of placing test-generated files in the local filesystem.

One concern with this approach is that large files could consume a lot of memory.  This could be mitigated with more code, such as via a hybrid memory/tempfile solution.  However, this does mean more maintenance burden and more code paths to keep in mind during testing.  It may not be worth that complexity.

This solution would likely allow tests using Pebble filesystem APIs to "just work" in many cases, with users being able to supply their own data files directly if necessary, but in a performant way which doesn't expose the guts of its implementation to the user.

Addressing the 3 test cases listed above which go beyond simple API support:

* Pre-populating the filesystem wouldn't inherently require anything extra.  Tests can simply pull Harness.model.unit.get_container(container_name), and use the container's API to push files and make directories, in the same way the charm itself would.  This could be done prior to Harness.start() if necessary.
* Counting and/or introspecting calls, if necessary, can be done via wrapping the APIs via unittest.mock.patch.object, using its wraps keyword parameter to maintain the normal behavior if desired.
* Handling code which causes filesystem side effects is probably not a common case; it also is probably best handled via mocks on a case-by-case basis rather than trying to bake it into the framework.

### API behavior

Beyond having a mock of the backend itself, we also need to consider the interface provided by ops.testing._TestingPebbleClient.  Its 5 methods should operate as close as reasonably possible to how the live ops.pebble.Client class works.

Based off of examining a Juju 2.9.12-based deployment, this is how I would propose we implement the APIs for ops.testing._TestingPebbleClient:

#### pull

Parameters:

* path (str)
* encoding (str) = 'utf-8'

Return value:

* If path specifies a file which exists in the mocked filesystem:
  * If encoding is None: returns file-like object for pulling data in bytes format.
  * If encoding is non-None: returns file-like object for pulling data in str format, or if data cannot be decoded, raises a UnicodeDecodeError.
* If path specifies a directory or symlink: raise a PathError, args[0] = 'generic-file-error'
* If path doesn't exist: raise a PathError, args[0] = 'not-found'

Notable differences versus ops.pebble.Client: None (beyond obviously using a fake filesystem backend)

#### push

Parameters:

* path (str)
* source (str, bytes, or file-like object serving data as str or bytes)
* encoding (str) = 'utf-8'
* make_dirs (bool) = False
* permissions (int) = None
* user_id (int) = None
* user (str) = None
* group_id (int) = None
* group (str) = None

Return value: None

Side effects:

* If destination file does not exist and its parent directory does: create the file
* If destination file does not exist and its parent directory does not: creates the needed parent directories if make_dirs is True; otherwise raises a PathError, args[0] = 'not-found'
* If destination file path is underneath a file rather than a directory: raises a PathError, args[0] = 'generic-file-error'
* Encoding isn't used by the backend; it's merely used by Operator Framework for encoding input data in str format into bytes format.
* Permission and ownership parameters are essentially stored as-is for simplicity, with the caveat that permissions must be an integer between 0 and octal 777.  (If not, this function will raise a PathError with args[0] = 'generic-file-error'.)
* If make_dirs is True, created parent directories will default to root:root ownership; only the target directory will receive the specified permissions and ownership.  Parent directories do, however, receive the specified permissions.

Notable differences versus ops.pebble.Client:

* In ops.pebble.Client, if both string and integer forms of a ownership parameter were provided (e.g. user and user_id), the backend would resolve the string parameters to their ID equivalents and raise an error if there was a mismatch.  However, to avoid the need to track mappings between string and integer IDs for users and groups, I propose we skip this verification and simply store the provided parameters.

#### list_files

Parameters:

* path (str)
* pattern (str) = None
* itself (bool) = False

Return value:

* If the remote path exists and is a directory,
  * If itself is False, returns a list of FileInfo objects within that directory.
  * If itself is True, returns a single-item list containing a FileInfo object for the directory itself.
* If the remote path exists and is a file, returns a single-item list containing a FileInfo object for that file.
* ~~If the remote path exists and is a symlink, the symlink is resolved and the return value is based upon the symlink's fully-resolved target.~~  **Note:** At present, there is no way to create symlinks in the mock filesystem via this proposal.
* If a pattern is specified, it is applied as a filter against the "name" fields of the returned FileInfo objects, and only the matching objects will be returned.  The filter is not applied to the path field, thus patterns such as '/usr/bin/vim*' will result in all items being filtered out.  The filter is a glob filter, i.e. '*' matches 0 or more characters and '?' matches exactly 1 character.  Regular expression patterns are not supported.

Notable differences versus ops.pebble.Client: Uses Python's fnmatch library's glob logic, which slightly differs from the golang path.Match used by Pebble, but in ways which are unlikely to raise issues.

#### make_dir

Parameters:

* path (str)
* make_parents (bool) = False
* permissions (int) = None
* user_id (int) = None
* user (str) = None
* group_id (int) = None
* group (str) = None

Return value: None

Side effects:

* If path does not exist and parent path is a directory: creates the directory.
* If path does not exist and parent path is a file: raises a PathError, args[0] = 'generic-file-error'.
* If path does not exist and nor does its parent, and make_parents is False: raises os.pebble.PathError, args[0] = 'not-found'
* If path does not exist and nor does its parent, and make_parents is True: equivalent to running make_dir for each of the subdirectories below the nearest existing ancestor.  (Likewise, if that ancestor is actually a file, it will error.)
* Permission and ownership parameters are essentially stored as-is for simplicity, with the caveat that permissions must be an integer between 0 and octal 777.  (If not, this function will raise a PathError with args[0] = 'generic-file-error'.)
* If make_parents is True, created parent directories will default to 0755 permissions and root:root ownership; only the target directory will receive the specified permissions and ownership.

Notable differences versus ops.pebble.Client: As with the push method, the real pebble backend has more sophisticated logic regarding the ownership parameters.  However, for simplicity we will simply store the provided values as-is.

#### remove_path

Parameters:

* path (str)
* recursive (bool) = False

Return value: None

Side effects:

* If path exists and is a file: removes it.
* If path exists, is a non-empty directory and recursive is False: raises an a PathError with args[0] = 'generic-file-error'.
* If path exists, is a non-empty directory and recursive is True: removes the remote files recursively.
* If path doesn't exist and recursive=False, raises a PathError with args[0] = 'not-found'.
* If path doesn't exist and recursive=True, does nothing.

Notable differences versus ops.pebble.Client: None (beyond obviously using a fake filesystem backend)

#### Other notes

The proposed implementation relies on using ops.model.Container's methods for pre-populating the mock filesystem.  As there is presently no way to create symlinks in this way, there is presently no way to pre-populate such in the mock filesystem.

#### References

* [Pebble file I/O commands and API documentation](https://docs.google.com/document/d/1NPPZZB_qCwtTru-YsKkRSAb6mXJzBiE0fG3GTZnx4fM/edit?usp=sharing)

## Required API changes

This proposal would not require any API changes nor additional public functions; it purely describes how ops.testing should handle the already-stubbed-out Pebble filesystem APIs and is intended to guide implementation of such.

## Other solutions considered

### Filesystem backend

#### Do nothing

At its core, this issue is about mocking out I/O with a sidecar container via the pebble library.  Mocks could of course be used for this, and in some cases may be the most logical solution, especially for particularly unique test cases.

However, this means that any usage of the filesystem API via pebble is likely to result in errors when unit tests are written unless explicitly mocked out.  This may be seen as cumbersome.

#### Auto-mock the APIs

We could automatically use mock objects to provide default no-op behavior for these operations and allow for call checking.  This would be less cumbersome than requiring end users to mock up to 5 different APIs themselves, but would avoid providing an opinionated implementation of those APIs while under test.

#### Mock via a temporary directory

One idea which was also discussed on [issue 518](https://github.com/canonical/operator/issues/518) was to use a temporary directory to mock the remote system's filesystem.

This is very logical, and intuitively supports all 5 APIs at a basic level.  However, permissions and ownership should still be stored separately of the actual data as, if these were applied directly to the files in the temporary directory, it could prevent the tests themselves from accessing the files.  This methodology may also encourage end users to access this temporary directory directly, which may not be desirable.

If this route were taken, permissions/ownership metadata would need to be stored either outside the filesystem, or in separate metadata files rather than directly as metadata on the actual files themselves.

#### Mock via a hybrid memory/tempfile method

This is based off of what the bottle.py web microframework does for handling request bodies.  Specifically, code can be seen [here](https://github.com/bottlepy/bottle/blob/d1413a81ead7a6f130a06e21a17ca98f4ea30df6/bottle.py#L1343).  It has a cut-off constant which, if a body is under that length it gets handled in memory, while if it is above that constant it is handled via a temporary file.

This does allow for things to "just work" with less chance of breakage.  However, it adds the burden of having to test with files below and above the cutoff threshold in size and ensuring that both methodologies work as expected, and requires essentially a parallel implementation of behavior for both cases.  It's questionable if the benefits are worth the costs.

### API behavior

At present, other solutions have not been considered; the behavior of Pebble in a live deployment has been considered as the most appropriate model for behavior of the mocked APIs.
