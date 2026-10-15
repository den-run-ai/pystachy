"""LLVM serialization helpers for native ABI declarations and byte constants."""
from __future__ import annotations
from src.pystachy_compiler.specs import HEX


def llvm_decl(symbol: str, signature: list[str]) -> str:
    return f"declare {signature[0]} @{symbol}({', '.join(signature[1:])})"


def llstr(s: str) -> str:
    out: list[str] = []
    for c in s:
        o = ord(c)
        if o < 32 or o > 126 or c == '"' or c == "\\":
            out.append("\\" + HEX[o >> 4] + HEX[o & 15])
        else:
            out.append(c)
    return "".join(out)

