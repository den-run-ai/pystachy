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
