"""Drift and negative controls for compiler module-container ownership."""
import ast
import unittest

from compiler_state_globals import (
    ALIASES, LOOKUP, RETAINED, REWOUND, ROOT, WRITERS, inventory, read_sources,
    validate_sources, writes,
)


class GlobalOwnershipTests(unittest.TestCase):
    def test_current_tree_and_disjoint_ownership(self):
        sources = read_sources()
        self.assertEqual(validate_sources(sources), [])
        self.assertFalse(LOOKUP & REWOUND.keys())
        self.assertFalse(LOOKUP & RETAINED.keys())
        self.assertFalse(REWOUND.keys() & RETAINED.keys())
        self.assertEqual(WRITERS.keys(), REWOUND.keys() | RETAINED.keys())
        self.assertTrue(all(REWOUND.values()))
        self.assertTrue(all(RETAINED.values()))

    def test_new_container_declaration_forms(self):
        forms = ["[]", "{}", "set()", "list()", "dict()", "[x for x in ()]",
                 "{x: x for x in ()}", "{x for x in ()}", '"a b".split()',
                 '"a b".rsplit()', '"a\\nb".splitlines()', "([] ,)", "[] + []"]
        for value in forms:
            with self.subTest(value=value):
                errors = validate_sources({"added": f"CACHE = {value}\n"})
                self.assertIn("unclassified module container: added.CACHE", errors)
        for annotation in ("list[int]", "dict[str, int]", "set[str]", "list", "dict", "set"):
            errors = validate_sources({"added": f"cache: {annotation} = factory()\n"})
            self.assertIn("unclassified module container: added.cache", errors)

    def test_annotation_wrappers_and_import_aliases(self):
        forms = (
            ("", "'list[int]'"),
            ("import builtins as b\n", "b.dict[str, int]"),
            ("from builtins import set as S\n", "S[str]"),
            ("import typing as t\n", "t.Annotated[t.List[int], 'meta']"),
            ("from typing import Annotated as A, Dict as D\n", "\"A['D[str, int]', 'meta']\""),
            ("from typing_extensions import Annotated as A\n", "A[set[int], 'meta']"),
        )
        for imports, annotation in forms:
            with self.subTest(annotation=annotation):
                self.assertEqual(inventory({"probe": imports + f"CACHE: {annotation} = factory()\n"})[1],
                                 {"probe.CACHE"})
        for imports, annotation in (
            ("from typing import Annotated as A\n", "A[int, list[int]]"),
            ("from unrelated import Annotated as A\n", "A[list[int], 'meta']"),
            ("from unrelated import list\n", "list[int]"),
            ("", "'not valid!'"),
        ):
            self.assertEqual(inventory({"probe": imports + f"CACHE: {annotation} = factory()\n"})[1], set())

    def test_annotation_import_order(self):
        sources = (
            ("from typing import Annotated as A\nCACHE: A[list[int], 'meta'] = factory()\nfrom other import A\n", True),
            ("CACHE: list[int] = factory()\nfrom other import list\n", True),
            ("from other import A\nCACHE: A[list[int], 'meta'] = factory()\nfrom typing import Annotated as A\n", False),
        )
        for source, expected in sources:
            self.assertEqual("probe.CACHE" in inventory({"probe": source})[1], expected)

    def test_named_expression_aliases_and_inventory(self):
        for body, alias in (
            ("if (alias := KEYWORDS):\n        alias.clear()", "alias"),
            ("(alias := KEYWORDS).clear()", "alias"),
            ("(alias := KEYWORDS)['nested'].clear()", "alias"),
            ("other = (alias := KEYWORDS)\n    other.clear()", "other"),
            ("while (alias := KEYWORDS):\n        alias.clear()", "alias"),
        ):
            self.assertEqual(self.scan("def added():\n    " + body + "\n"),
                             {("lexer.KEYWORDS", "probe.added", alias)})
        self.assertEqual(inventory({"probe": "if (CACHE := {}):\n    pass\n"})[1], {"probe.CACHE"})
        for body in (
            "if (KEYWORDS := {}):\n        KEYWORDS.clear()",
            "if (alias := dict(KEYWORDS)):\n        alias.clear()",
            "f = lambda: (alias := KEYWORDS)\n    alias.clear()",
        ):
            self.assertEqual(self.scan("def added():\n    " + body + "\n"), set())

    def test_default_parameter_aliases(self):
        for arguments, alias in (("table=KEYWORDS", "table"), ("KEYWORDS=KEYWORDS", "KEYWORDS"),
                                 ("a, table=KEYWORDS, /, b=0", "table"),
                                 ("*, first=0, table=KEYWORDS", "table")):
            self.assertEqual(self.scan(f"def added({arguments}):\n    {alias}.clear()\n"),
                             {("lexer.KEYWORDS", "probe.added", alias)})
        source = "def outer():\n    alias = KEYWORDS\n    def inner(table=alias):\n        table.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "table")})
        source = "def outer():\n    def inner(table=(alias := KEYWORDS)):\n        table.clear()\n    alias.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "table"),
                                            ("lexer.KEYWORDS", "probe.outer", "alias")})
        for arguments in ("KEYWORDS", "KEYWORDS={}", "KEYWORDS=dict(KEYWORDS)"):
            self.assertEqual(self.scan(f"def added({arguments}):\n    KEYWORDS.clear()\n"), set())

    def test_method_defaults_use_class_namespace(self):
        for field in ("KEYWORDS = {}", "from unrelated import KEYWORDS"):
            source = f"class C:\n    {field}\n    def method(self, table=KEYWORDS):\n        table.clear()\n"
            self.assertEqual(self.scan(source), set())
        source = "class C:\n    alias = KEYWORDS\n    def method(self, table=alias):\n        table.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "table")})
        source = "class C:\n    KEYWORDS = {}\n    def method(self, table=KEYWORDS):\n        KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "KEYWORDS")})

    def test_method_default_assignment_expressions(self):
        source = "class C:\n    def first(self, table=(alias := KEYWORDS)):\n        table.clear()\n    def second(self, table=alias):\n        table.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.first", "table"),
                                            ("lexer.KEYWORDS", "probe.C.second", "table")})
        source = "class C:\n    def method(self, table=(KEYWORDS := {})):\n        table.clear()\n"
        self.assertEqual(self.scan(source), set())

    def test_default_captures_follow_argument_order(self):
        source = "class C:\n    def method(self, first=KEYWORDS, second=(KEYWORDS := {})):\n        first.clear()\n        second.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "first")})
        source = "class C:\n    def method(self, first=(alias := KEYWORDS), second=alias):\n        first.clear()\n        second.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "first"),
                                            ("lexer.KEYWORDS", "probe.C.method", "second")})

    def test_binding_targets_rebind_globals_and_shadow_locals(self):
        forms = (
            "for KEYWORDS in values:\n        pass",
            "with context() as KEYWORDS:\n        pass",
            "try:\n        pass\n    except Exception as KEYWORDS:\n        pass",
            "match value:\n        case {'item': KEYWORDS}:\n            pass",
            "def KEYWORDS():\n        pass",
            "class KEYWORDS:\n        pass",
        )
        for body in forms:
            with self.subTest(body=body):
                self.assertEqual(self.scan("def added():\n    global KEYWORDS\n    " + body + "\n"),
                                 {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
                self.assertEqual(self.scan("def added():\n    " + body + "\n    KEYWORDS.clear()\n"), set())
        for body in ("for KEYWORDS['x'] in values:\n        pass",
                     "with context() as KEYWORDS['x']:\n        pass"):
            self.assertEqual(self.scan("def added():\n    " + body + "\n"),
                             {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})

    def test_anonymous_scope_exclusion(self):
        source = "def added():\n    fn = lambda KEYWORDS: KEYWORDS.clear()\n    [KEYWORDS.clear() for KEYWORDS in values]\n"
        self.assertEqual(self.scan(source), set())
        source = "def added():\n    [None for KEYWORDS in values]\n    KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        source = "def added():\n    fn = lambda value=KEYWORDS.clear(): value\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})

    def test_conditional_initialization_and_module_aliases(self):
        sources = {"a": "from src.pystachy_compiler.z import TABLE\nALIAS = TABLE\n",
                   "z": "if flag:\n    TABLE = {}\n"}
        self.assertEqual(inventory(sources)[1], {"a.ALIAS", "z.TABLE"})
        for imported in ("from src.pystachy_compiler import z as other",
                         "import src.pystachy_compiler.z as other"):
            sources["a"] = imported + "\nALIAS = other.TABLE\n"
            self.assertEqual(inventory(sources)[1], {"a.ALIAS", "z.TABLE"})
        self.assertEqual(inventory({"added": "LEFT, RIGHT = [], {}\n"})[1],
                         {"added.LEFT", "added.RIGHT"})

    def test_match_case_declarations(self):
        source = "match mode:\n    case 0:\n        FIRST = {}\n    case _:\n        match other:\n            case 1:\n                SECOND: list = factory()\n"
        self.assertEqual(inventory({"added": source})[1], {"added.FIRST", "added.SECOND"})

    def test_imported_noncontainers_are_not_writers(self):
        for source in (
            "from src.pystachy_compiler.worker import Worker\ndef added():\n    Worker.clear()\n",
            "def added():\n    from src.pystachy_compiler.worker import Worker as Tool\n    Tool.clear()\n",
        ):
            with self.subTest(source=source):
                sources = {"probe": source, "worker": "class Worker:\n    pass\n"}
                trees, found, bindings = inventory(sources)
                self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found), set())

    def scan(self, body, imports="from src.pystachy_compiler.lexer import KEYWORDS\n"):
        sources = {"probe": imports + body, "lexer": "KEYWORDS = {}\n"}
        trees, found, bindings = inventory(sources)
        return writes(trees["probe"], "probe", bindings["probe"], found)

    def test_new_direct_writer_of_lookup_table(self):
        for operation in ('KEYWORDS["bad"] = True', 'del KEYWORDS["bad"]',
                          'KEYWORDS.clear()', 'KEYWORDS.update({"bad": True})',
                          'KEYWORDS.setdefault("bad", True)', 'KEYWORDS["nested"].append(1)'):
            with self.subTest(operation=operation):
                self.assertEqual(self.scan("def added():\n    " + operation + "\n"),
                                 {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})

    def test_global_rebinding_and_augmented_mutation(self):
        self.assertEqual(self.scan("def added():\n    global KEYWORDS\n    KEYWORDS = {}\n"),
                         {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        self.assertEqual(self.scan("def added():\n    KEYWORDS['x'] += 1\n"),
                         {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        self.assertEqual(self.scan("def added():\n    alias = KEYWORDS\n    alias |= {'bad': True}\n"),
                         {("lexer.KEYWORDS", "probe.added", "alias")})
        for assignment in ("KEYWORDS, other = {}, []", "other, (KEYWORDS, last) = [], ({}, [])",
                           "KEYWORDS, other = factory()", "KEYWORDS, *other = factory()",
                           "[other, KEYWORDS] = factory()"):
            with self.subTest(assignment=assignment):
                self.assertEqual(self.scan("def added():\n    global KEYWORDS\n    " + assignment + "\n"),
                                 {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        for targets in ("KEYWORDS, other", "other, (KEYWORDS, last)"):
            with self.subTest(targets=targets):
                self.assertEqual(self.scan("def added():\n    global KEYWORDS\n    del " + targets + "\n"),
                                 {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})

    def test_import_alias_and_module_qualified_writer(self):
        self.assertEqual(self.scan("def added():\n    renamed.clear()\n",
                                  "from src.pystachy_compiler.lexer import KEYWORDS as renamed\n"),
                         {("lexer.KEYWORDS", "probe.added", "renamed")})
        self.assertEqual(self.scan("def added():\n    lex.KEYWORDS.clear()\n",
                                  "from src.pystachy_compiler import lexer as lex\n"),
                         {("lexer.KEYWORDS", "probe.added", "lex.KEYWORDS")})
        self.assertEqual(self.scan("def added():\n    lex.KEYWORDS.clear()\n",
                                  "import src.pystachy_compiler.lexer as lex\n"),
                         {("lexer.KEYWORDS", "probe.added", "lex.KEYWORDS")})
        self.assertEqual(self.scan("def added():\n    src.pystachy_compiler.lexer.KEYWORDS.clear()\n",
                                  "import src.pystachy_compiler.lexer\n"),
                         {("lexer.KEYWORDS", "probe.added", "src.pystachy_compiler.lexer.KEYWORDS")})
        for operation in ("lex.KEYWORDS = {}", "del lex.KEYWORDS"):
            with self.subTest(operation=operation):
                self.assertEqual(self.scan("def added():\n    " + operation + "\n",
                                          "from src.pystachy_compiler import lexer as lex\n"),
                                 {("lexer.KEYWORDS", "probe.added", "lex.KEYWORDS")})

    def test_local_alias_chain_and_nested_container(self):
        source = "def added():\n    one = KEYWORDS\n    two = one['x']\n    two.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "two")})

    def test_nonlocal_alias_augmented_mutation(self):
        source = "def outer():\n    alias = KEYWORDS\n    def inner():\n        nonlocal alias\n        alias |= {'bad': True}\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "alias")})
        source = "def outer():\n    alias = dict(KEYWORDS)\n    def inner():\n        nonlocal alias\n        alias |= {'bad': True}\n"
        self.assertEqual(self.scan(source), set())
        source = "def outer():\n    alias = KEYWORDS\n    def inner():\n        nonlocal alias\n        alias = {}\n"
        self.assertEqual(self.scan(source), set())

    def test_control_flow_nested_function_writer_owner(self):
        source = "def outer():\n    match value:\n        case 0:\n            def inner():\n                KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        source = "def outer():\n    match value:\n        case 0 if KEYWORDS.clear():\n            pass\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer", "KEYWORDS")})
        source = "def outer():\n    try:\n        pass\n    except Exception:\n        def inner():\n            KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})

    def test_conditional_function_and_method_definitions(self):
        for header in ("if flag:", "try:", "match value:\n    case 0:"):
            indent = "        " if header.startswith("match") else "    "
            source = header + "\n" + indent + "def added():\n" + indent + "    KEYWORDS.clear()\n"
            if header == "try:":
                source += "except Exception:\n    pass\n"
            self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        source = "class C:\n    if flag:\n        def method(self):\n            KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "KEYWORDS")})

    def test_local_imports_and_import_aliases(self):
        forms = (
            ("from src.pystachy_compiler.lexer import KEYWORDS", "KEYWORDS"),
            ("from src.pystachy_compiler.lexer import KEYWORDS as table", "table"),
            ("from src.pystachy_compiler import lexer as lex", "lex.KEYWORDS"),
            ("import src.pystachy_compiler.lexer as lex", "lex.KEYWORDS"),
            ("import src.pystachy_compiler.lexer", "src.pystachy_compiler.lexer.KEYWORDS"),
        )
        for imported, expression in forms:
            with self.subTest(imported=imported):
                source = f"def added():\n    {imported}\n    {expression}.clear()\n"
                self.assertEqual(self.scan(source, ""), {("lexer.KEYWORDS", "probe.added", expression)})
        source = "def added():\n    from src.pystachy_compiler.lexer import KEYWORDS\n    alias = KEYWORDS\n    alias.clear()\n"
        self.assertEqual(self.scan(source, ""), {("lexer.KEYWORDS", "probe.added", "alias")})

    def test_local_import_shadowing_and_scope(self):
        source = "def added():\n    from unrelated import KEYWORDS\n    KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), set())
        for imported in ("import unrelated as lex", "from unrelated import lexer as lex"):
            source = f"def added():\n    {imported}\n    lex.KEYWORDS.clear()\n"
            self.assertEqual(self.scan(source, "from src.pystachy_compiler import lexer as lex\n"), set())
        source = "def outer():\n    from src.pystachy_compiler.lexer import KEYWORDS\n    def inner(KEYWORDS):\n        KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source, ""), set())
        source = "def outer():\n    from src.pystachy_compiler.lexer import KEYWORDS as alias\n    def inner():\n        alias.clear()\n"
        self.assertEqual(self.scan(source, ""), {("lexer.KEYWORDS", "probe.outer.inner", "alias")})

    def test_nested_local_class_methods(self):
        source = "def outer():\n    class C:\n        def method(self):\n            KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.C.method", "KEYWORDS")})
        source = "def outer():\n    alias = KEYWORDS\n    class C:\n        alias = {}\n        def method(self):\n            alias.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.C.method", "alias")})
        source = "def outer():\n    from src.pystachy_compiler.lexer import KEYWORDS as alias\n    class C:\n        class D:\n            def method(self):\n                alias.clear()\n"
        self.assertEqual(self.scan(source, ""), {("lexer.KEYWORDS", "probe.outer.C.D.method", "alias")})
        source = "def outer():\n    alias = KEYWORDS\n    class C:\n        def method(self, alias):\n            alias.clear()\n"
        self.assertEqual(self.scan(source), set())

    def test_aliases_do_not_oscillate_or_drop_possible_origins(self):
        source = "def added():\n    a = KEYWORDS\n    b = a\n    a = b\n    a.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "a")})

    def test_local_shadow_and_copy_are_not_global_writes(self):
        for source in ("def added(KEYWORDS):\n    KEYWORDS.clear()\n",
                       "def added():\n    KEYWORDS = {}\n    KEYWORDS.clear()\n",
                       "def added():\n    KEYWORDS, other = factory()\n    KEYWORDS.clear()\n",
                       "def added():\n    other, *KEYWORDS = factory()\n    KEYWORDS.clear()\n",
                       "def added():\n    copy = dict(KEYWORDS)\n    copy.clear()\n",
                       "def added():\n    value = 0\n    value |= KEYWORDS['x']\n"):
            with self.subTest(source=source):
                self.assertEqual(self.scan(source), set())

    def test_initialization_is_not_a_post_import_write(self):
        sources = {"lexer": "KEYWORDS = {}\nfor word in words:\n    KEYWORDS[word] = True\n"}
        trees, _, bindings = inventory(sources)
        self.assertEqual(writes(trees["lexer"], "lexer", bindings["lexer"]), set())

    def test_method_and_nested_function_owners(self):
        source = "class C:\n    def method(self):\n        KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "KEYWORDS")})
        source = "def outer():\n    def inner():\n        KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        source = "def outer():\n    alias = KEYWORDS\n    def inner():\n        alias.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "alias")})

    def test_missing_or_reclassified_ownership_fails(self):
        sources = read_sources()
        sources["diagnostics"] = sources["diagnostics"].replace("FILES: list[str] = []", "FILES = None")
        self.assertIn("stale container classification: diagnostics.FILES", validate_sources(sources))
        sources = read_sources()
        sources["lexer"] += "\ndef bad_writer():\n    KEYWORDS.clear()\n"
        self.assertIn("unreviewed container writer: lexer.bad_writer writes lexer.KEYWORDS via KEYWORDS",
                      validate_sources(sources))

    def test_alias_exception_cannot_hide_direct_sentinel_write(self):
        source = "def gen_verify():\n    NOLABELS.append('bad')\n"
        imports = "from src.pystachy_compiler.ir import NOLABELS\n"
        sources = {"ircheck": imports + source, "ir": "NOLABELS = []\n"}
        trees, _, bindings = inventory(sources)
        actual = writes(trees["ircheck"], "ircheck", bindings["ircheck"])
        self.assertEqual(actual, {("ir.NOLABELS", "ircheck.gen_verify", "NOLABELS")})
        self.assertFalse(actual & ALIASES)

    def test_rewound_registry_has_existing_executable_controls(self):
        # Tie this classification to the real restart/removal-control harness.
        # New restart-owned state needs assertions there, not just an allowlist entry.
        tree = ast.parse((ROOT / "tools/test_compiler_state_probe.py").read_text())
        contract = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name == "restart_contract")
        assignment = next(n for n in contract.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "names" for t in n.targets))
        self.assertEqual(set(ast.literal_eval(assignment.value)),
                         {name.split(".")[-1] for name in REWOUND})


if __name__ == "__main__":
    unittest.main()
