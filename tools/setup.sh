#!/bin/sh
# Package-manager setup; --check never installs. No arguments retain CI's UBSan dependency.
set -eu
mode=${1:---verify}
case $mode in --check | --minimal | --verify) ;; *)
  echo "usage: tools/setup.sh [--minimal | --verify | --check]" >&2; exit 2 ;;
esac
[ $# -le 1 ] || { echo "tools/setup.sh: too many arguments" >&2; exit 2; }
cd "$(dirname "$0")/.."
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
LLVM=$(find_llvm)
valid=true
for t in clang opt lli llvm-link llvm-as; do
  "${LLVM:+$LLVM/}$t" --version 2> /dev/null | grep -q "version $major\." || valid=false
done
if [ -n "${PYSTACHY_LLVM:-}" ] && [ "$valid" = false ]; then
  echo "tools/setup.sh: PYSTACHY_LLVM=$PYSTACHY_LLVM must contain a complete LLVM $major toolchain" >&2
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
      if [ "$mode" = --verify ]; then PKGS="$PKGS libclang-rt-18-dev"; fi
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
"$PY" --version
echo "ready: make PY=$PY"
