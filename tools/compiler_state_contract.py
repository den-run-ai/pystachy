"""Hosted structural check for Frame's manual field transfers (#767).

This checks the declared Frame contract, not whether every Gen field that ought
to be function-scoped has been declared there. It is not a rollback verifier.
"""
import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "pystachy_compiler"


def member(tree, name):
    found = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name]
    if len(found) != 1:
        raise ValueError(f"expected one definition of {name}, found {len(found)}")
    return found[0]


def attribute(node, owner):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == owner:
        return node.attr
    return None


def assignments(fn, owner):
    """List every direct attribute assignment, retaining duplicates and its RHS."""
    result = []
    for node in ast.walk(fn):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for target in targets:
            field = attribute(target, owner)
            if field is not None:
                result.append((field, node.value))
    return result


def validate_sources(gen, ir, emission):
    """Return errors for the current explicit assignment/constructor convention."""
    try:
        gen_init = member(member(ast.parse(gen), "Gen"), "__init__")
        frame_init = member(member(ast.parse(ir), "Frame"), "__init__")
        emitted = ast.parse(emission)
        save = member(emitted, "gen_save")
        restore = member(emitted, "gen_restore")
    except (ValueError, SyntaxError) as exc:
        return [str(exc)]
    errors = []
    gen_fields = {name for name, _ in assignments(gen_init, "self")}
    frame = assignments(frame_init, "self")
    frame_fields = {name for name, _ in frame}
    if not all(isinstance(n, (ast.Assign, ast.AnnAssign))
               and len(n.targets if isinstance(n, ast.Assign) else [n.target]) == 1
               and attribute(n.targets[0] if isinstance(n, ast.Assign) else n.target, "self") is not None
               and n.value is not None for n in frame_init.body):
        errors.append("Frame initialization must use unconditional direct assignments")
    for name, count in Counter(name for name, _ in frame).items():
        if count != 1:
            errors.append(f"Frame initializes {name} {count} times")
    for name in sorted(frame_fields - gen_fields):
        errors.append(f"Frame field {name} is absent from Gen.__init__")

    # These three fields are transferred by construction; all others by assignment.
    seeds = ["curfn", "fn", "blk"]
    args = frame_init.args
    if ([arg.arg for arg in args.args] != ["self", *seeds]
            or args.posonlyargs or args.kwonlyargs or args.defaults or args.vararg or args.kwarg):
        errors.append("Frame constructor parameters must be self, curfn, fn, blk")
    for name in seeds:
        values = [value for field, value in frame if field == name]
        if len(values) != 1 or not isinstance(values[0], ast.Name) or values[0].id != name:
            errors.append(f"Frame constructor must initialize {name} from {name}")
    constructors = [n for n in ast.walk(save) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Frame"]
    if len(constructors) != 1:
        errors.append("gen_save must construct exactly one Frame")
    else:
        call = constructors[0]
        if call.keywords or [attribute(arg, "self") for arg in call.args] != seeds:
            errors.append("gen_save must construct Frame(self.curfn, self.fn, self.blk)")
        if not any(isinstance(n, ast.Assign) and n.value is call and len(n.targets) == 1
                   and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "fr"
                   for n in save.body):
            errors.append("gen_save must assign the Frame constructor to fr")

    for fn, destination, source, expected in (
        (save, "fr", "self", frame_fields - set(seeds)),
        (restore, "self", "fr", frame_fields),
    ):
        transfers = assignments(fn, destination)
        counts = Counter(name for name, _ in transfers)
        for name in sorted(expected - counts.keys()):
            errors.append(f"{fn.name} is missing {name}")
        for name in sorted(counts.keys() - expected):
            errors.append(f"{fn.name} has unexpected field {name}")
        for name, count in counts.items():
            if count != 1:
                errors.append(f"{fn.name} transfers {name} {count} times")
        for name, value in transfers:
            if attribute(value, source) != name:
                errors.append(f"{fn.name} must transfer {destination}.{name} from {source}.{name}")
        body = fn.body[1:-1] if fn is save else fn.body
        if not all(isinstance(n, ast.Assign) and len(n.targets) == 1
                   and attribute(n.targets[0], destination) is not None for n in body):
            errors.append(f"{fn.name} transfers must be direct single assignments")
    if len(save.body) != len(assignments(save, "fr")) + 2 or not isinstance(save.body[-1], ast.Return) or not isinstance(save.body[-1].value, ast.Name) or save.body[-1].value.id != "fr":
        errors.append("gen_save must contain only construction, transfers and return fr")
    if len(restore.body) != len(assignments(restore, "self")):
        errors.append("gen_restore must contain only field transfers")
    return errors


def read_sources():
    return tuple((SOURCE / name).read_text(encoding="utf-8") for name in ("gen.py", "ir.py", "emission.py"))


if __name__ == "__main__":
    problems = validate_sources(*read_sources())
    for problem in problems:
        print(problem)
    if not problems:
        print("Frame contract: all declared fields match Gen initialization and exact save/restore mappings")
    raise SystemExit(bool(problems))
