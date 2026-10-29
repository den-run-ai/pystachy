#!/bin/sh
# The corpus (tests/run.sh, JIT and AOT) in configurations that make verify does not test and that
# must change no result (make variants; docs/testing.md#configuration-variants):
#   opt-1 ... opt-5  PYSTACHY_OPT turning off the passes on the IR (specs.py's OPTS) that rows 1 to 5
#                    of a covering array leave off. Its row 0 is every pass on, the default that verify
#                    tests (verify also turns them all off); with it, these rows run every two passes in
#                    each of their four on/off combinations. A pass's column is a distinct set of 3 of
#                    the 6 rows that includes row 0: two columns share row 0, each has a row the other
#                    lacks, and some row is in neither. Ten such sets exist; a new pass takes the next
#   cflags-O0        PYSTACHY_CFLAGS=-O0: the runtime unoptimized, and with it an AOT program's whole
#                    module, whose IR then runs as the compiler emitted it. The runtime's frames keep
#                    every local in memory, which changes the dead words that the conservative
#                    collector scans as roots (tools/runtime_coverage.sh's instrumented runtime is
#                    another such variant, the one whose registers exposed open()'s retention)
# The caller's settings that the steps set, or that would change the tests, are dropped, as
# tests/verify.sh drops them; each variant builds a runtime of its own, in a temporary cache. The
# logs go to build/variants/ (so a checkout runs one at a time). Fails when a variant fails a test.
# usage: tools/variants.sh [FILE...]   (as tests/run.sh takes them; default: every case)
#   env: COMPILER (default ./pystachy), MODES (default "jit aot"), VARIANTS (default: all, in the
#        order above), VARIANTS_SHARD=I/N (shard I of N of the corpus alone, as
#        tests/verify.sh shards it: tools/shard_cases.sh), PY (default python3, to read OPTS)
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
PYS=${COMPILER:-./pystachy}
PY=${PY:-python3}
MODES=${MODES:-jit aot}
case $PYS in *" "*) ;; *) [ -x "$PYS" ] || { echo "tools/variants.sh: no compiler $PYS (make, or COMPILER=...)" >&2; exit 2; } ;; esac
ign=$(env | sed -nE 's/^(PYSTACHY_(PATH|CFLAGS|GC|GC_STRESS|GC_STRESS_PROGRAM|IRCHECK|IRFX|OPT|JIT_INLINE|JIT_CODEGEN|UNICODE_AUDIT|ARGV0))=.*$/\1/p' | sort -u)
for e in $ign; do echo "tools/variants.sh: ignoring $e=$(printenv "$e")"; unset "$e"; done
export PYSTACHY_HOME="$ROOT"
W=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-variants.XXXXXX") || exit 1
trap 'rm -rf "$W"' EXIT
trap 'exit 130' INT TERM
L=$ROOT/build/variants
# opt-N and the PYSTACHY_OPT of row N, one a line
$PY -I - "$ROOT" > "$W/rows" <<'EOF' || { echo "tools/variants.sh: $PY cannot read OPTS (src/pystachy_compiler/specs.py)" >&2; exit 2; }
import itertools, sys
sys.path.insert(0, sys.argv[1])
from src.pystachy_compiler.specs import OPTS
cols = [c for c in itertools.combinations(range(6), 3) if 0 in c]
if len(OPTS) > len(cols):
    raise SystemExit(f"{len(OPTS)} passes, but the array has {len(cols)} columns: widen it")
rows = [[r in cols[j] for j in range(len(OPTS))] for r in range(6)]
for a, b in itertools.combinations(range(len(OPTS)), 2):
    assert len({(row[a], row[b]) for row in rows}) == 4, (OPTS[a], OPTS[b])
for r in range(1, 6):
    print(f"opt-{r}", ",".join("-" + OPTS[j] for j in range(len(OPTS)) if not rows[r][j]))
EOF
all="$(cut -d' ' -f1 "$W/rows" | tr '\n' ' ')cflags-O0"
for v in ${VARIANTS:-$all}; do
  case " $all " in *" $v "*) ;; *) echo "tools/variants.sh: no variant $v (the variants: $all)" >&2; exit 2 ;; esac
done
if [ -n "${VARIANTS_SHARD:-}" ]; then
  [ $# = 0 ] || { echo "tools/variants.sh: FILEs or VARIANTS_SHARD, not both" >&2; exit 2; }
  tools/shard_cases.sh "$VARIANTS_SHARD" > "$W/cases" || exit 2
  while IFS= read -r f; do set -- "$@" "$f"; done < "$W/cases"
  [ $# != 0 ] || { echo "tools/variants.sh: shard $VARIANTS_SHARD has no case" >&2; exit 1; }
fi
rm -rf "$L"; mkdir -p "$L" || exit 1
failed=
for v in ${VARIANTS:-$all}; do
  case $v in
    opt-*) set=PYSTACHY_OPT=$(sed -n "s/^$v //p" "$W/rows") ;;
    cflags-O0) set=PYSTACHY_CFLAGS=-O0 ;;
  esac
  t0=$(date +%s)
  env "$set" PYSTACHY_CACHE="$W/cache-$v" tests/run.sh "$PYS" "$MODES" "$@" > "$L/$v.log" 2>&1
  st=$?
  echo "$v ($set; $MODES${VARIANTS_SHARD:+; shard $VARIANTS_SHARD}): $(tail -1 "$L/$v.log") in $(($(date +%s) - t0)) s"
  grep -v '^selected ' "$L/$v.log" | sed '$d' | head -40
  case $st in
    0) ;;
    1) failed="$failed $v" ;;
    *) echo "tools/variants.sh: tests/run.sh exited with status $st" >&2; exit "$st" ;;
  esac
done
[ -z "$failed" ] || { echo "tools/variants.sh: failed:$failed (logs in build/variants/)" >&2; exit 1; }
