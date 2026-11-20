#!/bin/sh
# Build and check the minimal LLVM toolchain that Pystachy's driver runs (docs/llvm-toolchain.md):
# clang, opt, lli, llc, llvm-link and llvm-as over one shared libLLVM that holds the host's target
# alone, from LLVM's release sources.
#
#   tools/llvm_toolchain.sh build OUT          fetch, configure, build, check and pack OUT/NAME.tar.xz
#   tools/llvm_toolchain.sh compile OUT I N    compile slice I of N of the object files into OUT/objects
#   tools/llvm_toolchain.sh check DIR          check the toolchain directory DIR (its bin holds the tools)
#   tools/llvm_toolchain.sh name               print NAME, pystachy-llvm-VERSION-linux-ARCH
#
# Compiling is most of a build, so it can be shared: N machines each run compile for one slice, and
# build then finds every object in the LLVM_TOOLCHAIN_OBJECTS directory that holds theirs and only
# links, checks and packs. The LLVM toolchain workflow does this. compile needs ninja.
#
# The archive runs wherever the C and C++ libraries are at least as new as the build host's. For a
# portable one, build in an old distribution: docs/llvm-toolchain.md uses the manylinux_2_28 image
# (glibc 2.28, libstdc++ from GCC 8). The build needs cmake 3.20 or later, a C++17 compiler, Python 3,
# curl, tar and xz; ninja is used when present, else make.
#
# Settings (environment):
#   LLVM_TOOLCHAIN_VERSION, LLVM_TOOLCHAIN_SHA256   the release and the hash of its source archive
#   LLVM_TOOLCHAIN_SOURCE    an archive already fetched (its hash is checked all the same)
#   LLVM_TOOLCHAIN_WORK      the source and build directory (default OUT/work; several GiB)
#   LLVM_TOOLCHAIN_JOBS      parallel jobs (default: the CPU count)
#   LLVM_TOOLCHAIN_BUILD     CMAKE_BUILD_TYPE (default Release; MinSizeRel is smaller and compiles slower)
#   LLVM_TOOLCHAIN_OBJECTS   a directory of compiled objects to reuse and add to (build: none by
#                            default; compile: OUT/objects). It must be used at one path, with one
#                            source and build directory: an object's key is its compile command
#   LLVM_TOOLCHAIN_GLIBC, LLVM_TOOLCHAIN_GLIBCXX   check: the newest symbol versions the binaries
#                            may need (2.28 and 3.4.25 for manylinux_2_28); unset, they are reported
set -eu

VERSION=${LLVM_TOOLCHAIN_VERSION:-18.1.8}
SHA256=${LLVM_TOOLCHAIN_SHA256:-0b58557a6d32ceee97c8d533a59b9212d87e0fc4d2833924eb6c611247db2f2a}
MAJOR=${VERSION%%.*}
BUILD=${LLVM_TOOLCHAIN_BUILD:-Release}
# What the driver runs: pystachy_toolchain.py's TOOLS, and llc for PYSTACHY_JIT_CODEGEN=0 under lli.
TOOLS="clang opt lli llc llvm-link llvm-as"
ROOT=$(cd "$(dirname "$0")/.." && pwd)

fail() { echo "llvm_toolchain: $*" >&2; exit 1; }

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) ARCH=x86_64; TARGET=X86; HEADERS="x86-resource-headers" ;;
  Linux-aarch64) ARCH=aarch64; TARGET=AArch64; HEADERS="arm-common-resource-headers;aarch64-resource-headers" ;;
  *) fail "no recipe for $(uname -s) $(uname -m): Linux x86-64 and AArch64 only" ;;
esac
NAME=pystachy-llvm-$VERSION-linux-$ARCH

# The newest version of the symbols with prefix $2 (GLIBC_ or GLIBCXX_) that the file $1 needs.
newest() {
  objdump -T "$1" 2> /dev/null | sed -n "s/.*($2\\([0-9.]*\\)).*/\\1/p" | sort -u -t. -k1,1n -k2,2n -k3,3n | tail -n 1
}

# 0 if the dotted version $1 is at most $2.
at_most() {
  [ "$(printf '%s\n%s\n' "$1" "$2" | sort -t. -k1,1n -k2,2n -k3,3n | tail -n 1)" = "$2" ]
}

# Print the C and C++ library versions the toolchain directory $1 needs; fail if it needs any other
# host library, or versions newer than LLVM_TOOLCHAIN_GLIBC and LLVM_TOOLCHAIN_GLIBCXX allow.
requirements() {
  glibc=0
  glibcxx=0
  for f in "$1"/bin/* "$1"/lib/libLLVM*; do
    [ -L "$f" ] && continue
    for need in $(objdump -p "$f" | awk '$1 == "NEEDED" {print $2}'); do
      case "$need" in
        libLLVM*|libc.so.6|libm.so.6|libdl.so.2|libpthread.so.0|librt.so.1|libstdc++.so.6|libgcc_s.so.1|ld-linux-*) ;;
        *) fail "$f needs $need from the host" ;;
      esac
    done
    v=$(newest "$f" GLIBC_)
    if [ -n "$v" ] && ! at_most "$v" "$glibc"; then glibc=$v; fi
    v=$(newest "$f" GLIBCXX_)
    if [ -n "$v" ] && ! at_most "$v" "$glibcxx"; then glibcxx=$v; fi
  done
  echo "needs glibc $glibc and libstdc++ GLIBCXX_$glibcxx or later"
  if [ -n "${LLVM_TOOLCHAIN_GLIBC:-}" ]; then
    at_most "$glibc" "$LLVM_TOOLCHAIN_GLIBC" || fail "needs glibc $glibc, newer than $LLVM_TOOLCHAIN_GLIBC"
  fi
  if [ -n "${LLVM_TOOLCHAIN_GLIBCXX:-}" ]; then
    at_most "$glibcxx" "$LLVM_TOOLCHAIN_GLIBCXX" || fail "needs GLIBCXX_$glibcxx, newer than $LLVM_TOOLCHAIN_GLIBCXX"
  fi
}

check() {
  dir=$(cd "$1" && pwd) || fail "no directory $1"
  bin=$dir/bin
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  for t in $TOOLS; do
    [ -x "$bin/$t" ] || fail "$bin/$t is missing"
    "$bin/$t" --version > "$tmp/version" 2>&1 || fail "$t --version failed: $(cat "$tmp/version")"
    grep -q "version $VERSION" "$tmp/version" || fail "$t is not LLVM $VERSION: $(sed 1q "$tmp/version")"
  done
  [ -f "$dir/lib/clang/$MAJOR/include/stddef.h" ] || fail "clang's headers are missing from $dir/lib/clang/$MAJOR/include"

  # One target: another one's code would be most of the size this build exists to avoid.
  targets=$("$bin/llc" --version | sed '1,/Registered Targets:/d' | awk '{print $1}' | tr '\n' ' ')
  case "$TARGET" in
    X86) want="x86 x86-64 " ;;
    *) want="aarch64 aarch64_32 aarch64_be arm64 arm64_32 " ;;
  esac
  [ "$targets" = "$want" ] || fail "registered targets are '$targets', not '$want'"

  # The JIT runner links the libLLVM that lli loads (driver.py's jit_launcher finds it with ldd).
  shared=$(ldd "$bin/lli" | sed -n 's/^[[:space:]]*libLLVM[^ ]* => \(.*\) (0x[0-9a-f]*)$/\1/p' | sed 1q)
  [ -n "$shared" ] || fail "lli loads no shared libLLVM, which the JIT runner needs"
  case "$(cd "$(dirname "$shared")" && pwd)" in
    "$dir/lib") ;;
    *) fail "lli loads $shared, outside $dir/lib" ;;
  esac

  # Nothing from the host but the C and C++ libraries.
  requirements "$dir"

  # The driver's steps on two C files: C to IR, assemble, link, optimize with a
  # coroutine pipeline as generators use, then the same answer from lli, llc and clang's own code
  # generation.
  cat > "$tmp/a.c" << 'EOF'
#include <stddef.h>
#include <stdio.h>
long square(long);
int main(void) {
  long sum = 0;
  for (long i = 0; i < 1000; i++) sum += square(i);
  printf("%ld %zu\n", sum, sizeof(max_align_t));
  return 0;
}
EOF
  echo 'long square(long x) { return x * x; }' > "$tmp/b.c"
  (
    cd "$tmp" &&
    "$bin/clang" -O2 -S -emit-llvm -x c a.c -o a.ll -fexceptions &&
    "$bin/clang" -O2 -S -emit-llvm -x c b.c -o b.ll &&
    "$bin/llvm-as" a.ll -o a.bc &&
    "$bin/llvm-as" b.ll -o b.bc &&
    "$bin/llvm-link" --only-needed a.bc b.bc -o linked.bc &&
    "$bin/opt" -passes='coro-early,cgscc(coro-split),coro-cleanup,default<O2>,verify' linked.bc -o opt.bc &&
    "$bin/lli" opt.bc > jit.out &&
    "$bin/llc" -O0 -filetype=obj -relocation-model=pic opt.bc -o llc.o &&
    "$bin/clang" llc.o -o llc.exe &&
    ./llc.exe > llc.out &&
    "$bin/clang" -O2 -fPIC -c -x ir opt.bc -o clang.o &&
    "$bin/clang" clang.o -o clang.exe -lm &&
    ./clang.exe > clang.out
  ) || fail "the driver's steps failed"
  [ "$(cat "$tmp/jit.out")" = "332833500 $(cut -d' ' -f2 "$tmp/clang.out")" ] || fail "lli printed '$(cat "$tmp/jit.out")'"
  cmp -s "$tmp/jit.out" "$tmp/llc.out" && cmp -s "$tmp/jit.out" "$tmp/clang.out" || fail "lli, llc and clang disagree"

  # Pystachy's JIT runner, built and checked as the driver does it at first use.
  if [ -f "$ROOT/lljit.c" ]; then
    "$bin/clang" -O2 -std=c11 -D_GNU_SOURCE -DLLVM_VERSION_MAJOR="$MAJOR" -w "$ROOT/lljit.c" "$shared" -ldl \
      -o "$tmp/lljit" -Xlinker --disable-new-dtags -Xlinker -rpath -Xlinker "$(dirname "$shared")" || fail "lljit.c does not build"
    for o in -O0 -O2; do
      [ "$("$tmp/lljit" "$o" -self-check)" = "$(printf 'two\nlljit')" ] || fail "lljit $o -self-check failed"
    done
  fi
  echo "ok: $dir"
}

# The compiler launcher of the object store $1, for the command in the other arguments. If the
# same command ran before, its object and dependency file are copied from the store; otherwise it
# runs and they are kept. The key is the command and its directory with LLVM_TOOLCHAIN_STAMP, which
# prepare derives from the compilers' versions and the source archive's hash.
launch() {
  store=$1
  shift
  object=
  depfile=
  previous=
  for argument in "$@"; do
    case "$previous" in
      -o) object=$argument ;;
      -MF) depfile=$argument ;;
    esac
    previous=$argument
  done
  [ -n "$object" ] || fail "launch: no -o in: $*"
  key=$store/$(printf '%s\n' "${LLVM_TOOLCHAIN_STAMP:?}" "$PWD" "$@" | sha256sum | cut -d' ' -f1)
  if [ -f "$key.o" ]; then
    if [ -n "$depfile" ]; then cp "$key.d" "$depfile"; fi
    cp "$key.o" "$object"
    return
  fi
  "$@"
  # The object goes last and by rename, so a key that has an object has its dependency file too.
  if [ -n "$depfile" ]; then cp "$depfile" "$key.d"; fi
  cp "$object" "$key.o.$$"
  mv "$key.o.$$" "$key.o"
}

# Fetch and check the sources, then configure the build in OUT ($1). Sets out, work, jobs, src,
# stage and generator; $objects names the object store, or is empty.
prepare() {
  mkdir -p "$1"
  out=$(cd "$1" && pwd)
  work=${LLVM_TOOLCHAIN_WORK:-$out/work}
  jobs=${LLVM_TOOLCHAIN_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
  archive=${LLVM_TOOLCHAIN_SOURCE:-$work/llvm-project-$VERSION.src.tar.xz}
  src=$work/llvm-project-$VERSION.src
  stage=$out/$NAME
  mkdir -p "$work"

  if [ ! -f "$archive" ]; then
    curl -fL --retry 3 -o "$archive.part" \
      "https://github.com/llvm/llvm-project/releases/download/llvmorg-$VERSION/llvm-project-$VERSION.src.tar.xz"
    mv "$archive.part" "$archive"
  fi
  echo "$SHA256  $archive" | sha256sum -c - > /dev/null || fail "$archive is not the pinned LLVM $VERSION source archive"
  if [ ! -f "$src/llvm/CMakeLists.txt" ]; then
    rm -rf "$src"
    tar -xJf "$archive" -C "$work" "llvm-project-$VERSION.src/llvm" "llvm-project-$VERSION.src/clang" \
      "llvm-project-$VERSION.src/cmake" "llvm-project-$VERSION.src/third-party"
  fi

  generator="Unix Makefiles"
  if command -v ninja > /dev/null 2>&1; then generator=Ninja; fi
  launcher=
  if [ -n "$objects" ]; then
    mkdir -p "$objects"
    launcher="$ROOT/tools/llvm_toolchain.sh;launch;$(cd "$objects" && pwd)"
    LLVM_TOOLCHAIN_STAMP=$(printf '%s\n' "$SHA256" "$("${CC:-cc}" --version | sed 1q)" "$("${CXX:-c++}" --version | sed 1q)" \
      | sha256sum | cut -d' ' -f1)
    export LLVM_TOOLCHAIN_STAMP
  fi
  # One target and one shared libLLVM for every tool; clang's own libraries are linked into clang,
  # where unused code is discarded. No optional host library is used, so the result needs only the
  # C and C++ libraries. The static analyzer, ARC migration and plugins are not built. Release is
  # compiled at -O2, as distributions build LLVM, not CMake's -O3.
  cmake -S "$src/llvm" -B "$work/build" -G "$generator" \
    -DCMAKE_BUILD_TYPE="$BUILD" \
    -DCMAKE_C_FLAGS_RELEASE="-O2 -DNDEBUG" -DCMAKE_CXX_FLAGS_RELEASE="-O2 -DNDEBUG" \
    -DCMAKE_C_COMPILER_LAUNCHER="$launcher" -DCMAKE_CXX_COMPILER_LAUNCHER="$launcher" \
    -DCMAKE_INSTALL_PREFIX="$stage" \
    -DLLVM_ENABLE_PROJECTS=clang \
    -DLLVM_TARGETS_TO_BUILD="$TARGET" \
    -DLLVM_BUILD_LLVM_DYLIB=ON -DLLVM_LINK_LLVM_DYLIB=ON -DCLANG_LINK_CLANG_DYLIB=OFF \
    -DLLVM_DISTRIBUTION_COMPONENTS="LLVM;clang;core-resource-headers;utility-resource-headers;$HEADERS;opt;lli;llc;llvm-link;llvm-as" \
    -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF -DLLVM_ENABLE_TERMINFO=OFF \
    -DLLVM_ENABLE_LIBEDIT=OFF -DLLVM_ENABLE_FFI=OFF -DLLVM_ENABLE_LIBPFM=OFF -DLLVM_ENABLE_CURL=OFF \
    -DLLVM_ENABLE_HTTPLIB=OFF -DLLVM_ENABLE_Z3_SOLVER=OFF \
    -DLLVM_ENABLE_ASSERTIONS=OFF -DLLVM_ENABLE_BINDINGS=OFF -DLLVM_ENABLE_PLUGINS=OFF \
    -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_INCLUDE_DOCS=OFF -DLLVM_INCLUDE_UTILS=OFF \
    -DCLANG_ENABLE_STATIC_ANALYZER=OFF -DCLANG_ENABLE_ARCMT=OFF -DCLANG_PLUGIN_SUPPORT=OFF \
    -DCLANG_INCLUDE_TESTS=OFF -DCLANG_INCLUDE_DOCS=OFF
}

# Compile slice $2 of $3 of the object files that the distribution is linked from, and what
# they need first (LLVM's table generators and their output), into the object store.
compile() {
  case "$2$3" in *[!0-9]*) fail "compile: I and N are numbers, not '$2' and '$3'" ;; esac
  [ "$2" -lt "$3" ] || fail "compile: slice $2 is not below $3"
  objects=${LLVM_TOOLCHAIN_OBJECTS:-$1/objects}
  prepare "$1"
  [ "$generator" = Ninja ] || fail "compile needs ninja"
  ninja -C "$work/build" -t inputs install-distribution-stripped | grep '\.o$' | LC_ALL=C sort > "$work/objects.txt"
  awk -v i="$2" -v n="$3" '(NR - 1) % n == i' "$work/objects.txt" > "$work/slice.txt"
  [ -s "$work/slice.txt" ] || fail "slice $2 of $3 is empty"
  echo "slice $2 of $3: $(wc -l < "$work/slice.txt") of $(wc -l < "$work/objects.txt") object files"
  xargs ninja -C "$work/build" -j "$jobs" < "$work/slice.txt"
}

build() {
  objects=${LLVM_TOOLCHAIN_OBJECTS:-}
  prepare "$1"
  rm -rf "$stage"
  cmake --build "$work/build" --target install-distribution-stripped --parallel "$jobs"

  # clang's other names (clang++, clang-cl, clang-cpp) are not ones the driver runs.
  for link in "$stage"/bin/*; do
    case " $TOOLS clang-$MAJOR " in
      *" $(basename "$link") "*) ;;
      *) rm -f "$link" ;;
    esac
  done
  mkdir -p "$stage/share/licenses"
  cp "$src/llvm/LICENSE.TXT" "$stage/share/licenses/LLVM-LICENSE.TXT"
  cp "$src/clang/LICENSE.TXT" "$stage/share/licenses/clang-LICENSE.TXT"
  {
    echo "LLVM $VERSION for Pystachy: Linux $ARCH, $TARGET target only"
    echo "tools: $TOOLS"
    echo "source: llvm-project-$VERSION.src.tar.xz sha256 $SHA256"
    echo "recipe: tools/llvm_toolchain.sh sha256 $(sha256sum "$0" | cut -d' ' -f1)"
    echo "build: $BUILD, $("${CC:-cc}" --version | sed 1q), $(ldd --version | sed 1q)"
    requirements "$stage"
  } > "$stage/share/BUILD.txt"
  (cd "$stage" && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs sha256sum > MANIFEST.sha256)
  check "$stage"

  # The same bytes for the same inputs: sorted names, no owner, the sources' time. The x86 filter
  # shortens x86 code by about 6%; every xz reads it (AArch64's needs xz 5.4, so it is not used).
  epoch=${SOURCE_DATE_EPOCH:-$(stat -c %Y "$src/llvm/CMakeLists.txt")}
  filter=
  if [ "$ARCH" = x86_64 ]; then filter=--x86; fi
  # shellcheck disable=SC2086
  tar -C "$out" --sort=name --owner=0 --group=0 --numeric-owner --mtime="@$epoch" -cf - "$NAME" \
    | xz -T1 $filter --lzma2=preset=9e,dict=64MiB > "$out/$NAME.tar.xz"
  (cd "$out" && sha256sum "$NAME.tar.xz" > "$NAME.tar.xz.sha256")
  cat "$stage/share/BUILD.txt"
  ls -l "$out/$NAME.tar.xz"
}

case "${1:-}" in
  build) [ $# -eq 2 ] || fail "usage: llvm_toolchain.sh build OUT"; build "$2" ;;
  compile) [ $# -eq 4 ] || fail "usage: llvm_toolchain.sh compile OUT I N"; compile "$2" "$3" "$4" ;;
  check) [ $# -eq 2 ] || fail "usage: llvm_toolchain.sh check DIR"; check "$2" ;;
  name) echo "$NAME" ;;
  launch) shift; launch "$@" ;;
  *) fail "usage: llvm_toolchain.sh build OUT | compile OUT I N | check DIR | name" ;;
esac
