# Minimal LLVM toolchain

[`tools/llvm_toolchain.sh`](../tools/llvm_toolchain.sh) builds, from LLVM's release sources,
the part of LLVM that Pystachy's driver runs: `clang`, `opt`, `lli`, `llc`, `llvm-link` and
`llvm-as` over one shared `libLLVM` that holds the host's target alone, with clang's C headers
for that architecture. Built in the `manylinux_2_28` image, the x86-64 archive is 25.5 MiB
(101.1 MiB unpacked) and its tools run on Linux with glibc 2.28 or later.

Pystachy does not download this toolchain: [installation](install.md) still uses a
distribution's LLVM, or the pinned packages that `pystachy_toolchain.py` fetches. Select a
built toolchain with `PYSTACHY_LLVM`:

```sh
tar -xJf pystachy-llvm-18.1.8-linux-x86_64.tar.xz
export PYSTACHY_LLVM="$PWD/pystachy-llvm-18.1.8-linux-x86_64/bin"
tools/setup.sh --check
```

The directory can be moved: the tools find `libLLVM` through `$ORIGIN/../lib`, and clang
finds its headers in `../lib/clang/18`.

## Contents

| | Minimal toolchain | Ubuntu 24.04 packages |
|---|---:|---:|
| Download | 25.5 MiB | 64.5 MiB |
| Installed | 101.1 MiB | 308.8 MiB |
| `libLLVM` | 61.4 MiB, one target | 117.5 MiB, 21 targets |
| clang | 36.3 MiB, its libraries linked in | 61.8 MiB `libclang-cpp` |
| Host libraries | glibc 2.28, libstdc++ | glibc 2.38, libstdc++, libedit, libffi, libtinfo, libxml2, libzstd, zlib |

The Ubuntu column is LLVM 18.1.3 as `pystachy_toolchain.py` pins it, without
`libclang-rt-18-dev`. Both need the host's linker and C library development files to
link a program (`build-essential` on Ubuntu). [Measured](#measured) gives the build behind
the first column.

Each choice removes code the driver never reaches:

- **One target.** The driver compiles for the host only.
- **One shared `libLLVM`.** The six tools share it, and the [JIT runner](internals.md#the-jit-runner)
  links the `libLLVM` that `lli` loads. Clang's own libraries are linked into `clang`, where
  the linker drops what clang does not reach.
- **No optional host library.** zlib, zstd, libxml2, terminfo, libedit and libffi are off, so
  the tools need only the C and C++ libraries.
- **No static analyzer, ARC migration or plugins.** `clang --analyze` reports that the
  action is not compiled in.

LLVM is compiled at `-O2`, because the driver's time is LLVM's.
`LLVM_TOOLCHAIN_BUILD=MinSizeRel` compiles it for size instead: the archive is 16.2 MiB,
36% smaller, and `opt` and `llc` took 28% and 43% longer on the compiler's own IR.

What the archive leaves out limits three uses. It has no compiler-rt, so `PYSTACHY_CFLAGS`
with `-fsanitize`, `PYSTACHY_PROFILE_GENERATE` and the UBSan stage of `make verify` need a
distribution's LLVM. It cannot cross-compile. Without zlib, clang neither writes nor reads
compressed debug sections.

## Build

Compiling the 2,364 object files takes about two CPU-hours, 40% of it for clang's 594: 33
minutes on four cores, against a 15-minute limit on workflow jobs
([PR budget](testing.md#pr-budget)). The
[LLVM toolchain workflow](../.github/workflows/llvm-toolchain.yml) therefore shares the
compiling among jobs. It runs on manual dispatch and when the recipe changes on `main`:

1. Twelve `compile` jobs each run `tools/llvm_toolchain.sh compile OUT I 12`. It builds LLVM's
   table generators, which every job needs, then compiles every twelfth object file of the
   distribution into `OUT/objects`.
2. `package` downloads the twelve sets into one directory and runs `build` with
   `LLVM_TOOLCHAIN_OBJECTS` naming it. `build` finds each object compiled, links, runs the
   check below and packs the archive, which the job uploads with its `.sha256`.
3. `bootstrap` extracts the archive, runs the check and `make` with it, and runs two corpus
   areas in JIT and AOT.

An object is kept under a hash of its compile command, the compilers' versions and the source
archive's hash, and is reused only under that key, so every job mounts the checkout at `/src`.
`build` compiles an object that no slice compiled: a wrong slice costs time, not the result.

On one machine `build` does all of it. Build in the pinned image, from the repository root:

```sh
docker run --rm -v "$PWD:/src" -w /src \
  -e LLVM_TOOLCHAIN_GLIBC=2.28 -e LLVM_TOOLCHAIN_GLIBCXX=3.4.25 \
  quay.io/pypa/manylinux_2_28_x86_64@sha256:d086f64cddcace250ef0f0073583c51b8298159303290a730c9f59bd91edfd2c \
  tools/llvm_toolchain.sh build build/llvm-toolchain
```

The script fetches `llvm-project-18.1.8.src.tar.xz`, checks its pinned SHA-256, builds and
installs LLVM's `distribution` target, runs the check below and writes
`pystachy-llvm-18.1.8-linux-x86_64.tar.xz` with its `.sha256`. Inside the archive,
`share/BUILD.txt` records the source hash, the recipe's hash, the compiler and the library
versions needed, and `MANIFEST.sha256` lists every file. The archive has sorted names, no
owners and the sources' time, so the same binaries give the same bytes.

The archive needs C and C++ libraries at least as new as the build host's; the two
`LLVM_TOOLCHAIN_GLIB*` settings make the build fail if it needs newer ones than
`manylinux_2_28` promises. The script's header lists the other settings. On AArch64, use
the `manylinux_2_28_aarch64` image; that build is untested.

## Check

```sh
tools/llvm_toolchain.sh check build/llvm-toolchain/pystachy-llvm-18.1.8-linux-x86_64
```

The check fails unless the directory holds the six tools at the pinned release with one
registered target, `lli` loads the directory's own `libLLVM`, and no file needs a host
library other than the C and C++ libraries. It then runs the driver's steps on a small
program: C to IR, `llvm-as`, `llvm-link --only-needed`, a coroutine and `-O2` pipeline in
`opt`, and the same output from `lli`, `llc` and clang's code generation. From a checkout it
also builds [`lljit.c`](../lljit.c) against that `libLLVM` and runs its self-check, as the
driver does at first use. `python3 -m unittest discover -s tools -p test_llvm_toolchain.py`
checks the recipe's pins and the check's refusals.

## Measured

These are measurements of 19 and 20 November 2026, built in the image above on a shared
4-CPU x86-64 host. They are not rerun by CI. The `-O2` archive (SHA-256 `b61cb774…5526929e`)
comes from one `build` of the recipe at commit `7fde2da2`; the `MinSizeRel` one
(`212abbe8…89948fbc`) from `a4b2fd18`, whose LLVM settings for that build type are the same.

| | `-O2` (default) | `MinSizeRel` | Ubuntu 18.1.3 |
|---|---:|---:|---:|
| Archive | 25.5 MiB | 16.2 MiB | 64.5 MiB |
| Installed | 101.1 MiB | 69.1 MiB | 308.8 MiB |
| `opt -passes='default<O2>'` | 26.7 s | 34.3 s | 26.0 s |
| `llc -O2 -filetype=obj` | 19.9 s | 28.5 s | 20.5 s |
| `make`, the three-stage bootstrap | 308 s | 422 s | 315 s |
| Full corpus, JIT and AOT | 528 s | 698 s | not run |

`opt` and `llc` ran on the compiler's stage-1 IR (1,064,114 lines) on one pinned core, and
each figure is the median of three interleaved rounds. The bootstrap and corpus times are
single runs with four workers on Ubuntu 24.04.

The workflow ran twice on GitHub's `ubuntu-24.04` runners on 20 November 2026, first with
eight slices. Those runners compile 1.4 to 2 times slower than the host above:

| Slices | `compile` jobs | `package` | Whole run |
|---:|---:|---:|---:|
| 8 | 7.7 to 8.6 min, and one of 11.1 | 3.0 min | 22.9 min |
| 12 | 5.7 to 9.1 min | 2.7 min | 20.0 min |

A whole run includes `bootstrap`, 5.8 minutes with twelve slices, and the wait for runners
while the pull request's own checks ran. In the 11.1-minute job, one minute fetched the image
and the sources and configured, and three built the table generators. `package` found 2,360
objects compiled and assembled the other four. Both runs, and eight slices built in the same
image on the host above, gave one archive, byte for byte: SHA-256 `364462a2…94aafc98`.

With each of the three archives selected by `PYSTACHY_LLVM` on Ubuntu 24.04, `make` reached
the compiler's and the runtime's fixed points and `make test` passed all 5,395 cases (8,784
JIT and AOT runs). Every binary needs at most glibc 2.27 and `GLIBCXX_3.4.22`, and
`tools/linux_abi.py --max-glibc 2.28` reports no violation.

The toolchain's floor is lower than Pystachy's, whose [supported platforms](install.md) need
glibc 2.39. On AlmaLinux 8.10 (glibc 2.28, GCC 8's `libgcc_s`) the check passes, and `make`
reaches both fixed points only with `PYSTACHY_CFLAGS=-pthread`. Of 1,106 runs of a 559-case
sample there, 24 failed: in 22 JIT runs an exception escaped a handler that catches it in
AOT, and one case printed another last digit from `pow` in both modes.
[#998](https://github.com/den-run-ai/pystachy/issues/998) tracks an older baseline.
