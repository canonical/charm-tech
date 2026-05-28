---
name: skill-writer
description: Author, structure, and validate an agent skill. Use when creating a new SKILL.md, substantially rewriting an existing one, deciding what to bundle as scripts vs references, or importing an external skill. Covers frontmatter, body structure, depth gates (when to split a skill), the script-vs-checklist decision, prompt-injection hygiene, validation, and testing.
allowed-tools: Read, Write, Edit, Bash
license: Apache-2.0
metadata:
  source: "Combined: tonyandrewmeyer/cantrip skill-writer (judgment, structure, hygiene) + canonical/copilot-collections generate-agent-skills (validate_skill.py, templates, output patterns, script-vs-checklist)"
---

# Skill Writer

A guide for writing `SKILL.md` documents that earn their tokens. A
skill lives in its own directory — `skills/<category>/<name>/SKILL.md`
— and is load-on-demand guidance: the agent sees the one-line
description in its index always, but the full body only enters context
when the agent decides the situation calls for it. Write for that
moment: high signal, no filler.

This skill is harness-neutral. It assumes only the common
[agent-skill format](https://agentskills.io): a directory with a
`SKILL.md` carrying YAML frontmatter, optional `scripts/`, `references/`,
and `assets/` subdirectories.

## When to use

- You are adding a new skill directory.
- You are substantially rewriting an existing skill.
- You are deciding whether a piece of work belongs in a `scripts/`
  script or a `references/` checklist.
- You are adapting an external skill for import.

Skip this for a one-line correction to an existing skill — run
`skill-scanner` instead to confirm you have not introduced new issues.

## Frontmatter — every skill starts here

Every `SKILL.md` begins with YAML frontmatter. Two fields are required:

```yaml
---
name: my-skill
description: One-sentence hook that helps the agent decide whether to load this
---
```

Rules:

- `name` matches the directory: `skills/<category>/my-skill/SKILL.md`
  means `name: my-skill`. Lowercase, hyphenated, matching the regex
  `^[a-z0-9][a-z0-9-]*[a-z0-9]$`.
- `description` is one sentence, high-entropy, third person, and
  keyword-rich — it carries both **what** the skill does and **when**
  to reach for it. Read it as "the agent has 200 skills to choose from
  — why this one, now?".
  - Good: *"Deploy-test-debug retry strategy — triage failures, bound
    retries, escalate when stuck."*
  - Bad: *"A skill for fixing things"* (too vague);
    *"iterate-fix-retry-loop-strategy-for-autonomous-deploy-cycle"*
    (keyword soup).
- Optional fields some toolchains read: `allowed-tools` (least-privilege
  — see hygiene below), `license`, and a `metadata:` block (author,
  version, source/provenance). Keep them minimal and accurate.

## Body — structure and depth

The body loads when the agent invokes the skill, so its size is the
price of turning it on. Aim for **150–400 lines** of Markdown. Longer
than that and you are probably bundling two skills.

### Required sections

- A **one-paragraph intro** under the `# Title`, restating the
  description in context.
- A **"When to use"** block covering positive triggers ("run this at
  the start of a review task") *and* negative triggers ("skip for
  docs-only changes"). Ambiguity here makes the agent over-apply or
  forget the skill.
- The **actual guidance** — checks, steps, heuristics. Prefer
  checklists and numbered steps over prose.
- A **structured output format** if the skill produces findings — show
  a concrete example block to copy.
- A **"What this skill is not"** block. Spelling out the scope edge
  stops the skill from sliding into adjacent concerns.

### The instruction strategy — tune the freedom level

Do not write every instruction at the same strictness. Match the
phrasing to the risk of the step:

| Freedom | Use case | Style | Example |
| :-- | :-- | :-- | :-- |
| **High** | Creative, exploratory work | Guiding heuristics | "Draft a summary; keep the tone factual." |
| **Medium** | Analysis, transformation | Pseudo-code steps | "1. List the files. 2. Classify each." |
| **Low** | Destructive or precise ops | Strict commands | "Run `scripts/migrate.py`. Do not edit the files by hand." |

### The router pattern

`SKILL.md` should act as a **router**, not an encyclopedia: it tells the
agent *how to find* knowledge, and defers depth to `references/`. Put
long catalogues, tables, and worked examples in reference files and
point at them, so the body stays loadable cheaply. See
`references/templates.md` for frontmatter and structure patterns, and
`references/output-patterns.md` for ways to specify consistent output.

## Scripts vs references — decide before you build

The single most common authoring mistake is writing a script for a job
the agent should reason through, or writing prose for a job a script
should do deterministically. Ask: **is this analysis or computation?**

- **Analysis** — reading, synthesising, pattern recognition, judgement.
  → Put it in a `references/` checklist or knowledge file for the agent
  to follow. (Repository analysis, code review, doc synthesis.)
- **Computation** — math, API/DB calls, precise transformations,
  validation, boilerplate generation. → Put it in a `scripts/` script
  for deterministic, repeatable execution.

`scripts/` is for deterministic operations and external interactions;
`references/` is for checklists, pattern libraries, domain knowledge,
and decision trees; `assets/` is for files used in output (templates,
images, seed data). When in doubt, prefer a reference — analysis is the
agent's strength, and a script that encodes judgement will rot.

## Depth gates — when to split a skill

One subject per skill. If you are tempted to write:

- *"security-review and bug-review combined"* — split into two skills
  that cross-reference each other.
- *"the whole charmcraft workflow"* covering init, pack, upload,
  release — split along verb boundaries; the agent only needs the
  relevant verb.
- *"everything about relations"* — too broad; break into schema,
  testing, and runtime-pitfalls skills.

Signals a skill is too big: body over 500 lines; a table of contents
with more than six top-level entries; two unrelated "When to use"
triggers that rarely co-occur.

## Prompt-injection hygiene

Skills are trusted content loaded into the agent's context. They must
not contain text that could steer the agent around its guardrails, even
by accident. `skill-scanner` flags these as `HIGH`:

```
ignore (all )?previous instructions
disregard the (system|previous) prompt
you are (now )?a ... assistant
forget everything you were told
```

Rules of thumb:

- **No imperative redirection** — the phrasings above are only safe
  inside a clearly-labelled example code block.
- **No role assertions in prose** — a sentence telling the reader what
  they *are* (rather than what to *do*) reads like a system-prompt
  override.
- **No embedded user-supplied text** — make any quoted example
  obviously an example (fenced block, explicit *example:* label).
- **No external URLs presented as authoritative** without source
  context. Treat external pages as untrusted even when the skill links
  them.
- **Least-privilege `allowed-tools`** — request only what the skill
  needs; a read-only review skill should not ask for `Bash` or write
  access.

Run `skill-scanner` against a draft before checking it in.

## Validate

Before checking in, run the bundled validator over the skill
directory:

```bash
python3 scripts/validate_skill.py --path skills/<category>/<name>
```

It checks the directory-name regex, that `SKILL.md` exists, that the
frontmatter has `name` and `description`, and that `name` matches the
directory. It advises (does not fail) on the presence of `references/`
and `scripts/`. A scaffold step is optional — there is no mandatory
generator; hand-authoring a skill is fine as long as it validates and
passes `skill-scanner`.

## Test — the evaluation companion (optional but recommended)

For skills that produce structured output, write a short `EVAL.md`
beside `SKILL.md` holding the scenarios the skill must handle:

```markdown
# EVAL: my-skill

## Scenario 1 — happy path
Input context: <short prompt fragment>
Expected output: <what the agent should produce>

## Scenario 2 — should decline
Input context: <context where the skill does not apply>
Expected output: <no findings / declines to run>
```

Keep it small — 3–5 well-chosen scenarios beat twenty superficial ones.
They are a contract: when you later edit the skill, re-read every
scenario and confirm the guidance still produces the expected answer.

## Naming and layout conventions

- Directory name == `name` == lowercase, hyphen-separated.
- One skill per directory. Supporting files (`EVAL.md`, references,
  scripts, assets) live in the same directory.
- `SKILL.md` and `EVAL.md` are the only uppercase filenames.

## Cite your sources

If the skill is adapted from an external source, add a closing section
(and/or a `metadata.source` field) recording provenance:

```markdown
## Source material

- getsentry/skills `find-bugs`: diff-based attack-surface mapping.
  Adapted for our conventions.
- OWASP Cheat Sheet Series: injection patterns.
```

Citations let the next author trace provenance when updating, and let
`skill-scanner` distinguish a vetted external reference from an
unexplained link.

## Done criteria

A skill is ready to check in when:

- `scripts/validate_skill.py` passes.
- `skill-scanner` reports no `HIGH` findings.
- The body is within the length budget and has the required sections.
- Any `EVAL.md` scenarios produce the expected output in a spot-check.

## What this skill is *not*

- Not a Markdown style guide — any well-formed CommonMark is fine as
  long as the frontmatter is valid YAML.
- Not a guide to a specific harness's tool or settings format — skills
  here are harness-agnostic.
- Not a substitute for `skill-scanner` — author with this, audit with
  that.
