# OP020 — Unit Status

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | Jul 14, 2022 |

## Abstract

This spec analyses the issues charmers currently face with using the ops-provided unit status object to express the charm's status. It describes the possible solutions we have thought of, one proof of concept that was devised and the early feedback we got on it.
Conclusions are drawn to propose a way forward: a library to handle setting and getting compound status, based on the "Priority Queue" pattern developed by the OpenStack team for classic and reactive charms.

## Rationale

Charm authors run into the following problems with status:

- The Operator Framework does not guard against clobbering a "Blocked" or "Error" status with an "Active" or "Waiting" status.
- There may be multiple causes of a "Blocked" status - e.g., multiple config values that have not been set - and Ops does not make it straightforward to "amalgamate" status.
- When a hook "fixes" a problem, it can be unclear whether the "Blocked" status should be cleared - there might be multiple problems!

### The OpenStack charmers solution: priority queue

We asked the OpenStack charmers to describe their solution.
They had implemented a priority queue to manage charm status.
The priority queue consists of a collection of statuses which can be managed independently. The 'master' status of a charm - the one that is eventually surfaced to the user and appears in `juju status`,  has status equivalent to the worst-case status of each of the 'child' statuses, and a message which provides a summary of each of the child status messages.
Each status is being tracked independently, and can be independently set by the charm author.

We set out to elaborate a proof of concept API to wrap this priority queue in the Operator Framework. The following requirements were identified for the solution:

- The priority queue would be modelled as an object, where each status could be assigned a manual priority value.
- The priority queue API would focus on statically defining, at charm creation time, how the pool would be composed. One would do this by subclassing StatusPool and defining class attributes corresponding to the statuses in the pool. This allowed for nice code completion and type hints for interacting with the status objects. There would be a way of dynamically adding/removing statuses at runtime, but that would not be the topmost use case for this lib.
- The same ops.model.StatusBase objects would be used to set statuses in the pool, and the API would also have the same 'feel', i.e. one should be able to set a child status by __setattr__, same as one does with CharmBase().unit.status = ActiveStatus('foo')
- Setting a status in a pool would, by default, not 'commit' the pool, i.e. would not automatically set the unit status. One has, instead, to manually call StatusPool.commit() that would 'resolve' the priority queue, coalesce it into one toplevel master status, and set the unit status to that.
- The clobbering logic would default to the one developed by the OpenStack team: the worst-case status would become the toplevel status, and the message would contain a summary of the child statuses (so that at all times one would have an overview of the lower-priority ones as well).
  - However, the clobbering logic would easily be pluggable by providing your own clobberer (a handful of other logical alternatives were also provided for experimentation).

Additionally, we had identified the following **nice-to-haves** for the library:

- Provide charm authors with tools to point operators toward a resolution. Options we considered:
  - assigning each Status object a logger instance and potentially expose shortcuts like Status.warning('foo'), so that the charmer would be able to associate log output with the 'status' instance that is responsible for it.
- Utilise the existing status history which is supported by Juju.

### Early feedback

We received usability feedback from two users, who found the following issues with the proposed solution:

- The implementation was too complex. The commenter proposed to scrap most of the sugar (the 'ops.model.StatusBase' feel, typing support) and offer instead a much leaner and concise solution. The commenter went on and implemented their own simpler version based on our design. [That can be seen here.](https://review.opendev.org/c/openstack/charm-ops-sunbeam/+/852796/60/ops_sunbeam/compound_status.py)
- The main use case for the pool, for another commenter, was not statically defining the status of a charm but instead dynamically managing, at runtime, a variable number of statuses. Our POC had focused on a charmer describing at charm creation time 'this charm has *n* statuses: one for its relation A, one for its workload, one for its config, ...' while the commenter wanted to use the pool to track statuses for each individual relation existing on an endpoint.

### Conclusions

- The priority queue concept works: everyone agreed that **the topmost status should be the worst-case child status**.
- There was general agreement that **manually committing the pool** as desired was a good idea.
- There were different opinions on what the message should be:
  - some suggested that a single message (the one belonging to the worst-case status) should  be displayed in isolation, with the rationale:
    *"Typically the several broken statuses you have are interdependent, so as soon as you fix the 'worst' one, many other issues will resolve automatically, so there's no point in showing the lower-priority items."*
- Others suggested that there should be an action, or enough logger output, to determine what the subordinate statuses were, because it is good to have an overview.
- Lacking general agreement, we conclude that the **message clobbering strategy should remain configurable**, with a sensible default (the default should be the OpenStack one: show a summary of all subordinate statuses).

- Regarding the implementation, we concluded that a leaner, low-sugar solution should be preferred. **The StatusPool API should focus on dynamically defining statuses at runtime** instead of defining them statically e.g. by subclassing StatusPool. This does not prevent one from ALSO statically defining some statuses, in the charm's __init__ for example, using some sort of set_default strategy.
- The overall implementation should focus on being **lean and simple**.
- There was no agreement on whether some way should be provided (logging output, or an action) to pretty-print all statuses or either way provide an overview of the whole pool, also the lower-priority statuses. The initial implementation should therefore not include such a thing.
- Status objects that are part of the pool should **accept being set to unknown** to signify that they are at this time not relevant / tracked. E.g. the status for a relation that is not active, or a config mode that is not set.
- We received no feedback on the idea of associating a logger with each status - we therefore drop it for now. It will become clear later if there is interest for it.

## Specification

**Class StatusPool(Object); init sig = (charm: CharmBase, key:str = 'statuspool')**:

- attrs:
  - *AUTO_COMMIT*:*bool*   - flag to control whether the status pool should commit automatically every time one calls Status.set().
  - *summarizer*: *Summarizer*  - callable that takes a sequence of Status objects and outputs a single ops.model.StatusBase.
- *get_status(name: str) -> Status*.  - Adds a status to the pool. If it already exists, returns it.
- *delete_status(name: str) -> Status*.  - Pops a status from the pool if it exists, else does nothing.
- *coalesce() -> ops.model.StatusBase*. - Generate the highest-priority status
- *commit() -> None*; essentially: self.charm.unit.status = self.coalesce()

*StatusName = 'blocked' | 'active' | 'waiting' ...*

**Class Status; init sig = (name: str)**:

- attrs:
  - *value -> StatusName*
  - *message -> str*
- *set(value: StatusName, message: str='') -> None*.
- *unset() -> None.*  Sets the status back to "unknown", which by default will make it disappear from the clobbered status summary in the pool, but keep tracking it.

## Notes and Links

Initial [POC available here](https://github.com/PietroPasotti/compound-status)
Alternative, simplified [implementation available here](https://review.opendev.org/c/openstack/charm-ops-sunbeam/+/852796/60/ops_sunbeam/compound_status.py)
[Notes from June Meeting](https://docs.google.com/document/d/1I_dgldRUNBBJC5fEFNnKnmjS0eF9E3YYrwZ8P7XZKyg/edit?usp=sharing) with the OpenStack team
