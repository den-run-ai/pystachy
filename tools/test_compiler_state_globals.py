"""Drift and negative controls for compiler module-container ownership."""
import ast
import subprocess
import sys
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

    def test_parameterized_container_constructors(self):
        for name, args in (("list", "int"), ("dict", "str, bool"), ("set", "str")):
            for imports, constructor in (
                ("", name),
                ("import builtins\n", "builtins." + name),
                ("import builtins as b\n", "b." + name),
                (f"from builtins import {name} as C\n", "C"),
            ):
                for expression in (f"{constructor}[{args}]()", f"{constructor}()"):
                    with self.subTest(expression=expression):
                        self.assertEqual(inventory({"probe": imports + f"CACHE = {expression}\n"})[1],
                                         {"probe.CACHE"})
        for imports, expression in (
            ("", "tuple[int]()"), ("", "factory[list[int]]()"),
            ("from unrelated import list\n", "list[int]()"),
            ("from unrelated import list\n", "list()"),
            ("import unrelated as b\n", "b.dict[str, int]()"),
        ):
            self.assertEqual(inventory({"probe": imports + f"CACHE = {expression}\n"})[1], set())

    def test_conditional_container_initializers(self):
        for expression in ("{} if enabled else {}", "[] if enabled else None", "None if enabled else set()",
                           "[] or []", "enabled and {}", "enabled or dict[str, int]()",
                           "([] if first else None) or ({} if second else None)"):
            with self.subTest(expression=expression):
                self.assertEqual(inventory({"probe": f"CACHE = {expression}\n"})[1], {"probe.CACHE"})
        for expression in ("1 if [] else 2", "True if dict[str, int]() else False", "1 or 2",
                           "check([]) and 3", "factory({}) if enabled else factory([])"):
            self.assertEqual(inventory({"probe": f"VALUE = {expression}\n"})[1], set())

    def test_new_initializer_forms_report_container_and_writer(self):
        for expression in ("dict[str, bool]()", "{} if enabled else {}", "[] or []"):
            with self.subTest(expression=expression):
                sources = read_sources()
                sources["lexer"] += f"\nNEW_CACHE = {expression}\ndef added_writer():\n    NEW_CACHE.clear()\n"
                self.assertEqual(validate_sources(sources), [
                    "unclassified module container: lexer.NEW_CACHE",
                    "unreviewed container writer: lexer.added_writer writes lexer.NEW_CACHE via NEW_CACHE",
                ])

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

    def test_union_container_annotations(self):
        for imports, annotation in (
            ("", "dict[str, int] | None"), ("", "None | list[int]"),
            ("import typing as t\n", "t.Optional[set[str]]"),
            ("from typing import Union as U\n", "U[int, dict[str, bool]]"),
            ("from typing import Annotated as A, Optional as O\n", "\"A[O['list[int]'], 'meta']\""),
            ("from typing_extensions import Optional as O\n", "O[list[int]]"),
        ):
            self.assertEqual(inventory({"probe": imports + f"CACHE: {annotation} = factory()\n"})[1],
                             {"probe.CACHE"})
        for imports, annotation in (
            ("", "int | None"), ("from typing import Optional as O\n", "O[tuple[int]]"),
            ("from typing import Annotated as A\n", "A[int | None, list[int]]"),
            ("from unrelated import Optional as O\n", "O[list[int]]"),
            ("from typing import Union as U\n", "U[int, str]"),
        ):
            self.assertEqual(inventory({"probe": imports + f"CACHE: {annotation} = factory()\n"})[1], set())

    def test_unbound_builtin_mutators(self):
        imports = "from src.pystachy_compiler.lexer import KEYWORDS\n"
        for header, owner in (("", "dict"), ("import builtins as b\n", "b.dict"),
                              ("from builtins import dict as D\n", "D")):
            for operation in (f"{owner}.clear(KEYWORDS)", f"{owner}.__setitem__(KEYWORDS, 'bad', True)",
                              f"{owner}[str, bool].clear(KEYWORDS)"):
                self.assertEqual(self.scan("def added():\n    " + operation + "\n", imports + header),
                                 {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        source = "def outer():\n    from builtins import dict as D\n    def inner():\n        D.clear(KEYWORDS)\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        source = "def added():\n    list.append(FILES, 'bad')\n"
        sources = {"probe": "from src.pystachy_compiler.diagnostics import FILES\n" + source,
                   "diagnostics": "FILES = []\n"}
        trees, found, bindings = inventory(sources)
        self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found),
                         {("diagnostics.FILES", "probe.added", "FILES")})

    def test_builtin_mutator_shadows_and_copies(self):
        for prefix, body in (
            ("dict = Worker\n", "def added():\n    dict.clear(KEYWORDS)\n"),
            ("", "def added(dict):\n    dict.clear(KEYWORDS)\n"),
            ("", "def added():\n    dict = Worker\n    dict.clear(KEYWORDS)\n"),
            ("import builtins as b\n", "def added(b):\n    b.dict.clear(KEYWORDS)\n"),
            ("", "def added():\n    from unrelated import dict\n    dict.clear(KEYWORDS)\n"),
            ("", "def added():\n    from builtins import dict as D\n    D = Worker\n    D.clear(KEYWORDS)\n"),
            ("", "def added():\n    dict.clear(dict(KEYWORDS))\n"),
            ("", "def added():\n    dict.get(KEYWORDS, 'x')\n"),
        ):
            self.assertEqual(self.scan(prefix + body), set())
        source = "class C:\n    dict = Worker\n    def method(self):\n        dict.clear(KEYWORDS)\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "KEYWORDS")})

    def test_builtin_mutator_binding_edges(self):
        for body in ("def added():\n    (dict := Worker).clear(KEYWORDS)\n",
                     "def added():\n    (dict := Worker)[str, bool].clear(KEYWORDS)\n",
                     "def added():\n    dict: object\n    dict.clear(KEYWORDS)\n"):
            self.assertEqual(self.scan(body), set())
        source = "dict: object\ndef added():\n    dict.clear(KEYWORDS)\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        source = "def outer():\n    dict = Worker\n    def inner():\n        global dict\n        dict.clear(KEYWORDS)\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        source = "list = []\ndef added():\n    list.append(KEYWORDS)\n"
        self.assertEqual(self.scan(source), {("probe.list", "probe.added", "list")})

    def test_later_builtin_imports_in_nested_bodies(self):
        source = "def outer():\n    def inner():\n        D.clear(KEYWORDS)\n    from builtins import dict as D\n    inner()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        self.assertEqual(self.scan(source + "    D = Worker\n"),
                         {("lexer.KEYWORDS", "probe.outer.inner", "KEYWORDS")})
        source = "def outer():\n    class C:\n        def method(self):\n            D.clear(KEYWORDS)\n    from builtins import dict as D\n    C().method()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.outer.C.method", "KEYWORDS")})
        source = "def added():\n    D.clear(KEYWORDS)\n    from builtins import dict as D\n"
        self.assertEqual(self.scan(source), set())

    def test_inplace_and_reinitializing_mutator_calls(self):
        forms = (("list", "[]", "__iadd__", "[]"), ("list", "[]", "__imul__", "2"),
                 ("dict", "{}", "__ior__", "{}"), ("set", "set()", "__ior__", "set()"),
                 ("set", "set()", "__iand__", "set()"), ("set", "set()", "__ixor__", "set()"),
                 ("set", "set()", "__isub__", "set()"), ("dict", "{}", "__init__", "{}"))
        for owner, initial, method, value in forms:
            for operation in (f"CACHE.{method}({value})", f"{owner}.{method}(CACHE, {value})"):
                sources = {"probe": f"CACHE = {initial}\ndef added():\n    {operation}\n"}
                trees, found, bindings = inventory(sources)
                self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found),
                                 {("probe.CACHE", "probe.added", "CACHE")})

    def test_union_declaration_and_unbound_writer_full_source(self):
        sources = read_sources()
        sources["lexer"] += "\nNEW_CACHE: dict[str, bool] | None = factory()\ndef added_writer():\n    dict.clear(NEW_CACHE)\n"
        self.assertEqual(validate_sources(sources), [
            "unclassified module container: lexer.NEW_CACHE",
            "unreviewed container writer: lexer.added_writer writes lexer.NEW_CACHE via NEW_CACHE",
        ])
        sources = read_sources()
        sources["lexer"] += "\ndef added_writer():\n    dict.clear(KEYWORDS)\n"
        self.assertEqual(validate_sources(sources), [
            "unreviewed container writer: lexer.added_writer writes lexer.KEYWORDS via KEYWORDS",
        ])

    def test_annotation_only_does_not_declare_containers(self):
        for annotation in ("list[str]", "'dict[str, bool]'", "Optional[set[str]]",
                           "Annotated[list[int], 'meta']"):
            sources = {"probe": "from typing import Optional, Annotated\n" + f"CACHE: {annotation}\n"}
            self.assertEqual(inventory(sources)[1], set())
            sources["probe"] += "CACHE = []\n"
            self.assertEqual(inventory(sources)[1], {"probe.CACHE"})

    def test_annotation_only_preserves_existing_origins(self):
        sources = {"probe": "from src.pystachy_compiler.lexer import KEYWORDS as CACHE\n"
                   "CACHE: dict[str, bool]\ndef added():\n    CACHE.clear()\n",
                   "lexer": "KEYWORDS = {}\n"}
        trees, found, bindings = inventory(sources)
        self.assertEqual(found, {"lexer.KEYWORDS"})
        self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found, bindings),
                         {("lexer.KEYWORDS", "probe.added", "CACHE")})
        source = "class C:\n    alias = KEYWORDS\n    alias: dict\n    def method(self, table=alias):\n        table.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.C.method", "table")})

    def test_annotation_only_is_not_a_store_but_shadows_locals(self):
        for body in ("def added():\n    KEYWORDS: dict\n    KEYWORDS.clear()\n",
                     "def added():\n    KEYWORDS['new']: list\n"):
            self.assertEqual(self.scan(body), set())
        source = "def added():\n    KEYWORDS[KEYWORDS.clear()]: list\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})
        source = "def added():\n    lex.KEYWORDS: dict\n"
        self.assertEqual(self.scan(source, "from src.pystachy_compiler import lexer as lex\n"), set())
        source = "def added():\n    (KEYWORDS): dict\n    KEYWORDS.clear()\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "KEYWORDS")})

    def test_function_annotations_keep_lexical_shadows_without_runtime_aliases(self):
        for body in ("local: KEYWORDS.clear()", "local: (alias := KEYWORDS)\n    alias.clear()",
                     "local: (KEYWORDS := {})\n    KEYWORDS.clear()"):
            self.assertEqual(self.scan("def added():\n    " + body + "\n"), set())
        source = "def added():\n    KEYWORDS[(alias := KEYWORDS).clear()]: list\n"
        self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "alias")})

    def test_annotation_only_full_source(self):
        sources = read_sources()
        sources["lexer"] += "\nCACHE: list[str]\nKEYWORDS: dict[str, bool]\n"
        self.assertEqual(validate_sources(sources), [])
        sources["lexer"] += "\nCACHE = []\ndef added_writer():\n    CACHE.clear()\n"
        self.assertEqual(validate_sources(sources), [
            "unclassified module container: lexer.CACHE",
            "unreviewed container writer: lexer.added_writer writes lexer.CACHE via CACHE",
        ])

    def test_separate_annotation_and_initialization(self):
        for annotation in ("list[str]", "'dict[str, bool]'", "Optional[set[str]]",
                           "Annotated[list[int], 'meta']"):
            declaration = "from typing import Optional, Annotated\n" + f"CACHE: {annotation}\n"
            self.assertEqual(inventory({"probe": declaration})[1], set())
            for assignment in ("CACHE = factory()", "CACHE, other = factory(), 1"):
                self.assertEqual(inventory({"probe": declaration + assignment + "\n"})[1], {"probe.CACHE"})

    def test_separate_annotation_uses_declaration_bindings(self):
        for source, expected in (
            ("CACHE: list\nlist = factory\nCACHE = factory()\n", {"probe.CACHE"}),
            ("list = factory\nCACHE: list\nCACHE = factory()\n", set()),
            ("CACHE: list\nCACHE: int\nCACHE = factory()\n", set()),
            ("from typing import List as L\nCACHE: L[str]\nL = object\nCACHE = factory()\n", {"probe.CACHE"}),
            ("CACHE: list\ndel CACHE\n", set()),
            ("CACHE = 0\nCACHE: list\n", set()),
        ):
            with self.subTest(source=source):
                self.assertEqual(inventory({"probe": source})[1], expected)

    def test_separate_annotation_full_source(self):
        sources = read_sources()
        sources["lexer"] += "\nCACHE: dict[str, bool]\nCACHE = factory()\ndef added_writer():\n    CACHE.clear()\n"
        self.assertEqual(validate_sources(sources), [
            "unclassified module container: lexer.CACHE",
            "unreviewed container writer: lexer.added_writer writes lexer.CACHE via CACHE",
        ])

    def test_annotation_import_order(self):
        sources = (
            ("from typing import Annotated as A\nCACHE: A[list[int], 'meta'] = factory()\nfrom other import A\n", True),
            ("CACHE: list[int] = factory()\nfrom other import list\n", True),
            ("from other import A\nCACHE: A[list[int], 'meta'] = factory()\nfrom typing import Annotated as A\n", False),
        )
        for source, expected in sources:
            self.assertEqual("probe.CACHE" in inventory({"probe": source})[1], expected)

    def test_inventory_constructor_shadows(self):
        for name in ("list", "dict", "set"):
            for binding in (f"def {name}(): return 1", f"class {name}: pass",
                            f"{name} = lambda: 1", f"{name}: object = lambda: 1",
                            f"({name}, other) = (factory, None)"):
                with self.subTest(binding=binding):
                    source = binding + f"\nCACHE = {name}()\n"
                    self.assertEqual(inventory({"probe": source})[1], set())
            source = f"{name} = {name}()\n"
            self.assertEqual(inventory({"probe": source})[1], {f"probe.{name}"})
            for source in (f"{name} = (CACHE := {name}())\n", f"CACHE = ({name} := {name}())\n"):
                self.assertEqual(inventory({"probe": source})[1], {f"probe.{name}", "probe.CACHE"})
            source = f"{name}: object\nCACHE = {name}()\n"
            self.assertEqual(inventory({"probe": source})[1], {"probe.CACHE"})
            source = f"def {name}(value=(CACHE := {name}())): return value\nAFTER = {name}()\n"
            self.assertEqual(inventory({"probe": source})[1], {"probe.CACHE"})

    def test_inventory_annotation_alias_shadows_and_restores(self):
        for prefix, binding, annotation in (
            ("from typing import List as L", "L = object", "L[int]"),
            ("import typing as t", "t = unrelated", "t.List[int]"),
            ("from typing import Annotated as A", "def A(): pass", "A[list, 'meta']"),
            ("import builtins as b", "b.list = factory", "b.list"),
        ):
            source = f"{prefix}\n{binding}\nCACHE: {annotation} = factory()\n"
            self.assertEqual(inventory({"probe": source})[1], set())
        source = "list = factory\nfrom builtins import list\nCACHE = list()\n"
        self.assertEqual(inventory({"probe": source})[1], {"probe.CACHE"})
        source = "from typing import List as L\nL = object\nfrom typing import List as L\nCACHE: L[int] = factory()\n"
        self.assertEqual(inventory({"probe": source})[1], {"probe.CACHE"})

    def test_inventory_constructor_shadow_full_source(self):
        sources = read_sources()
        sources["probe"] = "def list(): return 1\nCACHE = list()\n"
        self.assertEqual(validate_sources(sources), [])

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

    def test_conditional_alias_origins(self):
        for expression in ("KEYWORDS if enabled else OPS", "KEYWORDS or OPS",
                           "(KEYWORDS if enabled else {}) or OPS"):
            for body in (f"def added():\n    alias = {expression}\n    alias.clear()\n",
                         f"def added(alias=({expression})):\n    alias.clear()\n",
                         f"def added():\n    ({expression})['nested'].clear()\n",
                         f"def added():\n    ({expression})['bad'] = 0\n"):
                with self.subTest(expression=expression, body=body):
                    sources = {"probe": "from src.pystachy_compiler.lexer import KEYWORDS, OPS\n" + body,
                               "lexer": "KEYWORDS = {}\nOPS = {}\n"}
                    trees, found, bindings = inventory(sources)
                    actual = writes(trees["probe"], "probe", bindings["probe"], found)
                    self.assertEqual({(origin, owner) for origin, owner, alias in actual},
                                     {("lexer.KEYWORDS", "probe.added"), ("lexer.OPS", "probe.added")})
        for expression in ("{} if KEYWORDS else {}", "dict(KEYWORDS) or {}",
                           "dict(KEYWORDS) if enabled else []"):
            self.assertEqual(self.scan(f"def added(alias=({expression})):\n    alias.clear()\n"), set())
            self.assertEqual(self.scan(f"def added():\n    alias = {expression}\n    alias.clear()\n"), set())

    def test_starred_unpack_declarations(self):
        for assignment in ("HEAD, *CACHE = [0, 1, 2]", "*CACHE, TAIL = (1, 2, 3)",
                           "HEAD, *CACHE, TAIL = factory()", "HEAD, (*CACHE,) = factory()",
                           "*(HEAD, *CACHE), = factory()", "*CACHE, = []",
                           "for HEAD, *CACHE in rows:\n    pass",
                           "with context() as (HEAD, *CACHE):\n    pass"):
            with self.subTest(assignment=assignment):
                self.assertEqual(inventory({"probe": assignment + "\n"})[1], {"probe.CACHE"})
        for assignment in ("HEAD, TAIL = factory()", "*(HEAD, TAIL), = [1, 2]",
                           "*[HEAD, TAIL], = factory()"):
            self.assertEqual(inventory({"probe": assignment + "\n"})[1], set())

    def test_starred_unpack_preserves_literal_outer_aliases(self):
        for assignment in ("left, *fresh, right = [KEYWORDS, 0, KEYWORDS]",
                           "left, *fresh, right = (KEYWORDS, KEYWORDS)"):
            source = "def added():\n    " + assignment + "\n    left.clear()\n    right.clear()\n    fresh.clear()\n"
            self.assertEqual(self.scan(source), {("lexer.KEYWORDS", "probe.added", "left"),
                                                ("lexer.KEYWORDS", "probe.added", "right")})
        for assignment in ("*fresh, = KEYWORDS", "left, *fresh, right = factory(KEYWORDS)",
                           "left, *fresh, right = [*KEYWORDS]"):
            source = "def added():\n    " + assignment + "\n    fresh.clear()\n"
            self.assertEqual(self.scan(source), set())

    def test_new_conditional_alias_and_starred_writer_controls(self):
        sources = read_sources()
        sources["lexer"] += "\ndef added_writer():\n    alias = KEYWORDS if enabled else OPS\n    alias.clear()\n"
        self.assertEqual(validate_sources(sources), [
            "unreviewed container writer: lexer.added_writer writes lexer.KEYWORDS via alias",
            "unreviewed container writer: lexer.added_writer writes lexer.OPS via alias",
        ])
        for assignment in ("HEAD, *NEW_CACHE = [0, 1, 2]", "HEAD, *NEW_CACHE = factory()"):
            sources = read_sources()
            sources["lexer"] += "\n" + assignment + "\ndef added_writer():\n    NEW_CACHE.clear()\n"
            self.assertEqual(validate_sources(sources), [
                "unclassified module container: lexer.NEW_CACHE",
                "unreviewed container writer: lexer.added_writer writes lexer.NEW_CACHE via NEW_CACHE",
            ])

    def test_module_subscript_alias_origins_without_new_declarations(self):
        for expression, origins in (("KEYWORDS['cache']", {"lexer.KEYWORDS"}),
                                    ("(KEYWORDS if enabled else OPS)['cache']", {"lexer.KEYWORDS", "lexer.OPS"})):
            sources = {"probe": "from src.pystachy_compiler.lexer import KEYWORDS, OPS\n"
                       + f"CACHE = {expression}\nALIAS = CACHE\ndef added():\n    ALIAS.clear()\n",
                       "lexer": "KEYWORDS = {'cache': {}}\nOPS = {'cache': {}}\n"}
            trees, found, bindings = inventory(sources)
            self.assertEqual(found, {"lexer.KEYWORDS", "lexer.OPS"})
            self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found),
                             {(origin, "probe.added", "ALIAS") for origin in origins})
        sources = {"probe": "TABLE = {'count': 1}\nCOUNT = TABLE['count']\nCOPY = COUNT\ndef read():\n    return COPY\n"}
        trees, found, bindings = inventory(sources)
        self.assertEqual(found, {"probe.TABLE"})
        self.assertEqual(writes(trees["probe"], "probe", bindings["probe"], found), set())
        sources = {"probe": "TABLE = {'cache': {}}\nCACHE: dict = TABLE['cache']\n"}
        self.assertEqual(inventory(sources)[1], {"probe.TABLE", "probe.CACHE"})

    def test_reexported_container_imports(self):
        forms = (
            "from src.pystachy_compiler.bridge import public as table\ndef added():\n    table.clear()\n",
            "from src.pystachy_compiler import bridge as b\ndef added():\n    b.public.clear()\n",
            "def added():\n    from src.pystachy_compiler.bridge import public as table\n    table.clear()\n",
            "def added():\n    import src.pystachy_compiler.bridge as b\n    b.public.clear()\n",
        )
        for consumer in forms:
            sources = {"consumer": consumer,
                       "bridge": "from src.pystachy_compiler.lexer import KEYWORDS as public\n",
                       "lexer": "KEYWORDS = {}\n"}
            for ordered in (sources, dict(reversed(list(sources.items())))):
                errors = validate_sources(ordered)
                self.assertTrue(any("consumer.added writes lexer.KEYWORDS" in error for error in errors))
                self.assertFalse(any("unclassified module container: bridge." in error for error in errors))

    def test_reexport_cycles_do_not_invent_containers(self):
        sources = {"a": "from src.pystachy_compiler.b import TABLE\n",
                   "b": "from src.pystachy_compiler.a import TABLE\n"}
        self.assertEqual(inventory(sources)[1], set())
        sources["a"] += "from src.pystachy_compiler.origin import TABLE\n"
        sources["origin"] = "TABLE = {}\n"
        sources["consumer"] = "from src.pystachy_compiler.b import TABLE\ndef added():\n    TABLE.clear()\n"
        self.assertTrue(any("consumer.added writes origin.TABLE" in error for error in validate_sources(sources)))

    def test_module_alias_reexport_cycles_are_bounded(self):
        sources = {"a": "from src.pystachy_compiler.origin import TABLE\nfrom src.pystachy_compiler import b as B\n",
                   "b": "from src.pystachy_compiler import a as A\n",
                   "origin": "TABLE = {}\n",
                   "consumer": "from src.pystachy_compiler import a\ndef added():\n    a.B.A.TABLE.clear()\n"}
        for ordered in (sources, dict(reversed(list(sources.items())))):
            trees, found, bindings = inventory(ordered)
            self.assertEqual(writes(trees["consumer"], "consumer", bindings["consumer"], found, bindings),
                             {("origin.TABLE", "consumer.added", "a.B.A.TABLE")})
            self.assertTrue(all(len(name.split(".")) <= 5 for names in bindings.values() for name in names))

    def test_swapping_reexport_cycle_converges(self):
        sources = {"origin": "ONE = {}\nTWO = {}\n",
                   "a": "from src.pystachy_compiler.origin import ONE as X, TWO as Y\nfrom src.pystachy_compiler.b import X as Y, Y as X\n",
                   "b": "from src.pystachy_compiler.a import X, Y\n",
                   "consumer": "from src.pystachy_compiler.a import X, Y\ndef added():\n    X.clear()\n    Y.clear()\n"}
        script = "from compiler_state_globals import inventory, writes\n" + f"sources = {sources!r}\n" + """
for ordered in (sources, dict(reversed(list(sources.items())))):
    trees, found, bindings = inventory(ordered)
    assert found == {"origin.ONE", "origin.TWO"}
    expected = {(origin, "consumer.added", alias) for origin in found for alias in ("X", "Y")}
    assert writes(trees["consumer"], "consumer", bindings["consumer"], found, bindings) == expected
"""
        subprocess.run([sys.executable, "-c", script], cwd=ROOT / "tools", check=True,
                       capture_output=True, text=True, timeout=5)

    def test_module_subscript_and_reexport_full_source_controls(self):
        sources = read_sources()
        sources["lexer"] += "\nNEW_CACHE = KEYWORDS['cache']\ndef added_writer():\n    NEW_CACHE.clear()\n"
        self.assertEqual(validate_sources(sources), [
            "unreviewed container writer: lexer.added_writer writes lexer.KEYWORDS via NEW_CACHE",
        ])
        sources = read_sources()
        sources["bridge"] = "from src.pystachy_compiler.lexer import KEYWORDS\n"
        sources["consumer"] = "def added_writer():\n    from src.pystachy_compiler.bridge import KEYWORDS\n    KEYWORDS.clear()\n"
        self.assertEqual(validate_sources(sources), [
            "unreviewed container writer: consumer.added_writer writes lexer.KEYWORDS via KEYWORDS",
        ])

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
