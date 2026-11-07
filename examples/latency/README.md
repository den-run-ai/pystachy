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

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_latency.py`](../../tests/programs/apps/example_latency.py)
compares 3,000 generated requests, malformed rows, single-request endpoints,
timeouts and empty responses with CPython.

The benchmark generates logs of one and four million requests. The program retains
latencies for each endpoint and sorts them for medians and quantiles.

```sh
python3 -I bench.py ../../pystachy 7
```

Generated inputs and executables go to `build/latency/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/latency/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
