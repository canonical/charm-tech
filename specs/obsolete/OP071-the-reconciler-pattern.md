# OP071 — The reconciler pattern

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Informational |
| Created | 4 Jul 2025 |

## Abstract

This documents records the best practice from the teams whose charms follow the reconciler pattern.

There's already [Holistic vs delta charms - The ops library documentation](https://ops.readthedocs.io/en/latest/explanation/holistic-vs-delta-charms.html)

The reconciler pattern takes it a few steps further:

| What \\ Charm type | Delta | Holistic | Reconciler |
| :---- | :---- | :---- | :---- |
| Observed Juju events | Individual events | Groups of named events | All events |
| Observed custom events | Individual events | Groups of named events | None |
| Charm code | Distributed across handlers | A single handler | A single handler |
| Workload control | In specific handlers | In the single handler | Unconditional |
| Charm library configuration | Ad hoc (?) | In init | In init |
| Passing data to charm libraries | In specific handlers | In the single handler | In the single handler |
| Data from charm libraries | From the custom event Reading properties | From custom events Reading properties | Reading properties |
|  |  |  |  |

## Rationale

Reasons why the specification should be accepted. It should explain why the existing state, if any, is inadequate to address the issue being handled. If possible, use cases should be included to help define and explain the goal.

Omit that section (rather than presenting silly reasoning) if there's no good motivation for the specification, or if it is completely obvious. Note that lack of motivation is a good reason to reject specifications.

## Specification

The specification should describe in detail the issue being addressed, and the proposed way to handle it, covering the areas involving the issue, and allow implementing the feature. It should *NOT* be an extensive "whitepaper" that is supposed to make sense even to someone not aware of the major context the issue is part of.

Use of subtopics is encouraged to structure the specification. This section could include diagrams, code samples (formatted using the code blocks addon), pseudo-code, tables, etc.

Open issues should be stated, and solved before the specification is approved.

Aim to keep the spec as brief as possible while getting the point across. There is no minimum length for a spec.

## Further Information

That section, if present, may describe why particular design decisions were made, alternate designs that were considered, and related work (e.g. how the issue is handled in other systems).

May also include links to other (related) specs, links to version control repos, links to Jira items spawned as a consequence or requirement of the specification or external information.
