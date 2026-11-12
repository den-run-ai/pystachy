"""Write the dashboard's store documents as local JSON files for ArtifactData batch writes.

usage: python3 store_docs.py ASSETS.json PAGE.html OUTDIR
ASSETS.json maps dataset id -> {"url": "/_blob/...", "name": "file.json"}.
"""
import datetime
import json
import sys
from pathlib import Path

DATASETS = {
    "samples": ("Sampled commits",
                "One row per sampled commit on main from 7 October to 11 November 2026: CPython test methods passing, "
                "first-error causes, benchmarks that work, source size and compiler size."),
    "speedups": ("AOT speed per benchmark and commit",
                 "Median AOT time of each benchmark at each sampled commit and of CPython 3.13.18 on the same source, "
                 "measured pinned to one core on an idle 4-vCPU VM; speedup is CPython's time over the commit's."),
    "history": ("Source size at every commit on main",
                "Lines of compiler, shipped library and runtime source, and differential test counts, at each of the "
                "660 first-parent commits on main."),
    "blockers_head": ("Most common first errors, latest commit",
                      "The 15 most frequent first compiler errors among the CPython test methods v0.4.0-alpha.5 rejects, "
                      "with the cause each was assigned."),
    "unlocks": ("Newly passing methods per sampled commit",
                "Methods that pass at a sampled commit but not at the previous one, by the cause of their first error "
                "at the previous one."),
    "census": ("Unmodified upstream pyperformance files",
               "Whether each of the 52 pyperformance 1.14.0 benchmark files compiles with only pyperf's runner replaced, "
               "the first sampled commit that compiled it, and its first error at the latest commit."),
    "changes": ("Largest speed changes and their causes",
                "The biggest AOT time changes between consecutive sampled commits, with the merge that caused each where "
                "a bisection over the first-parent merges in between found it, or the merges the interval contains."),
    "overlay_head": ("Latest commit with CPython's standard library added",
                     "Where the methods blocked by a missing library piece stop when CPython 3.13.16's pure-Python "
                     "standard library is on the import path, at v0.4.0-alpha.5."),
}


def main():
    assets, page, out = sys.argv[1:]
    assets = json.load(open(assets))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    edit = {"via": "claude", "at": now}
    json.dump({"title": "Pystachy speed vs surface", "lang": "en"}, open(out / "meta.json", "w"))
    for ds, (title, desc) in DATASETS.items():
        a = assets[ds]
        doc = {"title": title, "description": desc,
               "source": {"kind": "file", "url": a["url"], "name": a["name"], "format": "json"},
               "updated": {"at": now, "by": "Claude"}, "fixed": True, "edit": edit}
        json.dump(doc, open(out / f"ds-{ds}.json", "w"))
    json.dump({"text": Path(page).read_text(), "edit": edit}, open(out / "index.json", "w"))
    print("wrote", len(DATASETS) + 2, "documents to", out)


if __name__ == "__main__":
    main()
