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

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_topk.py`](../../tests/programs/apps/example_topk.py)
compares counts and heap and sort selections over generated text, including
`n=0` and `n` beyond the number of distinct words.

The benchmark generates texts of one and four million words and compares heap
selection with sorting. Both modes first build the word and adjacent-pair counts.

```sh
python3 -I bench.py ../../pystachy 7
```

Generated inputs and executables go to `build/topk/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/topk/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
