# pyaes 1.6.1: port reference

[Port guide](PORT.md) · [All ports](../README.md)

Upstream hashes identify the inputs used for this adaptation. Validation counts, build times
and benchmark timings below are historical snapshots from the port work; they have not been
rerun for every compiler change. Consult the [language guide](../../docs/language.md) for
current compiler features rather than inferring them from the adaptations.

## Upstream provenance

Source archive: `pyaes-1.6.1.tar.gz`. License: MIT; see [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES).

Archive SHA-256: `02c1b1405c38d3c370b085fb952dd8bea3fadcee6411ad99f312cc129c536d8f`.

| file | upstream SHA-256 | edits |
|---|---|---|
| `__init__.py` | `e20e2b5dedefe93c7259df8f59f017de1fad737b45f48074a36b09d6010226e7` | 2 regions |
| `aes.py` | `5dc0ff7ad948704ae9814fc2720f9b479599092a7a46e1fd9d55b78953a1a43f` | 12 regions, and `xrange(` written `range(` on 21 lines |

## Adaptation record

- AES methods and round-key fields are annotated; key bytes are represented as integer lists.
- The Python 2 compatibility shim is removed and twenty-one `xrange()` calls become `range()`.
- `list(a)` replaces shallow copying; signed big-endian key words are constructed with the module’s own word helper in place of `struct.unpack()`.
- The blockfeeder import and class-valued mode registry are omitted; unused mode code remains in `aes.py` and is outside the supported API.

## Validation snapshot

`tests/port_pyaes_cipher.py` runs the known answers of the standards both ways: FIPS-197's
Appendix C (the key 00 01 02 ... and the block 00 11 22 ... ff, for each key size, with its
number of rounds), and the twelve ECB blocks of NIST SP 800-38A F.1, whose three keys are
FIPS-197's Appendix A examples, with the last round key of each expansion as Appendix A lists
it and the first as signed words (`8e73b0f7` is -1905020681, as `struct.unpack('>i')` reads it).
Then it encrypts a block 20 times over and decrypts it back, for nine keys of the three sizes;
keys whose words read as -1, -2139062144, 2**31 - 1, -2**31 and 0 (signed-word conversion edges); blocks
of ints outside 0..255 (256, -1, 2**31, 2**39 - 1 and -129, and ints just inside the 64-bit
limits of each place in a word), which the cipher takes as upstream's does; a key list changed
after `AES()` has read it; counter mode built on `AES`, on the README's example; Telethon's
AES-IGE, on OpenSSL's IGE test vector (`test/igetest.c`) and with a 256-bit key; and the
`ValueError`s for keys of 0, 15, 17 and 33 ints and blocks of 0, 15 and 17. The known answers
are the standards' values, and OpenSSL (through CPython's `cryptography`) gives the same
ciphertexts. pyaes's own tests compare it with PyCrypto on random data, which the port cannot
run.

`tests/run.sh` compares what it prints with CPython's, JIT and AOT. Run under CPython against
the unmodified upstream package, with `AES.__init__` handed `bytes(key)` (upstream reads its key
with `struct.unpack`, which takes `bytes` only; that is the one adaptation), it prints exactly
what it prints against this port. It passes JIT and AOT with `PYSTACHY_IRCHECK=1`, also with the
CPython-hosted compiler and with `PYSTACHY_OPT=-all`.

It is one program rather than two because of its AOT build: building any program that uses
`pyaes.aes` takes 8.2 to 9.1 s of CPU time, where `print("hello")` takes 0.14 s and
`tests/port_iniconfig_api.py` 1.0 s. The time is clang's `-O2` over the module's code that
makes the 15 tables, one function of 3,614 list appends: `pystachy ir` takes 0.02 s, and a
class of the tables alone takes 7.5 to 8.2 s to build. The JIT run takes 0.26 to 0.28 s of CPU
time, and the executable 0.002 s. Under `make verify`'s gc-stress stage (the compiler collecting
every 1,000 allocations, the program at every allocation), the JIT run takes 0.37 to 0.44 s and
the AOT build and run 8.5 to 8.8 s and 0.06 s: 8.9 to 9.3 s of CPU time in all. On this 4-core
VM, running other jobs at a load of 10 to 14, the three steps took 9.2 to 16.3 s of wall-clock
time in four runs, almost all of it the AOT build.

## Benchmark snapshot

The headline workload is counter mode's: for each key size, 200,000 counter blocks encrypted,
with a checksum of the first and last byte of each and every 64th block decrypted back and
compared, 600,000 block encryptions and 9,375 decryptions in all (checksum 795704754 in every
row). Median of 3 runs, with process start-up, on a 4-core x86-64 VM:

| | wall clock | CPU time |
|---|---:|---:|
| Pystachy AOT executable, this port | 0.415 s | 0.278 s |
| CPython 3.13.16, unmodified pyaes 1.6.1 (`bytes` keys) | 14.002 s | 12.292 s |
| CPython 3.13.16, this port | 14.054 s | 11.760 s |
| CPython 3.13.16, `cryptography` 50.0.1 (OpenSSL), one block per call | 0.484 s | 0.394 s |

That is 44 times faster than CPython on upstream in CPU time, and 34 times in wall-clock time;
a second set of runs gave 0.285 s and 12.451 s of CPU time (44 times), and a third, with the
compiler of main at 4dc548a, 0.281 s and 12.190 s (43 times). The VM was running other jobs (a
load of 6 to 14 on its 4 cores), which spreads the wall-clock times; an earlier
measurement of a draft of this port on a quieter VM gave 0.32 s and 12.23 s of wall-clock time
(38 times). pyaes has no C extension: CPython runs it as Python everywhere, and programs that
need fast AES on CPython use a C library instead, such as `cryptography` or `pycryptodome`. For
scale, the last row runs the same loop with OpenSSL's AES through `cryptography`, one 16-byte
block per call: the executable's AES, pure Python compiled, takes less time than CPython
driving OpenSSL block by block.
