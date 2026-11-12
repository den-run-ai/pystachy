"""Generate explicit native calls for a deliberately bounded pytest source dialect.

Collection reads syntax, never imports or executes test modules. Generated modules
retain their original top-level statements, fixtures and test bodies. Only known
pytest declarations are replaced. Unknown source declarations are an error; the
CLI's independent oracle detects collection behavior hidden in imported symbols.
"""

import ast
import dataclasses
from dataclasses import dataclass, field
import io
import itertools
import keyword
import re
import tokenize


class CollectionError(ValueError):
    """The source needs collection semantics the native runner cannot preserve."""


@dataclass
class GeneratedModule:
    source: str
    cases: list[str]
    # The program imports pytest_native_fixtures (tmp_path, monkeypatch).
    builtin_fixtures: bool = False
    # Generated line -> original line, for the compiler's diagnostics (line_map).
    lines: dict[int, int] = field(default_factory=dict)


@dataclass
class Parameter:
    names: list[str]
    values: list[list[str]]
    ids: list[str]
    marks: list[list["Mark"]]


@dataclass
class Mark:
    kind: str
    # True/False, or the name of a condition its decorator evaluated at import.
    condition: object
    reason: str
    strict: bool = False
    run: bool = True
    # Source of xfail(raises=...): a class or a tuple of classes.
    raises: str | None = None


@dataclass
class Fixture:
    function: ast.FunctionDef | None  # (None: built in)
    dependencies: list[str]
    generator: bool
    autouse: bool
    scope: str = "function"
    params: Parameter | None = None
    # Takes request, of which request.param is supported.
    request: bool = False
    owner: str = ""  # (the test class of a method fixture)
    # What generated code calls: the function, a bound method or a scope's getter.
    call: str = ""
    # Yields or returns a value; a scope's cache holds values only.
    valued: bool = True
    named: bool = False  # (a built-in called with the test's name)
    origin: str = ""  # ("conftest", "builtin" or this module)


@dataclass
class Test:
    function: ast.FunctionDef
    owner: ast.ClassDef | None
    # Nearest decorator first, a class's after its method's, as pytest reads marks.
    parameters: list[Parameter]
    marks: list[Mark]
    usefixtures: list[str]


SCOPES = {"function": 0, "class": 1, "module": 2, "session": 3}
FINALIZERS = {"class": "class_finalizers", "module": "module_finalizers", "session": "session_finalizers"}
PYTEST_IMPORTS = {"fixture", "mark", "param", "raises", "fail", "skip", "xfail", "approx"}
PYTEST_CALLS = {"pytest.raises", "pytest.fail", "pytest.skip", "pytest.xfail", "pytest.approx"}
XUNIT_MODULE = {"setup_module", "setupModule", "teardown_module", "teardownModule",
                "setup_function", "teardown_function"}
XUNIT_CLASS = {"setup_method", "teardown_method", "setup_class", "teardown_class", "setup", "teardown"}
MONKEYPATCH = {"setenv", "delenv", "undo"}
BUILTIN_FIXTURES = {
    "tmp_path": Fixture(None, [], False, False, call="_pyn_fixtures.tmp_path", named=True, origin="builtin"),
    "monkeypatch": Fixture(None, [], True, False, call="_pyn_fixtures.monkeypatch", valued=True, origin="builtin"),
}


def _bound_names(node):
    return [item.id for item in ast.walk(node)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)]


def _main_guard(node):
    """`if __name__ == "__main__":` without else: dead code in a module pytest imports."""
    if not isinstance(node, ast.If) or node.orelse:
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    sides = [test.left, test.comparators[0]]
    return (any(isinstance(side, ast.Name) and side.id == "__name__" for side in sides)
            and any(isinstance(side, ast.Constant) and side.value == "__main__" for side in sides))


# pytest's built-in marks with collection or execution behavior; other marks only label tests.
SEMANTIC_MARKS = {"skip", "skipif", "xfail", "parametrize", "usefixtures", "filterwarnings"}
OPERATORS = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
             ast.In: "in", ast.NotIn: "not in"}


def _literal(node):
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _local_bindings(function):
    """Names bound in this function, excluding nested lexical scopes."""
    names = set()

    class Bindings(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)

        def visit_FunctionDef(self, node):
            names.add(node.name)
            for expression in node.decorator_list + node.args.defaults + [
                    value for value in node.args.kw_defaults if value is not None]:
                self.visit(expression)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            names.add(node.name)
            for expression in node.decorator_list + node.bases + [kw.value for kw in node.keywords]:
                self.visit(expression)

        def visit_Lambda(self, node):
            for expression in node.args.defaults + [value for value in node.args.kw_defaults if value is not None]:
                self.visit(expression)

        def visit_comprehension(self, node):
            # Comprehension targets stay in their own scope; a walrus in an
            # iterable/filter/body still binds in the containing function.
            self.visit(node.iter)
            for condition in node.ifs:
                self.visit(condition)

        def visit_Import(self, node):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

        def visit_ImportFrom(self, node):
            names.update(alias.asname or alias.name for alias in node.names)

    visitor = Bindings()
    for statement in function.body if not isinstance(function, ast.Lambda) else [function.body]:
        visitor.visit(statement)
    return names


def _own_nodes(function):
    """A function's nodes outside its nested functions, lambdas and classes."""
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        yield node
        pending.extend(ast.iter_child_nodes(node))


def _attribute(name):
    """_pyn_support.name as an expression."""
    return ast.Attribute(ast.Name("_pyn_support", ast.Load()), name, ast.Load())


class Generator:
    def __init__(self, source: str, filename: str, operands: bool = True, selected=None,
                 shared=None, conftest: bool = False, session_end: bool = True):
        self.source = source
        self.filename = filename
        self.operands = operands
        self.selected = selected
        # conftest.py's fixtures as this module calls them (export), or None.
        self.shared = shared or {}
        self.conftest = conftest
        # The last case that runs also ends the session scope.
        self.session_end = session_end
        try:
            self.tree = ast.parse(source, filename)
        except SyntaxError as error:
            raise CollectionError(f"{filename}:{error.lineno}: {error.msg}") from None
        # pytest imports a test module under its own name, so a script guard never runs there.
        self.tree.body = [node for node in self.tree.body if not _main_guard(node)]
        self.aliases = {}
        self.constants = {}
        self.fixtures = {}
        self.class_fixtures = {}
        self.tests = []
        self.classes = []
        self.preludes = {}
        self.counter = 0
        self.metadata_constants = set()
        # Names a test class binds: pytest declarations there cannot use them, because
        # the runner evaluates those declarations at module level.
        self.shadowed = None
        self.builtins_used = False

    def error(self, node, message):
        raise CollectionError(f"{self.filename}:{getattr(node, 'lineno', 1)}: {message}")

    def name(self, node):
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, "")
        if isinstance(node, ast.Attribute):
            base = self.name(node.value)
            return base + "." + node.attr if base else ""
        return ""

    def constant(self, node, track=False):
        if isinstance(node, ast.Name) and self.shadowed is not None and node.id in self.shadowed:
            self.error(node, "pytest declarations in a test class cannot use its attributes: " + node.id)
        if isinstance(node, ast.Name) and node.id in self.constants:
            if track:
                self.metadata_constants.add(node.id)
            return self.constants[node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            values = [self.constant(item, track) for item in node.elts]
            return tuple(values) if isinstance(node, ast.Tuple) else values
        if isinstance(node, ast.Dict):
            return {self.constant(k, track): self.constant(v, track) for k, v in zip(node.keys, node.values)}
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            self.error(node, "expected a literal or an earlier literal constant")

    def keywords(self, call, allowed):
        result = {}
        for kw in call.keywords:
            if kw.arg not in allowed or kw.arg in result:
                self.error(kw, "unsupported or duplicate pytest keyword: " + str(kw.arg))
            result[kw.arg] = self.constant(kw.value, True)
        return result

    def arguments(self, function, bound=False):
        """The fixture or parameter names a test or fixture requests; bound drops self."""
        args = function.args
        if args.posonlyargs or args.vararg or args.kwarg:
            self.error(function, "tests and fixtures require named, non-variadic arguments")
        required = args.args[:len(args.args) - len(args.defaults)]
        if bound:
            if not required:
                self.error(function, "methods of a test class require self")
            required = required[1:]
        required += [arg for arg, default in zip(args.kwonlyargs, args.kw_defaults) if default is None]
        return [arg.arg for arg in required]

    def is_generator(self, function):
        # Nested functions do not make their enclosing fixture a generator.
        return any(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in _own_nodes(function))

    def has_value(self, function, generator):
        """Whether a fixture yields or returns anything but None, as far as its syntax shows."""
        def valued(node):
            return node.value is not None and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        if generator:
            return any(isinstance(node, ast.YieldFrom) or isinstance(node, ast.Yield) and valued(node)
                       for node in _own_nodes(function))
        return any(isinstance(node, ast.Return) and valued(node) for node in _own_nodes(function))

    def parameter(self, decorator, annotations):
        if not isinstance(decorator, ast.Call) or len(decorator.args) != 2:
            self.error(decorator, "parametrize requires argument names and a literal value table")
        kws = self.keywords(decorator, {"ids"})
        names = self.constant(decorator.args[0], True)
        string_names = isinstance(names, str)
        if string_names:
            names = [name.strip() for name in names.split(",")]
        if (not isinstance(names, (list, tuple)) or not names
                or any(not isinstance(name, str) or not name.isidentifier() for name in names)
                or len(set(names)) != len(names)):
            self.error(decorator, "parametrize names must be distinct identifiers")
        return self.table(decorator, list(names), string_names, decorator.args[1], kws.get("ids"), annotations,
                          "parametrize")

    def table(self, decorator, names, string_names, table, ids, annotations, what):
        """One parametrization: its cases' value variables, IDs and marks, and their declarations."""
        inline = isinstance(table, (ast.List, ast.Tuple))
        rows = table.elts if inline else self.constant(table, True)
        if not isinstance(rows, (list, tuple)) or not rows:
            self.error(decorator, what + " needs a nonempty literal list or tuple")
        if len(rows) > 10000:
            self.error(decorator, what + " exceeds the 10000-case collection bound")
        if ids is not None and (not isinstance(ids, (list, tuple)) or len(ids) != len(rows)
                                or any(not isinstance(item, str) for item in ids)):
            self.error(decorator, "ids must be a literal string list matching the value table")
        result = []
        generated_ids = []
        row_marks = []
        prelude = []
        for index, row in enumerate(rows):
            expr = row if inline else ast.Subscript(value=table, slice=ast.Constant(index), ctx=ast.Load())
            explicit_id = None
            marks = []
            parameter_set = isinstance(expr, ast.Call) and self.name(expr.func) == "pytest.param"
            if parameter_set:
                items = [self.constant(item, True) for item in expr.args]
                expressions = expr.args
                seen = set()
                for kw in expr.keywords:
                    if kw.arg not in {"id", "marks"} or kw.arg in seen:
                        self.error(kw, "pytest.param supports id= and static marks= only")
                    seen.add(kw.arg)
                    if kw.arg == "id":
                        explicit_id = self.constant(kw.value, True)
                        if explicit_id is not None and not isinstance(explicit_id, str):
                            self.error(kw, "pytest.param id must be a literal string or None")
                    else:
                        if self.conftest:
                            self.error(kw, "marks on conftest.py fixture parameters are unsupported")
                        declarations = kw.value.elts if isinstance(kw.value, (ast.List, ast.Tuple)) else [kw.value]
                        marks = [mark for mark in (self.marker(item) for item in declarations) if mark is not None]
            else:
                value = self.constant(row, True) if inline else row
                single_value = string_names and len(names) == 1
                items = [value] if single_value else value
                if single_value:
                    expressions = [expr]
                elif isinstance(expr, (ast.List, ast.Tuple)):
                    expressions = expr.elts
                else:
                    expressions = [ast.Subscript(value=expr, slice=ast.Constant(i), ctx=ast.Load())
                                   for i in range(len(names))]
            if not isinstance(items, (list, tuple)) or len(items) != len(names):
                self.error(decorator, what + " row width does not match argument names")
            # Inline tables have no observable outer container. Retain their actual
            # row expressions once; named tables retain the original stored values.
            variables = []
            for name, expression in zip(names, expressions):
                variable = f"_pyn_param_{self.counter}"
                self.counter += 1
                annotation = annotations.get(name)
                # Hoisting []/{} loses the contextual element type supplied by
                # the test's argument. Restore it only for fresh container
                # literals, including nested empties; never convert shared
                # names/subscripts or copy their storage to make typing fit.
                empty = any(isinstance(part, (ast.List, ast.Tuple, ast.Set)) and not part.elts
                            or isinstance(part, ast.Dict) and not part.keys for part in ast.walk(expression))
                declaration = variable
                if (annotation is not None and empty
                        and isinstance(expression, (ast.List, ast.Tuple, ast.Set, ast.Dict))):
                    hint = annotation.value if isinstance(annotation, ast.Constant) and isinstance(
                        annotation.value, str) else ast.unparse(annotation)
                    # Strings preserve CPython's annotation evaluation count.
                    declaration += ": " + repr(hint)
                prelude.append(f"{declaration} = {ast.unparse(expression)}")
                variables.append(variable)
            result.append(variables)
            row_marks.append(marks)
            label = explicit_id if explicit_id is not None else ids[index] if ids is not None else None
            generated_ids.append(self.parameter_id("", label, index) if label is not None else "-".join(
                self.parameter_id(name, item, index) for name, item in zip(names, items)))
        counts = {value: generated_ids.count(value) for value in generated_ids}
        used = set(generated_ids)
        suffixes = {}
        for index, value in enumerate(generated_ids):
            if counts[value] <= 1:
                continue
            suffix = suffixes.get(value, 0)
            separator = "_" if value and value[-1].isdigit() else ""
            candidate = f"{value}{separator}{suffix}"
            while candidate in used:
                suffix += 1
                candidate = f"{value}{separator}{suffix}"
            generated_ids[index] = candidate
            suffixes[value] = suffix + 1
            used.add(candidate)
        return Parameter(list(names), result, generated_ids, row_marks), prelude

    @staticmethod
    def parameter_id(name, value, index):
        if isinstance(value, str):
            return value.encode("unicode_escape").decode("ascii")
        if isinstance(value, bytes):
            escapes = {9: "\\t", 10: "\\n", 13: "\\r"}
            return "".join(chr(byte) if 32 <= byte < 127 else escapes.get(byte, f"\\x{byte:02x}")
                           for byte in value)
        if value is None or isinstance(value, (bool, int, float, complex)):
            return str(value)
        return name + str(index)

    def fixture_names(self, decorator):
        """The literal fixture names of @pytest.mark.usefixtures(...)."""
        if not isinstance(decorator, ast.Call) or decorator.keywords:
            self.error(decorator, "usefixtures requires literal fixture names")
        names = [self.constant(argument) for argument in decorator.args]
        if any(not isinstance(name, str) or not name.isidentifier() for name in names):
            self.error(decorator, "usefixtures requires literal fixture names")
        return names

    def exception_classes(self, node):
        """Source of xfail(raises=...): a class's name, or a literal tuple of them."""
        items = node.elts if isinstance(node, ast.Tuple) else [node]
        for item in items:
            part = item
            while isinstance(part, ast.Attribute):
                part = part.value
            if not isinstance(part, ast.Name) or not items or self.name(item):
                self.error(node, "xfail raises= requires an exception class or a literal tuple of classes")
            if self.shadowed is not None and part.id in self.shadowed:
                self.error(node, "pytest declarations in a test class cannot use its attributes: " + part.id)
        if not items:
            self.error(node, "xfail raises= requires an exception class or a literal tuple of classes")
        return ast.unparse(node)

    def marker(self, decorator, prelude=None):
        """Return a skip/xfail mark, or None for a mark that only labels its test.

        A decorator's skipif condition may be an expression: it is evaluated once at
        import, in decorator order (appended to prelude), as pytest's decorator is.
        """
        call = decorator if isinstance(decorator, ast.Call) else None
        name = self.name(call.func if call else decorator)
        kind = name.removeprefix("pytest.mark.")
        if name.startswith("pytest.mark.") and kind and kind not in SEMANTIC_MARKS:
            # Labels such as slow/network change nothing without plugins or -m selection.
            # Their arguments still run where the decorator does, so they must be literals.
            for value in (call.args + [kw.value for kw in call.keywords]) if call else []:
                self.constant(value)
            return None
        raises = None
        if call is not None and kind == "xfail":
            expected = [kw for kw in call.keywords if kw.arg == "raises"]
            if len(expected) > 1:
                self.error(decorator, "unsupported or duplicate pytest keyword: raises")
            if expected:
                raises = self.exception_classes(expected[0].value)
                call = ast.copy_location(ast.Call(func=call.func, args=call.args, keywords=[
                    kw for kw in call.keywords if kw.arg != "raises"]), call)
        runtime = (kind == "skipif" and prelude is not None and call is not None and len(call.args) == 1
                   and not _literal(call.args[0])
                   and not (isinstance(call.args[0], ast.Name) and call.args[0].id in self.constants))
        args = [self.constant(arg, True) for arg in call.args] if call and not runtime else []
        allowed = {"reason"} if kind in ("skip", "skipif") else {"reason", "strict", "run"}
        kws = self.keywords(call, allowed) if call else {}
        reason = kws.get("reason", "")
        condition = True
        if runtime:
            expression = call.args[0]
            if any(self.name(part) for part in ast.walk(expression)):
                self.error(decorator, "skipif conditions cannot use pytest")
            if self.shadowed is not None:
                # The condition runs before the class body here, not inside it.
                for part in ast.walk(expression):
                    if isinstance(part, ast.Name) and part.id in self.shadowed:
                        self.error(decorator, "pytest declarations in a test class cannot use its attributes: "
                                   + part.id)
                    if isinstance(part, (ast.Call, ast.Subscript, ast.NamedExpr, ast.Await, ast.Yield,
                                         ast.YieldFrom, ast.ListComp, ast.SetComp, ast.DictComp,
                                         ast.GeneratorExp, ast.Lambda)):
                        self.error(decorator, "skipif conditions in a test class must be names, attributes, "
                                   "literals and comparisons")
            if "reason" not in kws:
                self.error(decorator, "skipif with a boolean condition requires an explicit reason")
            condition = f"_pyn_condition_{self.counter}"
            self.counter += 1
            prelude.append(f"{condition} = {ast.unparse(expression)}")
        elif kind == "skip":
            if len(args) > 1 or (args and "reason" in kws):
                self.error(decorator, "skip accepts one reason")
            reason = args[0] if args else reason
        elif kind in ("skipif", "xfail"):
            if len(args) > 1 or (kind == "skipif" and not args):
                self.error(decorator, kind + " requires at most one literal condition")
            if args:
                if not isinstance(args[0], bool):
                    self.error(decorator, "marker conditions must be literal booleans"
                               + (" (string conditions are unsupported)" if isinstance(args[0], str) else ""))
                condition = args[0]
            if (kind == "skipif" or args) and "reason" not in kws:
                self.error(decorator, kind + " with a boolean condition requires an explicit reason")
        else:
            self.error(decorator, "unsupported marker: " + kind)
        if not isinstance(reason, str):
            self.error(decorator, "marker reason must be a literal string")
        if any(not isinstance(kws[key], bool) for key in ("strict", "run") if key in kws):
            self.error(decorator, "xfail strict/run must be literal booleans")
        return Mark(kind, condition, reason, kws.get("strict", False), kws.get("run", True), raises)

    def decorations(self, node, prelude, annotations):
        """A test function's or test class's pytest marks, nearest decorator first."""
        parameters = []
        marks = []
        usefixtures = []
        for decorator in node.decorator_list:
            name = self.name(decorator.func if isinstance(decorator, ast.Call) else decorator)
            if name == "pytest.mark.parametrize":
                parameter, setup = self.parameter(decorator, annotations)
                parameters.append(parameter)
                prelude.extend(setup)
            elif name in {"pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail"}:
                marks.append(self.marker(decorator, prelude))
            elif name == "pytest.mark.usefixtures":
                usefixtures.append(self.fixture_names(decorator))
            elif name.startswith("pytest.mark.") and self.marker(decorator) is None:
                continue  # (a label: see marker)
            else:
                self.error(decorator, "unsupported test decorator")
        # pytest reads marks nearest the function first, as it applies them.
        return (list(reversed(parameters)), list(reversed(marks)),
                [name for names in reversed(usefixtures) for name in names])

    def collect(self):
        direct = set(self.tree.body)
        parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        classes = {node for node in self.tree.body if isinstance(node, ast.ClassDef) and node.name.startswith("Test")}
        # A literal is neither callable nor a class, so pytest collects no test from
        # `test_cases = [...]` or `TestData = (...)`, at module level or in a test class.
        literal_targets = set()
        for holder in [self.tree, *classes]:
            for node in holder.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and _literal(node.value):
                    literal_targets.add(node.targets[0])
                elif isinstance(node, ast.AnnAssign) and node.value is not None and _literal(node.value):
                    literal_targets.add(node.target)
        seen = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and node.id.startswith("_pyn_"):
                self.error(node, "names beginning _pyn_ are reserved by the native runner")
            if isinstance(node, ast.Name) and node.id in {
                    "__file__", "__name__", "__package__", "__spec__", "__test__", "__annotations__",
                    "pytestmark", "pytest_plugins"}:
                self.error(node, "module metadata and dynamic pytest collection are unsupported: " + node.id)
            if (isinstance(node, ast.Name) and node.id.startswith(("test", "Test"))
                    and isinstance(node.ctx, ast.Store) and node not in literal_targets):
                scope = parents.get(node)
                while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    scope = parents.get(scope)
                if scope is None:
                    self.error(node, "dynamically assigning tests is unsupported")
            if isinstance(node, ast.Global) and any(name.startswith(("test", "Test")) for name in node.names):
                self.error(node, "mutating test bindings through globals is unsupported")
            if isinstance(node, ast.ImportFrom) and node.level:
                self.error(node, "relative imports require package-aware collection")
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in direct:
                imported = ([item.name for item in node.names] if isinstance(node, ast.Import)
                            else [node.module or ""])
                if any(name == "pytest" or name.startswith(("pytest.", "_pytest")) for name in imported):
                    self.error(node, "pytest imports must be at module level")
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in {"globals", "locals", "vars", "eval", "exec", "compile", "__import__"}):
                self.error(node, "runtime namespace inspection or mutation is unsupported")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method = parents.get(node) in classes
                if node.name in XUNIT_MODULE or (method and node.name in XUNIT_CLASS):
                    self.error(node, "xunit setup/teardown hooks are unsupported; use fixtures")
                if node.name.startswith("_pyn_") or node.name.startswith("pytest_"):
                    self.error(node, "reserved runner name or unsupported pytest hook: " + node.name)
                if node.name.startswith("test") and node not in direct and not method:
                    # pytest collects module attributes and test classes' methods. A function
                    # defined inside another, or in a class that is not a test class, is
                    # neither; a conditional definition is one the collector cannot follow.
                    scope = parents.get(node)
                    while scope is not None and not isinstance(scope, (
                            ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                        scope = parents.get(scope)
                    if scope is None or scope in classes:
                        self.error(node, "test methods and conditional/nested test definitions are unsupported")
            if isinstance(node, ast.ClassDef):
                bases = [base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
                         for base in node.bases]
                if (any(base.endswith("TestCase") for base in bases)
                        or any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "runTest"
                               for item in node.body)):
                    # pytest collects these whatever the class is called.
                    self.error(node, "unittest test cases are unsupported")
                if node.name.startswith("Test") and node not in direct:
                    self.error(node, "nested and conditional test classes are unsupported")
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                # (A module is neither callable nor a class: pytest collects nothing from
                # "import test_helpers", whatever the module's name.)
                for alias in node.names:
                    if alias.name == "pytest":
                        self.aliases[alias.asname or alias.name] = "pytest"
                    elif alias.name.startswith("pytest.") or alias.name.startswith("_pytest"):
                        self.error(node, "pytest internals are unsupported")
            elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
                for alias in node.names:
                    if alias.name not in PYTEST_IMPORTS:
                        self.error(node, "unsupported pytest import: " + alias.name)
                    self.aliases[alias.asname or alias.name] = "pytest." + alias.name
            elif isinstance(node, ast.ImportFrom):
                if any((alias.asname or alias.name).startswith(("test", "Test")) or alias.name == "*"
                       for alias in node.names):
                    self.error(node, "imported tests and star imports are unsupported")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = _bound_names(node)
                if any(name in self.aliases for name in names):
                    self.error(node, "rebinding pytest or dynamically assigning tests is unsupported")
                try:
                    value = self.constant(node.value) if node.value is not None else None
                except CollectionError:
                    for name in names:
                        self.constants.pop(name, None)
                else:
                    if len(names) == 1:
                        self.constants[names[0]] = value
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen or node.name in self.aliases:
                    self.error(node, "duplicate function or pytest binding: " + node.name)
                seen.add(node.name)
                test = self.declare(node, None, self.preludes.setdefault(node, []))
                if test is not None:
                    self.finish_test(test)
            elif node in classes:
                if node.name in seen or node.name in self.aliases:
                    self.error(node, "duplicate function or pytest binding: " + node.name)
                seen.add(node.name)
                self.collect_class(node)
        if len(self.tests) > 10000:
            self.error(self.tree, "more than 10000 tests in one module")
        for owner, fixtures in self.class_fixtures.items():
            for name in fixtures:
                if name in self.fixtures or name in self.shared:
                    self.error(self.tree, "overriding a fixture in a test class is unsupported: " + name)
        self.validate_declarations()
        self.validate_constants()

    def collect_class(self, node):
        """A plain test class: pytest runs each test method on a new instance."""
        if node.bases or node.keywords:
            self.error(node, "test classes with base classes or class keywords are unsupported")
        if self.conftest:
            self.error(node, "conftest.py cannot define tests")
        self.shadowed = set()
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.shadowed.add(statement.name)
            elif isinstance(statement, ast.Import):
                self.shadowed.update(alias.asname or alias.name.split(".")[0] for alias in statement.names)
            elif isinstance(statement, ast.ImportFrom):
                self.shadowed.update(alias.asname or alias.name for alias in statement.names)
            else:
                self.shadowed.update(_bound_names(statement))
        prelude = self.preludes.setdefault(node, [])
        # A class's decorators run before its body does.
        parameters, marks, usefixtures = self.decorations(node, prelude, {})
        members = set()
        tests = []
        for statement in node.body:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if statement.name in members:
                self.error(statement, "duplicate method in a test class: " + statement.name)
            members.add(statement.name)
            if statement.name in ("__init__", "__new__"):
                # pytest warns and collects nothing from such a class.
                self.error(statement, "test classes cannot define __init__ or __new__")
            test = self.declare(statement, node, prelude)
            if test is not None:
                tests.append(test)
        self.shadowed = None
        for test in tests:
            test.parameters += parameters
            test.marks += marks
            test.usefixtures += usefixtures
            self.finish_test(test)
        self.classes.append(node)

    def declare(self, node, owner, prelude):
        """Record a fixture or a test (returned); other functions are the module's own."""
        fixture = [dec for dec in node.decorator_list
                   if self.name(dec.func if isinstance(dec, ast.Call) else dec) == "pytest.fixture"]
        if fixture:
            if len(fixture) != 1 or len(node.decorator_list) != 1:
                self.error(node, "fixtures support one fixture decorator only")
            if isinstance(node, ast.AsyncFunctionDef):
                self.error(node, "async fixtures are unsupported")
            self.declare_fixture(node, fixture[0], owner, prelude)
            return None
        if not node.name.startswith("test"):
            if owner is not None and any(self.name(dec.func if isinstance(dec, ast.Call) else dec)
                                         for dec in node.decorator_list):
                self.error(node, "pytest decorators on a helper method are unsupported")
            return None
        if self.conftest:
            self.error(node, "conftest.py cannot define tests")
        if isinstance(node, ast.AsyncFunctionDef) or self.is_generator(node):
            self.error(node, "async and generator tests are unsupported")
        annotations = {arg.arg: arg.annotation for arg in node.args.args + node.args.kwonlyargs
                       if arg.annotation is not None}
        parameters, marks, usefixtures = self.decorations(node, prelude, annotations)
        test = Test(node, owner, parameters, marks, usefixtures)
        self.tests.append(test)
        return test

    def finish_test(self, test):
        all_names = [name for parameter in test.parameters for name in parameter.names]
        if len(all_names) != len(set(all_names)):
            self.error(test.function, "duplicate parametrized argument")
        required = self.arguments(test.function, bound=test.owner is not None)
        if any(name not in required for name in all_names):
            self.error(test.function, "parametrized arguments must be required test arguments")

    def declare_fixture(self, node, decorator, owner, prelude):
        options = {}
        table = None
        ids = None
        if isinstance(decorator, ast.Call):
            if decorator.args:
                self.error(decorator, "fixture options must be keywords")
            plain = []
            for kw in decorator.keywords:
                if kw.arg == "params" and table is None:
                    table = kw.value
                elif kw.arg == "ids" and ids is None:
                    ids = kw.value
                else:
                    plain.append(kw)
            options = self.keywords(ast.copy_location(ast.Call(func=decorator.func, args=[], keywords=plain),
                                                      decorator), {"scope", "autouse", "name"})
        scope = options.get("scope", "function")
        if not isinstance(scope, str) or scope not in SCOPES:
            self.error(decorator, "fixture scope must be function, class, module or session")
        if not isinstance(options.get("autouse", False), bool):
            self.error(decorator, "autouse must be a literal boolean")
        fixture_name = options.get("name", node.name)
        if (not isinstance(fixture_name, str) or not fixture_name.isidentifier()
                or keyword.iskeyword(fixture_name) or fixture_name == "request"
                or fixture_name.startswith("_pyn_") or fixture_name in self.aliases):
            self.error(decorator, "fixture name must be a non-reserved literal identifier")
        fixtures = self.fixtures if owner is None else self.class_fixtures.setdefault(owner.name, {})
        if fixture_name in fixtures:
            self.error(decorator, "duplicate fixture name: " + fixture_name)
        if owner is None and fixture_name in self.shared:
            self.error(decorator, "overriding a conftest.py fixture is unsupported: " + fixture_name)
        if owner is not None and scope != "function":
            self.error(decorator, "fixtures defined in a test class must be function-scoped")
        arguments = self.arguments(node, bound=owner is not None)
        request = "request" in arguments
        parameter = None
        if table is not None:
            if scope != "function":
                # pytest reorders tests around a parametrized fixture of a wider scope.
                self.error(decorator, "parametrized fixtures must be function-scoped")
            parameter, setup = self.table(decorator, [fixture_name], True, table,
                                          self.constant(ids, True) if ids is not None else None, {}, "fixture params")
            prelude.extend(setup)
        elif ids is not None:
            self.error(decorator, "fixture ids require params")
        if request:
            if parameter is None:
                self.error(node, "request is supported only as request.param of a parametrized fixture")
            for part in ast.walk(node):
                if isinstance(part, ast.arg) and part.arg == "request" and part not in node.args.args + node.args.kwonlyargs:
                    self.error(part, "request is supported only as request.param of a parametrized fixture")
        generator = self.is_generator(node)
        if scope != "function":
            call = "_pyn_scope_get_" + node.name
        elif owner is not None:
            call = "_pyn_instance." + node.name
        else:
            call = node.name
        fixtures[fixture_name] = Fixture(
            node, [name for name in arguments if name != "request"], generator, options.get("autouse", False),
            scope, parameter, request, owner.name if owner is not None else "", call,
            self.has_value(node, generator))

    def validate_declarations(self):
        declarations = ({test.function.name for test in self.tests if test.owner is None}
                        | self.fixture_functions() | {node.name for node in self.classes})
        for name in declarations:
            bindings = 0
            for node in self.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    bindings += node.name == name
                elif isinstance(node, ast.Import):
                    bindings += sum((alias.asname or alias.name.split(".")[0]) == name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    bindings += sum((alias.asname or alias.name) == name for alias in node.names)
                else:
                    bindings += _bound_names(node).count(name)
            if bindings != 1:
                self.error(self.tree, "test and fixture declarations cannot be rebound: " + name)

    def declared_functions(self):
        """Every test and fixture function, at module level and in test classes."""
        functions = {test.function for test in self.tests}
        functions.update(fixture.function for fixture in self.fixtures.values())
        for fixtures in self.class_fixtures.values():
            functions.update(fixture.function for fixture in fixtures.values())
        return functions

    def validate_constants(self):
        # Literal table references preserve aliases, but their number/shape must
        # not change during module import. Reject mutation/escape instead of
        # silently collecting a stale subset of the real pytest cases.
        if not self.metadata_constants:
            return
        postponed = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                        and any(alias.name == "annotations" for alias in node.names) for node in self.tree.body)
        declared = self.declared_functions()
        bound = set()
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound.add(node.name)
            elif isinstance(node, ast.Import):
                bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                bound.update(alias.asname or alias.name for alias in node.names)
            else:
                bound.update(_bound_names(node))
        # Built-in method decorators run no module code, unless the module rebinds them.
        builtin = {"property", "staticmethod", "classmethod"} - bound

        def static(statements, method=False):
            for node in statements:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Function bodies run later; arbitrary decorators and defaults
                    # could mutate a parameter table before pytest collects it.
                    plain = method and all(isinstance(decorator, ast.Name) and decorator.id in builtin
                                           for decorator in node.decorator_list)
                    if node not in declared and node.decorator_list and not plain:
                        self.error(node, "named parameter tables require static module initialization")
                    evaluated = list(node.args.defaults) + [value for value in node.args.kw_defaults if value]
                    if not postponed:
                        arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                        arguments += [arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None]
                        evaluated += [arg.annotation for arg in arguments if arg.annotation is not None]
                        if node.returns is not None:
                            evaluated.append(node.returns)
                    if any(isinstance(part, ast.Call) for value in evaluated for part in ast.walk(value)):
                        self.error(node, "named parameter tables require static defaults and evaluated annotations")
                    continue
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.ClassDef) and not node.keywords and (
                        node in self.classes or not node.decorator_list) and all(
                        not isinstance(part, ast.Call) for base in node.bases for part in ast.walk(base)):
                    # A class body runs at import like module code; a test class's
                    # decorators are pytest marks, which hold literals only.
                    static(node.body, True)
                    continue
                if any(isinstance(part, (ast.Call, ast.AugAssign, ast.Delete, ast.ClassDef, ast.If, ast.For,
                                         ast.While, ast.Try, ast.With))
                       or isinstance(part, ast.Subscript) and isinstance(part.ctx, ast.Store)
                       for part in ast.walk(node)):
                    self.error(node, "named parameter tables require static module initialization")

        static(self.tree.body)
        for name in self.metadata_constants:
            definitions = []
            for node in self.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                    continue
                references = [part for part in ast.walk(node) if isinstance(part, ast.Name) and part.id == name]
                if not references:
                    continue
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and references == [
                        part for part in references if isinstance(part.ctx, ast.Store)]:
                    definitions.append(node)
                else:
                    self.error(node, "parametrize constants cannot be mutated or escape during import: " + name)
            if len(definitions) != 1:
                self.error(self.tree, "parametrize constants require one literal binding: " + name)

    def fixture_functions(self):
        return {fixture.function.name for fixture in self.fixtures.values()}

    def visible(self, owner):
        """The fixtures a test of this class (or of the module) can request, by name."""
        fixtures = dict(BUILTIN_FIXTURES)
        fixtures.update(self.shared)
        fixtures.update(self.fixtures)
        if owner is not None:
            fixtures.update(self.class_fixtures.get(owner.name, {}))
        return fixtures

    def closure(self, test, direct):
        """pytest's fixture closure of a test: its order of parametrization and setup.

        Autouse fixtures come first (conftest.py's, the module's, the class's, each by
        function name as pytest discovers them), then usefixtures and arguments; each
        name is followed by what its fixture requests, depth first, and wider scopes
        then move ahead. Directly parametrized names are not fixtures here.
        """
        fixtures = self.visible(test.owner)
        names = []
        groups = [self.shared, self.fixtures]
        if test.owner is not None:
            groups.append(self.class_fixtures.get(test.owner.name, {}))
        for group in groups:
            names += sorted((name for name, fixture in group.items() if fixture.autouse),
                            key=lambda name: group[name].function.name)
        names += test.usefixtures + self.arguments(test.function, bound=test.owner is not None)
        closure = []

        def visit(name):
            if name in closure:
                return
            closure.append(name)
            if name in direct:
                return
            if name not in fixtures:
                self.error(test.function, "unknown or unsupported fixture: " + name)
            for dependency in fixtures[name].dependencies:
                visit(dependency)

        for name in names:
            visit(name)
        closure.sort(key=lambda name: 0 if name in direct else SCOPES[fixtures[name].scope], reverse=True)
        return closure

    def setup_order(self, test, direct, closure):
        """The closure's fixtures in the order pytest sets them up: each after what it requests."""
        fixtures = self.visible(test.owner)
        order = []
        visiting = set()

        def visit(name, dependent):
            scope = "function" if name in direct else fixtures[name].scope
            if dependent is not None and SCOPES[scope] < SCOPES[fixtures[dependent].scope]:
                # pytest reports ScopeMismatch when the test sets up.
                self.error(test.function, f"fixture {dependent} of {fixtures[dependent].scope} scope cannot "
                           f"request {name} of {scope} scope")
            if name in direct:
                return
            if name in visiting:
                self.error(test.function, "fixture dependency cycle at " + name)
            if name in order:
                return
            visiting.add(name)
            for dependency in fixtures[name].dependencies:
                visit(dependency, name)
            visiting.remove(name)
            order.append(name)

        for name in closure:
            visit(name, None)
        return order

    def validate_body(self):
        parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        decorators = {item for holder in [*self.declared_functions(), *self.classes]
                      for dec in holder.decorator_list for item in ast.walk(dec)}
        method_fixtures = {fixture.function.name for fixtures in self.class_fixtures.values()
                           for fixture in fixtures.values()}
        monkeypatch = all("monkeypatch" not in fixtures for fixtures in
                          [self.shared, self.fixtures, *self.class_fixtures.values()])
        for node in ast.walk(self.tree):
            if node in decorators or isinstance(node, (ast.Import, ast.ImportFrom, ast.alias)):
                continue
            if (isinstance(node, ast.Attribute) and node.attr in {"__test__", "pytestmark"}
                    and isinstance(node.value, ast.Name)):
                self.error(node, "runtime pytest collection metadata is unsupported")
            if (isinstance(node, ast.Attribute) and node.attr in method_fixtures
                    and isinstance(node.value, ast.Name) and node.value.id == "self"):
                self.error(node, "fixture functions may only be requested by argument name")
            if (monkeypatch and isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "monkeypatch" and node.attr not in MONKEYPATCH):
                self.error(node, f"monkeypatch.{node.attr} is unsupported; setenv, delenv and undo are supported")
            if isinstance(node, ast.Global) and any(name in self.fixture_functions() for name in node.names):
                self.error(node, "mutating fixture declarations through globals is unsupported")
            if isinstance(node, ast.Name) and node.id in self.fixture_functions():
                scope = parents.get(node)
                ancestors = {node}
                comprehension_names = set()
                while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    if isinstance(scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                        # The first iterable is evaluated outside the implicit
                        # comprehension scope; targets only shadow inside it.
                        if scope.generators[0].iter not in ancestors:
                            for generator in scope.generators:
                                comprehension_names.update(_bound_names(generator.target))
                    ancestors.add(scope)
                    scope = parents.get(scope)
                arguments = [] if scope is None else scope.args.posonlyargs + scope.args.args + scope.args.kwonlyargs
                local_names = set() if scope is None else _local_bindings(scope)
                if node.id not in {argument.arg for argument in arguments} | local_names | comprehension_names:
                    self.error(node, "fixture functions may only be requested by argument name")
            name = self.name(node)
            if not name:
                continue
            parent = parents.get(node)
            if isinstance(parent, ast.Attribute) and parent.value is node:
                continue
            if not (isinstance(parent, ast.Call) and parent.func is node and name in PYTEST_CALLS):
                self.error(node, "unsupported pytest use: " + name)
            if name == "pytest.raises":
                expected = parent.args[0] if len(parent.args) == 1 else None
                if (expected is None or (isinstance(expected, ast.Tuple) and not expected.elts)
                        or any(kw.arg != "match" for kw in parent.keywords)):
                    self.error(parent, "raises supports one exception class or a literal tuple of classes, "
                               "and optional match= only")
            elif name == "pytest.approx":
                if len(parent.args) != 1 or any(kw.arg not in {"rel", "abs", "nan_ok"} for kw in parent.keywords):
                    self.error(parent, "approx supports one number and rel=, abs= and nan_ok= only")
            elif len(parent.args) > 1 or any(kw.arg != "reason" for kw in parent.keywords):
                self.error(parent, "outcome helpers accept one reason only")
        for fixtures in [self.fixtures, *self.class_fixtures.values()]:
            for fixture in fixtures.values():
                if not fixture.request:
                    continue
                for node in ast.walk(fixture.function):
                    if isinstance(node, ast.Name) and node.id == "request":
                        parent = parents.get(node)
                        if not (isinstance(parent, ast.Attribute) and parent.attr == "param"
                                and isinstance(parent.ctx, ast.Load)):
                            self.error(node, "request is supported only as request.param of a parametrized fixture")

    def typed_raises(self, function):
        """`with pytest.raises(E) as info:` blocks to expand so info.value keeps class E.

        The support module's context holds a BaseException, whose attributes compiled
        code cannot read. Where a function reads `info.value.attribute`, its block
        becomes try/except E, and info.value a variable of that class. Returns the
        With nodes and info names to rewrite; anything the expansion could change
        (another binding of the name, a use other than .value/.type/.typename/.match(),
        leaving the block by return/break/continue) keeps the context manager.
        """
        own = list(_own_nodes(function))
        parents = {child: node for node in own for child in ast.iter_child_nodes(node)}
        nested = {part.id for node in ast.walk(function) if node is not function
                  and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
                  for part in ast.walk(node) if isinstance(part, ast.Name)}
        arguments = {arg.arg for arg in ast.walk(function.args) if isinstance(arg, ast.arg)}
        declared = {name for node in own if isinstance(node, (ast.Global, ast.Nonlocal)) for name in node.names}
        # A class named by something the function binds: the block's body could bind it
        # again before the handler reads it, where pytest.raises keeps the class it was given.
        rebindable = _local_bindings(function) | arguments | declared
        blocks = {}
        names = {}
        for node in own:
            if not (isinstance(node, ast.With) and len(node.items) == 1):
                continue
            call = node.items[0].context_expr
            target = node.items[0].optional_vars
            if not (isinstance(call, ast.Call) and self.name(call.func) == "pytest.raises"
                    and len(call.args) == 1 and isinstance(target, ast.Name)
                    and all(kw.arg == "match" for kw in call.keywords) and len(call.keywords) <= 1):
                continue
            expected = call.args[0]
            while isinstance(expected, ast.Attribute):
                expected = expected.value
            name = target.id
            if (not isinstance(expected, ast.Name) or name in nested or name in arguments or name in declared
                    or name in names or expected.id in rebindable):
                continue
            references = [part for part in own if isinstance(part, ast.Name) and part.id == name]
            if sum(not isinstance(part.ctx, ast.Load) for part in references) != 1:
                continue
            inside = {part for statement in node.body for part in ast.walk(statement)}
            if any(isinstance(part, (ast.Return, ast.Break, ast.Continue, ast.Yield, ast.YieldFrom, ast.Await))
                   or part in references for part in inside):
                continue
            fields = False
            supported = True
            for part in references:
                if part is target:
                    continue
                parent = parents.get(part)
                if not (isinstance(parent, ast.Attribute) and isinstance(parent.ctx, ast.Load)
                        and parent.attr in {"value", "type", "typename", "match"}):
                    supported = False
                    break
                outer = parents.get(parent)
                if parent.attr == "match" and not (isinstance(outer, ast.Call) and outer.func is parent
                                                   and len(outer.args) == 1 and not outer.keywords):
                    supported = False
                    break
                if (parent.attr == "value" and isinstance(outer, ast.Attribute) and outer.value is parent
                        and isinstance(outer.ctx, ast.Load)):
                    fields = True
            if supported and fields:
                names[name] = blocks[node] = self.counter
                self.counter += 1
        return blocks, names

    def captured(self, node, location):
        """A comparison assertion's message showing its operands' reprs, or None.

        Literal operands show their source and names are read again; other operands are
        bound once, in order, by reserved walrus temporaries. The message runs only on
        failure, and a failing __repr__ cannot replace it. Names keep any narrowing the
        assertion gives them.
        """
        test = node.test
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and type(test.ops[0]) in OPERATORS):
            return None
        sides = [test.left, test.comparators[0]]
        if all(_literal(side) for side in sides):
            return None
        parts = [ast.Constant(location + "\nassert ")]
        for index, side in enumerate(sides):
            if index:
                parts.append(ast.Constant(f" {OPERATORS[type(test.ops[0])]} "))
            if _literal(side):
                parts.append(ast.Constant(ast.unparse(side)))
                continue
            if isinstance(side, ast.Name):
                value = ast.Name(side.id, ast.Load())
            else:
                temporary = f"_pyn_operand_{self.counter}"
                self.counter += 1
                bound = ast.NamedExpr(ast.Name(temporary, ast.Store()), side)
                if index:
                    test.comparators[0] = bound
                else:
                    test.left = bound
                value = ast.Name(temporary, ast.Load())
            parts.append(ast.FormattedValue(ast.Call(_attribute("saferepr"), [value], []), -1, None))
        return ast.JoinedStr(parts)

    def approximate(self, node, location, operator):
        """The message of `assert actual == pytest.approx(expected)`: both operands' reprs.

        visit_Compare made the comparison a call; its arguments are bound as captured()
        binds a comparison's operands.
        """
        call = node.test.operand if isinstance(node.test, ast.UnaryOp) else node.test
        if not (operator in ("==", "!=") and isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and call.func.attr == "approx_equal" and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "_pyn_support"):
            return None
        parts = [ast.Constant(location + "\nassert ")]
        for index, side in enumerate(call.args):
            if index:
                parts.append(ast.Constant(f" {operator} "))
            temporary = f"_pyn_operand_{self.counter}"
            self.counter += 1
            call.args[index] = ast.NamedExpr(ast.Name(temporary, ast.Store()), side)
            parts.append(ast.FormattedValue(ast.Call(_attribute("saferepr"), [ast.Name(temporary, ast.Load())], []),
                                            -1, None))
        return ast.JoinedStr(parts)

    def transform_source(self):
        declarations = self.declared_functions()
        classes = set(self.classes)
        requests = {fixture.function for fixtures in [self.fixtures, *self.class_fixtures.values()]
                    for fixture in fixtures.values() if fixture.request}
        filename = self.filename
        generator = self

        class RequestParameter(ast.NodeTransformer):
            """A parametrized fixture reads its case's value where it read request.param."""
            def visit_arg(self, node):
                if node.arg == "request":
                    node.arg = "_pyn_request_param"
                    node.annotation = None
                return node

            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == "request" and node.attr == "param":
                    return ast.copy_location(ast.Name("_pyn_request_param", ast.Load()), node)
                return self.generic_visit(node)

        class Rewrite(ast.NodeTransformer):
            def __init__(self):
                self.scopes = []
                # Per enclosing function: expanded raises blocks and their info names.
                self.raises = []

            def caught(self, node):
                """The expansion number of `info` in info.value, or None."""
                if isinstance(node, ast.Name) and self.raises and self.scopes[-1] == "function":
                    return self.raises[-1][1].get(node.id)
                return None

            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name == "pytest":
                        alias.asname = alias.asname or "pytest"
                        alias.name = "pytest_native_support"
                return node

            def visit_ImportFrom(self, node):
                if node.module == "pytest":
                    node.names = [alias for alias in node.names if alias.name not in {"fixture", "mark", "param"}]
                    node.module = "pytest_native_support"
                    return node if node.names else None
                return node

            def scoped(self, node, scope):
                self.scopes.append(scope)
                try:
                    return self.generic_visit(node)
                finally:
                    self.scopes.pop()

            def visit_FunctionDef(self, node):
                if node in declarations:
                    node.decorator_list = []
                if node in requests:
                    node = RequestParameter().visit(node)
                self.raises.append(generator.typed_raises(node))
                try:
                    return self.scoped(node, "function")
                finally:
                    self.raises.pop()

            def visit_AsyncFunctionDef(self, node):
                return self.scoped(node, "other")

            def visit_Lambda(self, node):
                return self.scoped(node, "other")

            def visit_ClassDef(self, node):
                if node in classes:
                    node.decorator_list = []
                return self.scoped(node, "other")

            def visit_With(self, node):
                number = self.raises[-1][0].get(node) if self.raises and self.scopes[-1] == "function" else None
                node = self.generic_visit(node)
                if number is None:
                    return node
                call = node.items[0].context_expr
                expected = call.args[0]
                value = ast.Name(f"_pyn_value_{number}", ast.Store())
                error = f"_pyn_caught_{number}"
                pattern = f"_pyn_match_{number}"
                # pytest.raises(E, match=...) reads E and checks the pattern before the body.
                before = [ast.Expr(expected)]
                handler = [ast.Assign([value], ast.Name(error, ast.Load()))]
                if call.keywords:
                    before += [ast.Assign([ast.Name(pattern, ast.Store())], call.keywords[0].value),
                               ast.Expr(ast.Call(_attribute("check_pattern"), [ast.Name(pattern, ast.Load())], []))]
                    handler.append(ast.Expr(ast.Call(_attribute("match_exception"), [
                        ast.Name(pattern, ast.Load()),
                        ast.Call(ast.Name("str", ast.Load()), [ast.Name(error, ast.Load())], [])], [])))
                missing = ast.Expr(ast.Call(_attribute("fail"), [ast.Constant("DID NOT RAISE " + ast.unparse(expected))], []))
                block = ast.Try(node.body, [ast.ExceptHandler(ast.parse(ast.unparse(expected), mode="eval").body,
                                                              error, handler)], [missing], [])
                return [ast.copy_location(statement, node) for statement in [*before, block]]

            def visit_Attribute(self, node):
                number = self.caught(node.value)
                if number is not None and isinstance(node.ctx, ast.Load) and node.attr != "match":
                    value = ast.Name(f"_pyn_value_{number}", ast.Load())
                    if node.attr == "value":
                        return ast.copy_location(value, node)
                    kind = ast.Call(ast.Name("type", ast.Load()), [value], [])
                    return ast.copy_location(kind if node.attr == "type" else ast.Attribute(kind, "__name__", ast.Load()),
                                             node)
                return self.generic_visit(node)

            def visit_Compare(self, node):
                node = self.generic_visit(node)
                right = node.comparators[0]
                if (len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq))
                        and isinstance(right, ast.Call) and generator.name(right.func) == "pytest.approx"
                        and not (isinstance(node.left, ast.Call) and generator.name(node.left.func) == "pytest.approx")):
                    # A number's == does not reach Approx.__eq__ in compiled code; this
                    # keeps the operands' order.
                    call = ast.Call(_attribute("approx_equal"), [node.left, right], [])
                    if isinstance(node.ops[0], ast.NotEq):
                        return ast.copy_location(ast.UnaryOp(ast.Not(), call), node)
                    return ast.copy_location(call, node)
                return node

            def visit_Call(self, node):
                number = self.caught(node.func.value) if isinstance(node.func, ast.Attribute) else None
                if number is not None and node.func.attr == "match":
                    text = ast.Call(ast.Name("str", ast.Load()), [ast.Name(f"_pyn_value_{number}", ast.Load())], [])
                    return ast.copy_location(ast.Call(_attribute("match_exception"),
                                                      [self.visit(node.args[0]), text], []), node)
                node = self.generic_visit(node)
                if (generator.name(node.func) == "pytest.raises" and len(node.args) == 1
                        and isinstance(node.args[0], ast.Tuple)):
                    node.func = _attribute("raises_any")
                    node.args = [ast.List(node.args[0].elts, ast.Load())]
                return node

            def visit_Assert(self, node):
                location = f"{filename}:{node.lineno}: assert {ast.unparse(node.test)}"
                custom = node.msg is not None
                operator = (OPERATORS.get(type(node.test.ops[0]))
                            if isinstance(node.test, ast.Compare) and len(node.test.ops) == 1 else None)
                node = self.generic_visit(node)
                if not custom:
                    detail = None
                    if generator.operands and self.scopes and self.scopes[-1] == "function":
                        detail = generator.captured(node, location) or generator.approximate(node, location, operator)
                    node.msg = detail or ast.Constant(location)
                return node

        # Validate before removing syntax; otherwise an unsupported use could disappear.
        self.validate_body()
        imports = ["import pytest_native_support as _pyn_support"]
        if self.shared:
            imports.append("import conftest as _pyn_conftest")
        if self.builtins_used:
            imports.append("import pytest_native_fixtures as _pyn_fixtures")
        output = []
        # Each entry: (text, the statement it came from or None).
        placed = False
        for node in self.tree.body:
            leading = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                       and isinstance(node.value.value, str) and not output
                       or isinstance(node, ast.ImportFrom) and node.module == "__future__")
            if not leading and not placed:
                # After a docstring and __future__ imports, before anything can use them.
                output += [(line, None) for line in imports]
                placed = True
            # (Declarations a decorator evaluated report at the function or class.)
            output += [(line, node) for line in self.preludes.get(node, [])]
            rewritten = Rewrite().visit(node)
            if rewritten is not None:
                output.append((ast.unparse(ast.fix_missing_locations(rewritten)), rewritten))
        if not placed:
            output += [(line, None) for line in imports]
        return output

    @staticmethod
    def value_annotation(function, generator):
        """Source of the type a fixture provides, from its return annotation, or None."""
        annotation = function.returns
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return None
        if annotation is None or (isinstance(annotation, ast.Constant) and annotation.value is None):
            return None
        if not generator:
            return ast.unparse(annotation)
        # Iterator[T], Iterable[T] or Generator[T, S, R], however the module names them.
        if not isinstance(annotation, ast.Subscript):
            return None
        kind = annotation.value.attr if isinstance(annotation.value, ast.Attribute) else getattr(annotation.value, "id", "")
        if kind not in {"Iterator", "Iterable", "Generator"}:
            return None
        item = annotation.slice.elts[0] if isinstance(annotation.slice, ast.Tuple) and annotation.slice.elts else annotation.slice
        if isinstance(item, ast.Constant) and item.value is None:
            return None
        return ast.unparse(item)

    def scope_block(self, fixture):
        """A module, class or session fixture's cache: set up on first request, kept until
        the scope's last case, and a setup failure repeated to every later request."""
        function = fixture.function
        key = function.name
        arguments = ", ".join(fixture.dependencies)
        call = f"{function.name}({', '.join(f'{name}={name}' for name in fixture.dependencies)})"
        lines = [f"_pyn_scope_failed_{key}: list[BaseException] = []", f"_pyn_scope_active_{key} = [False]"]
        if fixture.valued:
            # The cache starts empty: the fixture's own annotation types it where the
            # compiler cannot infer that from the value (a string keeps CPython from
            # evaluating names that exist for type checkers only).
            hint = self.value_annotation(function, fixture.generator)
            lines.append(f"_pyn_scope_value_{key}{': ' + repr('list[' + hint + ']') if hint else ''} = []")
        if fixture.generator:
            lines.append(f"_pyn_scope_generator_{key} = []")
        lines += [f"def _pyn_scope_finish_{key}() -> None:", f"    _pyn_scope_failed_{key}.clear()"]
        if fixture.valued:
            lines.append(f"    _pyn_scope_value_{key}.clear()")
        lines += [f"    if _pyn_scope_active_{key}[0]:", f"        _pyn_scope_active_{key}[0] = False"]
        if fixture.generator:
            lines += [f"        _pyn_generator = _pyn_scope_generator_{key}.pop()", "        try:",
                      "            next(_pyn_generator)", "        except StopIteration:", "            pass",
                      "        else:", "            try:", "                _pyn_generator.close()",
                      "            finally:",
                      f"                raise RuntimeError({('fixture ' + key + ' yielded more than once')!r})"]
        lines += [f"def _pyn_scope_get_{key}({arguments}):", f"    if _pyn_scope_failed_{key}:",
                  f"        raise _pyn_scope_failed_{key}[0]", f"    if not _pyn_scope_active_{key}[0]:",
                  # The scope clears a failed setup too, so its next use runs the fixture again.
                  f"        _pyn_support.{FINALIZERS[fixture.scope]}.append(_pyn_scope_finish_{key})",
                  "        try:"]
        if fixture.generator:
            lines += [f"            _pyn_generator = {call}", "            try:",
                      f"                {'_pyn_value = ' if fixture.valued else ''}next(_pyn_generator)",
                      "            except StopIteration:",
                      f"                raise RuntimeError({('fixture ' + key + ' did not yield')!r})"]
        else:
            lines.append(f"            {'_pyn_value = ' if fixture.valued else ''}{call}")
        lines += ["        except KeyboardInterrupt:", "            raise",
                  "        except BaseException as _pyn_error:",
                  f"            _pyn_scope_failed_{key}.append(_pyn_error)", "            raise"]
        if fixture.generator:
            lines.append(f"        _pyn_scope_generator_{key}.append(_pyn_generator)")
        if fixture.valued:
            lines.append(f"        _pyn_scope_value_{key}.append(_pyn_value)")
        lines.append(f"        _pyn_scope_active_{key}[0] = True")
        if fixture.valued:
            lines.append(f"    return _pyn_scope_value_{key}[0]")
        return "\n".join(lines)

    def execution(self, test, order, values, fixture_values, xfail, label):
        """Set up a case's fixtures, call its test and tear down: the statements of one run."""
        fixtures = self.visible(test.owner)
        function = test.function
        mode = 0 if xfail is None else 2 if xfail.raises else 1

        def failure(phase, p):
            # A setup failure is an error; xfail expects any exception, or only raises=.
            unexpected = "failed" if phase == "call" else "error"
            def record(outcome, q):
                return q + f"_pyn_report.record(_pyn_id, {phase!r}, {outcome!r}, _pyn_support.describe(_pyn_error))"
            if mode == 0:
                return [record(unexpected, p + "    ")]
            if mode == 1:
                return [record("xfailed", p + "    ")]
            return [p + f"    if isinstance(_pyn_error, {xfail.raises}):", record("xfailed", p + "        "),
                    p + "    else:", record(unexpected, p + "        ")]

        lines = [f"_pyn_teardown.mode = {mode}"] if mode else []
        lines.append("try:")
        if test.owner is not None:
            lines.append(f"    _pyn_instance = {test.owner.name}()")
        indent = 1
        generators = []
        values = dict(values)
        for index, name in enumerate(order):
            fixture = fixtures[name]
            arguments = [f"{dependency}={values[dependency]}" for dependency in fixture.dependencies]
            if fixture.named:
                arguments.insert(0, repr(label))
            if fixture.request:
                arguments.append(f"_pyn_request_param={fixture_values[name]}")
            if fixture.origin == "builtin":
                self.builtins_used = True
            call = f"{fixture.call}({', '.join(arguments)})"
            variable = f"_pyn_fixture_{index}"
            p = "    " * indent
            if fixture.scope != "function":
                # (A scope's getter returns its cached value, or runs for its effect.)
                lines += [p + f"{variable} = {call}"] if fixture.valued else [p + call, p + f"{variable} = None"]
            elif fixture.generator:
                generator = f"_pyn_generator_{index}"
                lines += [p + f"{generator} = {call}", p + "try:",
                          p + f"    {variable} = next({generator})", p + "except StopIteration:",
                          p + f"    raise RuntimeError({('fixture ' + name + ' did not yield')!r})",
                          p + "try:"]
                generators.append((indent, generator, name))
                indent += 1
            else:
                lines.append(p + f"{variable} = {call}")
            values[name] = variable
        p = "    " * indent
        callee = ("_pyn_instance." if test.owner is not None else "") + function.name
        arguments = ", ".join(f"{name}={values[name]}"
                              for name in self.arguments(function, bound=test.owner is not None))
        lines += [p + "_pyn_report.record(_pyn_id, 'setup', 'passed', '')", p + "try:",
                  p + f"    {callee}({arguments})",
                  p + "except _pyn_support.Skipped as _pyn_error:",
                  p + "    _pyn_report.record(_pyn_id, 'call', 'skipped', str(_pyn_error))",
                  p + "except _pyn_support.XFailed as _pyn_error:",
                  p + "    _pyn_report.record(_pyn_id, 'call', 'xfailed', str(_pyn_error))",
                  p + "except KeyboardInterrupt:", p + "    raise",
                  p + "except BaseException as _pyn_error:", *failure("call", p), p + "else:"]
        success = "failed" if xfail and xfail.strict else "xpassed" if xfail else "passed"
        detail = "[XPASS(strict)] " + xfail.reason if xfail and xfail.strict else xfail.reason if xfail else ""
        lines.append(p + f"    _pyn_report.record(_pyn_id, 'call', {success!r}, {detail!r})")
        matched = f", isinstance(_pyn_error, {xfail.raises})" if mode == 2 else ""
        for level, generator, name in reversed(generators):
            p = "    " * level
            lines += [p + "finally:", p + "    try:", p + "        try:",
                      p + f"            next({generator})", p + "        except StopIteration:",
                      p + "            pass", p + "        else:", p + "            try:",
                      p + f"                {generator}.close()", p + "            finally:",
                      p + f"                raise RuntimeError({('fixture ' + name + ' yielded more than once')!r})",
                      p + "    except _pyn_support.Skipped as _pyn_error:",
                      p + "        _pyn_teardown.skipped(str(_pyn_error))",
                      p + "    except _pyn_support.XFailed as _pyn_error:",
                      p + "        _pyn_teardown.xfailed(str(_pyn_error))",
                      p + "    except KeyboardInterrupt:", p + "        raise",
                      p + "    except BaseException as _pyn_error:",
                      p + f"        _pyn_teardown.failed(_pyn_support.describe(_pyn_error){matched})"]
        lines += ["except _pyn_support.Skipped as _pyn_error:",
                  "    _pyn_report.record(_pyn_id, 'setup', 'skipped', str(_pyn_error))",
                  "except _pyn_support.XFailed as _pyn_error:",
                  "    _pyn_report.record(_pyn_id, 'setup', 'xfailed', str(_pyn_error))",
                  "except KeyboardInterrupt:", "    raise",
                  "except BaseException as _pyn_error:", *failure("setup", "")]
        return lines

    def wrapper(self, test, case_number, nodeid, label, values, fixture_values, parameter_marks, closure):
        """One case: skip marks, then its run, then the teardown of every scope ending with it.

        _pyn_ends tells which wider scopes this case ends in the order the suite runs:
        its class (1), its module (2) or the session (3).
        """
        order = self.setup_order(test, set(values), closure)
        marks = test.marks + parameter_marks
        skip = next((mark for mark in marks if mark.kind in {"skip", "skipif"} and mark.condition is True), None)
        # Conditions that decorators evaluated at import (marker), tested in pytest's order.
        conditions = [mark for mark in marks if mark.kind == "skipif" and isinstance(mark.condition, str)]
        xfail = next((mark for mark in marks if mark.kind == "xfail" and mark.condition), None)
        lines = [f"def _pyn_case_{case_number}(_pyn_report: _pyn_support.Report, _pyn_ends: int) -> None:",
                 f"    _pyn_id = {nodeid!r}", "    _pyn_teardown = _pyn_support.Teardown()"]
        if skip:
            body = [f"_pyn_report.record(_pyn_id, 'setup', 'skipped', {skip.reason!r})"]
        elif xfail and not xfail.run:
            body = [f"_pyn_teardown.mode = {2 if xfail.raises else 1}",
                    f"_pyn_report.record(_pyn_id, 'setup', 'xfailed', {xfail.reason!r})"]
        else:
            body = self.execution(test, order, values, fixture_values, xfail, label)
        if conditions and not skip:
            guarded = []
            for index, mark in enumerate(conditions):
                guarded += [f"{'elif' if index else 'if'} _pyn_support.condition({mark.condition}):",
                            f"    _pyn_report.record(_pyn_id, 'setup', 'skipped', {mark.reason!r})"]
            body = [*guarded, "else:", *("    " + line for line in body)]
        lines += ["    " + line for line in body]
        # A skipped last case still ends its scopes, in its own teardown.
        lines.append("    _pyn_teardown.scopes(_pyn_ends)")
        if xfail and xfail.raises and not skip:
            lines += ["    for _pyn_error in _pyn_teardown.scope_errors:",
                      f"        if isinstance(_pyn_error, {xfail.raises}):",
                      "            _pyn_teardown.matched += 1"]
        lines.append("    _pyn_teardown.record(_pyn_report, _pyn_id)")
        return "\n".join(lines)

    def select(self, keys):
        """The cases that node-ID selectors name, in pytest's order.

        pytest drops a selector that another one contains (a class contains its tests,
        a test its parametrized cases) and collects the rest in the order given.
        """
        arguments = []
        for position, selector in enumerate(self.selected):
            base, bracket, rest = selector.partition("[")
            arguments.append((tuple(base.split("::")), bracket + rest if bracket else None, position, selector))
        kept = []
        for argument in sorted(arguments, key=lambda argument: (argument[0], argument[1] or "")):
            last = kept[-1] if kept else None
            if (last is None or argument[0][:len(last[0])] != last[0]
                    or (last[1] is not None and last[1] != argument[1])):
                kept.append(argument)
        run = []
        for parts, parametrization, _, selector in sorted(kept, key=lambda argument: argument[2]):
            matches = [index for index, (case_parts, case_parametrization) in enumerate(keys)
                       if case_parts[:len(parts)] == parts
                       and (parametrization is None or (case_parts == parts and case_parametrization == parametrization))]
            if not matches:
                raise CollectionError(f"not found: {self.filename}::{selector}")
            run += [index for index in matches if index not in run]
        return run

    def generate(self):
        self.collect()
        cases = []
        wrappers = []
        keys = []
        owners = []
        for test in self.tests:
            function = test.function
            direct = [name for parameter in test.parameters for name in parameter.names]
            closure = self.closure(test, direct)
            fixtures = self.visible(test.owner)
            # pytest parametrizes a test by its fixtures' params, in closure order, before
            # its own parametrize marks; the first varies slowest and leads the ID.
            axes = [(fixtures[name].params, name) for name in closure
                    if name not in direct and fixtures[name].params is not None]
            axes += [(parameter, None) for parameter in test.parameters]
            for indexes in itertools.product(*(range(len(parameter.values)) for parameter, _ in axes)):
                values = {}
                fixture_values = {}
                ids = []
                marks = []
                for (parameter, fixture), index in zip(axes, indexes):
                    if fixture is None:
                        values.update(zip(parameter.names, parameter.values[index]))
                    else:
                        fixture_values[fixture] = parameter.values[index][0]
                    ids.append(parameter.ids[index])
                    marks.extend(parameter.marks[index])
                parametrization = "[" + "-".join(ids) + "]" if ids else None
                parts = ((test.owner.name,) if test.owner is not None else ()) + (function.name,)
                nodeid = f"{self.filename}::{'::'.join(parts)}{parametrization or ''}"
                if len(cases) >= 10000:
                    self.error(function, "more than 10000 generated cases in one module")
                # pytest names a test's tmp_path directory after it.
                label = re.sub(r"\W", "_", function.name + (parametrization or ""))[:30]
                wrappers.append((self.wrapper(test, len(cases), nodeid, label, values, fixture_values, marks,
                                              closure), function))
                cases.append(nodeid)
                keys.append((parts, parametrization))
                owners.append(test.owner)
        # Node IDs select cases; every case's declarations still run at import.
        run = list(range(len(cases))) if self.selected is None else self.select(keys)
        chunks = self.transform_source()
        # Pragmas are comments and therefore absent from the AST. Preserve their
        # original opt-ins; the runner never opts the input into Any itself.
        pragmas = "\n".join(token.string for token in tokenize.generate_tokens(io.StringIO(self.source).readline)
                            if token.type == tokenize.COMMENT and re.match(r"#\s*pystachy:", token.string))
        chunks += [(self.scope_block(fixture), fixture.function) for fixture in self.fixtures.values()
                   if fixture.scope != "function"]
        if not self.conftest:
            runner = ["def _pyn_run(_pyn_path: str) -> int:", "    _pyn_report = _pyn_support.Report(_pyn_path)"]
            for position, index in enumerate(run):
                following = run[position + 1] if position + 1 < len(run) else None
                if following is None:
                    ends = 3 if self.session_end else 2
                else:
                    ends = 0 if owners[index] is not None and owners[following] is owners[index] else 1
                runner.append(f"    _pyn_case_{index}(_pyn_report, {ends})")
            runner.append("    return _pyn_report.finish()")
            chunks += [("import sys as _pyn_sys", None), *wrappers, ("\n".join(runner), None),
                       ("if __name__ == '__main__':\n    _pyn_sys.exit(_pyn_run(_pyn_sys.argv[1]))", None)]
        source = pragmas + "\n"
        lines = {}
        for text, origin in chunks:
            first = source.count("\n") + 1
            # Generated code for a declaration reports at that declaration; the
            # runner's own code (0) at no test line.
            lines[first] = getattr(origin, "lineno", 0)
            if lines[first]:
                try:
                    _pair_lines(origin, ast.parse(text).body[0], first - 1, lines)
                except (SyntaxError, IndexError):
                    pass
            source += text + "\n\n"
        return GeneratedModule(source.rstrip("\n") + "\n", [cases[index] for index in run], self.builtins_used,
                               lines)

    def export(self):
        """This conftest.py's fixtures as a test module of its directory calls them."""
        fixtures = {}
        for name, fixture in self.fixtures.items():
            params = fixture.params
            if params is not None:
                params = Parameter(params.names, [["_pyn_conftest." + value for value in row]
                                                  for row in params.values], params.ids, params.marks)
            fixtures[name] = dataclasses.replace(fixture, call="_pyn_conftest." + fixture.call, params=params,
                                                 origin="conftest")
        return fixtures


def _pair_lines(original, generated, offset, lines):
    """Map a generated statement's lines to the statement it was unparsed from.

    Both trees have the same statements; expressions may differ in shape, so only
    statement lists are walked in step.
    """
    if hasattr(original, "lineno") and hasattr(generated, "lineno"):
        lines.setdefault(generated.lineno + offset, original.lineno)
    for name in ("body", "orelse", "finalbody", "handlers", "cases"):
        first = getattr(original, name, None)
        second = getattr(generated, name, None)
        if isinstance(first, list) and isinstance(second, list) and len(first) == len(second):
            for one, other in zip(first, second):
                _pair_lines(one, other, offset, lines)


def original_line(module: GeneratedModule, line: int) -> int | None:
    """The test source line a generated line came from, or None for the runner's own code."""
    known = [generated for generated in module.lines if generated <= line]
    return module.lines[max(known)] or None if known else None


def generate(source: str, filename: str, operands: bool = True, selected=None, shared=None,
             session_end: bool = True) -> GeneratedModule:
    """Collect and adapt one module, or reject unsupported collection explicitly.

    operands keeps comparison operands for assertion failures (Generator.captured);
    selected lists node-ID selectors (`name`, `name[id]`, `Class` or `Class::name`) to
    run, in order; shared holds the fixtures of the directory's conftest.py
    (generate_conftest); session_end is false for every module but the last that runs.
    """
    return Generator(source, filename, operands, selected, shared, False, session_end).generate()


def generate_conftest(source: str, filename: str, operands: bool = True):
    """Adapt a conftest.py: its generated module, and its fixtures for generate(shared=)."""
    generator = Generator(source, filename, operands, conftest=True)
    module = generator.generate()
    return module, generator.export()
