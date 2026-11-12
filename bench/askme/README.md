# AskMe harness on five runtimes

How fast is a coding-agent harness when the model is not the bottleneck? This
benchmark runs the [typed AskMe port](../../examples/askme/README.md) from one
source on CPython, PyPy, mypyc, the Pystachy JIT and a Pystachy executable,
beside the reference `askme.py` on CPython and PyPy. Every model reply is
recorded in advance, so the measured time is the harness alone.

Results: [2026-11-12](results/2026-11-12-runtimes.md).

## What is measured

| Workload | Contents |
|---|---|
| `--help` | Process start to exit; no run |
| Scenario suite | The port's committed scenarios (all but the one that waits for a 5-second timeout): complete runs of 3 to 15 model requests, some with shell actions |
| Navigation run | One run of 2,001 requests over 240-line files: reads, searches, edits, writes, tree listings |
| Controller run | The same script over tiny files, so prompt building, reply decoding and policy checks dominate |
| HTTP run | 101 requests against an instant loopback server through each implementation's real transport |

Each sample is one fresh process: wall time around `fork`/`wait4`, user plus
system CPU and peak resident memory from `wait4`. Runtimes are interleaved
round-robin and pinned to one core. The tables report medians; the JSON keeps
every sample.

## Correctness before timing

A runtime is timed only after it reproduces CPython's transcript on every
workload: each model request, JSONL event and console line, the structured
result, the exit code and a hash of every workspace file. Wall times and the
workspace path are the only normalized values. The reference harness is held
to the same transcript, so all seven columns did the same work.

## Reading the numbers

- The port answers requests in-process in every workload but the HTTP run.
  That isolates the harness; it is not a deployment.
- In the HTTP run the port starts one `curl` process per request on every
  runtime. The compiled program has no socket or TLS library, so process
  startup, not Python speed, sets its per-request cost.
- CPython, PyPy and mypyc use the C `json` and `hashlib` modules. Pystachy
  uses its own JSON codec and the port's pure SHA-256.
- `pystachy run` compiles on the first launch and reuses its
  [program cache](../../docs/program-cache.md) afterwards. The JIT column is a
  cached launch; the first launch is reported with the build costs.
- A shared virtual machine timed these runs. Differences of a few percent
  between neighbouring rows are noise.

## Reproduce

```sh
make
python3 bench/askme/bench.py --out build/askme-runtimes \
  --askme /path/to/askme --pypy /path/to/pypy3 --mypyc /path/to/mypyc \
  --reference-pypy /path/to/pypy-with-requests/bin/python
python3 bench/askme/report.py build/askme-runtimes.json
```

Run it with a Python that has `requests` installed, which the reference
harness needs. Every tool but CPython is optional: a runtime without its option
is left out. `workload.py OUTPUT.json [TASKS] [STEPS]` writes the long run as a
scenario file for other uses.
