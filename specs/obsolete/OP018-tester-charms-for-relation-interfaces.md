# OP018 — Tester charms for relation interfaces

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-04-29 |

## Abstract

This advances a pattern to develop tester charms for relation interfaces along with ways to distribute them and use them.

**Goals**:

- Make the development of tester charms for relation interfaces easier
- Make the maintenance of unit and integration testing code for relation interfaces easier
- Make the development and maintenance of test code in charms relying on a third-party relation easier

**Non-goals**:

- Address runtime concerns of relation code, charm libs or charms

## Rationale

Developing a tester charm for a relation interface nowadays typically involves:

- charmcraft init (or clone a template)
- Delete a few files you are not going to need (config, itests, utests, readmes, jujuignore, etc...)
- Override metadata.yaml and charm.py (the only two files that typically will be different across tester charm) to implement a very basic requirer (or provider) for your relation interface.
- Charm.py will define a tester charm with some simple logic to mock the requirer (or provider) side of the relation.

This is repetitive and error-prone because each tester charm is developed from scratch and needs to be individually tested.
Furthermore, typically a relation interface charm library defines the requirer and the provider, and the library 'lives' with the provider side of the relation. The requirer side of the interface will be used by some other charm. Both the requirer and the provider charm will want to test the integration; which means the above has to be done twice in two places, which makes maintenance harder. When the library receives an update, the tester charm might reveal that there is an issue, but the developer will have to:

- dive into the library code to find out how to fix it
- Fix the tester charm
- Fix the charm.

We propose to ship, together with the relation interface code (living in some charm lib), the core logic of a tester charm encapsulated ideally in a single function. This logic can be consumed by unit and integration tests in any charm that uses the charm lib under consideration.

To achieve this, we propose to add to the ops library (to start with, it will be a charm lib):

- A *Tester* decorator to associate a function containing said core logic to the relation endpoint (relation_name + [requirer/provider]) it intends to be a tester for.

The middleware to achieve this should live in the charmcraft tool. In particular we propose to add to charmcraft three entry points:

- *charmcraft tester test [path/to/lib.py]*: to verify that the *Tester*-decorated function meets some minimal soundness requirements (a smoke test). This is a tool for the developer of the lib and the tester code.

- *charmcraft tester init [path/to/lib.py]:* to create a charm folder structure (like *charmcraft init* would) where the charm metadata is automatically generated and the *Tester-*decorated function body gets filled into the charm's __init__. This is a tool for the consumer of the lib.
- (this is optional) *charmcraft tester generate-fixtures:* to generate, based on the available metadata, *pytest(*and *pytest-operator)* fixtures to use in test code. This is a tool for the consumer of the lib.

## Specification

Firstly, we propose that the tester charm code lives with the library it is supposed to be a tester for, or closer to it. So that the maintainer of the library also is responsible for maintaining the infrastructure for the charms that will integrate with it to verify their compatibility with the protocol. This is both for unit and integration testing.

Furthermore we propose to streamline the structure of a tester charm to a minimal abstract structure to facilitate the task of writing (and maintaining) the tester charm code. Since only the metadata and the `charm.py` code will change, we propose to introduce some tooling in `ops.testing` and `charmcraft` to facilitate the maintenance and consumption of the tester charms.

The characteristics of a tester charm are:

- Only requires/provides exactly one relation
- Implements the provider or requirer side only.
- Has minimal itests/utests (a smoke test namely), to verify that the tester charm itself is functional.
- All the charm does is:
  - Try and search for a relation called {relation name}; if not found: exit with status Blocked.
  - Try and read the data from the relation, decide if we're happy or not; if not, exit with status Blocked or Waiting, depending on things.
  - If all is well, do what is appropriate (mock your side of the relation data for example, drop a file to your container, spin up a service, send an email, etc...) and exit with status Active.

The proposed workflow for the developer of the library is: add to your charm lib code the following lines:

lib/charms/my_charm/v0/my_relation_library.py

| from ops.testing import Tester ...

class MyRelationProvider(Object):
   ...

class MyRelationRequirer(Object):
   ...
 # This is how we specify the tester for the provider
@Tester(MyRelationProvider, 'provides')
def test_provider(self, framework, key) -> Status:
   provider = MyRelationProvider(self, ...)

   # if we don't have a MyRelation yet:
   if not provider.relation:
       return WaitingStatus('awaiting relation')
   # if the relation is alive but the data doesn't look good
   elif not provider.happy:
       return BlockedStatus('nope')
   # if the relation is alive and the other side provided what it was expected to
   else:
       mock_data = {'foo': 'bar'}
       provider.reply(mock_data)
       return ActiveStatus('all good!') @Tester(MyRelationRequirer, 'provides')
def test_requirer(self, framework, key) -> Status:
   requirer = MyRelationRequirer(self, ...)    ...

 |
| :---- |


The tester charms that this code abstracts away can and should in turn be tested (to catch errors in the test_provider body). This can be done in an automated way. Simple unit and integration tests can be automatically generated and run by charmcraft (or another dedicated tool).

The developer of the tester code would run:
`charmcraft test -tester ./lib/charms/my_charm/v0/my_relation_library.py` and the tool will:

- Scan my_relation_library.py for Tester objects
- Pack a charm for each
- Run the charm through:
  - A simple integration test deploying the charm and verifying that it reaches Waiting status
  - A simple unit test using the Harness that fires the initial hooks on the charm; verifies the status is Waiting throughout.
  - Creates the required relation, verifies that the status goes to Blocked or Active.


This is what the workflow would look like for a user of the relation (be it the charm that owns it, the provider, or any requirer charm):

The user runs `charmcraft init -tester my_relation:requirer` and that will bootstrap a charm folder with:

metadata.yaml:

| provides:
  my_relation:
       interface: my_relation |
| :---- |

charm.py:

| def test(self, framework, key) -> Status:
   ... # same as above, copy-pasted

class MyRelationProviderTesterCharm(CharmBase):
   def __init__(self, framework, key):
       super(MyRelationProviderTesterCharm, self).__init__(framework, key)
       self.unit.status = test(self, framework, key) |
| :---- |

### Further work

We could provide (`charmcraft init -tester-fixtures my_relation:requirer`) to generate, based on the same data, `pytest-operator` fixtures that build and deploy MyRelationProviderTesterCharm, so that all the developer has to do is (pseudocode):

| def test_integrate_my_relation(ops_test, my_relation_provider_tester, my_charm):
   ops_test.deploy(my_relation_provider_tester)
   ops_test.model.wait_for_idle(my_relation_provider_tester.name, status='waiting')

   ops_test.deploy(my_charm)
   ops_test.juju(
       "relate",
       f"{my_relation_provider_tester.name}:my_relation"
       f"{my_charm.name}:my_relation"
       )

   ops_test.model.wait_for_idle(...) |
| :---- |
|  |



## Case studies:

Traefik Ingress-per-app requirer tester code (cf.[https://github.com/canonical/traefik-k8s-operator/pull/47](https://github.com/canonical/traefik-k8s-operator/pull/47))

| relations = self.model.relations.get("ingress-per-app")
if not relations:
   self.unit.status = BlockedStatus("not related yet")
   Return
relation=relations[0]

ipa_ingress = IngressPerAppRequirer(charm=self, endpoint="ingress-per-app")
try:
   ipa_ingress.request(host="0.0.0.0", port=80)
   # can raise UnversionedRelation error if we're in a departed hook
except Exception as e:
   print(f"error requesting ingress: {e}")

self.unit.status = WaitingStatus("ipa not ready yet")
try:
   if ipa_ingress.is_ready(relation):
       self.unit.status = ActiveStatus("ipa all good!")
except Exception as e:
   print("IPA error:", e) |
| :---- |

Traefik Ingress-per-unit requirer tester code (cf.[https://github.com/canonical/traefik-k8s-operator/pull/47](https://github.com/canonical/traefik-k8s-operator/pull/47))

| relations = self.model.relations.get("ingress-per-app")
if not relations:
   self.unit.status = BlockedStatus("not related yet")
   Return
relation=relations[0]
relation = relations[0]
ipu_ingress = IngressPerUnitRequirer(charm=self)

ipu_ingress.provide_ingress_requirements(host="0.0.0.0", port=80)
self.unit.status = WaitingStatus("ipu not ready yet")

try:
   if ipu_ingress.is_ready(relation):
       self.unit.status = ActiveStatus("ipu all good!")
except Exception as e:
   print("IPU error:", e) |
| :---- |

Ingress-per-unit requirer tester from  traefik-route (Cfr https://github.com/PietroPasotti/traefik-route-k8s-operator/tree/main/tests/integration/ingress-requirer-mock) (note the subtle differences, and how having a unified tester charm would make life easier...):

| if not self.unit.is_leader():
   self.unit.status = BlockedStatus("no leadership")
   return

ingress = IngressPerUnitRequirer(charm=self)
model: Model = self.model
ipu_relations = model.relations.get("ingress-per-unit")

if ipu_relations:
   ipu_relation = ipu_relations[0]
   ingress.provide_ingress_requirements(host="0.0.0.0", port=80)

   if ingress.is_ready(ipu_relation):
       self.unit.status = ActiveStatus("all good!")
   else:
       self.unit.status = WaitingStatus("ipu not ready yet")
else:
   self.unit.status = BlockedStatus("ipu not related")
 |
| :---- |

### Multi-stage relation back-and-forth: how that could be done

Granted, there are cases where this simplification of the flow a tester charm has to go through will be too restrictive, but it is possible to write testers for multi-stage relations (provided the back-and-forth does not branch too much) like so:

| @Tester(MyRelationProvider, 'provides')
def test_provider(self, framework, key) -> Status:
   provider = MyRelationProvider(self, ...)

   # if we don't have a MyRelation yet:
   if not provider.relation:
       return WaitingStatus('awaiting relation')
   # if the relation is alive but the data doesn't look good
   elif not provider.remote_has_sent_handshake:
       return BlockedStatus('no handshake yet')
   else:
       provider.reply_to_handshake('yes')

   if not provider.remote_has_sent_data:
       return BlockedStatus('no data yet')
   else:
       provider.send_data_back('other_data')

   if not provider.remote_has_provided_access_to_resource:
       return BlockedStatus('no access yet')

   # ... more stages?

   else:
       mock_data = {'foo': 'bar'}
       provider.reply(mock_data)
       return ActiveStatus('all good!')

@pytest.fixture
def provider_tester_charm(): ... # generated by charmcraft tester generate-fixtures

def test_integration_requirer(provider_tester_charm, requirer_charm, ops_test):
   # deploy the two apps
   await ops_test.deploy(provider_tester_charm)
   await ops_test.deploy(requirer_charm)

   assert await ops_test.get_app(provider_app_name).status_type is WaitingStatus

   # relate the two apps
   await ops_test.relate(provider_app_name, endpoint_1, requirer_app_name, endpoint_2)

   # eventually it reaches active
   await ops_test.get_app(provider_app_name).status_type is ActiveStatus |
| :---- |

## Further Information

This code might, if not together with the library code (which seems logical), live in [https://github.com/canonical/charm-relation-interfaces](https://github.com/canonical/charm-relation-interfaces). It could be part of the spec of the relation itself.
It feels that the 'tester' folders present in that repo, moreover, were conceived with a similar goal in mind. Let's agree on which way to go :)

Kind of situations this spec might help address
[DA009 - K8s Integration test charm](https://docs.google.com/document/d/1KWvtfcr4pJpbMaLc_rGMkrKf-dS7jMtPWmC68d3e2as/edit)

### Mitigation

If this is too much work, we could fall back on a `charmcraft init -minimal` which contains a 'tester' template only including the bare minimum to create these dummy charms. We could do this anyway, also.
