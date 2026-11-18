#!/bin/bash
# Copy the second edition into the repository's research/ folder (a research branch; never merged into main).
# The first edition, research/speed-vs-surface-2026-11-12, is left as it is.
set -euo pipefail
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
V=$S/v2
R=/home/user/pystachy/research/speed-vs-surface-2026-11-18
rm -rf "$R"
mkdir -p "$R/scripts" "$R/data" "$R/page" "$R/raw" "$R/print" "$R/export"
cp $V/README.md "$R/README.md"
cp $S/sweep/commits_v2.txt "$R/commits.txt"
for f in build_one.sh pipeline.sh analyze_one.py method_sweep.py extract_qualify.py cpython_ref.py timing.py report.py \
         datasets.py classify.py analysis.py git_metrics.py export_matrix.py overlay.py bisect_perf.py store_docs.py \
         export_md.py perf_specs.json retime.py groups.py progress.py change_shares.py changes.py after_builds.sh \
         timing_phase.sh timing_jit_build.sh figures.py assemble_research.sh; do
  cp $V/scripts/$f "$R/scripts/"
done
for f in index.html render.js export.js interact.js offline_check.js section.js sheet.js sources.json; do
  cp $V/page/$f "$R/page/"
done
for f in README.md prepare.py build_print.py charts.js print.css render_print.js otf2ttf.py data.json; do
  cp $V/print/$f "$R/print/"
done
cp $V/data/*.json "$R/data/"
cp -r $V/export/. "$R/export/"
cp $V/raw/timing.json $V/raw/retime-*.json $V/raw/change_shares.json $V/raw/progress-report-to-head.json \
   $V/raw/progress-steps.txt $V/raw/groups-*.txt $V/raw/analysis.txt $V/raw/timing-cold-jit-build.json "$R/raw/"
python3 - "$S" "$R" <<'EOF'
import json, glob, os, sys
S, R = sys.argv[1:]
labels = [line.split()[0] for line in open(f"{S}/sweep/commits_v2.txt") if line.strip()]
builds = [json.load(open(f"{S}/results/build-{l}.json")) for l in labels]
json.dump(builds, open(f"{R}/raw/builds.json", "w"), indent=0)
census = {l: json.load(open(f"{S}/results/census-{l}.json")) for l in labels}
json.dump(census, open(f"{R}/raw/census.json", "w"), indent=0)
prep = {l: json.load(open(f"{S}/results/perfprep-{l}.json")) for l in labels}
json.dump(prep, open(f"{R}/raw/perfprep.json", "w"), indent=0)
q = json.load(open(f"{S}/sweep/qualified.json"))
json.dump({"python": q["python"], "left_out": q["left_out"], "errors": q["errors"],
           "records": [{k: r[k] for k in ("file", "test", "cpython") if k in r} for r in q["records"]]},
          open(f"{R}/raw/qualified.json", "w"))
EOF
(cd $V/scripts && python3 export_matrix.py $S/sweep/commits_v2.txt "$R/raw/methods_matrix.csv.gz" "$R/raw/methods_head_errors.csv.gz")
gzip -9 -c $S/results/methods-overlay-1117-1034_3cf23d20.json > "$R/raw/methods_head_overlay.json.gz"
gzip -9 -c $S/results/methods-dynany-1117-1034_3cf23d20.json > "$R/raw/methods_head_dynamic_any.json.gz"
du -sh "$R"; find "$R" -type f | sort | sed "s|$R/||"
