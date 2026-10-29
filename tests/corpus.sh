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

# corpus_shard I N [WEIGHTS]: the cases of shard I of N (0 <= I < N), one a line, heaviest first, so
# that tests/run.sh's workers do not end on a long case. The cases are taken in order of their weight
# in WEIGHTS (default tests/case_weights.txt, which tools/case_weights.py writes from measured times),
# heaviest first and then in C order, and each joins the shard whose weight is least so far (the first
# of equals): greedy longest-processing-time. Every case of corpus joins exactly one shard, whatever
# WEIGHTS holds: a case it lacks weighs its kind's default ("default program W" for programs and
# deviations, "default rejection W"; 1000 without one), and a malformed line, a weight of more than
# nine digits or a path outside the corpus counts for nothing, so a stale or missing table costs
# balance, never coverage. Integers and the C locale give the same shards on every runner.
corpus_shard() {
  (
    export LC_ALL=C
    corpus | awk -v table="${3:-tests/case_weights.txt}" '
      function weight(x) { return x ~ /^[0-9]+$/ && length(x) <= 9 }
      BEGIN {
        def["program"] = 1000; def["rejection"] = 1000
        while ((getline line < table) > 0) {
          n = split(line, f, " ")
          if (n == 3 && f[1] == "default" && (f[2] in def) && weight(f[3])) def[f[2]] = f[3] + 0
          else if (n == 2 && weight(f[1])) w[f[2]] = f[1] + 0
        }
      }
      { print (($0 in w) ? w[$0] : def[$0 ~ /^tests\/errors\// ? "rejection" : "program"]), $0 }' |
      sort -k1,1nr -k2 |
      awk -v shard="$1" -v shards="$2" '
        BEGIN { for (s = 0; s < shards; s++) load[s] = 0 }
        { least = 0
          for (s = 1; s < shards; s++) if (load[s] < load[least]) least = s
          load[least] += $1
          if (least == shard) print substr($0, index($0, " ") + 1) }'
  )
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
