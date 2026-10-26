# Integer work of 2026-10-26: session tooling and raw evidence

Research evidence only; do not merge this branch. These are the scratch tools, probes, outputs and logs behind #902, #903, #904 and #905 (merged) and draft #906 (#125's masked arithmetic), kept as the session left them. Nothing here is maintained. Scripts keep the session's absolute paths (`/home/user/pystachy`, and `$SP` for the scratch directory), and logs name binaries and directories that were not kept (listed below).

Revisions: main `68a67fcb4b6bf927f9db4ca7d15d7d3cd6eccf97` (after #905); #906 head `623f3fe172d5778f7f6894b2aae839fe1b5a9d82`; #901 head `9c81341a7b47dcddb8829c731c0fe0ca7901cd9b` for `bench/integers`. Toolchain: Linux x86-64, LLVM and clang 18.1.3, GCC 13.3.0 for the sanitizer builds, CPython 3.13.16 from uv 0.12.23.

| Path | Contents | Used for |
|---|---|---|
| `h/` | C harness. `common.h` stubs `runtime.c`'s helpers so `mpz.c` compiles alone. Each `*_tu.c` renames one `mpz.c`'s entry points (`old_*`, `new_*`, ...): `mpz_old.c` is `mpz/mpz.c` at `5996c1c4` (#889), `mpz_arith.c` and `mpz_div.c` are working copies within 11 and 19 lines of #904's and #905's merged files, and `new_tu.c` includes the checkout's. `test.c` compares new with old (value, digits, error text); `cpy.c` answers `hpy/cmp_*.py`'s commands; `bench*.c` time old and new in a bump arena; `div.patch` is an intermediate #905 diff. | #903-#905: differential checks under `-fsanitize=address,undefined`, core timings |
| `hpy/` | `cmp_text.py`, `cmp_arith.py` and `cmp_div.py` compare `h/cpy.c` with CPython's `int` on random inputs. `cpy_arith_time.py` and `cpy_div_time.py` are the CPython `timeit` baselines. `runbench.py` takes interleaved, pinned medians of `bi/`. `irfuncs.py` and `irfuncs.sh` list the functions whose IR differs, naming string constants by their contents. `masksites.py` lists the `&` expressions #906 lowers. | #903-#906 |
| `irsame_all.sh` | IR oracle over the corpus, with both compilers reading one `PYSTACHY_HOME` | #906 |
| `bi/` | #901's `bench/integers` programs: `*_mpz.py` unchanged, the others with the `# pystachy: python-int` line blanked | #904 and #905 end-to-end timings |
| `prof/` | single-test copies of the adapted `test_long` program, for profiling | #902, #904, #905 |
| `m125/`, `m125b/` | #125's repros and their outputs: `.cpy` CPython, `.old` main, `.new` and `.newaot` #906 in JIT and AOT, `.hosted` the draft under the hosted compiler. `irshape.*` are IR shapes, `masked_draft.py` the first draft of the lowering, `aug.py` the `&=` probe. | #906 |
| `dynid/` | Dynamic `Any` identity probe and its outputs | #906's second commit |
| `probe/octal_limit.py` | `int(text, 0)` digit-limit probe | #903 |
| `rv.ivjm/` | one `random`-importing program's IR under main's (`old.ll`) and #906's (`new.ll`) compilers | #906 IR oracle |
| `*.log`, `*.txt`, `*.out`, `optin.json` | build, lint and check logs, `irsame` runs, the Dynamic `Any` opt-in replay, focused runs, case lists and outputs | #903-#906 validation |
| `pr_*.md` | the published descriptions of #904 (`mul`), #905 (`div`) and #906 (`masked`) | |

Not kept (rebuildable, environment-specific, or not written in this session):

- 61 executables: AOT builds of `bi/`, `prof/` and the probes, and sanitizer builds of `h/`.
- `venv/` (CPython 3.13.16 from uv 0.12.23) and `uvenv/` (the virtual environment that installed uv).
- `cpython-src/`: `Python-3.13.16.tar.xz`, SHA-256 `f4b1bfb3c79b5bb11b8d228a12504163b4c0dab4d679828d8f5f26b6cb6ab35d`; its `Objects/longobject.c` has SHA-256 `8f3c1c8e496b5eab4ebca0b908bea0fe82a5815882cbc6e4edcb16b437eea0e5`.
- Five runtime homes (`arithhome`, `divhome`, `oldhome`, `ubsan-home`, `ubsan-masked`): copies of `lib/`, `mpz/`, `runtime.c`, `runtime.py` and `ryu/` at the tested revisions, with their build caches.
- `bench-upload/`: the uploaded `int-representation-bench.tar.gz`, which the session read but did not write.

Copies of `mpz/mpz.c` and of the adapted CPython tests keep their sources' licenses, as the repository's `THIRD_PARTY_NOTICES` records. Claude Code wrote these files during the session, at the maintainer's request; they have had no independent review. `SHA256SUMS` lists every other file here.
