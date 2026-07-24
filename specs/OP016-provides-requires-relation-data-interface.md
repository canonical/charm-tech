# OP016 — Provides-Requires Relation data interface

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2022-04-07 |

## Abstract

It is a common pattern in charming to write charm libs providing relation interfaces consisting of a Provider and a Requirer side. We propose here a new relation data OO layer to facilitate writing such relation interfaces.

**Goals**:

- Identify the pain points in the present way of interfacing with relation data in *ops*.
- Facilitate the development of provides-requires charm libs
- Facilitate the development of code where direct read/write access of relation data is desired (i.e. when not mediated by a charm lib API).

**Non-goals**:

- Facilitate the consumption of charm libs via their API

## Rationale

When charming, one often has to read and write relation data. Especially when writing both sides of a relation interface (a charm lib, typically), one realises that **it is challenging to think about the data being exchanged** and the flow of it.
I think this task would become simpler if we were to adopt a new metaphor for what we are doing, followed by a new vocabulary and a new OO model in Ops core.

Additionally, we believe that allowing the user to **type** the databags (a local unit databag vs. a remote application databag) is essential to helping the developers understand what they are doing, develop faster and spot bugs more easily, as well as documenting relation libraries.

It is impossible to tackle the second problem (typing) without reworking the OO layer because the current interface (RelationData) does not distinguish between local/remote apps and units in the mapping it exposes. Consequently we cannot communicate in any way that RelationData[<LocalUnit>] is not the same type as RelationData[<RemoteUnit>] (or even RelationData[<LocalApp>]!)

## Specification

We propose to create an endpoint-wrapper charm lib that one can import and use seamlessly with ops. In the future, we could think of merging some of these concepts in ops.

Suppose we're developing a MyCharm with metadata:

| name: my-charm
provides:
  foo:
   interface: bar |
| :---- |

We propose to reference relation data using the following notation:

| from endpoint_wrapper import Endpoint
class MyRelationProvider(Object):
     def __init__(self, *args):
       super().__init__(*args)
       self._endpoint = Endpoint(self, 'foo', on_changed=self._handle)

   def _handle(self, event):
       # we get the specific foo relation we're dealing with; this replaces event.relation (if this ever gets merged in ops, self.foo.current and event.relation would be the same object.
       relation = self.foo.current

       data = relation.remote_app_data['some_var']
       relation.local_app_data['some_var'] = "44"

       # self.foo represents multiple relations:
       config = []
       for relation in self.foo.relations:
           config.append(relation.remote_app_data['some_var'])
           for _remote_unit, unit_data in relation.remote_units_data.items():
               config.append(unit_data)

       # we don't have to think about the difference between self.app and relation.app; it suffices to know what is local and what is remote
       relation.local_apps_data[relation.remote_app]['configured'] = True
              def publish_url(self, unit_name:str, url:str):
       # we get the specific foo relation we're dealing with; this replaces event.relation (if this ever gets merged in ops, self.foo.current and event.relation would be the same object.
       relation = self.foo.current
       Relation.local_app_data.urls = update(...)
         |
| :---- |

##### Typing:

We can type a relation endpoint using dataclasses, TypedDicts, pydantic Models, or whatever we like.

| # We do so by creating models for the four types of databags involved in the relation: remote app, remote unit, local app, local unit. In this example, requirer unit and provider app hold no data, so we omit them.

class AppModelA(TypedDict):
  ingress: int

class UnitModelB(TypedDict):
  unit_name: float

# we instantiate a Template to hold this information.
bar_template = Template(
   requirer=DataBagModel(
       app=AppModelA
   ),
   provider=DataBagModel(
       unit=UnitModelB
   )
)

# we instantiate Endpoint and tell to mypy that we're looking at the template from the POV of the provider
foo = Endpoint(self, 'foo', provider_template=bar_template)

data = foo.local_apps_data[<some_app_instance>] # mypy/pyright know that this is of type: AppModelA; because local=provider.
# so this is good:
Ingress = data['ingress']

# but we get in-IDE linter errors for:
key = data['non_existent_key']
data['another_bad_key'] = 42 |
| :---- |

The idea is that *bar_template* would live and be maintained in the charm lib codebase and be used by both the requirer and the provider charms.

## Prior art

- [ST010 - Adopt schemas into charm relations](https://docs.google.com/document/d/1mpG_t9cB0CDWzpUlTRK5_eED-abLY5Z4wxEIdgqLtCM/edit#heading=h.yxtctpev7qc0)
  This document appears to be about (a precursor of) SDI.
- SDI: [https://pypi.org/project/serialized-data-interface/](https://pypi.org/project/serialized-data-interface/)
  This project was abandoned as it was too complex to maintain (and the maintainer left). The core idea is to wrap a requirer/provider endpoint and assign to it a schema (in jsonschema) that will automatically validate the databag contents on each read/write. Also, the wrapper exposes a 'status' depending on the presence of data and its correctness, e.g. 'ready' (relation exists and data is correct) and 'broken' (relation exists but data is invalid).
  This differs from our proposal in that we don't focus on validating or formatting the databag contents, only on the way in which they are exposed to and accessed by the user. Clearly our proposal offers a natural entry point on validation: the template. We can leverage pydantic as a modelling language to get validation on top of the wrapper's plumbing with minimal effort.

- O11y team: "had some base classes at one point but abandoned them since they weren't doing anything useful".

- Data team: [data-platform-libs](https://github.com/canonical/data-platform-libs/tree/main/lib/charms/data_platform_libs/v0)

## Current status

You can try out a POC implementation of some of these concepts at:
[https://github.com/PietroPasotti/relation-wrapper](https://github.com/PietroPasotti/relation-wrapper/tree/main)

To use:
*charmcraft fetch-lib charms.relation_wrapper.v0.endpoint_wrapper*

POC:
[https://github.com/canonical/istio-operators/blob/master/charms/istio-pilot/lib/charms/istio_pilot/v0/istio_gateway_name.py](https://github.com/canonical/istio-operators/blob/master/charms/istio-pilot/lib/charms/istio_pilot/v0/istio_gateway_name.py)  becomes [https://pastebin.canonical.com/p/ktQGvSymkC/](https://pastebin.canonical.com/p/ktQGvSymkC/)
