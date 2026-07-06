# OP006 — Phased Goal State Support

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-09-02 |

## Abstract

[Note:  this morphed into just a simple "planned_units" implementation]

Implement a "planned_peers" method.

## Rational

"Goal State" is still an area of active development in Juju Core. There are various technical challenges that need to be addressed, including support for goal state that rapidly changes.

We want to give users of the Operator Framework some access to goal state, while insulating them from the challenges until best practices and solutions are more firmly established.

Specifically, we want to tell charm authors how many peers they might expect for a given application. This solves common use cases, such as determining the appropriate status to set for an HA application with pending units.

## Specification

We want to develop the minimal amount of code here, while providing a nice platform for future development.

### Example of Goal State:

### `units:`

### `mysql/0:`

### `status: active`

### `since: 2200-11-05 15:29:12Z`

### `relations:`

### `db:`

### `mysql/0:`

### `status: active`

### `since: 2200-11-05 15:29:12Z`

### `server:`

### `wordpress/0:`

### `status: active`

### `since: 2200-11-05 15:29:12Z`

### Some thinking aloud in pseudo code follows ...

### `ops/model.py`

### `class GoalState:`

### `def __init__(self, meta, backend):`

### `self._units = []`

### `self._relations = []`

### `self._backend = backend`

### `self.meta = meta`

### `def _fetch(self):`

### `state = self._backend.goal_state()  # TODO: cache?`

### `self._units = state.get('units', [])`

### `self._relations = state.get('relations', [])`

### `def peer_count(self):`

### `self._fetch()`

### `return len(self._units)`

### `class ModelBackend:`

### `...`

### `def goal_state(self):`

### `return self._run('goal-state', return_output=True, use_json=True)`
