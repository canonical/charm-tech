# OP060 — Canonical donating to smaller open source projects we use

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Process |
| Created | 2025-02-25 |

## Abstract

This spec proposes a way for Canonical to contribute back financially to some of the smaller open source projects we use heavily.

## Rationale

Canonical creates a huge amount of open source software; we also contribute financially to some larger open source organisations such as Mozilla. However, we haven't had a systematic way of giving back to smaller open source projects that we use. Such projects are often overlooked and underfunded. Canonical could increase goodwill with the open source community by donating to these projects - as well as [encourage maintenance](https://xkcd.com/2347/) of them and reduce our [risk](https://research.swtch.com/deps).

Some smaller open source projects are used heavily by Canonical, for example [coverage.py](http://coverage.py) (used by most charms and many of our other Python projects), [flask](https://flask.palletsprojects.com/) (used by several of our web projects), [go-sqlite](https://github.com/mattn/go-sqlite3) (a key component of some of our Go projects), [tokio-rs](https://tokio.rs/) (used heavily in the Rust ecosystem), and hundreds of others.

We get a lot of value from projects like these, so it would be great if we can help them out financially. In addition, results from our last company survey indicated that many Canonical employees want to improve our social consciousness, and this would be one way to achieve that.

## Specification

This spec proposes that Canonical starts by using [thanks.dev](https://thanks.dev/) as a simple "Phase I" way to give back to a lot of smaller projects that we use, without much manual work on our part.

Thanks.dev is a website that allows companies to donate a set amount of money each month, and their system divides it up according to the dependencies you have. They automatically track your dependency tree and divide the money up, like so:

![][image1]

In addition to the automatic weightings, thanks.dev provides settings to manually override the weights for certain languages, orgs, or even projects. For example, we could bump Go and Rust higher or bump JS down (because the npm ecosystem encourages huge numbers of dependencies). We could also exclude certain orgs or repos that we definitely didn't want to give to.

However, the default settings look like a good start for Canonical's orgs. I've set this up as a demo on my own thanks.dev account with the Github orgs canonical, charmed-kubernetes, and juju (public repositories only for now). Our top dependencies by org are as follows:

![][image2]

You can click on each of the orgs to drill into the projects we depend on, and our repositories that use them. For example, drilling into `gh/nedbat` shows just how many of our Python projects use coverage.py (this shows only the first few - the full list is 402 projects):

![][image3]

They currently only support tracking dependencies of and donating to GitHub and GitLab projects. Canonical obviously uses projects outside that, and hosts projects on other systems than those. This would only be a "Phase I" approach, and not preclude us from doing more later. (Or working with the thanks.dev team to support Launchpad!)

Thanks.dev does all the hard work of reaching out to the maintainers, sending money, and so on. To do that for hundreds of projects manually would be a huge effort. If a maintainer can't be reached or doesn't want to receive the donation, that amount is distributed to the rest of the projects. For this service, thanks.dev charges a 5% cut (a donor can "tip" them more if they want), in addition to the Stripe fees:

![][image4]

In terms of auditing, thanks.dev provides a public link for donors that lists a breakdown of their distributions to date, for example, [Sentry's](https://thanks.dev/o/sentry-241112). They also provide a public breakdown for recipients, for example, developer [Remy Sharp](https://thanks.dev/r/gh/remy). They distribute funds via Stripe, GitHub Sponsors ([public page](https://github.com/orgs/thnxdev/sponsoring#)), Open Collective ([public page](https://opencollective.com/thanks-dev)), and Wise.

