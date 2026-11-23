"""wasm/spill_roots.py on small modules: what the linear-memory stack holds during a call.

usage: python3 -m unittest discover -s tools -p test_wasm_spill_roots.py   (the engine checks need node)

Each module imports env.scan, which counts the words of the linear-memory stack, from
__stack_pointer to its top, that equal MAGIC: what the collector's scan would find while the
function calls it. The functions keep MAGIC in a local or on the operand stack across that call.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("spill_roots", ROOT / "wasm" / "spill_roots.py")
spill_roots = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spill_roots)

I32, I64 = 0x7F, 0x7E
MAGIC = 0x5EED5EED
TOP = 65536


def uleb(v: int) -> bytes:
    out = bytearray()
    spill_roots.put_uleb(out, v)
    return bytes(out)


def sleb(v: int) -> bytes:
    out = bytearray()
    spill_roots.put_sleb(out, v)
    return bytes(out)


def vec(items: list) -> bytes:
    return uleb(len(items)) + b"".join(items)


def name(s: str) -> bytes:
    return uleb(len(s)) + s.encode()


def section(sid: int, payload: bytes) -> bytes:
    return bytes([sid]) + uleb(len(payload)) + payload


def functype(params: list, results: list) -> bytes:
    return b"\x60" + vec([bytes([t]) for t in params]) + vec([bytes([t]) for t in results])


def i32c(v: int) -> bytes:
    return b"\x41" + sleb(v if v < 1 << 31 else v - (1 << 32))


def i64c(v: int) -> bytes:
    return b"\x42" + sleb(v if v < 1 << 63 else v - (1 << 64))


def get(x: int) -> bytes:
    return b"\x20" + uleb(x)


def put(x: int) -> bytes:
    return b"\x21" + uleb(x)


# function indices: imports scan (0) and fd_close (1), then mark_roots (2), wasi_roots_spilled (3),
# helper (4, calls scan: reached through the table), raiser (5, calls scan, then traps, as pys_fail
# raises), then the tests
SCAN, FD_CLOSE, MARK, FLAG, HELPER, RAISER = 0, 1, 2, 3, 4, 5
TYPES = [functype([], []), functype([], [I32]), functype([I32], [I32]), functype([], [I32, I32])]
CALL_SCAN = b"\x10" + uleb(SCAN)


def module(tests: list) -> bytes:
    """tests: (name, type index, local types, body) exported under name"""
    funcs = [(0, [], b""), (1, [], i32c(0)), (1, [], CALL_SCAN), (0, [], CALL_SCAN + b"\x1a\x00")]
    funcs += [(t, ls, body) for _, t, ls, body in tests]
    imports = vec([name("env") + name("scan") + b"\x00" + uleb(1),
                   name("wasi_snapshot_preview1") + name("fd_close") + b"\x00" + uleb(2)])
    code = []
    for _, ls, body in funcs:
        locs = vec([uleb(1) + bytes([t]) for t in ls])
        code.append(uleb(len(locs) + len(body) + 1) + locs + body + b"\x0b")
    exports = [name("memory") + b"\x02\x00", name("sp") + b"\x03\x00"]
    for k in range(len(tests)):
        exports.append(name(tests[k][0]) + b"\x00" + uleb(2 + len(funcs) - len(tests) + k))
    exports.append(name(spill_roots.FLAG) + b"\x00" + uleb(FLAG))
    names = vec([uleb(MARK) + name(spill_roots.COLLECTOR), uleb(FLAG) + name(spill_roots.FLAG),
                 uleb(HELPER) + name("helper"), uleb(RAISER) + name("raiser")]
                + [uleb(2 + len(funcs) - len(tests) + k) + name(tests[k][0]) for k in range(len(tests))])
    return (b"\0asm\1\0\0\0" + section(1, vec(TYPES)) + section(2, imports)
            + section(3, vec([uleb(t) for t, _, _ in funcs]))
            + section(4, vec([b"\x70\x00\x01"])) + section(5, vec([b"\x00\x01"]))
            + section(6, vec([bytes([I32, 1]) + i32c(TOP) + b"\x0b"]))
            + section(7, vec(exports))
            + section(9, vec([b"\x00" + i32c(0) + b"\x0b" + vec([uleb(HELPER)])]))
            + section(10, vec(code))
            + section(0, name("name") + section(1, names) + section(7, vec([b"\x00" + name("__stack_pointer")]))))


# Each returns what scan found at the call the test is about.
TESTS = [
    # MAGIC in a local that is read after the call
    ("live_i32", 1, [I32, I32], i32c(MAGIC) + put(0) + CALL_SCAN + put(1) + get(0) + i32c(MAGIC) + b"\x6b" + get(1) + b"\x6a"),
    # MAGIC packed into the high half of an i64 local read after the call
    ("live_i64", 1, [I64, I32], i64c(MAGIC << 32 | 7) + put(0) + CALL_SCAN + put(1) + get(0) + b"\xa7" + i32c(7) + b"\x6b" + get(1) + b"\x6a"),
    # MAGIC only on the operand stack, under the call (its local is dead after the call)
    ("under_call", 1, [I32], i32c(MAGIC) + put(0) + get(0) + CALL_SCAN + b"\x6a" + i32c(MAGIC) + b"\x6b"),
    # MAGIC under the call's own argument (call_indirect's table index)
    ("under_args", 1, [I32], i32c(MAGIC) + put(0) + get(0) + i32c(0) + b"\x11" + uleb(1) + b"\x00" + b"\x6a" + i32c(MAGIC) + b"\x6b"),
    # MAGIC live across the first call, dead at the second: its slot is cleared by then
    ("dead_cleared", 1, [I32, I32], i32c(MAGIC) + put(0) + CALL_SCAN + get(0) + b"\x6a" + put(1) + CALL_SCAN),
    # MAGIC read only by the catch of a try around the call
    ("handler", 1, [I32], i32c(MAGIC) + put(0) + b"\x06\x7f" + CALL_SCAN + b"\x19" + get(0) + b"\x0b"),
    # MAGIC live across a call_indirect (to a function that calls scan)
    ("indirect", 1, [I32, I32], i32c(MAGIC) + put(0) + i32c(0) + b"\x11" + uleb(1) + b"\x00" + put(1) + get(0) + i32c(MAGIC) + b"\x6b" + get(1) + b"\x6a"),
    # a branch out of the function
    ("branch_out", 1, [I32], i32c(MAGIC) + put(0) + CALL_SCAN + get(0) + i32c(MAGIC) + b"\x6b" + b"\x6a" + b"\x0c\x00"),
    # an explicit return
    ("returns", 1, [I32], i32c(MAGIC) + put(0) + CALL_SCAN + get(0) + i32c(MAGIC) + b"\x6b" + b"\x6a" + b"\x0f"),
    # MAGIC read after a call that never returns once it has collected: no frame
    ("after_raise", 1, [I32], i32c(MAGIC) + put(0) + b"\x10" + uleb(RAISER) + get(0)),
    # MAGIC read by a catch around such a call: a frame
    ("caught_raise", 1, [I32], i32c(MAGIC) + put(0) + b"\x06\x7f" + b"\x10" + uleb(RAISER) + i32c(0)
     + b"\x19" + get(0) + b"\x0b"),
]

RUNNER = r"""
const fs = require("fs");
const [file, ...tests] = process.argv.slice(1);   // (node -e has no script path)
const MAGIC = 0x5eed5eed, TOP = 65536;
let mem, sp, last;   // last: what the latest scan found
const imports = {
  env: { scan() { const w = new Uint32Array(mem.buffer); let n = 0;
    for (let a = sp.value; a < TOP; a += 4) if (w[a >>> 2] === MAGIC) n++; return last = n; } },
  wasi_snapshot_preview1: { fd_close() { return 0; } },
};
const instance = new WebAssembly.Instance(new WebAssembly.Module(fs.readFileSync(file)), imports);
mem = instance.exports.memory; sp = instance.exports.sp;
const out = {flag: instance.exports.wasi_roots_spilled()};
for (const t of tests) {
  try { instance.exports[t](); } catch (e) { sp.value = TOP; }   // (raiser traps: no catch restores sp)
  out[t] = sp.value === TOP ? last : "sp " + sp.value;
}
console.log(JSON.stringify(out));
"""


def run(data: bytes) -> dict:
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "m.wasm")
        with open(path, "wb") as f:
            f.write(data)
        out = subprocess.run(["node", "-e", RUNNER, path] + [t[0] for t in TESTS],
                             capture_output=True, text=True, check=True)
        return json.loads(out.stdout)
    finally:
        shutil.rmtree(d)


@unittest.skipUnless(shutil.which("node"), "needs node")
class EngineTest(unittest.TestCase):
    def test_spilled_values_are_on_the_stack(self):
        got = run(spill_roots.rewrite(module(TESTS)))
        want = {"flag": 1, "live_i32": 1, "live_i64": 1, "under_call": 1, "under_args": 1,
                "dead_cleared": 0, "handler": 1, "indirect": 1, "branch_out": 1, "returns": 1,
                "after_raise": 0, "caught_raise": 1}
        self.assertEqual(got, want)

    def test_control(self):
        # without the pass (or with --no-spill), the stack holds none of them
        got = run(module(TESTS))
        self.assertEqual(got, {"flag": 0, **{t[0]: 0 for t in TESTS}})
        got = run(spill_roots.rewrite(module(TESTS), spill=False))
        self.assertEqual(got, {"flag": 1, **{t[0]: 0 for t in TESTS}})


def bodies(data: bytes) -> list:
    code = [p for s, p in spill_roots.Module(data).sections if s == 10][0]
    n, p = spill_roots.uleb(code, 0)
    out = []
    for _ in range(n):
        size, p = spill_roots.uleb(code, p)
        out.append(code[p:p + size])
        p += size
    return out


class StaticTest(unittest.TestCase):
    def test_calls_that_cannot_collect_are_left_alone(self):
        # a call to a WASI import needs no frame, nor does a call with nothing live
        body = i32c(MAGIC) + put(0) + i32c(3) + b"\x10" + uleb(FD_CLOSE) + get(0) + b"\x6a"
        data = module([("wasi_only", 1, [I32], body)])
        before = bodies(data)
        after = bodies(spill_roots.rewrite(data))
        self.assertEqual(after[-1], before[-1])
        self.assertEqual(after[MARK - 2], before[MARK - 2])
        self.assertEqual(after[FLAG - 2], b"\x00\x41\x01\x0b")
        self.assertEqual(after[HELPER - 2], before[HELPER - 2])   # it calls scan with nothing live

    def test_refusals(self):
        tail = ("tail", 1, [], b"\x12" + uleb(SCAN))
        with self.assertRaisesRegex(spill_roots.Unsupported, "tail call"):
            spill_roots.rewrite(module([tail]))
        crossing = ("crossing", 1, [], i32c(MAGIC) + b"\x02\x7f" + CALL_SCAN + b"\x0b" + b"\x6a")
        with self.assertRaisesRegex(spill_roots.Unsupported, "keeps a value on the stack"):
            spill_roots.rewrite(module([crossing]))
        simd = ("simd", 1, [], b"\xfd\x0c" + bytes(16) + b"\xfd\x1b\x00" + CALL_SCAN + b"\x6a")
        with self.assertRaisesRegex(spill_roots.Unsupported, "opcode 0xfd"):
            spill_roots.rewrite(module([simd]))

    def test_returning_collectors(self):
        # whether a call may collect and then return: wasm/check_no_collect.py's question
        data = module([("calls_raiser", 1, [], b"\x10" + uleb(RAISER) + i32c(0)),
                       ("calls_helper", 1, [], b"\x10" + uleb(HELPER)),
                       ("catches_raiser", 1, [], b"\x06\x40\x10" + uleb(RAISER) + b"\x19\x0b" + i32c(0)),
                       ("wasi_only", 1, [], i32c(3) + b"\x10" + uleb(FD_CLOSE))])
        self.assertEqual(spill_roots.returning_collectors(data),
                         {spill_roots.COLLECTOR: True, spill_roots.FLAG: False, "helper": True, "raiser": False,
                          "calls_raiser": False, "calls_helper": True, "catches_raiser": True, "wasi_only": False})


class NoCollectTest(unittest.TestCase):
    def test_check_names_each_wrong_entry(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from src.pystachy_compiler.utils import rtsym
        from wasm import check_no_collect
        from wasm.tir_wasm import RETURNS_UNCOLLECTED
        from wasm.wasi_abi import LIBC_WRAPPERS
        syms = [LIBC_WRAPPERS.get(rtsym(k), rtsym(k)) for k in RETURNS_UNCOLLECTED]
        collects = {sym: False for sym in syms}
        self.assertEqual(check_no_collect.wrong(collects), [])
        collects[syms[0]] = True
        del collects[syms[1]]
        self.assertEqual(check_no_collect.wrong(collects),
                         [f"{RETURNS_UNCOLLECTED[0]}: {syms[0]} may collect and then return",
                          f"{RETURNS_UNCOLLECTED[1]}: runtime.wasm has no function {syms[1]}"])


if __name__ == "__main__":
    unittest.main()
