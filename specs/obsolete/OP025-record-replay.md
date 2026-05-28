# OP025 — Record/replay

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Standard |
| Created | 2022-08-08 |

## Abstract

## Rationale

#### Limitations

The current proposal's main limitation stems from it being implemented downstream of Ops instead of in juju. Ops does not know what happened in juju, it only 'sees' the resulting event sequences. We can only guess, if we see `relation-departed`, whether the user scaled down an app, removed it altogether, or simply removed the relation. We can probably make the guess fine enough, but it would be much easier if this recording functionality were implemented in juju.
Juju has the full picture

- User does X
- Unit A sees changes 1, 2, 3
- Unit A fires event e
- Unit B sees changes 1, 2, 3
- Unit B fires event f
- ...

The 'user does X' part is what Ops has limited introspection about. Therefore this functionality is best moved over to juju when the spec is mature enough. See the relative spec for a more detailed discussion.



## Further Information
