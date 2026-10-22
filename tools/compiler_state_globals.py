"""Hosted inventory of compiler module containers and their declared writers.

This checks the compiler's explicit global-container convention, including imports,
simple local aliases and nested subscripts. It is not a whole-program effect or
alias analysis: mutation through arbitrary calls or object attributes is not proved
absent. Reviewed lookup tables are not claimed to be deeply immutable.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/pystachy_compiler"
PREFIX = "src.pystachy_compiler."

# These are initialized when modules load, then reviewed as lookup tables. Adding
# a container or a post-import writer requires an explicit ownership decision.
LOOKUP = set("""
driver.COMPILER_SOURCES driver.CPUID driver.RTPARTS
dynamic.XCMP dynamic.XOPS dynamic.BINOPS dynamic.UNOPS dynamic.CMPOPS
dynamic.BINDUNDERS dynamic.BUILTIN
ir.NONUMS ir.NOVALS ir.NOLABELS ircheck.RESULT_NUMBERS
lexer.KEYWORDS lexer.OPS lexer.ESCAPES lexer.PREFIXES lexer.NONPRINT lexer.NOTID
local_versions.UNVERSIONED parser.ATOMS
reflection.BUILTIN_TYPES reflection.SLOT_WRAPPERS reflection.OBJ_BUILTINS reflection.TYPE_BUILTINS
scalar_ir.SCALAR_INTS scalar_ir.SCALAR_BIN scalar_ir.SCALAR_FLOAT
scalar_ir.SCALAR_ICMP scalar_ir.SCALAR_FCMP scalar_ir.SCALAR_CASTS scope.COMPNAMES
specs.PYBUILTINS specs.MODNAMES specs.ANNKINDS specs.GENERICS specs.CBUILTIN
specs.ABSTRACT_DECOS specs.STANDINS specs.OPAQUE specs.TYPEMODS specs.NOCALL
specs.IOPS specs.CHECKED specs.IRT specs.FOPS specs.FRT specs.ICMP specs.FCMP
specs.SPECIAL specs.UNCALLED specs.REFL specs.ORDOP specs.DUNDER specs.UNARY
specs.CALLS specs.RTL specs.TBAA_SIZES specs.TBAA_NAMES specs.ERRNO specs.MODFUNCS
specs.CTYPES specs.MODATTRS specs.OSCONST specs.FLOATINFO specs.VERSIONINFO
specs.TYPING specs.TYPEARGS specs.ABCS specs.ABCSMORE specs.RANGE_TAKERS specs.RANGE_METHODS
specs.FUTURE specs.DEFAULTS specs.EXCEPTIONS specs.EXCBASES specs.EXCATTRS specs.EXCINIT
specs.EXCKW specs.HASATTR specs.NONEARG specs.OPTARG specs.NONERET specs.OPTCALLS
specs.NOREF specs.UNSUPPORTED specs.INERT_DECOS specs.INERT specs.PURE specs.RAISERS
specs.CODECS specs.ARITY specs.METHODS specs.TEXT_OPS specs.UNICODE_AUDIT
specs.FSETMETHODS specs.SETMETHODS specs.IROPS specs.OPTS specs.VALUE_AT specs.FX
specs.FXBIT specs.RUNTIME specs.RTDATA specs.RTSYM
structs.STRUCT_FNS structs.NATIVE_SIZES structs.STANDARD_SIZES
syntax.DCOPTS syntax.EXPRNAMES syntax.STARTS syntax.CMPOPS syntax.AUGOPS syntax.BINOPS
utils.DECRUNS
""".split())

# These five rewind boundaries have executable removal controls in
# test_compiler_state_probe.py. This inventory does not substitute for them.
REWOUND = {
    "diagnostics.FILES": "truncate appended file names to the entry length",
    "syntax.LAMBDAS": "restore the entry counter",
    "names.RENAMED": "clear class display-name discoveries",
    "specs.LIBS": "truncate appended link libraries to the entry length",
    "specs.LINKDL": "truncate appended dynamic-link requirements to the entry length",
}
RETAINED = {
    "diagnostics.DYNFILES": "loader file-index opt-ins; currently retained across restarts",
    "specs.GLUE": "loader public-name discoveries; currently retained across restarts",
    "specs.SPECSHOW": "specialization display names; currently retained across restarts",
    "specs.MODULES": "driver builtin-module configuration, including temporary runtime mode",
}
# Retained means observed policy, not proof that retaining semantic state is safe.
# Keep #767 open for those contracts and for indirect mutation/alias effects.
WRITERS = {
    "diagnostics.FILES": {"loader.Loader.program", "loader.Loader.parse", "driver.compile_program"},
    "diagnostics.DYNFILES": {"loader.Loader.program", "loader.Loader.parse"},
    "syntax.LAMBDAS": {"parser.Parser.test1", "driver.compile_program"},
    "names.RENAMED": {"program.gen_program", "driver.compile_program"},
    "specs.LIBS": {"lower_module.gen_cextern", "driver.compile_program", "driver.main"},
    "specs.LINKDL": {"lower_module.gen_cextern", "driver.compile_program"},
    "specs.GLUE": {"loader.Loader.load"},
    "specs.SPECSHOW": {"templates.gen_specialize"},
    "specs.MODULES": {"driver.runtime_ir", "driver.main"},
}
# gen_verify borrows NOLABELS as out, then copies before append/extend.
# The conservative alias scan cannot prove that control flow; this local is a
# reviewed exception, not permission for a direct write to the shared sentinel.
ALIASES = {("ir.NOLABELS", "ircheck.gen_verify", "out")}
MUTATORS = {"append", "extend", "insert", "pop", "remove", "clear", "update", "setdefault",
            "sort", "reverse", "add", "discard", "popitem", "difference_update",
            "intersection_update", "symmetric_difference_update", "__setitem__", "__delitem__"}


def statements(body):
    """Module initialization, including conditional/loop bodies, excluding scopes."""
    for node in body:
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for field in ("body", "orelse", "finalbody"):
                yield from statements(getattr(node, field, []))
            for handler in getattr(node, "handlers", []):
                yield from statements(handler.body)


def assigned(node):
    if isinstance(node, ast.Assign):
        return node.targets, node.value
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return [node.target], node.value
    if isinstance(node, ast.Delete):
        return node.targets, None
    return [], None


def target_leaves(target):
    if isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from target_leaves(item)
    elif isinstance(target, ast.Starred):
        yield from target_leaves(target.value)
    else:
        yield target


def pairs(node):
    """Assignment bindings, including literal tuple/list unpacking."""
    def unpack(target, value):
        if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List))
                and len(target.elts) == len(value.elts)):
            for left, right in zip(target.elts, value.elts):
                yield from unpack(left, right)
        else:
            yield target, value
    targets, value = assigned(node)
    for target in targets:
        yield from unpack(target, value)


def container(value, annotation, known):
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        if annotation.value.id in {"list", "dict", "set"}:
            return True
    if isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(value, (ast.Name, ast.Attribute)):
        return root_id(value) in known
    if isinstance(value, ast.Tuple):
        return any(container(v, None, known) for v in value.elts)
    if isinstance(value, ast.BinOp):
        return container(value.left, None, known) or container(value.right, None, known)
    if isinstance(value, ast.Call):
        return (isinstance(value.func, ast.Name) and value.func.id in {"list", "dict", "set"}
                or isinstance(value.func, ast.Attribute) and value.func.attr in {"split", "rsplit", "splitlines"})
    return False


def inventory(sources):
    trees = {name: ast.parse(source) for name, source in sources.items()}
    found = set()
    bindings = {module: {} for module in trees}
    # Iterate import/assignment aliases to a fixed point across module order.
    changed = True
    while changed:
        changed = False
        for module, tree in trees.items():
            names = bindings[module]
            for node in statements(tree.body):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PREFIX):
                    for alias in node.names:
                        names[alias.asname or alias.name] = node.module[len(PREFIX):] + "." + alias.name
                elif isinstance(node, ast.ImportFrom) and node.module == PREFIX[:-1]:
                    for alias in node.names:
                        for origin in found:
                            if origin.startswith(alias.name + "."):
                                names[(alias.asname or alias.name) + origin[len(alias.name):]] = origin
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(PREFIX):
                            imported = alias.name[len(PREFIX):]
                            for origin in found:
                                if origin.startswith(imported + "."):
                                    names[(alias.asname or alias.name) + origin[len(imported):]] = origin
                known = {name for name, origin in names.items() if origin in found}
                for target, value in pairs(node):
                    if container(value, getattr(node, "annotation", None), known):
                        if isinstance(target, ast.Name):
                            origin = module + "." + target.id
                            if origin not in found:
                                found.add(origin)
                                changed = True
                            names[target.id] = origin
    return trees, found, bindings


def root_id(node):
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Attribute):
        parent = root_id(node.value)
        return parent + "." + node.attr if parent else ""
    return node.id if isinstance(node, ast.Name) else ""


def root_name(node, names):
    return names.get(root_id(node))


def writes(tree, module, bindings):
    """Conservative simple-local-alias scan; later rebindings do not erase aliases."""
    result = set()

    def visit_scope(scope, path, outer=None):
        if isinstance(scope, ast.ClassDef):
            for child in scope.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit_scope(child, path + "." + child.name)
            return
        names = ({name: {origin} for name, origin in bindings.items()}
                 if outer is None else {name: set(origins) for name, origins in outer.items()})
        # Parameters and local rebinding shadow globals unless declared global.
        nodes = list(statements(scope.body))
        declared = {name for n in nodes if isinstance(n, ast.Global) for name in n.names}
        for name in declared:
            names.pop(name, None)
            if name in bindings:
                names[name] = {bindings[name]}
        local = {a.arg for a in scope.args.posonlyargs + scope.args.args + scope.args.kwonlyargs}
        local.update(a.arg for a in (scope.args.vararg, scope.args.kwarg) if a is not None)
        for n in nodes:
            local.update(t.id for root in assigned(n)[0] for t in target_leaves(root)
                         if isinstance(t, ast.Name))
        for name in list(names):
            if name.split(".")[0] in local - declared:
                names.pop(name, None)
        # Fixed point handles chains declared in either source order. This can
        # overapproximate a reused local; intentional aliases need review.
        changed = True
        while changed:
            changed = False
            for n in nodes:
                if isinstance(n, ast.AugAssign):
                    continue  # The RHS contributes values, not a new alias binding.
                for target, value in pairs(n):
                    origin = root_name(value, names)
                    if origin and isinstance(target, ast.Name) and not origin <= names.get(target.id, set()):
                        names[target.id] = names.get(target.id, set()) | origin
                        changed = True
        for n in nodes:
            targets = [target for root in assigned(n)[0] for target in target_leaves(root)]
            for target in targets:
                origin = root_name(target, names)
                if origin and (isinstance(target, (ast.Subscript, ast.Attribute)) or isinstance(n, ast.AugAssign)
                               or isinstance(target, ast.Name) and target.id in declared):
                    result.update((name, path, root_id(target)) for name in origin)
            # Walk expressions but not bodies again or nested function scopes.
            for child in ast.iter_child_nodes(n):
                if isinstance(child, ast.stmt):
                    continue
                for expression in ast.walk(child):
                    if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute):
                        if expression.func.attr in MUTATORS:
                            origin = root_name(expression.func.value, names)
                            if origin:
                                result.update((name, path, root_id(expression.func.value)) for name in origin)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit_scope(n, path + "." + n.name, names)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visit_scope(node, module + "." + node.name)
    return result


def validate_sources(sources):
    trees, found, bindings = inventory(sources)
    declared = LOOKUP | REWOUND.keys() | RETAINED.keys()
    errors = [f"unclassified module container: {name}" for name in sorted(found - declared)]
    errors += [f"stale container classification: {name}" for name in sorted(declared - found)]
    actual = set().union(*(writes(tree, name, bindings[name]) for name, tree in trees.items()))
    allowed = {(name, writer, name.split(".")[-1]) for name, writers in WRITERS.items() for writer in writers} | ALIASES
    errors += [f"unreviewed container writer: {writer} writes {name} via {alias}" for name, writer, alias in sorted(actual - allowed)]
    errors += [f"stale container writer: {writer} writes {name} via {alias}" for name, writer, alias in sorted(allowed - actual)]
    return errors


def read_sources():
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(SOURCE.glob("*.py"))}


if __name__ == "__main__":
    problems = validate_sources(read_sources())
    for problem in problems:
        print(problem)
    if not problems:
        print("Compiler module-container inventory and declared writers match")
    raise SystemExit(bool(problems))
