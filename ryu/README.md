# ryu/: Ryu's shortest float digits

`repr()` of a float (and `str()`, `print()`, an f-string field without a spec, a float in a
container) prints the fewest digits that read back as the same float, and of those the closest to
it, as CPython's `dtoa` (mode 0) gives them. runtime.c's `pys_str_float` gets those digits from
[Ryu](https://github.com/ulfjack/ryu)'s `d2s_buffered_n()`, which this directory holds, and lays
them out as CPython does (where the point goes, when an exponent is written). runtime.c includes
`d2s.c`, so it is compiled wherever runtime.c is: the runtime of `pystachy run` and
`pystachy build`, the extension modules of `pystachy ext`, and the probes in `tools/`. The
driver's cached runtime is built from these files' bytes as from runtime.c's, and keyed by them
(`RTPARTS` in pystachy.py lists them; [docs/runtime-in-subset.md](../docs/runtime-in-subset.md)
§1.4).

| file | lines | from upstream |
|---|---:|---|
| `d2s.c` | 509 | `ryu/d2s.c` |
| `common.h` | 114 | `ryu/common.h` |
| `d2s_intrinsics.h` | 357 | `ryu/d2s_intrinsics.h` |
| `d2s_small_table.h` | 186 | `ryu/d2s_small_table.h` |
| `digit_table.h` | 35 | `ryu/digit_table.h` |
| `ryu.h` | 46 | `ryu/ryu.h` |
| `LICENSE-Boost` | 23 | `LICENSE-Boost` |

They are upstream's files at commit
[`4c0618b0e44f7ef027ebae05d2cc7812048f7c8f`](https://github.com/ulfjack/ryu/tree/4c0618b0e44f7ef027ebae05d2cc7812048f7c8f)
(2026-02-09); the last commit that changed them is `2dc4e9de79193dff780f85a95a5cf16456cbc414`
(2026-01-23, "d2s_small_table.h: fix small table POW5_INV_OFFSETS"). The one change: each
`#include "ryu/NAME"` line reads `#include "NAME"`, since a quoted include is looked for next to
the file that holds it, and the compiler is given no `-I`. Nothing else of upstream is here:
runtime.c defines `RYU_OPTIMIZE_SIZE`, so `d2s_full_table.h` is not needed (its tables take
10,688 bytes, the small ones 828, which compute the powers of 5 in between with a multiplication),
and the other conversions (`f2s`, `d2fixed`, `s2d`) are not used.

runtime.c declares `d2s_buffered_n`, `d2s_buffered` and `d2s` static before it includes `d2s.c`,
so that no symbol of Ryu leaves the runtime (the two it does not call are dropped), and includes
it with `NDEBUG` defined, as a release build would: Ryu's asserts check its own invariants, and
would make float repr call the C library's `__assert_fail`, a use of state (I) to
`tools/check_runtime.py`, which `pys_str_float`'s RUNTIME entry does not have.

## License

Upstream offers the files of its `ryu/` directory under the Apache License 2.0 or, alternatively,
the Boost Software License 1.0. Pystachy uses them under the **Boost Software License 1.0**,
whose text is `LICENSE-Boost`, as upstream gives it: it asks that the copyright notices ("Copyright
2018 Ulf Adams", in each file's header) and the license stay with the source, but asks nothing of
the machine code that Pystachy links into each program it builds. [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES)
lists them too.

## Updating

Copy the six files from upstream's `ryu/` directory at the new commit, make their includes relative
(`sed -i 's|^#include "ryu/\([a-z0-9_]*\.h\)"|#include "\1"|' ryu/*.c ryu/*.h`), and name the
commit here, in THIRD_PARTY_NOTICES and in the comment above runtime.c's `#include "ryu/d2s.c"`.
A file that the new `d2s.c` includes and these do not has to join them in `RTPARTS`, or the
driver's build of the runtime will not find it. `tests/programs/numbers/float_repr.py` checks the digits against
CPython's.
