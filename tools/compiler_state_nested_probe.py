"""Measure nested function-state boundaries with the real save/enter/restore.

This hosted research probe simulates operations in interrupted and nested functions;
it does not compile a program or prove which fields belong to a function. Findings
are reported normally; --strict makes any measured violation fail the command.
"""
import argparse
import json

from compiler_state_probe import Gen, Snapshot
from src.pystachy_compiler.ir import FnInfo, Val
from src.pystachy_compiler.syntax import Node

FIELDS = ("drying", "carried", "nonecmp", "fieldcmp", "cmpnode", "stkkey", "reflcopies", "stmtexpr")


def poison(g, serial, *, callee=False):
    """Give each interrupted operation distinct state, including mutable records."""
    g.drying = serial + 10
    g.carried = Val(f"%caller{serial}", "int")
    g.nonecmp = not callee
    g.fieldcmp = not callee
    g.cmpnode = Node("name", f"comparison{serial}", serial)
    g.stkkey = Node("tuple", f"key{serial}", serial)
    g.reflcopies = serial + 20
    g.stmtexpr = Node("expr", f"statement{serial}", serial)
    # Established saved fields are controls for the measurement mechanism.
    g.line = serial + 100
    g.ltype = {"marker": f"caller{serial}"}


def neutral(g):
    """Expected entry state for these specific operation fields, not a full schema."""
    missing = object()
    values = {name: getattr(g, name, missing) for name in (*FIELDS, "line", "ltype")}
    carried = values["carried"]
    return {
        "drying": values["drying"] == 0,
        "carried": isinstance(carried, Val) and all(getattr(carried, name, missing) == ""
                                                   for name in ("v", "t", "infer_from")),
        "nonecmp": values["nonecmp"] is False,
        "fieldcmp": values["fieldcmp"] is False,
        "cmpnode": values["cmpnode"] is g.nokey,
        "stkkey": values["stkkey"] is g.nokey,
        "reflcopies": values["reflcopies"] == 1,
        "stmtexpr": values["stmtexpr"] is None,
        "line": values["line"] == 0,
        "ltype": values["ltype"] == {},
    }


def measure(depth, fields=FIELDS):
    if not 1 <= depth <= 8:
        raise ValueError("depth must be between 1 and 8")
    g = Gen()
    boundaries = []

    def roots():
        return {field: getattr(g, field) for field in fields if hasattr(g, field)}

    def visit(level):
        poison(g, level)
        caller = Snapshot(roots())
        frame = g.save()
        f = FnInfo(f"nested{level}", f"@f.nested{level}", Node("probe", "", 0), "")
        g.enter(f, [])
        entry = neutral(g)
        event = {"level": level, "entry_leaks": sorted(field for field in fields if not entry[field])}
        boundaries.append(event)
        if level < depth:
            visit(level + 1)
        # A nested function may change its own state before returning to its caller.
        poison(g, level + depth, callee=True)
        g.restore(frame)
        event["caller_restore_changes"] = caller.changed(roots())

    visit(1)
    return {"depth": depth, "fields": list(fields), "boundaries": boundaries}


def has_violations(reports):
    return any(event["entry_leaks"] or event["caller_restore_changes"]
               for report in reports for event in report["boundaries"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 2, 3], choices=range(1, 9))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    reports = [measure(depth) for depth in args.depths]
    print(json.dumps({"reports": reports, "violations": has_violations(reports)}, indent=2))
    return int(args.strict and has_violations(reports))


if __name__ == "__main__":
    raise SystemExit(main())
