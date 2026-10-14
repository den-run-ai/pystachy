"""Guard online callback specialization by identity, preserving live program state.

Run with the same native compiler settings as test_stream_online.py. Set
PYSTACHY_ONLINE_TEST_INLINE_RUNTIME=1 to test the runtime-inlining mode. These tests
exercise erased Callable values over strings, including stdlib bisect's key path;
closures and bound methods must remain generic even when they share code.
"""
import json
import os
import sys
import unittest

import test_stream_online as stream_tests


CALLBACKS = """
from typing import Callable

def hot_key(value: str) -> int:
    return len(value)

def cold_key(value: str) -> int:
    return len(value) + 7
"""
CALLS = """
def consume(key) -> int:
    return key("record")

def dispatch(key: Callable[[str], int]) -> int:
    return consume(key)
"""
MONOMORPHIC = "import sys\n" + CALLBACKS + CALLS + """
callbacks: list[Callable[[str], int]] = [hot_key, cold_key]
total = 0
for i in range(int(sys.argv[1])):
    total += dispatch(callbacks[0])
print(total)
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "online tier currently supports Linux AOT")
class CallbackOnlineTests(unittest.TestCase):
    # Reuse harness operations without inheriting or importing a TestCase class,
    # which would cause unittest discovery to execute the stream suite twice.
    write = stream_tests.StreamOnlineTests.write
    build = stream_tests.StreamOnlineTests.build
    expected = stream_tests.StreamOnlineTests.expected
    run_program = stream_tests.StreamOnlineTests.run_program
    row = stream_tests.StreamOnlineTests.row
    installed = stream_tests.StreamOnlineTests.installed
    wrapper = stream_tests.StreamOnlineTests.wrapper

    def setUp(self):
        stream_tests.StreamOnlineTests.setUp(self)
        # Callable identity specialization must work without reference unions.
        self.env.pop("PYSTACHY_CLOSED_UNIONS", None)
        self.env.pop("PYSTACHY_REFERENCE_UNIONS", None)
        self.env["PYSTACHY_ONLINE_INLINE_RUNTIME"] = os.environ.get(
            "PYSTACHY_ONLINE_TEST_INLINE_RUNTIME", "0")

    def test_threshold_compiles_once_in_the_live_process(self):
        self.write("import os\nimport sys\n" + CALLBACKS + """
seen: list[str] = []
def consume(key) -> int:
    seen.append("record")
    return key(seen[-1])
def dispatch(key: Callable[[str], int]) -> int:
    return consume(key)
pid = os.getpid()
with open("host-pid.txt", "w") as output:
    output.write(str(pid))
callbacks: list[Callable[[str], int]] = [hot_key, cold_key]
total = 0
for i in range(int(sys.argv[1])):
    with open("completed.txt", "w") as output:
        output.write(str(len(seen)))
    total += dispatch(callbacks[0])
print(total, len(seen), os.getpid() == pid)
""")
        wrapper = self.wrapper()
        self.build(compiler=wrapper)
        self.assertEqual(self.run_program(99, compiler=wrapper), "594 99 True\n")
        before = self.row()
        self.assertEqual((before["calls"], before["attempts"], before["hits"]), (99, 0, 0))
        self.assertFalse(self.log.exists(), "compiler ran below the threshold")
        self.assertEqual(self.run_program(105, compiler=wrapper), "630 105 True\n")
        row = self.installed(105, 6)
        entries = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["completed"], "99", "the trigger body must execute once after compilation")
        self.assertEqual(entry["pid"], row["compiler_pid"])
        self.assertEqual(entry["parent_pid"], int((self.directory / "host-pid.txt").read_text()))
        self.assertEqual(entry["argv"][0], "trace")

    def test_balanced_callback_identities_do_not_compile(self):
        self.write(MONOMORPHIC.replace("dispatch(callbacks[0])", "dispatch(callbacks[i % 2])"))
        self.build()
        self.assertEqual(self.run_program(120), self.expected(120))
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (120, 0, 0, 0))

    def test_changed_callbacks_closure_environments_and_bound_methods_fall_back(self):
        self.write(CALLBACKS + CALLS + """
def factory(suffix: str) -> Callable[[str], int]:
    def key(value: str) -> int:
        return len(value + suffix)
    return key
class Key:
    def __init__(self, suffix: str) -> None:
        self.suffix = suffix
    def read(self, value: str) -> int:
        return len(value + self.suffix)
instance = Key("bound")
callbacks: list[Callable[[str], int]] = [hot_key, cold_key, factory("a"), factory("different"), instance.read]
total = 0
for i in range(113):
    index = 0 if i < 100 or i == 112 else 1 if i < 104 else 2 if i < 108 else 3 if i < 111 else 4
    total += dispatch(callbacks[index])
print(total)
print(dispatch(callbacks[2]), dispatch(callbacks[3]), dispatch(callbacks[4]))
""")
        self.build()
        self.assertEqual(self.run_program(stress=True), self.expected())
        self.installed(116, 2)

    def test_unknown_closures_do_not_trigger_specialization(self):
        self.write("from typing import Callable\n" + CALLS + """
def factory(suffix: str) -> Callable[[str], int]:
    def key(value: str) -> int:
        return len(value + suffix)
    return key
callbacks: list[Callable[[str], int]] = [factory("first"), factory("second")]
total = 0
for i in range(120):
    total += dispatch(callbacks[0 if i < 110 else 1])
print(total)
""")
        self.build()
        self.assertEqual(self.run_program(stress=True), self.expected())
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (120, 0, 0, 0))

    def test_generic_callback_retains_its_callable_argument_contract(self):
        self.write("""
from typing import Callable
def hot(value) -> int:
    values = [value]
    values.append(None)
    return len(values)
def consume(key) -> int:
    return key(1)
def dispatch(key: Callable[[int | None], int]) -> int:
    return consume(key)
callbacks: list[Callable[[int | None], int]] = [hot]
total = 0
for i in range(120):
    total += dispatch(callbacks[0])
print(total)
""")
        # The Callable adapter passes Optional[int], so hot's inferred list
        # accepts None. A raw direct call would instantiate hot(int) and narrow
        # that mutable contract. Such callbacks must remain on their adapter.
        self.build()
        self.assertEqual(self.run_program(stress=True), self.expected())
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (120, 0, 0, 0))

    def test_global_effects_and_exceptions_never_replay(self):
        self.write("from typing import Callable\n" + """
evaluations = 0
fail = False
seen: list[str] = []
callback_calls = 0
def hot_key(value: str) -> int:
    global callback_calls
    callback_calls += 1
    if fail:
        raise ValueError("hot")
    return len(value)
def cold_key(value: str) -> int:
    global callback_calls
    callback_calls += 1
    raise ValueError("cold")
def argument(key: Callable[[str], int]) -> Callable[[str], int]:
    global evaluations
    evaluations += 1
    return key
def consume(key) -> int:
    seen.append("record" + str(len(seen)))
    return key(seen[-1])
def dispatch(key: Callable[[str], int]) -> int:
    return consume(argument(key))
callbacks: list[Callable[[str], int]] = [hot_key, cold_key]
total = 0
caught = 0
finished = 0
for i in range(106):
    fail = i == 99 or i == 103
    try:
        total += dispatch(callbacks[0 if i < 105 else 1])
    except ValueError as error:
        print("caught", error)
        caught += 1
    finally:
        finished += 1
print(total, len(seen), callback_calls, evaluations, caught, finished)
print(seen[99], seen[103], seen[105])
""")
        self.build()
        self.assertEqual(self.run_program(stress=True), self.expected())
        self.installed(106, 6)

    def test_callback_discovered_in_later_function_body_is_registered(self):
        self.write(CALLBACKS + CALLS + """
def later() -> Callable[[str], int]:
    return hot_key
callbacks: list[Callable[[str], int]] = [cold_key]
# Compile the selected call site before later() materializes hot_key's Callable.
print(dispatch(callbacks[0]))
callbacks[0] = later()
total = 0
for i in range(105):
    total += dispatch(callbacks[0])
print(total)
""")
        self.build()
        self.assertEqual(self.run_program(), self.expected())
        self.installed(106, 7)

    def test_changed_callback_registry_rejects_the_child(self):
        self.write(MONOMORPHIC)
        expected = self.expected(105)
        self.build()
        # Keep the Callable signature and object layout but replace the named
        # singleton. An old host must not accept this source's callback registry.
        self.write(MONOMORPHIC.replace("hot_key", "renamed_hot_key"))
        self.assertEqual(self.run_program(105), expected)
        row = self.row()
        self.assertEqual((row["calls"], row["attempts"], row["installs"], row["hits"]), (105, 1, 0, 0))
        self.assertNotIn(row["failure"], ["", "0", "none", "ok", "-"])

    def test_inline_runtime_hot_operations_keep_host_exception_paths(self):
        self.write("""
from typing import Callable
items: list[str] = ["record"]
position = 0
numerator = 24
denominator = 2
callback_calls = 0
def hot_key(value: str) -> int:
    global callback_calls
    callback_calls += 1
    return len(value)
def consume(key) -> int:
    return key(items[position]) + numerator // denominator
def dispatch(key: Callable[[str], int]) -> int:
    return consume(key)
callbacks: list[Callable[[str], int]] = [hot_key]
for i in range(100):
    if dispatch(callbacks[0]) != 18:
        raise RuntimeError("incorrect warmup")
for case in range(7):
    position = -1 if case == 0 else 1 if case == 1 else 0
    numerator = -9223372036854775808 if case == 3 else -23 if case == 6 else 23
    denominator = 0 if case == 2 else -1 if case == 3 or case == 4 else -5 if case == 5 else 5
    try:
        print("result", dispatch(callbacks[0]))
    except IndexError as error:
        print("index", str(error))
    except ZeroDivisionError as error:
        print("zero", str(error))
    except OverflowError as error:
        print("overflow", str(error))
print("callbacks", callback_calls)
""")
        self.build()
        self.assertEqual(self.run_program(stress=True),
                         "result 10\nindex list index out of range\n"
                         "zero integer division or modulo by zero\n"
                         "overflow integer result does not fit in 64 bits\n"
                         "result -17\nresult 1\nresult 1\ncallbacks 106\n")
        self.installed(107, 8)

    def test_unmodified_bisect_key_path_matches_exact_cpython_positions(self):
        self.write("from bisect import bisect_left, bisect_right\n" + CALLBACKS + """
records: list[str] = ["", "", "a", "bb", "cc", "ddd", "eeee", "ffff", "ggggg", "hhhhhhh", "iiiiiiiiiii"]
queries: list[int] = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12]
positions: list[int] = []
def alternate_key(value: str) -> int:
    return len(value + "")
def consume(key) -> int:
    total = 0
    for query in queries:
        left = bisect_left(records, query, key=key)
        right = bisect_right(records, query, key=key)
        positions.append(left)
        positions.append(right)
        total += left + right
    return total
def dispatch(key: Callable[[str], int]) -> int:
    return consume(key)
callbacks: list[Callable[[str], int]] = [hot_key, alternate_key]
total = 0
for i in range(110):
    positions.clear()
    total += dispatch(callbacks[0 if i < 105 or i % 2 == 0 else 1])
    print(positions)
print(total)
""")
        expected = self.expected()
        self.build()
        self.assertEqual(self.run_program(stress=True), expected)
        self.installed(110, 8)


if __name__ == "__main__":
    unittest.main()
