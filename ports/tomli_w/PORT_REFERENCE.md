# tomli-w 1.2.0: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `tomli_w-1.2.0.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `2dd14fac5a47c27be9cd4c976af5a12d87fb1f0b4512f81d69cce3b35ae25021`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `b85ea5a4b65f3f974a6a0327ece2d7d5702256eff8847315b8fba162afa3f410` | none |
| `_writer.py` | `76c89f152db161fd62efa9a64727f3f72d76e710bb67f1d0f38e592a126c617b` | 11 edits, 24 markers |

## Adaptation record

- Document/value functions are templates. Their `Any` and `Mapping[str, Any]` parameters keep
  upstream's annotations; those annotated `object`, `Mapping` or `tuple | list` are unannotated.
  Temporary table/literal lists hold keys and look up typed values when rendered.
- Type tests guard statically specialized branches. Chunk generators return lists.
- Date/time imports and branches are omitted, and identity-keyed inline-table caching is removed.
- `format_key_part()` has no `try` for the `TypeError` of a key that is no `str`: its message
  names `type(part)`, and keys are strings.
- `_writer.py` has eleven logical edits; `__init__.py` is unchanged. The re-baseline (#262)
  restored upstream's `TYPE_CHECKING = False` flag, its frozensets of characters and their
  `issuperset()`, and `hex()`, where earlier versions of the port used strings and loops.

## Validation snapshot

`tests/port_tomli_w_values.py` writes values: `str`s with quotes, backslashes, tabs, the short
escapes `\b`, `\f`, `\n`, `\r`, the other C0 controls and DEL as `\uXXXX`, and the C1 controls, the
byte order mark, U+10FFFF, an emoji, the first and last characters of each length in UTF-8, NEL
and the line and paragraph separators as they are; bare keys and quoted ones (empty, with a
space, a tab, a control character or a non-ASCII character); multiline strings (with CRLF, quotes,
backslashes and escapes, and strings that stay single-line) and the same text without the option;
`int`s at both 64-bit limits; `float`s (`inf`, `-inf`, `nan`, `-0.0`, `5e-324`, the largest, and
exponents); `bool`s; empty and nested arrays, and tuples; `indent=` 0, 1, 2 and the
`ValueError` for -1. `tests/port_tomli_w_tables.py` writes tables: an empty document, empty and
nested tables (with no header where they hold only tables), quoted keys in headers, and
arrays of tables, inline (each table at most 100 characters, the limit exactly, the same table
twice, nested inline tables, empty tables, a tuple of tables, an array of arrays of tables) or as
`[[...]]` tables (a table of 101 characters, a long value, a multiline string, arrays of tables in
tables and in arrays of tables), the limit at `indent=` 0, 2 and 8 (it counts the indent), the
order of keys deleted and set again, and 200 documents of random shapes (tables of arrays of
tables of `int`s, from a linear congruential generator, with keys that need quotes, at indents 0
to 5). Many cases are those of tomli-w's own tests
(`tests/test_style.py` and `tests/test_types.py` of its repository at tag 1.2.0; the sdist has
none), with one type of value in each container. `tests/port_tomli_w_ini2toml.py` is a program
of two ports, ini2toml: it reads INI text with `ports/iniconfig` and writes it as TOML with
`tomli_w`, a section as a table and a value continued on more lines as a multiline string, for a
`setup.cfg` and for a text with a byte order mark, comments, an empty section, a dotted section
name, non-ASCII text, quotes and backslashes in a continued value, an empty value, a `:` separator
and a tab. Its AOT build is a 121 KB executable, linked with libc, libm and libgcc_s only.

`tests/run.sh` compares what they print with CPython's, JIT and AOT. Run under CPython against the
unmodified upstream package (and the unmodified iniconfig 2.3.1), all three print exactly what they
print against this port. They pass JIT and AOT with `PYSTACHY_IRCHECK=1`, with the native compiler
and the CPython-hosted one, with `PYSTACHY_OPT=-all`, and in `make verify`'s gc-stress form (the
compiler collecting every 1,000 allocations, the program at every allocation), where the JIT run
and the AOT build and run of `port_tomli_w_values`, `port_tomli_w_tables` and
`port_tomli_w_ini2toml` take 1.6 s, 2.6 s and 1.1 s of CPU together (1.7 s, 2.6 s and 1.3 s of wall
clock), almost all of it the AOT build. Without gc-stress, each JIT run takes 0.1 to 0.2 s of CPU.
`tests/run.sh` passes as a whole (1,937 passed, 0 failed).
Under CPython, the port's `_writer.py` also writes what upstream's writes for 120,000 random
documents, with mixed types, non-ASCII text, nested arrays of tables and `indent=` 0 to 8, which
checks the edits of `gen_table_chunks()`.

## Benchmark snapshot

**Run time.** The headline workload: a document of 20,000 tables of 10 `str` values (a third of
the keys need quotes, and each value has quotes, a tab and a newline to escape), written with
`dumps()` 5 times (31.8 MB of TOML), then an array of 20,000 small tables, which stays inline
(0.75 MB). The program builds the document first, in both runs. Median of 5 runs, with process
start-up, on a 4-core x86-64 VM that was running other jobs (load 4 to 5):

| | CPU | wall clock |
|---|---:|---:|
| Pystachy AOT executable, this port | 1.59 s | 1.66 s |
| CPython 3.13.16, unmodified tomli-w 1.2.0 | 2.34 s | 2.42 s |

That is 1.47 times faster in CPU time (1.46 times in wall clock; an earlier set of runs, at load
11 to 16, gave the same CPU times). Timed inside the program with `time.process_time()` (3 runs),
the 5 `dumps()` take 1.44 to 1.45 s against 2.12 to 2.25 s (1.47 times), and the inline array of
tables 0.063 to 0.065 s against 0.058 to 0.059 s: slower, as the port renders each of its tables
twice, where upstream's cache renders it once. tomli-w is pure Python: there is no C extension
that CPython would run instead.

**Long strings with many escapes.** `format_string()` builds its result with `result += ...`,
twice for each character it escapes (a quote, a backslash or a control character) and for each
newline of a multiline string, and `+=` on a `str` copies it in Pystachy
([#112](https://github.com/den-run-ai/pystachy/issues/112)), where CPython extends it in place.
So the time to write one string grows with the square of its escapes: a value of 80,000 `"`
characters takes 0.88 s of CPU in the AOT build against 0.01 s in CPython, and one of 160,000
takes 3.15 s against 0.02 s. The strings of the workload above, a few escapes each, are not
affected.

**Build time.** `pystachy build` of a program that imports `tomli_w` and writes one document
takes 0.6 s of CPU (0.14 s for `print(1)`) and makes an 85 KB executable; each other type of
document compiles the writer's functions again. The tests' builds take 1.4 s, 1.8 s and 1.0 s of
CPU.
