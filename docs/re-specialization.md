# Regex matchers generated from a profile (prototype)

`lib/re` compiles each pattern to the bytecode CPython's compiler makes, then interprets it in
`lib/re/_sre.py`, a port of CPython's C engine. A program usually compiles a handful of patterns and
runs each one many times, so the interpreter decodes the same code again and again.
`tools/re_specialize.py` removes that work. It records which patterns a program uses, then writes
Python functions that each match one pattern. They are compiled with the program, and `lib/re`
runs them instead of the interpreter.

This is value specialization, keyed on the pattern rather than on a type. Pystachy's templates
already specialize code by type at build time. The evidence for keying on values instead is in
[#392](https://github.com/den-run-ai/pystachy/issues/392) and its follow-up discussion: the two
measured wins of skewed-type experiments came from a fixed callback and a fixed regex. A `Pattern`
object always runs the same code. The matchers are generated ahead of time from a profile, as
profile-guided AOT. Online tier-up, as V8 does for regexps, would need in-process code loading
([#707](https://github.com/den-run-ai/pystachy/issues/707),
[#704](https://github.com/den-run-ai/pystachy/issues/704)) and a code cache
([#104](https://github.com/den-run-ai/pystachy/issues/104)).

## Use

Record, generate, build:

```sh
python3.13 tools/re_specialize.py record -o build/prog-re.json prog.py ARGS...
python3.13 tools/re_specialize.py generate -o build/prog-re/_pystachy_re_specialized.py build/prog-re.json
PYSTACHY_PATH=build/prog-re ./pystachy build prog.py -o prog
```

`record` runs the program under CPython. It uses `sys.monitoring` to count the matching calls made
on each compiled pattern: `match`, `fullmatch`, `search`, `findall`, `finditer`, `split`, `sub`,
`subn` and `scanner`, wherever they are called (also through bound methods, as `fnmatch` makes
them). `generate` writes one matcher for each pattern called at least `--min-calls` times
(default 1), counting the calls of all the profiles it reads. It also takes `--pattern P [--flags F]`.
The module's docstring lists the patterns it could not generate, with the reason.

Imports find the generated module before `lib/_pystachy_re_specialized.py`, which has no matchers.
That holds when the module is on `PYSTACHY_PATH` or in the program's own directory, which comes
first. A stale profile is harmless: a pattern it lacks keeps the interpreter. The name is reserved
for this module: `lib/re` imports whichever `_pystachy_re_specialized.py` comes first, so a
program's own module of that name must be one the tool wrote.

## How a matcher is used

When `re` compiles a pattern, `Pattern` calls `lookup(pattern, flags, code)`. The lookup matches on
the source and flags, then compares the bytecode the pattern compiled to with the bytecode the
matcher was generated from. Any difference means no matcher.

A matcher runs only on a subject that `lib/re` reads in place: an ASCII `str`, or a file's bytes
that are not UTF-8, which Pystachy reads as code points 0 to 255. A decoded subject keeps the
interpreter. There are two entry points:

- `match()` serves `Pattern.match()` and `fullmatch()`.
- `attempt()` runs at each position a search tries. The search loop is still `_sre.sre_search()`,
  with all of its prefilters: literal prefixes, set scans, the bit-parallel alternative filter and
  literal finds. Only the work at each candidate position changes.

A matcher declines a match that would nest more than 1,000 group-repeat iterations. Each iteration
is a native call, and the interpreter's explicit stack has no such limit. Declining leaves the state
as the caller set it up, and `sre_match()` runs that attempt.

## What a matcher is

The generator parses the bytecode into nodes. It writes one function per point where the
interpreter would push a context, which is continuation-passing style. Each opcode does what
CPython's `sre_lib.h` does, in the same order:

- marks are set, and the marks between them cleared;
- `lastmark` and `lastindex` are saved and restored at alternatives and repeats;
- the data stack keeps mark values inside group repeats, as `MARK_PUSH` and `MARK_POP` do;
- greedy single-character repeats give characters back, with CPython's literal-tail skip;
- lazy repeats take one more each time;
- group repeats stop after an empty iteration, by `last_ptr`;
- lookaround and atomic bodies are separate submatches;
- `must_advance` and `match_all` are checked at the top-level `SUCCESS`.

Character tests are tables of 256 entries. They are computed by `lib/re`'s own functions (`charset`,
`category`, case folding and word tests) for every code point an in-place subject can hold, so they
agree with the interpreter by construction.

The generator writes every opcode `lib/re` emits for `str` patterns except `GROUPREF_EXISTS`
(`(?(1)a|b)`). Patterns that use it keep the interpreter. A pattern whose matcher would exceed
4,000 lines does too.

## Measurements

Main `681bdd1` plus this branch, on a shared 4-vCPU Xeon VM at 2.80 GHz, with CPython 3.13.16 and
LLVM 18.1.3. Each workload was profiled under CPython with the arguments shown, then built twice
with `pystachy build`, with and without its matchers. The table gives medians of five rounds of
the timed part, pinned to one core, with the three modes interleaved. Every output matched
CPython's.

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

Callgrind counts the same work without the host's noise. These are per-loop differences between
runs of one and two loops:

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

- **Remaining costs.** Allocating the state and match objects is still per call. That is most of
  what remains in the `[&<]` loop. `regex_dna` spends its time in decoding, substitutions and the
  alternative filter, which the matchers leave unchanged.
- **First version.** An earlier version of this prototype generated a search loop per pattern,
  with a first-character filter in place of the interpreter's prefilters. It ran the date pattern
  3.0× faster but made `regex_dna` 0.66× as fast, so the interpreter's search loop now calls the
  matchers.
- **Without matchers.** Programs keep the interpreter's cost: callgrind counts per loop changed by
  −0.7% (`regex_v8`), +0.5% (`regex_effbot`) and +0.06% (`regex_dna`) against main's `lib/re`. The
  IR of `tests/lib_re.py` grows by 0.9%.
- **Build size.** Generated code costs build time and binary size, roughly in proportion to the
  number of matchers:

  | Workload | Matchers | AOT build | Executable |
  |---|---:|---:|---:|
  | HTMLParser | 10 | 7.8 → 9.7 s | 593 → 671 KB |
  | `regex_v8` | 231 (19,144 lines) | 12.9 → 53.2 s | 0.58 → 1.60 MB |
  | `regex_v8`, `--min-calls 1000` | 65 (5,918 lines) | 20.0 s | 0.86 MB |

  The 65 matchers keep most of the gain: 243.5 ms against 232.3 ms with all 231, and 359.4 ms with
  none, in one paired run.
- **The JIT.** `pystachy run` compiles the matchers on every run, since there is no
  compiled-program cache yet ([#104](https://github.com/den-run-ai/pystachy/issues/104)).
  Medians of three runs:

  | Workload | Whole process, without → with | Timed part, without → with |
  |---|---:|---:|
  | HTMLParser | 2.99 → 3.38 s | 553 → 311 ms |
  | `regex_v8`, 65 matchers | 5.09 → 7.31 s | 450 → 318 ms |
  | `regex_v8`, all 231 | 5.09 → 12.08 s | 460 → 279 ms |

## Validation

- `tools/test_re_specialize.py`, which Lint runs, generates matchers for 300 random patterns and 38
  hand-picked ones. The random patterns cover every construct the generator writes, with flags.
  The hand-picked ones exercise the subtler mark rules: restores inside repeats, cleared gaps, stale
  groups kept, empty iterations, lookaround groups and backreferences. Each runs inside
  CPython-hosted `lib/re` on random subjects and is compared with CPython's `re`: the spans, groups,
  `lastindex` and `lastgroup` of `search`, `match`, `fullmatch` (also with `pos` and `endpos`),
  `finditer`, `findall`, `split` and `subn`. The same patterns also run on in-place subjects of all
  256 byte values, against CPython's `re` on their Latin-1 decoding.
- The same test checks six more properties:
  - `html.parser`'s own patterns, as CPython compiles them, give CPython's results on HTML;
  - deep repeats decline and still match as CPython does;
  - empty iterations end a repeat;
  - a lookup with other code, flags or source finds no matcher;
  - `generate --pattern P --flags F` keys the matcher by `P` and the flags its `Pattern` has;
  - the recorder counts calls, running the program as `python3.13 PROGRAM` does, and the checked-in
    matchers of the native test are what the tool writes.
- `make re-specialize-check` runs more patterns. With 2,000 patterns on each of seeds 1, 2 and 3,
  1,937, 1,957 and 1,949 matchers were generated, and all agreed with CPython in about 1.9M matcher
  answers.
- Fifteen deliberate generator bugs each fail the check, never finish, or (an empty iteration that
  does not end its repeat, which the depth limit hides from the results) fail the unit test. They
  cover mark restores, repeat backtracking, lookbehind width, the INFO minimum, case folding,
  possessive and atomic groups, `must_advance`, the attempt's start and mark gaps.
- `tests/re_specialize.py` is the native differential test. Its `.path` file finds the 29 matchers
  generated from its own CPython profile. It covers the probe patterns, mark cases, `fnmatch` globs,
  non-ASCII subjects and a repeat deeper than the limit. It passes in JIT and AOT, and with a
  collection at every allocation. It leaves out HTMLParser to keep CI's GC groups short. There the
  compiler collects every 1,000 allocations: with HTMLParser and its matchers, the test's AOT build
  took 112 s (50 s without matchers); without HTMLParser, it takes 49 s.
- The existing `lib/re`, `fnmatch`, `textwrap`, `html.parser` and router tests pass in JIT and AOT:
  45 cases, 90 runs. `make re-fuzz`, `make re-probe` (its counts unchanged) and
  `make check-recordings` pass too.

## Limits and next steps

- **Profile only.** Matchers come from a profile or from `--pattern`. A pattern built at run time
  from data the profile did not see keeps the interpreter.
- **In-place subjects only.** Decoded subjects, which hold characters of several bytes, keep the
  interpreter ([#589](https://github.com/den-run-ai/pystachy/issues/589)).
- **Caller fusion.** Fusing a matcher into its caller would remove the `Match` objects and the
  per-call state, as "specializing higher up the call stack" would.
- **Glob literals.** Literal prefixes and suffixes of `fnmatch` globs can be tested without any
  generated code. In the router that analysis alone measured 9.9× (327 against 3,248 ns per event).
  That is separate work.
- **Online tier-up.** Compiling matchers at run time, for patterns the profile missed, needs
  in-process code loading and a cache.
