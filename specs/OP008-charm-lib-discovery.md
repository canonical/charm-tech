# OP008 — Charm lib discovery

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2021-09-16 |

## Abstract

Implement better discoverability of charm libs.

## Rational

In several discussions in the charmers feedback session, it would have been useful to point folks to a known good collection of charm library examples. Right now, to the best of my knowledge, one simply needs to "know" which charms have libraries, and which libraries might be good.

## Existing libraries

Right now, our list of charms actually using libraries is fairly sparse. Here is (I believe), the complete list of charms, followed by their libraries:

### `nginx-ingress-integrator:`

### `- ingress`

### `mongodb-k8s:`

### `- mongodb`

### `prometheus-k8s:`

### `- prometheus`

### `alertmanager-k8s:`

### `- alertmanager_dispatch`

### `grafana-k8s:`

### `- grafana_dashboard`

### `- grafana_source`

### `cassandra-k8s:`

### `- cassandra`

### `redis-k8s:`

### `- redis`

(Note that this list was compiled with a fairly naive/lazy invocation of juju find, so I may not have found every charm in the index that uses libraries.)

## Specification

We will be "done done" on this when two or three of the following artifacts have been created:

1) A discourse post highlighting some "known excellent" charm libraries. This can be updated over time.
2) A section in the docs linking to examples. (Can we duplicate the discourse post here?)
3) An index in CharmHub listing libraries.

The implementation of this last can get rather complex. We probably need to focus on an MVP first, and possibly enhance later with a "highlighted libraries" section in the store.
