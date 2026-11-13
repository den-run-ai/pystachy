#!/bin/bash
# lint-run.sh TREE LOGDIR: run the unit-test commands of TREE's Lint workflow one by one, with the
# pinned interpreter first on PATH as python3, and print each command's exit status
tree=$1; logs=$2; mkdir -p "$logs"
cd "$tree" || exit 1
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2
n=0; bad=0
while IFS= read -r cmd; do
  n=$((n + 1))
  bash -c "$cmd" > "$logs/$n.log" 2>&1; code=$?
  [ $code = 0 ] || { bad=$((bad + 1)); echo "FAIL($code) #$n: $cmd"; }
done < <(grep -E "^\s+(run: )?(PYSTACHY_[A-Z_]+=\S+ )*python3 (-m unittest|tools/lint_controls)" .github/workflows/lint.yml | sed -E 's/^\s+(run: )?//')
echo "$n commands, $bad failed"
