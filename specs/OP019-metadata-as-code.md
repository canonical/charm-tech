# OP019 — Metadata-as-code

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2022-06-02 |

## Abstract

As a 'code project' (repo), a charm contains a number of YAML metadata files.
The code depends on this metadata, in that the metadata is (at runtime) parsed
and used to generate dynamically certain namespaces which (at deploy time) are
used to interact with the juju API.

We think it would be beneficial to charmers to close the gap between metadata and code.

**Goals**:

- Facilitate the creation of charms (especially the early stages) by enabling code completion and linting on metadata-driven code paths and resources.
- Facilitate the maintenance of charms by keeping all data in one place and closely tied together.

**Non-goals**:

- Change the way the 'backend' works (i.e. charmcraft, juju).
- Change the way metadata is consumed by charmcraft
- Change deploy-time behaviour or charm directory structure
- Reduce the amount of text/code it takes to specify metadata (e.g. to declare a resource).

## Rationale

A few typical situations:

- If you define a 'proxy' config option in `config.yaml`, but your code says `self.config['proxA']`, only the runtime environment (e.g. a unittest) will spot the error, because the runtime will parse the yaml and determine that 'proxA' is an unknown option.

- If you specify a 'database' relation in metadata.yaml, the IDE does not know of it, as a consequence you have to KNOW that 'self.on.database_relation_created' is a thing, just like you have to go and read the documentation to know that 'self.on.database_relation_bork' will raise a runtime error.

- If you specify a container in metadata.yaml, similarly, you have to KNOW that there is a 'self.on.container_name_pebble_ready'.

A way to mitigate these issues is to specify all that metadata **in code**, so that the linter will know (and lint-time is code-writing-time), that, for example, 'proxA' is not a valid config option, and that there is a 'self.database' object which is of type **relation**, which has some attributes such as on_created, on_joined, etc... which you can register callbacks to.

This has another additional advantage: all information is in one place. It's easier to see what resources, actions,  metadata your charm has. You don't need to go search for the yaml file in  which to add this or that piece of information; instead, you do it there next  to the charm code. This eases the cognitive load on developers to have to go back to the metadata and check 'what was the name of that relation endpoint/config option/resource/storage again?'.

The metadata required by charmcraft does not simply go away: we can derive it from the data structures we have expressed as code and generate it at charmcraft-pack-time.

We inject a part in charmcraft.yaml that ensures that before the charm is built the metadata-as-code is parsed and piped out to the respective yaml files. The yaml files can be cleaned up afterwards.

## Specification

## Instead of importing CharmBase from ops, import Jinx from jinx. You write jinxes like so:

| from jinx import *
class ExampleJinx(Jinx):
    name = 'my-charm'  # the only mandatory attribute; the rest is optional     maintainer = 'maintainer@example.com'     summary = 'demonstration jinx'

    def __init__(self, framework, key=None):
        super().__init__(framework, key) |
| :---- |

## Save the file and run unpack /path/to/jinx_file.py

## And this will create for you:

* # charmcraft.yaml

* # actions.yaml (empty in this case)

* # config.yaml (empty in this case)

* # metadata.yaml

### relations

| from jinx import *

class ExampleJinx(Jinx):
    name = 'my-charm'

    # you declare the endpoints
    db_relation = require('db', InterfaceMeta('interface'))
    ingress_relation = provide('ingress', InterfaceMeta('ingress-per-cookie'))

    def __init__(self, framework, key=None):
        super().__init__(framework, key)
        # you use them
        self.db_relation.on_changed(self._on_db_changed)
        # is the new self.framework.observe(self.on.db_relation_changed, self._on_db_changed)

        # and then ...
        self.ingress_relation.on_departed(...)

    def _on_db_changed(self, event: RelationChangedEvent):
        pass |
| :---- |

### config

| from jinx import *

class ExampleJinx(Jinx):
    name = 'my-charm'

    # you declare the config options
    thing = config(string('thing-config-key-name', 'my description', default='foo'))
    other_thing = config(float_(description='my description', default=1.2))

    def __init__(self, framework, key=None):
        super().__init__(framework, key)

        self.config.on_changed(self._on_config_changed)
        # is the new self.framework.observe ...

    def _on_config_changed(self, event: ConfigChangedEvent):
        # you get the config directly, by name:
        thing_value = self.thing  # the type checker knows this is a str
        # is the new self.config['thing'] |
| :---- |

### actions

| from jinx import *

class ExampleJinx(Jinx):
    name = 'my-charm'

    # you declare an action like so:
    get_data = action(
        'get-data', params(
            foo=string(default='2'),
            bar=integer(default=2),
            baz=float_(default=2.2))
    )

    def __init__(self, framework, key=None):
        super().__init__(framework, key)
        # you don't observe actions here, instead...

    # you do this:
    @get_data.handler
    def _on_config_changed(self, event: ActionEvent):
        # the rest is (for now) as usual...
        event.params['foo'] |
| :---- |

## Current status

You can try out a POC implementation of some of this at:
[https://github.com/PietroPasotti/jinx](https://github.com/PietroPasotti/jinx)

To use:

- fetch the repo
- from jinx import *
- write some!
