"""Audit archived byte-BPE evidence without executing measured programs.

Run from any directory with Python 3.11+. This checks recorded hashes, strict
timing rows, sample counts, full-state witnesses and summary arithmetic. It does
not rerun a benchmark or prove that historical binaries can be rebuilt bitwise.
"""
import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics


HERE = Path(__file__).resolve().parent
TIMINGS = ("first_train", "second_train", "train", "encode", "decode")
MAIN_MODES = (
    "cpython_original", "cpython_adapted", "cython_original", "cython_scalar",
    "cython_adapted", "mypyc_original", "pypy_original", "pystachy_aot",
    "pystachy_scalar_tuple",
)
SECONDARY_MODES = ("pystachy_jit", "pystachy_jit_inline100k", "pystachy_aot_gc8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def parse_times(text, expected=TIMINGS):
    rows = text.splitlines()
    require(len(rows) == len(expected), "incorrect timing row count")
    times = {}
    for row in rows:
        fields = row.split()
        require(len(fields) == 2, f"invalid timing row: {row!r}")
        key, raw_value = fields
        require(key in expected and key not in times, f"unknown or duplicate timing key: {key}")
        value = float(raw_value)
        require(math.isfinite(value) and value > 0, f"invalid timing value: {raw_value}")
        times[key] = value
    require(set(times) == set(expected), "incomplete timing rows")
    return times


def same_number(actual, expected, message):
    require(isinstance(actual, (int, float)) and math.isfinite(actual), message)
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0), message)


def check_series(report, oracle_sha, modes, processes):
    require(report["status"] == "passed", "incomplete historical series")
    require(set(report["samples"]) == set(modes), "unexpected series modes")
    workload = report["workload"]
    expected_workload = {
        "corpus_bytes": 31206, "vocab_size": 1024, "processes": processes,
        "train_warmups": 2, "encode_warmups": 20, "decode_warmups": 100,
        "train_loops": 1, "encode_loops": 50, "decode_loops": 200,
    }
    require(all(workload[key] == value for key, value in expected_workload.items()),
            "historical workload changed")
    require(report["oracle_sha256"] == oracle_sha, "series oracle changed")
    require(len(report["order"]) == processes, "missing process round")
    for order in report["order"]:
        require(len(order) == len(modes) and set(order) == set(modes), "invalid mode order")
    require(set(report["summary"]) == set(modes), "unexpected summary modes")
    for mode, rows in report["samples"].items():
        require(len(rows) == processes, f"incorrect sample count: {mode}")
        require(sorted(row["round"] for row in rows) == list(range(processes)),
                f"missing or duplicate round: {mode}")
        for row in rows:
            require(row["stdout_sha256"] == oracle_sha, f"state witness mismatch: {mode}")
            require(row["command"][-3:] == ["1024", "50", "200"], "command loop mismatch")
            times = parse_times(row["stderr"])
            for stage in TIMINGS:
                divisor = workload.get(stage + "_loops", 1)
                same_number(row[stage + "_seconds"], times[stage] / divisor,
                            f"incorrect divisor: {mode}/{stage}")
        expected_metrics = {stage + "_seconds" for stage in TIMINGS}
        expected_metrics.update(("wall_seconds", "cpu_seconds", "sampled_main_rss_kib"))
        require(set(report["summary"][mode]) == expected_metrics, "summary metric mismatch")
        for metric, summary in report["summary"][mode].items():
            values = [row[metric] for row in rows]
            require(all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0
                        for value in values), f"invalid {mode}/{metric} sample")
            expected = {"median": statistics.median(values), "min": min(values), "max": max(values)}
            require(set(summary) == set(expected), "summary statistic mismatch")
            for statistic, value in expected.items():
                same_number(summary[statistic], value, f"incorrect {mode}/{metric}/{statistic}")


def reconstructed_sources(repo):
    upstream = (repo / "examples/byte_bpe/upstream/bpe_tokeniser.py").read_text(encoding="utf-8")
    adapted = (repo / "bench/pyperformance/bpe_tokeniser.py").read_text(encoding="utf-8")
    benchmark = ast.parse((repo / "examples/byte_bpe/benchmark.py").read_text(encoding="utf-8"))
    pattern = next(ast.literal_eval(node.value) for node in benchmark.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "PATTERN"
                           for target in node.targets))
    wanted = {"SimpleBytePairEncoding", "bpe_encode", "bpe_train"}
    nodes = [node for node in ast.parse(upstream).body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in wanted]
    require(len(nodes) == len(wanted) and {node.name for node in nodes} == wanted,
            "upstream kernel extraction changed")
    original = ("from __future__ import annotations\nimport collections\nimport re\n\n" +
                "\n\n".join(ast.get_source_segment(upstream, node) for node in nodes) +
                f"\n\nBPE_PATTERN = {pattern!r}\n")

    def replace_once(source, old, new):
        require(source.count(old) == 1, f"source adaptation no longer unique: {old}")
        return source.replace(old, new)

    cython_scalar = replace_once(upstream, "from __future__ import annotations\n",
                                 "from __future__ import annotations\n\nimport cython\n")
    cython_scalar = replace_once(cython_scalar, "def bpe_encode(",
                                 "@cython.locals(i=cython.Py_ssize_t, b=cython.uchar)\ndef bpe_encode(")
    cython_scalar = replace_once(cython_scalar, "def bpe_train(",
                                 "@cython.locals(i=cython.Py_ssize_t, token=cython.Py_ssize_t)\ndef bpe_train(")
    mypyc = replace_once(upstream, "stats = collections.Counter()",
                         "stats: collections.Counter[tuple[bytes, bytes]] = collections.Counter()")
    scalar_tuple = replace_once(adapted, "if (word[i], word[i + 1]) == most_common_pair:",
                                "if word[i] == most_common_pair[0] and word[i + 1] == most_common_pair[1]:")
    return pattern, {"original_extracted": original, "cython_original": upstream,
                     "cython_scalar": cython_scalar, "cython_adapted": adapted,
                     "mypyc_original": mypyc, "pystachy_scalar_tuple": scalar_tuple}


def check_diagnostics(phases, warmup, six_line_sha):
    for report, modes, loops, expected in (
        (phases, ("cpython_original", "pypy_original", "pystachy_aot"), 50,
         ("regex", "utf8", "merge", "full")),
        (warmup, ("pypy_original", "pystachy_aot"), 200, ("full",)),
    ):
        require(report["status"] == "passed", "incomplete encoding diagnostic")
        require(report["processes_per_mode"] == 3, "diagnostic process count changed")
        require(len(report["runs"]) == len(modes) * 3, "diagnostic sample count changed")
        for mode in modes:
            rows = [row for row in report["runs"] if row["mode"] == mode]
            require(sorted(row["round"] for row in rows) == [0, 1, 2], "diagnostic round mismatch")
            for row in rows:
                require(row["returncode"] == 0 and row["stdout_sha256"] == six_line_sha,
                        "diagnostic output mismatch")
                require(row["stdout_lines"] == 6 and row["first_four_match_existing_oracle"]
                        and row["six_lines_match_pristine_cpython"], "diagnostic witness incomplete")
                times = parse_times(row["stderr"], expected)
                for phase in expected:
                    actual = (row["per_operation_seconds"][phase] if len(expected) > 1
                              else row["seconds_per_full_encode"])
                    same_number(actual, times[phase] / loops, "diagnostic divisor mismatch")
            for phase in expected:
                values = [(row["per_operation_seconds"][phase] if len(expected) > 1
                           else row["seconds_per_full_encode"]) * 1000 for row in rows]
                summary = report["summary"][mode][phase] if len(expected) > 1 else report["summary"][mode]
                same_number(summary["median_ms"], statistics.median(values), "diagnostic median mismatch")
                require(len(summary["range_ms"]) == 2, "diagnostic range missing")
                for actual, target in zip(summary["range_ms"], (min(values), max(values)), strict=True):
                    same_number(actual, target, "diagnostic range mismatch")
                require(len(summary["samples_ms"]) == len(values), "diagnostic sample list mismatch")
                for actual, target in zip(summary["samples_ms"], values, strict=True):
                    same_number(actual, target, "diagnostic sample list mismatch")
        require(report["source_hashes_after"] == report["source_hashes"], "diagnostic input changed")
    require(phases["warmups_per_phase"] == 20 and phases["measured_loops_per_phase"] == 50,
            "phase schedule changed")
    require(warmup["warmups"] == 200 and warmup["measured_loops"] == 200,
            "extended warmup schedule changed")
    require(warmup["binary_sha256"] == phases["binary_sha256"] == warmup["binary_sha256_after"],
            "extended warmup used a different binary")
    by_mode = {mode: {row["round"]: row["seconds_per_full_encode"]
                      for row in warmup["runs"] if row["mode"] == mode}
               for mode in ("pypy_original", "pystachy_aot")}
    ratios = [by_mode["pystachy_aot"][i] / by_mode["pypy_original"][i] for i in range(3)]
    summary = warmup["summary"]["pystachy_over_pypy_seconds_ratio"]
    require(len(summary["paired_ratios"]) == 3, "missing paired ratio")
    for actual, expected in zip(summary["paired_ratios"], ratios, strict=True):
        same_number(actual, expected, "extended warmup paired ratio mismatch")
    same_number(summary["paired_median_ratio"], statistics.median(ratios), "paired median mismatch")
    same_number(summary["ratio_of_medians"],
                statistics.median(by_mode["pystachy_aot"].values()) /
                statistics.median(by_mode["pypy_original"].values()), "ratio of medians mismatch")


def summary_csv(main, secondary):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    columns = ["series", "mode", "processes"]
    for stage in ("train", "encode", "decode"):
        columns += [f"{stage}_{statistic}_ms" for statistic in ("median", "min", "max")]
    columns += ["sampled_main_rss_median_mib", "whole_warmed_process_median_seconds"]
    writer.writerow(columns)
    for name, report in (("main", main), ("secondary", secondary)):
        for mode, summary in report["summary"].items():
            row = [name, mode, report["workload"]["processes"]]
            row += [f"{summary[stage + '_seconds'][statistic] * 1000:.9f}"
                    for stage in ("train", "encode", "decode")
                    for statistic in ("median", "min", "max")]
            row += [f"{summary['sampled_main_rss_kib']['median'] / 1024:.9f}",
                    f"{summary['wall_seconds']['median']:.9f}"]
            writer.writerow(row)
    return output.getvalue()


def verify_all(here=HERE, check_csv=True):
    repo = here.parents[3]
    manifest = load(here / "manifest.json")
    for group, root in (("recorded_files", here), ("generated_files", here), ("repository_inputs", repo)):
        for name, entry in manifest[group].items():
            data = (root / name).read_bytes()
            require(len(data) == entry["bytes"] and sha(data) == entry["sha256"], f"hash mismatch: {name}")
    pattern, sources = reconstructed_sources(repo)
    for mode, digest in manifest["generated_kernel_identities"].items():
        require(sha(sources[mode].encode()) == digest, f"source adaptation mismatch: {mode}")
    oracle = (here / "full-output-oracle.txt").read_bytes()
    oracle_sha = sha(oracle)
    lines = oracle.decode().splitlines()
    require(len(lines) == 4, "incomplete primary oracle")
    ranks, tokens, decoded_bytes, decoded = map(ast.literal_eval, lines)
    require(len(ranks) == 1024 and len(tokens) == 10335, "unexpected oracle dimensions")
    corpus = (repo / "bench/pyperformance/data/frankenstein_intro.txt").read_bytes()
    require(decoded_bytes == corpus and decoded.encode("utf-8") == corpus, "oracle corpus mismatch")
    decoder = {token: word for word, token in ranks}
    require(len(decoder) == 1024 and b"".join(decoder[token] for token in tokens) == corpus,
            "oracle token decoding mismatch")
    main, secondary = (load(here / name) for name in ("comparison.json", "secondary.json"))
    check_series(main, oracle_sha, MAIN_MODES, 5)
    check_series(secondary, oracle_sha, SECONDARY_MODES, 3)
    for report in (main, secondary):
        require(report["git_revision"] == manifest["measured_revision"], "measured revision mismatch")
        require(report["created_utc"].startswith(manifest["measured_date_utc"]), "measured date mismatch")
    require(main["input_sha256"] == secondary["input_sha256"], "secondary input identity changed")
    historical_inputs = {name.rsplit("/", 1)[-1]: digest for name, digest in main["input_sha256"].items()}
    require(historical_inputs["stages_warm.py"] == sha((here / "measured/stages_warm.py.txt").read_bytes()),
            "measured stage driver mismatch")
    require(historical_inputs["manifest.json"] == sha((here / "comparator-manifest.json").read_bytes()),
            "comparator manifest mismatch")

    state = {"ranks": [[base64.b64encode(key).decode(), value] for key, value in ranks],
             "tokens": tokens, "decoded": decoded, "bytes": base64.b64encode(decoded_bytes).decode()}
    serialized = json.dumps(state, ensure_ascii=False).encode()
    comp_correctness = load(here / "comparator-correctness.json")
    comp_manifest = load(here / "comparator-manifest.json")
    require(set(comp_correctness["modes"]) == {"original", *comp_manifest["modes"]},
            "missing comparator correctness evidence")
    for mode, record in comp_correctness["modes"].items():
        require(record["recorded_json_sha256"] == sha(serialized)
                and record["recorded_json_bytes"] == len(serialized), "comparator state mismatch")
        require(record["full_state_matches_oracle"] and record["fixture_stdout_matches"],
                "incomplete comparator correctness")
        if mode != "original":
            built = comp_manifest["modes"][mode]
            require(built["correctness_sha256"] == sha(serialized), "comparator manifest state mismatch")
            require(built["source_sha256"] == sha(sources[mode].encode()), "comparator source mismatch")
            require(built["module"].endswith(".so") and
                    record["log_tail"] == f"module {built['module']}\nfull corpus validated\n",
                    "native comparator import evidence missing")
            require(main["input_sha256"][built["module"]] == built["module_sha256"],
                    "different comparator binary measured")
    for inputs in load(here / "measured/comparator-build-inputs.json").values():
        for entry in inputs.values():
            require(sha(entry["contents"].encode()) == entry["sha256"], "build input hash mismatch")
    fixtures = {"cpython": (here / "fixture-output.txt").read_bytes(),
                "pypy": (here / "fixture-pypy-output.txt").read_bytes()}
    require(fixtures["pypy"].replace(b"arg is an empty sequence", b"max() iterable argument is empty")
            == fixtures["cpython"], "unexpected PyPy fixture difference")
    for record in load(here / "correctness-final.json"):
        require(record["returncode"] == 0 and record["stderr"] == "", "fixture execution failed")
        expected = (b"" if record["name"].startswith("build-")
                    else fixtures["pypy" if "pypy" in record["name"] else "cpython"])
        require(record["stdout_sha256"] == sha(expected), "fixture witness mismatch")

    words = re.findall(pattern, decoded)
    six_lines = oracle + (str(words) + "\n" + str([word.encode("utf-8") for word in words]) + "\n").encode()
    phases, warmup = (load(here / name) for name in ("encoding-phases.json", "warmup-sensitivity.json"))
    check_diagnostics(phases, warmup, sha(six_lines))
    require(phases["source_hashes"]["driver"] == sha((here / "measured/encoding_phases.py.txt").read_bytes()),
            "encoding phase driver mismatch")
    historic_root = Path(main["environment"]["PYSTACHY_HOME"]).parent
    for mode, identity in manifest["assembly_source_identities"].items():
        binary_sha = (phases["binary_sha256"] if mode == "phases"
                      else main["input_sha256"][str(historic_root / identity["binary"])])
        require(binary_sha == identity["binary_sha256"], "disassembly binary identity mismatch")
        require(main["input_sha256"][str(historic_root / identity["kernel"])] == identity["kernel_sha256"],
                "disassembly kernel identity mismatch")
    scalar = load(here / "scalar-tuple-manifest.json")
    require(scalar["source_sha256"] == sha(sources["pystachy_scalar_tuple"].encode()), "tuple variant mismatch")
    require(scalar["stages_sha256"] == manifest["assembly_source_identities"]["scalar_tuple"]["binary_sha256"],
            "different tuple variant measured")
    for record in scalar["runs"]:
        require(record["returncode"] == 0, "tuple variant validation failed")
        if "stdout_matches_expected" in record:
            expected = oracle if record["name"] == "native-full-corpus" else fixtures["cpython"]
            require(record["stdout_matches_expected"] and record["stdout_sha256"] == sha(expected),
                    "tuple variant witness mismatch")
    probe_tree = ast.parse((here / "measured/probe_language_gaps.py.txt").read_text())
    probe_inputs = {node.targets[0].id: ast.literal_eval(node.value) for node in probe_tree.body
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in ("variations", "extras")}
    probes = load(here / "language-probes.json")
    require(len(probes) == len(probe_inputs["variations"]) + len(probe_inputs["extras"]),
            "missing language probe")
    for record in probes:
        name = record["name"]
        if name in probe_inputs["variations"]:
            source = sources["cython_adapted"]
            change = probe_inputs["variations"][name]
            if change:
                require(source.count(change[0]) == 1, "nonunique language probe change")
                source = source.replace(*change)
        else:
            source = probe_inputs["extras"][name]
        require(sha(source.encode()) == record["source_sha256"], f"language probe source mismatch: {name}")
    operations = load(here / "operations.json")
    require(operations["stdout_sha256"] == oracle_sha and
            operations["complete_stdout_matches_pinned_pristine_oracle"], "operation-count oracle mismatch")
    counts, derived = operations["counts"], operations["derived"]
    require(derived["training_tuple_allocation_sites_executed_in_raw_ir"] ==
            counts["training_pair_visits"] + counts["training_rebuild_pair_comparisons"], "tuple count mismatch")
    require(derived["training_redundant_pair_key_allocations_lower_bound"] ==
            counts["training_pair_visits"] - counts["training_unique_key_insertions"], "key count mismatch")
    require(derived["encode_optional_int_box_sites_executed_in_raw_ir"] ==
            counts["encode_successful_rank_lookups"] + 2 * counts["encode_new_minimum_updates"],
            "optional box count mismatch")
    if check_csv:
        require((here / "summary.csv").read_text() == summary_csv(main, secondary), "summary CSV is stale")
    baseline = {row["round"]: row["train_seconds"] for row in main["samples"]["pystachy_aot"]}
    variant = {row["round"]: row["train_seconds"] for row in main["samples"]["pystachy_scalar_tuple"]}
    ratios = [baseline[i] / variant[i] for i in range(5)]
    return {"main_samples": 45, "secondary_samples": 9, "phase_samples": 9, "extended_warmup_samples": 6,
            "full_oracle_sha256": oracle_sha, "scalar_tuple_training_paired_ratios": ratios,
            "scalar_tuple_training_paired_median": statistics.median(ratios),
            "scalar_tuple_training_ratio_of_medians": statistics.median(baseline.values()) /
            statistics.median(variant.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-summary", action="store_true", help="regenerate summary.csv after verification")
    args = parser.parse_args()
    result = verify_all(check_csv=not args.write_summary)
    if args.write_summary:
        (HERE / "summary.csv").write_text(summary_csv(load(HERE / "comparison.json"),
                                                    load(HERE / "secondary.json")))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
