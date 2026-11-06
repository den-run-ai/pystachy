# Regex matchers generated from a profile (prototype)

Generate a matcher for each frequently used regex to avoid repeatedly decoding
its bytecode. The prototype in [`tools/re_specialize.py`](../tools/re_specialize.py)
records a program's patterns under CPython and generates Python functions that
Pystachy compiles with the program. `lib/re` uses a generated matcher when the
pattern and subject are supported, and otherwise keeps its bytecode interpreter.

The workflow is profile-guided AOT. Generated code can reduce matching time, but
adds build time and executable size; the [recorded measurements](#measurements)
show both costs.

## Use

### Record, generate and build

Run these commands from the repository root, replacing `prog.py` and `ARGS...`
with the program and its arguments:

```sh
python3.13 tools/re_specialize.py record -o build/prog-re.json prog.py ARGS...
python3.13 tools/re_specialize.py generate -o build/prog-re/_pystachy_re_specialized.py build/prog-re.json
PYSTACHY_PATH=build/prog-re ./pystachy build prog.py -o prog
```

`record` uses `sys.monitoring` to count calls to each compiled pattern's
`match`, `fullmatch`, `search`, `findall`, `finditer`, `split`, `sub`, `subn` and
`scanner` methods. It also sees bound-method calls, such as those from `fnmatch`.

`generate` writes one matcher per eligible pattern. Its module docstring lists
patterns it could not generate and the reasons.

| Generation input | Behavior |
|---|---|
| One or more profile files | Sum each pattern's calls across the supplied profiles. |
| `--min-calls N` | Generate patterns called at least `N` times; the default is 1. |
| `--pattern P [--flags F]` | Generate a matcher directly, without recording a program. |

### Make the generated module available

Place `_pystachy_re_specialized.py` on `PYSTACHY_PATH` or in the program's own
directory. The program directory takes precedence. Either location lets imports
find it before [`lib/_pystachy_re_specialized.py`](../lib/_pystachy_re_specialized.py),
the fallback module with no matchers.

The module name is reserved: `lib/re` imports the first module with that name,
so a program-local copy must be one the generator wrote. A missing pattern or
stale profile safely leaves that pattern on the interpreter.

### Recorder behavior

`record` runs the program with `runpy.run_path()`, preserving its exit status and
messages and importing from its directory. A program that never starts writes
no profile. Paths retain the spelling of `PROGRAM`: a relative path gives a
relative `__file__`, and a directory or zip file gives a relative first
`sys.path` entry.

The program shares the tool's interpreter. Modules the tool imports, including
`re` and `json`, are already loaded, and recording occupies one `sys.monitoring`
tool ID: 4 if available, otherwise the first free ID.

## How a matcher is used

When `re` compiles a pattern, `Pattern` calls `lookup(pattern, flags, code)`.
Lookup checks the source, flags and exact compiled bytecode against those used
to generate the matcher. Any mismatch falls back to the interpreter.

Matchers support subjects that `lib/re` reads in place: ASCII `str` values and
file bytes that are not UTF-8, which Pystachy reads as code points 0–255.
Decoded subjects use the interpreter.

| Entry point | Responsibility |
|---|---|
| `match()` | Serve `Pattern.match()` and `Pattern.fullmatch()`. |
| `attempt()` | Match at a candidate search position. `_sre.sre_search()` still chooses positions using literal prefixes, set scans, the bit-parallel alternative filter and literal finds. |

A generated matcher uses one native call per nested group-repeat iteration. If
an attempt would exceed 1,000 such iterations, it declines without changing the
caller's initial state. `sre_match()` then runs that attempt using the
interpreter's explicit stack, which has no corresponding limit.

## What a matcher is

Normally, `lib/re` compiles a pattern to CPython-compatible bytecode and
interprets it in [`lib/re/_sre.py`](../lib/re/_sre.py), a port of CPython's C
engine. The generator parses that bytecode into nodes and writes a function for
each point where the interpreter would push a context. These functions pass
continuations to preserve CPython's `sre_lib.h` operation order:

- Set capture marks and clear gaps between them.
- Save and restore `lastmark` and `lastindex` at alternatives and repeats.
- Preserve marks inside group repeats, as `MARK_PUSH` and `MARK_POP` do.
- Backtrack greedy single-character repeats with CPython's literal-tail skip;
  grow lazy repeats one character at a time.
- Stop group repeats after an empty iteration using `last_ptr`.
- Run lookaround and atomic bodies as separate submatches.
- Check `must_advance` and `match_all` at the top-level `SUCCESS`.

Character tests use 256-entry tables computed by `lib/re`'s own charset,
category, case-folding and word tests. They cover every code point an in-place
subject can hold and agree with the interpreter by construction.

The generator supports the opcodes `lib/re` emits for `str` patterns except
`GROUPREF_EXISTS`, used by conditionals such as `(?(1)a|b)`. Those patterns stay
on the interpreter, as do patterns whose generated matcher would exceed
4,000 lines.

This specializes on a pattern value, whereas Pystachy's existing templates
specialize on types. The motivation and earlier fixed-callback and fixed-regex
measurements are discussed in
[#392](https://github.com/den-run-ai/pystachy/issues/392).

## Measurements

### Setup and provenance

These are recorded prototype results against main
[`681bdd1`](https://github.com/den-run-ai/pystachy/commit/681bdd1) plus the matcher
changes. The original record identifies the changes as “this branch” without
pinning their revision; these numbers are historical evidence, not a benchmark
of current main.

The host was a shared 4-vCPU Xeon VM at 2.80 GHz, using CPython 3.13.16 and
LLVM 18.1.3. Each workload was profiled under CPython with the arguments below,
then built with and without matchers using `pystachy build`. Timings are medians
of five interleaved rounds, pinned to one core, for the timed workload only.
Every output matched CPython's. Speedup compares AOT without and with matchers.

### Matching time

| Workload | Matchers | CPython | AOT | AOT with matchers | Speedup |
|---|---:|---:|---:|---:|---:|
| `(\d{4})-(\d{2})-(\d{2})`: `finditer` and groups over a 1 MB log, ×5 | 1 | 171.6 ms | 129.2 ms | 62.3 ms | 2.07× |
| `[&<]`: a `search(s, pos)` loop over 1.7 MB of HTML, ×5 | 1 | 151.1 ms | 79.6 ms | 65.8 ms | 1.21× |
| `[A-Za-z_][A-Za-z0-9_]*`: `findall` over 1 MB of code, ×5 | 1 | 172.4 ms | 98.7 ms | 52.3 ms | 1.89× |
| `\s*(\w+)\s*=\s*(\d+)\s*$`: `match` on 20,000 short lines, ×10 | 1 | 116.9 ms | 140.5 ms | 68.6 ms | 2.05× |
| `html.parser.HTMLParser`: 10 feeds of a 2,000-row page | 10 | 683.0 ms | 501.8 ms | 257.7 ms | 1.95× |
| [`examples/route`](../examples/route/README.md) `--no-cache` routing: 1M events, 21 globs | 22 | 2,410 ms | 3,101 ms | 2,142 ms | 1.45× |
| pyperformance `regex_v8`, 20 loops | 231 | 492.9 ms | 440.2 ms | 252.5 ms | 1.74× |
| pyperformance `regex_effbot`, 20 loops | 17 | 623.1 ms | 329.0 ms | 269.7 ms | 1.22× |
| pyperformance `regex_dna`, 4 loops | 21 | 869.3 ms | 296.7 ms | 288.0 ms | 1.03× |

### Instruction counts and remaining costs

Callgrind counts measure the same work without wall-clock timing noise. The
values below are millions of instructions per loop, calculated as the difference
between runs of one and two loops.

| Workload | AOT | AOT with matchers |
|---|---:|---:|
| date pattern | 278M | 136M |
| `[&<]` loop | 132M | 113M |
| identifier `findall` | 194M | 94M |
| `match` on short lines | 113M | 36M |
| HTMLParser, per feed | 389M | 198M |
| `regex_v8` | 173M | 89M (100M with the 65 matchers of `--min-calls 1000`) |
| `regex_effbot` | 163M | 123M |
| `regex_dna` | 518M | 501M |

State and match objects are still allocated per call; they account for most of
the remaining cost in the `[&<]` loop. `regex_dna` instead spends much of its
time in decoding, substitutions and the alternative filter, which matchers
leave unchanged.

An earlier prototype generated its own search loop with a first-character
filter. It made the date pattern 3.0× faster but reduced `regex_dna` to 0.66×
its previous speed. The current design therefore retains the interpreter's
search loop and prefilters.

Without any generated matchers, Callgrind counts per loop changed by −0.7%
(`regex_v8`), +0.5% (`regex_effbot`) and +0.06% (`regex_dna`) relative to the
recorded main baseline. The IR for `tests/programs/library/lib_re.py` grew 0.9%.

### Build time and executable size

More generated matchers cost build time and binary size:

| Workload | Matchers | AOT build | Executable |
|---|---:|---:|---:|
| HTMLParser | 10 | 7.8 → 9.7 s | 593 → 671 KB |
| `regex_v8` | 231 (19,144 lines) | 12.9 → 53.2 s | 0.58 → 1.60 MB |
| `regex_v8`, `--min-calls 1000` | 65 (5,918 lines) | 20.0 s | 0.86 MB |

The 65 matchers selected by `--min-calls 1000` retained most of the runtime gain.
In a separate paired run, they took 243.5 ms, compared with 232.3 ms for all
231 matchers and 359.4 ms with none. These are single-run results, distinct from
the five-round medians above.

### JIT startup cost

`pystachy run` recompiles the matchers on every run because there is no
compiled-program cache yet
([#104](https://github.com/den-run-ai/pystachy/issues/104)). The recorded medians
of three runs show faster matching but a slower whole process:

| Workload | Whole process, without → with | Timed part, without → with |
|---|---:|---:|
| HTMLParser | 2.99 → 3.38 s | 553 → 311 ms |
| `regex_v8`, 65 matchers | 5.09 → 7.31 s | 450 → 318 ms |
| `regex_v8`, all 231 | 5.09 → 12.08 s | 460 → 279 ms |

## Validation

### Run the checks

From the repository root, use the unit tests or the larger differential check:

```sh
python3.13 -m unittest discover -s tools -p test_re_specialize.py
make re-specialize-check
make re-specialize-check RE_SPECIALIZE="2000 1"
```

The default differential check uses 400 patterns and seed 1. `RE_SPECIALIZE`
sets the pattern count and seed; the last command requests 2,000 patterns.

### What the tests cover

[`tools/test_re_specialize.py`](../tools/test_re_specialize.py), also run by
Lint, generates matchers for 300 random patterns and 38 hand-picked patterns.
Random cases cover supported constructs and flags. Hand-picked cases exercise
mark restoration in repeats, cleared gaps, stale groups, empty iterations,
lookaround captures and backreferences.

The matchers run in CPython-hosted `lib/re` and are compared with CPython's `re`.
Checks cover spans, groups, `lastindex` and `lastgroup` for `search`, `match`,
`fullmatch` (including `pos` and `endpos`), `finditer`, `findall`, `split` and
`subn`. In-place subjects containing all 256 byte values are compared against
CPython matching their Latin-1 decoding.

The same suite checks:

- CPython-compiled `html.parser` patterns on HTML.
- Deep-repeat fallback and termination after empty iterations.
- Rejection of mismatched source, flags or bytecode at lookup.
- Correct pattern and effective flags for `generate --pattern P --flags F`.
- Recorder call counts and program-running behavior.
- Agreement between generated output and the native test's checked-in matchers.

The [native differential test](../tests/programs/library/re_specialize.py) uses
its `.path` file to load 29 matchers generated from its own CPython profile. It
covers probe patterns, capture marks, `fnmatch` globs, non-ASCII subjects and a
repeat deeper than the generated-matcher limit, in JIT, AOT and GC-stress modes.

### Recorded validation results

The prototype validation recorded the following results; they are not fresh
runs against current main:

- With 2,000 patterns on each of seeds 1, 2 and 3, the differential check generated
  1,937, 1,957 and 1,949 matchers. About 1.9 million matcher answers agreed with
  CPython.
- Fifteen deliberate generator bugs failed a check, prevented termination or
  failed a unit test. They covered mark restores and gaps, repeat backtracking,
  lookbehind width, the INFO minimum, case folding, possessive and atomic groups,
  `must_advance` and the attempt's start. The unit test also caught an empty
  iteration that failed to end its repeat, although the depth limit hid it from
  result comparisons.
- The native test passed in JIT, AOT and with collection at every allocation.
  HTMLParser was excluded to keep CI's GC groups short. In the compiler's
  collect-every-1,000-allocations mode, its AOT build took 112 s with HTMLParser
  and matchers, 50 s with HTMLParser but no matchers, and 49 s without HTMLParser.
- Existing `lib/re`, `fnmatch`, `textwrap`, `html.parser` and router coverage
  passed 45 cases in JIT and AOT, for 90 runs. `make re-fuzz`, `make re-probe`
  (with unchanged counts) and `make check-recordings` also passed.

## Limits and next steps

| Boundary | Current behavior or next step |
|---|---|
| Unseen patterns | A pattern needs a profile entry or `--pattern`; patterns constructed from unseen run-time data use the interpreter. |
| Decoded subjects | Multi-byte decoded characters use the interpreter; see [#589](https://github.com/den-run-ai/pystachy/issues/589). |
| Caller fusion | Integrating a matcher into its caller could remove `Match` objects and per-call state. |
| Glob literals | Testing literal prefixes and suffixes of `fnmatch` globs needs no generated code. Separate router work measured 9.9×: 327 versus 3,248 ns per event. |
| Online compilation | Compiling newly observed patterns at run time needs in-process code loading ([#707](https://github.com/den-run-ai/pystachy/issues/707), [#704](https://github.com/den-run-ai/pystachy/issues/704)) and a code cache ([#104](https://github.com/den-run-ai/pystachy/issues/104)). |
