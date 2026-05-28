# OP076 — Secrets backend refactoring

| Field | Value |
| --- | --- |
| Type | Implementation |
| Created | 12 Sept 2025 |

## Abstract

Ops contains a "shared secrets cache" that was designed to work around Juju limitations at the time.
This document describes how this cache will be removed or refactored.

## Rationale

The primary motivation is to resolve this Ops bug:

- [Secret objects getting out of sync](https://github.com/canonical/operator/issues/1536)

Analysis reveals that the backend `_secret_set_cache` was introduced to work around:

- [`secret-set` invocations are merged within the same hook](https://bugs.launchpad.net/juju/+bug/2081034) fixed in Juju 3.5.5
- [`secret-set` no longer creates a new revision if the content is same](https://bugs.launchpad.net/juju/+bug/2069238) fixed in Juju 3.6.0
  - Note that read-modify-write update specified lower still causes redundant secret revisions in earlier Juju versions, however the blow-up is limited to a fixed multiple.

Now that all supported Juju series contain the fix for both bugs (3.6) or don't have secret functionality (2.9), we should be able to throw the cache out.

At the same time, there are Juju 3.2 controllers deployed internally at Canonical, which means that we can't completely rely on the hook tools and unit agent.

Related issues:

- [Secret `description` is not emulated correctly in unit tests](https://github.com/canonical/operator/issues/2037) (ops)
- [secret-set and secret-get hook tools may swallow errors](https://github.com/juju/juju/issues/20623) (juju)

## Partial

TBD describe what was done and what was not done

## Specification

The main code flow will be made for Juju 3.6, the cache will be removed and  ops method calls will be translated to hook tool invocations as follows:

| Model.get_secret(id=...) | *# Must raise early on error* secret-get $id |
| :---- | :---- |
| Model.get_secret(label=...) | *# Must raise early on error* secret-get --label $label |
| Model.get_secret(     id=...,     label=...) | secret-get $id --label $label
*# deliberately ignore the output juju#20623* |
| Secret.label  *# property* | *# If the secret is pinned by id:*
secret-info-get $id
*# If the secret is pinned by label:*
**return** self._label |
| Secret.get_content() | secret-get $id *# or* secret-get --label $label |
| Secret.get_content(refresh=True) | secret-get $id --refresh *# or* secret-get --label $label --refresh |
| Secret.peek_content() | secret-get $id --peek *# or* secret-get --label $label --peek |
| Secret.get_info() | secret-info-get $id *# or* secret-info-get --label $label |
| Secret.set_content(...) | secret-set $id ... |
| Secret.set_info(label=...) | *# If pinned by label*
if self._label == label: return id = (secret-info-get --label $label).id *# In any case* secret-get $id --label $label |
| Secret.set_info(description=...) | secret-set $id --description $desc |
| Secret.set_info(expire=...) | secret-set $id --expire $exp |
| Secret.set_info(rotate=...) | **if** rotate == (secret-info-get $id).rotation:
    **return** secret-set $id --rotate $rot |
| Secret.set_info(     label=...,     rotate=..., ) | *# Juju 3.6.x* secret-set $id --label $label --rotate $rot *# Juju 3.0.x \~ 3.5.x* secret-set $id --label $label
secret-info-get $id
secret-set $id [--desc old.desc ...] --rotate $rot |
| Secret.set_info(expire=...) ... Secret.set_content(...) | *# Juju 3.6.x* secret-set $id --expire $exp ...  secret-set $id key1=... key2=... *# Juju 3.0.x \~ 3.5.x* secret-get $id secret-set $id --expire $exp ... secret-info-get $id
secret-set $id --expire $exp ... |
| Secret.set_content(dict(key1=...)) Secret.set_content({"key1": ...}) ... Secret.set_info(expire=...) | *# Juju 3.6.x* secret-set $id key1=... key2=... ... secret-set $id --expire $exp *# Juju 3.0.x \~ 3.5.x* secret-info-get $id secret-set $id key1=... key2=... ... secret-get $id --peek secret-info-get $id secret-set $id --expire $exp key1=... key2=... |

Note that label is special, it is orthogonal to content and metadata.

The two implementations will be validated using a set of integration tests with extensive coverage of different combinations of ownership, revisions, labels, metadata, and content.

The tests will be run against a range of Juju versions, where 3.6 outcome is considered authoritative (that's on the test author's shoulders, validated during PR review) and 3.x outcomes must conform to the very same outcomes. Additionally, the same test charm will be exercised using `ops[testing]` to ensure that the unit testing framework emulates the same outcomes.

## Possible semantics changes

##### Early vs. late secret content resolution

Today, `self.model.get_secret(...)` loads the secret content during the call.

The call may fail in a variety of circumstances:

- Secret with given id does not existexit
- No secret with given consumer label exists
- Secret with given id exists but access has not been granted

The call may also erroneously succeed (a false positive) if both id and label are supplied, don't match, and another secret with the supplied label exists. The Juju hook tool may fail or may [return the content by label, ignoring the id](https://github.com/juju/juju/issues/20623).

Some charms may rely on greedy content resolution, that is catch the exception at this point in time, and not catch exceptions later.

One possibility is to break that assumption, and have `get_secret` return an object that only contains id or label, without attempting to resolve the secret content.

## Further information

Nothing at this point.
