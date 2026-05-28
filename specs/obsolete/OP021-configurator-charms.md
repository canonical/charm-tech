# OP021 — Configurator charms

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-07-21 |

## Abstract

This proposal is about solidifying a charm-writing pattern, and determining whether any additional plumbing on our side is necessary to facilitate it. The pattern is that of the configurator charm; where we have one core charm that contains the operator knowledge, and one or more configurator charms that relate to it and configure a single functionality group each.

## Rationale

Charms should be simple. But production-ready charms typically end up having lots of configuration options and knobs to turn. This complexifies charm design.

## Specification

We could consider a pattern where instead of a charm you have a bundle; one core charm and then several configurator charms around it, which take care of configuring the core charm (each configurator charm would represent one (optional) functionality group).

- How would a configurator charm look like?
- Is the burden on the user acceptable?
- Would the flow be
  - Juju deploy foo
  - Juju deploy foo-func-bar
  - Juju config foo-func-bar bar-specific-config=baz
- Is the purpose of the configurator charm just to wrap a chunk of the config, or also a chunk of the functionality? I.e. look at `traefik-route`, where the charm handles some logic as well.

- How would WE help make it happen, if this were a good idea?
  - Do we need a new charmcraft init profile?
  - A ConfiguratorInterface class to wrap this type of endpoints, which you can grab to do e.g. `self.config_interface_foo['config-key']` (config is exchanged via relation data.
