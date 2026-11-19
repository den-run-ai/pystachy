# Minimal LLVM toolchain

[`tools/llvm_toolchain.sh`](../tools/llvm_toolchain.sh) builds, from LLVM's release sources,
the part of LLVM that Pystachy's driver runs: `clang`, `opt`, `lli`, `llc`, `llvm-link` and
`llvm-as` over one shared `libLLVM` that holds the host's target alone, with clang's C headers
for that architecture. Built in the `manylinux_2_28` image, the archive runs on Linux with
glibc 2.28 or later.

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

Each choice removes code the driver never reaches:

- **One target.** The driver compiles for the host only.
- **One shared `libLLVM`.** The six tools share it, and the [JIT runner](internals.md#the-jit-runner)
  links the `libLLVM` that `lli` loads. Clang's own libraries are linked into `clang`, where
  the linker drops what clang does not reach.
- **No optional host library.** zlib, zstd, libxml2, terminfo, libedit and libffi are off, so
  the tools need only the C and C++ libraries.
- **`MinSizeRel`.** LLVM is compiled for size.
- **No static analyzer, ARC migration or plugins.** `clang --analyze` reports that the
  action is not compiled in.

What the archive leaves out limits three uses. It has no compiler-rt, so `PYSTACHY_CFLAGS`
with `-fsanitize`, `PYSTACHY_PROFILE_GENERATE` and the UBSan stage of `make verify` need a
distribution's LLVM. It cannot cross-compile. Without zlib, clang neither writes nor reads
compressed debug sections.

## Build

Compiling LLVM and clang takes longer than the 15-minute limit on workflow jobs
([PR budget](testing.md#pr-budget)), so no workflow runs the build. Build in the pinned image,
from the repository root:

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
