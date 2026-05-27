# OP072 — Charmhub Public Listing Review Process

| Field | Value |
| --- | --- |
| Type | Process |
| Created | Jul 15, 2025 |

**This spec updates and replaces sections of [CC003](https://docs.google.com/document/d/1YHzR52hpVjPhuvgYmT249EegM07vypB4lRHSgI8KXIQ/edit?usp=drivesdk).**

## Abstract

[CC003 Charm Review Process](https://docs.google.com/document/d/1YHzR52hpVjPhuvgYmT249EegM07vypB4lRHSgI8KXIQ/edit?usp=sharing) provides clear reasoning for why a review process for public listing in Charmhub is required, and a process that has been used for the last two years. Recently, as the volume of public listing requests has increased, and the charming ecosystem has matured, flaws in the review process have been identified. This spec proposes adjustments to the process to attempt to fix those complaints, while retaining the original motivation and core definition of charm maturity of CC003.

## Rationale

Several issues have been identified with the existing process, by reviewers, members of the Charm Tech team, and charm authors (both within and external to Canonical).

* **Inconsistency in terms of what is reviewed**. Some criteria are written subjectively, and some reviewers go beyond what is in the checklist. It's not clear to reviewers what is expected of them, and it's not clear to authors what the expectations are of their charm, and this means that the substance of reviews differs depending on the reviewer, even when charms are very similar.
* **Code review or no code review?** The instructions get people to do a 'from empty' pull request, which hints at code review, but generally the checklist isn't about reviewing the code. This means that some reviewers do code review and some do not. When code review is done, some reviewers do a line-by-line detailed review, some are looking only at high-level design, and others are only looking for specific issues. In general, by the time a request is made for public listing, the charm design is 'baked' and would be difficult to change (design and line-by-line style reviews are better much earlier in the process). The title "Charm Review Process" contributes to this confusion - the process is reviewing the charm specifically in terms of eligibility for public listing, rather than being for a general or design review.
* **Lack of automation.** Some of the checks are 'does this exist', or 'does this run without errors', which isn't a good use of reviewer time.
* **Inability to pre-check.** Authors, particularly external ones, would like to know how close they are to meeting the criteria, before a review is submitted.
* **"Charm works as expected" is hard to review.** Sometimes you need specialised resources, sometimes there are poor instructions, sometimes there's a fairly extensive and time-consuming amount of work to test a fairly simple charm.
* **Inconsistent timing** - time to get assigned a reviewer, time for the reviewer to do an initial review, follow-up time. There are no times documented, so no-one is "wrong" here, but no-one is happy, either.
* **Easy to get forgotten** - Discourse threads are not in anyone's ticketing system, so there's no system for making sure that progress is being made.
* **Difficult to assign the right people** - maybe someone is on vacation, maybe it's a really busy pulse for someone, and similar issues.

## Specification

To address the identified issues, the following adjustments will be made to the process:

* **Very explicit instructions that are as objective as possible**. It should be clear to any reviewer and any author what the expectations are. If the reviewer wants to add additional commentary, that's fine, but it does not block the public listing. Reviewers can submit PRs for improvements to the process, checklist, and best practices when they notice something missing, and that can be discussed as a group before being adopted.
* **No code review**, other than specific items in the main checklist or best practices. It's too late to be reviewing the code line-by-line, and that should primarily be the responsibility of the people building the charm, not the reviewer.
* **Automate as many checks as possible**. Let authors get results prior to a reviewer being assigned, and remove tedious tasks from the reviewer to minimise the time commitment and maximise using their expertise.
* **Prefer demos** over the reviewer testing the charm behaviour themselves, except for simple cases. For simple cases, there should be a tutorial that can be followed.
* **Use a ticketing system** rather than Discourse.
* **Explicitly state the expected timetable for reviewing**.
* **Assign reviews to team managers**, with the expectation that they delegate to someone from their team to do the actual review.

### Process

#### Overview

* Use GitHub (many charming teams are more primarily using Jira, but we need something that is externally accessible - reviewers can mirror tickets from GitHub to Jira if needed). It's reasonable to expect anyone that is submitting a charm for review can use GitHub issues.
* Use a GitHub issue form to get the required data in a simple format, ensuring that everything required is provided by the author.
* Use a GitHub workflow to automatically post a comment on the issue that outlines what is needed from the reviewer. This also does automatic checks where possible, so pre-ticks some items. There is a mechanism to trigger the automatic checks to run again. The automation also picks an appropriate manager to assign the review to.
* The reviewer posts comments on the issue that indicate whether items have been successfully reviewed or not. The checklist items must be kept in the same form so that the GitHub automation can update the state of the request, but additional free-form comments can be added for any additional comments that the reviewer has for the author.
* A new way is found to contact the store team to publicly list the charm (instead of a @ping on Discourse), perhaps posting a ticket somewhere, through some automation?
* Issues are closed (:fixed) when the review is successful and the charm has been publicly listed.
* Charm Tech is responsible for monitoring the state of issues overall, but team managers are responsible for meeting the timelines in the issues they are assigned.

#### Requesting public listing

The issue form will request from the author:

* The charm name
* A URL where a demo recording of the charm, or a tutorial that can be used to run the charm. Alternatively, the author can arrange a meeting with the reviewer to demo the charm functionality.
* The URL for the charm repository
* A URL that shows that the charm has automated linting
* A URL that shows that the charm has automated releasing
* A URL that shows that the charm has automated integration tests
* A URL for the charm's documentation

We intend to do future work that looks at standardising the CI workflows that charms use, particularly around linting, releasing, and testing. As part of that work, it is likely that we will be able to both avoid asking for those URLs (at least for GitHub) and also evaluate whether they do what is expected.

A GitHub workflow will be triggered when an issue is created from the form. The workflow will add a comment to the issue with instructions for the reviewer, including a checklist for the review (similar to the checklist that's in the existing Discourse template) comprised of both checks defined in the workflow's code and also pulling the best practices from across the Juju, Ops, and Charmcraft documentation. The workflow will also assign a manager to the review - the manager is then expected to delegate the review to someone in their team, by tagging them in a comment.

#### Permissions

Although we generally trust both the author and the reviewer, and GitHub provides an audit history for any changes to issues, we want to prevent 'cheating' (perhaps accidental) by having items checked off by the wrong person.

* Team managers need to have sufficient repository permissions to be assigned issues, which gives them the ability to make edits to issues. For this case, as these are trusted Canonical employees, we will rely on them working within the process.
* The issue description is editable by the author, who opened the issue. For this reason, the description is only used as data storage for the information the author provided when opening the issue (and not any part of the checklist itself). The author is able to edit the description to provide additional information or correct existing information, although they need to keep to the existing format or the automation will not work (until the description is fixed).
* The primary checklist showing the state of the review is kept in a comment by the automation, which is not editable by the author or the reviewer (unless the reviewer happens to be from Charm Tech or a manager).
* The assignment of the review by the manager to a member of their team must be done by the person assigned to the review, and must be done by @-mentioning the reviewer in a comment.
* Only comments by the reviewer (identified as above) can adjust the review checklist (other than the automation).

#### Automation

Where possible, the requirements will be automatically checked. This minimises the load on the reviewer, but also allows the author to regularly evaluate their progress against many of the requirements.

The GitHub workflow that adds the initial requirements will do an evaluation at that time and tick off any that are already met. When new comments are added to the thread (this could be the reviewer providing their review, or the author triggering an update) a workflow will re-evaluate the list and update the checklist.

An initial set of checks will be automated, some of which will only work if the repository is hosted on GitHub. The automation can be extended as required through the normal development process.

* A contribution guidelines document exists. For now, a file existing is sufficient (we do not make any attempt to evaluate the content of the file).
* A license file exists (for the automation, also that it matches one of a set of known licenses - if it's something else, then the reviewer will need to manually check it).
* A security document exists. For now, a file existing is sufficient (we do not make any attempt to evaluate the content of the file).
* charmcraft.yaml has name, title, summary, and description that aren't the default ones from the profile, and a links field that has documentation, issues, source, and contact fields, which are all valid URLs. Note that we do not currently evaluate the content itself.
* The charm name is in the expected format.
* The charm's action's names use the expected convention.
* The charms' config names use the expected convention.
* The repository name uses the expected convention.
* All of the (non peer) relations in charmcraft.yaml have an explicit "requires" field.
* "format", "lint", "unit", and "integration" commands exist in a tox, Makefile, or Just file, and all of these other than "integration" run successfully (running "integration" is too heavy for this test).
* When the "charm" plugin is used, strict dependencies are required.
* requires-python is set in pyproject.toml
* The repository has a dependency lock file (uv.lock, poetry.lock, requirements.txt).
* The charm has a 100x100 SVG icon. The requirements also include it being a circle with a flat colour and a logo, and there are several other best practices - all of those are too difficult to automate, and it doesn't seem like we should force reviewers to check them.

If the automation does not 'pass' any of these checks, the reviewer can do that instead. For example, if the license URL gives a license but it's not one we recognise, or if the charm's actions are not in the expected naming convention but there is a legitimate reason for that.

Similarly, for checks that the automation cannot handle, the reviewer posts a comment that has a ticked version of the checklist item, and the workflow automation will copy that tick over to the primary list (always in comment #1).

#### Timeframes

Charm team managers are asked to ensure that an initial review is completed within three working days (with time zone differences, this may end up close to a calendar week). Asking managers to assign the review within their team, the clearer review process (and particularly the removal of implied code review), and the addition of automation makes a tighter turnaround more feasible.

Reviewers are asked to respond to follow-ups by the author within one working day. This can be only an acknowledgement ("thanks for the update - I'll review the new information next Wednesday"), but helps the author be confident in the expected timeframe.

The overall time for the review will depend on the responsiveness of the author and how many issues are found.

## Further Information

The repository will be [https://github.com/canonical/charmhub-listing-review](https://github.com/canonical/charmhub-listing-review) - for now the prototype code and examples are located in a temporary repository in tonyandrewmeyer/charmhub-listing-review.

* [Example request](https://github.com/tonyandrewmeyer/charmhub-listing-review/issues/2)
* [Example comment](https://github.com/tonyandrewmeyer/charmhub-listing-review/issues/2#issuecomment-3047512986)
* [Issue submission form](https://github.com/tonyandrewmeyer/charmhub-listing-review/issues) (choose the first option)

### Illustrated Walkthrough

Using the "New issue" button in GitHub prompts the author to choose an issue type.
![][image1]

The "Charmhub Listing Request" type provides the author with a form to complete.
![][image2]
An issue then exists in the repository (note that the label was added automatically).
![][image3]

The workflow will then add a comment with instructions, a checklist, and assign the issue. Some checkboxes may be pre-ticked if the automated evaluation was able to determine that the criteria is met.

![][image4]
