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

## Second round, with line-level profiles

`PYSTACHY_DEBUG_LINES=1` gives callgrind file and line for code that LLVM inlined
([`parser-speed/profile-lines.txt`](parser-speed/profile-lines.txt)). It showed two things the
function-level profile hid:

- 16.6% of the instructions were the port's own SHA-1 of each source file (the source hash),
  59 instructions a byte. Written out with the schedule in sixteen locals it is 44; C is about 10.
  The rounds compile cleanly; what remains is 32-bit arithmetic in 64-bit ints (rotates are not
  recognized, the sixteen words and the state spill) and nine instructions for each byte read
  (an overflow-checked `off + k` and a bounds check).
- 4.8% was `binascii.crc32` in the benchmark itself. `parser-speed/bench2.py` computes its
  checksum after the timed loop; the figures below use it.

| Build | Time (median of 5) | Against the extension | Instructions |
|---|---:|---:|---:|
| Rust extension 0.13.1 under CPython | 0.093 s | 1 | not counted |
| Port at `e84dab75` | 0.215 s | 2.30 | 1.946 G |
| Port at `c8d19249` | 0.137 s | 1.46 | 1.381 G |
| Port at `c8d19249`, profile-guided build (#1444) | 0.126 s | 1.36 | 1.231 G |

Since `269eec3e`: a local cursor in the identifier loop and no slice for names that cannot be
keywords (3%); a syntax node of 128 bytes in place of 152, which the allocator serves inline
(`gc_alloc` pops a free slot inline only under 136 bytes; 2%); the unrolled SHA-1 (6%).

Profile-guided builds: clang's flags through `PYSTACHY_CFLAGS` break the runtime's build (two
modules each get a "CG Profile" module flag). Applied to the whole-program step only they work,
except that LLVM 18's optimizer aborts where a profile is applied to a generator function
(a presplit coroutine; found by bisecting the profile by function), so a generating build marks
those `noprofile`. Draft #1444 adds `PYSTACHY_PROFILE_GENERATE` and `PYSTACHY_PROFILE_USE`.

Open, larger than a port change:

1. SHA-1 and the other digests as C kernels in the runtime, for `hashlib` (#1288) and this port:
   asked of #1288's session.
2. `gc_alloc`'s inline pop for every size class that is cleared when its free list is refilled,
   where the size is a constant at the call (objects of 136 bytes and more call `gc_slow` today).
3. `bytearray` (#493), alias tags for `str` and `bytes` (after the UMAP session's list tags),
   allocation without clearing: as listed below.

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

As first written, with what the third round (below) found:

1. TBAA tags for `str` and `bytes` accesses: measured, no gain on this workload. Not submitted.
2. `bytearray` (#493), which removes the pending-byte list here and the chunk lists of
   `librt.internal`'s `WriteBuffer` and `io.BytesIO`. Not started: the largest piece left.
3. Nodes by kind and identifiers as offsets in the port. Not started.
4. Allocation without clearing for constructors that store every field first. Not started; the
   allocator's inline path for larger objects is #1445.
5. Profile-guided builds: #1444.

## What the UMAP session reported

Its reply of 2026-11-13, not checked here; its evidence is `research/umap-numba-2026-11-13/README.md`
at `8afc7dd2` on branch `claude/dreamy-shannon-bb3cu1`.

- Ahead-of-time builds target the baseline CPU; `-march=native` gave 0 to 1.5% on its loops after
  its fixes, and `-O3` nothing. The same as here.
- A runtime function marked `no_builtin` is never inlined into a caller without the attribute
  (`pys_fpow`, `pys_m_pow`, `pys_m_fmod`). The JIT never inlines the runtime: 2.8 times slower than
  ahead-of-time on its scanning loop.
- List access cost 26 instructions an element against Numba's 4: overflow-checked index
  arithmetic, negative-index normalization, the bounds check, and reloads of the length and items
  pointer. It gives three causes of the reloads: header loads that follow an overflow exit, any
  call that is not inlined, and two TBAA roots, the compiler's "pystachy fields" and clang's for
  inlined runtime C, so an inlined `pys_list_set` store forces the length to be reloaded.
- Every list store loads `l->ids` and branches to `opt_in_trap`, in plain programs too.
- Its pull requests #1436 and #1437 change `runtime.c` only. It may next extend `listguard` to
  loop-invariant offsets and hoist list headers, in `optimizations.py` and the lowering, and will
  say so first.

The two-roots cause is the list form of item 3 above, so tags for `str` and `bytes` accesses and
its header hoisting belong to one piece of work; whoever starts tells the other.

## Third round: alias tags, the allocator and SHA-1

Measured on 2026-11-13 with LLVM 18.1.3, by callgrind unless a time is given. The parser
benchmark is `parser-speed/bench2.py` over mypy's 143 files, and every build below prints the
same checksum of its output.

### Tags for `str` and `bytes` accesses: no gain here

On the UMAP session's list tags (#1442, head `0e7c9690`), a program's inline reads of a
`bytes`'s length and bytes were tagged under the same root, as a struct of their own
(`parser-speed/str-tags-experiment.diff`: `gen_bytes_read`, the `bytes` loop and `len()`; 207
length loads and 157 byte loads of the parser carry the tags).

| Program | Without | With |
|---|---:|---:|
| Parser benchmark | 1,378,529,497 | 1,378,529,536 |
| `parser-speed/scan.py`, which keeps its cursor in a field, on 1 MiB | 32,703,269 | 30,850,846 |

The scanner here keeps its cursor in a local, so nothing in its loops stores to memory that an
untagged load could alias. A program that keeps the cursor in a field gains 5.7%. With no
consumer that gains, this was not submitted; the UMAP session was told. #1442 by itself gives
1.3785 G against main's 1.3815 G.

### The allocator's inline path: #1445

Its first CI run failed `tools/test_runtime_jitfast.py`, which CI's "native JIT and variants"
jobs run with every `tools/test_runtime_*.py` and no make target does: the JIT tier has its own
copy of the fast path (`lower_module.py`'s `JITFAST`), which that test compares with
`gc_alloc` size by size. The copy keeps its 136-byte cutoff, where it calls the slow path; the
test now says so and checks both. A change to `runtime.c` needs those tests run locally.

`gc_alloc` popped a free slot inline only below 136 bytes. Two million 20-field objects:
465.0 M instructions against 576.0 M. The parser with its earlier 152-byte nodes: 1.913 G
against 1.947 G; with today's 128-byte nodes it does not change. A first version tested
`__builtin_constant_p(n)`, which is decided while the runtime is compiled, before a program's
call is inlined: the path was dead, and the test was removed.

### SHA-1: where 43.8 instructions a byte went

The source hash is 14% of the parser's instructions. `parser-speed/sha1/shabench.py` hashes
1 MiB with the port's `_sha1.py`; the figures are the difference between three rounds and one,
per byte.

| Version | Instructions a byte |
|---|---:|
| C, rounds in a loop (`sha1-looped.c`), `clang -O2` | 45.3 |
| C, rounds written out as the port's are (`sha1-unrolled.c`), `clang -O2` | 21.8 |
| Port at `c8d19249`, main's compiler | 43.8 |
| with `if off < 0 or off + 64 > len(m): raise` first | 35.7 |
| with `off &= 0x3FFFFFFFFFFFFFC0` and that guard | 38.4 |
| with `if off < 0: raise` and the last byte read first | 35.8 |
| with `off &= 0x3FFFFFFFFFFFFFC0` and the last byte read first | 32.7 |
| with `off &= 0x3FFFFFFFFFFFFFFF` and the last byte read first (the port now) | 32.4 |
| `c8d19249` with the 32-bit lowering (below) | 34.1 |
| the port now with the 32-bit lowering | 23.0 |

Two separate costs:

- **Byte reads.** Each of the 64 reads had an index overflow check, a bounds check, the
  negative-index path and a spill: about nine instructions. A guard written as a signed
  comparison lets LLVM drop the overflow checks (correlated value propagation) but not the
  bounds checks: its constraint elimination does not carry `off + 64 <= len` to the unsigned
  `off + k < len` tests. Reading the highest index first gives it an unsigned fact, and with the
  offset's top bits cleared it knows the additions cannot wrap: 63 bounds checks go, and the
  byte reads merge into sixteen 4-byte loads with `bswap`. Clearing the low six bits as well
  turns the additions into `or`s and loses the merge. This is a change to the port's generator
  only (`tools/ast_serialize_sha1.py`, on #1435's branch).
- **Rotations.** `((x << c) | (x >> (32 - c))) & 0xFFFFFFFF` stayed two 64-bit shifts: LLVM
  treats the `or` of disjoint bits as an addition and reassociates it into the round's sum, after
  which the backend finds 18 of the 224 rotations. Written as 32-bit operations
  (`sha1/rotate-generic.ll`), LLVM makes `llvm.fshl.i32` of them where it knows `x` to be below
  2**32, and leaves the same three operations as before where it does not. The compiler change
  (`gen_low32`, branch `claude/confident-einstein-ep3lh6-rotate32`) computes a masked expression
  in `%i32` when a side is a constant from 0 to 2**32 - 1 and the other holds only int literals,
  constants and variables under `+ - * & | ^`, `<<` by a literal below 32 and `>>` of a variable
  by a literal below 64: 221 of the 224 become `rol`. It is draft #1447. A first version wrote the rotation itself,
  with a term for `x`'s bits from 32 up; it cost an instruction where LLVM does not know `x`'s
  range, and the generic rules need no such term.

`make irsame REF=bf699eb5` reports 289 of 4,494 programs for #1447. Compiled one by one with
both compilers: 33 have IR that the lowering changed (the compiler itself, users of `random` and
`binascii`, the masked-int cases); in 242 one string constant holds the reference compiler's
own library path (`build/ref/lib/`); 14 are rejections whose message names that path, which the
tool leaves alone inside quotes. No exit status and no other message text differs. The 256 would
be reported for any reference.

The parser benchmark: 1,381,548,169 with main's compiler and the port at `c8d19249`;
1,329,405,242 with the new byte reads; 1,337,473,777 with the lowering alone; 1,286,461,196
with both (6.9% fewer).

Timed together on one core (best of nine rounds, median of five runs): the extension 0.095 s;
the port at `ff997414` 0.131 s, 1.38 times it; the same built with #1447's lowering 0.124 s,
1.30 times. The time moves less than the instruction count: the bounds checks that went were
branches the processor predicted.

The hashlib port of #1288 (head `8ff1e487`, `sha1/hashlib-bench.py`) does not gain as written:
sha1 66.8 to 67.2, sha256 125.3 to 124.3, md5 58.5 to 58.5 instructions a byte. Its rounds are a
loop over a list of words, and LLVM does not know that values loaded from a list or carried
round the loop are below 2**32. Its owner preferred a general compiler change to C block
functions in `runtime.c`, and was sent these figures with what would let its loops gain: masks
where values enter, and a block's last byte read first.

`parser-speed/keep-bitcode-clang.sh` is the `clang` wrapper (used as `PYSTACHY_LLVM`'s clang)
that kept the linked module of a build, to read the optimized IR of one function.
