# bytearray: status and a measured consumer (2026-11-18)

Draft PR [#1478](https://github.com/den-run-ai/pystachy/pull/1478), branch
`claude/confident-einstein-ep3lh6-bytearray`, head `dbdb926680b5d997b40f0b26597cb44f1fcb0c6b`
(main `3cf23d20` merged in). Refs #493.

## What the type is

A class of the subset in `lib/_pystachy_bytearray.py`, imported by a parse-time hook into any
module that reads the builtin name. Its storage is a private `bytes` buffer that seven compiler
primitives (`__pys_ba_*`, allowed in that module only) read and write in place. Slices reach the
class as `_getslice`, `_setslice` and `_delslice` with the bounds as written. What is supported and
what is rejected is in the PR's paragraph of `docs/language/compatibility.md`.

## Consumer: the parser port's output buffer

Question: is the plain bytearray code as fast as a buffer tuned by hand around `list[int]`?

- Compiler: the bytearray branch at `420b2b61` (main `3cf23d20` plus #1478), AOT build.
- Program: `parser-speed/bench2.py`, the 143 mypy source files, `parse()` calls timed alone.
- Port: `lib/ast_serialize` of #1435 at `ff997414`. It compiles on that compiler unchanged.
- Base: `Serializer` keeps pending bytes in a `list[int]` with `room()`/`flush()` and joins chunks.
- Variant: one `bytearray`; `append`, `+=` and `bytes(buf)`.
  Patch: [`bytearray/serializer-on-bytearray.patch`](bytearray/serializer-on-bytearray.patch)
  (80 lines removed, 22 added).

Both builds print the same result: 143 files, 6,342,809 output bytes, CRC 2417416597.

| Measure | `list[int]` chunks | bytearray | Change |
|---|---|---|---|
| Instructions, whole run, 1 round (callgrind) | 1,329,485,387 | 1,222,612,669 | −8.0% |
| Best of 5 rounds, median of 7 runs | 0.1146 s | 0.1064 s | −7% |
| Range of those 7 runs | 0.1058–0.1303 s | 0.0988–0.1187 s | overlap |
| Peak memory (`VmHWM`, 3 rounds) | 51,712 kB | 51,820 kB | same |
| Executable | 1,528,456 bytes | 1,525,392 bytes | same |

The instruction count is the figure to rely on: it includes reading the files and the CRC, which
are the same in both. The timings are from a shared host, runs interleaved on one core
(`taskset -c 2`); their ranges overlap, so the 7% is a direction, not a measurement. Raw lines:
[`bytearray/times.log`](bytearray/times.log).

The change cannot go into #1435 until #1478 is on main: #1435 is based on #1276, not on main.

## What CI found

- `692c44c8`: the opt-in verify group failed. In a module with `# pystachy: python-int`, a size,
  index or byte reaches the buffer primitives as a promoting int, which they rejected. `08460029`
  narrows them there and in written slice bounds; `bytearray_promoting_ints.py` covers both.
- `08460029`: no Verification or Lint run started, because the branch conflicted with main (412
  commits ahead, among them a `complex` class built the same way). `420b2b61` merges main with both
  sides kept in nine files. Locally on that tree: fixed points, 41 cases in JIT/AOT, hosted and GC
  stress, six make gates, and the opt-in group (4 of 4 steps) pass.

## Next: `pack_into`/`readinto` before `memoryview`

Mentions in the merged tree (`grep -rw`, `lib/**/*.py` and `ports/`):

| Name | lib files | `lib/compatibility.md` notes | ports |
|---|---|---|---|
| `bytearray` | 5 (89 lines) | 7 | 0 |
| `memoryview` | 3 (11 lines) | 5 | 0 |
| `unpack_from` | 2 | 3 | 0 |
| `pack_into` | 2 | 1 | 0 |
| `readinto` | 0 | 2 | 0 |

The notes that name a gap are about library functions that take no bytearray: `struct`
(`pack_into()`), `binascii` and `base64` inputs, `io.BytesIO` (`readinto()`, `getbuffer()`). Each
`memoryview` mention is a note that there is none; no code waits on one. A memoryview of a
bytearray also needs an export count that every resizing method checks (CPython's `BufferError`),
so it changes the class it sits on.

Not done: rejection cases for the unsupported forms (`bytes + bytearray`, `bytes == bytearray`,
`int * bytearray`, `bytes | bytearray` annotations), `make irsame`, macOS.

## #1478 in v0.6.0-alpha.3 (2026-11-18)

Main `e2b97bb45` merged in; an independent review of `35c9bdeaa` found nine problems, fixed in
`f0d3f0b59` with a case each recorded with CPython (two crashes of a `bytearray | None` that is
None, a new compile-time rejection of a `__bytes__` returning no bytes, and six mismatches). The
three crash and rejection cases fail with `35c9bdeaa`'s compiler. Fixing `__eq__` to return
`NotImplemented` made `bytes == bytearray` compile and match CPython. Deferred: #1552.

## Taking bytes or a bytearray (branch `-byteslike`, head `db8e3b42`)

A parameter annotated `bytes | bytearray` is left unannotated and recorded (`FnInfo.bufs`), so
each call specializes the function for its argument's type; `pcoerce` takes any other argument as
an annotated `bytes` parameter does. `struct` reads a bytearray through its module's readers
(`_get_int`, `_get_bool`, `_get_pascal`, `_bytes`) and `pack_into()` writes into one
(`_store_int`, no bytes object between). `hashlib` takes `bytes(data)`.

Found on the way: a slice of all of a bytes object is that object (`pys_str_slice`), so an `s`
item spanning a full buffer was the live buffer (`b'!bcd'` where CPython prints `b'abcd'`); and
Pystachy value-numbers a runtime call without memory effects, `pys_bytes_get` among them, so a
buffer must never be read as a `bytes`. `analysis.buffer_escape` now rejects, when the module
compiles, any read of a buffer but through the primitives; a copy of the module with a buffer
alias is rejected, naming the line.

Buffer benchmark (`bench_buffers.py`, 200,000 records of 6 bytes, AOT, best of 5 rounds, three
runs; CPython 3.13.16 from an earlier run of the same script on this host):

| Operation | This branch | CPython |
|---|---:|---:|
| `pack_into` a bytearray | 0.56 ms | 21.5 ms |
| assign `struct.pack(...)` to a slice | 15.6 ms | 60.7 ms |
| `b"".join` of `struct.pack(...)` | 17.3 ms | 33.2 ms |
| `unpack_from` of bytes | 1.41 ms | 28.8 ms |
| `unpack_from` of a bytearray, in place | 0.43-0.52 ms | 28.7 ms |
| `unpack_from` of a copy of each record | 5.4 ms | 82.9 ms |

## One alias class for byte payloads (branch `-bytetbaa`)

A program's inline reads of a `bytes`'s length and bytes and the bytearray's primitives carry
TBAA tags of a struct `@str` under the fields' root (length at 0 with `!range`, bytes at 24);
a `bytes`'s reads and a buffer's reads and writes share one tag, and nothing is marked
invariant. `Gen.memclass` gives `Gen.canon` the same classes. Against the bytes-like head, the
IR of all 5,231 programs differs in metadata and checkout paths only (no code, status or message
changes; tools/irsame-metadata-only.sh and a pass that also drops path lines).

Negative controls: with buffer stores tagged apart from their loads, `bytes_alias_orders.py`
prints 85244 where CPython prints 85850 (LLVM reuses a stale byte at indices only the run knows
to be equal; at equal addresses basic alias analysis decides first and no tag matters); with
`Gen.memclass`'s rules off, its unit test fails.

Instructions (callgrind, one run, same outputs):

| Program | Without | With | Change |
|---|---:|---:|---:|
| bytearray append, then index (2,000,000) | 38,438,053 | 34,438,081 | -10.4% |
| `scan.py`: cursor in a field, 1 MiB | 34,177,284 | 27,885,828 | -18.4% |
| parser, bytearray serializer | 1,222,669,094 | 1,211,636,199 | -0.9% |
| parser, `list[int]` serializer | 1,329,363,940 | 1,327,199,909 | -0.2% |
| buffer benchmark | 993,025,559 | 990,425,611 | -0.3% |

Time, interleaved on one core: `scan.py` on 32 MiB, 0.160 s against 0.151 s (medians of 7,
ranges 0.159-0.184 and 0.149-0.153), 5.6% less, as #1442's round measured for a cursor in a
field. The append and index loops: no difference beyond noise (2.05 against 2.03 ms, 1.59
against 1.61 ms), though they run 10.4% fewer instructions. One slower result: in the buffer
benchmark's binary the `unpack_from` loop of bytes took 1.74 against 1.42 ms (medians of 8),
with the same instructions in `_struct._unpack_int` (41.6 M in both); the same loop in a program
of its own takes 0.101 against 0.102 s. That is the binary's layout, not the tags.
