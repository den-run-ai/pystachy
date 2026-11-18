"""Report several rejections of one program: compile a copy, stub the function that failed, repeat.

A compilation stops at its first rejection, so porting a module costs one compilation per
restriction it meets. This CPython-hosted tool is not error recovery in the compiler, where a
failed stage cannot be resumed. It copies PROGRAM and the modules that it imports from its own
directory and from --path into a scratch tree, compiles the copy (COMPILER ir), records the
diagnostic, replaces the body of the innermost function that holds the diagnostic's line with a
stub, and compiles again. A stub keeps the signature, the decorators and the number of every
other line. The sources are never changed and nothing is run. docs/porting.md has an example.

The survey ends when the copy compiles, at --max rejections, or at a rejection that no stub
removes: a statement outside any function, a file outside the copy (the compiler's own lib/), a
file that CPython's ast cannot parse, or a location or stubbed function that is rejected again.

Limits of the report:
- Only code that the entry program reaches is compiled, so a module that nothing imports and a
  function that nothing calls are not surveyed, unless that function's parameters and result are
  all annotated.
- A function reports at most one rejection: its stub hides the rest of its body.
- A stub changes the program. A function that only raises has no result type of its own, and a
  stubbed method no longer assigns its fields, so a later rejection may come of an earlier stub.
  A rejection is marked as one that may follow from a stub when its function uses the name of the
  stubbed function or a field that the stubbed method assigned, or when the statement at a call
  site of its diagnostic does (outside any function, the statement at its own line), directly or
  through a variable assigned from such a use. The mark goes by names only: it can be missing
  where a stub's effect passes through other code, and present without cause.

Exit status, as tools/inspect_compiler.py's: 0 the program compiles with no rejection, 1 rejections
were found, 2 a usage error or a compiler failure without a diagnostic, 124 a compilation exceeded
--timeout.
"""
import argparse
import ast
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tokenize
import warnings

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
# A rejection is exit status 1 with one line on stderr (rejection() in tests/run.sh).
DIAGNOSTIC = re.compile(r"(?P<file>.+?):(?P<line>[0-9]+): error: (?P<message>.*)")
# The compiler appends the specializations it was compiling, innermost first, as
# "MESSAGE (NOTE; NOTE)": see gen_err in src/pystachy_compiler/emission.py and Gen.making.
NOTE = r"(?:compiling|specializing|making a) "
NOTES = re.compile(rf" \((?={NOTE}).*\)$")
CALL_SITE = re.compile(r" at (?P<file>.+?):(?P<line>[0-9]+)(?=$|, where )")
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
Function = ast.FunctionDef | ast.AsyncFunctionDef
# what reading and parsing a file can raise (MemoryError: source nested too deeply for CPython's parser)
UNPARSED = (OSError, SyntaxError, ValueError, RecursionError, MemoryError)
STUB = 'raise NotImplementedError("rejection survey stub")'
# A method of these names must return this type even without a return annotation (specs.SPECIAL),
# which a body that only raises does not: its stub returns a value of the type instead.
RESULTS = {"__str__": '""', "__repr__": '""', "__format__": '""', "__len__": "0", "__hash__": "0",
           **{name: "False" for name in ("__bool__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__")}}
LIMITS = ("Only code that the entry program reaches is compiled: a module that nothing imports is not "
          "surveyed, nor is a function that nothing calls unless its parameters and result are all "
          "annotated. A function reports at most one rejection, because its stub hides the rest of its body.")


class Unparsable(Exception):
    pass


def parse(source: str | bytes) -> ast.Module:
    """SOURCE's syntax tree. CPython's warnings about it, such as an invalid escape in a pattern
    string, are not printed: the survey reports the compiler's diagnostics."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(source)


def parse_diagnostic(text: str) -> dict | None:
    """The file, line, message and notes (outermost first) of a diagnostic line, or None."""
    match = DIAGNOSTIC.fullmatch(text)
    if match is None:
        return None
    message, context = match["message"], []
    notes = NOTES.search(message)
    if notes is not None:
        context = re.split(rf"; (?={NOTE})", notes.group()[2:-1])[::-1]
        message = message[:notes.start()]
    return {"file": match["file"], "line": int(match["line"]), "message": message, "context": context}


def call_sites(context: list[str]) -> list[tuple[str, int]]:
    """The FILE:LINE that each note names, in the notes' order."""
    found = [CALL_SITE.search(note) for note in context]
    return [(match["file"], int(match["line"])) for match in found if match is not None]


def imported(tree: ast.AST, package: str) -> set[str]:
    """The dotted names that the import statements of a module of PACKAGE may load as modules."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            parents = package.split(".") if package else []
            parts = parents[:max(0, len(parents) - node.level + 1)] if node.level else []
            base = ".".join(parts + ([node.module] if node.module else []))
            names.update(f"{base}.{alias.name}" if base else alias.name for alias in node.names if alias.name != "*")
            if base:
                names.add(base)
    return names


def program_files(program: str, roots: list[str]) -> list[tuple[int, str]]:
    """The files to copy, each as its root's index and its path below that root: the entry, then
    every module of the roots that an import statement of these files names, found as the
    compiler's loader finds modules (Loader.filepath). A file ast cannot parse adds none."""
    located: dict[str, tuple[str, list[tuple[int, str]]]] = {}

    def locate(name):
        # ("package" or "module", [its file]), ("namespace", its directories) or ("", [])
        if name not in located:
            parent, _, base = name.rpartition(".")
            places = [(k, "") for k in range(len(roots))]
            if parent:
                kind, held = locate(parent)
                places = [(k, os.path.dirname(file)) for k, file in held] if kind == "package" else held if kind == "namespace" else []
            files = [(kind, (k, file)) for k, below in places
                     for kind, file in (("package", os.path.join(below, base, "__init__.py")), ("module", os.path.join(below, base + ".py")))
                     if os.path.isfile(os.path.join(roots[k], file))]
            portions = [(k, os.path.join(below, base)) for k, below in places if os.path.isdir(os.path.join(roots[k], below, base))]
            located[name] = (files[0][0], [files[0][1]]) if files else ("namespace" if portions else "", portions)
        return located[name]

    files = [(0, os.path.basename(program))]
    packages = {files[0]: ""}  # each file's package, which its relative imports start from
    done = 0
    while done < len(files):
        root, below = files[done]
        done += 1
        try:
            tree = parse(Path(roots[root], below).read_bytes())
        except UNPARSED:
            continue
        for name in sorted(imported(tree, packages[root, below])):
            parts = name.split(".")
            for n in range(1, len(parts) + 1):
                kind, held = locate(".".join(parts[:n]))
                if kind in ("package", "module") and held[0] not in packages:
                    packages[held[0]] = ".".join(parts[:n if kind == "package" else n - 1])
                    files.append(held[0])
    return files


def nested_scopes(node: ast.AST):
    """The def and class statements directly inside NODE's own scope."""
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(child, (*FUNCTIONS, ast.ClassDef)):
            yield child
        else:
            pending.extend(ast.iter_child_nodes(child))


def scope_chain(tree: ast.AST, line: int) -> list:
    """The def and class statements that hold LINE, outermost first. Each runs from its def or
    class line, so a decorator belongs to the scope around it."""
    chain = []
    node = tree
    while node is not None:
        node = next((scope for scope in nested_scopes(node) if scope.lineno <= line <= scope.end_lineno), None)
        if node is not None:
            chain.append(node)
    return chain


def qualified(chain: list) -> str:
    """The qualified name, as __qualname__ spells it, of the last definition of CHAIN."""
    parts = []
    for k, node in enumerate(chain):
        if k > 0 and not isinstance(chain[k - 1], ast.ClassDef):
            parts.append("<locals>")
        parts.append(node.name)
    return ".".join(parts)


def first_line(node: ast.AST) -> int:
    return min([node.lineno] + [decorator.lineno for decorator in getattr(node, "decorator_list", [])])


def statement_at(tree: ast.AST, line: int):
    """The innermost statement whose lines, decorators included, hold LINE, or None."""
    found = None
    for node in ast.walk(tree):  # (breadth first: a statement comes after those that hold it)
        if isinstance(node, ast.stmt) and first_line(node) <= line <= node.end_lineno:
            found = node
    return found


def names_used(node: ast.AST, stored: bool = False) -> set[str]:
    """The variable and attribute names in NODE: all of them, or (STORED) those it assigns."""
    used = set()
    for part in ast.walk(node):
        if isinstance(part, (ast.Name, ast.Attribute)) and (not stored or isinstance(part.ctx, ast.Store)):
            used.add(part.id if isinstance(part, ast.Name) else part.attr)
    return used


def own_names(statement: ast.AST) -> set[str]:
    """The names STATEMENT uses outside the statements it holds: of an if, a for or a def, its header's."""
    used = set()
    for _, value in ast.iter_fields(statement):
        for part in value if isinstance(value, list) else [value]:
            if isinstance(part, ast.AST) and not isinstance(part, (ast.stmt, ast.excepthandler, ast.match_case)):
                used |= names_used(part)
    return used


def reaching(scope: ast.AST, names: set[str]) -> set[str]:
    """NAMES and, in turn, what SCOPE assigns from an expression that uses one of them."""
    names = set(names)
    grown = True
    while grown:
        grown = False
        for node in ast.walk(scope):
            value, targets = None, []
            if isinstance(node, ast.Assign):
                value, targets = node.value, node.targets
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                value, targets = node.value, [node.target]
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                value, targets = node.iter, [node.target]
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                value, targets = node.context_expr, [node.optional_vars]
            if value is not None and names_used(value) & names:
                assigned = set().union(*(names_used(target, True) for target in targets)) - names
                names |= assigned
                grown = grown or bool(assigned)
    return names


def is_generator(function: Function) -> bool:
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        if not isinstance(node, (*FUNCTIONS, ast.ClassDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))
    return False


def stub_statement(chain: list) -> str:
    """The body that replaces that of the function CHAIN ends with."""
    function = chain[-1]
    if is_generator(function):
        return STUB + "; yield"  # (still a generator, for the loops over its calls)
    method = len(chain) > 1 and isinstance(chain[-2], ast.ClassDef)
    if method and function.name in RESULTS and function.returns is None:
        return "return " + RESULTS[function.name]
    return STUB


def stub_names(chain: list) -> set[str]:
    """What other code may miss once the function CHAIN ends with is a stub: its name (its result
    type) and, for a method, the fields it assigned through its first parameter."""
    function = chain[-1]
    names = {function.name}
    parameters = function.args.posonlyargs + function.args.args
    if len(chain) > 1 and isinstance(chain[-2], ast.ClassDef) and parameters:
        for node in ast.walk(function):
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store) and \
                    isinstance(node.value, ast.Name) and node.value.id == parameters[0].arg:
                names.add(node.attr)
    return names


def stubbed(text: str, function: Function, statement: str) -> str:
    """TEXT with FUNCTION's body replaced by STATEMENT and blank lines: no line changes its number."""
    lines = io.StringIO(text, newline="").readlines()  # (ends lines where Python does, not at a form feed)
    first = function.body[0]
    start = first_line(first)
    line = lines[start - 1]
    head = line[:len(line) - len(line.lstrip(" \t\f"))]
    if start == first.lineno:
        before = line.encode("utf-8")[:first.col_offset].decode("utf-8")
        if before.strip():
            head = before  # the body begins on a line of the header: def f(x): return x
    lines[start - 1] = head + statement + line[len(line.rstrip("\r\n")):]
    for k in range(start, function.end_lineno):
        lines[k] = lines[k][len(lines[k].rstrip("\r\n")):]
    return "".join(lines)


def compile_once(command: list[str], entry: str, env: dict, timeout: float) -> tuple[str, str]:
    """One compilation to IR: ("compiled", ""), ("rejected", the diagnostic line), ("timeout", why)
    or ("failed", why) for any other result, which is no rejection."""
    try:
        run = subprocess.run([*command, "ir", entry, "-o", os.devnull], env=env, stdin=subprocess.DEVNULL,
                             capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", f"The survey ended: a compilation exceeded {timeout:g} seconds."
    except OSError as error:
        return "failed", f"The survey ended: the compiler did not run ({error})."
    if run.returncode == 0:
        return "compiled", ""
    lines = run.stderr.splitlines()
    if run.returncode == 1 and len(lines) == 1 and DIAGNOSTIC.fullmatch(lines[0]):
        return "rejected", lines[0]
    return "failed", (f"The survey ended: the compiler failed without a diagnostic (exit {run.returncode}): "
                      + " | ".join(lines[-5:]))


class Survey:
    def __init__(self, scratch: str, program: str, path: list[str]):
        self.program = program
        # the directories that the compiler searches before its own lib/ (driver.py), and the copy
        # of each: only the copies are ever written
        self.roots = [os.path.dirname(program), *path]
        self.copies = [os.path.join(scratch, "program")] + [os.path.join(scratch, f"path{k}") for k in range(1, len(self.roots))]
        self.entry = os.path.join(self.copies[0], os.path.basename(program))
        self.sources: dict[str, tuple[str, str, ast.AST]] = {}
        for copy in self.copies:
            os.makedirs(copy)
        for k, below in program_files(program, self.roots):
            target = os.path.join(self.copies[k], below)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(self.roots[k], below), target)

    def environment(self) -> dict:
        # The copies come first. The directories themselves follow, in their order, for a module
        # that only the compiler's lib/ imports from them: the scan of imports does not see it.
        originals = [os.path.abspath(root or ".") for root in self.roots]
        return dict(os.environ, PYSTACHY_PATH=":".join(self.copies[1:] + originals))

    def owned(self, path: str) -> bool:
        # Resolved first: a path that climbs out of a copy ("..") or leaves it through a symbolic
        # link is not the copy's. Only files inside the copies are ever written.
        real = os.path.realpath(path)
        return any(real.startswith(os.path.realpath(copy) + os.sep) for copy in self.copies)

    def shown(self, text: str) -> str:
        """TEXT with each path of the copies as the path of the file it copies."""
        for copy, root in zip(self.copies, self.roots):
            text = text.replace(copy + os.sep, os.path.join(root, ""))
        return text

    def source(self, path: str) -> tuple[str, str, ast.AST]:
        """The text of file PATH, its encoding and its syntax tree."""
        if path not in self.sources:
            try:
                data = Path(path).read_bytes()
                encoding = tokenize.detect_encoding(io.BytesIO(data).readline)[0]
                text = data.decode(encoding)
                self.sources[path] = (text, encoding, parse(text))
            except UNPARSED as error:
                raise Unparsable(f"{type(error).__name__}: {error}") from error
        return self.sources[path]

    def uses(self, path: str, line: int, names: set[str], whole: bool) -> bool:
        """Does the code at line LINE of PATH use one of NAMES: the function that holds the line
        (WHOLE), else the statement at the line, for which a variable or field that the function
        or the module around it assigns from such a use counts too."""
        try:
            tree = self.source(path)[2]
        except Unparsable:
            return False
        functions = [node for node in scope_chain(tree, line) if isinstance(node, FUNCTIONS)]
        if whole and functions:
            return bool(names_used(functions[-1]) & names)
        statement = statement_at(tree, line)
        return statement is not None and bool(own_names(statement) & reaching(functions[-1] if functions else tree, names))

    def run(self, command: list[str], limit: int, timeout: float) -> dict:
        rejections: list[dict] = []
        stubs: dict[tuple[str, int], tuple[int, set[str]]] = {}  # (file, def line): rejection, names
        env = self.environment()
        compilations = 0
        while True:
            outcome, detail = compile_once(command, self.entry, env, timeout)
            compilations += 1
            if outcome == "compiled":
                count = len(rejections)
                detail = (f"With {count} function{'s' * (count != 1)} stubbed, the copy compiles." if count
                          else "The program compiles.")
            if outcome != "rejected":
                break
            found = parse_diagnostic(detail)
            path, line = found["file"], found["line"]
            where = f"{self.shown(path)}:{line}"
            chain, problem = [], ""
            try:
                chain = scope_chain(self.source(path)[2], line)
            except Unparsable as error:
                problem = str(error)
            functions = [k for k, node in enumerate(chain) if isinstance(node, FUNCTIONS)]
            if functions:
                chain = chain[:functions[-1] + 1]  # (a class inside a function: that function)
            key = (path, chain[-1].lineno) if functions else None
            again = next((r["index"] for r in rejections if (r["file"], r["line"]) == (self.shown(path), line)),
                         stubs[key][0] if key in stubs else 0)
            if again:
                outcome = "repeated"
                detail = (f"The survey ended at {where}, still rejected with {rejections[again - 1]['definition']} "
                          f"stubbed (rejection {again}): {self.shown(found['message'])}.")
                break
            sites = call_sites(found["context"])
            follows = [index for index, names in stubs.values()
                       if self.uses(path, line, names, True) or any(self.uses(file, at, names, False) for file, at in sites)]
            rejection = {
                "index": len(rejections) + 1, "file": self.shown(path), "line": line,
                "definition": qualified(chain) if functions else None,
                "scope": "function" if functions else "unknown" if problem else f"class {qualified(chain)}" if chain else "module",
                "message": self.shown(found["message"]),
                "context": [self.shown(note) for note in found["context"]],
                "call_sites": [{"file": self.shown(file), "line": at} for file, at in sites],
                "stubbed": False,
                "may_follow_from": sorted(follows),
            }
            rejections.append(rejection)
            if not self.owned(path):
                outcome = "outside"
                detail = (f"The survey ended at {where}: the file is outside the copied sources (the compiler's "
                          "own lib/, or a module that only it imports), where nothing is stubbed.")
            elif problem:
                outcome, detail = "unparsable", f"The survey ended at {where}: CPython's ast cannot parse the file ({problem})."
            elif not functions:
                place = f"in class {qualified(chain)}, outside any function," if chain else "at module level"
                outcome, detail = "no-function", f"The survey ended at {where}: a statement {place} cannot be stubbed."
            elif len(rejections) >= limit:
                outcome, detail = "bound", f"The survey ended at --max {limit} rejections; more may remain."
            else:
                text, encoding, _ = self.source(path)
                Path(path).write_bytes(stubbed(text, chain[-1], stub_statement(chain)).encode(encoding))
                del self.sources[path]
                stubs[key] = (rejection["index"], stub_names(chain))
                rejection["stubbed"] = True
                continue
            break
        status = {"timeout": "timeout", "failed": "error"}.get(outcome, "rejected" if rejections else "ok")
        return {"schema_version": SCHEMA_VERSION, "program": self.program, "path": self.roots[1:],
                "compiler": command, "status": status, "compilations": compilations,
                "rejections": rejections, "ended": {"reason": outcome, "detail": detail}, "limits": LIMITS}


def render(report: dict) -> str:
    lines = []
    rejections = report["rejections"]
    for rejection in rejections:
        notes = f" ({'; '.join(rejection['context'][::-1])})" if rejection["context"] else ""
        lines.append(f"{rejection['index']}. {rejection['file']}:{rejection['line']}: error: {rejection['message']}{notes}")
        place = {"function": f"in {rejection['definition']}", "module": "at module level",
                 "unknown": "in a file that CPython's ast cannot parse"}.get(
            rejection["scope"], f"in {rejection['scope']}, outside any function")
        earlier = [f"{rejections[index - 1]['definition']} (rejection {index})" for index in rejection["may_follow_from"]]
        lines.append(f"   {place}" + (f"; may follow from the stub of {', '.join(earlier)}" if earlier else ""))
    lines.append(f"{len(rejections)} rejection{'s' * (len(rejections) != 1)} in {report['compilations']} "
                 f"compilation{'s' * (report['compilations'] != 1)} of {report['program']}. {report['ended']['detail']}")
    lines.append(report["limits"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("program", metavar="PROGRAM", help="the entry file; it is compiled, never run")
    parser.add_argument("--compiler", metavar="CMD", default=shlex.join([sys.executable, str(ROOT / "pystachy.py")]),
                        help="shell-split command, no shell evaluation (default: this checkout's hosted compiler)")
    parser.add_argument("--path", metavar="DIRS", help="module directories separated by ':' (default: PYSTACHY_PATH)")
    parser.add_argument("--max", metavar="N", type=int, default=20, help="rejections to record before stopping (default: 20)")
    parser.add_argument("--timeout", metavar="S", type=float, default=120.0, help="seconds for each compilation (default: 120)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON instead of text")
    parser.add_argument("--keep", metavar="DIR", help="copy the scratch tree, with its stubs, to this new directory")
    args = parser.parse_args(argv)
    try:
        command = shlex.split(args.compiler)
    except ValueError as error:
        parser.error(f"--compiler: {error}")
    if not command:
        parser.error("--compiler must not be empty")
    if args.max < 1 or not 0 < args.timeout < float("inf"):
        parser.error("--max must be at least 1 and --timeout a finite positive number")
    if not os.path.isfile(args.program):
        parser.error(f"not a file: {args.program}")
    if args.keep is not None and os.path.lexists(args.keep):
        parser.error(f"--keep directory must not exist: {args.keep}")
    # (the compiler looks for modules beside the file that a symbolic link names: survey that file)
    program = os.path.realpath(args.program) if os.path.islink(args.program) else args.program
    path = os.environ.get("PYSTACHY_PATH", "") if args.path is None else args.path
    try:
        with tempfile.TemporaryDirectory(prefix="pystachy-survey-") as scratch:
            survey = Survey(os.path.realpath(scratch), program, [d for d in path.split(":") if d])
            report = survey.run(command, args.max, args.timeout)
            if args.keep is not None:
                shutil.copytree(scratch, args.keep)
    except OSError as error:
        print(f"rejection_survey: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return {"ok": 0, "rejected": 1, "timeout": 124}.get(report["status"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
