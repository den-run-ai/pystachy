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
            "intersection_update", "symmetric_difference_update", "__setitem__", "__delitem__",
            "__iadd__", "__imul__", "__ior__", "__iand__", "__ixor__", "__isub__", "__init__"}
BUILTIN_CONTAINERS = {"list", "dict", "set"}
CONTAINER_ANNOTATIONS = BUILTIN_CONTAINERS | {"container"}


def statements(body):
    """Module initialization, including conditional/loop bodies, excluding scopes."""
    for node in body:
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for field in ("body", "orelse", "finalbody"):
                yield from statements(getattr(node, field, []))
            for handler in getattr(node, "handlers", []):
                yield from statements(handler.body)
            for case in getattr(node, "cases", []):
                yield from statements(case.body)


def expression_nodes(node):
    """Expression descendants, stopping before every statement body or scope."""
    if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
        return  # Comprehension scopes require separate effect/alias review.
    if isinstance(node, ast.Lambda):
        for value in node.args.defaults + node.args.kw_defaults:
            if value is not None:
                yield value
                yield from expression_nodes(value)
        return  # Defaults execute here; the anonymous body does not.
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.stmt):
            yield child
            yield from expression_nodes(child)


def assigned(node):
    if isinstance(node, ast.Assign):
        return node.targets, node.value
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return [node.target], node.value
    if isinstance(node, ast.Delete):
        return node.targets, None
    return [], None


def function_expressions(node):
    """Local variable annotations are lexical syntax, not runtime expressions."""
    if isinstance(node, ast.AnnAssign):
        for value in (node.target, node.value):
            if value is not None:
                yield value
                yield from expression_nodes(value)
    else:
        yield from expression_nodes(node)


def scope_nodes(body, expressions=expression_nodes):
    for node in statements(body):
        yield node
        yield from (child for child in expressions(node) if isinstance(child, ast.NamedExpr))


def binding_targets(node):
    """Explicit stores, separate from assignments that can create aliases."""
    if (isinstance(node, ast.AnnAssign) and node.value is None and not node.simple
            and isinstance(node.target, ast.Name)):
        return  # A parenthesized name annotation does not make a function local.
    yield from assigned(node)[0]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        yield node.target
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        yield from (item.optional_vars for item in node.items if item.optional_vars is not None)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        yield ast.Name(id=node.name)
    elif isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            yield ast.Name(id=alias.asname or (alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name))
    for handler in getattr(node, "handlers", []):
        if handler.name:
            yield ast.Name(id=handler.name)
    for case in getattr(node, "cases", []):
        for pattern in ast.walk(case.pattern):
            name = (pattern.name if isinstance(pattern, (ast.MatchAs, ast.MatchStar)) else
                    pattern.rest if isinstance(pattern, ast.MatchMapping) else None)
            if name:
                yield ast.Name(id=name)


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
    if isinstance(node, ast.AnnAssign) and node.value is None:
        return  # An annotation alone neither creates nor replaces a value.
    def unpack(target, value):
        if isinstance(target, ast.Starred):
            # The starred result is a fresh list, never an alias to its iterable.
            fresh = value if isinstance(value, ast.List) else ast.List(elts=[], ctx=ast.Load())
            yield from unpack(target.value, fresh)
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = (value.elts if isinstance(value, (ast.Tuple, ast.List))
                      and not any(isinstance(v, ast.Starred) for v in value.elts) else None)
            star = next((i for i, t in enumerate(target.elts) if isinstance(t, ast.Starred)), -1)
            if values is not None and star >= 0 and len(values) >= len(target.elts) - 1:
                end = len(values) - (len(target.elts) - star - 1)
                values = values[:star] + [ast.List(elts=values[star:end], ctx=ast.Load())] + values[end:]
            if values is None or len(values) != len(target.elts):
                values = [None] * len(target.elts)
            for left, right in zip(target.elts, values):
                yield from unpack(left, right)
        else:
            yield target, value
    targets, value = assigned(node)
    if isinstance(node, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)):
        targets = list(binding_targets(node))  # Only starred targets have a known fresh result.
    for target in targets:
        yield from unpack(target, value)


def annotation_import(node, names):
    """Only explicit builtin/typing imports; no annotation evaluation."""
    wrappers = {"Annotated": "annotated", "Optional": "optional", "Union": "union"}
    exports = {"builtins": {name: name for name in BUILTIN_CONTAINERS},
               "typing": {"List": "container", "Dict": "container", "Set": "container", **wrappers},
               "typing_extensions": wrappers}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            local = alias.asname or alias.name
            for name in list(names):
                if name.split(".")[0] == local.split(".")[0]:
                    names.pop(name)
            if isinstance(node, ast.ImportFrom):
                kind = exports.get(node.module, {}).get(alias.name)
                if kind:
                    names[local] = kind
            else:
                names.update({local + "." + key: kind for key, kind in exports.get(alias.name, {}).items()})


def container_annotation(annotation, names):
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return False
        return container_annotation(annotation, names)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return container_annotation(annotation.left, names) or container_annotation(annotation.right, names)
    if isinstance(annotation, ast.Subscript):
        kind = names.get(root_id(annotation.value))
        if kind == "annotated" and isinstance(annotation.slice, ast.Tuple) and annotation.slice.elts:
            return container_annotation(annotation.slice.elts[0], names)
        if kind == "optional":
            return container_annotation(annotation.slice, names)
        if kind == "union":
            values = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
            return any(container_annotation(value, names) for value in values)
        return kind in CONTAINER_ANNOTATIONS
    return names.get(root_id(annotation)) in CONTAINER_ANNOTATIONS


def container(value, annotation, known, annotations):
    if container_annotation(annotation, annotations):
        return True
    if isinstance(value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(value, (ast.Name, ast.Attribute)):
        return root_id(value) in known
    if isinstance(value, ast.NamedExpr):
        return container(value.value, None, known, annotations)
    if isinstance(value, ast.Tuple):
        return any(container(v, None, known, annotations) for v in value.elts)
    if isinstance(value, ast.IfExp):
        return container(value.body, None, known, annotations) or container(value.orelse, None, known, annotations)
    if isinstance(value, ast.BoolOp):
        return any(container(v, None, known, annotations) for v in value.values)
    if isinstance(value, ast.BinOp):
        return container(value.left, None, known, annotations) or container(value.right, None, known, annotations)
    if isinstance(value, ast.Call):
        return (annotations.get(root_id(value.func)) in CONTAINER_ANNOTATIONS
                or isinstance(value.func, ast.Attribute) and value.func.attr in {"split", "rsplit", "splitlines"})
    return False


def import_bindings(node, containers, exports=None, max_depth=None):
    """Resolve explicit imports through known module exports and re-exports."""
    if isinstance(node, ast.ImportFrom):
        if not node.module or not (node.module == PREFIX[:-1] or node.module.startswith(PREFIX)):
            return {}
    elif not isinstance(node, ast.Import) or not any(alias.name.startswith(PREFIX) for alias in node.names):
        return {}
    symbols = {origin: {origin} for origin in containers}
    if exports is not None:
        symbols.update({module + "." + name: origins for module, names in exports.items()
                        for name, origins in names.items()})
    names = {}

    def add(source, local):
        for symbol, origins in symbols.items():
            if symbol == source or symbol.startswith(source + "."):
                name = local + symbol[len(source):]
                if max_depth is None or len(name.split(".")) <= max_depth:
                    names[name] = set(origins)

    if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PREFIX):
        for alias in node.names:
            add(node.module[len(PREFIX):] + "." + alias.name, alias.asname or alias.name)
    elif isinstance(node, ast.ImportFrom) and node.module == PREFIX[:-1]:
        for alias in node.names:
            add(alias.name, alias.asname or alias.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith(PREFIX):
                add(alias.name[len(PREFIX):], alias.asname or alias.name)
    return names


def inventory(sources):
    trees = {name: ast.parse(source) for name, source in sources.items()}
    found = set()
    bindings = {module: {} for module in trees}
    proven = {module: {} for module in trees}
    # Cyclic module aliases must not grow unreferenced qualifier paths forever.
    max_depth = max((len(root_id(node).split(".")) for tree in trees.values() for node in ast.walk(tree)
                     if isinstance(node, (ast.Name, ast.Attribute))), default=1)
    # Iterate declarations, aliases and explicit re-exports across module order.
    changed = True
    while changed:
        changed = False
        for module, tree in trees.items():
            names = bindings[module]
            definite = proven[module]
            previous = ({key: set(value) for key, value in names.items()},
                        {key: set(value) for key, value in definite.items()})
            annotations = {name: name for name in BUILTIN_CONTAINERS}
            for node in scope_nodes(tree.body):
                annotation_import(node, annotations)
                for target, origins in import_bindings(node, found, bindings, max_depth).items():
                    names[target] = names.get(target, set()) | origins
                for target, origins in import_bindings(node, found, proven, max_depth).items():
                    definite[target] = definite.get(target, set()) | origins
                for target, value in pairs(node):
                    if not isinstance(target, ast.Name):
                        continue
                    if container(value, getattr(node, "annotation", None), definite, annotations):
                        origin = module + "." + target.id
                        if origin not in found:
                            found.add(origin)
                            changed = True
                        names[target.id] = {origin}
                        definite[target.id] = {origin}
                    else:
                        # A subscript may be scalar: retain possible source owners
                        # for later writes without declaring another container.
                        origins = root_name(value, names)
                        if origins:
                            names[target.id] = names.get(target.id, set()) | origins
            changed |= previous != (names, definite)
    return trees, found, bindings


def root_id(node):
    if isinstance(node, (ast.IfExp, ast.BoolOp)):
        return ast.unparse(node)
    if isinstance(node, ast.NamedExpr):
        return root_id(node.target)
    if isinstance(node, ast.Subscript):
        return root_id(node.value)
    if isinstance(node, ast.Attribute):
        parent = root_id(node.value)
        return parent + "." + node.attr if parent else ""
    return node.id if isinstance(node, ast.Name) else ""


def root_name(node, names):
    if isinstance(node, (ast.NamedExpr, ast.Subscript)):
        return root_name(node.value, names)
    if isinstance(node, (ast.IfExp, ast.BoolOp)):
        values = [node.body, node.orelse] if isinstance(node, ast.IfExp) else node.values
        return set().union(*(root_name(value, names) or set() for value in values))
    return names.get(root_id(node))


def update_types(node, types):
    """Explicit rebinding invalidates builtin names; only imports restore them."""
    if isinstance(node, ast.AnnAssign) and node.value is None:
        return  # Module annotations alone do not bind names; function locals were pruned separately.
    targets = [target for root in binding_targets(node) for target in target_leaves(root)]
    for target in targets:
        key = root_id(target)
        for name in list(types):
            if name == key or isinstance(target, ast.Name) and name.startswith(key + "."):
                types.pop(name)
    annotation_import(node, types)


def writes(tree, module, bindings, containers=None, exports=None):
    """Conservative simple-local-alias scan; later rebindings do not erase aliases."""
    result = set()
    if containers is None:
        containers = LOOKUP | REWOUND.keys() | RETAINED.keys() | set().union(*bindings.values())
    module_types = {name: name for name in BUILTIN_CONTAINERS}
    for node in scope_nodes(tree.body):
        update_types(node, module_types)

    def visit_scope(scope, path, outer=None, default_outer=None, outer_types=None):
        names = ({name: set(origins) for name, origins in bindings.items()}
                 if outer is None else {name: set(origins) for name, origins in outer.items()})
        types = dict(module_types if outer_types is None else outer_types)
        if isinstance(scope, ast.ClassDef):
            # Class fields can supply method defaults, but are not closures.
            nodes = []
            for child in statements(scope.body):
                nodes.append(child)
                nodes.extend(n for n in expression_nodes(child) if isinstance(n, ast.NamedExpr))
            for child in nodes:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit_scope(child, path + "." + child.name, outer, names, types)
                if isinstance(child, ast.AnnAssign) and child.value is None:
                    continue  # Keep existing class values available to method defaults.
                aliases = [(target.id, root_name(value, names)) for target, value in pairs(child)
                           if isinstance(target, ast.Name)]
                local = {t.id for root in binding_targets(child) for t in target_leaves(root)
                         if isinstance(t, ast.Name)}
                for name in list(names):
                    if name.split(".")[0] in local:
                        names.pop(name)
                names.update({name: origin for name, origin in aliases if origin})
                names.update(import_bindings(child, containers, exports))
            return
        defaults = scope.args.defaults
        positional = scope.args.posonlyargs + scope.args.args
        default_names = dict(names if default_outer is None else default_outer)
        captures = {}
        for argument, value in (list(zip(positional[len(positional) - len(defaults):], defaults))
                                + list(zip(scope.args.kwonlyargs, scope.args.kw_defaults))):
            origin = root_name(value, default_names)
            if origin:
                captures[argument.arg] = set(origin)
            expressions = [] if value is None else [value, *expression_nodes(value)]
            for expression in expressions:
                if isinstance(expression, ast.NamedExpr):
                    origin = root_name(expression.value, default_names)
                    default_names.pop(expression.target.id, None)
                    if origin:
                        default_names[expression.target.id] = origin
        # Parameters and local rebinding shadow globals unless declared global.
        lexical_nodes = list(scope_nodes(scope.body))
        nodes = list(scope_nodes(scope.body, function_expressions))
        declared = {name for n in nodes if isinstance(n, ast.Global) for name in n.names}
        enclosing = {name for n in nodes if isinstance(n, ast.Nonlocal) for name in n.names}
        for name in declared:
            names.pop(name, None)
            if name in bindings:
                names[name] = set(bindings[name])
            for key in list(types):
                if key.split(".")[0] == name:
                    types.pop(key)
            types.update({key: kind for key, kind in module_types.items() if key.split(".")[0] == name})
        local = {a.arg for a in scope.args.posonlyargs + scope.args.args + scope.args.kwonlyargs}
        local.update(a.arg for a in (scope.args.vararg, scope.args.kwarg) if a is not None)
        for n in lexical_nodes:
            local.update(t.id for root in binding_targets(n) for t in target_leaves(root)
                         if isinstance(t, ast.Name))
        for name in list(names):
            if name.split(".")[0] in local - declared - enclosing:
                names.pop(name, None)
        for name in list(types):
            if name.split(".")[0] in local - declared - enclosing:
                types.pop(name)
        closure_types = dict(types)
        later_types = dict(types)
        for n in nodes:
            update_types(n, later_types)
            closure_types.update(later_types)
        names.update(captures)
        for n in nodes:
            for name, origins in import_bindings(n, containers, exports).items():
                names.setdefault(name, set()).update(origins)
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
            targets = ([] if isinstance(n, ast.AnnAssign) and n.value is None else
                       [target for root in binding_targets(n) for target in target_leaves(root)])
            for target in targets:
                origin = root_name(target, names)
                if origin and (isinstance(target, (ast.Subscript, ast.Attribute)) or isinstance(n, ast.AugAssign)
                               or isinstance(target, ast.Name) and target.id in declared):
                    result.update((name, path, root_id(target)) for name in origin)
            for expression in function_expressions(n):
                if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Attribute):
                    if expression.func.attr in MUTATORS:
                        receiver = expression.func.value
                        origin = root_name(receiver, names)
                        owner = receiver
                        while isinstance(owner, ast.Subscript):
                            owner = owner.value
                        if (not origin and isinstance(owner, (ast.Name, ast.Attribute))
                                and types.get(ast.unparse(owner)) in BUILTIN_CONTAINERS and expression.args):
                            receiver = expression.args[0]
                            origin = root_name(receiver, names)
                        if origin:
                            result.update((name, path, root_id(receiver)) for name in origin)
            update_types(n, types)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Bodies may run after later imports; defaults still execute here.
                visit_scope(n, path + "." + n.name, names, outer_types=types | closure_types)
    for node in statements(tree.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visit_scope(node, module + "." + node.name)
    return result


def validate_sources(sources):
    trees, found, bindings = inventory(sources)
    declared = LOOKUP | REWOUND.keys() | RETAINED.keys()
    errors = [f"unclassified module container: {name}" for name in sorted(found - declared)]
    errors += [f"stale container classification: {name}" for name in sorted(declared - found)]
    actual = set().union(*(writes(tree, name, bindings[name], found, bindings) for name, tree in trees.items()))
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
