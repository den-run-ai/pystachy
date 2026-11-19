#!/bin/sh
# irexpect.sh COMPILER FILE.py KIND...: print the .calls/.tbaa expectations that tools/check_ir.sh
# compares, from COMPILER's `ir` output with every optimization on (as check_ir.sh compiles them)
PYS=$1; f=$2; shift 2
T=$(mktemp -d)
PYSTACHY_IRCHECK=1 PYSTACHY_OPT= $PYS ir "$f" > $T/ir.ll || exit 1
for kind; do
case $kind in
calls) awk '/^define / { f = $0; sub(/\(.*/, "", f); sub(/.* /, "", f); c = "" }
    /^  .*(call|invoke) [^@]*@pys_/ { s = $0; sub(/^.*(call|invoke) [^@]*@/, "", s); sub(/\(.*/, "", s); c = c " " s }
    /^}/ && f != "" { print f ":" c; f = "" }' $T/ir.ll ;;
tbaa) awk 'NR == FNR {
      if ($0 ~ /^![0-9]+ = !\{!"/) { s = $0; sub(/^[^"]*"/, "", s); sub(/".*/, "", s); name[$1] = s }
      else if ($0 ~ /^![0-9]+ = !\{![0-9]+, ![0-9]+, i64 [0-9]+\}$/) { s = $0; sub(/^[^{]*\{/, "", s); sub(/\}$/, "", s)
        split(s, p, ", "); base[$1] = p[1]; sub(/^i64 /, "", p[3]); off[$1] = p[3] }
      next }
    /^define / { f = $0; sub(/\(.*/, "", f); sub(/.* /, "", f); c = "" }
    /^  .*, !tbaa !/ { t = $0; sub(/.*, !tbaa /, "", t); sub(/[^!0-9].*/, "", t)
      w = "load"; if ($0 ~ /^  store /) w = "store"; c = c " " w ":" name[base[t]] "+" off[t] }
    /^}/ && f != "" { print f ":" c; f = "" }' $T/ir.ll $T/ir.ll ;;
esac
done
rm -rf $T
