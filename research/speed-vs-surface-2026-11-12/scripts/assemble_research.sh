#!/bin/bash
# Copy the evaluation into the repository's research/ folder (a research branch; never merged into main).
set -euo pipefail
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
R=/home/user/pystachy/research/speed-vs-surface-2026-11-12
rm -rf "$R"
mkdir -p "$R/scripts" "$R/data" "$R/page" "$R/raw"
cp $S/research-readme.md "$R/README.md"
cp $S/sweep/commits_all.txt "$R/commits.txt"
for f in build_one.sh pipeline.sh analyze_one.py method_sweep.py extract_qualify.py cpython_ref.py timing.py report.py \
         datasets.py classify.py analysis.py git_metrics.py export_matrix.py overlay.py bisect_perf.py store_docs.py; do
  [ -f $S/sweep/$f ] && cp $S/sweep/$f "$R/scripts/"
done
cp $S/sweep/perf_specs.json "$R/scripts/"
cp $S/page/index.html "$R/page/index.html"
cp $S/page/render.js "$R/page/render.js"
cp $S/page/data/*.json "$R/data/"
cp $S/results/timing.json "$R/raw/timing.json"
python3 - "$S" "$R" <<'EOF'
import json, glob, os, sys
S, R = sys.argv[1:]
builds = [json.load(open(f)) for f in sorted(glob.glob(f"{S}/results/build-1*.json"))]
json.dump(builds, open(f"{R}/raw/builds.json", "w"), indent=0)
census = {os.path.basename(f)[7:-5]: json.load(open(f)) for f in sorted(glob.glob(f"{S}/results/census-1*.json"))}
json.dump(census, open(f"{R}/raw/census.json", "w"), indent=0)
prep = {os.path.basename(f)[9:-5]: json.load(open(f)) for f in sorted(glob.glob(f"{S}/results/perfprep-1*.json"))}
json.dump(prep, open(f"{R}/raw/perfprep.json", "w"), indent=0)
q = json.load(open(f"{S}/sweep/qualified.json"))
json.dump({"python": q["python"], "left_out": q["left_out"], "errors": q["errors"],
           "records": [{k: r[k] for k in ("file", "test", "cpython") if k in r} for r in q["records"]]},
          open(f"{R}/raw/qualified.json", "w"))
EOF
(cd $S/sweep && python3 export_matrix.py commits_all.txt "$R/raw/methods_matrix.csv.gz" "$R/raw/methods_head_errors.csv.gz")
gzip -9 -c $S/results/methods-HEAD-overlay.json > "$R/raw/methods_head_overlay.json.gz"
[ -f $S/results/methods-HEAD-dynany.json ] && gzip -9 -c $S/results/methods-HEAD-dynany.json > "$R/raw/methods_head_dynamic_any.json.gz"
du -sh "$R"; find "$R" -type f | sort
