#!/bin/sh
# Package-manager setup; --check and --cpu never install. No arguments retain CI's UBSan and BLAS dependencies:
# make blas-check calls Ubuntu's LP64 libblas.so.3 of the reference BLAS and of OpenBLAS, which once
# installed is also that name's default provider.
set -eu
mode=${1:---verify}
case $mode in --check | --minimal | --verify | --cpu) ;; *)
  echo "usage: tools/setup.sh [--minimal | --verify | --check | --cpu]" >&2; exit 2 ;;
esac
[ $# -le 1 ] || { echo "tools/setup.sh: too many arguments" >&2; exit 2; }
cd "$(dirname "$0")/.."

# Keep the worker's LLVM profile distinct from raw OS identification. Neither is
# a bootstrap reuse key, and an unavailable or unknown value stays unidentified.
cpu_identity() {
  printf 'Worker system: '; uname -srm
  echo "LLVM host profile (opt --version):"
  if ! "${1:+${1%/}/}opt" --version 2>/dev/null; then
    echo "LLVM host profile unavailable"
  fi
  echo "OS CPU identification (/proc/cpuinfo):"
  cpu_fields=
  if [ -r /proc/cpuinfo ]; then
    cpu_fields=$(sed -n \
      -e '/^\(vendor_id\|model name\|cpu family\|model\|stepping\)[[:space:]]*:/p' \
      -e '/^\(CPU implementer\|CPU architecture\|CPU variant\|CPU part\|CPU revision\|Hardware\|Revision\|Model\)[[:space:]]*:/p' \
      /proc/cpuinfo | LC_ALL=C sort -u)
  fi
  printf '%s\n' "${cpu_fields:-OS CPU identification unavailable}"
}
if [ "$mode" = --cpu ]; then
  cpu_identity "${PYSTACHY_LLVM:-}"
  exit 0
fi

PY=${PY:-$(command -v python3.13 || command -v python3 || printf '%s' python3)}

find_llvm() {
  if "$PY" -c 'import sys; assert sys.version_info >= (3, 11)' 2> /dev/null; then
    "$PY" -c 'import pystachy; print(pystachy.llvm_dir())'
  else
    printf '%s\n' "${PYSTACHY_LLVM:-}"
  fi
}

major=18
[ "$(uname -s)" != Darwin ] || major=20
releases="LLVM $major"
LLVM=$(find_llvm)
if [ -n "${PYSTACHY_LLVM:-}" ] && [ $major = 18 ]; then
  # An explicit Linux toolchain may be any release from 18 to 23 (docs/install.md#other-llvm-releases)
  releases="one LLVM release from 18 to 23"
  found=$("$LLVM/clang" --version 2> /dev/null | sed -n '1s/.* version \([0-9][0-9]*\)\..*/\1/p')
  case $found in 19 | 20 | 21 | 22 | 23) major=$found ;; esac
fi
valid=true
for t in clang opt lli llvm-link llvm-as; do
  "${LLVM:+$LLVM/}$t" --version 2> /dev/null | grep -q "version $major\." || valid=false
done
if [ -n "${PYSTACHY_LLVM:-}" ] && [ "$valid" = false ]; then
  echo "tools/setup.sh: PYSTACHY_LLVM=$PYSTACHY_LLVM must contain a complete toolchain of $releases" >&2
  exit 1
fi

if [ "$mode" != --check ]; then
  case $(uname -s) in
    Linux)
      command -v apt-get > /dev/null 2>&1 || {
        echo "tools/setup.sh: install LLVM 18, Python 3.11+ and make with your package manager, then use --check" >&2; exit 1;
      }
      PKGS="git make python3"
      if [ "$valid" = false ]; then PKGS="$PKGS clang-18 llvm-18 llvm-18-runtime"; fi
      if [ "$mode" = --verify ]; then PKGS="$PKGS libclang-rt-$major-dev libblas3 libopenblas0-pthread"; fi
      miss=
      for p in $PKGS; do
        dpkg-query -W -f '${Status}' "$p" 2> /dev/null | grep -q 'install ok installed' || miss="$miss $p"
      done
      if [ -n "$miss" ]; then
        su=; [ "$(id -u)" = 0 ] || su=sudo
        i=1
        until $su apt-get update && $su apt-get install -y --no-install-recommends $miss; do
          [ "$i" -lt 3 ] || { echo "tools/setup.sh: apt failed $i times" >&2; exit 1; }
          sleep $((i * 10)); i=$((i + 1))
        done
      fi
      ;;
    Darwin)
      command -v brew > /dev/null 2>&1 || {
        echo "tools/setup.sh: install Homebrew from https://brew.sh first" >&2; exit 1;
      }
      [ "$valid" = true ] || brew install llvm@20
      if ! "$PY" -c 'import sys; assert sys.version_info >= (3, 11)' 2> /dev/null; then
        brew install python@3.13
        PY="$(brew --prefix python@3.13)/bin/python3.13"
      fi
      ;;
    *) echo "tools/setup.sh: use your package manager, then run --check" >&2; exit 1 ;;
  esac
fi

"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
command -v make > /dev/null 2>&1 || { echo "tools/setup.sh: make is required" >&2; exit 1; }
LLVM=$(find_llvm)
for t in clang opt lli llvm-link llvm-as; do
  tool=${LLVM:+$LLVM/}$t
  version=$("$tool" --version) || { echo "tools/setup.sh: missing $tool" >&2; exit 1; }
  printf '%s\n' "$version" | grep -q "version $major\." || {
    echo "tools/setup.sh: $tool must be LLVM $major; set PYSTACHY_LLVM to a complete LLVM $major bin directory" >&2; exit 1;
  }
  printf '%s\n' "$version" | head -1
done
cpu_identity "$LLVM"
"$PY" --version
echo "ready: make PY=$PY"
