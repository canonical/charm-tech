# OP013 — Add networking data to harness

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2021-12-06 |

## Problem statement

Charm authors currently don't have a standardized, centralized way to get dummy network data out of the harness.

## Reference

- [Current juju networking docs](https://discourse.charmhub.io/t/charm-network-primitives/1126)
- [The OF Network class](https://github.com/canonical/operator/blob/main/ops/model.py#L563)

## Current State of the world

Right now, the testing harness provides no mock data to populate model.Network, and charm authors need to mock the data themselves.

Examples:

- [prometheus networking tests](https://github.com/canonical/prometheus-k8s-operator/blob/main/tests/unit/test_charm.py#L28)
- The observability charms use a [patch_network_get wrapper](https://github.com/canonical/alertmanager-k8s-operator/blob/ce6325635bde4614f9032e3683e597ab7e6e50ff/tests/unit/helpers.py#L11) to set bind_address.

In production, the Operator Framework calls out to Juju's network-get routine, which takes a binding name as an argument, and returns data like the following:

```` ``` ````
`bind-addresses:`
`- macaddress: ""`
  `interfacename: ""`
  `addresses:`
  `- address: 10.136.107.33`
    `cidr: ""`
`ingress-addresses:`
`- 10.136.107.33`
```` ``` ````

This is mapped into a `Network` object in Python. The Network object stores lists of `NetworkInterface`, `ipaddress.ip_address` and `ipaddress.ip_network` objects. Charm authors don't access this object directly, however. Instead, they call Model.get_binding(<name>).network.

The return method from .network is a dict w/ a structure that reflects that initial call to network get. E.g., a charm author could get at the ip of the bind address in the example above by looking at <network get dict>['bind-addresses']['addresses'][0]['address']

## Proposed Solution

A charm author needs to be able to do the following:

1) Pass a known good binding name to get_binding, and get some useful dummy data out.
2) Get an appropriate error message if the binding doesn't or shouldn't exist.
3) Be able to populate the data themselves, if desired.

#### Deriving bindings

At instantiation, the test harness should inspect the test metadata.yaml, and derive a deduplicated list of valid "bindings" from it. Bindings can be obtained by inspecting the keys in the `requires`, `provides` and `peers` entries of the metadata.

See: [https://github.com/juju-solutions/charm-mysql/blob/master/metadata.yaml](https://github.com/juju-solutions/charm-mysql/blob/master/metadata.yaml)

#### Populating bindings with test data

Like the other methods that exist in the Operator Framework, but not in the testing harness (ops.testing._TestingModelBackend), TestingModelBackend.network_get will raise a NotImplemented error if called.

We need to define `network_get` in the harness, and have it return good test data. We probably want to take the same approach that we did to planned units, where we auto generate by default, but allow user override. Specifically:

1) By default, a call to network_get will automatically generate dummy ip addresses and return them. This allows charm authors to test just the code that uses network_get, without having to worry about setup.
2) We should also provide a set_network_get routine, which will set network info for a given binding. If this routine is invoked, the automagic should be turned off! The set bindings can be saved in the _TestingModelBackend instance as ._network_get_data
