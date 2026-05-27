# OP081 — Add ability to listen for service exits in Pebble

| Field | Value |
| --- | --- |
| Status | Braindump |
| Type | Implementation |
| Created | Dec 1, 2025 |

*After discussion with the team that requested this feature (who probably don't need it after all), and looking at the proof-of-concepts and research that indicate that this is probably >1000 lines of changed code and tests right at the heart of Pebble service management, we decided to not progress this any further.*

## Abstract

Short description of the issue being addressed. Limit this to a couple of sentences.

## Rationale

Currently, when a service exits, Pebble offers four choices, each separately configurable for the service exiting successfully or unsuccessfully:

* ignore: do nothing
* shutdown: shut down Pebble (with a successful exit code)
* failure-shutdown: shut down Pebble (with an exit code of 10)
* restart: attempt to restart the exited service (this is the default behaviour)

TODO:

* Talk to the people about the motivation for the big solution, maybe not necessary.
* Verify with Ben/networking that this functionality is still required - and in particular get more details about exactly what sort of things needs to happen between the service exit and a restart.

This does not allow for custom, more complex behaviour. For example, in SONiC on Ubuntu (currently using supervisord but wanting to change to Pebble), the service exit behaviour is stored in an external configuration database. When a service exits, a script is run that uses the database to decide what to do next, via [supervisord's events system](https://supervisord.org/events.html).

In addition, there has been [discussion](https://github.com/canonical/pebble/pull/86#discussion_r795964837) about improving service management so that more data is visible, such as when a service is failing (or flailing) - knowing how often it has restarted would be useful (some of this information is now available via the metrics endpoint).

Benefits of using changes/tasks for service lifecycle:

* Visibility: all operations visible in changes API
* Notices: restarting generates a change-update notice
* Consistency with manual start/stop commands, checks system

## Specification

*Two options (to narrow down to one before going to review).*

Simpler one is adding a notice (type: service-exit, key of the service name, last-data could include information about the exit like the code, some stderr content) when a service exits. Can use the existing notices API to poll for new notices of this type and take appropriate action, which could include issuing a "start" command, so you could use "ignore" plus this for a custom action that did include restarting.

More complex one would be to move service management to be more like health checks, a long running change for the service running and then a "restart" change for restarting (maybe also Pebble shutdown change for consistency, although that seems a bit odd, so probably those actions stay as they are.

This has the benefit of much more visibility into the service lifecycle, particularly restarts. It also makes manual starts and restarts more consistent, as both will be handled via changes & tasks.

[PoC](https://github.com/tonyandrewmeyer/pebble/pull/1)

Instead of using the internal state machine with timers, we'll expose the service lifecycle through the existing changes API.

In the `serviceData` struct, we'll add:

* A channel for notification from the `monitor-service` task
* An ID to link to the `change` that is running the service (if it is)
* *Last exit code and action (the PoC has this, but I think probably it can be dropped)*

Current:
stateInitial -> stateStarting -> stateRunning ->stateBackoff -> ...
Start/stop are changes (and tasks)
Service exit: exited() method, transition to stateBackoff, timer to trigger restart via backoffTimeElapsed

In `doStart` (the start command), the PoC starts the service as it did before and then has a monitoring task. **This should get unified with the new method**.

**Current bug with PoC: `startup-enabled` doesn't work, need to manually start.**

Add a new `run-service` change

* "This service is running"
* Long-running change (so needs purge protection like checks)
* Has tasks to start and monitor the service
* Ends when the service exits (DONE for clean, ERROR for non-zero)

Add a new `restart-service` change (maybe we can re-use what's done on manual start?)

* "Restarting this service after exit"
* Created when a service exits and on-failure / on-success is set to restart
* Handles exponential backoff delays
* Manages all restart attempts
* Creates a new run-service change when successful

In `exited`:

* Determine which action should be taken (ignore, exit, failure exit, restart) if it's the service that has exited, or just ignore if it's a `stop` command.
* Send a notification that the service exited through to the monitor change via the new channel. This will also handle restart if needed.

New `doStart` (the PoC has this as `doStartService` as I was keeping compatibility, but I should get rid of that and just make it `doStart`).

* Start the service
* Do the 1s wait

New `doRestartService`:

* Loop with exponential backoff (like the existing system).
* Each attempt bumps the attempt counter, which triggers a change-update notice (this is perhaps too noisy?)
* Attempts to start (with the 1s delay system).

New `changeStatusChanged` (needs better name). Manages the `run-service` -> (exit) -> `restart-service` -> (success) cycle.

* Basically just completes the appropriate `change`.

TODO: make this a diagram

State transitions

User starts service -> runService change created (Do) -> start-service task (starts process) -> Task completes (change moves to a monitoring, still in DOING) -> service exits -> runService change is complete (DONE if exit code 0, ERROR if exit code non-zero)

(on-success/on-failure ignore) -> nothing else
(on-success/on-failure shutdown/shutdown-failure) -> trigger system shutdown (like now)
(on-success/on-failure restart) -> restartService change created, restart-service task handles backoff and attempts, each attempt updates the task (which will trigger a notice - maybe this is too many and it should just be updating the changeUpdate data?) -> service restarts successfully -> restartService change DONE -> new runService change

runService change

* service-no-prune
* start-service task
  * doStart logic
  * default -> do -> doing -> done / error
  * When complete service is stateRunning
  * On failure task goes to error status, change fails
* monitor-service task
  * WaitFor start-service
  * Blocks until service exits (on a channel that is signaled when the service exits)
  * Exit code goes into task data
  * Do -> Doing (monitoring) -> Done (exit 0) or Error (exit non-zero)

restartService change

* service-no-prune
* restart-service task
  * Handles backoff
  * Multiple restart attempts
  * Updates task data on each attempt
  * Do -> Doing -> Done (success, service is running)

Integration with existing components

Manual stop

* Create a stop-service change
* Aborts the run-service change
* Stop task sends term/kill (like now)
* Monitor-service task's tomb.Dying() will trigger, aborting the monitoring

Check failure restart

* CheckManager calls ServiceManager.CheckFailed()
* Finds the active run-service change for the service
* Sends term to the service (stateTerminating)
* When service exited, exited signals the monitor-service task
* Monitor-service completes, run-service change completes
* changeStatusChanged creates restart-service change

Startup services:

* Create run-service changes for all startup:enabled services
* Executed by task runner as usual
* WHAT ABOUT PERSISTENT CHANGES, remove in shutdown?

FIGURE OUT:

* Maybe monitor-service task and start-service should be the same?
* Check if there are any limits for restarting currently (give up after X). I think not, but either way we should keep the same behaviour.
* Pruning - what is the behaviour for runService changes, is it aligned with the other ones, is it the right choice?
* Make sure that the interaction with checks will still work the same way
* Persistence: does this change? How is restarting info persisted now? Do we get into a loop we don't want, interaction with startup:disabled etc?

## Further Information

* [Networking issue](https://github.com/canonical/pebble/issues/713)
* [Earlier issue around observing exits](https://github.com/canonical/pebble/issues/104)
