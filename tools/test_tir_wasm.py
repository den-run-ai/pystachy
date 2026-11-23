"""wasm/tir_wasm.py: a typed IR module's text to a WebAssembly module, refusing by name what it
does not lower (wasm/README.md). Node validates the module where it is installed."""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("tir_wasm", ROOT / "wasm" / "tir_wasm.py")
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)

HELLO = """module complete opts=[allocelide] {
  const @s.0 kind=string text=" "
  const @s.1 kind=string text="\\n"
  const @s.2 kind=string text="hello, world"
  const @s.5 kind=string text="integer result does not fit in 64 bits"
  const @s.6 kind=string text=OverflowError
  runtime ovf.smul
  runtime write
  runtime str.int
  runtime raise
}

function @main.init() -> None effects="R A I rF wF" name=<module> kind=block {
entry:
  ~%t2 %t3 %t4 = ovf * (int 6, int 7) : int
  check message="OverflowError: integer result does not fit in 64 bits" (bool %t4) -> L6
L6:
  rt entry=write (str @s.2, int 1) : None
  rt entry=write (str @s.0, int 1) : None
  %t7 = rt entry=str.int (int %t3) : str
  rt entry=write (str %t7, int 1) : None
  rt entry=write (str @s.1, int 1) : None
  ret
"":
  br -> L5
L5:
  raise exception=OverflowError (str @s.6, str @s.5)
cold "OverflowError: integer result does not fit in 64 bits" -> L5
}
"""


EXCEPTION = """module complete {
  class E base=Exception fields=[] exception=Exception
  const @x.E kind=exception refs=[@s.2 @s.2 @show @show null]
  const @s.2 kind=string text=E
}
function @main.init() -> None kind=block {
entry:
  ret
}
function @show(self: E) -> str kind=class {
entry:
  ret (str @s.2)
}
"""

def emit(text):
    return bytes(T.Emitter(T.parse(text)).module())


class TirWasm(unittest.TestCase):
    def test_object_dispatch_metadata_uses_ids_and_quoted_names(self):
        module = T.parse('module complete objects=["odd: name":1 C:0] compared=[C] hashed=["odd: name"] {\n'
                         '  class "odd: name"\n  class C\n}')
        self.assertEqual(module.objects, ["C", "odd: name"])
        self.assertEqual(module.compared, {"C": True})
        self.assertEqual(module.hashed, {"odd: name": True})

    def test_object_dispatch_metadata_rejects_ambiguous_rows(self):
        for attrs, reason in [
            ("objects=[C:0 C:1]", "duplicate class"),
            ("objects=[C:0 D:0]", "distinct and dense"),
            ("objects=[C:1]", "distinct and dense"),
            ("objects=[C:-1]", "invalid object dispatch ID"),
            ("objects=[C:0] objects=[D:0]", "duplicate module attribute"),
            ("objects=[C:0D:1]", "invalid separator"),
            ("objects=[E:0]", "unknown object dispatch class"),
            ("compared=[C]", "no object dispatch ID"),
            ("objects=[C:0] hashed=[D]", "no object dispatch ID"),
        ]:
            with self.subTest(attrs=attrs), self.assertRaisesRegex(T.Refused, reason):
                T.parse(f"module complete {attrs} {{\n  class C\n  class D\n}}")

    def test_module(self):
        out = emit(HELLO)
        self.assertEqual(out[:8], b"\x00asm\x01\x00\x00\x00")
        for name in (b"pys_write", b"pys_str_int", b"pys_raise", b"pystachy.data", b"init"):
            self.assertIn(name, out)
        # the strings' Str headers: byte length, hash 0, characters + 1, then the bytes
        self.assertIn((12).to_bytes(8, "little") + bytes(8) + (13).to_bytes(8, "little") + b"hello, world\x00", out)

    def test_bad_cfg_edges_are_named_refusals(self):
        valid = """module complete {
}
function @main.init() -> None kind=block {
entry:
  rt entry=recursion.enter -> next, cleanup : int
next:
  check key=check (bool 0) -> done
cleanup:
  br -> done
done:
  %t0 = phi (int 1, int 2) -> next, cleanup : int
  ret
cold check -> cleanup
}
"""
        # Exercise exactly the graph a suspension analysis or register packer receives.
        def validate(source):
            return T.parse(source).funcs[0].block_indices()
        self.assertEqual(validate(valid), {"entry": 0, "next": 1, "cleanup": 2, "done": 3})
        for before, after, reason in (
            ("-> next, cleanup :", "-> next, missing :", "unknown block missing"),
            ("br -> done", "br -> missing", "unknown block missing"),
            ("-> next, cleanup : int\n  ret", "-> missing, cleanup : int\n  ret", "from unknown block missing"),
            ("(int 1, int 2)", "(int 1)", "unequal input"),
            ("cold check -> cleanup", "cold other -> cleanup", "without a cold block"),
            ("cold check -> cleanup", "cold check -> missing", "unknown block missing"),
            ("cleanup:\n", "entry:\n", "duplicate block entry"),
        ):
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, reason):
                validate(valid.replace(before, after))

    def test_plain_generator_saves_values_and_refuses_cleanup(self):
        source = """module complete plain=[gen[int]] {
  const @name kind=string text=gen
}
function @main.init() -> None kind=block {
entry:
  ret
}
function @generator() -> gen[int] coroutine {
entry:
  gen.start (str @name) -> initial
initial:
  %t0 = scalar.bin add (int 4, int 5) : int
  ~%t1 ~%t2 = gen.yield (%slot %t0) -> final
final:
  ~%t3 ~%t4 = gen.ret (%slot 4)
}
"""
        self.assertIn(b"__indirect_function_table", emit(source))
        self.assertIn(b"__indirect_function_table", emit(source.replace("gen.ret (%slot 4)", "gen.ret (%slot %t0)")))
        for before, after, reason in (
            ("gen.ret (%slot 4)", "gen.ret (%slot %t1)", "untyped result of gen.yield"),
            ("gen.yield (", "gen.yield cleanup=1 (", "yield with cleanup"),
            ("-> final", "-> missing", "unknown block missing"),
        ):
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, reason):
                emit(source.replace(before, after))

    def test_counted_generator_drop_requires_a_cleanup_free_constructor(self):
        producer = """function @left() -> gen[int] coroutine {
entry:
  gen.start (str @name) -> first
first:
  ~%t0 ~%t1 = gen.yield (%slot 1) -> last
last:
  ~%t2 ~%t3 = gen.ret
}
"""
        consumer = """module complete {
  const @name kind=string text=g
}
function @main.init() -> None kind=block {
entry:
  %t0 = call callee=@left : gen[int]
  gen.drop (gen[int] %t0)
  ret
}
"""
        clean = consumer + producer
        self.assertIn(b"__indirect_function_table", emit(clean))
        forwarded = clean.replace("  gen.drop (gen[int] %t0)",
                                  "  %t1 = cast (gen[int] %t0) : gen[int]\n  gen.drop (gen[int] %t1)")
        with self.assertRaisesRegex(T.Refused, "counted generator drop"):
            emit(forwarded)

        # Even if a future emitter handles cleanup yields, a second producer of
        # the same handle type must not inherit the first one's simple drop.
        mixed = clean + producer.replace("@left", "@right").replace("gen.yield (", "gen.yield cleanup=1 (")
        T.check_generator_drops(T.parse(mixed))
        dirty = mixed.replace("call callee=@left", "call callee=@right")
        for source in (dirty, dirty.replace("module complete", "module complete plain=[gen[int]]")):
            with self.subTest(source=source), self.assertRaisesRegex(T.Refused, "counted generator drop"):
                T.check_generator_drops(T.parse(source))
        with self.assertRaisesRegex(T.Refused, "yield with cleanup"):
            emit(mixed)

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_generator_resumes_at_the_yielding_phi_predecessor(self):
        source = """module complete {
  global @seed type=int
  global @result type=float
  const @name kind=string text=gen
}
function @main.init() -> None kind=block {
entry:
  %t0 = mem.load (&int @seed) : int
  %t1 = call callee=@values (int %t0) : gen[int]
  gen.resume (gen[int] %t1)
  gen.resume (gen[int] %t1)
  ret
}
function @values(seed: int) -> gen[int] coroutine {
entry:
  %t0 = scalar.bin add (int %a0, int 3) : int
  gen.start (str @name) -> initial
initial:
  %t1 = num.cmp == (int %t0, int 4) : bool
  %t2 = num.cast (int %t0) : float
  cbr (bool %t1) -> yes, no
yes:
  %t3 = scalar.bin fadd (float %t2, float 0.25) : float
  ~%t4 ~%t5 = gen.yield (%slot 1) -> shared
no:
  %t6 = scalar.bin fsub (float %t2, float 0.5) : float
  ~%t7 ~%t8 = gen.yield (%slot 2) -> shared
shared:
  %t9 = phi (float %t3, float %t6) -> yes, no : float
  %t10 = phi (float 10.0, float 20.0) -> yes, no : float
  %t11 = scalar.bin fadd (float %t9, float %t10) : float
  mem.store (&float @result, float %t11)
  ~%t12 ~%t13 = gen.ret
}
"""
        script = """
const mod = new WebAssembly.Module(require("node:fs").readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({initial: 1});
const table = new WebAssembly.Table({initial: 1, element: "anyfunc"});
let heap = 4096;
const rt = {pys_recursion_state: 0, __indirect_function_table: table,
  pys_alloc(size) { const base = heap; heap += Number(size); return base; }};
const instance = new WebAssembly.Instance(mod, {env: {memory, data: 0}, rt});
const view = new DataView(memory.buffer);
for (const [seed, expected] of [[0n, 22.5], [1n, 14.25]]) {
  view.setBigInt64(Number(process.argv[2]), seed, true);
  instance.exports.init();
  require("node:assert/strict").equal(view.getFloat64(Number(process.argv[3]), true), expected);
}
"""
        emitter = T.Emitter(T.parse(source))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "generator.wasm"
            path.write_bytes(emitter.module())
            subprocess.run(["node", "-e", script, str(path), str(emitter.addr["@seed"]), str(emitter.addr["@result"])],
                           check=True, timeout=10)

    def test_legacy_container_header_allocation_is_refused(self):
        for kind, fields in (("list", 4), ("dict", 12)):
            prefix = " ".join(f'" {kind}.{k}":str' for k in range(fields))
            text = f"""module complete {{
  class C fields=[{prefix} tail:int]
}}
function @main.init() -> None kind=block {{
entry:
  %instance = alloc.fixed : C
  ret
}}
"""
            with self.subTest(kind=kind), self.assertRaisesRegex(T.Refused, "legacy container header of C"):
                emit(text)

    @unittest.skipUnless(shutil.which("node"), "node validates the module")
    def test_node_validates(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "hello.wasm"
            path.write_bytes(emit(HELLO))
            check = "new WebAssembly.Module(require('fs').readFileSync(process.argv[1]))"
            subprocess.run(["node", "-e", check, str(path)], check=True)

    def test_guest_root_frames_keep_live_references_across_collecting_calls(self):
        text = """module complete {
}
function @make() -> list[int] {
entry:
  %t0 = rt entry=list.new_atomic (int 3) : list[int]
  ret (list[int] %t0)
}
function @main.init() -> None kind=block {
entry:
  %t0 = call callee=@make : list[int]
  %t1 = call callee=@make : list[int]
  %t2 = rt entry=list.get (list[int] %t0, int 0) : *int
  %t3 = call callee=@make : list[int]
  rt entry=list.clear (list[int] %t1) : None
  ret
}
"""
        for roots, kept in ((True, [[], ["%t0"], [], ["%t1"], [], []]), (False, [[]] * 6)):
            with self.subTest(roots=roots):
                emitter = T.Emitter(T.parse(text), False, roots)
                out = emitter.module()
                self.assertEqual(b"pys_wasi_set_guest_roots" in out, roots)
                main = [fn for fn in emitter.funcs if fn.name == "@main.init"][0]
                # (list.get and list.clear collect only as they raise; the allocation's frame is empty)
                self.assertEqual([i.keep for i in main.blocks[0].code], kept)
                self.assertEqual(emitter.rooted, {"@make", "@main.init"})   # (both may allocate and return)

    def test_global_root_slots_are_pointer_typed_and_relocated(self):
        decls = "  global @n type=int\n  global @items type=list[int]\n  root @items"
        text = HELLO.replace("  runtime ovf.smul", decls + "\n  runtime ovf.smul")
        emitter = T.Emitter(T.parse(text))
        self.assertIn(b"pys_wasi_set_global_roots", emitter.module())
        self.assertIn(emitter.root_table, emitter.relocs)
        self.assertEqual(struct.unpack_from("<I", emitter.data, emitter.root_table)[0], emitter.addr["@items"])
        for name in ("@n", "@missing", "@items extra"):
            with self.subTest(name=name), self.assertRaisesRegex(T.Refused, "global root"):
                emit(text.replace("root @items", "root " + name))

    def test_constant_fields_and_float_slots(self):
        text = HELLO.replace('text="hello, world"', 'text=" items=(str @s.1)"')
        text = text.replace("  runtime ovf.smul", '  const @tc.0 kind=tuple items=(float "bitcast (i64 9218868437227405312 to double)", float "bitcast (i64 -4503599627370496 to double)")\n  runtime ovf.smul')
        module = T.Emitter(T.parse(text))
        module.lay_out_data()
        self.assertEqual(module.data[module.addr["@s.2"] + 24:][:17], b" items=(str @s.1)")
        self.assertEqual(module.data[module.addr["@tc.0"]:][:16], struct.pack("<dd", float("inf"), float("-inf")))

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_control_flow_and_packed_bool(self):
        # Each program records its result in its first (and only) global.
        preamble = """module complete {
  global @result type=int
}
function @main.init() -> None kind=block {
entry:
"""
        cases = [
            ("""  %t1 = slot.unpack (*bool 2) : bool
  cbr (bool %t1) -> yes, no
yes:
  mem.store (&int @result, int 1)
  ret
no:
  mem.store (&int @result, int 42)
  ret
""", False),
            ("""  %t0 = scalar.cast zext (%byte -1) : int
  %t1 = scalar.bin sub (int %t0, int 213) : int
  mem.store (&int @result, int %t1)
  ret
""", False),
            ("""  br -> next
next:
  %t0 = phi (int 0, int %t1) -> entry, next : int
  %t1 = scalar.bin add (int %t0, int 1) : int
  %t2 = num.cmp < (int %t1, int 42) : bool
  cbr (bool %t2) -> next, done
done:
  mem.store (&int @result, int %t1)
  ret
""", False),
            # (nested loops: the inner one's exit continues the outer one, 6 * 7 times in all)
            ("""  br -> outer
outer:
  %t0 = phi (int 0, int %t5) -> entry, step : int
  %t1 = phi (int 0, int %t7) -> entry, step : int
  br -> inner
inner:
  %t2 = phi (int 0, int %t4) -> outer, inner : int
  %t3 = phi (int %t1, int %t7) -> outer, inner : int
  %t7 = scalar.bin add (int %t3, int 1) : int
  %t4 = scalar.bin add (int %t2, int 1) : int
  %t8 = num.cmp < (int %t4, int 7) : bool
  cbr (bool %t8) -> inner, step
step:
  %t5 = scalar.bin add (int %t0, int 1) : int
  %t9 = num.cmp < (int %t5, int 6) : bool
  cbr (bool %t9) -> outer, done
done:
  mem.store (&int @result, int %t7)
  ret
""", False),
            # (two ways into one loop, which no structured loop can express: the dispatcher's)
            ("""  mem.store (&int @result, int 0)
  %t0 = slot.unpack (*bool 2) : bool
  cbr (bool %t0) -> a, b
a:
  %t1 = mem.load (&int @result) : int
  %t2 = scalar.bin add (int %t1, int 1) : int
  mem.store (&int @result, int %t2)
  br -> b
b:
  %t3 = mem.load (&int @result) : int
  %t4 = num.cmp < (int %t3, int 42) : bool
  cbr (bool %t4) -> a, done
done:
  ret
""", True),
        ]
        script = """
const fs = require('node:fs');
const mod = new WebAssembly.Module(fs.readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({ initial: 1 });
const instance = new WebAssembly.Instance(mod, { env: { memory, data: 0 }, rt: { pys_recursion_state: 0 } });
instance.exports.init();
console.log(new DataView(memory.buffer).getBigInt64(0, true).toString());
"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "case.wasm"
            for body, irreducible in cases:
                with self.subTest(irreducible=irreducible, body=body.split("\n")[0]):
                    emitter = T.Emitter(T.parse(preamble + body + "}"))
                    path.write_bytes(emitter.module())
                    # a reducible loop is a Wasm loop; only an irreducible one needs the dispatcher
                    self.assertEqual(emitter.dispatch_local >= 0, irreducible)
                    self.assertEqual(emitter.structured, not irreducible)
                    result = subprocess.check_output(["node", "-e", script, str(path)], text=True, timeout=10)
                    self.assertEqual(result.strip(), "42")

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_recursive_locals_follow_cfg_edges_and_keep_addressable_slots(self):
        text = """module complete {
  global @result type=int
}
function @main.init() -> None kind=block {
  %total.1 = slot : int
  %top.2 = slot : int
entry:
  rt entry=recursion.enter : int
  mem.store (&int %total.1, int 40)
  mem.store (&int %top.2, int 2)
  br -> setup
work:
  %t0 = scalar.bin add (int 1, int 2) : int
  br -> loop
setup:
  %t1 = mem.load (&int %total.1) : int
  br -> work
loop:
  %t2 = phi (int 0, int %t3) -> work, again : int
  %t3 = scalar.bin add (int %t2, int 1) : int
  %t4 = num.cmp < (int %t3, int 2) : bool
  cbr (bool %t4) -> again, done
again:
  br -> loop
done:
  %t5 = scalar.bin add (int %t1, int %t3) : int
  mem.store (&int @result, int %t5)
  ret
}
function @unused() -> None {
}
"""
        script = """
const mod = new WebAssembly.Module(require("node:fs").readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({ initial: 1 });
const view = new DataView(memory.buffer);
view.setBigInt64(8, 1000n, true);
const rt = {pys_recursion_state: 0, pys_recursion_error() { throw Error("depth"); }};
new WebAssembly.Instance(mod, { env: { memory, data: 64 }, rt }).exports.init();
require("node:assert/strict").equal(view.getBigInt64(64, true), 42n);
"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "recursive.wasm"
            path.write_bytes(emit(text))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
        with self.assertRaisesRegex(T.Refused, "from unknown block missing"):
            emit(text.replace("int %t3) -> work, again", "int %t3, int %t0) -> work, again, missing"))
        with self.assertRaisesRegex(T.Refused, "unequal input and predecessor counts"):
            emit(text.replace("int %t3) -> work, again", "int %t3) -> work"))

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_float_division_and_sqrt_call_the_runtime_only_to_raise(self):
        # x / y and math.sqrt(x) are Wasm instructions; the runtime's raising entries are called
        # only for a zero divisor or a number below zero (-0.0 is not), where Python raises
        text = """module complete {
  global @result type=float
  runtime fdiv
  runtime m.sqrt
}
function @main.init() -> None kind=block {
entry:
  %t0 = rt entry=fdiv (float 84.0, float 2.0) : float
  %t1 = rt entry=m.sqrt (float 1764.0) : float
  %t2 = rt entry=fdiv (float 1.0, float 0.0) : float
  %t3 = rt entry=m.sqrt (float -4.0) : float
  %t4 = rt entry=m.sqrt (float -0.0) : float
  %t5 = rt entry=fdiv (float 1.0, float -0.0) : float
  %t6 = scalar.bin fadd (float %t0, float %t1) : float
  %t7 = scalar.bin fadd (float %t6, float %t2) : float
  %t8 = scalar.bin fadd (float %t7, float %t3) : float
  %t9 = scalar.bin fadd (float %t8, float %t4) : float
  %t10 = scalar.bin fadd (float %t9, float %t5) : float
  mem.store (&float @result, float %t10)
  ret
}
"""
        script = """
const assert = require("node:assert/strict");
const mod = new WebAssembly.Module(require("node:fs").readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({ initial: 1 });
const calls = [];
const rt = {
  pys_recursion_state: 0,
  pys_fdiv: (a, b) => { calls.push(["fdiv", a, Object.is(b, -0) ? "-0" : b]); return -1; },
  pys_m_sqrt: x => { calls.push(["sqrt", x]); return -2; },
};
new WebAssembly.Instance(mod, { env: { memory, data: 64 }, rt }).exports.init();
assert.deepEqual(calls, [["fdiv", 1, 0], ["sqrt", -4], ["fdiv", 1, "-0"]]);
assert.equal(new DataView(memory.buffer).getFloat64(Number(process.argv[2]), true), 42 + 42 - 1 - 2 - 1);
"""
        emitter = T.Emitter(T.parse(text))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "float.wasm"
            path.write_bytes(bytes(emitter.module()))
            subprocess.run(["node", "-e", script, str(path), str(64 + emitter.addr["@result"])], check=True, timeout=10)

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_memmove_is_a_bulk_copy_and_c_ints_compare(self):
        # bytearray slices move bytes with llvm.memmove and compare them with memcmp's C int
        text = """module complete {
  global @a type=int
  global @b type=int
  global @result type=int
  runtime memmove
  runtime memcmp
}
function @main.init() -> None kind=block {
entry:
  mem.store (&int @a, int 4242)
  rt entry=memmove (&int @b, &int @a, int 8, %i1 false) : None
  %t0 = rt entry=memcmp (&int @a, &int @b, int 8) : %i32
  %t1 = scalar.cmp eq (%i32 %t0, %i32 0) : bool
  %t2 = scalar.cmp slt (%i32 %t0, %i32 1) : bool
  %t3 = select (bool %t1, bool %t2, bool false) : bool
  %t4 = num.cast (bool %t3) : int
  %t5 = mem.load (&int @b) : int
  %t6 = scalar.bin add (int %t4, int %t5) : int
  mem.store (&int @result, int %t6)
  ret
}
"""
        script = """
const assert = require("node:assert/strict");
const mod = new WebAssembly.Module(require("node:fs").readFileSync(process.argv[1]));
assert.deepEqual(WebAssembly.Module.imports(mod).filter(i => i.kind === "function").map(i => i.name), ["pys_wasi_memcmp"]);
const memory = new WebAssembly.Memory({ initial: 1 });
const view = new DataView(memory.buffer);
const memcmp = (a, b, n) => {
  for (let k = 0; k < Number(n); k++) {
    const d = view.getUint8(a + k) - view.getUint8(b + k);
    if (d !== 0) return d;
  }
  return 0;
};
new WebAssembly.Instance(mod, { env: { memory, data: 64 }, rt: { pys_recursion_state: 0, pys_wasi_memcmp: memcmp } }).exports.init();
assert.equal(view.getBigInt64(Number(process.argv[2]), true), 4243n);
"""
        emitter = T.Emitter(T.parse(text))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "memmove.wasm"
            path.write_bytes(bytes(emitter.module()))
            subprocess.run(["node", "-e", script, str(path), str(64 + emitter.addr["@result"])], check=True, timeout=10)

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_tuple_frames_share_and_restore_the_runtime_stack(self):
        program = """module complete {
}
function @main.init() -> None kind=block {
  %stk.1 = slot kind=2 : tuple[int,int,int]
  %stk.2 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  rt entry=on_stack (%ptr %stk.2) : int
  call callee=@inner : None
  rt entry=on_stack (%ptr %stk.1) : int
  ret
}
function @inner() -> None {
  %stk.1 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  ret.none
}
"""
        script = """
const assert = require('node:assert/strict');
const moduleBytes = require('node:fs').readFileSync(process.argv[1]);
const memory = new WebAssembly.Memory({initial: 1});
const sp = new WebAssembly.Global({value: 'i32', mutable: true}, 512);
const seen = [];
const instance = new WebAssembly.Instance(new WebAssembly.Module(moduleBytes), {
  env: {memory, data: 128},
  rt: {
    __stack_pointer: sp,
    pys_recursion_state: 0,
    pys_recursion_stack_error() { throw Error('stack floor'); },
    pys_on_stack(pointer) { seen.push([pointer, sp.value]); return 1n; },
  },
});
instance.exports.init();
assert.deepEqual(seen, [[480,480], [504,480], [464,464], [480,480]]);
assert.equal(sp.value, 512);
new DataView(memory.buffer).setBigInt64(16, 500n, true);
assert.throws(instance.exports.init, /stack floor/);
assert.equal(sp.value, 512);
assert.equal(seen.length, 4);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.wasm"
            path.write_bytes(emit(program))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)

    def test_frame_slot_refusals(self):
        program = """module complete {
}
function @main.init() -> None kind=block {
entry:
  ret
}
function @bad() -> tuple[int] {
  %stk.4 = slot kind=2 : tuple[int]
entry:
  ret (tuple[int] %stk.4)
}
"""
        with self.assertRaisesRegex(T.Refused, "return of frame slot %stk.4"):
            emit(program)
        for t in ("int", "vtuple[int]"):
            with self.subTest(t=t), self.assertRaisesRegex(T.Refused, "requires a fixed tuple"):
                emit(program.replace("slot kind=2 : tuple[int]", f"slot kind=2 : {t}"))

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_invoke_restores_tuple_and_runtime_frames_before_handler(self):
        program = """module complete exceptions {
}
function @main.init() -> None kind=block {
  %stk.1 = slot kind=2 : tuple[int]
  %h.2 = slot : exc
entry:
  br -> body
body: handler=caught
  call callee=@inner -> done, caught : None
caught:
  ~%t3 ~%t4 = landing(%addr %h.2) -> handler : exc
handler:
  %t5 = mach.load(%ptr %h.2) : exc
  rt entry=on_stack (%ptr %t5) : int
  br -> done
done:
  rt entry=on_stack (%ptr %stk.1) : int
  ret
}
function @inner() -> None {
  %stk.1 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  rt entry=list.get (list[int] null, int 0) : *int
  ret.none
}
"""
        script = """
const assert = require('node:assert/strict');
const mod = new WebAssembly.Module(require('node:fs').readFileSync(process.argv[1]));
const sp = new WebAssembly.Global({value: 'i32', mutable: true}, 512);
const tag = new WebAssembly.Tag({parameters: ['i32']});
const seen = [];
const instance = new WebAssembly.Instance(mod, {
  env: {memory: new WebAssembly.Memory({initial: 1}), data: 128, pystachy_exception: tag},
  rt: {
    __stack_pointer: sp,
    pys_recursion_state: 0,
    pys_recursion_stack_error() { throw Error('stack floor'); },
    pys_on_stack(pointer) { seen.push([pointer, sp.value]); return 1n; },
    pys_list_get() {
      sp.value -= 32; // Model a C frame whose epilogue is skipped by the exception.
      throw new WebAssembly.Exception(tag, [73]);
    },
  },
});
instance.exports.init();
assert.deepEqual(seen, [[480, 480], [73, 496], [496, 496]]);
assert.equal(sp.value, 512);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unwind.wasm"
            legacy = emit(program)
            modern = bytes(T.Emitter(T.parse(program), True).module())
            self.assertNotEqual(legacy, modern)
            path.write_bytes(legacy)
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
            # Independent feature probe: (module (func (try_table))).
            probe = "process.exit(WebAssembly.validate(Buffer.from('0061736d01000000010401600000030201000a080106001f40000b0b','hex')) ? 0 : 1)"
            if subprocess.run(["node", "-e", probe], check=False, timeout=10).returncode == 0:
                path.write_bytes(modern)
                subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
        for before, after, reason in [
            ("-> done, caught", "-> done", "exception edges"),
            ("-> done, caught", "-> done, handler", "without a landing"),
            ("slot : exc", "slot : int", "exception slot"),
        ]:
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, reason):
                emit(program.replace(before, after))

    def test_callable_indices_match_the_reactor_table(self):
        program = """module complete {
  const @cvo kind=callable refs=[@code null]
}
function @code(env: env, v: int) -> int kind=def {
entry:
  ret (int %a1)
}
function @main.init() -> None kind=block {
entry:
  %ptr1 = mach.load (callable[int,int] @cvo) : %ptr
  %answer = icall (%ptr %ptr1, env null, int 42) : int
  ret
}
"""
        output = emit(program)
        self.assertIn(b"__indirect_function_table", output)
        # A caller can receive its target as an argument without contributing
        # any local entries to the imported function table.
        external = program.replace("  const @cvo kind=callable refs=[@code null]\n", "")
        external = external.replace("  %ptr1 = mach.load (callable[int,int] @cvo) : %ptr\n", "")
        external = external.replace("%ptr %ptr1", "%ptr null")
        self.assertIn(b"__indirect_function_table", emit(external))
        for old, new, reason in (
            ("refs=[@code null]", "refs=[@unknown null]", "invalid callable constant"),
            ("refs=[@code null]", "refs=[@code @cvo]", "invalid callable constant"),
            ("@cvo kind=callable refs=[@code null]", "@x.mk.0 kind=callable refs=[null]", "invalid exception constructor table"),
            ("icall (%ptr %ptr1", "icall (int %ptr1", "invalid indirect call signature"),
        ):
            with self.subTest(new=new), self.assertRaisesRegex(T.Refused, reason):
                emit(program.replace(old, new))

    def test_exception_callback_signatures(self):
        self.assertIn(b"__indirect_function_table", emit(EXCEPTION))
        with self.assertRaisesRegex(T.Refused, "requires string names"):
            emit(EXCEPTION.replace("refs=[@s.2", "refs=[null"))
        for before, after in (("self: E", "self: int"), (" -> str kind", " -> int kind"),
                              ("@show @show null", "@show @missing null"),
                              ("@show @show null", "@show @show @show")):
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, "exception callback"):
                emit(EXCEPTION.replace(before, after))

    @unittest.skipUnless(shutil.which("node"), "node instantiates the module")
    def test_callbacks_append_to_the_reactor_table(self):
        script = """
const assert = require('node:assert/strict');
const mod = new WebAssembly.Module(require('node:fs').readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({initial: 1});
const words = new DataView(memory.buffer);
function load(data, table) {
  return new WebAssembly.Instance(mod, {env: {memory, data},
    rt: {pys_recursion_state: 0, __indirect_function_table: table}});
}
const table = new WebAssembly.Table({element: 'anyfunc', initial: 2});
const first = load(128, table);
table.set(1, first.exports.init);
load(256, table);
assert.equal(table.length, 4);
assert.equal(table.get(1), first.exports.init);
for (const [data, index] of [[128, 2], [256, 3]]) {
  assert.equal(words.getUint32(data + 8, true), index);
  assert.equal(words.getUint32(data + 12, true), index);
  assert.equal(words.getUint32(data + 16, true), 0);
  assert.equal(table.get(index)(0), data + 24); // @s.2 after the 20-byte descriptor and alignment padding
}
const fixed = new WebAssembly.Table({element: 'anyfunc', initial: 2, maximum: 2});
assert.throws(() => load(384, fixed), WebAssembly.RuntimeError);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "callback.wasm"
            path.write_bytes(emit(EXCEPTION))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_empty_key_kinds_relocate_and_preserve_the_tag(self):
        # A fresh dict takes the untagged descriptor; after a forwarded result
        # was populated its built kind must preserve the runtime's tag bit.
        program = """module complete {
  const @padding kind=tuple
  const @desc kind=string text=H0
  hole 1 type=dict[K,str]
  hole 2 type=set[int]
  keykind dict[K,str] kind="ptrtoint (ptr @desc to i64)" built="ptrtoint (ptr getelementptr (i8, ptr @desc, i64 2) to i64)"
  keykind set[K] built="ptrtoint (ptr @desc to i64)"
  keykind set[int] kind=-7 built=-7
}
function @main.init() -> None kind=block {
entry:
  %d = rt entry=dict.new hole=1 (int 0, int 0) : dict[K,str]
  %p = empty.kind hole=1 (dict[K,str] %d)
  %s = rt entry=set.new (int 0) : set[K]
  %q = empty.kind (set[K] %s)
  %n = rt entry=set.new hole=2 (int 0) : set[int]
  %r = empty.kind (set[int] %n)
  ret
}
"""
        script = """
const assert = require("node:assert/strict");
const bytes = require("node:fs").readFileSync(process.argv[1]);
const module = new WebAssembly.Module(bytes);
for (const data of [64, 128]) {
  const memory = new WebAssembly.Memory({initial: 1});
  const descriptor = BigInt(data + 8); // after the padding tuple
  const rt = {pys_recursion_state: 0, pys_dict_new(kind) {
    assert.equal(kind, descriptor);
    return 512;
  }, pys_set_new(kind) {
    assert.ok(kind === 0n || kind === -7n);
    return kind === 0n ? 544 : 560;
  }};
  new WebAssembly.Instance(module, {env: {memory, data}, rt}).exports.init();
  const view = new DataView(memory.buffer);
  assert.equal(view.getBigInt64(520, true), descriptor + 2n);
  assert.equal(view.getBigInt64(552, true), descriptor);
  assert.equal(view.getBigInt64(568, true), -7n);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kinds.wasm"
            path.write_bytes(emit(program))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
        for bad_tag in ("i64 3)", "i32 2)"):
            with self.subTest(bad_tag=bad_tag), self.assertRaisesRegex(T.Refused, "symbol"):
                emit(program.replace("i64 2)", bad_tag))
        for invalid in ("--7", "²"):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(T.Refused, "dict/set key kind"):
                emit(program.replace("built=-7", f"built={invalid}"))

    def test_refusals_name_what(self):
        cases = {
            HELLO.replace("entry=write", "entry=unknown"): "runtime entry unknown",
            HELLO.replace("module complete", "module"): "complete",
            HELLO.replace("opts=[allocelide]", "opts=[allocelide] dynamic"): "dynamic",
            HELLO.replace("  ret\n", "  %t9 = gen.start : int\n  ret\n"): "operation gen.start",
            HELLO.replace("  ret\n", "  %t9 = mach.addr element=dyntype (%ptr null, int 3) : %ptr\n  ret\n"): "mach.addr element dyntype",
            HELLO.replace("L6:\n", "L6: handler=L5\n"): "handler",
        }
        for text, what in cases.items():
            with self.assertRaises(T.Refused) as raised:
                emit(text)
            self.assertIn(what, raised.exception.what)

    def test_finalized_block_handler_syntax(self):
        program = HELLO.replace("module complete", "module complete exceptions")
        # A region can name a pad that finalization removed when it had no callers.
        self.assertEqual(emit(program), emit(program.replace("L6:", 'L6: handler="unused pad"')))
        for suffix in (" handler=", ' handler=""', ' handler="unterminated', " handler=pad extra", " handler=pad["):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(T.Refused, "handler"):
                T.parse(program.replace("L6:", "L6:" + suffix))


if __name__ == "__main__":
    unittest.main()
