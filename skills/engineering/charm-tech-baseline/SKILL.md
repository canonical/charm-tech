---
name: charm-tech-baseline
description: Audit a repository against the Canonical Charm Tech baseline — SSDLC compliance, supply-chain hygiene, and best-of-class extras — and explain or fix the gaps. Tier-aware (product / canonical / personal), agent-generic; drives the deterministic check and fix package in `canonical/charm-tech-code`.
license: CC-BY-4.0
metadata:
  source: Canonical Charm Tech, 26.10 cycle
  audience: any AI coding agent operating on a single repo at a time
---

# Charm Tech baseline audit

Run a structured audit of a single repository's compliance with the Canonical Charm Tech baseline that the 26.10 cycle distilled from SSDLC (SEC0023–SEC0061), the Astral OSS-security best-of-class review, and per-tool measurement work. Emit a JSON report of findings, explain each gap in human-readable form, and optionally apply deterministic fixes for the mechanical ones. Three tiers — `product`, `canonical`, `personal` — control which checks apply; tier is detected from the remote URL or passed explicitly.

## When to use

Use when:

- A new Canonical or personal repo is being stood up and needs the baseline applied from scratch.
- An existing repo needs a compliance gap analysis ahead of a cycle's audit.
- A repo is being promoted up tiers (personal → canonical, canonical → product) and the requirement set widens.
- A targeted check is needed (`--only=security-md`, `--only=dependabot`) to verify one specific control.

Skip when:

- The change is docs-only or a single bug fix — nothing in this skill applies.
- The repo isn't a long-lived first-party project (forks of upstream projects, scratch repos, demo recordings).
- The user is asking about *one* specific tool (e.g. "how do I add zizmor") — answer directly using [`references/decisions.md`](references/decisions.md) rather than running a full audit.

## How to use

Three things need to be present before step 1: `uvx`, an authenticated
`gh` (tier detection and `immutable-releases` shell out to it), and
`git` with the repository checked out and an `origin` remote. The
package's own dependencies are resolved by `uvx` and are not your
problem.

The checks and fixes are a Python package in
[`canonical/charm-tech-code`](https://github.com/canonical/charm-tech-code),
under `charm-tech-baseline`; this skill is the knowledge that makes its output
mean something. Run it with `uvx`, from inside the repository being audited:

```bash
uvx --from "git+https://github.com/canonical/charm-tech-code@<40-char-sha>#subdirectory=charm-tech-baseline" \
  charm-tech-baseline check
```

Pin the SHA rather than tracking `main`. That repository has no release
process, so the SHA is the version.

The rest of this section writes `charm-tech-baseline` for that whole
invocation. `charm-tech-baseline list` prints the check and fix names.

### 1. Detect the tier

`charm-tech-baseline detect-tier` inspects `git remote get-url origin`, resolves forks of `canonical/*` back to the upstream slug (via `gh repo view --json isFork,parent`, or an `upstream` remote as fallback), and prints one of:

- `product` — Canonical-owned repo classified as a *product* in the SEC0023 applicability matrix (full SSDLC requirements scale to the planned release type). Charm Tech examples this cycle: `operator`, `pebble`, `jubilant`, `concierge`, `charmlibs`.
- `canonical` — Canonical-owned repo that is **not** a SEC0023 product (tooling repos, demo charms, internal helpers). Gets cross-cutting requirements only (SECURITY.md, Dependabot, supply-chain hygiene), not the per-requirement SSDLC procedures.
- `personal` — Non-Canonical repo with no canonical upstream (a from-scratch project, or one in flight before transfer). Gets best-of-class hygiene only; no Canonical-internal requirements apply. A personal-account *fork* of `canonical/<repo>` resolves to that upstream's tier, not `personal`.
- `unknown` — no origin remote, or not a GitHub URL.

`check` does this for itself when `--tier` is not given, so running it separately is only for confirming what a repo resolves to.

If detection is ambiguous, ask the user; do not guess. Tier classification flips obligations on/off in the report, so getting it wrong wastes effort or hides gaps.

The user may override: pass `--tier=product|canonical|personal`. The report header always echoes the resolved tier and whether it was detected or overridden.

### 2. Run the audit

```bash
charm-tech-baseline check [--tier=<tier>] [--only=<check>[,<check>...]] [--format=json|markdown]
```

Every check that applies to the resolved tier runs, and the results are aggregated into one report. Default output is JSON for agent consumption; pass `--format=markdown` for a human-readable summary.

Each check reports one of four statuses:

- `pass`
- `fail` — a gap
- `na` — not applicable at this tier, or nothing to check against
- `unknown` — the answer lives somewhere the check cannot see (a Drive sheet, a spreadsheet). **Not a quieter `pass`**: surface it and verify the off-repo source.

A check that raises appears in the report's `notes`, not as a `fail` — that is a bug in the check rather than a finding about the repo.

### 3. Interpret the report

The agent's job is to read the JSON, identify the gaps that need human judgement vs the ones that are mechanical, and propose a remediation plan. Use the references to ground every recommendation:

- [`references/ssdlc-framework.md`](references/ssdlc-framework.md) — what each SEC0XXX requirement actually mandates, where artefacts live, who reviews.
- [`references/decisions.md`](references/decisions.md) — settled cycle-level decisions and carve-outs (for example, admin bypass is `pull_request` not `always`).
- [`references/skipped-tools.md`](references/skipped-tools.md) — tools that were *measured* and skipped (harden-runner, actionlint, pydoclint, prek, shellcheck), with the basis. **Do not re-recommend these without new evidence.**
- [`references/open-investigations.md`](references/open-investigations.md) — items waiting on external triggers (`uv audit` stable, GitHub native L7 firewall GA, OpenSSF Scorecard rollout gated on operator).
- [`references/question-batteries.md`](references/question-batteries.md) — the AGENTS.md question-battery schema: what an entry records, why grading an answer and verifying it against the repo are kept apart, and when an entry honestly has no repo anchor.

### 4. Apply mechanical fixes

For each gap, decide:

- **Mechanical** (file missing, standard template applies): run the matching fix, for example `charm-tech-baseline fix add-security-md`. A fix copies from the package's bundled templates and stages the change for review. The `remediation.script` field in the report names the fix to run.
- **Judgement-required** (SECURITY.md customisation beyond the template, threat model authoring, SEC0045 event scoping, security documentation extension): produce a draft for human review; do not commit autonomously.

Never apply a fix the user did not ask for. The skill's job is to surface gaps, explain them, and offer remediation — not to mutate a repository unprompted.

## Check coverage

These are the checks the package ships. A new check lands in `charm-tech-baseline/src/charm_tech_code/charm_tech_baseline/checks/` in `canonical/charm-tech-code` and gets a row here; each new entry must extend the JSON report schema additively (no breaking changes to existing fields).

| Check ID | Tiers | Mandate | Notes |
|---|---|---|---|
| `security-md` | all | SEC0025 / SEC0026 + V2.0 cross-cutting | File presence + disclosure-policy link. |
| `dependabot` | all | SEC0025 | `.github/dependabot.{yml,yaml}` with ≥1 ecosystem **and** a cooldown of ≥7 days on each (Charm Tech baseline — charmlibs#499). Cooldown values validated via python3+PyYAML; falls back to a presence-only check when those are missing. |
| `code-of-conduct` | all | Convention | Ubuntu-CoC link-only form (not Contributor Covenant). |
| `contributing` | product, canonical | Convention | `CONTRIBUTING.md` *or* `HACKING.md` *or* `docs/contributing.md` accepted, AND a `# Pull requests` heading so the validate-pr-title.py "Read more" URL anchors. Template at `assets/CONTRIBUTING.md.template` follows the dominant Charm Tech pattern (substantive standalone doc; no SECURITY/CoC cross-links — those live in their own files). |
| `agents-md` | all | Best-of-class | Minimal AGENTS.md (warns past 200 lines). |
| `agents-md-content` | all | Best-of-class | AGENTS.md content is trustworthy, not merely present (Layer 1 staleness): commands parse and their tools resolve, safe commands run and exit 0 while environment-gated ones are reported `verify-manually`, referenced paths/symbols/test suites resolve, prose version pins match what CI pins, and harness-shaped content is flagged as out of scope. `na` when there is no AGENTS.md. |
| `agents-md-battery` | all | Best-of-class | The repo's question battery still describes the repo (Layer 2 seed data): every `source_line` is still in AGENTS.md, every assertion still holds, and the entries conform to the schema. Batteries live in the package's `assets/question-batteries/`, one per repo; schema and rationale in [`references/question-batteries.md`](references/question-batteries.md). `na` for a repo with no battery — only repos through the Layer 2 authoring gate have one. |
| `pre-commit-config` | all | Convention | Flags `rev:` version pins (versions belong in `pyproject.toml`). |
| `gha-sha-pinning` | all | Astral best-of-class | All actions SHA-pinned; no exceptions allowed. |
| `yaml-extension` | all | Convention | YAML files under `.github/` must use `.yaml`, not `.yml`. Mechanical fix `rename-yml-to-yaml` uses `git mv`; a manual sweep is still needed for `workflow_call uses:` paths, README links, and downstream action consumers. |
| `workflow-secrets` | all | Canonical Security "Repository security" — Secrets | Scans `.github/workflows/*.y*ml` for four leakage patterns: (1) workflow-level `env:` referencing `${{ secrets.* }}`; (2) job-level `env:` referencing `${{ secrets.* }}` (both over-scope the secret beyond the step that needs it); (3) `run: echo`/`printf`/`cat` interpolating a secret expression (log-masking not guaranteed for every transformation); (4) `secrets: inherit` on reusable-workflow calls. Env-scope checks need python3+PyYAML; textual checks (echo/inherit) run either way. Personal-tier: advisory. |
| `uv-exclude-newer` | all | Canonical Security "How-To: Secure a repo" — Minimum release age | Requires `[tool.uv].exclude-newer` in `pyproject.toml` set to a rolling ≥7-day quarantine (friendly duration like `"7 days"` / `"1 week"`, or ISO 8601 like `"P7D"`). Complements Dependabot cooldown by covering every OTHER uv resolution path — manual `uv add`, `uv lock` regens, uvx bootstraps, CI re-resolves — that Dependabot cooldown alone doesn't reach. Accepts RFC 3339 timestamps (absolute snapshot) with a note recommending rolling durations instead. Uses python3+tomllib (stdlib 3.11+) for validation; falls back to a text-only presence check when unavailable. `na` on non-uv projects (no `pyproject.toml`); `fail` when `uv.lock` exists but `[tool.uv]` doesn't (this IS a uv project that just needs the section added). |
| `dependency-review` | product, canonical | Cycle sweep | `actions/dependency-review-action` wired. |
| `attest-build-provenance` | product, canonical | SEC0023 best-of-class | Required when a publish/release workflow exists. |
| `attest-sbom-deprecated` | all | Upstream deprecation | Flags `uses: actions/attest-sbom@…` in any workflow. The action is deprecated; swap in `actions/attest` (same `subject-path` / `sbom-path` inputs, same SBOM predicate). Ref: [actions/attest-sbom](https://github.com/actions/attest-sbom) deprecation notice. |
| `openssf-scorecard` | product, canonical | Best-of-class (gated on operator) | Workflow + README badge. |
| `conventional-commits` | product, canonical | Convention | PR-title validation workflow. Fix installs operator-style `validate-pr-title.yaml` + `check-conventional-pr-title.py` from the package's `assets/` and rewrites the help URL to this repo. |
| `immutable-releases` | product, canonical | GitHub-side toggle | Inspects latest release via `gh api`. |
| `trusted-publishing` | all | Astral best-of-class + cycle baseline | Workflows publishing to PyPI use Trusted Publishing (`pypa/gh-action-pypi-publish` with `id-token: write`, no `password`/`username`). Flags `twine upload` and any token-input use. `na` when no PyPI publish workflow is present. Templates: **personal/canonical** → `assets/trusted-publishing.yaml.template` (inline CycloneDX SBOM + `attest-build-provenance` + `attest`); **product** → `assets/trusted-publishing-product.yaml.template` + `assets/sbom-secscan.yaml.template` + `assets/sbomber-manifest-sdist.yaml.template` + `assets/sbomber-manifest-wheel.yaml.template`. Environment name is `publish-pypi`. **When applying any of these templates the agent must (a) replace every `REPLACE_WITH_*` marker, (b) modernise each SHA-pinned action to the latest release — look up the current commit SHA on GitHub and update the `# vX.Y.Z` comment — and (c) verify the result passes zizmor with no findings before opening the PR.** |
| `repo-settings` | all | Cycle baseline | Either declared in `canonical-repo-automation` (CRA) or live settings match the baseline (squash-only merges, delete-branch-on-merge, secret scanning + push protection, Dependabot security updates, private vulnerability reporting, selected-actions allowlist). Drift on a CRA-enrolled repo is `judgement` (run CRA apply); a non-enrolled canonical-owned repo gets a `judgement` remediation pointing at CRA enrolment; personal-tier gets the mechanical `apply-repo-settings.py` fix. |
| `secscan-workflow` | product | SEC0025 | Two flavours accepted: sbomber-driven (workflow invokes `canonical/sbomber` + `.sbomber-manifest*.yaml` with `clients.secscan` and per-artifact `ssdlc_params`), or direct `canonical-secscan-client` with `--ssdlc-product-name` / `--ssdlc-cycle` CLI params. |
| `sbom-workflow` | product | SEC0027 | `sbom-request` workflow or `.sbomber-manifest-*.yaml`. Workflows must trigger on `release` / `schedule` / `push: tags:` (per-cycle cadence); `workflow_dispatch`-only fails. |
| `tiobe-config` | product | SEC0024 | TIOBE TICS workflow present, references `secrets.TICSAUTHTOKEN`, and language linters declared (Python: `flake8` + `pylint`; Go: `staticcheck`). |
| `tqi-security-target` | product | SEC0024 | Informational — target lives in *TiCS Targets* spreadsheet. |
| `sec0030-coverage` | product | SEC0030 V1.3 | Looks for seven required sections in `docs/explanation/security.md` or `SECURITY.md`. |
| `sec0045-events` | product | SEC0045 | Per-product disposition; greps for OWASP Application Logging Vocabulary event-name tokens (`authn_*`, `authz_*`, `sys_*`, `user_*`, `session_*`, `excessive_use`, `malicious_*`, `input_validation_*`) as well as the broader `OWASP`/`securitylog` name references. Pass signal recorded in evidence (`event-name-tokens` vs `name-reference-only`). |
| `threat-model-drive` | product | SEC0028 | Informational — model lives in SSDLC Artifacts Drive. |
| `vulnerability-response-plan` | product, canonical | SEC0026 | Informational — plan lives in SSDLC Artifacts Drive. |

Checks that emit `unknown` status are informational and require the agent to verify the off-repo source (Drive sheet, *TiCS Targets* spreadsheet, etc.). The agent should not silently treat `unknown` as `pass`.

## Report shape

The umbrella check emits the following JSON shape. Agents should rely on this contract; new checks must extend the schema additively.

```json
{
  "schema_version": 1,
  "repo": "git@github.com:canonical/example",
  "tier": "canonical",
  "tier_source": "detected|override",
  "generated_at": "2026-06-27T20:00:00Z",
  "checks": [
    {
      "id": "security-md",
      "status": "pass|fail|na|unknown",
      "tier_applies": ["product", "canonical", "personal"],
      "summary": "SECURITY.md is present and links to the Ubuntu disclosure policy.",
      "evidence": {"path": "SECURITY.md", "lines": 41},
      "remediation": null
    },
    {
      "id": "dependabot",
      "status": "fail",
      "tier_applies": ["product", "canonical"],
      "summary": "No .github/dependabot.yaml found.",
      "evidence": {},
      "remediation": {
        "kind": "mechanical",
        "script": "add-dependabot",
        "human_review": "Confirm the ecosystem set matches the repo (Python? Go? Actions?)."
      }
    }
  ],
  "notes": [
    "secscan check (external API) returned exit 3; re-run with network access."
  ]
}
```

Field rules:

- `status` is one of the four strings above; no other values allowed.
- `tier_applies` lists the tiers the check is defined for. A check that is `na` for the current tier still appears in the report so the agent can confirm coverage; the agent omits these from the user-facing summary unless asked.
- `remediation.kind` is `mechanical` (script can be invoked unattended after human review) or `judgement` (agent must draft, not invoke).

## What this skill is *not*

- **Not a replacement for the SSDLC framework.** The framework lives in Canonical's GRC / OCISO documents; this skill summarises the parts a per-repo audit needs. Authoritative decisions belong with GRC.
- **Not a tool installer.** Checks assume the repo's tool config exists (zizmor, ruff, pre-commit, etc.); they look at config files, not binaries. Tool *adoption* is per-repo work, not this skill's job.
- **Not a one-size-fits-all CI policy.** Tier decides which checks apply; the agent must respect the tier and not push product-tier obligations onto personal repos.
- **Not a substitute for `skill-scanner`.** Run `skill-scanner` over this skill itself before each change to confirm hygiene; do not hand-edit findings out.
- **Not self-contained.** The checks are a package in `canonical/charm-tech-code`; this skill without it can explain the baseline but cannot measure a repo against it.
