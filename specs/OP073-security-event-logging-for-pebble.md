# OP073 — Security event logging for Pebble

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | Jul 29, 2025 |

## Abstract

As part of the Canonical SSDLC, products are required to log security events, as covered in [SEC0045](https://docs.google.com/document/d/1nInWP9pEEhloKMfgzDsd4Pub4530OxQcKKh716Gvxfk/edit?tab=t.0). This spec outlines the security events that happen in Pebble, and how those will be logged.

## Specification

We plan to add security logging for the following events:

* Daemon startup/shutdown (sys_startup, sys_shutdown)
  * Fields: UID ("sys_startup:1000")
  * We considered adding sys_crash, but there's no way in Go to have a global panic handler, so it's not really feasible within Pebble itself.
* Unauthorized access attempt to API (authz_fail)
  * Fields: UID or user, resource (API URL, for example "/v1/layers")
  * The authz_fail log is level=critical and only seems to apply if you know the user but they're unauthorized
* Administrative activity (authz_admin)
  * Fields: UID or user, operation (for example "add-layer", "push-file")
  * Pebble has the concept of "admin" user, but it's too general - it's used for all writes. Instead, we'd reserve this for cases that are admin *and* sensitive:
    * add layer
    * files (pull and push)
    * exec
* Updating identities (user_created, user_updated, user_deleted)
  * Fields: username, operation
* Health checks stopped (sys_monitor_disabled)
  * UID or user, operation (for example "check-stopped")

As an example, the startup and shutdown security logs would appear as follows:

```
# Daemon startup
2025-07-30T03:53:54.474Z [pebble] {"type": "security", "datetime": "2025-07-30T15:53:54+12:00", "level": "WARN", "event": "sys_startup:1000", "description": "Starting daemon", "appid": "pebble"}

# Daemon shutdown
2025-07-30T03:53:57.947Z [pebble] {"type": "security", "datetime": "2025-07-30T15:53:57+12:00", "level": "WARN", "event": "sys_shutdown:1000", "description": "Shutting down daemon", "appid": "pebble"}
```

## Further Information

These OWASP documents have more details than the security spec about the types of security event and the expected formats, including the log level:

* [Logging - OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
* [Logging Vocabulary - OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html)

This spec was originally based on [OP067 - Security Event Logging for Charm SDK](https://docs.google.com/document/d/1VsxGDxuUOo6A3PfT_qzFssR3qTOJInrHPORitnbtiDk/edit?tab=t.0) ([related PR](https://github.com/canonical/operator/pull/1905)).
