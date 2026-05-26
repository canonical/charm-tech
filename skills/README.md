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
npx skills add canonical/charm-tech --list                  # list available skills
npx skills add canonical/charm-tech                         # pick from a list, into this project
npx skills add canonical/charm-tech --all                   # install all of them, into this project
npx skills add canonical/charm-tech --skill code-review     # one, into this project
npx skills add canonical/charm-tech --skill code-review -g  # one, into your user/global skills
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

### `meta/` — skills and agent docs

| Skill | What it does |
| :-- | :-- |
| `skill-writer` | Author, structure, and validate a skill — frontmatter, body structure, depth gates, the script-vs-checklist decision, injection hygiene, validation, testing. |
| `skill-scanner` | Audit a skill for prompt injection, scope bloat, description drift, malicious scripts, secret exposure, and excessive permissions. Ships a static scanner. |
| `agents-md` | Maintain `AGENTS.md` (the cross-tool agent-docs standard) — minimal, high-signal agent instructions. |

## Related skills elsewhere

Skills our team finds useful that live in other repositories — not bundled
here, but worth installing from their source:

| Skill | Where | Notes |
| :-- | :-- | :-- |
| `documentation-review` (+ `documentation-build`, `documentation-diataxis`, `documentation-structure`, `documentation-style`, `documentation-verify`) | [canonical/copilot-collections](https://github.com/canonical/copilot-collections) | End-to-end documentation review. `documentation-review` orchestrates the other five, so install the whole set together. |

## Provenance and licences

Skills are vendored from several sources. Each skill is the single source of
truth for its own provenance and licensing: see the top-level `license` field
and `metadata.source` in its `SKILL.md` frontmatter, plus any bundled
`LICENSE` file (for example `security-review`, whose reference material
derives from the [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)).

## Contributing

Author new skills with **`skill-writer`** and audit them with
**`skill-scanner`** before opening a PR. Validate the layout with:

```bash
python3 skills/meta/skill-writer/scripts/validate_skill.py --path skills/<category>/<name>
```

Keep skills scoped to **maintaining our repos** (the criterion above), and
keep them harness-agnostic.

Every skill **must** declare a top-level `license` and a `metadata.source` in
its `SKILL.md` frontmatter. Set `license` to an
[SPDX identifier](https://spdx.org/licenses/) (e.g. `Apache-2.0`, `CC-BY-4.0`)
— it's a standard frontmatter field. Set `metadata.source` to the upstream URL
the skill was vendored or adapted from (use this repo's URL for skills
originally authored here); `source` is a custom field, so it lives under
`metadata`. Bundle a `LICENSE` file in the skill directory when the licence
requires the full text or the reference material adds its own terms.
