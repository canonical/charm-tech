# OP031 — Maintaining oci-images for K8s charms

| Field | Value |
| --- | --- |
| Type | Process |
| Created | Feb 9, 2023 |

## Abstract

Keeping software up to date is an important aspect of information security. Kubernetes charms are made of two containers, the operator and the workload. This specification outlines the steps that should be taken by Charm developers to keep their **workload** up to date with the latest security fixes. Spec OP030 addresses the process for the operator.

## Rationale

There is currently no standard in how OCI images used by charms are kept up to date. It is often the case that the image is only updated manually to a new release when new features are required. It is a risky situation, especially for stable charms that do not receive regular development.

Also, many different teams are developing charms, and have different processes in place. There is a great opportunity to standardize the process, in order to automate it once for all developers.

## Specification

This specification covers the processes on how to build, upload, scan and update OCI images used by charms. Most of this specification is expected to be superseded by an official rockcraft specification in the future.

### Building OCI images

OCI images used for charms should be either built by rockcraft, or upstream images when they are well maintained. They should be based upon the latest Ubuntu LTS release. APT and snap packages versions pinning is left up to the charm developers. When version pinning is used, a verification process must be in place to ensure that the pinned versions are not vulnerable.

### Uploading OCI images

Once built, OCI images should be tested, before uploading the image to Charmhub using charmcraft, or being uploaded to an intermediary registry. Once uploaded to Charmhub, the image can be removed from the intermediary registry, at the developers discretion.

### Scanning OCI images

Scanning images for security issues is an important step to ensure that customers get secure software. Before getting uploaded, images should be scanned by using Trivy.

This will be done through the official Trivy GitHub action, with the results automatically uploaded to GitHub's Security tab. For this reason, CodeQL will need to be enabled for all repositories containing OCI images, and it should be configured to fail checks on pull requests on any high or higher errors. Those errors will be able to be dismissed with an explanation in the case that the vulnerability will not be fixed.

It is understood that the vulnerability report will be public on all public repositories, in the GitHub security tab.

Additionally, all supported images should be scanned weekly at a minimum. This will also be done using Trivy, but those scans will automatically open internal Jira tickets for vulnerabilities. The exact mechanism is currently under development in the Kubeflow team and will be added to this spec once finalized.

**Updating OCI images**
Images should be rebuilt, tested, scanned and uploaded anytime "HIGH" or "CRITICAL" vulnerabilities are detected in our images and fixed upstream. If some of those vulnerabilities are deemed lower risk for this particular OCI image, exceptions should be written for each vulnerability individually with a comment explaining why the vulnerability is not fixed.

### Distributing updated OCI images

When a charm is deployed, the OCI image is downloaded and deployed. However, it will not be automatically updated when a new version is pushed on Charmhub. This problem is out of scope for this specification. It is recommended to address this issue with Juju.

### Shared workflows

This specification is implemented in a shared workflow hosted on GitHub. It can be found at: [https://github.com/canonical/nginx-rock/pull/4](https://github.com/canonical/nginx-rock/pull/4). (This is a temporary link to discuss the details. Please look at the workflows and reports on that branch while reviewing this spec)
