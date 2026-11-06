#!/usr/bin/env python3
"""Summarize completed GC process results using paired round ratios.

Ratios are candidate/control; smaller is lower elapsed time or memory. Warmups
are excluded. Observed ranges and A/A variation are descriptive, not confidence
intervals or significance tests. No aggregate across unlike workloads is made.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

PAIRS = [("main_aa", "main"), ("scalar", "main"), ("default", "scalar"),
         ("default", "main"), ("atomic_union", "default"), ("atomic_union", "main"),
         ("block", "default")]


BDW_IDENTITY = ("version", "mode", "markers", "incremental", "protection")
BDW_COUNTERS = ("collections", "stopped_world_ms", "pauses", "heap_peak_bytes",
                "heap_bytes", "free_bytes", "allocated_bytes")


def bdw_diagnostics(sample):
    lines = [line for line in sample.get("stderr_tail", "").splitlines() if line.startswith("bdwgc:")]
    if not lines:
        return None
    if len(lines) != 1:
        raise ValueError("ambiguous BDWGC diagnostic")
    tokens = [token.split("=", 1) for token in lines[0].split()[1:]]
    fields = dict(tokens)
    if len(fields) != len(tokens) or set(fields) != set(BDW_IDENTITY + BDW_COUNTERS):
        raise ValueError("unexpected BDWGC diagnostic fields")
    if len(fields["version"].split(".")) != 3 or not all(p.isdigit() for p in fields["version"].split(".")):
        raise ValueError("invalid BDWGC version")
    if fields["mode"] not in ("default", "incremental", "generational"):
        raise ValueError("unknown BDWGC mode")
    for key in ("markers", "incremental", "protection") + BDW_COUNTERS:
        fields[key] = float(fields[key]) if key == "stopped_world_ms" else int(fields[key])
        if not math.isfinite(fields[key]) or fields[key] < 0:
            raise ValueError("invalid BDWGC diagnostic value")
    if fields["markers"] < 1 or fields["incremental"] not in (0, 1):
        raise ValueError("invalid BDWGC configuration")
    return fields


def ratios(numerators, denominators):
    if any(n <= 0 or d <= 0 for n, d in zip(numerators, denominators)):
        return None  # zero/rounded-zero GC times do not support a ratio
    values = [n / d for n, d in zip(numerators, denominators)]
    return {"paired": values, "geometric_mean": math.exp(statistics.fmean(map(math.log, values))),
            "median": statistics.median(values), "min": min(values), "max": max(values),
            "lower_rounds": sum(v < 1 for v in values), "equal_rounds": sum(v == 1 for v in values)}


def validate(report):
    if not report.get("complete") or not report.get("all_outputs_match"):
        raise ValueError("refusing incomplete or output-failing results")
    variants = {v["name"]: v for v in report["variants"]}
    if len(variants) != len(report["variants"]):
        raise ValueError("duplicate variant name")
    wanted = {(name, phase, rnd) for name in variants
              for phase, count in (("warmup", report["warmups"]), ("measure", report["rounds"]))
              for rnd in range(count)}
    if report["rounds"] < 1:
        raise ValueError("at least one measured round is required")
    actual, signatures = {}, set()
    for sample in report["samples"]:
        key = sample["variant"], sample["phase"], sample["round"]
        if key in actual or key not in wanted:
            raise ValueError("duplicate or unexpected sample")
        if sample["returncode"] != 0 or not sample["output_matches"] or not sample["stdout_sha256"]:
            raise ValueError("sample failed output validation")
        needs_artifact = any("{output}" in arg for arg in variants[key[0]]["argv"])
        if needs_artifact and not sample.get("artifact_sha256"):
            raise ValueError("missing required artifact")
        signatures.add((sample["stdout_sha256"], sample.get("artifact_sha256")))
        for metric in ("wall_s", "user_s", "system_s", "peak_rss_kib"):
            value = sample[metric]
            if not math.isfinite(value) or value < 0 or (metric == "wall_s" and value == 0):
                raise ValueError("invalid measurement")
        actual[key] = sample
    if set(actual) != wanted or len(signatures) != 1:
        raise ValueError("missing samples or differing raw output hashes")
    for variant in variants.values():
        if variant.get("validated_executable_sha256", variant["executable_sha256"]) != variant["executable_sha256"]:
            raise ValueError("executable differs from validated build")
    return variants, {name: [actual[name, "measure", rnd] for rnd in range(report["rounds"])] for name in variants}


def compare_metadata(candidate, control):
    for key in ("cwd", "address_space_mib", "inputs_sha256"):
        if candidate.get(key) != control.get(key):
            raise ValueError(f"incomparable {key}: {candidate['name']}/{control['name']}")
    if candidate["argv"][1:] != control["argv"][1:]:
        raise ValueError("comparison uses different workload arguments")
    a, b = candidate.get("env", {}), control.get("env", {})
    return {"same_executable": candidate["executable_sha256"] == control["executable_sha256"],
            "environment_differences": {key: {"candidate": a.get(key), "control": b.get(key)}
                                        for key in sorted(a.keys() | b.keys()) if a.get(key) != b.get(key)}}


def summarize(report, pairs=None):
    variants, samples = validate(report)
    result = {"workload": report["workload"], "rounds": report["rounds"],
              "warmups_excluded": report["warmups"], "cpu": report["cpu"],
              "started_utc": report.get("started_utc"), "loadavg_before": report.get("loadavg_before"),
              "loadavg_after": report.get("loadavg_after"), "variants": {}, "comparisons": [], "notes": []}
    data = {}
    for name, rows in samples.items():
        values = {"wall_s": [r["wall_s"] for r in rows],
                  "cpu_s": [r["user_s"] + r["system_s"] for r in rows],
                  "rss_mib": [r["peak_rss_kib"] / 1024 for r in rows]}
        all_bdw = [bdw_diagnostics(r) for r in report["samples"] if r["variant"] == name]
        bdw_identity = {}
        if any(all_bdw):
            if not all(all_bdw) or len({tuple(r[k] for k in BDW_IDENTITY) for r in all_bdw}) != 1:
                raise ValueError(f"{name}: inconsistent BDWGC configuration or missing diagnostics")
            if any(r.get("gc_reports") for r in rows):
                raise ValueError("native and BDWGC collection metrics cannot be combined")
            bdw_identity = {"bdw_" + k: all_bdw[0][k] for k in BDW_IDENTITY}
            measured = [bdw_diagnostics(r) for r in rows]
            for field in BDW_COUNTERS:
                values["bdw_" + field] = [r[field] for r in measured]
        elif all(len(r.get("gc_reports", [])) == 1 for r in rows):
            for field in ("elapsed_ms", "collections", "heap_peak_mib", "last_live_mib"):
                values["gc_" + field] = [r["gc_reports"][0][field] for r in rows]
            values["gc_share_pct"] = [g / (t * 10) for g, t in zip(values["gc_elapsed_ms"], values["wall_s"])]
        else:
            result["notes"].append(f"{name}: no unambiguous native GC summary in every measured sample")
        data[name] = values
        result["variants"][name] = {key + "_median": statistics.median(v) for key, v in values.items()}
        result["variants"][name].update(bdw_identity, wall_s_min=min(values["wall_s"]), wall_s_max=max(values["wall_s"]))
        if min(values["wall_s"]) < 1:
            result["notes"].append(f"{name}: at least one native sample is shorter than one second")
        if variants[name].get("env", {}).get("PYSTACHY_GC") == "profile":
            result["notes"].append(f"{name}: detailed profiling enabled; do not combine with headline stats timings")
    contrasts = pairs if pairs is not None else [(a, b) for a, b in PAIRS if a in variants and b in variants]
    for candidate, control in contrasts:
        meta = compare_metadata(variants[candidate], variants[control])
        a, b = data[candidate], data[control]
        comparison = {"candidate": candidate, "control": control, **meta,
                      "rounds": list(range(report["rounds"])),
                      "wall": ratios(a["wall_s"], b["wall_s"]),
                      "cpu": ratios(a["cpu_s"], b["cpu_s"]),
                      "rss": ratios(a["rss_mib"], b["rss_mib"])}
        if "gc_elapsed_ms" in a and "gc_elapsed_ms" in b:
            deltas = [x - y for x, y in zip(a["gc_elapsed_ms"], b["gc_elapsed_ms"])]
            comparison.update(gc_ratio=ratios(a["gc_elapsed_ms"], b["gc_elapsed_ms"]),
                              gc_delta_ms={"paired": deltas, "median": statistics.median(deltas)})
        if candidate == "main_aa" and control == "main":
            if not meta["same_executable"] or meta["environment_differences"]:
                raise ValueError("main_aa is not an identical-binary, identical-setting A/A control")
            deviations = [abs(v - 1) * 100 for v in comparison["wall"]["paired"]]
            result["aa"] = {"geometric_mean_ratio": comparison["wall"]["geometric_mean"],
                            "median_absolute_paired_pct": statistics.median(deviations),
                            "max_absolute_paired_pct": max(deviations)}
        if meta["same_executable"] and not meta["environment_differences"] and candidate != "main_aa":
            result["notes"].append(f"{candidate}/{control}: identical executable bytes and settings; "
                                   "timing differences are control observations, not an optimization effect")
        if candidate == "block" and control == "default" and not meta["same_executable"]:
            result["notes"].append("block/default do not share executable bytes; tracing-order isolation is absent")
        result["comparisons"].append(comparison)
    return result


def markdown(case):
    def pct(value):
        return f"{(value - 1) * 100:+.2f}%"
    lines = ["## " + case["workload"], "", f"{case['rounds']} paired measured rounds; "
             f"{case['warmups_excluded']} warmup(s) per variant excluded; CPU {case['cpu']}.", "",
             "| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for name, v in case["variants"].items():
        gc = f"{v['gc_elapsed_ms_median']:.2f}" if "gc_elapsed_ms_median" in v else "—"
        share = f"{v['gc_share_pct_median']:.2f}%" if "gc_share_pct_median" in v else "—"
        lines.append(f"| {name} | {v['wall_s_median']:.4f} | {v['rss_mib_median']:.2f} | {gc} | {share} |")
    if any("bdw_mode" in v for v in case["variants"].values()):
        lines += ["", "| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
        for name, v in case["variants"].items():
            if "bdw_mode" in v:
                lines.append(f"| {name} | {v['bdw_mode']} | {v['bdw_incremental']} / {v['bdw_protection']} / {v['bdw_markers']} | "
                             f"{v['bdw_collections_median']:g} | {v['bdw_stopped_world_ms_median']:.3f} | "
                             f"{v['bdw_heap_peak_bytes_median'] / 1048576:.2f} | {v['bdw_allocated_bytes_median'] / 1048576:.2f} |")
        lines += ["", "BDWGC stopped-world intervals exclude collector work outside those intervals. "
                  "They are not native GC elapsed time or GC CPU time; no GC share is computed from them."]
    lines += ["", "| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for c in case["comparisons"]:
        w = c["wall"]
        rss = pct(c["rss"]["median"]) if c["rss"] else "—"
        lines.append(f"| {c['candidate']} / {c['control']} | {pct(w['geometric_mean'])} | {pct(w['median'])} | "
                     f"{pct(w['min'])} to {pct(w['max'])} | {w['lower_rounds']}/{case['rounds']} | {rss} |")
    if "aa" in case:
        aa = case["aa"]
        lines += ["", f"Identical-binary A/A: median absolute paired difference {aa['median_absolute_paired_pct']:.2f}%; "
                  f"largest observed difference {aa['max_absolute_paired_pct']:.2f}%. These are descriptive observations, not significance thresholds."]
    if case["notes"]:
        lines += ["", *["- " + note for note in case["notes"]]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--pair", action="append", help="candidate/control; repeat to override default contrasts")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    pairs = None
    if args.pair:
        pairs = [tuple(p.split("/")) for p in args.pair]
        if any(len(p) != 2 for p in pairs):
            parser.error("--pair must be candidate/control")
    cases = []
    for path in args.results:
        raw = path.read_bytes()
        case = summarize(json.loads(raw), pairs)
        case.update(source=str(path.resolve()), source_sha256=hashlib.sha256(raw).hexdigest())
        cases.append(case)
    print("Elapsed and RSS changes are candidate/control − 1; negative values mean lower values. "
          "Ranges are observed paired minima/maxima, not confidence intervals.\n")
    print("\n\n".join(map(markdown, cases)))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"schema_version": 1, "ratio_direction": "candidate/control",
                                        "warmups_excluded": True, "cases": cases}, indent=2) + "\n")


if __name__ == "__main__":
    main()
