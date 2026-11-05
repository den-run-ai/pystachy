"""Preserve complete bootstrap reports/logs with shared input inventories."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+", help="run directories, in measurement order")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources, tools, reports, rows = {}, {}, [], []
    for directory in args.runs:
        report = json.loads((directory / "report.json").read_text())
        source = report.pop("source")
        source_id = source["sha256"]
        sources[source_id] = source
        toolset = report.pop("tools")
        tool_id = hashlib.sha256(json.dumps(toolset, sort_keys=True).encode()).hexdigest()
        tools[tool_id] = toolset
        report.update(source_inventory=source_id, tool_inventory=tool_id)
        for step in report["steps"]:
            if "log" in step:
                data = Path(step["log"]).read_bytes()
                step["log_sha256"] = hashlib.sha256(data).hexdigest()
                step["log_content"] = data.decode("utf-8", errors="replace")
        reports.append(report)
        options = report["options"]
        steps = {step["name"]: step for step in report["steps"]}
        rows.append({
            "run": directory.name, "status": report["status"], "variant": report["variant"],
            "jobs": options["jobs"], "build_jobs": options["build_jobs"],
            "stage1_opt": options["stage1_opt"], "partitions": options["partitions"],
            "runtime_c_cache": options["runtime_c_cache"],
            "wall_seconds": report["wall_seconds"], "command_cpu_seconds": report["cpu_seconds"],
            "largest_command_max_rss_mib": report["largest_command_max_rss_bytes"] / 1048576,
            "build1_seconds": steps["build1"].get("wall_seconds"),
            "build2_seconds": steps["build2"].get("wall_seconds"),
            "final_compiler_ir_seconds": steps["ir3"].get("wall_seconds"),
            "final_compiler_bytes": report.get("binaries", {}).get("pystachy2", {}).get("bytes"),
            "compiler_frontend_emissions": report["planned_work"]["compiler_frontend_emissions"],
        })
    args.output.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "source_inventories": sources, "tool_inventories": tools, "runs": reports}
    (args.output / "linux-llvm18.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with (args.output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
