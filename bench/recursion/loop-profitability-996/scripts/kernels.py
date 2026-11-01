"""Serial whole-process AOT instruction checks of existing recursion kernels."""
import argparse
import json
import os
from pathlib import Path
import re

import measure as m

CASES = {"ordinary_calls": 1000000, "object_calls": 10000, "json_calls": 1000}


def results(output):
    lines = output.splitlines()
    if len(lines) != 8 or not lines[0].startswith("warm "):
        raise ValueError(output)
    return [lines[0]] + [line.split()[0] for line in lines[1:]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roles", nargs="+", choices=m.ROLES)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    report = {"scope": "whole-process AOT including warmup and seven kernel iterations",
              "controller_sha256": m.digest(Path(__file__)),
              "measure_sha256": m.digest(Path(m.__file__)), "roles": {}}
    output = m.OUT / ("kernels-" + "-".join(args.roles) + ".json")
    for role in args.roles:
        before = m.manifest(role)
        cases = {}
        report["roles"][role] = {"source_manifest": before, "cases": cases}
        directory = m.OUT / role
        directory.mkdir(parents=True, exist_ok=True)
        for case, n in CASES.items():
            source = m.SOURCES / "bench/recursion" / (case + ".py")
            expected = results(m.execute([m.PY, source, str(n)], "baseline")["stdout"])
            binary = directory / case
            build = m.execute([m.PY, m.ROLES[role] / "pystachy.py", "build", source,
                               "-o", binary], role)
            native = m.execute([binary, str(n)], role)
            if results(native["stdout"]) != expected:
                raise ValueError((role, case, native))
            profile = m.execute(["valgrind", "--tool=callgrind", "--compress-strings=no",
                                 "--compress-pos=no", "--callgrind-out-file=" + str(directory / (case + ".callgrind")),
                                 binary, str(n)], role, 600)
            if results(profile["stdout"]) != expected:
                raise ValueError((role, case, profile))
            summary = re.findall(r"^summary: (\d+)$", (directory / (case + ".callgrind")).read_text(), re.M)
            if len(summary) != 1:
                raise ValueError(summary)
            cases[case] = {"n": n, "source": str(source), "source_sha256": m.digest(source),
                           "binary_sha256": m.digest(binary), "binary_bytes": binary.stat().st_size,
                           "expected": expected, "build": build, "native": native,
                           "profile": profile, "instructions": int(summary[0])}
            m.save(output, report)
            print(role, case, summary[0], flush=True)
        if before != m.manifest(role):
            raise ValueError("source changed during measurements")
    report["complete"] = True
    m.save(output, report)


if __name__ == "__main__":
    main()
