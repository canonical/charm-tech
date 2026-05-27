# OP040 — Pebble locking issues and possible solutions

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Implementation |
| Created | 2024-03-04 |

## Abstract

In the last month there have been two significant issues with Pebble mutex locks: a [three-way deadlock](https://github.com/canonical/pebble/issues/314) causing the server to hang, and a [slowness issue with the state lock](https://bugs.launchpad.net/juju/+bug/2052517) that caused the health check endpoint to take over 1s to respond when under load. Both issues have been fixed ([deadlock fix](https://github.com/canonical/pebble/pull/355), [health check fix](https://github.com/canonical/pebble/pull/369)), but it's likely similar issues could happen again unless we address the issues with server-wide locks in a more systematic and structural way. This braindump spec details the problems and suggests some possible solutions.

## Problems and possible improvements

The two issues mentioned above correspond to two larger problems, which will be presented below with discussion of possible improvements and solutions.

1. The large number of locks, the scope they're held for, and their locking dependencies.
2. The state lock in particular, due to how long unlocking takes when a large state database has been modified.

### 1. Locks and locking dependencies

The Pebble server has multiple server-wide locks, some of which are acquired together at various points. If there's a dependency between locks, or different parts of the code don't acquire the locks in the same order as other parts, that will result in a deadlock.

For example, in the three-way deadlock mentioned above, the following concurrent requests had lock dependencies that caused a complete server hang:

`goroutine 1: doStart: held services lock, waiting for state lock (taskLogf)`
`goroutine 2: POST /v1/services (start): held state lock, waiting for plan lock`
`goroutine 3: GET /v1/services: held plan lock, waiting for services lock`

There are 17 server-wide locks in Pebble, 7 of whose scope or use is concerning, and 10 of which seem innocuous enough:

**`// Server-wide mutexes that need review`**
`// DONE: it is a large scope, but the operations it does are short, will leave as is.`
`overlord/logstate/manager.go:26: mu sync.Mutex            // scope of this is a little concerning`

`// DONE: this one doesn't seem concerning any more after the refactor in #387`
`overlord/servstate/manager.go:25: planLock sync.Mutex     // protects ServiceManager.plan - scope concerning`
                                                          `//   especially as updatePlan calls other code`

`// DONE: lots of uses, but actually looks pretty reasonable, they're all held for a short time.`
`overlord/servstate/manager.go:29: servicesLock sync.Mutex // huge number of uses - needs audit`

`// DONE: this is a known issue - looking at other ways to solve (faster serialisation, faster db).`
`overlord/state/state.go:79: mu sync.Mutex                 // concerning: locks during state read and write`

`// DONE: tricky, but this is inherited from snapd, and well-tested, so will leave as is.`
`overlord/state/taskrunner.go:68: mu sync.Mutex            // concerning scope and interactions with state lock`
`overlord/stateengine.go:67: mgrLock sync.Mutex            // looks okay, but worth an audit`

`// DONE: again, inherited from snapd (plus we don't use this functionality), so will leave as is.`
`systemd/systemd.go:64: lock sync.Mutex                    // probably okay as we don't use systemd functions,`
                                                          `//   but worth an audit`

**`// Server-wide mutexes that seem okay`**
`daemon/daemon.go:107: mu sync.Mutex                       // simple: protects Daemon.requestedRestart var`
`daemon/daemon.go:352: mu sync.Mutex                       // simple: protects connTracker.conns map`
`logger/logger.go:48: loggerLock sync.Mutex                // simple: serialises logging calls`
`osutil/mkdirallchown.go:30:var mu sync.Mutex              // simple: serialises Mkdir[All]Chown calls`
`overlord/checkstate/manager.go:29: mutex sync.Mutex       // simple: protects CheckManager.checks map`
`overlord/cmdstate/manager.go:27: executionsMutex sync.Mutex // simple: protects CommandManager.executions map`
`overlord/cmdstate/manager.go:34: executionsCond: sync.NewCond(&sync.Mutex{}),`
                                                          `// simple: used to connect to a command execution`
`overlord/overlord.go:83: ensureLock sync.Mutex            // simple: protects Overlord.ensure* vars`
`overlord/servstate/manager.go:35: randLock sync.Mutex     // simple: protects ServiceManager.rand var`
`reaper/reaper.go:34: mutex sync.Mutex                     // simple: protects reaper vars`

Of particular concern are `ServiceManager.planLock`, `ServiceManager.servicesLock`, and `State.mu` (the state lock). These three locks have a widest usage and largest scopes, and it was the interaction of these that caused the three-way deadlock noted above.

#### Possible improvements for server-wide locks

There are several things that could be done to improve the number and scope of server-wide locks used in Pebble:

* Audit the scope and usage of each lock listed in the "need review" list above.
  * Have done a review. Will leave most as is, apart from known issues with state lock.
* Determine whether it's possible to reduce the scope of locking for each lock acquisition.
  * For example, does the plan lock need to be held while calling the plan handlers, which could execute arbitrary code from outside the servstate package?
    * **Fixed in https://github.com/canonical/pebble/pull/436**
  * Similar example: [PR](https://github.com/canonical/pebble/pull/374) to avoid holding check mutex when running action func.
    * **Fixed by the rewrite of checkstate: https://github.com/canonical/pebble/pull/409**
* Evaluate whether each of these locks needs to be server-wide, and whether it's possible to use more localized and finer-grained locking.
  * For example, most of the service-specific functions in servstate/handlers.go (serviceData methods) acquire servicesLock, but don't actually access anything server-wide, just serviceData field for a specific service.
    * **Decided not to do this (unless it starts causing problems)**
  * *NOTE from review meeting:* be careful here - coarse-grained locks means fewer and simpler locking, fine-grained locks mean more locks and more to think about. Going finer-grained often means more complexity (though more performance). This might not be the trade-off we want here, and it wouldn't have solved the 3-way deadlock.
* Ensure we're using `defer mutex.Unlock()` for all unlock operations, otherwise if there's a bug that causes a panic while the lock is acquired, the net/http handlers will recover from this and the server will deadlock. A hard failure is better than a deadlock.
  * In addition, we should probably disable net/http's default "recover from panic" behaviour (**done** in [PR #350](https://github.com/canonical/pebble/pull/350)). *NOTE from review meeting:* general agreement this should be done.
  * *NOTE from review meeting:* resist being dogmatic about "always using defer unlock" for simple cases. Plus, it's less important if we disable net/http's "recover from panic".
  * **Not going to do this - it's much less important now that we've disabled net/http's "recover from panic".**
* Determine whether we can avoid acquiring the state lock at the end of every API request (twice, in the [daemon's ServeHTTP method](https://github.com/canonical/pebble/blob/150cb9fe962c33856fa8839afbdc8d7ae27e4638/internals/daemon/daemon.go#L202-L221)).
  * This is used to inject Maintenance and Warnings into the API response - and neither of those features are used by Pebble (they were inherited from snapd).
  * **Done** in health check endpoint as a special case ([PR #369](https://github.com/canonical/pebble/pull/369)), as this endpoint needs to always return quickly.
  * **Doing** this in PR [#451](https://github.com/canonical/pebble/pull/451) and [#443](https://github.com/canonical/pebble/pull/443).

### 2. State lock slowness

The server-wide state lock is used to serialize access to Pebble's "state" database, which is a set of simple in-memory data structures that are written to a JSON file by [State.Unlock](https://github.com/canonical/pebble/blob/95b73bb24eafa386ad4924abb57ffae9b5ef4501/internals/overlord/state/state.go#L253) whenever the state is modified.

The Pebble code normally only holds the state lock for a short duration (reading or writing a variable or data structure), but the write-to-JSON-file during Unlock can take a relatively long time, especially when the state data gets large-ish or the system is under heavy load.

Here are some graphs and numbers:

* Before [this fix](https://github.com/canonical/pebble/pull/369), the Data Platform team was regularly seeing the lock be held for **over 1s** on a system under load (MySQL write/replication load) which was causing Kubernetes to terminate the container due to liveness probe timeouts.
* Attempting to reproduce on a developer laptop, we regularly saw lock times of **200-300ms** on a system with a fairly large state database under simulated load. For a state Unlock/write that takes about 100ms, we saw approximately 70ms spent in JSON marshalling and 30ms spent writing to disk (though almost all of that was the fsync).
* This [Polar Signals profile](https://pprof.me/ee7e36e75cf19ba43cdbbb06b1109505) shows that 84% (!) of Pebble CPU time comes from json.Marshal. In contrast to the 70/30 split above, only 0.3% was spent on fsync.
* Pebble state can grow fairly large (in the above tests the JSON file grew to around **1MB**), because every "change" (service start, notice recorded, and so on) records an entry in the state database.
* Some old entries (or more than 500 Ready changes) are pruned, but pruning only happens every **10 minutes**.

Even 100ms is a very heavy operation for just updating a variable or adding a single change record. The ideas below describe some possible approaches to address this.

#### Possible solutions for state lock slowness

We could **use an embedded database such as SQLite** in Pebble's state handling. SQLite can perform hundreds of thousands of reads per second, and thousands of writes per second (see [here](https://stackoverflow.com/questions/1711631/improve-insert-per-second-performance-of-sqlite) and [here](https://stackoverflow.com/questions/35804884/sqlite-concurrent-writing-performance)).

This refactoring would be a relatively big job, but I believe it would significantly improve the Pebble service manager's state handling:

* When updating, the database only has to write what's changed, not the entire JSON database. This is the main thing that would make it fast for Pebble.
* Querying would be much more flexible.
* The SQLite database format is extremely stable.
* There's a CGo-free SQLite port (really a cross-compilation from C to Go) that's very well tested, and not too far behind the C version in performance: [modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite)
* From what I can tell the SQLite engine would add about 3MB to the Pebble binary.

*NOTE from review meeting:* got pretty strong push-back against introducing something as complex as SQLite for this use case. (For reference, SQLite's codebase is 255,000 lines of C.)

Alternatively, we could consider much smaller changes:

* **Shrink size of change data for various tasks,** for example [`exec` is unnecessarily large](https://github.com/canonical/pebble/issues/411).
  * Done in [PR #478](https://github.com/canonical/pebble/pull/478).
* **Use a cheaper-to-serialise format than JSON**, such as [Cap'n Proto](https://github.com/capnproto/go-capnp), or JSON-binary formats like [BSON or MessagePack](https://json.nlohmann.me/features/binary_formats/). As you can see above, when the state file get larger, it's no longer very cheap to serialise as JSON.
  * Decided not to do this for now. See [here](https://github.com/canonical/pebble/issues/476#issuecomment-2415670675).
* Alternatively, we could **use a faster JSON serialisation library** (there are [several](https://github.com/goccy/go-json) [out there](https://github.com/go-faster/jx)).
  * Decided not to do this for now. See [here](https://github.com/canonical/pebble/issues/476#issuecomment-2415670675).
* **Avoid the use of fsync** when writing the state file. We understand that it's there to ensure durability - that the write actually goes to disk before the call returns in case of server or power failure. Is this level of durability necessary for Pebble?
  * *NOTE from review meeting:* strong push-back against removing the durability guarantee.
* **Write the state on an interval** if it's changed (for example, 100ms or 1s) instead of on every State.Unlock call. Writes to state would no longer be synchronous with the main code, again removing the durability guarantee.
  * *NOTE from review meeting:* strong push-back against removing the durability guarantee.
* **Use multiple files or appendable files** to reduce the size and scope of writes. However, this quickly gets into "writing our own database" territory.
* *NOTE from review meeting:* Consider having an UnlockNonDurable() where the *caller* can specify "durability doesn't matter here". [Ben isn't convinced this would help much: most of the writes are recording changes, which need to be durable (if anything does).]
* *NOTE from review meeting*: broad agreement from the Juju team to allow 2 or 3 failures for the Kubernetes liveness check. Gustavo is in strong agreement with this: increasing the number of allowed failures or the timeout, or both.
* *NOTE from review meeting:* consider an embedded databases other than SQLite.
  * We just want a tool where we don't have to write the whole world when you change one variable or add one item.
  * [BoltDB](https://github.com/boltdb/bolt) was one option mentioned (likely using [bbolt](https://github.com/etcd-io/bbolt), etcd's fork). [Comparison of Badger vs LMDB vs Bolt.](https://dgraph.io/blog/post/badger-lmdb-boltdb/)

## Changelog

| Date | Status | Author(s) | Comment |
| :---- | :---- | :---- | :---- |
| 2024-03-04 | Braindump | [Ben Hoyt](mailto:ben.hoyt@canonical.com) | Initial brain dump |
| 2024-03-06 | Approved | [Ben Hoyt](mailto:ben.hoyt@canonical.com) | Updated with notes from 5 March review meeting (marked "NOTE from review meeting"). Marked as Approved, even though it's not a spec as such, as their was broad agreement we need to do this work, and put two items on Charm Tech's 24.10 roadmap. |
