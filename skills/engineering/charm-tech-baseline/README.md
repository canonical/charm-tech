# charm-tech-baseline skill

Reusable AI-agent skill that audits a single repository against the Canonical Charm Tech baseline and, where the gaps are mechanical, fixes them.

## Why this exists

The 26.10 cycle's baseline work produced a set of data: which SSDLC requirements apply at which tier, what carve-outs we accept, which best-of-class tools we measured and skipped, which sweeps we ran and which we retracted. None of that is useful if it lives only as a PROGRESS log: the next time a new repo lands the work has to be re-derived.

This skill consolidates the cycle's output into a form an AI agent can load on demand and apply to one repo at a time.

## Where the code lives

The checks and fixes are a Python package in [`canonical/charm-tech-code`](https://github.com/canonical/charm-tech-code), under `charm-tech-baseline`, and the skill drives it through `uvx`. What stays here is what an agent reads: when a check applies, what a finding means, which decisions are settled, and which tools were measured and skipped.

The split is deliberate. Code that has to be run wants a lockfile, a test suite and CI, none of which a directory of loose scripts inside a skill was ever going to get. Prose that an agent reads wants to sit beside the other skills. Neither half is much use without the other, so each names the other.

```bash
uvx --from "git+https://github.com/canonical/charm-tech-code@<40-char-sha>#subdirectory=charm-tech-baseline" \
  charm-tech-baseline check --tier=product
```

Pin the SHA. There is no release process in that repository and the SHA is the version, which is the same trust decision every pinned `uses: actions/checkout@<sha>` line already makes.

## Layout

```
SKILL.md                   # the skill (router; loaded by the agent)
README.md                  # this file (human-readable)
references/                # static knowledge; loaded by the agent on demand
  ssdlc-framework.md       # SEC0023 matrix + per-requirement summary
  decisions.md             # settled carve-outs
  skipped-tools.md         # tools we measured and skipped, with the basis
  open-investigations.md   # items waiting on external triggers
  question-batteries.md    # AGENTS.md question-battery schema and rationale
```

## Agent-generic

The skill follows the common [agent-skill format](https://agentskills.io) (YAML frontmatter + Markdown body + standard subdirectories). It does not reference agent-specific tools, slash commands, or harness features. Any agent that can read files, run shell commands, and interpret JSON can use it.

## Maintenance

When a future cycle's baseline work changes a decision:

1. Update the relevant `references/*.md` entry (note the date and the new evidence).
2. If a new check is warranted, add a module to `charm-tech-baseline/src/charm_tech_code/charm_tech_baseline/checks/` in `canonical/charm-tech-code`, with a test, and a matching entry in `SKILL.md`'s coverage table here. The two land as separate PRs, so add the check first and the table row once it has merged.
3. If a previously-skipped tool now has measured value, update `skipped-tools.md` *with the new measurement*; do not silently re-recommend.
4. Re-run `skill-scanner` over this skill.
