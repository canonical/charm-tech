---
name: cli-standards
description: Canonical CLI design standards. Use when designing, implementing, or reviewing command-line interfaces. Covers grammar, commands, flags, parameters, feedback, colours, tables, verbosity, and tone of voice.
license: CC-BY-4.0
compatibility: universal
allowed-tools: Read Grep Glob
metadata:
  source: https://github.com/tonyandrewmeyer/charming-with-claude
---

# Canonical CLI Standards

These standards define how Canonical CLI tools should look and behave. They originate from discussions with Canonical's senior tech leads and define best practice. All points must be strongly considered before contributing CLI code at Canonical.

For full do/don't examples of every rule, see [examples.md](references/examples.md).

---

## Grammar + Vocabulary

### Commands are verbs
Every command that acts on a primary object must be a verb (for example: `install`, `refresh`, `login`). Choose verbs that imply the object type they act on.

### Commands are logically grouped
Group commands that act on the same object type or domain (for example: build lifecycle vs. store management).

### Verb-noun form
When verbs alone are insufficient to distinguish objects, use `verb-noun` form:
```
snap set-quota
```

### Listing secondary objects
Use the plural noun as shorthand instead of `list-foobar`:
```
snap services        # not: snap list-services
snap list            # for listing primary objects (snaps)
```

### Showing state
- Use `status` over `show-status`
- Use `foobar-status` over `show-foobar-status`
- Use `foobar` over `show-foobar`

### Standard commands

| Command | Purpose |
|---------|---------|
| `tool init` | Local initialisation |
| `tool bootstrap` | Distributed initialisation (cluster, VM, cloud) |
| `tool list` | Overview of all primary type instances |
| `tool foobars` | Overview of all secondary type instances |
| `tool show <id>` | Details for one primary instance |
| `tool status` | Current tool state |
| `tool start/stop` | Services, long-running processes |
| `tool enable/disable` | Primary type, feature |
| `tool get/set/unset` | Configuration |
| `tool create-foo <id>` | Create secondary object |
| `tool delete-foo <id>` | Delete secondary object |
| `tool help` | Show help |
| `tool version` | Show release version |

### Sublevels
At most **one** sublevel may be used. Alternatively, split into separate tools with associated names:
```
cmd cluster config --secret "$(cat secret.txt)"
# OR
cmd-cluster config --secret "$(cat secret.txt)"
```

---

## Parameters, Flags and Options

### Positional parameters
Only use when the meaning of each position is natural and easily memorisable:
```
cp sourcefile destfile      # clear directional meaning
```

### Flags
- **Short flags** (`-R`): only for frequent actions easily implied from context
- **Long flags** (`--recursive`): more descriptive, for less frequent actions
- **Do not offer both** short and long for the same action
- Short flags must allow stacking: `-yadf` = `-y -a -d -f`
- Flags must not depend on ordering

### Commonly used flags
All tools must support at minimum: `--help`

### Flags with values
- Must support separation by whitespace: `--verbosity debug`
- May support separation by `=`: `--rsh="ssh -p 2222"`

### Flags accepting multiple values
Two accepted patterns — do not provide both:
```
# Repeated (singular name):
tool do-foo --channel=edge --channel=beta

# Comma-separated (plural name):
tool do-foo --channels=edge,beta
```

### Key=value arguments
```
tool do-foo --bar key=value
charmcraft release my-charm --channel=edge --resource foo=7 --resource bar=1
```

### `--` separator
Use `--` to separate tool flags from a passed command line:
```
multipass exec docker -- snapcraft --help
```

---

## Feedback

### Errors, warnings, and success messages
- **Errors**: something went wrong, non-successful completion
- **Warnings**: non-ideal state, non-vital step failed, deprecation
- **Success**: command or step completed successfully

All messages must be human-readable, short, and succinct.

### Colour usage
- Use colour for visual hierarchy only — never as the sole mechanism conveying information
- Only enable colour when the output stream supports it
- Disable colour when `NO_COLOR` is set or output is redirected
- Limit to ANSI colours; use bold for additional hierarchy
- Avoid green on white and blue on black for longer text

---

## Tabular Data

### Format
- Column delimiter: two spaces
- Headers: left-aligned, UPPER CASE, bold
- No ASCII line decorations
- Show headers by default; support `--no-headers`
- No spaces within cells (spaces delimit columns)
- Use short column names (for example: `REV` not `REVISION`)
- Optional `NOTES` column always last

### Empty states
Show a clear message instead of empty headers:
```
$ snap list
No snaps installed.
```
Empty state message goes to stderr; exit code remains zero.

For machine-readable output, output the zero value:
```
$ foo list --format=json    # (empty)
$ foo list --format=yaml
items: []
```

---

## Verbosity Levels

| Mode | Flag | Detail |
|------|------|--------|
| **Quiet** | `--quiet` | No output. Only errors for failed operations. |
| **Brief** | `--brief` (CLI default) | Critical info only. Progress and success/failure. |
| **Verbose** | `--verbose` (daemon default) | Descriptive detail about execution steps. Proper capitalisation and punctuation. |
| **Debug** | `--verbosity=debug` | Developer-level detail about internal execution. |
| **Trace** | `--verbosity=trace` | Code-level execution detail (debugger-equivalent). |

### Timestamps
Use ISO 8601: `2024-06-29T03:24:20Z`

### Ephemeral feedback
- Use line-overwriting only in interactive tty sessions, never when piped
- Use ephemeral feedback for intermediate steps where the final outcome is understood (for example: `snap remove`)
- Use non-ephemeral (new line) for steps with meaningful consequences (for example: machine allocation)

---

## CLI Copy and Tone of Voice

### Principles
- **Concise**: stripped of excess, no clutter
- **Precise**: exact terminology, critical details
- **Clear**: unambiguous, immediately understandable

### Terminology consistency
CLIs and UIs must use identical terminology. Define a single source of truth per product.

### Rules
- Use **passive, succinct** sentences for missing arguments: `Invalid URL: "htp://foo.bar"`
- Use **active, direct, friendly** tone for helpful information — without being apologetic
- Use **"cannot"** instead of "didn't / couldn't / failed to / unable to"
- **Do not** use contractions (`can't` → `cannot`)

```
# GOOD
error: cannot establish the connection

# BAD
error: connection couldn't be established
Oops, something went wrong.
```
