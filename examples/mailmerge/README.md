# mailmerge: template-based message rendering

Render an mbox file from a message template and tab-separated records using
[`string.Template`](../../lib/compatibility.md#string). The same source runs
under CPython and compiles with Pystachy.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 gendata.py 100000 > data.tsv
python3 mailmerge.py notice.txt data.tsv > notices.mbox
pystachy build mailmerge.py -o mailmerge
./mailmerge notice.txt data.tsv > notices.mbox
```

Create a template with headers and body, using `$name`, `${due}` or other
column names. `$$` writes a literal dollar sign. `$seq` and `$count` are supplied
as keyword arguments and take precedence over record fields.

The program validates placeholders before rendering. Missing fields stop it
unless `--safe` is used, which leaves those placeholders intact. `--split`
pre-splits a fixed template instead of using `Template` for every record.
Records are streamed; generated data and tested mailbox output are deterministic.

<a id="mailmerge-a-message-for-each-record-of-a-data-file-with-stringtemplate"></a>
<a id="what-template-costs"></a>
<a id="tests"></a>

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_mailmerge.py`](../../tests/programs/apps/example_mailmerge.py)
compares 150 generated messages, safe and split modes, and invalid or missing
placeholders with CPython.

The benchmark renders 100,000 generated records using `substitute()`,
`safe_substitute()` and the pre-split template path.

```sh
python3 -I bench.py ../../pystachy 7
```

Generated inputs and executables go to `build/mailmerge/` at the repository root.
Earlier measurements without a compiler revision are preserved in
[the historical table](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/mailmerge/README.md#recorded-benchmark).
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
