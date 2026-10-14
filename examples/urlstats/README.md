# urlstats: access-log URL reports

Summarize paths, query parameters and canonical URLs from Common or Combined
Log Format using [`urllib.parse`](../../lib/compatibility.md#urllibparse).
Canonicalization re-encodes path segments and sorts query pairs, preserving
escaped slashes within a segment.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 genlog.py 1000000 > access.log
python3 urlstats.py access.log
pystachy build urlstats.py -o urlstats
./urlstats --top 10 access.log
./urlstats --canon access.log
```

`--canon` emits a canonical URL per request instead of the summary; `--top N`
limits listed paths/URLs; `--time` reports reading and reporting times to stderr.
Invalid UTF-8 escapes are counted and decoded with U+FFFD; broken escapes such
as `%zz` remain unchanged. The generator includes reordered queries, non-ASCII
text and encoding edge cases. Tested reports match CPython.

<a id="urlstats-what-the-requests-of-an-access-log-asked-for-with-urllibparse"></a>
<a id="speed"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. Logs of 200k (26 MB) and 1M (131 MB) requests; median wall time of seven
process runs, including startup; peak RSS of one run. Other jobs shared the host.

| Log | Mode | CPython 3.13.16 | Pystachy AOT | CPython RSS | AOT RSS |
|---|---|---:|---:|---:|---:|
| 200k | report | 2.389 s | 0.433 s | 21.5 MB | 43.1 MB |
| 200k | `--canon` | 2.514 s | 0.462 s | 16.9 MB | 40.8 MB |
| 1M | report | 12.926 s | 2.196 s | 40.8 MB | 58.2 MB |
| 1M | `--canon` | 13.369 s | 2.482 s | 28.4 MB | 50.5 MB |

The baseline is 5.4–5.9× faster compiled with higher peak memory. CPython
caches `urlsplit` results; the port does not.

## Checks and reproduction

`tests/example_urlstats.py` compares 400 generated requests, malformed lines
and URL escaping/canonicalization edge cases with CPython.

```sh
python3 -I bench.py ../../pystachy 7
```

The benchmark writes generated inputs and executables to `build/urlstats/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
