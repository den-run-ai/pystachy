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

## Recorded benchmark

Historical measurements on a 4-core x86-64 VM; the compiler commit was not
recorded. 100,000 records (7.9 MB input, 47 MB output); median wall time of seven
process runs, including startup; peak RSS of one run. This baseline predates
later regex optimizations; see [caching measurements](../../docs/caching.md).

| mode | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| `substitute()` | 1.265 s | 0.969 s | 1.30x | 10.9 MB | 36.5 MB |
| `--safe`, `safe_substitute()` | 1.249 s | 0.933 s | 1.34x | 11.0 MB | 36.5 MB |
| `--split` | 0.389 s | 0.292 s | 1.33x | 11.0 MB | 36.2 MB |

Pre-splitting the template was about 3× faster in either runtime. Each compiled
mode was about 1.3× faster than its CPython counterpart in this baseline.

## Checks and reproduction

`tests/example_mailmerge.py` compares 150 generated messages, safe/split modes
and invalid or missing placeholders with CPython.

```sh
python3 -I bench.py ../../pystachy 7
```

The benchmark writes generated inputs and executables to `build/mailmerge/` at the
repository root. Results depend on workload and host; see
[the performance guide](../../docs/performance.md).
