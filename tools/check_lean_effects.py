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
from src.pystachy_compiler.utils import is_tuple, targs, tslots  # noqa: E402

WRITES = frozenset({"wL", "wD", "wO", "wG"})
# runtime.c's allocators (pys_alloc, pys_alloc_atomic, pys_new: malloc, returns_nonnull), sized in
# bytes by their one operand.
FRESH_RUNTIME = frozenset({"alloc", "alloc_atomic", "new"})
WORD = 8
ELEMENT_BYTES = {"int": 8, "%ptr": 8, "%byte": 1}  # (mach.addr's element types, ircheck.py)
# The address of a numeric result's identity box: each caller passes a dyn slot it allocates
# (calls.py's idresult), or forwards its own (lowering.py's recursion and tuple wrappers).
IDENTITY_RETURN = "%idret"


def literal(value):
    try:
        return int(value)
    except ValueError:
        return None


def fresh_addresses(operations):
    """Addresses inside memory this body allocates itself: a register an allocator returns (a
    fixed object's or tuple's alloc.fixed, or a runtime allocation of a literal byte size) and a
    field of such an object or a word at a literal index within such a tuple or allocation (a
    fixed tuple has lowering.py's 8 * tslots bytes). A store there changes
    nothing that existed when the function was called, which is all its callers' facts describe
    (each execution of an allocation is new memory). Any other derivation, such as a phi, a
    select, a load or a computed index, is not fresh."""
    sizes, fresh = {}, set()
    for op in operations:
        if op["op"] == "alloc.fixed" and len(op["results"]) == 1:
            fresh.add(f"%t{op['results'][0]}")
            if is_tuple(op["type"]) and op["type"].endswith("]") and "..." not in targs(op["type"]):
                sizes[f"%t{op['results'][0]}"] = WORD * tslots(op["type"])
        elif (op["op"] == "rt" and op["text"] in FRESH_RUNTIME and len(op["results"]) == 1
              and len(op["operands"]) == 1):
            size = literal(op["operands"][0]["value"])
            if size is not None and size > 0:
                sizes[f"%t{op['results'][0]}"] = size
                fresh.add(f"%t{op['results'][0]}")
    changed = True
    while changed:
        changed = False
        for op in operations:
            if len(op["results"]) != 1 or f"%t{op['results'][0]}" in fresh or not op["operands"]:
                continue
            base = op["operands"][0]["value"]
            derived = False
            if op["op"] == "field.addr" and len(op["operands"]) == 1:
                # (a field of an object: the IR types it, and the object is base's)
                derived = base in fresh and base not in sizes
            elif op["op"] == "mach.addr" and len(op["operands"]) == 2 and base in sizes:
                # (getelementptr of the element type: a word, or a byte; a word store at a byte
                # index must still end inside the allocation)
                index = literal(op["operands"][1]["value"])
                width = ELEMENT_BYTES.get(op["text"])
                derived = (width is not None and index is not None and 0 <= index
                           and index * width + WORD <= sizes[base])
            if derived:
                fresh.add(f"%t{op['results'][0]}")
                changed = True
    return fresh


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


def slot_names(function):
    """A function's own stack slots (each an alloca of its frame), as operands name them."""
    slots = set()
    for slot in function.get("slots", []):
        require(isinstance(slot, dict) and isinstance(slot.get("results"), list) and len(slot["results"]) == 1
                and type(slot.get("immediate")) is int and isinstance(slot.get("text"), str), "invalid effect slot")
        if slot["immediate"] != 2:
            suffix = ".def" if slot["immediate"] == 1 else ""
            slots.add(f"%{slot['text'] or 'h'}{suffix}.{slot['results'][0]}")
    return slots


def local_writes(function, identity_slot=False):
    """Body writes and direct callees, without using the compiler's analysis. identity_slot: every
    direct call of the function passes a slot of its caller as the identity-return buffer
    (summaries checks this), so storing through %idret writes no state of its caller."""
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
    slots = slot_names(function)
    fields = {f"%t{op['results'][0]}" for op in operations
              if op["op"] == "field.addr" and len(op["results"]) == 1}
    fresh = fresh_addresses(operations)
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
            if address in slots or address in fresh or (identity_slot and address == IDENTITY_RETURN):
                # (the function's own stack slots, escaped or not, which no global, object, list
                # or dict shares; memory it allocated; and its caller's identity-return slot)
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
    # A function that stores through %idret writes the identity-return buffer its caller passes
    # last (calls.py's idresult: a dyn slot it allocates). That is no state of the caller only where
    # every direct call in the snapshot passes one of its own slots, its own %idret (forwarding a
    # buffer) or null; any other argument keeps the store unknown.
    returners = {symbol for symbol, function in by_symbol.items()
                 if any(isinstance(operand, dict) and operand.get("value") == IDENTITY_RETURN
                        for block in function.get("blocks", []) if isinstance(block, dict)
                        for op in block.get("operations", []) if isinstance(op, dict)
                        for operand in op.get("operands", []))}
    unverified = set()
    for function in by_symbol.values():
        own = slot_names(function)
        for block in function.get("blocks", []):
            for op in block.get("operations", []) if isinstance(block, dict) else []:
                if isinstance(op, dict) and op.get("op") == "call" and op.get("text") in returners:
                    last = op["operands"][-1] if op.get("operands") else {}
                    if not (last.get("type") == "*dyn"
                            and (last.get("value") in own or last.get("value") in (IDENTITY_RETURN, "null"))):
                        unverified.add(op["text"])
    inferred, declared, callers = {}, {}, {symbol: set() for symbol in by_symbol}
    for symbol, function in by_symbol.items():
        body, callees = local_writes(function, symbol in returners and symbol not in unverified)
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
