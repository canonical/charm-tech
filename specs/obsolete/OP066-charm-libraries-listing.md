# OP066 — Charm Libraries Listing

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Informational |
| Created | 9 Jun 2025 |

## Abstract

Charm library discovery could use some love. This spec outlines a plan for a library listing owned by Charm Tech. It would likely be hosted on [canonical-charmlibs.readthedocs-hosted.com](http://canonical-charmlibs.readthedocs-hosted.com). There is a [PR](https://github.com/canonical/charmtech-charmlibs/pull/73) and [preview docs build](https://canonical-charmlibs--73.com.readthedocs.build/reference/non-relation-libs/) available with more up to date design than described in the spec.

## Rationale

Library discovery can be tricky on Charmhub, with libraries being listed under specific charms, and the distinction between relation libraries, internal libraries, and general purpose libraries not always being clear. Packages hosted on PyPI can be searched, and we have the charmlibs namespace for libraries going forward, but there are a number of older and newer packages that don't use the namespace - plus the phrase 'works like a charm' is not exclusive to charming. Discoverability is also hampered by libraries being hosted in multiple places - Charmhub, PyPI, and potentially git urls as well.

## Specification

### Non-relation libs

The main feature of the library listing would be a table like this one. This table would list non-relation, non-internal libraries, whether hosted on Charmhub, or Python packages hosted elsewhere.

Emojis are used to save space and hopefully improve readability and searchability - for example, search for'🖥️' or '🖥️machine' to get libraries for machine charms, rather than searching for 'machine' to get libraries that mention machine anywhere. A description of the emojis would appear on the page, e.g.:

| A ✅ indicates a library recommended by Charm Tech for use in modern charms, while a 🪦 indicates a legacy library with a better alternative that should be used by new charms. ⬜ is a placeholder indicating neither. 📚 is a link to any separate documentation for the library and ⌨️ is a link to the source code repository for the library. |
| :---- |

|  | Library | Type | Substrate | Description |
| :---- | :---- | :---- | :---- | :---- |
| ✅ | [charmlibs.pathops](https://pypi.org/project/charmlibs-pathops) [📚](https://canonical-charmlibs.readthedocs-hosted.com/) [⌨️](https://github.com/canonical/charmtech-charmlibs) | PyPI | 🖥️machine ☸️K8s | Substrate agnostic path operations. |
| 🪦 | [operator_libs_linux.v2.snap](https://charmhub.io/operator-libs-linux/libraries/snap) [⌨️](https://github.com/canonical/operator-libs-linux) | Charmhub  | 🖥️machine | Legacy library for snap operations. New charms should use charmlibs.snap |

### Relation libs

Relation libs are distinctly different from non-relation libs in two key ways. Firstly, while a non-relation lib is an implementation detail of a charm's internal workings, a relation lib is an implementation detail of how a charm provides (or requires) a Juju relation endpoint for interacting with other charms. Secondly, while a non-relation lib's working are entirely implementation details from the perspective of Juju and other charms, a relation lib produces and/or consumes data that conforms to a relation schema, which other charms are aware of.

The `Interface` column would link to the charmhub or charm-relation-interfaces page (which? both?). The ' Library' column would follow the format of non-relation libs (e.g. name[linking to canonical source], (docs link, src link)).

|  | Interface | Library | Type | Description |
| :---- | :---- | :---- | :---- | :---- |
| ✅ | loki_push_api |  | Charmhub |  |
| ✅ | tls-certificates |  | Charmhub | Recommended lib for ... |
| 🪦 | tls-certificates |  | Charmhub | Legacy lib ... |

## Further Information

There's an older listing of Charmhub hosted libs, which would likely be replaced by this listing:
[https://juju.is/docs/sdk/library-index](https://juju.is/docs/sdk/library-index) (redirects to ->) [https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/libname-py-file/#popular-libraries](https://canonical-charmcraft.readthedocs-hosted.com/en/stable/reference/files/libname-py-file/#popular-libraries)
