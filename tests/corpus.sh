# shellcheck shell=sh
# Where the corpus's cases are, for the scripts that list, count or shard them (tests/run.sh,
# tests/record.sh, tests/verify.sh, tools/shard_cases.sh, tools/coverage.sh, tools/runtime_coverage.sh,
# tools/irsame.sh, tools/check_ir.sh), which source this file from the repository's root:
#   tests/programs/AREA/NAME.py   a differential program, its sidecars beside it: NAME.out and NAME.err
#                                 (CPython's recording), NAME.in, NAME.full and NAME.path
#   tests/deviations/NAME.py      a documented deviation, with its hand-written NAME.out
#   tests/errors/AREA/NAME.py     a rejection, its expected message in its first line, NAME.path beside
#                                 it where it imports one of the helper packages in tests/
# tools/rtabi.py finds them with the same patterns in Python.
# Each area is a directory of cases on one subject; the helper packages that cases import (mods/,
# loader/, emods/...) lie directly in tests/, which a case's NAME.path names for them.

# corpus: the cases, one a line, in the order of the locale's collation (C order under LC_ALL=C,
# which the shards rely on)
corpus() {
  for f in tests/programs/*/*.py tests/deviations/*.py tests/errors/*/*.py; do
    [ -f "$f" ] && printf '%s\n' "$f"
  done
  return 0
}

# corpus_strays: the files no pattern of corpus finds, which no run would test: a program,
# rejection or sidecar directly in tests/, tests/programs/ or tests/errors/ (where the flat layout
# before kept them), or in a directory below an area's
corpus_strays() {
  for f in tests/*.py tests/*.out tests/*.err tests/*.in tests/*.full tests/*.path \
    tests/programs/* tests/programs/*/*/* tests/errors/*.py tests/errors/*.out tests/errors/*.err \
    tests/errors/*.in tests/errors/*.full tests/errors/*.path tests/errors/*/*/*; do
    [ -e "$f" ] || [ -L "$f" ] || continue
    case $f in
      */__pycache__ | */__pycache__/*) continue ;;  # (CPython's, where a program imports another)
      tests/programs/*/*/*) ;;
      tests/programs/*) [ ! -d "$f" ] || continue ;;
    esac
    printf '%s\n' "$f"
  done
  return 0
}
