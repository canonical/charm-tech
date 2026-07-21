# OP028 — State-transition and functional testing framework for charms

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2022-09-28 |

## Abstract

This spec outlines certain limitations of the current Operator Framework charm unit-testing framework (the ops.testing Harness), proposing a new unit testing framework called Scenario.

## Rationale

#### Charm execution state isolation

Each harness instance creates one charm instance, then allows the user to simulate certain events, which all get fired on the same charm instance. There is no way at the moment to 'reinitialize' the charm.
This leads to problems when, e.g.:

-  The charm has some logic in its __init__, e.g. if it only initializes a certain lib if a certain config value is set, or passes down to a lib's init some current config value or current a current relation instance, or conditionally listens to certain events, et cetera.
- sometimes charm or library logic observe the `framework.on.commit` event, which the harness never fires.
- charm code mistakenly attaches state to the instance ('self'). Since the harness charm instance remains the same, the code would work locally but break in integration testing.

[See this bug report for more context.](https://github.com/canonical/operator/issues/736)

Two separate attempts have been made at adding logic to the instance to allow reinitializing the charm in the harness:

- [This one](https://github.com/canonical/operator/pull/758) (rejected)
- [This other one](https://github.com/canonical/operator/pull/835) (still open, stale)

While solving this problem would take care of some of the issues with Harness (__init__ logic, attaching state to instance attributes), it does not solve all of them.

#### Charm execution context transparency

The harness, as it stands, seems to cater to two distinct needs:

- Simulate the context within which the charm itself runs: what relations are available, whether the unit has leadership, etc... In short, it allows mocking the answer to the question: "if the charm at this point were to run this hook tool/make this pebble call, what would the answer be?"
- Trigger charm execution when this context changes, simulating the way that juju would do it. For example, when leadership changes, run the charm with a 'leader-settings-changed' or `leader-elected` event, or if a remote unit is added and sets some relation data, fire the appropriate events, etc... In short, it allows mocking the answer to the question: "if [this or that] happened in the juju model, how would the charm be executed?" For example: "if that relation was removed, what codepath would the charm take?"

We believe that this duplicity is the root cause of some of the shortcomings of the harness, and that both needs would better be served by a thin layer on top of the harness that would take care of the context (and use the harness as a backend for setting it up, since the harness already has the functionality).

The harness would no longer be responsible for initializing the charm, holding on to the charm instance, or choosing which events to fire, when, and with what arguments.

Writing unittests with the harness, as it stands, misrepresents how a 'live' charm runtime will behave. Our test code should better reflect the isolation of charm runs (this event is fired) and the accompanying context (this is the context that event occurs with).

**We believe it is easier to understand a "charm bug" as a failure to map an initial state to a new (valid!) state, instead of a failure to digest a certain event sequence**. Instead of testing a charm by 'firing a sequence of events on it, and in between changing the context', we believe it will be easier to think about the charm's runtime in this way. And therefore, easier to write good tests for a charm as 'for each event: set up the context in which the event occurs; then fire the event'.

To achieve this, we need something more than Harness.

### Charm state

With Harness, it is hard to keep track of what the state of a charm is at any given moment, because you incrementally mutate it to get it to a certain point.
With Harness, you procedurally call methods thereby driving the charm to a given state, but it is hard to get a full picture of what, at any point, the state looks like.

As a consequence, it is reasonably easy to assert that a piece of state is the way you want it to be, but very hard to check that some unexpected piece of state did NOT change. That is, it is hard to obtain a delta of the charm's state before and after an event.

## Proposal

We propose a new testing framework encouraging a stricter subdivision of each test in three sections:

- Arrange: set up a situation
- Act: trigger a charm execution with some event as context
- Assert: that the charm handles that situation (in that context) correctly.

Compare this with the pattern most Harness tests follow: do a bit of set-up (which triggers an event); assert; do the next bit of set-up (triggering one more event), and so on *ad infinitum*. Harness has facilities to 'block' event emission during specific parts of the set-up, but in most cases each intermediate state is also supposed to be consistent, so there's little value added in remembering not to emit events that you are actually not testing for, so in practice very few tests do so.

We propose to add to the ops testing toolbox two new primitives, more closely matching what is 'really' going on when a live, deployed charm is being called by the juju unit.

When a charm is executed, a static part of its execution context is provided by **environment variables**. This includes information such as the name of the unit the charm is on, the juju API address, the name of the event that is being dispatched by juju, parameters of that event, etc... This data we propose to represent in a data structure called **Event**.

Another, somewhat more dynamic (and lazily fetched) part of the charm execution context is exposed by the **hook tools**. These wrap Juju API calls and expose data about the charm's leadership status, relation databag contents, etc... This data we encapsulate in a data structure called **State**.

Summing up, the two new key concepts and first-class citizens of scenario tests are:

- An **Event**: the execution context of the charm; answers the question: why am I being run by juju?
- A **State** object: answers the question: if I ran <this hook tool/this pebble call>, what would I get back?

The mental model of a charm scenario tests promote is that of an input-output black-box state machine. Scene A = (Event A + State A) goes in, the charm does something, State B comes out. The user can check that State B is 'valid', i.e. how they expect it to be.

Compare this with the Harness model, where the user instantiates the harness, mutates it thereby triggering several events on the charm, running assertions in between.
Given the completeness of the State data structure, it's also trivial to check that **nothing else has changed**, something which is very difficult with Harness.

Instead of calling *Harness.begin_with_initial_hooks*, the user would define a sequence of independent scenes (events and their accompanying contexts), allowing for a much richer description of what the initial sequence looks like: you have leadership during start, but not install, you can connect to your container on *install* already, then you receive *pebble_ready* but can't connect, etc...

A scene is played inside a **Scenario**, that is a context responsible for keeping track of which scene is playing and assembling the results of the play.

The user would be given tools to compose their own scenarios, and we could consider adding a few built-in sequences (to play the role begin_with_initial_hooks used to play):

- Setup sequence (with leadership): *leader-setup*
- Setup sequence (without leadership): *follower-setup*
- Teardown sequence
- *More?*

The user would be able to specify their own sequences (and, as we will see below, share them with other charms and charmers!) and use them to unittest the charm, running assertions before/after each scene is played.

### Examples

With harness:

```py
def test_relation_set_harness():
    harness = Harness(MyCharm, meta="""
        name: mycharm
        requires:
          foo:
            interface: bar
        """)
    harness.begin()
    harness.set_leader()
    relation_id = harness.add_relation("foo", "remoteapp")
    harness.add_relation_unit(relation_id, "remoteapp/1")
    harness.add_relation_unit(relation_id, "remoteapp/4")

    harness.begin_with_initial_hooks()

    assert harness.get_relation_data(relation_id, "mycharm") == {"a": "b"}
    assert harness.get_relation_data(relation_id, "mycharm/0") == {"c": "d"}
```

With scenario:

```py
def test_relation_set_scenario(mycharm: Type[CharmBase]):
    scenario = Scenario(charm_spec=CharmSpec.from_charm(mycharm))
    scene = Scene(
        event("start"),
        state=State(
            leader=True,
            relations=[
                Relation(
                    endpoint="foo",
                    interface="bar",
                    remote_unit_ids=[1, 4],
                )
            ]
        ))

    out = scenario.play(scene)

    assert out.relations[0] == Relation(  # we can compare the data structures in their entirety - to ensure nothing else has changed.
                    endpoint="foo",
                    interface="bar",
                    remote_unit_ids=[1, 4],
                    local_app_data={"a": "b"}
                    local_unit_data={"c": "d"},
)
```

## Scenario as a language to express charm runtime states and other use cases.

There are other reasons why having a language to express event/context pairs is a promising direction.

### Portable tests

Suppose you write a relation charm lib. How can you help the users of your library to write tests to verify that their implementation of the consumer/provider can correctly interface with the other side of the relation?

What if you could serialize a Scenario, give it to the user, and then all the user would have to do is:

| scenario = Scenario.loads(source)
# configure the scenario to suit your charm, e.g.
#  provide required config,...
scenario.play(MyCharm) |
| :---- |

### Failure reproducibility

Suppose we add to ops.main an *atexit* exception hook which works such that, if an error occurs, it captures the Scene(Context, Event) pair and logs it somewhere. Instead of digging through a stack trace to figure out what codepath was taken that led to the error, one would be able to go and inspect the context and tell:

- Leader-get returned False.
- Can_connect returned True
- List_files returned this and that
- Config-get contained this and that
- ...
- Config_changed was fired.
- This error resulted.

This makes it easier to find out why something went wrong. Not to mention the fact that one could grab that Scene, fire it up in a Scenario, and reproduce the error locally within seconds! If the Context is complete, this should definitely be possible.

### Regression testing

An additional attractive use-case for such a serialized representation of a sequence of events (plus contexts) is **regression testing:** suppose you could record a live charm and keep track of the events it sees and the contexts it sees them in (what responses do hook tool calls get etc...). If the charm breaks, that Scenario (the part of it that led to the bug) can be used to reproduce the bug, and, once it's fixed, it can be added to a library of scenarios to be run as part of a regression testing suite.

In line with the insight above that charm testing should be about identifying the situations in which the charm code fails to map a valid state to another valid state (by "choosing the right operation to perform"), this also means that our regression testing code can be made very simple: each test would consist of a situation, and would check that the charm can handle it correctly.

It would greatly simplify testing to see the charm as an input/output function, and assert: given this input, is the output what we expect it to be?

### Better testing environment isolation

Finally, the Scenario-based testing paradigm offers the opportunity to achieve much stricter isolation of our testing runs. Using a fresh charm instance for each test helps catch bugs where the user attaches state to the charm by means of instance attributes, but what if the user were to use class attributes? We could extend the Scenario-based tests to run each scene in a container, getting our simulation one step closer to reality.


### Custom event testing

Suppose your charm listens to a charm-lib-emitted *'foo-baz'* custom event, triggered on *relation-changed* if the remote data is valid.
In Harness, to exercise that codepath, you would have two options:

* Set up all preconditions and finally emit a *relation-changed* (by doing harness.update_relation_data...). The charm lib will emit *foo-baz*, and the charm's handler will eventually be called.
* manually dig into the charm and emit it:
  *harness.charm.lib_object_hook.on.whatever_foo_baz.emit(...)*

With Scenario, you can trigger it as if it was any other event (as if it were a hook):

| State().trigger("foo_baz", MyCharm) |
| :---- |

## Open questions

### charm-specific context

Not all context is juju-owned. If the charm makes, say, an http call to some server somewhere, or calls a workload-specific api without going through pebble, we wouldn't be aware of that.
In other words, what counts as state for this charm - that is up for the charm itself to determine.
There are two options here:

- We say: that's external context, we won't capture that. If you choose to work around juju to get your charm state, you're on your own. You'll need to mock it yourself in tests, and if that is the thing that's breaking your charm, you will not get our help in fixing it.  That's what we're going for initially.
- We could offer an `@memo` decorator that users can wrap their 'external' calls with. That decorator will inform us that the return values of that function, at runtime, are what counts as state for this charm.

  *An interesting side-effect of this approach is that we'd be offering a more flexible way of charmers to declare what counts as state for this charm. You could wrap a complex function of what relations you have, whether you are leader, your config, etc... to some higher-level piece of data that your charm can consume to determine what to do, and present that as 'state' for debugging purposes.*

**Conclusion**: this needs to be explored in [a separate spec](https://docs.google.com/document/d/1G62PosrObvmQY5KbxvqaxByojlhDxrmNtcbPS39YbaY/edit).
