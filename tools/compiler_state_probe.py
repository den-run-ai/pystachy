"""Hosted observation of successful dry() boundaries; not a rollback implementation.

Run on one small input per process. All reflection stays outside the compiler subset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.driver import compile_program
from src.pystachy_compiler.gen import Gen

ROOT = Path(__file__).resolve().parent.parent


class Snapshot:
    """Compare values, identities, aliases and nested contents, including cycles.

    Keep references alive so an object freed during the probe cannot have its id
    reused. Unknown object types fail visibly instead of disappearing from the audit.
    This is deliberately expensive debug tooling, never a compiler hot-path check.
    """

    def __init__(self, roots):
        self.keep = []
        self.values = {name: self.freeze(value, set()) for name, value in roots.items()}

    def freeze(self, value, seen):
        if type(value) in (type(None), bool, int, str, bytes):
            return (type(value).__name__, value)
        if type(value) is float:
            return ("float", value.hex())
        ident = id(value)
        if ident in seen:
            return ("ref", ident)
        seen.add(ident)
        self.keep.append(value)
        if type(value) in (list, tuple):
            data = tuple(self.freeze(item, seen) for item in value)
        elif type(value) is dict:
            # Order can affect deterministic symbol allocation; preserve it too.
            data = tuple((self.freeze(k, seen), self.freeze(v, seen)) for k, v in value.items())
        elif type(value).__module__.startswith("src.pystachy_compiler."):
            data = tuple((k, self.freeze(v, seen)) for k, v in vars(value).items())
        else:
            raise TypeError(f"unhandled state type: {type(value)}")
        return (type(value).__module__, type(value).__name__, ident, data)

    def changed(self, roots):
        after = Snapshot(roots)
        return sorted(name for name in self.values.keys() | after.values.keys()
                      if self.values.get(name) != after.values.get(name))


def emission_roots(g):
    return {"blk": g.blk, "fn.blocks": g.fn.blocks, "fn.loops": g.fn.loops,
            "cur": g.cur, "term": g.term, "line": g.line, "drying": g.drying}


def probe(path, observe=True):
    """Observe actual compiler walks, retaining discoveries rather than undoing them."""
    events = []
    passes = []
    original = Gen.dry
    program = Gen.program

    def observed_program(g, mods):
        event = {"declined_in": sorted(g.xnot), "outcome": "aborted"}
        passes.append(event)
        try:
            result = program(g, mods)
        except BaseException:
            event.update(new_declines=sorted(g.newx), global_types=dict(g.gtypes))
            raise
        event.update(outcome="returned", new_declines=sorted(g.newx),
                     global_types=dict(g.gtypes))
        return result

    def checked(g, node, want=""):
        local = Snapshot(emission_roots(g))
        all_state = Snapshot(vars(g))
        event = {"line": node.line, "depth": g.drying, "outcome": "aborted"}
        events.append(event)
        # An exception abandons the pass. Never catch one and resume compilation.
        result = original(g, node, want)
        changed = local.changed(emission_roots(g))
        if changed:
            raise AssertionError(f"successful dry changed saved emission: {changed}")
        event.update(outcome="returned", result=result,
                     retained=all_state.changed(vars(g)))
        return result

    path = Path(path).resolve()
    with patch.object(Gen, "dry", checked if observe else original), \
            patch.object(Gen, "program", observed_program):
        ir = compile_program(str(path), path.read_text(encoding="latin-1"),
                             [str(path.parent), str(ROOT / "lib")], "")
    return {"case": str(path.relative_to(ROOT)), "observed": observe,
            "ir_sha256": hashlib.sha256(ir.encode()).hexdigest(),
            "passes": passes, "dry_calls": events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(probe(args.path, not args.baseline), indent=2))


if __name__ == "__main__":
    main()
