# OP030 — Keeping charm dependencies up-to-date

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Process |
| Created | Feb 7, 2023 |

## Abstract

Keeping software up to date is an important aspect of information security. Kubernetes charms are made of at least two containers, the operator and the workload. This specification outlines the steps that should be taken by Charm developers to keep their **operators** up to date with the latest security fixes. Other specs will cover workload container images (OP031) and operator images.

## Rationale

There is currently no standard in how charms are kept up to date. It is often the case that a charm is updated only when new features are added. It is a risky situation, especially for stable charms that do not receive regular development.

Also, many different teams are developing charms, and have different processes in place. There is a great opportunity to standardize the process, in order to automate it once for all developers.

## Specification

This specification covers the process to keep the base up to date, and the dependencies.

### Base

Bases are the underlying operating system used for the charm code. The "build" base is used by charmcraft for building the charm, while the "run-on" base is used by Juju when deploying the charm. The "run-on" base in the case of a machine charm will be the supported operating system that needs to run on the target machine to deploy the charm. In the case of Kubernetes charms, the "run-on" base will be the base image used by Juju to deploy the charm code on.

The bases used to build and run charms are not maintained by the charm developers. However, the choice of the base is made by charm developers. The base should be the latest LTS version of Ubuntu, in order to receive the latest security updates. The only exception is for machine charms where the operating software cannot run on the latest LTS release, for any reason. In that case, the most recent LTS release that works should be used.

### Python dependencies

The python dependencies are the python libraries that are used in the built charm. They should:

* Be listed in a requirements.txt file, or in the PYDEPS variable for charm libraries
  * All dependencies with pinned versions must be specified
  * Tooling to manage the requirements.txt file is left to each team, but recommended (pip-compile, pip-tools, poetry, etc.).
  * Have exact versions specified, but can be defined as ranges in the tools used to generate the requirements.txt file. Example:
    * A dependency on requests would be set like this in requirements.txt:
      * requests == 2.28.2
    * When using pip-compile, it could be set like this in requirements.in:
      * Requests < 2.29
  * If multiple versions of the same library are required on different bases, they should be defined with environment markers, as defined in PEP-508 ([https://peps.python.org/pep-0508/](https://peps.python.org/pep-0508/))

* Be reviewed and updated at least once a week
  * Using Renovate ([https://docs.renovatebot.com/](https://docs.renovatebot.com/)) for this task is recommended
    * A base Renovate configuration should be maintained centrally for all operator engineering to be extended by each team for their specific needs
    * Changes to the shared configuration will be done by pull requests and require 3 approvers from charming engineering teams, from at least 2 teams
    * Individual teams or projects can extend the shared configuration for their own needs
    * Should check tox.ini and requirements.txt files
    * Should check PYDEPS variables in library files
    * Should check GitHub actions
  * A shared Renovate configuration is maintained at: [https://github.com/canonical/route53-acme-operator/pull/11](https://github.com/canonical/route53-acme-operator/pull/11) (temporary link for discussion)

There exist alternatives to Renovate, like Dependabot from GitHub. Renovate has been chosen because it is not tied to GitHub and will work with Launchpad projects, and is already used by many teams with great success.

### Charm libraries

Charm libraries installed with `charmcraft fetch-lib` should be validated with the "canonical/charming-actions/check-libraries" GitHub Action.

### APT dependencies

The APT dependencies used in a charm will be linked to the base. As such, they will already be maintained following the LTS strategy. To ensure they benefit from security patches, those dependencies should not be pinned to specific versions, except for machine charms when a specific version of a package is required for a workload.

### Promoting to stable

To ensure users receive the security fixes from updated dependencies, stable charms should be promoted to the stable channel of the relevant track weekly at a minimum. When it is necessary to maintain multiple parallel versions of a charm, tracks should be used for stable releases so that security updates can be promoted to stable older versions of the charms. This will be accomplished by the repository having one branch per published track.
