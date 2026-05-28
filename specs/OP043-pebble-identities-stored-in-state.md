# OP043 — Pebble identities stored in state

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2024-04-29 |

**Note:** this has been implemented in [PR #434](https://github.com/canonical/pebble/pull/434) (and the 4 subsequent PRs).

## Abstract

Pebble and its derivatives require a means of authenticating users of the API. Currently, Pebble authentication works by reading the UID of the connecting process via the SO_PEERCRED socket option, and authorisation is determined as one of three levels of access based on the UID: open (system-info and health APIs only), user (read access to almost everything), or admin (read/write access to everything). However, over TCP or from a container with a different user namespace, we have to establish trust another way.

This spec presents an alternative proposal from the earlier [JU092 Pebble authentication](https://docs.google.com/document/d/1Q_KFMdsMFIAkUQb-CgOenXlWjVG3h1wxI-BV0JvhPh8/edit) spec: instead of specifying authentication configuration via the Pebble plan and layers, **this spec proposes storing authentication configuration in Pebble state, with various APIs and commands to add and update the configuration.**

This will allow additional peer-cred UIDs to be supported now, as well as new authentication types in future.

## Specification

"State" is Pebble's database that is persisted to disk: every time state is modified, the in-memory representation is modified and the changes are saved to disk (the current implementation serialises state to a file in the $PEBBLE directory). At present, Changes, Tasks, and Notices are stored in state.

We propose storing "identities" - Pebble user configuration - in state. This will be a mapping of identity name to configuration fields that describe what authentication types are allowed for that user. Initially we would only support one authentication type, `local`, meaning a local user ID authenticated via the existing peer-cred system. In future, we could add additional authentication types such as `tls` or Basic HTTP (`http`) authentication.

We propose adding new API endpoints to add or update identities as well as to list them. We also propose adding new commands to wrap those APIs, and an option for `pebble run` to seed the Pebble daemon with an initial set of identities.

### API endpoints

The new API for **adding identities** would be a synchronous request as follows (admin only):

```
POST /v1/identities
{
  "action": "add",
  "identities": {
    "ben": {
      "access": "admin",
      "local": {"user-id": 1234}
      # Or, in future:
      # "tls": {"cert": "..."}
      # "http": {"username": "ben", "password": "hunter2"}
    },
    "mary": {
      "access": "read",
      "local": {"user-id": 4321}
    }
  }
}
```

The "local" key is the authentication type (local peer-cred user), and the object nested under it holds the configuration for this type. An identity may have multiple authentication types.

For "local" identities, the user-ids (of the resulting identities) must be unique. As one example, it would be an error to try to add user "ben" with user-id 1234 and "mary" with user-id 1234. Future authentication types might have similar uniqueness constraints.

Valid values for the "access" field are:

* `admin`: all access, read and write
* `read`: read access to everything, also ability to add custom notice for your user
* `untrusted`: limited access for untrusted users (/v1/system-info, /v1/health)

For the "add" action, if any of the named identities already exist, the call would fail with an error (eg: "user 'ben' already exists").

To **update identities** (admin only), callers would use the same endpoint but with action "update". This would replace any existing named identities with the configuration given. When updating, if any named identity did not exist, the call would fail with an error.

To **replace identities** (admin only), callers would use the same endpoint but with action "replace". This would be an idempotent replacement of all the given identities - that is, it would update existing identities and create non-existent ones. This call would also support null to remove identities (see below).

To **remove identities** (admin only), callers would use the same endpoint but with action "remove". This would completely remove access for the given names. If the caller tries to remove any non-existent entities, the remove will fail. For this request, the input would be a map with identity names as keys and null as values, for example:

```
POST /v1/identities
{
  "action": "remove",
  "identities": {
    "ben": null,
    "mary": null
  }
}
```

To **list identities** (read access), the new API would provide only the name, access level, and the non-sensitive *settings* under the authentication type (specifically, no secrets). For example:

```
GET /v1/identities

{
  "type": "sync",
  "result": {
    "ben": {
      "access": "admin",
      "local": {"user-id": 1234}
    },
    "mary": {
       "access": "read",
       "local": {...}
    }
  }
}
```

### Commands

We propose adding new Pebble client commands that correspond to each of the above actions. These commands would add/update/replace/remove identities. The configuration would be specified as a YAML file in each case:

```
# Syntax:
pebble add-identities --from <file.yaml>
pebble update-identities --from <file.yaml> [--replace]
pebble remove-identities --from <file.yaml>

# Example:
pebble add-identities --from=auth.yaml

# For future extension, "reserve" this key=value syntax,
# which would fail if the value was a secret
pebble [add|update|remove]-identities <name> key1=val1 key2=val2

# Example (future extension):
pebble add-identities ben access=admin local-user-id=1234

auth.yaml:
----------
identities:
  ben:
    access: admin
    local: {"user-id": 1234}
  mary:
    access: read
    local: {"user-id": 4321}
----------

# Possible future extension, "offline" mode (updates state db without Pebble daemon).
pebble add-identities <args> --offline
```

#### Showing identities

The `identities` command would list all identities, and `identity` would show details for a single named identity:

```
$ pebble identities
Name  Access  Types
ben   admin   http,local,tls
mary  read    local

# Possible extension (not required for v1):
$ pebble identities --format=yaml
identities:
  ben:
    access: admin
    local:
      user-id: 1234
  mary:
    access: read
    local:
      user-id: 4321

# This would show details (but NOT secrets)
$ pebble identity mary
access: read
local:
  user-id: 4321
```

#### pebble run --identities

The new `--identities` option to the `pebble run` command would allow seeding the Pebble daemon with a file that specifies identities to start up with. It would operate as if `pebble update-identities --replace --from=auth.yaml` as executed before starting up.

```
# Example:
pebble run --identities=auth.yaml

auth.yaml:
----------
identities:
  ben:
    access: admin
    local: {"user-id": 4321}
  mary:
    access: read
    local: {"user-id": 1234}
----------
```

#### pebble identities --help

In addition to the above commands, we would tweak the help output for the new commands:

```
# Make "pebble help" print this for the identities category:

     Notices: warnings, okay, notices, notice, notify
  Identities: identities --help

# Then make "pebble identities --help" refer to all the other identity commands.
```

## Further Information

* [Original JU092 Pebble authentication spec](https://docs.google.com/document/d/1Q_KFMdsMFIAkUQb-CgOenXlWjVG3h1wxI-BV0JvhPh8/edit)
