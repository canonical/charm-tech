# OP029 — Support for open-port / close-port (in Python Operator Framework)

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | Feb 7, 2023 |

## Abstract

We want to add an API in the Python Operator Framework (ops) to allow charmers to open and close ports, so that there's a Pythonic way for charmers to open and close ports, and charms don't have to resort to using `subprocess.run()` to manually call the `open-port` and `close-port` hook tools.

## Background

A charm can call the `open-port` hook tools to record intent that it wants to expose that port (or port range); later, when the admin runs `juju expose`, Juju actually updates the cloud configuration to make that port accessible. (Similar with `close-port` and `juju unexpose`.)

In Juju 3, we made `open-port` and `close-port` work for K8s sidecar charms, and in that case when `juju expose` is executed, Juju updates the K8s service definition to allow access. At the time of writing this spec, for K8s charms Juju only allowed `open-port` and `close-port` to work on the leader unit (whereas for VM charms these commands must be executed on each unit).

However, for consistency between K8s and machine charms, we'd like to update Juju to remove the is-leader check for open-port on K8s charms and instead open the *union* of ports requested in the K8s service definition. When `close-port` is called, Juju would only close the port on the service definition once all units said they wanted it closed. We've opened [LP2007334](https://bugs.launchpad.net/juju/+bug/2007334) to track that work in Juju.

In Juju 2.9, [we added an `--endpoints` option](https://discourse.charmhub.io/t/granular-control-of-application-expose-parameters-in-the-upcoming-2-9-juju-release/3597) to the `open-port` and `close-port` hook tools as well as `juju expose`, to allow you to only expose the port for a specific purpose (relation endpoint). However, this is now more or less considered a design mistake as it conflates relations with network traffic flows, and we've decided not to add that to the ops API for now to avoid propagating a less-than-ideal feature.

## Specification

We propose adding a new API for opening and closing ports and listing opened ports as methods on the `model.Unit` class.

```py
class Unit:
    def open_port(self,
                  protocol: Literal['tcp', 'udp', 'icmp'],
                  port: Optional[int] = None):
        """Open a port with the given protocol for this unit.

        On Kubernetes sidecar charms, the ports opened are not strictly
        per-unit: Juju will open the union of ports from all units.
        However, normally each unit will make the same open_port() call.

        Args:
            protocol: String representing the protocol; must be one of
                'tcp', 'udp', or 'icmp' (lowercase is recommended, but
                uppercase is also supported).
            port: The port to open. Required for TCP and UDP; not allowed
                for ICMP.
        """

    def close_port(self, ...):  # same args as open_port
   	 """Close a port with the given protocol for this unit."""

    def opened_ports(self) -> Set[OpenedPort]:
        """Return a list of opened ports for this unit."""

@dataclasses.dataclass(frozen=True)
class OpenedPort:
    protocol: Literal['tcp', 'udp', 'icmp']
    port: Optional[int]  # None if protocol is 'icmp'

# Example usage in a charm
class MyCharm(CharmBase):
    def _on_install(self, event):
        self.unit.open_port('tcp', 3306)
        self.unit.open_port('tcp', 4000)
        self.unit.open_port('icmp')
```

## Previous discussion

We previously proposes two sets of port APIs, one on Application and one on Unit, to handle the application case (for K8s) and the per-unit case (for machine charms). We also supported port ranges and the "endpoints" functionality. However, after discussion with Gustavo, Jon, and Ian (15 Feb 2023), we decided to simplify as follows - for simplicity, but also so that K8s and machine charms can use the same API (better for "universal charms").

* Only add the Unit methods for now (open_port, close_port, opened_ports), not the Application ones, and make them work for K8s and machine charms. Both types of charms will call Unit.open_port() without an is-leader check. This will involve changes on the Juju side:
  * For K8s charms, remove the Juju is-leader check, and make Juju update the service definition to open the *union* of all ports requested. When close-port is called, Juju would only update the service definition to close the port when all units have asked for it to be closed. This is a fairly good experience on both charm types.
  * For machine charms, no Juju changes are required.
  * Later on, we could consider adding Application.open_port() and what that means for both types of charms, but we won't do that this cycle.
* Remove port ranges. These are rare, and don't work on K8s anyway - so simplify and be consistent.
* Remove "endpoints". The "endpoints" feature was probably a design mistake (conflating relations with network traffic flows) and we don't want to propagate a bad design.
* If people *really* need port ranges or endpoints, they can continue to shell out and call the open-port hook tool manually.

Also: allow both lowercase and uppercase protocol ( 'TCP' or 'tcp'), but guide people to 'TCP' uppercase in the type annotation.

## Open questions

* Ryan Barry's idea for an [open-port event](https://github.com/canonical/operator/issues/179#issuecomment-1420488689).
  * If user opens port (using hook tool) from Juju CLI, charm has no way to know.

## Additional Information

* The [`open-port` functionality](https://github.com/juju/charm-helpers/blob/7d443d8a628763414455838ca28fd8beeea03005/charmhelpers/core/hookenv.py#L830) in the charm-helpers library.
* [Work-in-progress implementation in ops.](https://github.com/canonical/operator/pull/905)

## History

| Date | Status | Author(s) | Comment |
| :---- | :---- | :---- | :---- |
| 2023-02-15 |   | Ben Hoyt | Revised after spec discussion with Gustavo, Jon S, and Ian. |
| 2023-02-09 | Revisions | Ben Hoyt | Revised API after discussion with John M. |
| 2023-02-08 | Initial spec | Ben Hoyt |  |
| Aug 31, 2023 | Completed | Ben Hoyt | Implemented and shipped in https://github.com/canonical/operator/pull/905 |
