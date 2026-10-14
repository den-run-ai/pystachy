#!/bin/sh
# The cached runtime's rules (#24; docs/runtime-in-subset.md §1.4), with a private PYSTACHY_HOME, a copy
# of the compiler and LLVM tools behind wrappers (PYSTACHY_LLVM) that count the runtime's builds
# (llvm-as compiles nothing else) and can fail, kill or edit a source in the middle of one. The program
# prints a message of runtime.py and one of runtime.c, which show what its runtime was built from.
#   - The cache is used again while nothing it is built from changes, also through another path to
#     the same tools, and by the AOT tier.
#   - It is built again, and the new entry replaces the old, when runtime.py changes by an edit of the
#     same size whose mtime is set back, when runtime.c changes, when a file it includes from ryu/
#     changes (the home's: the runs start in a directory whose ryu/d2s.c does not compile), when they
#     change while the runtime is built (the edits set their mtimes back: the build is of the bytes it
#     read, and the next run builds the new ones), when a tool changes and when the compiler changes
#     (also by an edit of the same size whose mtime is set back).
#   - PYSTACHY_CFLAGS and PYSTACHY_OPT get entries of their own (the same passes named otherwise, the
#     same one); the tools found through PATH too.
#   - A failed llvm-link and a build killed after opt leave nothing that a later run uses.
#   - pystachy ext caches its glue (pyembed.c, pyext.c) beside the runtime and uses it again.
#   - With a tool whose times have not settled, run and ext build a runtime (and glue) of their own,
#     which they use, and publish nothing.
#   - The compiler is found through PATH as the shell finds it, past a directory and a file that is
#     not executable, and through a symbolic link; a script run by CPython is opened as named, in the
#     current directory, not looked for in PATH.
# usage: tests/cache.sh [COMPILER]   (default ./pystachy; "python3 -m pystachy" tests the CPython-hosted
#        compiler, from a copy of pystachy.py and src/). $PY (default python3) loads the extension modules,
#        or the CPython that runs the hosted compiler does
cd "$(dirname "$0")/.." || exit 1
PYS=${1:-./pystachy}
CPY=${PY:-python3}
case $PYS in
  *" -m pystachy") PY=${PYS% -m pystachy}; CPY=$PY; me=pystachy.py; from=pystachy.py ;;
  *) PY=; me=pystachy; from=$PYS ;;
esac
unset PYSTACHY_CFLAGS PYSTACHY_OPT PYSTACHY_PATH PYSTACHY_GC PYSTACHY_GC_STRESS PYSTACHY_IRFX PYSTACHY_CACHE
T=${TMPDIR:-/tmp}/pystachy-cache.$$
rm -rf "$T"
mkdir -p "$T/home" "$T/bin" "$T/llvm" "$T/tmp" "$T/d1/pystachy" "$T/d1/clang" "$T/d2" "$T/d3" "$T/d4" "$T/ryu" || exit 1
trap 'rm -rf "$T"' EXIT
H=$T/home
B=$H/build
cp runtime.c runtime.py pyembed.c pyext.c "$H/" && cp -R lib ryu "$H/" && cp "$from" "$T/bin/$me" && cp "$from" "$T/base" || exit 1
if [ -n "$PY" ] && [ -d src ]; then cp -R src "$T/bin/" || exit 1; fi
# the runs start in $T: a runtime.c that took its includes from there would not compile
printf '#error "ryu/d2s.c of the current directory"\n' > "$T/ryu/d2s.c" || exit 1
# the edits: the same size, other messages
sed 's/substring not found/substring NOT found/g' runtime.py > "$T/NOT.py"
sed 's/invalid literal for int()/INVALID literal for int()/g' runtime.c > "$T/INVALID.c"
cp runtime.py "$T/orig.py" && cp runtime.c "$T/orig.c" || exit 1
for f in py c; do
  e=NOT.py; [ $f = c ] && e=INVALID.c
  if cmp -s "$T/orig.$f" "$T/$e" || [ "$(wc -c < "$T/orig.$f")" != "$(wc -c < "$T/$e")" ]; then
    echo "tests/cache.sh: cannot make a same-size edit of runtime.$f"; exit 1
  fi
done
printf 'try:\n    print("abc".index("z"))\nexcept ValueError as e:\n    print(e)\ntry:\n    print(int("x"))\nexcept ValueError as e:\n    print(e)\n' > "$T/prog.py"
P0="substring not found"; P1="substring NOT found"
C0="invalid literal for int() with base 10: 'x'"; C1="INVALID literal for int() with base 10: 'x'"
: > "$T/built"
# The wrappers: llvm-as counts the builds; llvm-link fails (CACHE_FAIL) or runs edit.sh (CACHE_EDIT)
# when it links the runtime (not a program: --only-needed); opt kills the compiler once it has written
# the runtime's bitcode (CACHE_KILL), and the shell that ran opt, unless that shell exec'd it
for t in clang llvm-as llvm-link opt lli; do
  real=$(command -v "${PYSTACHY_LLVM:+${PYSTACHY_LLVM%/}/}$t") || { echo "tests/cache.sh: cannot find $t"; exit 1; }
  case $t in
    llvm-as) hook="echo >> '$T/built'" ;;
    llvm-link) hook="if [ \"\$1\" != --only-needed ]; then [ -z \"\$CACHE_FAIL\" ] || exit 1; [ -z \"\$CACHE_EDIT\" ] || sh '$T/edit.sh'; fi" ;;
    opt) hook="if [ \"\$1\" = -O2 ] && [ -n \"\$CACHE_KILL\" ]; then '$real' \"\$@\"; p=\$PPID
  case \$(ps -o comm= -p \$p) in sh | dash | bash) p=\"\$p \$(ps -o ppid= -p \$p)\" ;; esac; kill -9 \$p; exit 1; fi" ;;
    clang) hook=:; realdir=$(dirname "$real") ;;
    *) hook=: ;;
  esac
  printf '#!/bin/sh\n%s\nexec %s "$@"\n' "$hook" "'$real'" > "$T/llvm/$t" && chmod +x "$T/llvm/$t" || exit 1
done
ln -s llvm "$T/llvm2"
ln -s ../bin/pystachy "$T/d3/pystachy"
printf '#!/bin/sh\necho decoy\n' > "$T/d2/pystachy"
cp pystachy.py "$T/d4/pystachy.py" && chmod +x "$T/d4/pystachy.py"
# the copy of the compiler, the tools and the sources must have settled (2 s) for the cache to be written
sleep 3

pass=0; fail=0
ok() { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }
builds() { wc -l < "$T/built" | tr -d ' '; }
# the cache's runtimes (inode and name), their number, its ext glue, and the other files but the
# hashes (partial ones)
entries() { (cd "$B" && ls -i runtime-py-*-????????????????.bc runtime-py-*-????????????????.o 2> /dev/null); }
pairs() { (cd "$B" && ls runtime-py-*-????????????????.bc 2> /dev/null) | wc -l | tr -d ' '; }
glue() { (cd "$B" && ls -i runtime-py-*-????????????????.py*.bc 2> /dev/null); }
others() {
  for f in "$B"/*; do
    case ${f##*/} in
      runtime-py-*-????????????????.bc | runtime-py-*-????????????????.o | runtime-py-*-????????????????.py*.bc | runtime-py.hashes) ;;
      *) printf '%s ' "${f##*/}" ;;
    esac
  done
}
# pys ARGS...: the compiler under test, run by its path from $T, PYSTACHY_LLVM the wrappers (or $LLVM)
pys() { (cd "$T" && TMPDIR="$T/tmp" PYSTACHY_HOME="$H" PYSTACHY_LLVM="${LLVM-$T/llvm}" $PY "$T/bin/$me" "$@"); }
# check NAME OUTPUT BUILDS [VAR=VALUE...]: pystachy run prog.py, with VAR=VALUE in its environment (and
# the compiler run by name from directory $BYNAME if that is set), prints OUTPUT after BUILDS builds
check() {
  c_name=$1; c_want=$2; c_n=$3; shift 3
  c_b=$(builds)
  c_got=$( (for a; do export "${a?}"; done
            if [ -n "${BYNAME-}" ]; then
              cd "$BYNAME" && TMPDIR="$T/tmp" PYSTACHY_HOME="$H" PYSTACHY_LLVM="${LLVM-$T/llvm}" $PY $me run "$T/prog.py"
            else pys run prog.py; fi) 2>&1)
  c_b=$(($(builds) - c_b))
  if [ "$c_got" = "$c_want" ] && [ "$c_b" = "$c_n" ]; then ok "$c_name"
  else bad "$c_name: printed '$c_got' after $c_b builds of the runtime (expected '$c_want' after $c_n)"; fi
}
same() { if [ "$(entries)" = "$1" ]; then ok "$2"; else bad "$2: the entries changed from:"; echo "$1"; echo "to:"; entries; fi; }
npairs() { if [ "$(pairs)" = "$1" ]; then ok "$2"; else bad "$2: $(pairs) entries, not $1"; entries; fi; }
clean() { if [ -z "$(others)" ] && [ -z "$(ls -A "$T/tmp")" ]; then ok "$1"; else bad "$1: $(others) $(ls -A "$T/tmp")"; fi; }
# edit FILE CONTENT: FILE gets CONTENT's bytes, in place, and its mtime back (touch -r)
edit() { cp -p "$1" "$T/ref" && cat "$2" > "$1" && touch -r "$T/ref" "$1"; }
out=$(printf '%s\n%s' "$P0" "$C0")

echo "-- the compiler: $PYS"
check "a first run builds the runtime" "$out" 1
npairs 1 "one entry: a .bc and its .o"
clean "no partial or temporary file is left"
E=$(entries)
check "nothing changed: the cache is used" "$out" 0
same "$E" "the same entry, not written again"
if [ -s "$B/runtime-py.hashes" ]; then ok "the hashes of settled files are kept"; else bad "no runtime-py.hashes"; fi
b=$(builds)
if pys build prog.py -o "$T/prog" && [ "$("$T/prog")" = "$out" ] && [ "$(builds)" = "$b" ]; then ok "the AOT tier uses the cache"
else bad "the AOT tier does not use the cache"; fi
same "$E" "the AOT tier writes no entry"
check "the same tools through another path (a symbolic link): the cache is used" "$out" 0 LLVM="$T/llvm2"
same "$E" "the same entry"

edit "$H/runtime.py" "$T/NOT.py"
if [ "$H/runtime.py" -nt "$T/ref" ] || [ "$H/runtime.py" -ot "$T/ref" ] || [ "$(wc -c < "$H/runtime.py")" != "$(wc -c < "$T/ref")" ]; then
  bad "the edit of runtime.py did not keep its size and mtime"; fi
out=$(printf '%s\n%s' "$P1" "$C0")
check "an edit of runtime.py of the same size, its mtime set back: built again" "$out" 1
npairs 1 "the new entry replaces the old"
cat "$T/INVALID.c" > "$H/runtime.c"
check "an edit of runtime.c: built again" "$(printf '%s\n%s' "$P1" "$C1")" 1
printf '/* an edit */\n' >> "$H/ryu/common.h"
check "an edit of ryu/common.h, which runtime.c includes: built again, from the home's ryu/" "$(printf '%s\n%s' "$P1" "$C1")" 1
check "and used then" "$(printf '%s\n%s' "$P1" "$C1")" 0
# edits while the runtime is built, after its sources were read, both with their mtimes set back
cat "$T/orig.py" > "$H/runtime.py"
cp -p "$H/runtime.py" "$T/ref.py" && cp -p "$H/runtime.c" "$T/ref.c" || exit 1
printf '%s\n' "cat '$T/NOT.py' > '$H/runtime.py' && touch -r '$T/ref.py' '$H/runtime.py' && cat '$T/orig.c' > '$H/runtime.c' && touch -r '$T/ref.c' '$H/runtime.c'" > "$T/edit.sh"
check "runtime.py and runtime.c edited while the runtime is built: it holds what was read" "$(printf '%s\n%s' "$P0" "$C1")" 1 CACHE_EDIT=1
check "the next run builds the edited sources" "$out" 1
check "and the run after it uses them" "$out" 0
E=$(entries)

got=$( (export CACHE_FAIL=1 PYSTACHY_CFLAGS=-DPYSTACHY_CACHE_TEST; pys run prog.py) 2>&1)
st=$?
if [ $st != 0 ] && echo "$got" | grep -q "cannot build the runtime"; then ok "a failed llvm-link fails the run"
else bad "a failed llvm-link: status $st, $got"; fi
same "$E" "a failed build leaves no entry"
clean "nor a partial or temporary file"
check "the same flags then build the runtime" "$out" 1 PYSTACHY_CFLAGS=-DPYSTACHY_CACHE_TEST
npairs 2 "PYSTACHY_CFLAGS: an entry of their own"
check "PYSTACHY_OPT=-all: built" "$out" 1 PYSTACHY_OPT=-all
npairs 3 "PYSTACHY_OPT: an entry of its own"
check "the same passes turned off by name: the same entry" "$out" 0 PYSTACHY_OPT=-tupleiter,-dictfuse,-listget,-listfast,-moduleints
check "without them, the first entry is used" "$out" 0
echo "# changed" >> "$T/llvm/opt"
sleep 3
check "opt changed: built again" "$out" 1
npairs 3 "the new entry replaces the one of the old opt"
check "and used then" "$out" 0

if [ -n "$PY" ]; then x='#x'; y='#y'; else x=x; y=y; fi
{ cat "$T/base"; printf '%s' "$x"; } > "$T/edited" && cat "$T/edited" > "$T/bin/$me" || exit 1
sleep 3
check "the compiler changed: built again" "$out" 1
cp -p "$T/bin/$me" "$T/ref" && { cat "$T/base"; printf '%s' "$y"; } > "$T/edited" && cat "$T/edited" > "$T/bin/$me" && touch -r "$T/ref" "$T/bin/$me" || exit 1
if cmp -s "$T/ref" "$T/bin/$me" || [ "$(wc -c < "$T/ref")" != "$(wc -c < "$T/bin/$me")" ]; then bad "the edit of the compiler is not of the same size"; fi
sleep 3
check "the compiler edited, the same size, its mtime set back: built again" "$out" 1
npairs 3 "the new entry replaces the old compiler's"
E=$(entries)

if [ -n "$PY" ]; then
  # Components must participate in the compiler's content fingerprint too.
  component=$(find "$T/bin/src/pystachy_compiler" -name '*.py' -type f | sort | head -1)
  [ -n "$component" ] || exit 1
  cp "$component" "$T/component-base" && { cat "$T/component-base"; printf '#x'; } > "$T/edited" && cat "$T/edited" > "$component" || exit 1
  sleep 3
  check "a compiler component changed: built again" "$out" 1
  cp -p "$component" "$T/ref" && { cat "$T/component-base"; printf '#y'; } > "$T/edited" && cat "$T/edited" > "$component" && touch -r "$T/ref" "$component" || exit 1
  if cmp -s "$T/ref" "$component" || [ "$(wc -c < "$T/ref")" != "$(wc -c < "$component")" ]; then bad "the component edit did not keep its size"; fi
  sleep 3
  check "a component edited, the same size, its mtime set back: built again" "$out" 1
  npairs 3 "the new entry replaces the old component's"
  E=$(entries)
  check "python3 pystachy.py opens ./pystachy.py, not the one on PATH: the cache is used" "$out" 0 BYNAME="$T/bin" PATH="$T/d4:$PATH"
else
  check "run by name through PATH, past a directory and a file that is not executable: the cache is used" "$out" 0 \
    BYNAME="$T" PATH="$T/d1:$T/d2:$T/bin:$PATH"
  check "run by name through a symbolic link: the cache is used" "$out" 0 BYNAME="$T" PATH="$T/d3:$PATH"
fi
same "$E" "the same entries"
check "the tools found through PATH, past a directory named clang: built with them" "$out" 0 LLVM= PATH="$T/d1:$realdir:$PATH"
npairs 4 "an entry of their own"
E=$(entries)
check "and used then" "$out" 0 LLVM= PATH="$T/d1:$realdir:$PATH"
same "$E" "the same entries"
clean "no partial or temporary file is left"

# pystachy ext: an extension module's glue (pyembed.c, pyext.c) is cached beside the runtime, by the
# same rules; the module is loaded where $CPY is CPython 3.12 or later
loads() { # loads NAME: the module of $T/so/NAME.abi3.so doubles 21
  if "$CPY" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2> /dev/null; then
    if [ "$(cd "$T/so" && "$CPY" -c "import $1; print($1.twice(21))" 2>&1)" = 42 ]; then ok "and $CPY loads the module"
    else bad "$CPY cannot load $1.abi3.so"; fi
  fi
}
mkdir -p "$T/so"
printf 'from ffi import export\n\n\n@export\ndef twice(n: int) -> int:\n    return n * 2\n' > "$T/m.py"
cp "$T/m.py" "$T/m2.py"
b=$(builds)
if pys ext m.py -o so/m.abi3.so && [ -f "$T/so/m.abi3.so" ] && [ $(($(builds) - b)) = 2 ] && [ "$(glue | wc -l | tr -d ' ')" = 2 ]; then
  ok "pystachy ext builds pyembed.c and pyext.c once, beside the cached runtime"
else bad "pystachy ext: $(($(builds) - b)) builds, glue: $(glue)"; fi
loads m
G=$(glue)
b=$(builds)
if pys ext m.py -o so/m.abi3.so && [ "$(builds)" = "$b" ] && [ "$(glue)" = "$G" ]; then ok "and uses them then"
else bad "pystachy ext again: $(($(builds) - b)) builds, glue: $(glue)"; fi
same "$E" "the runtime's entries are the same"
clean "no partial or temporary file is left"
# a tool whose times have not settled (opt's mtime in the future): each run builds a runtime (and
# glue) of its own, which it uses, publishes nothing and leaves nothing
touch -t 203001010000 "$T/llvm/opt"
check "a tool not settled: a run builds a runtime of its own" "$out" 1
same "$E" "and publishes nothing"
clean "and leaves nothing"
b=$(builds)
if pys ext m2.py -o so/m2.abi3.so && [ -f "$T/so/m2.abi3.so" ] && [ $(($(builds) - b)) = 3 ]; then
  ok "pystachy ext builds a runtime and glue of its own"
else bad "pystachy ext with a tool not settled: $(($(builds) - b)) builds"; fi
loads m2
same "$E" "and publishes no runtime"
if [ "$(glue)" = "$G" ]; then ok "nor glue"; else bad "glue published: $(glue)"; fi
clean "and leaves nothing"
touch "$T/llvm/opt"
sleep 3
E=$(entries)

# last, as it leaves a partial file and a temporary directory behind (as a killed build does)
cat "$T/orig.py" > "$H/runtime.py"
got=$( (export CACHE_KILL=1; pys run prog.py) 2>&1)
st=$?
if [ $st != 0 ]; then ok "a build killed after opt ends the run"; else bad "a killed build: status 0, $got"; fi
same "$E" "and writes no entry"
out=$(printf '%s\n%s' "$P0" "$C0")
check "the next run builds the runtime" "$out" 1
npairs 4 "and its entry replaces the old"
echo "$pass passed, $fail failed"
[ $fail = 0 ]
