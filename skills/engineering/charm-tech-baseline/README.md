# charm-tech-baseline skill

Reusable AI-agent skill that audits a single repository against the Canonical Charm Tech baseline and, where the gaps are mechanical, fixes them.

## Why this exists

The 26.10 cycle's baseline work produced a set of data: which SSDLC requirements apply at which tier, what carve-outs we accept, which best-of-class tools we measured and skipped, which sweeps we ran and which we retracted. None of that is useful if it lives only as a PROGRESS log: the next time a new repo lands the work has to be re-derived.

This skill consolidates the cycle's output into a form an AI agent can load on demand and apply to one repo at a time.

## How to use it

```bash
# audit
scripts/check.py                                 # auto-detect tier, JSON output
scripts/check.py --tier=personal --format=markdown
scripts/check.py --only=security-md,dependabot

# fix (mechanical only — agent must judge)
scripts/fixes/add-security-md.py
scripts/fixes/add-dependabot.py
```

The skill itself is the canonical entry point — see [`SKILL.md`](SKILL.md). An AI agent loads `SKILL.md`, runs `check.py`, reads the JSON report, and uses the references to explain gaps and propose remediation.

## Layout

```
SKILL.md                   # the skill (router; loaded by the agent)
README.md                  # this file (human-readable)
references/                # static knowledge; loaded by the agent on demand
  ssdlc-framework.md       # SEC0023 matrix + per-requirement summary
  decisions.md             # settled carve-outs
  skipped-tools.md         # tools we measured and skipped, with the basis
  sweep-history.md         # sweeps that landed; sweeps that were retracted
  open-investigations.md   # items waiting on external triggers
assets/                    # file templates used by fix scripts
scripts/                   # deterministic checks + fixes
  check.py                 # umbrella runner; emits JSON or markdown
  detect-tier.py           # remote-URL inspection → tier name
  checks/                  # one script per control
  fixes/                   # one script per mechanical remediation
  lib/                     # shared Python helpers (common.py)
```

## Agent-generic

The skill follows the common [agent-skill format](https://agentskills.io) (YAML frontmatter + Markdown body + standard subdirectories). It does not reference agent-specific tools, slash commands, or harness features. Any agent that can read files, run shell commands, and interpret JSON can use it.

## Maintenance

When a future cycle's baseline work changes a decision:

1. Update the relevant `references/*.md` entry (note the date and the new evidence).
2. If a new check is warranted, add a script to `scripts/checks/` and a matching entry to `SKILL.md`'s coverage table.
3. If a previously-skipped tool now has measured value, update `skipped-tools.md` *with the new measurement*; do not silently re-recommend.
4. Re-run `skill-scanner` and `scripts/validate_skill.py`.
