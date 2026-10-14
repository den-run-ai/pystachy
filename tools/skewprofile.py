"""Record one receiver parameter for the opt-in native caller-specialization probe.

This deliberately profiles one named Python function in the current thread. It
does not infer annotations, inspect containers or run user-defined type hooks.
Every matching call counts in the denominator, including unrepresentable types.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import sys


HEADER = "pystachy-skew-v1"
MAX_CLASSES = 64


def identity(cls):
    # Custom metaclasses can install descriptors even on __module__/__qualname__.
    # They are outside Pystachy's class subset; count them without invoking hooks.
    if type(cls) is not type:
        return "<other>"
    module = type.__getattribute__(cls, "__module__")
    name = type.__getattribute__(cls, "__qualname__")
    if type(module) is not str or type(name) is not str or len(module) + len(name) > 1024:
        return "<other>"
    parts = name.split(".") if module == "__main__" else (module + "." + name).split(".")
    return ".".join(parts) if all(p.isidentifier() for p in parts) else "<other>"


class Census:
    def __init__(self, function, parameter):
        self.function = function
        self.parameter = parameter
        self.counts = Counter()
        self.total = 0

    def observe(self, frame, event, arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        if type(module) is not str:
            return
        function = frame.f_code.co_qualname
        name = function if module == "__main__" else module + "." + function
        if name != self.function:
            return
        self.total += 1
        name = identity(type(frame.f_locals[self.parameter])) if self.parameter in frame.f_locals else "<other>"
        if name not in self.counts and len(self.counts) >= MAX_CLASSES:
            name = "<other>"
        self.counts[name] += 1

    def rows(self):
        if self.total < 100 or not self.counts:
            return []
        name, hits = self.counts.most_common(1)[0]
        if name == "<other>" or hits * 10 < self.total * 9:
            return []
        return ["\t".join([self.function, self.parameter, name, str(hits), str(self.total)])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--function", required=True, help="batch for the main script, or module.function")
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("program", type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    census = Census(args.function, args.parameter)
    old_argv, old_path, old_profile = sys.argv, list(sys.path), sys.getprofile()
    try:
        sys.argv = [str(args.program), *args.arguments]
        sys.path.insert(0, str(args.program.resolve().parent))
        sys.setprofile(census.observe)
        runpy.run_path(str(args.program), run_name="__main__")
    finally:
        sys.setprofile(old_profile)
        sys.argv, sys.path[:] = old_argv, old_path
    rows = census.rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join([HEADER, *rows]) + "\n")
    print(json.dumps({"function": args.function, "parameter": args.parameter,
                      "calls": census.total, "classes": dict(census.counts),
                      "selected": rows, "source_sha256": hashlib.sha256(args.program.read_bytes()).hexdigest(),
                      "python": sys.version.split()[0]}, sort_keys=True))


if __name__ == "__main__":
    main()
