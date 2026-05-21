---
name: go-standards
description: Canonical Go coding standards and best practices. Use when writing, reviewing, or refactoring Go code. Covers formatting, naming, errors, functions, structs, interfaces, and testing conventions.
argument-hint: [topic]
license: default
compatibility: universal
allowed-tools: Read Grep Glob
---

# Canonical Go Best Practices

These standards define "Canonical Go" style. They complement [Effective Go](https://go.dev/doc/effective_go) and [Google's Go style guidelines](https://google.github.io/styleguide/go/decisions). All new code must abide by `go fmt` and `go vet`.

For full code examples of every rule, see [examples.md](examples.md).

---

## Cosmetic Discipline

### Braces
- No extra newlines between braces. Use compact struct/slice literal style:
```go
tests := []struct{
    name string
}{{
    name: "foo",
}, {
    name: "bar",
}}
```

### Spacing (blank lines)
Use blank lines **semantically**, not aesthetically. Rules:
- Declaration + immediate use/check = **no** blank line (strongly associated)
- Declaration used across multiple blocks = blank line after declaration
- Declaration + check (≤3 lines) = no blank line; check >3 lines = blank line after

```go
// GOOD: declaration and check are strongly associated
x, err := foo()
if err != nil {
    return nil, err
}
```

### Grouping
- Don't interleave unrelated code. Group strongly interdependent sections.
- Declare closures close to where they're used if they capture values.
- If no captures needed, define at top of highest scope to make that obvious.
- Consider whether a closure is needed at all — prefer simple top-to-bottom flow.

---

## Naming Discipline

Names should:
- **Say what they mean** — `copy(dest, source)` not `copy(x, y)`
- **Have consistent word order** — if the API uses `verbNoun`, keep using `verbNoun`
- **Be concise** — shorter is better when unambiguous
- **Use simple words** — prefer short common words over long rare ones
- **Be unified** — one name per concept across the codebase
- **Avoid including types** — `needle` not `needleString` (unless disambiguating)
- **Use US spelling** (company policy)

If a good name can't be found, the API probably needs refactoring.

Take **extreme** care with exported names — they can't be changed without breaking consumers.

---

## Error Discipline

### Error messages
- Start with a lowercase verb, usually prefixed with "cannot"
- Keep messages concise and consistently phrased
- Lowercase first letter (errors may be wrapped, capitals mid-line look bad)
- Uppercase for acronyms (TCP, OS) and product names (LXD)
- Tailor message detail to the expected reader (developer vs end-user)
- Avoid repeating context that will be added by wrapping higher up the stack

```go
// GOOD
return fmt.Errorf("cannot connect to %s: %v", addr, err)

// BAD
return fmt.Errorf("Connection to server failed: %v", err)
```

### Custom error types
- Use custom error types **only** when the caller can take specific recovery action.
- Add public fields to expose data needed for error handling decisions.
- For unrecoverable errors, use `errors.New` or `fmt.Errorf`.

### Error wrapping: `%w` vs `%v`
- **`%w`** (wrap): Use when consumers should be able to inspect/match the inner error via `errors.Is`/`errors.As`. Beware: this makes the inner error part of your public API.
- **`%v`** (paste): Use for unrecoverable errors where consumers should not inspect the inner error. This is the safer default.
- Don't wrap at every function boundary — only at meaningful abstraction layer boundaries. Over-wrapping produces long, low-information error chains that expose stack internals.

### Panic calmly
- Prefer `error` returns over panics.
- Panics are acceptable when:
  - The caller misused the API (prefix with `internal error:`)
  - Error handling is impossible (e.g., `init` functions, global `var` declarations)
- Provide `Foo() (Value, error)` + `MustFoo() Value` pairs when both contexts are needed.
- Use `panic("unreachable")` to mark logically impossible code paths (rare, but makes control flow explicit).

---

## Code Discipline

### Pyramids of doom
- Max 3 levels of indentation. Refactor deeper nesting into functions.
- Convert error-returning branches into early-return preconditions.

### Inline `if`
- `if err := fn(); err != nil` is fine for short expressions.
- If the initializer is long/multi-line, break it out into a separate statement.

### Variable declaration
Prefer in this order:
1. `foo := expr` — default choice, even for explicit zero values (signals the zero value may be read before reassignment)
2. `var foo type` — when the zero value is never read before assignment
3. `var foo = expr` — avoid (verbose, no advantage over `:=`)
4. `var foo type = expr` — avoid (verbose; use `foo := type(expr)` for type assertion)

Put `var` declarations first, don't mingle with `:=`.

### Interface implementation assertion
Use compile-time checks when a type must implement an interface:
```go
var _ io.Reader = &MyFile{}
var _ io.Writer = &MyFile{}
```

### Struct population (unexported)
- Always use named fields (never anonymous initialization)
- Match variable names to field names when copying values
- Either compute all fields inline OR pre-compute all into variables — no mixing
- Keep field order consistent with the type definition
- Single-line structs: only if ≤~25 characters of fields

### Struct population (exported)
- Don't expose structs for direct population — use setter/builder methods instead.
- Exception: parameter/option structs where users pass data (not touch internals).

### Comments
- Comments should explain **why**, not **what** (the code already says what).
- Sentences end with a full stop.
- Implementation details go in function body comments, not doc comments.
- Use top-of-file comments to tie together complex cross-function patterns.

### Global state
- Almost never use global state. If you think you need it, you almost certainly don't.

---

## Function Discipline

### Function docs
- Start doc comment with the function name: `// Foo transforms...`
- 1-2 concise sentences covering purpose and when/why to use it.
- Don't list parameters (names+types should be self-explanatory). Don't describe implementation.
- Use "the" (definite article) when referring to parameters, not "a".
- All exported functions require doc comments. Unexported functions used across files require them unless trivial.
- Don't document who calls a function — document what it does.

### Function naming
- Getters are nouns; other functions contain verbs.
- Maintain consistent word order with surrounding API.
- Watch for noun/verb ambiguity: `SizeEstimate` (getter) vs `EstimateSize` (action).

### Nil arguments
- Don't defensively nil-check every nillable argument — that's the caller's responsibility.
- If nil is valid/optional, document it and check for it.

### Passing structs
- Prefer pointer parameters and return values for structs:
  - Promotes consistent types and semantics across the API
  - Allows optional parameters
  - `return nil, err` is clearer than `return SomeStruct{}, err`

### Return values
- Return computed values, don't take output pointers (this isn't C).
- When error is nil → return valid values. When error is non-nil → return zero values.
- `return nil, nil` is misleading. `return foo, err` (non-nil both) is misleading.

### Return value naming
- Name returns when it adds information. `ok` for success booleans, `err` for errors.
- Don't name when redundant: `(err error)` adds nothing over `error`.

### Receivers
- Always name receivers, even when unused (consistency).
- Use consistent receiver types — always pointer OR always value, not mixed.
- Avoid nil receiver patterns; use a helper function instead.

### Bare returns
- Don't use bare returns. They sacrifice clarity for brevity.
- Exception: deferred functions that must modify named return values (rare, born of necessity).

---

## Test Discipline

- Tests should be self-contained — no ordering dependencies between tests.
- Use table-driven tests to share setup/teardown across similar cases.
- Use zero values for "not applicable" fields (e.g., omit `expectedOutput` when `expectedError` is set).
- Group happy-path tests first, error tests last.
- Don't over-abstract test helpers — readers shouldn't need to study a test API to understand tests.
- Compact brace style for test table entries (see [examples.md](examples.md)).

```go
tests := []struct{
    name   string
    input  any
    expect string
}{{
    name:  "valid input",
    input: 123,
}, {
    name:   "invalid input",
    input:  nil,
    expect: "input required",
}}
```
