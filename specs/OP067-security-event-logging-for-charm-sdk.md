# OP067 — Security Event Logging for Charm SDK

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | Jun 10, 2025 |

[Draft implementation for ops in this PR](https://github.com/canonical/operator/pull/1905/files).

## Abstract

As part of the Canonical SSDLC, products are required to log security events, as covered in [SEC0045](https://docs.google.com/document/d/1nInWP9pEEhloKMfgzDsd4Pub4530OxQcKKh716Gvxfk/edit?tab=t.0). This spec outlines the security events that exist within each of the "Charm SDK" products, and how those will be logged. For ops, the spec covers logging security events that occur as a result of using the framework, but it does not include adding an API for charms to log security events of their own.

## Specification

The products that Charm Tech manages, which constitute the "Charm SDK" (excluding Pebble, which has a separate security line item) are:

* [ops](https://pypi.org/project/ops/), including [ops-scenario](https://pypi.org/project/ops-scenario/) and [ops-tracing](https://pypi.org/project/ops-tracing/)
* [Concierge](https://snapcraft.io/concierge)
* [Jubilant](https://pypi.org/project/jubilant/)

### Logging Security Events

#### ops, ops-scenario, ops-tracing

[SEC0045](https://docs.google.com/document/d/1nInWP9pEEhloKMfgzDsd4Pub4530OxQcKKh716Gvxfk/edit?tab=t.0) indicates that security event logs should go to the existing logging destinations, but does specify a structured log format that is required. For ops and ops-tracing, this means the destination is the Juju log, and for ops-scenario, this is the existing Python logger object that will typically end up in pytest output.

A new convenience method will be added to ops.log, `_security_event`.

```py
# In ops/log.py

class _SecurityEventAuthZ(enum.Enum):
    AUTHZ_FAIL = "authz_fail"
    # And so on

def _log_security_event(
    level: Literal['INFO', 'WARN', 'CRITICIAL'],
    event_type: {union of the various enums} | str,
    event: str,
    *,
    description: str,
) -> None:
    """Send a structured security event log to Juju, as defined by SEC0045.

    Args:
        * level: the level of the event (of the OWASP levels)
        * event_type: the type of event (as per the OWASP documentation)
        * event: the name of the event, in the format described by OWASP
          https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html
        * description: a free-form description of the event, meant for human
            consumption. Includes additional details of the event that do not
            fit in the event name.
    """
    # 'datetime' will be set to datetime.datetime.now(datetime.UTC)
    # 'type' will be set to 'security'
    # 'appid' will be set to the unit's name and model UUID (from JUJU_MODEL_UUID)
    ...

# Example usage (this is only an example -- the description is an implementation detail).

import ops.log as _log

_log._log_security_event(
    "WARN",
    _log.SecurityEventAuthZ.AUTHZ_FAIL,
    'secret-get',
    description=f"Hook-tool 'secret-get' failed with an {juju_output!r} error."
        f"Arguments were: {args!r}. Unit {'is' if self.unit.is_leader() else 'is not'} "
        f"leader.",
)
```

#### Concierge

Concierge logs to [stderr](https://github.com/canonical/concierge/blob/a8143a89a4c2168a153a9260f18f455b966ad490/cmd/main.go#L41) via [slog](https://pkg.go.dev/log/slog). A new logger will be added specifically for security events, with a JSONHandler handler, which handles the conversion to JSON. The needs of Concierge are simpler, therefore at the point of each event all of the relevant fields will be logged to this logger, rather than having a common utility handler.

#### Jubilant

No events need to be logged, as Jubilant simply wraps the Juju CLI.

### Security Event Summary

#### ops, ops-scenario, ops-tracing

##### Authentication-related events [AUTHN]

There is no login process in ops (including ops.pebble), ops-scenario, or ops-tracing, so "Successful login", "Failed login", "Account lockout", and "Password changed" are not relevant.

There are no authentication tokens in ops (including ops.pebble), ops-scenario, or ops-tracing, so "Token created", "Token revoked", "Token reused", and "Token deleted" are not relevant.

##### Authorization-related events [AUTHZ]

* **Unauthorized access attempt**: triggered by any error from a Juju hook tool that includes "access denied" (for example, attempting to access a secret without permission, attempting to access relation data without permission).
* Administrative activity: ops, ops-scenario, and ops-tracing do not have access levels, so there is no activity that is specifically "administrative" (from the point of view of the workload, almost everything is administrative, and from the point of view of Juju, nothing is administrative).

These will be logged at WARNING level, and the event name is "authz_fail:{hook tool}". The security event log will include the hook tool that was executed, its arguments (other than for juju-log, action-fail, and action-set, and not including the contents of referenced files), and the exit code and stdout/stderr output from the hook tool.

##### System-level related events [SYS]

* **System startup**: we consider the "system" to be Juju rather than the Ops framework, so leave any logging of event hook starting/stopping to Juju. See [JU151 - Security Event Logging in Juju](https://docs.google.com/document/d/1P4beVsyN-dQ6mRCJWBsc1B655VA-HIf7K6DBVxyUH6w/edit?usp=drivesdk) for details on the Juju security event logging.
* **System shutdown**: as with startup, we leave logging of these events to Juju.
* **System restart**: triggered when [ops.Unit.reboot](https://ops.readthedocs.io/en/latest/reference/ops.html#ops.Unit.reboot) is called.
  * Event name: "sys_restart:[userid]", level INFO.
* **System crash**: triggered when the charm code crashes (via [the existing excepthook](https://github.com/canonical/operator/blob/aa2bc7c35edb9ee2da60cea5cdc19bf13ed1704b/ops/log.py#L85)).
  * Event name: "sys_crash[:reason]", level ERROR.
* **System monitoring disabled**: triggered when [ops.Container.stop_checks](https://ops.readthedocs.io/en/latest/reference/pebble.html#ops.pebble.Client.stop_checks) is called.
  * Event name: "sys_monitor_disabled:[userid,tracing]", level INFO.
  * Note that ops.pebble.Client.stop_checks will do the same. Pebble will emit a security event log for either case, and we do not see additional value in duplicating the event at the Python client level. See [https://github.com/canonical/pebble/pull/666](https://github.com/canonical/pebble/pull/666) for details of the Pebble logging.

##### User-related events [USER]

* **User created**: triggered when [ops.pebble.Client.replace_identities](https://ops.readthedocs.io/en/latest/reference/pebble.html#ops.pebble.Client.replace_identities) is called.
  * Pebble will emit a security event log in this case, and we do not see additional value in duplicating the event at this layer.
* **User updated**: triggered when [ops.pebble.Client.replace_identities](https://ops.readthedocs.io/en/latest/reference/pebble.html#ops.pebble.Client.replace_identities) or [ops.pebble.Client.remove_identities](https://ops.readthedocs.io/en/latest/reference/pebble.html#ops.pebble.Client.remove_identities) is called.
  * Pebble will emit a security event log in this case, and we do not see additional value in duplicating the event at this layer.

See [https://github.com/canonical/pebble/pull/666](https://github.com/canonical/pebble/pull/666) for details of the Pebble logging.

#### Concierge

##### Authentication-related events [AUTHN]

There is no login process in Concierge, so "Successful login", "Failed login", "Account lockout", and "Password changed" are not relevant.

There are no authentication tokens in Concierge, so "Token created", "Token revoked", "Token reused", and "Token deleted" are not relevant. A Google credential file can be passed through Concierge but is not part of Concierge itself.

##### Authorization-related events [AUTHZ]

* Unauthorized access attempt: TBD.
  **Administrative activity**: triggered any time Concierge executes a process with `sudo`, or executes a process where sudo would have been required if Concierge hadn't made adjustments to the user, or would have failed if Concierge itself wasn't run with `sudo`.

These will be logged at INFO level. The event name is "authz_admin:{current user},user_privilege_change".

##### System-level related events [SYS]

* **System startup**: triggered when Concierge starts.
  * Logged at INFO. Event name is "sys_startup:{current username}".
* **System shutdown**: triggered when Concierge finishes.
  * Logged at INFO. Event name is "sys_shutdown:{current username}".
* System restart: Concierge itself does not restart. Restarting services (such as lxd) does not apply.
* **System crash**: triggered if Concierge panics.
  * Logged at WARNING. Event name is "sys_crash:{panic details}".
* System monitoring disabled: Concierge does not have any system monitoring.

##### User-related events [USER]

* User created: Concierge does not create users.
* **User updated**: triggered when Concierge modifies users: adding users to the lxd group, and adjusting the user to work with MicroK8s.

These will be logged at INFO level. The event name is "user_updated:{current username},{changed username},{what was changed}".

#### Jubilant

None of the events in the current version of the SSLDC (25.10) are relevant to Jubilant itself. For events that are triggered by Jubilant running Juju CLI commands, those will be captured by Juju itself and do not need to be separately logged by Jubilant.

## Further Information

These OWASP documents have more details than the security spec about the types of security event and the expected formats, including the log level:

* [Logging - OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
* [Logging Vocabulary - OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html)

Related specs:

* [JU151 - Security Event Logging in Juju](https://docs.google.com/document/d/1P4beVsyN-dQ6mRCJWBsc1B655VA-HIf7K6DBVxyUH6w/edit?tab=t.0)
* [OP073 - Security Event Logging in Pebble](https://docs.google.com/document/d/1u73b0CXAu6DX0zPaiBkGIPBHPUV3y_I6fahr5PnPS1M/edit?usp=drivesdk)

### Hook Command Access Failure

* action-fail: "not running an action" - this doesn't seem like an AuthZ failure
* action-get: "not running an action" - this doesn't seem like an AuthZ failure
* action-log: "not running an action" - this doesn't seem like an AuthZ failure
* action-set: "not running an action" - this doesn't seem like an AuthZ failure
* add-metric: setter only (also the backend functionality has been removed)
* application-version-set: any unit can set the workload version
* close-port: any unit can close its ports
* config-get: it's not possible to request config that you don't have access to
* **credential-get: "cannot access cloud credentials: permission denied"**
* goal-state: any unit can request the goal state
* is-leader: any unit can know whether or not they are the leader
* juju-log: any unit can send to the log - Juju controls which unit it is attributed to
* juju-reboot: only reboots
* leader-get: any unit can get the data (also this is deprecated)
* **leader-set: "cannot write leadership settings: cannot write settings: not the leader"**
* network-get: "no network config found for binding "peer"" or "invalid value "39" for option -r: relation not found" - this doesn't seem like an AuthZ failure
* open-port: any unit can open its ports
* opened-ports: any unit can see which of its ports are open
* payload-register: setter only (also the backend functionality has been removed)
* payload-status-set: setter only (also the backend functionality has been removed)
* payload-unregister: setter only (also the backend functionality has been removed)
* relation-get: "invalid value "39" for option -r: relation not found" - this doesn't seem like an AuthZ failure
* relation-ids: any unit can get its own relation IDs list
* relation-list: any unit can get its own relation list
* relation-model-get: any unit can get the relation model UUID
* **relation-set: "cannot write relation settings"**
* resource-get: "could not download resource: HTTP request failed: Get https://10.240.88.236:17070/model/.../resources/foo: resource#uptime/foo not found" - this doesn't seem like an AuthZ failure - any unit can request the resources that are present
* **secret-add: "this unit is not the leader"**
* **secret-get: "permission denied"**
* **secret-grant: "secret "..." not found"**
* secret-ids: any unit may ask which secrets it has access to
* **secret-info-get: "secret "..." not found"**
* secret-remove: no output if the secret isn't found - this perhaps is an AuthZ failure, but we can't report it without being told that, so need to leave it for the Juju security event
* secret-revoke: no output if the secret isn't found - this perhaps is an AuthZ failure, but we can't report it without being told that, so need to leave it for the Juju security event
* secret-set: no output if the secret isn't found - this perhaps is an AuthZ failure, but we can't report it without being told that, so need to leave it for the Juju security event
* state-delete: any unit can delete from its own state data
* state-get: any unit can get its own state data
* state-set: any unit can set its own state data
* **status-get: "finding application status: this unit is not the leader"**
* **status-set: "this unit is not the leader"**
* storage-add: any unit can request storage
* storage-get: any unit can get the storage details
* storage-list: any unit can get the storage list
* unit-get: any unit can request its public or private address
