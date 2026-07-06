# OP027 — Exposing core ops constructs as context vars

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-08-08 |

## Abstract

This spec proposes to add a new `ops.context` module that contains references (or getter functions) to various ops-initialized objects, including

- The charm
- The framework
- The current event

## Rationale

#### Cleaner charm lib code

Many charm libraries hook onto charm events to transform them into lib-specific events.
The init signatures of [k8s-service-patch](http://k8s-service-patch), [jujutopology (from_charm)](https://github.com/canonical/traefik-k8s-operator/blob/main/lib/charms/observability_libs/v0/juju_topology.py), [prometheus-scrape](https://github.com/canonical/traefik-k8s-operator/blob/main/lib/charms/prometheus_k8s/v0/prometheus_scrape.py), [traefik's ingress libs](https://github.com/canonical/traefik-k8s-operator/blob/main/lib/charms/traefik_k8s/v1/ingress.py), [mongodb](https://charmhub.io/mongodb-k8s/libraries/mongodb), just to mention a few popular libs, all conform to the pattern `CharmLibObject(charm: CharmBase, a*,k **)`, and this is not an exception, but an accepted pattern. The existence of a pattern itself hints at the opportunity for generalization.

#### It just makes sense™

- The current event **is**, from a juju agent's perspective, context. Why should ops choose not to present that context as such to the charm, but keep it in the background and only surface it to event handler methods?
- The charm is, similarly, context for charm libs and in general every object that the charm itself creates and uses. Since it's a singleton owned and initialized by the framework itself, why do we force charm code to pass references to itself down to user code?
- Same for Framework.

#### Easier to tell production env from testing env

Currently, ops code contains a number of internal, private flags to inform the framework's backend of whether the (charm) code is running in production or it is being tested.
This is exposed as a `backend._hook_is_running:str` prop. Passing this flag down to all objects that need to distinguish production/testing code forces us to pass down the Framework object itself (or callbacks). Having a globally accessible `event` context var would spare us this need, as any code in ops would be able to ask "is there a currently running event?" without complicating its (init) signature with a Framework object it wouldn't otherwise need.

#### Better testability of charm lib code

By isolating these ops objects as distinct variables, it becomes easier for charm lib testing code to mock them individually, or to omit them altogether if they are not accessed by the library code.
In order to facilitate said mocking, we should consider exposing a public `ops.main.setup_context(charm:CharmBase, framework:Framework, event:EventBase)` function. Test user code can call that function to ensure the envvars are properly setup.

#### Better exposure of nested event chains

Suppose the charm receives a relation-changed event, which gets deferred. The charm receives then a relation-broken event, but the deferred relation-changed will be reemitted first. It is presently impossible (unless you go dig into os.environ) for the charm to realize that the deferred event is, in the present context, no longer "relevant", or in some circumstances it could be plain wrong to perform certain actions, and give rise to errors.
Exposing the 'currently running event' as a global envvar would enable charm code to have safer control flows when it comes to deferring events.
Also, in some cases, charm libs wrap multiple events and coalesce them into a single charm-facing event. The charm has no choice but to conform to this API (or re-subscribe to the raw events individually, and re-wrap them). Exposing the currently running event would allow charm code to 'unwrap' the library-owned event and check the 'underlying one' without breaking the lib boundary or duplicating code.

#### Simpler charm libs patterns

Exposing direct access to 'the current event' means that charm libs that perform relatively simple tasks (such as do something on install) could be drastically simplified. Consider for example the [k8s-service-patch](https://github.com/canonical/traefik-k8s-operator/blob/main/lib/charms/observability_libs/v0/kubernetes_service_patch.py); the current design forces it to inherit from Object, and use `framework.observe` calls to respond to specific events (install and upgrade).
This library could be rewritten using a simpler, more functional style, like:

| def patch(*args, **kwargs):
   if get_current_event().name in {'install', 'upgrade'}:
       _patch(*args, **kwargs) |
| :---- |

## Risks

Depending on the order in which we choose to initialize those variables, the current event might become available to the charm at init time.
This means accepting the risk (but not necessarily endorse the pattern!) that charmers start writing code like:

| class MyCharm(CharmBase):
   def __init__(self, a*, k**):
       if get_current_event().name == 'install':
           self._on_install()
       ... |
| :---- |

Disclaimer: nothing prevents charm code from doing this already (from os.environ...), it would just become easier.
