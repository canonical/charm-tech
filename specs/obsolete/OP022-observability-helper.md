# OP022 — Observability helper

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-07-21 |

## Abstract

This spec proposes to add to `ops` a helper function to ease integrating observability into a charm.

Goals:

- make it easier to set up COS integration in a charm
- Keep a charm's init and namespace clean of observability-related code and data

Risks:

- Will this make `ops` less general, too specific, tie it to a specific stack, force us to maintain more code as that stack independently evolves?

## Rationale

Observability is essential to production-ready charms.
At the moment, if one wants to add observability to a charm and integrate with the COS lite stack, there are a few repetitive steps to be taken.
[The boilerplate isn't much in terms of lines of code. However, it feels like most of it is easy to abstract away so, why not?]
The current pattern encourages the user to, on charm init, instantiate the providers/requirers for the observability endpoints and store them in the `self` namespace. However, in most cases, these objects are not accessed elsewhere from charm code and only help polluting it. The main role of these objects is to register observers and run event-bound logic when applicable.

## Specification

We propose to add to ops a /ops/helpers.py file where we could also add in the future similar functionality groups-related helpers.
At the moment in the file there would be:

- Add_grafana
- Add_loki
- Add_prometheus
- Add_observability

The main role of add_* is to

1) Check that the required charm lib is installed (useful in unittests)
2) Check that metadata.yaml has the required endpoint (useful in unittests)
3) Initialize the appropriate endpoint wrapper (imported from the charm lib) like one normally would in a charm's init.

Add_observability is a higher-level wrapper that calls the three others, as typically one wants to use a combination of loki, grafana and prometheus.

## Examples

| # suppose only loki_k8s.v0.loki_push_api is present in /lib/charms
class MyCharm(CharmBase):
    META = {"requires": {"logging-loki-foo": {'endpoint': 'loki_push_api'}}}

    def __init__(self, ...):
        add_loki(self, loki='loki_endpoint') |
| :---- |

| # suppose all charm libs are fetched
class MyCharm(CharmBase):
   META = {
        "requires": {             "logging-loki-foo": {'endpoint': 'loki_push_api'}             },
        "provides": {
            "grafana_dash": {'endpoint': 'grafana_dashboard'},
            "metrics-endpoint": {'endpoint': 'prometheus_scrape'}
           }
        }

    def __init__(self, ...):
        add_observability(self,
                          grafana={'relation name':'grafana_dash'},
                          loki={'relation name':'logging-loki-foo', 'log_files': ['/path/to/file.log']},
                          prometheus={
                              'relation name': "metrics-endpoint",
                              'jobs': [{"static_configs": [
                                  {"targets": ["*:4080"]}]}]}) |
| :---- |

## Status

Simple POC implementation: [https://pastebin.canonical.com/p/whpDY3p6xG/](https://pastebin.canonical.com/p/whpDY3p6xG/)
