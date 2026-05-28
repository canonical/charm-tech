# OP015 — Recursive Directory Push/Pull

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2022-02-03 |

## Abstract

Sometimes it is useful to recursively list, push, and pull directories from the workload container - particularly for charm development and debugging. Actions are another example of charm operations that would benefit from recursive push/pull for files.  Charm developers may want to modify multiple files as part of the same hook or action, or may want to verify the presence of automatically generated filesystem structures.  Recursive pull functionality is a natural extension of the existing pebble-oriented file-based interactions (e.g. push, pull, etc.).  We propose adding two additional methods providing recursive versions of existing methods:

* ops.model.Container.pull_path: recursively pull (a tree of) files from the workload container.
* ops.model.Container.push_path: recursively push (a tree of) files on the charm container to the workload container.

## Specification

While we will follow the same API pattern implemented by the existing pebble client (e.g. list, pull, etc.) methods, consolidating this new functionality into the same methods is suboptimal because they have different return types/semantics (directory vs. file), different args, etc. and will share little implementation.  The Container API will have new push_recursive and pull_recursive methods.  Push will look like this:

`def push_path(source_path: Union[str, Iterable], dest_dir: str, user=None, user_id=None, group=None, group_id=None)`

where files are copied from the directory tree rooted at *source_path* into *dest_dir*.  Logging errors is preferred over raising exceptions in order to avoid placing the charm/unit in an error state for what may have been a human operator error from e.g. running an action.  Permissions will be preserved.  *user, user_id, group,* and *group_id* behave identically as they do on Client.push.

The semantics for pushing and path handling are as follows:

* push_path("/foo/*", "/bar") "/foo/baz" becomes "/bar/baz" (foo must be a dir)
* push_path("/foo", "/bar"): "/foo" becomes "/bar/foo" (foo can be dir or file)
* push_path("/foo/baz", "/bar"): "/foo/baz" becomes "/bar/baz" (baz can be dir or file)
* push_path([a, b, c, ...], "/bar"): is equivalent to the semantics of the previous examples performed independently for each path a, b, c, etc.

The "/*" can only be used as the final element of a path and means "the contents of" - for indicating that the contents of a directory should be moved/copied rather than the directory itself.  a "/For push_path, the destination must be an absolute path.  For pull_path, the source must be an absolute path.

And recursive pull will look like this:

`def pull_path(source_path: Union[str, Iterable], dest_dir: str)`

where *source_path* is the remote/workload-side path to pull from and *dest_dir* is the local/charm-side path in which to deposit files.  pull_path uses the same path semantics, globbing, etc. as are used for push_path.

For now, any *list_recursive* functionality will be maintained privately and later exposed if important use cases arise.  For now, internal recursive listing logic for pull_recursive and push_recursive will be shared and kept consistent with each other as much as possible.

## Further Information

Originally a separate specification was written to implement this functionality on the pebble-side (see [https://docs.google.com/document/d/1DV4yhsFIbYNhaHnxl5y_NNSUBZU4VrDIPFou3J5fwsA/edit?usp=sharing](https://docs.google.com/document/d/1DV4yhsFIbYNhaHnxl5y_NNSUBZU4VrDIPFou3J5fwsA/edit?usp=sharing), [https://github.com/canonical/pebble/pull/68](https://github.com/canonical/pebble/pull/68)  ).  The advantage to that approach is it reduces the number of network-operations necessary to transfer files recursively (i.e. a single network operation instead of one per directory).  However, implementing the functionality directly in the operator framework is simpler and quicker.  And taking advantage of the pebble APIs existing ability to retrieve multiple files via a single request mitigates most of the request ballooning.  If use cases arise where performance of the framework-approach is unacceptable, the recursion can be migrated into pebble without affecting the framework API as long as we are careful to preserve pattern/globbing semantics.

One consideration regarding potential consolidation of list_recursive and the existing list_files: this would require settling on globbing/pattern matching syntax and semantics since the existing list_files method already supports it.

### Patterns

Because there are subtleties about keeping pattern/globbing semantics consistent in our APIs regardless of where things are implemented (pebble vs. operator framework), we are not committing to any recursive pattern matching/globbing support at this time.  Pattern/globbing functionality will be a likely future non-breaking addition to the list_recursive, pull_recursive, and push_recursive methods.  Pattern matching should use syntax/semantics consistent with those provided in the non-recursive list_files method except it can include multiple path elements - not just a file/base name.  The matching could e.g. work from right to left:

`/foo/bar/baz.txt`
`/foo/boo.txt`
`/baz.txt`

`'*.txt' matches all files.  '*/*.txt' matches baz and boo.  'foo/*' matches boo.`

Pebble only matches against the file basename itself - not the directories the file is in.  Pebble uses the Go standard library path.Match - which has slightly different syntax than python fnmatch/glob libs (e.g. '^' in Go vs '!' in python).  One option would be to stop using pebble's pattern param in the file listing API - and just use our own globbing on the operator framework side - allowing all globbing to be implemented consistently in a single location.  Not sure if that idea is any good, but it is an option.  However, the reverse is not possible - we will never be able to implement all globbing on the pebble side because a recursive push will always require building up the file list on the operator framework side.

### Discussions

**Notes from 1 April (team review):**

* Ignore dotfiles by default with a kwarg to enable copying them.
* Kill FileInfo usage now that users don't usually interact with the _many methods directly.
* client API pull - make sure exception has info for all error content from pebble, and an exception is raised even if only 1 out of N files error
* Probably kill max_depth

pebble.Client:

* push_many(files: Iterable[PushFile], dest_path: str, prefix='')
* pull_many(files: Iterable[str], dest_path: str, prefix='')
* make list_recursive just be private and not a client func.

model.Container:

* def push_recursive(source_path: str, dest_path: str, max_files=10000, keep_permissions=True, user=None, user_id=None, group=None, group_id=None, follow_symlinks: bool=False, include_dotfiles=False):
  * Eats list_recursive_local behavior.
  * "prefix" is always the local_dir
* def pull_recursive(source_path: str, dest_path: str,
                        follow_symlinks: bool=False,
                        max_files: int=10000,

          include_dotfiles=False)
* def list_recursive: private or not? - maybe private for now.

**Notes from 10 May (team review):**

* Let's limit scope to what we know for sure is super useful/needed
  * dump pull/push_many
  * dump args like max_files, include_dotfiles, etc. (for now)
* Rename to push/pull_path
* Support the common case of wanting to push/pull a few files (e.g. a list)
* Allow minimal globbing support to facilitate semantic distinction of copy this thing vs copy this thing's contents.
