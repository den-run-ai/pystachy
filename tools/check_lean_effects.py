"""Independent write-effect closure for the Lean adapters' direct calls.

Compiler summaries may be conservative, but are not evidence that the operations
visible in the same snapshot cannot mutate a guarded object. Reconstruct those
effects and retain both. Runtime contracts and address roles remain trusted.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
import sys

from check_lean_boundary import OP_KEYS, require

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler.specs import IROPS, RUNTIME  # noqa: E402

WRITES = frozenset({"wL", "wD", "wO", "wG"})


def writes(tokens):
    """The four mutable states tracked by the access model."""
    return set(WRITES if "U" in tokens or "U?" in tokens else WRITES.intersection(tokens))


def runtime_writes(operation):
    contract = RUNTIME.get(operation["text"])
    if contract is None:
        return set(WRITES)
    tokens = set(contract.split("|")[1].split())
    if "U?" in tokens:
        # Use the adapter's conservative descriptor rule, not Gen.opfx or its
        # inferred call summary. Exception classes and identity-key errors may
        # invoke user code, so preserve those possibilities too.
        if any(letter in operation["descriptor"] for letter in "OHPEA"):
            return set(WRITES)
        tokens.remove("U?")
    return writes(tokens)


def local_writes(function):
    """Body writes and direct callees, without using the compiler's analysis."""
    require(isinstance(function.get("blocks"), list), "invalid effect function blocks")
    require(all(isinstance(block, dict) and isinstance(block.get("operations"), list)
                for block in function["blocks"]), "invalid effect block")
    operations = [op for block in function["blocks"] for op in block["operations"]]
    require(isinstance(function.get("slots", []), list), "invalid effect function slots")
    for op in operations + function.get("slots", []):
        require(isinstance(op, dict) and set(op) == OP_KEYS, "invalid effect instruction fields")
        require(all(isinstance(op[key], str) for key in ("op", "text", "descriptor")),
                "invalid effect instruction name")
        require(isinstance(op["results"], list) and all(type(number) is int for number in op["results"]),
                "invalid effect results")
        require(isinstance(op["operands"], list) and all(
            isinstance(operand, dict) and isinstance(operand.get("value"), str)
            for operand in op["operands"]), "invalid effect operands")
    slots = set()
    for slot in function.get("slots", []):
        require(len(slot["results"]) == 1 and type(slot["immediate"]) is int, "invalid effect slot")
        if slot["immediate"] != 2:
            suffix = ".def" if slot["immediate"] == 1 else ""
            slots.add(f"%{slot['text'] or 'h'}{suffix}.{slot['results'][0]}")
    escaped = {operand["value"] for op in operations for position, operand in enumerate(op["operands"])
               if operand["value"] in slots and not (position == 0 and op["op"] in
                    {"mem.load", "mem.store", "mach.load", "mach.store", "landing"})}
    private = slots - escaped
    fields = {f"%t{op['results'][0]}" for op in operations
              if op["op"] == "field.addr" and len(op["results"]) == 1}
    result, callees = set(), set()
    for op in operations:
        kind = op["op"]
        if kind in {"call", "init"}:
            callees.add(op["text"] if kind == "call" else "@init." + op["text"])
        elif kind == "rt":
            result.update(runtime_writes(op))
        elif kind in {"mem.store", "mach.store"}:
            require(bool(op["operands"]), "memory store lacks its address")
            address = op["operands"][0]["value"]
            if address in private:
                continue
            if address.startswith("@"):
                result.add("wG")
            elif address in fields:
                result.add("wO")
            else:
                # Unlike the compiler's raw-memory summary, the adapter has no
                # checked guarantee that an unknown address cannot alias a global.
                result.update(WRITES)
        elif kind in {"mem.load", "mach.load"}:
            pass
        else:
            tokens = set(IROPS.get(kind, "*").split())
            result.update(WRITES if "*" in tokens else writes(tokens))
    return result, callees


def summaries(snapshot):
    """Conservative call summaries, including actual bodies and transitive calls.

Missing bodies or advertised summaries remain unknown. The reverse worklist
reaches a fixed point even for mutually recursive functions; an empty recursive
cycle cannot conceal a write reachable elsewhere in the cycle.
"""
    functions = snapshot.get("functions")
    require(isinstance(functions, list), "invalid function list for effect validation")
    by_symbol = {}
    for function in functions:
        require(isinstance(function, dict) and isinstance(function.get("symbol"), str),
                "invalid function for effect validation")
        symbol = function["symbol"]
        require(symbol not in by_symbol, "duplicate function symbol in effect validation")
        by_symbol[symbol] = function
    inferred, declared, callers = {}, {}, {symbol: set() for symbol in by_symbol}
    for symbol, function in by_symbol.items():
        body, callees = local_writes(function)
        tokens = function.get("effects")
        declared[symbol] = set(tokens.split()) if isinstance(tokens, str) else {"U"}
        inferred[symbol] = body | writes(declared[symbol])
        for callee in callees:
            if callee in by_symbol:
                callers[callee].add(symbol)
            else:
                inferred[symbol].update(WRITES)
    pending, queued = deque(inferred), set(inferred)
    while pending:
        callee = pending.popleft()
        queued.remove(callee)
        for caller in callers[callee]:
            before = len(inferred[caller])
            inferred[caller].update(inferred[callee])
            if len(inferred[caller]) != before and caller not in queued:
                pending.append(caller)
                queued.add(caller)
    return {symbol: declared[symbol] | inferred[symbol] for symbol in by_symbol}
