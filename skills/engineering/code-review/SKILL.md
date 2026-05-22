---
name: code-review
description: Canonical code review guidelines. Use when reviewing code, preparing PRs for review, or giving feedback on changesets. Covers tone, procedures, code quality, changeset scope, and review process.
license: CC-BY-4.0
compatibility: universal
allowed-tools: Read Grep Glob
metadata:
  source: https://github.com/tonyandrewmeyer/charming-with-claude
---

# Canonical Code Review Guidelines

These guidelines define how code reviews should be conducted at Canonical. They focus on broadly applicable review techniques that are relevant to all projects.

Based on spec PE-ALL-005.

---

## Soft Skills

### Tone
- Review the **submission**, not the author. Avoid "you did this wrong."
- Prefer "this could be improved by…" or "this doesn't seem right to me…"
- Be **constructive** — suggest how something may be improved
- For non-critical suggestions, make clear it's informational, not a change request: "I might have done this differently for these reasons…"
- Avoid being overtly negative, even if something is poor quality
- Remember: review is a **learning experience** for both author and reviewers

### Label comments by intent
Prefix each comment with its intent so the author can tell blocking issues from
optional ones at a glance (see [Conventional Comments](https://conventionalcomments.org/)):
- `blocking:` — must be resolved before merge
- `suggestion:` — a proposed improvement; the author decides
- `nit:` — minor/stylistic; non-blocking by definition
- `question:` — seeking clarification, not necessarily a change
- `praise:` — call out something done well
Add `(non-blocking)` to any label when the distinction isn't obvious from the prefix.

### Self-review
- Before submitting changes you authored, review your own diff first
- Catches spurious changes, incomplete work, and things missed while editing
- Reviewing your own diff changes how you reason about the code — read it as the reviewer will

---

## Procedures

- If **CI isn't passing**, investigate why before approving
- Commits/PRs should **reference their tracking ticket** where one exists (e.g. a link to the issue)
- Pull request descriptions must be **usefully descriptive** — "Fixed Bug 12345" is not sufficient; include a sentence or two about what changed and why

---

## Code Quality

- All patches must follow the **code style and conventions** of the appropriate project
- Look for cases where end-user function behaviour **diverges from upstream** — ask for clarification and push for upstreamable implementations

---

## Changeset Size and Scope

### Size
- Large changesets are complex and difficult to review
- Large changesets can usually be **split** into smaller commits or separate tickets
- They tend to combine related but not strictly connected changes
- Use pragmatism — sometimes a large changeset is genuinely necessary
- When a changeset is too large, still review it in full, but **recommend splitting** it (a `suggestion:`, not a blocker) — note where the natural seams are

### Scope
- Does it address things **not needed** in the ticket? Call them out — good changes can go in a separate commit/ticket
- Does it address things **not mentioned** in the commit message?
- Does it make unintentional changes that might cause bugs?

### Completeness
- Watch for **missing files** (forgot to `git add`)
- Missing files do not always cause CI failures (e.g. a comment referencing a README that was not committed)

---

## Recommended Review Process

1. **Read the ticket(s)** — understand what should be done, verify referenced tickets are correct
2. **Skim** commit messages and code for formatting, size, and scope issues
3. **Dive deeper**:
   - Check **leaf functions** first (no calls to other modified functions)
   - Work upward toward functions with more modified invocations
4. **Walk through** new control flow, computational, or memory mapping behaviour — consider optimisation opportunities, especially on hot paths
5. Use **linters and static analysis** as pre-commit hooks where available

---

## Project-Specific Considerations

For projects applying patches not yet upstreamed:
- Patches should be of **upstream quality** and submitted upstream simultaneously
- Include DEP3-style `Forwarded:` tags with links to upstream submissions
- Ubuntu-originated patches: mark `UBUNTU: SAUCE:`
- Partner-originated patches: mark `<VENDOR>: SAUCE:`
