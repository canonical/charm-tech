# CLI Help Output

Normative rules for help output, condensed from
[Canonical's CLI help rules](https://github.com/canonical/cli-skill/blob/main/cli-skill/references/cli-help.md).

**MUST** = required. **SHOULD** = strongly recommended; deviations need justification.
**CAN** = optional.

## Entrypoints

- MUST provide help in both command and flag form.
- MUST accept at minimum: `tool help`, `tool --help`, `tool -h`, `tool help <command>`,
  `tool <command> --help`.
- SHOULD support `tool help --all` for a full command overview.

## Top-level help

- MUST print to stdout when the help request succeeds.
- MUST include: usage; a summary (one sentence or short paragraph); global options;
  commands or command groups; how to get command-level or topic-level help.
- SHOULD include the version in the header or first block.
- SHOULD group by topic when there are many commands.
- CAN suggest setup or configuration when the environment is uninitialised.

## Command help

- MUST include command-specific usage, the command's intent and default behaviour, and
  its options.
- SHOULD group options by function (for example: target, output, authentication).
- SHOULD include examples for non-trivial commands.
- CAN include related commands.

## Topic help

- If topic help exists, it MUST include the topic summary, the commands in the topic,
  and how to reach command-specific help.
- SHOULD give brief context explaining the domain.

## Flags and arguments

- Every flag MUST have a one-line description.
- Flags with constrained values MUST list the accepted values.
- Flags with defaults MUST show the default.
- Usage MUST distinguish required from optional arguments.
- If a flag has implications (for example `--devmode` implying weaker validation), help
  SHOULD state the implication.
- Flag names and vocabulary MUST match the CLI's grammar and existing commands.

## Guidance and recovery

- Help MUST include a clear path to more detail (`help <command>`, `help <topic>`, or
  equivalent).
- On an incomplete or invalid invocation, the CLI MUST print concise feedback to stderr
  *and* the corrected usage.
- Help SHOULD give actionable next steps for common setup failures (for example a
  missing config file).
- Help CAN include documentation URLs.

## Visual hierarchy

- Section ordering MUST be stable across commands, with clear section labels
  (`Usage`, `Global options`, `Examples`, `Related commands`).
- Alignment and indentation MUST allow fast column scanning of command and option lists;
  major sections MUST be separated by whitespace.
- Line widths SHOULD stay readable in a standard terminal; wrapped descriptions SHOULD
  use hanging indentation.
- Key actions SHOULD come near the top (usage, primary commands, high-value options).
- Colour or styling MUST NOT be required to understand the structure — monochrome output
  MUST remain readable. See the colour rules in the main skill.
- Commands in grouped lists SHOULD be visually distinct from their descriptions.
- Emphasis CAN mark warnings or suggestions, but SHOULD be sparse and consistent.

## Consistency

- Section naming SHOULD be consistent between top-level and command help.
- Terminology SHOULD be consistent across help pages (`command`, `option`, `topic`,
  `summary`).
- Equivalent option classes SHOULD be documented the same way across commands.
