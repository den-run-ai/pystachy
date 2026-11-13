"""Generate explicit native calls for a deliberately bounded pytest source dialect.

Collection reads syntax, never imports or executes test modules. Generated modules
retain their original top-level statements, fixtures and test bodies. Only known
pytest declarations are replaced. Unknown source declarations are an error; the
CLI's independent oracle detects collection behavior hidden in imported symbols.
"""

import ast
import builtins
import copy
import dataclasses
from dataclasses import dataclass, field
import io
import itertools
import keyword
import math
import re
import string
import tokenize


class CollectionError(ValueError):
    """The source needs collection semantics the native runner cannot preserve."""


@dataclass
class GeneratedModule:
    source: str
    cases: list[str]
    # The program imports pytest_native_fixtures (tmp_path, monkeypatch).
    builtin_fixtures: bool = False
    # The other fixture modules the program imports (SUPPORT_MODULES): caplog's, capsys and capfd's.
    support_modules: list[str] = field(default_factory=list)
    # Generated line -> original line, for the compiler's diagnostics (line_map).
    lines: dict[int, int] = field(default_factory=dict)
    # conftest.py hooks left out of the program, which the pytest comparison answers for.
    hooks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Opaque:
    """A parameter value the collector does not evaluate; name is its __name__ if it shows one."""
    name: str | None = None


@dataclass
class Read:
    """A parameter value the collector read through an imported constant, for the program to check."""
    value: object


@dataclass
class Parameter:
    names: list[str]
    values: list[list[str]]
    ids: list[str]
    marks: list[list["Mark"]]


@dataclass
class Mark:
    # skip, skipif, xfail, filterwarnings, unittest's unit-skip and unit-xfail, or label:
    # a mark that only names its test (-m and -k read it), whose name is its reason.
    kind: str
    # True/False, or the name of a condition its decorator evaluated at import.
    condition: object
    reason: str
    strict: bool = False
    run: bool = True
    # Source of xfail(raises=...): a class or a tuple of classes.
    raises: str | None = None
    # A filterwarnings mark's (action, message regex, category) entries, as written.
    filters: tuple = ()


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
    # A unittest.TestCase method: setUp, the test and tearDown all run in its call phase.
    unit: bool = False


@dataclass
class ClassInfo:
    """A module-level class that pytest collects, or a base class of one."""
    node: ast.ClassDef
    unit: bool  # (derives from unittest.TestCase)
    bases: list["ClassInfo"]
    mro: list["ClassInfo"] = field(default_factory=list)  # (itself first)
    parameters: list[Parameter] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    usefixtures: list[str] = field(default_factory=list)
    tests: dict[str, Test] = field(default_factory=dict)  # (its own test methods)
    names: set[str] = field(default_factory=set)  # (every name its body binds)
    hooks: dict[str, ast.FunctionDef] = field(default_factory=dict)  # (setup_method, teardown_method)


SCOPES = {"function": 0, "class": 1, "module": 2, "session": 3}
FINALIZERS = {"class": "class_finalizers", "module": "module_finalizers", "session": "session_finalizers"}
PYTEST_IMPORTS = {"fixture", "mark", "param", "raises", "fail", "skip", "xfail", "approx", "warns",
                  "deprecated_call"}
PYTEST_CALLS = {"pytest.raises", "pytest.fail", "pytest.skip", "pytest.xfail", "pytest.approx", "pytest.warns",
                "pytest.deprecated_call"}
# Contexts that expect a warning: written out around warnings.catch_warnings (Rewrite.visit_With).
WARNS = {"pytest.warns": 1, "pytest.deprecated_call": 0}
UNIT_WARNS = {"assertWarns": 1, "assertWarnsRegex": 2}
XUNIT_MODULE = {"setup_module", "setupModule", "teardown_module", "teardownModule",
                "setup_function", "teardown_function", "setUpModule", "tearDownModule"}
XUNIT_CLASS = {"setup_class", "teardown_class"}
# A test class's per-test hooks, which run as a fixture of the class would (INSTANCE).
XUNIT_METHOD = {"setup_method", "teardown_method"}
# Where a class with those hooks makes its object, in a test's fixture order.
INSTANCE = "<instance>"
# unittest.TestCase machinery the runner does not drive.
UNIT_UNSUPPORTED = {"setUpClass", "tearDownClass", "run", "debug", "runTest", "__init__", "__new__",
                    "__call__", "addCleanup", "doCleanups", "addClassCleanup", "doClassCleanups",
                    "enterContext", "enterClassContext", "id", "shortDescription", "defaultTestResult",
                    "countTestCases", "assertLogs", "assertNoLogs",
                    "failureException", "addTypeEqualityFunc"}
# conftest.py hooks that only add text to pytest's own report: nothing a test can observe.
REPORT_HOOKS = {"pytest_report_header", "pytest_terminal_summary"}
# conftest.py hooks pytest runs around the session and its collection. The native program
# does not run them: the comparison with pytest then shows whether an outcome depended on
# one, so they are accepted only while that comparison is on (Generator.verified).
VERIFIED_HOOKS = {"pytest_addoption", "pytest_configure", "pytest_unconfigure", "pytest_sessionstart",
                  "pytest_sessionfinish", "pytest_collection_modifyitems", "pytest_collection_finish",
                  "pytest_ignore_collect"}
# pytest's classes as tests name them in annotations, which the runner removes: a
# parameter is typed by the value the runner passes.
PYTEST_TYPES = {"MonkeyPatch", "FixtureRequest", "SubRequest", "TempPathFactory", "CaptureFixture",
                "LogCaptureFixture", "WarningsRecorder", "ExceptionInfo", "Config", "Parser", "Item",
                "Session", "Metafunc", "MarkDecorator", "Mark", "Cache", "Pytester", "RecordedHookCall",
                "FixtureDef", "TempdirFactory", "Function", "Module", "Class", "Package", "Collector",
                "CallInfo", "TestReport", "CollectReport", "RaisesExc", "RaisesGroup"}
UNITTEST_IMPORTS = {"TestCase", "SkipTest", "skip", "skipIf", "skipUnless", "expectedFailure", "main"}
UNITTEST_MARKS = {"unittest.skip", "unittest.skipIf", "unittest.skipUnless", "unittest.expectedFailure"}
MONKEYPATCH = {"setenv", "delenv", "undo", "context"}
# monkeypatch methods the generator writes out where they are called (Generator.patch_plan).
MONKEYPATCH_WRITTEN = {"setattr", "setitem", "delitem", "chdir"}
BUILTIN_FIXTURES = {
    "tmp_path": Fixture(None, [], False, False, call="_pyn_fixtures.tmp_path", named=True, origin="builtin"),
    "monkeypatch": Fixture(None, [], True, False, call="_pyn_fixtures.monkeypatch", valued=True, origin="builtin"),
    "recwarn": Fixture(None, [], True, False, call="_pyn_fixtures.recwarn", valued=True, origin="builtin"),
    "tmp_path_factory": Fixture(None, [], False, False, scope="session", call="_pyn_fixtures.tmp_path_factory",
                                origin="builtin"),
    "tmpdir": Fixture(None, [], False, False, call="_pyn_fixtures.tmpdir", named=True, origin="builtin"),
    # (Their own modules: only a suite that asks for caplog compiles logging, and only one
    # that captures output needs a compiler with os.dup2.)
    "caplog": Fixture(None, [], True, False, call="_pyn_logging.caplog", valued=True, origin="builtin"),
    "capsys": Fixture(None, [], True, False, call="_pyn_capture.capture", valued=True, origin="builtin"),
    "capfd": Fixture(None, [], True, False, call="_pyn_capture.capture", valued=True, origin="builtin"),
}
# The modules of built-in fixtures beside pytest_native_fixtures, by the alias generated code calls.
SUPPORT_MODULES = {"_pyn_logging": "pytest_native_logging", "_pyn_capture": "pytest_native_capture"}


UNKNOWN = object()  # (what evaluate() returns for an expression it does not read)


class _Unread:
    """An item of a list, tuple or dict display that evaluate() does not read.

    The display's length and a dict's keys are still known: sorted(TABLE) and
    range(len(CASES)) are read where TABLE's values are objects.
    """


UNREAD = _Unread()
# Builtins whose __name__ is their name: pytest names such a parameter value after it.
BUILTIN_NAMES = {name for name, value in vars(builtins).items()
                 if callable(value) and getattr(value, "__name__", None) == name}
STATIC_TYPES = (type(None), bool, int, float, complex, str, bytes, tuple, list, dict, range)
# Pure builtins the collector may call on literal data to read a parameter table.
STATIC_CALLS = {name: getattr(builtins, name) for name in (
    "range", "len", "list", "tuple", "sorted", "enumerate", "zip", "min", "max", "sum", "abs", "str",
    "int", "float", "bool", "repr", "chr", "ord", "dict", "round", "divmod", "any", "all", "bytes",
    "hex", "oct", "bin", "ascii")}
STATIC_CALLS["reversed"] = lambda value: list(reversed(value))
STATIC_ITERTOOLS = {"product": itertools.product, "chain": itertools.chain,
                    "combinations": itertools.combinations, "permutations": itertools.permutations,
                    "combinations_with_replacement": itertools.combinations_with_replacement,
                    "zip_longest": itertools.zip_longest}
# Methods that read their object and leave it unchanged, by the object's type.
STATIC_METHODS = {
    str: {name for name in dir(str) if not name.startswith("_")},
    bytes: {name for name in dir(bytes) if not name.startswith("_")},
    list: {"index", "count", "copy"}, tuple: {"index", "count"},
    dict: {"items", "keys", "values", "get", "copy"},
    int: {"bit_length", "bit_count"}, float: {"is_integer", "hex"}, range: {"index", "count"}}
STATIC_MODULES = {
    "string": {name: getattr(string, name) for name in (
        "ascii_letters", "ascii_lowercase", "ascii_uppercase", "digits", "hexdigits", "octdigits",
        "punctuation", "whitespace")},
    "math": {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}}
STATIC_LIMIT = 100000  # (items of one value, and evaluation steps of one table)
BINARY = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
          ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
          ast.BitOr: lambda a, b: a | b, ast.BitAnd: lambda a, b: a & b, ast.BitXor: lambda a, b: a ^ b}
COMPARE = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
           ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
           ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


def _static(value, budget=None, partial=False):
    """Whether a value is plain data a literal could write: no objects, sets or generators.

    partial also takes UNREAD items: the shape of a table of objects.
    """
    budget = budget if budget is not None else [STATIC_LIMIT]
    budget[0] -= 1
    if partial and value is UNREAD:
        return True
    if budget[0] < 0 or not isinstance(value, STATIC_TYPES):
        return False
    if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > 4096:
        return False
    if isinstance(value, (str, bytes, range)):
        return len(value) <= STATIC_LIMIT
    if isinstance(value, (tuple, list)):
        return all(_static(item, budget, partial) for item in value)
    if isinstance(value, dict):
        return all(_static(key, budget) and _static(item, budget, partial) for key, item in value.items())
    return True


def _literal_node(value):
    """An expression that writes a static value; a float that has no literal by float()."""
    if value is UNREAD:
        return ast.Name("_pyn_unread", ast.Load())  # (described() finds no value for it)
    if isinstance(value, float) and (value != value or value in (math.inf, -math.inf)):
        return ast.Call(ast.Name("float", ast.Load()), [ast.Constant(str(value))], [])
    if isinstance(value, tuple):
        return ast.Tuple([_literal_node(item) for item in value], ast.Load())
    if isinstance(value, list):
        return ast.List([_literal_node(item) for item in value], ast.Load())
    if isinstance(value, dict):
        return ast.Dict([_literal_node(key) for key in value], [_literal_node(item) for item in value.values()])
    if isinstance(value, range):
        return ast.Call(ast.Name("range", ast.Load()), [ast.Constant(value.start), ast.Constant(value.stop),
                                                         ast.Constant(value.step)], [])
    return ast.Constant(value)


def _bound_names(node):
    """The names a statement or target binds in its own scope, in no particular order."""
    names = []
    pending = [node]
    while pending:
        item = pending.pop()
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
            names.append(item.id)
        for child in ast.iter_child_nodes(item):
            # (A comprehension's targets, like a function's locals, are its own.)
            if not isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda,
                                      ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                pending.append(child)
    return names


WARNING_CLASSES = {"Warning", "UserWarning", "DeprecationWarning", "PendingDeprecationWarning", "SyntaxWarning",
                   "RuntimeWarning", "FutureWarning", "ImportWarning", "UnicodeWarning", "BytesWarning",
                   "ResourceWarning", "EncodingWarning"}
# The names -m matches: pytest's own marks by kind, labels by name.
MARK_NAMES = {"skip", "skipif", "xfail", "filterwarnings", "label"}


def warning_filter(text: str):
    """(action, message regex, category) of a filterwarnings entry the program can apply, or None.

    pytest's form is action:message:category:module:lineno. The program applies an
    action, a message and a built-in warning class.
    """
    parts = [part.strip() for part in text.split(":")]
    action, message, category = parts[0], (parts[1:2] or [""])[0], (parts[2:3] or [""])[0] or "Warning"
    if (action not in {"error", "ignore", "always", "default", "module", "once"} or category not in WARNING_CLASSES
            or any(parts[3:])):
        return None
    return action, message, category


def match_expression(text: str, option: str):
    """Compile pytest's -k or -m expression into a function of a name test.

    The grammar is pytest's: names joined by `and`, `or` and `not`, with parentheses;
    an empty expression matches everything. The result takes a function that says
    whether one name matches (a substring of the test's names for -k, one of its
    marks for -m).
    """
    tokens = re.findall(r"[()]|[^\s()]+", text)
    position = 0

    def bad():
        return CollectionError(f"unsupported {option} expression: {text!r} (names, and, or, not and parentheses "
                               "are supported)")

    def peek():
        return tokens[position] if position < len(tokens) else None

    def primary():
        nonlocal position
        token = peek()
        position += 1
        if token == "not":
            inner = primary()
            return lambda match: not inner(match)
        if token == "(":
            inner = either()
            if peek() != ")":
                raise bad()
            position += 1
            return inner
        if token is None or token in {")", "and", "or"} or not re.fullmatch(r"(?:\w|[:+\-.\[\]\\/])+", token):
            raise bad()
        return lambda match: match(token)

    def both():
        nonlocal position
        left = primary()
        while peek() == "and":
            position += 1
            left = (lambda first, second: lambda match: first(match) and second(match))(left, primary())
        return left

    def either():
        nonlocal position
        left = both()
        while peek() == "or":
            position += 1
            left = (lambda first, second: lambda match: first(match) or second(match))(left, both())
        return left

    if not tokens:
        return lambda match: True
    result = either()
    if position != len(tokens):
        raise bad()
    return result


def _type_checking(node, names, modules):
    """`if TYPE_CHECKING:` without else: imports for annotations, which never run."""
    if not isinstance(node, ast.If) or node.orelse:
        return False
    test = node.test
    return (isinstance(test, ast.Name) and test.id in names
            or isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name) and test.value.id in modules)


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


def _scalar(value):
    """Whether pytest names a parameter of this value after the value: a number, string, bytes or None."""
    return value is None or type(value) in (bool, int, float, str, bytes)


def _statement_names(statement):
    """The names a module-level statement binds."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [statement.name]
    if isinstance(statement, ast.Import):
        return [alias.asname or alias.name.split(".")[0] for alias in statement.names]
    if isinstance(statement, ast.ImportFrom):
        return [alias.asname or alias.name for alias in statement.names]
    return _bound_names(statement)


def _attribute(name):
    """_pyn_support.name as an expression."""
    return ast.Attribute(ast.Name("_pyn_support", ast.Load()), name, ast.Load())


class Generator:
    def __init__(self, source: str, filename: str, operands: bool = True, selected=None,
                 shared=None, conftest: bool = False, session_end: bool = True, path: str = "",
                 module: str = "", imports=None, package: bool = False, alias: str = "_pyn_conftest",
                 helper: bool = False, resolve=None, strict: bool = False, verified: bool = False,
                 keyword: str = "", markexpr: str = "", unavailable=None):
        self.source = source
        # Fixtures the runner left out of this module or of a conftest.py above it, each
        # with the reason: a test that requests one cannot be collected, though another
        # fixture of its name (a wider conftest.py's, a built-in) is in sight.
        self.unavailable = dict(unavailable or {})
        # pytest's -k and -m: the cases to run among those the node IDs select.
        self.keyword = match_expression(keyword, "-k")
        self.markexpr = match_expression(markexpr, "-m")
        self.filename = filename
        # The run is compared with pytest's, which answers for the hooks left out (VERIFIED_HOOKS).
        self.verified = verified
        # pytest's xfail_strict setting: what an xfail mark without strict= means.
        self.strict = strict
        # resolve(path, level, module, name) -> (source, filename, path, module) of the module
        # beside the tests that `from module import name` reads, or None: where a test
        # class's imported base class is defined.
        self.resolve = resolve
        self.imported = {}
        self.module_names = {}
        self.external = {}
        self.external_nodes = {}
        self.external_constants = {}
        # Whether the last evaluate(..., external=True) read an imported constant.
        self.read_external = False
        self.external_reasons = {}
        self.fixed_names = None
        # What the test module reads as __file__ and __name__: pytest imports the original
        # file under its own name, where the generated one has another path.
        self.path = path or filename
        self.module = module or filename.rsplit("/", 1)[-1].removesuffix(".py")
        self.operands = operands
        self.selected = selected
        # The fixtures of the conftest.py files above this module as it calls them (export):
        # one group per file, the outermost directory's first; a nearer file's fixture
        # replaces an outer one of its name.
        self.shared_groups = [shared] if isinstance(shared, dict) else list(shared or [])
        self.shared = {name: fixture for group in self.shared_groups for name, fixture in group.items()}
        # (module, alias) for each of those files, which this module imports.
        self.imports = imports if imports is not None else [("conftest", "_pyn_conftest")] if self.shared else []
        # The name this conftest.py's own fixtures are called through elsewhere.
        self.alias = alias
        self.conftest = conftest
        # In a package, where relative imports resolve.
        self.package = package
        # A module beside the tests that only needs adapting: nothing is collected from it.
        self.helper = helper
        # The last case that runs also ends the session scope.
        self.session_end = session_end
        try:
            self.tree = ast.parse(source, filename)
        except SyntaxError as error:
            raise CollectionError(f"{filename}:{error.lineno}: {error.msg}") from None
        # pytest imports a test module under its own name, so a script guard never runs there.
        self.tree.body = [node for node in self.tree.body if not _main_guard(node)]
        self.aliases = {}
        self.hooks = []
        if conftest:
            self.drop_hooks()
        self.type_imports()
        self.constants = {}
        # Module-level names: every one bound; modules by their import name; classes,
        # functions and imported names by the __name__ their binding shows; and the
        # value expression of each name assigned once.
        self.bound = set()
        self.modules = {}
        self.named = {}
        self.bindings = {}
        self.rebound = set()
        self.unread = False
        self.fixtures = {}
        self.class_fixtures = {}
        self.tests = []
        self.classes = []
        self.preludes = {}
        self.counter = 0
        self.metadata_constants = set()
        # `pytestmark = ...` statements, which become the marks of their tests.
        self.dropped = set()
        # Module-level names for marks (`needs_x = pytest.mark.skipif(...)`): what
        # decorations() makes of each.
        self.mark_aliases = {}
        # A filterwarnings mark is in use: wrappers need the warnings module.
        self.warning_marks = False
        # Fixtures that take request without reading it: the parameter is removed.
        self.unused_requests = set()
        # Declarations that read a named parameter table, placed after the module's own code.
        self.late = []
        # Names a test class binds: pytest declarations there cannot use them, because
        # the runner evaluates those declarations at module level.
        self.shadowed = None
        self.builtins_used = False
        self.support_used = set()
        # monkeypatch calls the program writes out (patch_plan), and their functions.
        self.patches = {}
        self.patch_functions = []

    def error(self, node, message):
        raise CollectionError(f"{self.filename}:{getattr(node, 'lineno', 1)}: {message}")

    def drop_hooks(self):
        """Leave out the hooks of a conftest.py that the native program does not run."""
        hooks = [node for node in self.tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in REPORT_HOOKS | VERIFIED_HOOKS]
        # A fixture that fills doctest_namespace serves doctests, which the program does not run.
        doctests = [node for node in self.tree.body if isinstance(node, ast.FunctionDef)
                    and any(argument.arg == "doctest_namespace" for argument in node.args.args)
                    and any("fixture" in ast.unparse(decorator) for decorator in node.decorator_list)]
        for node in hooks + doctests:
            if node.name in VERIFIED_HOOKS or node in doctests:
                if not self.verified:
                    self.error(node, f"{node.name} is not run natively, and only the comparison with pytest "
                               "shows that no outcome depends on it: run with that comparison (no --no-compare)")
                self.hooks.append(node.name + (" (doctest_namespace)" if node in doctests else ""))
        hooks += doctests
        # sys.path.insert(0, "."): a compiled program's imports are resolved before it runs.
        for node in self.tree.body:
            call = node.value if isinstance(node, ast.Expr) else None
            if (isinstance(call, ast.Call) and ast.unparse(call.func) in ("sys.path.insert", "sys.path.append")
                    and all(isinstance(argument, ast.Constant) for argument in call.args) and not call.keywords):
                if not self.verified:
                    self.error(node, "sys.path changes are not made natively, and only the comparison with pytest "
                               "shows that no outcome depends on them: run with that comparison (no --no-compare)")
                self.hooks.append(ast.unparse(call))
                hooks.append(node)
        names = {node.name for node in hooks if isinstance(node, ast.FunctionDef)}
        self.tree.body = [node for node in self.tree.body if node not in hooks]
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and node.id in names:
                self.error(node, "a pytest hook that the native program leaves out is used by other code: "
                           + node.id)

    def type_imports(self):
        """Take pytest's names out of `if TYPE_CHECKING:` blocks, where they only serve annotations."""
        names = set()
        modules = set()
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "typing" and not node.level:
                names.update(alias.asname or alias.name for alias in node.names if alias.name == "TYPE_CHECKING")
            elif isinstance(node, ast.Import):
                modules.update(alias.asname or alias.name for alias in node.names if alias.name == "typing")
        body = []
        for node in self.tree.body:
            if not _type_checking(node, names, modules):
                body.append(node)
                continue
            kept = []
            for statement in node.body:
                if isinstance(statement, ast.ImportFrom) and not statement.level and (
                        statement.module == "pytest" or (statement.module or "").startswith("_pytest")):
                    for alias in statement.names:
                        if alias.name != "*":
                            self.aliases[alias.asname or alias.name] = "pytest." + alias.name
                elif isinstance(statement, ast.Import) and all(alias.name == "pytest" for alias in statement.names):
                    for alias in statement.names:
                        self.aliases[alias.asname or alias.name] = "pytest"
                else:
                    kept.append(statement)
            if kept:
                node.body = kept
                body.append(node)
        self.tree.body = body

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
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            value = self.evaluate(node, None, track)
            if value is UNKNOWN:
                self.error(node, "expected a literal or an expression of earlier literal constants")
            return value

    def evaluate(self, node, env=None, track=False, partial=False, external=False):
        """The value of an expression over literals that runs no test code, else UNKNOWN.

        partial allows a result with UNREAD items, which shows a table's rows. external
        also reads constants that `from` imports bind (external_constant), and sets
        read_external when the value depends on one.

        Reads literals, earlier constants, arithmetic, comparisons, subscripts, f-strings,
        comprehensions and calls of pure builtins and itertools functions (STATIC_CALLS):
        enough for range(3), [n * 2 for n in SIZES] or sorted(TABLE.items()).
        """
        budget = [STATIC_LIMIT]
        env = env or {}

        class Unknown(Exception):
            pass

        def bind(target, value, scope):
            if isinstance(target, ast.Name):
                scope[target.id] = value
            elif isinstance(target, (ast.Tuple, ast.List)) and not any(isinstance(e, ast.Starred) for e in target.elts):
                items = list(value)
                if len(items) != len(target.elts):
                    raise Unknown
                for part, item in zip(target.elts, items):
                    bind(part, item, scope)
            else:
                raise Unknown

        def comprehension(generators, scope, emit):
            if not generators:
                emit(scope)
                return
            first = generators[0]
            if first.is_async:
                raise Unknown
            for item in run(first.iter, scope):
                inner = dict(scope)
                bind(first.target, item, inner)
                if all(run(condition, inner) for condition in first.ifs):
                    comprehension(generators[1:], inner, emit)

        reading = set()

        def item_of(node, scope):
            try:
                return run(node, scope)
            except Unknown:
                return UNREAD

        def call(node, scope):
            if any(keyword.arg is None for keyword in node.keywords) or any(
                    isinstance(argument, ast.Starred) for argument in node.args):
                raise Unknown
            arguments = [run(argument, scope) for argument in node.args]
            keywords = {keyword.arg: run(keyword.value, scope) for keyword in node.keywords}
            function = node.func
            if isinstance(function, ast.Name):
                if function.id not in STATIC_CALLS or function.id in self.bound or function.id in scope:
                    raise Unknown
                if function.id == "sorted" and "key" in keywords:
                    raise Unknown
                target = STATIC_CALLS[function.id]
            elif isinstance(function, ast.Attribute):
                owner = function.value
                if (isinstance(owner, ast.Name) and self.modules.get(owner.id) == "itertools"
                        and function.attr in STATIC_ITERTOOLS):
                    target = STATIC_ITERTOOLS[function.attr]
                else:
                    receiver = run(owner, scope)
                    if function.attr not in STATIC_METHODS.get(type(receiver), ()):
                        raise Unknown
                    target = getattr(receiver, function.attr)
            else:
                raise Unknown
            result = target(*arguments, **keywords)
            if not isinstance(result, STATIC_TYPES):
                # (An iterator or view: read it now, within the budget.)
                result = list(itertools.islice(result, STATIC_LIMIT + 1))
            return result

        def run(node, scope):
            budget[0] -= 1
            if budget[0] < 0:
                raise Unknown
            if isinstance(node, ast.Constant):
                if node.value is Ellipsis:
                    raise Unknown
                return node.value
            if isinstance(node, ast.Name):
                if node.id in scope:
                    return scope[node.id]
                if self.shadowed is not None and node.id in self.shadowed:
                    self.error(node, "pytest declarations in a test class cannot use its attributes: " + node.id)
                if node.id in self.constants:
                    if track:
                        self.metadata_constants.add(node.id)
                    return self.constants[node.id]
                if node.id in self.bindings and node.id not in reading:
                    # A display of objects bound once: its shape, with UNREAD items.
                    reading.add(node.id)
                    try:
                        value = run(self.bindings[node.id], {})
                    finally:
                        reading.discard(node.id)
                    if track:
                        self.metadata_constants.add(node.id)
                    return value
                if external:
                    value = self.external_constant(node.id)
                    if value is not UNKNOWN:
                        self.read_external = True
                        return value
                raise Unknown
            if isinstance(node, (ast.Tuple, ast.List)):
                items = []
                for item in node.elts:
                    if isinstance(item, ast.Starred):
                        items.extend(run(item.value, scope))
                    else:
                        items.append(item_of(item, scope))
                return tuple(items) if isinstance(node, ast.Tuple) else items
            if isinstance(node, ast.Dict):
                if any(key is None for key in node.keys):
                    raise Unknown
                return {run(key, scope): item_of(value, scope) for key, value in zip(node.keys, node.values)}
            if isinstance(node, ast.UnaryOp):
                value = run(node.operand, scope)
                if isinstance(node.op, ast.Not):
                    return not value
                if isinstance(node.op, ast.USub):
                    return -value
                if isinstance(node.op, ast.UAdd):
                    return +value
                return ~value
            if isinstance(node, ast.BinOp):
                left, right = run(node.left, scope), run(node.right, scope)
                if isinstance(node.op, ast.Pow):
                    if not (isinstance(right, int) and 0 <= right <= 64 and isinstance(left, (int, float))):
                        raise Unknown
                    return left ** right
                if isinstance(node.op, (ast.LShift, ast.RShift)):
                    if not (isinstance(right, int) and 0 <= right <= 256 and isinstance(left, int)):
                        raise Unknown
                    return left << right if isinstance(node.op, ast.LShift) else left >> right
                if type(node.op) not in BINARY:
                    raise Unknown
                if isinstance(node.op, ast.Mult):
                    for sequence, times in ((left, right), (right, left)):
                        if isinstance(sequence, (str, bytes, list, tuple)) and isinstance(times, int):
                            if len(sequence) * max(times, 0) > STATIC_LIMIT:
                                raise Unknown
                return BINARY[type(node.op)](left, right)
            if isinstance(node, ast.BoolOp):
                value = run(node.values[0], scope)
                for following in node.values[1:]:
                    if bool(value) != isinstance(node.op, ast.And):
                        break
                    value = run(following, scope)
                return value
            if isinstance(node, ast.Compare):
                left = run(node.left, scope)
                for operator, comparator in zip(node.ops, node.comparators):
                    right = run(comparator, scope)
                    if type(operator) not in COMPARE or not COMPARE[type(operator)](left, right):
                        if type(operator) not in COMPARE:
                            raise Unknown
                        return False
                    left = right
                return True
            if isinstance(node, ast.IfExp):
                return run(node.body if run(node.test, scope) else node.orelse, scope)
            if isinstance(node, ast.Subscript):
                value = run(node.value, scope)
                if isinstance(node.slice, ast.Slice):
                    parts = [None if part is None else run(part, scope)
                             for part in (node.slice.lower, node.slice.upper, node.slice.step)]
                    return value[slice(*parts)]
                return value[run(node.slice, scope)]
            if isinstance(node, ast.JoinedStr):
                text = ""
                for part in node.values:
                    if isinstance(part, ast.Constant):
                        text += part.value
                        continue
                    value = run(part.value, scope)
                    if part.conversion == 114:
                        value = repr(value)
                    elif part.conversion == 115:
                        value = str(value)
                    elif part.conversion == 97:
                        value = ascii(value)
                    spec = run(part.format_spec, scope) if part.format_spec is not None else ""
                    text += format(value, spec)
                return text
            if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
                items = []
                comprehension(node.generators, scope, lambda inner: items.append(run(node.elt, inner)))
                return items
            if isinstance(node, ast.DictComp):
                result = {}
                def emit(inner):
                    result[run(node.key, inner)] = run(node.value, inner)
                comprehension(node.generators, scope, emit)
                return result
            if isinstance(node, ast.Attribute):
                owner = node.value
                if isinstance(owner, ast.Name) and owner.id not in scope:
                    constants = STATIC_MODULES.get(self.modules.get(owner.id, ""))
                    if constants is not None and node.attr in constants:
                        return constants[node.attr]
                raise Unknown
            if isinstance(node, ast.Call):
                return call(node, scope)
            raise Unknown

        try:
            value = run(node, dict(env))
        except (Unknown, RecursionError):
            return UNKNOWN
        except CollectionError:
            raise
        except Exception:  # (whatever the expression raises, it was not read)
            return UNKNOWN
        return value if _static(value, None, partial) else UNKNOWN

    def unroll(self, node):
        """A comprehension's element expression for each item of its literal iterables.

        The loop variables are written into each copy as literals, so the copies run in
        order where the comprehension stood; None unless the iterables and conditions
        are ones evaluate() reads.
        """
        targets = {name for generator in node.generators for name in _bound_names(generator.target)}
        for part in ast.walk(node.elt):
            # (A nested scope could bind a loop variable's name again.)
            if isinstance(part, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                                 ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom)):
                return None
        rows = []

        class Substitute(ast.NodeTransformer):
            def __init__(self, scope):
                self.scope = scope

            def visit_Name(self, name):
                if name.id in self.scope and isinstance(name.ctx, ast.Load):
                    return ast.copy_location(_literal_node(self.scope[name.id]), name)
                return name

        def loop(index, scope):
            if index == len(node.generators):
                rows.append(Substitute({name: scope[name] for name in targets if name in scope})
                            .visit(copy.deepcopy(node.elt)))
                return len(rows) <= 10000
            generator = node.generators[index]
            if generator.is_async:
                return False
            iterable = self.evaluate(generator.iter, scope, True)
            if iterable is UNKNOWN or isinstance(iterable, (bool, int, float, complex, type(None))):
                return False
            for item in iterable:
                inner = dict(scope)
                if not self.bind(generator.target, item, inner):
                    return False
                keep = True
                for condition in generator.ifs:
                    value = self.evaluate(condition, inner, True)
                    if value is UNKNOWN:
                        return False
                    if not value:
                        keep = False
                        break
                if keep and not loop(index + 1, inner):
                    return False
            return True

        return rows if loop(0, {}) else None

    def bind(self, target, value, scope):
        """Assign a loop target from a literal item; False for a shape that does not fit."""
        if isinstance(target, ast.Name):
            scope[target.id] = value
            return True
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)) and len(value) == len(
                target.elts) and not any(isinstance(part, ast.Starred) for part in target.elts):
            return all(self.bind(part, item, scope) for part, item in zip(target.elts, value))
        return False

    def expand(self, node, depth=0):
        """The row expressions of a parameter table that is not one display, or None.

        A display with *unpacking, a comprehension over literals, list()/tuple() of such,
        tables joined by +, a name bound once to any of these, or a value evaluate() reads.
        """
        if depth > 20:
            return None
        if isinstance(node, (ast.List, ast.Tuple)):
            rows = []
            for item in node.elts:
                if isinstance(item, ast.Starred):
                    part = self.expand(item.value, depth + 1)
                    if part is None:
                        return None
                    rows += part
                else:
                    rows.append(item)
            return rows
        if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
            return self.unroll(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self.expand(node.left, depth + 1), self.expand(node.right, depth + 1)
            return None if left is None or right is None else left + right
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("list", "tuple")
                and node.func.id not in self.bound and len(node.args) == 1 and not node.keywords
                and not isinstance(node.args[0], ast.Starred)):
            return self.expand(node.args[0], depth + 1)
        if isinstance(node, ast.Name) and node.id in self.bindings and not (
                self.shadowed is not None and node.id in self.shadowed):
            self.metadata_constants.add(node.id)
            return self.expand(self.bindings[node.id], depth + 1)
        value = self.evaluate(node, None, True)
        if value is UNKNOWN:
            # Its rows hold objects: the program makes the table, the collector counts it.
            value = self.evaluate(node, None, True, True)
            self.unread = True
        if value is UNKNOWN or value is UNREAD or isinstance(value, (bool, int, float, complex, type(None))):
            return None
        return [_literal_node(item) for item in value]

    def unshadowed(self, node):
        """Reject a declaration in a test class that reads the class's own attributes.

        The runner evaluates such declarations at module level, before the class body.
        """
        if self.shadowed is not None:
            for part in ast.walk(node):
                if isinstance(part, ast.Name) and part.id in self.shadowed:
                    self.error(part, "pytest declarations in a test class cannot use its attributes: " + part.id)

    def described(self, node):
        """A parameter value for its ID: the literal it is, or an Opaque expression.

        pytest names a class or function after its __name__ and any other object after
        the argument and its index. Only syntax is read here, so a name is taken to be
        what its binding shows; the pytest comparison reports an ID that differs.
        """
        try:
            return self.constant(node, True)
        except CollectionError:
            if isinstance(node, ast.Name) and self.shadowed is not None and node.id in self.shadowed:
                raise
        static = self.evaluate(node)
        if static is not UNKNOWN:
            return static
        # A value computed from a constant of a module beside the tests, such as
        # len(ALPHABET) + 1: pytest names the case after the value, which the generated
        # program checks where it binds the parameter (Read).
        self.read_external = False
        static = self.evaluate(node, external=True)
        if static is not UNKNOWN and self.read_external:
            if isinstance(static, (list, tuple)):
                return [Read(item) if _scalar(item) else item for item in static]
            return Read(static) if _scalar(static) else static
        if isinstance(node, ast.Lambda):
            return Opaque("<lambda>")
        if isinstance(node, ast.Name) and (node.id in self.named or (
                node.id in BUILTIN_NAMES and node.id not in self.bound)):
            return Opaque(self.named.get(node.id, node.id))
        return Opaque()

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
        prelude = []
        # rows: the expression that shows each row's shape and ID. source: the module's
        # own table, whose rows generated code reads by position once the module has
        # been imported, as pytest reads them when it collects; without one, each row
        # expression runs once where the decorator stood.
        source = None
        self.unshadowed(table)
        if isinstance(table, (ast.List, ast.Tuple)) and not any(isinstance(item, ast.Starred) for item in table.elts):
            rows = table.elts
        else:
            if isinstance(table, ast.Name) and table.id in self.rebound:
                self.error(decorator, "parametrize constants require one literal binding: " + table.id)
            self.unread = False
            rows = self.expand(table)
            if rows is None:
                self.error(decorator, what + " needs a table the collector can read: a literal, range(), a "
                           "comprehension over literals, or a name bound once to one")
            if isinstance(table, ast.Name):
                source = table
                bound = self.bindings.get(table.id)
                value = self.constants.get(table.id, UNKNOWN)
                sequence = isinstance(value, (list, tuple)) if value is not UNKNOWN else (
                    isinstance(bound, (ast.List, ast.Tuple, ast.ListComp, ast.BinOp))
                    or isinstance(bound, ast.Call) and isinstance(bound.func, ast.Name)
                    and bound.func.id in ("list", "tuple", "sorted"))
                if not sequence:
                    # (A dict, range or other iterable, which pytest iterates once.)
                    source = ast.Name(f"_pyn_table_{self.counter}", ast.Load())
                    self.counter += 1
                    self.late.append(f"{source.id} = list({table.id})")
                # The collector read the table's length from syntax; the program checks it.
                self.late.append(f"_pyn_support.table_length(len({source.id}), {len(rows)}, {table.id!r})")
            elif self.unread:
                # The table's expression runs once, where the decorator stood.
                source = ast.Name(f"_pyn_table_{self.counter}", ast.Load())
                self.counter += 1
                prelude += [f"{source.id} = list({ast.unparse(table)})",
                            f"_pyn_support.table_length(len({source.id}), {len(rows)}, {what!r})"]
        if not rows:
            self.error(decorator, what + " needs a nonempty table")
        if len(rows) > 10000:
            self.error(decorator, what + " exceeds the 10000-case collection bound")
        if ids is not None and (not isinstance(ids, (list, tuple)) or len(ids) != len(rows)
                                or any(item is not None and not isinstance(item, (str, int, float))
                                       for item in ids)):
            self.error(decorator, "ids must be a literal list of strings, numbers or None matching the value table")
        result = []
        generated_ids = []
        row_marks = []
        for index, row in enumerate(rows):
            expr = row if source is None else ast.Subscript(value=source, slice=ast.Constant(index), ctx=ast.Load())
            explicit_id = None
            marks = []
            parameter_set = isinstance(row, ast.Call) and self.name(row.func) == "pytest.param"
            if parameter_set and source is not None:
                self.error(decorator, "pytest.param rows must be written in the decorator's own table")
            if parameter_set:
                if any(isinstance(item, ast.Starred) for item in row.args):
                    self.error(row, "pytest.param values must be written out: expected a literal or an expression")
                items = [self.described(item) for item in row.args]
                expressions = row.args
                seen = set()
                for kw in row.keywords:
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
                single_value = string_names and len(names) == 1
                display = isinstance(row, (ast.List, ast.Tuple)) and not any(
                    isinstance(item, ast.Starred) for item in row.elts)
                if single_value or not display:
                    value = self.described(row)
                else:
                    value = [self.described(item) for item in row.elts]
                if isinstance(value, Read) and not single_value:
                    value = Opaque()  # (a row that is one value, as any other the collector cannot read)
                if isinstance(value, Opaque) and not single_value:
                    if source is None:
                        # A row some expression makes: read once, then by position.
                        variable = f"_pyn_row_{self.counter}"
                        self.counter += 1
                        prelude.append(f"{variable} = {ast.unparse(expr)}")
                        expr = ast.Name(variable, ast.Load())
                    value = [Opaque()] * len(names)
                items = [value] if single_value else value
                if single_value:
                    expressions = [expr]
                elif source is None and isinstance(expr, (ast.List, ast.Tuple)) and display:
                    expressions = expr.elts
                else:
                    expressions = [ast.Subscript(value=expr, slice=ast.Constant(i), ctx=ast.Load())
                                   for i in range(len(names))]
            if not isinstance(items, (list, tuple)) or len(items) != len(names):
                self.error(decorator, what + " row width does not match argument names")
            # The values read through imported constants, by position, for the program to check.
            read = {position: item.value for position, item in enumerate(items) if isinstance(item, Read)}
            items = [item.value if isinstance(item, Read) else item for item in items]
            # Inline tables have no observable outer container. Retain their actual
            # row expressions once; named tables retain the original stored values.
            label = explicit_id if explicit_id is not None else ids[index] if ids is not None else None
            if label is not None and not isinstance(label, str):
                label = str(label)
            variables = []
            for position, (name, expression) in enumerate(zip(names, expressions)):
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
                target = self.late if source is not None and isinstance(table, ast.Name) else prelude
                target.append(f"{declaration} = {ast.unparse(expression)}")
                if position in read and label is None:
                    # The case is named after this value, which the collector read from
                    # another module's source.
                    target.append(f"_pyn_support.parameter_value(repr({variable}), {repr(read[position])!r}, "
                                  f"{ast.unparse(row if source is None else expression)!r})")
                variables.append(variable)
            result.append(variables)
            row_marks.append(marks)
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
        if isinstance(value, Opaque) and value.name is not None:
            return value.name
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
            # Labels such as slow/network change nothing but what -m and -k select.
            # Their arguments still run where the decorator does, so they must be literals.
            for value in (call.args + [kw.value for kw in call.keywords]) if call else []:
                self.constant(value)
            return Mark("label", True, kind)
        if kind == "filterwarnings":
            if call is None or call.keywords or not call.args:
                self.error(decorator, "filterwarnings takes filter strings")
            filters = []
            for argument in call.args:
                text = self.constant(argument, True)
                parsed = warning_filter(text) if isinstance(text, str) else None
                fields = [part.strip() for part in text.split(":")] if isinstance(text, str) else []
                if (parsed is None and len(fields) >= 3 and fields[0] != "error"
                        and fields[2].startswith(("pytest.", "_pytest."))):
                    continue  # (pytest's own warnings: the native program raises none)
                if parsed is None:
                    self.error(decorator, "filterwarnings marks support an action, a message and a built-in "
                               f"warning class: {text!r}")
                filters.append(parsed)
            self.warning_marks = True
            return Mark("filterwarnings", True, "", filters=tuple(filters))
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
            self.runtime_condition(decorator, expression)
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
        return Mark(kind, condition, reason, kws.get("strict", self.strict), kws.get("run", True), raises)

    def unit_mark(self, decorator, prelude, method):
        """unittest's skip decorators and expectedFailure, or None where the condition is false.

        A decorated method is skipped in its call phase, where unittest runs it; a
        decorated class in setup, as pytest's own skip marks are.
        """
        call = decorator if isinstance(decorator, ast.Call) else None
        kind = self.name(call.func if call else decorator).removeprefix("unittest.")
        if kind == "expectedFailure":
            if call is not None:
                self.error(decorator, "expectedFailure takes no arguments")
            return Mark("unit-xfail", True, "")
        if call is None or call.keywords or len(call.args) != (1 if kind == "skip" else 2):
            self.error(decorator, f"unittest.{kind} requires " + (
                "a reason" if kind == "skip" else "a condition and a reason"))
        reason = self.constant(call.args[-1], True)
        if not isinstance(reason, str):
            self.error(decorator, "marker reason must be a literal string")
        condition = True
        if kind != "skip":
            expression = call.args[0]
            value = self.evaluate(expression, None, True)
            if value is not UNKNOWN:
                if bool(value) != (kind == "skipIf"):
                    return None
            else:
                self.runtime_condition(decorator, expression)
                condition = f"_pyn_condition_{self.counter}"
                self.counter += 1
                source = ast.unparse(expression)
                prelude.append(f"{condition} = bool({source})" if kind == "skipIf" else f"{condition} = not ({source})")
        return Mark("unit-skip" if method else "skip" if condition is True else "skipif", condition, reason)

    def runtime_condition(self, decorator, expression):
        """Reject a skip condition that cannot run where the runner evaluates it: at module level."""
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

    def decorations(self, node, prelude, annotations, unit=False, method=True):
        """A test function's or test class's pytest marks, nearest decorator first."""
        parameters = []
        marks = []
        usefixtures = []
        for decorator in node.decorator_list:
            name = self.name(decorator.func if isinstance(decorator, ast.Call) else decorator)
            if isinstance(decorator, ast.Name) and decorator.id in self.mark_aliases and (
                    self.shadowed is None or decorator.id not in self.shadowed):
                # (One mark, read where the name was assigned.)
                named = self.mark_aliases[decorator.id]
                parameters.extend(named[0])
                marks.extend(named[1])
                usefixtures.append(named[2])
            elif name in UNITTEST_MARKS:
                if not unit:
                    self.error(decorator, "unittest decorators are supported on unittest.TestCase classes and "
                               "their methods only")
                mark = self.unit_mark(decorator, prelude, method)
                if mark is not None:
                    marks.append(mark)
            elif name == "pytest.mark.xfail" and unit:
                self.error(decorator, "pytest.mark.xfail on a unittest.TestCase is unsupported; "
                           "use unittest.expectedFailure")
            elif name == "pytest.mark.parametrize":
                parameter, setup = self.parameter(decorator, annotations)
                parameters.append(parameter)
                prelude.extend(setup)
                marks.append(Mark("label", True, "parametrize"))
            elif name in {"pytest.mark.skip", "pytest.mark.skipif", "pytest.mark.xfail",
                          "pytest.mark.filterwarnings"}:
                marks.append(self.marker(decorator, prelude))
            elif name == "pytest.mark.usefixtures":
                usefixtures.append(self.fixture_names(decorator))
                marks.append(Mark("label", True, "usefixtures"))
            elif name.startswith("pytest.mark.") and name != "pytest.mark.":
                marks.append(self.marker(decorator))  # (a label: see marker)
            else:
                self.error(decorator, "unsupported test decorator")
        # pytest reads marks nearest the function first, as it applies them.
        return (list(reversed(parameters)), list(reversed(marks)),
                [name for names in reversed(usefixtures) for name in names])

    def unittest_bases(self, node, seen=()):
        """Whether a class derives from unittest.TestCase, as far as this module shows."""
        for base in node.bases:
            name = self.name(base)
            if name == "unittest.TestCase":
                return True
            origin = self.attribute_base(base)
            if origin is not None and self.external_class(*origin) is not None:
                if self.external_class(*origin).unit:
                    return True
                continue
            # (An imported base that is called a test case very probably is one.)
            if isinstance(base, ast.Attribute) and base.attr.endswith("TestCase"):
                return True
            if isinstance(base, ast.Name):
                local = self.class_nodes.get(base.id)
                if local is not None and local is not node and local not in seen:
                    if self.unittest_bases(local, (*seen, node)):
                        return True
                elif local is None:
                    external = self.external_info(base.id)
                    if external is not None and external.unit or external is None and base.id.endswith("TestCase"):
                        return True
        return False

    def scan_imports(self):
        """Note what this module imports from pytest and unittest, and each `from` import."""
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("pytest", "unittest"):
                        self.aliases[alias.asname or alias.name] = alias.name
                    else:
                        # `import a.b` binds a, through which a.b is read; `import a.b as c` binds c.
                        self.module_names[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module in ("pytest", "unittest") and not node.level:
                    for alias in node.names:
                        self.aliases[alias.asname or alias.name] = node.module + "." + alias.name
                else:
                    for alias in node.names:
                        self.imported[alias.asname or alias.name] = (node.level, node.module, alias.name)

    def marker_base(self, base):
        """The name of a base class that only says how a class is typed, or "".

        typing.Protocol, typing.Generic[T], abc.ABC and object: the compiled class has
        no such base to derive from.
        """
        if isinstance(base, ast.Subscript):
            base = base.value
        dotted = ast.unparse(base) if isinstance(base, (ast.Name, ast.Attribute)) else ""
        if isinstance(base, ast.Name):
            if base.id == "object" and "object" not in self.bound:
                return "object"
            origin = self.imported.get(base.id)
            dotted = f"{origin[1]}.{origin[2]}" if origin is not None and not origin[0] else ""
        elif dotted:
            head, _, attribute = dotted.rpartition(".")
            dotted = self.module_names.get(head, "") + "." + attribute if head in self.module_names else ""
        return dotted if dotted in ("typing.Protocol", "typing.Generic", "typing_extensions.Protocol",
                                    "abc.ABC") else ""

    def attribute_base(self, base):
        """(level, module, name) of a base class written module.Class, or None."""
        if not isinstance(base, ast.Attribute):
            return None
        head = ast.unparse(base.value) if isinstance(base.value, (ast.Name, ast.Attribute)) else ""
        if head in self.module_names and head not in self.class_nodes:
            return 0, self.module_names[head], base.attr
        if isinstance(base.value, ast.Name) and base.value.id in self.imported:
            # (`from package import module`: the name may be a module of that package.)
            level, module, name = self.imported[base.value.id]
            return level, (module + "." if module else "") + name, base.attr
        return None

    def external_info(self, name, depth=0):
        """The class a `from` import binds to this name, read from its module beside the tests.

        Returns its ClassInfo, or None for a name that is no such class. Only a plain
        class is read: one whose own tests carry no decorators and that defines no
        fixtures, since its module is adapted, not collected.
        """
        if name not in self.imported:
            return None
        return self.external_class(*self.imported[name], depth)

    def external_constant(self, name):
        """The number, string, bytes or None that a `from` import binds to name, else UNKNOWN.

        Read as this module's own constants are, from syntax: the one module-level
        binding of the name in the module beside the tests that defines it, through the
        modules that pass it on. The program checks each value a test ID was made from.
        """
        if name in self.external_constants:
            return self.external_constants[name]
        value = self.external_constants[name] = UNKNOWN
        if (name not in self.imported or self.resolve is None
                or sum(_statement_names(statement).count(name) for statement in self.tree.body) != 1
                or any(isinstance(node, ast.Global) and name in node.names for node in ast.walk(self.tree))):
            return value
        level, module, original = self.imported[name]
        path = self.path
        for _ in range(8):
            found = self.resolve(path, level, module, original) if original != "*" else None
            if found is None:
                break
            path = found[2]
            try:
                tree = ast.parse(found[0])
            except (SyntaxError, RecursionError, ValueError):
                break
            bindings = [statement for statement in tree.body if original in _statement_names(statement)]
            if (len(bindings) != 1 or _statement_names(bindings[0]).count(original) != 1
                    or any(isinstance(node, ast.Global) and original in node.names for node in ast.walk(tree))):
                break
            statement = bindings[0]
            if isinstance(statement, ast.ImportFrom):
                level, module = statement.level, statement.module
                original = next(alias.name for alias in statement.names if (alias.asname or alias.name) == original)
                continue
            single = (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                      and isinstance(statement.targets[0], ast.Name)
                      or isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                      and statement.value is not None)
            if single:
                try:
                    literal = ast.literal_eval(statement.value)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    break
                if _scalar(literal):
                    value = literal
            break
        self.external_constants[name] = value
        return value

    def external_node(self, level, module, original, depth=0):
        """(generator of its module, class node) of a class another module defines, or None.

        A package's __init__ may pass on a class of one of its modules.
        """
        key = (level, module, original)
        if key in self.external_nodes:
            return self.external_nodes[key]
        self.external_nodes[key] = None
        if self.resolve is None or depth > 8:
            return None
        found = self.resolve(self.path, level, module, original)
        if found is None:
            return None
        source, filename, path, dotted = found
        try:
            other = Generator(source, filename, False, path=path, module=dotted, package=True, helper=True,
                              resolve=self.resolve)
        except (CollectionError, SyntaxError, RecursionError):
            return None
        other.class_nodes = {node.name: node for node in other.tree.body if isinstance(node, ast.ClassDef)}
        other.infos = {}
        other.bound = {name for statement in other.tree.body for name in _statement_names(statement)}
        other.scan_imports()
        node = other.class_nodes.get(original)
        if node is not None:
            self.external_nodes[key] = (other, node)
        elif original in other.imported:
            self.external_nodes[key] = other.external_node(*other.imported[original], depth + 1)
        return self.external_nodes[key]

    def constructed(self, node, depth=0, own=True):
        """Whether a class of this module has a constructor: pytest collects no such Test* class.

        It defines __init__ or __new__ (own), or a base does; a Protocol has one too.
        None when a base is one the collector cannot read (a built-in or installed class).
        """
        if own and any(isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and statement.name in ("__init__", "__new__") for statement in node.body):
            return True
        answer = False
        for base in node.bases:
            marker = self.marker_base(base)
            if marker.endswith(".Protocol"):
                return True
            if marker:
                continue
            found = None
            if isinstance(base, ast.Name) and self.class_nodes.get(base.id) not in (None, node):
                found = (self, self.class_nodes[base.id])
            elif isinstance(base, ast.Name) and base.id in self.imported:
                found = self.external_node(*self.imported[base.id])
            elif self.attribute_base(base) is not None:
                found = self.external_node(*self.attribute_base(base))
            if found is None or depth > 16:
                answer = None
                continue
            inner = found[0].constructed(found[1], depth + 1)
            if inner:
                return True
            if inner is None:
                answer = None
        return answer

    def external_class(self, level, module, original, depth=0):
        """The ClassInfo of a class of another module (external_info), named by how it is imported.

        None for a class the collector cannot use; external_reasons says why where the
        class is one it could read, for the test class that derives from it (most
        imported classes are no test's base).
        """
        name = (level, module, original)
        if name in self.external:
            return self.external[name]
        self.external[name] = None
        found = self.external_node(level, module, original, depth)
        if found is None:
            return None
        other, node = found
        filename = other.filename
        try:
            info = other.class_info(node)
        except CollectionError:
            return None  # (reported at the test class that derives from it)
        for ancestor in info.mro:
            if ancestor.tests or ancestor.node not in other.class_nodes.values():
                continue
            if ancestor.node.decorator_list:
                return self.unusable(name, ancestor.node, f"{filename}: decorators on an imported base class are "
                                     "unsupported: " + ancestor.node.name)
            for statement in ancestor.node.body:
                if any(target == "pytestmark" for target in _bound_names(statement)):
                    return self.unusable(name, statement,
                                         f"{filename}: pytestmark in an imported base class is unsupported")
                if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if any(other.name(dec.func if isinstance(dec, ast.Call) else dec)
                       for dec in statement.decorator_list) or (
                        statement.name.startswith("test") and statement.decorator_list):
                    return self.unusable(name, statement, f"{filename}: decorated methods of an imported base "
                                         "class are unsupported: " + statement.name)
                if ancestor.unit and statement.name in UNIT_UNSUPPORTED:
                    return self.unusable(name, statement,
                                         f"{filename}: unsupported unittest.TestCase method: " + statement.name)
        for ancestor in info.mro:
            if ancestor.tests or ancestor.node not in other.class_nodes.values():
                continue
            for statement in ancestor.node.body:
                if statement.name.startswith("test") if isinstance(statement, ast.FunctionDef) else False:
                    ancestor.tests[statement.name] = Test(statement, ancestor.node, [], [], [], ancestor.unit)
        self.external[name] = info
        return info

    def unusable(self, name, node, message):
        """Note why an imported class cannot be a test's base (external_class); returns None."""
        self.external_reasons[name] = (node, message)
        return None

    def imported_kind(self, node, alias):
        """What pytest makes of an imported name that begins test or Test.

        "inert" when it collects nothing: a module; a class that has a constructor, or
        whose name begins test (pytest collects Test* classes); a function whose name
        begins Test. "class" for a class it collects that the collector can read: a
        unittest case, or a Test* class without a constructor. None for anything else,
        which may be a test the collector cannot read.
        """
        local = alias.asname or alias.name
        if self.resolve is None:
            return None
        if self.resolve(self.path, node.level, (node.module + "." if node.module else "") + alias.name, "") is not None:
            return "inert"
        found = self.external_node(node.level, node.module, alias.name)
        if found is not None:
            other, definition = found
            readable = self.external_info(local) is not None and not self.conftest
            if other.unittest_bases(definition):
                return "class" if readable else None
            if local.startswith("test"):
                return "inert"
            constructed = other.constructed(definition)
            if constructed is None:
                return None
            return "inert" if constructed else "class" if readable else None
        located = self.resolve(self.path, node.level, node.module, alias.name)
        if located is None:
            return None
        try:
            body = ast.parse(located[0]).body
        except (SyntaxError, RecursionError):
            return None
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name == alias.name:
                return "inert" if local.startswith("Test") else None
        return None

    def class_info(self, node):
        """This class with its module-level bases resolved, or an error for bases it cannot read."""
        if node in self.infos:
            return self.infos[node]
        if node.keywords:
            self.error(node, "test classes with class keywords are unsupported")
        unit = False
        bases = []
        for base in node.bases:
            if self.name(base) == "unittest.TestCase":
                unit = True
            elif isinstance(base, ast.Name) and self.class_nodes.get(base.id) not in (None, node) \
                    and self.class_nodes[base.id].lineno < node.lineno:
                bases.append(self.class_info(self.class_nodes[base.id]))
            elif isinstance(base, ast.Name) and base.id not in self.class_nodes and self.external_info(base.id):
                bases.append(self.external_info(base.id))
            elif self.attribute_base(base) is not None and self.external_class(*self.attribute_base(base)):
                bases.append(self.external_class(*self.attribute_base(base)))
            elif not self.marker_base(base):
                origin = (self.imported.get(base.id) if isinstance(base, ast.Name) else self.attribute_base(base))
                if origin in self.external_reasons:
                    self.error(node, self.external_reasons[origin][1])
                self.error(node, "test classes with imported or computed base classes are unsupported: "
                           + ast.unparse(base))
        if len(bases) + unit > 1:
            # (Compiled classes have one base; the unittest replacement is one.)
            self.error(node, "test classes with several base classes are unsupported")
        info = ClassInfo(node, unit or any(base.unit for base in bases), bases)
        info.mro = [info] + [ancestor for base in bases for ancestor in base.mro]
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                info.names.add(statement.name)
            elif isinstance(statement, ast.Import):
                info.names.update(alias.asname or alias.name.split(".")[0] for alias in statement.names)
            elif isinstance(statement, ast.ImportFrom):
                info.names.update(alias.asname or alias.name for alias in statement.names)
            else:
                info.names.update(_bound_names(statement))
        self.infos[node] = info
        return info

    def mark_alias(self, node, names, assigned):
        """`slow = pytest.mark.slow` or `needs_x = pytest.mark.skipif(...)`: a name for a mark.

        The mark is read here, where the statement runs, and the statement is left out
        of the program: a decorator that is the name stands for the mark.
        """
        value = node.value
        resolved = self.name(value.func if isinstance(value, ast.Call) else value)
        if resolved != "pytest.mark" and not resolved.startswith("pytest.mark."):
            return False
        if len(names) != 1 or assigned.get(names[0]) != 1 or self.conftest or names[0].startswith(("test", "Test")):
            self.error(node, "a pytest mark may be given one module-level name of a test module, assigned once")
        if isinstance(value, ast.Call) and resolved != "pytest.mark":
            holder = ast.copy_location(ast.ClassDef(names[0], [], [], [], [value]), node)
            self.mark_aliases[names[0]] = self.decorations(holder, self.preludes.setdefault(node, []), {},
                                                           method=False)
        else:
            # (pytest.mark itself, or a mark that takes its arguments where it decorates.)
            self.aliases[names[0]] = resolved
        self.dropped.add(node)
        return True

    def marks_of(self, node, value, prelude, unit):
        """The marks of `pytestmark = mark` or `pytestmark = [mark, ...]`, first one nearest."""
        if isinstance(node, ast.Assign) and len(node.targets) != 1:
            self.error(node, "pytestmark must be assigned once, to a mark or a list of marks")
        items = value.elts if isinstance(value, (ast.List, ast.Tuple)) else [value]
        holder = ast.copy_location(ast.ClassDef("pytestmark", [], [], [], list(reversed(items))), node)
        return self.decorations(holder, prelude, {}, unit=unit, method=False)

    def collect(self):
        direct = set(self.tree.body)
        parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}
        self.class_nodes = {node.name: node for node in self.tree.body if isinstance(node, ast.ClassDef)}
        self.infos = {}
        self.scan_imports()
        seen = set()
        assigned = {}
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.bound.add(node.name)
                self.named[node.name] = node.name
            elif isinstance(node, ast.Import):
                # (A module is neither callable nor a class: pytest collects nothing from
                # "import test_helpers", whatever the module's name.)
                for alias in node.names:
                    self.bound.add(alias.asname or alias.name.split(".")[0])
                    if alias.asname or "." not in alias.name:
                        self.modules[alias.asname or alias.name] = alias.name
                    if alias.name in ("pytest", "unittest"):
                        self.aliases[alias.asname or alias.name] = alias.name
                    elif alias.name.startswith("pytest.") or alias.name.startswith("_pytest"):
                        self.error(node, "pytest internals are unsupported")
                    elif alias.name.startswith("unittest."):
                        self.error(node, "unsupported unittest import: " + alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    self.bound.add(alias.asname or alias.name)
                    # (An imported CONSTANT is a value, not something with a __name__.)
                    if not alias.name.isupper() and alias.name != "*":
                        self.named[alias.asname or alias.name] = alias.name
                if node.module in ("pytest", "unittest") and not node.level:
                    allowed = PYTEST_IMPORTS | PYTEST_TYPES if node.module == "pytest" else UNITTEST_IMPORTS
                    for alias in node.names:
                        if alias.name not in allowed:
                            self.error(node, f"unsupported {node.module} import: " + alias.name)
                        self.aliases[alias.asname or alias.name] = node.module + "." + alias.name
                elif (node.module or "").startswith("_pytest") and not node.level and all(
                        alias.name in PYTEST_TYPES for alias in node.names):
                    # (Names for annotations, which the runner removes.)
                    for alias in node.names:
                        self.aliases[alias.asname or alias.name] = "pytest." + alias.name
                    self.dropped.add(node)
                elif (node.module or "").startswith(("_pytest", "unittest.")):
                    self.error(node, f"unsupported import from {node.module}")
            else:
                names = _bound_names(node)
                self.bound.update(names)
                for name in names:
                    assigned[name] = assigned.get(name, 0) + 1
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    self.bindings[node.targets[0].id] = node.value
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                    self.bindings[node.target.id] = node.value
        for name in list(self.named):
            if name in assigned:
                del self.named[name]
        for name in list(self.bindings):
            if assigned.get(name) != 1 or name in self.named or name in self.modules:
                del self.bindings[name]
        self.rebound = {name for name, count in assigned.items() if count > 1}
        # The classes pytest collects: unittest cases whatever their names, and Test* classes.
        # (A Test* class that inherits a constructor is no test class to pytest.)
        collected = [node for node in self.tree.body if isinstance(node, ast.ClassDef)
                     and (self.unittest_bases(node)
                          or node.name.startswith("Test") and self.constructed(node, own=False) is not True)]
        classes = set()
        for node in collected:
            classes.update(info.node for info in self.class_info(node).mro)
        for node in self.tree.body:
            if (isinstance(node, ast.ClassDef) and node not in classes and node.bases
                    and any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test")
                            for item in node.body)
                    and self.constructed(node, own=False) is None
                    and any(not (isinstance(base, ast.Name) and (base.id in self.class_nodes
                                                                 or self.external_info(base.id) is not None))
                            and not self.marker_base(base) for base in node.bases)):
                # Its base may be a unittest case defined elsewhere, which pytest would collect.
                self.error(node, "a class with test methods has a base class the collector cannot read: "
                           + ast.unparse(node.bases[0]))

        def plain(value):
            # A value that is neither callable nor a class, so pytest collects no test from
            # `test_cases = [...]` or `TestData = (...)`, at module level or in a test class.
            return _literal(value) or isinstance(value, (
                ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp, ast.JoinedStr,
                ast.Constant, ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp))

        literal_targets = set()
        marks = {}
        for holder in [self.tree, *classes]:
            for node in holder.body:
                target = (node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1
                          else node.target if isinstance(node, ast.AnnAssign) and node.value is not None else None)
                if target is not None and plain(node.value):
                    literal_targets.add(target)
                if any(name == "pytestmark" for name in (_bound_names(node) if isinstance(
                        node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) else [])):
                    if not isinstance(target, ast.Name) or holder in marks:
                        self.error(node, "pytestmark must be assigned once, to a mark or a list of marks")
                    marks[holder] = node
        mark_names = {target for node in marks.values() for target in ast.walk(node)
                      if isinstance(target, ast.Name) and target.id == "pytestmark"}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and node.id.startswith("_pyn_"):
                self.error(node, "names beginning _pyn_ are reserved by the native runner")
            if isinstance(node, ast.Name) and (node.id in {
                    "__package__", "__spec__", "__test__", "__annotations__", "pytest_plugins"}
                    or node.id in {"__file__", "__name__"} and not isinstance(node.ctx, ast.Load)
                    or node.id == "pytestmark" and node not in mark_names):
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
            if isinstance(node, ast.ImportFrom) and node.level and not self.package:
                # (Python has no parent package to resolve it in: pytest fails to import this.)
                self.error(node, "relative imports require the test's directory to be a package (__init__.py)")
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in direct:
                imported = ([item.name for item in node.names] if isinstance(node, ast.Import)
                            else [node.module or ""])
                if any(name in ("pytest", "unittest") or name.startswith(("pytest.", "_pytest", "unittest."))
                       for name in imported):
                    self.error(node, "pytest and unittest imports must be at module level")
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
            if isinstance(node, ast.ClassDef) and node not in direct:
                scope = parents.get(node)
                while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    scope = parents.get(scope)
                # (pytest collects module attributes: a class made inside a function is not one.)
                if scope is None and (node.name.startswith("Test") or self.unittest_bases(node)):
                    self.error(node, "nested and conditional test classes are unsupported")
        module_marks = ([], [], [])
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom) and node.module not in ("pytest", "unittest"):
                for alias in node.names:
                    local = alias.asname or alias.name
                    if alias.name == "*" or (local.startswith(("test", "Test"))
                                             and self.imported_kind(node, alias) is None):
                        self.error(node, "imported tests and star imports are unsupported")
                for alias in node.names:
                    # pytest collects a unittest case from every module that imports it, and
                    # a class called Test* that has no constructor.
                    local = alias.asname or alias.name
                    external = self.external_info(local)
                    origin = self.imported.get(local)
                    if external is None and origin in self.external_reasons and not self.conftest:
                        # pytest would collect it here: what the collector cannot use is an error.
                        found = self.external_node(*origin)
                        if found is not None and (found[0].unittest_bases(found[1]) or local.startswith("Test")):
                            self.error(node, self.external_reasons[origin][1])
                    if external is not None and not self.conftest and (
                            external.unit or local.startswith("Test") and self.imported_kind(node, alias) == "class"):
                        bound = copy.copy(external.node)
                        bound.name = local
                        info = ClassInfo(bound, external.unit, external.bases, [], tests=external.tests,
                                         names=external.names)
                        info.mro = [info, *external.mro[1:]]
                        self.infos[bound] = info
                        self.collected_tests(info)
            elif node is marks.get(self.tree):
                if self.conftest:
                    self.error(node, "pytestmark in conftest.py is unsupported")
                module_marks = self.marks_of(node, node.value, self.preludes.setdefault(node, []), False)
                self.dropped.add(node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = _bound_names(node)
                if any(name in self.aliases for name in names):
                    self.error(node, "rebinding pytest or dynamically assigning tests is unsupported")
                if node.value is None:
                    continue
                if self.mark_alias(node, names, assigned):
                    continue
                try:
                    value = self.constant(node.value)
                except CollectionError:
                    for name in names:
                        self.constants.pop(name, None)
                else:
                    if len(names) == 1 and assigned.get(names[0]) == 1:
                        self.constants[names[0]] = value
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen or node.name in self.aliases:
                    self.error(node, "duplicate function or pytest binding: " + node.name)
                seen.add(node.name)
                if node not in self.dropped:
                    self.declare(node, None, self.preludes.setdefault(node, []))
            elif node in classes:
                if node.name in seen or node.name in self.aliases:
                    self.error(node, "duplicate function or pytest binding: " + node.name)
                seen.add(node.name)
                self.collect_class(self.infos[node], marks.get(node), node in collected)
        for test in self.tests:
            test.parameters = test.parameters + module_marks[0]
            test.marks = test.marks + module_marks[1]
            test.usefixtures = test.usefixtures + module_marks[2]
            if test.unit and test.parameters:
                self.error(test.function, "unittest test methods cannot be parametrized")
            self.check_test(test)
        if len(self.tests) > 10000:
            self.error(self.tree, "more than 10000 tests in one module")
        for owner, fixtures in self.class_fixtures.items():
            for name in fixtures:
                if name in self.fixtures or name in self.shared:
                    self.error(self.tree, "overriding a fixture in a test class is unsupported: " + name)
        self.validate_declarations()
        self.validate_constants()

    def collect_class(self, info, pytestmark, collected):
        """A test class or a base of one: pytest runs each test method on a new instance.

        A base class declares its methods' marks and fixtures once; each class pytest
        collects then takes its own tests and those it inherits.
        """
        node = info.node
        if self.conftest:
            self.error(node, "conftest.py cannot define tests")
        self.shadowed = info.names
        prelude = self.preludes.setdefault(node, [])
        # A class's decorators run before its body does; pytest reads `pytestmark` in the
        # body first, then the decorators from the nearest.
        own = ([], [], [])
        if pytestmark is not None:
            own = self.marks_of(pytestmark, pytestmark.value, prelude, info.unit)
            self.dropped.add(pytestmark)
        decorated = self.decorations(node, prelude, {}, unit=info.unit, method=False)
        info.parameters, info.marks, info.usefixtures = (own[index] + decorated[index] for index in range(3))
        members = set()
        for statement in node.body:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if statement.name in members:
                self.error(statement, "duplicate method in a test class: " + statement.name)
            members.add(statement.name)
            if info.unit and (statement.name in UNIT_UNSUPPORTED or statement.name in XUNIT_METHOD):
                self.error(statement, "unsupported unittest.TestCase method: " + statement.name)
            if statement.name in XUNIT_METHOD:
                # pytest passes the test method; the runner has no such object to pass.
                arguments = statement.args
                extra = arguments.args[1:]
                if (isinstance(statement, ast.AsyncFunctionDef) or statement.decorator_list or arguments.vararg
                        or arguments.kwarg or arguments.kwonlyargs or arguments.posonlyargs
                        or len(arguments.args) not in (1, 2) or self.is_generator(statement)):
                    self.error(statement, f"{statement.name} must be a plain method of (self) or (self, method)")
                # (It may be handed on to super()'s hook, which the runner calls without it too.)
                passed = {argument for part in ast.walk(statement) if isinstance(part, ast.Call)
                          and isinstance(part.func, ast.Attribute) and part.func.attr in XUNIT_METHOD
                          and isinstance(part.func.value, ast.Call) and isinstance(part.func.value.func, ast.Name)
                          and part.func.value.func.id == "super" for argument in part.args}
                if extra and any(isinstance(part, ast.Name) and part.id == extra[0].arg and part not in passed
                                 for part in ast.walk(statement)):
                    self.error(statement, f"the method argument of {statement.name} is unsupported")
                info.hooks[statement.name] = statement
                continue
            if statement.name in ("__init__", "__new__"):
                # pytest warns and collects nothing from such a class.
                self.error(statement, "test classes cannot define __init__ or __new__")
            test = self.declare(statement, info, prelude)
            if test is not None:
                info.tests[statement.name] = test
        self.shadowed = None
        self.classes.append(node)
        if collected:
            self.collected_tests(info)

    def collected_tests(self, info):
        """Add the tests of a class pytest collects: its own and those it inherits."""
        node = info.node
        # Marks of the class and its bases apply to each test: a base's first, as pytest
        # lists them along the class's ancestry.
        parameters = [parameter for ancestor in reversed(info.mro) for parameter in ancestor.parameters]
        marks = [mark for ancestor in reversed(info.mro) for mark in ancestor.marks]
        usefixtures = [name for ancestor in reversed(info.mro) for name in ancestor.usefixtures]
        if info.unit:
            # unittest sorts the names of a case's test methods, inherited ones too.
            found = {}
            for ancestor in reversed(info.mro):
                for name in ancestor.names:
                    found.pop(name, None)
                found.update(ancestor.tests)
            inherited = [found[name] for name in sorted(found)]
        else:
            # pytest lists a base's tests before its subclass's, each in definition order;
            # any attribute of a subclass hides the base's of that name.
            inherited = []
            hidden = set()
            for ancestor in info.mro:
                inherited = [test for name, test in ancestor.tests.items() if name not in hidden] + inherited
                hidden |= ancestor.names
        for test in inherited:
            self.tests.append(Test(test.function, node, test.parameters + parameters, test.marks + marks,
                                   test.usefixtures + usefixtures, info.unit))

    def declare(self, node, info, prelude):
        """Record a fixture or a test (returned); other functions are the module's own."""
        owner = info.node if info is not None else None
        unit = info is not None and info.unit
        fixture = [dec for dec in node.decorator_list
                   if self.name(dec.func if isinstance(dec, ast.Call) else dec) == "pytest.fixture"]
        if fixture:
            if unit:
                self.error(node, "fixtures defined in a unittest.TestCase are unsupported")
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
        parameters, marks, usefixtures = self.decorations(node, prelude, annotations, unit=unit)
        test = Test(node, owner, parameters, marks, usefixtures, unit)
        if owner is None:
            self.tests.append(test)
        elif unit and self.arguments(node, bound=True):
            self.error(node, "unittest test methods take no arguments")
        return test

    def check_test(self, test):
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
        if owner is not None and scope != "function":
            self.error(decorator, "fixtures defined in a test class must be function-scoped")
        arguments = self.arguments(node, bound=owner is not None)
        if fixture_name in arguments:
            # (pytest gives such a fixture the one it overrides.)
            self.error(decorator, "a fixture that requests the fixture it overrides is unsupported: " + fixture_name)
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
        if request and parameter is None and not any(
                isinstance(part, ast.Name) and part.id == "request" for part in ast.walk(node)):
            # (A fixture that asks for request and never reads it.)
            request = False
            self.unused_requests.add(node)
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
        functions.update(test.function for info in self.infos.values() for test in info.tests.values())
        functions.update(fixture.function for fixture in self.fixtures.values())
        for fixtures in self.class_fixtures.values():
            functions.update(fixture.function for fixture in fixtures.values())
        return functions

    def validate_constants(self):
        # The collector read these names' values from their one binding. A named table's
        # rows are read again where the program has finished importing, as pytest reads
        # them, and its length is checked there (table_length); a second binding would
        # make the collector's reading another object's.
        for name in sorted(self.metadata_constants):
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
                self.error(self.tree, "parametrize constants require one literal binding: " + name)
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Global) and name in node.names:
                    self.error(node, "parametrize constants cannot be rebound through globals: " + name)
            for node in self.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                    continue
                references = [part for part in ast.walk(node) if isinstance(part, ast.Name) and part.id == name]
                if not references or node in self.dropped:
                    continue
                stores = [part for part in references if isinstance(part.ctx, ast.Store)]
                # Its definition, or an assignment whose value the collector reads whole
                # (which neither changes the table nor keeps another name for it).
                inside = set(ast.walk(node.value)) if getattr(node, "value", None) is not None else set()
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and (references == stores or (
                        all(part in inside for part in references)
                        and self.evaluate(node.value) is not UNKNOWN)):
                    continue
                self.error(node, "parametrize constants cannot be mutated or escape during import: " + name)

    def fixture_functions(self):
        return {fixture.function.name for fixture in self.fixtures.values()}

    def own_fixtures(self, owner):
        """The fixtures a test class defines or inherits, a subclass's over its base's."""
        fixtures = {}
        if owner is not None:
            for ancestor in reversed(self.infos[owner].mro):
                fixtures.update(self.class_fixtures.get(ancestor.node.name, {}))
        return fixtures

    def hooked(self, owner, name=None):
        """Whether a test class defines or inherits setup_method or teardown_method (or the one named)."""
        if owner is None:
            return False
        return any(hook in ancestor.hooks for ancestor in self.infos[owner].mro
                   for hook in ([name] if name else XUNIT_METHOD))

    def visible(self, owner):
        """The fixtures a test of this class (or of the module) can request, by name."""
        fixtures = dict(BUILTIN_FIXTURES)
        fixtures.update(self.shared)
        fixtures.update(self.fixtures)
        fixtures.update(self.own_fixtures(owner))
        if self.hooked(owner):
            # setup_method and teardown_method run as one fixture of the class: its setup
            # makes the test's object (Rewrite makes setup_method the class's __init__).
            fixtures[INSTANCE] = Fixture(None, [], self.hooked(owner, "teardown_method"), True, origin="instance")
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
        groups = [*self.shared_groups, self.fixtures]
        if test.owner is not None:
            groups.append(self.own_fixtures(test.owner))
        for index, group in enumerate(groups):
            if test.owner is not None and index == len(groups) - 1 and self.hooked(test.owner) and not test.unit:
                # pytest registers a class's setup_method ahead of the class's own fixtures.
                names.append(INSTANCE)
            # (A fixture that a nearer file, the module or the class overrides is theirs.)
            names += sorted((name for name, fixture in group.items() if fixture.autouse
                             and not any(name in later for later in groups[index + 1:])),
                            key=lambda name: group[name].function.name)
        names += test.usefixtures + self.arguments(test.function, bound=test.owner is not None)
        closure = []
        nearer = {**self.fixtures, **self.own_fixtures(test.owner)}

        def visit(name):
            if name in closure:
                return
            closure.append(name)
            if name in direct:
                return
            if name in self.unavailable and name not in nearer:
                self.error(test.function, f"the fixture {name} was left out: {self.unavailable[name]}")
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
        # (`pytestmark = ...` statements are declarations too.)
        decorators.update(item for statement in self.dropped for item in ast.walk(statement))
        # A parameter annotated with one of pytest's types (monkeypatch: pytest.MonkeyPatch)
        # is typed by the value the runner passes: Rewrite removes the annotation.
        decorators.update(item for annotation in self.pytest_annotations() for item in ast.walk(annotation))
        method_fixtures = {fixture.function.name for fixtures in self.class_fixtures.values()
                           for fixture in fixtures.values()}
        monkeypatch = all("monkeypatch" not in fixtures for fixtures in
                          [self.shared, self.fixtures, *self.class_fixtures.values()])
        # monkeypatch, and each m of `with monkeypatch.context() as m:`.
        receivers = {"monkeypatch"} | {
            item.optional_vars.id for node in ast.walk(self.tree) if isinstance(node, ast.With)
            for item in node.items if isinstance(item.optional_vars, ast.Name)
            and isinstance(item.context_expr, ast.Call) and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == "context" and isinstance(item.context_expr.func.value, ast.Name)
            and item.context_expr.func.value.id == "monkeypatch"}
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
                    and node.value.id in receivers and node.attr in MONKEYPATCH_WRITTEN):
                self.patch_plan(node, parents)
            elif (monkeypatch and isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "monkeypatch" and node.attr not in MONKEYPATCH):
                self.error(node, f"monkeypatch.{node.attr} is unsupported; setenv, delenv, setattr, setitem, "
                           "delitem, chdir, context and undo are supported")
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
            if name.startswith("unittest"):
                if name == "unittest.SkipTest" or (name == "unittest.TestCase" and isinstance(parent, ast.ClassDef)
                                                   and node in parent.bases):
                    continue
                self.error(node, "unsupported unittest use: " + name)
            if not (isinstance(parent, ast.Call) and parent.func is node and name in PYTEST_CALLS):
                self.error(node, "unsupported pytest use: " + name)
            if name in WARNS:
                item = parents.get(parent)
                block = parents.get(item)
                if not (isinstance(item, ast.withitem) and isinstance(block, ast.With) and len(block.items) == 1
                        and (item.optional_vars is None or isinstance(item.optional_vars, ast.Name))):
                    self.error(parent, name.removeprefix("pytest.") + " is supported as the one context of a with "
                               "statement")
                if len(parent.args) > WARNS[name] or any(kw.arg != "match" for kw in parent.keywords):
                    self.error(parent, name.removeprefix("pytest.") + " supports "
                               + ("warning classes and " if WARNS[name] else "") + "match= only")
                continue
            if name == "pytest.raises":
                expected = parent.args[0] if parent.args else None
                statement = parents.get(parent)
                if len(parent.args) > 1:
                    # raises(E, function, *arguments): written out as a with block.
                    if not (isinstance(statement, ast.Expr) or isinstance(statement, ast.Assign)
                            and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name)):
                        self.error(parent, "the callable form of raises must be a statement of its own")
                elif (expected is None or (isinstance(expected, ast.Tuple) and not expected.elts)
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
        if any(info.hooks for info in self.infos.values()):
            for node in ast.walk(self.tree):
                if isinstance(node, ast.Attribute) and node.attr in XUNIT_METHOD and not (
                        isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "super" and isinstance(parents.get(node), ast.Call)):
                    self.error(node, f"{node.attr} may be called through super() only")
        for function, receiver in self.unit_methods().items():
            for node in ast.walk(function):
                if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == receiver):
                    continue
                parent = parents.get(node)
                called = isinstance(parent, ast.Call) and parent.func is node
                if node.attr in UNIT_UNSUPPORTED or node.attr == "setUp":
                    self.error(node, "unsupported unittest.TestCase use: " + node.attr)
                if node.attr == "subTest":
                    statement = parents.get(parent) if called else None
                    if not (isinstance(statement, ast.withitem) and statement.optional_vars is None):
                        self.error(node, "subTest is supported as `with self.subTest(...):` only")
                    for value in parent.args + [kw.value for kw in parent.keywords]:
                        if any(isinstance(part, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr))
                               for part in ast.walk(value)):
                            self.error(node, "subTest arguments must be names, literals and attributes")
                if node.attr in UNIT_WARNS:
                    item = parents.get(parent) if called else None
                    block = parents.get(item)
                    if not (isinstance(item, ast.withitem) and isinstance(block, ast.With) and len(block.items) == 1
                            and (item.optional_vars is None or isinstance(item.optional_vars, ast.Name))
                            and len(parent.args) == UNIT_WARNS[node.attr] and not parent.keywords):
                        self.error(node, f"{node.attr} is supported as `with self.{node.attr}(...):` only")
                if node.attr in ("assertRaises", "assertRaisesRegex") and called:
                    fixed = 1 if node.attr == "assertRaises" else 2
                    if len(parent.args) < fixed or (len(parent.args) > fixed and not isinstance(
                            parents.get(parent), ast.Expr)):
                        self.error(parent, f"the callable form of {node.attr} must be a statement of its own")
                    if len(parent.args) == fixed and any(kw.arg != "msg" for kw in parent.keywords):
                        self.error(parent, f"{node.attr} supports an exception class"
                                   + (" and a pattern" if fixed == 2 else "") + " only")

    def patch_plan(self, node, parents):
        """Plan monkeypatch.setattr(target, "name", value), setitem(mapping, key, value) or delitem(mapping, key).

        A compiled program has no object to hold "the attribute name of any target",
        so each call becomes a call of its own function, typed by its arguments, that
        changes the value and hands monkeypatch the statements that put it back
        (patch_function). A target that is a name of the module, such as an imported
        module or a class, is written there as the test names it: neither is a value
        the program can pass.
        """
        method = node.attr
        call = parents.get(node)
        statement = parents.get(call)
        if not (isinstance(call, ast.Call) and call.func is node and isinstance(statement, ast.Expr)):
            self.error(node, f"monkeypatch.{method} is supported as a statement of its own")
        arguments = list(call.args)
        raising = True
        for option in call.keywords:
            if option.arg == "raising" and isinstance(option.value, ast.Constant) \
                    and isinstance(option.value.value, bool) and method != "setitem":
                raising = option.value.value
            else:
                self.error(call, f"monkeypatch.{method} takes its arguments by position, and raising= as a literal")
        if any(isinstance(argument, ast.Starred) for argument in arguments):
            self.error(call, f"monkeypatch.{method} arguments cannot be unpacked")
        if method == "setattr":
            if len(arguments) == 2 and isinstance(arguments[0], ast.Constant) and isinstance(arguments[0].value, str):
                self.error(call, "monkeypatch.setattr with a dotted name is unsupported: give the object and "
                           "the attribute's name")
            if len(arguments) != 3 or not (isinstance(arguments[1], ast.Constant) and isinstance(arguments[1].value, str)
                                           and arguments[1].value.isidentifier()):
                self.error(call, 'monkeypatch.setattr is supported as setattr(target, "name", value)')
            if not raising:
                self.error(call, "monkeypatch.setattr(raising=False) is unsupported: a compiled object has "
                           "the attributes its class gives it")
        elif method == "chdir":
            if len(arguments) != 1 or call.keywords:
                self.error(call, "monkeypatch.chdir is supported as chdir(path)")
            self.patches[call] = (method, len(self.patches), True, raising)
            return
        elif len(arguments) != (3 if method == "setitem" else 2):
            self.error(call, f"monkeypatch.{method} is supported as "
                       + ("setitem(mapping, key, value)" if method == "setitem" else "delitem(mapping, key)"))
        target = arguments[0]
        root = target
        while isinstance(root, ast.Attribute):
            root = root.value
        function = parents.get(statement)
        while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            function = parents.get(function)
        local = set()
        if function is not None and not isinstance(function, ast.Lambda):
            local = _local_bindings(function) | {argument.arg for argument in ast.walk(function.args)
                                                 if isinstance(argument, ast.arg)}
        named = isinstance(root, ast.Name) and root.id in self.bound and root.id not in local
        self.patches[call] = (method, len(self.patches), named, raising)

    def patch_function(self, call):
        """(the function of one monkeypatch call, the call of it): see patch_plan."""
        method, number, named, raising = self.patches[call]
        receiver = call.func.value
        if method == "chdir":
            # (The directory the first chdir left is the last to be restored, as pytest's one saved value.)
            text = "\n".join([f"def _pyn_patch_{number}(_pyn_patch, _pyn_value) -> None:",
                              "    _pyn_old = _pyn_os.getcwd()", "    def _pyn_undo() -> None:",
                              "        _pyn_os.chdir(_pyn_old)", "    _pyn_os.chdir(str(_pyn_value))",
                              "    _pyn_patch.later(_pyn_undo)"])
            return text, ast.Expr(ast.Call(ast.Name(f"_pyn_patch_{number}", ast.Load()), [receiver, call.args[0]], []))
        target = ast.unparse(call.args[0]) if named else "_pyn_target"
        passed = [receiver] + ([] if named else [call.args[0]])
        parameters = ["_pyn_patch"] + ([] if named else ["_pyn_target"])
        name = f"_pyn_patch_{number}"
        if method == "setattr":
            place = f"{target}.{call.args[1].value}"
            passed.append(call.args[2])
            body = [f"_pyn_old = {place}", "def _pyn_undo() -> None:", f"    {place} = _pyn_old",
                    f"{place} = _pyn_value", "_pyn_patch.later(_pyn_undo)"]
            parameters.append("_pyn_value")
        elif method == "setitem":
            passed += call.args[1:]
            parameters += ["_pyn_key", "_pyn_value"]
            # (Without an old value, the new one stands in to type the variable.)
            body = [f"_pyn_had = _pyn_key in {target}",
                    f"_pyn_old = {target}[_pyn_key] if _pyn_had else _pyn_value",
                    "def _pyn_undo() -> None:", "    if _pyn_had:", f"        {target}[_pyn_key] = _pyn_old",
                    f"    elif _pyn_key in {target}:", f"        del {target}[_pyn_key]",
                    f"{target}[_pyn_key] = _pyn_value", "_pyn_patch.later(_pyn_undo)"]
        else:
            passed.append(call.args[1])
            parameters.append("_pyn_key")
            body = [f"if _pyn_key not in {target}:",
                    *(["    raise KeyError(_pyn_key)"] if raising else ["    return"]),
                    f"_pyn_old = {target}[_pyn_key]", "def _pyn_undo() -> None:",
                    f"    {target}[_pyn_key] = _pyn_old", f"del {target}[_pyn_key]", "_pyn_patch.later(_pyn_undo)"]
        text = "\n".join([f"def {name}({', '.join(parameters)}) -> None:", *("    " + line for line in body)])
        return text, ast.Expr(ast.Call(ast.Name(name, ast.Load()), passed, []))

    def pytest_annotations(self):
        """Annotations of functions' parameters, and their returns, that name pytest."""
        found = []
        for function in ast.walk(self.tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            arguments = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
            for annotation in [argument.annotation for argument in arguments] + [function.returns]:
                if annotation is not None and any(self.name(part).startswith("pytest")
                                                  for part in ast.walk(annotation)):
                    found.append(annotation)
        return found

    def unit_methods(self):
        """Each method of a unittest case with the name of its receiver (`self`)."""
        methods = {}
        own = set(self.class_nodes.values())
        for info in self.infos.values():
            # (A base class imported from another module is adapted with that module.)
            if info.unit and info.node in own:
                for statement in info.node.body:
                    if isinstance(statement, ast.FunctionDef) and statement.args.args and not any(
                            isinstance(dec, ast.Name) and dec.id in ("staticmethod", "classmethod")
                            for dec in statement.decorator_list):
                        methods[statement] = statement.args.args[0].arg
        return methods

    def plain_read(self, node):
        """Whether evaluating node runs none of the test's code and cannot be changed by a call.

        A constant, a name, and an attribute of a module or of a class that this file
        names (math.pi, Color.RED). A call, a computation, a subscript and an attribute
        of an object, whose lookup may be a property, are not.
        """
        if self.fixed_names is None:
            # (Once per module: a generated file has thousands of such calls.)
            self.fixed_names = set(self.modules) | set(self.imported) | {
                item.name for item in ast.walk(self.tree) if isinstance(item, ast.ClassDef)}
        fixed = self.fixed_names

        def static(part):
            while isinstance(part, ast.Attribute):
                part = part.value
            return isinstance(part, ast.Name) and part.id in fixed

        return not any(isinstance(part, (ast.Call, ast.BinOp, ast.Subscript, ast.Await, ast.Yield, ast.YieldFrom,
                                         ast.NamedExpr, ast.ListComp, ast.SetComp, ast.DictComp,
                                         ast.GeneratorExp, ast.IfExp, ast.Compare, ast.BoolOp, ast.UnaryOp,
                                         ast.JoinedStr))
                       or (isinstance(part, ast.Attribute) and not static(part)) for part in ast.walk(node))

    def raises_block(self, context, callee, arguments, keywords, target, number):
        """`with context [as target]: callee(*arguments)` for raises(E, callee, *arguments).

        pytest looks the function up, then evaluates the arguments, and only then calls
        it: only the call itself may raise E. So what may run code or be changed by a
        later argument is bound first, in that order: a call or a computation, and an
        attribute of an object, whose lookup may be a property that raises and whose
        field an argument's call may replace. A name is read where it is called, as is
        an attribute of a module or of a class that this file names (math.floor,
        Path.cwd): reading those runs none of the test's code, and a class's method is
        no value a native program can hold.
        """
        before = []
        simple = self.plain_read

        def bound(node):
            if isinstance(node, ast.Starred):
                return ast.Starred(bound(node.value), ast.Load())
            if simple(node):
                return node
            name = f"_pyn_argument_{number}_{len(before)}"
            before.append(ast.Assign([ast.Name(name, ast.Store())], node))
            return ast.Name(name, ast.Load())

        callee = bound(callee)
        arguments = [bound(argument) for argument in arguments]
        keywords = [ast.keyword(kw.arg, bound(kw.value)) for kw in keywords]
        call = ast.Expr(ast.Call(callee, arguments, keywords))
        return [*before, ast.With([ast.withitem(context, target)], [call])]

    def typed_raises(self, function, receiver=None):
        """`with pytest.raises(E) as info:` blocks to expand so info.value keeps class E.

        In a unittest case (receiver names its `self`), `with self.assertRaises(E) as cm:`
        blocks likewise, for cm.exception.

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
            if not (isinstance(call, ast.Call) and isinstance(target, ast.Name)):
                continue
            pattern = None
            if (self.name(call.func) == "pytest.raises" and len(call.args) == 1
                    and all(kw.arg == "match" for kw in call.keywords) and len(call.keywords) <= 1):
                allowed = {"value", "type", "typename", "match"}
                if call.keywords:
                    pattern = call.keywords[0].value
            elif (receiver is not None and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == receiver and not call.keywords
                    and (call.func.attr, len(call.args)) in {("assertRaises", 1), ("assertRaisesRegex", 2)}):
                allowed = {"exception"}
                if len(call.args) == 2:
                    pattern = call.args[1]
            else:
                continue
            expected = call.args[0]
            original = expected
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
                        and parent.attr in allowed):
                    supported = False
                    break
                outer = parents.get(parent)
                if parent.attr == "match" and not (isinstance(outer, ast.Call) and outer.func is parent
                                                   and len(outer.args) == 1 and not outer.keywords):
                    supported = False
                    break
                if (parent.attr in ("value", "exception") and isinstance(outer, ast.Attribute)
                        and outer.value is parent and isinstance(outer.ctx, ast.Load)):
                    fields = True
            if supported and fields:
                names[name] = self.counter
                blocks[node] = (self.counter, original, pattern)
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

        unit_methods = self.unit_methods()
        hooks = {hook for info in self.infos.values() for hook in info.hooks.values()}
        hints = set(self.pytest_annotations())
        dropped = self.dropped
        unused_requests = self.unused_requests

        class Rewrite(ast.NodeTransformer):
            def __init__(self):
                self.scopes = []
                # Per enclosing function: expanded raises blocks and their info names.
                self.raises = []
                # Per enclosing function: the name of a unittest case's self, or None.
                self.receivers = []

            def receiver(self, node):
                """Whether an expression is the unittest case of the enclosing method."""
                return (isinstance(node, ast.Name) and bool(self.receivers) and self.receivers[-1] is not None
                        and node.id == self.receivers[-1])

            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id == "__file__":
                    return ast.copy_location(ast.Constant(generator.path), node)
                if isinstance(node.ctx, ast.Load) and node.id == "__name__":
                    return ast.copy_location(ast.Constant(generator.module), node)
                return node

            def caught(self, node):
                """The expansion number of `info` in info.value, or None."""
                if isinstance(node, ast.Name) and self.raises and self.scopes[-1] == "function":
                    return self.raises[-1][1].get(node.id)
                return None

            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name in ("pytest", "unittest"):
                        alias.asname = alias.asname or alias.name
                        alias.name = "pytest_native_support"
                return node

            def visit_ImportFrom(self, node):
                if node.module in ("pytest", "unittest") and not node.level:
                    node.names = [alias for alias in node.names if alias.name not in {
                        "fixture", "mark", "param", "skip", "skipIf", "skipUnless", "expectedFailure", "main"}
                        | (PYTEST_TYPES if node.module == "pytest" else set())
                        or node.module == "pytest" and alias.name == "skip"]
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
                for argument in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                    if argument.annotation in hints:
                        argument.annotation = None
                if node.returns in hints:
                    node.returns = None
                if node in unused_requests:
                    node.args.args = [argument for argument in node.args.args if argument.arg != "request"]
                    node.args.kwonlyargs = [argument for argument in node.args.kwonlyargs if argument.arg != "request"]
                if node in declarations:
                    node.decorator_list = []
                elif generator.helper:
                    # (A helper's fixtures and marks are not collected; only its code is kept.)
                    node.decorator_list = [decorator for decorator in node.decorator_list if not generator.name(
                        decorator.func if isinstance(decorator, ast.Call) else decorator)]
                if node in requests:
                    node = RequestParameter().visit(node)
                if node in hooks:
                    # (The runner calls these hooks itself, without the test method.)
                    node.args.args = node.args.args[:1]
                    if node.name == "setup_method":
                        node.name = "__init__"
                if node in unit_methods:
                    receiver = unit_methods[node]
                    if node.name == "setUp":
                        # Fields a case assigns in setUp are declared as __init__ declares
                        # them: the runner makes each test's object where unittest calls setUp.
                        node.name = "__init__"
                else:
                    # (A nested function sees the method's self unless it binds the name.)
                    receiver = self.receivers[-1] if self.receivers else None
                    if receiver in {arg.arg for arg in ast.walk(node.args) if isinstance(arg, ast.arg)}:
                        receiver = None
                self.receivers.append(receiver)
                self.raises.append(generator.typed_raises(node, receiver if node in unit_methods else None))
                try:
                    return self.scoped(node, "function")
                finally:
                    self.raises.pop()
                    self.receivers.pop()

            def visit_AsyncFunctionDef(self, node):
                return self.scoped(node, "other")

            def visit_Lambda(self, node):
                return self.scoped(node, "other")

            def visit_ClassDef(self, node):
                if node in classes:
                    node.decorator_list = []
                    node.body = [statement for statement in node.body if statement not in dropped] or [ast.Pass()]
                elif generator.helper:
                    node.decorator_list = [decorator for decorator in node.decorator_list if not generator.name(
                        decorator.func if isinstance(decorator, ast.Call) else decorator)]
                self.receivers.append(None)
                try:
                    return self.scoped(node, "other")
                finally:
                    self.receivers.pop()

            def visit_Expr(self, node):
                call = node.value
                if isinstance(call, ast.Call):
                    block = self.callable_raises(call, None)
                    if block is not None:
                        return block
                if call in generator.patches:
                    text, replacement = generator.patch_function(call)
                    generator.patch_functions.append(text)
                    return self.generic_visit(ast.copy_location(replacement, node))
                return self.generic_visit(node)

            def visit_Assign(self, node):
                if isinstance(node.value, ast.Call) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    block = self.callable_raises(node.value, node.targets[0])
                    if block is not None:
                        return block
                return self.generic_visit(node)

            def callable_raises(self, call, target):
                """The with block of raises(E, function, ...) or self.assertRaises(E, function, ...)."""
                fixed = 0
                if generator.name(call.func) == "pytest.raises" and len(call.args) > 1:
                    fixed = 1
                elif (target is None and isinstance(call.func, ast.Attribute) and self.receiver(call.func.value)
                        and call.func.attr in ("assertRaises", "assertRaisesRegex")):
                    fixed = 1 if call.func.attr == "assertRaises" else 2
                if not fixed or len(call.args) <= fixed:
                    return None
                context = ast.Call(call.func, call.args[:fixed], [])
                block = generator.raises_block(context, call.args[fixed], call.args[fixed + 1:], call.keywords,
                                               target, generator.counter)
                generator.counter += 1
                result = []
                for statement in block:
                    visited = self.visit(ast.fix_missing_locations(ast.copy_location(statement, call)))
                    result += visited if isinstance(visited, list) else [visited]
                return result

            def warning_context(self, node):
                """(classes, pattern) of `with pytest.warns(...)` or `with self.assertWarns(...)`, or None."""
                if len(node.items) != 1 or not isinstance(node.items[0].context_expr, ast.Call):
                    return None
                call = node.items[0].context_expr
                name = generator.name(call.func)
                if name in WARNS:
                    classes = call.args[0] if call.args else None
                    pattern = call.keywords[0].value if call.keywords else None
                    if name == "pytest.deprecated_call":
                        classes = ast.Tuple([ast.Name(kind, ast.Load()) for kind in (
                            "DeprecationWarning", "PendingDeprecationWarning", "FutureWarning")], ast.Load())
                elif (isinstance(call.func, ast.Attribute) and self.receiver(call.func.value)
                        and call.func.attr in UNIT_WARNS):
                    classes = call.args[0]
                    pattern = call.args[1] if len(call.args) > 1 else None
                else:
                    return None
                if classes is None:
                    classes = ast.Name("Warning", ast.Load())
                return (classes.elts if isinstance(classes, ast.Tuple) else [classes]), pattern

            def visit_With(self, node):
                expected = self.warning_context(node)
                if expected is not None:
                    # The block runs with every warning recorded; then one of the expected
                    # classes (and pattern) must be among them, also where the block raised an
                    # Exception, as pytest checks. The `as` name is the list of warnings.
                    classes, pattern = expected
                    target = node.items[0].optional_vars
                    caught = f"_pyn_caught_{generator.counter}"
                    log = target.id if target is not None else f"_pyn_warnings_{generator.counter}"
                    generator.counter += 1
                    module = ast.Name("_pyn_warnings", ast.Load())

                    def check():
                        return ast.Expr(ast.Call(_attribute("check_warnings"), [
                            ast.Name(log, ast.Load()), ast.List(classes, ast.Load()),
                            pattern if pattern is not None else ast.Constant(None)], []))

                    body = [ast.Assign([ast.Name(log, ast.Store())], ast.Call(
                                _attribute("recorded"), [ast.Name(caught, ast.Load())], [])),
                            ast.Expr(ast.Call(ast.Attribute(module, "simplefilter", ast.Load()),
                                              [ast.Constant("always")], [])),
                            ast.Try(node.body, [ast.ExceptHandler(ast.Name("Exception", ast.Load()), None,
                                                                  [check(), ast.Raise()])], [], [])]
                    block = ast.With([ast.withitem(ast.Call(ast.Attribute(module, "catch_warnings", ast.Load()), [],
                                                            [ast.keyword("record", ast.Constant(True))]),
                                                   ast.Name(caught, ast.Store()))], body)
                    return [self.generic_visit(ast.fix_missing_locations(ast.copy_location(block, node))),
                            self.generic_visit(ast.fix_missing_locations(ast.copy_location(check(), node)))]
                expansion = self.raises[-1][0].get(node) if self.raises and self.scopes[-1] == "function" else None
                labels = []
                entered = node.items[0].context_expr
                if (len(node.items) == 1 and isinstance(entered, ast.Call) and isinstance(entered.func, ast.Attribute)
                        and entered.func.attr == "subTest" and self.receiver(entered.func.value)):
                    # subTest's message and parameters only label its report, and the native
                    # context takes none (visit_Call). What may run code, such as a property,
                    # is still evaluated where the block is entered, in order.
                    labels = [ast.Expr(value) for value in [*entered.args, *[kw.value for kw in entered.keywords]]
                              if not isinstance(value, ast.Starred) and not generator.plain_read(value)]
                node = self.generic_visit(node)
                if labels:
                    visited = [self.visit(ast.fix_missing_locations(ast.copy_location(label, node))) for label in labels]
                    return [*visited, node]
                if expansion is None:
                    return node
                number, expected, matched = expansion
                value = ast.Name(f"_pyn_value_{number}", ast.Store())
                error = f"_pyn_caught_{number}"
                pattern = f"_pyn_match_{number}"
                # pytest.raises(E, match=...) reads E and checks the pattern before the body.
                before = [ast.Expr(expected)]
                handler = [ast.Assign([value], ast.Name(error, ast.Load()))]
                if matched is not None:
                    before += [ast.Assign([ast.Name(pattern, ast.Store())], matched),
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
                    if node.attr in ("value", "exception"):
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
                function = node.func
                if isinstance(function, ast.Attribute) and self.receiver(function.value):
                    if function.attr == "subTest":
                        # (Its message and parameters only label a subtest's report.)
                        node.args, node.keywords = [], []
                    elif function.attr in ("assertIsInstance", "assertNotIsInstance") and len(node.args) >= 2:
                        function.attr = "assertTrue" if function.attr == "assertIsInstance" else "assertFalse"
                        node.args = [ast.Call(ast.Name("isinstance", ast.Load()), node.args[:2], []), *node.args[2:]]
                    elif (function.attr in ("assertRaises", "assertRaisesRegex") and node.args
                            and isinstance(node.args[0], ast.Tuple)):
                        function.attr += "Any"
                        node.args[0] = ast.List(node.args[0].elts, ast.Load())
                    elif function.attr in ("assertRaises", "assertRaisesRegex"):
                        node.keywords = []
                elif (isinstance(function, ast.Attribute) and function.attr == "setUp" and self.receivers
                        and self.receivers[-1] is not None and isinstance(function.value, ast.Call)
                        and isinstance(function.value.func, ast.Name) and function.value.func.id == "super"):
                    function.attr = "__init__"
                elif (isinstance(function, ast.Attribute) and function.attr in XUNIT_METHOD and hooks
                        and isinstance(function.value, ast.Call) and isinstance(function.value.func, ast.Name)
                        and function.value.func.id == "super"):
                    # super().setup_method(method), in a class whose hooks the runner calls.
                    node.args, node.keywords = [], []
                    if function.attr == "setup_method":
                        function.attr = "__init__"
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
        if not self.helper:
            self.validate_body()
        imports = ["import pytest_native_support as _pyn_support"]
        imports += [f"import {module} as {alias}" for module, alias in self.imports]
        if self.builtins_used:
            imports.append("import pytest_native_fixtures as _pyn_fixtures")
        imports += [f"import {SUPPORT_MODULES[alias]} as {alias}" for alias in sorted(self.support_used)]
        if any(plan[0] == "chdir" for plan in self.patches.values()):
            imports.append("import os as _pyn_os")
        output = []
        # Each entry: (text, the statement it came from or None).
        placed = False
        if self.warning_marks or any(
                self.name(node) in WARNS or isinstance(node, ast.Attribute) and node.attr in UNIT_WARNS
                for node in ast.walk(self.tree)):
            imports.append("import warnings as _pyn_warnings")
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
            if node in self.dropped:
                continue
            rewritten = Rewrite().visit(node)
            for statement in rewritten if isinstance(rewritten, list) else [rewritten]:
                if statement is not None:
                    output.append((ast.unparse(ast.fix_missing_locations(statement)), statement))
        if not placed:
            output += [(line, None) for line in imports]
        # Named parameter tables are read here, after everything the module does at import.
        output += [(line, None) for line in self.late]
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
        if test.owner is not None and not test.unit and INSTANCE not in order:
            lines.append(f"    _pyn_instance = {test.owner.name}()")
        indent = 1
        generators = []
        values = dict(values)
        made = INSTANCE not in order
        for index, name in enumerate(order):
            fixture = fixtures[name]
            if name == INSTANCE:
                # setup_method (the class's __init__ here) runs at this point of the setup.
                p = "    " * indent
                lines.append(p + f"_pyn_instance = {test.owner.name}()")
                if fixture.generator:
                    lines.append(p + "try:")
                    generators.append((indent, None, name))
                    indent += 1
                made = True
                continue
            if not made and fixture.call.startswith("_pyn_instance."):
                self.error(test.function, f"fixture {name} of the test class is set up before the class's "
                           "setup_method, by a fixture outside the class")
            arguments = [f"{dependency}={values[dependency]}" for dependency in fixture.dependencies]
            if fixture.named:
                arguments.insert(0, repr(label))
            if fixture.request:
                arguments.append(f"_pyn_request_param={fixture_values[name]}")
            if fixture.origin == "builtin":
                alias = fixture.call.split(".")[0]
                if alias in SUPPORT_MODULES:
                    self.support_used.add(alias)
                else:
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
        lines.append(p + "_pyn_report.record(_pyn_id, 'setup', 'passed', '')")
        if test.unit:
            lines += self.unit_call(test, callee, p)
        else:
            lines += [p + "try:",
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
            lines += [p + "finally:", p + "    try:"]
            if generator is None:
                lines.append(p + "        _pyn_instance.teardown_method()")
            else:
                lines += [p + "        try:",
                          p + f"            next({generator})", p + "        except StopIteration:",
                          p + "            pass", p + "        else:", p + "            try:",
                          p + f"                {generator}.close()", p + "            finally:",
                          p + f"                raise RuntimeError({('fixture ' + name + ' yielded more than once')!r})"]
            lines += [p + "    except _pyn_support.Skipped as _pyn_error:",
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

    def unit_call(self, test, callee, p):
        """A unittest case's call phase, as TestCase.run orders it.

        A decorated skip comes first. Otherwise the object is made, which runs setUp (see
        Rewrite.visit_FunctionDef); then the test and tearDown run, each even if the
        other fails, and only if setUp finished. pytest reports the first of their
        failures as the call's and a second as the teardown's (UnitRun.finish).
        """
        marks = test.marks
        expecting = any(mark.kind == "unit-xfail" for mark in marks)
        skips = [mark for mark in marks if mark.kind == "unit-skip"]

        def guarded(statement, q, expected=False):
            return [q + "try:", q + "    " + statement,
                    q + "except KeyboardInterrupt:", q + "    raise",
                    q + "except BaseException as _pyn_error:",
                    q + f"    _pyn_unit.raised(_pyn_error{', True' if expected else ''})"]

        # (unittest expects a failure of the test method alone, a subtest's included.)
        call = guarded(f"{callee}()", "    ", expecting)
        if expecting:
            call = ["    _pyn_unit.expecting(True)", *call, "    _pyn_unit.expecting(False)"]
        body = [*guarded(f"_pyn_instance = {test.owner.name}()", ""), "else:",
                *call, *guarded("_pyn_instance.tearDown()", "    ")]
        always = next((mark for mark in skips if mark.condition is True), None)
        if always is not None:
            body = [f"_pyn_unit.skip({always.reason!r})"]
        elif skips:
            chain = []
            for index, mark in enumerate(skips):
                chain += [f"{'elif' if index else 'if'} {mark.condition}:", f"    _pyn_unit.skip({mark.reason!r})"]
            body = [*chain, "else:", *("    " + line for line in body)]
        return [p + "_pyn_unit = _pyn_support.UnitRun()", *(p + line for line in body),
                p + f"_pyn_unit.finish(_pyn_report, _pyn_id, {expecting}, _pyn_teardown)"]

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
        # A skipped last case still ends its scopes, in its own teardown.
        body.append("_pyn_teardown.scopes(_pyn_ends)")
        filters = [entry for mark in marks if mark.kind == "filterwarnings" for entry in mark.filters]
        if filters:
            # pytest applies a test's filterwarnings marks around each of its phases, nearest
            # mark first, so that a later one (its class's, its module's) takes precedence.
            body = ["with _pyn_warnings.catch_warnings():",
                    *(f"    _pyn_warnings.filterwarnings({action!r}, {message!r}, {category})"
                      for action, message, category in filters),
                    *("    " + line for line in body)]
        lines += ["    " + line for line in body]
        if xfail and xfail.raises and not skip:
            lines += ["    for _pyn_error in _pyn_teardown.scope_errors:",
                      f"        if isinstance(_pyn_error, {xfail.raises}):",
                      "            _pyn_teardown.matched += 1"]
        lines.append("    _pyn_teardown.record(_pyn_report, _pyn_id)")
        return "\n".join(lines)

    def chosen(self, names, labels):
        """Whether -k and -m keep a case with those lower-case names and those marks."""
        return (self.keyword(lambda name: any(name.lower() in word for word in names))
                and self.markexpr(lambda name: name in labels))

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
        words = []
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
                labels = {mark.reason if mark.kind == "label" else mark.kind
                          for mark in test.marks + marks if mark.kind in MARK_NAMES}
                # What -k matches: the test's name, those of its class, module and
                # directories, and its marks; -m matches the marks.
                words.append(({name.lower() for name in [*self.filename.split("/"), *parts[:-1],
                                                         function.name + (parametrization or ""), *labels]}, labels))
        # Node IDs select cases; every case's declarations still run at import.
        run = list(range(len(cases))) if self.selected is None else self.select(keys)
        run = [index for index in run if self.chosen(*words[index])]
        chunks = self.transform_source()
        # Pragmas are comments and therefore absent from the AST. Preserve their
        # original opt-ins; the runner never opts the input into Any itself.
        pragmas = "\n".join(token.string for token in tokenize.generate_tokens(io.StringIO(self.source).readline)
                            if token.type == tokenize.COMMENT and re.match(r"#\s*pystachy:", token.string))
        chunks += [(text, None) for text in self.patch_functions]
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
        parts = [pragmas + "\n"]
        first = parts[0].count("\n") + 1
        lines = {}
        for text, origin in chunks:
            # Generated code for a declaration reports at that declaration; the
            # runner's own code (0) at no test line.
            lines[first] = getattr(origin, "lineno", 0)
            if lines[first]:
                try:
                    _pair_lines(origin, ast.parse(text).body[0], first - 1, lines)
                except (SyntaxError, IndexError):
                    pass
            parts.append(text + "\n\n")
            first += text.count("\n") + 2
        return GeneratedModule("".join(parts).rstrip("\n") + "\n", [cases[index] for index in run],
                               self.builtins_used, [SUPPORT_MODULES[alias] for alias in sorted(self.support_used)],
                               lines, self.hooks)

    def adapt(self):
        """This helper module's source for the generated program (adapt_helper)."""
        self.class_nodes = {node.name: node for node in self.tree.body if isinstance(node, ast.ClassDef)}
        self.infos = {}
        self.scan_imports()
        for node in self.class_nodes.values():
            try:
                if self.unittest_bases(node):
                    self.class_info(node)
            except CollectionError:
                pass  # (left as written: the compiler reports what it cannot build)
        chunks = self.transform_source()
        pragmas = [token.string for token in tokenize.generate_tokens(io.StringIO(self.source).readline)
                   if token.type == tokenize.COMMENT and re.match(r"#\s*pystachy:", token.string)]
        return "\n".join([*pragmas, *(text for text, _ in chunks)]) + "\n"

    def export(self):
        """This conftest.py's fixtures as a test module of its directory calls them."""
        fixtures = {}
        for name, fixture in self.fixtures.items():
            params = fixture.params
            if params is not None:
                params = Parameter(params.names, [[self.alias + "." + value for value in row]
                                                  for row in params.values], params.ids, params.marks)
            fixtures[name] = dataclasses.replace(fixture, call=self.alias + "." + fixture.call, params=params,
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
             session_end: bool = True, path: str = "", module: str = "", imports=None,
             package: bool = False, resolve=None, strict: bool = False,
             verified: bool = False, keyword: str = "", markexpr: str = "", unavailable=None) -> GeneratedModule:
    """Collect and adapt one module, or reject unsupported collection explicitly.

    operands keeps comparison operands for assertion failures (Generator.captured);
    selected lists node-ID selectors (`name`, `name[id]`, `Class` or `Class::name`) to
    run, in order; shared holds the fixtures of the conftest.py files above the module
    (generate_conftest), one group per file from the outermost, and imports the
    (module, alias) each is imported as; session_end is false for every module but the
    last that runs; path and module are what the test module reads as __file__ and
    __name__; package says its directory is one, where relative imports resolve;
    resolve finds the module of an imported base class (Generator.__init__); strict is
    pytest's xfail_strict setting; verified says the run is compared with pytest's, which
    a conftest.py needs for the hooks the program leaves out (VERIFIED_HOOKS); keyword
    and markexpr are pytest's -k and -m expressions, which keep the cases they match.
    """
    return Generator(source, filename, operands, selected, shared, False, session_end, path, module, imports,
                     package, resolve=resolve, strict=strict, verified=verified, keyword=keyword,
                     markexpr=markexpr, unavailable=unavailable).generate()


def generate_conftest(source: str, filename: str, operands: bool = True, path: str = "", module: str = "",
                      shared=None, imports=None, package: bool = False, alias: str = "_pyn_conftest",
                      resolve=None, strict: bool = False, verified: bool = False, unavailable=None):
    """Adapt a conftest.py: its generated module, and its fixtures for generate(shared=).

    shared and imports name the conftest.py files above it, whose fixtures its own may
    request; other modules call its fixtures through alias.
    """
    generator = Generator(source, filename, operands, None, shared, True, True, path, module, imports, package,
                          alias, resolve=resolve, strict=strict, verified=verified, unavailable=unavailable)
    module = generator.generate()
    return module, generator.export()


def adapt_helper(source: str, filename: str, path: str = "", module: str = "", resolve=None) -> str:
    """A module beside the tests as the generated program imports it.

    Nothing is collected from it. Its pytest and unittest imports name the runner's
    replacement, its unittest cases are adapted as a test module's are, and __file__
    is its original path. A module that needs none of this is returned unchanged.
    """
    if not re.search(r"\b(pytest|unittest|__file__)\b", source):
        return source
    return Generator(source, filename, False, path=path, module=module, package=True, helper=True,
                     resolve=resolve).adapt()
