# OP003 — Local vs. Controller Storage and metadata v2 Charms

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2021-??-?? |

## Local vs. Controller Storage and metadata v2 Charms

## The problem

Currently, the Operator framework relies on a bit of a hack to automagically use controller storage instead of local storage for kubernetes charms. The hack doesn't work on metadata v2 charms, which breaks tests and charms unless they explicitly pass "use_controller_storage=True" when they instantiate the Framework object.

In detail, the hack looks like this:

- ops/main.py contains a helper method called `_should_use_controller_storage`.
- Said method, which is called when ops/main.main runs, checks for the presence of "kubernetes" in the series key in metadata.yaml.

The "series" key doesn't exist in metadata v2 charms. The information has, in fact, been moved out of the framework's reach, into the CharmHub API. We need to fix things that broke, preferably in a less fragile way.

## Proposed Solution #1 (hack)

That said, the first solution in this document is another hack. There are various ways that a charm could detect that it was running on top of kubernetes, and it could use storage as appropriate.

We could take a page from Juju Core, and "assume" storage support for objects with a container resource in the metadata.yaml, for example. Only kubernetes charms have a "container" resource. This hack is somewhat fragile, but it will fix some of the immediate problems, which include broken tests for k8s charms using the operator framework.

## Proposed Solution #2 (non hack)

This solution might include one or more of the following:

- Implementing some or all support for metadata v2.
- Fully supporting "assumes", and behaving appropriately.
- ???

The downside to the "correct" solution is that it will probably require charm authors to update their charms. For example, they might need to add "storage" to "assumes."

(The other downside is that assumes is not yet implemented.)

I think that we have an obligation to keep our automagic auto magicking, if possible. If we break something that was working, we need to have a very strong justification if we refuse to fix it. "The automagic was a hack" does not represent that sort of justification -- the time to object to hacks is before code hits production, not after other folks are relying on the hack!

TODO: get some feedback, and see if there is a good non hacky way of doing this without breaking people.
