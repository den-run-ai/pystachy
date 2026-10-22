# json_repair prototype throughput

A small repeated workload of ten synthetic trace-like records: three valid JSON
records and seven malformed inputs. It includes code strings, nested objects,
comments/fences/prose, incomplete literals and tool-argument strings. Records
are repaired individually. It is not a sample of production failure frequencies.

At source `ce6aee5e1dc1a3c3d8e85e833746e642e2839c9a`, on a shared Linux x86-64
AMD EPYC 9V74 host, CPython 3.13.16 and LLVM 18.1.3:

| Variant | Median seconds / 20,000 records | Relative to native AOT |
|---|---:|---:|
| Pristine json_repair 0.64.1 / CPython | 0.748 | 2.33× |
| Adapted port / CPython | 0.690 | 2.15× |
| Adapted port / Pystachy AOT | 0.321 | 1.00× |

Seven samples per variant, interleaved in rotating order and pinned to CPU 0.
[All samples and identities](results/prototype.json) are retained. The timed loop
calls `repair_json(return_objects=True)` and a small result-weight function.
Serialization, interpreter startup, JIT startup and AOT compilation are outside
the timer. Output witnesses match exactly across all three variants; the checksum
is 1,232,000 for 2,000 rounds. Results are advisory for this small repeated mix;
no memory, production throughput or general library speed claim is established.

## Reproduce

With the pinned upstream checkout described in the
[parity instructions](../../tests/upstream/json_repair/README.md):

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/json_repair_bench
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 bench/json_repair/bench.py 0
PYTHONPATH=ports python3.13 bench/json_repair/bench.py 0
/tmp/json_repair_bench 0
```

Compare the `outputs` and `per_round` lines exactly before timing. Choose an
allowed CPU from `os.sched_getaffinity(0)`. For each of seven rounds, run each
variant once, rotating which runs first:

```sh
PYTHONPATH=/tmp/json_repair_upstream/src taskset -c 0 python3.13 bench/json_repair/bench.py 2000
PYTHONPATH=ports taskset -c 0 python3.13 bench/json_repair/bench.py 2000
taskset -c 0 /tmp/json_repair_bench 2000
```

Use the median `seconds` for each variant. Each run must retain identical output
witnesses, `records 20000`, `per_round 616` and `checksum 1232000`. Ensure GC stress
is disabled and other builds/tests are not running before measuring. CPU pinning
does not isolate a shared host.

The [typing and scaling report](PROFILING.md) adds larger valid, malformed,
Unicode, logging and escaped-code-string workloads. It separates native code-size
changes from inconclusive timing differences and identifies quadratic rescanning.
