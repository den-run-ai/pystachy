# qrcode 8.2: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `qrcode-8.2.tar.gz`. License: BSD-3-Clause with pyqrnative MIT notice; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `35c3f2a4172b33136ab9f6b3ef1c00260dd2f66f858f24d88418a015f446506c`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `d02f23c778031d2278cb27651cdd35cadca2a4d876a4c3b75584bd0e4fa6e285` | 1 line |
| `constants.py` | `d02b1af1861d790f0d685ad19ade3799a560d763bcf5dfa82a088a01520edace` | none |
| `exceptions.py` | `2f67d9b9838ab1cbdd9fbdab6bec05f06c2caf6641f5e4595aba757f4203c781` | none |
| `LUT.py` | `3635ca3df1d24c56282e51a45e11637f6394abf1060fa9ab772607206ddd35c9` | none |
| `base.py` | `f49ff52f29c5e5d5c92b5e00cecf17c87258eba15f4e5b9827ae85f198de4ad6` | 10 regions: 6 method annotations, a field's, an import, a slice, and the 160 rows of `RS_BLOCK_TABLE` in brackets |
| `util.py` | `54e1b846b27a4243ecd1f2da6647de330c70c5d2292ac4479ba757be3a3d625e` | 28 regions, 9 of them method annotations |
| `main.py` | `385eee1c3033d938a1a5ee857ed79fe9f8951f6b69a152797a42c2206e25c890` | 35 regions, 13 of them method annotations |

## Adaptation record

- Encoder methods/fields are annotated; properties become fields with explicit checks in `make()`, and unused image-factory paths are omitted.
- The QR block table becomes lists of lists, preserving its values across rows of different lengths. Chunk generators materialize lists.
- `mask_bit()` selects the same expressions as upstream’s returned lambdas. Narrow string scanners replace the chunker’s regular expressions.
- Strings carry the byte payload; a CPython-only UTF-8 conversion branch keeps the adapted module’s output comparable with upstream. `constants.py`, `exceptions.py` and `LUT.py` are unchanged.

## Validation snapshot

`tests/port_qrcode_encode.py` prints three codes with `print_ascii()`: alphanumeric
(`HELLO WORLD`, level Q, border 1), numeric (20 digits, level L, inverted, no border) and
UTF-8 bytes (`https://example.com/путь?q=€`, level H, version 4). Then it prints checksums of
the modules of codes of no data, of mixed data that the optimizer splits into four chunks, of
CJK and emoji text, of a version-7 code (with its version information), of each of the 8 masks
given, and of a code given its version and mask by position (with `image_factory`'s `None`
fifth). Then the errors: `QRCode()`'s checks of `version` (41, 0, -1, 2**63 - 1, -2**63),
`mask_pattern`, `box_size` and `border`; an `int` `image_factory`; the setters' checks of 3
(`mask_pattern = 9`, `version` = 41, 0 and -1), and assignments that pass them; data too long
for version 1-H (`DataOverflowError`) and for any version (2,953 bytes fit 40-L, 2,954 raise the
version setter's `ValueError`); `error_correction=5` (`IndexError`); and `print_ascii(tty=True)`.
Then `best_fit()` across the three sizes of the length fields (versions 9/10 and 26/27, where it
tries again); `get_matrix()` with and without a border, and the aliasing of its border rows; two
`add_data()` calls and a second `make()`; `make(fit=False)` without a version; and the chunk
optimizer on 16 edge cases (each class of character, `$` before a final `"\n"` in the anchored
form, non-ASCII bytes between runs, NUL, combining marks) with `minimum` 1, 4 and 20, a
negative `minimum` (with and without the literal text `{-1,}` in the data, and a code made
with `optimize=-1`), and 60 pseudo-random strings, and `optimal_mode()`. `tests/run.sh`
compares what it prints with CPython's, JIT and AOT. Run under CPython against the unmodified
upstream package, it prints exactly what it prints against this port.

It leaves out what the port leaves out, and the deviations described in the port guide. The evaluation's and its
verifier's longer drivers print the same under CPython against the unmodified upstream, under
CPython against the port, and JIT and AOT: a 183-line demo, 310 strings through the chunker
(3,168 chunks) and 250 longer ones (11,586), the verifier's harder inputs (CJK, emoji,
combining marks, NUL, the 40-L capacity edges of 2,953 bytes and 7,089 digits, 64-bit
extremes, two `add_data()` calls) and `get_matrix()`.

The test is one program, not two, because its AOT build is slow, and `make verify` builds
every test in several stages: most of the build's time is LLVM's on the module code that makes
`RS_BLOCK_TABLE`'s 160 lists (a module of that table alone takes 2.2 s of CPU to build, where
hello world takes 0.14 s). On a 4-core VM that other jobs kept busy (load average 5 to 6), the
test runs in 0.4 s JIT, its AOT build takes 4.8 s (4.5 s of CPU) and the executable runs in
0.01 s. Under `make verify`'s gc-stress stage (the compiler collecting every 1,000
allocations, the program at every allocation), the JIT run takes 2.1 s, the AOT build 5.7 s
and the AOT run 1.7 s: 9.5 s in all, 8.1 s of CPU. Choosing a mask makes a code 9 times, so the
version-7 code, and the codes of `get_matrix()`, of the second `make()` and of
`make(fit=False)`, are given their mask.

## Benchmark snapshot

The evaluation's headline workload: 400 codes of all four error correction levels and versions
3 to 16 (URLs with letters and digits, so that the optimizer splits them), each fitted, masked
by the best of 8 and laid out, with a checksum of the versions and the dark modules (`codes 400
versions 3473 dark 570996` in all three). Median of 3 runs, with process start-up, on a 4-core
x86-64 VM:

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.535 s | 0.533 s |
| CPython 3.13.16, unmodified qrcode 8.2 | 4.571 s | 4.510 s |
| CPython 3.13.16, this port | 5.779 s | 5.337 s |

That is 8.5 times faster; a second set of runs gave 0.541 s and 4.629 s (8.6 times). JIT, with
the compilation, takes 0.948 s, and the executable is 402 KB. The VM's load average was 5 on
its 4 cores. qrcode has no C extension, but CPython runs its chunk optimizer in the C regex
engine; under CPython the port, whose optimizer and UTF-8 encoding are Python loops, is slower
than upstream, so the executable runs the code of this port 10 times faster (in CPU time) than
CPython does.
