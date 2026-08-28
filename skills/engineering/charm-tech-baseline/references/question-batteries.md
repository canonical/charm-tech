# AGENTS.md question batteries — schema and rationale

A **question battery** is a per-repo YAML file that captures, for each line of
that repo's `AGENTS.md` which earns its place, three things: the question an
agent would be asked, the answer that can be checked without a human reading
it, and the line the answer derives from.

Batteries ship with the `charm-tech-baseline` package in
[`canonical/charm-tech-code`](https://github.com/canonical/charm-tech-code),
under `src/charm_tech_code/charm_tech_baseline/assets/question-batteries/`,
one file per repo, named `<repo>.yaml`. The
`agents-md-battery` check validates a
battery against the repo it describes.

Design source: `roadmap/26.10/repo-setup/agents-md-validation.md` in
`canonical-work-queue` (Layer 2, implementation follow-up 2), as amended by
`agents-md-content-scope-decisions-2026-07-30.md`.

## Why batteries exist

Layer 2 of the AGENTS.md validation scheme is a behavioural eval: put the
question to a real agent with and without the file present, and classify the
line by what changes. It is the expensive, noisy layer, so it runs at authoring
time and **on suspicion** — when Layer 1 flags a line, when Layer 3 mines a
failure the line should have prevented, or when the repo changes underneath a
cache line.

The failure mode that costs is re-derivation: each time a trigger fires,
somebody re-reads `AGENTS.md`, re-invents the question, and re-guesses what
counts as a right answer. The battery writes that down once, at authoring time,
when the reasoning is fresh — so a triggered re-test is a lookup, not a
redesign.

## Two axes, deliberately kept apart

The single most important thing about this schema is that **grading an agent's
answer** and **verifying the entry still describes the repo** are different
questions, and an entry can be strong on one axis and empty on the other.

- `answer` says how a Layer 2 eval decides whether the agent got it right.
  It never touches the repo.
- `verify` says how *this* check decides the entry has not gone stale. It only
  touches the repo, never an agent.

Conflating them is the trap. "Conventional commits, no scopes" reads like an
un-checkable line, and the design doc calls it "not derivable from the tree at
all" — but that is a statement about `verify`, not about `answer`. The answer
is perfectly gradeable; what was in doubt was whether anything in the tree
still pins it. (In pytest-jubilant's case something does — see
`question-batteries/pytest-jubilant.yaml`.) Keeping the axes separate
means neither judgement gets smuggled into the other.

## File shape

```yaml
schema_version: 1
repo: pebble
upstream: canonical/pebble
source:
  agents_md_ref: chore/agents-md
  agents_md_sha: 40e3936c1a07ea3d2e1b792471d1aeaa2a76aa29
  agents_md_sha256: 44d99acd…
  seeded_from: roadmap/26.10/repo-setup/agents-md-validation.md (pebble table)
  seeded_on: 2026-08-19
entries:
  - id: single-gocheck-suite
    question: How do you run just the PebbleSuite gocheck suite?
    classification: cache
    source_line: go test ./internals/cli -check.f PebbleSuite
    answer:
      grade: command
      expect: go test ./internals/cli -check.f PebbleSuite
    verify:
      - kind: suite_in_package
        suite: PebbleSuite
        package: internals/cli
    ci_verifiable: true
```

### Top level

| Key | Required | Meaning |
|---|---|---|
| `schema_version` | yes | `1`. Bump only on a breaking change. |
| `repo` | yes | Repo name, matching the last segment of the origin URL. This is how the check finds the battery. |
| `upstream` | yes | `canonical/<repo>` — the repo the battery describes, even when validated against a fork. |
| `source` | yes | Where the source lines were read from (see below). |
| `entries` | yes | One entry per `AGENTS.md` line that earns its place. |

`source` records the exact file state the battery was seeded against:
`agents_md_ref` and `agents_md_sha` (branch and commit), `agents_md_sha256`
(digest of the `AGENTS.md` content), `seeded_from` (the design-doc table the
classifications came from) and `seeded_on`.

`agents_md_sha256` drives a **non-failing** drift signal: when the file's
current digest differs from the seeded one, the check reports
`agents_md_changed_since_seeding: true` in evidence. That is a Layer 2 re-test
trigger, not a defect — the file may have been improved. It is deliberately not
a failure, following the precedent set for intra-CI version skew in
`agents-md-content-scope-decisions-2026-07-30.md` §3: surface it as its own
evidence key rather than failing an unrelated check.

### Entry fields

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Stable slug, unique within the file. Referenced by re-test logs. |
| `question` | yes | What the agent is asked, in a fresh session with no file present. |
| `classification` | yes | `override` or `cache`, from the design doc's tables. |
| `source_line` | yes | The `AGENTS.md` text the answer derives from. |
| `answer` | yes | How to grade a reply (below). |
| `verify` | yes | How to confirm the entry still matches the repo (below). At least one assertion; use `kind: none` when there genuinely isn't one. |
| `ci_verifiable` | yes | Whether the answer's *truth* can be confirmed by an automated run. |
| `gated_by` | when `ci_verifiable: false` | What blocks it — the gating dependency, named. |
| `note` | no | Anything a re-tester needs that the fields don't carry. |

`classification` is the design doc's own vocabulary and carries its eviction
rule: an override is only ever removed when the underlying constraint
disappears; a cache line can be evicted on evidence that it has become cheap to
derive. The battery records which rule applies so a re-test does not have to
re-litigate it.

`source_line` is matched against `AGENTS.md` with **all whitespace collapsed**
on both sides, so a line that wraps in the file still matches a single-line
entry. Write it with single spaces.

### `answer.grade`

Three values. The first two are machine-gradeable; the third admits it isn't.

- **`command`** — the answer is a command line. `expect` holds the canonical
  form; grading is a whitespace-normalised match of `expect` against the
  agent's reply. Use for "what runs the unit tests" style questions.
- **`keywords`** — the answer is a fact. `require` lists strings that must all
  appear in the reply; `reject` lists strings that must not. Matching is
  case-insensitive unless `case_sensitive: true` is set on the entry (pebble's
  `cannot` / `Cannot` message-casing rule is the case where the distinction
  *is* the answer).
- **`judgement`** — the answer is a convention whose correct phrasing varies
  too much for keywords to grade honestly. `rubric` states what a correct reply
  must establish, for a human or an LLM grader. This is the honest bucket:
  forcing such an entry into `keywords` produces a grader that passes replies
  which miss the point and fails replies that make it.

`judgement` entries are still worth having — the question, the classification,
the source line and the repo anchor are all still mechanical. Only the grading
step needs a reader.

### `verify` kinds

Four kinds, each exercised by at least one seeded entry. The set is kept small
on purpose: an unexercised assertion kind is speculative machinery, which is
the exact complaint recorded against the symbol-reference pattern in the
scope-decisions doc.

- **`path_exists`** — `path` resolves in the repo.
- **`text_in_file`** — `pattern` (a Python regex) matches somewhere in `file`.
  This is the general mechanism, and it is also how a symbol reference is
  expressed: a word-boundary pattern against the file that should define it.
  There is no separate `symbol_in_path` kind, because it would be the same
  assertion with a narrower spelling.
- **`suite_in_package`** — `suite` appears in some `*.go` file under `package`.
  The canonical Layer 1 case: pebble's `PebbleSuite` documented against a
  package that no longer contains it.
- **`none`** — nothing in the tree pins this. Requires `reason`. An entry with
  `kind: none` is reported in evidence as not-anchored, and never fails.

Assertions are static: file contents, paths, identifiers. The battery check
deliberately does **not** execute commands — Layer 1's `agents-md-content`
check already classifies and runs them, and duplicating that here would double
the runtime and the environment surface for no new signal.

### `ci_verifiable`

`true` when the answer's truth can be confirmed by an automated run; `false`
when it cannot, with `gated_by` naming what blocks it (Docker, LXD + juju,
root, a GitHub setting not represented in the tree).

The boundary is the one settled in
`agents-md-content-scope-decisions-2026-07-30.md` §1: tree-mutating commands
are run, asserted clean and restored, so they count as verifiable;
environment-gated ones are not. Where that decision is settled but not yet
implemented in `agents-md-content.py`, the entry follows the decision and says
so in `note` — the batteries track the agreed boundary, not the current state
of one module.

A `false` entry is never dropped. It keeps its question, its classification and
its static anchor; what it loses is the runtime confirmation, and the battery
says exactly which dependency took it away. Silently omitting these would make
the battery look complete while hiding the lines nothing ever checks.

## Coverage

Batteries exist only for the six repos whose `AGENTS.md` has been through a
sweep and whose lines are classified in the design doc: pebble,
pytest-jubilant, charm-ubuntu, api_demo_server, charmlibs, concierge. The
other four (operator, jubilant, charmhub-listing-review, hyrum) have not
been through the Layer 2 authoring gate, so there is nothing to seed from.
The check reports `na` for a repo with no battery, which is the correct answer
rather than a gap.

Ten repos, not eleven: `canonical/charm-tech` is out of repo-setup scope, so
it is not counted here either.

## Adding or updating a battery

1. Run the Layer 2 authoring gate on the file first. The battery records the
   gate's output; it does not replace it.
2. Copy the `source_line` text verbatim from `AGENTS.md` (whitespace
   collapsed), never from the design doc's abbreviated table text.
3. Pick the weakest `answer.grade` that is still honest. `keywords` that only
   pass a reply which misses the point is worse than `judgement`.
4. Give every entry a `verify` assertion that would actually break if the repo
   changed underneath it. An assertion that can never fail is noise.
5. Update `source.agents_md_sha`, `agents_md_sha256` and `seeded_on`.
