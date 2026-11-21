"""Check direct Wasm tuple-frame bodies against the Lean frame model."""
import io
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def unsigned(stream):
    value = 0
    for shift in range(0, 35, 7):
        byte = stream.read(1)
        if not byte:
            break
        value |= (byte[0] & 127) << shift
        if byte[0] < 128:
            return value
    raise ValueError("invalid Wasm length")


def function_body(module):
    stream = io.BytesIO(module)
    if stream.read(8) != b"\0asm\x01\0\0\0":
        raise ValueError("invalid Wasm header")
    while section := stream.read(1):
        size = unsigned(stream)
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("truncated Wasm section")
        if section == b"\x0a":
            code = io.BytesIO(data)
            if unsigned(code) == 1:
                length = unsigned(code)
                body = code.read()
                if length == len(body):
                    return body
            raise ValueError("expected one complete function body")
    raise ValueError("missing code section")


def compile_frame(arities):
    from wasm import tir_wasm

    slots = "\n".join(f"  %stk.{i} = slot kind=2 : tuple[{','.join(['int'] * n)}]"
                      for i, n in enumerate(arities))
    text = f"module complete {{\n}}\nfunction @main.init() -> None kind=block {{\n{slots}\nentry:\n  ret\n}}"
    return function_body(tir_wasm.Emitter(tir_wasm.parse(text)).module())


def main():
    source = ["import PystachyWasmFrame", "open PystachyWasmFrame"]
    # Independent tuple ABI sizes. Cover equal and distinct raw/aligned sizes,
    # an empty tuple, multiple slots, and three signed LEB immediate widths.
    for slots in [(0,), (1,), (1, 2), (8,), (1025,)]:
        size = 8 * sum(max(1, n) for n in slots)
        body = compile_frame(slots)
        source.append(f"#guard matchesBody {size} {list(body)}")
    original = compile_frame((1,))
    for before, after in [
        (b"\x29\x03\x10", b"\x29\x03\x08"),  # load the recursion limit instead of the floor
        (b"\xad", b"\xac"),                    # sign-extend the old pointer
        (b"\x7c\x54", b"\x7c\x53"),            # signed comparison
        (b"\x41\x10\x6a", b"\x41\x20\x6a"),    # restore a different frame size
    ]:
        if original.count(before) != 1:
            raise ValueError("mutation did not match the frame fixture once")
        mutated = original.replace(before, after)
        source.append(f"#guard !matchesBody 8 {list(mutated)}")
    subprocess.run(["lake", "env", "lean", "--stdin"], cwd=ROOT / "tools/lean_boundary",
                   input="\n".join(source) + "\n", text=True, check=True)


if __name__ == "__main__":
    main()
