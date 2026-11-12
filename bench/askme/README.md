# AskMe harness on five runtimes

How fast is a coding-agent harness when the model is not the bottleneck? This
benchmark runs the [typed AskMe port](../../examples/askme/README.md) from one
source on CPython, PyPy, mypyc, the Pystachy JIT and a Pystachy executable,
beside the reference `askme.py` on CPython and PyPy. Every model reply is
recorded in advance, so the measured time is the harness alone.

Results: [2026-11-12, kept connections](results/2026-11-12-kept-connections.md);
earlier, [2026-11-12, `curl` per request](results/2026-11-12-runtimes.md).

## What is measured

| Workload | Contents |
|---|---|
| `--help` | Process start to exit; no run |
| Scenario suite | The port's committed scenarios (all but the one that waits for a 5-second timeout): complete runs of 3 to 15 model requests, some with shell actions |
| Navigation run | One run of 2,001 requests over 240-line files: reads, searches, edits, writes, tree listings |
| Controller run | The same script over tiny files, so prompt building, reply decoding and policy checks dominate |
| Transport runs | 103 requests against an instant loopback server through each real transport: the port's kept connection, its `curl` fallback, and both again over TLS, beside `askme.py`'s `requests.post` |

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

- The port answers requests from recorded replies in every workload but the
  transport runs. That isolates the harness; it is not a deployment.
- In the transport runs the port keeps one connection to the server; the
  executable's sockets and TLS are libc and OpenSSL through the FFI.
  `askme.py` opens a connection per request, so over TLS it pays a handshake
  each time. The loopback server replies at once: a real endpoint adds its
  own latency to every row, and a network round trip to each new connection.
- CPython, PyPy and mypyc use the C `json` and `hashlib` modules. Pystachy
  uses its own JSON codec and the port's pure SHA-256.
- `pystachy run` compiles the port at every launch: its
  [program cache](../../docs/program-cache.md) skips a program that declares
  `@ffi.extern` libraries
  ([#1320](https://github.com/den-run-ai/pystachy/issues/1320)), as the port
  has since it sends its own requests. The JIT column includes that
  compilation.
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
is left out, and the TLS rows need the `openssl` command for a test
certificate. `workload.py OUTPUT.json [TASKS] [STEPS]` writes the long run as a
scenario file for other uses.

## Compare two compilers

`compare.py` times executables of the port on the two long runs, after checking
that their transcripts are equal:

```sh
git stash && make && ./pystachy build examples/askme/askme_native.py -o /tmp/askme-before
git stash pop && make && ./pystachy build examples/askme/askme_native.py -o /tmp/askme-after
python3 bench/askme/compare.py before=/tmp/askme-before after=/tmp/askme-after
```
