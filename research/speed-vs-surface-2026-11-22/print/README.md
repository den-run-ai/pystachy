# Print edition

`export/report.pdf` is built from these files: one topic per A4 page, 10.5 pt body text and
vector charts drawn at their printed size with d3.

```sh
python3 prepare.py                          # print/data.json from data/, export/data/perf_index.csv and raw/
python3 build_print.py report-print.html    # self-contained HTML (d3 and data inline)
node render_print.js report-print.html report.pdf   # A4 PDF; fails if a page overflows
```

`prepare.py` reads the charted datasets, the blocker groups (`raw/groups-*.txt`), the progress since
the second and first editions (`raw/progress-prev-to-head.json`, `raw/progress-report-to-head.json`), the
changed-line shares, the `float`, `words` and `fib` re-timings, the idle-machine bootstraps
(`raw/bootstrap-idle.json`) and the agreement with the second edition's timing run. The fonts are Inter (SIL Open Font License 1.1) converted to TrueType outlines with
`otf2ttf.py` into `fonts/` (not committed), so Chromium embeds them as TrueType rather than Type 3.
Paths in the scripts point at the session's scratch directory, as in `scripts/`.
