#!/bin/sh
# Keep this launcher beside libminiui.so and the packaged AOT demo.
set -eu
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ ! -r "$here/libminiui.so" ]; then
    echo "Missing $here/libminiui.so; run build_backend.sh first" >&2
    exit 1
fi
case $(uname -s) in
    Linux) export LD_LIBRARY_PATH="$here${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ;;
    Darwin) export DYLD_LIBRARY_PATH="$here${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" ;;
    *) echo 'miniui launcher supports Linux; macOS is experimental' >&2; exit 1 ;;
esac
# Keep the caller's working directory and pass arguments through unchanged.
if [ "$#" -eq 0 ]; then set -- "$here/demo"; fi
exec "$@"
