# Named Unicode literal escapes: candidate measurements

This is an **unmerged candidate** for [#122](https://github.com/den-run-ai/pystachy/issues/122),
based on `44316e75fabc99108d3188c5b4d0d59e867f4a94`. It does not change the latest
evaluated-main revision or replace the historical compatibility audit.
[Normalized evidence](named-escapes-2026-10-18.json) retains source identities,
oracle inputs/outcomes, commands, consumer source and all timing samples.

The parser now resolves `\N{...}` through a names-only compiler helper using the
existing Unicode 15.1 generated table. It accepts character names, aliases and
derived names, with ASCII case-insensitive matching and significant spaces.
Named sequences remain invalid in source literals, although the runtime
`unicodedata.lookup()` API accepts them. Runtime Unicode code/data, the lexer and
the other parser methods are unchanged.

The helper returns a code point to the parser's existing UTF-8 encoder. It does
not consult the bootstrap interpreter's Unicode database, import the runtime
property database or generate another names table. Names decoding is lazy;
Hangul syllables use the algorithmic path without decoding that table. The
build dependency list and hosted compiler/cache fingerprint include the table.

## Correctness measured so far

Environment: Linux x86-64, CPython **3.13.16**, LLVM/Clang **18.1.3**, GNU ld
**2.42**, four logical CPUs, `PYSTACHY_JOBS=4`. The toolchain was extracted into
a local directory; Clang uses its matching GCC support directory, and a shell
wrapper supplies the extracted linker's shared-library directory. No project
verification gate was weakened for that layout.

- Baseline and candidate both reach three-stage compiler/runtime IR fixed
  points. Compiler IR grows from **621,423** to **627,615** lines; runtime IR
  stays at **18,388** lines.
- A frozen CPython oracle contains **60** expressions: 40 accepted and 20
  rejected. The baseline rejects 32 valid named-escape expressions. Hosted
  and native candidate compilers agree with all **60 syntax decisions** and
  all **20 rejection messages**.
- The 13 newly added source fixtures produce **4 passed / 11 failed** checks
  on the baseline. The broader selection of these fixtures, existing f-string
  boundaries and runtime Unicode tests passes **124 checks across 66 source
  fixtures** with each compiler, including JIT, AOT and applicable syntax checks.
  The new fixtures explicitly assert decoded code points, raw/backslash rules,
  aliases, derived-name bounds and named-sequence rejection.
- `tools/syntax_sweep.py` agrees with CPython on all **13 new source fixtures**.
- Independent helper checks cover all **473 aliases**, each in original and
  lowercase spelling, and reject all **461 named sequences**, also in both
  spellings. Thirty additional boundary cases pass. Running those helper
  checks on Python 3.12/Unicode 15.0 still accepts the shipped Unicode 15.1
  Extension I endpoints; accepted names are independent of the host database.

The actual iniconfig 2.3.1 `_parse.py` is a concrete consumer: its
`UTF8_BOM: Final = "\N{BYTE ORDER MARK}"` fails on the baseline, while candidate
JIT and AOT both parse BOM-prefixed and ordinary synthetic INI input, preserve
the expected values/source lines and match CPython's exact 44-byte output.
The parser was recovered by reversing the one documented BOM spelling edit in
the retained port; its complete bytes match upstream SHA-256
`15824a78105b52aa9ed414ce6ad073967c73be7ea5ae9d991a0df97a6e0cc2e1`.
`exceptions.py` is unchanged. An explicitly labelled empty package shim avoids
importing the adapted `IniConfig` wrapper. This proves the original parser
consumer, **not** full unmodified iniconfig or its upstream test suite.

`make lint` passes Ruff, shellcheck and Clang's warning checks. The full CPython
recording check covers 1,235 recordings, 76 deviations and nine library copies,
with **one failure**: the unchanged `exc_except_attr` test removes
`/nonexistent_zz`; this workspace returns `OSError(30, 'Read-only file system')`
where the recording expects `FileNotFoundError(2, 'No such file or directory')`.
Both that fixture and its recording are byte-identical to the baseline.
Neither was edited to hide the environment difference. The separate six-file
agent-example provenance check passes. Full verification is still running;
there is no complete matrix-pass or merge-readiness claim.

Reproduce the focused checks from the candidate checkout:

```sh
make
tests/run.sh ./pystachy 'jit aot' tests/syntax_named_unicode.py \
  tests/syntax_fstring*.py tests/lib_unicodedata*.py \
  tests/errors/syntax_named_unicode*.py tests/errors/syntax_fstring*.py
tests/run.sh 'python3.13 -m pystachy' 'jit aot' tests/syntax_named_unicode.py \
  tests/syntax_fstring*.py tests/lib_unicodedata*.py \
  tests/errors/syntax_named_unicode*.py tests/errors/syntax_fstring*.py
python3.13 -I tools/syntax_sweep.py --compiler ./pystachy \
  tests/syntax_named_unicode.py tests/errors/syntax_named_unicode*.py
make lint check-recordings
python3.13 tools/check_agent_source.py
make verify
```

## Compiler size and parser startup

The same build procedure produces these native binaries:

| | Baseline | Candidate |
|---|---:|---:|
| Bytes | 3,406,280 | 4,134,640 |
| SHA-256 | `7119ee47cc8471759a688143d554da3ee9a36b49f446f9e31d9069ccabd31f11` | `1ff50e8a2ad16735e1d0cb2d6b7b148d109b77912260903d55a9269e801eddb6` |

The increase is **728,360 bytes (21.38%)**. The reused generated table's source
file is 713,163 bytes; source bytes and linked binary bytes are different
measurements. No peak-memory measurement was made.

Each timing command starts a fresh process. Thirty-three interleaved rounds
reverse command order on alternate rounds; two warmup rounds are discarded,
leaving 31 samples per command. These are **warm OS/page-cache** measurements
on a shared host, with no concurrent task-local build or heavy tests. `check`
parses a tiny source file and does not invoke LLVM or execute its contents.

| Command/input | Baseline median ms | Candidate median ms |
|---|---:|---:|
| `--version` | 3.192 | 3.250 |
| `check`: `print("hello")` | 3.232 | 3.361 |
| `check`: `print("\N{BYTE ORDER MARK}")` | unsupported | 12.651 |
| `check`: `print("\N{BULLET}")` | unsupported | 12.255 |
| `check`: `print("\N{CJK UNIFIED IDEOGRAPH-2EBF0}")` | unsupported | 12.505 |
| `check`: `print("\N{HANGUL SYLLABLE GA}")` | unsupported | 3.339 |

The ordinary-startup sample ranges overlap; they do not establish a small
speedup or regression. The first table-backed lookup costs roughly 9 ms beyond
ordinary parsing in this sample. Hangul avoids that decode. These figures do
not measure cold OS startup, JIT/AOT compilation throughput, steady-state user
program speed or repeated-name workloads.

The candidate chooses reuse of the existing table plus a small names-only
decoder: one versioned data source, deterministic bootstrap behavior and no
runtime property database dependency, at the measured binary-size and first-use
costs above. The maintainer can assess that tradeoff without relying on the
older from-scratch prototype's measurements.

The decoder adapts `lib/_pystachy_unicodedata.py`; the Python and Unicode license
notices are retained in `THIRD_PARTY_NOTICES`. No generated data was changed.
