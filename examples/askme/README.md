# The complete AskMe coding agent, compiled

[AskMe](https://github.com/den-run-ai/askme) is a coding-agent harness. It plans
tasks, asks a model for one action at a time (`shell`, `write`, `edit`, `read`,
`search` or `tree`), runs it, replans on failure and validates completion. This
example is AskMe's typed port of that whole harness: eight modules, about 7,000
lines, that run unchanged on CPython and PyPy, compile with mypyc, and build
with Pystachy into a one-megabyte executable. No compiler or runtime change was
needed.

The [small agent](../agent/README.md) is a separate 680-line subset with its own
contract. This port implements AskMe's: AskMe's test suite replays 18 recorded
scenarios through its reference `askme.py` and through these files and requires
equal model requests, events, console lines, results and workspaces.

The files are pinned copies from
[AskMe's `native/` directory](https://github.com/den-run-ai/askme/tree/572c26284acc32dcac59095611237c464df8c22c/native),
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

The executable needs `curl` for HTTP, `/bin/sh` for shell actions and `timeout`
for their deadlines. It is **not a sandbox**: model-generated commands run with
your permissions. Live model behaviour is AskMe's and has not been re-qualified
for this build.

## How the harness fits the typed subset

| The harness needs | The port uses |
|---|---|
| Model replies, run state and step records with mixed values | [`json.JSONValue`](../../docs/json.md), narrowed with `isinstance`; no `Any` and no [dynamic `Any`](../../docs/dynamic-any.md) opt-in |
| One source for five runtimes | The alias is `json.JSONValue` under Pystachy and a `typing` union elsewhere, chosen by a [compile-time branch](../../docs/language/modules.md#compile-time-branches) on `sys.implementation.name` |
| `subprocess` with a deadline | `os.system`, `/bin/sh` and `timeout`, with output captured in a private scratch directory |
| `requests` | `curl`; headers travel in a private file, never in arguments |
| `hashlib.sha256` | A pure implementation in 64-bit arithmetic; CPython keeps `hashlib` |
| `pathlib` | `os.path` and helpers that follow `PurePosixPath` |
| `re`, `shlex`, `bisect`, `argparse` | [`lib/`](../../lib/README.md) |

Three adjustments came from writing one source for every compiler: fields set
from a call or another object's attribute carry annotations, variable-length
tuples that are searched with `in` became lists, and an `except ... as` name is
not reused for a second exception type in one function (mypyc types the name
from its first handler).

## Evidence

| Check | Scope |
|---|---|
| [`tests/programs/apps/example_askme.py`](../../tests/programs/apps/example_askme.py) | Four scripted runs in the differential corpus, compared with CPython in every verification configuration |
| `python3 bench/askme/bench.py --verify-only` | JIT and AOT transcripts of 17 scenarios and two 2,001-request runs equal CPython's |
| AskMe's `tests/test_native_port.py` with `ASKME_NATIVE_PYSTACHY=./pystachy` | 18 scenarios through `askme.py`, CPython, JIT and AOT; 55 actions through both action layers |
| `python3 tools/check_agent_source.py /path/to/askme` | The pinned files equal the pinned commit's |

The corpus case and the source pin run in CI. The other two are commands to run;
neither is a CI gate here.

## Measurements

Model replies recorded, so the harness alone is timed; medians on one shared
4-core x86-64 virtual machine, each runtime first reproducing CPython's
transcript ([method](../../bench/askme/README.md),
[full results](../../bench/askme/results/2026-11-12-runtimes.md)):

| Runtime | `--help` | 17 short runs | 2,001-request run | Peak memory, short run |
|---|---:|---:|---:|---:|
| Pystachy executable | 2.3 ms | 0.20 s | 1.7 to 2.0 s | 5 MB |
| Pystachy JIT, cached | 54 ms | 1.09 s | 1.7 to 2.4 s | 13 MB |
| mypyc + CPython 3.13 | 43 ms | 0.94 s | 1.3 to 1.7 s | 19 MB |
| CPython 3.13 | 45 ms | 0.98 s | 1.9 to 2.1 s | 17 MB |
| PyPy 7.3 | 106 ms | 2.70 s | 2.7 to 3.4 s | 123 MB |
| `askme.py` on CPython | 158 ms | 2.85 s | 2.4 to 2.5 s | 29 MB |

The executable wins where startup dominates: 19 times CPython to start and
4.9 times on complete short runs. On long runs it is at CPython's level,
because CPython already spends that time in C (`json`, `hashlib`,
`str.splitlines`), and mypyc is fastest. Through real HTTP the port's `curl`
process costs about 7 ms per request on every runtime, so `askme.py` with
`requests` finishes first after about 26 requests. With a hosted model, where
a request takes hundreds of milliseconds, these differences are a few percent
of a run; startup and footprint are what remain.

## Limits and next steps

- Linux is the validated platform. The adapters are POSIX code; macOS is
  untested.
- There is no socket or TLS library, so each model request starts a `curl`
  process. An in-process HTTP client would remove most of the per-request cost
  measured above.
- Comparing a `json.JSONValue` with a string goes through the runtime's generic
  equality. Narrowing 17 such comparisons by hand made the long runs 1.2 to 1.3
  times faster; specializing that comparison in the compiler would give every
  program the same gain.
- Under `PYSTACHY_IRCHECK=1`, which the test runner sets, `len()` of a `bytes`
  value stored directly as a `json.JSONValue` fails the union proof ("ubox
  needs matching tag and payload provenance") although the generated code is
  correct. `def size(raw: bytes) -> json.JSONValue: return len(raw)` reproduces
  it; the port passes its one such length through a function that returns
  `int`.
- `hashlib` and `subprocess` are not in `lib/`. The port's SHA-256 is about a
  sixth of the navigation run's instructions.
- Integers in a model reply must fit 64 bits and JSON nesting is bounded; both
  become ordinary decode failures that the harness retries.
