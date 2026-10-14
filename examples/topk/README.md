# topk: word-frequency reports

Count words and adjacent pairs, then select frequent, longest and rarest words
with [`heapq.nlargest` and `nsmallest`](../../lib/compatibility.md#heapq).

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gentext.py 1000000 > text.txt
python3 topk.py text.txt
pystachy build topk.py -o topk
./topk --time text.txt
./topk --sort text.txt
```

`--sort` selects the same results by sorting all entries; the default uses a
small heap. `--time` reports counting and selection times to stderr. Ties retain
input order. The deterministic generator makes a Zipf-distributed vocabulary.
Both tested runtimes produce the same report.

<a id="topk-the-most-frequent-words-of-a-text-picked-with-heapq"></a>
<a id="what-the-heap-buys"></a>
<a id="tests"></a>

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. Texts of 1M (6.4 MB) and 4M (26 MB) words; median wall time of seven process
runs, including startup; peak RSS of one run. Other jobs shared the host.

| Text | Selection | CPython 3.13.16 | Pystachy AOT | CPython RSS | AOT RSS |
|---|---|---:|---:|---:|---:|
| 1M words | heap | 0.769 s | 0.520 s | 120.6 MB | 115.3 MB |
| 1M words | sort | 0.988 s | 0.564 s | 172.2 MB | 146.1 MB |
| 4M words | heap | 3.446 s | 2.493 s | 399.9 MB | 402.1 MB |
| 4M words | sort | 3.934 s | 2.641 s | 579.8 MB | 483.8 MB |

Heap selection is cheaper than sorting in either runtime. Counting dominates
the whole program, so its speedup is smaller than the selection-only speedup.

## Checks and reproduction

`tests/example_topk.py` compares counts and heap/sort selections over generated
text, including n=0 and n beyond the number of distinct words.

```sh
python3 -I bench.py ../../pystachy 7
```

The benchmark writes generated inputs and executables to `build/topk/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
