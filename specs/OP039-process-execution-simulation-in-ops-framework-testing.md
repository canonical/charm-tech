# OP039 — Process Execution Simulation in Ops Framework Testing

| Field | Value |
| --- | --- |
| Status | Completed |
| Type | Standard |
| Created | 2023-08-09 |

## Abstract

This specification introduces a new feature for simulating process execution (Pebble exec) to the Ops framework `testing` module.

Note that not all Pebble exec features are supported (for example, long-running processes and signals), but this proposal aims to solve the existing, common use cases of `Container.exec` in charms. More advanced use cases can still be solved with charm-specific mocks.

## Rationale

Process execution (Pebble exec) is a critical component of most charms. Despite its ubiquity, the ops framework `testing` module doesn't provide any support for simulating process execution. As a result, many charms have to create their own patching and mocking systems for process execution during unit tests.

## Specification

### Process Execution Handler

The simulation of process execution will be facilitated by a user-provided Python function called the "process execution handler" or "exec handler". This handler will accept one argument: an execution argument object. This object contains process execution parameters given in the `ops.Container.exec` method. The handler is expected to return an execution result object as the result of the simulated process run.

The execution handler can return one of:

* A string (or byte string), which will be equivalent to just returning standard output with a 0 exit code, as in `ExecResult(exit_code=0, stdout=str_or_bytes, stderr='')`
* An integer, which will be equivalent to `ExecResult(exit_code=return_value, stdout='', stderr='')`
* A full `ExecResult` object (defined below)

**Type Definitions:**

```py
# Note: these fields are a subset of the Container.exec() args
@dataclass
class ExecArgs:
    command: list[str]  # full command line passed to exec()
    environment: dict[str, str] | None
    working_dir: str | None
    user_id: int | None
    user: str | None
    group_id: int | None
    group: str | None
    stdin: str | bytes | None
    encoding: str | None
    combine_stderr: bool
    timeout: float | None

@dataclass
class ExecResult:
    exit_code: int = 0
    stdout: str | bytes = ''
    stderr: str | bytes = ''

ExecHandler = Callable[[ExecArgs], ExecResult | str | bytes | int]
```

**Examples:**

```py
# always return success for every command
harness.handle_exec('container', [], lambda _: 0)

# simple example that just produces output (exit code 0)
harness.handle_exec('webserver', ['ls', '/etc'],
                        lambda _: 'passwd\nprofile\n')

# slightly more complex (use stdin)
harness.handle_exec('c1', ['sha1sum'],
                        lambda args: hashlib.sha1(args.stdin).hexdigest())

# more complex example using args.command
def docker_handler(args: testing.ExecArgs) -> testing.ExecResult:
    match args.command:
        case ['docker', 'run', image]:
            return testing.ExecResult(stdout=f'running {image}')
        case ['docker', 'ps']:
            return testing.ExecResult(stdout='CONTAINER ID   IMAGE ...\n')
        case _:
            return testing.ExecResult(exit_code=1, stderr='unknown command')

harness.handle_exec('database', ['docker'], docker_handler)
```

### Registering the Process Execution Handler

Handlers can be registered with  `Harness.handle_exec`. Subsequently, any invocation of `ops.Container.exec` will be emulated by triggering the corresponding process execution handler. The attachment of handlers to specific commands is achieved via prefix matching, designed to accommodate sub-commands in large programs like Docker (`docker ls`, `docker ps`, etc.) and WordPress (`wp theme`, `wp plugin`, etc.). The system does not simulate the OS's command search mechanism, meaning `["/bin/ls", "-l"]` and `["ls", "-l"]` are seen as distinct programs. Users can register multiple prefixes with varied command paths to a single handler if they wish to imitate this search behavior.

The execution handler is associated with the container. The execution handler lookup process is scoped by containers.

If multiple command line argument prefix matches are found for one command execution, the longest match wins. If no command line argument prefix match is found for a command execution, exception `pebble.APIError` will be raised, but with a user-friendly error message to direct users to register exec handler in the harness. The execution handler registration can be updated by re-registering with the same command prefix.

```py
class Harness:
    def handle_exec(
        self,
        container: str | model.Container,
        command_prefix: list[str],
        handler: ExecHandler,
    ):
        ...
```

### Handling Timeouts

The execution handler will receive the timeout value in the `ExecArgs`, and the execution handler should raise a `TimeoutError` to signal the harness that a timeout happened.

```py
def handle_timeout(exec_args: ExecArgs) -> int:
    if exec_args.timeout is not None and exec_args.timeout < 10:
        raise TimeoutError
```

### Handling combine_stderr

If the `ops.Container.exec` is invoked with `combine_stderr=True`, if needed, the execution handler can interleave the simulated standard error into the standard output. The harness will check the `ExecResult`, and raise a `ValueError` if the `ExecResult.stderr` is not empty.

```py
def handle_combine_stderr(exec_args: ExecArgs) -> ExecResult:
    if exec_args.combine_stderr:
        return ExecResult(exit_code=0, stdout="WARNING:foo\nOkay\n", stderr="")
    else:
        return ExecResult(exit_code=0, stdout="WARNING:foo\n", stderr="Okay\n")
```

### Example of Process Execution Handler

It's recommended for users to use closures to parameterize or pass values to the process execution handler.

```py
def test_wp_is_installed(harness):
    is_installed = False

    def wp_core_is_installed(exec_args: ExecArgs) -> int:
        return 0 if is_installed else 1

    harness.handle_exec(
        "container1"
        ["wp", "core", "is-installed"],
        wp_core_is_installed
    )
    ...
```

### Advance Process Execution Simulation (?)

By default, process simulation is conducted via a straightforward Python function call. However, this method causes that by the time `ops.Container.exec` returns the `ExecProcess`, the process run will always be finished. As a result, stdin, stdout, and stderr will always be closed and have static values, and signal handling cannot be simulated.

For these reasons, users can provide a generator as the execution handler. The generator type execution handler will yield `ExecOutput`, accept `ExecInput` via generator send and return the `ExecResult`.

The generator type execution handler will allow the simulation of signal handling, and interactive programs with stdin and stdout.

The `ops.ExecProcess` methods will be roughly translated into generator method:

```py
# ExecProcess.stdin.write ≈ handler generator.send
# ExecProcess.send_signal ≈ handler generator.send
# ExecProcess.stdout.read ≈ handler generator.__next__
# ExecProcess.stderr.read ≈ handler generator.__next__
```

**Examples:**

```py
@dataclass
class ExecInput:
    signal: Signals | None
    stdin: typing.AnyStr | None

@dataclass
class ExecOutput:
    stdout: typing.AnyStr = ''
    stderr: typing.AnyStr = ''

# handle singals

def handle_sleep_inf(exec_args: ExecArgs) -> typing.Generator[ExecOutput, ExecInput, ExecResult]:
    while True:
        exec_input = yield ExecOutput()
        if exec_input.signal in (signal.SIGTERM, signal.SIGINT, signal.SIGKILL):
            return ExecResult(0, '', '')

harness.handle_exec('container', ['sleep', 'inf'], handle_sleep_inf)

# handle interactive program

def handle_cat(exec_args: ExecArgs) -> typing.Generator[ExecOutput, ExecInput, ExecResult]:
    """simulate cat command without argument, which will echo stdin to stdout"""
    write_stdout = exec_args.stdin
    while True:
        exec_input = yield ExecOutput(stdout=write_stdout)
        write_stdout = exec_input.stdin
        # on stdin closed or kill signal
    if exec_input.stdin is None or exec_input.signal in (signal.SIGINT, signal.SIGKILL):
            return ExecResult(0, '', '')

harness.handle_exec('container', ['cat'], handle_cat)
```
