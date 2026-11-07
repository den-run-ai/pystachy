#!/bin/sh
# Build only the optional adapter; install raylib yourself. No downloads.
set -eu
cd "$(dirname "$0")/../.."
if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --atleast-version=5.5 raylib; then
    echo 'raylib >= 5.5 development files and pkg-config are required' >&2
    exit 1
fi
case $(uname -s) in
    Linux) shared=-shared ;;
    Darwin) shared=-dynamiclib ;;  # Build recipe only; macOS FFI is not validated.
    *) echo 'This prototype supports Linux; macOS build is experimental' >&2; exit 1 ;;
esac
mkdir -p build/miniui
tmp=$(mktemp build/miniui/adapter.XXXXXX)
trap 'rm -f "$tmp"' EXIT HUP INT TERM
# pkg-config deliberately expands into compiler/linker arguments.
# shellcheck disable=SC2046
"${CC:-cc}" -std=c99 -O2 -Wall -Wextra -Werror -fPIC "$shared" \
    examples/miniui/raylib_adapter.c -o "$tmp" $(pkg-config --cflags --libs raylib)
mv "$tmp" build/miniui/libminiui.so
printf '%s\n' 'Built build/miniui/libminiui.so (raylib remains an external dependency)'
