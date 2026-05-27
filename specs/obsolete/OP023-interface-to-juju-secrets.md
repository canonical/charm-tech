# OP023 — Interface to Juju Secrets

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-08-05 |

## Abstract

Juju is receiving new functionality to facilitate the sharing and management of "secrets" between units and applications.  This functionality and the reasoning behind it is described in the [JU040 - secrets core](https://docs.google.com/document/u/0/d/1CQckRwyhbdK8cgiuy0oOw3Ic8DAuJ8dne8T44F2xzu0/edit) specification.  In order to facilitate clean, structured usage of this functionality, the operator framework will implement a set of new APIs.  These APIs will primarily revolve around a new Secret class along with new event objects and hooks corresponding to secrets in Juju (e.g. secret-changed, secret-rotate, etc.).  The intent is to provide a relatively simple abstraction over the base juju behavior allowing the full access to secret-related APIs provided by Juju.

## Rationale

[JU040 - secrets core](https://docs.google.com/document/u/0/d/1CQckRwyhbdK8cgiuy0oOw3Ic8DAuJ8dne8T44F2xzu0/edit) - explains the necessity of this well.

## Specification

We need to support the following tasks/operations for secrets:

* secret generation (secret-add hook tool)
* secret (revision) updates (secret-update hook tool)
* secret retrieval (secret-get hook tool)
* secret access granting+revoking+sharing (secret-grant, secret-revoke hook tools)
* secret removal (secret-remove hook tool)

The operator framework will need the following new event classes corresponding to new secret related events in Juju:

* SecretRemoveEvent
* SecretRotateEvent - not deferrable (juju handles this)
* SecretExpiredEvent - not deferrable (juju handles this)
* SecretChangedEvent

Each of these events will have a ".`secret"` attribute for the event's associated secret object.  Secret objects will be created/managed by juju and the framework internals, charm developers will only interact with secret objects initialized through various framework APIs.  The Secret class will be formed approximately as follows:

`class Secret:`
    `The class is not meant to be instantiated directly by charm code.`

* `def __init__(self, uri, relation=None, label=None, revision=None):` Creates a new secret object representing the secret identified by the given uri/secret-id.  For secret objects that are primed to mediate non-owner access to a juju secret, relation must be specified.  label is an arbitrary tag optionally attached to a secret via the juju secret-get, secret-update, or secret-add hooks; the value set for this must be the one from juju.  Revision is an integer indicating which particular secret revision the object represents.
* `def set(self, **keysvals):` If you are the secret creator, update the secret to a new revision with the data from keysvals. Raises an error if you are not the owner.  Uses the secret-update hook tool under the hood. The data structure is updated in place and only committed after the hook exits successfully, same as config (as is done on the juju-agent side).
* `def update(self)`: Updates/binds the charm to the latest revision of the secret.  Uses "secret-get -update" hook tool.  This method is idempotent within a single hook/event context.
* `def grant(self, target: Unit|Application|Relation, relation:Relation = None):` If unit is None, grants secret access to the target.  If the target is a unit or application, a relation must be specified that governs the lifetime of the granted access.  This uses the secret-grant hook tool under the hood.  This raises an error if you are not the owner.
  * grant(self, relation) → grant(relation.app, relation=relation)
  * grant(self, unit) → error. Needs a relation.
* `def revoke(self, target: Unit|Application|Relation, relation:Relation = None)`: This is the complement of grant - removing access from either an entire application (if unit is None) or from the specified unit.  If target is a unit or application, the relation must be specified.
* `def prune(self):` Removes the revision of the underlying revision for the secret by calling the secret-remove hook tool.  This raises an error if you are not the owner of the secret.  This is useful when handling e.g. the secret-remove event or the secret-expired event.
* `def remove(self):` Deletes the entire secret - all revisions.  Raises an error if you are not the secret owner.  Uses the secret-remove hook tool.
* `def get(self, key):` This provides access to the actual secret payload/content associated with the named key (secrets contain key-value pairs).  This data will be loaded on-demand and not cached in order to avoid e.g. logging it unintentionally somehow.  This retrieves the value via the secret-get hook tool.
* def set_label(self, label): Sets the unit/app-local label for the secret.  Should be unique.

The Application class will need new methods for adding/creating and retrieving secret objects:

`class Application | Unit:`

* `def add_secret(self, label, content: dict, expiration: datetime.datetime=None, rotate=None):`  Creates a new secret with the current application as the owner.  `content` represents  the actual key-value pairs for the secret data/payload.    label corresponds to the "--label" flag in the juju secret hook tools.  expiration is an optional expiration time.  rotate is an interval - one of: hourly, daily, weekly, monthly, quarterly, yearly.

`class Model:`

* `def get_secret(self, handle: label|id) → Secret`: A tool for secret creators/owners to retrieve a secret object for a previously created secret that was assigned the given (unit-unique) label.  This is necessary to facilitate e.g. charms creating an app-global secret in an install hook that they then later retrieve in a relation-created/joined hook to grant access to other units.  This will use the secret-ids hook tool to retrieve secrets via label.

Backend methods will need to be added corresponding to the new hook tools:

* secret-get
* secret-update
* secret-add
* secret-grant
* secret-revoke
* secret-remove
* secret-ids

These will be called as appropriate by various methods in the Secret class, as well as the new methods added to the Application class.

Charm development example usage of these new APIs is detailed below.

### Example: Creating and Sharing Secrets

`class SecretProviderCharm(CharmBase):`
    `def __init__(self):`
        `self.framework.observe(self.on.foo_relation_created, _on_foo_relation_created)`

       `# often leaders will be doing the secret management`
	`if self.unit.is_leader():`
    `self.framework.observe(self.on.secret_rotate, _on_secret_rotate)`
    `self.framework.observe(self.on.secret_expired, _on_secret_expired)`
    `self.framework.observe(self.on.secret_remove, _on_secret_remove)`

    `def _on_foo_relation_created(self, event):`
        `if self.is_leader():`
            `label = 'token'`
            `expiration = ...`
            `secret = self.app.add_secret(label, expiration=expiration, rotate='monthly', data='...')`

            `# grants entire remote app access`
            `secret.grant(event.relation)`

            `# share secret id with remote app`
            `event.relation.data[self.app][key] = secret  # auto-serialized to uri`

    `def _on_secret_rotate(self, event):`
        `s = event.secret`
        `if s.label == 'token':`
		`s.update(token='...')`
        `elif s.label == ...:`
           `...`
    `def _on_secret_expired(self, event):`
        `event.secret.prune()`
        `...`

    `def _on_secret_remove(self, event):`
        `event.secret.prune() # remove obsolete revision`
        `...`

### Example: Consuming Secrets

`class SecretConsumerCharm(charm.CharmBase):`
    `def __init__(self):`
        `self.framework.observe(self.on.foo_relation_changed, self._on_foo_relation_changed)`
        `self.framework.observe(self.on.secret_changed, self._on_secret_changed)`

    `def _on_foo_relation_changed(self, event):`
        `rel = event.relation`
        `if 'token' in rel.data[rel.app] and self._db_conn is None:`
            `sec_id = rel.data[rel.app]['token']`
            `secret = self.app.get_secret(sec_id, 'db-token')`
            `self._auth_changed(secret)`
        `...`

    `def _on_secret_changed(self, event):`
        `event.secret.update()`
        `if event.secret.label == 'db-token':`
            `self._auth_changed(event.secret)`
        `elif event.secret.label == 'some-other-secret':`
            `...`

    `def _auth_changed(self, secret):`
        `self._db_conn = self._dial_db(secret.get('data'))`
        `...`

## Further Information

It was decided that we should focus on a lower-level abstraction/representation for secrets in the framework initially in order to allow the observation of how charms use them in the wild.  After more real-world secrets experience has accumulated, we will revisit potential higher-level APIs.  Particularly on the consumer side, it should be possible to streamline things.  One idea, for example is to do something like the following:

`class SecretConsumingCharm(charm.CharmBase):`
    `def __init__(self):`
        `...`
        `self.app.observe_secret('the-relation', 'token', self._connect_db, self._db_connected)`

    `def _db_connected(self):`
        `...`
        `return is_connected`

    `def _connect_db(self, secret):`
        `...`
where the observe_secret call automatically sets up watching remote application relation data for the specified relation ("the-relation") and relation data key ("token").  When it observes a secret being set (on relation changed), it assigns an automatically generated label used to map incoming secret-changed events to the specified callback function (self._connect_db).  While this does remove a tiny bit of flexibility from the charm developer, the cost is small, and it removes nearly all the boiler plate code and  makes errors/mistakes much more difficult to commit.  However, this sort of higher-level API could maybe just be assumed by various relation interface libraries anyway.  So possibly the gain for including something like this in the framework is not so large.  Time will tell.
