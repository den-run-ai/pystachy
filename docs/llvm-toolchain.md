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
compiling among jobs. Only a person starts it, since an uncached run takes an hour of runner
time:

1. `generators` runs `tools/llvm_toolchain.sh fingerprint OUT`, a hash of the source archive,
   the compilers' versions and every compile command, and looks for a cache of objects under
   it. Finding none, it runs `tools/llvm_toolchain.sh generators OUT`, which compiles LLVM's
   three table generators into `OUT/objects`: nearly every other object file includes a header
   that one of them writes, so each of the next jobs needs them first.
2. Six `compile` jobs start with those objects and each run
   `tools/llvm_toolchain.sh compile OUT I 6`, which compiles every sixth object file of the
   distribution into `OUT/objects`. With cached objects these jobs are skipped.
3. `package` restores the cached objects, or downloads the jobs' sets into one directory, and
   runs `build` with `LLVM_TOOLCHAIN_OBJECTS` naming it. `build` finds each object compiled,
   links, runs the check below and packs the archive, which the job uploads with its
   `.sha256`. After a run that compiled, the job caches the directory.
4. `bootstrap` extracts the archive, runs the check and `make` with it, and runs two corpus
   areas in JIT and AOT.

An object is kept under a hash of its compile command, the compilers' versions and the source
archive's hash, and is reused only under that key, so every job mounts the checkout at `/src`.
A job compiles what its directory lacks: a slice without the generators' objects, or `build`
after a wrong slice, costs time, not the result.

The cache serves a run whose fingerprint an earlier run had: a change to the recipe's check or
packing, or to the workflow, compiles nothing. A new LLVM release, compiler or compile flag
compiles everything. GitHub drops a cache that no run has read for seven days, and one written
on another branch than `main` serves that branch alone.

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
versions needed, and `MANIFEST.sha256` lists every file. `share/licenses` holds LLVM's and
clang's licenses and, in `LLVM-THIRD-PARTY.TXT`, the terms of the code that `libLLVM` compiles
in under other ones: the regex, BLAKE3, xxHash, MD5 and SHA sources and Unicode's tables. The
archive has sorted names, no owners and the sources' time, so the same binaries give the same
bytes.

The archive needs C and C++ libraries at least as new as the build host's; the two
`LLVM_TOOLCHAIN_GLIB*` settings make the build fail if it needs newer ones than
`manylinux_2_28` promises. The script's header lists the other settings. On AArch64, use
the `manylinux_2_28_aarch64` image: the workflow builds x86-64 alone, and [measured](#measured)
has the one AArch64 build.

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

## Publish

Run the workflow on `main` with a revision, such as `1`. Once `bootstrap` has passed, the
`publish` job runs [`tools/llvm_toolchain_release.py`](../tools/llvm_toolchain_release.py), which
attaches the archive and its `.sha256` to the GitHub release `llvm-toolchain-18.1.8-1`. No other
job can write to the repository, and a run given a revision on another branch stops before it
compiles.

The release is a draft until the archive has been downloaded from it and compared. It is not
a Pystachy version: its tag starts no release workflow, and it is published as neither a
prerelease nor the repository's latest release, which the tool checks afterwards. A published
release is not changed. Publishing the same archive under its revision again passes, and
another archive needs the next revision; any change to `tools/llvm_toolchain.sh` gives
another archive, because `share/BUILD.txt` records the recipe's hash.

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

The workflow ran six times on GitHub's `ubuntu-24.04` runners on 20 November 2026; the fifth
was a second attempt of the fourth, at the same commit. Those runners compile 1.4 to 2 times
slower than the host above. In the first two runs there was no `generators` job, and every
slice compiled the table generators itself:

| Jobs before the archive | Each `compile` job | Their runner time | Archive after | Whole run |
|---|---:|---:|---:|---:|
| 8 slices, `package` | 7.7 to 8.6 min, and one of 11.1 | 70.1 min | 17.1 min | 22.9 min |
| 12 slices, `package` | 5.7 to 9.1 min | 86.2 min | 13.6 min | 20.0 min |
| `generators`, 6 slices, `package` | 7.3 to 9.3 min | 53.7 min | 14.6 min | 20.4 min |
| `generators`, 8 slices, `package` | 5.8 to 8.0 min | 60.6 min | 13.5 min | 19.4 min |
| `generators`, `package`: objects cached | skipped | 3.5 min | 3.6 min | 10.0 min |
| `generators`, 6 slices, `package`: cache written | 7.1 to 8.2 min, and one of 10.7 | 55.0 min | 16.9 min | 22.5 min |

A whole run adds `bootstrap`, 5.8 to 6.3 minutes, and the wait for runners while the pull
request's own checks ran: up to 3.6 minutes in the first run. `generators` took 2.8 minutes,
or 0.9 when it found the cache, and `package` 2.3 to 3.0. The fifth run found the 68 MB cache
that the fourth wrote, and compiled nothing.

Twelve slices that each compiled the generators brought the archive one minute sooner than
six that did not, for 60% more runner time, because each job repeated the same work. The
slowest of the twelve jobs and a quick one each spent a minute fetching the image and the
sources and configuring, and two to three minutes on the generators: 46% of the job. With the
generators' objects, a slice reached its own 16 to 21 seconds into the build. Eight such
slices brought the archive 1.1 minutes sooner than six, for 13% more runner time; that is
within the spread of the runners, on which equal slices of one run took 7.3 to 9.3 minutes,
so the workflow compiles six. The sixth run was the workflow as it is, six slices that end by
writing the cache, on a branch that held none; one slow slice set its 16.9 minutes. By these
times one runner would need about 45 minutes for the whole build, an estimate: no job may run
that long.

`package` found 2,360 objects compiled and assembled the other four. The first two runs, and
eight slices built in the same image on the host above, gave one archive, byte for byte:
SHA-256 `364462a2…94aafc98`. The third run and six slices on that host gave another,
`8c964bce…799ca32c`, and the fifth run and those six slices a third, `9d71e217…528b61c1`. The
files of all three are equal except `share/BUILD.txt`, which records the recipe's hash. The
recipe then added `share/licenses/LLVM-THIRD-PARTY.TXT`: the sixth run, which compiled every
object again, and that host's objects of before gave a fourth archive, `aa7aeba2…86e18d85`,
whose other files are the third's.

The sixth run's jobs also ran once on `ubuntu-24.04-arm` runners in the
`manylinux_2_28_aarch64` image, with the recipe unchanged. The slices took 7.0 to 9.7 minutes,
and the AArch64 archive, 23.0 MiB with SHA-256 `bf002c93…dc6fd087`, was ready after 15.3
minutes. It passed the check, and with it `make` reached both fixed points and two corpus
areas passed in JIT and AOT. That is one build: nothing has reproduced its bytes.

With each of the first three archives selected by `PYSTACHY_LLVM` on Ubuntu 24.04, `make`
reached the compiler's and the runtime's fixed points and `make test` passed all 5,395 cases
(8,784 JIT and AOT runs). Every binary needs at most glibc 2.27 and `GLIBCXX_3.4.22`, and
`tools/linux_abi.py --max-glibc 2.28` reports no violation.

The toolchain's floor is lower than Pystachy's, whose [supported platforms](install.md) need
glibc 2.39. On AlmaLinux 8.10 (glibc 2.28, GCC 8's `libgcc_s`) the check passes, and `make`
reaches both fixed points only with `PYSTACHY_CFLAGS=-pthread`. Of 1,106 runs of a 559-case
sample there, 24 failed: in 22 JIT runs an exception escaped a handler that catches it in
AOT, and one case printed another last digit from `pow` in both modes.
[#998](https://github.com/den-run-ai/pystachy/issues/998) tracks an older baseline.
