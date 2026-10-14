# Porting and upstream test coverage

Pystachy's library has three kinds of implementation: unchanged Python modules,
upstream modules adapted to the static subset, and typed implementations of components
that CPython supplies in C. Each needs evidence for the behavior it actually supports.

## Two different correctness claims

Running an edited module under CPython with upstream's tests checks that the edits
preserve its behavior there. It does not establish that those tests compile, or that
the compiled module takes the same implementation paths. For example,
`lib/functools.py` selects CPython's native cache wrapper under CPython. Some ports
also keep CPython-only branches for APIs the subset does not support.

Compiled compatibility comes from running supported cases through Pystachy and
comparing them with upstream on CPython. `tests/run.sh` already does this with the
recordings checked by `make check-recordings`. `make test-py` means the *compiler*
runs under CPython; the test programs still run compiled, in JIT and AOT modes.

Keep these claims separate in a port's documentation and reports. A passing hosted
suite is never a count of passing compiled upstream cases.

## Prototype checks

This is the first bounded implementation of [#361](https://github.com/den-run-ai/pystachy/issues/361).
The acceptance manifest covers **fnmatch and textwrap only**. It does not inventory
the whole CPython suite or certify every module in `lib/`.

```sh
make port-check
make test-cpython-subset
make port-check-large
```

Use the exact CPython version in `.python-version` (currently 3.13.16), or set
`PY=/path/to/python3.13`. `port-check` needs no LLVM. `port-check-large` needs the
normal LLVM toolchain and builds the native compiler; use
`PORT_COMPILER=build/verify/pystachy2` to reuse a verified compiler and
`PYSTACHY_LLVM=/path/to/llvm/bin` to select its tools.

`port-check` verifies the vendored upstream source, tests and license against pinned
SHA-256 values. The files come from CPython commit
`cbc944f4bc59639a444dd971c737788ba2283a91` (3.13.16). It checks the exact recorded
adaptation diff against the current port, validates the upstream case inventory,
and runs the unedited upstream suite against the edited module in an isolated
CPython process. Import location and test counts are checked, so importing the
host's original module or discovering no tests cannot produce a passing result.
The report is `build/port-check.json`.

The adaptation diff makes every source change reviewable and prevents an unrecorded
change from passing CI. It does **not** establish that a nearby `# Pystachy port:`
comment explains an entire diff hunk. Reviewers still check the reason for each
adaptation; blindly refreshing the diff is not an acceptance check.

The per-case manifest distinguishes complete compiled coverage, partial coverage,
documented deviations, unsupported cases and cases not yet mapped to complete
upstream assertions. Partial means that supported assertions run, but a substantive
operation or input remains unsupported or adapted. A similar input or a reference
to a test file is not evidence that every assertion of an upstream method has been
preserved.

Initial inventory (counts are upstream test methods, not individual assertions):

| Module | Hosted upstream pass | Complete compiled mappings | Partial | Deviation | Unsupported | Not yet mapped |
|---|---:|---:|---:|---:|---:|---:|
| fnmatch | 17/17 | 12 | 2 | 0 | 3 | 0 |
| textwrap | 66/66 | 63 | 1 | 2 | 0 | 0 |

`make test-cpython-subset` runs the actual compiled expansion: the fnmatch suite,
three textwrap files and seven selected cache/lru_cache methods from
`test_functools.py`. It compares native JIT/AOT execution with CPython recordings.
These five differential programs are in the normal corpus, so CI also exercises
them with both compiler hosts, GC stress, UBSan and optimizations disabled. The
individual upstream method IDs appear in the source and completion output.

The fnmatch selection retains 2,372 assertions from 12 complete methods, plus seven
assertions from the two partial methods. Textwrap retains the complete assertion
sets of 63 methods. Its two Unicode failures are exercised in a separate deviation
test. One method retains its result assertions with a changed wrapper initialization;
the original bool-to-int field assignment has its own rejection test and is counted
as partial. No methods remain unmapped in either inventory.

The seven functools methods retain 23 assertion statements (38 checks including
loops), covering cache statistics, clearing, recursion, negative and None maxsize,
keyword calls and a reentrant miss. Recursive helpers move to module scope and one
captured flag becomes a one-cell list; these adaptations are disclosed in the file.
This is a selected cache suite, not an inventory of all functools APIs. Its header
pins upstream's test file by commit and SHA-256 and names unsupported exclusions.
Its IDs name the upstream source mixins (`TestCache` and `TestLRU`), each run once
against CPython's public wrapper and Pystachy's implementation.

`port-check-large` runs four supported `test_re.ReTests` methods at upstream input
sizes under CPython and compiled JIT/AOT: 50,000 group repeats, the large lazy-repeat
regression, 10,000 alternatives, and a 10,000,000-character anchored search. It uses
normal GC, compares results, and has bounded process timeouts. Upstream's CPU-time
assertion is omitted; elapsed times are informational. The smaller versions continue
to exercise the collect-at-every-allocation configuration in the regular corpus.
These four cases are a separate explicit selection, not a complete regex inventory.

CI runs `port-check` and `port-check-large` as independent jobs beside the existing
verification groups; the compiled subset belongs to those groups' normal corpus.
The existing required verification gate also requires both jobs to succeed. The
large fixture lives under `tests/upstream/` so the regular `tests/*.py` glob does not
multiply these inputs through every stress configuration.

## Checklist for extending a port

1. Try upstream unchanged, then make small, explained adaptations. Keep the source
   valid Python. A compiler feature should serve more than one library.
2. Pin upstream source and tests together, record their hashes and license, and
   retain an exact, reviewed adaptation diff. Change pins deliberately.
3. Run upstream tests against the edited source on CPython and verify which module
   was imported. Record the actual tests and exceptions, including skips.
4. Import supported upstream cases into the differential corpus, preserving their
   assertions and naming their source methods. Use ordinary functions, tables and
   assertions rather than implementing `unittest` inside the compiler.
5. Account for every inventoried case. Record a concrete reason and evidence for
   deviations or exclusions. Do not silently normalize Unicode offsets or remove
   failing assertions to count a whole method as covered.
6. Put unsupported uses in `tests/errors/` and observable differences in
   `tests/deviations/`. Non-ASCII behavior remains part of the inventory while
   [#120](https://github.com/den-run-ai/pystachy/issues/120) is open.
7. Measure runtime, build time and memory separately from correctness. Compare
   upstream CPython, the adapted source on CPython, JIT and AOT; disclose losses
   and CPython-only accelerators as well as gains.

Next extensions should address the recorded Unicode and typing exclusions, then
expand other suites such as heapq and bisect and the remaining supported cache cases.
Large generated inputs and longer fuzz campaigns can be expanded independently;
this prototype does not schedule a nightly workflow or add a general test transpiler.
