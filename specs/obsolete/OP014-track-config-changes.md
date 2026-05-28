# OP014 — Track Config Changes

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-1-20 |

## ![][image1]

## Track config changes (Bug #649)

## ---

*The Charmed Operator Framework*

## Overview

`The goal is to provide the functionality to obtain values of previous config, which gives the user the ability to respond independently to each configuration option change in the config. This functionality is provided on older charms via` config.previous `function, however this is limited only for previous values and does not provide a whole history of changes that could be used to rollback. An example for basic use is restarting a service, and only if the value associated with that service has changed.`

`Config history tracking must take into account the fact that a config can contain many options, and each of these options could contain a 64-bit encoded string, which could lead to a large overheat if all values for each option in the configuration were tracked. Therefore, it is recommended that only a certain option be tracked based on user choice.`

## Proposal

### Operator Framework

`The` tacked `functionality, which configures a new observer for pre_commit, is added to the` Framework `object and allows values to be stored for certain keys in the config. This will allow the user to access the history of values inside the charm via` self.framework.tack `and it will be up to the user where and how to use it.`

`The new value will be tracked by` ConfigHistoryObserver`, which will be observed (will be observed with the tacked function) on the` Framework `pre_commit event. Like this the history should be protected from manual or re-triggering the ConfigChanged Event event and correspond with actual history of configuration changed by the user.`

#### ConfigHistoryObserver object

`The` ConfigHistoryObserver `object, based on the` Object `object with _stroed value define as` StoredState`, will provide several functions:`

1. `In` __init__ `sets the default values for all keys in the config as a list containing the current value.`
2. `The` history `property, which will point to _stored.history object.`
3. `The` keys `property and keys setter are used to track certain config keys.`
4. `The` on_tack `function to handle tracking.`

| class ConfigHistoryObserver(Object):
	"""A class used to store config history for current application."""
	_stored = StoredState()

	def __init__(self, parent):
    	super().__init__(parent, None)
    	self._keys = list(self.model.config.keys())
    	self._depth = -1
    	self._stored.set_default(history={key: [self.model.config[key]] for key in self.keys})

	@property
	def history(self) -> 'StoredDict':
    	"""Config history."""
    	return self._stored.history

	@property
	def keys(self) -> typing.List[str]:
    	"""List of tacked keys."""
    	return self._keys

	@keys.setter
	def keys(self, keys: typing.List[str]) -> None:
    	"""Set list if tacked keys."""
    	_keys = []
    	for key in keys:
        	if key not in self.model.config.keys():
            	raise ValueError("Key {} was not found in application config.".format(key))

        	_keys.append(key)

    	self._keys = keys

	def set_depth(self, depth: int) -> None:
    	"""Set depth of tacked history."""
    	if not isinstance(depth, int) and (depth == -1 or 1 <= depth):
        	raise ValueError("Depth must be integer from range [1, inf). [inf <==> -1]")

    	self._depth = depth

	def _get_last_value(self, key: str) -> typing.Any:
    	"""Get last value for certain key."""
    	key_history = self._stored.history.get(key, [])
    	if not isinstance(key_history, (list, StoredList)) or len(key_history) == 0:
        	raise RuntimeError("Could not get last value for %s", key)

    	return key_history[-1]

	def _tack(self, key):
    	"""Tack specific key from model config."""
    	value = self.framework.model.config[key]
    	if self._get_last_value(key) != value:
        	logger.debug("tack value %s for %s key", value, key)
        	self._stored.history[key].append(value)

        	if self._depth != -1 and len(self._stored.history[key]) > self._depth:
            	# drop old values
            	self._stored.history[key] = self._stored.history[key][-self._depth:]

	def on_tack(self, _):
    	"""Tack config keys on config-changed."""
    	for key in self.keys:
        	self._tack(key)
 |
| :---- |

#### Tracking activation

`Tracking can be activated inside the charm` __init__ `function, using the` self.framework.tacked `function and the keys whose tracking is required.`

| class OperatorCharm(CharmBase):
	"""Charm the service."""

	def __init__(self, *args):
    	super().__init__(*args)
    	self.framework.tacked(["key-1"], depth=-1) |
| :---- |

`The` activate_tracking `function will have two arguments:`

1. **`keys`** `: List[str] - list of keys`
2. **`depth`** `: int - maximum depth of history for individual keys [default=-1] <==> unlimited history`

#### Storage

`The history object will be stored by` SQLiteStorage `into the sqlite3 database as BLOB object or by` JujuStorage `into the controller database. The approach will be the same as for using` StoredState `inside the charm. The bjects are packaged in a binary form with a pickle library.`

### Examples of use

| class OperatorCharm(CharmBase):
"""Charm the service."""

	def __init__(self, *args):
    	    	super().__init__(*args)
    		self.framework.observe(self.on.config_changed,      	    	    	    	    	     self._on_config_changed)
    	    	self.framework.tacked(
      		keys=["key-1", "key-2"], depth=-1,
  	    	)
	...
    	def _on_config_changed(self, _):
    	    	"""Testing config changed handler."""
    	    	...
    	    	if self.model.config["key-1"] != self.framework.tack["key-1"][-1]:
		    	container.restart("service-1") |
| :---- |

### Overheating calculation

`Tracking history matching will extend the duration of the config-changed hook as well as memory usage. These changes have been tested and do not bring significant at once even in the long run.`

`In the test case with one tracked key and a value defined as a string of 20000 characters, the following values were found. The config-changed hook increased time from 0.024ms to 0.038ms and memory usage has increased less than 1 MiB.`

`The test result can be found here(v0.2). There is the Draft PR #685 and it was tested with the following bash command.`

| for HISTORY in true false
do
    juju config history-overheat history=$HISTORY
    for _ in {1..10}
    do
   	 juju config history-overheat test-key="$(openssl rand -hex 20000)"
   	 sleep 5
    done
done |
| :---- |

[image1]: <data:image/png;base64,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>
