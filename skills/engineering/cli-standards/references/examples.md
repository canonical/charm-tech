# CLI Standards — Examples Catalogue

Illustrative do/don't examples for every section in the CLI standards skill.

---

## Grammar: Commands as Verbs

```
# ✅ Verbs that imply the object type
snap install firefox
snap refresh firefox
snap login

# ⚠️ Avoid: inconsistent or non-verb commands
snap do-install firefox
snap firefox-refresh
```

## Grammar: Verb-Noun Form

```
# ✅ Use verb-noun when verbs alone are ambiguous
snap set-quota mysnap

# ⚠️ Avoid: verb-noun-noun compounds
create-vmhost-network vmh1:nw1

# ✅ Use flags to flatten hierarchy
create-network --vmhost vmh1 nw1
```

## Grammar: Listing Secondary Objects

```
# ✅ Plural noun shorthand
snap services
snapcraft release-status

# ⚠️ Avoid: list- prefix for secondary objects
snap list-services
snapcraft show-release-status
```

## Grammar: Accepted Verbs and Symmetry

```
# ✅ Accepted verbs, not invented synonyms
snap save firefox
snap restore 42
snap forget 42

# ⚠️ Avoid: a novel verb when an accepted one means the same
cmd verify config.yaml       # use validate
cmd nuke my-widget           # ambiguous and informal; use remove

# ✅ Symmetrical verbs within a command family
cmd create-foo foo1
cmd delete-foo foo1

# ⚠️ Avoid: mismatched pairs
cmd add-foo foo1
cmd delete-foo foo1
```

## Grammar: Sublevels

```
# ✅ At most one sublevel
cmd cluster config --secret "$(cat secret.txt)"

# ✅ Or split into a separate tool
cmd-cluster config --secret "$(cat secret.txt)"

# ⚠️ Avoid: multiple sublevels
cmd cluster node config --secret "$(cat secret.txt)"
```

---

## Positional Parameters

```
# ✅ Clear directional meaning
cp sourcefile destfile

# ✅ Single parameter with obvious meaning
docker pull ubuntu
snapcraft revisions my-snap

# ⚠️ Avoid: interchangeable positions
ln <target> <the other target>
```

## Flags: Short vs Long

```
# ✅ Short flag for frequent, easily implied actions
ls -l
tar -xzf archive.tar.gz

# ✅ Long flag for less frequent, descriptive actions
snapcraft pack --verbosity debug

# ⚠️ Avoid: offering both short and long for the same flag
tool do-foo -v
tool do-foo --verbose    # users must memorise both
```

## Flags: Stacking

```
# ✅ Short flags allow stacking
apt upgrade -yadf
apt upgrade -y -a -d -f    # equivalent

# ✅ Order-independent
apt upgrade -a -d
apt upgrade -d -a          # same result
```

## Flags: Multiple Values

```
# ✅ Repeated flag (singular name)
tool do-foo --channel=edge --channel=beta

# ✅ Comma-separated (plural name)
tool do-foo --channels=edge,beta

# ⚠️ Avoid: providing both forms
tool do-foo --channel=edge --channels=edge,beta
```

## Flags: Key=Value Arguments

```
# ✅ Key=value with singular flag
charmcraft release my-charm --channel=edge --resource foo=7 --resource bar=1

# ✅ Multiple key=value pairs
tool do-foo --bar a-key=1 --bar a-key=2 --bar a-key=3

# ✅ Plural flag with comma-separated values
tool do-foo --bars a-key=1,a-key=2

# ✅ Complex constraints
juju deploy haproxy -n 2 --constraints spaces=dmz,^cms,^database
```

## The `--` Separator

```
# ✅ Separate tool flags from passed command
multipass exec docker -- docker kill e1261a3214
multipass exec docker -- snapcraft --help
# --help is passed to snapcraft, not multipass
```

---

## Feedback: Error Messages

```
# ✅ Clear, actionable error
error: cannot establish the connection

# ⚠️ Avoid: contractions
error: can't establish the connection

# ⚠️ Avoid: chatty/apologetic
Oops, something went wrong. Please either let juju create a new
controller using "juju bootstrap" or...

# ✅ Direct and helpful
Create a new controller using "juju bootstrap" or connect to another
controller using "juju register".
```

## Feedback: Missing Arguments

```
# ✅ Passive, succinct
Invalid URL: "htp://foo.bar"

# ⚠️ Avoid: addressing the user
You need to provide a valid URL.
```

## Feedback: "cannot" not Contractions

```
# ✅
error: cannot establish the connection

# ⚠️ Avoid
error: connection couldn't be established
error: failed to establish the connection
error: unable to establish the connection
```

---

## Colour Usage

```
# ✅ Colour for emphasis, not as sole information carrier
✓ Build complete       # green ✓ reinforces the text, but text alone is sufficient

# ✅ Check for colour support
if os.isatty(sys.stdout.fileno()) and not os.environ.get("NO_COLOR"):
    # enable colour

# ⚠️ Avoid: relying on colour alone
●                      # red dot with no text — inaccessible
```

---

## Tables: Format

```
# ✅ Standard format: two-space delimiter, UPPER CASE headers, no decoration
NAME                VERSION      REV  TRACKING         PUBLISHER           NOTES
amberol             0.10.3       30   latest/stable    alexmurray✪         -
android-studio      2023.1.1    148   latest/stable    snapcrafters✪       classic

# ⚠️ Avoid: ASCII decorations
+------------------+---------+-----+
| NAME             | VERSION | REV |
+------------------+---------+-----+
| amberol          | 0.10.3  | 30  |
+------------------+---------+-----+

# ⚠️ Avoid: spaces within cells
PUBLISHER NAME    VERSION
alex murray       0.10.3     # "alex murray" breaks awk processing
```

## Tables: Empty States

```
# ✅ Clear empty state message (to stderr, exit code 0)
$ snap list
No snaps installed.

# ⚠️ Avoid: empty table with only headers
$ snap list
NAME  VERSION  REV  TRACKING  PUBLISHER  NOTES

# ✅ Machine-readable: output zero value
$ foo list --format=json
$ foo list --format=yaml
items: []
```

---

## Verbosity

```
# ✅ Default (brief) — critical info only
$ sudo snap refresh
All snaps up to date.

# ⚠️ Avoid: chatty brief output
$ foo refresh
We checked for the newest revisions for your installed snaps and you are all good!

# ✅ Precise output
$ snap refresh --hold=24h firefox
General refreshes of "firefox" held until 2025-07-26T14:10:53+01:00

# ⚠️ Avoid: vague output
$ foo refresh --hold=24h firefox
Now holding refreshes for your snap.

# ✅ Clear "not found" state
$ snap list syf
error: no matching snaps installed

# ⚠️ Avoid: silent failure (showing no data)
$ snap list syf
$
```

## Timestamps

```
# ✅ ISO 8601
2024-06-29T03:24:20Z

# ⚠️ Avoid: ambiguous formats
06/29/2024 3:24 AM
29 Jun 2024
```

## Help Output

```
# ✅ Top-level help: version, usage, summary, global options, grouped commands, pointer to more help
$ snap help
snap 2.67
Usage:
    snap <command> [<options>...]

    The snap command lets you install, configure, refresh and remove snaps.

Global options:
  --help       Show this help message and exit
  --quiet      Only show warnings and errors, not progress
  --verbose    More verbose output, repeat to increase detail
  --version    Show the application version and exit

Basic commands:
  find         Find packages to install
  install      Install snaps on the system
  remove       Remove snaps from the system
  list         List installed snaps

Other topics:
  Snapshots    saved, save, check-snapshot, restore, forget
  Account      login, logout, whoami

For more information about a command, run 'snap help <command>'.
For more information about a topic, run 'snap help <topic>'.

# ✅ Command help: options grouped by function, values and defaults shown, examples, related commands
$ snap help install
Usage:
  snap install [<option>...] <snap>...

The install command installs the named snaps on the system. With no further options, the snaps are installed tracking the stable channel, with strict security confinement.

Channel and revision options:
  --stable               Install from the stable channel (default)
  --channel=<channel>    Use the specified channel instead of stable
Installation mode options:
  --devmode              Put snap in development mode and disable security confinement
  --dangerous            Install the given snap file even if there are no pre-acknowledged signatures for it (implied by --devmode)

Examples:
  Install the latest snap from the stable channel
    snap install btop

Related commands:
  snap find    Find snaps to install
  snap info    Get information about a snap and its available channels

# ⚠️ Avoid: one flat option list, no value placeholder, implication buried in prose
[install command options]
      --channel=      Use this channel instead of stable
      --edge          Install from the edge channel
      --devmode       Put snap in development mode and disable security confinement
```

## Changing a CLI

```
# ✅ Minor version: still works, deprecation warning on stderr naming the replacement
$ foo bar --qux
warning: "--qux" flag is deprecated, use "--waldo" instead

$ foo bar
warning: "foo bar" is deprecated and will be removed in the 3.0 release

# ✅ Next major version: fails (exit code 2) with a message naming the replacement
$ lxc launch <image> <instance> -c key=value
error: "-c" flag was removed, use "--config" instead

# ✅ Major version after that: plain error, messaging removed
$ lxc launch <image> <instance> -c key=value
error: invalid flag "-c"

# ⚠️ Avoid: removing or renaming without a deprecation release first
```

---

## Tone of Voice: Concise, Precise, Clear

```
# ✅ Concise
All snaps up to date.

# ✅ Precise
General refreshes of "firefox" held until 2025-07-26T14:10:53+01:00

# ✅ Clear
error: no matching snaps installed

# ⚠️ Avoid: chatty
We checked for the newest revisions for your installed snaps
and you are all good!

# ⚠️ Avoid: vague
Now holding refreshes for your snap.

# ⚠️ Avoid: ambiguous (silent empty output)
$
```

## Terminology Consistency

```
# ✅ Same term everywhere
CLI: juju deploy --to machine-3
UI:  "Deploy to machine-3"
Docs: "Deploy the charm to a machine"

# ⚠️ Avoid: mixed terminology
CLI: juju deploy --to machine-3
UI:  "Deploy to node-3"         # "node" vs "machine"
Docs: "Deploy the charm to a host"  # "host" vs "machine"
```
