#!/usr/bin/env python3
"""Run fresh final counts/timing/compile phases with the already-reviewed measurement core."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import measure_recovered as core
import replay_support as replay

def main():
    assert len(sys.argv) == 4 and sys.argv[1] in ("counts", "timings", "compile") and sys.argv[2] == "--output"
    phase, out = sys.argv[1], Path(sys.argv[3]).resolve()
    report = json.loads((out / "measurement.json").read_text())
    assert report["phases"]["prepare"]["status"] == "passed" and phase not in report["phases"]
    core.HOMES = {name: Path(report["source_identities"][name]["directory"]) for name in ("main", "eca", "candidate")}
    identity = replay.digest(Path(__file__))
    report.setdefault("phase_launchers", {})[phase] = {"path": str(Path(__file__).resolve()), "sha256": identity,
                                                        "scope": "Only variant/home binding changes; reviewed core algorithms and helpers remain unchanged."}
    replay.save_json(out / "measurement.json", report)
    def verify_identities():
        for name, home in core.HOMES.items():
            assert replay.source_identity(home) == report["source_identities"][name], (name, "full source identity changed")
            assert replay.digest(report["native_compilers"][name]["path"]) == report["native_compilers"][name]["sha256"], (name, "native compiler changed")
        assert replay.digest(Path(__file__)) == identity, "phase launcher changed"
    try:
        verify_identities()
        core.main()
        verify_identities()
    except BaseException as error:
        current = json.loads((out / "measurement.json").read_text())
        record = current["phases"].setdefault(phase, {})
        if record.get("status") == "passed":
            record["core_status_before_provenance_failure"] = "passed"
        record.update(status="failed", launcher_error=repr(error), finished_utc=datetime.now(timezone.utc).isoformat())
        replay.save_json(out / "measurement.json", current)
        raise
    current = json.loads((out / "measurement.json").read_text())
    current["phase_launchers"][phase]["full_commit_tree_status_inputs_native_identity_pre_post_passed"] = True
    replay.save_json(out / "measurement.json", current)

if __name__ == "__main__":
    main()
