# latency: access-log statistics

Summarize request latency by endpoint with
[`statistics`](../../lib/compatibility.md#statistics): means, byte-weighted means,
medians, p90/p99, geometric means, common status and server-error rate.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 genlog.py 1000000 > access.log
python3 latency.py access.log
pystachy build latency.py -o latency
./latency --time access.log
```

Input rows contain time, method, path, status, latency in milliseconds and
response size in bytes. Endpoints are ordered by total request latency. `-`
latencies count toward statuses only; malformed lines are skipped and counted.
`--time` reports reading and calculation times to stderr. The generated input
and reports are deterministic across the tested runtimes.

<a id="latency-the-request-latencies-of-each-endpoint-of-an-access-log-with-statistics"></a>
<a id="what-compiling-buys"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. Logs of 1M (55 MB) and 4M (218 MB) requests; median of seven alternating
process runs, including startup; peak RSS of one run. Other jobs shared the host.

| Log | CPython 3.13.16 | Pystachy AOT | Speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| 1M requests | 2.322 s | 1.489 s | 1.56× | 137.2 MB | 162.3 MB |
| 4M requests | 12.223 s | 8.519 s | 1.43× | 512.5 MB | 668.2 MB |

Repeated sorting for medians and quantiles dominates calculation. The compiled
program uses more peak memory despite storing floats unboxed.

## Checks and reproduction

`tests/example_latency.py` compares 3,000 generated requests, malformed rows,
single-request endpoints, timeouts and empty responses with CPython.

```sh
python3 -I bench.py ../../pystachy 7
```

The benchmark writes generated inputs and executables to `build/latency/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
