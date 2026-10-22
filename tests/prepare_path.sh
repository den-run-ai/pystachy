#!/bin/sh
# Resolve a case's import path and prepare path-sensitive fixtures in the caller's
# temporary directory. Shared by execution, recording, IR and runtime ABI checks.
# usage: sh tests/prepare_path.sh CASE.py TEMP_DIR (CASE.path must exist)
mp=$(cat "${1%.py}.path") || exit 1
case ${1##*/} in
  closure_paths.py)
    mkdir -p "$2/paths]" &&
      cat "$mp/closure_path_fixture.py" > "$2/paths]/closure_path_fixture.py" || {
        echo "cannot prepare bracket-path fixture" >&2; exit 1;
      }
    mp="$2/paths]"
    ;;
esac
printf '%s\n' "$mp"
