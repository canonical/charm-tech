# Charm Tech documentation style guide

This is the documentation and docstring style we use across Charm Tech projects,
regardless of the programming language. For language-specific code style, see
[python.md](./python.md) and [go.md](./go.md).

New docs should follow these guidelines, unless there's a good reason not to.
Sometimes existing docs don't follow these, but we're happy for them to be
updated to do so (either all at once, or as you change nearby text).

Of course, this is just a start! We add to this list as things come up in code
review; this list reflects our team decisions.

## Docs and docstrings

### English spelling

**Note:** [Canonical's documentation style guide](https://documentation.ubuntu.com/style-guide)
has changed to American English ("Canonical previously used UK English, but has
changed to US English"). Our docs haven't migrated yet, so for now we keep
**British** spelling for consistency with our existing content — for example
"colour" rather than "color", "labelled" rather than "labeled", "serialise"
rather than "serialize". Expect this recommendation to flip to American English
in due course.

Better still, where you can, **reword to avoid words that are spelt differently**
in British and American English — then the text reads correctly under either
convention and won't need touching when we migrate. For example, prefer "encode
the config as JSON" over "serialise the config", or "this changes how the charm
behaves" over "this changes the charm's behaviour".

When you're dealing with code and APIs, use whatever spelling the code or API
offers — match it exactly. For example, `pytest.mark.parametrize` and
`color: #fff` stay as they are.

### Spell out abbreviations

Abbreviations and acronyms in docstrings should usually be spelled out, for
example, "for example" rather than "e.g.", "that is" rather than "i.e.", "and so
on" rather than "etc", and "unit testing" rather than UT.

However, it's okay to use acronyms that are very well known in our domain, like
HTTP or JSON or RPC.

## How to write great documentation

- Use short sentences, ideally with one or two clauses.
- Use headings to split the doc into sections. Make sure that the purpose of
  each section is clear from its heading.
- Avoid a long introduction. Assume that the reader is only going to scan the
  first paragraph and the headings.
- Avoid background context unless it's essential for the reader to understand.

Recommended tone:

- Use a casual tone, but avoid idioms. Common contractions such as "it's" and
  "doesn't" are great.
- Use "we" to include the reader in what you're explaining.
- Avoid passive descriptions. If you expect the reader to do something, give a
  direct instruction.

Where docs are published, we organise the pages according to
[Diátaxis](https://diataxis.fr/) (tutorials, how-to guides, reference, and
explanation).
