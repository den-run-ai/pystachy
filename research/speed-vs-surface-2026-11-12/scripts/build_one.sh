#!/bin/bash
# usage: build_one.sh LABEL SHA   -> worktree $S/wt/LABEL, log $S/logs/build-LABEL.log, $S/results/build-LABEL.json
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
REPO=/home/user/pystachy
label=$1 sha=$2
wt=$S/wt/$label
log=$S/logs/build-$label.log
out=$S/results/build-$label.json
mkdir -p $S/wt $S/logs $S/results
if [ ! -d "$wt" ]; then
  git -C $REPO worktree add --detach "$wt" "$sha" > "$log" 2>&1 || { echo "{\"label\":\"$label\",\"sha\":\"$sha\",\"ok\":false,\"error\":\"worktree\"}" > "$out"; exit 1; }
fi
cd "$wt" || exit 1
# no inherited Pystachy settings; the checkout's default caches (build/) stay private to it
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
start=$(date +%s.%N)
make PY=/usr/local/bin/python3.13 pystachy >> "$log" 2>&1
rc=$?
end=$(date +%s.%N)
ir_lines=$( [ -f build/stage1.ll ] && wc -l < build/stage1.ll || echo 0)
rt_lines=$( [ -f build/rt1.ll ] && wc -l < build/rt1.ll || echo 0)
size=$( [ -f pystachy ] && stat -c %s pystachy || echo 0)
python3 - "$out" "$label" "$sha" "$rc" "$start" "$end" "$ir_lines" "$rt_lines" "$size" <<'EOF'
import json, sys
out, label, sha, rc, start, end, ir, rt, size = sys.argv[1:]
json.dump({"label": label, "sha": sha, "ok": rc == "0", "rc": int(rc), "build_s": float(end) - float(start),
           "compiler_ir_lines": int(ir), "runtime_py_ir_lines": int(rt), "binary_bytes": int(size)}, open(out, "w"))
EOF
# the stage IR is large and no longer needed (its line count is recorded)
rm -f build/stage1.ll build/stage2.ll build/stage3.ll build/rt1.ll build/rt2.ll build/rt3.ll
echo "$label rc=$rc $(python3 -c "print(round($end - $start))")s ir=$ir_lines"
exit $rc
