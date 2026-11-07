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

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_urlstats.py`](../../tests/programs/apps/example_urlstats.py)
compares 400 generated requests, malformed lines, and URL escaping and
canonicalization edge cases with CPython.

The benchmark generates logs of 200,000 and one million requests and exercises
summary and canonical-output modes. Both CPython and the port cache `urlsplit()`
results; the workload determines how often that cache can help.

```sh
python3 -I bench.py ../../pystachy 7
```

Generated inputs and executables go to `build/urlstats/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/urlstats/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
