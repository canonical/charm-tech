# OP??? — AI-assisted development in Charm Tech

| Field | Value |
| --- | --- |
| Status | Braindump |
| Type | Process |
| Created | 1 November 2026 |

## Abstract

This specification sets out how Charm Tech uses AI tools for software development. We standardise on [Pi](https://pi.dev) as the coding harness and OpenRouter as the provider, with GitHub Copilot instead for confidential projects. GLM and Kimi are the default model families. Whoever submits a change is still responsible for it.

We want useful AI-assisted work to be repeatable without lowering our standards, leaking data, or moving work from the author to the reviewer.

## Rationale

We're already using AI tools to explore code, implement and debug changes, write tests and docs, and review. A shared setup makes it easier to reuse instructions and skills, compare results, and help each other. Models change quickly, and the best one varies by task, so we standardise the harness, the context, and the limits rather than a prompt or a model version.

AI-generated work can look convincing and still be subtly wrong. It can also produce code nobody needed, shallow tests, and pull requests that cost more to review than they saved to write. Our existing engineering standards still apply.

## Scope

This specification covers the tools we use, where shared knowledge lives, the limits on data and agent actions, and how we judge whether the tools are helping.

It doesn't require anyone to use AI tools, and it doesn't relax any project's contribution, review, testing, security, or release requirements. It doesn't replace Canonical's rules for handling private and confidential data.

## Specification

### Standard toolset

| Layer | Choice | Policy |
| :---- | :---- | :---- |
| Harness | Pi | The team's supported harness for interactive coding and shared skills. |
| Models | GLM and Kimi | The default model families on OpenRouter. |
| Provider | OpenRouter, or GitHub Copilot for confidential projects | The provider, account, and model must also be approved for the data you send. An endpoint that works isn't necessarily one that's approved. |
| Project context | `AGENTS.md` | Repository-specific instructions, version-controlled in the repository. |
| Reusable procedures | Skills | Shared, version-controlled skills in the [Agent Skills](https://agentskills.io) format, so they work in any compatible harness. |
| Automated workflows | Whatever fits | Rigid, event-driven pipelines don't have to use Pi. |

We record each change to the default models in `DECISIONS.md`. Changing a model shouldn't mean changing repository instructions or skills, unless the new model shows up a real problem in them.

You're welcome to try another approved harness, but feed what you learn back into the team setup, so it doesn't become a private workflow only you understand.

We recommend running Pi in the repository's own Workshop, our LXD-based development environment. Workshops are planned for every repository and include Pi, but some repositories don't have one with Pi yet. In those repositories, or if a task needs something the Workshop doesn't provide, a custom VM or other isolated environment is fine.

#### Why these choices

Pi is minimal and extensible, which matches how we like to build our own tools. It's highly customisable, but it's also opinionated, and we like that too. By default it runs tools without asking for approval. We think that's the right default, as long as it runs in a sandbox. Pi is open source under the MIT licence, although some future parts may be [Fair Source](https://fair.io). We admire the [values of Earendil](https://earendil.com/values/), the company behind Pi, and we expect [Pi Durable](https://earendil.com/posts/pi-durable/) to be worth exploring.

Canonical lets us choose between GitHub Copilot, Gemini, and OpenRouter as the provider. In our experience, Gemini models generally aren't good enough. We tried Copilot, but we found that OpenRouter's flexibility suits us better. Copilot is still required for confidential projects.

We prefer open-weight models for our defaults, because that's Canonical's preference.

#### Recommended Pi extensions

Pi extensions are third-party npm packages that run with the same access as Pi. Install only the ones you need, and pin each to a version. Propose additions in a pull request to this specification.

| Extension | What it adds | Notes |
| :---- | :---- | :---- |
| [`pi-lens`](https://github.com/apmantza/pi-lens) | Real-time feedback from language servers, linters, formatters, and type checkers. | The agent sees the same problems the project's own tooling reports. |
| [`pi-subagents`](https://github.com/nicobailon/pi-subagents) | Delegation to a subagent, and scripted multi-agent workflows. | Useful for review passes in a fresh context. |
| [`pi-web-access`](https://github.com/nicobailon/pi-web-access) | Web search, fetching URLs, cloning repositories, and extracting text from PDFs. | Search queries go to a third-party search provider, so the data rules here apply to them too. |
| [`pi-prompt-template-model`](https://github.com/nicobailon/pi-prompt-template-model) | Lets a prompt template choose the model it runs with. | Makes it easy to send routine tasks to a lower-cost model. |
| [`pi-intercom`](https://github.com/nicobailon/pi-intercom) | Messaging between Pi sessions on the same machine. | Useful when one session researches and another implements. |
| [`pi-autoname`](https://github.com/ssdiwu/pi-autoname) | Meaningful names for sessions. | Optional. |

### Context and reusable instructions

Give an actively maintained repository an `AGENTS.md` when repository-specific guidance would noticeably improve how agents behave. It should cover what an engineer joining the project would need to work safely, including:

* what the repository is for, and its important boundaries;
* the commands for development, formatting, linting, type checking, and testing;
* project-specific design constraints and common mistakes; and
* any files or operations an agent mustn't touch without being told to.

Keep it short, and link to the project's existing docs rather than copying them. Update it in the same change that makes it wrong.

If a repeatable task applies across repositories, make it a shared skill rather than copying a section into several `AGENTS.md` files. We review changes to shared instructions and skills like code. When an agent keeps needing the same correction, ask whether the fix belongs in `AGENTS.md`, a shared skill, or the project's docs, rather than in your own local configuration.

Guidance shared across the team, such as policy, decisions, model defaults, and skills, goes in [`canonical/charm-tech`](https://github.com/canonical/charm-tech). Runnable code shared by more than one project, such as tools that call a model or implement an agent workflow, goes in [`canonical/charm-tech-code`](https://github.com/canonical/charm-tech-code), one separately testable package per tool. Workflow entry points and GitHub Actions YAML stay in the repository that runs them, pinning the shared tool by commit SHA. That way their triggers and permissions are reviewed alongside the project.

### Development workflow

AI assistance fits into our existing development process.

Give the agent the issue, the relevant code and docs, any constraints, and a concrete definition of done. Say what's out of scope. The agent shouldn't add unrelated refactoring, new dependencies, compatibility layers, retries, or abstractions unless the task needs them. If a change spans several components or involves real design choices, have the agent write a short plan first, and check that the plan tackles the actual problem.

Keep the work small enough that you can understand and review it. The agent should reuse existing patterns rather than add a second way of doing the same thing. Prefer the smaller, clearer implementation, but if a well-supported dependency does the job, use it rather than generating a local replacement we then have to own. A feature being cheap to generate doesn't make it worth having, and generated code, tests, and dependencies mustn't grow beyond what the team can look after.

#### Verify the result

When the agent has the environment it needs, it must run the checks that exercise the changed behaviour. It must report what it actually ran, and never suggest that a check passed when it didn't run it. You decide whether that's enough, which means reading the diff, running anything the agent didn't, and trying the real behaviour where tests alone aren't good evidence.

Generated tests must protect observable behaviour. Don't add tests that only check a mock returned what it was told to, that mirror the implementation, or that add coverage without checking behaviour. A three-line fix doesn't need a 300-line test file.

Property-based and fuzz testing can find paths that example-based tests miss, but they change the shape of a test suite, so they need more review than one more test case. During the first half of the 27.04 cycle, we'll try out property-based, Hypothesis-style, and fuzz-testing tools, and then decide which should become project standards.

#### Review before submission

Read and understand the whole change before you submit it. If you can't explain a line or a decision, it isn't ready for review.

An agent in a fresh context makes a useful extra review pass, particularly for edge cases, regressions, needless complexity, and missing tests. For complex work, a few focused reviews (for example, one for correctness and one for tests) work better than one agent reviewing everything. These don't replace your own review or peer review.

Using AI shouldn't make a pull request harder to review. Keep it focused, explain why the change is needed, call out the important decisions, and include the evidence that it works.

#### Perform security-focused AI review

Canonical's Secure Software Development Lifecycle (SSDLC) policy requires a developer-led, AI-assisted security review for some products and release types, starting in the 27.04 cycle. The [SSDLC Vulnerability Discovery and Identification policy](https://library.canonical.com/corporate-policies/information-security-policies/ssdlc/ssdlc---vulnerability-discovery-and-identification) sets out when the review applies, what it covers, and how to track its findings. Like any AI review, it's advisory, and doesn't replace peer review.

### Human responsibility and attribution

You own every code, test, docs, and design decision you submit. Reviewers are reviewing your contribution, not raw model output.

An agent must never add a `Signed-off-by` line for you. Only you can certify the Developer Certificate of Origin.

We don't require AI attribution on commits or pull requests, but repositories and upstream projects may have their own rules, and those take precedence. Where attribution is useful or required, use an `Assisted-by` trailer naming the harness and model:

```
Assisted-by: <harness>:<model-name-and-version>
```

For example, `Assisted-by: pi:glm-5.3`.

### Data and security

Canonical's [AI in the workplace policy](https://library.canonical.com/corporate-policies/ai-governance-policies/artificial-intelligence-%28%22ai%22%29-in-the-workplace-policy) applies to everything this specification covers, and takes precedence where the two differ.

Public code, docs, issues, and pull requests can go to models through OpenRouter. Private repository content and internal documents can only go to a harness, provider, model, and account approved for that data. If you're not sure whether something is approved, or how it's classified, don't send it.

Check logs, stack traces, configuration, and generated artefacts before you send them to a model. Never send secrets, credentials, private infrastructure details, customer or employee data, embargoed vulnerabilities, or anything else that isn't public. If you send protected information by accident, follow the normal security incident process. Deleting the conversation isn't enough.

### Boundaries on agent actions

Pi runs tools without asking first, so run it in a sandbox, such as the repository's Workshop or a VM. Inside the sandbox, an agent can read and edit the checked-out repository and run its development commands. The sandbox and the credentials you give the agent are what stop it doing anything else. Don't rely on it asking before something destructive, hard to reverse, or outside the sandbox.

Give agents the least access the task needs: scoped, read-only credentials where you can. In particular, don't give an agent credentials that would let it, without a separate approved process:

* merge or approve a pull request;
* publish a package, charm, snap, image, or release;
* push to a protected branch;
* change production or shared infrastructure; or
* disclose or rotate credentials.

Agents can gather evidence and suggest an answer, but product, security, and legal decisions stay with people.

### Automated agent workflows

Move repeatable, event-driven work into shared workflows where that's useful. Design, exploration, and one-off work still happen locally, and that hands-on work is how we learn enough to automate something well.

Each automated agent workflow needs its own specification or documented review. It should cover the trigger, permissions, data boundary, model and provider, spending limit, timeout, failure behaviour, audit trail, and the point where a human approves. A failing advisory AI service shouldn't block ordinary development, unless we've deliberately made that check required.

Split complex workflows into explicit stages, each with a narrow input and output, rather than relying on one orchestrating agent to follow a long prompt. Where it helps, isolate each stage's context and pass versioned files or commits between stages.

GitHub Actions is a reasonable place to start, because it already handles events, logs, permissions, and an audit trail. Run untrusted tool calls in a container or another isolated environment, and never treat text from an issue, pull request, or comment as a trusted instruction. Workflows triggered by external content start with a manual approval step, to limit prompt injection, repeated triggering, and runaway model cost. A workflow can become automatic later, once we understand its inputs, failure modes, and cost.

### Model choice and evaluation

Use a lower-cost model for routine work and a more capable one when the task needs it. When you're not confident in an answer, comparing independent answers from both often helps more than prompting the same context again.

We review the defaults roughly monthly. A model doesn't become a default because it tops a benchmark or because one person had a good result with it. We try it on real Charm Tech work and compare it with the current defaults.

We judge the setup by outcomes, not by tokens used or code generated. Useful measures include:

* whether the change is correct after review;
* defects found before peer review;
* review effort and the number of revision rounds;
* time taken to reach a verified result;
* model and provider cost;
* how often someone has to switch away from a default model to finish a task; and
* repeated failures that should become instructions, skills, tooling, or tests.

We don't need to record every interaction. Write a short experiment record when comparing models, changing a default, adding a shared skill, or deciding whether to adopt an automated workflow. Include the task, harness, model and version, relevant settings, outcome, how you verified it, cost if you have it, and what you learnt. Experiment records go in the `experiments/` directory of `canonical/charm-tech`.

### Team assets and maintenance

The `agents-md` skill in `canonical/charm-tech` helps write an `AGENTS.md` for repositories that need one. We hold a recurring 30-minute AI and testing discussion to share tools, results, and failures, and to propose changes to the defaults.

### Project maturity

Projects carry different risks and are at different stages, so they won't all have the same automation. During the 27.04 cycle, we'll document the expected maturity levels for testing, security checks, agent instructions, and automated review. Each actively maintained project will then record a target and a path towards it.

The aim is for every actively maintained project to have an automated reviewer suited to its risk and maturity. Then correctness, testing, security, and docs checks run whether or not someone remembers to run them. AI review still doesn't replace human review.

## Further Information

The common harness and shared setup draw on SEC068 and MA296. The human accountability, contribution, and data rules draw on CE141, CS309, and OS113. The separation of harness, reusable capabilities, and workflows draws on ISD285 and RK112. The guidance on experiments and costs draws on AC215 and PEALL006. The review and automated-workflow boundaries draw on LP299, CE155, PL103, and BIN-002.

The security-review requirements draw on SSDLC Vulnerability Discovery and Identification (SEC0025), Vulnerability Response (SEC0026), and the Code Repository Security Policy (SEC0065).
