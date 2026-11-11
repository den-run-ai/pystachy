"""Generate explicit native calls for a deliberately bounded pytest source dialect.

Collection reads syntax, never imports or executes test modules. Generated modules
retain their original top-level statements, fixtures and test bodies. Only known
pytest declarations are replaced. Unknown source declarations are an error; the
CLI's independent oracle detects collection behavior hidden in imported symbols.
"""

import ast
from dataclasses import dataclass
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


@dataclass
class Fixture:
    function: ast.FunctionDef
    dependencies: list[str]
    generator: bool
    autouse: bool


@dataclass
class Parameter:
    names: list[str]
    values: list[list[str]]
    ids: list[str]
    marks: list[list[tuple]]


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


class Generator:
    def __init__(self, source: str, filename: str, operands: bool = True, selected=None):
        self.source = source
        self.filename = filename
        self.operands = operands
        self.selected = selected
        try:
            self.tree = ast.parse(source, filename)
        except SyntaxError as error:
            raise CollectionError(f"{filename}:{error.lineno}: {error.msg}") from None
        # pytest imports a test module under its own name, so a script guard never runs there.
        self.tree.body = [node for node in self.tree.body if not _main_guard(node)]
        self.aliases = {}
        self.constants = {}
        self.fixtures = {}
        self.tests = []
        self.parameters = {}
        self.marks = {}
        self.usefixtures = {}
        self.preludes = {}
        self.counter = 0
        self.metadata_constants = set()

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

    def arguments(self, function):
        args = function.args
        if args.posonlyargs or args.vararg or args.kwarg:
            self.error(function, "tests and fixtures require named, non-variadic arguments")
        required = args.args[:len(args.args) - len(args.defaults)]
        required += [arg for arg, default in zip(args.kwonlyargs, args.kw_defaults) if default is None]
        return [arg.arg for arg in required]

    def is_generator(self, function):
        # Nested functions do not make their enclosing fixture a generator.
        pending = list(function.body)
        found = False
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(node, (ast.Yield, ast.YieldFrom)):
                found = True
            pending.extend(ast.iter_child_nodes(node))
        return found

    def parameter(self, decorator, function):
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
        table = decorator.args[1]
        inline = isinstance(table, (ast.List, ast.Tuple))
        rows = table.elts if inline else self.constant(table, True)
        if not isinstance(rows, (list, tuple)) or not rows:
            self.error(decorator, "parametrize needs a nonempty literal list or tuple")
        if len(rows) > 10000:
            self.error(decorator, "parametrize exceeds the 10000-case collection bound")
        ids = kws.get("ids")
        if ids is not None and (not isinstance(ids, (list, tuple)) or len(ids) != len(rows)
                                or any(not isinstance(item, str) for item in ids)):
            self.error(decorator, "ids must be a literal string list matching the value table")
        result = []
        generated_ids = []
        row_marks = []
        prelude = []
        annotations = {arg.arg: arg.annotation for arg in function.args.args + function.args.kwonlyargs
                       if arg.annotation is not None}
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
                self.error(decorator, "parametrize row width does not match argument names")
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
        return kind, condition, reason, kws.get("strict", False), kws.get("run", True)

    def collect(self):
        direct = set(self.tree.body)
        parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        seen = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and node.id.startswith("_pyn_"):
                self.error(node, "names beginning _pyn_ are reserved by the native runner")
            if isinstance(node, ast.Name) and node.id in {
                    "__file__", "__name__", "__package__", "__spec__", "__test__", "__annotations__",
                    "pytestmark", "pytest_plugins"}:
                self.error(node, "module metadata and dynamic pytest collection are unsupported: " + node.id)
            if (isinstance(node, ast.Name) and node.id.startswith(("test", "Test"))
                    and isinstance(node.ctx, ast.Store)):
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
                if node.name in {"setup_module", "setupModule", "teardown_module", "teardownModule",
                                 "setup_function", "teardown_function"}:
                    self.error(node, "xunit setup/teardown hooks are unsupported; use fixtures")
                if node.name.startswith("_pyn_") or node.name.startswith("pytest_"):
                    self.error(node, "reserved runner name or unsupported pytest hook: " + node.name)
                if node.name.startswith("test") and node not in direct:
                    self.error(node, "test methods and conditional/nested test definitions are unsupported")
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                self.error(node, "test classes are unsupported")
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.asname or alias.name).startswith(("test", "Test")):
                        self.error(node, "imported tests require package-aware collection")
                    if alias.name == "pytest":
                        self.aliases[alias.asname or alias.name] = "pytest"
                    elif alias.name.startswith("pytest.") or alias.name.startswith("_pytest"):
                        self.error(node, "pytest internals are unsupported")
            elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
                for alias in node.names:
                    if alias.name not in {"fixture", "mark", "param", "raises", "fail", "skip", "xfail"}:
                        self.error(node, "unsupported pytest import: " + alias.name)
                    self.aliases[alias.asname or alias.name] = "pytest." + alias.name
            elif isinstance(node, ast.ImportFrom):
                if any((alias.asname or alias.name).startswith(("test", "Test")) or alias.name == "*"
                       for alias in node.names):
                    self.error(node, "imported tests and star imports are unsupported")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = _bound_names(node)
                if any(name in self.aliases or name.startswith(("test", "Test")) for name in names):
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
                fixture = [dec for dec in node.decorator_list
                           if self.name(dec.func if isinstance(dec, ast.Call) else dec) == "pytest.fixture"]
                if fixture:
                    if len(fixture) != 1 or len(node.decorator_list) != 1:
                        self.error(node, "fixtures support one fixture decorator only")
                    if isinstance(node, ast.AsyncFunctionDef):
                        self.error(node, "async fixtures are unsupported")
                    decorator = fixture[0]
                    kws = {}
                    if isinstance(decorator, ast.Call):
                        if decorator.args:
                            self.error(decorator, "fixture options must be keywords")
                        kws = self.keywords(decorator, {"scope", "autouse", "name"})
                    if kws.get("scope", "function") != "function":
                        self.error(decorator, "only function-scoped fixtures are supported")
                    if not isinstance(kws.get("autouse", False), bool):
                        self.error(decorator, "autouse must be a literal boolean")
                    fixture_name = kws.get("name", node.name)
                    if (not isinstance(fixture_name, str) or not fixture_name.isidentifier()
                            or keyword.iskeyword(fixture_name) or fixture_name == "request"
                            or fixture_name.startswith("_pyn_") or fixture_name in self.aliases):
                        self.error(decorator, "fixture name must be a non-reserved literal identifier")
                    if fixture_name in self.fixtures:
                        self.error(decorator, "duplicate fixture name: " + fixture_name)
                    self.fixtures[fixture_name] = Fixture(node, self.arguments(node), self.is_generator(node),
                                                         kws.get("autouse", False))
                elif node.name.startswith("test"):
                    if isinstance(node, ast.AsyncFunctionDef) or self.is_generator(node):
                        self.error(node, "async and generator tests are unsupported")
                    self.tests.append(node)
                    parameters = []
                    prelude = []
                    marks = []
                    usefixtures = []
                    for decorator in node.decorator_list:
                        name = self.name(decorator.func if isinstance(decorator, ast.Call) else decorator)
                        if name == "pytest.mark.parametrize":
                            parameter, setup = self.parameter(decorator, node)
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
                    self.usefixtures[node.name] = [name for names in reversed(usefixtures) for name in names]
                    all_names = [name for parameter in parameters for name in parameter.names]
                    if len(all_names) != len(set(all_names)):
                        self.error(node, "duplicate parametrized argument")
                    required = self.arguments(node)
                    if any(name not in required for name in all_names):
                        self.error(node, "parametrized arguments must be required test arguments")
                    self.parameters[node.name] = list(reversed(parameters))
                    self.preludes[node.name] = prelude
                    self.marks[node.name] = list(reversed(marks))
        if len(self.tests) > 10000:
            self.error(self.tree, "more than 10000 tests in one module")
        self.validate_declarations()
        self.validate_constants()

    def validate_declarations(self):
        declarations = {function.name for function in self.tests} | self.fixture_functions()
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

    def validate_constants(self):
        # Literal table references preserve aliases, but their number/shape must
        # not change during module import. Reject mutation/escape instead of
        # silently collecting a stale subset of the real pytest cases.
        if not self.metadata_constants:
            return
        postponed = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                        and any(alias.name == "annotations" for alias in node.names) for node in self.tree.body)
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Function bodies run later; arbitrary decorators and defaults
                # could mutate a parameter table before pytest collects it.
                if node not in self.tests and node.name not in self.fixture_functions() and node.decorator_list:
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
            if any(isinstance(part, (ast.Call, ast.AugAssign, ast.Delete, ast.ClassDef, ast.If, ast.For,
                                     ast.While, ast.Try, ast.With))
                   or isinstance(part, ast.Subscript) and isinstance(part.ctx, ast.Store)
                   for part in ast.walk(node)):
                self.error(node, "named parameter tables require static module initialization")
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

    def fixture_order(self, function, parameters):
        order = []
        visiting = set()

        def visit(name):
            if name in parameters:
                return
            if name not in self.fixtures:
                self.error(function, "unknown or unsupported fixture: " + name)
            if name in visiting:
                self.error(function, "fixture dependency cycle at " + name)
            if name in order:
                return
            visiting.add(name)
            for dependency in self.fixtures[name].dependencies:
                visit(dependency)
            visiting.remove(name)
            order.append(name)

        # Pytest discovers module fixtures in attribute (function-name) order;
        # a public fixture alias must not change autouse setup/teardown order.
        for name in sorted(self.fixtures, key=lambda name: self.fixtures[name].function.name):
            fixture = self.fixtures[name]
            if fixture.autouse:
                visit(name)
        # pytest requests autouse, then usefixtures, then argument fixtures.
        for name in self.usefixtures.get(function.name, []) + self.arguments(function):
            visit(name)
        return order

    def validate_body(self):
        parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        decorators = {item for function in self.tests + [f.function for f in self.fixtures.values()]
                      for dec in function.decorator_list for item in ast.walk(dec)}
        for node in ast.walk(self.tree):
            if node in decorators or isinstance(node, (ast.Import, ast.ImportFrom, ast.alias)):
                continue
            if (isinstance(node, ast.Attribute) and node.attr in {"__test__", "pytestmark"}
                    and isinstance(node.value, ast.Name)):
                self.error(node, "runtime pytest collection metadata is unsupported")
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
            if not (isinstance(parent, ast.Call) and parent.func is node
                    and name in {"pytest.raises", "pytest.fail", "pytest.skip", "pytest.xfail"}):
                self.error(node, "unsupported pytest use: " + name)
            if name == "pytest.raises":
                if (len(parent.args) != 1 or isinstance(parent.args[0], ast.Tuple)
                        or any(kw.arg != "match" for kw in parent.keywords)):
                    self.error(parent, "raises supports one exception class and optional match= only")
            elif len(parent.args) > 1 or any(kw.arg != "reason" for kw in parent.keywords):
                self.error(parent, "outcome helpers accept one reason only")

    def captured(self, node, location):
        """A comparison assertion's message showing its operands' reprs, or None.

        Literal operands show their source and names are read again; other operands are
        bound once, in order, by reserved walrus temporaries. The message runs only on
        failure. Names keep any narrowing the assertion gives them.
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
            parts.append(ast.FormattedValue(value, ord("r"), None))
        return ast.JoinedStr(parts)

    def transform_source(self):
        declarations = set(self.tests) | {fixture.function for fixture in self.fixtures.values()}
        filename = self.filename
        generator = self

        class Rewrite(ast.NodeTransformer):
            def __init__(self):
                self.scopes = []
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
                return self.scoped(node, "function")

            def visit_AsyncFunctionDef(self, node):
                return self.scoped(node, "other")

            def visit_ClassDef(self, node):
                return self.scoped(node, "other")

            def visit_Assert(self, node):
                if node.msg is None:
                    location = f"{filename}:{node.lineno}: assert {ast.unparse(node.test)}"
                    detail = None
                    if generator.operands and self.scopes and self.scopes[-1] == "function":
                        detail = generator.captured(node, location)
                    node.msg = detail or ast.Constant(location)
                return node

        # Validate before removing syntax; otherwise an unsupported use could disappear.
        self.validate_body()
        output = []
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in self.preludes:
                output.extend(self.preludes[node.name])
            rewritten = Rewrite().visit(node)
            if rewritten is not None:
                output.append(ast.unparse(rewritten))
        return "\n\n".join(output)

    def wrapper(self, function, case_number, nodeid, parameters, parameter_marks):
        order = self.fixture_order(function, parameters)
        marks = self.marks[function.name] + parameter_marks
        skip = next((mark for mark in marks if mark[0] in {"skip", "skipif"} and mark[1] is True), None)
        # Conditions that decorators evaluated at import (marker), tested in pytest's order.
        conditions = [mark for mark in marks if mark[0] == "skipif" and isinstance(mark[1], str)]
        xfail = next((mark for mark in marks if mark[0] == "xfail" and mark[1]), None)
        lines = [f"def _pyn_case_{case_number}(_pyn_report: _pyn_support.Report) -> None:",
                 f"    _pyn_id = {nodeid!r}"]
        if not skip:
            for mark in conditions:
                lines += [f"    if _pyn_support.condition({mark[1]}):",
                          f"        _pyn_report.record(_pyn_id, 'setup', 'skipped', {mark[2]!r})",
                          "        _pyn_report.record(_pyn_id, 'teardown', 'passed', '')",
                          "        return"]
        if skip or (xfail and not xfail[4]):
            marker = skip or xfail
            outcome = "skipped" if skip else "xfailed"
            lines += [f"    _pyn_report.record(_pyn_id, 'setup', {outcome!r}, {marker[2]!r})",
                      "    _pyn_report.record(_pyn_id, 'teardown', 'passed', '')"]
            return "\n".join(lines)
        lines += ["    _pyn_teardown_errors = ''", "    _pyn_teardown_skip = ''",
                  "    _pyn_teardown_xfail = ''", "    _pyn_teardown_xfail_count = 0", "    try:"]
        indent = 2
        generators = []
        values = dict(parameters)
        for index, name in enumerate(order):
            fixture = self.fixtures[name]
            args = ", ".join(f"{dep}={values[dep]}" for dep in fixture.dependencies)
            variable = f"_pyn_fixture_{index}"
            p = "    " * indent
            if fixture.generator:
                generator = f"_pyn_generator_{index}"
                lines += [p + f"{generator} = {fixture.function.name}({args})", p + "try:",
                          p + f"    {variable} = next({generator})", p + "except StopIteration:",
                          p + f"    raise RuntimeError({('fixture ' + name + ' did not yield')!r})",
                          p + "try:"]
                generators.append((indent, generator, name))
                indent += 1
            else:
                lines.append(p + f"{variable} = {fixture.function.name}({args})")
            values[name] = variable
        p = "    " * indent
        args = ", ".join(f"{name}={values[name]}" for name in self.arguments(function))
        lines += [p + "_pyn_report.record(_pyn_id, 'setup', 'passed', '')", p + "try:",
                  p + f"    {function.name}({args})",
                  p + "except _pyn_support.Skipped as _pyn_error:",
                  p + "    _pyn_report.record(_pyn_id, 'call', 'skipped', str(_pyn_error))",
                  p + "except _pyn_support.XFailed as _pyn_error:",
                  p + "    _pyn_report.record(_pyn_id, 'call', 'xfailed', str(_pyn_error))",
                  p + "except KeyboardInterrupt:", p + "    raise",
                  p + "except BaseException as _pyn_error:",
                  p + f"    _pyn_report.record(_pyn_id, 'call', {'xfailed' if xfail else 'failed'!r}, _pyn_support.describe(_pyn_error))",
                  p + "else:"]
        success = "failed" if xfail and xfail[3] else "xpassed" if xfail else "passed"
        detail = "[XPASS(strict)] " + xfail[2] if xfail and xfail[3] else xfail[2] if xfail else ""
        lines.append(p + f"    _pyn_report.record(_pyn_id, 'call', {success!r}, {detail!r})")
        for level, generator, name in reversed(generators):
            p = "    " * level
            lines += [p + "finally:", p + "    try:", p + "        try:",
                      p + f"            next({generator})", p + "        except StopIteration:",
                      p + "            pass", p + "        else:", p + "            try:",
                      p + f"                {generator}.close()", p + "            finally:",
                      p + f"                raise RuntimeError({('fixture ' + name + ' yielded more than once')!r})",
                      p + "    except _pyn_support.Skipped as _pyn_error:",
                      p + "        _pyn_teardown_skip += str(_pyn_error) + '\\n'",
                      p + "    except _pyn_support.XFailed as _pyn_error:",
                      p + "        _pyn_teardown_xfail += str(_pyn_error) + '\\n'",
                      p + "        _pyn_teardown_xfail_count += 1",
                      p + "    except KeyboardInterrupt:", p + "        raise",
                      p + "    except BaseException as _pyn_error:",
                      p + "        _pyn_teardown_errors += _pyn_support.describe(_pyn_error) + '\\n'"]
        lines += ["    except _pyn_support.Skipped as _pyn_error:",
                  "        _pyn_report.record(_pyn_id, 'setup', 'skipped', str(_pyn_error))",
                  "    except _pyn_support.XFailed as _pyn_error:",
                  "        _pyn_report.record(_pyn_id, 'setup', 'xfailed', str(_pyn_error))",
                  "    except KeyboardInterrupt:", "        raise",
                  "    except BaseException as _pyn_error:",
                  f"        _pyn_report.record(_pyn_id, 'setup', {'xfailed' if xfail else 'error'!r}, _pyn_support.describe(_pyn_error))",
                  "    if (_pyn_teardown_errors or _pyn_teardown_xfail_count > 1",
                  "            or (_pyn_teardown_xfail_count and _pyn_teardown_skip)):",
                  f"        _pyn_report.record(_pyn_id, 'teardown', {'xfailed' if xfail else 'error'!r}, _pyn_teardown_errors + _pyn_teardown_skip + _pyn_teardown_xfail)",
                  "    elif _pyn_teardown_skip:",
                  "        _pyn_report.record(_pyn_id, 'teardown', 'skipped', _pyn_teardown_skip)",
                  "    elif _pyn_teardown_xfail:",
                  "        _pyn_report.record(_pyn_id, 'teardown', 'xfailed', _pyn_teardown_xfail)",
                  "    else:", "        _pyn_report.record(_pyn_id, 'teardown', 'passed', '')"]
        return "\n".join(lines)

    def generate(self):
        self.collect()
        cases = []
        wrappers = []
        for function in self.tests:
            params = self.parameters[function.name]
            combinations = itertools.product(*(range(len(param.values)) for param in params))
            for indexes in combinations:
                values = {}
                ids = []
                marks = []
                for parameter, index in zip(params, indexes):
                    values.update(zip(parameter.names, parameter.values[index]))
                    ids.append(parameter.ids[index])
                    marks.extend(parameter.marks[index])
                nodeid = f"{self.filename}::{function.name}" + ("[" + "-".join(ids) + "]" if ids else "")
                if len(cases) >= 10000:
                    self.error(function, "more than 10000 generated cases in one module")
                wrappers.append(self.wrapper(function, len(cases), nodeid, values, marks))
                cases.append(nodeid)
        run = list(range(len(cases)))
        if self.selected is not None:
            # Node IDs select cases in their order, as pytest's arguments do; repeats are
            # collected once. Every case's declarations still run at import.
            run = []
            for selector in self.selected:
                wanted = f"{self.filename}::{selector}"
                matches = [index for index, case in enumerate(cases)
                           if case == wanted or case.split("[", 1)[0] == wanted]
                if not matches:
                    raise CollectionError("not found: " + wanted)
                run += [index for index in matches if index not in run]
        original = self.transform_source()
        # Pragmas are comments and therefore absent from the AST. Preserve their
        # original opt-ins; the runner never opts the input into Any itself.
        pragmas = "\n".join(token.string for token in tokenize.generate_tokens(io.StringIO(self.source).readline)
                            if token.type == tokenize.COMMENT and re.match(r"#\s*pystachy:", token.string))
        tail = ["import pytest_native_support as _pyn_support", "import sys as _pyn_sys", *wrappers,
                "def _pyn_run(_pyn_path: str) -> int:",
                "    _pyn_report = _pyn_support.Report(_pyn_path)"]
        tail += [f"    _pyn_case_{i}(_pyn_report)" for i in run]
        tail += ["    return _pyn_report.finish()", "if __name__ == '__main__':",
                 "    _pyn_sys.exit(_pyn_run(_pyn_sys.argv[1]))"]
        return GeneratedModule(pragmas + "\n" + original + "\n\n" + "\n\n".join(tail) + "\n",
                               [cases[index] for index in run])


def generate(source: str, filename: str, operands: bool = True, selected=None) -> GeneratedModule:
    """Collect and adapt one module, or reject unsupported collection explicitly.

    operands keeps comparison operands for assertion failures (Generator.captured);
    selected lists node-ID selectors (`name` or `name[id]`) to run, in order.
    """
    return Generator(source, filename, operands, selected).generate()
