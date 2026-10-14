# Native stream unions and call-site feedback

**Experimental draft.** This implements native reference-union execution, native
profile collection, and guarded caller specialization through the shared AOT/JIT
compiler. It is offline type feedback, not online compilation or path tracing.
A positive end-to-end speedup has not been established.

Stacked integration base `c2079c0` (the same tree as local measurement base
`5be2744`) combines the existing #378 library ports, #382
scalar-union machinery, #383 HTML probe, and #384 receiver-feedback work. This draft changes only
the stream boundary, its feedback mechanism, field inference, and validation.

The experiment targets a missing type boundary in the existing standard-library
`shlex` port: `TextIO` and `io.StringIO` are unrelated native representations, but
both provide the stream methods needed by the parser. A value loaded from
`list[TextIO | StringIO]` cannot be made concrete by ordinary call-site template
specialization alone.

The default port converts files to `StringIO` by reading them completely. The
probe adds a private `_stream` constructor argument that retains the original
stream. Its default boolean marker is resolved by constructor specialization, leaving
ordinary port calls unchanged. The parser's existing `read_token()` body is
unchanged. Special methods compile eagerly, so probe instances also route their
iterator methods directly to `read_token()`. The probe exercises that method
directly; it does **not** restore
`get_token()`, file inclusion, or mixed source-stack behavior.

`bench/stream_skew.py` sends the erased union through the typed `read_tokens`
wrapper into the unannotated `tokenize` helper and the existing constructor. The
generic version must preserve both stream alternatives down to character reads.
The concrete controls compile the **same** helper and parser bodies for an exact
`StringIO` or `TextIO`. The selected clone narrows the helper argument, the constructor template and
its stream field. It has useful work to remove only if the concrete controls
demonstrate a reliable advantage over generic native dispatch.

This differs from the earlier HTML probe: stream method calls occur inside the
character loop, rather than only at a few outer document boundaries. It is still
possible that character allocation and lexical work dominate. No speedup follows
from type skew alone.

## Workload and checks

The ASCII input combines command arguments, assignments, quotes, escaped spaces,
multiline tokens, and comments. Both stream types read the same input. Exact
token-list checks are separate from the timed checksum loop. Memory timings
include rewinding the concrete `StringIO`, lexer construction and parsing, and
exclude fixture creation, compilation, and process startup. File timings also
include reopening the file, because native `TextIO` does not currently support
`seek`. Compare generic and concrete modes for the same stream type; file and
memory timings include different work.

The `train` mode supplies 199 memory streams and one file stream: this is a
controlled 99.5% fixture, not an observed application distribution. `check` uses
balanced and reversed distributions. The caller owns and closes both streams.
The benchmark modes are `bench`, `static`, `file`, and `static-file`; the second
argument sets the repetition count and the third supplies an optional fixture
path. The default path is `build/stream-skew-input.txt`.

An adapted-source CPython oracle must preload standard-library modules before
adding `lib`, because that directory also contains a partial `collections` port:

```sh
mkdir -p build
python3 -c 'import collections, typing, re, runpy, sys; sys.path.insert(0, "lib"); sys.argv = ["bench/stream_skew.py", "check"]; runpy.run_path(sys.argv[0], run_name="__main__")'
```

For an independent upstream parser oracle, load the benchmark source under normal
CPython and replace only its private `_stream=stream` constructor keyword with
`instream=stream`. Both oracles currently produce:

```text
check 586964006 14087136144
```

## Research relationship

[Polymorphic inline caches](https://bibliography.selflanguage.org/pics.html)
record receivers at individual call sites. [Type feedback](https://bibliography.selflanguage.org/type-feedback.html)
uses those observations to remove unresolved dispatch and enable inlining.
[Selective specialization](https://projectsweb.cs.washington.edu/research/projects/cecil/www/Papers/specialize-pldi.html)
selects caller contexts where greater type precision has a useful downstream
effect. Native closed-union execution supplies the missing generic baseline in
this probe; a profile can choose guarded clones, but cannot make unobserved
members illegal. Offline feedback is not an online tracing JIT.

The [upstream shlex contract](https://docs.python.org/3.13/library/shlex.html)
accepts stream-like objects with `read` and `readline`, and closes included
streams at EOF. Full restoration of those behaviors remains broader than this
single `read_token()` experiment.


## What previous attempts missed

| Prior work | Relevant result | Gap addressed here |
| --- | --- | --- |
| #374–#376 | Numeric entry/region specialization and a scalar native interpreter | Real file and mutable class references stay in Pystachy's existing heap; no private-image object ABI or second interpreter |
| #377 | Skew increases when keyed by caller context, especially in object-oriented programs | Native records include the caller's compiled parameter types and source call site |
| #384 | HTML hot methods were already concrete; only outer dispatches changed | A stream field remains a real union inside the character parser until its caller is specialized |
| #386, withdrawn | External regex generation did not test the intended compiler/runtime boundary | Normal compiler templates and the original parser body are used |
| #387 | Runtime-length capture tuples work, but concrete tuple controls showed no gain | Different missing type family; tuple shape/value specialization is not repeated |

A concrete AOT control is a performance ceiling, not a compatibility prerequisite:
its availability does not imply that mixed runtime values can already execute.
Conversely, skew alone does not establish a performance opportunity. The useful
comparison is generic native execution against a guarded concrete version of the
same body, with separate correctness and compatibility evidence.

## Compiler and runtime changes

- `PYSTACHY_CLOSED_UNIONS=1 PYSTACHY_REFERENCE_UNIONS=1` enables up to four
  native file/class members. Existing scanned union boxes retain the original
  pointers; objects and files are neither copied nor serialized.
- Ordinary union method calls evaluate explicit arguments once and dispatch to
  the existing native member method. Member-specific defaults and exception
  paths remain intact. Methods must return identical types. Callable instance
  fields, overlapping class families and scalar/reference mixtures are rejected.
- A class-family member can hold a subclass. Its method calls retain ordinary
  subclass dispatch. A recorded union-member tag is **not** a claim about the
  exact subclass; dynamic subclass `isinstance` checks inspect the object header.
- Constructor field inference can reuse an ordinary generic helper's inferred
  return when its simple positional/default argument types are known. It reuses
  template compilation and its existing resource/recursion limits. Unknown
  arguments still require an annotation. This small general inference change is
  also needed for the default shlex constructor after extracting stream selection.
- An explicitly selected unannotated function with one reference-union argument
  can record native member tags at its caller site. Selection requires at least
  100 calls and 90% share. Profiles choose optimizations; the declared union,
  including members absent from training, remains the execution contract.
- The selected concrete template and the generic template use the same typed IR,
  LLVM lowering, runtime, heap and exception machinery. A non-null/member guard
  selects the concrete call before the callee body executes. Arguments and defaults
  have already been evaluated once. Misses call the generic body;
  a thrown exception never replays the call.
- Recording has 256 fixed rows, copies bounded symbolic identities, and retains
  no GC pointers. Overflow invalidates the profile. The compiler reads at most
  64 KiB, rejects malformed/duplicate rows conservatively, and caps top-level
  selected template signatures at 16; normal template budgets also apply.

The compiler flag `PYSTACHY_FEEDBACK_FUNCTION=tokenize` selects the experiment.
`PYSTACHY_FEEDBACK_RECORD=1` emits training calls; the executable writes its
profile at exit to `PYSTACHY_FEEDBACK_OUT`. Recompile with
`PYSTACHY_FEEDBACK_PROFILE` to select a concrete caller. Optional
`PYSTACHY_FEEDBACK_COUNTERS=1` records hot/miss entries independently of timings.
No CPython profiler participates in this path. JIT here means Pystachy's existing
pre-execution LLVM JIT; runtime recompilation, adaptive PIC evolution and
mid-function deoptimization remain unimplemented.

Profiles are tied to the source/compilation context. Nonmatching or missing rows
lose specialization. Stale matching rows can still select a guarded clone and
may be suboptimal; every selected row still requires a type guard. This
is a bounded declared-type experiment, not inference of arbitrary `Any`, open
class worlds, recursive heterogeneous JSON, or dynamic imports.

The local eligibility check rejects reassigned/captured parameter dependencies,
unsafe stores and inferred alias/container contracts. It is deliberately
conservative. It does not analyze arbitrary downstream helper/constructor
mutation contracts: a more complex profile-selected body may still be rejected
by ordinary type checking. There is no speculative compiler-state rollback.

## Candidate selection

`shlex` is the best immediate stdlib probe because its unresolved stream calls
are inside the hot loop and its current stream conversion is a visible type
limitation. Full source-stack restoration is the next compatibility step, not
part of this private parser probe. Existing `tomli-w` and `urllib.parse.urlencode`
are good subsequent candidates for `dict[str, str | list[str]]`; they need
container-member unions and primarily promise compatibility. Full JSON and
BeautifulSoup require substantially broader recursive-container and object
semantics. Small numeric kernels and regex pattern-value generators do not test
this missing native reference boundary.

## Reproduction and evidence

```sh
export PYSTACHY_LLVM=/path/to/llvm/bin
python3 tools/bench_stream_feedback.py --repeats 1000 --samples 7
make stream-feedback-check
```

The runner builds generic, recording, selected and counter variants, validates
exact token contents against CPython's upstream `shlex`, checks AOT/JIT outputs,
and stores raw execution samples, source hashes, build timings, executable sizes
and native profiles in `docs/benchmarks/stream-feedback.json`.
The controlled training profile is 199 `io$StringIO` / 1 `file`. Held-out balanced
and reversed workloads record 7 hot / 17 fallback entries, with matching outputs.

The benchmark includes manually concrete controls in every binary. Its identical
generic/selected file sizes therefore do not measure the marginal code-size cost
of adding a clone to a deployed program. Build timings are individual samples,
not evidence of a compilation speed change.

## Measured result

The initial unpinned samples ran during another compiler bootstrap and had wide
ranges. A focused follow-up reused the same binaries after that work ended,
pinned processes to CPU 4, and rotated seven samples of 4,000 parses each:

| Native memory-stream path | Median process CPU time | Sample range |
|---|---:|---:|
| Generic union | 2.113 s | 2.071–2.151 s |
| Profile-selected | 2.042 s | 2.006–2.251 s |
| Statically concrete | 2.058 s | 1.988–2.326 s |

Paired generic/selected ratios had median **1.025×**, range **0.926–1.060×**.
Paired generic/concrete ratios had median **1.013×**, range **0.925–1.068×**.
These small, overlapping results do **not demonstrate a reliable speedup** or
substantial remaining headroom over concrete compilation. They establish that
native erased stream values, feedback, guarded specialization and fallback work
through the existing parser. File timings are not included in this comparison.

Single hosted-compiler build samples were 4.008 s for generic and 3.655 s for
selected; they are not statistical compile-time comparisons. Both executables
were 309,208 bytes, with the code-size limitation described above. The
[raw record](benchmarks/stream-feedback.json) preserves both runs, every CPU
sample, paired ratios, execution order and executable hashes.

The runner now accepts `--timing-cpu` to select an allowed CPU and checks source
hashes both before and after measurement to reject concurrent source changes.
The recorded follow-up used existing binaries without rebuilding or instrumenting
them; it is stored separately as `affinity_followup` in the raw record.

## Native code diagnosis

Inspection of the benchmark's existing AOT binaries confirms that specialization
changes the character-reading path. Reproduce without recompilation:

```sh
nm -S --size-sort build/stream-feedback/baseline
nm -S --size-sort build/stream-feedback/optimized
objdump -d --disassemble=f.read_tokens build/stream-feedback/optimized
objdump -d --disassemble='m.shlex$shlex-1.read_token.1' build/stream-feedback/baseline
objdump -d --disassemble=f.tokenize.2 build/stream-feedback/optimized
objdump -d --disassemble='m.io$StringIO.read' build/stream-feedback/baseline
```

Symbol suffixes and addresses can change between builds. The source hashes and
build provenance in [the measurement record](benchmarks/stream-feedback.json)
identify the measured revision. In the inspected binaries:

- The generic `read_token` loads the boxed stream and compares its member tag
  before choosing `pys_file_read` or `StringIO.read`. Character-loop backedges
  return before that comparison: LLVM has **not** hoisted it out of the loop.
- The selected `read_tokens` checks the member once and tail-calls `tokenize.2`.
  That concrete parser calls `StringIO.read` and `readline` directly; its body has
  no file-read calls. The generic path remains available on a guard miss.
- The selected body and manual concrete control converge to the same emitted
  function. In the optimized binary, the control's call sites also call
  `tokenize.2`; no separate `f.concrete` symbol remains. Its 6,645-byte body has
  the same 1,510-instruction mnemonic sequence as the baseline's manual concrete
  function. These counts describe this build, not a compiler guarantee.

Both paths still box the optional `size=1` argument and call the same native
`StringIO.read`. That method checks the stream, joins pending writes, updates its
position and allocates/copies nonempty substrings. Parser string operations and
allocation paths also remain. This unchanged work plausibly limits the gain from
removing dispatch, but that is an inference from code inspection: no CPU shares
or dominant bottleneck were measured here. A small timing difference therefore
does not mean that execution missed the specialized character-reading path.

## Validation

- Three compiler bootstrap stages emitted identical IR (387,585 lines); all three
  runtime.py stages also matched (10,996 lines).
- Native JIT/AOT corpus: 2,857 checks passed. The subsequently added
  `field_helper_return` regression separately passed both modes.
- Eleven stream-feedback integration tests passed with both the hosted compiler
  and the bootstrapped native compiler. They cover shared mutable references,
  GC stress, argument/default effects, exceptions without replay, nullable
  receivers, malformed profiles, unsafe aliases, and module-qualified types.
- Sixteen existing receiver-specialization tests and 58 flow/closed-union
  integration checks passed.
- CPython 3.13.16 recording audit: 804 recordings, 36 documented deviations and
  nine unchanged library files checked, zero failures. The pinned development
  dependency `typing_extensions==4.16.0` was installed in an isolated environment.
- Runtime signature/effect checks, strict C syntax checking, Ruff and
  `git diff --check` passed. The new integration suite is wired into CI.

The evidence above is local validation. CI results are tracked on the draft PR.
