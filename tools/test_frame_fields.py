"""The code generator's function-scoped fields are listed alike in each place that keeps them (#767).

While the compiler builds one function it may compile another: a template's instance for a call, a
function compiled early for a global's type, a class's special methods. Gen.save() keeps the
interrupted function's state in a Frame, gen_enter gives the nested function a fresh one, and
Gen.restore() brings the first one's back. So each function-scoped field of Gen is written by hand in
four lists: Gen.__init__ (src/pystachy_compiler/gen.py) initializes it, Frame.__init__ (ir.py) holds
it, gen_save and gen_restore (emission.py) copy it out and back; and gen_enter (functions.py) assigns
it for each function. A field that gen_enter assigns and Frame leaves out carries the nested
function's state into the function it interrupts; one that Frame saves and gen_enter does not assign
starts the nested function with the interrupted one's.

The test reads the source of those five functions (it imports no compiler code) and fails, naming
the field and each list that lacks it, unless gen_save copies into its Frame (Frame(...)'s arguments,
then fr.X = self.X) exactly the fields Frame.__init__ assigns and gen_restore copies the same ones
back (self.X = fr.X); Gen.__init__ initializes each of them and each that gen_enter assigns;
gen_enter assigns each field Frame holds, except those NOT_RESET lists; and Frame holds each field
gen_enter assigns, except those NOT_SAVED lists. Each exception gives its reason. A statement of
another form in gen_save or gen_restore fails the test too: it reads only those copies.
PYSTACHY_SRC names another checkout to read (default: the one that holds this file).

Run with python3 -m unittest discover -s tools -p test_frame_fields.py.
"""
import ast
import os
import unittest

ROOT = os.environ.get("PYSTACHY_SRC") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = "src/pystachy_compiler/gen.py"
IR = "src/pystachy_compiler/ir.py"
EMISSION = "src/pystachy_compiler/emission.py"
FUNCTIONS = "src/pystachy_compiler/functions.py"
# the lists: (the name messages give it, its file, its class or "", its def)
LISTS = [("Gen.__init__", GEN, "Gen", "__init__"), ("Frame.__init__", IR, "Frame", "__init__"),
         ("gen_save", EMISSION, "", "gen_save"), ("gen_restore", EMISSION, "", "gen_restore"),
         ("gen_enter", FUNCTIONS, "", "gen_enter")]
SAVES = ["Frame.__init__", "gen_save", "gen_restore"]

# the fields gen_enter assigns that Frame does not save, by design: what compiling a nested function
# leaves in them stays for the function it interrupts. Each with its reason, in one line.
NOT_SAVED: dict = {}
# the fields Frame holds that gen_enter does not assign, by design: the code that starts a nested
# function sets them. Each with its reason, in one line.
NOT_RESET = {
    "modlevel": "each caller of save() sets it for what it compiles, module code or a function; gen_enter reads it",
    "lenient": "set around helpers compiled leniently (obj_helpers, dyn_xhelper); save()'s callers that compile clear it",
}

FOOTER = (f"A function-scoped field of Gen is listed in four places, which must agree: Gen.__init__ ({GEN}), "
          f"Frame.__init__ ({IR}), gen_save and gen_restore ({EMISSION}); and gen_enter ({FUNCTIONS}) assigns "
          "it for each function. Leaving it out of one lets state leak between a function and one compiled in the "
          "middle of it (#767). NOT_SAVED and NOT_RESET in tools/test_frame_fields.py list the exceptions, each "
          "with its reason.")


def find(tree: ast.Module, cls: str, name: str):
    """the def of function name at the top level of tree, or of method name of its class cls; None if none"""
    body = tree.body
    if cls != "":
        body = next((n.body for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls), [])
    return next((n for n in body if isinstance(n, ast.FunctionDef) and n.name == name), None)


def statements(d: ast.FunctionDef) -> list:
    """the statements of def d, after its docstring"""
    first = d.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return d.body[1:]
    return d.body


def targets(st: ast.AST) -> list:
    """what st assigns, if it is an assignment (an annotated one with a value), also what it unpacks to"""
    if isinstance(st, ast.Assign):
        todo = list(st.targets)
    elif isinstance(st, ast.AnnAssign) and st.value is not None:
        todo = [st.target]
    else:
        return []
    out = []
    while todo:
        t = todo.pop()
        if isinstance(t, (ast.Tuple, ast.List)):
            todo.extend(t.elts)
        elif isinstance(t, ast.Starred):
            todo.append(t.value)
        else:
            out.append(t)
    return out


def attr(e: ast.AST, obj: str) -> str:
    """X if e is obj.X, else the empty string"""
    if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == obj:
        return e.attr
    return ""


def stores(d: ast.FunctionDef) -> list:
    """[(X, the statement)]: each assignment self.X = ... in def d (self: its first parameter), in the
    order of the source, outside the functions, lambdas and classes it defines"""
    me = d.args.args[0].arg
    out = []
    todo = list(d.body)
    while todo:
        n = todo.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        for t in targets(n):
            if attr(t, me) != "":
                out.append((attr(t, me), n))
        todo.extend(ast.iter_child_nodes(n))
    return sorted(out, key=lambda s: s[1].lineno)


def join(words: list) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def note(out: dict, x: str, value: ast.expr, ok: bool, st: ast.stmt, where: str, problems: list) -> None:
    """record that statement st (at where) copies value, which is field x if ok, into the place of x"""
    if not ok:
        problems.append(f"{where}: `{ast.unparse(st)}` copies `{ast.unparse(value)}` into the place of '{x}': "
                        "copy each field into its own")
    if x in out:
        problems.append(f"{where}: `{ast.unparse(st)}` copies '{x}' again (also at line {out[x]})")
    else:
        out[x] = st.lineno


def saved(d: ast.FunctionDef, params: list, pfields: dict, problems: list) -> dict:
    """{X: its line}: the fields gen_save (def d) copies into its Frame, the arguments of its Frame(...)
    (params: Frame.__init__'s, pfields: the field that keeps each) and then fr.X = self.X"""
    me = d.args.args[0].arg
    out: dict = {}
    fr = ""
    for st in statements(d):
        where = f"gen_save ({EMISSION}:{st.lineno})"
        ts = targets(st)
        one = isinstance(st, ast.Assign) and len(ts) == 1
        if fr == "" and one and isinstance(ts[0], ast.Name) and isinstance(st.value, ast.Call) \
                and isinstance(st.value.func, ast.Name) and st.value.func.id == "Frame":
            fr = ts[0].id
            args = [(params[i] if i < len(params) else "", a) for i, a in enumerate(st.value.args)]
            for k in st.value.keywords:
                args.append((k.arg or "", k.value))
            for p, a in args:
                if p in pfields:
                    note(out, pfields[p], a, attr(a, me) == pfields[p], st, where, problems)
                else:
                    problems.append(f"{where}: Frame(...) passes `{ast.unparse(a)}` for no parameter that "
                                    "Frame.__init__ keeps in a field")
        elif fr != "" and isinstance(st, ast.Return) and isinstance(st.value, ast.Name) and st.value.id == fr:
            continue
        elif fr != "" and one and attr(ts[0], fr) != "" and attr(st.value, me) != "":
            note(out, attr(ts[0], fr), st.value, attr(st.value, me) == attr(ts[0], fr), st, where, problems)
        else:
            problems.append(f"{where}: `{ast.unparse(st)}` is not {fr or 'fr'}.X = {me}.X, the only copy "
                            "the check reads there")
    return out


def restored(d: ast.FunctionDef, problems: list) -> dict:
    """{X: its line}: the fields gen_restore (def d) copies back from its Frame, self.X = fr.X"""
    me = d.args.args[0].arg
    fr = d.args.args[1].arg if len(d.args.args) > 1 else ""
    out: dict = {}
    for st in statements(d):
        where = f"gen_restore ({EMISSION}:{st.lineno})"
        ts = targets(st)
        if fr != "" and isinstance(st, ast.Assign) and len(ts) == 1 and attr(ts[0], me) != "" \
                and attr(st.value, fr) != "":
            note(out, attr(ts[0], me), st.value, attr(st.value, fr) == attr(ts[0], me), st, where, problems)
        else:
            problems.append(f"{where}: `{ast.unparse(st)}` is not {me}.X = {fr or 'fr'}.X, the only copy "
                            "the check reads there")
    return out


def check(sources: dict, not_saved=None, not_reset=None) -> list:
    """the problems of the lists in sources ({path: its text}), with exceptions not_saved and not_reset
    (default: NOT_SAVED and NOT_RESET); [] if they agree"""
    not_saved = NOT_SAVED if not_saved is None else not_saved
    not_reset = NOT_RESET if not_reset is None else not_reset
    problems: list = []
    trees: dict = {}
    defs: dict = {}
    for label, path, cls, name in LISTS:
        if path not in trees:
            trees[path] = ast.parse(sources[path], path)
        defs[label] = find(trees[path], cls, name)
        if defs[label] is None or len(defs[label].args.args) == 0:
            problems.append(f"no {label} in {path} to read (LISTS in tools/test_frame_fields.py says where it is)")
    if problems:
        return problems
    fdef = defs["Frame.__init__"]
    params = [a.arg for a in fdef.args.args[1:]]
    frame: dict = {}
    pfields: dict = {}  # each parameter of Frame.__init__ that a field keeps, and that field
    for x, st in stores(fdef):
        if x in frame:
            problems.append(f"Frame.__init__ ({IR}:{st.lineno}) assigns '{x}' again (also at line {frame[x]})")
            continue
        frame[x] = st.lineno
        if isinstance(st.value, ast.Name) and st.value.id in params:
            pfields[st.value.id] = x
    if len(frame) == 0:
        problems.append(f"Frame.__init__ ({IR}:{fdef.lineno}) assigns no field: nothing to compare")
    has = {"Gen.__init__": {x for x, _ in stores(defs["Gen.__init__"])}, "Frame.__init__": set(frame),
           "gen_save": set(saved(defs["gen_save"], params, pfields, problems)),
           "gen_restore": set(restored(defs["gen_restore"], problems)),
           "gen_enter": {x for x, _ in stores(defs["gen_enter"])}}
    for x in sorted(not_saved):
        kept = [label for label in SAVES if x in has[label]]
        if x not in has["gen_enter"]:
            problems.append(f"NOT_SAVED lists '{x}', which gen_enter ({FUNCTIONS}) does not assign: remove it")
        elif len(kept) > 0:
            problems.append(f"NOT_SAVED lists '{x}', which {join(kept)} also list: remove it there or here")
    for x in sorted(not_reset):
        if x in has["gen_enter"]:
            problems.append(f"NOT_RESET lists '{x}', which gen_enter ({FUNCTIONS}) assigns: remove it")
        elif x not in has["Frame.__init__"]:
            problems.append(f"NOT_RESET lists '{x}', which Frame.__init__ ({IR}) does not hold: remove it")
    where = {label: f"{label} ({path}:{defs[label].lineno})" for label, path, _, _ in LISTS}
    for x in sorted(has["Frame.__init__"] | has["gen_save"] | has["gen_restore"] | has["gen_enter"]):
        if x in not_saved and not any(x in has[label] for label in SAVES):
            want = ["Gen.__init__", "gen_enter"]
        else:
            want = ["Gen.__init__"] + SAVES + ([] if x in not_reset else ["gen_enter"])
        missing = [where[label] for label in want if x not in has[label]]
        if len(missing) > 0:
            present = [label for label, _, _, _ in LISTS if x in has[label]]
            problems.append(f"'{x}' is missing from {join(missing)}; it is in {join(present)}")
    return problems


def report(problems: list) -> str:
    return "\n".join(problems + [FOOTER])


def sources(root: str = ROOT) -> dict:
    """{path: its text}: the files of LISTS in checkout root"""
    out = {}
    for _, path, _, _ in LISTS:
        with open(os.path.join(root, path), encoding="utf-8") as f:
            out[path] = f.read()
    return out


class AgreementTests(unittest.TestCase):
    def test_the_lists_agree(self):
        problems = check(sources())
        if len(problems) > 0:
            self.fail(report(problems))

    def test_each_exception_gives_its_reason(self):
        for x, why in list(NOT_SAVED.items()) + list(NOT_RESET.items()):
            self.assertTrue(why.strip() != "" and "\n" not in why, x)


# negative controls: the sources changed in each way the lists can disagree
FIELD = "probe_state"  # a field none of the lists has


def splice(text: str, st: ast.stmt, code: list, before: bool = False) -> str:
    """text with statement st replaced by the lines code, indented as st is, or with them before it"""
    lines = text.splitlines(keepends=True)
    new = [" " * st.col_offset + c + "\n" for c in code]
    return "".join(lines[: st.lineno - 1] + new + lines[st.lineno - 1 if before else st.end_lineno:])


def parsed(src: dict, label: str):
    """(the path of list label, its def) in src"""
    _, path, cls, name = next(p for p in LISTS if p[0] == label)
    return path, find(ast.parse(src[path]), cls, name)


def add_field(src: dict, label: str) -> dict:
    """src with FIELD added to list label, as its other fields are"""
    path, d = parsed(src, label)
    me = d.args.args[0].arg
    sts = statements(d)
    if label == "gen_save":
        st, code = sts[-1], f"{sts[0].targets[0].id}.{FIELD} = {me}.{FIELD}"  # (before its return)
    elif label == "gen_restore":
        st, code = sts[0], f"{me}.{FIELD} = {d.args.args[1].arg}.{FIELD}"
    else:
        st, code = sts[0], f"{me}.{FIELD} = {{}}"
    return {**src, path: splice(src[path], st, [code], before=True)}


def drop(src: dict, label: str, field: str) -> dict:
    """src without the statements of list label that assign field (self.field or fr.field)"""
    path, d = parsed(src, label)
    text = src[path]
    hits = [n for n in ast.walk(d) if any(isinstance(t, ast.Attribute) and t.attr == field for t in targets(n))]
    for st in sorted(hits, key=lambda n: -n.lineno):
        text = splice(text, st, [])
    return {**src, path: text}


class NegativeControlTests(unittest.TestCase):
    def setUp(self):
        self.src = sources()

    def field(self) -> str:
        """a field of every list that gen_enter assigns and Frame(...) does not take: the first of Frame's"""
        enter = [x for x, _ in stores(parsed(self.src, "gen_enter")[1])]
        d = parsed(self.src, "Frame.__init__")[1]
        params = [a.arg for a in d.args.args]
        for x, st in stores(d):
            if x in enter and not (isinstance(st.value, ast.Name) and st.value.id in params):
                return x
        self.fail("Frame.__init__ has no field that gen_enter assigns")

    def assertMissing(self, problems: list, field: str, label: str):
        self.assertEqual(len(problems), 1, report(problems))
        self.assertTrue(problems[0].startswith(f"'{field}' is missing from {label} ("), problems[0])
        text = report(problems)
        for name, path, _, _ in LISTS:
            self.assertIn(name, text)
            self.assertIn(path, text)

    def test_a_new_field_in_every_list(self):
        src = self.src
        for label, _, _, _ in LISTS:
            src = add_field(src, label)
        self.assertEqual(check(src), [])

    def test_a_new_field_left_out_of_one_list(self):
        # (#767's negative control is the one left out of Frame.__init__)
        for left, _, _, _ in LISTS:
            with self.subTest(left=left):
                src = self.src
                for label, _, _, _ in LISTS:
                    if label != left:
                        src = add_field(src, label)
                self.assertMissing(check(src), FIELD, left)

    def test_a_field_dropped_from_one_list(self):
        x = self.field()
        for label, _, _, _ in LISTS:
            with self.subTest(label=label):
                self.assertMissing(check(drop(self.src, label, x)), x, label)

    def test_a_field_that_only_gen_enter_assigns(self):
        src = add_field(add_field(self.src, "Gen.__init__"), "gen_enter")
        problems = check(src)
        self.assertMissing(problems, FIELD, "Frame.__init__")
        for label in SAVES:
            self.assertIn(label + " (", problems[0])
        self.assertEqual(check(src, not_saved={FIELD: "a reason"}), [])

    def test_a_field_copied_into_the_place_of_another(self):
        for label in ["gen_save", "gen_restore"]:
            with self.subTest(label=label):
                path, d = parsed(self.src, label)
                a, b = [st for st in statements(d) if isinstance(st, ast.Assign)
                        and isinstance(st.targets[0], ast.Attribute)][:2]
                code = f"{ast.unparse(a.targets[0])} = {ast.unparse(b.value)}"  # (fr.X = self.Y, self.X = fr.Y)
                problems = check({**self.src, path: splice(self.src[path], a, [code])})
                self.assertEqual(len(problems), 1, report(problems))
                self.assertIn(f"{label} ({path}:{a.lineno}): `{code}` copies `{ast.unparse(b.value)}` into the "
                              f"place of '{a.targets[0].attr}'", problems[0])

    def test_frame_arguments_swapped(self):
        path, d = parsed(self.src, "gen_save")
        st = statements(d)[0]
        args = [ast.unparse(a) for a in st.value.args]
        code = f"{st.targets[0].id} = Frame({', '.join([args[1], args[0]] + args[2:])})"
        problems = check({**self.src, path: splice(self.src[path], st, [code])})
        self.assertEqual(len(problems), 2, report(problems))
        for p, arg in zip(problems, args[1::-1]):
            self.assertIn(f"`{code}` copies `{arg}` into the place of", p)

    def test_a_copy_made_twice_and_a_statement_the_check_does_not_read(self):
        path, d = parsed(self.src, "gen_save")
        sts = statements(d)
        fr = sts[0].targets[0].id
        twice = splice(self.src[path], sts[-1], [ast.unparse(sts[1]), f"print({fr})"], before=True)
        problems = check({**self.src, path: twice})
        self.assertEqual(len(problems), 2, report(problems))
        self.assertIn(f"copies '{sts[1].targets[0].attr}' again (also at line {sts[1].lineno})", problems[0])
        self.assertIn(f"`print({fr})` is not {fr}.X = ", problems[1])

    def test_a_list_not_found(self):
        text = self.src[EMISSION].replace("def gen_save(", "def gen_save_frame(")
        self.assertNotEqual(text, self.src[EMISSION])
        self.assertEqual(check({**self.src, EMISSION: text}),
                         [f"no gen_save in {EMISSION} to read (LISTS in tools/test_frame_fields.py says where it is)"])

    def test_stale_and_needed_exceptions(self):
        x = self.field()
        cases = [({"not_reset": {**NOT_RESET, x: "r"}}, f"NOT_RESET lists '{x}', which gen_enter"),
                 ({"not_reset": {**NOT_RESET, FIELD: "r"}}, f"NOT_RESET lists '{FIELD}', which Frame.__init__"),
                 ({"not_saved": {x: "r"}}, f"NOT_SAVED lists '{x}', which Frame.__init__, gen_save and gen_restore"),
                 ({"not_saved": {FIELD: "r"}}, f"NOT_SAVED lists '{FIELD}', which gen_enter")]
        for kw, start in cases:
            with self.subTest(start=start):
                problems = check(self.src, **kw)
                self.assertEqual(len(problems), 1, report(problems))
                self.assertTrue(problems[0].startswith(start), problems[0])
        # without NOT_RESET, each field it lists is missing from gen_enter
        problems = check(self.src, not_reset={})
        self.assertEqual([p.split(" is missing from gen_enter (")[0] for p in problems],
                         [f"'{x}'" for x in sorted(NOT_RESET)])


if __name__ == "__main__":
    unittest.main()
