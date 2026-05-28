# OP014 — Composable Charms

| Field | Value |
| --- | --- |
| Status | Rejected |
| Created | 2022-04-07 |

## Abstract

We see some patterns arise in the usage of the ops framework to write charms. Some consider them to be antipatterns, some don't, but the fact is they appear to be useful as many, many charms converge to using them. This proposal is about whether and how to improve the Operator Framework to address the issues that these patterns attempt to work around.

## Rationale

We're referring to the **'common-exit-hook'** pattern, and the **'catchall-event-handler'** pattern.

Fact is, many charms (TBD: which charms?) are easier to reason about if the flow is as follows:

1) Observe the world's current state (its own workload's health, the liveliness [and presence] of any number of integrations, storage, the juju agent status, etc...) and gather it up in one big blobby State
2) Depending on the State, choose what to do
3) Check how things went in 2): did it work well, did it not succeed?; condense it as a single Status + message and publish it for the admin to see
4) Exit

We think for this reason the patterns mentioned above arise: the common exit hook allows 3) to be done in a uniform way, and the catchall event handler allows 1) to be done in a single place. This strategy proves to be not only effective, but also rather elegant at least in cases where the charm isn't especially complex (e.g. [the prometheus charm](https://github.com/canonical/prometheus-k8s-operator/blob/main/src/charm.py)). For XXL charms such as openstack, we can imagine this being unmanageable.

Another related issue to this is: [https://github.com/canonical/operator/issues/665](https://github.com/canonical/operator/issues/665) .  The idea is that if status gets set to e.g. blocked, only certain other hooks/situations should be allowed to unblock the status.  Basically we are operating in a different charm state - which in the suggested solution in this doc would be represented by a different subcharm.

Furthermore, we see that some charms have some common guards that trigger defers or early-exits at the beginning of each hook, for example container.can_connect() on k8s. Many k8s charms are basically useless until their container is ready. Why do we force authors to write that code?

Finally, one of the refrains of charming is `idempotency`, which boils down to 'you shouldn't care how you got here'. Then why do we force users to subscribe to specific events, when these events don't necessarily map to the state that the users need to actually be in to take action? This is presently code for: 'wait for scriptlets', but we think there's more to it. We think the OF can do a better job of encoding charm state machines.

## Specification

I think the best way to see how this could look like is via a pseudocod-y spec, where it is self-evident how the code flows.

| class Charm(CharmBase):
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       if self.container.can_connect():
           self.branch(ConnectedCharm)

       self.on.container_pebble_ready(self._install_software)

   def _install_software(self, event):
       print('install')


class ConnectedCharm(CharmBase):
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       if self._is_related() and self._relation_healthy():
           self.branch(RelatedCharm)

       self.on.friendship_relation_created(self._relate)
       self.on.friendship_relation_departed(self._depart)

   def _relate(self, event):
       print('relate')

   def _depart(self, event):
       print('depart')

   def _is_related(self):
       # check that relation is there
       return True

   def _relation_healthy(self):
       # remote has shared data
       return True

class RelatedCharm(CharmBase):
   ... |
| :---- |

I think what's evident from this spec is that Charms become composable, layered entities where branches only become active when a certain state is observed, whereby logic is contained to where it belongs. Not only this avoids boilerplate and catch-all state-gathering, but also allows users who complain about 'what has changed in config'? To make their charms a lot more flexible in a natural way:

| class ConfigurableCharm(CharmBase):
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       if self.config['A'] == 'foo':
           self.branch(FooCharm)

       if self.config['B'] == 'bar':
           self.branch(BarCharm) |
| :---- |

This way, the A-specific (foo) charm logic can be contained to a specific branch...

A Charm then becomes a tree-like structure, with a root charm (no state known) down to hyper-specialised leaves where the state is fully known and predictable, and can do logic that 'assumes' a great deal of it and is as a result much simpler and debuggable.

This has the potential of making reasoning about idempotency easier: it doesn't matter how you got here: fact is given that you are executing a code block in the branch root/connected_charm/related_charm, you are somehow connected to a container and you have a healthy relationship with charm Y. Do with it what you have to.

Another use case:

| class MyCharm(CharmBase):
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)

       if self.unit.is_leader():
           self.branch(LeaderCharm)

class LeaderCharm(CharmBase):
   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       self.followers.whip()  # or whatever a good leader would do |
| :---- |

With this "the charm", instead of being a static entity, is dynamically assembled at runtime by observing the (workload, juju) state. So if for example the workload isn't live yet, the charm will not have access to any workload management logic (yet, until it does).
