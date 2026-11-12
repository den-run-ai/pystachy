# Native mypy on Pystachy: proposal and baseline

Research branch material, not for `main` ([CONTRIBUTING](../../CONTRIBUTING.md#repository-contents)).
Measured on 11 November 2026 at Pystachy `b40ee87` (v0.4.0-alpha.4) against the mypy
release the repository already pins, 2.4.1. On 12 November the import sweep and the
probes gave the same counts at `6e02b36` (v0.4.0-alpha.6): 26 of 242 and 27 of 50.

Tracked in [#1322](https://github.com/den-run-ai/pystachy/issues/1322) and its sub-issues
#1323 to #1331.

## Proposal

Compile upstream mypy, unmodified, into a Python-free executable with Pystachy; qualify
it against mypy's own 11,361 data-driven test cases; then use it inside Pystachy's
pipeline as the type gate, as a PEP 484 front half for `pystachy check`, and as a source
of type facts. Continue to `mypyc.irbuild` afterwards.

The measurements below show that the bet is a finite list of work rather than an open
research problem. mypy is fully annotated and written in the mypyc dialect, whose
semantics (early binding, native classes, no monkey patching) are close to Pystachy's
contract. Today 26 of its 242 modules compile, and every failure is a compile-time
rejection, not a miscompilation. The largest obstacle is not a missing language feature
but compile scale: base-typed method calls lower to a compare chain over every class,
which makes a 1,009-line visitor program take 251 s to build.

Three work streams follow from that, in this order: make class-heavy programs
compile in bounded time; extend the class model and type forms to the mypyc dialect;
supply the runtime and library pieces. Each feature below is general, tied to a counted
mypy idiom, and has a probe that fails today.

## Baseline

| Measurement | Result |
|---|---|
| Source size (no tests, no typeshed) | mypy 143 files, 115,301 lines; mypyc 103 files, 43,645 lines |
| Modules whose `import` compiles to IR, unmodified | 26 of 242, all near-empty packages or leaf modules |
| First blocker of the other 216 | `mypy_extensions` 72, `librt` 72, `importlib` 20, `gc` 11, `inspect` 8, `contextlib.ExitStack` 6, other missing modules 20, other forms 7 |
| Idiom probes (one mypy idiom each, CPython as oracle) | 27 pass, 23 rejected at compile time, 0 wrong outputs |
| `pystachy check` (syntax) over mypy and mypyc, tests included | 336 of 336 files |
| `pystachy check` over mypy's bundled typeshed | 761 of 761 `.pyi` files, 2.5 s |
| mypy 2.4.1 on the 56 compiler modules, cold cache | mypyc wheel 4.5–5.5 s, 228 MiB (3 runs); pure Python 24.5–26.0 s (2 runs); warm 0.2 s either way |
| Pystachy compiling itself (66,345 lines) | 4.9 s and 848 MiB to 34.2 MB of IR; 126 s and 1.5 GiB for the `-O2` executable |
| Generated visitor program, 100 classes × 100 base-typed call sites (1,009 lines) | 2.06 MB of IR; AOT `-O2` 251.5 s; JIT run 2.0 s |
| Same, 200 classes × 400 sites (2,609 lines) | 14.5 MB of IR; `opt` still running after 9.5 minutes, stopped |

Timings are single wall-clock runs on a shared 4-vCPU VM, unpinned, with CPython 3.13.18
and LLVM 18.1.3. They size the problem; they are not benchmarks. A compiled import means
IR was emitted, not that the module runs.

What mypy's source asks of a compiler, from a static census ([`results/`](results)):

| Property | Count in mypy (mypyc) |
|---|---|
| Annotated parameters; functions without a return annotation | 9,204; 0 |
| Parameters typed `Any`; typed `object` | 26; 73 |
| `match` statements; `async` functions; metaclasses | 0; 0; 1 (`ABCMeta`) |
| `isinstance` calls | 4,180 (932): 3,132 on a name, 782 on an attribute, 246 with a tuple of classes |
| Classes; descendants of `Node`; of `Type` | 464; 98; 32 (mypyc: 181 classes, 43 `Op`) |
| Classes with several bases | 14 (1), all trait combinations |
| `Generic[...]` roots; subclass sites; distinct instantiations | 7; 38; 27 (mypyc: 20 sites, 12 instantiations) |
| `accept()` definitions | 126 (54) |
| Union annotations by width | 1,207 of two members, 37 of three, 5 of four, 4 wider |
| Unions mixing a scalar with a class | 23 (19) |
| `getattr` with a run-time name; `setattr` | 20; 7 |
| Builtin subclasses | 1: `SymbolTable(dict[str, SymbolTableNode])` |

## Reproduce

Build with `make`. Download and hash-check `mypy-2.4.1.tar.gz` (SHA-256
`63b590965691e540a335fa74dadf31a7069142f6b72e234689bbd244edf55623`) into a new directory,
and copy its `mypy/` and `mypyc/` Python files, without `test`, `typeshed`, `test-data`,
`lib-rt`, `doc` and `external`, to `$PKGS`; `$SRC` is the unpacked archive. Read the
download with `python3 -I` only.

```sh
python3 tools/import_sweep.py -j 3 ./pystachy "$PKGS" build/mypy-sweep.json
python3 research/mypy-native/scripts/run_probes.py research/mypy-native/probes ./pystachy build/mypy-probes.json
python3 -I research/mypy-native/scripts/census.py "$SRC" build/census-mypy.json mypy
echo mypy.main mypy.checker mypy.types | python3 -I research/mypy-native/scripts/census2.py "$SRC" mypy
python3 research/mypy-native/scripts/gen_hier.py 100 100 > build/h.py && ./pystachy build build/h.py -o build/h
```

[`scripts/sweep.py`](scripts/sweep.py) repeats the sweep with several `PYSTACHY_PATH`
entries. [`stand-ins/`](stand-ins) holds throwing stubs of `librt` and `ast_serialize`
used only to see past the first import; they are probes, not implementations.

## Why this target

mypy has an exact oracle at every level: 8,306 `check-*` cases, 331 parser cases, 577
semantic-analysis cases and 755 mypyc IR-building cases, all source text with expected
output. Its serialized AST and fixed-format cache are byte strings that two
implementations can compare. It has a strong performance baseline in the mypyc wheel.
The repository already depends on it for `make typecheck`, so a native build has a
consumer on the first day it works.

The two compilers can also check each other. mypyc already compiles all 55 Pystachy
compiler modules and reproduces the self-compiled IR byte for byte
([record](../../examples/comm/mypyc_compiler.md)). This proposal adds the other direction.

## Design

### Rules

The ground rule of [#409](https://github.com/den-run-ai/pystachy/issues/409) stands:
each extension accepts more Python and changes no program that compiles today.

Upstream stays unmodified. Adaptations go into Pystachy's `lib/` (a compiler-known
`mypy_extensions`, a native `librt`), not into a patch series. A patch is the last resort,
counted and written so that upstream could take it.

mypy proposes and Pystachy verifies. A type fact imported from mypy, or accepted from
`cast` or `TypeGuard`, is used only where Pystachy's own rules prove it or behind a
class-tag guard whose failing path runs CPython's behavior: a by-name attribute lookup
through the class's reflection record. A guard never raises an error that CPython would
not ([#555](https://github.com/den-run-ai/pystachy/pull/555)).

### Compile scale

**Method tables.** A call through a base-typed receiver now emits one compare and
branch per class in the hierarchy: 1,231 IR lines per call site for 200 classes. mypy
has 98 `Node` classes, 32 `Type` classes and 126 `accept` methods. Number class tags in
preorder so that every subtree is a contiguous interval, and call through a table
indexed by tag for hierarchies above a small fan-out. Keep today's chain below that
threshold, where LLVM can inline the targets. `isinstance` then becomes one unsigned
range compare. Exit test: the 200 × 400 probe builds in under a minute, and
`make irsame` shows no change for small hierarchies. `tools/scaling.py` should own the
probe.

**Codegen units.** Self-compilation spends 4.9 s in the frontend and about 121 s in
LLVM on one whole-program module. mypy's `main` closure is 92,547 lines. Emit one LLVM
module per source module (or import cycle), optimize them in parallel, and cache objects
by IR hash, toolchain and flags. Partitioning must be deterministic so that the
fixed-point check compares units. This also shortens every bootstrap and verify run.

**Independent diagnostics.** The compiler stops at the first error, so a sweep of 242
interdependent modules reveals one blocker per module per iteration.
[#261](https://github.com/den-run-ai/pystachy/issues/261) (semantic checking with
independent-unit diagnostics) is a prerequisite for port velocity, not a convenience.

### Types and class model

| Gap | Probe | Mechanism | Tracker |
|---|---|---|---|
| Identity class decorators `@trait`, `@mypyc_attr`, `@final` | p01, p02 | Compiler-known names; no run-time effect | [#7](https://github.com/den-run-ai/pystachy/issues/7) |
| Several trait bases; a trait deriving from the shared root; trait attributes | p03, p04, p22 | Fields come from the primary chain only; reject unless the linearization agrees with it. Trait calls and attribute offsets go through per-class interface tables | #7 |
| Generic class as a base | p05, p06 | Resolve the base to its canonical instantiation | [#962](https://github.com/den-run-ai/pystachy/issues/962) |
| Virtual generic method, `accept(self, v: Visitor[T]) -> T` | p05 | One table slot per representation of `T` (reference, integer, float), not per type. All reference instantiations share code | new |
| `isinstance(x, (A, B))`; narrowing `e.node` | p07, p09 | Static type is a set of tag intervals under one root. Attribute narrowing holds until a call or store that the effect summaries cannot exclude, then the tag is tested again | #7 |
| Class unions wider than four | p11 | Hierarchy objects already carry a tag, so a class-only union is a plain pointer with a class-set type: no box, any width | new |
| Scalar with class, `Type \| str \| None` | p12 | Extend the tagged mixed union with reference members | [#251](https://github.com/den-run-ai/pystachy/issues/251) |
| `Sequence[Base]` from `list[Derived]`; `Sequence[int]` from a tuple; `tuple[Type, ...]` | p13a, p13c, p13d | Read-only abstract views are covariant over references at no cost, since slots are uniform pointers. Add object elements to runtime-length tuples | new |
| `ClassVar`, `TypeGuard`, `cast(C, x)`, class-valued `TypeVar` bound, `NotImplemented`, `Protocol`, `TypedDict` | p16b, p18, p26b, p19, p20, p32, p25b | Small forms. `Protocol` is the closed set of conforming classes; guards as in Rules | [#254](https://github.com/den-run-ai/pystachy/issues/254) |
| Methods-only `dict[K, V]` subclass | p14 | A statically distinct dict type without added fields, the one form mypy uses and mypyc permits | #7 |
| `getattr(self, "visit_" + name)` | p33 | A name-to-slot table over methods of one signature | [#487](https://github.com/den-run-ai/pystachy/issues/487) |

Representation-based slots also limit template growth outside hierarchies, where
compile time currently rises with each specialization.

### Runtime and libraries

`lib/mypy_extensions.py` must be Pystachy's own: upstream's file builds `i64` and `u8`
from metaclasses and imports `typing._type_check`. mypyc leaves signed native-integer
overflow undefined, so Pystachy's checked 64-bit `int` is a valid `i64`; `u8` wraps.

`librt` is the mypyc runtime library that mypy 2.4 requires: `internal` (the
`ReadBuffer`/`WriteBuffer` cache codec, 1,314 lines of C upstream), `base64`, `strings`,
`time`, `vecs` and `threading`. Write it in the subset over a growable byte buffer, which
the runtime lacks today, and compare its bytes with upstream's extension under CPython.

The `mypy.main` closure needs `hashlib` (SHA-1), `gc` controls, `platform`, `pprint`,
`configparser`, `subprocess`, `contextlib.ExitStack`, `collections.ChainMap`,
`sys.executable` and two `argparse` forms. `importlib.resources` locates the bundled
typeshed (761 stubs, 5 MB), so the executable needs a data directory beside it or an
embedded archive. `importlib.import_module` loads plugins; link the default plugins
statically and reject others. mypy parses files on a `ThreadPoolExecutor`; an executor in
`lib/` that runs each task inline gives the same results. Process workers belong to
[#754](https://github.com/den-run-ai/pystachy/issues/754).

Two runtime behaviors matter at mypy's heap size. mypy tunes CPython's collector: it
raises the thresholds, disables collection while it loads the module graph, and then
promotes what it loaded with a `gc.freeze()`/`gc.unfreeze()` pair. These calls should map
to Pystachy's collector controls; whether a region that is no longer marked pays off is
unmeasured. mypy also sets the recursion limit to 2**14 to walk deep trees. That already
works: at `6e02b36`, `sys.setrecursionlimit(2**14)` followed by a 12,000-deep recursion
runs natively (checked on 12 November, after the first version of this note claimed
otherwise).

### Parser

mypy 2.4 parses with `ast_serialize`, a Rust extension over Ruff's parser that returns a
serialized AST for `mypy/nativeparse.py` to decode. First link that crate through a
small C-ABI shim and Pystachy's FFI: exact upstream behavior, at the price of a Rust
toolchain for this target only. Then emit the same format from Pystachy's own parser,
with the Rust output as oracle. The parser already accepts all of mypy and typeshed,
including `match`, `async` and PEP 695 syntax, but accepting a file does not show that
the trees agree; error recovery and messages are Ruff's and need the comparison.

### Using native mypy in the pipeline

1. **Type gate.** `make typecheck` runs the native executable, shipped in the native
   archives and Docker image so that the gate needs no Python. Both checkers run until
   their diagnostics on the tree are identical.
2. **PEP 484 diagnostics.** `pystachy check --types` reports mypy's errors before the
   subset's own. Run mypy as a separate process with typed binary records, not linked
   into the compiler: linking would add about 90,000 lines to each bootstrap stage.
3. **Type facts.** Where the compiler now stops with "cannot infer the type of field;
   annotate it", ask mypy's inferred type and narrowing, under the guard rule. Measure
   the result in annotations and port adaptations removed
   ([#262](https://github.com/den-run-ai/pystachy/issues/262)). This needs typing split
   from emission behind an interface that `Gen` fills first, with identical IR.
4. **typeshed as the library contract.** Compare `lib/` and the builtin tables with
   typeshed's signatures and report drift.
5. **mypyc dialect.** Programs written for mypyc compile unmodified.
6. **mypyc IR to typed IR, undecided.** Lowering `mypyc.irbuild` output to Pystachy's IR
   would separate typing from code generation completely. mypyc's types and primitives
   assume CPython objects and reference counts, so decide after a spike on 20 IR-building
   cases, not before.

## Qualification ladder

Each rung is a closure of modules that import one another eagerly, with an oracle that
exists upstream. Run each natively in JIT and AOT, with CPython mypy as the reference.

| Rung | Closure | Oracle |
|---|---|---|
| Q1 leaf components | `mypyc.namegen` (qualified today), `mypy.graph_utils`, `mypyc.codegen.cstring` | Upstream unit tests through the native pytest runner |
| Q2 data model | `mypy.types`: 16 modules, 15,764 lines | Fixed-format cache read and rewritten byte-identically |
| Q3 parse | `mypy.nativeparse`: 28 modules, 22,160 lines | 331 `parse*` cases; tree dumps of mypy, typeshed and the corpus |
| Q4 semantic analysis | toward the checker closure | 577 `semanal*` and 75 `typexport*` cases |
| Q5 checker | `mypy.checker`: 74 modules, 74,637 lines | 8,306 `check-*` cases |
| Q6 command line | `mypy.main`: 105 modules, 92,547 lines | 125 `cmdline*` cases; identical output on the compiler; a cache written by one implementation read by the other |
| Q7 mypyc front end | `mypyc.irbuild.main`: 71 modules, 31,471 lines | 755 `irbuild*` cases, IR text |

Performance gates apply at Q6 on pinned cores with medians: first faster than
interpreted mypy (24.5 s here), then parity with the mypyc wheel (4.5–5.5 s, 228 MiB).
The long suites run in a scheduled or manual workflow from hash-pinned fetches; PR CI
keeps its 20-job and 15-minute limits and gains only a smoke subset.

## Phases

| Phase | Content | Exit |
|---|---|---|
| 0 Foundations | Method tables, codegen units and object cache, #261, compiler-known `mypy_extensions`, the sweep and probes as a maintained tool | 200 × 400 probe under a minute; self-build wall time halved on four cores; baseline reproducible from pinned inputs |
| 1 Class model | Traits, class-set narrowing, decorators, small typing forms, dict base | `mypy.nodes` closure (10 modules) compiles; Q1 |
| 2 Generics, unions, variance | #962, representation slots, wide and mixed unions, covariant views | `mypy.types` closure compiles; Q2 |
| 3 Runtime and parser | `librt`, stdlib modules, collector controls, Rust parser link | Q3, Q4 |
| 4 Checker and CLI | Remaining blockers found by Q5 | Q5, Q6, performance gates; pipeline uses 1 and 2 |
| 5 Integration | Type facts, typeshed contract, mypyc front end, the IR decision | Q7; annotations removed |

## Risks

- **Narrowing soundness.** Attribute and guard narrowing can go stale across calls and
  mutations ([#768](https://github.com/den-run-ai/pystachy/issues/768)). The guard rule
  bounds the damage to a slower path; each form still needs a mutation test.
- **Specialization cost.** 27 visitor instantiations and 126 `accept` methods multiply
  without representation slots. Bound it with `tools/compilelimits.py`.
- **Collector behavior.** A conservative collector on a heap of a few hundred MiB of
  small linked objects may retain or scan too much. Measure at Q2, before the checker.
- **Upstream movement.** `librt` and the AST format are versioned and change between
  mypy releases. Pin one release and move it deliberately, with a sweep diff.
- **Scope.** The daemon and fine-grained server, `stubgenc` and `stubtest` (which
  introspect CPython), reports and dynamically loaded plugins are outside the native
  target.
- **Licenses.** mypy and `librt` are MIT, typeshed Apache-2.0, and `ast_serialize`
  vendors Ruff crates. Update the notices before vendoring or linking any of them.

## Not measured

No mypy module beyond an import has been executed natively. The probes cover 50 idioms,
not all of mypy; the checker closure will expose more. Collector behavior, memory at
scale, the Rust link and the trait layout are designs without prototypes.
