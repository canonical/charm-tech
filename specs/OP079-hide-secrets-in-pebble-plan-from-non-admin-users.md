# OP079 — Hide secrets in Pebble plan from non-admin users

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | Nov 17, 2025 |

## Abstract

A  common (particularly in the "12 Factor" space) mechanism workloads provide for accepting secrets is to read them from environment variables. A Pebble layer can contain environment variables for services, so an approach when charming such a workload is to insert secrets into the layer when dynamically adding it. However, a non-admin Pebble user should not have access to these secrets via Pebble, but can currently see them when retrieving the plan. We will change Pebble so that retrieving the plan requires admin access.

## Rationale

Secrets are often passed to workloads as environment variables because they provide a simple, standardised way for applications to access sensitive data like API keys or database credentials without hardcoding them into code or configuration files. This practice was popularised by the [12-Factor App methodology](https://12factor.net/config).

When workloads are managed by Pebble, environment variables can be passed to services using the `environment` field (and to health checks in the `environment` field of an `exec` check). For charms, the content of the secrets is typically retrieved from a Juju secret and then templated into the layer containing the service and/or health checks before dynamically adding the layer to Pebble. This limits the exposure of the secret content.

However, a Pebble user with only read access can retrieve the full plan, which includes all environment variable names and values. This means that a Pebble user that only has read access can currently access secret content when it is passed to the workload using environment variables. Within the charm context, this means that non-root users in the workload container can access secrets via `pebble plan`.

The goal of this spec is to limit exposure of sensitive data to non-admin Pebble users; it is not intended to protect against a (for example, compromised) admin user.

## Specification

The `plan` [API](https://github.com/canonical/pebble/blob/cc8a147ac250c24f87b91bdf439e78f49acaa14f/internals/daemon/api.go#L64) will be changed to require admin access. This does remove the ability to retrieve some debugging information for users with only read access, but it's more common for a user with admin access to debug issues with charms or rocks.

For example, when used from the CLI:

```
// As a user with 'admin' access:
$ pebble plan
services:
    srv1:
        override: replace
        command: /bin/sleep 60
        environment:
            FOO: bar
            SECRET_BAR: password
checks:
    chk1:
        override: replace
        threshold: 3
        exec:
            command: /bin/true
            environment:
                HEALTHFOO: bar
                HEALTHSECRET_BAR: password

// As a user with 'read' access:
$ pebble plan
error: access denied (try with sudo)
exit status 1
```

When `plan` is used as an admin user, there is no change from the existing behaviour. An admin is able to use the Pebble filesystem API to `pull` the environment variables from `/proc/{pid}/environ` so masking the values in the plan does not increase the security of the values.

This change is **not** backwards compatible, but we will not increase the major Pebble version from 1 to 2. The precedent here is that [access to the `pull` API was removed for non-admin users](https://github.com/canonical/pebble/pull/406) without increasing the major version. In addition, we believe that users that are fetching the plan are almost certainly connecting as admin users (for example, charms or Juju users). As such, we feel that this is an extremely minor incompatibility and not worth the cost of a new major version.

### Implications across the Pebble-verse

#### Charms / Juju

Juju (Kubernetes sidecar) charms are the primary focus of the change proposed in this spec. Note that in a non-root or sudoers workload container, the user that Pebble runs as still automatically has admin level access, so is not impacted by this change.

There is one known case where a charm workload is using Pebble to retrieve the plan as a non-admin user. The [`mongo-single-kernel-library`](https://github.com/canonical/mongo-single-kernel-library/blob/6/edge/single_kernel_mongo/utils/helpers.py) runs a logrotate process passing in a custom configuration file. That file gets the a URI (containing a username and secret) from Pebble at runtime, via:

`$(pebble plan | yq -r .services.{service_name}.environment.{env_variable})`

This runs as the `mongodb` user. However, the charm could just write the actual value into the file, rather than having logrotate run a shell command to get it at runtime. The environment variable is already accessible via the filesystem (in `proc`) so this does not significantly change the security posture.

#### Rocks

The Pebble layer in `rockcraft.yaml` should not include any sensitive content. When a rock is used (outside of Juju) sensitive content should be injected via Docker, Kubernetes secrets, and other common techniques. This means that it's unlikely that the problem exists with (non-Juju) rocks, as satisfactory solutions already exist.

However, if anyone is adding a layer dynamically to Pebble, which includes sensitive content, then this becomes the same as the Charm / Juju case: we should limit exposure of this content to users that do not have admin access.

#### Proposed use in self-hosted GitHub runner

This is likely an important improvement in this (proposed) Pebble use-case. Inside the runner, arbitrary user workloads will be run - if the workload is able to access the Pebble executable or socket then user accounts should not be able to access any sensitive data in the plan. Since this initiative is only at the investigation stage, it's not possible to provide concrete examples.

#### Project Crystal (as a library)

Project Crystal does not expose the plan via its API, so this change does not impact (eventual) downstream users. Internal use will also not be impacted by this change.

## Further Information

### Proof-of-concept Implementations

* [Proof-of-concept implementation](https://github.com/tonyandrewmeyer/pebble/tree/claude/pebble-plan-command-016Fc2ZVUaTqde7RQZM1oaXC) of masking the variables.
* Implementation of changing the access level.

### User Context & Reports

* [https://github.com/canonical/pebble/security/advisories/GHSA-rvvq-vh46-qxjf](https://github.com/canonical/pebble/security/advisories/GHSA-rvvq-vh46-qxjf)
* [https://github.com/canonical/pebble/issues/656](https://github.com/canonical/pebble/issues/656)

### Alternatives

#### Annotate environment variables

This is alternative backwards-compatible solution; allowing values to be a map that has a "sensitive" field (like Terraform). However, this would require additional work from Pebble users (such as Charm or Rock maintainers) and result in a less clean layer specification.

```
# An example of changing the type of environment variable values to allow annotation
# indicating that the content is sensitive.
services:
   override: replace
   command: /bin/sleep 60
   environment:
     NOT_SECRET: foo
     SECRET_THING:
       value: bar
       sensitive: true
```

#### Mask environment variables for non-admin users

The `plan` API could be changed to mask (replace with "*****", as with sensitive content in identities) the values of all environment variables in both services and health exec checks, if the user's access level is not "admin" (that is, an API user that's explicitly set to admin if using identities, or root or the UID the daemon is running as).

All environment variable values would be masked, not only ones with sensitive content, because Pebble cannot currently determine which variables might have sensitive content (and looking for specific key names is too brittle). This does remove some debugging information for users with only read access, but it's more common for a user with admin access to debug issues with charms or rocks.

For example, when used from the CLI:

```
// As a user with 'admin' access:
$ pebble plan
services:
    srv1:
        override: replace
        command: /bin/sleep 60
        environment:
            FOO: bar
            SECRET_BAR: password
checks:
    chk1:
        override: replace
        threshold: 3
        exec:
            command: /bin/true
            environment:
                HEALTHFOO: bar
                HEALTHSECRET_BAR: password

// As a user with 'read' access:
$ pebble plan
services:
    srv1:
        override: replace
        command: /bin/sleep 60
        environment:
            FOO: '*****'
            SECRET_BAR: '*****'
checks:
    chk1:
        override: replace
        threshold: 3
        exec:
            command: /bin/true
            environment:
                HEALTHFOO: '*****'
                HEALTHSECRET_BAR: '*****'
```

#### Add secret backends

A more complex solution would be to add knowledge of secret backends (such as Juju or Vault) to Pebble, and support for retrieving secrets from the backend and injecting them into the environment (retrieving the plan would only show the secret backend to be used and the identifier for the secret). This could be similar to ephemeral resources in Terraform, Helm secrets, or LoadCredentialEncrypted in systemd. This would also be backwards compatible, and would be a stronger solution that also prevented a user with admin access from seeing secrets via the plan (but not via other methods). However, it would be a significant addition to Pebble, which does not appear to be justified at this time.

Kubernetes allows setting environment variables from secrets in the definition of a container, but that is a broader solution than we want, because the secrets are then available to all processes in the container (much like ones from Pebble are now).

#### Require transferring secrets with files

Another alternative is to avoid using environment variables to provide secrets to the workload entirely, by making use of workload features to load secrets in another manner (such as from a secret server). However, not all workloads have such features, and adding such a feature is typically more work than a charmer is intending to do when charming a service.

#### Wrap setting the environment (Current Workaround)

We currently suggest that users wrap the workload. For example, a generic wrapper might look like this:

```shell
#!/usr/bin/env bash
# Usage: ./secret-wrapper.sh KEY1:SECRET-ID1 KEY2:SECRET-ID2 ... -- command args...

set -euo pipefail

# Collect secrets until we hit "--"
envs=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --)
            shift
            break
            ;;
        *)
            if [[ "$1" == *:* ]]; then
                key="${1%%:*}"
                secret_id="${1#*:}"
                value=$(juju secret-get "$secret_id")
                envs+=("$key=$value")
            else
                echo "Invalid argument format: $1 (expected key:secret-id or --)" >&2
                exit 1
            fi
            ;;
    esac
    shift
done

for kv in "${envs[@]}"; do
    export "$kv"
done

if [[ $# -eq 0 ]]; then
    echo "No command specified to run after secrets" >&2
    exit 1
fi

exec "$@"
```

### Review of non-admin API access

Since we are proposing adjusting the access that a non-admin user has to the API, we have also reviewed the remaining access. We did not find any additional access that should be removed from non-admin users.

* `/v1/system-info`
  * Provides boot ID, HTTP[S] address, and version number.
* `/v1/heath`
  * Indicates whether the overall state is healthy.
* `/v1/changes[/{id}[/wait]]`
  * For each change, provides a list of tasks, an ID, a kind, a summary, the current status, a `ready` Boolean, and timestamps.
  * For each task, provides an ID, a kind, a summary, the current status, progress tracking, timestamps, and task (error) logs.
* `/v1/services[/{name}]`
  * Provides the name, startup value, current state, and a timestamp for entering that state (startup comes from the plan, but is not sensitive).
* `/v1/logs`
  * Pebble must never log anything itself that a non-admin should not be able to read.
  * Workloads are responsible for their own log content safety, and should not be logging anything that other users should not be able to read.
* `/v1/checks`
  * Provides the name, startup value, current status, threshold, and a change ID (startup and threshold come from the plan, but are not sensitive).
* `/v1/notices`
  * Custom access control: users can only read their own notices, not ones for other users, or system-wide notices.
* `/v1/identities`
  * Sensitive information is masked.
* `/v1/pairing`
  * Special `PairingAccess` is required.
* `/v1/metrics`
  * Special `MetricsAccess` is required.
