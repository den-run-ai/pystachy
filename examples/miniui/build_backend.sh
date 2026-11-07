#!/bin/sh
# Build only the optional adapter; install raylib yourself. No downloads.
set -eu
if [ "$#" -gt 1 ]; then
    echo "Usage: $0 [output-directory]" >&2
    exit 2
fi
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
out=${1:-$here/../../build/miniui}
mkdir -p -- "$out"
out=$(CDPATH='' cd -- "$out" && pwd)
if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --atleast-version=5.5 raylib; then
    echo 'raylib >= 5.5 development files and pkg-config are required' >&2
    exit 1
fi
case $(uname -s) in
    Linux) shared=-shared ;;
    Darwin) shared=-dynamiclib ;;  # Build recipe only; macOS FFI is not validated.
    *) echo 'This prototype supports Linux; macOS build is experimental' >&2; exit 1 ;;
esac
tmp=$(mktemp "$out/adapter.XXXXXX")
trap 'rm -f "$tmp"' EXIT HUP INT TERM
# pkg-config deliberately expands into compiler/linker arguments.
# shellcheck disable=SC2046
"${CC:-cc}" -std=c99 -O2 -Wall -Wextra -Werror -fPIC "$shared" \
    "$here/raylib_adapter.c" -o "$tmp" $(pkg-config --cflags --libs raylib)
chmod 644 "$tmp"
mv -- "$tmp" "$out/libminiui.so"
if [ "$here" != "$out" ]; then cp -- "$here/run.sh" "$out/run.sh"; fi
chmod 755 "$out/run.sh"
printf '%s\n' "Built $out/libminiui.so and run.sh (raylib remains an external dependency)"
