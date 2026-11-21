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

Inventory (counts are upstream test methods, not individual assertions):

| Module | Hosted upstream pass | Complete compiled mappings | Partial | Deviation | Unsupported | Not yet mapped |
|---|---:|---:|---:|---:|---:|---:|
| fnmatch | 17/17 | 12 | 2 | 0 | 3 | 0 |
| textwrap | 66/66 | 65 | 1 | 0 | 0 | 0 |

`make test-cpython-subset` runs the actual compiled expansion: the fnmatch suite,
four textwrap files and seven selected cache/lru_cache methods from
`test_functools.py`. It compares native JIT/AOT execution with CPython recordings.
These six differential programs are in the normal corpus, so CI also exercises
them with both compiler hosts, GC stress, UBSan and optimizations disabled. The
individual upstream method IDs appear in the source and completion output.

The fnmatch selection retains 2,372 assertions from 12 complete methods, plus seven
assertions from the two partial methods. Textwrap retains the complete assertion
sets of 65 methods, including two formerly divergent Unicode cases now recorded
against CPython. One method retains its result assertions with a changed wrapper initialization;
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

Lint runs `port-check`. Native verification runs `port-check-large` after bootstrap,
and its normal corpus covers the compiled subset. The large fixture lives under
`tests/upstream/` to keep those inputs out of every stress configuration.

## Port one application component at a time

Choose a component with a small interface and output you can compare byte for byte.
The [JSON repair companion](../examples/json_repair/README.md) shows how to keep
a CPython host and verify the actual native extension against upstream results.

For a component that stores several iterator implementations, follow the
[typed iterator tutorial](../examples/typed_iterator/README.md). It uses an explicitly
annotated `Callable` field to share one typed consumer across list, tuple, custom
iterator and generator sources. The tutorial includes a CPython recording, native
JIT/AOT and GC-stress commands, and inspection of the actual compiled interface.
This is a bounded adaptation with an integer item contract; broader `Iterable[T]`
and `Protocol` storage remains a separate language feature.

Experiments with mypy and mypyc illustrate two ways to choose that boundary.

| Component | What the experiment checked |
|---|---|
| [mypy `stubgen` documentation parser](https://github.com/den-run-ai/mypy/commit/020c4327eda82b02eaf56c630b799b3c74f8eb0f) | CPython ran the CLI with an adapted parser. The native extension and the AOT and JIT workers produced the same four `.pyi` files as the CPython reference. The linked fork patch reuses the documentation index across modules and can run entirely on CPython. |
| [mypyc `NameGenerator`](https://github.com/python/mypy/blob/1231cf158a9cab0c41f613f3d8070c1332632f29/mypyc/namegen.py) | The upstream module compiled in isolation. A separate two-module build using an extension for name generation preserved generated C, headers and IR. |

These are component prototypes. The supported ports and their test commands are
listed in the [ports catalog](../ports/README.md).

## Survey a program's rejections

A compilation stops at its first rejection, so an unported module shows one restriction
per compilation. `tools/rejection_survey.py` lists several in one run, without changing the
compiler or the sources. It compiles, with `pystachy ir`, a scratch copy of the program and
of the modules that it imports. After each rejection it replaces the body of the innermost
function that holds the diagnostic's line with a stub and compiles again. A stub keeps the
signature, the decorators and the number of every other line, so each diagnostic names an
original line. The program is never run.

```sh
python3 tools/rejection_survey.py example.py
python3 tools/rejection_survey.py --compiler ./pystachy --path upstream/src --json entry.py
```

`--compiler` defaults to the checkout's hosted compiler, which needs no build; a native
compiler is faster. `--path` lists module directories as `PYSTACHY_PATH` does and
defaults to it. `--max N` bounds the rejections (default 20), `--timeout S` each
compilation (default 120 seconds), and `--keep DIR` saves the stubbed copy. For a program
whose `Box.__init__` assigns `self.size = size + "px"`, whose `Box.area()` returns
`self.size * 2` and whose `total()` adds `"1"` to the sum of a list of `int`s, the report
is as follows; a last line, not shown, restates the first limit below.

```text
1. example.py:3: error: cannot infer the type of field 'size'; annotate it (self.size: T = ...)
   in Box.__init__
2. example.py:10: error: unsupported operand type(s) for +: 'int' and 'str' (compiling total(list[int]) for the call at example.py:13)
   in total
3. example.py:6: error: 'Box' object has no attribute 'size'
   in Box.area; may follow from the stub of Box.__init__ (rejection 1)
3 rejections in 4 compilations of example.py. With 3 functions stubbed, the copy compiles.
```

The third rejection comes of the stub of `__init__`, which no longer assigns `size`. Read a
report with these limits in mind:

- **Reach.** Only code that the entry reaches is compiled: not a module that nothing
  imports, nor a function that nothing calls unless its parameters and result are all
  annotated ([templates](language/typing.md#function-and-method-templates)), nor code that
  only a stubbed body reached. A function reports at most one rejection. To survey a
  library module, write an entry that calls each of its functions from a function of its own.
- **Rejections that no stub removes.** The survey ends at a rejection outside any function
  (at module level or in a class body), in a file outside the copy (the compiler's own
  `lib/`) or in a file that CPython's `ast` cannot parse, and at one that recurs in a
  stubbed function, as a rejected signature or decorator does. The summary line names it.
- **Stubs change the program.** A stub raises `NotImplementedError`. A generator's stub
  also holds a `yield`, and an unannotated method that must return a type, such as
  `__len__` or `__eq__`, returns a constant of that type. A function that only raises has no
  result type of its own, and a stubbed method no longer assigns its fields. A rejection is
  marked as one that *may follow from* a stub when its function uses the stubbed function's
  name or such a field, or the statement at a call site that its diagnostic names does,
  directly or through a variable assigned from such a use. The mark goes by names only: it
  can be missing, or present without cause.

The exit status follows `tools/inspect_compiler.py`: 0 when the program compiles with no
rejection, 1 when rejections were found, 2 for a usage error or a compiler failure without
a diagnostic, and 124 when a compilation exceeds `--timeout`. `--json` gives each
rejection's `file`, `line`, `definition` (or `null`), `scope`, `message`, `context` (the
compiler's notes, outermost first), `call_sites`, whether it was `stubbed`, the indexes of
the earlier rejections it `may_follow_from`, and why the survey `ended`.

## Checklist for extending a port

1. Try upstream unchanged, then make small, explained adaptations. Keep the source
   valid Python. A compiler feature should serve more than one library.
   [Survey its rejections](#survey-a-programs-rejections) to see several restrictions
   in one run.
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
   `tests/deviations/`. Non-ASCII behavior remains part of the inventory: invalid
   UTF-8 and surrogates [still differ](language/compatibility.md#unicode).
7. Measure runtime, build time and memory separately from correctness. Compare
   upstream CPython, the adapted source on CPython, JIT and AOT; disclose losses
   and CPython-only accelerators as well as gains.

Next extensions should address the recorded Unicode and typing exclusions, then
expand other suites such as heapq and bisect and the remaining supported cache cases.
Large generated inputs and longer fuzz campaigns can be expanded independently;
this prototype does not schedule a nightly workflow or add a general test transpiler.
