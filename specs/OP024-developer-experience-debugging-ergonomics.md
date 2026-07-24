# OP024 — Developer experience & debugging ergonomics.

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Standard |
| Created | 2022-08-08 |

## Abstract @an

At the moment, Juju + OF do not offer an integrated development experience. When writing a charm, one often starts from a template, then writes tests with Harness + python-libjuju (or zaza), then releases/deploys. Should bugs arise, attempts to reproduce and recreate the scenario in unit or integration, fix it, and repeat.

Many juju constructs are opaque when looked at from the charm developer's perspective. Specifically, the most exotic/juju-specific concepts are the ones that new developers often need extra guidance with, particularly relations and the event model.
This spec proposes tooling which could aid the development and debugging of charms.

## Rationale

#### Issues with the present state of development/debugging of relations.

##### Inspecting the contents of formed relations is hard

Given a model with two related units, in order to gain a full picture of the databags involved in the relation, I presently have to run `juju show-unit A` and `juju show-unit B`, and I have to understand that the databag contents returned by `show-unit A` match the databags owned by B, as seen by A, and not A's own databags. To see A's databags, I have to run `show-unit B`.

##### Proposal

To address this issue, we propose a new tool that displays side-by-side the databag contents for two related units (or multiple units of two related applications). This should ideally have the ability to update live, similar to the `watch` command.

A prototype lives at https://github.com/PietroPasotti/jhack#show-relation

##### It is hard to see what went wrong / inspect the history of a relation

Unless both charms, at each event, logged a complete snapshot of a relation's databags, it is impossible to check what the state of a relation was at a given point in time (say, BEFORE the last event was processed, or BEFORE this remote unit joined the relation).

##### Proposal

To address this issue, we need to develop infrastructure that records snapshots of the state of all units at predictable points in time, presumably before and after an event is processed.

A prototype is being developed; see [OP025](https://docs.google.com/document/u/0/d/1gp18VX9HmZDjSImSsQI55nC_lDFeH7cijKkbJ8CB2QY/edit) for the spec.

###### Limitations

The current proposal's main limitation stems from it being implemented downstream of Ops instead of in juju. Ops does not know what happened in juju, it only 'sees' the resulting event sequences. We can only guess, if we see `relation-departed`, whether the user scaled down an app, removed it altogether, or simply removed the relation. We can probably make the guess fine enough, but it would be much easier if this recording functionality were implemented in juju.
Juju has the full picture

- User does X
- Unit A sees changes 1, 2, 3
- Unit A fires event e
- Unit B sees changes 1, 2, 3
- Unit B fires event f
- ...

The 'user does X' part is what Ops has limited introspection about. Therefore this functionality is best moved over to juju when the spec is mature enough. See the relative spec for a more detailed discussion.

##### It is hard to reproduce in tests what went wrong

Suppose I could use the `record` infrastructure discussed in the previous point to see exactly what sequence of events/remote relation data updates caused my charm to break. In order to test for this sequence and prevent regressions, I'd have to manually code this sequence in a unit or integration test suite. This is impractical and difficult to do.

##### Proposal

To address this issue, we could develop infrastructure, given the `records` we discussed above, can `replay` them  in a unit or integration test suite.
The user experience would look like:

- `juju record my-charm |> repro.log`
- Take any action necessary to reproduce the bug (config change, add remote unit, scale up/down, ...)
- Adding an integration test to catch regressions could be as simple as:

| await ops_test.replay('./path/to/repro.log') |
| :---- |

#### Issues with the present state of development/debugging of events.

##### It is hard to visualize the sequence of events fired on one/more units, how they interleave, and their deferral status.

At the moment, all we have for this is the `juju debug-log`.
Especially beginners have a hard time figuring out the timing of event sequences, and how they compose when multiple units are considered. Deferrals are even more complicated to understand, and it is hard to identify perpetual deferral loops from the debug-log.

##### Proposal

We propose to develop a tool to tail events being fired on one or multiple units, visualizing their timestamps, and if applicable, their deferral status.

A prototype lives at https://github.com/PietroPasotti/jhack#tail

##### It is hard to know the payload/context of events.

At the moment, unless our charm logs this information manually, it is impossible to know WHICH remote unit left when we see a `*-relation-departed` event - and possibly even which remote application this applies to.

##### Proposal

As part of the `record` functionality mentioned above, the serialized representation of the current event should include any and all context of the event. In most cases, including the content of `event.snapshot()` should suffice.

##### It is hard to reproduce (in tests) what went wrong

Suppose I see that the charm raises an error on a very specific `relation-joined` event. The only way to reproduce the error is to create a new model, redeploy all charms, relate, wait.
There is currently no way to

1) Simply re-fire the event as-it-was. Either I intercept the event with `juju debug-hooks`, at which point I can 'fire' it at will (but only the first execution will have access to a 'clean/original' starting state)
2) Easily reproduce the sequence of user actions/events that led to this problem/situation.

##### Proposal

The second point is closely related to the `record/replay' functionality discussed above with relations in mind.
The first point requires an apart solution. We propose to add a `simulate-event` tool that, given a recorded event data structure (as output from the `record` tool), is able to trigger a charm execution and drop the developer in a similar environment as they'd get from running `debug-hooks`. This entails that the `record` tool should also snapshot the environment variables set by juju. It remains to be determined if this is possible at all (we're currently investigating whether some envvars are somehow single-use, or whether executing a charm in this way would cause irreversible desync in juju's model).

###### Limitations

The current proposal's main limitation stems from it being implemented downstream of Ops instead of in juju. We are attempting to run an event independent of juju, which is not what juju was meant to allow. If this tool were to be built into juju, we could request the agent to fire a certain event (run the charm **right now** with a few overridden envvars, namely) and that would be it.

#### Issues during charm development

##### The Ops API is not programmatically discoverable while coding

By that we mean that, if a newcomer were to `import ops` in an interactive REPL (say, ipython) or a new charm file and simply start hacking around (relying on docstring, autocomplete, etc...) he wouldn't get very far.
Two main reasons:

- Lack of typing.
- Many constructs are dynamic (such as a charm's `config`, and a charm's `on` events, which means only the runtime env has knowledge about what it contains.

##### Proposal

Firstly, we propose to type the whole of `ops`. (Done!) This means that when coding (from most modern IDEs) the user will get code completion, inline hints and docs.

Secondly, we propose to restructure the way charm metadata is defined. This is described in [another spec](https://docs.google.com/document/u/0/d/1j0l5AKKE6KBpKxNAJ-zqzZGMZjIBn8JnAURo18QZB3U/edit). For a POC implementation and a closer look at what this could look like: see [jinxes](https://github.com/PietroPasotti/jinx).

#### Issues during live charm testing/development

##### It is hard to update a line of code and rapidly see the changes in a deployed charm

Suppose you deploy a charm you're developing that has a simple typo or some non-juju-lifecycle-related bug. If you want to fix it, at the moment you need to:
Edit the charm locally. Charmcraft pack. Redeploy/refresh.

##### Proposal

We propose to add a `sync` command that automatically watches a folder or a list of files for changes, and juju scp's any diff to a live charm.
A POC lives in [jhack sync](https://github.com/PietroPasotti/jhack#sync).

###### Limitations

This might work for simple scenarios where a `juju resolve` is enough to trigger a retry - where the charm, before breaking, did not have a chance to alter any state yet. If the state has changed already, then this approach will not work. The documentation needs to be clear on this.
If we had the `record/replay` functionality above, we could simply ask juju to roll back the state to before the event that broke the charm was fired, then resume the flow from there, with the updated charm code. Then all problems would be solved.

#### The bigger picture - offering an integrated development environment.

By observing the development environment/process of several charmers during pair-programming sessions, we observed that:

- Most people use a console pane at a time, switching between windows to run different commands
- Not many people use `juju status`/`juju models` on a watch.

Of course personal preferences here differ, and we don't want to force everyone to use a static, fixed environment, but especially for newcomers, I think it would be valuable to have a default setup consisting of:


- one terminal to run commands
- One terminal displaying juju status -relations
- One terminal with `juju debug-log`

  Personally I also always have:

- One terminal with `juju models` on a watch
- One terminal with `jhack tail`
- One terminal with `jhack show-relation` whenever I am working on relations.

We believe there's value to be gained from offering an interactive representation of a model, one resembling juju status but, additionally to that: keyboard shortcuts to:

- add / remove an app/unit from the debug-log (D)
- Add / remove an app/unit from jhack tail (T)
- Mark a relation to visualize with show-relation (R)
- Remove an application (Del)
- Scale up/down an app (ctrl+/ctrl-)
- Relate/unrelate two endpoints (Start/Del)
- Start a debug-code/debug-hooks session (Ctrl-K, Ctrl-H)

This could be terminal-based (to allow remote dev/debugging), or we could offer and develop a (say) pycharm plugin to make this all easy.

## Roadmap

-  ~~[It is hard to see at a glance what the contents of related units' databags are](#inspecting-the-contents-of-formed-relations-is-hard)~~
- [ ] [It is hard to see what went wrong / inspect the history of a relation](#it-is-hard-to-see-what-went-wrong-/-inspect-the-history-of-a-relation)
- [ ] [It is hard to reproduce in tests what went wrong](#it-is-hard-to-reproduce-in-tests-what-went-wrong)
-  ~~[It is hard to visualize the sequence of events fired on one/more units, how they interleave, and their deferral status.](#it-is-hard-to-visualize-the-sequence-of-events-fired-on-one/more-units,-how-they-interleave,-and-their-deferral-status.)~~
- [ ] [It is hard to know the payload/context of events.](#it-is-hard-to-know-the-payload/context-of-events.)
- [ ] [It is hard to reproduce (in tests) what went wrong](#it-is-hard-to-reproduce-(in-tests)-what-went-wrong)
- [ ] [The Ops API is not programmatically discoverable while coding](#the-ops-api-is-not-programmatically-discoverable-while-coding)
      -  ~~Typing ops~~
      - [ ] jinxes
- [ ] [It is hard to update a line of code and rapidly see the changes in a deployed charm](#it-is-hard-to-update-a-line-of-code-and-rapidly-see-the-changes-in-a-deployed-charm)
- [ ] [The bigger picture - offering an integrated development environment.](#the-bigger-picture---offering-an-integrated-development-environment.)

## Further Information

#
