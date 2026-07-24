# OP034 — Service context for Pebble exec and health checks

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2023-06-13 |

## Abstract

For Pebble exec and command-based health checks, it's often useful to run these commands in the context of a particular service, reusing environment variables and other context from that service. We propose adding a "service context" option for Pebble exec commands and health checks of type `exec` that will use the context from a given service.

## Specification

Pebble [issue 159](https://github.com/canonical/pebble/issues/159) (on Charm Tech's roadmap for 23.10) briefly mentions adding "context" but doesn't go into details, so below is a more detailed explanation.

### Pebble exec

We would add a "service-context" option to the exec API as follows:

```
type execPayload struct {
    Command        []string          `json:"command"`
    Environment    map[string]string `json:"environment"`
    ...
    ServiceContext string            `json:"service-context"`
}
```

If "service-context" was set to a non-empty string (which would have to be a valid service name), when the one-shot command was executed, Pebble would use the following options from the named service:

* **Environment variables** (keys set on the exec call would override the service's)
* **User and group** (and user_id / group_id)
* **Working directory** (once `working-dir` is added to the service config - [issue 158](https://github.com/canonical/pebble/issues/158))

If the option was set on the exec call as well, the exec call's value would override the service config. Specifically for environment variables, if both "service-context" and "environment" were set, any keys in the environment map would override the service context.

We would need to add a similar parameter to the ops library's `pebble.Client.exec` and `ops.Container.exec` methods, as follows:

```py
def exec(self, command: List[str], *,
         service_context: Optional[str] = None,
         environment: Optional[Dict[str, str]] = None,
         ...
):
```

We would also add a `pebble --context` flag to the CLI, with the same meaning. (Note that the name is the shorter `--context` rather than `--service-context` here, by design.)

As an example, a Pebble plan might have a "webapp" service that connected to a database:

```
services:
  webapp:
    command: python3 webapp.py
    override: replace
    environment:
      PORT: 8080
      DB_HOSTNAME: dbserver
      DB_USERNAME: webapp
    user: app
    group: app
```

Then you might want to use Pebble exec to run a command that backed up the database using the same database hostname and username as the web app, for example:

```py
process = container.exec(['python3', 'backup.py'],
                         service_context='webapp', user='backup')
process.wait_output()
```

This would pull in the `PORT` and `DB_*` environment variables and the "app" group from the service config, but override the user to be "backup".

### Health checks (of type `exec`)

Similarly, for health checks of type exec, we'd add a "service-context" key in the health check layer configuration:

```
checks:
  upchk:
    exec:
      command: <commmand>
      environment:
        <name>: <value>
      ...
      service-context: <service name>
```

This would have the same semantics as the context option for Pebble exec described above.

## Open questions

* For health check configuration, should we allow specifying "service-context: none" (or "service-context: default") to mean "don't inherit any environment variables or other context? Would it be too problematic that the string "none" / "default" is valid service name?

## Notes

* In [PR 234](https://github.com/canonical/pebble/pull/234), we changed exec and command-based health checks to inherit the daemon's environment variables.
* Separately, we're planning to add a top-level environment section with key-value pairs, that forms the base environment for all services. See spec [RK020](https://docs.google.com/document/d/11Q_iv_mKdlouZFtQ1RQh5pRQmqIwv70TI-eKX6_733w/edit#).

## Additional information

* [JU012](https://docs.google.com/document/d/1npbNQMokDUoGX1UT61CvnMq6lIJ6MnU6CwExkymHEcA/edit) - original spec for Pebble one-shot commands
* [JU011](https://docs.google.com/document/d/1d6-h3UAt2VPUSvlkVF30l8iuDW8raRNkHbp5M6NUo1A/edit) - original spec for Pebble health checks (and service auto-restart)

### Notes from 2023-07-11 spec review meeting

Naming brainstorming:

* **service-context (this is our decision - see below for other uses)**
* service-ctx
* as-service
* inherit-service
* from-service
* in-service
* inherit-from-service
* in-service-context

`CLI: pebble exec --context=svc1 echo foo    # short version here`
`exec API: "service-context"                 # long here`
`Go API: ExecOptions{ServiceContext string}  # and here`
`Python API: container.exec(['echo', 'foo'], service_context='svc1')  # and here`
