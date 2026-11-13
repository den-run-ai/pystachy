# Closing the gap between the subset parser and the Rust extension

Measured on 2026-11-13. The workload is `parser-speed/bench.py`: `ast_serialize.parse()` over
mypy 2.4.1's 143 source files (4.57 MB), cache version 5, the files read beforehand; best of 9
rounds, pinned to one core, binaries interleaved. Instruction counts are callgrind's for one round.
The machine is a shared 4-vCPU Xeon at 2.1 GHz with AVX2.

## Where it stands

| Build | Time (median of 5) | Against the extension | Instructions |
|---|---:|---:|---:|
| Rust extension 0.13.1 under CPython | 0.1015 s | 1 | not counted |
| Port at `e84dab75`, compiled ahead of time | 0.264 s | 2.60 | 1.949 G |
| Port at `13ab65ce` | 0.208 s | 2.05 | 1.621 G |
| Port at `269eec3e` | 0.188 s | 1.88 | 1.540 G |

The first three rows were timed together and the last in a later run, in which the first build
again took 0.264 s and the extension 0.100 s.

`269eec3e` is byte for byte the extension on mypy and mypyc (seven option sets), CPython's `Lib/`
(two), this repository's `tests/` and `lib/`, 6,000 damaged sources and 405 type strings; its 9
test checks pass in JIT/AOT, hosted and GC-stressed, with the six make gates and the `opt-in`
verify group.

## What the first profile showed

[`parser-speed/profile-before.txt`](parser-speed/profile-before.txt). About a third of the
instructions were not lexing or parsing:

| Cost | Share | Cause |
|---|---:|---|
| `memset` | 15.8% | The collector clears reused memory: half under list growth (`reserve`), half refilling small-object free lists |
| `memcpy` | 8.2% | `b"".join()` of the output chunks, and list growth |
| `pys_str_join` | 6.0% | The serializer appended one `bytes` per tag and int: 4.0 million chunks for 6.3 MB |
| `Serializer.location` | 7.0% | Two binary searches of the line starts per node |
| `Serializer.int_` | 4.7% | It called itself for long ints, so it was never inlined and carried the recursion guard |

The program allocates about 450 MiB per round (14 collections of a 32 MiB window) for 4.57 MB of
source. Collection itself is cheap: 12 ms of 270.

## What changed in the port

- The serializer stores tags and ints in a list of fixed length and turns it into one chunk when
  it fills (no `bytearray` exists to append to). 4.0 million chunks became a few thousand.
- `int_()` no longer recurses.
- `LineIndex.line_of()` tries the line found last and the next one before searching.
- The parser kept a fourth token array, of flags, that nothing read.
- `parse_name()` and `parse_attribute_expression()` made an identifier node only to copy it into
  the node they return (`269eec3e`): 5% of the instructions, and one collection in ten.

## What was tried and did not help

| Experiment | Result |
|---|---|
| `PYSTACHY_CFLAGS=-march=x86-64-v3` and `-march=native` | 0.258 to 0.267 s against 0.258 to 0.267 s: no difference. The code is scalar and branchy; libc's `memset` and `memcpy` already pick AVX2 at run time |
| `PYSTACHY_GC=off` | Slower (0.37 to 0.42 s): fresh pages cost more than reuse |
| `PYSTACHY_GC_MIN=256` and `1024` | No difference |
| Profile-guided optimization through `PYSTACHY_CFLAGS` | `-fprofile-generate` builds and runs; `-fprofile-use` aborts `opt` while the runtime is built. #1218 prototypes it for the compiler's own build |
| `bytes(list)` in `runtime.py` with one range test after the loop | That function 25% cheaper, the program 1.2%; the loop still does not vectorize (below) |

The pipeline already optimizes the program and the runtime as one module at `-O2` and inlines the
allocator's fast path, so there is no missing link-time step.

## What still separates it from Rust

[`parser-speed/profile-after.txt`](parser-speed/profile-after.txt).

1. **Allocation volume, about 20%.** Still about 320 MiB per round. Every syntax node is one class
   of 20 fields (about 170 bytes), each identifier is a new `bytes`, and three token arrays grow by
   doubling. The collector clears memory that the constructor then writes again. Port level: nodes
   by kind with fewer fields, identifiers kept as offsets. Compiler level: allocate without
   clearing where the constructor stores every field before anything else can allocate.
2. **No growable byte buffer.** `bytearray` is missing (#493). The pending-byte list costs eight
   bytes per byte and a conversion, 4.8% in `pys_bytes_from_list` plus the writers' tests.
3. **A store to a new `bytes` is taken to alias a list's header.** In `pys_bytes_from_list` the
   loop reloads the list's length and items pointer, and repeats the bounds check, on every
   iteration, because the byte store carries no TBAA tag and the object it writes came from the
   inlined free-list pop, which has no `noalias`. `fieldtbaa` and `listguard` tag object fields
   and list items only. Tagging `str` and `bytes` payload accesses under the same root would let
   LLVM hoist those loads and vectorize such loops; it would also help every scanning loop that
   stores a field between two reads of the text.
4. **Branchy code without profile data.** The lexer and parser are about 30% of the instructions.

## Recent pull requests that bear on this

| PR | Bearing |
|---|---|
| #1431 (draft) whole-program folding of arguments and fields a program never varies | Measured: the parser branch merged with it runs 1.6199 G instructions against 1.6206 G, the same time and the same executable size. The benchmark's options reach `parse()` as run-time values |
| #1377 (draft) link ahead-of-time builds against a precompiled runtime | Not measured here. Its own figures give 0.95 to 1.08 of the instructions executed, since runtime functions over 200 instructions stop being inlined; the parser leans on inlined runtime code |
| #1332 (merged) whole-`str` `startswith()` and `endswith()` skip code-point counts | Not measured; the parser scans `bytes` |
| #1284, #1285, #1274, #1307 | Not measured. By their descriptions they concern layout reads, shared proof passes, virtual dispatch and union equality, and the parser has one node class and no unions in its loops |

## Order of work that the numbers suggest

1. TBAA tags for `str` and `bytes` payload and header accesses (item 3 above): a compiler change
   that helps every scanner, small in code, and needing the full verification that a wrong tag
   deserves.
2. `bytearray` (#493), which removes the pending-byte list here and the chunk lists of
   `librt.internal`'s `WriteBuffer` and `io.BytesIO`.
3. Nodes by kind and identifiers as offsets in the port (item 1).
4. Allocation without clearing for constructors that store every field first.
5. Profile-guided builds, once `-fprofile-use` survives the runtime's build.

The UMAP session was asked for what it learned about LLVM settings, intrinsics and hot spots in
its Numba comparison; no answer had arrived when this was written.
