"""Generated-code cost guard for already-materialized numeric list identities."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLANG = shutil.which(str(Path(os.environ["PYSTACHY_LLVM"]) / "clang") if os.environ.get("PYSTACHY_LLVM") else "clang")
CONSUMERS = ("pys_list_get_identity", "pys_list_append_identity", "pys_list_set_identity")
LABEL = r"[-a-zA-Z$._0-9]+"


def blocks(ir, name):
    match = re.search(r"^define[^\n]*@" + re.escape(name) + r"\([^\n]*\{\n(.*?)^}", ir, re.M | re.S)
    if match is None:
        raise AssertionError(f"missing runtime definition: {name}")
    result = {}
    current = "entry"
    for raw in match[1].splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        label = re.fullmatch("(" + LABEL + "):", line)
        if label:
            current = label[1]
        else:
            result.setdefault(current, []).append(line)
    if not result:
        raise AssertionError(f"empty runtime definition: {name}")
    return result


def reachable(ir, name, call_free=False):
    cfg = blocks(ir, name)
    pending = [next(iter(cfg))]
    seen = set()
    while pending:
        label = pending.pop()
        if label in seen:
            continue
        if label not in cfg:
            raise AssertionError(f"missing block {label} in {name}")
        seen.add(label)
        code = "\n".join(cfg[label])
        if call_free and re.search(r"\b(?:call|invoke|callbr)\b", code):
            continue
        yield code
        pending.extend(re.findall(r"\blabel %(" + LABEL + ")", code))


def returns_without_calls(ir, name):
    return any(re.search(r"^ret\b", code, re.M) for code in reachable(ir, name, call_free=True))


def reachable_callees(ir, name):
    return {callee for code in reachable(ir, name)
            for callee in re.findall(r"\b(?:call|invoke)\b[^\n]*@(" + LABEL + r")\(", code)}


class IdentityCostCheckerTests(unittest.TestCase):
    def test_only_reachable_call_free_returns_count(self):
        source = """define void @probe(i1 %clean) {
entry:
  br i1 %clean, label %fast, label %slow
fast:
  ret void
slow:
  call void @materialize()
  br label %fast
}
"""
        self.assertTrue(returns_without_calls(source, "probe"))
        self.assertEqual(reachable_callees(source, "probe"), {"materialize"})
        self.assertFalse(returns_without_calls(source.replace(
            "br i1 %clean, label %fast, label %slow", "br label %slow"), "probe"))
        self.assertFalse(returns_without_calls(source.replace(
            "fast:\n", "fast:\n  call void @unnecessary()\n"), "probe"))

    def test_missing_function_or_block_fails_closed(self):
        for source in ("", "define void @probe() {\nentry:\n  br label %missing\n}\n"):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                returns_without_calls(source, "probe")


@unittest.skipUnless(CLANG, "clang is required for the generated numeric-list cost guard")
class RuntimeListIdentityTests(unittest.TestCase):
    @classmethod
    def compile_runtime(cls, source):
        # Match the runtime's optimized C stage; naming SSA values affects only
        # readability. Compile the real source and its includes, without linking.
        result = subprocess.run([CLANG, "-O2", "-S", "-emit-llvm", "-x", "c", "-",
                                 "-I", str(ROOT), "-o", "-", "-fexceptions", "-fno-discard-value-names"],
                                input=source, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout

    @classmethod
    def setUpClass(cls):
        source = (ROOT / "runtime.c").read_text()
        declaration = "void pys_list_identity(List *l, I kind) {"
        if source.count(declaration) != 1:
            raise AssertionError("numeric-list identity wrapper definition not found exactly once")
        cls.optimized = cls.compile_runtime(source)
        # A real optimizer negative control: restore the mandatory nested call,
        # without weakening the runtime semantics or mocking emitted LLVM text.
        cls.noinline = cls.compile_runtime(source.replace(
            declaration, "__attribute__((noinline)) " + declaration, 1))

    def test_clean_reads_and_stores_need_no_runtime_call(self):
        for name in CONSUMERS:
            with self.subTest(name=name):
                self.assertTrue(returns_without_calls(self.optimized, name), name)
                self.assertIn("list_identity_slow", reachable_callees(self.optimized, name))
        # Missing/dirty companions still reach the allocating materializer.
        self.assertTrue(reachable_callees(self.optimized, "list_identity_slow"))

    def test_out_of_line_wrapper_is_detected(self):
        for name in CONSUMERS:
            with self.subTest(name=name):
                self.assertIn("pys_list_identity", reachable_callees(self.noinline, name))
                self.assertFalse(returns_without_calls(self.noinline, name), name)


if __name__ == "__main__":
    unittest.main()
