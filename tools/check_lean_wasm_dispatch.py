"""Bind the Lean object callback layout to the emitter's start, element, code and data sections."""
from pathlib import Path
import subprocess

from check_lean_wasm_frame import function_bodies, sections
from wasm import tir_wasm


def compile_dispatch():
    # The one-byte global forces padding before the rows. Text declaration
    # order, numeric class ID order and function index order are all distinct.
    text = """module complete objects=[B:1 A:0] compared=[A] hashed=[B] {
  class A
  class B
  global @pad type=bool
}
function @main.init() -> None kind=block {
entry:
  ret
}
"""
    for name, params, result in [
        ("hash.B", ["B"], "int 37"),
        ("repr.B", ["B", "B"], "str null"),
        ("cmp.A", ["int", "A", "A"], "bool true"),
        ("eq.A", ["A", "A"], "bool false"),
        ("repr.A", ["A", "A"], "str null"),
    ]:
        signature = ", ".join(f"%p{i}: {t}" for i, t in enumerate(params))
        text += (f"function @o.{name}({signature}) -> {result.split()[0]} kind=class {{\n"
                 f"entry:\n  ret ({result})\n}}\n")
    return tir_wasm.Emitter(tir_wasm.parse(text)).module()


def main():
    binary = dict(sections(compile_dispatch()))
    bodies = list(function_bodies(binary[10]))
    # The setter is the fixture's only function import. Function 7 is start,
    # defined after init (1) and the five callbacks (2 through 6).
    if len(bodies) != 7:
        raise ValueError("unexpected function count in object-dispatch fixture")
    fields = {"start": binary[8], "elems": binary[9], "body": bodies[6], "data": binary[11]}
    checks = ["import PystachyWasmDispatch", "open PystachyWasmDispatch"]
    for key, data in fields.items():
        checks.append(f"def {key} : List Nat := {list(data)}")
    checks.append("#guard matchesFixture start elems body data")
    # Wrong element target, store into an absent field, truncated pointer store,
    # wrong registered row count, and nonzero data in an absent field.
    for field, marker, idx, replacement in [
        ("elems", bytes([6, 5, 4]), 1, 4),
        ("body", bytes([0x36, 2, 36]), 2, 32),
        ("body", bytes([0x36, 2, 12]), 0, 0x3a),
        ("body", bytes([0x41, 2, 0x10]), 1, 1),
    ]:
        data = fields[field]
        if data.count(marker) != 1:
            raise ValueError("mutation did not match the dispatch fixture once")
        at = data.index(marker) + idx
        args = " ".join(f"({key}.set {at} {replacement})" if key == field else key for key in fields)
        checks.append(f"#guard !matchesFixture {args}")
    # Last 12 bytes start at the absent eq slot in class 1.
    checks.append(f"#guard !matchesFixture start elems body (data.set {len(binary[11]) - 12} 1)")
    subprocess.run(["lake", "env", "lean", "--stdin"], cwd=Path(__file__).parent / "lean_boundary",
                   input="\n".join(checks) + "\n", text=True, check=True)


if __name__ == "__main__":
    main()
