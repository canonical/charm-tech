# OP048 — Pebble $VAR-style interpolation in layer configuration

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Implementation |
| Created | 2024-08-06 |

## Abstract

Pebble layer configuration supports defining environment variables that should be set when running a service's command. These are defined as a mapping of key-value pairs:

```
environment:
  FOO: <some value>
  BAR: <some value>
  ...
```

We want to implement a feature where `${VAR}`-style environment variable interpolation is supported in the layer configuration.

An informal example:

```
environment:
  FOO: <some value>
  BAR: <some value>
  BAZ: ${HOME}        # BAZ becomes value of user's HOME
  QUX: ${FOO}/${BAR}  # BAR becomes value of FOO + "/" + BAR
  ...
```

## Rationale

With environment variable interpolation, referring to current environment variables in the layer configuration is easier. With environment variables referring to each other, copy-and-pasted duplicated values are reduced in the configuration.

This will close [issue 182](https://github.com/canonical/pebble/issues/182).

## Specification

Use `${VAR}` (`$VAR` will not be supported) in an environment variable value in the layer configuration. This will also affect `services.<name>.environment` and `checks.<name>.exec.environment`.

Example:

```
services:
  svc:
    override: replace
    command: sleep 1000
    environment:
      THINGDIR: /home/${USER}/thing
      CMD_DIR: /root/sleepy
      CMD_SOCKET: ${CMD_DIR}/.sock
```

Explanations:

- Variables can refer to each other. In the example above, `CMD_SOCKET` will be rendered with the value of `CMD_DIR` defined in the `environment` section.
- If a variable is not defined in the `environment` section, the value will be fetched from the current environment variables. In the example above, `${USER}` is fetched from the current environment variables (that of the `pebble run` process).
- The value will be an empty string if a variable is not defined in the environment list here or in the user's environment. Users need to make sure the referred env var is set.
- The order does not matter. In the example above, even if `CMD_DIR` is defined after `CMD_SOCKET` which refers to it, `CMD_SOCKET` will still be rendered with the value of `CMD_DIR.`
- If a circular reference is detected, an error will be returned.

Based on incomplete research on 28 randomly selected charms (see the list below), there are a few cases where the `$` literal could appear in the environment:

- password/secrets:
  - database
  - JWT secret
  - OpenSearch
  - token for other services
  - webhook secret
  - etc.
- cookies
- public/private keys

Although it's not "highly" likely, there still is a chance that the password/secret/keys might contain `$` or even `${...}`. For maximum backwards compatibility, the `${VAR}` syntax is chosen, `$VAR` won't be supported.

If the user needs to pass a literal `$` as the value, it needs to be escaped as `$$`.

Researched charms:

- alertmanager-k8s-operator
- ams
- anbox-cloud-dashboard
- atlantis-operator
- candid
- charmcraft init-simple templates
- discourse-k8s-operator
- juju-dashboard-charm
- kafka-k8s-operator
- katib-operators
- kfp-operators
- kratos-operator
- kubeflow-profiles-operator
- kubeflow-volumes-operator
- mysql-router-k8s-operator
- netbox
- penpot-operator
- ranger-k8s-operator
- redis-k8s-operator
- redis-operator
- sdcore-nssf-k8s-operator
- sdcore-pcf-k8s-operator
- sdcore-udr-k8s-operator
- sdcore-webui-k8s-operator
- synapse-operator
- temporal-k8s-operator
- ubuntu-metrics-k8s-operator
- ubuntu-repository-metadata-operator

## Further Information

* [Proof-of-concept code](https://github.com/IronCore864/yaml-config-env-interpolation)
* Jira issue: [https://warthogs.atlassian.net/browse/CHARMTECH-195](https://warthogs.atlassian.net/browse/CHARMTECH-195)

## Meeting Minutes

2024-08-06:
Discussions and initial decisions:

1. Only support `${VAR}` style, not `$VAR` style.
2. Use `$$` to mean literal `$`.
3. Order is not significant, use topology sort.
4. Only allow `${VAR}` to reference other variables defined in layers, not in the parent environment. This item is debatable because the main idea of this spec is to support this. For example, [here's a charm using this feature](https://github.com/canonical/alertmanager-k8s-operator/blob/0e635746ee2f14fd75fd3a8f0d7029ffea553de4/src/alertmanager.py#L196.). Some incomplete research is done based on the 20+ charms above and most layers/services/environments don't get values from env var, they get it from config. So, maybe it's OK to only allow `${VAR}` to reference other variables defined in layers, not in the parent environment, but again, in that way, this spec becomes "allowing users to refer to variables defined in other layers", which creates more problems (like flatten and merge and topology sort) than it resolves" and it's not a particularly useful feature.
5. Layers flattening first and then interpolating? We are not 100% sure about this.

The doc has been updated to reflect points 1, 2, and 3.
