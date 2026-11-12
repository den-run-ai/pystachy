# The complete AskMe coding agent, compiled

[AskMe](https://github.com/den-run-ai/askme) is a coding-agent harness. It plans
tasks, asks a model for one action at a time (`shell`, `write`, `edit`, `read`,
`search` or `tree`), runs it, replans on failure and validates completion. This
example is AskMe's typed port of that whole harness: twelve modules, about 8,000
lines, that run unchanged on CPython and PyPy, compile with mypyc, and build
with Pystachy into a one-megabyte executable. The executable sends its own HTTP
and HTTPS requests: libc sockets and OpenSSL, bound through the [FFI](../../docs/ffi.md).

The [small agent](../agent/README.md) is a separate 680-line subset with its own
contract. This port implements AskMe's: AskMe's test suite replays 18 recorded
scenarios through its reference `askme.py` and through these files and requires
equal model requests, events, console lines, results and workspaces.

The files are pinned copies from
[AskMe's `native/` directory](https://github.com/den-run-ai/askme/tree/593017afa31bd50b940dfa2defe39fc9fe47f697/native),
proposed there in [pull request 130](https://github.com/den-run-ai/askme/pull/130);
`UPSTREAM.json` records the commit and every file's SHA-256, and
`make check-recordings` verifies them.

## Run a recorded scenario

From the repository root:

```sh
./pystachy build examples/askme/askme_native.py -o build/askme
workdir=$(mktemp -d)
build/askme --working-dir "$workdir" \
  --replay examples/askme/scenarios/hello.json 'Create hello.txt containing hello'
cat "$workdir/hello.txt"
rm -rf "$workdir"
```

A scenario file holds a prompt's recorded model replies, so no model server is
involved. Substitute `./pystachy run examples/askme/askme_native.py` or
`python3 examples/askme/askme_native.py` for `build/askme` to run the same
source in the other modes.

## Use a model

The options and environment variables are AskMe's
([configuration](https://github.com/den-run-ai/askme/blob/main/docs/configuration.md)):

```sh
export LLM_BACKEND=openrouter OPENROUTER_API_KEY=...
build/askme --working-dir /path/to/disposable/project --result-json result.json \
  'Fix the failing tests'
```

The executable needs `/bin/sh` for shell actions and `timeout` for their
deadlines. For `https://` it loads the system's `libssl.so.3` at the first
request; behind a proxy, or without that library, it runs `curl` instead. It is
**not a sandbox**: model-generated commands run with your permissions. Live
model behaviour is AskMe's and has not been re-qualified for this build.

## How the harness fits the typed subset

| The harness needs | The port uses |
|---|---|
| Model replies, run state and step records with mixed values | [`json.JSONValue`](../../docs/json.md), narrowed with `isinstance`; no `Any` and no [dynamic `Any`](../../docs/dynamic-any.md) opt-in |
| One source for five runtimes | The alias is `json.JSONValue` under Pystachy and a `typing` union elsewhere, chosen by a [compile-time branch](../../docs/language/modules.md#compile-time-branches) on `sys.implementation.name` |
| `subprocess` with a deadline | `os.system`, `/bin/sh` and `timeout`, with output captured in a private scratch directory |
| `requests` | An HTTP/1.1 client in the subset (`native_http.py`) over [`@ffi.extern`](../../docs/ffi.md#calling-c) declarations of libc's sockets and OpenSSL 3; it keeps each endpoint's connection and verifies certificates and host names. The interpreters run the same client over `socket` and `ssl` |
| A library that loads only when used | A module-level `import` under a run-time condition, then the `import` in the function that needs it: the module's `@extern` definitions run, and `dlopen` its library, at that first call |
| `hashlib.sha256` | A pure implementation in 64-bit arithmetic; CPython keeps `hashlib` |
| `pathlib` | `os.path` and helpers that follow `PurePosixPath` |
| `re`, `shlex`, `bisect`, `argparse` | [`lib/`](../../lib/README.md) |

Three adjustments came from writing one source for every compiler: fields set
from a call or another object's attribute carry annotations, variable-length
tuples that are searched with `in` became lists, and an `except ... as` name is
not reused for a second exception type in one function (mypyc types the name
from its first handler).

The FFI modules assume 64-bit little-endian Linux with glibc: `struct addrinfo`
and `struct pollfd` are read and written as bytes and 64-bit words. OpenSSL
writes with `write(2)`, so `SIGPIPE` is ignored around each TLS call and
restored after it.

## Evidence

| Check | Scope |
|---|---|
| [`tests/programs/apps/example_askme.py`](../../tests/programs/apps/example_askme.py) | Four scripted runs in the differential corpus, compared with CPython in every verification configuration |
| `python3 bench/askme/bench.py --verify-only` | JIT and AOT transcripts of 17 scenarios and two 2,001-request runs equal CPython's |
| AskMe's `tests/test_native_port.py` with `ASKME_NATIVE_PYSTACHY=./pystachy` | 18 scenarios through `askme.py`, CPython, JIT and AOT; 56 actions through both action layers; live runs against loopback HTTP and HTTPS servers; an untrusted certificate chain and a wrong host name rejected before any request is sent |
| `python3 tools/check_agent_source.py /path/to/askme` | The pinned files equal the pinned commit's |

The corpus case and the source pin run in CI. The other two are commands to run;
neither is a CI gate here.

## Measurements

Model replies recorded, so the harness alone is timed, then a loopback server
for the transport; medians on one shared 4-core x86-64 virtual machine, each
runtime first reproducing CPython's transcript
([method](../../bench/askme/README.md),
[full results](../../bench/askme/results/2026-11-12-kept-connections.md)):

| Runtime | `--help` | 17 short runs | 2,001-request run | Request over HTTP, HTTPS | Peak memory, short run |
|---|---:|---:|---:|---:|---:|
| Pystachy executable | 2.4 ms | 0.24 s | 1.4 to 1.7 s | 0.8 ms, 1.5 ms | 5 MB |
| mypyc + CPython 3.13 | 46 ms | 1.00 s | 1.7 to 1.8 s | 1.5 ms, 2.0 ms | 19 MB |
| CPython 3.13 | 47 ms | 1.04 s | 2.0 to 2.2 s | 1.5 ms, 2.1 ms | 17 MB |
| PyPy 7.3 | 117 ms | 2.93 s | 3.2 to 3.4 s | 4.1 ms, 4.7 ms | 124 MB |
| `askme.py` on CPython | 165 ms | 2.95 s | 2.7 to 2.8 s | 4.1 ms, 28 ms | 29 MB |

The executable starts 19 times faster than CPython, finishes complete short
runs 4.4 times faster, and leads the long runs: 1.3 to 1.4 times CPython and
slightly ahead of mypyc. A request includes the harness's own work; the port
keeps its connection, where `askme.py` opens one, and over TLS handshakes, for
every request. `pystachy run` is absent from the table: it compiles the port at
each launch, 4.4 s, because the program cache skips programs that declare
`@ffi.extern` libraries
([#1320](https://github.com/den-run-ai/pystachy/issues/1320)). With a hosted
model, where a request takes hundreds of milliseconds, the kept connection is
the saving that remains visible; startup and footprint are the rest.

## Limits and next steps

- Linux is the validated platform. The process adapter is POSIX code and macOS
  is untested; the FFI streams are Linux-only, so elsewhere HTTP falls back to
  `curl`.
- `socket`, `ssl` and `http.client` are not in `lib/`: the port declares the C
  functions itself ([#1310](https://github.com/den-run-ai/pystachy/issues/1310)).
  The client speaks HTTP/1.1 only and one request at a time.
- A function's `import` compiles only for a module that module-level code also
  imports ([#1311](https://github.com/den-run-ai/pystachy/issues/1311)); the
  conditional module-level import above is the workaround.
- `hashlib` and `subprocess` are not in `lib/`
  ([#1308](https://github.com/den-run-ai/pystachy/issues/1308),
  [#1309](https://github.com/den-run-ai/pystachy/issues/1309)). The port's
  SHA-256 is about a sixth of the navigation run's instructions, and commands
  run through `os.system` with their output in files.
- JSON encoding, string joins and dict growth now lead the profile
  ([#1314](https://github.com/den-run-ai/pystachy/issues/1314)).
- Integers in a model reply must fit 64 bits and JSON nesting is bounded; both
  become ordinary decode failures that the harness retries.
