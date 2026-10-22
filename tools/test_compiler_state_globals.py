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
        for annotation in ("list[int]", "dict[str, int]", "set[str]"):
            errors = validate_sources({"added": f"cache: {annotation} = factory()\n"})
            self.assertIn("unclassified module container: added.cache", errors)

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

    def scan(self, body, imports="from src.pystachy_compiler.lexer import KEYWORDS\n"):
        sources = {"probe": imports + body, "lexer": "KEYWORDS = {}\n"}
        trees, _, bindings = inventory(sources)
        return writes(trees["probe"], "probe", bindings["probe"])

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
