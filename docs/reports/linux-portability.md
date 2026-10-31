# Linux binary portability assessment

Date: 2026-10-30. Related roadmap: [#998](https://github.com/den-run-ai/pystachy/issues/998).
Source inspection starts from `main` at
[`06e3ad5d`](https://github.com/den-run-ai/pystachy/commit/06e3ad5d08514ba31fb231fe4636a962fe6578e3).

## Decision for alpha.4

Keep the Ubuntu 24.04 / **glibc 2.39+** support baseline for both Linux release
architectures. `manylinux_2_28` is a plausible follow-up build target, but no
Pystachy compiler has been built and executed at that baseline in this assessment.
The published Linux executable already imports symbols newer than 2.28, and
relabeling that artifact cannot make it portable.

Linux ARM64 release work and an older libc baseline are independent changes. An
Ubuntu ARM64 build establishes neither manylinux compliance nor a portable
cross-compilation sysroot. Compiler wheels and pip/uv installation remain separate
deliverables under #998.

## Measured published artifact

This evidence is from the **published alpha.3 x86-64 archive**, not the alpha.4
candidate or an ARM64 build. The archive was downloaded from the
[alpha.3 release](https://github.com/den-run-ai/pystachy/releases/tag/v0.1.0-alpha.3)
and checked against its published `.sha256` file before extraction. The manifest
identifies source commit `f5a09d4223139d7255e31051be97fc509e1ca1fe`.

| Property | Observed value |
|---|---|
| Archive | `pystachy-v0.1.0-alpha.3-linux-x86_64.tar.gz` |
| Archive SHA-256 | `4e12e30ce6c48fd2d30163b7af01e51b1048976670f9a9b025d5edc4e7a2a864` |
| Compiler SHA-256 | `ae0c4b0508a7b47536e12244a00b538c35a6f5149dcbc00ffcaab6b35a48c524` |
| ELF objects in complete extracted payload | 1: the native compiler |
| ELF architecture / type | x86-64 / `ET_DYN` position-independent executable |
| Imported GLIBC symbol floor | **2.38** |
| Direct shared-library dependencies | `libc.so.6`, `libm.so.6`, `libgcc_s.so.1` |
| Imported GCC unwind versions | `GCC_3.0`, `GCC_4.2.0` |
| RPATH / RUNPATH | None |

The imports above the proposed 2.28 baseline are:

| Symbol | Required version |
|---|---|
| `__isoc23_strtol`, `__isoc23_strtoll` | `GLIBC_2.38` |
| `__libc_start_main` | `GLIBC_2.34` |
| `stat`, `lstat`, `fstat` | `GLIBC_2.33` |

These are imported versions from `readelf --dyn-syms` / `--version-info`, not
strings found anywhere in the executable. A symbol floor is only a lower bound;
it does **not** justify lowering the documented support baseline from 2.39 to
2.38. External LLVM, distribution libraries, CPU requirements and actual execution
still need validation.

## What must be portable

The [release packager](../../tools/release.py) ships one native compiler plus
runtime C/Python sources, `pyext.c`, `pyembed.c`, library sources, and the Ryu/mpz
sources. It does not bundle LLVM or libpython. The compiler can report its version
without LLVM; compiling and running new programs requires the toolchain.

The [driver](../../src/pystachy_compiler/driver.py) and
[setup check](../../tools/setup.sh) require **five matching LLVM tools**:
`clang`, `opt`, `lli`, `llvm-link`, and `llvm-as`. Linux verification uses LLVM 18.
`llc` is not a separate prerequisite in the current driver. JIT mode also builds
and loads a runtime shared library; AOT mode links a runtime built against the
consumer's headers and libraries. CPython embedding/extensions and optional FFI
libraries have additional dependencies.

Consequently, four questions need separate answers:

1. Can the packaged compiler executable run on the chosen baseline?
2. Can a complete supported LLVM toolchain run there and compile its runtime?
3. Do JIT, exceptions, GC and advertised FFI modes work there?
4. Where can the generated AOT executable run, given its own sysroot, libraries
   and CPU flags?

A successful answer to the first question does not answer the others.

## Why manylinux is feasible but not turnkey

PyPA provides AlmaLinux 8 based `manylinux_2_28` images for **both x86_64 and
aarch64**. They provide an appropriate older userspace in which to build, with
Python interpreters for bootstrapping and packaging. The optional
`manylinux-install-clang` helper supplies only a static subset of LLVM tools;
its documented examples include Clang and linker/object utilities, not Pystachy's
complete optimizer/JIT/bitcode toolchain. It is therefore insufficient by itself
for the existing bootstrap and JIT checks. See the
[manylinux image and toolchain documentation](https://github.com/pypa/manylinux/blob/main/README.rst).

The first bounded experiment should use a pinned manylinux 2.28 image on each
native architecture and a pinned **complete LLVM 18** built for that environment.
A reusable builder image can amortize the LLVM build. Keep LLVM external to the
compiler package initially; bundling it would add another payload and dependency
closure to audit. Build the compiler and runtime against the old headers/libraries
instead of copying Ubuntu's compiled objects into the image.

This is a feasibility inference from the build structure and available upstream
images, not a successful baseline build. No source-level dependency on a new
glibc API has been established as an unavoidable blocker here; only the concrete
newer symbol imports of the existing binary have been established.

[Auditwheel](https://github.com/pypa/auditwheel/blob/main/README.rst) can inspect
wheel dependencies and bundle eligible external shared libraries. It cannot
downgrade newer glibc/libstdc++ symbol requirements, and static dependency analysis
does not discover arbitrary libraries opened with `dlopen`. A complete baseline
build and clean consumer tests are still required.

For a compiler wheel with no imported CPython extension, a Python launcher plus
the independent executable can use an appropriate `py3-none-<platform>` tag,
with a truthful `Requires-Python` floor. Platform independence must not be claimed:
the executable still has an OS/CPU/libc contract. The
[wheel tag specification](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)
defines Python, ABI and platform as separate tag components. Generated CPython
extensions have their own ABI and platform requirements.

[PEP 600](https://peps.python.org/pep-0600/) makes a manylinux tag a compatibility
promise for the specified architecture and glibc baseline. Neither a filename
change nor a low maximum GLIBC symbol alone fulfills that promise. Alpine/musl
requires a separate musllinux effort.

## Reusable artifact check

[`tools/linux_abi.py`](../../tools/linux_abi.py) inspects every ELF executable or
shared library in an extracted release directory. It records hashes,
architectures, ELF interpreters, direct dependencies, required symbol versions and
library search paths without running the binaries. GNU `readelf` is its only
external tool. It rejects malformed/unreadable evidence and linked payloads that
could escape or be omitted from the supplied tree. The explicitly supplied root
and any entry below a directory root must not be symlinks. Aliases in the root's
parent path components are resolved normally; the resulting real directory is
the traversal boundary.

```sh
# The documented alpha baseline; select aarch64 for the Linux ARM64 artifact.
python3 tools/linux_abi.py EXTRACTED_RELEASE \
  --architecture x86_64 --max-glibc 2.39 --json build/linux-abi.json

# A proposed baseline; published alpha.3 fails this check with GLIBC_2.38.
python3 tools/linux_abi.py EXTRACTED_RELEASE \
  --architecture x86_64 --max-glibc 2.28 --json build/linux-abi-2.28.json

python3 -m unittest discover -s tools -p test_linux_abi.py
```

Exit status is 0 for the requested symbol/architecture constraints, 1 for a
recorded violation, and 2 for invalid inputs or failed inspection. JSON explicitly
states its limits: it does not resolve external dependency trees, detect all CPU
instructions, validate kernel support, or certify manylinux. Each generated AOT
program and any bundled toolchain must be inspected separately.

Before lowering the release baseline, retain native bootstrap fixed points and
JIT/AOT correctness, exception/unwind, GC-stress, relocation/read-only-install and
advertised FFI checks on the oldest supported environment. Audit the complete
payload, test representative newer distributions, then run clean pip/uv consumer
installs for actual compiler wheels. Until that evidence exists, retain the
current explicit glibc baseline and ordinary native archives.
