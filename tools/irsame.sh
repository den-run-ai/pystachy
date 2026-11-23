#!/bin/sh
# IR oracle for refactors of the code generator: compilers OLD and NEW run `ir` on every program
# of the corpus, from the repository root as tests/run.sh runs them, and must print the same LLVM
# IR byte for byte, the same messages (all of a rejection's) and the same exit status.
# Only each compiler's own library prefix is normalized: to lib/ in diagnostic source locations,
# and to <lib> (its parent to <home>) in the IR string constants that hold its real library
# directory (sys.path's entry), its home (sys.prefix), a library module's file (__file__) or the
# ImportError message naming one, with their sizes; messages, line numbers, other paths and other
# IR remain significant. Each compiler still reads its own library, so changes to library contents
# are exercised rather than hidden by a shared home.
# The corpus is pystachy.py (first: it takes longest), runtime.py, tests/programs/*/*.py,
# tests/deviations/*.py, bench/*.py, bench/pyperformance/*.py, tests/ir/*.py and the rejections
# tests/errors/*/*.py (tests/corpus.sh), with PYSTACHY_PATH
# from NAME.path where it exists, as tests/run.sh runs them. When both compilers have runtime mode
# (`pystachy rt`), runtime.py and
# tests/errors/runtime/rtmode_*.py are compiled with `rt`, as the driver and tests/run.sh compile them
# (every program's executable holds runtime.py's code); otherwise with `ir`, as programs, which
# runtime.py is not, so it then fails alike with both. tests/ir/*.py probe code-generation paths the others never
# take: they are only compiled (here and by tools/check_ir.sh), never run. tests/ir/pending/ holds
# the probes of open compiler bugs, which are not part of the corpus until the fix moves them up.
# The programs run in PYSTACHY_JOBS workers (default: one per CPU), each taking the next program
# left. The first 3 that differ are shown with the start of each diff (the IR's from its first
# differing line, named by the function that holds it); the last line counts them all. Only sh and
# the tools tests/run.sh uses are needed (no python), as in the Python-free stage of tests/verify.sh.
# With --check, they run `check` (which only parses) instead, as tests/run.sh runs it (no NAME.path,
# no IR), and must print the same messages with the same exit status (tests/verify.sh's tests-cpython,
# on the syntax_*.py cases).
# PYSTACHY_CASE_TIMES=FILE appends "MILLISECONDS CASE" as each worker finishes, timing both
# compilers and the comparison together. Completed timings survive interruption; GNU date's %N
# is required, as in tests/run.sh. The report itself stays in input order.
# usage: tools/irsame.sh [--check] OLD NEW [FILE...]   (compiler commands, e.g. build/ref/pystachy
#        ./pystachy or "python3 pystachy.py"; make irsame REF=<commit> runs it against that commit's compiler)
cd "$(dirname "$0")/.." || exit 1
HOW=ir
[ "${1:-}" != --check ] || { HOW=check; shift; }
[ $# -ge 2 ] || { echo "usage: tools/irsame.sh [--check] OLD NEW [FILE...]" >&2; exit 2; }
OLD=$1; NEW=$2; shift 2
for f; do [ -f "$f" ] || { echo "tools/irsame.sh: no such program: $f" >&2; exit 2; }; done

# Match driver.compiler_home() and the loader's removal of one leading ./, without running a
# command to discover its home. Recognize direct executables and Python script invocations;
# unfamiliar wrappers stay unnormalized rather than guessing which library they load.
library_prefix() (
  set -f
  set -- $1
  [ $# -gt 0 ] || exit 0
  if [ $# -gt 1 ]; then
    case ${1##*/} in python | python[0-9]* | pypy | pypy[0-9]*) shift ;; *) exit 0 ;; esac
    while [ $# -gt 1 ]; do
      case $1 in -I | -B | -E | -s | -S | -u | -O | -OO) shift ;; *) exit 0 ;; esac
    done
    case $1 in *.py) ;; *) exit 0 ;; esac
  fi
  home=${PYSTACHY_HOME:-}
  if [ -z "$home" ]; then
    case $1 in */*) home=${1%/*} ;; *) home=. ;; esac
    [ -f "$home/runtime.c" ] || home=$home/..
  fi
  [ -d "$home/lib" ] || exit 0
  prefix=$home/lib/
  printf '%s\n' "${prefix#./}"
)
OLD_LIB=$(library_prefix "$OLD")
NEW_LIB=$(library_prefix "$NEW")

# The real directory of a library prefix, as the compiler embeds it in IR (os.path.realpath):
# nothing when it is unknown or holds a character that LLVM would escape in a string constant.
library_real() (
  [ -n "$1" ] || exit 0
  real=$(cd "$1" 2> /dev/null && pwd -P) || exit 0
  case $real in /*) ;; *) exit 0 ;; esac
  case $real in *[!A-Za-z0-9_./-]*) exit 0 ;; esac
  printf '%s\n' "$real"
)
OLD_REAL=$(library_real "$OLD_LIB")
NEW_REAL=$(library_real "$NEW_LIB")

# A quoted value can imitate a complete compilation context or function description. If it
# contains this library prefix, preserve the messages verbatim; never hide a literal difference.
# An apostrophe between two word characters (program's, M's) or of a possessive after a call or
# a description (f()'s, <lambda>'s) is the compiler's prose, not a quote; inside a quoted value,
# where it is also part of the value, it keeps the value open, so the check stays conservative.
quoted_library_path() (
  prefix=$1
  while IFS= read -r message || [ -n "$message" ]; do
    message=${message#*: error:}
    quote=; escaped=0; previous=
    while [ -n "$message" ]; do
      if [ -n "$quote" ]; then
        case $message in "$prefix"*) exit 0 ;; esac
      fi
      char=${message%"${message#?}"}
      message=${message#?}
      next=${message%"${message#?}"}
      prose=0
      if [ "$char" = "'" ]; then
        case $previous$next in [[:alnum:]_][[:alnum:]_]) prose=1 ;; esac
        case $previous$message in [\)\>]s | [\)\>]s[![:alnum:]_]*) prose=1 ;; esac
      fi
      if [ "$escaped" = 1 ]; then escaped=0
      elif [ -n "$quote" ]; then
        if [ "$char" = '\' ]; then escaped=1
        elif [ "$char" = "$quote" ] && [ $prose = 0 ]; then quote=
        fi
      else
        case $char in
          "'") [ $prose = 1 ] || quote=$char ;;
          '"') quote=$char ;;
        esac
      fi
      previous=$char
    done
    [ -z "$quote" ] || exit 0
  done < "$2"
  exit 1
)

# Only source-location shapes emitted by diagnostics.where(), including nested call contexts.
# Ambiguous quoted payloads and unfamiliar contexts remain raw rather than weakening the oracle.
normalize_messages() {
  if [ -z "$1" ]; then cat "$2"; return; fi
  if quoted_library_path "$1" "$2"; then cat "$2"; return; fi
  # Literal prefix in a BRE with | as delimiter (paths may contain regexp metacharacters).
  pattern=$(printf '%s\n' "$1" | sed 's/[][\\.^$*|]/\\&/g')
  location='[A-Za-z0-9_/-][A-Za-z0-9_./-]*\.py:[0-9][0-9]*'
  sed -e "s|^$pattern\($location: error:\)|lib/\1|" \
      -e "s|\([;(] *compiling [^;]* at \)$pattern\($location\)|\1lib/\2|g" \
      -e "s|\([;(] *specializing [^;]* at \)$pattern\($location\)|\1lib/\2|g" \
      -e "s|\([;(] *making [^;]* at \)$pattern\($location\)|\1lib/\2|g" \
      -e "s|\(<function [^<>]*\(<[a-z]*>[^<>]*\)* (\)$pattern\($location\))|\1lib/\3)|g" "$2"
}

# normalize_ir REAL FILE SCRIPT: FILE's IR with REAL, a compiler's real library directory, rewritten
# in the string constants (a str's length-prefixed global, whose sizes must agree with its text)
# whose whole text is REAL (sys.path's entry), its parent (sys.prefix), a file under REAL
# (a library module's __file__) or ImportError's message naming one (gen_unbound()), as <lib>,
# <home>, <lib>/FILE and that message naming <lib>/FILE, with the sizes recomputed so the IR stays
# valid. No compiler embeds those placeholders, so a relative path where the other embeds a real
# one still differs. Other lines, and names with characters the shapes do not allow, stay raw.
# SCRIPT is scratch.
normalize_ir() {
  real=$1; home=${1%/*}
  if [ -z "$real" ] || ! grep -F -q "${home:-$real}" "$2"; then cat "$2"; return; fi
  grep -n -F "${home:-$real}" "$2" |
    sed -n 's/^\([0-9][0-9]*\):\(@s\.[0-9][0-9]*\) = private unnamed_addr global {i64, i64, i64, \[\([0-9][0-9]*\) x i8\]} {i64 \([0-9][0-9]*\), i64 0, i64 \([0-9][0-9]*\), \[\([0-9][0-9]*\) x i8\] c"\([^"\\]*\)\\00"}, align 8$/\1 \2 \3 \4 \5 \6 \7/p' |
    while read -r line name size length capacity array text; do
      [ "$size" = "$capacity" ] && [ "$size" = "$array" ] && [ "$size" = $((length + 1)) ] &&
        [ "${#text}" = "$length" ] || continue
      case $text in *[![:print:]]*) continue ;; esac
      file=; message=
      case $text in
        "$real") normal='<lib>' ;;
        "$home") [ -n "$home" ] || continue; normal='<home>' ;;
        "$real"/*.py) file=${text#"$real"/} ;;
        "cannot import name '"*"' from '"*"' ($real/"*".py)")
          rest=${text#"cannot import name '"}; imported=${rest%%"'"*}; rest=${rest#*"' from '"}
          module=${rest%%"'"*}; file=${rest#*"' ($real/"}; file=${file%")"}
          message="cannot import name '$imported' from '$module' (<lib>/$file)"
          [ "$text" = "cannot import name '$imported' from '$module' ($real/$file)" ] || continue
          case $imported in '' | *[!A-Za-z0-9_]*) continue ;; esac
          case $module in '' | *[!A-Za-z0-9_.]*) continue ;; esac ;;
        *) continue ;;
      esac
      if [ -n "$file" ]; then
        case $file in *[!A-Za-z0-9_./-]*) continue ;; esac
        normal=${message:-<lib>/$file}
      fi
      size=$((${#normal} + 1))
      printf '%sc\\\n%s = private unnamed_addr global {i64, i64, i64, [%s x i8]} {i64 %s, i64 0, i64 %s, [%s x i8] c"%s\\\\00"}, align 8\n' \
        "$line" "$name" "$size" "${#normal}" "$size" "$size" "$normal"
    done > "$3"
  sed -f "$3" "$2"
}

RT=0  # (whether both have runtime mode: their usage names it)
[ $HOW = check ] || { { $OLD 2>&1 | grep -q 'pystachy rt '; } && { $NEW 2>&1 | grep -q 'pystachy rt '; } && RT=1; }
if [ $# = 0 ]; then
  for f in pystachy.py runtime.py tests/programs/*/*.py tests/deviations/*.py bench/*.py bench/pyperformance/*.py \
      tests/ir/*.py tests/errors/*/*.py; do
    [ -f "$f" ] && set -- "$@" "$f"
  done
fi
JOBS=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $JOBS in '' | *[!0-9]* | 0) JOBS=1 ;; esac
TIMES=${PYSTACHY_CASE_TIMES:-}
if [ -n "$TIMES" ]; then
  case $(date +%s%N) in
    '' | *[!0-9]*) echo "tools/irsame.sh: no case times (PYSTACHY_CASE_TIMES needs date +%s%N, GNU date's)" >&2; TIMES= ;;
  esac
fi
SHOW=3
T=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-irsame.XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT TERM

# same FILE DIR: compile FILE with both compilers in DIR; DIR/report says what differs (empty: nothing)
same() {
  if [ $HOW = check ]; then
    $OLD check "$1" > "$2/old.msg" 2>&1; a=$?
    $NEW check "$1" > "$2/new.msg" 2>&1; b=$?
  else
    mp=$PYSTACHY_PATH
    if [ -f "${1%.py}.path" ]; then
      mp=$(sh tests/prepare_path.sh "$1" "$2") || {
        echo "cannot prepare import path" > "$2/report"; return;
      }
    fi
    how=ir
    case $RT:$1 in 1:runtime.py | 1:*/runtime.py | 1:*/rtmode_*.py) how=rt ;; esac
    PYSTACHY_PATH=$mp $OLD $how "$1" -o "$2/old.ll" > "$2/old.msg" 2>&1; a=$?
    PYSTACHY_PATH=$mp $NEW $how "$1" -o "$2/new.ll" > "$2/new.msg" 2>&1; b=$?
  fi
  messages=0
  if ! cmp -s "$2/old.msg" "$2/new.msg"; then
    if ! normalize_messages "$OLD_LIB" "$2/old.msg" > "$2/old.normal.msg" ||
        ! normalize_messages "$NEW_LIB" "$2/new.msg" > "$2/new.normal.msg"; then
      echo "  cannot normalize diagnostics" > "$2/report"; return
    fi
    cmp -s "$2/old.normal.msg" "$2/new.normal.msg" || messages=1
  fi
  ir=0
  if [ -f "$2/old.ll" ] && [ -f "$2/new.ll" ] && ! cmp -s "$2/old.ll" "$2/new.ll"; then
    if ! normalize_ir "$OLD_REAL" "$2/old.ll" "$2/old.sed" > "$2/old.normal.ll" ||
        ! normalize_ir "$NEW_REAL" "$2/new.ll" "$2/new.sed" > "$2/new.normal.ll"; then
      echo "  cannot normalize IR" > "$2/report"; return
    fi
    cmp -s "$2/old.normal.ll" "$2/new.normal.ll" || ir=1
  fi
  {
    [ $a = $b ] || echo "  exit status $a -> $b"
    if [ $messages = 1 ]; then
      echo "  messages:"; diff -u "$2/old.normal.msg" "$2/new.normal.msg" | sed 1,2d | head -12
    fi
    if [ $ir = 1 ]; then
      l=$(diff "$2/old.normal.ll" "$2/new.normal.ll" | sed -n '1s/^\([0-9]*\).*/\1/p')
      fn=$(head -n "${l:-0}" "$2/old.normal.ll" | sed -n 's/^define [^@]*\(@[^(]*\)(.*/\1/p' | tail -1)
      echo "  IR${l:+ from line $l}${fn:+ (in $fn)}:"; diff -u "$2/old.normal.ll" "$2/new.normal.ll" | sed 1,2d | head -16
    elif [ -f "$2/old.ll" ] && [ -f "$2/new.ll" ]; then
      :
    elif [ -f "$2/old.ll" ] || [ -f "$2/new.ll" ]; then
      echo "  IR written by only one compiler"
    fi
  } > "$2/report.part"
  mv "$2/report.part" "$2/report"
  rm -f "$2/old.ll" "$2/new.ll" "$2/old.normal.ll" "$2/new.normal.ll"
}
# a worker: each program whose directory it is the first to create (mkdir is atomic)
worker() {
  i=0
  for f; do
    i=$((i + 1))
    if [ ! -d "$T/$i" ] && mkdir "$T/$i" 2> /dev/null; then
      [ -z "$TIMES" ] || t0=$(date +%s%N)
      same "$f" "$T/$i"
      # One append per completed case; workers never rewrite another worker's row.
      [ -z "$TIMES" ] || printf '%s %s\n' "$((($(date +%s%N) - t0) / 1000000))" "$f" >> "$TIMES"
    fi
  done
}
k=1
while [ $k -lt "$JOBS" ]; do
  worker "$@" &
  k=$((k + 1))
done
worker "$@"
wait
n=0; bad=0
for f; do
  n=$((n + 1)); r=$T/$n/report
  [ -f "$r" ] && [ ! -s "$r" ] && continue
  bad=$((bad + 1))
  if [ $bad -le $SHOW ]; then
    echo "DIFF $f"
    if [ -f "$r" ]; then cat "$r"; else echo "  no result (its worker died)"; fi
  fi
done
if [ $bad = 0 ]; then echo "$n programs identical"; else echo "$bad of $n differ"; fi
[ $bad = 0 ]
