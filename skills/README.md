<!--
  Copyright 2026 Canonical Ltd.
  See LICENSE file for licensing details.
-->

# Charm Tech Skills

Curated [agent skills](https://agentskills.io) for the **Charm Tech team**.

These skills target **maintaining our own repositories** — `ops`/operator,
pebble, jubilant, pytest-jubilant, concierge, charmlibs, the charmcraft
tooling, and friends — *not* authoring charms. Charm-authoring skills
(charmcraft/jhack/juju workflows, scenario/jubilant test writing, ingress,
observability, 12-factor, …) live elsewhere; see
[cantrip](https://github.com/tonyandrewmeyer/cantrip),
[charming-with-claude](https://github.com/tonyandrewmeyer/charming-with-claude),
and [canonical/skills-playground](https://github.com/canonical/skills-playground).

Every skill here is **harness-agnostic**: it works with any
[skills-compatible agent](https://agentskills.io/clients) (Claude Code,
GitHub Copilot CLI, Cursor, Codex, Gemini CLI, Windsurf, …) and does not
assume a particular coding harness.

## Installing

### With the `skills` CLI (recommended)

```bash
npx skills add canonical/charm-tech --list             # list available skills
npx skills add canonical/charm-tech                    # install all of them
npx skills add canonical/charm-tech --skill code-review        # one, into this project
npx skills add canonical/charm-tech --skill code-review -g     # one, into your user/global skills
```

### Manually

Each skill is a self-contained directory. Copy the one you want into your
agent's skills folder:

```bash
# Claude Code — user-level (all projects) or project-level
cp -r skills/engineering/code-review ~/.claude/skills/code-review
cp -r skills/engineering/code-review <your-project>/.claude/skills/code-review
```

For other agents, copy into that agent's skills directory instead. The
`<category>/` grouping below is organisational only — the skill name is what
the tooling keys on, so nesting depth does not matter.

## Available skills

### `engineering/` — code, standards, security, CI

| Skill | What it does |
| :-- | :-- |
| `code-review` | Canonical code-review guidelines — tone, procedure, changeset scope, review process. |
| `go-standards` | Canonical Go coding standards (formatting, naming, errors, structs, interfaces, testing). For pebble and concierge. |
| `cli-standards` | Canonical CLI design standards — grammar, flags, feedback, tables, verbosity, tone. For charmcraft/pebble/jubilant CLIs. |
| `security-review` | General OWASP-style code security review with per-language and infrastructure guides, confidence gating, and exploitability verification. |
| `gha-security-review` | GitHub Actions security review — pwn requests, expression injection, credential theft, supply-chain attacks, with concrete PoCs. |
| `iterate-pr` | Drive a PR to green: fix CI failures, address review feedback, push, and wait, on a loop. |

### `documentation/` — docs review

| Skill | What it does |
| :-- | :-- |
| `documentation-review` | Orchestrates an end-to-end documentation review (build, Diataxis, structure, accuracy, style) and renders a consolidated report. See note below. |

### `meta/` — skills and agent docs

| Skill | What it does |
| :-- | :-- |
| `skill-writer` | Author, structure, and validate a skill — frontmatter, body structure, depth gates, the script-vs-checklist decision, injection hygiene, validation, testing. |
| `skill-scanner` | Audit a skill for prompt injection, scope bloat, description drift, malicious scripts, secret exposure, and excessive permissions. Ships a static scanner. |
| `agents-md` | Maintain `AGENTS.md` (the cross-tool agent-docs standard) — minimal, high-signal agent instructions. |

## Notes

- **`documentation-review` is the orchestrator only.** It invokes five atomic
  skills (`documentation-build`, `documentation-diataxis`,
  `documentation-structure`, `documentation-style`, `documentation-verify`)
  that are **not** bundled here. Install them from
  [canonical/copilot-collections](https://github.com/canonical/copilot-collections)
  if you want the full pipeline; otherwise treat this as a review checklist.
- **`iterate-pr`** references `${CLAUDE_SKILL_ROOT}` (a Claude Code env var)
  when locating its helper scripts. On other harnesses, point at the script
  paths directly.

## Provenance and licences

Skills are vendored from several sources; attribution is preserved in each
skill's frontmatter (`metadata.source`) and any bundled `LICENSE`.

| Skill | Source | Licence |
| :-- | :-- | :-- |
| `code-review`, `go-standards`, `cli-standards` | [charming-with-claude](https://github.com/tonyandrewmeyer/charming-with-claude) | CC BY 4.0 |
| `documentation-review` | [canonical/copilot-collections](https://github.com/canonical/copilot-collections) | Apache-2.0 |
| `security-review` | locally-installed; reference material derived from the [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) | Apache-2.0 / refs CC BY-SA 4.0 (see skill `LICENSE`) |
| `gha-security-review`, `iterate-pr`, `agents-md` | locally-installed | Apache-2.0 |
| `skill-writer` | combined: [cantrip](https://github.com/tonyandrewmeyer/cantrip) + [copilot-collections](https://github.com/canonical/copilot-collections) | Apache-2.0 |
| `skill-scanner` | combined: [cantrip](https://github.com/tonyandrewmeyer/cantrip) + locally-installed scanner | Apache-2.0 |

## Contributing

Author new skills with **`skill-writer`** and audit them with
**`skill-scanner`** before opening a PR. Validate the layout with:

```bash
python3 skills/meta/skill-writer/scripts/validate_skill.py --path skills/<category>/<name>
```

Keep skills scoped to **maintaining our repos** (the criterion above), and
keep them harness-agnostic.
