#!/bin/sh
# The LLVM 18 toolchain that make verify needs, on Ubuntu 24.04: clang-18 (clang), llvm-18 (opt,
# llvm-link, llvm-as), llvm-18-runtime (lli) and libclang-rt-18-dev (the UBSan runtime of the
# sanitizer stage). apt runs only when a package is missing (CI's runner image has them all), and
# retries; then the tools' versions are printed. As root or with sudo; CI runs it, and so can a cloud
# environment's setup script.
# usage: tools/setup.sh
PKGS="clang-18 llvm-18 llvm-18-runtime libclang-rt-18-dev"
miss=
for p in $PKGS; do
  dpkg-query -W -f '${Status}' "$p" 2> /dev/null | grep -q 'install ok installed' || miss="$miss $p"
done
if [ -n "$miss" ]; then
  echo "installing:$miss"
  su=; [ "$(id -u)" = 0 ] || su=sudo
  i=1
  until $su apt-get update && $su apt-get install -y --no-install-recommends $miss; do
    [ $i -lt 3 ] || { echo "tools/setup.sh: apt failed $i times"; exit 1; }
    sleep $((i * 10)); i=$((i + 1))
  done
fi
LLVM=${PYSTACHY_LLVM:-/usr/lib/llvm-18/bin}
for t in clang opt lli llvm-link llvm-as; do
  [ -x "$LLVM/$t" ] || { echo "tools/setup.sh: no $LLVM/$t (PYSTACHY_LLVM: the LLVM 18 bin directory)"; exit 1; }
  "$LLVM/$t" --version | head -1
done
python3 --version
